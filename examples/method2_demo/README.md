# Method 2 — `PATCH_FILE` demo

Method 2 patches each missing day in file 1 with the corresponding day
from file 2. A month is only marked missing when the **same day** is
missing in both files.

## Files

| File | Contents |
|------|----------|
| `generate.py` | Deterministic generator |
| `data/target.MON` | 3 hydro years (2000-10 through 2003-09) |
| `data/gauge_a.DAY` | All complete except **cal Jun 2002** (whole month missing) |
| `data/gauge_b.DAY` | All complete except **cal Jun 2003** (whole month missing) |

The two gauges share the same RNG seed for their base values — only
their gap patterns differ. Because the gaps are orthogonal (different
months), each file fills the other's hole exactly.

To regenerate: `python3 examples/method2_demo/generate.py`

## Run it

```bash
python3 -m disag --no-gui --method 2 \
    --monthly examples/method2_demo/data/target.MON \
    --daily1  examples/method2_demo/data/gauge_a.DAY \
    --daily2  examples/method2_demo/data/gauge_b.DAY \
    --output  /tmp/m2.day \
    --report  /tmp/m2.rep
```

**Expected:**
```
Done — 36 months written (36 disaggregated, 0 missing).
```

The `.rep` body is empty in the per-month section — Method 2 does
day-level patching silently (just like tier 2 in Method 5). The fact
that no month was marked missing means file 2's days successfully
filled file 1's gap (and vice versa) on the day level.

## What this demo proves

- Cal Jun 2002 — gappy in file 1 — was filled day-by-day from file 2.
- Cal Jun 2003 — gappy in file 2 — kept its file-1 values.
- Output coverage is 36/36 even though each file individually is
  35/36 (one month each).

## What if both files miss the same day?

Method 2 marks the **whole month** as missing — same as Method 0.
You can verify by editing `generate.py` to give both files the same
gap, regenerating, and re-running. That case behaves identically to
running Method 0 against `gauge_a.DAY` alone.

## Contrast with Method 5

Method 5 (`PATCH_EXCEED`) on the same data would also fill both gaps
via tier-2 day-level patching. The behavioural difference only
matters when both files miss the same day: Method 2 marks the month
missing, Method 5 falls through to tier 3 (an exceedance-matched
donor month). See [../method5_demo/](../method5_demo/).
