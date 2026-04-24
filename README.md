# disag

Disaggregate monthly streamflow data to daily flows.

Given a monthly generated flow record (Mm3/month) and one or two observed daily
flow records (m3/s), `disag` distributes each monthly total across the days of
that month in proportion to the shape of the observed daily record.

This is a Python port of the original Delphi/Pascal tool **Disag-MD** (first
written by AJ Greyling in 1991, last updated by H Beuster in 2007). The original
source is preserved in [`delphi_files/`](delphi_files/).

---

## Requirements

Python 3.8 or later. No third-party packages — only the standard library
(`tkinter`, `calendar`, `argparse`).

> **macOS note:** Apple's Xcode Command Line Tools Python has a broken tkinter
> on macOS 15 (Sequoia). Use Homebrew Python instead:
> ```bash
> brew install python@3.13 python-tk@3.13
> python3.13 -m disag
> ```

---

## Running the tool

### GUI (default)

```bash
python3 -m disag
```

The window lets you browse for input files, choose a disaggregation method, and
click **Disaggregate!**.

### Command line

```bash
python3 -m disag --no-gui \
    --method 0 \
    --monthly  path/to/generated.mon \
    --daily1   path/to/observed.day \
    --output   path/to/output.day \
    --report   path/to/output.rep
```

**Example using test files:**

```bash
python3 -m disag --no-gui \
    --method 0 \
    --monthly  ./testfiles/SINDILA.MON \
    --daily1   ./testfiles/RUKOKI-l.DAY \
    --output   ./test_output.day \
    --report   ./test_output.rep
```

Run `python3 -m disag --help` for full usage.

---

## Disaggregation methods

| # | Name | Daily files needed |
|---|------|--------------------|
| 0 | **One disaggregator** — use daily file 1 as the shape | 1 |
| 1 | **Patch with similar month** — use file 1; fill missing days from the calendar month in another year whose monthly volume is closest | 1 |
| 2 | **Patch with file 2** — use file 1; fill missing days from file 2 | 2 |
| 3 | **Incremental** — pattern = (daily file 1) − (daily file 2) | 2 |
| 4 | **Even distribution** — equal flow on every day of the month | 0 |

See [docs/algorithm.md](docs/algorithm.md) for the full formula and details on
how missing data is handled for each method.

---

## Files

| Extension | Description |
|-----------|-------------|
| `.mon` / `.nat` / `.cur` | Monthly input — one record per hydro year (Oct–Sep), values in Mm3/month |
| `.day` | Daily input or output — one record per calendar month, values in m3/s |
| `.rep` | Text report — logs any months where patching or fallback was applied |

See [docs/file-formats.md](docs/file-formats.md) for the exact file layout.

---

## Project layout

```
disag/              Python package
  files.py          File I/O (read/write .day and .mon)
  algorithm.py      Core disaggregation logic
  gui.py            Tkinter GUI
  __main__.py       Entry point (GUI + CLI)

exceed/             Exceedance analysis package
  files.py          File I/O (read .day and .mon)
  algorithm.py      Frequency/exceedance calculation
  __main__.py       CLI entry point

delphi_files/       Original Delphi/Pascal source (reference only)
docs/               Detailed technical documentation
```

---

## exceed — Flow frequency (exceedance) analysis

Calculate flow frequency curves for monthly and daily streamflow data. Produces 12 separate exceedance analyses (one per calendar month).

### Usage

```bash
# Monthly exceedance analysis
python3 -m exceed --monthly path/to/file.mon --output path/to/report.rep

# Daily exceedance analysis
python3 -m exceed --daily path/to/file.day --output path/to/report.rep

# Both monthly and daily
python3 -m exceed --monthly file.mon --daily file.day --output report.rep
```

**Example using test files:**

```bash
python3 -m exceed --monthly ./testfiles/SINDILA.MON \
                  --daily ./testfiles/RUKOKI-l.DAY \
                  --output ./exceedance.rep
```

Run `python3 -m exceed --help` for full usage.
