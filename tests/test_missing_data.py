"""Missing-data behaviour across all six disaggregation methods.

Synthetic in-test fixtures (no committed data files). Covers the
edge cases that operators ask about most:

* a single missing day inside an otherwise complete month
* a whole missing month in the daily record
* a missing year span (no daily data for an entire hydro year)
* a negative monthly value in ``gen_monthly`` (treated as MISSING)
* a zero monthly value (valid — output is all zeros for that month)
* an empty daily file (no records at all)
* an empty monthly file (raises ValueError)

For each scenario the assertion is the user-visible contract:
which months survive, which are marked MISSING, and which audit
lines fire.
"""

import calendar
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import DisagMethod, disaggregate
from disag.files import DailyRecord, MISSING


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _full_month(year: int, month: int, per_day: float = 1.0) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    return DailyRecord(year=year, month=month, v=[per_day] * dim)


def _month_with_missing_day(
    year: int, month: int, missing_day_1based: int, per_day: float = 1.0
) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]
    v = [per_day] * dim
    v[missing_day_1based - 1] = MISSING
    return v and DailyRecord(year=year, month=month, v=v)


def _hydro_year_daily(year: int, per_day: float = 1.0) -> dict:
    """One hydro year (Oct year .. Sep year+1) of full daily records."""
    out = {}
    y, m = year, 10
    for _ in range(12):
        out[(y, m)] = _full_month(y, m, per_day=per_day)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _hydro_year_monthly(year: int, vol: float = 10.0) -> dict:
    """One hydro year of monthly volumes."""
    out = {}
    y, m = year, 10
    for _ in range(12):
        out[(y, m)] = vol
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _two_hydro_years_monthly(start: int, vol: float = 10.0) -> dict:
    out = _hydro_year_monthly(start, vol)
    out.update(_hydro_year_monthly(start + 1, vol))
    return out


def _two_hydro_years_daily(start: int, per_day: float = 1.0) -> dict:
    out = _hydro_year_daily(start, per_day)
    out.update(_hydro_year_daily(start + 1, per_day))
    return out


def _record(records: list, year: int, month: int) -> DailyRecord:
    return next(r for r in records if (r.year, r.month) == (year, month))


def _is_missing(rec: DailyRecord) -> bool:
    return all(v == MISSING for v in rec.v)


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------

class EmptyMonthlyTests(unittest.TestCase):
    def test_empty_monthly_raises(self):
        with self.assertRaises(ValueError):
            disaggregate(DisagMethod.ONE_FILE, {}, [{}], no_files=1)

    def test_empty_monthly_raises_for_every_method(self):
        for m in DisagMethod:
            with self.subTest(method=m):
                with self.assertRaises(ValueError):
                    disaggregate(m, {}, [{}, {}], no_files=2)


class EmptyDailyFileTests(unittest.TestCase):
    """A daily file with no records leaves every month missing (except EVEN)."""

    def test_empty_daily_marks_every_month_missing(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        recs, _ = disaggregate(DisagMethod.ONE_FILE, gen, [{}], no_files=1)
        self.assertEqual(len(recs), 12)
        self.assertTrue(all(_is_missing(r) for r in recs))

    def test_even_method_ignores_empty_daily(self):
        # EVEN doesn't need a daily file, so the output stays valid even when
        # the daily list is empty.
        gen = _hydro_year_monthly(2000, vol=10.0)
        recs, _ = disaggregate(DisagMethod.EVEN, gen, [], no_files=0)
        self.assertEqual(len(recs), 12)
        self.assertFalse(any(_is_missing(r) for r in recs))
        # Even distribution: every day for a given month carries the same
        # converted m3/s value.
        oct_2000 = _record(recs, 2000, 10)
        self.assertEqual(len(set(oct_2000.v)), 1)
        self.assertGreater(oct_2000.v[0], 0.0)


# ---------------------------------------------------------------------------
# Single-day gap
# ---------------------------------------------------------------------------

class SingleDayMissingTests(unittest.TestCase):
    """One MISSING day in the daily record — behaviour differs per method."""

    def _setup(self):
        gen = _two_hydro_years_monthly(2000, vol=10.0)
        daily = _two_hydro_years_daily(2000, per_day=1.0)
        # Drop day 15 of Jan 2001 in file 1
        v = list(daily[(2001, 1)].v)
        v[14] = MISSING
        daily[(2001, 1)] = DailyRecord(year=2001, month=1, v=v)
        return gen, daily

    def test_one_file_marks_whole_month_missing(self):
        gen, daily = self._setup()
        recs, _ = disaggregate(
            DisagMethod.ONE_FILE, gen, [daily], no_files=1,
        )
        jan = _record(recs, 2001, 1)
        self.assertTrue(_is_missing(jan), 'ONE_FILE drops the whole month')
        # Surrounding months unaffected
        self.assertFalse(_is_missing(_record(recs, 2000, 12)))
        self.assertFalse(_is_missing(_record(recs, 2001, 2)))

    def test_patch_file_uses_file2_for_the_gap(self):
        gen, daily = self._setup()
        # File 2 has a full Jan 2001 — should fill the gap day.
        daily2 = _two_hydro_years_daily(2000, per_day=2.0)
        recs, log = disaggregate(
            DisagMethod.PATCH_FILE, gen, [daily, daily2], no_files=2,
        )
        jan = _record(recs, 2001, 1)
        self.assertFalse(
            _is_missing(jan),
            'PATCH_FILE should backfill the missing day from file 2',
        )
        # No "missing day" report line — gap was silently patched.
        # No specific gap audit line is emitted by PATCH_FILE today, so just
        # confirm the month survives.

    def test_patch_cal_borrows_from_similar_month(self):
        gen, daily = self._setup()
        # Adjust gen so Jan 2002 has a volume close to Jan 2001 → it becomes
        # the patch candidate.
        gen[(2002, 1)] = 10.0
        recs, log = disaggregate(
            DisagMethod.PATCH_CAL, gen, [daily], no_files=1,
        )
        jan = _record(recs, 2001, 1)
        self.assertFalse(_is_missing(jan))
        self.assertTrue(
            any('2001  1' in l and 'similar calendar month 2002  1' in l for l in log),
            f'expected calendar-month patch line, got: {log!r}',
        )

    def test_patch_exceed_uses_donor(self):
        # Tier-3 needs ≥2 valid Januaries in BOTH the target distribution
        # AND the per-file donor pool. Jan 2001 is gappy (excluded from
        # donor pool), so we need at least 2 OTHER complete Januaries.
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen.update(_hydro_year_monthly(2001, vol=10.0))
        gen.update(_hydro_year_monthly(2002, vol=12.0))
        daily = _hydro_year_daily(2000, per_day=1.0)
        daily.update(_hydro_year_daily(2001, per_day=1.5))
        daily.update(_hydro_year_daily(2002, per_day=2.0))
        # Gap day 15 of Jan 2001 in file 1
        v = list(daily[(2001, 1)].v)
        v[14] = MISSING
        daily[(2001, 1)] = DailyRecord(year=2001, month=1, v=v)

        recs, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [daily], no_files=1,
        )
        jan = _record(recs, 2001, 1)
        self.assertFalse(_is_missing(jan))
        self.assertTrue(
            any('donor: file 1' in l and '2001  1' in l for l in log),
            f'expected tier-3 donor line, got: {log!r}',
        )


# ---------------------------------------------------------------------------
# Whole missing month
# ---------------------------------------------------------------------------

class WholeMonthMissingTests(unittest.TestCase):
    def _setup_two_years(self):
        gen = _two_hydro_years_monthly(2000, vol=10.0)
        daily = _two_hydro_years_daily(2000, per_day=1.0)
        # Delete entire Jan 2001 record from file 1
        del daily[(2001, 1)]
        return gen, daily

    def test_one_file_marks_missing_month(self):
        gen, daily = self._setup_two_years()
        recs, _ = disaggregate(
            DisagMethod.ONE_FILE, gen, [daily], no_files=1,
        )
        self.assertTrue(_is_missing(_record(recs, 2001, 1)))
        self.assertFalse(_is_missing(_record(recs, 2000, 12)))

    def test_patch_file_uses_file2_whole_month(self):
        gen, daily = self._setup_two_years()
        daily2 = _two_hydro_years_daily(2000, per_day=2.0)
        recs, _ = disaggregate(
            DisagMethod.PATCH_FILE, gen, [daily, daily2], no_files=2,
        )
        self.assertFalse(_is_missing(_record(recs, 2001, 1)))

    def test_incremental_drops_when_either_file_missing_month(self):
        gen, daily = self._setup_two_years()
        daily2 = _two_hydro_years_daily(2000, per_day=0.5)
        recs, _ = disaggregate(
            DisagMethod.INCREMENTAL, gen, [daily, daily2], no_files=2,
        )
        # File 1 is missing the whole month → INCREMENTAL marks it missing
        self.assertTrue(_is_missing(_record(recs, 2001, 1)))


# ---------------------------------------------------------------------------
# Missing year (no daily data for a full hydro year)
# ---------------------------------------------------------------------------

class MissingYearTests(unittest.TestCase):
    """gen_monthly covers 3 years; daily has only year 2."""

    def _setup(self):
        # 3 hydro years of gen so the output spans 36 months; daily covers
        # the middle hydro year only.
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen.update(_hydro_year_monthly(2001, vol=12.0))
        gen.update(_hydro_year_monthly(2002, vol=14.0))
        daily = _hydro_year_daily(2001)   # Oct 2001 .. Sep 2002
        return gen, daily

    def _setup_for_tier3(self):
        # Tier-3 needs ≥2 entries per calendar-month donor distribution.
        # gen covers 3 hydro years; daily covers 2 (the first hydro year
        # is the one that gets backfilled).
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen.update(_hydro_year_monthly(2001, vol=12.0))
        gen.update(_hydro_year_monthly(2002, vol=14.0))
        daily = _hydro_year_daily(2001, per_day=1.0)   # Oct 2001..Sep 2002
        daily.update(_hydro_year_daily(2002, per_day=1.5))  # Oct 2002..Sep 2023
        return gen, daily

    def test_one_file_only_year_2_disaggregated(self):
        gen, daily = self._setup()
        recs, _ = disaggregate(
            DisagMethod.ONE_FILE, gen, [daily], no_files=1,
        )
        # Output spans the full 3 hydro years = 36 months
        self.assertEqual(len(recs), 36)
        ok = [r for r in recs if not _is_missing(r)]
        # Only the 12 months of hydro year 2001 should be disaggregated
        self.assertEqual(len(ok), 12)
        self.assertTrue(all(
            (r.year, r.month) >= (2001, 10) and (r.year, r.month) <= (2002, 9)
            for r in ok
        ))

    def test_even_works_for_every_month(self):
        gen, daily = self._setup()
        recs, _ = disaggregate(DisagMethod.EVEN, gen, [], no_files=0)
        # EVEN never marks anything missing as long as gen_monthly has a value
        self.assertEqual(len(recs), 36)
        self.assertFalse(any(_is_missing(r) for r in recs))

    def test_patch_exceed_recovers_year_via_tier3(self):
        gen, daily = self._setup_for_tier3()
        recs, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [daily], no_files=1,
        )
        non_missing = [r for r in recs if not _is_missing(r)]
        # Every month should be filled: tier 1 for the 24 daily-covered
        # months, tier 3 for the missing hydro year 2000 (Oct 2000..Sep 2001).
        self.assertEqual(len(non_missing), 36)
        patched = [l for l in log if 'donor: file 1' in l]
        # Expect roughly 12 tier-3 patch lines (one per backfilled month).
        self.assertGreaterEqual(len(patched), 12)


# ---------------------------------------------------------------------------
# Negative / zero monthly values
# ---------------------------------------------------------------------------

class MonthlyValueEdgeCasesTests(unittest.TestCase):
    def test_negative_gen_treated_as_missing(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen[(2001, 1)] = -99.99
        daily = _hydro_year_daily(2000, per_day=1.0)
        recs, _ = disaggregate(
            DisagMethod.ONE_FILE, gen, [daily], no_files=1,
        )
        self.assertTrue(_is_missing(_record(recs, 2001, 1)))
        # Other months still disaggregated
        self.assertFalse(_is_missing(_record(recs, 2000, 12)))

    def test_zero_gen_emits_all_zero_days_and_warns(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen[(2001, 1)] = 0.0
        daily = _hydro_year_daily(2000, per_day=1.0)
        recs, log = disaggregate(
            DisagMethod.ONE_FILE, gen, [daily], no_files=1,
        )
        jan = _record(recs, 2001, 1)
        # 0.0 gen × normalised qD = 0 — all days zero, not MISSING
        self.assertFalse(_is_missing(jan))
        self.assertTrue(all(v == 0.0 for v in jan.v))
        self.assertTrue(
            any('target monthly value(s) are zero' in l for l in log),
            f'expected zero-month warning in report, got: {log!r}',
        )

    def test_patch_exceed_skips_negative_target_silently(self):
        # PATCH_EXCEED's pm_entry should still register the iterated month,
        # but no tier counts and a "monthly value missing" reason.
        gen = _hydro_year_monthly(2000, vol=10.0)
        gen.update(_hydro_year_monthly(2001, vol=10.0))
        gen[(2001, 1)] = MISSING  # negative sentinel
        daily = _two_hydro_years_daily(2000, per_day=1.0)
        recs, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [daily], no_files=1,
        )
        self.assertTrue(_is_missing(_record(recs, 2001, 1)))
        # Per-month breakdown should include a 'monthly value missing' note
        self.assertTrue(
            any('monthly value missing' in l for l in log),
            'PATCH_EXCEED report should annotate negative-gen months',
        )


class IncrementalEdgeCasesTests(unittest.TestCase):
    """INCREMENTAL = file1 - file2. The disag formula clamps negative
    differences to zero before summing, so an over-correction never
    produces negative daily flow."""

    def test_negative_difference_clamped_to_zero(self):
        # file 2 is everywhere bigger than file 1 → every day's qD is
        # negative, gets clamped to zero. With qM == 0 the output month
        # falls back to even distribution (well-defined behaviour) and
        # emits the "monthly flow <= 0" line.
        gen = _hydro_year_monthly(2000, vol=10.0)
        daily1 = _hydro_year_daily(2000, per_day=1.0)
        daily2 = _hydro_year_daily(2000, per_day=5.0)
        recs, log = disaggregate(
            DisagMethod.INCREMENTAL, gen, [daily1, daily2], no_files=2,
        )
        # All months disaggregated (no missing), with even-distribution
        # fallback applied per month due to qM=0.
        self.assertEqual(len(recs), 12)
        self.assertTrue(any('Observed monthly flow <= 0' in l for l in log))
        # Output daily values are uniform per month (even-distribution fallback).
        for r in recs:
            self.assertFalse(_is_missing(r))
            self.assertEqual(len(set(r.v)), 1)


class PatchFileStartDateTests(unittest.TestCase):
    """PATCH_FILE only consults file 2 once file 2's own data begins.
    Before file 2 starts, the method silently falls back to file 1
    (same behaviour as method 0)."""

    def test_before_file2_starts_uses_file1_only(self):
        # gen_monthly spans 2 hydro years; file 1 covers both; file 2
        # only covers the second hydro year. Months in hydro year 1 must
        # come from file 1 alone — even if file 1 has gaps there, file 2
        # must not be consulted (it would falsely appear absent).
        gen = _two_hydro_years_monthly(2000, vol=10.0)
        daily1 = _two_hydro_years_daily(2000, per_day=1.0)
        # File 2 covers hydro year 2001 only (Oct 2001..Sep 2002)
        daily2 = _hydro_year_daily(2001, per_day=2.0)
        # Drop day 15 of Nov 2000 in file 1 — before file 2 starts.
        v = list(daily1[(2000, 11)].v)
        v[14] = MISSING
        daily1[(2000, 11)] = DailyRecord(year=2000, month=11, v=v)

        recs, _ = disaggregate(
            DisagMethod.PATCH_FILE, gen, [daily1, daily2], no_files=2,
        )
        # Nov 2000 cannot be patched (file 2 hasn't started) → missing.
        self.assertTrue(_is_missing(_record(recs, 2000, 11)))
        # Months in hydro year 2001 are file-1-driven; file 2 only
        # patches where file 1 is missing. With file 1 complete there,
        # they're all fine.
        self.assertFalse(_is_missing(_record(recs, 2001, 10)))


class DecisionLogTests(unittest.TestCase):
    """The .rep decision log records one self-describing row per month for
    *every* method — not just PATCH_EXCEED."""

    def _month_rows(self, log):
        # Rows in the per-month table start with a 4-digit year.
        return [l for l in log if l[:4].strip().isdigit()]

    def test_log_has_header_and_one_row_per_month(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        daily = _hydro_year_daily(2000, per_day=1.0)
        recs, log = disaggregate(DisagMethod.ONE_FILE, gen, [daily], no_files=1)
        self.assertIn('Decision log (one row per month):', log)
        self.assertTrue(any(l.startswith('YYYY MM') for l in log))
        self.assertEqual(len(self._month_rows(log)), len(recs))

    def test_even_method_notes_every_month(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        recs, log = disaggregate(DisagMethod.EVEN, gen, [], no_files=0)
        rows = self._month_rows(log)
        self.assertEqual(len(rows), len(recs))
        self.assertTrue(all('even distribution' in r for r in rows))

    def test_incremental_note_names_both_files(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        d1 = _hydro_year_daily(2000, per_day=5.0)
        d2 = _hydro_year_daily(2000, per_day=1.0)
        _, log = disaggregate(DisagMethod.INCREMENTAL, gen, [d1, d2], no_files=2)
        self.assertTrue(
            any('file 1' in r and 'file 2' in r for r in self._month_rows(log)),
            'incremental rows should name both source files',
        )

    def test_one_file_clean_run_says_disaggregated_from_file_1(self):
        gen = _hydro_year_monthly(2000, vol=10.0)
        daily = _hydro_year_daily(2000, per_day=1.0)
        _, log = disaggregate(DisagMethod.ONE_FILE, gen, [daily], no_files=1)
        rows = self._month_rows(log)
        self.assertTrue(all('disaggregated from file 1' in r for r in rows))
        self.assertFalse(any('MISSING' in r for r in rows))


if __name__ == '__main__':
    unittest.main()
