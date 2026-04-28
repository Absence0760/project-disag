# Exceed demo — three modes

This directory contains a small synthetic dataset and three runnable
walkthroughs that exercise each mode of the `exceed` tool: **Basic**
(per-calendar-month exceedance), **Seasonal** (curves grouped by
season), and **Matching** (pairing monthly and daily curves at the
same exceedance percentile).

The dataset is deliberately tiny — 10 hydro years (Oct 2000 – Sep
2010), one synthetic gauge — so the row counts are predictable and a
reader can verify the expected output by hand.

## Files

| File | Contents |
|------|----------|
| [`generate.py`](generate.py)   | Deterministic generator. Re-run any time to reproduce the data. |
| [`seasonal.py`](seasonal.py)   | Driver script for the seasonal mode (not in exceed's CLI today). |
| [`matching.py`](matching.py)   | Driver script for the monthly↔daily matching mode (also not in the CLI). |
| [`data/target.MON`](data/target.MON) | Mock monthly volumes (Mm³/month) — wet Dec–Feb, dry Jun–Aug. |
| [`data/gauge.DAY`](data/gauge.DAY)   | Mock daily flows (m³/s) on the same seasonal shape, with per-day jitter. |

To regenerate: `python3 examples/exceed_demo/generate.py`

## Sample sizes

Every calendar-month bucket is fully populated — there are no gaps in
the demo data, so the per-month counts are exactly:

| Calendar month | Monthly file | Daily file |
|---|---:|---:|
| January   | 10 | 310 |
| February  | 10 | 282 |
| March     | 10 | 310 |
| April     | 10 | 300 |
| May       | 10 | 310 |
| June      | 10 | 300 |
| July      | 10 | 310 |
| August    | 10 | 310 |
| September | 10 | 300 |
| October   | 10 | 310 |
| November  | 10 | 300 |
| December  | 10 | 310 |

Daily February = 8 × 28 + 2 × 29 = 282, accounting for leap years 2004
and 2008 (cal Feb 2004 and cal Feb 2008 both fall in this 10-hydro-year
window).

---

## Mode 1 — Basic per-calendar-month exceedance

Produces 24 curves: 12 monthly (one per calendar month, 10 values each)
plus 12 daily (one per calendar month, 282–310 values each).

```bash
python3 -m exceed --no-gui \
    --monthly examples/exceed_demo/data/target.MON \
    --daily   examples/exceed_demo/data/gauge.DAY \
    --output  /tmp/exceed_basic.rep \
    --intervals 20
```

**Expected stdout:**

```
Reading monthly file: …/target.MON
Calculating exceedance (20 intervals)...
  January: 10 values
  February: 10 values
  …
  December: 10 values
Reading daily file: …/gauge.DAY
Calculating exceedance (20 intervals)...
  January: 310 values
  February: 282 values
  …
  December: 310 values
Writing report: /tmp/exceed_basic.rep
Done!
```

**Expected `.rep` shape:** 12 `MONTHLY - <MONTH>` sections followed by
12 `DAILY - <MONTH>` sections, each section a 20-row exceedance curve.

The `Above range: 1` header on monthly sections is expected — the
top-of-range interval is exclusive at the top, so a calendar month's
maximum value lands in the "above range" bucket. With only 10 monthly
values, that's 10 % of the points. The daily sections also show
`Above range: 1` for the same reason; with 300+ values, 1 / 310 ≈ 0.3 %
falls above range.

---

## Mode 2 — Seasonal grouping

Pools calendar months into 2, 3, or 4 season buckets and computes one
curve per season.  Three presets are defined in
[`exceed/algorithm.py`](../../exceed/algorithm.py):

| `--seasons` | Season → months |
|---|---|
| 2 | Wet (Oct–Mar)   ·  Dry (Apr–Sep) |
| 3 | Summer (Jun–Aug) · Fall (Sep–Nov) · Winter (Dec–May) |
| 4 | Winter (Dec–Feb) · Spring (Mar–May) · Summer (Jun–Aug) · Fall (Sep–Nov) |

```bash
python3 examples/exceed_demo/seasonal.py --seasons 4 --source monthly
```

**Expected counts (monthly source):**

| Preset | Season | Months pooled | Total values |
|---|---|---|---:|
| 2 | Wet     | Oct–Mar              | 60 |
| 2 | Dry     | Apr–Sep              | 60 |
| 3 | Summer  | Jun–Aug              | 30 |
| 3 | Fall    | Sep–Nov              | 30 |
| 3 | Winter  | Dec–May              | 60 |
| 4 | Winter  | Dec–Feb              | 30 |
| 4 | Spring  | Mar–May              | 30 |
| 4 | Summer  | Jun–Aug              | 30 |
| 4 | Fall    | Sep–Nov              | 30 |

Each "Total values" = months_in_season × 10 (one monthly value per
calendar month per hydro year). For `--source daily` the totals scale
up by ~30× (days_in_month × 10 hydro years).

The same rank/percentile arithmetic applies as in Basic mode — the
only difference is which months feed the bucket.

---

## Mode 3 — Monthly↔daily matching

For one chosen calendar month, builds the monthly curve and the daily
curve independently and then pairs entries on the two curves whose
exceedance percentages are within `--tolerance` percentage points
(default 5 pp).

```bash
python3 examples/exceed_demo/matching.py --month 1 --tolerance 5
```

**Expected stdout (truncated):**

```
Matching — January, tolerance ±5 percentage points
Monthly values: 10     Daily values: 310
======================================================================

Exceed Mo% Exceed Da%      Flow Mo      Flow Da    Δexceed
----------------------------------------------------------------------
   100.00%    100.00%        3.963        1.254      0.00
    90.00%     90.00%        4.203        1.503      0.00
    …
    20.00%     21.29%        8.532        3.247      1.29
```

`Flow Mo` is in Mm³/month (units of the monthly file); `Flow Da` is in
m³/s (units of the daily file). The two columns therefore aren't
directly comparable in absolute value — they describe the same
distribution at the same exceedance percentile but in different units.
A ratio of `Flow Mo / Flow Da` should be roughly constant across rows
if the two files describe the same physical flow series; on this mock
data it's around 2.6–3.2 (close to `1e6 / 86400 / 30 × month_days` ≈
3.0 for January).

`Δexceed` is the algorithm's own match key: the absolute difference
between the monthly and daily exceedance percentages, in percentage
points. Pairs with `Δexceed > tolerance` are dropped.

`--month 6` (a dry month) and `--month 12` (a wet month) are
interesting alternatives — the absolute flows differ by an order of
magnitude but the exceedance curves still pair up cleanly.

---

## What the three modes prove together

| Mode | Curves produced | Sample size driver | Output type |
|------|-----------------|--------------------|-------------|
| Basic     | 24 (12 monthly + 12 daily) | per calendar month | `.rep` file with curves stacked |
| Seasonal  | 2, 3, or 4                 | months pooled by season | stdout per-season curves |
| Matching  | 1 paired list              | one calendar month at a time | stdout aligned table |

All three are driven by the same `target.MON` / `gauge.DAY` pair, so
differences between their outputs come purely from how the input is
*grouped* before exceedance is computed.
