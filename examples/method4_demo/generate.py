#!/usr/bin/env python3
"""Generate the method 4 (EVEN) demo dataset.

Method 4 distributes each month's volume evenly across its days — every
day in a 30-day month gets exactly ``volume / 30``, every day in a
31-day month gets ``volume / 31``. No daily input file is needed.

This is the right method when no observed daily record exists at all
and there's nowhere to borrow a shape from. The output flat-lines
within each month, but the monthly totals are correct.

Output is just a target.MON.
"""

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

YEARS = list(range(2000, 2003))
HYDRO_MONTHS = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

SEASONAL_MM3 = {
    10: 3.5, 11: 4.5, 12: 5.0,
    1:  5.0, 2:  4.5, 3:  4.0,
    4:  3.0, 5:  2.0, 6:  1.5,
    7:  1.0, 8:  1.5, 9:  2.5,
}


def _hydro_to_calendar(hy: int, hm: int) -> tuple:
    return (hy if hm >= 10 else hy + 1, hm)


def gen_monthly() -> dict:
    random.seed(31)
    return {
        _hydro_to_calendar(hy, hm): round(SEASONAL_MM3[hm] * random.uniform(0.6, 1.4), 3)
        for hy in YEARS for hm in HYDRO_MONTHS
    }


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


def main() -> None:
    write_monthly(os.path.join(DATA_DIR, 'target.MON'), gen_monthly())
    print(f'Wrote 1 mock file to {DATA_DIR}')


if __name__ == '__main__':
    main()
