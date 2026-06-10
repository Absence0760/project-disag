"""Unit tests for web/backend/handler.py — Lambda routing + validation.

These cover the contract layer (routing, X-Client-Id parsing,
_require_cloudfront, _validate_input_key, error-response shapes) that
the end-to-end Playwright integration tests don't pin in isolation.

boto3 is stubbed at import time via sys.modules so the test suite
stays pure-stdlib — each test that touches S3 patches
``handler._s3_client`` with its own MagicMock and asserts on the call
shape.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock

# Make `import handler` resolve to web/backend/handler.py. Also put
# the repo root on sys.path so handler.py's own `from disag.algorithm
# import …` works without depending on the Lambda zip layout.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
WEB_BACKEND = os.path.join(ROOT, 'web', 'backend')
if WEB_BACKEND not in sys.path:
    sys.path.insert(0, WEB_BACKEND)

# Stub boto3 before handler imports it. The handler tests never
# exercise real AWS — _s3_client is replaced per-test.
if 'boto3' not in sys.modules:
    sys.modules['boto3'] = MagicMock()

import handler  # noqa: E402

CLIENT_ID = '11111111-1111-4111-8111-111111111111'
OTHER_CLIENT = '22222222-2222-4222-8222-222222222222'
CONVERT_FIXTURE = os.path.join(ROOT, 'examples', 'convert_demo', 'data', 'SAMPLE.ANS')


def _make_event(
    method='GET',
    path='/',
    *,
    body=None,
    client_id=CLIENT_ID,
    extra_headers=None,
):
    headers = {}
    if client_id is not None:
        headers['x-client-id'] = client_id
    if extra_headers:
        headers.update(extra_headers)
    ev = {
        'requestContext': {'http': {'method': method}},
        'rawPath': path,
        'headers': headers,
    }
    if body is not None:
        ev['body'] = body if isinstance(body, str) else json.dumps(body)
    return ev


def _body(resp):
    return json.loads(resp['body']) if resp['body'] else None


class HandlerTestBase(unittest.TestCase):
    """Common fixtures: a fresh boto3 stub + bucket env per test."""

    def setUp(self):
        self.s3 = MagicMock()
        # Lazy s3() in handler reuses _s3_client; pre-seeding it bypasses
        # the boto3.client('s3') call (which is already a MagicMock).
        self._orig_s3_client = handler._s3_client
        self._orig_inputs = handler.INPUTS_BUCKET
        self._orig_outputs = handler.OUTPUTS_BUCKET
        self._orig_secret = handler.CLOUDFRONT_SHARED_SECRET
        handler._s3_client = self.s3
        handler.INPUTS_BUCKET = 'test-inputs'
        handler.OUTPUTS_BUCKET = 'test-outputs'
        handler.CLOUDFRONT_SHARED_SECRET = None

    def tearDown(self):
        handler._s3_client = self._orig_s3_client
        handler.INPUTS_BUCKET = self._orig_inputs
        handler.OUTPUTS_BUCKET = self._orig_outputs
        handler.CLOUDFRONT_SHARED_SECRET = self._orig_secret


# ── routing + framing ───────────────────────────────────────────────


class RoutingTests(HandlerTestBase):
    def test_options_short_circuits_with_204(self):
        # Preflight must succeed even without X-Client-Id — credentials
        # don't ride on OPTIONS.
        resp = handler.lambda_handler(
            _make_event(method='OPTIONS', path='/upload', client_id=None),
            None,
        )
        self.assertEqual(resp['statusCode'], 204)

    def test_api_prefix_stripped(self):
        # CloudFront forwards /api/X to APIGW; handler strips the
        # leading /api so its route table uses bare paths. Easiest
        # way to prove the strip happened without dragging the full
        # /runs S3 plumbing into a unit test: hit an unknown bare
        # path under /api and confirm the 404 message mentions the
        # STRIPPED path.
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/api/nope'),
            None,
        )
        self.assertEqual(resp['statusCode'], 404)
        msg = _body(resp)['error']
        self.assertIn(' /nope', msg)
        self.assertNotIn('/api/nope', msg)

    def test_unknown_route_returns_404_with_path(self):
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/nope'),
            None,
        )
        self.assertEqual(resp['statusCode'], 404)
        self.assertIn('/nope', _body(resp)['error'])

    def test_invalid_json_body_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', body='{not json'),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)
        self.assertIn('Invalid JSON', _body(resp)['error'])


# ── X-Client-Id parsing ─────────────────────────────────────────────


class ClientIdTests(HandlerTestBase):
    def test_missing_header_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', client_id=None),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)
        self.assertIn('X-Client-Id', _body(resp)['error'])

    def test_bogus_format_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', client_id='not-a-uuid'),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_uppercase_header_name_accepted(self):
        # APIGW lowercases headers, but tolerate the original-cased
        # form so a curl with 'X-Client-Id' works against the local
        # shim too.
        ev = _make_event(method='POST', path='/upload', body={'filename': 'x.mon'}, client_id=None)
        ev['headers']['X-Client-Id'] = CLIENT_ID
        resp = handler.lambda_handler(ev, None)
        # /upload happy path mocked below; here we only assert we got
        # past the client-id gate.
        self.assertNotEqual(resp['statusCode'], 400)


# ── CloudFront shared secret ────────────────────────────────────────


class RequireCloudfrontTests(HandlerTestBase):
    def test_secret_unset_passes_locally(self):
        # CLOUDFRONT_SHARED_SECRET is None in setUp — the gate is a no-op.
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/runs'),
            None,
        )
        # The /runs path itself doesn't 403 — it returns 200 with the
        # mocked pagination empty.
        self.assertNotEqual(resp['statusCode'], 403)

    def test_secret_set_header_missing_returns_403(self):
        handler.CLOUDFRONT_SHARED_SECRET = 's3cr3t'
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/runs'),
            None,
        )
        self.assertEqual(resp['statusCode'], 403)

    def test_secret_set_header_wrong_returns_403(self):
        handler.CLOUDFRONT_SHARED_SECRET = 's3cr3t'
        resp = handler.lambda_handler(
            _make_event(
                method='GET',
                path='/runs',
                extra_headers={'x-cloudfront-shared-secret': 'guess'},
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 403)

    def test_secret_set_header_correct_passes(self):
        handler.CLOUDFRONT_SHARED_SECRET = 's3cr3t'
        resp = handler.lambda_handler(
            _make_event(
                method='GET',
                path='/runs',
                extra_headers={'x-cloudfront-shared-secret': 's3cr3t'},
            ),
            None,
        )
        self.assertNotEqual(resp['statusCode'], 403)

    def test_options_not_gated_by_shared_secret(self):
        # CORS preflight has to work even from non-CloudFront origins
        # or the browser blocks the actual request.
        handler.CLOUDFRONT_SHARED_SECRET = 's3cr3t'
        resp = handler.lambda_handler(
            _make_event(method='OPTIONS', path='/upload', client_id=None),
            None,
        )
        self.assertEqual(resp['statusCode'], 204)


# ── bucket presence ─────────────────────────────────────────────────


class BucketsRequiredTests(HandlerTestBase):
    def test_missing_buckets_returns_503(self):
        handler.INPUTS_BUCKET = None
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', body={'filename': 'x.mon'}),
            None,
        )
        self.assertEqual(resp['statusCode'], 503)


# ── /upload ─────────────────────────────────────────────────────────


class UploadTests(HandlerTestBase):
    def setUp(self):
        super().setUp()
        self.s3.generate_presigned_post.return_value = {
            'url': 'https://test-inputs.s3.amazonaws.com',
            'fields': {'key': 'placeholder'},
        }

    def test_missing_filename_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', body={}),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_happy_path_includes_max_bytes_and_ttl(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/upload', body={'filename': 'SINDILA.MON'}),
            None,
        )
        self.assertEqual(resp['statusCode'], 200)
        body = _body(resp)
        self.assertIn('key', body)
        self.assertIn('url', body)
        self.assertEqual(body['max_bytes'], handler.MAX_UPLOAD_BYTES)
        self.assertEqual(body['expires_in'], handler.UPLOAD_TTL)

    def test_presigned_post_policy_includes_content_length_range(self):
        # M1 finding: the size-cap conditions must reach S3 so an
        # oversized upload is rejected server-side before any object
        # lands. Without this, MAX_UPLOAD_BYTES is unenforced.
        handler.lambda_handler(
            _make_event(method='POST', path='/upload', body={'filename': 'big.mon'}),
            None,
        )
        kwargs = self.s3.generate_presigned_post.call_args.kwargs
        conds = kwargs['Conditions']
        # condition tuple shape: ['content-length-range', min, max]
        size_conds = [c for c in conds if c[0] == 'content-length-range']
        self.assertEqual(len(size_conds), 1)
        self.assertEqual(size_conds[0][2], handler.MAX_UPLOAD_BYTES)

    def test_key_scoped_to_caller_client_id(self):
        # Path traversal at the IAM layer requires that the issued key
        # always live under inputs/<this-client>/.
        handler.lambda_handler(
            _make_event(method='POST', path='/upload', body={'filename': '../etc/passwd'}),
            None,
        )
        kwargs = self.s3.generate_presigned_post.call_args.kwargs
        self.assertTrue(kwargs['Key'].startswith(f'inputs/{CLIENT_ID}/'))
        # Filename traversal should be sanitised — no '..' segments
        # in the final S3 key.
        self.assertNotIn('..', kwargs['Key'].split('/'))


# ── _validate_input_key ─────────────────────────────────────────────


class ValidateInputKeyTests(HandlerTestBase):
    def test_rejects_foreign_client_prefix(self):
        # Direct unit test of the helper — it must 403 keys outside
        # the caller's prefix.
        with self.assertRaises(handler._ClientError) as cm:
            handler._validate_input_key(
                CLIENT_ID,
                f'inputs/{OTHER_CLIENT}/abc/foo.mon',
            )
        self.assertEqual(cm.exception.status, 403)

    def test_rejects_traversal_segments(self):
        with self.assertRaises(handler._ClientError) as cm:
            handler._validate_input_key(
                CLIENT_ID,
                f'inputs/{CLIENT_ID}/../../etc/passwd',
            )
        self.assertEqual(cm.exception.status, 400)

    def test_accepts_owned_prefix(self):
        good = f'inputs/{CLIENT_ID}/abc/SINDILA.MON'
        self.assertEqual(handler._validate_input_key(CLIENT_ID, good), good)


# ── /disag ──────────────────────────────────────────────────────────


class DisagValidationTests(HandlerTestBase):
    def test_missing_monthly_key_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/disag', body={'method': 0}),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)
        self.assertIn('monthly_key', _body(resp)['error'])

    def test_invalid_method_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/disag',
                body={'method': 99, 'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon'},
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_foreign_monthly_key_returns_403(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/disag',
                body={
                    'method': 0,
                    'monthly_key': f'inputs/{OTHER_CLIENT}/x/m.mon',
                    'daily1_key': f'inputs/{CLIENT_ID}/x/d.day',
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 403)


# ── /exceed ─────────────────────────────────────────────────────────


class ExceedValidationTests(HandlerTestBase):
    def test_no_keys_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/exceed', body={'intervals': 20}),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_non_int_intervals_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon',
                    'intervals': 'lots',
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_intervals_below_range_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon',
                    'intervals': 0,
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_intervals_above_range_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon',
                    'intervals': 10_000,
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_foreign_monthly_key_returns_403(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{OTHER_CLIENT}/x/m.mon',
                    'intervals': 20,
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 403)

    def test_seasons_not_a_list_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon',
                    'seasons': 'spring',
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_season_with_invalid_month_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/exceed',
                body={
                    'monthly_key': f'inputs/{CLIENT_ID}/x/m.mon',
                    'seasons': [{'name': 'Bad', 'months': [13]}],
                },
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)


# ── /convert ────────────────────────────────────────────────────────


class ConvertTests(HandlerTestBase):
    def setUp(self):
        super().setUp()
        # Each /convert run writes to /tmp/<run_id>/ — clean up after.
        self._tmps = []

        def _download(Bucket, Key, local_path):
            """Mimic boto3's download_file by copying a fixture into the
            caller-supplied local path. Tests choose the fixture via
            self.fixture_to_download."""
            shutil.copy(self.fixture_to_download, local_path)

        self.s3.download_file.side_effect = _download
        self.s3.generate_presigned_url.return_value = 'https://stub/get'
        self.fixture_to_download = CONVERT_FIXTURE

    def tearDown(self):
        super().tearDown()
        for d in self._tmps:
            shutil.rmtree(d, ignore_errors=True)

    def test_missing_ans_key_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='POST', path='/convert', body={}),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_foreign_ans_key_returns_403(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/convert',
                body={'ans_key': f'inputs/{OTHER_CLIENT}/x/foo.ans'},
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 403)

    def test_happy_path_writes_mon_and_rep_keys(self):
        resp = handler.lambda_handler(
            _make_event(
                method='POST',
                path='/convert',
                body={'ans_key': f'inputs/{CLIENT_ID}/x/SAMPLE.ANS'},
            ),
            None,
        )
        self.assertEqual(resp['statusCode'], 200)
        body = _body(resp)
        self.assertEqual(body['tool'], 'convert')
        self.assertTrue(body['output_key'].endswith('output.mon'))
        self.assertTrue(body['report_key'].endswith('output.rep'))
        # output and report must be uploaded — assert both calls fired.
        upload_keys = [c.args[2] for c in self.s3.upload_file.call_args_list]
        self.assertTrue(any(k.endswith('output.mon') for k in upload_keys))
        self.assertTrue(any(k.endswith('output.rep') for k in upload_keys))

    def test_error_does_not_leak_tmp_path_or_run_id(self):
        # The MEDIUM audit fix: ans_to_mon's ValueError embeds the full
        # /tmp/<run_id>/<filename> path. The handler must NOT propagate
        # that to the wire response.
        garbage = tempfile.NamedTemporaryFile('w', suffix='.ANS', delete=False)
        garbage.write('this is definitely not the source layout\n' * 3)
        garbage.close()
        self.addCleanup(os.unlink, garbage.name)
        self.fixture_to_download = garbage.name

        # The handler logs the underlying error to stdout (CloudWatch
        # in prod) — capture it so the test output stays clean.
        buf = io.StringIO()
        with redirect_stdout(buf):
            resp = handler.lambda_handler(
                _make_event(
                    method='POST',
                    path='/convert',
                    body={'ans_key': f'inputs/{CLIENT_ID}/x/bad.ans'},
                ),
                None,
            )

        self.assertEqual(resp['statusCode'], 400)
        msg = _body(resp)['error']
        self.assertNotIn('/tmp/', msg)
        # Run IDs look like '1700000000-abcdef12'; a partial check that
        # nothing of that shape is in the wire error.
        self.assertNotRegex(msg, r'\d{10}-[0-9a-f]{8}')
        # The detail must still reach CloudWatch though — otherwise
        # this becomes a "log nothing" regression.
        self.assertIn('convert failed', buf.getvalue())


# ── /runs/{id} ──────────────────────────────────────────────────────


class GetRunTests(HandlerTestBase):
    def setUp(self):
        super().setUp()
        # Empty list_objects_v2 → handler returns 404.
        self.s3.list_objects_v2.return_value = {'Contents': []}

    def test_invalid_run_id_format_returns_400(self):
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/runs/not-a-run-id'),
            None,
        )
        self.assertEqual(resp['statusCode'], 400)

    def test_unknown_run_returns_404(self):
        resp = handler.lambda_handler(
            _make_event(method='GET', path='/runs/1700000000-abcdef12'),
            None,
        )
        self.assertEqual(resp['statusCode'], 404)


if __name__ == '__main__':
    unittest.main()
