#!/usr/bin/env python3
"""
Driver for the seasonal-grouping mode of the ``exceed`` tool.

The exceed CLI today only emits per-calendar-month curves; the
seasonal mode is GUI-only.  This script calls
``calculate_seasonal_exceedance`` directly so the demo's seasonal
walkthrough is runnable without opening the GUI.

Usage:
    python3 examples/exceed_demo/seasonal.py [--seasons 2|3|4]
                                             [--source monthly|daily]
                                             [--intervals N]

Defaults: --seasons 4, --source monthly, --intervals 20.

Prints a curve per season to stdout in the same shape as the basic
report.  Exits with status 0.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from exceed.algorithm import (  # noqa: E402
    SEASON_PRESETS,
    calculate_seasonal_exceedance,
)
from exceed.files import read_daily_file, read_monthly_file  # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Seasonal exceedance demo for the exceed tool.',
    )
    parser.add_argument('--seasons', type=int, choices=[2, 3, 4], default=4)
    parser.add_argument('--source', choices=['monthly', 'daily'],
                        default='monthly')
    parser.add_argument('--intervals', type=int, default=20)
    args = parser.parse_args()

    if args.source == 'monthly':
        data = read_monthly_file(os.path.join(DATA_DIR, 'target.MON'))
    else:
        data = read_daily_file(os.path.join(DATA_DIR, 'gauge.DAY'))

    seasons = SEASON_PRESETS[args.seasons]
    results = calculate_seasonal_exceedance(data, seasons, args.intervals)

    print(f'Seasonal exceedance — {args.seasons}-season preset, '
          f'{args.source} source, {args.intervals} intervals')
    print('=' * 70)
    for name, months in seasons.items():
        if name not in results:
            print(f'\n{name.upper()} (months {months}): no data')
            continue
        r = results[name]
        print(f'\n{name.upper()} (months {months})')
        print('-' * 70)
        print(f'Total values: {r.total_count}  '
              f'Below range: {r.count_below}  '
              f'Above range: {r.count_above}')
        print()
        print('Exceedance%    Flow Value')
        print('-' * 30)
        for pct, flow in zip(r.exceedance_pct, r.flow_values):
            print(f'{pct:8.2f}%     {flow:12.3f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
