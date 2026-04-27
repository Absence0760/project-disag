"""File I/O tests: round-trip, format edge cases, and report writer.

Covers the gotchas called out in CLAUDE.md and disag/CLAUDE.md so a
reader/writer regression can't slip through CI.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import DisagMethod
from disag.files import (
    DAILY_HEADER_LINES,
    MISSING,
    DailyRecord,
    read_daily_file,
    read_monthly_file,
    write_daily_file,
)
from disag.report import write_report


def _tmp(suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


HEADER = {
    'monthly_file': '', 'daily_file_1': '', 'daily_file_2': '',
    'method_str': 'test', 'run_date': '2026-01-01 00:00:00',
}


class DailyRoundTripTests(unittest.TestCase):
    """write_daily_file → read_daily_file should be lossless for typical input."""

    def test_round_trip_three_months(self):
        records = [
            # 31 days
            DailyRecord(year=2000, month=1, v=[float(i) for i in range(1, 32)]),
            # 28 days (non-leap Feb)
            DailyRecord(year=2001, month=2, v=[float(i) * 0.5 for i in range(1, 29)]),
            # 30 days
            DailyRecord(year=2001, month=4, v=[float(i) * 0.1 for i in range(1, 31)]),
        ]
        path = _tmp('.day')
        try:
            write_daily_file(path, records, HEADER)
            back = read_daily_file(path)
            self.assertEqual(len(back), 3)
            for orig in records:
                self.assertIn((orig.year, orig.month), back)
                got = back[(orig.year, orig.month)].v
                # Writer rounds to 3 decimals for small positives, so allow
                # a small float tolerance.
                self.assertEqual(len(got), len(orig.v))
                for a, b in zip(got, orig.v):
                    self.assertAlmostEqual(a, b, places=2)
        finally:
            os.unlink(path)

    def test_leap_year_february_round_trip(self):
        # 29-day Feb is a separate code path (dim != 28 → reads days 29+
        # off a separate continuation line).
        records = [DailyRecord(year=2020, month=2, v=[1.5] * 29)]
        path = _tmp('.day')
        try:
            write_daily_file(path, records, HEADER)
            back = read_daily_file(path)
            self.assertEqual(len(back[(2020, 2)].v), 29)
            self.assertAlmostEqual(back[(2020, 2)].v[28], 1.5, places=2)
        finally:
            os.unlink(path)

    def test_all_missing_round_trip(self):
        records = [DailyRecord(year=2000, month=1, v=[MISSING] * 31)]
        path = _tmp('.day')
        try:
            write_daily_file(path, records, HEADER)
            back = read_daily_file(path)
            self.assertEqual(len(back[(2000, 1)].v), 31)
            for v in back[(2000, 1)].v:
                self.assertLess(v, 0)
        finally:
            os.unlink(path)


class DailyEdgeCaseTests(unittest.TestCase):
    """The four gotchas called out in CLAUDE.md."""

    def _write_legacy(self, body: str) -> str:
        """Write a legacy-format .day file with a 12-line header and the
        given body. Returns the path."""
        path = _tmp('.day')
        with open(path, 'w') as f:
            for _ in range(DAILY_HEADER_LINES):
                f.write('-\n')
            f.write(body)
        return path

    def test_concatenated_negatives_parsed_as_separate_values(self):
        # Real Delphi-era files write -99.99 with no separators between
        # negative day values, e.g. ``-99.990-99.990-99.990 0.123…``.
        # The reader must slice by 7-char fixed-width columns, not split.
        body = (
            '2000  1   -99.990\n'
            '-99.990-99.990-99.990-99.990-99.990-99.990-99.990\n'
            '-99.990-99.990-99.990-99.990-99.990-99.990-99.990\n'
            '-99.990-99.990-99.990-99.990-99.990-99.990-99.990\n'
            '-99.990-99.990-99.990-99.990-99.990-99.990-99.990\n'
            '-99.990-99.990-99.990\n'
        )
        path = self._write_legacy(body)
        try:
            back = read_daily_file(path)
            self.assertEqual(len(back[(2000, 1)].v), 31)
            for v in back[(2000, 1)].v:
                self.assertAlmostEqual(v, -99.99, places=2)
        finally:
            os.unlink(path)

    def test_two_digit_year_normalised(self):
        # ``51  6`` should be read as 1951-06.
        body = (
            ' 51  6     1.234\n'
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.800  0.900  1.000  1.100  1.200  1.300  1.400\n'
            '  1.500  1.600  1.700  1.800  1.900  2.000  2.100\n'
            '  2.200  2.300  2.400  2.500  2.600  2.700  2.800\n'
            '  2.900  3.000\n'
        )
        path = self._write_legacy(body)
        try:
            back = read_daily_file(path)
            self.assertIn((1951, 6), back)
            self.assertEqual(len(back[(1951, 6)].v), 30)
        finally:
            os.unlink(path)

    def test_four_digit_year_preserved(self):
        body = (
            '2019  6     1.234\n'
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.800  0.900  1.000  1.100  1.200  1.300  1.400\n'
            '  1.500  1.600  1.700  1.800  1.900  2.000  2.100\n'
            '  2.200  2.300  2.400  2.500  2.600  2.700  2.800\n'
            '  2.900  3.000\n'
        )
        path = self._write_legacy(body)
        try:
            back = read_daily_file(path)
            self.assertIn((2019, 6), back)
        finally:
            os.unlink(path)

    def test_record_header_total_field_skipped(self):
        # The first line of each record is ``YYY MM TOTAL`` where TOTAL
        # is the monthly Mm³ summary, NOT a daily value. Reader must
        # NOT mistake it for day 1.
        body = (
            '2000  1   500.000\n'                # TOTAL is huge — would alarm
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.100  0.200  0.300  0.400  0.500  0.600  0.700\n'
            '  0.100  0.200  0.300\n'
        )
        path = self._write_legacy(body)
        try:
            back = read_daily_file(path)
            # No day should be 500.0 — the TOTAL field must not have
            # leaked into the daily array.
            for v in back[(2000, 1)].v:
                self.assertLess(v, 1.0)
        finally:
            os.unlink(path)


class MonthlyReaderTests(unittest.TestCase):
    """read_monthly_file maps hydro-year rows to calendar (year, month) keys."""

    def _write_mon(self, hydro_rows: list) -> str:
        """hydro_rows: list of (year, [12 values]) tuples."""
        path = _tmp('.MON')
        with open(path, 'w') as f:
            for _ in range(5):
                f.write('-\n')
            for year, vals in hydro_rows:
                f.write(f'{year:4d} ' + ' '.join(f'{v:8.3f}' for v in vals) + '\n')
        return path

    def test_hydro_year_maps_to_calendar(self):
        # Hydro 2000 row → Oct 2000 .. Sep 2001
        path = self._write_mon([(2000, list(range(1, 13)))])
        try:
            m = read_monthly_file(path)
        finally:
            os.unlink(path)
        # column 1 (index 0) = Oct of hydro year (2000) → (2000, 10)
        self.assertEqual(m[(2000, 10)], 1.0)
        self.assertEqual(m[(2000, 11)], 2.0)
        self.assertEqual(m[(2000, 12)], 3.0)
        # column 4 (index 3) = Jan of hydro year + 1 → (2001, 1)
        self.assertEqual(m[(2001, 1)], 4.0)
        # column 12 (index 11) = Sep of hydro year + 1 → (2001, 9)
        self.assertEqual(m[(2001, 9)], 12.0)

    def test_two_digit_hydro_year_normalised(self):
        path = self._write_mon([(51, list(range(1, 13)))])
        try:
            m = read_monthly_file(path)
        finally:
            os.unlink(path)
        # Hydro year 51 → 1951; first cal key should be (1951, 10)
        self.assertIn((1951, 10), m)
        self.assertNotIn((51, 10), m)

    def test_malformed_lines_skipped(self):
        path = _tmp('.MON')
        with open(path, 'w') as f:
            for _ in range(5):
                f.write('-\n')
            # malformed: only 5 tokens instead of ≥13
            f.write('garbage 1 2 3 4\n')
            # valid line
            f.write('2000 1 2 3 4 5 6 7 8 9 10 11 12\n')
        try:
            m = read_monthly_file(path)
        finally:
            os.unlink(path)
        # Only 12 keys (the one valid row), not 24
        self.assertEqual(len(m), 12)


class ReportWriterTests(unittest.TestCase):
    """write_report → read back assertions on structure."""

    def test_report_round_trip_with_records(self):
        records = [
            DailyRecord(year=2000, month=1, v=[1.0] * 31),
            DailyRecord(year=2000, month=2, v=[MISSING] * 28),
        ]
        report_lines = [
            '2000  2 Observed daily flow < 0,   Patched with 1999  2',
            'Tier coverage summary (days):',
            '  Tier 1 (file 1)        :     31 day(s)',
        ]
        path = _tmp('.rep')
        try:
            write_report(path, DisagMethod.PATCH_EXCEED, report_lines, records)
            with open(path) as f:
                content = f.read()
        finally:
            os.unlink(path)

        # Header
        self.assertIn('Disag Report', content)
        self.assertIn('Distrib with file 1, file 2, then exceedance-matched donor',
                     content)
        # Each report line preserved verbatim
        for line in report_lines:
            self.assertIn(line, content)
        # Coverage summary present and arithmetically correct
        # (1 disaggregated, 1 missing → 50% missing)
        self.assertIn('Months written     : 2', content)
        self.assertIn('Disaggregated    : 1', content)
        self.assertIn('Missing (-99.99) : 1', content)
        self.assertIn('Total adjustments  : 3', content)

    def test_report_round_trip_no_records_section(self):
        # Without records, the per-record summary block should be omitted
        path = _tmp('.rep')
        try:
            write_report(path, DisagMethod.ONE_FILE, ['adjustment line'])
            with open(path) as f:
                content = f.read()
        finally:
            os.unlink(path)
        self.assertIn('adjustment line', content)
        self.assertNotIn('Months written', content)
        self.assertIn('Total adjustments  : 1', content)


if __name__ == '__main__':
    unittest.main()
