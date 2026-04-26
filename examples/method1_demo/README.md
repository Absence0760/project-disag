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

Method 5 (`PATCH_EXCEED`) on the same data would pick a donor by
**percentile rank**, not absolute volume. Here gen_monthly's June
distribution is `[1.0, 2.5, 2.6, 4.0]`; 2.5 ranks at 75 % exceedance.
The donor pool (file 1's complete Junes excluding the gappy 2002) has
volumes `[1.0, 2.6, 4.0]` ranked at `[100, 67, 33] %`. Closest to 75 %
is 67 % → still 2003. So both methods agree on this dataset.

The methods diverge when the daily file's gauge has a different scale
than `gen_monthly` — see [../method5_demo/](../method5_demo/) for that
case.
