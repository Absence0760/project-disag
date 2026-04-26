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


if __name__ == '__main__':
    unittest.main()
