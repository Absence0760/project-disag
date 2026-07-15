"""Seam-smoothing test data: splice seams where the patched values land
exactly 2x or 4x above the neighbouring live (observed) days.

The scenarios pin the tier-2 scale factor to exactly 1.0 — file 2 is flat
2.0 m3/s in every June, matching file 1's complete Junes — and put the
whole seam in the *level* difference: file 1's observed June-2004 days sit
at 1.0 (2x scenario) or 0.5 (4x scenario) while the fill injects 2.0 on
each gap day. That makes the unblended seam ratios exact and the expected
``seam_blend`` corrections analytic:

* 2x seam — both anchors imply a x1/2 correction (inside the x3 cap): the
  fill lands exactly on the live level and the seam disappears.
* 4x seam — the implied x1/4 correction is capped at x1/3
  (``_SEAM_CORR_CAP``): the fill settles at 4/3 of the live level. The
  jump is tamed well below 4x but the cap leaves a visible residual.

In both cases only the patched days move. The live days at the seam edges
(last observed day before the gap, first observed day after it) are never
rewritten — blending observed data as well for "really radical" (>=4x)
seams is not implemented, and ``test_live_edge_days_are_never_rewritten``
documents that contract.
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
    _SEAM_CORR_CAP,
    disaggregate,
)
from disag.files import DailyRecord, MISSING


# Indices of the June-2004 gap days (days 10-12); anchors are index 8
# (last live day before the seam) and index 12 (first live day after it).
GAP = (9, 10, 11)
LAST_LIVE, FIRST_LIVE = GAP[0] - 1, GAP[-1] + 1


def _flat(year: int, month: int, value: float) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(year=year, month=month, v=[value] * dim)


def _seam_scenario(obs_level: float, obs_level_after: float = None):
    """June-only run with a controlled seam ratio of ``2.0 / obs_level``.

    File 1 is flat 2.0 for the complete Junes 2000-2003; June 2004 sits at
    ``obs_level`` (``obs_level_after`` beyond the gap, default the same)
    with the GAP days missing. File 2 is flat 2.0 in every June, so its
    complete-month mean equals file 1's and the tier-2 scale factor is
    exactly 1.0 — each gap day injects 2.0 unmodified.
    """
    after = obs_level if obs_level_after is None else obs_level_after
    years = range(2000, 2005)
    gen = {(y, 6): 30.0 for y in years}
    f1 = {(y, 6): _flat(y, 6, 2.0) for y in range(2000, 2004)}
    f1[(2004, 6)] = DailyRecord(
        year=2004, month=6,
        v=[MISSING if d in GAP else (obs_level if d < GAP[0] else after)
           for d in range(30)],
    )
    f2 = {(y, 6): _flat(y, 6, 2.0) for y in years}
    return gen, [f1, f2]


def _run(obs_level: float, config=None, obs_level_after: float = None):
    gen, files = _seam_scenario(obs_level, obs_level_after)
    return disaggregate(DisagMethod.PATCH_EXCEED, gen, files, 2,
                        config=config)


def _june(records) -> DailyRecord:
    return next(r for r in records if (r.year, r.month) == (2004, 6))


def _month_sum_mm3(rec) -> float:
    return sum(rec.v) * 86400 / 1e6


class SeamTestDataTests(unittest.TestCase):
    """Validate the fixture itself: without blending the splice really
    does land the patched days exactly 2x / 4x above the live edges."""

    def test_unblended_seam_is_exactly_2x(self):
        june = _june(_run(1.0)[0])
        self.assertAlmostEqual(june.v[GAP[0]] / june.v[LAST_LIVE], 2.0)
        self.assertAlmostEqual(june.v[GAP[-1]] / june.v[FIRST_LIVE], 2.0)

    def test_unblended_seam_is_exactly_4x(self):
        june = _june(_run(0.5)[0])
        self.assertAlmostEqual(june.v[GAP[0]] / june.v[LAST_LIVE], 4.0)
        self.assertAlmostEqual(june.v[GAP[-1]] / june.v[FIRST_LIVE], 4.0)

    def test_gap_days_are_tier2_fills(self):
        _, log = _run(1.0)
        self.assertTrue(
            any('gaps filled from file 2 (3 day(s)' in l for l in log), log)


class TwoXSeamBlendTests(unittest.TestCase):
    def test_seam_is_eliminated(self):
        # x1/2 correction at both anchors is inside the cap, so the fill
        # lands exactly on the live level at both edges of the gap.
        june = _june(_run(1.0, DisagConfig(seam_blend=True))[0])
        self.assertAlmostEqual(june.v[GAP[0]] / june.v[LAST_LIVE], 1.0)
        self.assertAlmostEqual(june.v[GAP[-1]] / june.v[FIRST_LIVE], 1.0)

    def test_no_patched_day_stays_double_the_live_edge(self):
        june = _june(_run(1.0, DisagConfig(seam_blend=True))[0])
        for d in GAP:
            self.assertLess(june.v[d] / june.v[LAST_LIVE], 1.2)

    def test_report_notes_the_blend(self):
        _, log = _run(1.0, DisagConfig(seam_blend=True))
        self.assertTrue(any('seam-blended 1 gap(s)' in l for l in log), log)


class FourXSeamBlendTests(unittest.TestCase):
    def test_correction_is_capped_at_one_third(self):
        # The 4x seam implies a x1/4 correction — outside the cap, so the
        # fill settles at 4/3 of the live level instead of 1.0.
        june = _june(_run(0.5, DisagConfig(seam_blend=True))[0])
        expected = 4.0 / _SEAM_CORR_CAP
        for d in GAP:
            self.assertAlmostEqual(june.v[d] / june.v[LAST_LIVE], expected)

    def test_patched_days_end_far_below_4x(self):
        june = _june(_run(0.5, DisagConfig(seam_blend=True))[0])
        for d in GAP:
            self.assertLess(june.v[d] / june.v[LAST_LIVE], 1.5)

    def test_live_edge_days_are_never_rewritten(self):
        # Current contract: even on a radical (4x) seam, blending adjusts
        # only the patched days. The live days at the seam edges keep the
        # month's observed shape — they are not smoothed toward the fill.
        june = _june(_run(0.5, DisagConfig(seam_blend=True))[0])
        self.assertAlmostEqual(june.v[LAST_LIVE], june.v[0])
        self.assertAlmostEqual(june.v[FIRST_LIVE], june.v[29])


class MixedSeamTests(unittest.TestCase):
    """4x seam on the left edge, 2x on the right: the capped left
    correction (x1/3) and uncapped right correction (x1/2) interpolate in
    log space across the run."""

    def _blended_june(self):
        recs, _ = _run(0.5, DisagConfig(seam_blend=True),
                       obs_level_after=1.0)
        return _june(recs)

    def test_fixture_has_both_ratios(self):
        june = _june(_run(0.5, obs_level_after=1.0)[0])
        self.assertAlmostEqual(june.v[GAP[0]] / june.v[LAST_LIVE], 4.0)
        self.assertAlmostEqual(june.v[GAP[-1]] / june.v[FIRST_LIVE], 2.0)

    def test_fill_ramps_monotonically_between_the_anchors(self):
        june = self._blended_june()
        self.assertLess(june.v[GAP[0]], june.v[GAP[1]])
        self.assertLess(june.v[GAP[1]], june.v[GAP[2]])

    def test_both_edge_steps_shrink(self):
        june = self._blended_june()
        self.assertLess(june.v[GAP[0]] / june.v[LAST_LIVE], 4.0)
        self.assertLess(june.v[GAP[-1]] / june.v[FIRST_LIVE], 2.0)


class MassBalanceAndConfigTests(unittest.TestCase):
    def test_mass_balance_holds_for_every_config(self):
        for obs_level in (1.0, 0.5):
            for cfg in (None,
                        DisagConfig(seam_blend=True),
                        DisagConfig(daily_fdc_mapping=True,
                                    seam_blend=True)):
                recs, _ = _run(obs_level, cfg)
                self.assertAlmostEqual(
                    _month_sum_mm3(_june(recs)), 30.0, places=6)

    def test_fdc_mapping_degrades_to_linear_on_flat_file2(self):
        # File 2 has no spread, so its FDC pools are unusable and the
        # recommended fdc+seam combo must reproduce the seam-only ratios.
        seam = _june(_run(0.5, DisagConfig(seam_blend=True))[0])
        both = _june(_run(0.5, DisagConfig(daily_fdc_mapping=True,
                                           seam_blend=True))[0])
        for d in GAP:
            self.assertAlmostEqual(seam.v[d] / seam.v[LAST_LIVE],
                                   both.v[d] / both.v[LAST_LIVE])


if __name__ == '__main__':
    unittest.main()
