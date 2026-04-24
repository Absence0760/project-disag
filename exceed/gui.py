"""Tkinter GUI for the Exceed tool."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .algorithm import calculate_monthly_exceedance
from .files import read_daily_file, read_monthly_file, write_exceedance_report


class ExceedApp(tk.Tk):
    """Tkinter GUI for flow frequency analysis."""
    
    def __init__(self):
        super().__init__()
        self.title('Flow Frequency (Exceedance) Analysis')
        self.resizable(False, False)
        self._build_ui()
    
    def _build_ui(self):
        """Build the user interface."""
        # ── File inputs ────────────────────────────────────────────────
        files_frame = ttk.LabelFrame(self, text='Input / Output Files')
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
            var = tk.StringVar()
            self._vars[key] = var
            var.trace_add('write', lambda *_: self._validate())
            
            entry = ttk.Entry(files_frame, textvariable=var, width=58, state='readonly')
            entry.grid(row=row, column=1, padx=4, pady=3)
            self._entries[key] = entry
            
            btn = ttk.Button(
                files_frame, text='…', width=3,
                command=lambda k=key, m=mode: self._browse(k, m),
            )
            btn.grid(row=row, column=2, padx=(0, 8), pady=3)
            self._btns[key] = btn
        
        # ── Intervals selection ────────────────────────────────────────
        intervals_frame = ttk.LabelFrame(self, text='Frequency Distribution')
        intervals_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)
        
        ttk.Label(intervals_frame, text='Number of intervals:').grid(
            row=0, column=0, sticky='w', padx=8, pady=5)
        
        self._intervals_var = tk.IntVar(value=20)
        intervals_spin = ttk.Spinbox(
            intervals_frame, from_=5, to=100, textvariable=self._intervals_var,
            width=10)
        intervals_spin.grid(row=0, column=1, sticky='w', padx=8, pady=5)
        
        # ── Status bar ────────────────────────────────────────────────
        self._status_var = tk.StringVar(value='Select files to begin.')
        ttk.Label(self, textvariable=self._status_var,
                  foreground='#555', anchor='w').grid(
            row=2, column=0, sticky='ew', padx=10)
        
        # ── Buttons ───────────────────────────────────────────────────
        btn_bar = ttk.Frame(self)
        btn_bar.grid(row=3, column=0, sticky='ew', padx=10, pady=(2, 10))
        
        ttk.Button(btn_bar, text='Cancel', command=self.destroy).pack(side='left')
        
        self._btn_run = ttk.Button(
            btn_bar, text='Analyze!',
            command=self._run, state='disabled',
        )
        self._btn_run.pack(side='right')
    
    def _browse(self, key: str, mode: str):
        """Browse for a file."""
        initial = os.getcwd()
        
        filetypes_map = {
            'mon': [('Monthly flow files', '*.mon *.nat *.cur'), ('All files', '*.*')],
            'day': [('Daily flow files', '*.day'), ('All files', '*.*')],
            'rep': [('Report files', '*.rep')],
        }
        ext_map = {'rep': '.rep'}
        
        if mode == 'open':
            path = filedialog.askopenfilename(
                initialdir=initial,
                filetypes=filetypes_map.get(key, [('All', '*.*')]))
        else:
            path = filedialog.asksaveasfilename(
                initialdir=initial,
                defaultextension=ext_map.get(key, ''),
                filetypes=filetypes_map.get(key, [('All', '*.*')]),
            )
        
        if path:
            self._vars[key].set(path)
            
            # Auto-fill report file if monthly is chosen
            if key == 'mon' and not self._vars['rep'].get():
                base = os.path.splitext(path)[0]
                self._vars['rep'].set(base + '.rep')
    
    def _validate(self):
        """Validate form and enable/disable run button."""
        has_mon = bool(self._vars['mon'].get()) and os.path.isfile(
            self._vars['mon'].get())
        has_day = bool(self._vars['day'].get()) and os.path.isfile(
            self._vars['day'].get())
        has_rep = bool(self._vars['rep'].get())
        
        ok = (has_mon or has_day) and has_rep
        self._btn_run.config(state='normal' if ok else 'disabled')
    
    def _run(self):
        """Run the exceedance analysis."""
        self._btn_run.config(state='disabled')
        num_intervals = self._intervals_var.get()
        
        try:
            monthly_exceedance = {}
            month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            
            # Process monthly data
            if self._vars['mon'].get():
                self._set_status('Reading monthly file…')
                monthly_data = read_monthly_file(self._vars['mon'].get())
                
                self._set_status('Calculating monthly exceedance…')
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
                self._set_status('Reading daily file…')
                daily_data = read_daily_file(self._vars['day'].get())
                
                self._set_status('Calculating daily exceedance…')
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
            
            self._set_status('Writing report…')
            write_exceedance_report(self._vars['rep'].get(), monthly_exceedance)
            
            msg = f'Done — {len(monthly_exceedance)} analyses written.'
            self._set_status(msg)
            messagebox.showinfo('Analysis complete', msg)
        
        except Exception as exc:
            self._set_status(f'Error: {exc}')
            messagebox.showerror('Error', str(exc))
        finally:
            self._validate()
    
    def _set_status(self, text: str):
        """Update status bar."""
        self._status_var.set(text)
        self.update_idletasks()


if __name__ == '__main__':
    app = ExceedApp()
    app.mainloop()
