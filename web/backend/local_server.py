"""Local dev server — runs the Lambda handler behind a stdlib HTTP server.

Sketches an API-Gateway-shaped event so the same handler.py works on
the laptop and in AWS. Requires `INPUTS_BUCKET`, `OUTPUTS_BUCKET`, and
credentials in the env (or a `~/.aws/config` profile pointed at the
real or LocalStack S3).

    $ INPUTS_BUCKET=disag-inputs-dev OUTPUTS_BUCKET=disag-outputs-dev \\
        python3 web/backend/local_server.py
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from web.backend.handler import lambda_handler  # noqa: E402


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        self._dispatch('GET', body=b'')

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get('content-length', '0'))
        body = self.rfile.read(length) if length else b''
        self._dispatch('POST', body=body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch('OPTIONS', body=b'')

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
        self.wfile.write(payload)


def main() -> None:
    port = int(os.environ.get('PORT', '8000'))
    print(f'Listening on http://127.0.0.1:{port}')
    ThreadingHTTPServer(('127.0.0.1', port), _Handler).serve_forever()


if __name__ == '__main__':
    main()
