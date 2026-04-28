#!/usr/bin/env python3
"""
Driver for the monthly↔daily matching mode of the ``exceed`` tool.

The exceed CLI today only emits per-calendar-month curves; matching is
GUI-only.  This script calls ``calculate_monthly_exceedance`` for the
chosen calendar month from both files and then ``match_exceedance_values``
to pair entries on the two curves whose exceedance percentages are
within a tolerance.

Usage:
    python3 examples/exceed_demo/matching.py [--month 1..12]
                                             [--tolerance PCT]
                                             [--intervals N]

Defaults: --month 1 (January), --tolerance 5.0, --intervals 20.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from exceed.algorithm import (  # noqa: E402
    calculate_monthly_exceedance,
    match_exceedance_values,
)
from exceed.files import read_daily_file, read_monthly_file  # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')

MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Monthly↔daily exceedance matching demo.',
    )
    parser.add_argument('--month', type=int, choices=range(1, 13), default=1)
    parser.add_argument('--tolerance', type=float, default=5.0)
    parser.add_argument('--intervals', type=int, default=20)
    args = parser.parse_args()

    monthly_data = read_monthly_file(os.path.join(DATA_DIR, 'target.MON'))
    daily_data = read_daily_file(os.path.join(DATA_DIR, 'gauge.DAY'))

    if not monthly_data.get(args.month):
        print(f'No monthly data for {MONTH_NAMES[args.month]}', file=sys.stderr)
        return 1
    if not daily_data.get(args.month):
        print(f'No daily data for {MONTH_NAMES[args.month]}', file=sys.stderr)
        return 1

    m_result = calculate_monthly_exceedance(
        monthly_data[args.month], args.intervals)
    d_result = calculate_monthly_exceedance(
        daily_data[args.month], args.intervals)

    matches = match_exceedance_values(m_result, d_result,
                                      tolerance_pct=args.tolerance)

    print(f'Matching — {MONTH_NAMES[args.month]}, '
          f'tolerance ±{args.tolerance:g} percentage points')
    print(f'Monthly values: {m_result.total_count}     '
          f'Daily values: {d_result.total_count}')
    print('=' * 70)
    if not matches:
        print(f'\nNo monthly exceedance points fell within the daily curve '
              f'within ±{args.tolerance:g} pp.')
        return 0

    print(f'\n{"Exceed Mo%":>10} {"Exceed Da%":>10}   '
          f'{"Flow Mo":>10}   {"Flow Da":>10}   {"Δexceed":>8}')
    print('-' * 70)
    for m in matches:
        print(f'{m["exceed_monthly"]:9.2f}% {m["exceed_daily"]:9.2f}%   '
              f'{m["flow_monthly"]:10.3f}   {m["flow_daily"]:10.3f}   '
              f'{m["diff"]:7.2f}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
