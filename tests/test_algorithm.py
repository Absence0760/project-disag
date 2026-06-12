"""Unit tests for disag/algorithm.py — the per-helper pieces of PATCH_EXCEED.

Stdlib only (project policy); ``python3 -m unittest discover tests`` runs
these. ``pytest`` also picks them up automatically.
"""

import os
import sys
import unittest
from unittest.mock import patch

# Make ``disag`` importable when running tests from anywhere
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import (
    DisagMethod,
    NO_FILES,
    _exceed_pct,
    _monthly_totals_from_daily,
    _per_month_distributions,
    _tier2_scale_factors,
    disaggregate,
    find_exceed_donor,
)
from disag.files import DailyRecord, MISSING


class ExceedPctTests(unittest.TestCase):
    """The rank percentile is the foundation of tier-3 matching."""

    def test_smallest_value_gets_100_pct(self):
        self.assertAlmostEqual(_exceed_pct(1, [1, 2, 3, 4]), 100.0)

    def test_largest_value_gets_one_over_n(self):
        self.assertAlmostEqual(_exceed_pct(4, [1, 2, 3, 4]), 25.0)

    def test_value_above_max_returns_zero(self):
        self.assertEqual(_exceed_pct(99, [1, 2, 3]), 0.0)

    def test_empty_distribution_returns_zero(self):
        self.assertEqual(_exceed_pct(1, []), 0.0)

    def test_ties_count_at_or_above(self):
        # Three values == 5; everyone is "≥ 5" so all share 100 %.
        self.assertAlmostEqual(_exceed_pct(5, [5, 5, 5]), 100.0)


class MonthlyTotalsFromDailyTests(unittest.TestCase):
    """The completeness gate is what protects tier 3 from picking gappy donors."""

    def test_complete_month_included(self):
        rec = DailyRecord(year=2000, month=1, v=[1.0] * 31)
        totals = _monthly_totals_from_daily({(2000, 1): rec})
        self.assertEqual(totals, {(2000, 1): 31.0})

    def test_one_missing_day_excludes_whole_month(self):
        v = [1.0] * 30 + [MISSING]
        rec = DailyRecord(year=2000, month=1, v=v)
        totals = _monthly_totals_from_daily({(2000, 1): rec})
        self.assertEqual(totals, {})

    def test_short_record_excluded(self):
        # Day count < dim — possible if the file is truncated
        rec = DailyRecord(year=2000, month=1, v=[1.0] * 28)
        totals = _monthly_totals_from_daily({(2000, 1): rec})
        self.assertEqual(totals, {})

    def test_none_record_skipped(self):
        totals = _monthly_totals_from_daily({(2000, 1): None})
        self.assertEqual(totals, {})


class FindExceedDonorTests(unittest.TestCase):
    """Rank-match donor selection and tie-break ordering."""

    def _gen_monthly(self, values_by_year):
        """{year: vol}  →  {(year, 6): vol}.  Just June for simplicity."""
        return {(y, 6): v for y, v in values_by_year.items()}

    def _full_june(self, year, monthly_total_proxy):
        # 30 days summing approximately to a chosen proxy total
        per_day = monthly_total_proxy / 30.0
        return DailyRecord(year=year, month=6, v=[per_day] * 30)

    def test_exact_percentile_match_wins(self):
        # Realistic setup: target year (2002) has a gappy daily record so
        # is *not* in obs_totals.  The 4 donor candidates' totals at
        # absolute scale ×100 of gen_monthly should still rank-match.
        gen = self._gen_monthly({2000: 1.0, 2001: 2.0, 2002: 3.0,
                                 2003: 4.0, 2004: 5.0})
        obs = {(y, 6): self._full_june(y, v * 100) for y, v in
               {2000: 1.0, 2001: 2.0, 2003: 4.0, 2004: 5.0}.items()}
        totals = _monthly_totals_from_daily(obs)
        td, dd = _per_month_distributions(gen, [totals])
        result = find_exceed_donor(2002, 6, gen, [totals], td, dd)
        self.assertIsNotNone(result)
        file_idx, donor_year, p_target, p_donor = result
        # 2002's p_target in the 5-value gen_monthly dist = 60 % (3rd-largest)
        # Donor dist has 4 values.  Per-rank percentiles {25, 50, 75, 100}.
        # Closest to 60 is 50 % → that's the second-largest donor → year 2003.
        self.assertEqual(file_idx, 0)
        self.assertAlmostEqual(p_target, 60.0)
        self.assertAlmostEqual(p_donor, 50.0)
        self.assertEqual(donor_year, 2003)

    def test_self_target_excluded(self):
        # Defensive guard: even if the target somehow appears in obs_totals
        # (it shouldn't — gappy month → not in totals), we don't pick it.
        gen = self._gen_monthly({2000: 1.0, 2001: 2.0, 2002: 3.0})
        obs = {(y, 6): self._full_june(y, v) for y, v in
               {2000: 1.0, 2001: 2.0, 2002: 3.0}.items()}
        totals = _monthly_totals_from_daily(obs)
        td, dd = _per_month_distributions(gen, [totals])
        result = find_exceed_donor(2001, 6, gen, [totals], td, dd)
        # 2001 is the target; donor must be 2000 or 2002.
        self.assertIsNotNone(result)
        self.assertNotEqual(result[1], 2001)

    def test_returns_none_when_target_dist_too_small(self):
        # Only one June in gen_monthly → percentile undefined.
        gen = self._gen_monthly({2000: 1.0})
        obs = {(2000, 6): self._full_june(2000, 1.0)}
        totals = _monthly_totals_from_daily(obs)
        td, dd = _per_month_distributions(gen, [totals])
        self.assertIsNone(
            find_exceed_donor(2000, 6, gen, [totals], td, dd)
        )

    def test_returns_none_when_no_donor_pool(self):
        gen = self._gen_monthly({2000: 1.0, 2001: 2.0, 2002: 3.0})
        # Donor file has zero complete records
        td, dd = _per_month_distributions(gen, [{}])
        self.assertIsNone(
            find_exceed_donor(2001, 6, gen, [{}], td, dd)
        )

    def test_file_idx_tiebreak(self):
        # Same percentile, same year proximity, two files → file 0 wins.
        gen = self._gen_monthly({2000: 1.0, 2001: 2.0, 2002: 3.0})
        # Both files have identical 2000+2002 records → identical
        # percentile distributions for tier 3; tie-break should prefer file 0.
        f1 = {(2000, 6): self._full_june(2000, 1.0),
              (2002, 6): self._full_june(2002, 3.0)}
        f2 = {(2000, 6): self._full_june(2000, 1.0),
              (2002, 6): self._full_june(2002, 3.0)}
        t1 = _monthly_totals_from_daily(f1)
        t2 = _monthly_totals_from_daily(f2)
        td, dd = _per_month_distributions(gen, [t1, t2])
        result = find_exceed_donor(2001, 6, gen, [t1, t2], td, dd)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 0)   # file 1 (idx 0)


class Tier2ScaleFactorsTests(unittest.TestCase):
    """The cross-river rescaling factor for tier-2 patches."""

    def test_identity_when_one_file(self):
        f = _tier2_scale_factors([{(2000, 1): 10}])
        self.assertEqual(f, [{m: 1.0 for m in range(1, 13)}])

    def test_per_month_ratio(self):
        f1_totals = {(2000, 1): 100, (2001, 1): 200, (2000, 6): 10, (2001, 6): 20}
        f2_totals = {(2000, 1): 10,  (2001, 1): 20,  (2000, 6): 1,  (2001, 6): 2}
        factors = _tier2_scale_factors([f1_totals, f2_totals])
        self.assertEqual(factors[0][1], 1.0)
        # mean(f1[1])=150, mean(f2[1])=15 → ratio 10
        self.assertAlmostEqual(factors[1][1], 10.0)
        # mean(f1[6])=15, mean(f2[6])=1.5 → ratio 10
        self.assertAlmostEqual(factors[1][6], 10.0)

    def test_global_fallback_when_month_missing_in_one_file(self):
        # File 2 has no January records; should fall back to overall ratio
        f1 = {(2000, 1): 100, (2001, 1): 200, (2000, 6): 10}
        f2 = {(2000, 6): 1, (2001, 6): 2}
        factors = _tier2_scale_factors([f1, f2])
        # Per-month for Jan unavailable; global mean(f1)/mean(f2) = (100+200+10)/3 / (1+2)/2 = ~103.3/1.5 = 68.9
        self.assertAlmostEqual(factors[1][1], 310 / 3.0 / (3.0 / 2.0), places=4)

    def test_zero_or_missing_falls_back_to_one(self):
        # No data anywhere for January in file 2; file 2 mean is also zero
        f1 = {(2000, 1): 100}
        f2: dict = {}
        factors = _tier2_scale_factors([f1, f2])
        self.assertEqual(factors[1][1], 1.0)


class MethodTableTests(unittest.TestCase):
    """Catch accidental enum/registry drift."""

    def test_no_files_keys_match_enum(self):
        self.assertEqual(set(NO_FILES.keys()), set(DisagMethod))

    def test_patch_exceed_minimum_files_is_one(self):
        self.assertEqual(NO_FILES[DisagMethod.PATCH_EXCEED], 1)


class PatchExceedDonorGapTests(unittest.TestCase):
    """Defence-in-depth for the donor-coverage validation in
    `_convert_month`'s PATCH_EXCEED branch.

    `find_exceed_donor` picks by monthly-volume percentile only — it
    does not inspect day-level completeness of the donor's record. The
    upstream filter `_monthly_totals_from_daily` does enforce
    completeness today, so incomplete records never reach the donor
    pool. But a single-line regression of that filter (or a future
    caller that builds `obs_totals` differently) would expose the qD
    loop's `val = -999.0` fall-through path, which silently clamps to
    0 and emits synthetic zero-flow days no audit line announces.

    The validation in `_convert_month` catches that case explicitly:
    if the picked donor's record is short, or has its own MISSING value
    on a day we need, the target month is marked MISSING with a
    "Donor … missing day(s) X — month marked missing" report line.

    These tests bypass `_monthly_totals_from_daily` via mock so the
    broken-donor case can actually fire.
    """

    def _full_month(self, year, total_proxy):
        return DailyRecord(year=year, month=6, v=[total_proxy / 30.0] * 30)

    def _scenario(self, donor_record):
        """Target = 2003 June, day 15 (1-indexed) missing in both files.
        The picked donor candidate is whatever ``donor_record`` is —
        nothing else is eligible (file 1 has no other Junes; file 2 has
        only the gappy target + this candidate).
        """
        # gen_monthly needs >=2 Junes so target_dist has the >=2 entries
        # find_exceed_donor requires.
        gen_monthly = {
            (2001, 6): 100.0,
            (2003, 6): 300.0,
        }
        # File 1 has only the gappy target. donor_dist for file 1 ends
        # up length 1 (with the mock bypass) → excluded by find_exceed_donor.
        f1 = {
            (2003, 6): DailyRecord(
                year=2003, month=6,
                v=[10.0] * 14 + [MISSING] + [10.0] * 15,
            ),
        }
        # File 2 has the same gappy target + one donor candidate. After
        # self-exclusion, (2001, 6) = donor_record is the only candidate.
        f2 = {
            (2003, 6): DailyRecord(
                year=2003, month=6,
                v=[10.0] * 14 + [MISSING] + [10.0] * 15,
            ),
            (2001, 6): donor_record,
        }
        return gen_monthly, [f1, f2]

    def _run_with_broken_donor_filter(self, gen, daily):
        """Run disaggregate with the donor-completeness filter disabled,
        so the test can drive an incomplete donor through the rest of
        the pipeline. Real callers always go through the filter."""

        def _no_filter_totals(obs):
            # Same shape as _monthly_totals_from_daily but accepts every
            # record regardless of length / MISSING values.
            return {
                (y, m): sum(v for v in rec.v if v >= 0)
                for (y, m), rec in obs.items() if rec is not None
            }

        with patch(
            'disag.algorithm._monthly_totals_from_daily',
            side_effect=_no_filter_totals,
        ):
            return disaggregate(
                DisagMethod.PATCH_EXCEED, gen, daily, no_files=2
            )

    def _patch_log(self, log):
        return [
            l for l in log
            if l[:4].strip().isdigit() and '2003  6' in l
        ]

    def test_short_donor_marks_month_missing(self):
        short = DailyRecord(year=2001, month=6, v=[5.0] * 10)
        gen, daily = self._scenario(short)
        recs, log = self._run_with_broken_donor_filter(gen, daily)

        june_2003 = next(r for r in recs if (r.year, r.month) == (2003, 6))
        # Validation in _convert_month must reject the short donor — no
        # silent zero-fill on the missing day, no truncated patch.
        self.assertTrue(
            all(v == MISSING for v in june_2003.v),
            f'June 2003 should be MISSING when donor is short; got {june_2003.v}',
        )
        msg = self._patch_log(log)
        self.assertTrue(
            any('missing day(s) 15' in l and l.lstrip().startswith('2003')
                and 'MISSING' in l
                for l in msg),
            f'expected explicit donor-gap log line, got: {msg}',
        )

    def test_donor_with_gap_on_required_day_marks_month_missing(self):
        # Full length, but MISSING on the exact day we need.
        gappy = DailyRecord(
            year=2001, month=6,
            v=[5.0] * 14 + [MISSING] + [5.0] * 15,
        )
        gen, daily = self._scenario(gappy)
        recs, log = self._run_with_broken_donor_filter(gen, daily)

        june_2003 = next(r for r in recs if (r.year, r.month) == (2003, 6))
        self.assertTrue(
            all(v == MISSING for v in june_2003.v),
            f'June 2003 should be MISSING when donor shares the gap; got {june_2003.v}',
        )
        msg = self._patch_log(log)
        self.assertTrue(
            any('missing day(s) 15' in l and l.lstrip().startswith('2003')
                and 'MISSING' in l
                for l in msg),
            f'expected explicit donor-gap log line, got: {msg}',
        )

    # Happy-path regression for PATCH_EXCEED is covered end-to-end by
    # the existing scenario tests in tests/test_e2e.py against the
    # committed examples/method5_demo/data/ fixtures — no need for an
    # additional one here.


class PatchExceedRoutineNoteTests(unittest.TestCase):
    """The decision-log wording for routine (non-donor) PATCH_EXCEED months.

    The note is finalised from the per-source day counts after the qD
    loop. The subtle case is a month where file 1 is *fully* missing and
    file 2 covers every day: tier 2 supplies all of them, so file 1
    contributes nothing. The note must say so plainly ("disaggregated
    from file 2 (file 1 fully missing)") rather than the mixed-month
    "disaggregated from file 1, gaps filled from file 2" — the latter
    implies file 1 contributed days when it contributed none.
    """

    @staticmethod
    def _decision_row(log, year, month):
        for line in log:
            parts = line.split()
            if (len(parts) >= 5 and parts[0].isdigit() and parts[1].isdigit()
                    and int(parts[0]) == year and int(parts[1]) == month):
                return parts
        return None

    def test_file1_fully_missing_labelled_as_file2(self):
        # June 2003: file 1 all-MISSING, file 2 complete → every day tier 2.
        gen = {(2001, 6): 100.0, (2003, 6): 300.0}
        f1 = {(2003, 6): DailyRecord(2003, 6, [MISSING] * 30)}
        f2 = {
            (2001, 6): DailyRecord(2001, 6, [10.0] * 30),
            (2003, 6): DailyRecord(2003, 6, [5.0 + d * 0.1 for d in range(30)]),
        }
        recs, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [f1, f2], no_files=2)

        row = self._decision_row(log, 2003, 6)
        self.assertIsNotNone(row, 'no decision-log row for June 2003')
        f1_days, f2_days, oth_days = int(row[2]), int(row[3]), int(row[4])
        note = ' '.join(row[5:])
        self.assertEqual((f1_days, f2_days, oth_days), (0, 30, 0),
                         f'all 30 days should come from file 2; row={row}')
        self.assertTrue(
            note.startswith('disaggregated from file 2 (file 1 fully missing'),
            f'unexpected note: {note!r}')
        self.assertIn('file-2 → file-1 scale ×', note,
                      f'note should surface the tier-2 scale factor: {note!r}')

        june = next(r for r in recs if (r.year, r.month) == (2003, 6))
        self.assertTrue(all(v >= 0 for v in june.v),
                        'June 2003 should be disaggregated, not marked MISSING')

    def test_mixed_month_keeps_gaps_filled_wording(self):
        # June 2003: file 1 missing one day, file 2 fills it → file 1 still
        # contributes 29 days, so the mixed-month wording is correct.
        gen = {(2001, 6): 100.0, (2003, 6): 300.0}
        f1_vals = [10.0] * 14 + [MISSING] + [10.0] * 15
        f1 = {(2003, 6): DailyRecord(2003, 6, f1_vals)}
        f2 = {
            (2001, 6): DailyRecord(2001, 6, [8.0] * 30),
            (2003, 6): DailyRecord(2003, 6, [8.0] * 30),
        }
        recs, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [f1, f2], no_files=2)

        row = self._decision_row(log, 2003, 6)
        self.assertIsNotNone(row, 'no decision-log row for June 2003')
        f1_days, f2_days = int(row[2]), int(row[3])
        note = ' '.join(row[5:])
        self.assertEqual((f1_days, f2_days), (29, 1),
                         f'29 file-1 days + 1 file-2 fill expected; row={row}')
        self.assertTrue(
            note.startswith('disaggregated from file 1, gaps filled from file 2'),
            f'unexpected note: {note!r}')
        self.assertIn('file-2 → file-1 scale ×', note,
                      f'note should surface the tier-2 scale factor: {note!r}')


if __name__ == '__main__':
    unittest.main()
