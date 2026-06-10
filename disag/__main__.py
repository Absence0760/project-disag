"""
Entry point.

GUI mode (default)
------------------
    python -m disag

CLI mode
--------
    python -m disag --no-gui \\
        --method 0 \\
        --monthly  path/to/file.mon \\
        --daily1   path/to/file1.day \\
        --output   path/to/out.day \\
        --report   path/to/out.rep

Methods
    0  One disaggregator file
    1  Patch missing days with flows from a similar month (same calendar month, closest volume)
    2  Patch missing days with daily file 2
    3  Incremental catchment: pattern = (daily 1) − (daily 2)
    4  Even distribution (no daily file needed)
    5  Patch with file 1, then file 2, then exceedance-matched donor month (file 2 optional)
"""

import argparse
import os
import re
import sys


def _parse_tier_coverage(report_lines):
    """Pull tier-1/2/3 day counts out of the .rep coverage summary.

    Returns ``(t1, t2, t3)`` or ``None`` if the summary block isn't
    present (i.e. method != PATCH_EXCEED).
    """
    counts = {1: None, 2: None, 3: None}
    for line in report_lines:
        for tier in (1, 2, 3):
            if line.lstrip().startswith(f'Tier {tier}'):
                m = re.search(r':\s+(\d+)\s+day', line)
                if m:
                    counts[tier] = int(m.group(1))
    if any(v is None for v in counts.values()):
        return None
    return counts[1], counts[2], counts[3]


def main():
    parser = argparse.ArgumentParser(
        prog='python -m disag',
        description='Disaggregate NS monthly flows to daily flows.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--no-gui', dest='gui', action='store_false', default=True,
        help='Run in command-line mode (default: open GUI)',
    )
    parser.add_argument(
        '--method', '-m', type=int, choices=range(6), default=0, metavar='N',
        help='Disaggregation method 0-5 (CLI mode only)',
    )
    parser.add_argument('--monthly',  help='Monthly input file (.mon/.nat/.cur)')
    parser.add_argument('--daily1',   help='Daily reference file 1 (.day)')
    parser.add_argument('--daily2',   help='Daily reference file 2 (.day)')
    parser.add_argument('--output', '-o', help='Output daily file (.day)')
    parser.add_argument('--report', '-r', help='Report file (.rep)')

    args = parser.parse_args()

    if args.gui:
        # Import-only check — do NOT instantiate Tk() here. On macOS 26 + Tk 9
        # creating then destroying a Tk root before the real app's Tk root
        # corrupts state and triggers a PAC trap inside Tk_MacOSXGetTkWindow.
        try:
            import tkinter  # noqa: F401
        except ImportError as exc:
            print(
                f'Cannot open GUI: {exc}\n\n'
                'tkinter is not available in this Python installation.\n'
                'On macOS, fix it with:\n'
                '    brew install python@3.13 python-tk@3.13\n'
                '    python3.13 -m disag\n\n'
                'To run without a GUI use --no-gui (see --help).',
                file=sys.stderr,
            )
            raise SystemExit(1)

        from .gui import DisagApp
        app = DisagApp()
        app.mainloop()
        return

    # ── CLI mode ──────────────────────────────────────────────────────
    from .algorithm import (
        DisagMethod,
        METHOD_NAMES,
        NO_FILES,
        count_coverage,
        disaggregate,
    )
    from .files import read_daily_file, read_monthly_file, write_daily_file
    from .report import write_report

    method = DisagMethod(args.method)
    min_files = NO_FILES[method]

    required = {'monthly': args.monthly, 'output': args.output, 'report': args.report}
    if min_files >= 1:
        required['daily1'] = args.daily1
    if min_files >= 2:
        required['daily2'] = args.daily2

    missing = [f'--{k}' for k, v in required.items() if not v]
    if missing:
        parser.error(f'The following arguments are required: {", ".join(missing)}')

    # PATCH_EXCEED accepts an optional file 2; treat it as a 2-file run if supplied
    use_daily2 = min_files >= 2 or (
        method == DisagMethod.PATCH_EXCEED and bool(args.daily2)
    )
    no_files = 2 if use_daily2 else min_files

    print(f'Method    : {METHOD_NAMES[method]}')
    print(f'Reading   : {args.monthly}')
    gen_monthly = read_monthly_file(args.monthly)

    obs_daily = [{}, {}]
    if no_files >= 1:
        print(f'Reading   : {args.daily1}')
        obs_daily[0] = read_daily_file(args.daily1)
    if use_daily2:
        print(f'Reading   : {args.daily2}')
        obs_daily[1] = read_daily_file(args.daily2)

    print('Disaggregating…')
    records, report_lines = disaggregate(method, gen_monthly, obs_daily, no_files)

    header_info = {
        'monthly_file': os.path.basename(args.monthly),
        'daily_file_1': os.path.basename(args.daily1) if no_files >= 1 else '',
        'daily_file_2': os.path.basename(args.daily2) if use_daily2 else '',
        'method_str':   METHOD_NAMES[method],
    }
    print(f'Writing   : {args.output}')
    write_daily_file(args.output, records, header_info)

    print(f'Report    : {args.report}')
    write_report(args.report, method, report_lines, records)

    disagg, missing = count_coverage(records)
    pct_missing = (missing / len(records) * 100) if records else 0

    print(f'\nDone — {len(records)} months written '
          f'({disagg} disaggregated, {missing} missing).')
    if report_lines:
        print(f'Per-month decision log written to {args.report}')

    if pct_missing > 50 and method == DisagMethod.ONE_FILE:
        print(
            f'\nWARNING: {pct_missing:.0f}% of output months are missing data.\n'
            f'  The daily input has gaps and Method 0 drops any month with\n'
            f'  even one missing day. Try Method 1 (--method 1) to patch\n'
            f'  missing days from the closest-volume same-month in another\n'
            f'  year, or Method 5 (--method 5) for an exceedance-percentile\n'
            f'  match that works across rivers of different scale. Each\n'
            f'  patch will be logged in the report.',
            file=sys.stderr,
        )

    # Method 5 can produce a fully-disaggregated output where most days
    # are tier-3 synthetic (donor-copied) rather than real observations.
    # The "0 missing" line above doesn't reflect that, so warn explicitly
    # when the synthetic share is high. Threshold is 50% — below that,
    # the output is mostly real data and no nudge is needed.
    if method == DisagMethod.PATCH_EXCEED:
        coverage = _parse_tier_coverage(report_lines)
        if coverage is not None:
            t1, t2, t3 = coverage
            total = t1 + t2 + t3
            if total > 0:
                pct_synth = 100.0 * t3 / total
                if pct_synth > 50:
                    print(
                        f'\nWARNING: {pct_synth:.0f}% of output days are '
                        f'tier-3 synthetic.\n'
                        f'  {t1} day(s) from file 1, {t2} day(s) from file 2, '
                        f'{t3} day(s) from\n'
                        f'  percentile-matched donor months. Each donor '
                        f'choice is logged\n'
                        f'  in the report ({args.report}). The daily shape '
                        f'of synthetic\n'
                        f'  months is borrowed; only the monthly volume is '
                        f'from the input.',
                        file=sys.stderr,
                    )


if __name__ == '__main__':
    main()
