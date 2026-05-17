"""Local dev server — runs the Lambda handler behind a stdlib HTTP server.

Sketches an API-Gateway-shaped event so the same handler.py works on
the laptop and in AWS.

Two modes:

* **Real AWS** — set INPUTS_BUCKET, OUTPUTS_BUCKET, and AWS credentials
  in the env. boto3 talks to S3 directly.

      INPUTS_BUCKET=disag-dev-inputs OUTPUTS_BUCKET=disag-dev-outputs \\
          python3 web/backend/local_server.py

* **Self-contained** — set LOCAL_S3=1. boto3 is replaced with an
  in-process stub backed by a temp directory under /tmp/, and the
  server handles `/_local-s3/{put,get}/{bucket}/{key}` for pre-signed
  uploads/downloads. No AWS needed. This is what the Playwright
  integration tests use.

      LOCAL_S3=1 python3 web/backend/local_server.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ── On-disk S3 stub ───────────────────────────────────────────────────
#
# Mirrors the subset of boto3's S3 client that handler.py uses:
#   - generate_presigned_url (put_object | get_object)
#   - upload_file / download_file
#   - list_objects_v2 / get_paginator('list_objects_v2')
#
# Pre-signed URLs point back at this server on /_local-s3/{action}/{bucket}/{key}.
# The browser PUTs / GETs through us as if we were S3.

LOCAL_S3_ROOT = Path(os.environ.get('LOCAL_S3_ROOT', tempfile.gettempdir() + '/disag-local-s3'))
LOCAL_S3_PORT = int(os.environ.get('PORT', '8000'))


class _LocalS3:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        return self.root / bucket / key

    def generate_presigned_url(self, op: str, Params: dict, ExpiresIn: int = 3600) -> str:
        action = 'put' if op == 'put_object' else 'get'
        bucket = Params['Bucket']
        key = Params['Key']
        return f'http://127.0.0.1:{LOCAL_S3_PORT}/_local-s3/{action}/{bucket}/{key}'

    def upload_file(self, src: str, bucket: str, key: str) -> None:
        dest = self._path(bucket, key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    def download_file(self, bucket: str, key: str, dest: str) -> None:
        shutil.copyfile(self._path(bucket, key), dest)

    def list_objects_v2(self, Bucket: str, Prefix: str = '', **_: Any) -> dict:
        bucket_root = self.root / Bucket
        items: list[dict] = []
        if bucket_root.exists():
            for p in sorted(bucket_root.rglob('*')):
                if not p.is_file():
                    continue
                key = str(p.relative_to(bucket_root)).replace(os.sep, '/')
                if not key.startswith(Prefix):
                    continue
                stat = p.stat()
                items.append({
                    'Key': key,
                    'Size': stat.st_size,
                    'LastModified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                })
        return {'Contents': items}

    def get_paginator(self, _op: str) -> '_LocalS3Paginator':
        return _LocalS3Paginator(self)


class _LocalS3Paginator:
    def __init__(self, client: _LocalS3) -> None:
        self.client = client

    def paginate(self, Bucket: str, Prefix: str = '', **_: Any) -> Iterable[dict]:
        # Single-page response is fine for the local stub — directory
        # listings are small and there's no continuation token to honour.
        yield self.client.list_objects_v2(Bucket=Bucket, Prefix=Prefix)


def _enable_local_s3() -> _LocalS3:
    """Swap handler's boto3 client for the on-disk stub and pre-seed buckets."""
    from web.backend import handler

    stub = _LocalS3(LOCAL_S3_ROOT)
    handler._s3_client = stub  # type: ignore[attr-defined]
    handler.INPUTS_BUCKET = os.environ.setdefault('INPUTS_BUCKET', 'local-inputs')
    handler.OUTPUTS_BUCKET = os.environ.setdefault('OUTPUTS_BUCKET', 'local-outputs')
    (LOCAL_S3_ROOT / handler.INPUTS_BUCKET).mkdir(parents=True, exist_ok=True)
    (LOCAL_S3_ROOT / handler.OUTPUTS_BUCKET).mkdir(parents=True, exist_ok=True)
    return stub


_local_s3: _LocalS3 | None = None
if os.environ.get('LOCAL_S3') == '1':
    _local_s3 = _enable_local_s3()


from web.backend.handler import lambda_handler  # noqa: E402


# ── HTTP server ──────────────────────────────────────────────────────


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        if self._maybe_serve_local_s3('get'):
            return
        self._dispatch('GET', body=b'')

    def do_PUT(self) -> None:  # noqa: N802
        if self._maybe_serve_local_s3('put'):
            return
        self._dispatch('PUT', body=self._read_body())

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch('POST', body=self._read_body())

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch('OPTIONS', body=b'')

    def log_message(self, fmt: str, *args: Any) -> None:
        # Default handler prints to stderr — keep that, but trim the
        # noise so test output stays readable.
        sys.stderr.write(f'[local] {self.address_string()} {fmt % args}\n')

    def _read_body(self) -> bytes:
        length = int(self.headers.get('content-length', '0'))
        return self.rfile.read(length) if length else b''

    def _maybe_serve_local_s3(self, expected_action: str) -> bool:
        """Handle /_local-s3/{put,get}/{bucket}/{key} when LOCAL_S3=1."""
        if _local_s3 is None or not self.path.startswith('/_local-s3/'):
            return False
        try:
            _, _, action, bucket, *rest = self.path.split('/', 4)
        except ValueError:
            self._reply(400, b'Malformed local-s3 path')
            return True
        if action != expected_action or not rest:
            self._reply(404, b'Not found')
            return True
        key = unquote(rest[0])
        target = _local_s3._path(bucket, key)
        if expected_action == 'put':
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self._read_body())
            self._reply(200, b'')
        else:
            if not target.is_file():
                self._reply(404, b'Key not found')
                return True
            self._reply(200, target.read_bytes(), content_type='application/octet-stream')
        return True

    def _reply(self, status: int, body: bytes, *, content_type: str = 'text/plain') -> None:
        self.send_response(status)
        self.send_header('content-type', content_type)
        self.send_header('access-control-allow-origin', '*')
        self.send_header('access-control-allow-methods', 'GET, PUT, POST, OPTIONS')
        self.send_header('access-control-allow-headers', '*')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _dispatch(self, method: str, *, body: bytes) -> None:
        event = {
            'requestContext': {'http': {'method': method}},
            'rawPath': self.path.split('?', 1)[0],
            'body': body.decode('utf-8') if body else '',
            'isBase64Encoded': False,
        }
        resp = lambda_handler(event, None)
        self.send_response(resp['statusCode'])
        for k, v in resp.get('headers', {}).items():
            self.send_header(k, v)
        self.end_headers()
        payload = resp.get('body', '')
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        if payload:
            self.wfile.write(payload)


def main() -> None:
    port = LOCAL_S3_PORT
    if _local_s3 is not None:
        print(f'Local S3 stub: {LOCAL_S3_ROOT}', flush=True)
    print(f'Listening on http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), _Handler).serve_forever()


if __name__ == '__main__':
    main()
