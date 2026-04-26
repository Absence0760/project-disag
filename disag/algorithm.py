"""
Core disaggregation algorithm.

Converts monthly flows (Mm3/month) to daily flows (m3/s) using one of five
methods that borrow a daily shape from an observed daily record.

Formula
-------
    Qgen_daily[d] = Qgen_monthly * (Qobs_daily[d] / sum(Qobs_daily)) * 1e6/86400

Unit conversion at the end: Mm3/day → m3/s  (×1e6 / 86400)
"""

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


def find_exceed_donor(
    target_year: int,
    target_month: int,
    gen_monthly: dict,
    obs_totals: list,       # list of {(y, m): vol} dicts, one per daily file
) -> Optional[tuple]:
    """Find an exceedance-matched donor month for PATCH_EXCEED tier 3.

    Picks the (file_idx, donor_year) whose monthly volume sits at the
    closest exceedance percentile to the target's, within its own daily
    file's per-calendar-month distribution. Ties broken by year proximity
    to ``target_year``, then by smaller file index.

    Returns ``(file_idx, donor_year, p_target, p_donor)`` or ``None`` if
    no eligible donor exists.
    """
    target_vol = gen_monthly.get((target_year, target_month))
    if target_vol is None or target_vol < 0:
        return None

    target_dist = [v for (y, m), v in gen_monthly.items()
                   if m == target_month and v >= 0]
    if len(target_dist) < 2:
        return None
    p_target = _exceed_pct(target_vol, target_dist)

    target_dim = calendar.monthrange(target_year, target_month)[1]

    best_key: Optional[tuple] = None
    best_p_donor: float = 0.0

    for file_idx, totals in enumerate(obs_totals):
        if not totals:
            continue
        donor_dist = [v for (y, m), v in totals.items() if m == target_month]
        if len(donor_dist) < 2:
            continue
        for (y, m), vol in totals.items():
            if m != target_month:
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
    report_lines: list,
    obs_totals: Optional[list] = None,   # precomputed monthly totals per file
) -> DailyRecord:
    dim = calendar.monthrange(year, month)[1]

    # --- Monthly generated value (Mm3/month) ---
    gen_val = gen_monthly.get((year, month))
    if gen_val is None or gen_val < 0:
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

    # --- Missing-data check ---
    missing = False
    patch_year: Optional[int] = None
    exceed_donor: Optional[DailyRecord] = None

    if method == DisagMethod.EVEN:
        pass  # never missing

    elif method == DisagMethod.ONE_FILE:
        if rec1 is None or any(rec1.v[d] < 0 for d in range(dim)):
            missing = True

    elif method == DisagMethod.INCREMENTAL:
        if rec1 is None or rec2 is None:
            missing = True
        elif any(rec1.v[d] < 0 or rec2.v[d] < 0 for d in range(dim)):
            missing = True

    elif method == DisagMethod.PATCH_FILE:
        # Missing only if the same day is absent from BOTH files
        for d in range(dim):
            f1 = rec1.v[d] if rec1 else -999.0
            f2 = rec2.v[d] if rec2 else -999.0
            if f1 < 0 and f2 < 0:
                missing = True
                break

    elif method == DisagMethod.PATCH_CAL:
        # If any day is missing, try to borrow a complete month from another year
        needs_patch = rec1 is None or any(rec1.v[d] < 0 for d in range(dim))
        if needs_patch:
            patch_year = find_patch_year(year, month, gen_monthly, obs_daily[0])
            if patch_year is not None:
                report_lines.append(
                    f'{year:4d}{month:3d}'
                    f' Observed daily flow < 0,'
                    f'   Patched with {patch_year:4d}{month:3d}'
                )
            else:
                missing = True

    elif method == DisagMethod.PATCH_EXCEED:
        # Tier 1+2: any day missing in BOTH files triggers tier 3
        needs_donor = False
        for d in range(dim):
            f1 = rec1.v[d] if rec1 and d < len(rec1.v) else -999.0
            f2 = rec2.v[d] if rec2 and d < len(rec2.v) else -999.0
            if f1 < 0 and f2 < 0:
                needs_donor = True
                break

        if needs_donor:
            donor = find_exceed_donor(
                year, month, gen_monthly, obs_totals or []
            )
            if donor is None:
                missing = True
            else:
                file_idx, donor_year, p_target, p_donor = donor
                exceed_donor = obs_daily[file_idx].get((donor_year, month))
                if exceed_donor is None:
                    missing = True
                else:
                    report_lines.append(
                        f'{year:4d}{month:3d}'
                        f' Observed daily flow < 0,'
                        f'   Patched with file {file_idx + 1}'
                        f' {donor_year:4d}{month:3d}'
                        f' (target exceed%={p_target:5.1f},'
                        f' donor exceed%={p_donor:5.1f})'
                    )

    if missing:
        return DailyRecord(year=year, month=month, v=[MISSING] * dim)

    # --- Build daily pattern qD[] ---
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

            elif method == DisagMethod.INCREMENTAL:
                val = f1 - f2

            elif method == DisagMethod.PATCH_FILE:
                val = f2 if f1 < 0 else f1

            elif method == DisagMethod.PATCH_CAL:
                if f1 < 0 and patch_year is not None:
                    rec_patch = obs_daily[0].get((patch_year, month))
                    f3 = rec_patch.v[d] if rec_patch and d < len(rec_patch.v) else -999.0
                    val = f3
                else:
                    val = f1

            elif method == DisagMethod.PATCH_EXCEED:
                if f1 >= 0:
                    val = f1
                elif f2 >= 0:
                    val = f2
                elif exceed_donor is not None and d < len(exceed_donor.v):
                    val = exceed_donor.v[d]
                else:
                    val = -999.0

            else:
                val = f1

            qD.append(max(val, 0.0))   # clamp negatives to zero

        qM = sum(qD)

    # --- Handle zero observed monthly total ---
    if qM <= 0 and gen_val > 0:
        report_lines.append(
            f'{year:4d}{month:3d}'
            f' Observed monthly flow <= 0,'
            f'   Gen Flow= {gen_val:7.3f}'
        )
        qD = [1.0] * dim
        qM = float(dim)

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

    # --- Determine processing start date ---

    # Hydro-year start for each daily file
    obs_starts = [_hydro_start_ym(obs_daily[f]) for f in range(no_files)]

    if no_files == 0:
        start_daily = (1900, 10)
    elif method == DisagMethod.INCREMENTAL and no_files >= 2:
        start_daily = max(obs_starts[0], obs_starts[1])
    else:
        start_daily = obs_starts[0]

    # Monthly file start: first hydro year (always October).
    # read_monthly_file keys each row starting at (hydro_year, 10), so the
    # minimum key's month is always 10. If a caller supplies a dict whose
    # first key is January–September, step back to the October that started
    # that hydro year.
    first_mon = min(gen_monthly.keys())
    hydro_year = first_mon[0] if first_mon[1] >= 10 else first_mon[0] - 1
    monthly_start = (hydro_year, 10)

    start_ym = max(start_daily, monthly_start)

    # --- Determine processing end date ---
    end_candidates = [max(gen_monthly.keys())]
    for f in range(no_files):
        if obs_daily[f]:
            end_candidates.append(max(obs_daily[f].keys()))
    end_ym = min(end_candidates)

    # Start date for file-2 (PATCH_FILE: use file 1 only before this)
    start_obs_2 = obs_starts[1] if no_files >= 2 else (9999, 12)

    # --- Precompute per-file monthly totals for PATCH_EXCEED tier 3 ---
    obs_totals: list = []
    if method == DisagMethod.PATCH_EXCEED:
        obs_totals = [_monthly_totals_from_daily(obs_daily[f])
                      for f in range(len(obs_daily))]

    # --- Iterate months ---
    report_lines: list = []
    output_records: list = []

    year, month = start_ym
    while (year, month) <= end_ym:
        rec = _convert_month(
            year, month, method,
            gen_monthly, obs_daily,
            start_obs_2, report_lines,
            obs_totals=obs_totals,
        )
        output_records.append(rec)
        year, month = _inc_month(year, month)

    return output_records, report_lines
