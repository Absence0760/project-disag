#!/usr/bin/env python3
"""Generate the method 2 (PATCH_FILE) demo dataset.

Method 2 patches each missing day in file 1 with the corresponding day
from file 2. A month is marked missing only when the same day is
missing in *both* files.

Mock dataset uses two daily files with **orthogonal** gaps so each
file fills the other's holes exactly:

    gauge_a.DAY: cal Jun 2002 entirely missing,  rest complete
    gauge_b.DAY: cal Jun 2003 entirely missing,  rest complete

With both files supplied, both months get fully patched at the day
level (no whole-month miss); with just one file, the gap stays.
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

SEASONAL_MM3 = {
    10: 3.5, 11: 4.5, 12: 5.0,
    1:  5.0, 2:  4.5, 3:  4.0,
    4:  3.0, 5:  2.0, 6:  1.5,
    7:  1.0, 8:  1.5, 9:  2.5,
}
SEASONAL_M3S = {m: v * 10 for m, v in SEASONAL_MM3.items()}


def _hydro_to_calendar(hy: int, hm: int) -> tuple:
    return (hy if hm >= 10 else hy + 1, hm)


def gen_monthly() -> dict:
    random.seed(13)
    return {
        _hydro_to_calendar(hy, hm): round(SEASONAL_MM3[hm] * random.uniform(0.6, 1.4), 3)
        for hy in YEARS for hm in HYDRO_MONTHS
    }


def gen_daily(seed: int, gap_months=()) -> list:
    random.seed(seed)
    gap_months = set(gap_months)
    out = []
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            dim = calendar.monthrange(cy, cm)[1]
            if (cy, cm) in gap_months:
                values = [-99.99] * dim
            else:
                base = SEASONAL_M3S[hm]
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
    # Use the same seed for both gauges so the underlying base series
    # is identical — only the gap pattern differs.
    write_daily(os.path.join(DATA_DIR, 'gauge_a.DAY'),
                gen_daily(seed=17, gap_months={(2002, 6)}),
                'gauge_a.DAY')
    write_daily(os.path.join(DATA_DIR, 'gauge_b.DAY'),
                gen_daily(seed=17, gap_months={(2003, 6)}),
                'gauge_b.DAY')
    print(f'Wrote 3 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
