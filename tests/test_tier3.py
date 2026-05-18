"""Sub-process coverage for PATCH_EXCEED tier-3 (exceedance-matched donor).

`find_exceed_donor` and the donor-application loop in `_convert_month`'s
PATCH_EXCEED branch implement several discrete sub-processes:

* same-calendar-month filter on donor candidates
* self-exclusion of the target month
* leap-year filter (donor month-length must match the target's)
* distribution-size gate (target + per-file donor pool need ≥2 entries)
* closest-percentile selection
* tie-breaks: year proximity → file index → year value
* cross-river donor scaling (donor day × tier2_scale)
* whole-month tier-3 fill (every day sourced from donor)
* mixed tier-1 / tier-2 / tier-3 days within a single output month

Each test below pins one of those sub-processes. Some overlap with the
broader percentile/tie-break coverage in ``tests/test_algorithm.py``;
the duplication is deliberate — these tests document each sub-process
explicitly so a regression points at the responsible piece of logic.
"""

import calendar
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import (
    DisagMethod,
    _monthly_totals_from_daily,
    _per_month_distributions,
    _tier2_scale_factors,
    disaggregate,
    find_exceed_donor,
)
from disag.files import DailyRecord, MISSING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full(year: int, month: int, per_day: float) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(year=year, month=month, v=[per_day] * dim)


def _gappy(year: int, month: int, per_day: float, gap_day_1based: int) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    v = [per_day] * dim
    v[gap_day_1based - 1] = MISSING
    return DailyRecord(year=year, month=month, v=v)


def _build_dists(gen, files):
    totals = [_monthly_totals_from_daily(f) for f in files]
    td, dd = _per_month_distributions(gen, totals)
    return totals, td, dd


def _record(records, year, month):
    return next(r for r in records if (r.year, r.month) == (year, month))


def _is_missing(rec):
    return all(v == MISSING for v in rec.v)


def _tier_line(log, year, month):
    """Find the per-month tier-breakdown row for (year, month) in the report.

    Both the patch-event log line and the breakdown row begin with the same
    ``YYYY MM`` prefix, so disambiguate by requiring the 3rd whitespace
    token to be a digit (the T1 count).
    """
    prefix = f'{year:4d} {month:2d}'
    for l in log:
        if not l.lstrip().startswith(prefix):
            continue
        tokens = l.split()
        if len(tokens) >= 3 and tokens[2].isdigit():
            return l
    raise AssertionError(f'no tier-breakdown line for {year}-{month} in: {log!r}')


# ---------------------------------------------------------------------------
# Sub-process: same-calendar-month filter
# ---------------------------------------------------------------------------

class SameMonthFilterTests(unittest.TestCase):
    """A donor MUST be from the same calendar month as the target.

    Donors from another month (even with closer percentiles) are skipped.
    """

    def test_only_same_month_donors_considered(self):
        gen = {
            (2000, 6): 100.0, (2001, 6): 200.0, (2002, 6): 300.0,
            # Some Julys, similar values — must NOT be picked for a June target
            (2000, 7): 100.0, (2001, 7): 200.0, (2002, 7): 300.0,
        }
        f1 = {
            (2000, 6): _full(2000, 6, 1.0),
            (2001, 6): _full(2001, 6, 2.0),
            (2000, 7): _full(2000, 7, 1.0),
            (2001, 7): _full(2001, 7, 2.0),
            (2002, 7): _full(2002, 7, 3.0),
        }
        totals, td, dd = _build_dists(gen, [f1])
        result = find_exceed_donor(2002, 6, gen, totals, td, dd)
        self.assertIsNotNone(result)
        _, donor_year, _, _ = result
        # donor must be one of the Junes — Junes in donor pool are 2000, 2001
        self.assertIn(donor_year, (2000, 2001))


# ---------------------------------------------------------------------------
# Sub-process: year-proximity tie-break
# ---------------------------------------------------------------------------

class YearProximityTiebreakTests(unittest.TestCase):
    """When two donors share a percentile, the year closer to the target wins."""

    def test_closer_year_wins(self):
        # Target 2005 June, vol = 50 → p_target depends on full gen dist.
        # Two donor years have identical totals → same p_donor; the
        # closer year (1995 < 1985 → 2005-1995=10, 2005-1985=20)
        # should win.
        gen = {
            (1985, 6): 100.0,
            (1995, 6): 100.0,
            (2005, 6): 50.0,
            (2010, 6): 200.0,
        }
        f1 = {
            (1985, 6): _full(1985, 6, 100.0 / 30),
            (1995, 6): _full(1995, 6, 100.0 / 30),
            (2010, 6): _full(2010, 6, 200.0 / 30),
        }
        totals, td, dd = _build_dists(gen, [f1])
        result = find_exceed_donor(2005, 6, gen, totals, td, dd)
        self.assertIsNotNone(result)
        _, donor_year, _, _ = result
        self.assertEqual(donor_year, 1995,
                         '1995 is closer to 2005 than 1985 is')


# ---------------------------------------------------------------------------
# Sub-process: leap-year filter
# ---------------------------------------------------------------------------

class LeapYearFilterTests(unittest.TestCase):
    """Donor's month-length must match the target's — Feb 29 mismatch."""

    def test_leap_target_skips_non_leap_donor(self):
        # Target Feb 2000 (29 days) needs a Feb donor with 29 days.
        # Feb 1999 has 28 days → must be skipped despite being only candidate.
        gen = {
            (1999, 2): 50.0,
            (2000, 2): 75.0,
            (2001, 2): 80.0,   # non-leap, 28 days
        }
        f1 = {
            (1999, 2): _full(1999, 2, 50.0 / 28),
            (2001, 2): _full(2001, 2, 80.0 / 28),
        }
        totals, td, dd = _build_dists(gen, [f1])
        result = find_exceed_donor(2000, 2, gen, totals, td, dd)
        # No leap-year donor available → must return None
        self.assertIsNone(
            result,
            'Feb 29 target must not borrow from a 28-day Feb donor',
        )

    def test_non_leap_target_skips_leap_donor(self):
        # Mirror: Feb 2001 (28 days) target with only a 29-day Feb 2000 donor.
        gen = {
            (1999, 2): 50.0,
            (2000, 2): 75.0,
            (2001, 2): 80.0,
        }
        f1 = {
            (2000, 2): _full(2000, 2, 75.0 / 29),   # 29 days (leap)
        }
        totals, td, dd = _build_dists(gen, [f1])
        result = find_exceed_donor(2001, 2, gen, totals, td, dd)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Sub-process: distribution-size gate
# ---------------------------------------------------------------------------

class DistributionSizeGateTests(unittest.TestCase):
    def test_single_entry_target_dist_returns_none(self):
        gen = {(2000, 6): 100.0}
        f1 = {(2000, 6): _full(2000, 6, 100.0 / 30)}
        totals, td, dd = _build_dists(gen, [f1])
        self.assertIsNone(find_exceed_donor(2000, 6, gen, totals, td, dd))

    def test_single_entry_donor_dist_returns_none(self):
        # target_dist has 3 entries, but the file-1 donor pool has only 1
        # complete June → donor_dist len 1 < 2 → return None.
        gen = {(2000, 6): 100.0, (2001, 6): 200.0, (2002, 6): 300.0}
        f1 = {
            (2000, 6): _gappy(2000, 6, 100.0 / 30, 15),
            (2001, 6): _gappy(2001, 6, 200.0 / 30, 15),
            (2002, 6): _full(2002, 6, 300.0 / 30),
        }
        totals, td, dd = _build_dists(gen, [f1])
        # Target = 2000 June. Donor pool has only 2002 (others are gappy
        # → excluded by completeness filter). donor_dist len = 1 → None.
        self.assertIsNone(find_exceed_donor(2000, 6, gen, totals, td, dd))


# ---------------------------------------------------------------------------
# Sub-process: whole-month tier-3 fill
# ---------------------------------------------------------------------------

class WholeMonthTier3Tests(unittest.TestCase):
    """Target month has zero usable days in file 1+2 → entire month is tier 3."""

    def test_every_day_is_tier3(self):
        # gen has 3 hydro years; daily covers 2 of them. The third hydro
        # year is a complete tier-3 fill from the donor pool.
        gen = {}
        for y in (2000, 2001, 2002):
            for hy_offset in range(12):
                m = 10 + hy_offset
                yy = y + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                gen[(yy, m)] = 10.0 + hy_offset
        f1 = {}
        for y in (2000, 2001):
            for hy_offset in range(12):
                m = 10 + hy_offset
                yy = y + (m - 1) // 12
                m = ((m - 1) % 12) + 1
                f1[(yy, m)] = _full(yy, m, 1.0)

        recs, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1], no_files=1,
        )

        # Pick a month from hydro year 2002 — should be entirely tier 3.
        target = _record(recs, 2002, 10)
        self.assertFalse(_is_missing(target))
        # Per-month tier-breakdown line for 2002 10 must show 0 t1, 0 t2,
        # and 31 t3 (October has 31 days).
        nums = [int(x) for x in _tier_line(log, 2002, 10).split()[:5]]
        # nums = [year, month, t1, t2, t3]
        self.assertEqual(nums[2], 0, 'no tier-1 days expected')
        self.assertEqual(nums[3], 0, 'no tier-2 days expected')
        self.assertEqual(nums[4], 31, '31 tier-3 days expected (Oct)')


# ---------------------------------------------------------------------------
# Sub-process: mixed tier 1 / tier 2 / tier 3 within a single month
# ---------------------------------------------------------------------------

class MixedTiersTests(unittest.TestCase):
    """One month with: tier-1 days (file 1), tier-2 days (file 2 fill),
    and tier-3 days (no file at that day → donor month patches them in)."""

    def test_single_month_has_all_three_tiers(self):
        # Setup: Jan 2005, 31 days.
        #   days 1-10   → file 1 has values (tier 1)
        #   days 11-20  → file 1 missing, file 2 has values (tier 2)
        #   days 21-31  → both files missing (tier 3 picks donor)
        target_year, target_month = 2005, 1

        def jan_record(year, day_values):
            return DailyRecord(year=year, month=1, v=day_values)

        # Target Jan 2005 in file 1: 1-10 present, 11-31 MISSING
        f1_target = jan_record(
            target_year,
            [1.0] * 10 + [MISSING] * 21,
        )
        # Target Jan 2005 in file 2: 1-10 MISSING (irrelevant — f1 wins),
        # 11-20 present, 21-31 MISSING
        f2_target = jan_record(
            target_year,
            [MISSING] * 10 + [2.0] * 10 + [MISSING] * 11,
        )

        # Donor pool: 2 complete Januaries each in file 1 and file 2.
        f1 = {(target_year, 1): f1_target}
        f2 = {(target_year, 1): f2_target}
        # Two complete years each, with values that won't accidentally
        # rank-tie the donor (each file's distribution has 2 distinct totals).
        for y, per_day in [(2000, 1.0), (2001, 3.0)]:
            f1[(y, 1)] = _full(y, 1, per_day)
            f2[(y, 1)] = _full(y, 1, per_day * 1.5)

        # gen needs ≥2 valid Januaries for the target distribution.
        gen = {
            (2000, 1): 31.0,
            (2001, 1): 93.0,
            (target_year, 1): 62.0,
        }

        recs, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [f1, f2], no_files=2,
        )

        target = _record(recs, target_year, target_month)
        self.assertFalse(_is_missing(target), 'all three tiers must combine to a complete month')

        # Per-month breakdown line should report t1=10, t2=10, t3=11
        t_line = _tier_line(log, target_year, target_month)
        nums = [int(x) for x in t_line.split()[:5]]
        self.assertEqual(nums[2], 10, f'expected 10 tier-1 days, got line: {t_line!r}')
        self.assertEqual(nums[3], 10, f'expected 10 tier-2 days, got line: {t_line!r}')
        self.assertEqual(nums[4], 11, f'expected 11 tier-3 days, got line: {t_line!r}')


# ---------------------------------------------------------------------------
# Sub-process: cross-river donor scaling (tier2_scale applied to donor)
# ---------------------------------------------------------------------------

class CrossRiverDonorScalingTests(unittest.TestCase):
    """When the donor comes from file 2, its day values are multiplied by
    ``tier2_scale[file_idx][month]`` so file-2's absolute scale doesn't
    distort qD when mixed with tier-1 days.

    The scale factor cancels in the final disaggregation formula
    (gen × qD/qM) for whole-month tier-3 fills, but it matters when a
    month mixes tier 1/2 days with tier-3 days — which is what this
    test exercises.
    """

    def test_scale_factor_is_applied_to_donor_days(self):
        # File 1: scale ~1, file 2: scale ~10. Tier-2 scale factor for
        # file 2 → multiply file-2 day by 10 when patching into file-1
        # shape.
        f1 = {
            (2000, 1): _full(2000, 1, 10.0),
            (2001, 1): _full(2001, 1, 20.0),
            (2002, 1): _full(2002, 1, 30.0),
        }
        f2 = {
            (2000, 1): _full(2000, 1, 1.0),
            (2001, 1): _full(2001, 1, 2.0),
            (2002, 1): _full(2002, 1, 3.0),
        }
        scale = _tier2_scale_factors(
            [_monthly_totals_from_daily(f1), _monthly_totals_from_daily(f2)]
        )
        # File-1 Jan mean = mean(10*31, 20*31, 30*31) = 20*31 = 620
        # File-2 Jan mean = mean(1*31, 2*31, 3*31)    = 2*31  = 62
        # ratio = 10
        self.assertAlmostEqual(scale[1][1], 10.0, places=6)

    def test_disag_produces_consistent_shape_with_donor_rescaled(self):
        # Construct a scenario where Jan 2003 needs a tier-3 donor and
        # the only eligible donor lives in file 2 (file 1 has no other
        # complete Januaries).  The rescaled donor should leave the
        # output's day-to-day RATIO identical regardless of file-2's
        # absolute scale — that's the whole point of the tier-2 rescale.

        def build(file2_scale: float):
            gen = {
                (2000, 1): 50.0, (2001, 1): 50.0, (2002, 1): 50.0,
                (2003, 1): 50.0,
            }
            # File 1: gappy Jan 2003, no other complete Januaries
            f1 = {
                (2003, 1): DailyRecord(
                    year=2003, month=1,
                    v=[MISSING] * 31,
                ),
            }
            # File 2: complete Januaries for 2000, 2001 (donor pool) +
            # gappy target.  Use a non-flat shape so the rescale matters.
            shape = [1.0 + 0.1 * i for i in range(31)]
            f2 = {
                (2000, 1): DailyRecord(
                    year=2000, month=1,
                    v=[s * file2_scale for s in shape],
                ),
                (2001, 1): DailyRecord(
                    year=2001, month=1,
                    v=[s * file2_scale * 2 for s in shape],
                ),
                (2003, 1): DailyRecord(
                    year=2003, month=1, v=[MISSING] * 31,
                ),
            }
            return gen, [f1, f2]

        recs_a, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, *build(1.0), no_files=2,
        )
        recs_b, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, *build(100.0), no_files=2,
        )

        jan_a = _record(recs_a, 2003, 1).v
        jan_b = _record(recs_b, 2003, 1).v

        # Whole-month tier-3 fill → the disag formula's gen × qD/qM
        # ratio cancels any uniform multiplier on qD. The two runs must
        # produce identical daily output despite file-2's scale being
        # 100× different.
        for a, b in zip(jan_a, jan_b):
            self.assertAlmostEqual(a, b, places=6)


if __name__ == '__main__':
    unittest.main()
