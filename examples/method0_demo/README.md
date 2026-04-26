# Method 0 — `ONE_FILE` demo

The simplest method: borrow the daily shape from a single observed
record. **Any month with a missing day gets dropped from the output.**

## Files

| File | Contents |
|------|----------|
| `generate.py` | Deterministic generator (fixed seeds) |
| `data/target.MON` | 3 hydro years (2000-10 through 2003-09) of monthly volumes |
| `data/gauge_complete.DAY` | All 36 months complete |
| `data/gauge_with_gap.DAY` | Same RNG sequence, but **June 2002** is entirely missing |

To regenerate: `python3 examples/method0_demo/generate.py`

## Scenario A — complete file

Every month has a valid daily record, so every output month is
disaggregated.

```bash
python3 -m disag --no-gui --method 0 \
    --monthly examples/method0_demo/data/target.MON \
    --daily1  examples/method0_demo/data/gauge_complete.DAY \
    --output  /tmp/m0a.day \
    --report  /tmp/m0a.rep
```

**Expected:**
```
Done — 36 months written (36 disaggregated, 0 missing).
```

## Scenario B — one whole-month gap

`gauge_with_gap.DAY` has all 30 days of June 2002 set to `-99.99`.
Method 0 marks the **whole month** as missing — there is no patching.

```bash
python3 -m disag --no-gui --method 0 \
    --monthly examples/method0_demo/data/target.MON \
    --daily1  examples/method0_demo/data/gauge_with_gap.DAY \
    --output  /tmp/m0b.day \
    --report  /tmp/m0b.rep
```

**Expected:**
```
Done — 36 months written (35 disaggregated, 1 missing).
```

The output `2002-06` record will be 30 days of `-99.99`. The `.rep`
file stays empty in the body — Method 0 doesn't log per-month, it just
writes the missing sentinel.

## What this demo proves

- Method 0 succeeds when daily data is complete.
- Method 0 silently drops whole months when a single day is missing.
- This is why the warning in the CLI / GUI suggests Method 1 (or 5)
  when more than half the months would be marked missing.
