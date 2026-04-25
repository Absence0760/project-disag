# Exceedance Analysis

The `exceed` tool computes **flow-frequency curves** — for a set of flow
values, the percentage of records that meet or exceed each flow magnitude.

## Core formula

Divide the value range `[min, max]` into `N` equal-width intervals
(default `N = 20`). For each input value `v`, find the interval index
`i = ⌊(v − min) / Δ⌋ + 1`. Tally `counts[i]`.

Then walk down from the top interval, accumulating counts:

```
cum_sum_i  = count_above_range + Σ counts[k]   for k = N, N-1, …, i
exceed_%_i = 100 × cum_sum_i / total_count
flow_i     = (i − 1) × Δ + min
```

`exceed_%_i` is the percentage of values ≥ `flow_i`. By construction it is
monotonically non-increasing as `flow_i` increases.

| Symbol | Description |
|--------|-------------|
| `Δ`    | `(max − min) / N` — interval width |
| `count_above_range` | values strictly greater than `max` (rare; only with manual ranges) |
| `count_below_range` | values strictly less than `min` (also rare) |

When `min == max` (all values identical) the calculator nudges `max` up by
`1.01 × min + 0.01` to avoid a zero-width range.

## Per-month grouping

The reader flattens input into 12 calendar-month buckets:

- **Monthly file (`.mon`):** each hydro-year row contributes one value to
  each calendar month. With 70 hydro-years of data, January will have 70
  values, February 70, etc.
- **Daily file (`.day`):** each daily record contributes its valid days to
  the corresponding calendar month. Missing days (`-99.99`) are excluded.

Exceedance is then computed independently for each calendar month.

## Seasonal grouping

The `Seasonal` tab groups calendar months into seasons before computing one
exceedance per season. Three presets are defined in
`exceed/algorithm.py:SEASON_PRESETS`:

| Seasons | Definition |
|---------|------------|
| 2 | Wet (Oct–Mar), Dry (Apr–Sep) — hydro-year halves |
| 3 | Summer (Jun–Aug), Fall (Sep–Nov), Winter (Dec–May) |
| 4 | Calendar quarters: Winter Dec–Feb, Spring Mar–May, Summer Jun–Aug, Fall Sep–Nov |

The GUI lets you override the preset month-set per season via checkboxes.

## Monthly ↔ daily matching

The `Matching` tab compares the monthly and daily exceedance curves for the
same calendar month. For each entry on the monthly curve, it finds the
closest entry on the daily curve and reports the pair if
`|exceed_monthly − exceed_daily| ≤ tolerance` (default 5 percentage points).

Output columns:

```
Exceedance%   Flow Monthly   Flow Daily   Difference
```

Use this to sanity-check that the disaggregation preserves the shape of
the daily distribution at corresponding exceedance levels.

## Missing-value handling

Per the file-format spec ([file-formats.md](file-formats.md)), **any
negative value** is the missing-data sentinel — `-99.99` and `-99.990` are
the conventional ones, but `-999`, `-50`, `-1`, etc. are equally valid.
The exceed reader filters out any value `< 0` before min/max or interval
computation.

There is no patching or backfill in the exceed tool. Missing days are
simply dropped, so a calendar month's sample size = (years with data) ×
(days in month) − (missing days). The disag tool does provide patching
methods (1, 2, 4) that *replace* missing daily values; see
[algorithm.md](algorithm.md) for those.

## CLI

```bash
python3 -m exceed --no-gui \
    --monthly testfiles/SINDILA.MON \
    --daily   testfiles/RUKOKI-l.DAY \
    --output  exceedance.rep \
    --intervals 20
```

`--monthly` and `--daily` are both optional but at least one is required.
`--intervals` is the `N` above; valid range 5–100.

The CLI mode emits a basic per-month report; seasonal and matching modes
are GUI-only at present.

## Output format

```
--------------------------------------------------------------------------------
Exceedance Analysis Report  : 2026-04-24 20:05:32
--------------------------------------------------------------------------------

JANUARY
--------------------------------------------------------------------------------
Total values: 70  Below range: 0  Above range: 1

Exceedance%    Flow Value
------------------------------
  100.00%            0.290
   98.57%            0.476
   …
    4.29%            3.824
```

`Above range: 1` means one value exceeded `max` (typically the largest input
value itself, since the interval boundary is exclusive at the top).
