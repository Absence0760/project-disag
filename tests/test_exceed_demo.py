"""End-to-end tests for the exceed demo in examples/exceed_demo/.

Each mode (Basic / Seasonal / Matching) is asserted to behave exactly
as its README claims, against the deterministic committed mock data.
The demo is the user-facing walkthrough of the exceed tool, so this
file is also where we catch drift between the README and the actual
algorithm output.

Stdlib only.
"""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from exceed.algorithm import (
    SEASON_PRESETS,
    calculate_monthly_exceedance,
    calculate_seasonal_exceedance,
    match_exceedance_values,
)
from exceed.files import read_daily_file, read_monthly_file


DEMO_DIR = os.path.join(ROOT, 'examples', 'exceed_demo')
DATA = os.path.join(DEMO_DIR, 'data')


# Expected per-calendar-month sample sizes for the daily file.
# 10 hydro years (Oct 2000 – Sep 2010) means each calendar Jan/Mar/May/
# Jul/Aug/Oct/Dec contributes 31 days × 10 = 310; Apr/Jun/Sep/Nov give
# 30 × 10 = 300; Feb gives 28 × 8 + 29 × 2 = 282 (cal Feb 2004 and 2008
# are leap years inside the window).
EXPECTED_DAILY_COUNTS = {
    1: 310, 2: 282, 3: 310, 4: 300, 5: 310, 6: 300,
    7: 310, 8: 310, 9: 300, 10: 310, 11: 300, 12: 310,
}


class BasicModeTests(unittest.TestCase):
    """Mode 1: per-calendar-month exceedance via the exceed CLI."""

    def test_per_month_value_counts(self):
        monthly = read_monthly_file(os.path.join(DATA, 'target.MON'))
        daily = read_daily_file(os.path.join(DATA, 'gauge.DAY'))
        for m in range(1, 13):
            self.assertEqual(
                len(monthly[m]), 10,
                f'cal month {m} should have 10 monthly values, '
                f'got {len(monthly[m])}',
            )
            self.assertEqual(
                len(daily[m]), EXPECTED_DAILY_COUNTS[m],
                f'cal month {m} daily count drifted from demo README',
            )

    def test_cli_writes_basic_report(self):
        # Drive the same command the README documents; assert the .rep
        # file contains the expected MONTHLY/DAILY sections.
        with tempfile.TemporaryDirectory() as tmp:
            rep = os.path.join(tmp, 'out.rep')
            result = subprocess.run(
                [sys.executable, '-m', 'exceed', '--no-gui',
                 '--monthly', os.path.join(DATA, 'target.MON'),
                 '--daily',   os.path.join(DATA, 'gauge.DAY'),
                 '--output',  rep,
                 '--intervals', '20'],
                cwd=ROOT,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(rep) as f:
                body = f.read()
        # 12 monthly sections + 12 daily sections
        for name in ('JANUARY', 'JUNE', 'DECEMBER'):
            self.assertIn(f'MONTHLY - {name}', body)
            self.assertIn(f'DAILY - {name}', body)
        # 20 interval rows means 20 percentage values per section
        self.assertGreater(body.count('Exceedance%'), 23)


class SeasonalModeTests(unittest.TestCase):
    """Mode 2: seasonal grouping uses calculate_seasonal_exceedance."""

    def setUp(self):
        self.monthly = read_monthly_file(os.path.join(DATA, 'target.MON'))
        self.daily = read_daily_file(os.path.join(DATA, 'gauge.DAY'))

    def test_4season_monthly_totals(self):
        results = calculate_seasonal_exceedance(
            self.monthly, SEASON_PRESETS[4], num_intervals=20,
        )
        # Every 4-season bucket has 3 months × 10 hydro years = 30 values.
        for season in ('Winter', 'Spring', 'Summer', 'Fall'):
            self.assertEqual(
                results[season].total_count, 30,
                f'4-season {season} monthly total drifted',
            )

    def test_2season_monthly_totals(self):
        results = calculate_seasonal_exceedance(
            self.monthly, SEASON_PRESETS[2], num_intervals=20,
        )
        # Wet/Dry: each is 6 months × 10 hydro years = 60 values.
        for season in ('Wet Season', 'Dry Season'):
            self.assertEqual(results[season].total_count, 60)

    def test_3season_monthly_totals(self):
        results = calculate_seasonal_exceedance(
            self.monthly, SEASON_PRESETS[3], num_intervals=20,
        )
        # Summer + Fall = 3 months × 10 years; Winter = 6 months × 10 years.
        self.assertEqual(results['Summer'].total_count, 30)
        self.assertEqual(results['Fall'].total_count, 30)
        self.assertEqual(results['Winter'].total_count, 60)

    def test_4season_daily_totals(self):
        results = calculate_seasonal_exceedance(
            self.daily, SEASON_PRESETS[4], num_intervals=20,
        )
        # Winter: Dec(310) + Jan(310) + Feb(282) = 902.
        # Spring: Mar(310) + Apr(300) + May(310) = 920.
        # Summer: Jun(300) + Jul(310) + Aug(310) = 920.
        # Fall:   Sep(300) + Oct(310) + Nov(300) = 910.
        self.assertEqual(results['Winter'].total_count, 902)
        self.assertEqual(results['Spring'].total_count, 920)
        self.assertEqual(results['Summer'].total_count, 920)
        self.assertEqual(results['Fall'].total_count, 910)

    def test_seasonal_driver_script_runs(self):
        # Smoke-test the demo's seasonal.py driver — README documents it.
        result = subprocess.run(
            [sys.executable, os.path.join(DEMO_DIR, 'seasonal.py'),
             '--seasons', '4', '--source', 'monthly'],
            cwd=ROOT,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for season in ('WINTER', 'SPRING', 'SUMMER', 'FALL'):
            self.assertIn(season, result.stdout)
        self.assertIn('Total values: 30', result.stdout)


class MatchingModeTests(unittest.TestCase):
    """Mode 3: monthly↔daily matching."""

    def test_january_matches_within_default_tolerance(self):
        monthly = read_monthly_file(os.path.join(DATA, 'target.MON'))
        daily = read_daily_file(os.path.join(DATA, 'gauge.DAY'))
        m_result = calculate_monthly_exceedance(monthly[1], 20)
        d_result = calculate_monthly_exceedance(daily[1], 20)
        matches = match_exceedance_values(
            m_result, d_result, tolerance_pct=5.0,
        )
        # With a 5pp tolerance every monthly point should have a daily
        # neighbour: monthly has only 10 values so its curve is at
        # 10pp resolution, daily has 310 values.
        self.assertEqual(len(matches), 20)
        # Δexceed never exceeds the tolerance.
        for m in matches:
            self.assertLessEqual(m['diff'], 5.0)

    def test_zero_tolerance_yields_few_matches(self):
        monthly = read_monthly_file(os.path.join(DATA, 'target.MON'))
        daily = read_daily_file(os.path.join(DATA, 'gauge.DAY'))
        m_result = calculate_monthly_exceedance(monthly[1], 20)
        d_result = calculate_monthly_exceedance(daily[1], 20)
        matches = match_exceedance_values(
            m_result, d_result, tolerance_pct=0.0,
        )
        # 0-pp tolerance: only matches where Δexceed is exactly 0.
        # Every monthly exceedance % is a multiple of 10 (10/20 = 50%
        # → percentages quantise on 5%); the daily curve hits some of
        # these exactly, others slightly off.
        for m in matches:
            self.assertAlmostEqual(m['diff'], 0.0, places=6)

    def test_matching_driver_script_runs(self):
        result = subprocess.run(
            [sys.executable, os.path.join(DEMO_DIR, 'matching.py'),
             '--month', '1', '--tolerance', '5'],
            cwd=ROOT,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Matching — January', result.stdout)
        self.assertIn('Monthly values: 10', result.stdout)
        self.assertIn(f'Daily values: {EXPECTED_DAILY_COUNTS[1]}',
                      result.stdout)


if __name__ == '__main__':
    unittest.main()
