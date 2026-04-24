"""Entry point for exceed tool."""

import argparse
import sys


def main():
    """Main entry point - GUI or CLI depending on arguments."""
    parser = argparse.ArgumentParser(
        prog='python -m exceed',
        description='Calculate flow frequency (exceedance) curves.',
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
        '--intervals', '-i',
        type=int,
        default=20,
        help='Number of flow intervals for frequency distribution (default: 20)',
    )
    
    args = parser.parse_args()
    
    # Check for GUI mode
    if args.gui:
        try:
            import tkinter as _tk
            _tk.Tk().destroy()  # smoke-test before importing our GUI
        except Exception as exc:
            print(
                f'Cannot open GUI: {exc}\n\n'
                'tkinter is not working with this Python installation.\n'
                'On macOS, fix it with:\n'
                '    brew install python@3.13 python-tk@3.13\n'
                '    python3.13 -m exceed\n\n'
                'To run without a GUI use --no-gui (see --help).',
                file=__import__('sys').stderr,
            )
            raise SystemExit(1)
        
        from .gui import ExceedApp
        app = ExceedApp()
        app.mainloop()
        return
    
    # ── CLI mode ──────────────────────────────────────────────────────
    from .algorithm import calculate_monthly_exceedance
    from .files import read_monthly_file, read_daily_file, write_exceedance_report
    
    if not args.monthly and not args.daily:
        parser.error('At least one input file (--monthly or --daily) is required')
    
    monthly_exceedance = {}
    
    # Process monthly data
    if args.monthly:
        print(f'Reading monthly file: {args.monthly}')
        monthly_data = read_monthly_file(args.monthly)
        
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        
        print(f'Calculating exceedance ({args.intervals} intervals)...')
        for month in range(1, 13):
            if month not in monthly_data or not monthly_data[month]:
                print(f'  {month_names[month]}: no data')
                continue
            
            result = calculate_monthly_exceedance(monthly_data[month], args.intervals)
            monthly_exceedance[month] = {
                'flow_values': result.flow_values,
                'exceedance_pct': result.exceedance_pct,
                'count_above': result.count_above,
                'count_below': result.count_below,
                'total_count': result.total_count,
            }
            print(f'  {month_names[month]}: {result.total_count} values')
    
    # Process daily data
    if args.daily:
        print(f'Reading daily file: {args.daily}')
        daily_data = read_daily_file(args.daily)
        
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        
        print(f'Calculating exceedance ({args.intervals} intervals)...')
        for month in range(1, 13):
            if month not in daily_data or not daily_data[month]:
                print(f'  {month_names[month]}: no data')
                continue
            
            result = calculate_monthly_exceedance(daily_data[month], args.intervals)
            # Store with prefix to distinguish from monthly
            key = f'daily_{month}'
            monthly_exceedance[key] = {
                'flow_values': result.flow_values,
                'exceedance_pct': result.exceedance_pct,
                'count_above': result.count_above,
                'count_below': result.count_below,
                'total_count': result.total_count,
            }
            print(f'  {month_names[month]}: {result.total_count} values')
    
    # Write output report
    if args.output and monthly_exceedance:
        print(f'Writing report: {args.output}')
        write_exceedance_report(args.output, monthly_exceedance)
        print('Done!')
    elif not monthly_exceedance:
        print('No data to analyze', file=sys.stderr)


if __name__ == '__main__':
    main()
