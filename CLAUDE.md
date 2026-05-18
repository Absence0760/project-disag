# CLAUDE.md

Operator notes for Claude Code working on this repo. Keep this short — link to
deeper docs rather than duplicating them here.

## What this project is

A Python port of the Delphi/Pascal **Disag-MD** hydrology tool (AJ Greyling
1991, last updated H Beuster 2007). The original Pascal source is preserved
read-only under [delphi_files/](delphi_files/). Two independent Python
packages are built from it:

| Package | Purpose | Entry point |
|---------|---------|-------------|
| [disag/](disag/) | Disaggregate monthly flows to daily flows | `python -m disag` |
| [exceed/](exceed/) | Flow-frequency (exceedance) analysis | `python -m exceed` |

Both ship a Tkinter GUI (default) and a `--no-gui` CLI mode.

Per-package notes live in [disag/CLAUDE.md](disag/CLAUDE.md) and
[exceed/CLAUDE.md](exceed/CLAUDE.md). For the domain context — what
problem this project actually solves, with worked examples — see
[docs/problem.md](docs/problem.md).

## Dependencies

Python ≥ 3.8, **standard library only** (`tkinter`, `calendar`, `argparse`,
`re`, `dataclasses`, `datetime`, `enum`, `typing`). Do not add third-party
packages — the original tool is meant to run anywhere with a stock Python.

## Running things

```bash
# Disag — disaggregate monthly → daily
python3 -m disag                                  # GUI
python3 -m disag --help                           # CLI usage
python3 -m disag --no-gui --method 0 \
    --monthly testfiles/SINDILA.MON \
    --daily1  testfiles/RUKOKI-l.DAY \
    --output  /tmp/out.day --report /tmp/out.rep

# Convert a Pitman .ANS monthly file into the NinhamShand .MON layout
python3 -m disag.convert path/to/PUNRQ6.ANS path/to/PUNRQ6.MON

# Exceed — flow-frequency analysis
python3 -m exceed                                 # GUI (3 tabs)
python3 -m exceed --no-gui \
    --monthly testfiles/SINDILA.MON \
    --daily   testfiles/RUKOKI-l.DAY \
    --output  /tmp/exceed.rep
```

Test fixtures live in [testfiles/](testfiles/) (gitignored — they are large
and binary-ish). Use `SINDILA.MON` (monthly) and `RUKOKI-l.DAY` (daily) for
manual sanity checks.

Automated tests live in [tests/](tests/) and run with the standard
library's unittest module:

```bash
python3 -m unittest discover tests             # whole suite (140+ tests)
python3 -m unittest tests.test_algorithm       # PATCH_EXCEED helper unit tests
python3 -m unittest tests.test_e2e             # PATCH_EXCEED scenarios + observability
python3 -m unittest tests.test_demo_methods    # methods 0–4 end-to-end
python3 -m unittest tests.test_file_io         # files.py + report.py round-trip
python3 -m unittest tests.test_exceed          # exceed/ package
python3 -m unittest tests.test_cli             # subprocess-driven CLI
python3 -m unittest tests.test_convert         # .ANS → .MON converter
python3 -m unittest tests.test_missing_data    # missing-day/month/year edge cases
python3 -m unittest tests.test_tier3           # PATCH_EXCEED tier-3 sub-processes
```

The end-to-end tests use the deterministically-generated mock data in
[examples/](examples/) (each `methodN_demo/data/`) — committed files,
so the suite has no external dependencies. CI also re-runs every
`generate.py` and asserts no committed file drifts.

### What's NOT tested

`disag/gui.py` and `exceed/gui.py` — the Tkinter GUIs — are not
covered by automated tests and are not run in CI. Reasons:

- Tk needs a display server; running it in headless CI requires
  `xvfb` plus a Tk-aware test harness. The setup cost outweighs the
  value for two small, well-isolated GUI modules.
- All non-trivial logic the GUIs depend on (algorithms, file I/O,
  reports) lives in `disag.algorithm` / `disag.files` / `disag.report`
  / `exceed.algorithm` / `exceed.files` and *is* tested. The GUIs are
  mostly Tk plumbing — radio buttons, file pickers, validation
  toggles, and `_run` glue that calls into the tested code.

If you change GUI behaviour, exercise it manually:

```bash
# disag GUI
python3 -m disag

# exceed GUI (3 tabs: Basic / Seasonal / Matching)
python3 -m exceed
```

On macOS use Homebrew Python 3.13 (stock macOS Python's `_tkinter`
is broken — see the "macOS tkinter" gotcha below).

## Gotchas

### macOS tkinter

Apple's stock Python on macOS 15 (Sequoia) has a broken `_tkinter`. The GUI
will fail to import. Use Homebrew Python instead:

```bash
brew install python@3.13 python-tk@3.13
python3.13 -m disag
```

The `__main__.py` for both packages does an `import tkinter` check before
importing the GUI, and prints the Homebrew hint if it fails. Do NOT change
this to `tk.Tk().destroy()` — instantiating a Tk root before the real app
root corrupts state on macOS 26 + Tk 9 (PAC trap in
`Tk_MacOSXGetTkWindow`). Don't paper over the import error — print the hint.

### Daily file format quirks

`.day` files are **fixed-width**, not whitespace-separated. The authoritative
parser is [disag/files.py:read_daily_file](disag/files.py) — it reads each
daily value as a 7-character right-justified column. **Do not** try to
`.split()` data lines:

- Negative sentinels are written without separators: `-99.990-99.990-99.990`
  → `.split()` produces one unparsable token.
- Year fields are sometimes 2-digit (`51`) and sometimes 4-digit (`2019`).
  Use `if year < 1900: year += 1900` to normalise.
- The first line of each record is `YYY MM TOTAL` — the `TOTAL` is a monthly
  summary in Mm3, **not** a daily value. Skip it.

`exceed/` reuses `disag.files.read_daily_file` rather than rolling its own
to avoid this trap. The exceed module had a regex-based parser that hit all
three of these gotchas — see git history for the fix.

See [docs/file-formats.md](docs/file-formats.md) for the full spec.

### The Delphi source has a known backfill bug

When porting/extending the patching methods (`PATCH_CAL`, `PATCH_FILE` in
`disag/algorithm.py`), do **not** treat the Pascal behaviour as ground truth.
The user has flagged the original `delphi_files/uDisag_md.pas` (around lines
241–294) as buggy. Re-derive the intended behaviour from
[docs/algorithm.md](docs/algorithm.md) and confirm with the user before
matching the Pascal output exactly.

### Hydro-year convention

The monthly file stores rows as **hydro years** (October → September). When
indexing into `read_monthly_file` output, October of year *N* belongs to the
hydro-year row labelled *N*, but January of year *N+1* is also on that same
row. The exceed reader maps these into calendar months for you; the disag
reader keys by `(calendar_year, calendar_month)`. Mind the off-by-one.

## Project layout

```
disag/              Python package — disaggregation
  files.py          File I/O — authoritative .day / .mon reader/writer
  algorithm.py      Core disaggregation logic (6 methods)
  convert.py        Pitman .ANS → NinhamShand .MON converter (`python -m disag.convert`)
  gui.py            Tkinter GUI
  report.py         .rep file writer
  __main__.py       Entry point (GUI + CLI)

exceed/             Python package — flow frequency
  files.py          File I/O (delegates to disag.files for .day)
  algorithm.py      Exceedance, seasonal grouping, matching
  gui.py            Tkinter GUI (Basic / Seasonal / Matching tabs)
  __main__.py       Entry point (GUI + CLI)

delphi_files/       Original Pascal source — reference only, do not modify
docs/               Detailed technical documentation
  algorithm.md      Disag formula and per-method behaviour
  file-formats.md   .day / .mon / .rep on-disk layout
  exceed.md         Exceedance algorithm and matching logic
testfiles/          Sample input files (gitignored)
```

## Conventions

- No `__init__.py` exports beyond what's needed; import from submodules.
- Prefer editing existing files to creating new ones.
- Don't add docstrings or comments that just restate the code. The existing
  style favours short module-level docstrings and minimal inline comments.
- When touching `disag/files.py`, run both `python3 -m disag --no-gui …` and
  `python3 -m exceed --no-gui …` against the fixtures — exceed depends on
  this reader.
