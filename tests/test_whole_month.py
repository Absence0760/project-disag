"""Tests for the Method-5 whole-month replacement option (DisagConfig).

When ``whole_month_donor_fraction`` is set, a PATCH_EXCEED month whose
file-1 gap share reaches the fraction is rebuilt from ONE coherent source
instead of being spliced source-by-source. The source is chosen by tier
priority: file 1 (a complete file-1 month never trips), else file 2 if it
covers the whole month, else the exceedance-matched donor month.

Stdlib only; ``python3 -m unittest discover tests`` runs these.
"""

import calendar as _cal
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from disag.algorithm import DisagConfig, DisagMethod, disaggregate
from disag.files import DailyRecord, MISSING, read_daily_file, read_monthly_file

DATA = os.path.join(ROOT, 'examples', 'method5_demo', 'data')
HM = (10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9)


def _rec(cy, hm, missing_days=()):
    dim = _cal.monthrange(cy, hm)[1]
    v = [1.0] * dim
    for d in missing_days:
        v[d] = MISSING
    return DailyRecord(year=cy, month=hm, v=v)


def _scenario(n_years=6, start_hy=2000, sparse_june=False):
    """Build gen_monthly + two complete daily files over full hydro years.

    Distinct per-(year, month) volumes give every calendar month a real
    percentile distribution. Callers punch gaps into the target month
    afterwards. With ``sparse_june`` only one June survives in gen_monthly,
    so tier 3 cannot fire for June (no donor pool).
    """
    gen, obs1, obs2 = {}, {}, {}
    for y in range(start_hy, start_hy + n_years):
        for hm in HM:
            cy = y if hm >= 10 else y + 1
            gen[(cy, hm)] = float(hm) + 0.1 * (cy - start_hy)
            obs1[(cy, hm)] = _rec(cy, hm)
            obs2[(cy, hm)] = _rec(cy, hm)
    if sparse_june:
        for key in [k for k in gen if k[1] == 6 and k != (start_hy + 1, 6)]:
            del gen[key]
    return gen, obs1, obs2


def _row(log, cy, hm):
    prefix = f'{cy:4d} {hm:2d}'
    return next((l for l in log if l.startswith(prefix)), None)


def _counts(log, cy, hm):
    """(F1, F2, OTH) day counts from the decision-log row for (cy, hm)."""
    parts = _row(log, cy, hm).split()
    return int(parts[2]), int(parts[3]), int(parts[4])


class DisagConfigValidationTests(unittest.TestCase):
    def test_none_is_valid(self):
        self.assertIsNone(DisagConfig().whole_month_donor_fraction)
        self.assertIsNone(
            DisagConfig(whole_month_donor_fraction=None)
            .whole_month_donor_fraction)

    def test_mid_range_valid(self):
        self.assertEqual(
            DisagConfig(whole_month_donor_fraction=0.5)
            .whole_month_donor_fraction, 0.5)

    def test_upper_bound_inclusive(self):
        # 1.0 is valid — replace only when file 1 is missing the entire month.
        self.assertEqual(
            DisagConfig(whole_month_donor_fraction=1.0)
            .whole_month_donor_fraction, 1.0)

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            DisagConfig(whole_month_donor_fraction=0)

    def test_above_one_rejected(self):
        with self.assertRaises(ValueError):
            DisagConfig(whole_month_donor_fraction=1.5)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            DisagConfig(whole_month_donor_fraction=-0.1)

    def test_non_numeric_rejected(self):
        with self.assertRaises(ValueError):
            DisagConfig(whole_month_donor_fraction='x')

    def test_bool_rejected(self):
        # bool is an int subclass — reject it so True/False can't sneak in
        with self.assertRaises(ValueError):
            DisagConfig(whole_month_donor_fraction=True)


class TriggerIsFile1GapsTests(unittest.TestCase):
    """The trigger measures the fraction of days file 1 is missing.

    With a single daily file there is no file 2, so the only reachable
    whole-month source is the exceedance donor.
    """

    def _run(self, fraction, n_gaps=15):
        gen, obs1, _ = _scenario()
        obs1[(2003, 6)] = _rec(2003, 6, range(n_gaps))
        cfg = DisagConfig(whole_month_donor_fraction=fraction)
        return disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, {}], 1, config=cfg)

    def test_at_threshold_replaces_whole_month_from_donor(self):
        _, log = self._run(0.5)          # 15/30 == 0.5 → trips
        self.assertEqual(_counts(log, 2003, 6), (0, 0, 30))
        row = _row(log, 2003, 6)
        self.assertIn('whole-month donor replacement', row)
        self.assertIn('file 1 missing 15/30 day(s)', row)
        self.assertIn('whole month taken from donor', row)

    def test_just_below_threshold_splices(self):
        _, log = self._run(0.6)          # 15/30 == 0.5 < 0.6 → splice
        self.assertEqual(_counts(log, 2003, 6), (15, 0, 15))
        row = _row(log, 2003, 6)
        self.assertNotIn('whole-month', row)
        self.assertIn('patched from donor', row)

    def test_measure_is_file1_gap_fraction(self):
        _, log = self._run(10 / 30, n_gaps=10)   # 10/30 file-1 gaps
        self.assertIn('file 1 missing 10/30 day(s)', _row(log, 2003, 6))
        self.assertEqual(_counts(log, 2003, 6), (0, 0, 30))


class WholeMonthSourcePriorityTests(unittest.TestCase):
    """Source priority when the trigger fires: file 1 → file 2 → exceedance.

    A complete file 1 has no gaps and never trips, so the reachable order
    is file 2 (if it covers every day) then the exceedance donor.
    """

    def test_file2_complete_wins_over_donor(self):
        gen, obs1, obs2 = _scenario()
        obs1[(2003, 6)] = _rec(2003, 6, range(20))   # 20/30 file-1 gaps → trips
        # obs2[(2003, 6)] stays complete → whole month taken from file 2.
        cfg = DisagConfig(whole_month_donor_fraction=0.5)
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2, config=cfg)
        self.assertEqual(_counts(log, 2003, 6), (0, 30, 0))
        row = _row(log, 2003, 6)
        self.assertIn('whole-month file-2 replacement', row)
        self.assertIn('file 1 missing 20/30 day(s)', row)
        self.assertIn('whole month taken from file 2 2003  6', row)

    def test_file2_incomplete_falls_through_to_donor(self):
        gen, obs1, obs2 = _scenario()
        obs1[(2003, 6)] = _rec(2003, 6, range(20))   # 20/30 file-1 gaps → trips
        obs2[(2003, 6)] = _rec(2003, 6, [25])        # file 2 short one day → not whole
        cfg = DisagConfig(whole_month_donor_fraction=0.5)
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2, config=cfg)
        self.assertEqual(_counts(log, 2003, 6), (0, 0, 30))
        row = _row(log, 2003, 6)
        self.assertIn('whole-month donor replacement', row)
        self.assertIn('whole month taken from donor', row)

    def test_below_threshold_splices_three_ways(self):
        gen, obs1, obs2 = _scenario()
        # File 1 missing 0-11 (12/30 gaps); file 2 covers 0-5 but not 6-11 →
        # both-missing 6-11 (donor). 12/30 < 0.5, so no whole-month.
        obs1[(2003, 6)] = _rec(2003, 6, range(12))
        obs2[(2003, 6)] = _rec(2003, 6, range(6, 12))
        cfg = DisagConfig(whole_month_donor_fraction=0.5)
        _, log = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, obs2], 2, config=cfg)
        # days 12-29 file 1 (18); days 0-5 file 2 (6); days 6-11 donor (6)
        self.assertEqual(_counts(log, 2003, 6), (18, 6, 6))
        self.assertNotIn('whole-month', _row(log, 2003, 6))


class DegradeToSpliceTests(unittest.TestCase):
    """Enabling the option must never make a month worse than the default."""

    def test_no_donor_available_matches_splice(self):
        # June is sparse in gen_monthly → tier 3 cannot fire for June.
        gen, obs1, _ = _scenario(sparse_june=True)
        # The one surviving June (2001) is the gappy target.
        obs1[(2001, 6)] = _rec(2001, 6, range(20))   # 20/30 gaps → trips 0.5

        recs_splice, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, {}], 1)
        cfg = DisagConfig(whole_month_donor_fraction=0.5)
        recs_whole, _ = disaggregate(
            DisagMethod.PATCH_EXCEED, gen, [obs1, {}], 1, config=cfg)

        # Same month is missing in both modes — degrade, not a worse outcome.
        june_splice = next(r for r in recs_splice if (r.year, r.month) == (2001, 6))
        june_whole = next(r for r in recs_whole if (r.year, r.month) == (2001, 6))
        self.assertTrue(all(v == MISSING for v in june_splice.v))
        self.assertEqual(june_whole.v, june_splice.v)
        # Overall missing count is not increased by enabling the option.
        miss_splice = sum(1 for r in recs_splice if all(v == MISSING for v in r.v))
        miss_whole = sum(1 for r in recs_whole if all(v == MISSING for v in r.v))
        self.assertEqual(miss_whole, miss_splice)

    def test_donor_incomplete_over_whole_month_falls_back_to_splice(self):
        # Neither file 2 (absent) nor a complete donor exists: the donor covers
        # every *needed* day but is missing a day the target has real data for,
        # so no single source spans the month. It must splice (keep real days,
        # donor the gaps), not blow the whole month away as MISSING.
        gen, obs1, _ = _scenario()
        obs1[(2003, 6)] = _rec(2003, 6, range(20))     # 20/30 gaps → 0.5 trips
        obs1[(2004, 6)] = _rec(2004, 6, [20])          # donor short on day 20
        cfg = DisagConfig(whole_month_donor_fraction=0.5)
        with patch('disag.algorithm.find_exceed_donor',
                   return_value=(0, 2004, 66.7, 62.5)):
            recs, log = disaggregate(
                DisagMethod.PATCH_EXCEED, gen, [obs1, {}], 1, config=cfg)
        june = next(r for r in recs if (r.year, r.month) == (2003, 6))
        self.assertFalse(all(v == MISSING for v in june.v))
        self.assertEqual(_counts(log, 2003, 6), (10, 0, 20))  # spliced, not 0/0/30
        self.assertIn('patched from donor', _row(log, 2003, 6))
        self.assertNotIn('whole-month', _row(log, 2003, 6))


class RegressionTests(unittest.TestCase):
    """Default config leaves existing PATCH_EXCEED output byte-for-byte unchanged."""

    def _demo(self, config):
        gen = read_monthly_file(os.path.join(DATA, 'target.MON'))
        obs = [
            read_daily_file(os.path.join(DATA, 'gauge_a_with_gaps.DAY')),
            read_daily_file(os.path.join(DATA, 'gauge_b_partial.DAY')),
        ]
        return disaggregate(DisagMethod.PATCH_EXCEED, gen, obs, 2, config=config)

    def test_none_config_matches_omitting_config(self):
        base_recs, base_log = self._demo(None)
        for cfg in (None, DisagConfig(), DisagConfig(whole_month_donor_fraction=None)):
            recs, log = self._demo(cfg)
            self.assertEqual(log, base_log)
            self.assertEqual([r.v for r in recs], [r.v for r in base_recs])


if __name__ == '__main__':
    unittest.main()
