"""Tkinter GUI for the Exceed tool with seasonal grouping and matching."""

import os
import subprocess
import sys
from tkinter import (
    BooleanVar,
    DoubleVar,
    IntVar,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)

from .algorithm import (
    calculate_monthly_exceedance,
    calculate_seasonal_exceedance,
    get_season_presets,
)
from .files import (
    read_daily_file,
    read_monthly_file,
    write_exceedance_report,
    write_exceedance_svg,
    write_matching_report,
    write_seasonal_exceedance_report,
)


def _open_in_os(path: str) -> None:
    """Open a file/folder with the platform's default handler."""
    if sys.platform == 'darwin':
        subprocess.run(['open', path], check=False)
    elif os.name == 'nt':
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(['xdg-open', path], check=False)


class _Tooltip:
    """Minimal hover tooltip for a widget (stdlib Tk only)."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self._tip = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, _event=None):
        if self._tip or not self.text:
            return
        from tkinter import Label, Toplevel
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f'+{x}+{y}')
        Label(
            self._tip, text=self.text, justify='left', relief='solid',
            borderwidth=1, background='#ffffe0', padx=6, pady=3,
            wraplength=320,
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ExceedApp(Tk):
    """Tkinter GUI for flow frequency analysis with seasonal and matching support."""
    
    def __init__(self):
        super().__init__()
        self.title('Flow Frequency (Exceedance) Analysis')
        self.resizable(True, True)
        self._last_dir = os.getcwd()
        self._build_ui()

    def _finish(self, status_var, msg: str, report_path: str):
        """Report success and offer to open the report file."""
        status_var.set(msg)
        if report_path and os.path.isfile(report_path):
            if messagebox.askyesno(
                'Analysis complete', f'{msg}\n\nOpen the report now?'):
                _open_in_os(report_path)
        else:
            messagebox.showinfo('Analysis complete', msg)

    @staticmethod
    def _svg_path_for(report_path: str) -> str:
        """SVG path sitting next to the report (same base name)."""
        return os.path.splitext(report_path)[0] + '.svg'
    
    def _build_ui(self):
        """Build the user interface with tabs."""
        # Create main notebook with tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Basic Analysis
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text='Basic')
        self._build_basic_tab(basic_frame)
        
        # Tab 2: Seasonal Analysis
        seasonal_frame = ttk.Frame(notebook)
        notebook.add(seasonal_frame, text='Seasonal')
        self._build_seasonal_tab(seasonal_frame)
        
        # Tab 3: Matching
        matching_frame = ttk.Frame(notebook)
        notebook.add(matching_frame, text='Matching')
        self._build_matching_tab(matching_frame)
    
    def _build_basic_tab(self, parent):
        """Build the basic analysis tab."""
        # ── File inputs ────────────────────────────────────────────────
        files_frame = ttk.LabelFrame(parent, text='Input / Output Files')
        files_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 4))
        
        file_rows = [
            ('Monthly File (optional)', 'mon', 'open'),
            ('Daily File (optional)', 'day', 'open'),
            ('Report File (output)', 'rep', 'save'),
        ]
        
        self._vars = {}
        self._entries = {}
        self._btns = {}
        
        for row, (label, key, mode) in enumerate(file_rows):
            ttk.Label(files_frame, text=label, anchor='w').grid(
                row=row, column=0, sticky='w', padx=(8, 4), pady=3)
            var = StringVar()
            self._vars[key] = var
            var.trace_add('write', lambda *_: self._validate_basic())
            
            entry = ttk.Entry(files_frame, textvariable=var, width=50, state='readonly')
            entry.grid(row=row, column=1, padx=4, pady=3)
            self._entries[key] = entry
            
            btn = ttk.Button(
                files_frame, text='…', width=3,
                command=lambda k=key, m=mode: self._browse(k, m),
            )
            btn.grid(row=row, column=2, padx=(0, 8), pady=3)
            self._btns[key] = btn
        
        # ── Intervals selection ────────────────────────────────────────
        intervals_frame = ttk.LabelFrame(parent, text='Frequency Distribution')
        intervals_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        
        ttk.Label(intervals_frame, text='Number of intervals:').grid(
            row=0, column=0, sticky='w', padx=8, pady=5)
        
        self._intervals_var = IntVar(value=20)
        intervals_spin = ttk.Spinbox(
            intervals_frame, from_=5, to=100, textvariable=self._intervals_var,
            width=10)
        intervals_spin.grid(row=0, column=1, sticky='w', padx=8, pady=5)
        _Tooltip(intervals_spin,
                 'How many flow bands the range is split into. More '
                 'intervals = finer curve, but needs more data per band.')

        self._basic_svg_var = BooleanVar(value=False)
        ttk.Checkbutton(
            intervals_frame, text='Also save a flow-frequency chart (.svg)',
            variable=self._basic_svg_var,
        ).grid(row=1, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 5))

        # ── Status bar ────────────────────────────────────────────────
        self._status_var = StringVar(value='Select files to begin.')
        ttk.Label(parent, textvariable=self._status_var,
                  foreground='#555', anchor='w').grid(
            row=2, column=0, sticky='ew', padx=10)
        
        # ── Buttons ───────────────────────────────────────────────────
        btn_bar = ttk.Frame(parent)
        btn_bar.grid(row=3, column=0, sticky='ew', padx=10, pady=(2, 10))
        
        ttk.Button(btn_bar, text='Cancel', command=self.destroy).pack(side='left')
        
        self._btn_basic = ttk.Button(
            btn_bar, text='Analyze!',
            command=self._run_basic, state='disabled',
        )
        self._btn_basic.pack(side='right')
    
    def _build_seasonal_tab(self, parent):
        """Build the seasonal analysis tab."""
        # ── File inputs ────────────────────────────────────────────────
        files_frame = ttk.LabelFrame(parent, text='Input / Output Files')
        files_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=10, pady=(10, 4))
        
        ttk.Label(files_frame, text='Monthly File:', anchor='w').grid(
            row=0, column=0, sticky='w', padx=(8, 4), pady=3)
        self._seasonal_mon_var = StringVar()
        self._seasonal_mon_var.trace_add('write', lambda *_: self._validate_seasonal())
        entry = ttk.Entry(files_frame, textvariable=self._seasonal_mon_var, width=50, state='readonly')
        entry.grid(row=0, column=1, padx=4, pady=3)
        ttk.Button(
            files_frame, text='…', width=3,
            command=lambda: self._browse_seasonal_monthly(),
        ).grid(row=0, column=2, padx=(0, 8), pady=3)
        
        ttk.Label(files_frame, text='Report File:', anchor='w').grid(
            row=1, column=0, sticky='w', padx=(8, 4), pady=3)
        self._seasonal_rep_var = StringVar()
        self._seasonal_rep_var.trace_add('write', lambda *_: self._validate_seasonal())
        entry = ttk.Entry(files_frame, textvariable=self._seasonal_rep_var, width=50, state='readonly')
        entry.grid(row=1, column=1, padx=4, pady=3)
        ttk.Button(
            files_frame, text='…', width=3,
            command=lambda: self._browse_seasonal_report(),
        ).grid(row=1, column=2, padx=(0, 8), pady=3)
        
        # ── Season configuration ────────────────────────────────────────
        config_frame = ttk.LabelFrame(parent, text='Season Configuration')
        config_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        
        ttk.Label(config_frame, text='Seasons:').grid(row=0, column=0, sticky='w', padx=8, pady=5)

        self._season_preset_var = StringVar(value='2')
        preset_menu = ttk.Combobox(
            config_frame, textvariable=self._season_preset_var,
            values=['2', '3', '4'], state='readonly', width=5)
        preset_menu.grid(row=0, column=1, sticky='w', padx=8, pady=5)
        preset_menu.bind('<<ComboboxSelected>>', lambda e: self._update_season_config())

        ttk.Label(
            config_frame,
            text='Pick a preset, then tick/untick months to customise.',
            foreground='#555',
        ).grid(row=0, column=2, sticky='w', padx=8, pady=5)
        
        # Season detail frame (will be populated dynamically)
        self._season_detail_frame = ttk.Frame(config_frame)
        self._season_detail_frame.grid(row=1, column=0, columnspan=3, sticky='ew', padx=8, pady=5)
        
        self._season_definitions = {}  # Will hold {season_name: {month: BooleanVar}}
        
        # Load default 2-season
        self._load_season_preset()

        # ── Intervals selection ────────────────────────────────────────
        intervals_frame = ttk.LabelFrame(parent, text='Frequency Distribution')
        intervals_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=5)

        ttk.Label(intervals_frame, text='Number of intervals:').grid(
            row=0, column=0, sticky='w', padx=8, pady=5)

        self._seasonal_intervals_var = IntVar(value=20)
        seasonal_spin = ttk.Spinbox(
            intervals_frame, from_=5, to=100,
            textvariable=self._seasonal_intervals_var, width=10,
        )
        seasonal_spin.grid(row=0, column=1, sticky='w', padx=8, pady=5)
        _Tooltip(seasonal_spin,
                 'How many flow bands the range is split into. More '
                 'intervals = finer curve, but needs more data per band.')

        self._seasonal_svg_var = BooleanVar(value=False)
        ttk.Checkbutton(
            intervals_frame, text='Also save a flow-frequency chart (.svg)',
            variable=self._seasonal_svg_var,
        ).grid(row=1, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 5))

        # ── Status and button ───────────────────────────────────────────
        self._seasonal_status_var = StringVar(value='Configure seasons and select files.')
        ttk.Label(parent, textvariable=self._seasonal_status_var,
                  foreground='#555', anchor='w').grid(
            row=3, column=0, columnspan=2, sticky='ew', padx=10)

        btn_bar = ttk.Frame(parent)
        btn_bar.grid(row=4, column=0, columnspan=2, sticky='ew', padx=10, pady=(2, 10))
        
        ttk.Button(btn_bar, text='Cancel', command=self.destroy).pack(side='left')
        
        self._btn_seasonal = ttk.Button(
            btn_bar, text='Analyze Seasons!',
            command=self._run_seasonal, state='disabled',
        )
        self._btn_seasonal.pack(side='right')
    
    def _build_matching_tab(self, parent):
        """Build the matching analysis tab."""
        # ── File inputs ────────────────────────────────────────────────
        files_frame = ttk.LabelFrame(parent, text='Input / Output Files')
        files_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 4))
        
        file_rows = [
            ('Monthly File', 'match_mon', 'open'),
            ('Daily File', 'match_day', 'open'),
            ('Report File (output)', 'match_rep', 'save'),
        ]
        
        self._match_vars = {}
        self._match_entries = {}
        
        for row, (label, key, mode) in enumerate(file_rows):
            ttk.Label(files_frame, text=label, anchor='w').grid(
                row=row, column=0, sticky='w', padx=(8, 4), pady=3)
            var = StringVar()
            self._match_vars[key] = var
            var.trace_add('write', lambda *_: self._validate_matching())
            
            entry = ttk.Entry(files_frame, textvariable=var, width=50, state='readonly')
            entry.grid(row=row, column=1, padx=4, pady=3)
            self._match_entries[key] = entry
            
            btn = ttk.Button(
                files_frame, text='…', width=3,
                command=lambda k=key, m=mode: self._browse_matching(k, m),
            )
            btn.grid(row=row, column=2, padx=(0, 8), pady=3)
        
        # ── Analysis options ───────────────────────────────────────────
        options_frame = ttk.LabelFrame(parent, text='Analysis Options')
        options_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        
        ttk.Label(options_frame, text='Tolerance (% exceedance):').grid(
            row=0, column=0, sticky='w', padx=8, pady=5)
        self._tolerance_var = DoubleVar(value=5.0)
        tol_spin = ttk.Spinbox(options_frame, from_=0.1, to=50,
                               textvariable=self._tolerance_var, width=10)
        tol_spin.grid(row=0, column=1, sticky='w', padx=8, pady=5)
        _Tooltip(tol_spin,
                 'Pair a monthly and a daily flow when their exceedance '
                 'percentiles agree within this many percent.')
        
        ttk.Label(options_frame, text='Intervals:').grid(row=0, column=2, sticky='w', padx=8, pady=5)
        self._match_intervals_var = IntVar(value=20)
        ttk.Spinbox(options_frame, from_=5, to=100, textvariable=self._match_intervals_var,
                   width=10).grid(row=0, column=3, sticky='w', padx=8, pady=5)
        
        # ── Status bar ────────────────────────────────────────────────
        self._match_status_var = StringVar(value='Select files to begin.')
        ttk.Label(parent, textvariable=self._match_status_var,
                  foreground='#555', anchor='w').grid(
            row=2, column=0, sticky='ew', padx=10)
        
        # ── Buttons ───────────────────────────────────────────────────
        btn_bar = ttk.Frame(parent)
        btn_bar.grid(row=3, column=0, sticky='ew', padx=10, pady=(2, 10))
        
        ttk.Button(btn_bar, text='Cancel', command=self.destroy).pack(side='left')
        
        self._btn_match = ttk.Button(
            btn_bar, text='Match Exceedance!',
            command=self._run_matching, state='disabled',
        )
        self._btn_match.pack(side='right')
    
    def _browse(self, key: str, mode: str):
        """Browse for a file (basic tab)."""
        filetypes_map = {
            'mon': [('Monthly flow files', '*.mon *.nat *.cur'), ('All files', '*.*')],
            'day': [('Daily flow files', '*.day'), ('All files', '*.*')],
            'rep': [('Report files', '*.rep')],
        }
        ext_map = {'rep': '.rep'}

        if mode == 'open':
            path = filedialog.askopenfilename(
                initialdir=self._last_dir,
                filetypes=filetypes_map.get(key, [('All', '*.*')]))
        else:
            path = filedialog.asksaveasfilename(
                initialdir=self._last_dir,
                defaultextension=ext_map.get(key, ''),
                filetypes=filetypes_map.get(key, [('All', '*.*')]),
            )

        if path:
            self._last_dir = os.path.dirname(path)
            self._vars[key].set(path)
            # Suggest a report name from the first input file chosen.
            if key in ('mon', 'day') and not self._vars['rep'].get():
                base = os.path.splitext(path)[0]
                self._vars['rep'].set(base + '.rep')

    def _browse_seasonal_monthly(self):
        """Browse for monthly file (seasonal tab)."""
        path = filedialog.askopenfilename(
            initialdir=self._last_dir,
            filetypes=[('Monthly flow files', '*.mon *.nat *.cur'), ('All files', '*.*')])
        if path:
            self._last_dir = os.path.dirname(path)
            self._seasonal_mon_var.set(path)

    def _browse_seasonal_report(self):
        """Browse for report file (seasonal tab)."""
        path = filedialog.asksaveasfilename(
            initialdir=self._last_dir,
            defaultextension='.rep',
            filetypes=[('Report files', '*.rep')])
        if path:
            self._last_dir = os.path.dirname(path)
            self._seasonal_rep_var.set(path)

    def _browse_matching(self, key: str, mode: str):
        """Browse for a file (matching tab)."""
        filetypes_map = {
            'match_mon': [('Monthly flow files', '*.mon *.nat *.cur'), ('All files', '*.*')],
            'match_day': [('Daily flow files', '*.day'), ('All files', '*.*')],
            'match_rep': [('Report files', '*.rep')],
        }
        ext_map = {'match_rep': '.rep'}

        if mode == 'open':
            path = filedialog.askopenfilename(
                initialdir=self._last_dir,
                filetypes=filetypes_map.get(key, [('All', '*.*')]))
        else:
            path = filedialog.asksaveasfilename(
                initialdir=self._last_dir,
                defaultextension=ext_map.get(key, ''),
                filetypes=filetypes_map.get(key, [('All', '*.*')]),
            )

        if path:
            self._last_dir = os.path.dirname(path)
            self._match_vars[key].set(path)
    
    def _load_season_preset(self):
        """Load selected season preset."""
        num_seasons = int(self._season_preset_var.get())
        presets = get_season_presets(num_seasons)
        self._season_definitions = {}
        
        # Clear previous season detail frame
        for widget in self._season_detail_frame.winfo_children():
            widget.destroy()
        
        # Create checkboxes for each month per season
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for season_idx, (season_name, season_months) in enumerate(presets.items()):
            # Season label
            ttk.Label(self._season_detail_frame, text=f'{season_name}:',
                     font=('', 10, 'bold')).grid(row=season_idx, column=0, sticky='w', padx=4, pady=3)
            
            # Month checkboxes
            month_frame = ttk.Frame(self._season_detail_frame)
            month_frame.grid(row=season_idx, column=1, columnspan=2, sticky='ew', padx=4, pady=3)
            
            season_vars = {}
            for month_num in range(1, 13):
                is_in_season = month_num in season_months
                var = BooleanVar(value=is_in_season)
                season_vars[month_num] = var
                
                cb = ttk.Checkbutton(month_frame, text=months[month_num-1], variable=var)
                cb.pack(side='left', padx=2)
            
            self._season_definitions[season_name] = season_vars
    
    def _update_season_config(self):
        """Update season configuration when preset changes."""
        self._load_season_preset()
    
    def _validate_basic(self):
        """Validate basic tab form."""
        has_mon = bool(self._vars['mon'].get()) and os.path.isfile(self._vars['mon'].get())
        has_day = bool(self._vars['day'].get()) and os.path.isfile(self._vars['day'].get())
        has_rep = bool(self._vars['rep'].get())
        
        ok = (has_mon or has_day) and has_rep
        self._btn_basic.config(state='normal' if ok else 'disabled')
    
    def _validate_seasonal(self):
        """Validate seasonal tab form."""
        has_mon = (bool(self._seasonal_mon_var.get()) and
                  os.path.isfile(self._seasonal_mon_var.get()))
        has_rep = bool(self._seasonal_rep_var.get())
        
        ok = has_mon and has_rep
        self._btn_seasonal.config(state='normal' if ok else 'disabled')
    
    def _validate_matching(self):
        """Validate matching tab form."""
        has_mon = (bool(self._match_vars['match_mon'].get()) and
                  os.path.isfile(self._match_vars['match_mon'].get()))
        has_day = (bool(self._match_vars['match_day'].get()) and
                  os.path.isfile(self._match_vars['match_day'].get()))
        has_rep = bool(self._match_vars['match_rep'].get())
        
        ok = has_mon and has_day and has_rep
        self._btn_match.config(state='normal' if ok else 'disabled')
    
    def _run_basic(self):
        """Run basic exceedance analysis."""
        self._btn_basic.config(state='disabled')
        num_intervals = self._intervals_var.get()
        
        try:
            monthly_exceedance = {}

            # Process monthly data
            if self._vars['mon'].get():
                self._status_var.set('Reading monthly file…')
                monthly_data = read_monthly_file(self._vars['mon'].get())
                
                self._status_var.set('Calculating monthly exceedance…')
                for month in range(1, 13):
                    if month in monthly_data and monthly_data[month]:
                        result = calculate_monthly_exceedance(
                            monthly_data[month], num_intervals)
                        monthly_exceedance[month] = {
                            'flow_values': result.flow_values,
                            'exceedance_pct': result.exceedance_pct,
                            'count_above': result.count_above,
                            'count_below': result.count_below,
                            'total_count': result.total_count,
                        }
            
            # Process daily data
            if self._vars['day'].get():
                self._status_var.set('Reading daily file…')
                daily_data = read_daily_file(self._vars['day'].get())
                
                self._status_var.set('Calculating daily exceedance…')
                for month in range(1, 13):
                    if month in daily_data and daily_data[month]:
                        result = calculate_monthly_exceedance(
                            daily_data[month], num_intervals)
                        key = f'daily_{month}'
                        monthly_exceedance[key] = {
                            'flow_values': result.flow_values,
                            'exceedance_pct': result.exceedance_pct,
                            'count_above': result.count_above,
                            'count_below': result.count_below,
                            'total_count': result.total_count,
                        }
            
            if not monthly_exceedance:
                raise ValueError('No usable flow data found in the input file(s).')

            report_path = self._vars['rep'].get()
            self._status_var.set('Writing report…')
            write_exceedance_report(report_path, monthly_exceedance)

            extra = ''
            if self._basic_svg_var.get():
                svg_path = self._svg_path_for(report_path)
                self._status_var.set('Writing chart…')
                write_exceedance_svg(svg_path, monthly_exceedance)
                extra = f'  Chart: {os.path.basename(svg_path)}'

            msg = f'Done — {len(monthly_exceedance)} analyses written.{extra}'
            self._finish(self._status_var, msg, report_path)

        except Exception as exc:
            self._status_var.set(f'Error: {exc}')
            messagebox.showerror('Error', str(exc))
        finally:
            self._validate_basic()
    
    def _run_seasonal(self):
        """Run seasonal exceedance analysis."""
        self._btn_seasonal.config(state='disabled')
        
        try:
            self._seasonal_status_var.set('Reading monthly file…')
            monthly_data = read_monthly_file(self._seasonal_mon_var.get())
            
            self._seasonal_status_var.set('Calculating seasonal exceedance…')
            num_intervals = self._seasonal_intervals_var.get()
            
            # Build seasons dict from checkboxes
            seasons = {}
            for season_name, month_vars in self._season_definitions.items():
                months = [m for m in range(1, 13) if month_vars[m].get()]
                if months:
                    seasons[season_name] = months
            
            if not seasons:
                messagebox.showerror('Error', 'No months selected for any season')
                self._validate_seasonal()
                return
            
            # Calculate seasonal exceedance
            seasonal_results = calculate_seasonal_exceedance(monthly_data, seasons, num_intervals)
            
            # Format for output
            seasonal_exceedance = {}
            for season_name, result in seasonal_results.items():
                seasonal_exceedance[season_name] = {
                    'flow_values': result.flow_values,
                    'exceedance_pct': result.exceedance_pct,
                    'count_above': result.count_above,
                    'count_below': result.count_below,
                    'total_count': result.total_count,
                }
            
            report_path = self._seasonal_rep_var.get()
            self._seasonal_status_var.set('Writing report…')
            write_seasonal_exceedance_report(report_path, seasonal_exceedance)

            extra = ''
            if self._seasonal_svg_var.get():
                svg_path = self._svg_path_for(report_path)
                self._seasonal_status_var.set('Writing chart…')
                write_exceedance_svg(svg_path, seasonal_exceedance,
                                     title='Seasonal flow-frequency curve')
                extra = f'  Chart: {os.path.basename(svg_path)}'

            msg = (f'Done — {len(seasonal_exceedance)} seasonal analyses '
                   f'written.{extra}')
            self._finish(self._seasonal_status_var, msg, report_path)

        except Exception as exc:
            self._seasonal_status_var.set(f'Error: {exc}')
            messagebox.showerror('Error', str(exc))
        finally:
            self._validate_seasonal()
    
    def _run_matching(self):
        """Run exceedance matching analysis."""
        self._btn_match.config(state='disabled')
        
        try:
            self._match_status_var.set('Reading monthly file…')
            monthly_data = read_monthly_file(self._match_vars['match_mon'].get())
            
            self._match_status_var.set('Reading daily file…')
            daily_data = read_daily_file(self._match_vars['match_day'].get())
            
            num_intervals = self._match_intervals_var.get()
            tolerance = self._tolerance_var.get()

            self._match_status_var.set('Calculating exceedance and matching…')

            report_path = self._match_vars['match_rep'].get()
            total_matches = write_matching_report(
                report_path, monthly_data, daily_data, num_intervals, tolerance)

            msg = f'Done — {total_matches} matches found.'
            self._finish(self._match_status_var, msg, report_path)

        except Exception as exc:
            self._match_status_var.set(f'Error: {exc}')
            messagebox.showerror('Error', str(exc))
        finally:
            self._validate_matching()


if __name__ == '__main__':
    app = ExceedApp()
    app.mainloop()
