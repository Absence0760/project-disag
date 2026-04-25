"""Report writing functionality."""

from datetime import datetime

from .algorithm import METHOD_NAMES, DisagMethod, count_coverage


def write_report(
    path: str,
    method: DisagMethod,
    report_lines: list,
    records: list = None,
) -> None:
    """Write disaggregation report to file.

    If ``records`` is provided, a coverage summary (disaggregated vs
    missing month counts) is included so a "0 adjustments" line can't be
    confused with "0 problems".
    """
    dash = '-' * 80
    with open(path, 'w') as fh:
        fh.write(dash + '\n')
        fh.write(f'Disag Report  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        fh.write(f'Method        : {METHOD_NAMES[method]}\n')
        fh.write(dash + '\n')
        for line in report_lines:
            fh.write(line + '\n')
        fh.write(dash + '\n')
        if records is not None:
            disagg, missing = count_coverage(records)
            total = disagg + missing
            pct = (missing / total * 100) if total else 0
            fh.write(f'Months written     : {total}\n')
            fh.write(f'  Disaggregated    : {disagg}\n')
            fh.write(f'  Missing (-99.99) : {missing}  ({pct:.1f}%)\n')
        fh.write(f'Total adjustments  : {len(report_lines)}\n')
