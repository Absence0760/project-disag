# Method 1 — `PATCH_CAL` demo

Method 1 patches a missing day in a target month from the **closest-
volume** same calendar month in another year, provided that year's
daily record for that month is complete.

## The rigged calendar Junes

The mock `target.MON` overrides the four June values to:

| Calendar June | Volume (Mm³) | Notes |
|---|---:|---|
| 2001 | 1.000 | daily complete |
| **2002** | **2.500** | **target — gappy in daily file** |
| 2003 | 2.600 | daily complete  ← closest volume to target |
| 2004 | 4.000 | daily complete |

`|2.500 − 2.600| = 0.1`, beating both `|2.500 − 1.000| = 1.5` and
`|2.500 − 4.000| = 1.5`. So the algorithm should pick **2003** as the
patch year.

## Files

| File | Contents |
|------|----------|
| `generate.py` | Deterministic generator (fixed seeds; June values pinned) |
| `data/target.MON` | 4 hydro years (2000-10 through 2004-09) |
| `data/gauge_with_gap.DAY` | All 48 months complete except cal Jun 2002 (whole month missing) |

To regenerate: `python3 examples/method1_demo/generate.py`

## Run it

```bash
python3 -m disag --no-gui --method 1 \
    --monthly examples/method1_demo/data/target.MON \
    --daily1  examples/method1_demo/data/gauge_with_gap.DAY \
    --output  /tmp/m1.day \
    --report  /tmp/m1.rep
```

**Expected:**
```
Done — 48 months written (48 disaggregated, 0 missing).
1 adjustment(s) logged to /tmp/m1.rep
```

**Expected report body:**
```
2002  6 Observed daily flow < 0,   Patched with 2003  6
```

## What this demo proves

- Method 1 picks the donor with the smallest absolute volume
  difference in `gen_monthly` (here, 2003).
- The donor month must have a complete daily record in file 1.
- The patch is logged once per month, with the donor year and month.
- The output for cal Jun 2002 will use cal Jun 2003's daily shape,
  rescaled by the disag formula to sum to 2.500 Mm³.

## Contrast with Method 5

Method 5 (`PATCH_EXCEED`) on the same data picks a *different* donor.
Try it:

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method1_demo/data/target.MON \
    --daily1  examples/method1_demo/data/gauge_with_gap.DAY \
    --output  /tmp/m5.day \
    --report  /tmp/m5.rep
```

The Method-5 report logs a tier-3 patch like:

```
2002  6 Observed daily flow < 0,   Patched with file 1 2004  6 (target exceed%= 75.0, donor exceed%= 66.7)
```

Method 5 picks **2004**, not 2003. Why?

- **Method 1** matches on absolute volume *in `gen_monthly`*. With
  Junes `{1.0, 2.5, 2.6, 4.0}`, `|2.5 − 2.6| = 0.1` wins → 2003.
- **Method 5** matches on percentile rank *in the daily file's
  distribution*. The 3 complete-June daily-file totals (RNG-driven,
  not pinned) rank 2004 at the 66.7 % exceedance level — closest to
  the target's 75 % rank in `gen_monthly`. So 2004 wins.

This is the headline reason method 5 exists for cross-river data:
the daily file's absolute scale doesn't track `gen_monthly`'s, so
matching by absolute volume across the two distributions is
meaningless. Match by rank instead. See
[../method5_demo/](../method5_demo/) for a worked example with two
gauges of clearly different absolute scale.

A regression test in `tests/test_e2e.py:Method1VsMethod5DivergenceTests`
also constructs a small artificial dataset where the two methods
disagree by design and asserts the picks.
