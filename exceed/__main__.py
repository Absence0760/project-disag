"""Entry point for exceed tool.

GUI mode (default)
------------------
    python -m exceed

CLI mode
--------
    # Basic: one exceedance curve per calendar month
    python -m exceed --no-gui --monthly file.mon --output out.rep
    python -m exceed --no-gui --daily file.day  --output out.rep --svg out.svg

    # Seasonal: pool calendar months into 2, 3, or 4 seasons
    python -m exceed --no-gui --monthly file.mon --seasonal 2 --output out.rep

    # Matching: pair monthly vs daily exceedance percentiles
    python -m exceed --no-gui --monthly file.mon --daily file.day \\
        --match --tolerance 5 --output out.rep
"""

import argparse
import sys

MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def _positive_int(text: str) -> int:
    """argparse type: an integer >= 1 (used for --intervals)."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f'expected an integer, got {text!r}')
    if value < 1:
        raise argparse.ArgumentTypeError(
            f'must be >= 1, got {value}')
    return value


def main():
    """Main entry point - GUI or CLI depending on arguments."""
    parser = argparse.ArgumentParser(
        prog='python -m exceed',
        description='Calculate flow frequency (exceedance) curves.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--no-gui', dest='gui', action='store_false', default=True,
        help='Run in command-line mode (default: open GUI)',
    )
    parser.add_argument(
        '--monthly', '-m',
        help='Monthly input file (.mon/.nat/.cur)',
    )
    parser.add_argument(
        '--daily', '-d',
        help='Daily input file (.day)',
    )
    parser.add_argument(
        '--output', '-o',
        help='Output report file (.rep)',
    )
    parser.add_argument(
        '--svg',
        help='Also write a flow-frequency chart to this path (.svg)',
    )
    parser.add_argument(
        '--intervals', '-i',
        type=_positive_int,
        default=20,
        metavar='N',
        help='Number of flow intervals for the distribution (default: 20)',
    )
    parser.add_argument(
        '--seasonal', type=int, choices=(2, 3, 4), metavar='{2,3,4}',
        help='Group calendar months into N seasons (needs --monthly)',
    )
    parser.add_argument(
        '--match', action='store_true',
        help='Pair monthly vs daily exceedance percentiles '
             '(needs --monthly and --daily)',
    )
    parser.add_argument(
        '--tolerance', '-t', type=float, default=5.0, metavar='PCT',
        help='Exceedance%% tolerance for --match (default: 5.0)',
    )

    args = parser.parse_args()

    # Check for GUI mode
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
                '    brew install python@3.14 python-tk@3.14\n'
                '    python3.14 -m exceed\n\n'
                'To run without a GUI use --no-gui (see --help).',
                file=sys.stderr,
            )
            raise SystemExit(1)

        from .gui import ExceedApp
        app = ExceedApp()
        app.mainloop()
        return

    # ── CLI mode ──────────────────────────────────────────────────────
    try:
        _run_cli(parser, args)
    except FileNotFoundError as exc:
        parser.exit(1, f'Error: input file not found: {exc.filename}\n')
    except (ValueError, OSError) as exc:
        # Clean one-line message instead of a raw traceback for the
        # common "bad/unreadable file" and "no usable data" cases.
        parser.exit(1, f'Error: {exc}\n')


def _run_cli(parser, args):
    """CLI dispatch — basic, seasonal, or matching."""
    from .algorithm import (
        calculate_monthly_exceedance,
        calculate_seasonal_exceedance,
        get_season_presets,
    )
    from .files import (
        read_monthly_file,
        read_daily_file,
        write_exceedance_report,
        write_exceedance_svg,
        write_matching_report,
        write_seasonal_exceedance_report,
    )

    # ── Matching mode ─────────────────────────────────────────────────
    if args.match:
        if not (args.monthly and args.daily):
            parser.error('--match requires both --monthly and --daily')
        if not args.output:
            parser.error('--match requires --output')
        print(f'Reading monthly file: {args.monthly}')
        monthly_data = read_monthly_file(args.monthly)
        print(f'Reading daily file: {args.daily}')
        daily_data = read_daily_file(args.daily)
        print(f'Matching exceedance (tolerance {args.tolerance:g}%)…')
        total = write_matching_report(
            args.output, monthly_data, daily_data,
            args.intervals, args.tolerance)
        print(f'Writing report: {args.output}')
        print(f'Done — {total} matches found.')
        return

    # ── Seasonal mode ─────────────────────────────────────────────────
    if args.seasonal:
        if not args.monthly:
            parser.error('--seasonal requires --monthly')
        if not args.output:
            parser.error('--seasonal requires --output')
        print(f'Reading monthly file: {args.monthly}')
        monthly_data = read_monthly_file(args.monthly)
        seasons = get_season_presets(args.seasonal)
        print(f'Calculating {args.seasonal}-season exceedance '
              f'({args.intervals} intervals)…')
        seasonal_results = calculate_seasonal_exceedance(
            monthly_data, seasons, args.intervals)
        seasonal_exceedance = {
            name: {
                'flow_values': r.flow_values,
                'exceedance_pct': r.exceedance_pct,
                'count_above': r.count_above,
                'count_below': r.count_below,
                'total_count': r.total_count,
            }
            for name, r in seasonal_results.items()
        }
        for name, r in seasonal_results.items():
            print(f'  {name}: {r.total_count} values')
        if not seasonal_exceedance:
            raise ValueError('no usable monthly data for any season')
        print(f'Writing report: {args.output}')
        write_seasonal_exceedance_report(args.output, seasonal_exceedance)
        if args.svg:
            print(f'Writing chart: {args.svg}')
            write_exceedance_svg(args.svg, seasonal_exceedance,
                                 title='Seasonal flow-frequency curve')
        print('Done!')
        return

    # ── Basic mode ────────────────────────────────────────────────────
    if not args.monthly and not args.daily:
        parser.error('At least one input file (--monthly or --daily) is required')

    monthly_exceedance = {}

    if args.monthly:
        print(f'Reading monthly file: {args.monthly}')
        monthly_data = read_monthly_file(args.monthly)
        print(f'Calculating exceedance ({args.intervals} intervals)...')
        for month in range(1, 13):
            if month not in monthly_data or not monthly_data[month]:
                print(f'  {MONTH_NAMES[month]}: no data')
                continue
            result = calculate_monthly_exceedance(
                monthly_data[month], args.intervals)
            monthly_exceedance[month] = {
                'flow_values': result.flow_values,
                'exceedance_pct': result.exceedance_pct,
                'count_above': result.count_above,
                'count_below': result.count_below,
                'total_count': result.total_count,
            }
            print(f'  {MONTH_NAMES[month]}: {result.total_count} values')

    if args.daily:
        print(f'Reading daily file: {args.daily}')
        daily_data = read_daily_file(args.daily)
        print(f'Calculating exceedance ({args.intervals} intervals)...')
        for month in range(1, 13):
            if month not in daily_data or not daily_data[month]:
                print(f'  {MONTH_NAMES[month]}: no data')
                continue
            result = calculate_monthly_exceedance(
                daily_data[month], args.intervals)
            monthly_exceedance[f'daily_{month}'] = {
                'flow_values': result.flow_values,
                'exceedance_pct': result.exceedance_pct,
                'count_above': result.count_above,
                'count_below': result.count_below,
                'total_count': result.total_count,
            }
            print(f'  {MONTH_NAMES[month]}: {result.total_count} values')

    if not monthly_exceedance:
        raise ValueError('no usable flow data found in the input file(s)')

    if not args.output and not args.svg:
        print(
            'WARNING: analysis complete but nothing was written — pass '
            '--output FILE.rep\n         (and/or --svg FILE.svg) to save '
            'the results.',
            file=sys.stderr,
        )
        return

    if args.output:
        print(f'Writing report: {args.output}')
        write_exceedance_report(args.output, monthly_exceedance)
    if args.svg:
        print(f'Writing chart: {args.svg}')
        write_exceedance_svg(args.svg, monthly_exceedance)
    print('Done!')


if __name__ == '__main__':
    main()
