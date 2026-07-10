#!/usr/bin/env python3
"""
Ground-truth evaluation of Method 5's injected-day normalisation knobs
(daily FDC quantile mapping, seam blending) — the runnable source of the
results table in docs/method5.md.

Builds a synthetic world where the truth is known:

  * River A (the target): smooth response — high baseflow, slow recession.
  * Gauge B (the donor): same regional rain, but flashy — sharp spikes,
    fast recession, different absolute scale.

gen_monthly comes from A's true daily series, file 1 is A's gauge with
punched gaps, file 2 is B's gauge (occasionally missing whole months so
tier 3 fires). Every punched day's true value is known, so each config's
fill error is measured directly rather than eyeballed.

Run from the repo root:
    python3 examples/injected_day_eval/evaluate.py            # seeds 42 7 123
    python3 examples/injected_day_eval/evaluate.py --seed 5   # one custom seed

Columns:
    injMAE / injRMSE — error on the injected (punched) days, m3/s
    r_p95 / r_max    — P95 / max of output÷truth on injected days
                       (the "one huge flow" symptom is a large r_max)
    realMAE          — error on the REAL days of months containing fills
                       (the monthly-sum normalisation spreads an inflated
                       fill onto the observed days too)
    seamMAE          — |output step − true step| across gap boundaries
    flags            — injected-day spike-audit count from the .rep
"""

import argparse
import calendar
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from disag.algorithm import DisagConfig, DisagMethod, disaggregate  # noqa: E402
from disag.files import DailyRecord, MISSING  # noqa: E402

N_YEARS = 20
START_YEAR = 1990          # hydro years 1990-10 .. 2010-09

CONFIGS = [
    ('baseline (linear scale)', DisagConfig()),
    ('fdc', DisagConfig(daily_fdc_mapping=True)),
    ('seam', DisagConfig(seam_blend=True)),
    ('fdc+seam', DisagConfig(daily_fdc_mapping=True, seam_blend=True)),
    ('fdc+seam+wm50', DisagConfig(daily_fdc_mapping=True, seam_blend=True,
                                  whole_month_fraction=0.5)),
]


def _months():
    y, m = START_YEAR, 10
    end = (START_YEAR + N_YEARS, 9)
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def build_world(seed):
    """(gen_monthly, [file1, file2], truth_a, punched) for one seed."""
    rng = random.Random(seed)
    truth_a = {}
    gen, f1, f2, punched = {}, {}, {}, {}
    qa, qb = 6.0, 1.5
    for (y, m) in _months():
        dim = calendar.monthrange(y, m)[1]
        wet = m in (10, 11, 12, 1, 2, 3)
        p_event = 0.25 if wet else 0.06
        intensity = 8.0 if wet else 2.0
        va, vb = [], []
        for _ in range(dim):
            rain = (rng.expovariate(1.0 / intensity)
                    if rng.random() < p_event else 0.0)
            qa = 0.95 * qa + 0.05 * 5.0 + 0.35 * rain * math.exp(rng.gauss(0, 0.15))
            qb = 0.55 * qb + 0.45 * 1.2 + 0.85 * rain * math.exp(rng.gauss(0, 0.15))
            va.append(qa)
            vb.append(qb)
        truth_a[(y, m)] = va
        gen[(y, m)] = sum(va) * 86400 / 1e6
        v1, v2 = list(va), list(vb)
        gone = set()
        r = rng.random()
        if r < 0.05:                    # whole month gone from file 1
            gone = set(range(dim))
        elif r < 0.13:                  # most of the month gone
            n = int(dim * rng.uniform(0.6, 0.9))
            start = rng.randrange(dim - n + 1)
            gone = set(range(start, start + n))
        elif r < 0.33:                  # a mid-month run of 3-10 days
            n = rng.randint(3, 10)
            start = rng.randrange(1, max(2, dim - n))   # keep an anchor day
            gone = set(range(start, start + n))
        for d in gone:
            v1[d] = MISSING
        if rng.random() < 0.10:         # file 2 loses whole months sometimes
            v2 = [MISSING] * dim
        f1[(y, m)] = DailyRecord(year=y, month=m, v=v1)
        f2[(y, m)] = DailyRecord(year=y, month=m, v=v2)
        punched[(y, m)] = gone
    return gen, [f1, f2], truth_a, punched


def score(records, report, truth_a, punched):
    by_ym = {(r.year, r.month): r for r in records}
    inj_err, inj_ratio, real_err, seam_err = [], [], [], []
    for ym, gone in punched.items():
        rec = by_ym.get(ym)
        if rec is None or not gone or any(v == MISSING for v in rec.v):
            continue
        truth = truth_a[ym]
        dim = len(truth)
        for d in range(dim):
            e = rec.v[d] - truth[d]
            if d in gone:
                inj_err.append(e)
                if truth[d] > 0:
                    inj_ratio.append(rec.v[d] / truth[d])
            else:
                real_err.append(e)
        for d in gone:
            for nb in (d - 1, d + 1):
                if 0 <= nb < dim and nb not in gone:
                    seam_err.append(abs((rec.v[d] - rec.v[nb])
                                        - (truth[d] - truth[nb])))
    flags = 0
    for line in report:
        if line.lstrip().startswith('flagged'):
            flags = int(line.split(':')[1].split('of')[0])

    def rmse(errs):
        return math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else 0.0

    def mae(errs):
        return sum(abs(e) for e in errs) / len(errs) if errs else 0.0

    return {
        'n_inj': len(inj_err),
        'inj_mae': mae(inj_err),
        'inj_rmse': rmse(inj_err),
        'ratio_p95': (sorted(inj_ratio)[int(0.95 * len(inj_ratio))]
                      if inj_ratio else 0.0),
        'ratio_max': max(inj_ratio) if inj_ratio else 0.0,
        'real_mae': mae(real_err),
        'seam_mae': mae(seam_err),
        'flags': flags,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('--seed', type=int, action='append',
                        help='seed(s) to evaluate (repeatable); '
                             'default: 42 7 123, the docs/method5.md set')
    args = parser.parse_args()
    seeds = args.seed or [42, 7, 123]

    header = (f"{'config':26s} {'injMAE':>7s} {'injRMSE':>8s} {'r_p95':>6s} "
              f"{'r_max':>6s} {'realMAE':>8s} {'seamMAE':>8s} {'flags':>6s}")
    for seed in seeds:
        gen, files, truth_a, punched = build_world(seed)
        print(f'=== seed {seed} ===')
        print(header)
        print('-' * len(header))
        n_inj = 0
        for name, cfg in CONFIGS:
            records, report = disaggregate(
                DisagMethod.PATCH_EXCEED, gen, files, 2, config=cfg)
            s = score(records, report, truth_a, punched)
            n_inj = s['n_inj']
            print(f"{name:26s} {s['inj_mae']:7.3f} {s['inj_rmse']:8.3f} "
                  f"{s['ratio_p95']:6.2f} {s['ratio_max']:6.2f} "
                  f"{s['real_mae']:8.3f} {s['seam_mae']:8.3f} "
                  f"{s['flags']:6d}")
        print(f'({n_inj} injected days scored; units m3/s; '
              'ratio = output/truth on injected days)\n')


if __name__ == '__main__':
    main()
