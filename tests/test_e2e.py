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
