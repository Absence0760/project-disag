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
"""

import argparse
import os
import sys


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
        '--method', '-m', type=int, choices=range(5), default=0, metavar='N',
        help='Disaggregation method 0-4 (CLI mode only)',
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
    from .algorithm import DisagMethod, METHOD_NAMES, NO_FILES, disaggregate
    from .files import read_daily_file, read_monthly_file, write_daily_file
    from .report import write_report

    method = DisagMethod(args.method)
    no_files = NO_FILES[method]

    required = {'monthly': args.monthly, 'output': args.output, 'report': args.report}
    if no_files >= 1:
        required['daily1'] = args.daily1
    if no_files >= 2:
        required['daily2'] = args.daily2

    missing = [f'--{k}' for k, v in required.items() if not v]
    if missing:
        parser.error(f'The following arguments are required: {", ".join(missing)}')

    print(f'Method    : {METHOD_NAMES[method]}')
    print(f'Reading   : {args.monthly}')
    gen_monthly = read_monthly_file(args.monthly)

    obs_daily = [{}, {}]
    if no_files >= 1:
        print(f'Reading   : {args.daily1}')
        obs_daily[0] = read_daily_file(args.daily1)
    if no_files >= 2:
        print(f'Reading   : {args.daily2}')
        obs_daily[1] = read_daily_file(args.daily2)

    print('Disaggregating…')
    records, report_lines = disaggregate(method, gen_monthly, obs_daily, no_files)

    header_info = {
        'monthly_file': os.path.basename(args.monthly),
        'daily_file_1': os.path.basename(args.daily1) if args.daily1 else '',
        'daily_file_2': os.path.basename(args.daily2) if args.daily2 else '',
        'method_str':   METHOD_NAMES[method],
    }
    print(f'Writing   : {args.output}')
    write_daily_file(args.output, records, header_info)

    print(f'Report    : {args.report}')
    write_report(args.report, method, report_lines)

    print(f'\nDone — {len(records)} months written.')
    if report_lines:
        print(f'{len(report_lines)} adjustment(s) logged to {args.report}')


if __name__ == '__main__':
    main()
