"""Unit coverage for disag/algorithm.py's small helpers.

The end-to-end suites in test_demo_methods.py, test_e2e.py, and
test_missing_data.py exercise these helpers transitively but never
pin their isolated behaviour. A regression in `_inc_month` would
silently corrupt every run before any end-to-end assertion noticed.
`_hydro_start_ym` is a standalone hydro-year helper (no longer on the
disaggregation path since file-2 activation switched to the record's
actual first month); it is pinned here so its behaviour can't drift.

Each test below names a discrete invariant of one helper so a
regression points at the responsible function.
"""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import (
    _hydro_start_ym,
    _inc_month,
    count_coverage,
    find_patch_year,
)
from disag.files import DailyRecord, MISSING


class IncMonthTests(unittest.TestCase):
    """Walk every month-boundary case so a future refactor can't drift."""

    def test_increments_within_year(self):
        self.assertEqual(_inc_month(2024, 1), (2024, 2))
        self.assertEqual(_inc_month(2024, 6), (2024, 7))
        self.assertEqual(_inc_month(2024, 11), (2024, 12))

    def test_rolls_over_december_to_january_next_year(self):
        self.assertEqual(_inc_month(2024, 12), (2025, 1))
        self.assertEqual(_inc_month(1999, 12), (2000, 1))

    def test_handles_leap_year_february(self):
        # _inc_month doesn't validate day counts — just month ordering.
        # Feb 29 happens via calendar.monthrange elsewhere; the helper
        # only advances the (year, month) tuple.
        self.assertEqual(_inc_month(2024, 2), (2024, 3))


class HydroStartYmTests(unittest.TestCase):
    """Hydro year starts in October.  A file beginning Oct..Dec belongs
    to the current hydro year; one beginning Jan..Sep belongs to the
    PREVIOUS hydro year — so its first complete hydro year starts on
    the following October."""

    def _rec(self, year, month):
        return DailyRecord(year=year, month=month, v=[1.0] * 28)

    def test_record_starting_october_uses_same_year(self):
        recs = {(2020, 10): self._rec(2020, 10), (2020, 11): self._rec(2020, 11)}
        self.assertEqual(_hydro_start_ym(recs), (2020, 10))

    def test_record_starting_november_rolls_to_next_october(self):
        recs = {(2020, 11): self._rec(2020, 11)}
        self.assertEqual(_hydro_start_ym(recs), (2021, 10))

    def test_record_starting_january_keeps_same_calendar_year(self):
        # Jan 2020 is part of hydro year 2019 (Oct 2019..Sep 2020).
        # The first COMPLETE hydro year starting at or after Jan 2020
        # is Oct 2020.
        recs = {(2020, 1): self._rec(2020, 1)}
        self.assertEqual(_hydro_start_ym(recs), (2020, 10))

    def test_record_starting_september_rolls_to_october_same_year(self):
        # Sep 2020 is the LAST month of hydro year 2019. First complete
        # hydro year after it starts Oct 2020.
        recs = {(2020, 9): self._rec(2020, 9)}
        self.assertEqual(_hydro_start_ym(recs), (2020, 10))

    def test_empty_records_returns_sentinel(self):
        # The sentinel (9999, 10) is what disaggregate uses to say
        # "this daily file has no data; never let it gate a window."
        self.assertEqual(_hydro_start_ym({}), (9999, 10))


class CountCoverageTests(unittest.TestCase):
    """All-or-nothing month classification — the basis of every
    coverage report and warning."""

    def test_complete_month_counted_disaggregated(self):
        rec = DailyRecord(year=2020, month=6, v=[5.0] * 30)
        d, m = count_coverage([rec])
        self.assertEqual((d, m), (1, 0))

    def test_one_missing_day_marks_whole_month_missing(self):
        v = [5.0] * 29 + [MISSING]
        rec = DailyRecord(year=2020, month=6, v=v)
        d, m = count_coverage([rec])
        self.assertEqual((d, m), (0, 1))

    def test_all_missing_marks_missing(self):
        rec = DailyRecord(year=2020, month=6, v=[MISSING] * 30)
        d, m = count_coverage([rec])
        self.assertEqual((d, m), (0, 1))

    def test_zero_values_count_as_complete(self):
        # Zero is a valid flow (dry month), not a missing-data sentinel.
        rec = DailyRecord(year=2020, month=6, v=[0.0] * 30)
        d, m = count_coverage([rec])
        self.assertEqual((d, m), (1, 0))

    def test_mixed_records_summed_correctly(self):
        good = DailyRecord(year=2020, month=6, v=[1.0] * 30)
        bad = DailyRecord(year=2020, month=7, v=[1.0] * 30 + [MISSING])
        d, m = count_coverage([good, bad])
        self.assertEqual((d, m), (1, 1))

    def test_empty_list_returns_zero_zero(self):
        self.assertEqual(count_coverage([]), (0, 0))


class FindPatchYearTests(unittest.TestCase):
    """PATCH_CAL's donor-finding logic.  Picks the same-calendar-month
    year whose `gen_monthly` volume is CLOSEST to the target's AND
    whose `obs_daily` record is complete."""

    def _full_month(self, year, month, per_day=1.0):
        return DailyRecord(year=year, month=month, v=[per_day] * 30)

    def test_closest_volume_with_complete_record_wins(self):
        gen = {(2000, 6): 50.0, (2001, 6): 60.0, (2002, 6): 200.0, (2003, 6): 55.0}
        obs = {
            (2000, 6): self._full_month(2000, 6),
            (2001, 6): self._full_month(2001, 6),
            (2002, 6): self._full_month(2002, 6),
            (2003, 6): self._full_month(2003, 6),
        }
        # Target 2002 June, volume 200. Closest other June is 60 (2001).
        # Wait, 60 is the closest of {50, 60, 55}? |200-60|=140, |200-50|=150,
        # |200-55|=145 → 60 wins.
        self.assertEqual(find_patch_year(2002, 6, gen, obs), 2001)

    def test_target_year_excluded_from_candidates(self):
        gen = {(2000, 6): 50.0, (2001, 6): 50.0}
        obs = {
            (2000, 6): self._full_month(2000, 6),
            (2001, 6): self._full_month(2001, 6),
        }
        # Target's own year must never be picked even though its
        # volume is trivially closest (zero diff).
        self.assertEqual(find_patch_year(2000, 6, gen, obs), 2001)

    def test_gappy_candidate_skipped(self):
        gen = {(2000, 6): 50.0, (2001, 6): 50.5, (2002, 6): 200.0}
        obs = {
            (2000, 6): self._full_month(2000, 6),
            (2001, 6): DailyRecord(
                year=2001, month=6,
                v=[1.0] * 14 + [MISSING] + [1.0] * 15,
            ),
            (2002, 6): self._full_month(2002, 6),
        }
        # 2001 is the closest by volume to 2000 (target), but it has a
        # gap on day 15 → skipped. 2002 wins despite a much larger diff.
        self.assertEqual(find_patch_year(2000, 6, gen, obs), 2002)

    def test_missing_target_volume_returns_none(self):
        gen = {(2000, 6): 50.0, (2001, 6): 50.5}
        obs = {(2001, 6): self._full_month(2001, 6)}
        # Target's gen value is missing — patching makes no sense.
        self.assertIsNone(find_patch_year(2002, 6, gen, obs))

    def test_negative_target_volume_returns_none(self):
        gen = {(2000, 6): -99.99, (2001, 6): 50.0}
        obs = {(2001, 6): self._full_month(2001, 6)}
        # Negative is the missing-data sentinel; same as not present.
        self.assertIsNone(find_patch_year(2000, 6, gen, obs))

    def test_no_other_year_returns_none(self):
        gen = {(2000, 6): 50.0}
        obs = {(2000, 6): self._full_month(2000, 6)}
        # Only the target year exists. Self-excluded → no candidate.
        self.assertIsNone(find_patch_year(2000, 6, gen, obs))

    def test_negative_candidate_volume_skipped(self):
        gen = {(2000, 6): 50.0, (2001, 6): -99.99, (2002, 6): 200.0}
        obs = {
            (2001, 6): self._full_month(2001, 6),
            (2002, 6): self._full_month(2002, 6),
        }
        # 2001's gen is missing → not a valid candidate even though the
        # daily record is complete.
        self.assertEqual(find_patch_year(2000, 6, gen, obs), 2002)

    def test_only_same_calendar_month_considered(self):
        gen = {
            (2000, 6): 50.0,
            (2001, 6): 200.0,
            (2001, 7): 50.0,  # very close to target, but wrong month
        }
        obs = {
            (2001, 6): self._full_month(2001, 6),
            (2001, 7): self._full_month(2001, 7),
        }
        # July 2001 has the closest volume but it's the wrong calendar
        # month → must be ignored. 2001 June (only viable candidate) wins.
        self.assertEqual(find_patch_year(2000, 6, gen, obs), 2001)


if __name__ == '__main__':
    unittest.main()
