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
