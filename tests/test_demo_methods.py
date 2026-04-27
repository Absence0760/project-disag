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
        # Method 0 doesn't log per-month
        self.assertEqual(log, [])

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
        patches = [l for l in log if 'Patched with' in l]
        self.assertEqual(len(patches), 1)
        self.assertIn('2002  6', patches[0])
        self.assertIn('Patched with 2003  6', patches[0])


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


if __name__ == '__main__':
    unittest.main()
