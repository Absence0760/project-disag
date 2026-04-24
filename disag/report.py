"""Report writing functionality."""

from datetime import datetime

from .algorithm import METHOD_NAMES, DisagMethod


def write_report(path: str, method: DisagMethod, report_lines: list) -> None:
    """Write disaggregation report to file."""
    dash = '-' * 80
    with open(path, 'w') as fh:
        fh.write(dash + '\n')
        fh.write(f'Disag Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        fh.write(f'Method        : {METHOD_NAMES[method]}\n')
        fh.write(dash + '\n')
        for line in report_lines:
            fh.write(line + '\n')
        fh.write(dash + '\n')
        fh.write(f'Total adjustments : {len(report_lines)}\n')
