"""End-to-end CLI tests via subprocess.

Drives ``python -m disag --no-gui`` as a real process so argparse
behaviour, exit codes, and stderr/stdout messages are exercised
exactly as a user would see them.  Catches drift in:

  * argparse choices (--method 0..5)
  * required-arg error messages
  * --help content
  * the high-missing warning trigger
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _demo(*parts):
    return os.path.join(ROOT, 'examples', *parts)


def _run_cli(*args, expect_success=True):
    """Helper: run ``python -m disag --no-gui ARGS`` and return CompletedProcess."""
    res = subprocess.run(
        [sys.executable, '-m', 'disag', '--no-gui', *args],
        capture_output=True, text=True, cwd=ROOT,
    )
    if expect_success:
        assert res.returncode == 0, (
            f'expected success, got rc={res.returncode}\n'
            f'stdout: {res.stdout}\nstderr: {res.stderr}'
        )
    return res


def _tmp(suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class HelpAndArgparseTests(unittest.TestCase):
    """Things every CLI must get right — help text and argument validation."""

    def test_help_lists_methods_zero_through_five(self):
        res = subprocess.run(
            [sys.executable, '-m', 'disag', '--help'],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(res.returncode, 0)
        for n in range(6):
            self.assertIn(f'    {n}  ', res.stdout,
                          f'method {n} missing from --help')

    def test_method_six_rejected(self):
        # --method choices is range(6) → 6 should be rejected
        res = subprocess.run(
            [sys.executable, '-m', 'disag', '--no-gui', '--method', '6'],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('invalid', res.stderr.lower() + res.stdout.lower())

    def test_method_5_requires_monthly_and_daily1(self):
        # No --monthly / --daily1 / --output / --report
        res = subprocess.run(
            [sys.executable, '-m', 'disag', '--no-gui', '--method', '5'],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('required', res.stderr.lower())

    def test_method_2_requires_daily2(self):
        # PATCH_FILE has NO_FILES = 2; --daily2 must be required
        res = subprocess.run(
            [sys.executable, '-m', 'disag', '--no-gui', '--method', '2',
             '--monthly', _demo('method2_demo', 'data', 'target.MON'),
             '--daily1',  _demo('method2_demo', 'data', 'gauge_a.DAY'),
             '--output',  '/tmp/x.day',
             '--report',  '/tmp/x.rep'],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('daily2', res.stderr.lower())


class HappyPathRunTests(unittest.TestCase):
    """A real CLI run against each demo's fixture."""

    def test_method0_runs_to_completion(self):
        out = _tmp('.day')
        rep = _tmp('.rep')
        try:
            res = _run_cli(
                '--method', '0',
                '--monthly', _demo('method0_demo', 'data', 'target.MON'),
                '--daily1',  _demo('method0_demo', 'data', 'gauge_complete.DAY'),
                '--output',  out,
                '--report',  rep,
            )
            self.assertIn('Done', res.stdout)
            self.assertIn('36 disaggregated', res.stdout)
            self.assertTrue(os.path.exists(out))
            self.assertTrue(os.path.exists(rep))
        finally:
            for p in (out, rep):
                if os.path.exists(p):
                    os.unlink(p)

    def test_method4_runs_without_daily_input(self):
        out = _tmp('.day')
        rep = _tmp('.rep')
        try:
            res = _run_cli(
                '--method', '4',
                '--monthly', _demo('method4_demo', 'data', 'target.MON'),
                '--output',  out,
                '--report',  rep,
            )
            self.assertIn('36 disaggregated', res.stdout)
        finally:
            for p in (out, rep):
                if os.path.exists(p):
                    os.unlink(p)

    def test_method5_with_optional_daily2(self):
        out = _tmp('.day')
        rep = _tmp('.rep')
        try:
            # PATCH_EXCEED's NO_FILES is 1, but --daily2 is accepted and
            # used when supplied. Confirm the run succeeds and the report
            # mentions tier-2 scale factors (they're non-1.0 here).
            _run_cli(
                '--method', '5',
                '--monthly', _demo('method5_demo', 'data', 'target.MON'),
                '--daily1',  _demo('method5_demo', 'data', 'gauge_a_with_gaps.DAY'),
                '--daily2',  _demo('method5_demo', 'data', 'gauge_b_full.DAY'),
                '--output',  out,
                '--report',  rep,
            )
            with open(rep) as f:
                content = f.read()
            self.assertIn('Tier coverage summary', content)
            self.assertIn('scale factors', content)
        finally:
            for p in (out, rep):
                if os.path.exists(p):
                    os.unlink(p)


class HighMissingWarningTests(unittest.TestCase):
    """The warning that fires when method 0 leaves a lot of months missing."""

    def test_no_warning_when_coverage_high(self):
        out = _tmp('.day')
        rep = _tmp('.rep')
        try:
            res = _run_cli(
                '--method', '0',
                '--monthly', _demo('method0_demo', 'data', 'target.MON'),
                '--daily1',  _demo('method0_demo', 'data', 'gauge_with_gap.DAY'),
                '--output',  out,
                '--report',  rep,
            )
            # 1 of 36 months missing = 2.8 % — well under the 50 % trigger
            self.assertNotIn('WARNING', res.stderr)
        finally:
            for p in (out, rep):
                if os.path.exists(p):
                    os.unlink(p)


if __name__ == '__main__':
    unittest.main()
