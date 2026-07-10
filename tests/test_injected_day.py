"""Injected-day normalisation: FDC quantile mapping, seam blending, and
the always-on spike audit (PATCH_EXCEED).

Covers the three sub-processes added so cross-river fills look like the
target river rather than the donor:

* ``_fdc_map`` — rank-position transfer between daily flow-duration curves
* ``_resolve_fdc`` — pool selection (month → annual → linear fallback)
* ``_blend_seams`` — log-interpolated edge correction on spliced gap runs
* the injected-day spike audit report section (always on for method 5)
* end-to-end: a flashy file-2 spike is flagged by the audit, tamed by
  ``daily_fdc_mapping``, and splice seams are smoothed by ``seam_blend``
  — while every configuration preserves the monthly mass balance.
"""

import calendar
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import (
    DisagConfig,
    DisagMethod,
    _blend_seams,
    _daily_fdc_pools,
    _fdc_map,
    _resolve_fdc,
    disaggregate,
)
from disag.files import DailyRecord, MISSING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ramp(year: int, month: int, base: float, step: float) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(
        year=year, month=month, v=[base + step * d for d in range(dim)]
    )


def _record(records, year, month):
    return next(r for r in records if (r.year, r.month) == (year, month))


def _month_sum_mm3(rec) -> float:
    return sum(rec.v) * 86400 / 1e6


def _scenario():
    """June-only run: file 1 is a smooth ramp, file 2 the same shape ×10
    with a large spike on day 11 every year; June 2004 is missing days
    10–12 from file 1, so those three days are tier-2 injected."""
    years = range(2000, 2005)
    gen = {(y, 6): 30.0 for y in years}
    f1 = {(y, 6): _ramp(y, 6, 1.0, 0.1) for y in years}
    f1[(2004, 6)] = DailyRecord(
        year=2004, month=6,
        v=[MISSING if d in (9, 10, 11) else 1.0 + 0.1 * d for d in range(30)],
    )
    f2 = {}
    for y in years:
        rec = _ramp(y, 6, 10.0, 1.0)
        rec.v[10] = 300.0            # the donor catchment's flood day
        f2[(y, 6)] = rec
    return gen, [f1, f2]


def _run(config=None):
    gen, files = _scenario()
    return disaggregate(DisagMethod.PATCH_EXCEED, gen, files, 2,
                        config=config)


# ---------------------------------------------------------------------------
# _fdc_map unit behaviour
# ---------------------------------------------------------------------------

class FdcMapTests(unittest.TestCase):
    def test_zero_maps_to_zero(self):
        self.assertEqual(_fdc_map(0.0, [1.0, 2.0], [10.0, 20.0]), 0.0)
        self.assertEqual(_fdc_map(-5.0, [1.0, 2.0], [10.0, 20.0]), 0.0)

    def test_identity_when_pools_match(self):
        pool = [1.0, 2.0, 3.0, 4.0]
        for v in (1.0, 2.5, 3.9, 4.0):
            self.assertAlmostEqual(_fdc_map(v, pool, pool), v)

    def test_monotone(self):
        src = [1.0, 2.0, 5.0, 9.0]
        dst = [0.5, 0.9, 1.1, 2.0]
        vals = [_fdc_map(v, src, dst) for v in (1.5, 2.0, 4.0, 8.0)]
        self.assertEqual(vals, sorted(vals))

    def test_above_source_max_ratio_extrapolates(self):
        # 4 is 2× the source max → 2× the destination max, not clamped
        self.assertAlmostEqual(
            _fdc_map(4.0, [1.0, 2.0], [10.0, 30.0]), 60.0
        )

    def test_below_source_min_ratio_extrapolates(self):
        self.assertAlmostEqual(
            _fdc_map(0.5, [1.0, 2.0], [10.0, 30.0]), 5.0
        )

    def test_tied_source_values_take_midpoint_rank(self):
        # value 2 spans ranks 1..2 of [1, 2, 2, 3] → midpoint rank 1.5 of
        # 0..3 → p = 0.5 → destination midpoint
        self.assertAlmostEqual(
            _fdc_map(2.0, [1.0, 2.0, 2.0, 3.0], [0.0, 10.0, 20.0, 30.0]),
            15.0,
        )


# ---------------------------------------------------------------------------
# _resolve_fdc pool selection
# ---------------------------------------------------------------------------

class ResolveFdcTests(unittest.TestCase):
    def _pools(self):
        f1 = {(2000, 6): _ramp(2000, 6, 1.0, 0.1)}
        f2 = {(2000, 6): _ramp(2000, 6, 10.0, 1.0)}
        return _daily_fdc_pools([f1, f2])

    def test_source_file_1_is_identity(self):
        self.assertIsNone(_resolve_fdc(self._pools(), 0, 6))

    def test_month_pool_preferred(self):
        got = _resolve_fdc(self._pools(), 1, 6)
        self.assertIsNotNone(got)
        self.assertEqual(got[2], 6)

    def test_annual_fallback_when_month_pool_flat(self):
        f1 = {(2000, 6): _ramp(2000, 6, 1.0, 0.1),
              (2000, 7): DailyRecord(year=2000, month=7, v=[5.0] * 31)}
        f2 = {(2000, 6): _ramp(2000, 6, 10.0, 1.0),
              (2000, 7): DailyRecord(year=2000, month=7, v=[50.0] * 31)}
        pools = _daily_fdc_pools([f1, f2])
        got = _resolve_fdc(pools, 1, 7)   # July pools are flat
        self.assertIsNotNone(got)
        self.assertEqual(got[2], 0)

    def test_none_when_no_usable_pools(self):
        pools = _daily_fdc_pools([
            {(2000, 6): DailyRecord(year=2000, month=6, v=[2.0] * 30)},
            {(2000, 6): DailyRecord(year=2000, month=6, v=[20.0] * 30)},
        ])
        self.assertIsNone(_resolve_fdc(pools, 1, 6))


# ---------------------------------------------------------------------------
# _blend_seams unit behaviour
# ---------------------------------------------------------------------------

class BlendSeamsTests(unittest.TestCase):
    def test_two_anchor_constant_correction(self):
        # Both anchors imply ×2 → the whole run lifts by exactly ×2.
        qD = [2.0, 1.0, 1.0, 1.0, 2.0]
        tiers = [1, 2, 2, 2, 1]
        n = _blend_seams(qD, tiers, lambda tier, d: 1.0)
        self.assertEqual(n, 1)
        for v in qD[1:4]:
            self.assertAlmostEqual(v, 2.0)
        self.assertEqual(qD[0], 2.0)
        self.assertEqual(qD[4], 2.0)

    def test_correction_is_capped(self):
        qD = [9.0, 1.0, 9.0]
        tiers = [1, 2, 1]
        _blend_seams(qD, tiers, lambda tier, d: 1.0)   # implied ×9 → cap ×3
        self.assertAlmostEqual(qD[1], 3.0)

    def test_one_sided_run_decays_towards_one(self):
        # Run touches the month start: only the right anchor exists, and
        # the correction weakens with distance from it.
        qD = [1.0, 1.0, 1.0, 3.0]
        tiers = [2, 2, 2, 1]
        n = _blend_seams(qD, tiers, lambda tier, d: 1.0)
        self.assertEqual(n, 1)
        self.assertTrue(1.0 < qD[0] < qD[1] < qD[2] < 3.0)

    def test_no_anchor_leaves_run_untouched(self):
        qD = [1.0, 1.0, 1.0]
        tiers = [2, 2, 2]
        n = _blend_seams(qD, tiers, lambda tier, d: 1.0)
        self.assertEqual(n, 0)
        self.assertEqual(qD, [1.0, 1.0, 1.0])

    def test_missing_source_at_anchor_is_skipped(self):
        qD = [2.0, 1.0, 1.0]
        tiers = [1, 2, 2]
        n = _blend_seams(qD, tiers, lambda tier, d: None)
        self.assertEqual(n, 0)
        self.assertEqual(qD[1:], [1.0, 1.0])


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

class ConfigValidationTests(unittest.TestCase):
    def test_non_bool_flags_rejected(self):
        with self.assertRaises(ValueError):
            DisagConfig(daily_fdc_mapping='yes')
        with self.assertRaises(ValueError):
            DisagConfig(seam_blend=1)

    def test_defaults_accepted(self):
        cfg = DisagConfig()
        self.assertFalse(cfg.daily_fdc_mapping)
        self.assertFalse(cfg.seam_blend)


# ---------------------------------------------------------------------------
# End-to-end: spike audit, FDC mapping, seam blending
# ---------------------------------------------------------------------------

class SpikeAuditTests(unittest.TestCase):
    def test_flashy_injected_day_is_flagged_by_default(self):
        _, log = _run()
        audit = [l for l in log if 'spike audit' in l]
        self.assertEqual(len(audit), 1)
        flagged = next(l for l in log if l.lstrip().startswith('flagged'))
        self.assertIn('1 of 3', flagged)
        worst = next(l for l in log if l.lstrip().startswith('worst'))
        self.assertIn('2004  6 day 11 (tier 2)', worst)

    def test_output_is_unchanged_by_the_audit(self):
        # The audit is report-only: default-config output matches a run
        # with an explicit all-off config.
        rec_a, _ = _run()
        rec_b, _ = _run(DisagConfig())
        for a, b in zip(rec_a, rec_b):
            self.assertEqual(a.v, b.v)


class FdcMappingE2ETests(unittest.TestCase):
    def test_mapping_tames_the_spike(self):
        rec_base, _ = _run()
        rec_fdc, log = _run(DisagConfig(daily_fdc_mapping=True))
        base = _record(rec_base, 2004, 6)
        fdc = _record(rec_fdc, 2004, 6)
        # Day 11 (index 10) carries file 2's flood; mapped, it lands at
        # file-1-plausible magnitude — far below the linear-scaled value.
        self.assertLess(fdc.v[10], base.v[10] * 0.5)
        flagged = next(l for l in log if l.lstrip().startswith('flagged'))
        self.assertIn('0 of 3', flagged)
        self.assertTrue(any('FDC-mapped' in l for l in log))
        self.assertTrue(any('Daily FDC mapping summary' in l for l in log))

    def test_mass_balance_holds(self):
        for cfg in (None, DisagConfig(daily_fdc_mapping=True),
                    DisagConfig(seam_blend=True),
                    DisagConfig(daily_fdc_mapping=True, seam_blend=True)):
            recs, _ = _run(cfg)
            self.assertAlmostEqual(
                _month_sum_mm3(_record(recs, 2004, 6)), 30.0, places=6
            )


class CrossRiverDonorTests(unittest.TestCase):
    """Tier-3 donor sourced from FILE 2 — the cross-river case FDC mapping
    exists for. File 1 has no complete month (its donor pool is empty) and
    file 2 is absent for the target month, so the gap days must come from
    a file-2 donor year and ``exceed_donor_file_idx == 1``."""

    def _scenario(self):
        years = range(2000, 2005)
        gen = {(y, 6): 30.0 for y in years}
        # File 1 exists only for the target month, minus the gap days —
        # zero complete months, so it can never be the donor pool.
        f1 = {(2004, 6): DailyRecord(
            year=2004, month=6,
            v=[MISSING if d in (9, 10, 11) else 1.0 + 0.1 * d
               for d in range(30)],
        )}
        # File 2: complete flashy Junes for the donor years, but missing
        # the target month entirely (no tier-2 fill possible).
        f2 = {}
        for y in range(2000, 2004):
            rec = _ramp(y, 6, 10.0, 1.0)
            rec.v[10] = 300.0
            f2[(y, 6)] = rec
        return gen, [f1, f2]

    def _run(self, config=None):
        gen, files = self._scenario()
        return disaggregate(DisagMethod.PATCH_EXCEED, gen, files, 2,
                            config=config)

    def test_donor_comes_from_file_2(self):
        _, log = self._run()
        self.assertTrue(
            any('patched from donor: file 2' in l for l in log), log)

    def test_flashy_donor_day_flagged_without_mapping(self):
        _, log = self._run()
        worst = next(l for l in log if l.lstrip().startswith('worst'))
        self.assertIn('day 11 (tier 3)', worst)

    def test_fdc_mapping_reshapes_the_donor(self):
        rec_base, _ = self._run()
        rec_fdc, log = self._run(DisagConfig(daily_fdc_mapping=True))
        base = _record(rec_base, 2004, 6)
        fdc = _record(rec_fdc, 2004, 6)
        # The donor's flood day (300, its curve max) must land at file 1's
        # curve max (~3.9), not at donor scale.
        self.assertLess(fdc.v[10], base.v[10] * 0.5)
        # 123 audited: the four donor-pool Junes are file-2 whole-month
        # fills (4 × 30) plus the 3 tier-3 donor days in 2004.
        flagged = next(l for l in log if l.lstrip().startswith('flagged'))
        self.assertIn('0 of 123', flagged)
        self.assertTrue(any('123 injected day(s) mapped' in l for l in log))

    def test_seam_blend_works_on_donor_fills(self):
        recs, log = self._run(
            DisagConfig(daily_fdc_mapping=True, seam_blend=True))
        self.assertTrue(any('seam-blended 1 gap(s)' in l for l in log), log)
        self.assertFalse(any(v == MISSING for v in _record(recs, 2004, 6).v))

    def test_whole_month_donor_replacement_is_fdc_mapped(self):
        recs, log = self._run(DisagConfig(
            daily_fdc_mapping=True, whole_month_fraction=0.05))
        # 3/30 missing ≥ 5 % → whole month rebuilt from the file-2 donor,
        # every day FDC-mapped.
        self.assertTrue(
            any('whole-month donor replacement' in l for l in log), log)
        # 150 mapped: 4 × 30 file-2 whole-month fills + the 30-day donor
        # rebuild of 2004 June.
        self.assertTrue(any('150 injected day(s) mapped' in l for l in log))
        flagged = next(l for l in log if l.lstrip().startswith('flagged'))
        self.assertIn('0 of 150', flagged)
        rec = _record(recs, 2004, 6)
        # Mass balance survives the non-linear whole-month reshaping.
        self.assertAlmostEqual(_month_sum_mm3(rec), 30.0, places=6)


class SeamBlendE2ETests(unittest.TestCase):
    def test_seams_are_smoothed(self):
        rec_base, _ = _run()
        rec_blend, log = _run(DisagConfig(seam_blend=True))
        base = _record(rec_base, 2004, 6)
        blend = _record(rec_blend, 2004, 6)
        # The step from the last observed day (index 8) into the fill
        # (index 9) shrinks when the fill is anchored to its neighbours.
        step_base = abs(base.v[9] - base.v[8])
        step_blend = abs(blend.v[9] - blend.v[8])
        self.assertLess(step_blend, step_base)
        self.assertTrue(any('Seam blending summary' in l for l in log))
        self.assertTrue(any('seam-blended 1 gap(s)' in l for l in log))

    def test_whole_month_replacement_has_no_seams(self):
        recs, log = _run(DisagConfig(seam_blend=True,
                                     whole_month_fraction=0.05))
        # 3/30 missing ≥ 5% → whole month rebuilt from file 2 — coherent,
        # nothing to blend.
        summary = next(l for l in log if 'Seam blending summary' in l)
        self.assertIn('0 gap run(s)', summary)
