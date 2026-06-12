# Using Disag-MD

There are three ways to run the toolkit. They share the same file readers
and produce the same outputs — pick whichever fits how you work.

| Way | Best for | How |
|-----|----------|-----|
| **Web app** | A quick one-off run with nothing to install | Open the [Run](/run) page, upload your files, pick a tool, submit |
| **Desktop GUI** | Repeated local work on a machine with Python | `python3 -m disag` / `python3 -m exceed` |
| **Command line** | Scripting, batch runs, reproducible pipelines | `python3 -m disag --no-gui …` (see below) |

The GUI is the default; adding `--no-gui` switches a package into
command-line mode. Everything is stdlib-only — any stock Python ≥ 3.14
runs it, no packages to install.

---

## Disag — disaggregate monthly → daily

### Quickstart

```bash
# GUI
python3 -m disag

# CLI — method 0, one daily reference
python3 -m disag --no-gui --method 0 \
    --monthly path/to/flows.mon \
    --daily1  path/to/gauge.day \
    --output  out.day \
    --report  out.rep
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--no-gui` | off (GUI) | Run in command-line mode |
| `--method`, `-m` | `0` | Disaggregation method, `0`–`5` (see below) |
| `--monthly` | — | Monthly input file (`.mon` / `.nat` / `.cur`) **(required)** |
| `--daily1` | — | Daily reference file 1 (`.day`) |
| `--daily2` | — | Daily reference file 2 (`.day`) |
| `--output`, `-o` | — | Output daily file (`.day`) **(required)** |
| `--report`, `-r` | — | Report file (`.rep`) **(required)** |

### Which method, and what it needs

Pick the cheapest method that still gives a usable signal. The tool only
requires the daily files a method actually uses:

| Method | Daily files required | One-line summary |
|--------|----------------------|------------------|
| `0` One file | 1 (`--daily1`) | Drop any month with a missing day |
| `1` Patch (calendar) | 1 (`--daily1`) | Backfill missing days from the closest same-month year |
| `2` Patch (file) | 2 (`--daily1`, `--daily2`) | Fall back to file 2 wherever file 1 is blank |
| `3` Incremental | 2 (`--daily1`, `--daily2`) | Shape = file 1 − file 2 (catchment between two gauges) |
| `4` Even | 0 | Equal flow each day; no daily reference needed |
| `5` Patch (exceedance) | 1, file 2 optional | file 1 → file 2 → exceedance-matched donor month |

See [algorithm.md](algorithm.md) for the full per-method behaviour and
[method5.md](method5.md) for the cross-river donor in method 5. The
`.rep` report logs every patch and fallback so you can see where the
output is real versus synthetic — and the CLI prints a warning when a
method-0 run drops most of its months, or a method-5 run is mostly
synthetic.

---

## Exceed — flow-frequency analysis

Exceed has three modes, available from both the GUI tabs and the CLI.

### Quickstart

```bash
# GUI (Basic / Seasonal / Matching tabs)
python3 -m exceed

# Basic: one curve per calendar month, plus an SVG chart
python3 -m exceed --no-gui --monthly flows.mon --output out.rep --svg out.svg

# Seasonal: pool the 12 months into 2, 3, or 4 seasons
python3 -m exceed --no-gui --monthly flows.mon --seasonal 2 --output out.rep

# Matching: pair monthly vs daily percentiles within a tolerance
python3 -m exceed --no-gui --monthly flows.mon --daily gauge.day \
    --match --tolerance 5 --output out.rep
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--no-gui` | off (GUI) | Run in command-line mode |
| `--monthly`, `-m` | — | Monthly input file (`.mon` / `.nat` / `.cur`) |
| `--daily`, `-d` | — | Daily input file (`.day`) |
| `--output`, `-o` | — | Output report file (`.rep`) |
| `--svg` | — | Also write a flow-frequency chart to this path (`.svg`) |
| `--intervals`, `-i` | `20` | Number of flow intervals in the distribution (≥ 1) |
| `--seasonal` | — | Group months into `2`, `3`, or `4` seasons (needs `--monthly`) |
| `--match` | off | Pair monthly vs daily percentiles (needs `--monthly` and `--daily`) |
| `--tolerance`, `-t` | `5.0` | Exceedance-% tolerance for `--match` |

Basic mode takes a monthly file, a daily file, or both. You must pass
`--output` (and/or `--svg`) or the run computes the curves and then warns
that it wrote nothing. See [exceed.md](exceed.md) for the algorithm.

---

## Converting a Pitman `.ANS` file

If your monthly data comes out of the Pitman model as a `.ANS` file,
convert it to the `.MON` layout Disag reads first:

```bash
python3 -m disag.convert PUNRQ6.ANS PUNRQ6.MON
```

The desktop Disag GUI exposes the same step as a **Convert .ANS to .MON…**
button. See the [converter guide](converter.md) for the details and the
format trap it avoids.

---

## A note on the desktop GUI

On macOS, Apple's stock Python has a broken `_tkinter`, so the GUI fails
to import. Use Homebrew Python instead:

```bash
brew install python@3.14 python-tk@3.14
python3.14 -m disag
```

If you can't get a GUI at all, every feature is reachable from the CLI
with `--no-gui`. See [FAQ & troubleshooting](faq.md) for more.
