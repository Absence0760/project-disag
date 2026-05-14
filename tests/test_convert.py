"""Tests for disag.convert.ans_to_mon (Pitman .ANS → NinhamShand .MON)."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.convert import ans_to_mon
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


if __name__ == '__main__':
    unittest.main()
