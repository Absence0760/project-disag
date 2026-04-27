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


class HighSyntheticWarningTests(unittest.TestCase):
    """The Method-5 warning that fires when most output days are tier-3
    synthetic.  This is the user-facing equivalent of the report's
    Tier coverage summary — surfaces a heads-up that a fully-disaggregated
    output is mostly donor-copied rather than observed."""

    def test_no_warning_when_mostly_observed(self):
        # Scenario 1: file 1 is complete → 100% tier-1, 0% synthetic
        out = _tmp('.day')
        rep = _tmp('.rep')
        try:
            res = _run_cli(
                '--method', '5',
                '--monthly', _demo('method5_demo', 'data', 'target.MON'),
                '--daily1',  _demo('method5_demo', 'data', 'gauge_a_complete.DAY'),
                '--output',  out,
                '--report',  rep,
            )
            self.assertNotIn('WARNING', res.stderr)
            self.assertNotIn('synthetic', res.stderr)
        finally:
            for p in (out, rep):
                if os.path.exists(p):
                    os.unlink(p)

    def test_warning_fires_when_mostly_synthetic(self):
        # Construct a Method-5 run where most days come from tier-3 by
        # giving file 1 only a small slice of gen_monthly's coverage.
        # gen_monthly spans 10 hydro years; daily covers only 2 → 8 of
        # 10 hydro years are tier-3 backfilled → ≈ 80% synthetic.
        import calendar as _cal
        import tempfile
        # Local imports so the test file's stdlib-import block stays
        # ordered with the other CLI tests above.
        sys.path.insert(0, ROOT)
        from disag.files import DailyRecord, write_daily_file

        with tempfile.TemporaryDirectory() as td:
            mon_path = os.path.join(td, 'wide.MON')
            day_path = os.path.join(td, 'narrow.DAY')

            # Monthly file: 5-line header + one data line per hydro year
            # (12 values: Oct, Nov, Dec, Jan, …, Sep).
            with open(mon_path, 'w') as f:
                f.write('Test wide MON\n')
                f.write('Mm3/month\n')
                f.write('\n')
                f.write('Hydro years 2000-2009\n')
                f.write('\n')
                for hy in range(2000, 2010):
                    vals = ' '.join(f'{1.0 + 0.1 * i:8.3f}' for i in range(12))
                    f.write(f'{hy:4d}  {vals}\n')

            # Daily file: 2 complete hydro years, every day = 1.0
            recs = []
            for hy in (2002, 2003):
                for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                    cy = hy if hm >= 10 else hy + 1
                    dim = _cal.monthrange(cy, hm)[1]
                    recs.append(DailyRecord(year=cy, month=hm, v=[1.0] * dim))
            write_daily_file(day_path, recs, {
                'monthly_file': '', 'daily_file_1': '', 'daily_file_2': '',
                'method_str': 'mock fixture',
                'run_date': '2026-04-26 00:00:00',
            })

            out = _tmp('.day')
            rep = _tmp('.rep')
            try:
                res = _run_cli(
                    '--method', '5',
                    '--monthly', mon_path,
                    '--daily1',  day_path,
                    '--output',  out,
                    '--report',  rep,
                )
                self.assertIn('WARNING', res.stderr)
                self.assertIn('synthetic', res.stderr)
                self.assertIn('tier-3', res.stderr)
            finally:
                for p in (out, rep):
                    if os.path.exists(p):
                        os.unlink(p)


if __name__ == '__main__':
    unittest.main()
