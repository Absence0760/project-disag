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
    """Tier-3 donor rows in the decision log: a ``YYYY MM`` row whose note
    names a ``donor:`` source (only tier-3 patches carry that token)."""
    return [
        l for l in report_lines
        if l[:4].strip().isdigit() and 'donor:' in l
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
        self.assertIn('donor: file 1 2002  6', patches[0])

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
        self.assertIn('donor: file 1 2004  6', patches[0])
        self.assertIn('2005  6', patches[1])
        self.assertIn('donor: file 1 2002  6', patches[1])

    def test_scenario_5_all_three_tiers_in_one_month(self):
        # File 1 has Jun 2003 days 11..20 missing (0-indexed 10..19);
        # file 2 has Jun 2003 days 15..20 also missing (0-indexed 14..19).
        # → days 1..10 + 21..30 from Tier 1, days 11..14 from Tier 2,
        #   days 15..20 from a Tier-3 donor month (file 1 / Jun 2005).
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_scattered.DAY'),
             os.path.join(DATA, 'gauge_b_scattered.DAY')],
        )
        disagg, missing = count_coverage(recs)
        self.assertEqual(missing, 0)
        self.assertEqual(disagg, 72)

        patches = _tier3_patches(log)
        self.assertEqual(len(patches), 1)
        self.assertIn('2003  6', patches[0])
        self.assertIn('donor: file 1 2005  6', patches[0])

        # Tier coverage summary: 4 Tier-2 days, 6 Tier-3 days, all in 1 month.
        tier2 = next(l for l in log if 'Tier 2' in l)
        self.assertIn('4 day(s)', tier2)
        self.assertIn('1 month(s)', tier2)
        tier3 = next(l for l in log if 'Tier 3' in l)
        self.assertIn('6 day(s)', tier3)
        self.assertIn('1 month(s)', tier3)

        # Volume preservation for the mixed-tier month.
        gen = read_monthly_file(os.path.join(DATA, 'target.MON'))
        target = next(r for r in recs if (r.year, r.month) == (2003, 6))
        out_mm3 = sum(target.v) * 86400 / 1e6
        self.assertAlmostEqual(out_mm3, gen[(2003, 6)], places=3)


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

    def test_per_month_breakdown_lists_every_iterated_month(self):
        # Scenario 5: 1 month splits across all three tiers (Jun 2003 →
        # T1=20, T2=4, T3=6); every other month is pure T1.  The breakdown
        # section must therefore have a row for every iterated month, with
        # the mixed Jun 2003 row showing all three counts non-zero.
        recs, log = _run(
            DisagMethod.PATCH_EXCEED,
            [os.path.join(DATA, 'gauge_a_scattered.DAY'),
             os.path.join(DATA, 'gauge_b_scattered.DAY')],
        )

        # Section header + column header are present
        header_idx = next(
            (i for i, l in enumerate(log)
             if l.startswith('Decision log')),
            -1,
        )
        if header_idx == -1:
            self.fail('decision log section missing from report')
        self.assertTrue(log[header_idx + 1].startswith('YYYY MM'))

        # Pull the per-month rows: lines after the column header that begin
        # with a 4-digit year, stopping when we hit the tier-coverage summary.
        rows = []
        for l in log[header_idx + 2:]:
            if l.startswith('Tier coverage summary'):
                break
            if l[:4].strip().isdigit():
                rows.append(l)

        # Every iterated month must appear in the breakdown.
        self.assertEqual(len(rows), len(recs))

        # The mixed-tier month (Jun 2003) must show all three counts non-zero
        jun_2003 = next(r for r in rows if r.startswith('2003  6'))
        # Format: 'YYYY MM   F1 F2 OTH   result / source'
        parts = jun_2003.split()
        self.assertEqual(parts[0], '2003')
        self.assertEqual(parts[1], '6')
        t1, t2, t3 = int(parts[2]), int(parts[3]), int(parts[4])
        self.assertEqual(t1, 20)
        self.assertEqual(t2, 4)
        self.assertEqual(t3, 6)
        self.assertIn('donor: file 1 2005  6', jun_2003)

        # A non-tier-3 month should have zero T2/T3 and full T1
        oct_2000 = next(r for r in rows if r.startswith('2000 10'))
        parts = oct_2000.split()
        self.assertEqual(int(parts[2]), 31)  # Oct = 31 days
        self.assertEqual(int(parts[3]), 0)
        self.assertEqual(int(parts[4]), 0)

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

    def test_non_exceed_methods_emit_sentinel_records_for_clipped_months(self):
        # All methods iterate over gen_monthly's full hydro span. Months
        # outside the daily file's coverage are emitted in the output as
        # all-MISSING records (rather than silently dropped), so the
        # output file is self-describing.
        from disag.algorithm import disaggregate
        from disag.files import DailyRecord, MISSING
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
        records, _ = disaggregate(
            DisagMethod.ONE_FILE, gen, [obs], 1,
        )
        # Output spans all 21 hydro years × 12 months = 252 records
        self.assertEqual(len(records), 21 * 12)
        # First record (1990-10) is outside file 1's coverage → all MISSING
        first = records[0]
        self.assertEqual((first.year, first.month), (1990, 10))
        self.assertTrue(all(v == MISSING for v in first.v))
        # A record inside file 1's coverage has real values
        inside = next(
            r for r in records if (r.year, r.month) == (2005, 1)
        )
        self.assertTrue(all(v >= 0 for v in inside.v))

    def test_patch_exceed_backfills_instead_of_clipping(self):
        # PATCH_EXCEED extends the run window to gen_monthly's full span
        # rather than clipping to the daily file's coverage. Months
        # outside the daily file are backfilled via tier 3.
        from disag.algorithm import disaggregate
        from disag.files import DailyRecord
        import calendar as _cal
        gen = {}
        for y in range(1990, 2011):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = y if hm >= 10 else y + 1
                gen[(cy, hm)] = 1.0 + (hm % 5) * 0.1   # vary so percentile differs
        obs = {}
        for y in range(2000, 2010):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = y if hm >= 10 else y + 1
                dim = _cal.monthrange(cy, hm)[1]
                obs[(cy, hm)] = DailyRecord(year=cy, month=hm, v=[1.0] * dim)
        records, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1,
        )
        # No clipped-window warning for PATCH_EXCEED — backfill replaces clipping.
        self.assertFalse(
            any('outside the run window' in l for l in log),
            f'unexpected clipped warning under PATCH_EXCEED: '
            f'{[l for l in log if "outside" in l]}',
        )
        # Output spans all of gen_monthly: 21 hydro years × 12 months = 252
        self.assertEqual(len(records), 21 * 12)
        # Pre-2000 months were backfilled via tier 3 — every value is finite
        first_rec = records[0]
        self.assertEqual((first_rec.year, first_rec.month), (1990, 10))
        self.assertTrue(all(v >= 0 for v in first_rec.v))
        # Tier coverage summary should report a non-zero tier-3 count
        tier3 = next(l for l in log if 'Tier 3' in l)
        self.assertNotIn('     0 day(s)', tier3)


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
        patch = next(l for l in log if 'patched from' in l)
        self.assertIn('2003  6', patch)                               # target month
        self.assertIn('similar calendar month 2002  6', patch)        # method 1's pick

    def test_method5_picks_closest_percentile(self):
        from disag.algorithm import disaggregate
        gen, obs = self._build()
        _, log = disaggregate(DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1)
        patch = next(l for l in log if 'donor:' in l)
        self.assertIn('2003  6', patch)
        self.assertIn('donor: file 1 2005  6', patch)

    def test_methods_diverge_on_this_dataset(self):
        """Sanity: confirm the two methods explicitly chose different
        donor years on the same input."""
        from disag.algorithm import disaggregate
        gen, obs = self._build()
        _, log1 = disaggregate(DisagMethod.PATCH_CAL,    gen, [obs, {}], 1)
        _, log5 = disaggregate(DisagMethod.PATCH_EXCEED, gen, [obs, {}], 1)
        donor1 = next(l for l in log1 if 'patched from' in l)
        donor5 = next(l for l in log5 if 'donor:' in l)
        # Pick the donor-year token from each line and assert they differ
        self.assertIn('2002', donor1)
        self.assertIn('2005', donor5)
        self.assertNotIn('2002', donor5)


class Tier3CrossFileRescaleTests(unittest.TestCase):
    """Regression tests for the tier-3 cross-file rescale.

    When tier 3 fires and the donor month comes from file 2 (a different
    river at a different absolute scale), the donor's day values must be
    rescaled to file-1's per-calendar-month mean before they enter qD.
    Without the rescale, a *mixed* month — some days tier-1 from file 1,
    other days tier-3 from a file-2 donor — would get a distorted daily
    shape, with the tier-3 days appearing as an artificial drop or spike
    purely because of the cross-river scale mismatch.

    Whole-month tier-3 fills are unaffected by the rescale (a constant
    factor cancels in the disag formula's qD/qM ratio), so these tests
    specifically construct a *mixed* tier-1 + tier-3 month.
    """

    def _build_mixed_tier1_tier3_month(self):
        """Force tier 3 to pick a file-2 donor for some days of a month
        whose other days are tier-1 from file 1.

        Setup:
        - gen_monthly Junes: 1, 2, 3, 4, 5 across 5 hydro years.
          Target Jun 2003 has volume 3.0, percentile 60% (rank 3 of 5).
        - file 1: only Jun 2001 is complete (mean ~10 m³/s). Jun 2003
          has days 1-15 valid (~10 m³/s), days 16-30 missing. All other
          Junes have one missing day, so they're not eligible donors.
          → file 1's June donor pool has < 2 candidates → file 1 is
          disqualified as a donor source for June.
        - file 2: Junes 2001, 2002, 2004, 2005 complete with means
          ~1, 2, 4, 5 m³/s (uniform within each month). Jun 2003 has
          all 30 days missing.
          → file 2's June donor pool has 4 candidates.
        - Result: tier 3 picks file 2's Jun 2004 (uniform 4.0 m³/s).
          Without rescale: tier-3 days = 4.0 → mixed qD distorted.
          With rescale: tier-3 days = 4.0 × (10/3) ≈ 13.33 → coherent.
        """
        import calendar as _cal
        from disag.files import DailyRecord, MISSING

        gen = {}
        for hy in range(2000, 2005):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                gen[(cy, hm)] = 1.0
        gen[(2001, 6)] = 1.0
        gen[(2002, 6)] = 2.0
        gen[(2003, 6)] = 3.0    # target
        gen[(2004, 6)] = 4.0
        gen[(2005, 6)] = 5.0

        # File 1: only 2001 has a complete June; Jun 2003 days 1-15
        # valid, 16-30 missing; other Junes have 1 missing day.
        obs1 = {}
        file1_scale = 10.0
        for hy in range(2000, 2005):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                if hm == 6:
                    if cy == 2001:
                        v = [file1_scale] * dim
                    elif cy == 2003:
                        v = [file1_scale] * 15 + [MISSING] * (dim - 15)
                    else:
                        v = [file1_scale] * (dim - 1) + [MISSING]
                else:
                    v = [file1_scale] * dim
                obs1[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v)

        # File 2: 4 complete Junes at progressively wetter levels;
        # Jun 2003 entirely missing.
        obs2 = {}
        file2_means = {2001: 1.0, 2002: 2.0, 2004: 4.0, 2005: 5.0}
        for hy in range(2000, 2005):
            for hm in (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                cy = hy if hm >= 10 else hy + 1
                dim = _cal.monthrange(cy, hm)[1]
                if hm == 6:
                    if cy == 2003:
                        v = [MISSING] * dim
                    else:
                        v = [file2_means[cy]] * dim
                else:
                    v = [1.0] * dim
                obs2[(cy, hm)] = DailyRecord(year=cy, month=hm, v=v)

        return gen, obs1, obs2

    def test_donor_comes_from_file_2(self):
        gen, obs1, obs2 = self._build_mixed_tier1_tier3_month()
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2,
        )
        patch = next(l for l in log if 'donor:' in l)
        self.assertIn('2003  6', patch)
        self.assertIn('donor: file 2', patch)

    def test_tier3_donor_rescaled_to_file1_scale(self):
        # File-1 mean ≈ 10, file-2 mean ≈ 3 → rescale factor 10/3 ≈ 3.33.
        # Donor (file 2's Jun 2004 at 4.0/day uniform) → ~13.33/day on
        # file-1 scale.  So the day-16/day-1 ratio is ≈ 1.33 with the
        # rescale; without it, ratio would be 4/10 = 0.4 (the bug).
        gen, obs1, obs2 = self._build_mixed_tier1_tier3_month()
        recs, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2,
        )
        target = next(r for r in recs if (r.year, r.month) == (2003, 6))
        out_mm3 = sum(target.v) * 86400 / 1e6
        self.assertAlmostEqual(out_mm3, 3.0, places=3)
        ratio = target.v[15] / target.v[0]
        self.assertGreater(
            ratio, 1.0,
            f'tier-3 days dropped below tier-1 — cross-file scale leaked '
            f'into qD (ratio={ratio:.3f}, expected ≈ 1.33)',
        )
        self.assertAlmostEqual(ratio, 13.33 / 10.0, places=2)

    def test_whole_month_tier3_unaffected_by_rescale(self):
        # A constant scale cancels in the disag formula's qD/qM ratio,
        # so a whole-month tier-3 fill from a uniform donor produces a
        # uniform output regardless of which file the donor came from.
        import calendar as _cal
        from disag.files import DailyRecord, MISSING
        gen, obs1, obs2 = self._build_mixed_tier1_tier3_month()
        dim = _cal.monthrange(2003, 6)[1]
        obs1[(2003, 6)] = DailyRecord(year=2003, month=6, v=[MISSING] * dim)

        recs, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2,
        )
        target = next(r for r in recs if (r.year, r.month) == (2003, 6))
        self.assertTrue(all(abs(v - target.v[0]) < 1e-9 for v in target.v))
        out_mm3 = sum(target.v) * 86400 / 1e6
        self.assertAlmostEqual(out_mm3, 3.0, places=3)


if __name__ == '__main__':
    unittest.main()
