"""AWS Lambda handler that exposes disag + exceed over HTTP.

Wired behind API Gateway HTTP API (v2 payload format). All file
input/output flows through S3 — uploads are pre-signed POSTs with
size/content-type conditions, results are pre-signed GETs.

Multi-user model
----------------
No accounts: the browser generates a UUID v4 on first visit, stashes
it in localStorage, and sends it on every API call as `X-Client-Id`.
The backend uses that UUID to scope:

  - inputs : inputs/<client_id>/<uuid>/<safe-filename>
  - outputs: runs/<tool>/<client_id>/<run_id>/{output.day,output.rep}

A client never sees runs that don't carry its own client_id in the
key. Clearing the browser nukes history (no cross-device sync — the
trade-off for not requiring sign-up).

Routes
------
POST /upload         → { filename }                → presigned POST (form-fields)
POST /disag          → DisagRequest                → RunResult
POST /exceed         → ExceedRequest               → RunResult
POST /convert        → ConvertRequest              → RunResult
GET  /runs                                         → [RunSummary]   (scoped to caller)
GET  /runs/{run_id}                                → RunResult      (must match caller)

Environment
-----------
INPUTS_BUCKET     Bucket for user-uploaded inputs (presigned POST target)
OUTPUTS_BUCKET    Bucket for run outputs + reports
UPLOAD_TTL        Seconds for presigned POST URLs (default 300)
DOWNLOAD_TTL      Seconds for presigned GET URLs  (default 600)
MAX_UPLOAD_BYTES  Per-file upload size cap        (default 10 MiB)
ALLOWED_ORIGIN    CORS allow-origin — unset = no CORS header emitted
                  (production should set this explicitly to the CloudFront URL)
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
from disag.convert import ans_to_mon  # noqa: E402
from disag.files import read_daily_file, read_monthly_file, write_daily_file  # noqa: E402
from disag.report import write_report  # noqa: E402
from exceed.algorithm import calculate_monthly_exceedance  # noqa: E402
from exceed.files import (  # noqa: E402
    read_daily_file as exceed_read_daily,
    read_monthly_file as exceed_read_monthly,
    write_exceedance_report,
)

# Tools that publish runs under runs/<tool>/<client_id>/<run_id>/. Adding a
# new tool means adding it here so /runs and /runs/{id} can find it.
TOOLS = ('disag', 'exceed', 'convert')

# Bucket names are not required at import time so the local dev shim
# can boot without AWS config — the page loads and the user gets a
# clear per-request error instead of a cryptic ImportError. Production
# Lambda always has these set (see web/infra/lambda.tf).
INPUTS_BUCKET = os.environ.get('INPUTS_BUCKET')
OUTPUTS_BUCKET = os.environ.get('OUTPUTS_BUCKET')

# Two TTLs because uploads need shorter URLs (the captured-URL replay
# window is the main wallet-bleed risk on presigns) than downloads
# (operators page through history pages and re-download reports).
UPLOAD_TTL = int(os.environ.get('UPLOAD_TTL', '300'))
DOWNLOAD_TTL = int(os.environ.get('DOWNLOAD_TTL', '600'))

# Hard cap enforced via the presigned POST policy. The S3 PUT path
# does NOT support size conditions, which is why uploads use POST.
MAX_UPLOAD_BYTES = int(os.environ.get('MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))

# Intentionally no default — emitting `*` would let an attacker host a
# malicious page that posts to our API on a victim's behalf. Production
# Lambda env sets this to the CloudFront URL; local dev sets it via
# local_server.py.
ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN')

CLIENT_ID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)
RUN_ID_RE = re.compile(r'^\d+-[0-9a-f]{8}$')

# CloudFront stamps every /api/* request with this header at the
# origin layer (see web/infra/cloudfront.tf:custom_header). If the
# env var is set, the handler requires it on every non-OPTIONS
# request — so the bare API Gateway URL (a long .execute-api host
# that bypasses WAF + the rate-limit rule) is unreachable. Unset
# in local dev so curl/Playwright don't need to inject the header.
CLOUDFRONT_SHARED_SECRET = os.environ.get('CLOUDFRONT_SHARED_SECRET')

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

    # CloudFront's `/api/*` behaviour forwards the full path to API
    # Gateway, which means production requests arrive as `/api/upload`
    # etc. The route table below uses bare `/upload` so both prefixes
    # work — strip a leading `/api` if present.
    if path.startswith('/api/') or path == '/api':
        path = path[len('/api'):] or '/'

    if method == 'OPTIONS':
        return _respond(204, '')

    try:
        _require_cloudfront(event)
        client_id = _client_id(event)

        if method == 'POST' and path == '/upload':
            return _respond(200, _handle_upload(client_id, _body(event)))
        if method == 'POST' and path == '/disag':
            return _respond(200, _handle_disag(client_id, _body(event)))
        if method == 'POST' and path == '/exceed':
            return _respond(200, _handle_exceed(client_id, _body(event)))
        if method == 'POST' and path == '/convert':
            return _respond(200, _handle_convert(client_id, _body(event)))
        if method == 'GET' and path == '/runs':
            return _respond(200, _handle_list_runs(client_id))
        if method == 'GET' and path.startswith('/runs/'):
            run_id = path.split('/', 2)[2]
            return _respond(200, _handle_get_run(client_id, run_id))
        return _respond(404, {'error': f'No route for {method} {path}'})
    except _ClientError as exc:
        return _respond(exc.status, {'error': str(exc)})
    except Exception:  # noqa: BLE001 — surface unexpected failures
        # Log the full traceback to CloudWatch for triage, but never
        # leak class names, file paths, or AWS request IDs to the HTTP
        # caller. The audit flagged the previous `{type(exc).__name__}:
        # {exc}` shape as info-disclosure (A09).
        traceback.print_exc()
        return _respond(500, {'error': 'Internal server error'})


def _require_cloudfront(event: dict[str, Any]) -> None:
    """Reject requests that didn't come through CloudFront.

    CloudFront stamps every request with a shared secret header
    (web/infra/cloudfront.tf). A bare-API-Gateway-URL hit won't have
    it. Locally CLOUDFRONT_SHARED_SECRET is unset and the check
    becomes a no-op.

    Compares with hmac.compare_digest to dodge timing-leak nags from
    static analysers; the value is opaque and high-entropy, so
    practical attack value is near zero either way.
    """
    if not CLOUDFRONT_SHARED_SECRET:
        return
    headers = event.get('headers') or {}
    sent = headers.get('x-cloudfront-shared-secret') or headers.get(
        'X-CloudFront-Shared-Secret', ''
    )
    import hmac
    if not isinstance(sent, str) or not hmac.compare_digest(
        sent, CLOUDFRONT_SHARED_SECRET
    ):
        raise _ClientError(403, 'Forbidden')


def _client_id(event: dict[str, Any]) -> str:
    """Extract + validate the per-browser client ID.

    API Gateway lowercases header names; some intermediaries don't.
    Accept both shapes. The value must be a UUID — strict regex match
    so a caller can't smuggle path separators or wildcards into the
    S3 prefix.
    """
    headers = event.get('headers') or {}
    cid = headers.get('x-client-id') or headers.get('X-Client-Id') or ''
    if not isinstance(cid, str) or not CLIENT_ID_RE.match(cid):
        raise _ClientError(
            400,
            'X-Client-Id header is required and must be a UUID v4',
        )
    return cid


class _ClientError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _require_buckets() -> None:
    if not INPUTS_BUCKET or not OUTPUTS_BUCKET:
        raise _ClientError(
            503,
            'Backend not fully configured: set INPUTS_BUCKET and OUTPUTS_BUCKET '
            'to S3 buckets you can read/write. See web/README.md.',
        )


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
    headers = {
        'content-type': 'application/json',
        'access-control-allow-methods': 'GET, POST, OPTIONS',
        'access-control-allow-headers': 'content-type, x-client-id',
    }
    # Only advertise CORS when a specific origin is configured. Emitting
    # `*` by default would let any third-party page POST to our API on
    # a victim's behalf — see ALLOWED_ORIGIN comment at top.
    if ALLOWED_ORIGIN:
        headers['access-control-allow-origin'] = ALLOWED_ORIGIN
    return {
        'statusCode': status,
        'headers': headers,
        'body': payload,
    }


# ── /upload ──────────────────────────────────────────────────────────


def _handle_upload(client_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _require_buckets()
    filename = body.get('filename')
    if not filename or not isinstance(filename, str):
        raise _ClientError(400, 'filename is required')
    safe = SAFE_FILENAME.sub('_', filename)
    key = f'inputs/{client_id}/{uuid.uuid4()}/{safe}'
    # generate_presigned_post (NOT _url) is the only S3 signing form
    # that supports `content-length-range`. The POST policy is enforced
    # by S3 server-side — an oversized PUT to the returned URL fails
    # before any object is created.
    presigned = s3().generate_presigned_post(
        Bucket=INPUTS_BUCKET,
        Key=key,
        Conditions=[
            ['content-length-range', 1, MAX_UPLOAD_BYTES],
            ['starts-with', '$Content-Type', ''],
        ],
        ExpiresIn=UPLOAD_TTL,
    )
    return {
        'key': key,
        'url': presigned['url'],
        'fields': presigned['fields'],
        'expires_in': UPLOAD_TTL,
        'max_bytes': MAX_UPLOAD_BYTES,
    }


def _validate_input_key(client_id: str, key: Any) -> str:
    """Reject any submitted *_key that doesn't live under the caller's
    inputs/<client_id>/ prefix. Without this check a client could pass
    another client's key and have the Lambda fetch it — cross-user
    data read.
    """
    if not isinstance(key, str) or not key:
        raise _ClientError(400, 'Input key is required')
    expected_prefix = f'inputs/{client_id}/'
    if not key.startswith(expected_prefix):
        raise _ClientError(
            403,
            'Input key does not belong to this client',
        )
    # Defence-in-depth: also reject anything that contains traversal
    # sequences. S3 keys are opaque strings so `..` is treated as a
    # literal segment, but stripping it cuts off a footgun if the key
    # is ever joined into a filesystem path locally.
    if '..' in key.split('/'):
        raise _ClientError(400, 'Invalid input key')
    return key


# ── /disag ───────────────────────────────────────────────────────────


def _handle_disag(client_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _require_buckets()
    method_id = body.get('method', 0)
    try:
        dm = DisagMethod(int(method_id))
    except ValueError as exc:
        raise _ClientError(400, f'Invalid method: {method_id}') from exc

    min_files = NO_FILES[dm]

    if not body.get('monthly_key'):
        raise _ClientError(400, 'monthly_key is required')
    monthly_key = _validate_input_key(client_id, body.get('monthly_key'))

    daily1_key = None
    if min_files >= 1:
        if not body.get('daily1_key'):
            raise _ClientError(400, 'daily1_key is required for this method')
        daily1_key = _validate_input_key(client_id, body.get('daily1_key'))

    daily2_key = None
    use_daily2 = min_files >= 2 or (
        dm == DisagMethod.PATCH_EXCEED and bool(body.get('daily2_key'))
    )
    if min_files >= 2:
        if not body.get('daily2_key'):
            raise _ClientError(400, 'daily2_key is required for this method')
        daily2_key = _validate_input_key(client_id, body.get('daily2_key'))
    elif use_daily2:
        daily2_key = _validate_input_key(client_id, body.get('daily2_key'))

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

    return _publish_run(
        client_id, run_id, 'disag', output=output_path, report=report_path,
    )


# ── /exceed ──────────────────────────────────────────────────────────


def _handle_exceed(client_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _require_buckets()
    monthly_key_raw = body.get('monthly_key')
    daily_key_raw = body.get('daily_key')
    if not monthly_key_raw and not daily_key_raw:
        raise _ClientError(400, 'At least one of monthly_key or daily_key is required')

    monthly_key = _validate_input_key(client_id, monthly_key_raw) if monthly_key_raw else None
    daily_key = _validate_input_key(client_id, daily_key_raw) if daily_key_raw else None

    # Clamp intervals to a sane range BEFORE it reaches the algorithm.
    # intervals == 0 → ZeroDivisionError inside ExceedanceCalculator;
    # a huge value (e.g. 2**30) → counts-list allocation OOMs the
    # Lambda. Bounding here turns both into a 400.
    try:
        intervals = int(body.get('intervals', 20))
    except (TypeError, ValueError) as exc:
        raise _ClientError(400, 'intervals must be an integer') from exc
    if not (1 <= intervals <= 1000):
        raise _ClientError(400, 'intervals must be between 1 and 1000')

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

    return _publish_run(client_id, run_id, 'exceed', output=None, report=report_path)


def _result_to_dict(r: Any) -> dict[str, Any]:
    return {
        'flow_values': r.flow_values,
        'exceedance_pct': r.exceedance_pct,
        'count_above': r.count_above,
        'count_below': r.count_below,
        'total_count': r.total_count,
    }


# ── /convert ─────────────────────────────────────────────────────────


def _handle_convert(client_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _require_buckets()
    if not body.get('ans_key'):
        raise _ClientError(400, 'ans_key is required')
    ans_key = _validate_input_key(client_id, body.get('ans_key'))

    run_id = _new_run_id()
    workdir = Path(f'/tmp/{run_id}')
    workdir.mkdir(parents=True, exist_ok=True)

    src_path = _download(ans_key, workdir)
    out_path = workdir / 'output.mon'
    report_path = workdir / 'output.rep'

    try:
        result = ans_to_mon(str(src_path), str(out_path))
    except (OSError, ValueError) as exc:
        # ValueError from ans_to_mon → caller-supplied bad input → 400.
        # OSError on /tmp read/write → almost always a malformed upload
        # the tool can't open → also 400. In either case the underlying
        # exception message embeds the Lambda's /tmp/<run_id>/ path
        # (audit A09 — info disclosure), so we keep the wire response
        # generic and log the detail server-side for triage.
        print(f'convert failed for {ans_key}: {exc}')
        raise _ClientError(
            400,
            'Conversion failed: the file could not be read as a monthly '
            'streamflow file in the source layout.',
        ) from exc

    _write_convert_report(
        report_path,
        src_name=src_path.name,
        out_name=out_path.name,
        result=result,
    )

    return _publish_run(
        client_id, run_id, 'convert', output=out_path, report=report_path,
    )


def _write_convert_report(
    report_path: Path,
    *,
    src_name: str,
    out_name: str,
    result: Any,
) -> None:
    """Mirror the disag/exceed .rep style — a small text log of the run."""
    lines = [
        'Monthly file format conversion',
        '',
        f'Source file : {src_name}',
        f'Output file : {out_name}',
        f'Rows written: {result.rows_written}',
        f'First year  : {result.first_year}',
        f'Last year   : {result.last_year}',
        f'Skipped     : {result.skipped_total} non-data line(s)',
    ]
    if result.skipped:
        lines.append('')
        lines.append('Skipped lines (line number : text):')
        for lineno, text in result.skipped:
            # Truncate so a pathological input can't blow up the report.
            shown = text[:120] + ('…' if len(text) > 120 else '')
            lines.append(f'  {lineno:5d} : {shown}')
        if result.skipped_total > len(result.skipped):
            lines.append(
                f'  … ({result.skipped_total - len(result.skipped)} more skipped '
                f'lines not shown)'
            )
    report_path.write_text('\n'.join(lines) + '\n')


# ── /runs ────────────────────────────────────────────────────────────


def _handle_list_runs(client_id: str) -> list[dict[str, Any]]:
    _require_buckets()
    paginator = s3().get_paginator('list_objects_v2')
    runs: dict[str, dict[str, Any]] = {}
    # Scope the listing to runs/<tool>/<client_id>/ per tool so we only
    # ever see entries for the calling browser. Listing the global
    # runs/ prefix and filtering in-process would leak run_id values
    # via S3 access logs and burn unnecessary list throughput.
    for tool in TOOLS:
        prefix = f'runs/{tool}/{client_id}/'
        for page in paginator.paginate(Bucket=OUTPUTS_BUCKET, Prefix=prefix):
            for obj in page.get('Contents', []):
                # runs/<tool>/<client_id>/<run_id>/<file>
                parts = obj['Key'].split('/')
                if len(parts) < 5:
                    continue
                run_id = parts[3]
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


def _handle_get_run(client_id: str, run_id: str) -> dict[str, Any]:
    _require_buckets()
    # Hard regex check before the value ever lands in an S3 prefix.
    if not RUN_ID_RE.match(run_id):
        raise _ClientError(400, 'Invalid run_id format')
    # Find under runs/<tool>/<client_id>/<run_id>/. List both tools to
    # handle either case without storing a manifest. A run that doesn't
    # belong to this client never matches, which produces a 404 — same
    # response shape as a never-existed ID, so an attacker can't
    # distinguish "wrong owner" from "no such run".
    for tool in TOOLS:
        prefix = f'runs/{tool}/{client_id}/{run_id}/'
        resp = s3().list_objects_v2(Bucket=OUTPUTS_BUCKET, Prefix=prefix)
        contents = resp.get('Contents', [])
        if not contents:
            continue
        # Output is anything that isn't the .rep — covers .day for disag
        # and .mon for convert. Exceed has no output file at all.
        report_key = next((c['Key'] for c in contents if c['Key'].endswith('.rep')), None)
        output_key = next(
            (c['Key'] for c in contents if not c['Key'].endswith('.rep')),
            None,
        )
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
    client_id: str,
    run_id: str,
    tool: str,
    *,
    output: Path | None,
    report: Path,
) -> dict[str, Any]:
    base = f'runs/{tool}/{client_id}/{run_id}'
    output_key = None
    if output:
        # Preserve the output filename so the suffix (.day, .mon) survives
        # the trip to S3. _handle_get_run / the frontend differentiate by
        # extension when surfacing download links.
        output_key = f'{base}/{output.name}'
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
        ExpiresIn=DOWNLOAD_TTL,
    )
