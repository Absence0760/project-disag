"""AWS Lambda handler that exposes disag + exceed over HTTP.

Wired behind API Gateway HTTP API (v2 payload format). All file
input/output flows through S3 — uploads are pre-signed PUTs, results
are pre-signed GETs. Lambda's /tmp is the scratch dir; the runs and
output buckets keep the artefacts.

Routes
------
POST /upload         → { filename }                       → presigned PUT
POST /disag          → DisagRequest                       → RunResult
POST /exceed         → ExceedRequest                      → RunResult
GET  /runs                                                → [RunSummary]
GET  /runs/{run_id}                                       → RunResult

Environment
-----------
INPUTS_BUCKET    Bucket for user-uploaded inputs (presigned PUT target)
OUTPUTS_BUCKET   Bucket for run outputs + reports
PRESIGN_TTL      Seconds for presigned URLs (default 3600)
ALLOWED_ORIGIN   CORS allow-origin (default '*' — narrow in prod)
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

# disag/ and exceed/ are packaged into the Lambda zip alongside this
# file by web/backend/build.sh. The Pascal port is pure stdlib — see
# project root CLAUDE.md.
sys.path.insert(0, os.path.dirname(__file__))

from disag.algorithm import (  # noqa: E402
    METHOD_NAMES,
    NO_FILES,
    DisagMethod,
    disaggregate,
)
from disag.files import read_daily_file, read_monthly_file, write_daily_file  # noqa: E402
from disag.report import write_report  # noqa: E402
from exceed.algorithm import calculate_monthly_exceedance  # noqa: E402
from exceed.files import (  # noqa: E402
    read_daily_file as exceed_read_daily,
    read_monthly_file as exceed_read_monthly,
    write_exceedance_report,
)

INPUTS_BUCKET = os.environ['INPUTS_BUCKET']
OUTPUTS_BUCKET = os.environ['OUTPUTS_BUCKET']
PRESIGN_TTL = int(os.environ.get('PRESIGN_TTL', '3600'))
ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', '*')

_s3_client = None


def s3():
    # Lazy so module import doesn't require AWS creds (lets CI run an
    # import smoke test without stubbing boto3 deeply).
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client

# Inputs are written under inputs/<uuid>/<original-name>; outputs under
# runs/<run_id>/{output.day,output.rep} — see history listing below.
SAFE_FILENAME = re.compile(r'[^A-Za-z0-9._-]')


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('rawPath', '/')

    if method == 'OPTIONS':
        return _respond(204, '')

    try:
        if method == 'POST' and path == '/upload':
            return _respond(200, _handle_upload(_body(event)))
        if method == 'POST' and path == '/disag':
            return _respond(200, _handle_disag(_body(event)))
        if method == 'POST' and path == '/exceed':
            return _respond(200, _handle_exceed(_body(event)))
        if method == 'GET' and path == '/runs':
            return _respond(200, _handle_list_runs())
        if method == 'GET' and path.startswith('/runs/'):
            run_id = path.split('/', 2)[2]
            return _respond(200, _handle_get_run(run_id))
        return _respond(404, {'error': f'No route for {method} {path}'})
    except _ClientError as exc:
        return _respond(exc.status, {'error': str(exc)})
    except Exception as exc:  # noqa: BLE001 — surface unexpected failures
        traceback.print_exc()
        return _respond(500, {'error': f'{type(exc).__name__}: {exc}'})


class _ClientError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get('body') or '{}'
    if event.get('isBase64Encoded'):
        raw = base64.b64decode(raw).decode('utf-8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _ClientError(400, f'Invalid JSON body: {exc}') from exc


def _respond(status: int, body: Any) -> dict[str, Any]:
    payload = body if isinstance(body, str) else json.dumps(body)
    return {
        'statusCode': status,
        'headers': {
            'content-type': 'application/json',
            'access-control-allow-origin': ALLOWED_ORIGIN,
            'access-control-allow-methods': 'GET, POST, OPTIONS',
            'access-control-allow-headers': 'content-type',
        },
        'body': payload,
    }


# ── /upload ──────────────────────────────────────────────────────────


def _handle_upload(body: dict[str, Any]) -> dict[str, Any]:
    filename = body.get('filename')
    if not filename or not isinstance(filename, str):
        raise _ClientError(400, 'filename is required')
    safe = SAFE_FILENAME.sub('_', filename)
    key = f'inputs/{uuid.uuid4()}/{safe}'
    url = s3().generate_presigned_url(
        'put_object',
        Params={'Bucket': INPUTS_BUCKET, 'Key': key},
        ExpiresIn=PRESIGN_TTL,
    )
    return {'key': key, 'url': url, 'expires_in': PRESIGN_TTL}


# ── /disag ───────────────────────────────────────────────────────────


def _handle_disag(body: dict[str, Any]) -> dict[str, Any]:
    method_id = body.get('method', 0)
    try:
        dm = DisagMethod(int(method_id))
    except ValueError as exc:
        raise _ClientError(400, f'Invalid method: {method_id}') from exc

    min_files = NO_FILES[dm]
    monthly_key = body.get('monthly_key')
    daily1_key = body.get('daily1_key')
    daily2_key = body.get('daily2_key')

    if not monthly_key:
        raise _ClientError(400, 'monthly_key is required')
    if min_files >= 1 and not daily1_key:
        raise _ClientError(400, 'daily1_key is required for this method')
    if min_files >= 2 and not daily2_key:
        raise _ClientError(400, 'daily2_key is required for this method')

    use_daily2 = min_files >= 2 or (
        dm == DisagMethod.PATCH_EXCEED and bool(daily2_key)
    )
    no_files = 2 if use_daily2 else min_files

    run_id = _new_run_id()
    workdir = Path(f'/tmp/{run_id}')
    workdir.mkdir(parents=True, exist_ok=True)

    monthly_path = _download(monthly_key, workdir)
    gen_monthly = read_monthly_file(str(monthly_path))

    obs_daily: list[dict] = [{}, {}]
    daily1_path = None
    daily2_path = None
    if no_files >= 1:
        daily1_path = _download(daily1_key, workdir)
        obs_daily[0] = read_daily_file(str(daily1_path))
    if use_daily2:
        daily2_path = _download(daily2_key, workdir)
        obs_daily[1] = read_daily_file(str(daily2_path))

    records, report_lines = disaggregate(dm, gen_monthly, obs_daily, no_files)

    output_path = workdir / 'output.day'
    report_path = workdir / 'output.rep'
    header_info = {
        'monthly_file': monthly_path.name,
        'daily_file_1': daily1_path.name if daily1_path else '',
        'daily_file_2': daily2_path.name if daily2_path else '',
        'method_str': METHOD_NAMES[dm],
    }
    write_daily_file(str(output_path), records, header_info)
    write_report(str(report_path), dm, report_lines, records)

    return _publish_run(run_id, 'disag', output=output_path, report=report_path)


# ── /exceed ──────────────────────────────────────────────────────────


def _handle_exceed(body: dict[str, Any]) -> dict[str, Any]:
    monthly_key = body.get('monthly_key')
    daily_key = body.get('daily_key')
    intervals = int(body.get('intervals', 20))
    if not monthly_key and not daily_key:
        raise _ClientError(400, 'At least one of monthly_key or daily_key is required')

    run_id = _new_run_id()
    workdir = Path(f'/tmp/{run_id}')
    workdir.mkdir(parents=True, exist_ok=True)

    # Mirror exceed/__main__.py: compute one ExceedanceResult per
    # calendar month for monthly input, plus per-month for daily
    # input (keyed `daily_<month>`).
    monthly_exceedance: dict = {}
    if monthly_key:
        monthly_data = exceed_read_monthly(str(_download(monthly_key, workdir)))
        for month in range(1, 13):
            series = monthly_data.get(month)
            if not series:
                continue
            r = calculate_monthly_exceedance(series, intervals)
            monthly_exceedance[month] = _result_to_dict(r)
    if daily_key:
        daily_data = exceed_read_daily(str(_download(daily_key, workdir)))
        for month in range(1, 13):
            series = daily_data.get(month)
            if not series:
                continue
            r = calculate_monthly_exceedance(series, intervals)
            monthly_exceedance[f'daily_{month}'] = _result_to_dict(r)

    if not monthly_exceedance:
        raise _ClientError(400, 'No data found in the supplied input(s)')

    report_path = workdir / 'output.rep'
    write_exceedance_report(str(report_path), monthly_exceedance)

    return _publish_run(run_id, 'exceed', output=None, report=report_path)


def _result_to_dict(r: Any) -> dict[str, Any]:
    return {
        'flow_values': r.flow_values,
        'exceedance_pct': r.exceedance_pct,
        'count_above': r.count_above,
        'count_below': r.count_below,
        'total_count': r.total_count,
    }


# ── /runs ────────────────────────────────────────────────────────────


def _handle_list_runs() -> list[dict[str, Any]]:
    paginator = s3().get_paginator('list_objects_v2')
    runs: dict[str, dict[str, Any]] = {}
    for page in paginator.paginate(Bucket=OUTPUTS_BUCKET, Prefix='runs/'):
        for obj in page.get('Contents', []):
            # runs/<tool>/<run_id>/<file>
            parts = obj['Key'].split('/')
            if len(parts) < 4:
                continue
            _, tool, run_id, _name = parts[0], parts[1], parts[2], parts[3]
            entry = runs.setdefault(
                run_id,
                {
                    'run_id': run_id,
                    'tool': tool,
                    'created_at': obj['LastModified'].astimezone(timezone.utc).isoformat(),
                    'size_bytes': 0,
                },
            )
            entry['size_bytes'] += obj['Size']
    # Newest first.
    return sorted(runs.values(), key=lambda r: r['created_at'], reverse=True)


def _handle_get_run(run_id: str) -> dict[str, Any]:
    # Find under runs/<tool>/<run_id>/. List both tools to handle
    # either case without storing a manifest.
    for tool in ('disag', 'exceed'):
        prefix = f'runs/{tool}/{run_id}/'
        resp = s3().list_objects_v2(Bucket=OUTPUTS_BUCKET, Prefix=prefix)
        contents = resp.get('Contents', [])
        if not contents:
            continue
        output_key = next((c['Key'] for c in contents if c['Key'].endswith('.day')), None)
        report_key = next((c['Key'] for c in contents if c['Key'].endswith('.rep')), None)
        if not report_key:
            raise _ClientError(500, f'Run {run_id} is missing its report')
        created = min(c['LastModified'] for c in contents).astimezone(timezone.utc).isoformat()
        return {
            'run_id': run_id,
            'tool': tool,
            'created_at': created,
            'output_key': output_key,
            'report_key': report_key,
            'output_url': _presign_get(output_key) if output_key else None,
            'report_url': _presign_get(report_key),
        }
    raise _ClientError(404, f'No run {run_id}')


# ── helpers ──────────────────────────────────────────────────────────


def _new_run_id() -> str:
    # Sortable + unique. Lambda's /tmp can persist between warm
    # invocations, so the random suffix avoids collisions if two
    # invocations share a container.
    return f'{int(time.time())}-{uuid.uuid4().hex[:8]}'


def _download(key: str, workdir: Path) -> Path:
    local = workdir / Path(key).name
    s3().download_file(INPUTS_BUCKET, key, str(local))
    return local


def _publish_run(
    run_id: str,
    tool: str,
    *,
    output: Path | None,
    report: Path,
) -> dict[str, Any]:
    base = f'runs/{tool}/{run_id}'
    output_key = None
    if output:
        output_key = f'{base}/output.day'
        s3().upload_file(str(output), OUTPUTS_BUCKET, output_key)
    report_key = f'{base}/output.rep'
    s3().upload_file(str(report), OUTPUTS_BUCKET, report_key)
    return {
        'run_id': run_id,
        'tool': tool,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'output_key': output_key,
        'report_key': report_key,
        'output_url': _presign_get(output_key) if output_key else None,
        'report_url': _presign_get(report_key),
    }


def _presign_get(key: str) -> str:
    return s3().generate_presigned_url(
        'get_object',
        Params={'Bucket': OUTPUTS_BUCKET, 'Key': key},
        ExpiresIn=PRESIGN_TTL,
    )
