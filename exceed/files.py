"""File I/O for exceed tool."""

from typing import Dict, List

from disag.files import MONTHLY_HEADER_LINES, read_daily_file as _read_daily_records


def read_monthly_file(filepath: str) -> Dict[int, List[float]]:
    """
    Read monthly flow data file.

    Format: Hydro year rows (Oct-Sep) with 12 month columns.
    Returns dict: month_number (1-12 for Jan-Dec) -> list of values

    Args:
        filepath: Path to .mon file

    Returns:
        Dictionary mapping calendar month (1-12) to list of flow values
    """
    monthly_data = {i: [] for i in range(1, 13)}  # Jan(1) to Dec(12)

    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Skip the fixed free-form header (matches disag.files.read_monthly_file
    # and the docs/file-formats.md spec).
    for line in lines[MONTHLY_HEADER_LINES:]:
        line = line.strip()
        if not line or line.startswith('-'):
            continue

        # Parse line: Year followed by 12 monthly values
        parts = line.split()
        if len(parts) < 13:
            continue

        try:
            year = int(parts[0])
        except ValueError:
            continue
        if year < 1900:
            year += 1900

        # Extract 12 months (Oct-Sep in hydro year format)
        # Map to calendar months: Oct=10, Nov=11, Dec=12, Jan=1, Feb=2, ..., Sep=9
        hydro_months = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

        for i, cal_month in enumerate(hydro_months):
            try:
                value = float(parts[i + 1])
            except (ValueError, IndexError):
                continue
            # Spec: any negative value is the missing-data sentinel.
            if value >= 0:
                monthly_data[cal_month].append(value)

    return monthly_data


def read_daily_file(filepath: str) -> Dict[int, List[float]]:
    """
    Read daily flow data file and group values by calendar month.

    Delegates to disag.files.read_daily_file for the fixed-width parsing
    (handles 2- and 4-digit years, no-space negative values, and the
    monthly-total header line) and then strips MISSING values.

    Returns:
        Dictionary mapping calendar month (1-12) to list of daily flow values
        (missing values excluded).
    """
    daily_data: Dict[int, List[float]] = {i: [] for i in range(1, 13)}
    records = _read_daily_records(filepath)

    # Spec: any negative value is the missing-data sentinel (docs/file-formats.md).
    # Drop them before exceedance analysis; the exceed tool does not patch.
    for (_year, month), rec in records.items():
        for v in rec.v:
            if v >= 0:
                daily_data[month].append(v)

    return daily_data


def write_exceedance_report(filepath: str, monthly_exceedance: Dict) -> None:
    """
    Write exceedance analysis report to file.

    Accepts monthly results keyed by calendar-month int (1-12) and daily
    results keyed by string `daily_<month>` (e.g. `daily_1` for January).
    Monthly sections are written first, followed by daily sections.

    Args:
        filepath: Output file path
        monthly_exceedance: Dict mapping either int month or `daily_<month>`
            string to {flow_values, exceedance_pct, ...}
    """
    from datetime import datetime

    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']

    def _write_section(f, heading, result):
        f.write(f'{heading}\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total values: {result["total_count"]}  '
               f'Below range: {result["count_below"]}  '
               f'Above range: {result["count_above"]}\n\n')

        f.write('Exceedance%    Flow Value\n')
        f.write('-' * 30 + '\n')

        flows = result['flow_values']
        exceedances = result['exceedance_pct']

        for i in range(len(flows)):
            f.write(f'{exceedances[i]:8.2f}%     {flows[i]:12.3f}\n')

        f.write('\n')

    with open(filepath, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Exceedance Analysis Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('-' * 80 + '\n\n')

        for month in range(1, 13):
            if month not in monthly_exceedance:
                continue
            _write_section(f, f'MONTHLY - {month_names[month].upper()}',
                           monthly_exceedance[month])

        for month in range(1, 13):
            key = f'daily_{month}'
            if key not in monthly_exceedance:
                continue
            _write_section(f, f'DAILY - {month_names[month].upper()}',
                           monthly_exceedance[key])


def write_seasonal_exceedance_report(
    filepath: str,
    seasonal_exceedance: Dict[str, Dict]
) -> None:
    """
    Write seasonal exceedance analysis report to file.
    
    Args:
        filepath: Output file path
        seasonal_exceedance: Dict mapping season name to exceedance data
    """
    from datetime import datetime
    
    with open(filepath, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Seasonal Exceedance Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('-' * 80 + '\n\n')
        
        for season_name in sorted(seasonal_exceedance.keys()):
            result = seasonal_exceedance[season_name]
            f.write(f'{season_name.upper()}\n')
            f.write('-' * 80 + '\n')
            f.write(f'Total values: {result["total_count"]}  '
                   f'Below range: {result["count_below"]}  '
                   f'Above range: {result["count_above"]}\n\n')
            
            f.write('Exceedance%    Flow Value\n')
            f.write('-' * 30 + '\n')
            
            flows = result['flow_values']
            exceedances = result['exceedance_pct']
            
            for i in range(len(flows)):
                f.write(f'{exceedances[i]:8.2f}%     {flows[i]:12.3f}\n')
            
            f.write('\n')


