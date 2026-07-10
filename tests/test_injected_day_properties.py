"""Invariant and edge-case coverage for the injected-day normalisation
features (PATCH_EXCEED): FDC quantile mapping, seam blending, spike audit.

Two layers:

* ``RandomisedInvariantTests`` — a seeded synthetic world (smooth target
  river, flashy cross-river gauge, punched gaps) run under every knob
  combination, asserting the properties that must hold for *any* input:
  monthly mass balance, tier accounting that adds up, report counters
  that match the decision log, opt-in knobs that leave pure-tier-1
  months untouched, and the never-worse missing-month guarantee.
* Directed edge-case tests — the specific paths the scenario tests in
  ``test_injected_day.py`` don't reach: annual-pool and linear-factor
  FDC fallbacks (and their report lines), multiple seam runs in one
  month, the zero-observed even-fill interaction, and a leap-February
  donor under FDC mapping.
"""

import calendar
import math
import os
import random
import re
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import (
    DisagConfig,
    DisagMethod,
    MISSING,
    _resolve_fdc,
    disaggregate,
)
from disag.files import DailyRecord


# ---------------------------------------------------------------------------
# Report parsing helpers — the .rep text is the public contract, so the
# invariants are asserted against it rather than against internals.
# ---------------------------------------------------------------------------

def _tier_days(log):
    """{1: n, 2: n, 3: n} from the tier coverage summary."""
    out = {}
    for line in log:
        m = re.match(r'\s*Tier (\d) .*?:\s*(\d+) day', line)
        if m:
            out[int(m.group(1))] = int(m.group(2))
    return out


def _flagged(log):
    """(flagged, audited) from the spike audit, or None if absent."""
    for line in log:
        m = re.match(r'\s*flagged : (\d+) of (\d+)', line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _fdc_summary(log):
    """(mapped, extrapolated) from the FDC mapping summary, or None."""
    for line in log:
        m = re.match(
            r'Daily FDC mapping summary : (\d+) injected day\(s\) mapped, '
            r'(\d+) above the source curve', line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _decision_rows(log):
    """{(year, month): (f1, f2, oth, note)} from the decision log."""
    rows = {}
    in_log = False
    for line in log:
        if line.startswith('Decision log'):
            in_log = True
            continue
        if not in_log:
            continue
        m = re.match(r'(\d{4})\s+(\d{1,2})\s+(\d+)\s+(\d+)\s+(\d+)\s+(.*)',
                     line)
        if m:
            rows[(int(m.group(1)), int(m.group(2)))] = (
                int(m.group(3)), int(m.group(4)), int(m.group(5)),
                m.group(6),
            )
        elif rows:
            break
    return rows


# ---------------------------------------------------------------------------
# Synthetic world: smooth River A (the target), flashy cross-river gauge B,
# seeded gap punching. Same construction as the ground-truth evaluation in
# docs/method5.md, shrunk to keep the suite fast.
# ---------------------------------------------------------------------------

def _months(start_year, n_years):
    y, m = start_year, 10
    end = (start_year + n_years, 9)
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _make_world(seed, n_years=6):
    rng = random.Random(seed)
    gen, f1, f2 = {}, {}, {}
    qa, qb = 6.0, 1.5
    for (y, m) in _months(2000, n_years):
        dim = calendar.monthrange(y, m)[1]
        wet = m in (10, 11, 12, 1, 2, 3)
        va, vb = [], []
        for _ in range(dim):
            rain = (rng.expovariate(1.0 / (8.0 if wet else 2.0))
                    if rng.random() < (0.25 if wet else 0.06) else 0.0)
            qa = 0.95 * qa + 0.25 + 0.35 * rain * math.exp(rng.gauss(0, .15))
            qb = 0.55 * qb + 0.54 + 0.85 * rain * math.exp(rng.gauss(0, .15))
            va.append(qa)
            vb.append(qb)
        gen[(y, m)] = sum(va) * 86400 / 1e6
        v1, v2 = list(va), list(vb)
        r = rng.random()
        if r < 0.06:                    # whole month gone from file 1
            v1 = [-99.99] * dim
        elif r < 0.14:                  # most of the month gone
            n = int(dim * rng.uniform(0.6, 0.9))
            s = rng.randrange(dim - n + 1)
            for d in range(s, s + n):
                v1[d] = -99.99
        elif r < 0.34:                  # a mid-month run of 3-8 days
            n = rng.randint(3, 8)
            s = rng.randrange(1, max(2, dim - n))
            for d in range(s, s + n):
                v1[d] = -99.99
        if rng.random() < 0.10:         # file 2 loses whole months
            v2 = [-99.99] * dim
        f1[(y, m)] = DailyRecord(year=y, month=m, v=v1)
        f2[(y, m)] = DailyRecord(year=y, month=m, v=v2)
    return gen, [f1, f2]


SEEDS = (11, 42, 99)

CONFIGS = {
    'default': None,
    'fdc': DisagConfig(daily_fdc_mapping=True),
    'seam': DisagConfig(seam_blend=True),
    'fdc+seam': DisagConfig(daily_fdc_mapping=True, seam_blend=True),
    'wm50': DisagConfig(whole_month_fraction=0.5),
    'all': DisagConfig(daily_fdc_mapping=True, seam_blend=True,
                       whole_month_fraction=0.5),
}


class RandomisedInvariantTests(unittest.TestCase):
    """Properties that must hold for any input, any knob combination."""

    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        for seed in SEEDS:
            gen, files = _make_world(seed)
            for name, cfg in CONFIGS.items():
                records, log = disaggregate(
                    DisagMethod.PATCH_EXCEED, gen, files, 2, config=cfg)
                cls.runs[(seed, name)] = (gen, records, log)

    def _each(self):
        for (seed, name), (gen, records, log) in self.runs.items():
            with self.subTest(seed=seed, config=name):
                yield gen, records, log

    def test_monthly_mass_balance(self):
        # Every non-missing month must carry exactly the generated volume,
        # whatever reshaping happened inside it.
        for gen, records, _ in self._each():
            for rec in records:
                if any(v == MISSING for v in rec.v):
                    continue
                gen_val = gen.get((rec.year, rec.month))
                if gen_val is None:
                    continue
                self.assertAlmostEqual(
                    sum(rec.v) * 86400 / 1e6, gen_val,
                    delta=max(1e-9, gen_val * 1e-9),
                    msg=f'{rec.year}-{rec.month}',
                )

    def test_no_negative_output(self):
        for _, records, _ in self._each():
            for rec in records:
                for v in rec.v:
                    self.assertTrue(v >= 0 or v == MISSING)

    def test_decision_rows_account_for_every_day(self):
        # F1 + F2 + OTH == days in month for every non-missing,
        # non-even-fill month; 0 for missing months.
        for _, records, log in self._each():
            rows = _decision_rows(log)
            for rec in records:
                f1, f2, oth, note = rows[(rec.year, rec.month)]
                dim = calendar.monthrange(rec.year, rec.month)[1]
                if 'MISSING' in note:
                    self.assertTrue(all(v == MISSING for v in rec.v))
                elif 'even fill' not in note:
                    self.assertEqual(f1 + f2 + oth, dim,
                                     msg=f'{rec.year}-{rec.month}: {note}')

    def test_tier_summary_matches_decision_log(self):
        # The coverage summary is derived independently of the per-month
        # rows — they must agree (no even-fill months occur in this world:
        # all generated volumes are positive and shapes are non-zero).
        for _, records, log in self._each():
            rows = _decision_rows(log)
            tiers = _tier_days(log)
            live = [r for r in rows.values() if 'MISSING' not in r[3]]
            self.assertEqual(tiers[1], sum(r[0] for r in live))
            self.assertEqual(tiers[2], sum(r[1] for r in live))
            self.assertEqual(tiers[3], sum(r[2] for r in live))

    def test_spike_audit_counts_are_consistent(self):
        # audited == tier-2 + tier-3 days (file 1 has data in every
        # calendar month in this world, so every injected day is
        # auditable); flagged never exceeds audited.
        for _, records, log in self._each():
            tiers = _tier_days(log)
            audit = _flagged(log)
            if tiers[2] + tiers[3] == 0:
                self.assertIsNone(audit)
                continue
            flagged, audited = audit
            self.assertEqual(audited, tiers[2] + tiers[3])
            self.assertLessEqual(flagged, audited)

    def test_fdc_summary_counts_are_consistent(self):
        # Only file-2-sourced injections are mapped (file-1 donors are
        # identity), so tier2 <= mapped <= tier2 + tier3. Extrapolation
        # can never fire on real inputs: the source pool is built from
        # the same file the injected day comes from, so the day's value
        # is itself in the pool — the >max branch is defensive only.
        for _, records, log in self._each():
            summary = _fdc_summary(log)
            if summary is None:
                continue
            mapped, extrapolated = summary
            tiers = _tier_days(log)
            self.assertGreaterEqual(mapped, tiers[2])
            self.assertLessEqual(mapped, tiers[2] + tiers[3])
            self.assertEqual(extrapolated, 0)

    def test_default_config_is_identical_to_none(self):
        for seed in SEEDS:
            _, rec_none, _ = self.runs[(seed, 'default')]
            gen, files = _make_world(seed)
            rec_cfg, _ = disaggregate(
                DisagMethod.PATCH_EXCEED, gen, files, 2,
                config=DisagConfig())
            for a, b in zip(rec_none, rec_cfg):
                self.assertEqual(a.v, b.v)

    def test_knobs_never_touch_pure_tier1_months(self):
        # A month sourced 100% from file 1 must be bit-identical under
        # every knob combination — the options only act on injected days.
        for seed in SEEDS:
            _, base_records, base_log = self.runs[(seed, 'default')]
            rows = _decision_rows(base_log)
            base_by_ym = {(r.year, r.month): r for r in base_records}
            pure = [
                ym for ym, (f1, f2, oth, note) in rows.items()
                if f2 == 0 and oth == 0 and 'MISSING' not in note
            ]
            self.assertTrue(pure, 'world should contain pure-tier-1 months')
            for name in CONFIGS:
                _, records, _ = self.runs[(seed, name)]
                by_ym = {(r.year, r.month): r for r in records}
                for ym in pure:
                    self.assertEqual(
                        by_ym[ym].v, base_by_ym[ym].v,
                        msg=f'seed {seed} config {name} month {ym}',
                    )

    def test_knobs_never_create_missing_months(self):
        # Degrade-to-splice and report-only guarantees, generalised: any
        # month non-missing under the default stays non-missing under
        # every knob combination.
        for seed in SEEDS:
            _, base_records, _ = self.runs[(seed, 'default')]
            ok = {(r.year, r.month) for r in base_records
                  if all(v != MISSING for v in r.v)}
            for name in CONFIGS:
                _, records, _ = self.runs[(seed, name)]
                for rec in records:
                    if (rec.year, rec.month) in ok:
                        self.assertTrue(
                            all(v != MISSING for v in rec.v),
                            msg=f'seed {seed} config {name} '
                                f'{rec.year}-{rec.month}',
                        )

    def test_seam_blending_reduces_seam_steps_on_top_of_fdc(self):
        # The headline behaviour from the ground-truth evaluation, as a
        # regression guard: with FDC mapping on, adding seam blending must
        # shrink the aggregate step discontinuity at splice boundaries.
        for seed in SEEDS:
            with self.subTest(seed=seed):
                gap_steps = {}
                for name in ('fdc', 'fdc+seam'):
                    _, records, log = self.runs[(seed, name)]
                    rows = _decision_rows(log)
                    by_ym = {(r.year, r.month): r for r in records}
                    total = 0.0
                    for ym, (f1, f2, oth, note) in rows.items():
                        # Splice months only: mixed tier-1 + injected.
                        if 'MISSING' in note or 'whole-month' in note:
                            continue
                        if f1 == 0 or (f2 + oth) == 0:
                            continue
                        rec = by_ym[ym]
                        for d in range(1, len(rec.v)):
                            total += abs(rec.v[d] - rec.v[d - 1])
                    gap_steps[name] = total
                self.assertLess(gap_steps['fdc+seam'], gap_steps['fdc'])


# ---------------------------------------------------------------------------
# Directed edge cases
# ---------------------------------------------------------------------------

def _ramp(year, month, base, step):
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(year=year, month=month,
                       v=[base + step * d for d in range(dim)])


def _flat(year, month, value):
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(year=year, month=month, v=[value] * dim)


class FdcFallbackReportTests(unittest.TestCase):
    """The annual-pool and linear-factor fallback paths and their report
    lines — built but unasserted until now."""

    def _run(self, f2_builder):
        years = range(2000, 2005)
        gen = {}
        f1, f2 = {}, {}
        for y in years:
            for m in (6, 7):
                gen[(y, m)] = 30.0
                f1[(y, m)] = _ramp(y, m, 1.0, 0.1)
                f2[(y, m)] = f2_builder(y, m)
        # Punch a 3-day gap in June 2004 so tier 2 must inject.
        rec = f1[(2004, 6)]
        for d in (9, 10, 11):
            rec.v[d] = -99.99
        return disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2,
            config=DisagConfig(daily_fdc_mapping=True))

    def test_flat_month_pool_falls_back_to_annual(self):
        # File 2's Junes are flat (unusable month pool) but its Julys vary,
        # so the annual pool is usable — the mapping degrades one step.
        def build(y, m):
            return _flat(y, m, 20.0) if m == 6 else _ramp(y, m, 10.0, 1.0)
        records, log = self._run(build)
        self.assertTrue(
            any('annual-pool fallback in calendar month(s) [6]' in l
                for l in log), log[-8:])
        # Still mapped — not the linear factor.
        self.assertTrue(any('FDC-mapped' in l for l in log))

    def test_fully_flat_source_falls_back_to_linear(self):
        # File 2 is flat everywhere: month AND annual pools unusable, so
        # the linear mean-ratio factor applies and the note says so.
        records, log = self._run(lambda y, m: _flat(y, m, 20.0))
        self.assertTrue(
            any('linear-factor fallback in calendar month(s) [6]' in l
                for l in log), log[-8:])
        self.assertTrue(any('scale ×' in l for l in log))
        self.assertFalse(any('FDC-mapped' in l for l in log))

    def test_resolve_fdc_src_idx_out_of_range(self):
        from disag.algorithm import _daily_fdc_pools
        pools = _daily_fdc_pools([{(2000, 6): _ramp(2000, 6, 1.0, 0.1)}])
        self.assertIsNone(_resolve_fdc(pools, 1, 6))
        self.assertIsNone(_resolve_fdc(None, 1, 6))


class SeamEdgeCaseTests(unittest.TestCase):
    def test_two_gap_runs_in_one_month(self):
        years = range(2000, 2005)
        gen = {(y, 6): 30.0 for y in years}
        f1 = {(y, 6): _ramp(y, 6, 1.0, 0.1) for y in years}
        f2 = {(y, 6): _ramp(y, 6, 10.0, 1.0) for y in years}
        rec = f1[(2004, 6)]
        for d in (4, 5, 6, 14, 15, 16, 17):   # two separated runs
            rec.v[d] = -99.99
        records, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2,
            config=DisagConfig(daily_fdc_mapping=True, seam_blend=True))
        self.assertTrue(any('seam-blended 2 gap(s)' in l for l in log), log)
        self.assertTrue(
            any('1 gap run(s)' not in l and 'Seam blending summary' in l
                and '2 gap run(s)' in l for l in log))


class ZeroFlowInteractionTests(unittest.TestCase):
    def test_zero_target_month_stays_all_zero_under_knobs(self):
        years = range(2000, 2005)
        gen = {(y, 6): (0.0 if y == 2004 else 30.0) for y in years}
        f1 = {(y, 6): _ramp(y, 6, 1.0, 0.1) for y in years}
        f2 = {(y, 6): _ramp(y, 6, 10.0, 1.0) for y in years}
        rec = f1[(2004, 6)]
        for d in (9, 10, 11):
            rec.v[d] = -99.99
        records, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2,
            config=DisagConfig(daily_fdc_mapping=True, seam_blend=True))
        rec_out = next(r for r in records
                       if (r.year, r.month) == (2004, 6))
        self.assertTrue(all(v == 0.0 for v in rec_out.v))

    def test_even_fill_month_is_not_audited_or_counted(self):
        # All-zero observed shape + positive target → even fill. The
        # staged tier / audit / FDC counters must be discarded with the
        # shape, so the report shows no injected-day accounting at all.
        years = range(2000, 2005)
        gen = {(y, 6): 30.0 for y in years}
        f1, f2 = {}, {}
        for y in years:
            f1[(y, 6)] = _flat(y, 6, 0.0)
            f2[(y, 6)] = _flat(y, 6, 0.0)
        rec = f1[(2004, 6)]
        for d in (9, 10, 11):
            rec.v[d] = -99.99
        records, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2,
            config=DisagConfig(daily_fdc_mapping=True))
        rows = _decision_rows(log)
        self.assertIn('even fill', rows[(2004, 6)][3])
        self.assertIsNone(_flagged(log))
        summary = _fdc_summary(log)
        if summary is not None:
            self.assertEqual(summary[0], 0)
        # The even fill still delivers the monthly volume.
        rec_out = next(r for r in records
                       if (r.year, r.month) == (2004, 6))
        self.assertAlmostEqual(sum(rec_out.v) * 86400 / 1e6, 30.0,
                               places=6)


class LeapFebruaryFdcTests(unittest.TestCase):
    def test_leap_feb_cross_river_donor_under_fdc(self):
        # 29-day February target, donor drawn from file 2's leap
        # Februaries, FDC-mapped — the day-count bucketing and the
        # mapping must compose without dropping day 29.
        leap_years = (1996, 2000, 2004)
        gen = {(y, 2): 10.0 for y in leap_years}
        f1 = {(2004, 2): _ramp(2004, 2, 1.0, 0.1)}
        for d in (9, 10, 11):
            f1[(2004, 2)].v[d] = -99.99
        f2 = {(y, 2): _ramp(y, 2, 10.0, 1.0) for y in (1996, 2000)}
        records, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2,
            config=DisagConfig(daily_fdc_mapping=True, seam_blend=True))
        rec = next(r for r in records if (r.year, r.month) == (2004, 2))
        self.assertEqual(len(rec.v), 29)
        self.assertTrue(all(v != MISSING for v in rec.v))
        self.assertAlmostEqual(sum(rec.v) * 86400 / 1e6, 10.0, places=6)
        self.assertTrue(
            any('patched from donor: file 2' in l for l in log), log)


if __name__ == '__main__':
    unittest.main()
