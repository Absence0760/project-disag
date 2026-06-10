"""End-to-end tests for the per-method demos in examples/methodN_demo/.

Each method's demo is asserted to behave exactly as its README claims.
The demos use deterministic, committed mock data, so these tests are a
regression net for the algorithm + the per-method walkthroughs in one go.

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


def _data(demo_name: str, *parts: str) -> str:
    return os.path.join(ROOT, 'examples', demo_name, 'data', *parts)


def _run(method, monthly_path, daily_paths, no_files=None):
    gen = read_monthly_file(monthly_path)
    obs = [{}, {}]
    for i, p in enumerate(daily_paths):
        obs[i] = read_daily_file(p)
    if no_files is None:
        no_files = max(1, len(daily_paths))
    return disaggregate(method, gen, obs, no_files)


class Method0DemoTests(unittest.TestCase):
    """Method 0 — ONE_FILE: whole-month-missing-when-any-day-missing."""

    def test_complete_file_disaggregates_every_month(self):
        recs, log = _run(
            DisagMethod.ONE_FILE,
            _data('method0_demo', 'target.MON'),
            [_data('method0_demo', 'gauge_complete.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 36)
        # The decision log records every month; a clean run shows each one
        # disaggregated straight from file 1 — no MISSING, no patching.
        month_rows = [l for l in log if l[:4].strip().isdigit()]
        self.assertEqual(len(month_rows), 36)
        self.assertTrue(all('disaggregated from file 1' in l for l in month_rows))
        self.assertFalse(any('MISSING' in l or 'patched' in l for l in log))

    def test_one_whole_month_gap_marks_only_that_month_missing(self):
        recs, _ = _run(
            DisagMethod.ONE_FILE,
            _data('method0_demo', 'target.MON'),
            [_data('method0_demo', 'gauge_with_gap.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 1)
        self.assertEqual(disagg, 35)
        # Confirm the missing month is exactly cal Jun 2002
        missing_keys = [(r.year, r.month) for r in recs if all(v < 0 for v in r.v)]
        self.assertEqual(missing_keys, [(2002, 6)])


class Method1DemoTests(unittest.TestCase):
    """Method 1 — PATCH_CAL: closest-volume same-month patching."""

    def test_closest_volume_donor_is_picked(self):
        recs, log = _run(
            DisagMethod.PATCH_CAL,
            _data('method1_demo', 'target.MON'),
            [_data('method1_demo', 'gauge_with_gap.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 48)
        # Exactly one patch line, naming year 2003 as the donor
        patches = [l for l in log if 'patched from' in l]
        self.assertEqual(len(patches), 1)
        self.assertIn('2002  6', patches[0])
        self.assertIn('similar calendar month 2003  6', patches[0])

    def test_no_donor_marks_month_missing(self):
        """When every same-calendar-month record is also gappy, PATCH_CAL
        has no donor and must mark the target month missing."""
        import calendar as _cal

        from disag.algorithm import disaggregate
        from disag.files import DailyRecord, MISSING

        # 3 hydro years, target = (cal Jun 2002, year 1.5).  Pin every
        # June in the daily file to gappy → no donor available.
        gen = {}
        for hy in range(2000, 2003):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                gen[(cy, hm)] = 1.0
        obs = {}
        for hy in range(2000, 2003):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                if hm == 6:                     # gap every June
                    values = [MISSING] * dim
                else:
                    values = [1.0] * dim
                obs[(cy, hm)] = DailyRecord(year=cy, month=hm, v=values)

        recs, _ = disaggregate(DisagMethod.PATCH_CAL, gen, [obs, {}], 1)
        june_recs = [r for r in recs if r.month == 6]
        # Every June should be all-MISSING because no donor exists
        for r in june_recs:
            self.assertTrue(all(v < 0 for v in r.v),
                            f'{r.year}-06 has at least one non-missing value '
                            f'but PATCH_CAL had no donor available')


class Method2DemoTests(unittest.TestCase):
    """Method 2 — PATCH_FILE: day-level fallback to file 2."""

    def test_orthogonal_gaps_fill_each_other(self):
        recs, log = _run(
            DisagMethod.PATCH_FILE,
            _data('method2_demo', 'target.MON'),
            [_data('method2_demo', 'gauge_a.DAY'),
             _data('method2_demo', 'gauge_b.DAY')],
        )
        disagg, missing = count_coverage(recs)
        # Each file alone would have 1 missing month; the two together
        # cover each other's gap → 0 missing.
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 36)
        # No per-month patch lines (tier-2 day-level patching is silent
        # in PATCH_FILE, by design).
        self.assertEqual(
            [l for l in log if 'Patched' in l],
            [],
        )

    def test_either_file_alone_drops_a_month(self):
        # Sanity: confirm each gauge individually has the documented gap
        recs_a, _ = _run(
            DisagMethod.ONE_FILE,
            _data('method2_demo', 'target.MON'),
            [_data('method2_demo', 'gauge_a.DAY')],
        )
        recs_b, _ = _run(
            DisagMethod.ONE_FILE,
            _data('method2_demo', 'target.MON'),
            [_data('method2_demo', 'gauge_b.DAY')],
        )
        a_missing = [(r.year, r.month) for r in recs_a if all(v < 0 for v in r.v)]
        b_missing = [(r.year, r.month) for r in recs_b if all(v < 0 for v in r.v)]
        self.assertEqual(a_missing, [(2002, 6)])
        self.assertEqual(b_missing, [(2003, 6)])

    def test_same_day_missing_in_both_files_marks_month_missing(self):
        """PATCH_FILE marks the whole month missing when the SAME day is
        absent from both daily files."""
        import calendar as _cal

        from disag.algorithm import disaggregate
        from disag.files import DailyRecord, MISSING

        gen = {}
        for hy in range(2000, 2002):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                gen[(cy, hm)] = 1.0
        f1, f2 = {}, {}
        for hy in range(2000, 2002):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                v1 = [1.0] * dim
                v2 = [1.0] * dim
                if (cy, hm) == (2001, 6):     # gap day 5 in BOTH files
                    v1[4] = MISSING
                    v2[4] = MISSING
                f1[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v1)
                f2[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v2)

        recs, _ = disaggregate(DisagMethod.PATCH_FILE, gen, [f1, f2], 2)
        target = next(r for r in recs if (r.year, r.month) == (2001, 6))
        self.assertTrue(all(v < 0 for v in target.v),
                        '2001-06 should be all-MISSING when both files '
                        'have a gap on the same day')


class Method3DemoTests(unittest.TestCase):
    """Method 3 — INCREMENTAL: pattern = file 1 − file 2."""

    def test_incremental_runs_to_completion(self):
        recs, log = _run(
            DisagMethod.INCREMENTAL,
            _data('method3_demo', 'target.MON'),
            [_data('method3_demo', 'gauge_downstream.DAY'),
             _data('method3_demo', 'gauge_upstream.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 36)

    def test_incremental_volume_preservation(self):
        # Output's monthly total must equal target.MON's incremental volume
        gen = read_monthly_file(_data('method3_demo', 'target.MON'))
        recs, _ = _run(
            DisagMethod.INCREMENTAL,
            _data('method3_demo', 'target.MON'),
            [_data('method3_demo', 'gauge_downstream.DAY'),
             _data('method3_demo', 'gauge_upstream.DAY')],
        )
        for rec in recs:
            target = gen.get((rec.year, rec.month))
            if target is None or target < 0:
                continue
            output_mm3 = sum(rec.v) * 86400 / 1e6
            self.assertAlmostEqual(
                output_mm3, target, places=3,
                msg=f'volume mismatch at {rec.year}-{rec.month:02d}',
            )

    def test_single_missing_day_marks_whole_month_missing(self):
        """INCREMENTAL needs both files complete; one missing day in
        either file kills the whole month."""
        import calendar as _cal

        from disag.algorithm import disaggregate
        from disag.files import DailyRecord, MISSING

        gen = {}
        for hy in range(2000, 2002):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                gen[(cy, hm)] = 1.0
        f1, f2 = {}, {}
        for hy in range(2000, 2002):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                v1 = [3.0] * dim
                v2 = [1.0] * dim
                if (cy, hm) == (2001, 6):   # gap one day in file 1 only
                    v1[10] = MISSING
                f1[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v1)
                f2[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v2)

        recs, _ = disaggregate(DisagMethod.INCREMENTAL, gen, [f1, f2], 2)
        target = next(r for r in recs if (r.year, r.month) == (2001, 6))
        self.assertTrue(all(v < 0 for v in target.v),
                        'INCREMENTAL must mark the whole month missing '
                        'when even one day is missing in either file')


class Method4DemoTests(unittest.TestCase):
    """Method 4 — EVEN: equal flow on every day of the month."""

    def test_runs_without_any_daily_file(self):
        recs, log = _run(
            DisagMethod.EVEN,
            _data('method4_demo', 'target.MON'),
            [],     # no daily files
            no_files=0,
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 36)

    def test_within_a_month_every_day_has_the_same_value(self):
        recs, _ = _run(
            DisagMethod.EVEN,
            _data('method4_demo', 'target.MON'),
            [],
            no_files=0,
        )
        for rec in recs:
            unique = set(round(v, 6) for v in rec.v)
            self.assertEqual(
                len(unique), 1,
                f'{rec.year}-{rec.month:02d} has {len(unique)} unique values; '
                'EVEN method should produce constant within-month flow',
            )

    def test_volume_preservation(self):
        gen = read_monthly_file(_data('method4_demo', 'target.MON'))
        recs, _ = _run(
            DisagMethod.EVEN,
            _data('method4_demo', 'target.MON'),
            [],
            no_files=0,
        )
        for rec in recs:
            target = gen.get((rec.year, rec.month))
            if target is None or target < 0:
                continue
            output_mm3 = sum(rec.v) * 86400 / 1e6
            self.assertAlmostEqual(
                output_mm3, target, places=3,
                msg=f'volume mismatch at {rec.year}-{rec.month:02d}',
            )


if __name__ == '__main__':
    unittest.main()
