"""Path-containment tests for the local-dev S3 stub.

The `/_local-s3/{put,get,post}` endpoints accept a bucket and key from
the request, so `_LocalS3._path` is the only thing standing between a
crafted key and an arbitrary filesystem read/write on the dev box.
These tests pin the guard from both directions: legitimate handler
shaped keys resolve inside the root, and every traversal shape is
rejected before any filesystem access.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('LOCAL_S3_ROOT',
                      os.path.join(tempfile.gettempdir(), 'disag-test-s3'))

# local_server imports the handler at module level, which imports boto3 —
# stub it so the suite stays pure-stdlib (same pattern as test_handler.py).
if 'boto3' not in sys.modules:
    sys.modules['boto3'] = MagicMock()

from web.backend.local_server import _LocalS3  # noqa: E402


class LocalS3PathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stub = _LocalS3(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_handler_shaped_keys_resolve_inside_root(self):
        # The shapes handler.py actually generates.
        for key in (
            'inputs/11111111-2222-3333-4444-555555555555/abc123/m.mon',
            'runs/1712345678-deadbeef/output.day',
            'runs/1712345678-deadbeef/report.rep',
        ):
            target = self.stub._path('local-inputs', key)
            self.assertTrue(
                str(target).startswith(str(self.stub.root) + os.sep), key)

    def test_traversal_keys_are_rejected(self):
        for key in (
            '../outside.txt',
            '../../etc/passwd',
            'a/../../../etc/passwd',
            'a/./b',
            'a//b',
            '',
            '..',
        ):
            with self.assertRaises(ValueError, msg=f'key={key!r}'):
                self.stub._path('bucket', key)

    def test_traversal_buckets_are_rejected(self):
        for bucket in ('..', '.', ''):
            with self.assertRaises(ValueError, msg=f'bucket={bucket!r}'):
                self.stub._path(bucket, 'safe.txt')

    def test_symlink_escape_is_contained(self):
        # A symlink inside the tree pointing outside must not let a key
        # routed through it escape — realpath resolves it and the
        # containment check fires.
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        link = self.stub.root / 'bucket' / 'link'
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(outside.name, link)
        with self.assertRaises(ValueError):
            self.stub._path('bucket', 'link/escape.txt')

    def test_upload_then_download_round_trip(self):
        src = self.stub.root / 'src.bin'
        src.write_bytes(b'payload')
        self.stub.upload_file(str(src), 'bucket', 'inputs/x/y.bin')
        dest = self.stub.root / 'dest.bin'
        self.stub.download_file('bucket', 'inputs/x/y.bin', str(dest))
        self.assertEqual(dest.read_bytes(), b'payload')


if __name__ == '__main__':
    unittest.main()
