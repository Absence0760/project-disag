# disag — package notes for Claude Code

Disaggregate monthly streamflow (Mm3/month) into daily flow (m3/s) using one
of six methods. Python port of the Delphi `Disag-MD` tool.

See [../docs/algorithm.md](../docs/algorithm.md) for the formula and
per-method behaviour, and [../docs/file-formats.md](../docs/file-formats.md)
for the file layout.

## Module map

| File | Purpose |
|------|---------|
| [files.py](files.py) | `read_daily_file`, `read_monthly_file`, `write_daily_file`, `DailyRecord`, `MISSING`. **Authoritative `.day` parser for the whole repo** — `exceed/` reuses it. |
| [algorithm.py](algorithm.py) | `disaggregate(method, gen_monthly, obs_daily, no_files)`. Holds `DisagMethod` enum, `METHOD_NAMES`, `NO_FILES`, and `find_patch_year` (used by `PATCH_CAL`). |
| [convert.py](convert.py) | `ans_to_mon` — converts a Pitman Model `.ANS` monthly file into a NinhamShand `.MON`. Fixed-width 8-char column parser; collides without delimiters in wet years. Wired into the disag GUI as a "Convert .ANS to .MON…" button. |
| [report.py](report.py) | `write_report` — emits the `.rep` log of patches and fallbacks. |
| [gui.py](gui.py) | `DisagApp` — Tk window with method picker and file pickers. |
| [__main__.py](__main__.py) | Argparse + GUI smoke-test + dispatch. |

## Methods (DisagMethod enum values)

| # | Name | Daily files |
|---|------|-------------|
| 0 | `ONE_FILE` | 1 |
| 1 | `PATCH_CAL` — patch from a similar calendar month (matched by absolute volume in `gen_monthly`) | 1 |
| 2 | `PATCH_FILE` — patch from file 2 | 2 |
| 3 | `INCREMENTAL` — pattern = file 1 − file 2 | 2 |
| 4 | `EVEN` — equal flow per day | 0 |
| 5 | `PATCH_EXCEED` — file 1 → file 2 → exceedance-matched donor (cross-river percentile match) | 1 or 2 |

Number of required daily files is in `NO_FILES[method]` — use this rather
than hardcoding.

The single-donor patch methods (1, 2, 5) share one optional knob,
`DisagConfig(whole_month_fraction=f)` (also `--whole-month-fraction f` on the
CLI): when the fraction of a month's days **missing from file 1** reaches `f`,
rebuild the whole month from one coherent donor instead of splicing sources
day-by-day. Each method's donor differs — PATCH_CAL takes the matched
same-calendar-month year, PATCH_FILE takes file 2, PATCH_EXCEED walks its
tiers (file 2 if complete, else the exceedance-matched donor). If no single
source covers the whole month it degrades to the ordinary splice (never worse
than the default). Ignored by methods 0, 3, 4 (no single-donor patch step).
Default `None` = day-by-day splice (unchanged). See
[../docs/method5.md](../docs/method5.md#whole-month-replacement-optional).

Method 5 has two further opt-in knobs for cross-river fills —
`DisagConfig(daily_fdc_mapping=True)` (`--daily-fdc-mapping`) maps injected
day values through daily flow-duration curves instead of the linear scale
factor, and `DisagConfig(seam_blend=True)` (`--seam-blend`) blends splice
seams into the neighbouring observed days. Use seam blending **with** FDC
mapping, not alone. The `.rep` always carries an injected-day spike audit
for method 5 (report-only). See
[../docs/method5.md](../docs/method5.md#injected-day-normalisation-optional).

## Things to watch

### The Delphi backfill bug

When working on `PATCH_CAL` or `PATCH_FILE`, **do not** assume the original
`delphi_files/uDisag_md.pas` (lines 241–294) is correct. The user has flagged
its missing-data backfill logic as buggy. Re-derive the intended behaviour
from `docs/algorithm.md` and ask before mirroring the Pascal output exactly.

### Hydro year vs calendar year

The monthly file is keyed by **hydro year** (Oct → Sep) on disk but
`read_monthly_file` returns `{(calendar_year, calendar_month): Mm3}`. So
hydro row 1990 → `(1990, 10), (1990, 11), (1990, 12), (1991, 1), …, (1991, 9)`.
Mind the off-by-one when computing year boundaries.

### Daily file fixed-width parsing

Daily values are 7-char right-justified columns, not whitespace-separated.
A value that fills the field abuts its neighbour (e.g. `12345.612345.6`); the
`-99.99` sentinel renders as ` -99.99` — slice by column, don't `.split()`. The first line
of each record is `YYY MM TOTAL` — `TOTAL` is the monthly summary, not a
daily value. See [../docs/file-formats.md](../docs/file-formats.md).

## Verifying changes

There's a small automated suite — run it first:

```bash
python3 -m unittest discover tests
```

`disag/gui.py` is intentionally not in the suite — Tk needs a display
server that headless CI doesn't provide, and the GUI is mostly
plumbing over the tested algorithm/files/report modules. Exercise
the GUI manually after any change there: `python3 -m disag`.

For deeper sanity checks, run the CLI against the real fixtures:

```bash
# Method 0 (one disaggregator)
python3 -m disag --no-gui --method 0 \
    --monthly testfiles/SINDILA.MON \
    --daily1  testfiles/RUKOKI-l.DAY \
    --output  /tmp/out.day --report /tmp/out.rep

# Method 4 (even, no daily file)
python3 -m disag --no-gui --method 4 \
    --monthly testfiles/SINDILA.MON \
    --output  /tmp/out_even.day --report /tmp/out_even.rep
```

Inspect the `.rep` file for unexpected adjustment counts and spot-check the
`.day` output. Also re-run `python3 -m exceed --no-gui …` since `exceed/`
imports from `disag.files`.
