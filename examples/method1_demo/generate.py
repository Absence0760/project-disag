#!/usr/bin/env python3
"""Generate the method 1 (PATCH_CAL) demo dataset.

Method 1 patches missing days in a target month from the *closest-
volume* same calendar month in another year — provided that year's
daily record for that month is complete.

The mock dataset rigs four calendar Junes to specific monthly volumes
so the donor selection is unambiguous and easy to reason about by hand:

    cal Jun 2001 → 1.000 Mm³        |  daily complete
    cal Jun 2002 → 2.500 Mm³ (target, gappy in daily file)
    cal Jun 2003 → 2.600 Mm³        |  daily complete  ← closest match
    cal Jun 2004 → 4.000 Mm³        |  daily complete

|2.5 − 2.6| = 0.1 wins → June 2002's missing days are patched from
June 2003's daily record.
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

YEARS = list(range(2000, 2004))     # 4 hydro years → 48 months → 4 Junes
HYDRO_MONTHS = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
RUN_DATE = '2026-01-01 00:00:00'

SEASONAL_MM3 = {
    10: 3.5, 11: 4.5, 12: 5.0,
    1:  5.0, 2:  4.5, 3:  4.0,
    4:  3.0, 5:  2.0, 6:  1.5,
    7:  1.0, 8:  1.5, 9:  2.5,
}
SEASONAL_M3S = {m: v * 10 for m, v in SEASONAL_MM3.items()}

# Override the four Junes to known values so the closest-volume match
# is unambiguous and the walkthrough can show the arithmetic by hand.
JUNE_OVERRIDES = {
    (2001, 6): 1.000,
    (2002, 6): 2.500,
    (2003, 6): 2.600,
    (2004, 6): 4.000,
}


def _hydro_to_calendar(hy: int, hm: int) -> tuple:
    return (hy if hm >= 10 else hy + 1, hm)


def gen_monthly() -> dict:
    random.seed(11)
    rec: dict = {}
    for hy in YEARS:
        for hm in HYDRO_MONTHS:
            cy, cm = _hydro_to_calendar(hy, hm)
            rec[(cy, cm)] = round(SEASONAL_MM3[hm] * random.uniform(0.6, 1.4), 3)
    rec.update(JUNE_OVERRIDES)
    return rec


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
    # Gap the target month — cal Jun 2002 is on hydro year 2001's row,
    # daily column 9.  The patch year should be 2003 (closest volume).
    write_daily(os.path.join(DATA_DIR, 'gauge_with_gap.DAY'),
                gen_daily(seed=11, gap_months={(2002, 6)}),
                'gauge_with_gap.DAY')
    print(f'Wrote 2 mock files to {DATA_DIR}')


if __name__ == '__main__':
    main()
