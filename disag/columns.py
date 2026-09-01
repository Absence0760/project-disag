"""Flatten a .day file into two columns: one row per day, date and flow.

The .day block layout (a record header, then rows of seven 7-char fields)
is compact but assumes the consumer knows the format. Downstream tools that
just want a time series are easier to feed with one row per day:

    1981/10/01      0.214
    1981/10/02      0.225

Values keep the .day writer's decimal convention — 3 places below 100,
2 for 100–999 or the ``-99.99`` missing sentinel, 1 above 999 — so a value
round-trips through this format unchanged.
"""

from __future__ import annotations

import calendar
import datetime
import os
from typing import NamedTuple

from disag.files import read_daily_file

# Column widths for the fixed-width style: date left-justified, value
# right-justified. Wide enough for a 4-digit-year date and a 1-decimal
# value above 999.
DATE_WIDTH = 10
VALUE_WIDTH = 11

# Separator per style; None means fixed-width columns.
STYLE_SEPARATORS = {'fixed': None, 'csv': ',', 'tab': '\t'}
STYLE_SUFFIXES = {'fixed': '.txt', 'csv': '.csv', 'tab': '.tsv'}
DEFAULT_STYLE = 'fixed'
DEFAULT_DATE_FORMAT = '%Y/%m/%d'

# Suffix for the CSV that `python -m disag --columns` writes next to its
# .day output: MUY-NS-disag-m5.DAY → MUY-NS-disag-m5-columns.csv. Kept
# here so the run that produces the pair and any consumer looking for it
# agree on one spelling.
COLUMNS_SUFFIX = '-columns.csv'


class ColumnResult(NamedTuple):
    rows_written: int
    first_date: datetime.date
    last_date: datetime.date
    missing_rows: int


def default_columns_path(output: str) -> str:
    """Companion CSV path for a .day output written by a disag run."""
    return os.path.splitext(output)[0] + COLUMNS_SUFFIX


def format_value(v: float) -> str:
    """Render one daily value with the .day writer's decimal convention."""
    if v < 0:
        return f'{v:.2f}'
    if v > 999:
        return f'{v:.1f}'
    if v > 99:
        return f'{v:.2f}'
    return f'{v:.3f}'


def format_row(date_str: str, value_str: str, separator: str | None) -> str:
    if separator is None:
        return f'{date_str:<{DATE_WIDTH}}{value_str:>{VALUE_WIDTH}}'
    return f'{date_str}{separator}{value_str}'


def day_to_columns(
    src: str,
    dst: str,
    style: str = DEFAULT_STYLE,
    date_format: str = DEFAULT_DATE_FORMAT,
    header: bool = False,
) -> ColumnResult:
    """Write ``src`` (.day) to ``dst`` as date/value rows in date order.

    Every day of every month present in ``src`` gets a row, missing days
    included — dropping them would leave a gap the consumer can't
    distinguish from a month that was never in the file.
    """
    if style not in STYLE_SEPARATORS:
        raise ValueError(
            f'unknown style {style!r} (expected one of '
            f'{", ".join(sorted(STYLE_SEPARATORS))})'
        )

    records = read_daily_file(src)
    if not records:
        raise ValueError(f'no daily records found in {src}')

    separator = STYLE_SEPARATORS[style]
    rows = 0
    missing = 0
    first_date = last_date = None

    with open(dst, 'w') as fh:
        if header:
            fh.write(format_row('Date', 'Flow', separator) + '\n')
        for year, month in sorted(records):
            record = records[(year, month)]
            dim = calendar.monthrange(year, month)[1]
            for day in range(1, dim + 1):
                # A short record (truncated file) still owes the caller a
                # row per calendar day; fall back to the sentinel.
                value = record.v[day - 1] if day - 1 < len(record.v) else -99.99
                date = datetime.date(year, month, day)
                fh.write(
                    format_row(
                        date.strftime(date_format), format_value(value), separator
                    ) + '\n'
                )
                if value < 0:
                    missing += 1
                if first_date is None:
                    first_date = date
                last_date = date
                rows += 1

    return ColumnResult(
        rows_written=rows,
        first_date=first_date,
        last_date=last_date,
        missing_rows=missing,
    )


def _cli(argv: list | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='python -m disag.columns',
        description='Flatten a .day file into date/value rows, one per day.',
    )
    parser.add_argument('src', help='Source .day file')
    parser.add_argument(
        'dst', nargs='?', default=None,
        help='Destination file (default: source name with a .txt/.csv/.tsv '
             'extension to match --style)',
    )
    parser.add_argument(
        '--style', choices=sorted(STYLE_SEPARATORS), default=DEFAULT_STYLE,
        help='Column separator (default: %(default)s, space-padded columns)',
    )
    parser.add_argument(
        '--date-format', default=DEFAULT_DATE_FORMAT,
        help='strftime format for the date column (default: %%Y/%%m/%%d)',
    )
    parser.add_argument(
        '--header', action='store_true',
        help='Write a "Date/Flow" title row.',
    )
    parser.add_argument(
        '--quiet', '-q', action='store_true',
        help='Suppress the summary on stderr.',
    )
    args = parser.parse_args(argv)

    dst = args.dst or (os.path.splitext(args.src)[0] + STYLE_SUFFIXES[args.style])

    try:
        result = day_to_columns(
            args.src, dst,
            style=args.style,
            date_format=args.date_format,
            header=args.header,
        )
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f'wrote {result.rows_written} daily rows '
            f'({result.first_date} → {result.last_date}) to {dst}',
            file=sys.stderr,
        )
        if result.missing_rows:
            print(
                f'{result.missing_rows} row(s) carry the -99.99 missing sentinel',
                file=sys.stderr,
            )
    return 0


if __name__ == '__main__':
    import sys

    sys.exit(_cli())
