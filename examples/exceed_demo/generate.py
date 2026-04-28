#!/usr/bin/env python3
"""
Generate a small mock dataset that exercises every mode of the
``exceed`` tool: Basic (per-calendar-month curves), Seasonal (curves
per season group), and Matching (monthly vs daily curve comparison).

Run from the repo root:
    python3 examples/exceed_demo/generate.py

Outputs two files into examples/exceed_demo/data/:
    target.MON   — synthetic monthly volumes (Mm3/month) for "River X"
    gauge.DAY    — synthetic daily flows (m3/s)        for "River X"

The numbers are deterministic (fixed seeds) so the same files
regenerate byte-for-byte every time.

The dataset is sized to be small enough to inspect by hand:
    10 hydro years (Oct 2000 – Sep 2010)
    → 10 monthly values per calendar month (120 total)
    → ~30 × 10 ≈ 300 daily values per calendar month (~3650 total)
"""

import calendar
import os
import random
import sys

# Make `disag` and `exceed` importable when running from the repo root.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from disag.files import DailyRecord, write_daily_file  # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# 10 hydro years gives 10 monthly values per calendar month, which is
# enough to produce a 20-interval exceedance curve where most intervals
# are populated, while keeping the .MON file small enough to read by eye.
YEARS = list(range(2000, 2010))
HYDRO_MONTHS = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# Synthetic seasonal pattern (Mm3/month).  Same southern-hemisphere
# shape as the disag method5 demo: wet Dec–Feb, dry Jun–Aug.  Wider
# wet/dry separation here so the seasonal-grouped exceedance curves
# look meaningfully different from each other.
SEASONAL_MM3 = {
    10: 3.0, 11: 4.5, 12: 6.0,
    1:  6.5, 2:  5.5, 3:  4.0,
    4:  2.5, 5:  1.5, 6:  0.8,
    7:  0.5, 8:  0.7, 9:  1.5,
}

# Daily m3/s magnitude, derived from the monthly Mm3 budget so daily
# totals reconcile with the monthly file at roughly the right order of
# magnitude (the exceed tool doesn't actually require this — it treats
# the two files independently — but it makes the matching mode produce
# results a hand-reader can sanity-check).
SEASONAL_M3S = {m: v * 1e6 / 86400 / 30 for m, v in SEASONAL_MM3.items()}


def _hydro_to_calendar(hydro_year: int, hm: int) -> tuple:
    return (hydro_year if hm >= 10 else hydro_year + 1, hm)


# --------------------------------------------------------------------------
# Monthly data
# --------------------------------------------------------------------------

def gen_monthly() -> dict:
    """{(cal_year, cal_month): Mm3}.  Each value = seasonal × random[0.6, 1.4]."""
    random.seed(101)
    rec: dict = {}
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            rec[(cy, cm)] = round(SEASONAL_MM3[hm] * random.uniform(0.6, 1.4), 3)
    return rec


def write_monthly(path: str, rec: dict) -> None:
    """Write a 5-line header followed by one hydro-year row of 12 values.

    The reader skips the first ``MONTHLY_HEADER_LINES`` (= 5) lines,
    so we use them to embed a worked example of the layout.
    """
    with open(path, 'w') as f:
        f.write('-' * 80 + '\n')                                              # 1
        f.write(f'Description : {os.path.basename(path)} (mock)  '            # 2
                'Units: Mm3/month\n')
        f.write('Columns     : Oct Nov Dec | Jan Feb Mar Apr May Jun Jul '    # 3
                'Aug Sep   (hydro order)\n')
        f.write('NOTE        : 10 hydro years; row label = hydro year Y; '    # 4
                'cal Jan (Y+1) is in column 4\n')
        f.write('-' * 80 + '\n')                                              # 5
        for hy in YEARS:
            row = [f'{hy:4d}']
            for hm in HYDRO_MONTHS:
                cy, cm = _hydro_to_calendar(hy, hm)
                row.append(f'{rec[(cy, cm)]:8.3f}')
            f.write(' '.join(row) + '\n')


# --------------------------------------------------------------------------
# Daily data
# --------------------------------------------------------------------------

def gen_daily() -> list:
    """Build a list of DailyRecord covering the full 10-hydro-year window
    with no gaps.  Daily values follow the same seasonal shape as the
    monthly file plus per-day jitter so a calendar month's daily curve
    has visible spread.
    """
    random.seed(202)
    records = []
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            dim = calendar.monthrange(cy, cm)[1]
            base = SEASONAL_M3S[hm]
            values = [round(base * random.uniform(0.5, 1.5), 3)
                      for _ in range(dim)]
            records.append(DailyRecord(year=cy, month=cm, v=values))
    return records


# Pinned timestamp so the demo files regenerate byte-for-byte identical
# every time (no churn on `git status`).
RUN_DATE = '2026-01-01 00:00:00'


def write_daily(path: str, records: list, label: str) -> None:
    write_daily_file(path, records, {
        'monthly_file': '',
        'daily_file_1': label,
        'daily_file_2': '',
        'method_str':   'mock data',
        'run_date':     RUN_DATE,
    })


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    monthly = gen_monthly()
    write_monthly(os.path.join(DATA_DIR, 'target.MON'), monthly)

    write_daily(
        os.path.join(DATA_DIR, 'gauge.DAY'),
        gen_daily(),
        label='gauge.DAY',
    )

    print(f'Wrote 2 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
