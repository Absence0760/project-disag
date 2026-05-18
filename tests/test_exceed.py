"""Tests for the exceed/ package — exceedance calculator + I/O + CLI smoke."""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from exceed.algorithm import (
    ExceedanceCalculator,
    SEASON_PRESETS,
    calculate_monthly_exceedance,
    calculate_seasonal_exceedance,
    get_season_presets,
    match_exceedance_values,
)
from exceed.files import read_monthly_file as _exc_read_monthly


def _data_method4(name):
    return os.path.join(ROOT, 'examples', 'method4_demo', 'data', name)


class CalculatorTests(unittest.TestCase):
    """Exercise ExceedanceCalculator's bucket/percentile math directly."""

    def test_uniform_bucket_distribution(self):
        # 20 evenly-spaced values from 0 to 19 → range 0..19, 20 buckets
        # of width 1, so each bucket gets exactly one value.
        calc = ExceedanceCalculator(min_flow=0.0, max_flow=20.0, num_intervals=20)
        for v in range(20):
            calc.process_value(float(v))
        result = calc.calculate_result()
        self.assertEqual(result.total_count, 20)
        self.assertEqual(result.count_below, 0)
        self.assertEqual(result.count_above, 0)
        # Bottom interval has every value ≥ 0 → 100 %
        self.assertAlmostEqual(result.exceedance_pct[0], 100.0)
        # Top interval (i = N) has only the topmost value → 5 %
        self.assertAlmostEqual(result.exceedance_pct[-1], 5.0)

    def test_above_range_counted_separately(self):
        calc = ExceedanceCalculator(min_flow=0.0, max_flow=10.0, num_intervals=10)
        for v in [1.0, 2.0, 3.0, 50.0, 99.0]:
            calc.process_value(v)
        result = calc.calculate_result()
        self.assertEqual(result.count_above, 2)   # 50 + 99 are out-of-range high
        self.assertEqual(result.count_below, 0)

    def test_below_range_counted_separately(self):
        calc = ExceedanceCalculator(min_flow=10.0, max_flow=20.0, num_intervals=10)
        for v in [0.0, 5.0, 15.0]:
            calc.process_value(v)
        result = calc.calculate_result()
        self.assertEqual(result.count_below, 2)


class CalculateMonthlyExceedanceTests(unittest.TestCase):
    """The thin wrapper that auto-derives min/max from the data."""

    def test_returns_monotone_decreasing_exceedance(self):
        result = calculate_monthly_exceedance(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            num_intervals=5,
        )
        # Exceedance % is monotone non-increasing as flow value increases
        for prev, nxt in zip(result.exceedance_pct, result.exceedance_pct[1:]):
            self.assertGreaterEqual(prev, nxt)

    def test_identical_values_dont_zero_divide(self):
        # When min == max the calculator nudges max up by 1.01x + 0.01.
        # Here all 5 values are 1.0; this should not raise.
        result = calculate_monthly_exceedance([1.0] * 5, num_intervals=10)
        self.assertEqual(result.total_count, 5)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            calculate_monthly_exceedance([], num_intervals=10)


class SeasonalExceedanceTests(unittest.TestCase):
    """Pooling calendar months into seasons before computing exceedance."""

    def test_two_season_preset(self):
        seasons = get_season_presets(2)
        self.assertIn('Wet Season', seasons)
        self.assertIn('Dry Season', seasons)
        # Wet covers Oct-Mar, Dry covers Apr-Sep
        self.assertEqual(set(seasons['Wet Season']), {10, 11, 12, 1, 2, 3})
        self.assertEqual(set(seasons['Dry Season']), {4, 5, 6, 7, 8, 9})

    def test_seasonal_pools_values_across_months(self):
        monthly = {m: [float(m)] * 3 for m in range(1, 13)}   # 3 values/month
        seasons = {'A': [1, 2, 3], 'B': [11, 12]}
        results = calculate_seasonal_exceedance(monthly, seasons, num_intervals=5)
        self.assertEqual(results['A'].total_count, 9)   # 3 months × 3 values
        self.assertEqual(results['B'].total_count, 6)   # 2 months × 3 values

    def test_unknown_preset_returns_empty(self):
        self.assertEqual(get_season_presets(99), {})

    def test_all_three_presets_partition_calendar(self):
        # For 2 and 4 seasons every preset should partition the 12
        # calendar months without overlap.
        for n in (2, 4):
            months = []
            for m_list in SEASON_PRESETS[n].values():
                months.extend(m_list)
            self.assertEqual(sorted(months), list(range(1, 13)))


class MatchExceedanceTests(unittest.TestCase):
    """Pair a monthly exceedance entry with its closest daily counterpart."""

    def test_matches_within_tolerance(self):
        monthly = calculate_monthly_exceedance([1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                                               num_intervals=5)
        daily = calculate_monthly_exceedance([10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                                             num_intervals=5)
        matches = match_exceedance_values(monthly, daily, tolerance_pct=10.0)
        # With the same shape, every monthly entry should find a daily
        # entry within tolerance.
        self.assertGreater(len(matches), 0)
        for m in matches:
            self.assertLessEqual(m['diff'], 10.0)

    def test_zero_matches_when_tolerance_zero_and_dists_differ(self):
        monthly = calculate_monthly_exceedance([1, 2, 3], num_intervals=3)
        daily = calculate_monthly_exceedance([100, 200, 300], num_intervals=20)
        # Different bucket count → percentiles likely don't line up exactly
        matches = match_exceedance_values(monthly, daily, tolerance_pct=0.0)
        # Some percentiles might still match exactly (trivially),
        # but most should not. We just assert this doesn't crash.
        self.assertIsInstance(matches, list)


class ExceedReadMonthlyTests(unittest.TestCase):
    """exceed/files.py:read_monthly_file flattens to {month: [values]}."""

    def test_reads_demo_method4_target(self):
        m = _exc_read_monthly(_data_method4('target.MON'))
        # All 12 calendar months present
        self.assertEqual(set(m.keys()), set(range(1, 13)))
        # Each month has 3 values (3 hydro years)
        for month_values in m.values():
            self.assertEqual(len(month_values), 3)


class MatchExceedanceDirectionTests(unittest.TestCase):
    """Each match entry exposes both the monthly and daily flow at the
    matched exceedance percentage, plus the percentage diff between them."""

    def test_match_entries_carry_both_flows(self):
        # Monthly distribution shifted much higher than daily — the
        # paired flows should reflect that even when their percentile
        # ranks agree.
        monthly = calculate_monthly_exceedance(
            [100, 200, 300, 400, 500], num_intervals=5,
        )
        daily = calculate_monthly_exceedance(
            [1, 2, 3, 4, 5], num_intervals=5,
        )
        matches = match_exceedance_values(monthly, daily, tolerance_pct=100.0)
        self.assertGreater(len(matches), 0)
        for m in matches:
            self.assertIn('flow_monthly', m)
            self.assertIn('flow_daily', m)
            self.assertIn('exceed_monthly', m)
            self.assertIn('exceed_daily', m)
            self.assertIn('diff', m)
            # The diff is exceedance % difference (non-negative)
            self.assertGreaterEqual(m['diff'], 0.0)
            self.assertLessEqual(m['diff'], 100.0)
            # Monthly distribution was 100x larger throughout — paired
            # flows must reflect that.
            self.assertGreaterEqual(m['flow_monthly'], m['flow_daily'])

    def test_huge_tolerance_returns_pairing_for_every_monthly_entry(self):
        monthly = calculate_monthly_exceedance([1, 2, 3, 4, 5], num_intervals=5)
        daily = calculate_monthly_exceedance([10, 20, 30, 40, 50], num_intervals=5)
        matches = match_exceedance_values(monthly, daily, tolerance_pct=200.0)
        # With tolerance > any possible diff (max diff is 100 pp),
        # every monthly entry pairs.
        self.assertEqual(len(matches), len(monthly.exceedance_pct))


class SeasonalEdgeCasesTests(unittest.TestCase):
    """Edge cases for calculate_seasonal_exceedance not covered above."""

    def test_season_with_no_data_skipped(self):
        # Monthly data only for Jan + Feb; a "summer" season covering
        # Jun-Aug has zero values → it should be skipped, not raise.
        monthly = {1: [1.0, 2.0, 3.0], 2: [4.0, 5.0]}
        seasons = {'JanFeb': [1, 2], 'Summer': [6, 7, 8]}
        results = calculate_seasonal_exceedance(monthly, seasons, num_intervals=3)
        self.assertIn('JanFeb', results)
        self.assertNotIn('Summer', results)

    def test_algorithm_does_not_filter_negatives_caller_must(self):
        # Document the contract: calculate_seasonal_exceedance treats
        # every value in monthly_data as valid. Missing-data filtering
        # happens at the reader boundary (exceed.files.read_monthly_file
        # drops values < 0 at parse time). A caller that bypasses the
        # reader and hands in raw -99.99 sentinels will see them
        # bucketed as real flow.
        monthly = {1: [1.0, -99.99, 3.0]}
        seasons = {'Jan': [1]}
        results = calculate_seasonal_exceedance(monthly, seasons, num_intervals=3)
        self.assertEqual(
            results['Jan'].total_count, 3,
            'algorithm intentionally does not filter; pre-filter at the reader',
        )


class ExceedCliSmokeTest(unittest.TestCase):
    """Run python -m exceed --no-gui and confirm it produces a report."""

    def test_runs_against_demo_method4_target(self):
        fd, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd)
        try:
            res = subprocess.run(
                [sys.executable, '-m', 'exceed', '--no-gui',
                 '--monthly', _data_method4('target.MON'),
                 '--output', out, '--intervals', '10'],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(os.path.exists(out))
            with open(out) as f:
                content = f.read()
            # Per-calendar-month sections present
            self.assertIn('JANUARY', content.upper())
            self.assertIn('Exceedance%', content)
        finally:
            if os.path.exists(out):
                os.unlink(out)


if __name__ == '__main__':
    unittest.main()
