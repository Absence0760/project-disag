# Method 4 — `EVEN` demo

Method 4 distributes each month's volume **evenly across its days**.
No daily input file is needed. Every day in a 30-day month gets
exactly `volume / 30`; every day in a 31-day month gets `volume / 31`.

This is the right method when no observed daily record exists at all
and there's no donor to borrow a shape from. The output flat-lines
within each month, but the monthly totals are correct — useful for
downstream models that only care about monthly water balance and not
about within-month variability.

## Files

| File | Contents |
|------|----------|
| `generate.py` | Deterministic generator (only writes the .MON file) |
| `data/target.MON` | 3 hydro years (2000-10 through 2003-09) |

To regenerate: `python3 examples/method4_demo/generate.py`

## Run it

```bash
python3 -m disag --no-gui --method 4 \
    --monthly examples/method4_demo/data/target.MON \
    --output  /tmp/m4.day \
    --report  /tmp/m4.rep
```

**Expected:**
```
Done — 36 months written (36 disaggregated, 0 missing).
```

## Sample output

Jun 2002 (30 days, monthly volume 1.138 Mm³ in target.MON):
```
2002  6     1.138
  0.439  0.439  0.439  0.439  0.439  0.439  0.439
  0.439  …  (30 identical values)
```

Jul 2002 (31 days, monthly volume 0.864 Mm³):
```
2002  7     0.864
  0.323  0.323  0.323  0.323  0.323  0.323  0.323
  0.323  …  (31 identical values)
```

The per-day value changes between months (because the divisor is the
days-in-month) but is constant within each month.

## Volume check

Per-day m³/s × days × 86400 / 1e6 = monthly Mm³

* Jun 2002: `0.439 × 30 × 86400 / 1e6 ≈ 1.138 Mm³` ✓
* Jul 2002: `0.323 × 31 × 86400 / 1e6 ≈ 0.865 Mm³` ✓

## What this demo proves

- Method 4 needs no daily file at all (CLI: `--daily1` and `--daily2`
  must be omitted).
- Output volume sums to `target.MON` exactly.
- Within-month flow is constant — by construction, no shape
  information is borrowed from anywhere.

## When to use this

Method 4 is the *baseline* — use it when:

- You have monthly data but no observed daily record from anywhere.
- You only care about preserving monthly water balance, not daily
  variability.
- You're seeding a downstream model that will impose its own daily
  pattern.

For most engineering uses (reservoir simulation, environmental flow
assessments, FDC-based licensing) the within-month variability
matters and Method 4 is too coarse — pick Method 0/1/2/5 instead.
