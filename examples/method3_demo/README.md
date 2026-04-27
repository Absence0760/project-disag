# Method 3 — `INCREMENTAL` demo

Method 3 builds the daily shape from `file 1 − file 2` — the runoff
*between* two gauges on the same river. Used when you have an
upstream and a downstream gauge and want the daily series for the
sub-catchment that drains in between them.

## Files

| File | Contents |
|------|----------|
| `generate.py` | Deterministic generator |
| `data/target.MON` | 3 hydro years (2000-10 through 2003-09) — the *incremental* monthly volumes |
| `data/gauge_downstream.DAY` | All complete; absolute scale ≈ 3× upstream |
| `data/gauge_upstream.DAY` | All complete; same RNG noise as downstream so `(down − up)` is smooth |

The two gauges use the **same RNG seed** so the per-day differences
aren't dominated by independent noise. In real use you'd be working
with actual measurements, not synthetic data.

To regenerate: `python3 examples/method3_demo/generate.py`

## Run it

```bash
python3 -m disag --no-gui --method 3 \
    --monthly examples/method3_demo/data/target.MON \
    --daily1  examples/method3_demo/data/gauge_downstream.DAY \
    --daily2  examples/method3_demo/data/gauge_upstream.DAY \
    --output  /tmp/m3.day \
    --report  /tmp/m3.rep
```

**Expected:**
```
Done — 36 months written (36 disaggregated, 0 missing).
```

The output's monthly totals will match `target.MON`'s incremental
volumes; the daily shape will follow the day-to-day difference
between the downstream and upstream gauges (clamped to zero where
upstream momentarily exceeds downstream, which can happen with
synthetic noise but should not in nature).

## What this demo proves

- The disag formula handles the `qD = file_1 − file_2` shape.
- Output volume sums to `target.MON`'s monthly incremental volume.
- Negative differences (upstream > downstream) are clamped to zero
  before the normalisation step — the algorithm preserves sign in
  the formula.

## Failure case

If either daily file has a missing value on any day, **the whole
month is marked missing** — Method 3 doesn't patch. To verify, edit
`generate.py` to gap one day in either gauge and re-run.

## Contrast with Method 5

Method 5 (`PATCH_EXCEED`) uses a single donor file as a shape source
and assumes that shape is the target's. Method 3 is structurally
different: it constructs a synthetic shape from *two* gauges via
subtraction. Don't reach for Method 3 unless you actually have
upstream and downstream gauges of the same river.
