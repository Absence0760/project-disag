#!/usr/bin/env python3
"""Generate the method 3 (INCREMENTAL) demo dataset.

Method 3 builds the daily shape from ``file 1 − file 2`` — the runoff
*between* two gauges on the same river (downstream minus upstream).
Negative differences are clamped to zero before the disag formula's
normalisation.

Mock dataset puts a downstream gauge with consistently larger values
than an upstream gauge, so every (down − up) is positive and
non-trivial.
"""

import calendar
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from disag.files import DailyRecord, write_daily_file  # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

YEARS = list(range(2000, 2003))
HYDRO_MONTHS = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
RUN_DATE = '2026-01-01 00:00:00'

# River A's "incremental runoff" volumes (downstream − upstream).
# In real use, target.MON holds the modelled volume of the *increment*,
# not of either gauge — the disag formula scales the difference shape
# to that monthly increment volume.
SEASONAL_MM3 = {
    10: 1.5, 11: 2.0, 12: 2.5,
    1:  2.5, 2:  2.0, 3:  1.8,
    4:  1.2, 5:  0.8, 6:  0.5,
    7:  0.4, 8:  0.5, 9:  1.0,
}
SEASONAL_M3S = {m: v * 10 for m, v in SEASONAL_MM3.items()}


def _hydro_to_calendar(hy: int, hm: int) -> tuple:
    return (hy if hm >= 10 else hy + 1, hm)


def gen_monthly() -> dict:
    random.seed(23)
    return {
        _hydro_to_calendar(hy, hm): round(SEASONAL_MM3[hm] * random.uniform(0.7, 1.3), 3)
        for hy in YEARS for hm in HYDRO_MONTHS
    }


def gen_daily(seed: int, scale: float) -> list:
    """Daily series at a chosen absolute scale.  Both gauges share an
    underlying noise pattern so (downstream − upstream) is smooth."""
    random.seed(seed)
    out = []
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            dim = calendar.monthrange(cy, cm)[1]
            base = SEASONAL_M3S[hm] * scale
            values = [round(base * random.uniform(0.7, 1.3), 3) for _ in range(dim)]
            out.append(DailyRecord(year=cy, month=cm, v=values))
    return out


def write_monthly(path: str, rec: dict) -> None:
    with open(path, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Description : {os.path.basename(path)} (mock)  Units: Mm3/month\n')
        f.write('Columns     : Oct Nov Dec | Jan Feb Mar Apr May Jun Jul Aug Sep   (hydro order)\n')
        f.write('NOTE        : row label = hydro year Y; calendar June (Y+1) sits in column 9 of row Y\n')
        f.write('-' * 80 + '\n')
        for hy in YEARS:
            row = [f'{hy:4d}']
            for hm in HYDRO_MONTHS:
                row.append(f'{rec[_hydro_to_calendar(hy, hm)]:8.3f}')
            f.write(' '.join(row) + '\n')


def write_daily(path: str, recs: list, label: str) -> None:
    write_daily_file(path, recs, {
        'monthly_file': '', 'daily_file_1': label, 'daily_file_2': '',
        'method_str': 'mock data', 'run_date': RUN_DATE,
    })


def main() -> None:
    write_monthly(os.path.join(DATA_DIR, 'target.MON'), gen_monthly())
    # Same RNG seed for both gauges so the "down − up" pattern is
    # smooth, but downstream is consistently 3x the upstream scale.
    write_daily(os.path.join(DATA_DIR, 'gauge_downstream.DAY'),
                gen_daily(seed=29, scale=3.0), 'gauge_downstream.DAY')
    write_daily(os.path.join(DATA_DIR, 'gauge_upstream.DAY'),
                gen_daily(seed=29, scale=1.0), 'gauge_upstream.DAY')
    print(f'Wrote 3 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
