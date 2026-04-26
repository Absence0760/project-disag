#!/usr/bin/env python3
"""Generate the method 0 (ONE_FILE) demo dataset.

Method 0's defining behaviour: any month with even one missing day in
file 1 is marked missing in the output. This generator emits two daily
files — one fully complete, one with a single whole-month gap — so the
walkthrough can show both code paths.
"""

import calendar
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import random   # noqa: E402

from disag.files import DailyRecord, write_daily_file  # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

YEARS = list(range(2000, 2003))     # 3 hydro years → 36 months
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
    random.seed(7)
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
    write_daily(os.path.join(DATA_DIR, 'gauge_complete.DAY'),
                gen_daily(seed=11), 'gauge_complete.DAY')
    # One whole-month gap: cal Jun 2002 (hydro year 2001, column 9)
    write_daily(os.path.join(DATA_DIR, 'gauge_with_gap.DAY'),
                gen_daily(seed=11, gap_months={(2002, 6)}),
                'gauge_with_gap.DAY')
    print(f'Wrote 3 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
