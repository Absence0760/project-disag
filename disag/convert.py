"""Convert Pitman Model monthly output (.ANS) to NinhamShand monthly format (.MON).

The Pitman .ANS layout is **fixed-width 8-character columns** (year, then 12
hydro-year monthly values, then total + average), NOT whitespace-separated.
In wet years the monthly value can fill the entire 8-char field and collide
with the next column (e.g. `14639.1213670.74`), so ``.split()`` silently
corrupts those rows. Always slice by column position.

The .ANS hydro-year layout (Oct→Sep, row label = start year) lines up with
NinhamShand's .MON convention, so no month reshuffling is needed — only a
5-line header is prepended and the trailing total/average + AVERAGE summary
row are dropped.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import NamedTuple

ANS_COL_WIDTH = 8
ANS_DATA_COLS = 13  # year + 12 monthly values

# Defence against an adversarial .ANS that's all garbage: keep at most
# this many skipped lines so the in-memory list (and the .rep report
# we write from it) can't grow proportional to file size. Real files
# usually have 0–2 skipped lines (AVERAGE trailer + blanks).
SKIPPED_RETAIN_MAX = 100


class ConversionResult(NamedTuple):
    rows_written: int
    first_year: int
    last_year: int
    skipped: list  # list of (lineno, text); first SKIPPED_RETAIN_MAX entries only
    skipped_total: int  # actual count, even when truncated


def ans_to_mon(src: str, dst: str) -> ConversionResult:
    """Convert a Pitman .ANS file to a NinhamShand .MON file.

    Raises ``ValueError`` if no parseable data rows are found.
    """
    rows: list = []
    skipped: list = []
    skipped_total = 0

    def _skip(lineno: int, text: str) -> None:
        nonlocal skipped_total
        skipped_total += 1
        if len(skipped) < SKIPPED_RETAIN_MAX:
            skipped.append((lineno, text))

    with open(src) as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip('\n')
            if len(line) < ANS_COL_WIDTH * ANS_DATA_COLS:
                _skip(lineno, line)
                continue
            year_field = line[0:ANS_COL_WIDTH].strip()
            try:
                year = int(year_field)
            except ValueError:
                _skip(lineno, line)
                continue
            try:
                vals = [
                    float(line[ANS_COL_WIDTH * i: ANS_COL_WIDTH * (i + 1)])
                    for i in range(1, ANS_DATA_COLS)
                ]
            except ValueError as exc:
                raise ValueError(
                    f'{src}: line {lineno}: failed to parse 12 monthly '
                    f'values from fixed-width 8-char columns ({exc})'
                ) from exc
            rows.append((year, vals))

    if not rows:
        raise ValueError(f'{src}: no parseable data rows found')

    header = [
        f'Description   : {os.path.basename(dst)}',
        'Units         : Mm3/month',
        f'Source        : converted from {os.path.basename(src)}',
        f'Layout        : hydro year (Oct-Sep), {rows[0][0]}-{rows[-1][0]}',
        f'Converted     : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
    ]

    with open(dst, 'w') as fh:
        for h in header:
            fh.write(h + '\n')
        for year, vals in rows:
            fh.write(
                f'{year:5d}  '
                + '  '.join(f'{v:9.3f}' for v in vals)
                + '\n'
            )

    return ConversionResult(
        rows_written=len(rows),
        first_year=rows[0][0],
        last_year=rows[-1][0],
        skipped=skipped,
        skipped_total=skipped_total,
    )


def _cli(argv: list | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog='python -m disag.convert',
        description='Convert a Pitman .ANS monthly file to a NinhamShand .MON file.',
    )
    parser.add_argument('src', help='Source .ANS file')
    parser.add_argument('dst', help='Destination .MON file')
    parser.add_argument(
        '--quiet', '-q', action='store_true',
        help='Suppress the conversion summary on stderr.',
    )
    args = parser.parse_args(argv)

    try:
        result = ans_to_mon(args.src, args.dst)
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f'wrote {result.rows_written} hydro-year rows '
            f'({result.first_year}–{result.last_year}) to {args.dst}',
            file=sys.stderr,
        )
        if result.skipped_total:
            print(
                f'skipped {result.skipped_total} non-data line(s) '
                f'(AVERAGE trailer / blanks)',
                file=sys.stderr,
            )
    return 0


if __name__ == '__main__':
    import sys

    sys.exit(_cli())
