"""Tests for disag.convert.ans_to_mon (Pitman .ANS → NinhamShand .MON).

All fixtures are synthesised in-test so no customer data lives in the
repo. The wet-year column-collision case mirrors what real Pitman
outputs do in flood years but uses entirely fabricated values.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.convert import SKIPPED_RETAIN_MAX, _cli, ans_to_mon
from disag.files import read_monthly_file


def _ans_line(year: int, vals: list, total: float = None, avg: float = None) -> str:
    """Render an .ANS data row in the fixed-width 8-char-column layout.

    Trailing total/average use 10/9-char fields to match the real Pitman output
    (and to defend against a future converter bug that mis-counts the cutoff).
    """
    parts = [f'{year:8d}'] + [f'{v:8.2f}' for v in vals]
    if total is not None:
        parts.append(f'{total:10.2f}')
    if avg is not None:
        parts.append(f'{avg:9.2f}')
    return ''.join(parts) + '\n'


def _write_ans(path: str, body: str) -> None:
    with open(path, 'w') as fh:
        fh.write(body)


def _tmp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class AnsToMonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = _tmp('.ANS')
        self.dst = _tmp('.MON')

    def tearDown(self) -> None:
        for p in (self.src, self.dst):
            if os.path.exists(p):
                os.remove(p)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_clean_two_year_file_round_trips(self):
        vals_1990 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        vals_1991 = [12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        body = (
            _ans_line(1990, vals_1990, total=sum(vals_1990), avg=sum(vals_1990) / 12)
            + _ans_line(1991, vals_1991, total=sum(vals_1991), avg=sum(vals_1991) / 12)
        )
        _write_ans(self.src, body)

        result = ans_to_mon(self.src, self.dst)

        self.assertEqual(result.rows_written, 2)
        self.assertEqual(result.first_year, 1990)
        self.assertEqual(result.last_year, 1991)
        self.assertEqual(result.skipped, [])

        # NinhamShand .MON header: exactly 5 lines (file name / units /
        # blank / column titles / rule), matching MONTHLY_HEADER_LINES.
        with open(self.dst) as fh:
            head = [fh.readline().rstrip('\n') for _ in range(5)]
        self.assertEqual(head[0], f'File name : {os.path.basename(self.dst)}')
        self.assertEqual(head[1], 'Units     : M.m3')
        self.assertTrue(head[3].startswith('Year'))
        self.assertIn('Oct', head[3])
        self.assertIn('Sep', head[3])
        self.assertEqual(set(head[4]), {'-'})
        # Column titles and rule are the same width as a data row.
        self.assertEqual(len(head[3]), len(head[4]))

        m = read_monthly_file(self.dst)
        # hydro 1990 = Oct 1990 .. Sep 1991
        self.assertAlmostEqual(m[(1990, 10)], 1.0)   # Oct
        self.assertAlmostEqual(m[(1991, 1)], 4.0)    # Jan
        self.assertAlmostEqual(m[(1991, 9)], 12.0)   # Sep
        # hydro 1991 = Oct 1991 .. Sep 1992
        self.assertAlmostEqual(m[(1991, 10)], 12.0)  # Oct
        self.assertAlmostEqual(m[(1992, 9)], 1.0)    # Sep

    # ------------------------------------------------------------------
    # Trailer rows (the AVERAGE summary + blank lines)
    # ------------------------------------------------------------------

    def test_skips_blank_and_average_trailer_rows(self):
        vals = [1.0] * 12
        body = (
            _ans_line(1990, vals, total=12.0, avg=1.0)
            + '  \n'
            + ' AVERAGE    1.72    5.68   23.50   59.95   88.62  267.91'
              '  224.68    5.67    2.64    2.28    1.94    1.60'
              '    686.18     57.18\n'
        )
        _write_ans(self.src, body)

        result = ans_to_mon(self.src, self.dst)

        self.assertEqual(result.rows_written, 1)
        self.assertEqual(len(result.skipped), 2)
        skipped_linenos = [ln for ln, _ in result.skipped]
        self.assertEqual(skipped_linenos, [2, 3])

    def test_skipped_list_is_capped_to_defend_against_adversarial_input(self):
        # A pathological .ANS that's all garbage shouldn't be able to
        # grow `skipped` to one entry per line — the list (and the .rep
        # report we write from it) is bounded so attacker-controlled
        # input can't drive Lambda memory.
        nlines = SKIPPED_RETAIN_MAX + 50
        body = ''.join('not a data line\n' for _ in range(nlines))
        # Add one valid row so ans_to_mon doesn't raise "no parseable
        # data rows found".
        body += _ans_line(1990, [1.0] * 12, total=12, avg=1.0)
        _write_ans(self.src, body)

        result = ans_to_mon(self.src, self.dst)

        self.assertEqual(result.rows_written, 1)
        self.assertEqual(len(result.skipped), SKIPPED_RETAIN_MAX)
        self.assertEqual(result.skipped_total, nlines)

    # ------------------------------------------------------------------
    # The fixed-width column collision case
    # ------------------------------------------------------------------

    def test_handles_columns_with_no_whitespace_separator(self):
        # 14639.12 and 13670.74 each occupy the full 8-char column,
        # producing the substring '14639.1213670.74' — split() corrupts this,
        # so the converter must slice by column position.
        vals = [
            4.62, 6.87, 6.56, 228.93,
            1250.71, 14639.12, 13670.74,
            60.09, 10.87, 10.49, 8.57, 7.60,
        ]
        body = _ans_line(1999, vals, total=sum(vals), avg=sum(vals) / 12)
        # Sanity: the rendered line MUST contain the colliding substring,
        # otherwise the test isn't actually exercising the bug.
        self.assertIn('14639.1213670.74', body)
        _write_ans(self.src, body)

        result = ans_to_mon(self.src, self.dst)

        self.assertEqual(result.rows_written, 1)
        m = read_monthly_file(self.dst)
        self.assertAlmostEqual(m[(2000, 2)], 1250.71)   # Feb
        self.assertAlmostEqual(m[(2000, 3)], 14639.12)  # Mar
        self.assertAlmostEqual(m[(2000, 4)], 13670.74)  # Apr

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_empty_file_raises(self):
        _write_ans(self.src, '')
        with self.assertRaises(ValueError):
            ans_to_mon(self.src, self.dst)

    def test_only_trailer_rows_raises(self):
        _write_ans(self.src, '\n AVERAGE   1.0   2.0\n')
        with self.assertRaises(ValueError):
            ans_to_mon(self.src, self.dst)


def _synth_multi_year_ans(path: str) -> tuple:
    """Write a synthetic 4-year .ANS that exercises the realistic shape:

    * multiple hydro-year data rows
    * one wet-year row whose adjacent values fill the 8-char column
      with no whitespace (the column-collision case)
    * a blank line + AVERAGE trailer that must be skipped

    Returns ``(first_year, last_year)`` for assertion convenience.
    """
    vals_1990 = [1.00, 2.00, 5.00, 10.00, 20.00, 50.00,
                 30.00, 15.00, 8.00, 4.00, 2.00, 1.00]
    # Wet year — two adjacent values >= 10000 collide in the column layout.
    vals_1991 = [2.00, 4.00, 8.00, 200.00, 1500.00,
                 14639.12, 13670.74,
                 80.00, 12.00, 6.00, 3.00, 1.50]
    vals_1992 = [1.50, 3.00, 7.50, 15.00, 25.00, 60.00,
                 35.00, 18.00, 9.00, 4.50, 2.50, 1.20]
    vals_1993 = [1.20, 2.40, 6.00, 12.00, 22.00, 55.00,
                 32.00, 16.00, 8.50, 4.20, 2.20, 1.10]
    rows = [
        (1990, vals_1990),
        (1991, vals_1991),
        (1992, vals_1992),
        (1993, vals_1993),
    ]
    with open(path, 'w') as fh:
        for year, vals in rows:
            fh.write(_ans_line(year, vals, total=sum(vals), avg=sum(vals) / 12))
        fh.write('  \n')
        fh.write(
            ' AVERAGE    1.42    2.85    6.62  109.25  391.75  3701.03'
            '  3434.18   32.25    9.37    4.67    2.42    1.20'
            '   7696.99    641.41\n'
        )
    return rows[0][0], rows[-1][0]


class AnsToMonSyntheticMultiYearTests(unittest.TestCase):
    """End-to-end round trip of a multi-year synthetic .ANS.

    Asserts the wet-year column-collision row parses without truncation.
    A real customer reference .MON we audited mis-parsed this exact case
    (14639.12 → 4639.12) because its converter used ``.split()``; our
    fixed-width slicer handles it correctly.
    """

    def setUp(self) -> None:
        self.src = _tmp('.ANS')
        self.dst = _tmp('.MON')

    def tearDown(self) -> None:
        for p in (self.src, self.dst):
            if os.path.exists(p):
                os.remove(p)

    def test_round_trip_with_wet_year_and_trailer(self):
        first, last = _synth_multi_year_ans(self.src)

        result = ans_to_mon(self.src, self.dst)

        self.assertEqual(result.first_year, first)
        self.assertEqual(result.last_year, last)
        self.assertEqual(result.rows_written, last - first + 1)
        # Blank line + AVERAGE row both reported as skipped.
        self.assertEqual(len(result.skipped), 2)

        m = read_monthly_file(self.dst)
        # Hydro 1990 first column = Oct 1990
        self.assertAlmostEqual(m[(1990, 10)], 1.00, places=2)
        # Wet-year row hydro 1991: column 6 = Mar 1992, column 7 = Apr 1992.
        # These must round-trip at full precision despite the
        # column-collision in the .ANS layout.
        self.assertAlmostEqual(m[(1992, 3)], 14639.12, places=2)
        self.assertAlmostEqual(m[(1992, 4)], 13670.74, places=2)
        # Last hydro 1993 → Sep 1994
        self.assertIn((1994, 9), m)


class AnsToMonCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = _tmp('.ANS')
        self.dst = _tmp('.MON')
        _synth_multi_year_ans(self.src)

    def tearDown(self) -> None:
        for p in (self.src, self.dst):
            if os.path.exists(p):
                os.remove(p)

    def test_cli_converts_synthetic_fixture(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = _cli([self.src, self.dst])
        self.assertEqual(rc, 0)
        msg = buf.getvalue()
        self.assertIn('1990', msg)
        self.assertIn('1993', msg)
        self.assertGreater(os.path.getsize(self.dst), 0)

    def test_cli_derives_output_name_from_source(self):
        # Omitting dst writes <src without extension>.MON next to the source.
        derived = os.path.splitext(self.src)[0] + '.MON'
        self.addCleanup(lambda: os.path.exists(derived) and os.remove(derived))
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = _cli([self.src])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(derived))
        self.assertIn(derived, buf.getvalue())
        m = read_monthly_file(derived)
        self.assertIn((1990, 10), m)

    def test_cli_quiet_suppresses_summary(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = _cli(['--quiet', self.src, self.dst])
        self.assertEqual(rc, 0)
        self.assertEqual(buf.getvalue(), '')

    def test_cli_returns_error_on_empty_file(self):
        empty = _tmp('.ANS')
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                rc = _cli([empty, self.dst])
            self.assertEqual(rc, 1)
            self.assertIn('error:', buf.getvalue())
        finally:
            os.remove(empty)


if __name__ == '__main__':
    unittest.main()
