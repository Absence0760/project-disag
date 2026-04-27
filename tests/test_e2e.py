"""End-to-end PATCH_EXCEED test against the committed method5_demo fixtures.

These run the full ``disaggregate`` pipeline and assert on which months
end up missing and which tier-3 patches the report records.  They are
the closest thing the project has to a regression net for the
algorithm — when ``examples/method5_demo/data/`` is regenerated
deterministically, these expectations should not change.

Stdlib only.
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import DisagMethod, count_coverage, disaggregate
from disag.files import read_daily_file, read_monthly_file


DATA = os.path.join(ROOT, 'examples', 'method5_demo', 'data')


def _run(method, daily_paths):
    """Read the demo monthly file plus 0–2 daily files and run disaggregate."""
    gen = read_monthly_file(os.path.join(DATA, 'target.MON'))
    obs = [{}, {}]
    for i, path in enumerate(daily_paths):
        obs[i] = read_daily_file(path)
    no_files = max(1, len(daily_paths))
    records, report_lines = disaggregate(method, gen, obs, no_files)
    return records, report_lines


def _tier3_patches(report_lines):
    """The Tier-3 log lines start at column 0 with ``YYYY MM ``."""
    return [
        l for l in report_lines
        if l[:4].strip().isdigit() and 'Patched with file' in l
    ]


class Method5ScenarioTests(unittest.TestCase):
    """Each scenario in examples/method5_demo/README.md becomes one test."""

    def test_scenario_1_tier1_only(self):
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_complete.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 72)
        self.assertEqual(_tier3_patches(log), [])

    def test_scenario_2_tier1_plus_tier2(self):
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY'),
             os.path.join(DATA, 'gauge_b_full.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 72)
        # File 2 covers all of file 1's gaps day-by-day → no tier 3 fires.
        self.assertEqual(_tier3_patches(log), [])

    def test_scenario_3_tier1_plus_tier2_plus_tier3(self):
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY'),
             os.path.join(DATA, 'gauge_b_partial.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 72)
        patches = _tier3_patches(log)
        # Only Jun 2005 falls through to tier 3 — gauge B covers Jun 2003.
        self.assertEqual(len(patches), 1)
        self.assertIn('2005  6', patches[0])
        self.assertIn('Patched with file 1 2002  6', patches[0])

    def test_scenario_4_tier1_plus_tier3(self):
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 72)
        patches = _tier3_patches(log)
        self.assertEqual(len(patches), 2)
        self.assertIn('2003  6', patches[0])
        self.assertIn('Patched with file 1 2004  6', patches[0])
        self.assertIn('2005  6', patches[1])
        self.assertIn('Patched with file 1 2002  6', patches[1])


class ReportObservabilityTests(unittest.TestCase):
    """Each warning / summary line is information-only — implementing them
    must not change the disaggregated output, only the report content."""

    def _build(self, gen, daily, days_in_month=30, year_range=range(2000, 2006)):
        """Tiny helper: build {(y, m): vol} and a daily file dict from
        per-(year, month) inputs."""
        return gen, daily

    def test_tier_counter_summary_in_report(self):
        _, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY')],
        )
        # Summary block exists
        self.assertTrue(
            any('Tier coverage summary' in l for l in log),
            'tier counter summary missing from report',
        )
        # Tier 3 fired for both gappy Junes — 30 days each
        tier3 = next(l for l in log if 'Tier 3' in l)
        self.assertIn('60 day(s)', tier3)
        self.assertIn('2 month(s)', tier3)
        # Tier 2 stays empty (no file 2 supplied)
        tier2 = next(l for l in log if 'Tier 2' in l)
        self.assertIn('0 day(s)', tier2)

    def test_tier2_counter_when_file2_supplied(self):
        _, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY'),
             os.path.join(DATA, 'gauge_b_full.DAY')],
        )
        tier2 = next(l for l in log if 'Tier 2' in l)
        # File 2 covers Jun 2003 + Jun 2005 → 30 + 30 = 60 days, 2 months
        self.assertIn('60 day(s)', tier2)
        self.assertIn('2 month(s)', tier2)
        tier3 = next(l for l in log if 'Tier 3' in l)
        self.assertIn('0 day(s)', tier3)

    def test_zero_target_warning(self):
        from disag.algorithm import disaggregate
        from disag.files import DailyRecord
        # Construct a 4-year hydro-month gen_monthly with one zero
        gen = {}
        for y in range(2000, 2004):
            for hm in [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
                cy = y if hm >= 10 else y + 1
                gen[(cy, hm)] = 1.0
        gen[(2002, 6)] = 0.0   # the zero
        # Daily file covers everything cleanly
        obs0 = {}
        for y in range(2000, 2004):
            for hm in [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
                cy = y if hm >= 10 else y + 1
                import calendar as _cal
                dim = _cal.monthrange(cy, hm)[1]
                obs0[(cy, hm)] = DailyRecord(year=cy, month=hm, v=[1.0] * dim)
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [obs0, {}], 1)
        self.assertTrue(
            any('zero' in l and 'Warning' in l for l in log),
            f'no zero-target warning in report: {log[:5]}',
        )

    def test_sparse_calendar_month_warning(self):
        # Build a gen_monthly with only ONE January (sparse for tier 3)
        from disag.algorithm import disaggregate
        gen = {(2000, 1): 1.0}
        for hm in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            gen[(2000, hm)] = 1.0
        for hm in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            gen[(2001, hm)] = 1.0
            gen[(2002, hm)] = 1.0
        # delete 2001 January, keep 2000 and 2002 — actually just keep one
        del gen[(2001, 1)]
        del gen[(2002, 1)]
        # gen has 1 January (sparse) and 3 of every other month — but #9 flat
        # warning will also fire because all values are 1.0.  This test only
        # asserts the sparse warning is present.
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [{}, {}], 1,
        )
        self.assertTrue(
            any('fewer than 2' in l and '[1]' in l for l in log),
            f'no sparse warning for January in report: {log[:5]}',
        )

    def test_flat_distribution_warning(self):
        # Every June has the same value across years → flat distribution
        from disag.algorithm import disaggregate
        gen = {}
        for y in range(2000, 2003):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = y if hm >= 10 else y + 1
                gen[(cy, hm)] = float(hm)        # varies by month, same per year
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [{}, {}], 1,
        )
        # Every calendar month has identical values across the 3 years —
        # the flat warning should list all 12 months.
        flat_lines = [l for l in log if 'identical values' in l]
        self.assertEqual(len(flat_lines), 1)
        self.assertIn('1', flat_lines[0])
        self.assertIn('12', flat_lines[0])

    def test_clipped_window_warning(self):
        # gen_monthly has years 1990-2010, daily file starts in 2000 →
        # months before 2000-10 get clipped from the run window.
        from disag.algorithm import disaggregate
        from disag.files import DailyRecord
        import calendar as _cal
        gen = {}
        for y in range(1990, 2011):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = y if hm >= 10 else y + 1
                gen[(cy, hm)] = 1.0
        obs = {}
        for y in range(2000, 2010):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = y if hm >= 10 else y + 1
                dim = _cal.monthrange(cy, hm)[1]
                obs[(cy, hm)] = DailyRecord(year=cy, month=hm, v=[1.0] * dim)
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1,
        )
        self.assertTrue(
            any('outside the run window' in l and 'before' in l for l in log),
            'no clipped-before warning',
        )


class MonHeaderTests(unittest.TestCase):
    """The mock generator's .MON header has to remain reader-compatible
    while still being human-readable."""

    def test_header_explains_hydro_vs_calendar(self):
        path = os.path.join(DATA, 'target.MON')
        with open(path) as f:
            head = [next(f) for _ in range(5)]
        # The note explaining the row-label convention must be in the
        # 5-line header so a hand-reader sees it before any data.
        joined = ''.join(head).lower()
        self.assertIn('hydro year', joined)
        self.assertIn('june', joined)

    def test_reader_still_parses_with_new_header(self):
        # Reader must skip exactly the 5-line header; if the layout drifts
        # we'd lose the first record (and the parse would silently miss).
        path = os.path.join(DATA, 'target.MON')
        m = read_monthly_file(path)
        # 6 hydro years × 12 months each = 72 (year, month) keys
        self.assertEqual(len(m), 72)
        # Cal Jun 2003 is on the 2002 hydro-year row, column 9
        self.assertAlmostEqual(m[(2003, 6)], 1.554, places=3)


class VolumePreservationTest(unittest.TestCase):
    """For any tier (1, 2, or 3), the output's monthly total must equal
    the input's gen_monthly volume.  This is the core invariant of the
    disag formula — verifying it across a whole run is a good catch-all.
    """

    def test_output_monthly_total_equals_target(self):
        gen = read_monthly_file(os.path.join(DATA, 'target.MON'))
        recs, _ = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_with_gaps.DAY'),
             os.path.join(DATA, 'gauge_b_partial.DAY')],
        )
        for rec in recs:
            target = gen.get((rec.year, rec.month))
            if target is None or target < 0:
                continue
            # Skip entirely-missing output months (target is None covered above)
            if all(v < 0 for v in rec.v):
                continue
            output_mm3 = sum(rec.v) * 86400 / 1e6
            self.assertAlmostEqual(
                output_mm3, target, places=3,
                msg=f'Volume mismatch at {rec.year}-{rec.month:02d}',
            )


class Method1VsMethod5DivergenceTests(unittest.TestCase):
    """Constructed dataset where Method 1 (closest absolute volume) and
    Method 5 (closest exceedance percentile) pick *different* donors.

    This is the headline reason method 5 exists for cross-river data:
    when the daily file's absolute scale doesn't track gen_monthly's,
    the rank-based match disagrees with the absolute-volume match.
    """

    def _build(self):
        """Build gen_monthly + a single daily file with rigged Junes.

        gen_monthly Junes:
          (2001, 6) = 1.0
          (2002, 6) = 1.6   ← method 1 picks this (closest |1.6 − 1.5|=0.1)
          (2003, 6) = 1.5   ← target (gappy in daily file)
          (2004, 6) = 5.0
          (2005, 6) = 10.0

        Target's percentile in the 5-value June dist:
          sorted asc: 1.0 1.5 1.6 5.0 10.0; count_ge(1.5)=4 → 80 %.

        Daily file Jun TOTALS (target's own June is gappy, so excluded
        from the donor pool of 4):
          (2001, 6) =   100  → 4-value rank %: 50 %
          (2002, 6) =     5  →                100 %
          (2004, 6) =   200  →                 25 %
          (2005, 6) =    50  →                 75 %    ← method 5 picks this

        |80 − 75|=5 vs the next-closest |80 − 50|=30 → method 5 = 2005.
        Method 1 picks 2002 (smallest |Δvol| in gen_monthly).  Different.
        """
        import calendar as _cal

        from disag.files import DailyRecord, MISSING

        gen = {}
        # All other months get a benign 1.0 in gen_monthly.  Only Junes
        # are pinned to specific divergence-engineering values.
        for hy in range(2000, 2005):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                gen[(cy, hm)] = 1.0
        gen[(2001, 6)] = 1.0
        gen[(2002, 6)] = 1.6
        gen[(2003, 6)] = 1.5
        gen[(2004, 6)] = 5.0
        gen[(2005, 6)] = 10.0

        # Daily file: every month complete except (2003, 6) which is the
        # target.  Target year's June is all-missing, forcing both methods
        # to look elsewhere for a donor.
        june_totals = {2001: 100.0, 2002: 5.0, 2004: 200.0, 2005: 50.0}
        obs = {}
        for hy in range(2000, 2005):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                if hm == 6 and cy == 2003:
                    values = [MISSING] * dim
                elif hm == 6 and cy in june_totals:
                    # Spread the rigged total evenly across the 30 days
                    values = [june_totals[cy] / 30.0] * dim
                else:
                    values = [1.0] * dim
                obs[(cy, hm)] = DailyRecord(year=cy, month=hm, v=values)
        return gen, obs

    def test_method1_picks_closest_volume(self):
        from disag.algorithm import disaggregate
        gen, obs = self._build()
        _, log = disaggregate(DisagMethod.PATCH_CAL, gen, [obs, {}], 1)
        patch = next(l for l in log if 'Patched with' in l)
        self.assertIn('2003  6', patch)               # target month
        self.assertIn('Patched with 2002  6', patch)  # method 1's pick

    def test_method5_picks_closest_percentile(self):
        from disag.algorithm import disaggregate
        gen, obs = self._build()
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1)
        patch = next(l for l in log if 'Patched with file' in l)
        self.assertIn('2003  6', patch)
        self.assertIn('Patched with file 1 2005  6', patch)

    def test_methods_diverge_on_this_dataset(self):
        """Sanity: confirm the two methods explicitly chose different
        donor years on the same input."""
        from disag.algorithm import disaggregate
        gen, obs = self._build()
        _, log1 = disaggregate(DisagMethod.PATCH_CAL,    gen, [obs, {}], 1)
        _, log5 = disaggregate(DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1)
        donor1 = next(l for l in log1 if 'Patched with' in l)
        donor5 = next(l for l in log5 if 'Patched with file' in l)
        # Pick the donor-year token from each line and assert they differ
        self.assertIn('2002', donor1)
        self.assertIn('2005', donor5)
        self.assertNotIn('2002', donor5)


if __name__ == '__main__':
    unittest.main()
