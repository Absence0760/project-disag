# exceed — package notes for Claude Code

Flow-frequency (exceedance) analysis for monthly and daily streamflow data.
Produces 12 separate exceedance distributions (one per calendar month) plus
optional seasonal grouping and monthly↔daily exceedance matching.

See [../docs/exceed.md](../docs/exceed.md) for the algorithm and
[../docs/file-formats.md](../docs/file-formats.md) for input layout.

## Module map

| File | Purpose |
|------|---------|
| [files.py](files.py) | `read_monthly_file` (calendar-month flattening), `read_daily_file` (delegates to `disag.files.read_daily_file`), three report writers, and `write_exceedance_svg` (stdlib SVG flow-frequency curve — no matplotlib). |
| [algorithm.py](algorithm.py) | `ExceedanceCalculator`, `calculate_monthly_exceedance`, `calculate_seasonal_exceedance`, `match_exceedance_values`, plus `SEASON_PRESETS` (2 / 3 / 4 season). |
| [gui.py](gui.py) | `ExceedApp` — three-tab Tk window: **Basic**, **Seasonal**, **Matching**. |
| [__main__.py](__main__.py) | Argparse + GUI smoke-test + dispatch. |

## Three modes

Each mode is available from **both** the GUI tabs and the CLI.

1. **Basic** — exceedance distribution for each of 12 calendar months,
   computed independently for monthly and daily inputs. CLI: `--monthly`
   and/or `--daily`.
2. **Seasonal** — group calendar months into 2 / 3 / 4 seasons (presets in
   `SEASON_PRESETS`) and compute one exceedance per season. CLI:
   `--seasonal {2,3,4}` (needs `--monthly`).
3. **Matching** — for each calendar month, compute exceedance for monthly
   and daily inputs separately, then pair entries whose exceedance % are
   within a user-specified tolerance. CLI: `--match --tolerance PCT`
   (needs `--monthly` and `--daily`). Both the CLI and the GUI write the
   report via the shared `files.write_matching_report`.

Basic and seasonal mode also accept `--svg PATH` to render the
flow-frequency curve via `files.write_exceedance_svg` (stdlib SVG, no
matplotlib). The GUI exposes the same chart through an "Also save a
flow-frequency chart" checkbox on the Basic and Seasonal tabs.

## Why we delegate `.day` reading to disag

`exceed/files.py:read_daily_file` is a thin wrapper around
`disag.files.read_daily_file`. The earlier custom regex parser hit three
traps in real `.day` files:

1. 4-digit years (`2019  5`) didn't match a `\d{2}\s+\d{1,2}` regex, so all
   later records silently merged into whichever month was last parsed.
2. `.split()` couldn't separate concatenated negatives (`-99.990-99.990`).
3. The monthly-total field on each record's header line was being treated
   as a daily value.

The disag reader handles all three (fixed-width 7-char columns + 2/4-digit
year normalisation + skipping the header total). **Don't reintroduce a
custom parser here.**

## Verifying changes

Run the automated suite (covers the calculator math, seasonal pooling,
matching, file I/O, and the CLI):

```bash
python3 -m unittest tests.test_exceed
```

For deeper sanity-checking against the real fixture:

```bash
python3 -m exceed --no-gui \
    --monthly testfiles/SINDILA.MON \
    --daily   testfiles/RUKOKI-l.DAY \
    --output  /tmp/exceed.rep --intervals 20
```

Sanity values for `RUKOKI-l.DAY`: roughly 360–403 daily values per calendar
month (≈ years-with-data × days-in-month, minus missing). If May suddenly
balloons to 1985, the daily parser is broken — see "Why we delegate" above.

`exceed/gui.py` (the 3-tab Tk window) is **not** automatically tested
— the same headless-Tk reason as `disag/gui.py`. Exercise the
seasonal and matching tabs manually under Homebrew Python 3.14 (stock
macOS Python has a broken `_tkinter`).
