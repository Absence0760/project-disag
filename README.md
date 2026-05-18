# disag

Disaggregate monthly streamflow data to daily flows.

Given a monthly generated flow record (Mm3/month) and one or two observed daily
flow records (m3/s), `disag` distributes each monthly total across the days of
that month in proportion to the shape of the observed daily record.

For a plain-language explanation of the problem this project solves — with
worked examples — see [docs/problem.md](docs/problem.md).

This is a Python port of the original Delphi/Pascal tool **Disag-MD** (first
written by AJ Greyling in 1991, last updated by H Beuster in 2007). The original
source is preserved in [`delphi_files/`](delphi_files/).

---

## Download (pre-built executables)

Pre-built single-file executables for Windows, macOS, and Linux are produced
by [`.github/workflows/release.yml`](.github/workflows/release.yml) and
attached to each tagged release on GitHub. Each archive contains both
`disag` and `exceed` and has no Python dependency — just download, unpack,
and run:

| Platform | Archive | How to run |
|----------|---------|-----------|
| Windows  | `disag-windows-x64.zip`  | Unzip, double-click `disag.exe` (GUI) or run from `cmd` (CLI) |
| macOS    | `disag-macos-arm64.tar.gz` | `tar xzf … && ./disag` (you may need to allow it in System Settings → Privacy & Security on first run) |
| Linux    | `disag-linux-x64.tar.gz` | `tar xzf … && ./disag` |

To build them yourself on the current OS:

```bash
pip install pyinstaller
python packaging/build.py --clean
# → dist/disag, dist/exceed (or .exe on Windows)
```

PyInstaller does not cross-compile, so each OS must be built on a matching
machine (or via the GitHub Actions matrix above). For full per-platform
build instructions — including a Docker recipe for building Linux binaries
on a Mac, code-signing notes, and troubleshooting — see
[docs/building.md](docs/building.md).

## Running from source

Python 3.14 (matches the deployed Lambda runtime). The `disag/` and `exceed/`
packages are stdlib-only — no third-party dependencies, just `tkinter`,
`calendar`, `argparse`, etc.

> **macOS note:** Apple's Xcode Command Line Tools Python has a broken tkinter
> on recent macOS releases. Use Homebrew Python instead:
> ```bash
> brew install python@3.14 python-tk@3.14
> python3.14 -m disag
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

### Converting a Pitman `.ANS` file to a `.MON`

The disag tool reads NinhamShand-style `.MON` monthly files. If your
monthly data is in the Pitman model's `.ANS` format (fixed-width 8-char
columns, hydro-year layout), convert it first:

```bash
python3 -m disag.convert path/to/input.ANS path/to/output.MON
```

The converter slices by column position so it survives wet-year rows
where adjacent columns butt up with no whitespace (e.g.
`14639.1213670.74`) — a case that silently truncates values when
parsed with `.split()`. Same logic is wired into the disag GUI as a
**Convert .ANS to .MON…** button.

---

## Disaggregation methods

| # | Name | Daily files needed |
|---|------|--------------------|
| 0 | **One disaggregator** — use daily file 1 as the shape | 1 |
| 1 | **Patch with similar month** — use file 1; fill missing days from the calendar month in another year whose monthly volume is closest | 1 |
| 2 | **Patch with file 2** — use file 1; fill missing days from file 2 | 2 |
| 3 | **Incremental** — pattern = (daily file 1) − (daily file 2) | 2 |
| 4 | **Even distribution** — equal flow on every day of the month | 0 |
| 5 | **Patch with exceedance-matched donor** — use file 1, then file 2; for any day still missing, fill from a donor year picked by exceedance-percentile match (lets you borrow daily shape from a different river in the same area) | 1 or 2 |

See [docs/algorithm.md](docs/algorithm.md) for the full formula and details on
how missing data is handled for each method. Method 5 has its own deeper
write-up in [docs/method5.md](docs/method5.md) and a runnable demo at
[examples/method5_demo/](examples/method5_demo/).

See [CLAUDE.md](CLAUDE.md) for working notes — repo layout, gotchas, and
how to verify changes — when extending this project (with or without
Claude Code).

---

## Files

| Extension | Description |
|-----------|-------------|
| `.mon` / `.nat` / `.cur` | Monthly input — one record per hydro year (Oct–Sep), values in Mm3/month |
| `.day` | Daily input or output — one record per calendar month, values in m3/s |
| `.rep` | Text report — logs any months where patching or fallback was applied |
| `.ans` | Pitman model monthly output — converted to `.mon` via `python -m disag.convert` (see above) |

See [docs/file-formats.md](docs/file-formats.md) for the exact file layout.

---

## Project layout

```
disag/              Python package — disaggregation
  files.py          File I/O (read/write .day and .mon)
  algorithm.py      Core disaggregation logic
  convert.py        Pitman .ANS → NinhamShand .MON converter
  gui.py            Tkinter GUI
  __main__.py       Entry point (GUI + CLI)

exceed/             Python package — exceedance analysis
  files.py          File I/O (read .day and .mon)
  algorithm.py      Frequency/exceedance & seasonal grouping
  gui.py            Tkinter GUI (basic, seasonal, matching tabs)
  __main__.py       CLI + GUI entry point

web/                Browser front-end + AWS Lambda back-end (see web/README.md)
  frontend/         SvelteKit static site
  backend/          Python Lambda wrapping the two packages above
  infra/            Terraform — S3, CloudFront, API Gateway, Lambda, WAF, OIDC

tests/              Stdlib unittest suite (140+ tests, no external deps)
examples/           Per-method runnable demos with deterministic mock data
packaging/          PyInstaller build script for the standalone CLI binaries
delphi_files/       Original Delphi/Pascal source (reference only)
docs/               Detailed technical documentation
```

---

## exceed — Flow frequency (exceedance) analysis

Calculate flow frequency curves for monthly and daily streamflow data. Produces 12 separate exceedance analyses (one per calendar month).

### Usage

The default (no arguments) opens the GUI. Pass `--no-gui` with the file flags
to run from the command line:

```bash
# Monthly exceedance analysis
python3 -m exceed --no-gui --monthly path/to/file.mon --output path/to/report.rep

# Daily exceedance analysis
python3 -m exceed --no-gui --daily path/to/file.day --output path/to/report.rep

# Both monthly and daily
python3 -m exceed --no-gui --monthly file.mon --daily file.day --output report.rep
```

**Example using test files:**

```bash
python3 -m exceed --no-gui \
    --monthly ./testfiles/SINDILA.MON \
    --daily   ./testfiles/RUKOKI-l.DAY \
    --output  ./exceedance.rep
```

Run `python3 -m exceed --help` for full usage. Algorithm details and the
seasonal / matching modes are documented in [docs/exceed.md](docs/exceed.md).

---

## Web app — disag / exceed in the browser

[`web/`](web/) ships a SvelteKit single-page app in front of an AWS Lambda
that wraps the `disag/` and `exceed/` packages above. You upload `.mon` /
`.day` files in the browser, the Lambda runs the same code as the CLI,
and the resulting `.day` + `.rep` files come back as pre-signed download
URLs.

```
web/
  frontend/   SvelteKit + TypeScript + adapter-static (served from S3 behind CloudFront)
  backend/    Lambda handler (handler.py) — imports disag/ and exceed/, processes inputs in /tmp
  infra/      Terraform: S3 × 3, Lambda, API Gateway, CloudFront, WAF, OIDC role for CI deploys
```

Local dev:

```bash
corepack enable
pnpm setup                              # one-time: pnpm install + Python venv
pnpm dev                                # SvelteKit on :5173, local Lambda shim on :8000
```

The web app is provisioned and released independently of the CLI tool —
CLI releases are tagged `v*`, the web app uses `web-v*`. Full provisioning
+ deployment walkthrough lives in [web/README.md](web/README.md).

No accounts, no sign-up: the browser generates a UUID v4 on first visit
and uses it as a coarse scoping bucket for run history (see the handler
file's docstring for the trade-offs).
