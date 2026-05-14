"""Tkinter GUI for the Disag tool."""

# Lazy annotation evaluation (PEP 563) so PEP 585 generic-builtin
# annotations like dict[str, tk.StringVar] work on Python 3.8.
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .algorithm import (
    METHOD_LABELS,
    METHOD_NAMES,
    NO_FILES,
    DisagMethod,
    count_coverage,
    disaggregate,
)
from .convert import ans_to_mon
from .files import read_daily_file, read_monthly_file, write_daily_file
from .report import write_report


class DisagApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Disaggregate NS Monthly Flows to Daily Flows')
        self.resizable(False, False)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── File inputs ────────────────────────────────────────────────
        files_frame = ttk.LabelFrame(self, text='Input / Output Files')
        files_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 4))

        file_rows = [
            ('NS Monthly File (to be disaggregated)', 'mon',    'open',  True),
            ('NS Daily File 1',                       'day1',   'open',  True),
            ('NS Daily File 2',                       'day2',   'open',  True),
            ('Disaggregated Daily File (output)',     'dayout', 'save',  True),
            ('Report File (output)',                  'rep',    'save',  True),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        self._entries: dict[str, ttk.Entry] = {}
        self._btns: dict[str, ttk.Button] = {}

        for row, (label, key, mode, _) in enumerate(file_rows):
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

        # Utility row: convert a Pitman Model .ANS into a NinhamShand .MON
        # and auto-fill the monthly file picker with the result.
        ttk.Button(
            files_frame, text='Convert .ANS to .MON…',
            command=self._convert_ans,
        ).grid(row=len(file_rows), column=1, sticky='e', padx=4, pady=(2, 6))

        # ── Method selection ───────────────────────────────────────────
        method_frame = ttk.LabelFrame(self, text='Disaggregation Method')
        method_frame.grid(row=1, column=0, sticky='ew', padx=10, pady=5)

        self._method_var = tk.IntVar(value=0)
        for i, label in enumerate(METHOD_LABELS.values()):
            rb = ttk.Radiobutton(
                method_frame, text=label,
                variable=self._method_var, value=i,
                command=self._on_method_change,
            )
            rb.grid(row=i, column=0, sticky='w', padx=8, pady=2)

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
            btn_bar, text='Disaggregate!',
            command=self._run, state='disabled',
        )
        self._btn_run.pack(side='right')

        self._on_method_change()

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse(self, key: str, mode: str):
        initial = (
            os.path.dirname(self._vars['mon'].get())
            or os.path.dirname(self._vars.get('day1', tk.StringVar()).get())
            or os.getcwd()
        )

        filetypes_map = {
            'mon':    [('NS monthly flow files', '*.mon *.nat *.cur'), ('All files', '*.*')],
            'day1':   [('NS daily flow files', '*.day'), ('All files', '*.*')],
            'day2':   [('NS daily flow files', '*.day'), ('All files', '*.*')],
            'dayout': [('NS daily flow files', '*.day')],
            'rep':    [('Text report files', '*.rep')],
        }
        ext_map = {'dayout': '.day', 'rep': '.rep'}

        if mode == 'open':
            path = filedialog.askopenfilename(
                initialdir=initial, filetypes=filetypes_map.get(key, [('All', '*.*')]))
        else:
            path = filedialog.asksaveasfilename(
                initialdir=initial,
                defaultextension=ext_map.get(key, ''),
                filetypes=filetypes_map.get(key, [('All', '*.*')]),
            )

        if not path:
            return

        self._vars[key].set(path)

        # Auto-fill output paths when the monthly file is chosen
        if key == 'mon':
            base = os.path.splitext(path)[0]
            if not self._vars['dayout'].get():
                self._vars['dayout'].set(base + '.day')
            if not self._vars['rep'].get():
                self._vars['rep'].set(base + '.rep')

    # ------------------------------------------------------------------
    # Pitman .ANS → NinhamShand .MON conversion
    # ------------------------------------------------------------------

    def _convert_ans(self):
        initial = (
            os.path.dirname(self._vars['mon'].get())
            or os.path.dirname(self._vars.get('day1', tk.StringVar()).get())
            or os.getcwd()
        )

        src = filedialog.askopenfilename(
            title='Select Pitman Model .ANS file',
            initialdir=initial,
            filetypes=[('Pitman .ANS files', '*.ANS *.ans'), ('All files', '*.*')],
        )
        if not src:
            return

        default_dst = os.path.splitext(src)[0] + '.MON'
        dst = filedialog.asksaveasfilename(
            title='Save NinhamShand .MON file as',
            initialdir=os.path.dirname(default_dst),
            initialfile=os.path.basename(default_dst),
            defaultextension='.MON',
            filetypes=[('NS monthly flow files', '*.mon *.MON'), ('All files', '*.*')],
        )
        if not dst:
            return

        try:
            result = ans_to_mon(src, dst)
        except Exception as exc:
            messagebox.showerror('Conversion failed', str(exc))
            return

        self._vars['mon'].set(dst)  # auto-fill so the user can run immediately
        msg = (
            f'Wrote {result.rows_written} hydro-year rows '
            f'({result.first_year}–{result.last_year}) to:\n{dst}'
        )
        if result.skipped:
            msg += (
                f'\n\nSkipped {len(result.skipped)} non-data line(s) '
                '(blank lines / AVERAGE summary).'
            )
        messagebox.showinfo('Conversion complete', msg)

    # ------------------------------------------------------------------
    # Method-change callback
    # ------------------------------------------------------------------

    def _on_method_change(self):
        method = DisagMethod(self._method_var.get())
        needs_day1 = method != DisagMethod.EVEN
        # PATCH_EXCEED accepts file 2 but doesn't require it
        accepts_day2 = method in (
            DisagMethod.PATCH_FILE,
            DisagMethod.INCREMENTAL,
            DisagMethod.PATCH_EXCEED,
        )

        # Enable / disable the day1 and day2 rows
        for key, enabled in (('day1', needs_day1), ('day2', accepts_day2)):
            state = 'normal' if enabled else 'disabled'
            self._btns[key].config(state=state)
            # Entries are readonly but we can visually grey them out
            self._entries[key].config(
                style='TEntry' if enabled else 'Disabled.TEntry')

        # Clear the status bar so a stale "Done — N/M" from a previous run
        # doesn't look like it applies to the now-selected method.
        self._set_status('Method changed — click Disaggregate! to run.')
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self):
        method = DisagMethod(self._method_var.get())
        needs_day1 = method != DisagMethod.EVEN
        needs_day2 = method in (DisagMethod.PATCH_FILE, DisagMethod.INCREMENTAL)

        ok = bool(self._vars['mon'].get()) and os.path.isfile(self._vars['mon'].get())
        if needs_day1:
            ok = ok and bool(self._vars['day1'].get()) and os.path.isfile(
                self._vars['day1'].get())
        if needs_day2:
            ok = ok and bool(self._vars['day2'].get()) and os.path.isfile(
                self._vars['day2'].get())
        ok = ok and bool(self._vars['dayout'].get())
        ok = ok and bool(self._vars['rep'].get())

        self._btn_run.config(state='normal' if ok else 'disabled')

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _run(self):
        self._btn_run.config(state='disabled')
        method = DisagMethod(self._method_var.get())
        min_files = NO_FILES[method]

        # PATCH_EXCEED accepts an optional file 2 — if the user picked one,
        # treat the run as 2-file (otherwise stick to the method's minimum).
        use_day2 = min_files >= 2 or (
            method == DisagMethod.PATCH_EXCEED
            and bool(self._vars['day2'].get())
            and os.path.isfile(self._vars['day2'].get())
        )
        no_files = 2 if use_day2 else min_files

        try:
            self._set_status('Reading monthly file…')
            gen_monthly = read_monthly_file(self._vars['mon'].get())

            obs_daily = [{}, {}]
            if no_files >= 1:
                self._set_status('Reading daily file 1…')
                obs_daily[0] = read_daily_file(self._vars['day1'].get())
            if use_day2:
                self._set_status('Reading daily file 2…')
                obs_daily[1] = read_daily_file(self._vars['day2'].get())

            self._set_status('Disaggregating…')
            records, report_lines = disaggregate(method, gen_monthly, obs_daily, no_files)

            self._set_status('Writing output file…')
            header_info = {
                'monthly_file': os.path.basename(self._vars['mon'].get()),
                'daily_file_1': (os.path.basename(self._vars['day1'].get())
                                 if no_files >= 1 else ''),
                'daily_file_2': (os.path.basename(self._vars['day2'].get())
                                 if use_day2 else ''),
                'method_str': METHOD_NAMES[method],
            }
            write_daily_file(self._vars['dayout'].get(), records, header_info)

            self._set_status('Writing report…')
            write_report(self._vars['rep'].get(), method, report_lines, records)

            disagg, missing = count_coverage(records)
            pct_missing = (missing / len(records) * 100) if records else 0
            msg = (f'Done — {len(records)} months written\n'
                   f'  Disaggregated: {disagg}\n'
                   f'  Missing:       {missing} ({pct_missing:.0f}%)')
            if report_lines:
                msg += f'\n  Adjustments logged: {len(report_lines)}'
            self._set_status(f'Done — {disagg}/{len(records)} months disaggregated.')

            if pct_missing > 50 and method == DisagMethod.ONE_FILE:
                msg += (f'\n\nWARNING: most months are missing because the daily '
                        f'input has gaps and Method 0 drops any month with even '
                        f'one missing day. Try Method 1 (closest-volume similar '
                        f'month) or Method 5 (exceedance-percentile match) to '
                        f'patch missing days.')
                messagebox.showwarning('Disaggregation complete', msg)
            else:
                messagebox.showinfo('Disaggregation complete', msg)

        except Exception as exc:
            self._set_status(f'Error: {exc}')
            messagebox.showerror('Error', str(exc))
        finally:
            self._validate()

    def _set_status(self, text: str):
        self._status_var.set(text)
        self.update_idletasks()
