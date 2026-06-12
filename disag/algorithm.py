"""
Core disaggregation algorithm.

Converts monthly flows (Mm3/month) to daily flows (m3/s) using one of six
methods that borrow a daily shape from an observed daily record.

Formula
-------
    Qgen_daily[d] = Qgen_monthly * (Qobs_daily[d] / sum(Qobs_daily)) * 1e6/86400

Unit conversion at the end: Mm3/day → m3/s  (×1e6 / 86400)
"""

# Lazy annotation evaluation (PEP 563) so PEP 585 generic-builtin
# annotations like tuple[int, int] work on Python 3.8.
from __future__ import annotations

import calendar
from enum import IntEnum
from typing import Optional

from .files import DailyRecord, MISSING


# ---------------------------------------------------------------------------
# Method enum
# ---------------------------------------------------------------------------

class DisagMethod(IntEnum):
    ONE_FILE     = 0   # Disaggregate with daily file 1
    PATCH_CAL    = 1   # Use file 1; patch missing days from a similar calendar month
    PATCH_FILE   = 2   # Use file 1; patch missing days from file 2
    INCREMENTAL  = 3   # Pattern = (daily 1) − (daily 2)
    EVEN         = 4   # Even distribution (no daily file needed)
    PATCH_EXCEED = 5   # File 1 → file 2 → exceedance-matched donor month


METHOD_LABELS = {
    DisagMethod.ONE_FILE:     'Disaggregate with daily file 1',
    DisagMethod.PATCH_CAL:    'Disaggregate with daily file 1, patch with flows from similar month',
    DisagMethod.PATCH_FILE:   'Disaggregate with daily file 1, patch with daily file 2',
    DisagMethod.INCREMENTAL:  'Incremental catchment: disaggregate with (daily 1 − daily 2)',
    DisagMethod.EVEN:         'Use even distribution',
    DisagMethod.PATCH_EXCEED: 'Disaggregate with file 1, patch with file 2, then exceedance-matched donor',
}

METHOD_NAMES = {
    DisagMethod.ONE_FILE:     'One disaggregator',
    DisagMethod.PATCH_CAL:    'Distrib with file 1, Patched with similar month',
    DisagMethod.PATCH_FILE:   'Distrib with file 1, Patched with file 2',
    DisagMethod.INCREMENTAL:  'Distrib with incremental runoff (file 1 − file 2)',
    DisagMethod.EVEN:         'Even distribution',
    DisagMethod.PATCH_EXCEED: 'Distrib with file 1, file 2, then exceedance-matched donor',
}

# Minimum number of daily input files required by each method.
# PATCH_EXCEED accepts 1 or 2: file 2 is optional and, if supplied, is used
# both for tier-2 day-level patching and as a tier-3 donor pool source.
NO_FILES = {
    DisagMethod.ONE_FILE:     1,
    DisagMethod.PATCH_CAL:    1,
    DisagMethod.PATCH_FILE:   2,
    DisagMethod.INCREMENTAL:  2,
    DisagMethod.EVEN:         0,
    DisagMethod.PATCH_EXCEED: 1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_coverage(records: list) -> tuple[int, int]:
    """Return (disaggregated_count, missing_count) for a list of DailyRecord.

    A month counts as disaggregated only if every day has a non-negative
    value — the algorithm marks months all-or-nothing missing.
    """
    disagg = sum(1 for r in records if all(v >= 0 for v in r.v))
    return disagg, len(records) - disagg


def _inc_month(year: int, month: int) -> tuple:
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


def _hydro_start_ym(records: dict) -> tuple:
    """
    Return the (year, 10) hydro-year start for a daily file.

    If the file starts in November or December the first *complete* hydro year
    begins in October of the following calendar year.
    """
    if not records:
        return (9999, 10)
    year, month = min(records.keys())
    if month > 10:
        year += 1
    return year, 10


def find_patch_year(
    target_year: int,
    target_month: int,
    gen_monthly: dict,
    obs_daily: dict,
) -> Optional[int]:
    """Find the calendar year whose monthly volume is closest to the target month
    and whose daily record is complete (no missing days).

    Returns the year, or None if no suitable year exists.
    """
    target_vol = gen_monthly.get((target_year, target_month))
    if target_vol is None or target_vol < 0:
        return None

    best_year: Optional[int] = None
    best_diff = float('inf')

    for (y, m), vol in gen_monthly.items():
        if m != target_month or y == target_year or vol < 0:
            continue
        diff = abs(vol - target_vol)
        if diff >= best_diff:
            continue
        rec = obs_daily.get((y, m))
        if rec is None:
            continue
        dim = calendar.monthrange(y, m)[1]
        if all(rec.v[d] >= 0 for d in range(dim)):
            best_year = y
            best_diff = diff

    return best_year


def _monthly_totals_from_daily(obs: dict) -> dict:
    """Sum each daily-file month's values into a single monthly volume.

    Only months with a complete daily record (no value < 0) are included.
    Returned units are the raw m3/s sum — units don't matter for percentile
    matching since each file is ranked within its own distribution.
    """
    totals: dict = {}
    for (y, m), rec in obs.items():
        if rec is None:
            continue
        dim = calendar.monthrange(y, m)[1]
        if len(rec.v) < dim:
            continue
        if any(rec.v[d] < 0 for d in range(dim)):
            continue
        totals[(y, m)] = sum(rec.v[:dim])
    return totals


def _exceed_pct(value: float, distribution: list) -> float:
    """Exceedance percentile: 100 × (count of values >= `value`) / n.

    100 % means `value` is the smallest in the distribution; 0 % means it
    is strictly larger than every entry.
    """
    n = len(distribution)
    if n == 0:
        return 0.0
    return 100.0 * sum(1 for v in distribution if v >= value) / n


def _tier2_scale_factors(obs_totals: list) -> list:
    """Return the multiplier to apply to each daily file's day values when
    they are used for tier-2 patching under PATCH_EXCEED, so a file-2
    day plugged into a file-1 month doesn't carry file-2's absolute
    scale into qD.

    Returns ``factors`` such that ``factors[file_idx][m]`` is the
    file-1-relative scaling for calendar month ``m``.  ``factors[0][m]``
    is always 1.0.

    For ``file_idx >= 1`` the factor is
    ``mean(file_1[m]) / mean(file_idx[m])`` using each file's complete
    monthly totals for that calendar month.  Falls back to the
    annual-mean ratio if a calendar month has no overlapping data, then
    to 1.0 (i.e. no rescale) if even that's unavailable.
    """
    if not obs_totals:
        return []

    months = range(1, 13)
    per_month_means: list = []
    overall_means: list = []
    for totals in obs_totals:
        means: dict = {}
        all_vals: list = []
        for m in months:
            vals = [v for (y, mm), v in totals.items() if mm == m]
            if vals:
                means[m] = sum(vals) / len(vals)
            all_vals.extend(vals)
        per_month_means.append(means)
        overall_means.append(
            sum(all_vals) / len(all_vals) if all_vals else None
        )

    factors: list = [{m: 1.0 for m in months}]
    for file_idx in range(1, len(obs_totals)):
        f: dict = {}
        for m in months:
            t1 = per_month_means[0].get(m)
            ti = per_month_means[file_idx].get(m)
            if t1 is not None and ti is not None and ti > 0:
                f[m] = t1 / ti
            elif (overall_means[0] is not None
                  and overall_means[file_idx] is not None
                  and overall_means[file_idx] > 0):
                f[m] = overall_means[0] / overall_means[file_idx]
            else:
                f[m] = 1.0
        factors.append(f)
    return factors


def _per_month_distributions(
    gen_monthly: dict,
    obs_totals: list,
) -> tuple:
    """Precompute per-calendar-month distributions used by
    ``find_exceed_donor``.

    Returns ``(target_dists, donor_dists)`` where:
      * ``target_dists[m]`` is the list of valid ``gen_monthly`` values
        for calendar month ``m``;
      * ``donor_dists[file_idx][m]`` is the list of complete-month
        totals for the same calendar month in daily file ``file_idx``.
    """
    target_dists: dict = {m: [] for m in range(1, 13)}
    for (y, m), v in gen_monthly.items():
        if v >= 0:
            target_dists[m].append(v)

    donor_dists: list = []
    for totals in obs_totals:
        per_month: dict = {m: [] for m in range(1, 13)}
        for (y, m), v in totals.items():
            per_month[m].append(v)
        donor_dists.append(per_month)

    return target_dists, donor_dists


def find_exceed_donor(
    target_year: int,
    target_month: int,
    gen_monthly: dict,
    obs_totals: list,       # list of {(y, m): vol} dicts, one per daily file
    target_dists: Optional[dict] = None,
    donor_dists: Optional[list] = None,
) -> Optional[tuple]:
    """Find an exceedance-matched donor month for PATCH_EXCEED tier 3.

    Picks the (file_idx, donor_year) whose monthly volume sits at the
    closest exceedance percentile to the target's, within its own daily
    file's per-calendar-month distribution. Ties broken by year proximity
    to ``target_year``, then by smaller file index.

    The target's own ``(target_year, target_month)`` is excluded from
    the candidate pool defensively — by construction it shouldn't be in
    ``obs_totals`` (tier 3 only fires when the target month is
    incomplete), but the explicit guard makes the intent obvious.

    Pass ``target_dists``/``donor_dists`` (from ``_per_month_distributions``)
    to skip the per-call list building when ``find_exceed_donor`` is
    invoked many times during a single ``disaggregate`` run.

    Returns ``(file_idx, donor_year, p_target, p_donor)`` or ``None`` if
    no eligible donor exists.
    """
    target_vol = gen_monthly.get((target_year, target_month))
    if target_vol is None or target_vol < 0:
        return None

    if target_dists is None or donor_dists is None:
        target_dists, donor_dists = _per_month_distributions(
            gen_monthly, obs_totals
        )

    target_dist = target_dists.get(target_month, [])
    if len(target_dist) < 2:
        return None
    p_target = _exceed_pct(target_vol, target_dist)

    target_dim = calendar.monthrange(target_year, target_month)[1]

    best_key: Optional[tuple] = None
    best_p_donor: float = 0.0

    for file_idx, totals in enumerate(obs_totals):
        if not totals:
            continue
        donor_dist = donor_dists[file_idx].get(target_month, [])
        if len(donor_dist) < 2:
            continue
        for (y, m), vol in totals.items():
            if m != target_month:
                continue
            # Defensive: the target itself shouldn't be in the donor pool
            if (y, m) == (target_year, target_month):
                continue
            # Skip donors with mismatched month length (Feb leap-year mismatch)
            if calendar.monthrange(y, m)[1] != target_dim:
                continue
            p_donor = _exceed_pct(vol, donor_dist)
            key = (abs(p_donor - p_target), abs(y - target_year), file_idx, y)
            if best_key is None or key < best_key:
                best_key = key
                best_p_donor = p_donor

    if best_key is None:
        return None
    _, _, file_idx, year = best_key
    return (file_idx, year, p_target, best_p_donor)


# ---------------------------------------------------------------------------
# Per-month conversion
# ---------------------------------------------------------------------------

def _convert_month(
    year: int,
    month: int,
    method: DisagMethod,
    gen_monthly: dict,
    obs_daily: list,        # obs_daily[0] = file-1 dict, obs_daily[1] = file-2 dict
    start_obs_2: tuple,     # (year, month) when file-2 data begins
    decisions: dict,        # (year, month) -> per-month decision row, all methods
    obs_totals: Optional[list] = None,   # precomputed monthly totals per file
    target_dists: Optional[dict] = None,
    donor_dists: Optional[list] = None,
    tier2_scale: Optional[list] = None,
    tier_counters: Optional[dict] = None,
) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]

    # Register one decision row per iterated month, for *every* method, so the
    # report is a complete per-month audit trail. F1/F2/OTH count the days
    # sourced from daily file 1, daily file 2, and a patched / donor / even
    # source respectively; `note` records the result and the reason for it.
    dec = {'f1': 0, 'f2': 0, 'oth': 0, 'note': ''}
    decisions[(year, month)] = dec

    # --- Monthly generated value (Mm3/month) ---
    gen_val = gen_monthly.get((year, month))
    if gen_val is None or gen_val < 0:
        dec['note'] = 'MISSING — monthly value missing or negative'
        return DailyRecord(year=year, month=month, v=[MISSING] * dim)

    # --- Fetch observed daily records ---
    rec1 = obs_daily[0].get((year, month)) if obs_daily else None

    # File-2 is consulted by methods that combine two daily files. It is only
    # active once file-2's own data starts (so the report doesn't claim a
    # patch from a record that doesn't exist yet).
    use_file2 = (
        method in (
            DisagMethod.PATCH_FILE,
            DisagMethod.INCREMENTAL,
            DisagMethod.PATCH_EXCEED,
        )
        and len(obs_daily) > 1
        and (year, month) >= start_obs_2
    )
    rec2 = obs_daily[1].get((year, month)) if use_file2 else None

    # --- Missing-data check / donor selection ---
    # On the missing and patched branches we set ``dec['note']`` to the reason
    # here; the routine ones (plain file-1 disaggregation, tier-2 fills) are
    # finalised after the qD loop once the per-source day counts are known.
    missing = False
    patch_year: Optional[int] = None
    exceed_donor: Optional[DailyRecord] = None
    exceed_donor_file_idx: int = 0

    if method == DisagMethod.EVEN:
        pass  # never missing

    elif method == DisagMethod.ONE_FILE:
        if rec1 is None or any(rec1.v[d] < 0 for d in range(dim)):
            missing = True
            dec['note'] = 'MISSING — no complete daily record in file 1'

    elif method == DisagMethod.INCREMENTAL:
        if rec1 is None or rec2 is None:
            missing = True
            dec['note'] = 'MISSING — file 1 or file 2 unavailable this month'
        elif any(rec1.v[d] < 0 or rec2.v[d] < 0 for d in range(dim)):
            missing = True
            dec['note'] = 'MISSING — file 1 or file 2 has a missing day'

    elif method == DisagMethod.PATCH_FILE:
        # Missing only if the same day is absent from BOTH files
        for d in range(dim):
            f1 = rec1.v[d] if rec1 else -999.0
            f2 = rec2.v[d] if rec2 else -999.0
            if f1 < 0 and f2 < 0:
                missing = True
                dec['note'] = 'MISSING — day absent from both file 1 and file 2'
                break

    elif method == DisagMethod.PATCH_CAL:
        # If any day is missing, try to borrow a complete month from another year
        needs_patch = rec1 is None or any(rec1.v[d] < 0 for d in range(dim))
        if needs_patch:
            patch_year = find_patch_year(year, month, gen_monthly, obs_daily[0])
            if patch_year is not None:
                dec['note'] = (
                    f'patched from similar calendar month {patch_year:4d}{month:3d}'
                )
            else:
                missing = True
                dec['note'] = 'MISSING — file-1 gap, no complete similar month'

    elif method == DisagMethod.PATCH_EXCEED:
        # Tier 1+2: any day missing in BOTH files triggers tier 3.
        # Collect the day indices that need a donor so we can validate
        # the donor's coverage at those positions below — find_exceed_donor
        # picks by monthly-volume percentile and doesn't check day-level
        # completeness, so a donor month could itself be short or have
        # gaps on the exact days we need.
        needs_donor_days = []
        for d in range(dim):
            f1 = rec1.v[d] if rec1 and d < len(rec1.v) else -999.0
            f2 = rec2.v[d] if rec2 and d < len(rec2.v) else -999.0
            if f1 < 0 and f2 < 0:
                needs_donor_days.append(d)

        if needs_donor_days:
            donor = find_exceed_donor(
                year, month, gen_monthly, obs_totals or [],
                target_dists=target_dists, donor_dists=donor_dists,
            )
            if donor is None:
                dec['note'] = 'MISSING — no exceedance donor available'
                missing = True
            else:
                file_idx, donor_year, p_target, p_donor = donor
                exceed_donor = obs_daily[file_idx].get((donor_year, month))
                exceed_donor_file_idx = file_idx
                if exceed_donor is None:
                    dec['note'] = 'MISSING — exceedance donor record vanished'
                    missing = True
                else:
                    # Validate the donor covers every still-missing day with
                    # a non-missing value. Without this check, a short donor
                    # record (truncated file) or a donor month with its own
                    # gaps would silently fall through to `val = -999.0` in
                    # the qD loop, get clamped to 0, and emit synthetic
                    # zero-flow days no audit line ever announced.
                    bad = [
                        d for d in needs_donor_days
                        if d >= len(exceed_donor.v) or exceed_donor.v[d] < 0
                    ]
                    if bad:
                        dec['note'] = (
                            f'MISSING — donor file {file_idx + 1}'
                            f' {donor_year:4d}{month:3d}'
                            f' missing day(s) {",".join(str(d + 1) for d in bad)}'
                        )
                        missing = True
                    else:
                        dec['note'] = (
                            f'patched from donor: file {file_idx + 1}'
                            f' {donor_year:4d}{month:3d}'
                            f' (exceed% target={p_target:.1f} donor={p_donor:.1f})'
                        )
                        if tier_counters is not None:
                            tier_counters['tier3_matches'].append(
                                (year, month, p_target, p_donor,
                                 file_idx, donor_year)
                            )

    if missing:
        return DailyRecord(year=year, month=month, v=[MISSING] * dim)

    # --- Build daily pattern qD[] (counting each day's source into dec) ---
    if method == DisagMethod.EVEN:
        qD = [1.0] * dim
        qM = float(dim)
    else:
        qD = []
        for d in range(dim):
            f1 = rec1.v[d] if rec1 and d < len(rec1.v) else -999.0
            f2 = rec2.v[d] if rec2 and d < len(rec2.v) else -999.0

            if method == DisagMethod.ONE_FILE:
                val = f1
                dec['f1'] += 1

            elif method == DisagMethod.INCREMENTAL:
                val = f1 - f2
                dec['f1'] += 1

            elif method == DisagMethod.PATCH_FILE:
                if f1 < 0:
                    val = f2
                    dec['f2'] += 1
                else:
                    val = f1
                    dec['f1'] += 1

            elif method == DisagMethod.PATCH_CAL:
                if f1 < 0 and patch_year is not None:
                    rec_patch = obs_daily[0].get((patch_year, month))
                    f3 = rec_patch.v[d] if rec_patch and d < len(rec_patch.v) else -999.0
                    val = f3
                    dec['oth'] += 1
                else:
                    val = f1
                    dec['f1'] += 1

            elif method == DisagMethod.PATCH_EXCEED:
                if f1 >= 0:
                    val = f1
                    dec['f1'] += 1
                    if tier_counters is not None:
                        tier_counters['tier1_days'] += 1
                elif f2 >= 0:
                    # Rescale file-2 day to file-1's per-month scale so a
                    # mixed file-1/file-2 month doesn't get a distorted shape
                    # when the two gauges sit on different rivers.
                    scale = (
                        tier2_scale[1].get(month, 1.0)
                        if tier2_scale and len(tier2_scale) > 1 else 1.0
                    )
                    val = f2 * scale
                    dec['f2'] += 1
                    if tier_counters is not None:
                        tier_counters['tier2_days'] += 1
                        tier_counters['tier2_months'].add((year, month))
                elif exceed_donor is not None and d < len(exceed_donor.v):
                    # Same cross-river rescale as tier 2: when the donor
                    # comes from file 2, its day values must be brought
                    # up to file-1's scale before they enter qD, otherwise
                    # a mixed tier-1 / tier-3 month gets a distorted shape.
                    # For whole-month tier-3 fills the scale is constant
                    # across days so it cancels in the disag formula's
                    # ratio — applying it unconditionally is safe.
                    donor_scale = (
                        tier2_scale[exceed_donor_file_idx].get(month, 1.0)
                        if (tier2_scale
                            and exceed_donor_file_idx < len(tier2_scale))
                        else 1.0
                    )
                    val = exceed_donor.v[d] * donor_scale
                    dec['oth'] += 1
                    if tier_counters is not None:
                        tier_counters['tier3_days'] += 1
                        tier_counters['tier3_months'].add((year, month))
                else:
                    val = -999.0

            else:
                val = f1

            qD.append(max(val, 0.0))   # clamp negatives to zero

        qM = sum(qD)

    # --- Handle zero observed monthly total ---
    zero_fill = False
    if qM <= 0 and gen_val > 0:
        zero_fill = True
        qD = [1.0] * dim
        qM = float(dim)

    # --- Finalise the routine decision notes (missing / patched already set) ---
    if dec['note'] == '':
        if method == DisagMethod.EVEN:
            dec['note'] = 'even distribution'
        elif method == DisagMethod.INCREMENTAL:
            dec['note'] = 'disaggregated from file 1 − file 2'
        elif dec['f2'] > 0:
            if dec['f1'] == 0:
                dec['note'] = 'disaggregated from file 2 (file 1 fully missing)'
            else:
                dec['note'] = 'disaggregated from file 1, gaps filled from file 2'
        else:
            dec['note'] = 'disaggregated from file 1'
    if zero_fill:
        dec['note'] += ' (Observed monthly flow <= 0 — even fill)'

    # --- Disaggregate ---
    values = []
    for d in range(dim):
        q = gen_val * qD[d] / qM if qM > 0 else 0.0   # Mm3/day
        values.append(q * 1e6 / 86400)                  # Mm3/day → m3/s

    return DailyRecord(year=year, month=month, v=values)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def disaggregate(
    method: DisagMethod,
    gen_monthly: dict,      # {(year, month): float}  Mm3/month
    obs_daily: list,        # list of dicts {(year, month): DailyRecord}
    no_files: int,
) -> tuple:
    """
    Disaggregate monthly flows to daily flows.

    Parameters
    ----------
    method      : DisagMethod
    gen_monthly : {(year, month): Mm3/month value}
    obs_daily   : list of dicts; obs_daily[0] = file 1, obs_daily[1] = file 2
    no_files    : number of daily files actually supplied (0, 1, or 2)

    Returns
    -------
    (records: list[DailyRecord], report_lines: list[str])
    """
    if not gen_monthly:
        raise ValueError('Monthly input file is empty or could not be read.')

    # --- Determine processing window ---
    # Run window = full span of gen_monthly for every method.  Months
    # outside the daily file's coverage are emitted in the output anyway:
    #   - Method 5 (PATCH_EXCEED) backfills them via tier-3 donor matching;
    #   - Methods 1, 2 may opportunistically patch from a same-calendar
    #     month (Method 1) or from file 2 (Method 2) where their existing
    #     logic can succeed;
    #   - Methods 0, 3 emit -99.99 sentinels for those months.
    # Output length is therefore always equal to gen_monthly's hydro span,
    # so the .day file is self-describing — no silently-clipped months.

    # Hydro-year start for each daily file (used only by per-month logic
    # below, e.g. start_obs_2 for tier-2 / PATCH_FILE day-level patching).
    obs_starts = [_hydro_start_ym(obs_daily[f]) for f in range(no_files)]

    # Monthly file start: first hydro year (always October).
    first_mon = min(gen_monthly.keys())
    hydro_year = first_mon[0] if first_mon[1] >= 10 else first_mon[0] - 1
    monthly_start = (hydro_year, 10)

    start_ym = monthly_start
    end_ym = max(gen_monthly.keys())

    # Start date for file-2 (PATCH_FILE: use file 1 only before this)
    start_obs_2 = obs_starts[1] if no_files >= 2 else (9999, 12)

    # --- Precompute per-file monthly totals for PATCH_EXCEED tier 3 ---
    obs_totals: list = []
    target_dists: Optional[dict] = None
    donor_dists: Optional[list] = None
    tier2_scale: Optional[list] = None
    tier_counters: Optional[dict] = None
    report_lines: list = []
    if method == DisagMethod.PATCH_EXCEED:
        obs_totals = [_monthly_totals_from_daily(obs_daily[f])
                      for f in range(len(obs_daily))]
        target_dists, donor_dists = _per_month_distributions(
            gen_monthly, obs_totals
        )
        tier2_scale = _tier2_scale_factors(obs_totals)
        tier_counters = {
            'tier1_days': 0,
            'tier2_days': 0,
            'tier2_months': set(),
            'tier3_days': 0,
            'tier3_months': set(),
            # One (year, month, p_target, p_donor, file_idx, donor_year)
            # tuple per month actually patched from a donor — feeds the
            # tier-3 donor match-quality summary.
            'tier3_matches': [],
        }

    # --- Period-of-record header (every method) ---
    n_months = ((end_ym[0] - start_ym[0]) * 12
                + (end_ym[1] - start_ym[1]) + 1)
    start_hy = start_ym[0] if start_ym[1] >= 10 else start_ym[0] - 1
    end_hy = end_ym[0] if end_ym[1] >= 10 else end_ym[0] - 1
    n_hydro = end_hy - start_hy + 1
    report_lines.append(
        f'Period of record   : {start_ym[0]:4d}-{start_ym[1]:02d} → '
        f'{end_ym[0]:4d}-{end_ym[1]:02d}  '
        f'({n_hydro} hydro years, {n_months} months)'
    )

    # --- Pre-run warnings (information-only; output is unaffected) ---
    # Zero-target months — output for those months will be all zeros
    zero_months = sum(1 for v in gen_monthly.values() if v == 0.0)
    if zero_months:
        report_lines.append(
            f'Warning: {zero_months} target monthly value(s) are zero — '
            'their output days will all be zero.'
        )

    # PATCH_EXCEED-specific distribution warnings
    if method == DisagMethod.PATCH_EXCEED and target_dists is not None:
        # #7 Sparse calendar months — tier 3 cannot fire for these
        sparse = [m for m in range(1, 13) if len(target_dists[m]) < 2]
        if sparse:
            report_lines.append(
                f'Warning: gen_monthly has fewer than 2 valid values for '
                f'calendar month(s) {sparse} — tier 3 cannot fire there '
                'and any gappy month in those calendar months will be '
                'marked missing.'
            )
        # #9 Flat distributions — donor selection collapses to year proximity
        flat = [
            m for m in range(1, 13)
            if len(target_dists[m]) >= 2 and len(set(target_dists[m])) == 1
        ]
        if flat:
            report_lines.append(
                f'Warning: gen_monthly has identical values across all '
                f'years for calendar month(s) {flat} — tier-3 donor '
                'selection there will be decided purely by year proximity.'
            )
        # Sparse per-file donor pools — tier-3 also needs ≥2 complete
        # donor months in *each* file's per-calendar-month pool. Without
        # this warning, a daily file with only one complete record for a
        # given calendar month would silently lose tier-3 capability
        # there — at run time the report shows a "No tier-3 donor
        # available" line per affected month, but never explains *why*
        # the donor pool failed.
        if donor_dists is not None:
            for file_idx, per_month in enumerate(donor_dists):
                short = [m for m in range(1, 13) if len(per_month[m]) < 2]
                if short:
                    report_lines.append(
                        f'Warning: daily file {file_idx + 1} has fewer than 2 '
                        f'complete months for calendar month(s) {short} — '
                        'tier 3 cannot draw a donor from this file there.'
                    )

    # Tier-2 scale factor block — placed after warnings so the file
    # header clearly precedes the per-month log lines.
    if (method == DisagMethod.PATCH_EXCEED and tier2_scale is not None
            and len(tier2_scale) > 1
            and any(abs(f - 1.0) > 1e-9 for f in tier2_scale[1].values())):
        report_lines.append(
            'Tier-2 file-2 → file-1 scale factors '
            '(applied to file-2 day values when patching):'
        )
        for m in range(1, 13):
            report_lines.append(
                f'  month {m:2d}: {tier2_scale[1].get(m, 1.0):8.4f}'
            )

    # --- Iterate months ---
    output_records: list = []
    decisions: dict = {}

    year, month = start_ym
    while (year, month) <= end_ym:
        rec = _convert_month(
            year, month, method,
            gen_monthly, obs_daily,
            start_obs_2, decisions,
            obs_totals=obs_totals,
            target_dists=target_dists,
            donor_dists=donor_dists,
            tier2_scale=tier2_scale,
            tier_counters=tier_counters,
        )
        output_records.append(rec)
        year, month = _inc_month(year, month)

    # --- Per-month decision log — one row per iterated month, every method ---
    # This is the single authoritative record of what happened to each month
    # and why (which file the days came from, any patch/donor source, or the
    # reason it was marked missing). F1/F2/OTH are the day counts from daily
    # file 1, daily file 2, and a patched / donor / even source.
    report_lines.append('Decision log (one row per month):')
    report_lines.append('YYYY MM   F1  F2  OTH   result / source')
    for (y, m), dec in sorted(decisions.items()):
        report_lines.append(
            f'{y:4d} {m:2d}'
            f'  {dec["f1"]:3d} {dec["f2"]:3d} {dec["oth"]:3d}'
            f'   {dec["note"]}'
        )

    # Tier 1/2/3 day-count summary (PATCH_EXCEED only)
    if tier_counters is not None:
        t1 = tier_counters['tier1_days']
        t2 = tier_counters['tier2_days']
        t3 = tier_counters['tier3_days']
        tot = t1 + t2 + t3
        def _pct(n: int) -> str:
            return f'{n / tot * 100:5.1f}%' if tot else '  n/a'
        report_lines.append('Tier coverage summary (days):')
        report_lines.append(
            f'  Tier 1 (file 1)        : {t1:6d} day(s)  ({_pct(t1)})'
        )
        report_lines.append(
            f'  Tier 2 (file 2)        : {t2:6d} day(s)  ({_pct(t2)})'
            f'  across {len(tier_counters["tier2_months"]):3d} month(s)'
        )
        report_lines.append(
            f'  Tier 3 (donor month)   : {t3:6d} day(s)  ({_pct(t3)})'
            f'  across {len(tier_counters["tier3_months"]):3d} month(s)'
        )

        # Tier-3 donor match-quality summary — how closely the donor
        # months matched the target on the exceedance percentile that
        # drives PATCH_EXCEED selection. This is the quality metric for
        # the method's core operation; without it the per-month
        # target/donor percentiles in the log never get aggregated.
        matches = tier_counters['tier3_matches']
        if matches:
            gaps = [abs(pt - pd) for _, _, pt, pd, _, _ in matches]
            n = len(gaps)
            from_f1 = sum(1 for *_, fi, _ in matches if fi == 0)
            from_f2 = n - from_f1
            distinct = {(fi, dy, m) for _, m, _, _, fi, dy in matches}
            reused = n - len(distinct)
            outliers = sorted(
                ((y, m, pt, pd) for y, m, pt, pd, _, _ in matches
                 if abs(pt - pd) > 1.0),
                key=lambda r: abs(r[2] - r[3]), reverse=True,
            )
            report_lines.append(f'Tier-3 donor match quality ({n} months):')
            report_lines.append(
                f'  |target - donor| exceed gap : '
                f'mean {sum(gaps) / n:.2f} pt   max {max(gaps):.2f} pt'
            )
            report_lines.append(
                f'  donor source split          : '
                f'file 1: {from_f1:3d} month(s)   file 2: {from_f2:3d} month(s)'
            )
            report_lines.append(
                f'  distinct donor months       : '
                f'{len(distinct):3d}  ({reused} reused)'
            )
            if outliers:
                worst = '; '.join(
                    f'{y:4d}{m:3d} {pt:.1f} vs {pd:.1f}'
                    for y, m, pt, pd in outliers[:5]
                )
                more = f' (+{len(outliers) - 5} more)' if len(outliers) > 5 else ''
                report_lines.append(
                    f'  matches worse than 1.0 pt   : '
                    f'{len(outliers)}  [{worst}{more}]'
                )

    return output_records, report_lines
