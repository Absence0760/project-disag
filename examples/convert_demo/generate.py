#!/usr/bin/env python3
"""Generate the convert-demo fixture.

Emits a tiny synthetic monthly file in the source modelling layout
(.ans) so the converter end-to-end test can round-trip it through the
web handler without bundling real third-party data.

Layout produced (matches the fixed-width 8-char columns the .ans format
uses):

    yyyy<12 monthly values, 8 chars each><total><avg>

The integration suite uploads SAMPLE.ANS, runs /convert, and reads the
returned .mon back. The numbers here are arbitrary but include one
flood-year row where two adjacent fields touch (no separator) — the
hard case that the column-aware parser has to handle.
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Three hydro years; second year has a wet-season column where two
# adjacent 8-char fields touch (no whitespace between them).
ROWS = [
    (1990, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]),
    (1991, [9999.99, 14639.12, 13670.74, 100.0, 50.0, 25.0, 12.5, 6.25, 3.0, 2.0, 1.0, 0.5]),
    (1992, [12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]),
]


def _ans_line(year: int, vals: list[float]) -> str:
    parts = [f'{year:8d}'] + [f'{v:8.2f}' for v in vals]
    total = sum(vals)
    avg = total / 12
    parts.append(f'{total:10.2f}')
    parts.append(f'{avg:9.2f}')
    return ''.join(parts) + '\n'


def main() -> None:
    path = os.path.join(DATA_DIR, 'SAMPLE.ANS')
    with open(path, 'w') as fh:
        for year, vals in ROWS:
            fh.write(_ans_line(year, vals))
        # A blank trailer + AVERAGE row is what real source files emit
        # at the bottom; the converter skips them. Including one here
        # exercises that path too.
        fh.write('\n')
        fh.write('AVERAGE  any text trailing the data block is skipped\n')
    print(f'wrote {path}')


if __name__ == '__main__':
    main()
