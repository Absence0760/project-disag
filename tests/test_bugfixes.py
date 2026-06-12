"""Regression tests for four logic bugs found in disag/algorithm.py.

Each test reproduces the broken behaviour with hand-built inputs (no
fixtures), so a future refactor that reintroduces the bug fails loudly
and points at the responsible mechanism.

Bug 1 — file-2's partial first hydro-year was excluded from tier-2
        patching because the activation gate rounded the start UP to the
        first full October.
Bug 2 — February percentiles pooled 28- and 29-day months together,
        biasing the rank by the leap day.
Bug 3 — only PATCH_EXCEED guarded day-index access; the other methods
        would IndexError on a record shorter than its month length.
Bug 4 — tier day-counts were committed even when a month was replaced by
        the zero-observed even-fill, miscrediting the output to a tier
        that didn't shape it.

Stdlib only.
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
    _per_month_distributions,
    disaggregate,
)
from disag.files import DailyRecord, MISSING


def _rec(y, m, fill, gap_day=None):
    dim = calendar.monthrange(y, m)[1]
    v = [float(fill)] * dim
    if gap_day is not None:
        v[gap_day - 1] = MISSING
    return DailyRecord(year=y, month=m, v=v)


def _row(log, ym):
    """The decision-log row that starts with a given 'YYYY MM' label."""
    label = f'{ym[0]:4d} {ym[1]:2d}'
    return next(l for l in log if l.startswith(label))


class Bug1PartialFirstHydroYear(unittest.TestCase):
    """File-2 data in its partial first hydro year must still patch."""

    def _scenario(self):
        # Clean hydro year Oct 1999 .. Sep 2000.
        months = [(1999, 10), (1999, 11), (1999, 12)] + [(2000, m)
                                                          for m in range(1, 10)]
        gen = {k: 100.0 for k in months}
        # File 1 complete except one missing day in March 2000.
        f1 = {(y, m): _rec(y, m, 5.0,
                           gap_day=(15 if (y, m) == (2000, 3) else None))
              for (y, m) in months}
        # File 2 begins Jan 2000 — a partial first hydro year — and covers
        # the March gap day.
        f2 = {(2000, m): _rec(2000, m, 9.0) for m in range(1, 10)}
        return gen, f1, f2

    def test_partial_year_file2_patches_the_gap(self):
        gen, f1, f2 = self._scenario()
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2)
        march = _row(log, (2000, 3))
        # The single file-1 gap day is filled from file 2 (F2 column = 1),
        # not pushed to tier 3 / MISSING.
        self.assertIn('gaps filled from file 2', march)
        self.assertNotIn('MISSING', march)
        self.assertEqual(march.split()[3], '1')  # F2 day count

    def test_same_data_starting_october_is_unchanged(self):
        # Control: if file 2 already starts in October the gate never bit,
        # so the patched result must match the partial-year case.
        gen, f1, _ = self._scenario()
        months = list(gen.keys())
        f2 = {(y, m): _rec(y, m, 9.0) for (y, m) in months}
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [f1, f2], 2)
        self.assertIn('gaps filled from file 2', _row(log, (2000, 3)))


class Bug2FebruaryDayCountBuckets(unittest.TestCase):
    """February distributions split by day-count so a 29-day Feb is ranked
    only against other 29-day Februaries."""

    def test_leap_and_nonleap_february_go_to_separate_buckets(self):
        # 2000 and 2004 are leap (29 days); 2001-2003 are not (28).
        gen = {
            (2000, 2): 29.0, (2001, 2): 28.0, (2002, 2): 28.0,
            (2003, 2): 28.0, (2004, 2): 29.0,
        }
        target_dists, _ = _per_month_distributions(gen, [])
        self.assertIn((2, 28), target_dists)
        self.assertIn((2, 29), target_dists)
        self.assertEqual(len(target_dists[(2, 29)]), 2)   # 2000, 2004
        self.assertEqual(len(target_dists[(2, 28)]), 3)   # 2001-2003

    def test_constant_length_month_has_single_bucket(self):
        # June is always 30 days → exactly one bucket, no behaviour change.
        gen = {(2000, 6): 1.0, (2001, 6): 2.0, (2002, 6): 3.0}
        target_dists, _ = _per_month_distributions(gen, [])
        june_keys = [k for k in target_dists if k[0] == 6]
        self.assertEqual(june_keys, [(6, 30)])


class Bug3ShortRecordNoCrash(unittest.TestCase):
    """A record shorter than its month length is treated as having missing
    days, not an IndexError — consistently across every method."""

    def _gen_and_short(self, method_needs_two=False):
        gen = {(2000, 6): 100.0}
        short = DailyRecord(year=2000, month=6, v=[5.0] * 20)  # dim is 30
        f1 = {(2000, 6): short}
        files = [f1, {}] if method_needs_two else [f1]
        return gen, files

    def test_one_file_short_record_marked_missing(self):
        gen, files = self._gen_and_short()
        recs, _ = disaggregate(DisagMethod.ONE_FILE, gen, files, 1)
        june = next(r for r in recs if (r.year, r.month) == (2000, 6))
        self.assertTrue(all(v == MISSING for v in june.v))

    def test_patch_file_short_record_marked_missing(self):
        gen, files = self._gen_and_short(method_needs_two=True)
        recs, _ = disaggregate(DisagMethod.PATCH_FILE, gen, files, 2)
        june = next(r for r in recs if (r.year, r.month) == (2000, 6))
        self.assertTrue(all(v == MISSING for v in june.v))


class Bug4EvenFillTierAttribution(unittest.TestCase):
    """A month whose observed flow is all-zero falls back to even-fill; its
    days must not be credited to any tier in the coverage summary."""

    def test_zero_observed_month_not_counted_as_tier1(self):
        months = [(1999, 10), (1999, 11), (1999, 12)] + [(2000, m)
                                                          for m in range(1, 10)]
        gen = {k: 100.0 for k in months}           # all positive targets
        # File 1 complete everywhere; June 2000 is observed all-zero.
        f1 = {(y, m): _rec(y, m, (0.0 if (y, m) == (2000, 6) else 5.0))
              for (y, m) in months}
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [f1], 1)

        total_days = sum(calendar.monthrange(y, m)[1] for (y, m) in months)
        june_days = calendar.monthrange(2000, 6)[1]
        tier1 = next(l for l in log if 'Tier 1 (file 1)' in l)
        # Tier-1 day count excludes the even-filled June.
        self.assertIn(f'{total_days - june_days} day(s)', tier1)
        # And the month's row is flagged as an even fill.
        self.assertIn('even fill', _row(log, (2000, 6)))


if __name__ == '__main__':
    unittest.main()
