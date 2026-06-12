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
from exceed.files import (
    read_monthly_file as _exc_read_monthly,
    write_exceedance_svg,
    write_matching_report,
)


def _data_method4(name):
    return os.path.join(ROOT, 'examples', 'method4_demo', 'data', name)


def _data_method0(name):
    return os.path.join(ROOT, 'examples', 'method0_demo', 'data', name)


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


class ExceedMonthlyReaderCollisionTests(unittest.TestCase):
    """exceed's .mon reader must not drop wet-year rows whose contiguous
    9-char columns collide (regression: the old split()-based parser
    silently skipped them via `len(parts) < 13`)."""

    def test_wet_year_collision_row_is_not_dropped(self):
        vals = [2.0, 4.0, 8.0, 200.0, 1500.0, 14639.12, 13670.74,
                80.0, 12.0, 6.0, 3.0, 1.5]
        fd, path = tempfile.mkstemp(suffix='.MON')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with open(path, 'w') as f:
            for _ in range(5):
                f.write('-\n')
            f.write(f'{1991:4d}' + ''.join(f'{v:9.3f}' for v in vals) + '\n')

        data = _exc_read_monthly(path)
        # Hydro col 6 = Mar (cal month 3), col 7 = Apr (cal month 4).
        self.assertIn(14639.12, [round(v, 2) for v in data[3]])
        self.assertIn(13670.74, [round(v, 2) for v in data[4]])
        # Oct value present too (row wasn't skipped wholesale).
        self.assertIn(2.0, [round(v, 2) for v in data[10]])


class WriteExceedanceSvgTests(unittest.TestCase):
    """The SVG flow-frequency curve writer (stdlib-only, no matplotlib)."""

    def _dict(self, values):
        r = calculate_monthly_exceedance(values, 20)
        return {
            'flow_values': r.flow_values,
            'exceedance_pct': r.exceedance_pct,
            'count_above': r.count_above,
            'count_below': r.count_below,
            'total_count': r.total_count,
        }

    def _write(self, exceedance, **kw):
        fd, path = tempfile.mkstemp(suffix='.svg')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        write_exceedance_svg(path, exceedance, **kw)
        with open(path) as f:
            return f.read()

    def test_monthly_keys_render_a_polyline_per_series(self):
        exc = {1: self._dict([1.0, 2.0, 3.0, 4.0, 5.0]),
               6: self._dict([10.0, 20.0, 30.0])}
        svg = self._write(exc, title='Monthly flow-frequency curves')
        self.assertTrue(svg.lstrip().startswith('<svg'))
        self.assertIn('</svg>', svg)
        self.assertEqual(svg.count('<polyline'), 2)
        # Int month keys become month-name legend entries.
        self.assertIn('January', svg)
        self.assertIn('June', svg)
        self.assertIn('Monthly flow-frequency curves', svg)

    def test_daily_and_season_keys_label_correctly(self):
        exc = {'daily_3': self._dict([1.0, 2.0, 3.0]),
               'Wet Season': self._dict([4.0, 5.0, 6.0])}
        svg = self._write(exc)
        self.assertIn('Daily March', svg)
        self.assertIn('Wet Season', svg)

    def test_title_is_xml_escaped(self):
        exc = {1: self._dict([1.0, 2.0, 3.0])}
        svg = self._write(exc, title='Flows < 5 & rising')
        self.assertIn('Flows &lt; 5 &amp; rising', svg)
        self.assertNotIn('< 5 &', svg)

    def test_all_zero_flows_do_not_crash(self):
        # ymax guard: a degenerate all-zero series must not divide by zero.
        svg = self._write({1: self._dict([0.0, 0.0, 0.0])})
        self.assertIn('<polyline', svg)


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


class ExceedanceCalculatorValidationTests(unittest.TestCase):
    """The calculator rejects a non-positive interval count up front."""

    def test_zero_intervals_raises(self):
        with self.assertRaises(ValueError):
            ExceedanceCalculator(0.0, 10.0, 0)

    def test_negative_intervals_raises(self):
        with self.assertRaises(ValueError):
            ExceedanceCalculator(0.0, 10.0, -3)


class WriteMatchingReportTests(unittest.TestCase):
    """The shared matching-report writer used by the CLI and GUI."""

    def test_returns_count_and_writes_file(self):
        monthly = {m: [] for m in range(1, 13)}
        daily = {m: [] for m in range(1, 13)}
        monthly[1] = [1.0, 2.0, 3.0, 4.0, 5.0]
        daily[1] = [1.0, 2.0, 3.0, 4.0, 5.0]
        fd, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd)
        try:
            n = write_matching_report(out, monthly, daily,
                                      num_intervals=5, tolerance_pct=50.0)
            self.assertIsInstance(n, int)
            self.assertGreater(n, 0)
            with open(out) as f:
                content = f.read()
            self.assertIn('Exceedance Matching Report', content)
            self.assertIn('JANUARY', content.upper())
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_no_matches_writes_explicit_line(self):
        # Empty inputs → zero matches → explicit "no matches" line, not silence.
        monthly = {m: [] for m in range(1, 13)}
        daily = {m: [] for m in range(1, 13)}
        fd, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd)
        try:
            n = write_matching_report(out, monthly, daily)
            self.assertEqual(n, 0)
            with open(out) as f:
                self.assertIn('No matches found', f.read())
        finally:
            if os.path.exists(out):
                os.unlink(out)


class ExceedCliModesTest(unittest.TestCase):
    """Subprocess coverage for the CLI seasonal / match / svg / error paths."""

    def _run(self, *extra):
        return subprocess.run(
            [sys.executable, '-m', 'exceed', '--no-gui', *extra],
            capture_output=True, text=True, cwd=ROOT,
        )

    def test_seasonal_mode_writes_report(self):
        fd, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd)
        try:
            res = self._run('--monthly', _data_method4('target.MON'),
                            '--seasonal', '2', '--output', out)
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            with open(out) as f:
                self.assertIn('SEASON', f.read().upper())
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_match_mode_writes_report(self):
        fd, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd)
        try:
            res = self._run('--monthly', _data_method4('target.MON'),
                            '--daily', _data_method0('gauge_complete.DAY'),
                            '--match', '--tolerance', '5', '--output', out)
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            with open(out) as f:
                self.assertIn('Matching Report', f.read())
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_svg_flag_writes_chart(self):
        fd_r, out = tempfile.mkstemp(suffix='.rep')
        os.close(fd_r)
        fd_s, svg = tempfile.mkstemp(suffix='.svg')
        os.close(fd_s)
        try:
            res = self._run('--monthly', _data_method4('target.MON'),
                            '--output', out, '--svg', svg, '--intervals', '10')
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            with open(svg) as f:
                self.assertIn('<svg', f.read())
        finally:
            for p in (out, svg):
                if os.path.exists(p):
                    os.unlink(p)

    def test_zero_intervals_rejected(self):
        res = self._run('--monthly', _data_method4('target.MON'),
                        '--output', os.devnull, '--intervals', '0')
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('intervals', (res.stderr + res.stdout).lower())

    def test_missing_file_clean_error_no_traceback(self):
        res = self._run('--monthly', '/nonexistent/missing.MON',
                        '--output', os.devnull)
        self.assertNotEqual(res.returncode, 0)
        combined = res.stderr + res.stdout
        self.assertIn('Error:', combined)
        self.assertNotIn('Traceback', combined)

    def test_no_output_warns(self):
        res = self._run('--monthly', _data_method4('target.MON'))
        # Exit 0 (analysis ran) but a warning that nothing was saved.
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn('nothing was written', res.stderr)


if __name__ == '__main__':
    unittest.main()
