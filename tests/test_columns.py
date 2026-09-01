"""Tests for disag.columns — flattening a .day file to date/value rows."""

import calendar
import contextlib
import datetime
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.columns import (
    COLUMNS_SUFFIX,
    DATE_WIDTH,
    STYLE_SUFFIXES,
    VALUE_WIDTH,
    _cli,
    day_to_columns,
    default_columns_path,
    format_value,
)
from disag.files import (
    DAILY_HEADER_LINES,
    MISSING,
    DailyRecord,
    write_daily_file,
)

HEADER = {
    'monthly_file': '', 'daily_file_1': '', 'daily_file_2': '',
    'method_str': 'test', 'run_date': '2026-01-01 00:00:00',
}


def _tmp(suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class ColumnWriterTests(unittest.TestCase):

    def setUp(self):
        self.src = _tmp('.day')
        self.dst = _tmp('.txt')
        self.addCleanup(self._unlink, self.src)
        self.addCleanup(self._unlink, self.dst)

    @staticmethod
    def _unlink(path):
        if os.path.exists(path):
            os.unlink(path)

    def _write_src(self, records):
        write_daily_file(self.src, records, HEADER)

    def _rows(self):
        with open(self.dst) as f:
            return f.read().splitlines()

    def test_one_row_per_calendar_day_in_date_order(self):
        records = [
            DailyRecord(year=2000, month=1, v=[1.0] * 31),
            DailyRecord(year=2000, month=2, v=[2.0] * 29),   # leap
            DailyRecord(year=2000, month=3, v=[3.0] * 31),
        ]
        self._write_src(records)
        result = day_to_columns(self.src, self.dst)

        self.assertEqual(result.rows_written, 31 + 29 + 31)
        self.assertEqual(result.first_date, datetime.date(2000, 1, 1))
        self.assertEqual(result.last_date, datetime.date(2000, 3, 31))

        dates = [
            datetime.datetime.strptime(r.split()[0], '%Y/%m/%d').date()
            for r in self._rows()
        ]
        self.assertEqual(len(dates), len(set(dates)), 'duplicate dates')
        for earlier, later in zip(dates, dates[1:]):
            self.assertEqual((later - earlier).days, 1, f'gap after {earlier}')

    def test_leap_day_present_and_absent_in_the_right_years(self):
        for year, expect_feb29 in ((2000, True), (1900, False), (2001, False)):
            with self.subTest(year=year):
                dim = calendar.monthrange(year, 2)[1]
                self._write_src([DailyRecord(year=year, month=2, v=[1.0] * dim)])
                day_to_columns(self.src, self.dst)
                dates = {r.split()[0] for r in self._rows()}
                self.assertEqual(f'{year}/02/29' in dates, expect_feb29)

    def test_values_round_trip_unchanged(self):
        vals = [0.214, 5.5, 99.5, 150.25, 1500.5, MISSING] + [1.0] * 25
        self._write_src([DailyRecord(year=2000, month=1, v=vals)])
        day_to_columns(self.src, self.dst)
        written = [float(r.split()[1]) for r in self._rows()]
        for original, back in zip(vals, written):
            self.assertAlmostEqual(original, back, places=2)

    def test_missing_days_are_kept_not_dropped(self):
        vals = [1.0] * 15 + [MISSING] * 16
        self._write_src([DailyRecord(year=2000, month=1, v=vals)])
        result = day_to_columns(self.src, self.dst)
        self.assertEqual(result.rows_written, 31)
        self.assertEqual(result.missing_rows, 16)

    def test_fixed_style_column_positions(self):
        self._write_src([DailyRecord(year=2000, month=1, v=[1.0] * 31)])
        day_to_columns(self.src, self.dst, style='fixed')
        for row in self._rows():
            self.assertEqual(len(row), DATE_WIDTH + VALUE_WIDTH)
            self.assertEqual(row[:DATE_WIDTH].strip(), row.split()[0])
            self.assertEqual(row[DATE_WIDTH:].strip(), row.split()[1])

    def test_csv_and_tab_styles(self):
        self._write_src([DailyRecord(year=2000, month=1, v=[1.0] * 31)])
        for style, sep in (('csv', ','), ('tab', '\t')):
            with self.subTest(style=style):
                day_to_columns(self.src, self.dst, style=style)
                rows = self._rows()
                self.assertEqual(len(rows), 31)
                self.assertEqual(rows[0], f'2000/01/01{sep}1.000')

    def test_header_row_is_opt_in(self):
        self._write_src([DailyRecord(year=2000, month=1, v=[1.0] * 31)])
        day_to_columns(self.src, self.dst, style='csv')
        self.assertEqual(self._rows()[0], '2000/01/01,1.000')
        day_to_columns(self.src, self.dst, style='csv', header=True)
        self.assertEqual(self._rows()[0], 'Date,Flow')

    def test_custom_date_format(self):
        self._write_src([DailyRecord(year=2000, month=1, v=[1.0] * 31)])
        day_to_columns(self.src, self.dst, style='csv', date_format='%d/%m/%Y')
        self.assertEqual(self._rows()[0], '01/01/2000,1.000')

    def test_unknown_style_rejected(self):
        self._write_src([DailyRecord(year=2000, month=1, v=[1.0] * 31)])
        with self.assertRaises(ValueError):
            day_to_columns(self.src, self.dst, style='pipe')

    def test_empty_source_rejected(self):
        write_daily_file(self.src, [], HEADER)
        with self.assertRaises(ValueError):
            day_to_columns(self.src, self.dst)


class ValueFormatTests(unittest.TestCase):
    """Decimal convention must match disag.files._write_daily_record."""

    def test_matches_the_day_writer_field_for_field(self):
        # The two formatters are separate code; if one drifts, a value
        # would render differently in .day and in the column output.
        vals = [0.214, 5.5, 99.5, 150.25, 1500.56, MISSING] + [1.0] * 25
        src = _tmp('.day')
        try:
            write_daily_file(
                src, [DailyRecord(year=2000, month=1, v=vals)], HEADER
            )
            with open(src) as f:
                lines = f.read().splitlines()[DAILY_HEADER_LINES:]
            fields = []
            for line in lines[1:5]:                # days 1-28, 7 per line
                fields += [line[i:i + 7].strip() for i in range(0, 49, 7)]
            for original, day_field in zip(vals, fields):
                self.assertEqual(format_value(original), day_field)
        finally:
            os.unlink(src)

    def test_decimal_places_by_magnitude(self):
        self.assertEqual(format_value(0.2136), '0.214')
        self.assertEqual(format_value(99.0), '99.000')
        self.assertEqual(format_value(150.256), '150.26')
        self.assertEqual(format_value(1500.56), '1500.6')
        self.assertEqual(format_value(MISSING), '-99.99')


class ColumnCliTests(unittest.TestCase):

    def setUp(self):
        self.src = _tmp('.day')
        write_daily_file(
            self.src, [DailyRecord(year=2000, month=1, v=[1.0] * 31)], HEADER
        )
        self.addCleanup(os.unlink, self.src)

    def test_default_destination_matches_style(self):
        for style, suffix in sorted(STYLE_SUFFIXES.items()):
            with self.subTest(style=style):
                expected = os.path.splitext(self.src)[0] + suffix
                self.addCleanup(
                    lambda p=expected: os.path.exists(p) and os.unlink(p)
                )
                rc = _cli([self.src, '--style', style, '--quiet'])
                self.assertEqual(rc, 0)
                self.assertTrue(os.path.exists(expected))

    def test_missing_source_returns_error_code(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(_cli(['/nonexistent/nope.day', '--quiet']), 1)


class DefaultColumnsPathTests(unittest.TestCase):
    """The companion path a disag run writes its CSV to (--columns)."""

    def test_replaces_the_day_extension(self):
        self.assertEqual(
            default_columns_path('/out/MUY-NS-disag-m5.DAY'),
            '/out/MUY-NS-disag-m5' + COLUMNS_SUFFIX,
        )

    def test_leaves_dots_in_the_directory_alone(self):
        self.assertEqual(
            default_columns_path('/a.b/out.day'), '/a.b/out' + COLUMNS_SUFFIX
        )

    def test_extensionless_output_still_gets_a_csv(self):
        self.assertEqual(default_columns_path('/out/run'), '/out/run' + COLUMNS_SUFFIX)


if __name__ == '__main__':
    unittest.main()
