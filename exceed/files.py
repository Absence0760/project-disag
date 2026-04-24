"""File I/O for exceed tool."""

import re
from typing import Dict, List, Tuple


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
    
    # Skip header lines until we find the year column
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('Year'):
            data_start = i + 1
            break
    
    if data_start == 0:
        raise ValueError("Could not find data header in file")
    
    # Process data lines
    for line in lines[data_start:]:
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
        
        # Extract 12 months (Oct-Sep in hydro year format)
        # Map to calendar months: Oct=10, Nov=11, Dec=12, Jan=1, Feb=2, ..., Sep=9
        hydro_months = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        
        for i, cal_month in enumerate(hydro_months):
            try:
                value = float(parts[i + 1])
                monthly_data[cal_month].append(value)
            except (ValueError, IndexError):
                pass
    
    return monthly_data


def read_daily_file(filepath: str) -> Dict[int, List[float]]:
    """
    Read daily flow data file.
    
    Format: YYMM followed by flow values (7 per line typically).
    Missing values coded as -99.990.
    
    Returns dict: month_number (1-12) -> list of daily values (excluding missing)
    
    Args:
        filepath: Path to .day file
        
    Returns:
        Dictionary mapping calendar month (1-12) to list of daily flow values
    """
    daily_data = {i: [] for i in range(1, 13)}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    current_month = None
    current_year = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line starts with YYMM (year-month header)
        if len(line) >= 6 and line[0].isdigit():
            match = re.match(r'(\d{2})\s+(\d{1,2})', line)
            if match:
                year_short = int(match.group(1))
                month = int(match.group(2))
                current_year = 1900 + year_short if year_short >= 50 else 2000 + year_short
                current_month = month
                
                # Extract flow values from this line if they follow
                flow_part = line[6:].strip()
                if flow_part:
                    _process_flow_values(flow_part, current_month, daily_data)
                continue
        
        # If we have a current month, treat line as flow values
        if current_month is not None:
            _process_flow_values(line, current_month, daily_data)
    
    return daily_data


def _process_flow_values(flow_str: str, month: int, data_dict: Dict):
    """
    Process a string of space-separated flow values.
    
    Args:
        flow_str: String of space-separated numbers
        month: Calendar month (1-12)
        data_dict: Dictionary to append values to
    """
    # Split on whitespace and process each value
    parts = flow_str.split()
    for part in parts:
        try:
            value = float(part)
            # Exclude missing value marker
            if value > -99.0:  # Not a missing data marker
                data_dict[month].append(value)
        except ValueError:
            pass


def write_exceedance_report(filepath: str, monthly_exceedance: Dict[int, Dict]) -> None:
    """
    Write exceedance analysis report to file.
    
    Args:
        filepath: Output file path
        monthly_exceedance: Dict of {month: {flow_values, exceedance_pct, ...}}
    """
    from datetime import datetime
    
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    with open(filepath, 'w') as f:
        f.write('-' * 80 + '\n')
        f.write(f'Exceedance Analysis Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('-' * 80 + '\n\n')
        
        for month in range(1, 13):
            if month not in monthly_exceedance:
                continue
            
            result = monthly_exceedance[month]
            f.write(f'{month_names[month].upper()}\n')
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
