"""Exceedance (flow frequency) analysis algorithm."""

from dataclasses import dataclass


@dataclass
class ExceedanceResult:
    """Result of exceedance analysis."""
    flow_values: list  # Y values - flow magnitudes
    exceedance_pct: list  # X values - exceedance percentages
    count_above: int  # Count of values above range
    count_below: int  # Count of values below range
    total_count: int  # Total number of values processed


class ExceedanceCalculator:
    """Calculate flow frequency (exceedance) curves."""
    
    def __init__(self, min_flow: float, max_flow: float, num_intervals: int):
        """
        Initialize exceedance calculator.
        
        Args:
            min_flow: Minimum flow value for range
            max_flow: Maximum flow value for range
            num_intervals: Number of intervals to divide range into
        """
        self.min_flow = min_flow
        self.max_flow = max_flow
        self.num_intervals = num_intervals
        
        # Calculate interval size
        self.interval_size = (max_flow - min_flow) / num_intervals
        
        # Initialize counters
        self.counts = [0] * (num_intervals + 1)  # counts[1..num_intervals]
        self.count_above = 0
        self.count_below = 0
        self.total_count = 0
    
    def process_value(self, value: float):
        """
        Process a single flow value.
        
        Args:
            value: Flow value to process
        """
        # Determine which interval this value falls into
        # i = trunc((v - min) / interval) + 1
        i = int((value - self.min_flow) / self.interval_size) + 1
        
        if i < 1:
            self.count_below += 1
        elif i > self.num_intervals:
            self.count_above += 1
        else:
            self.counts[i] += 1
        
        self.total_count += 1
    
    def calculate_result(self) -> ExceedanceResult:
        """
        Calculate exceedance percentages from processed values.
        
        Returns:
            ExceedanceResult with flow values and exceedance percentages
        """
        flow_values = []
        exceedance_pct = []
        
        # Start from the top and work downward, accumulating counts
        cum_sum = self.count_above
        
        for i in range(self.num_intervals, 0, -1):
            cum_sum += self.counts[i]
            
            # Calculate exceedance percentage
            pct = (cum_sum / self.total_count * 100) if self.total_count > 0 else 0.0
            exceedance_pct.insert(0, pct)
            
            # Calculate flow value for this interval
            # flow = (i - 1) * interval + min
            flow = (i - 1) * self.interval_size + self.min_flow
            flow_values.insert(0, flow)
        
        return ExceedanceResult(
            flow_values=flow_values,
            exceedance_pct=exceedance_pct,
            count_above=self.count_above,
            count_below=self.count_below,
            total_count=self.total_count,
        )


def calculate_monthly_exceedance(values: list, num_intervals: int = 20) -> ExceedanceResult:
    """
    Calculate exceedance for a set of monthly flow values.
    
    Args:
        values: List of flow values (non-missing)
        num_intervals: Number of intervals for frequency distribution
        
    Returns:
        ExceedanceResult with exceedance analysis
    """
    if not values:
        raise ValueError("No values provided")
    
    min_val = min(values)
    max_val = max(values)
    
    # Handle case where all values are identical
    if min_val == max_val:
        max_val = min_val * 1.01 + 0.01  # Add small margin
    
    calc = ExceedanceCalculator(min_val, max_val, num_intervals)
    
    for value in values:
        calc.process_value(value)
    
    return calc.calculate_result()


# ── Season definitions ────────────────────────────────────────────────

SEASON_PRESETS = {
    2: {  # 2-season: wet/dry (Hydro year Oct-Sep)
        'Wet Season': [10, 11, 12, 1, 2, 3],    # Oct-Mar
        'Dry Season': [4, 5, 6, 7, 8, 9],       # Apr-Sep
    },
    3: {  # 3-season: Winter/Spring/Summer+Fall
        'Summer': [6, 7, 8],                     # Jun-Aug
        'Fall': [9, 10, 11],                     # Sep-Nov
        'Winter': [12, 1, 2, 3, 4, 5],           # Dec-May
    },
    4: {  # 4-season: Calendar seasons
        'Winter': [12, 1, 2],                    # Dec-Feb
        'Spring': [3, 4, 5],                     # Mar-May
        'Summer': [6, 7, 8],                     # Jun-Aug
        'Fall': [9, 10, 11],                     # Sep-Nov
    },
}


def get_season_presets(num_seasons: int) -> dict:
    """Get default season definitions for a given number of seasons."""
    return SEASON_PRESETS.get(num_seasons, {})


def calculate_seasonal_exceedance(
    monthly_data: dict,
    seasons: dict,
    num_intervals: int = 20
) -> dict:
    """
    Calculate exceedance grouped by seasons.
    
    Args:
        monthly_data: Dict mapping month (1-12) to list of values
        seasons: Dict mapping season name to list of months
        num_intervals: Number of intervals for frequency distribution
        
    Returns:
        Dict mapping season name to ExceedanceResult
    """
    results = {}
    
    for season_name, months in seasons.items():
        season_values = []
        
        for month in months:
            if month in monthly_data:
                season_values.extend(monthly_data[month])
        
        if season_values:
            results[season_name] = calculate_monthly_exceedance(
                season_values, num_intervals)
    
    return results


def match_exceedance_values(
    monthly_result: ExceedanceResult,
    daily_result: ExceedanceResult,
    tolerance_pct: float = 5.0
) -> list:
    """
    Find matching exceedance values between monthly and daily analyses.
    
    Returns list of matches where |exceed_monthly - exceed_daily| <= tolerance.
    
    Args:
        monthly_result: Monthly exceedance result
        daily_result: Daily exceedance result
        tolerance_pct: Exceedance percentage tolerance for matching
        
    Returns:
        List of dicts: {flow_monthly, exceed_monthly, flow_daily, exceed_daily, diff}
    """
    matches = []
    
    # For each monthly exceedance, find closest daily exceedance
    for i, exceed_m in enumerate(monthly_result.exceedance_pct):
        flow_m = monthly_result.flow_values[i]
        
        # Find best matching daily exceedance
        best_diff = tolerance_pct + 1
        best_match = None
        
        for j, exceed_d in enumerate(daily_result.exceedance_pct):
            flow_d = daily_result.flow_values[j]
            diff = abs(exceed_m - exceed_d)
            
            if diff < best_diff:
                best_diff = diff
                best_match = {
                    'flow_monthly': flow_m,
                    'exceed_monthly': exceed_m,
                    'flow_daily': flow_d,
                    'exceed_daily': exceed_d,
                    'diff': diff,
                }
        
        if best_match and best_diff <= tolerance_pct:
            matches.append(best_match)
    
    return matches
