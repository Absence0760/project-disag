#!/usr/bin/env python3
"""
Generate a small mock dataset that exercises every tier of Method 5
(PATCH_EXCEED).

Run from the repo root:
    python3 examples/method5_demo/generate.py

Outputs five files into examples/method5_demo/data/:
    target.MON               — synthetic monthly volumes for "River A"
    gauge_a_complete.DAY     — daily file 1, no gaps   → exercises tier 1
    gauge_a_with_gaps.DAY    — daily file 1 with two whole-month gaps
                                  (alone: tier 1 + tier 3)
    gauge_b_full.DAY         — daily file 2 that covers BOTH gauge_a gaps
                                  (with gauge_a_with_gaps: tier 1 + tier 2)
    gauge_b_partial.DAY      — daily file 2 that covers only ONE of the gaps
                                  (with gauge_a_with_gaps: tier 1 + 2 + 3)

The numbers are deterministic (fixed seeds) so the same files regenerate
byte-for-byte every time.
"""

import calendar
import os
import random
import sys

# Make `disag` importable when running from the repo root or this dir
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

# Six hydro years (Oct 2000 – Sep 2006) gives 5 candidates per calendar
# month after excluding the target — enough for percentile matching to
# produce visibly different ranks.
YEARS = list(range(2000, 2006))
HYDRO_MONTHS = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# Synthetic seasonal pattern (Mm3/month for River A).  Wet southern-hemisphere
# summer (Dec–Feb), drier winter (Jun–Aug).
SEASONAL_MM3 = {
    10: 3.5, 11: 4.5, 12: 5.0,
    1:  5.0, 2:  4.5, 3:  4.0,
    4:  3.0, 5:  2.0, 6:  1.5,
    7:  1.0, 8:  1.5, 9:  2.5,
}

# Gauge B's seasonal m3/s magnitude.  Note: the absolute scale differs
# from River A — this is the whole point of Method 5.  Same regional
# seasonality, different river.
SEASONAL_M3S = {m: v * 10 for m, v in SEASONAL_MM3.items()}


def _hydro_to_calendar(hydro_year: int, hm: int) -> tuple:
    """A hydro year runs Oct(Y) → Sep(Y+1).  Map (hydro_year, hydro_month)
    onto a calendar (year, month)."""
    return (hydro_year if hm >= 10 else hydro_year + 1, hm)


# --------------------------------------------------------------------------
# Monthly data
# --------------------------------------------------------------------------

def gen_monthly() -> dict:
    """{(cal_year, cal_month): Mm3}.  Each value = seasonal × random[0.5, 1.5]."""
    random.seed(42)
    rec: dict = {}
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            rec[(cy, cm)] = round(SEASONAL_MM3[hm] * random.uniform(0.5, 1.5), 3)
    return rec


def write_monthly(path: str, rec: dict) -> None:
    """Write a 5-line header followed by one hydro-year row of 12 values."""
    with open(path, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Description : {os.path.basename(path)} (mock)\n')
        f.write('Units       : Mm3/month\n')
        f.write('Hydro order : Oct Nov Dec Jan Feb Mar Apr May Jun Jul Aug Sep\n')
        f.write('-' * 80 + '\n')
        for hy in YEARS:
            row = [f'{hy:4d}']
            for hm in HYDRO_MONTHS:
                cy, cm = _hydro_to_calendar(hy, hm)
                row.append(f'{rec[(cy, cm)]:8.3f}')
            f.write(' '.join(row) + '\n')


# --------------------------------------------------------------------------
# Daily data
# --------------------------------------------------------------------------

def gen_daily(seed: int, scale: float, gap_months=None,
              keep_only=None) -> list:
    """Build a list of DailyRecord for the full 6-hydro-year window.

    Parameters
    ----------
    seed       : RNG seed; pick the same seed when you want two daily
                 files to share their underlying noise.
    scale      : multiplies SEASONAL_M3S so different gauges look different
                 in absolute magnitude.
    gap_months : iterable of (cal_year, cal_month) — written as all-missing.
    keep_only  : iterable of (cal_year, cal_month) — if set, every record
                 *not* in this set is dropped from the file (use this to
                 simulate file 2 covering only part of the period).
    """
    random.seed(seed)
    gap_months = set(gap_months or [])
    keep_only = set(keep_only) if keep_only is not None else None

    records = []
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            if keep_only is not None and (cy, cm) not in keep_only:
                continue
            dim = calendar.monthrange(cy, cm)[1]
            if (cy, cm) in gap_months:
                values = [-99.99] * dim
            else:
                base = SEASONAL_M3S[hm] * scale
                values = [round(base * random.uniform(0.7, 1.3), 3)
                          for _ in range(dim)]
            records.append(DailyRecord(year=cy, month=cm, v=values))
    return records


def write_daily(path: str, records: list, label: str) -> None:
    write_daily_file(path, records, {
        'monthly_file': '',
        'daily_file_1': label,
        'daily_file_2': '',
        'method_str':   'mock data',
    })


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    monthly = gen_monthly()
    write_monthly(os.path.join(DATA_DIR, 'target.MON'), monthly)

    # Gauge A — primary daily record.
    write_daily(
        os.path.join(DATA_DIR, 'gauge_a_complete.DAY'),
        gen_daily(seed=43, scale=1.0),
        label='gauge_a_complete.DAY',
    )

    # Gauge A with two whole-month gaps:
    #   - June 2003 (mid-record)  → covered by gauge B
    #   - June 2005 (later)       → not covered by gauge B → tier-3 patch
    write_daily(
        os.path.join(DATA_DIR, 'gauge_a_with_gaps.DAY'),
        gen_daily(seed=43, scale=1.0, gap_months={(2003, 6), (2005, 6)}),
        label='gauge_a_with_gaps.DAY',
    )

    # Gauge B — different river / gauge.  Smaller absolute scale (×0.3),
    # different RNG seed.

    # Variant 1: only covers hydro year 2002 (Oct-2002 .. Sep-2003), so
    # it fills Jun-2003's gap but not Jun-2005's.
    keep_b_partial = {_hydro_to_calendar(2002, hm) for hm in HYDRO_MONTHS}
    write_daily(
        os.path.join(DATA_DIR, 'gauge_b_partial.DAY'),
        gen_daily(seed=99, scale=0.3, keep_only=keep_b_partial),
        label='gauge_b_partial.DAY',
    )

    # Variant 2: covers BOTH hydro years that contain the gauge-A gaps —
    # 2002 (cal Jun 2003) and 2004 (cal Jun 2005).  With this file, both
    # gauge-A gaps fill cleanly via tier 2; tier 3 never fires.
    keep_b_full = (
        {_hydro_to_calendar(2002, hm) for hm in HYDRO_MONTHS}
        | {_hydro_to_calendar(2004, hm) for hm in HYDRO_MONTHS}
    )
    write_daily(
        os.path.join(DATA_DIR, 'gauge_b_full.DAY'),
        gen_daily(seed=99, scale=0.3, keep_only=keep_b_full),
        label='gauge_b_full.DAY',
    )

    print(f'Wrote 5 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
