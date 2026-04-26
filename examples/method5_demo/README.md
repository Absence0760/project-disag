# Method 5 demo — three scenarios

This directory contains a small synthetic dataset and three CLI commands
that exercise each tier of the `PATCH_EXCEED` (`--method 5`) algorithm
on its own. The dataset is deliberately tiny — six hydro years (2000-10
through 2006-09), 72 months total — so you can read the entire `.rep`
output and verify the result by hand.

## Files

| File | Contents |
|------|----------|
| [`generate.py`](generate.py) | Deterministic generator. Re-run any time to reproduce the data. |
| [`data/target.MON`](data/target.MON) | Monthly volumes (Mm³/month) for "River A". This is the file we want to disaggregate to daily. |
| [`data/gauge_a_complete.DAY`](data/gauge_a_complete.DAY) | Daily file 1 — primary gauge, no gaps. |
| [`data/gauge_a_with_gaps.DAY`](data/gauge_a_with_gaps.DAY) | Same as above but with two whole-month gaps: **June 2003** and **June 2005**. |
| [`data/gauge_b_partial.DAY`](data/gauge_b_partial.DAY) | Daily file 2 — different river, smaller absolute scale, only covers hydro year 2002 (Oct-2002 through Sep-2003). |

To regenerate: `python3 examples/method5_demo/generate.py`

The mock rivers share the same regional seasonality (wet ≈ Dec–Feb, dry
≈ Jun–Aug). Their absolute discharge differs: gauge B is ≈ 30% of
gauge A, simulating "different river, same area."

---

## Scenario 1 — Tier 1 only

Every month in `gauge_a_complete.DAY` is observed, so every output day
comes straight from real data. No patches.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_complete.DAY \
    --output  /tmp/s1.day \
    --report  /tmp/s1.rep
```

**Expected:**
```
Done — 72 months written (72 disaggregated, 0 missing).
```

The `.rep` body has **zero** `Patched with file …` lines.

---

## Scenario 2 — Tier 1 + Tier 3 (no file 2)

`gauge_a_with_gaps.DAY` is missing all of June 2003 and all of June 2005.
With no file 2 supplied, Tier 2 is unavailable, so both gaps fall through
to Tier 3.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_with_gaps.DAY \
    --output  /tmp/s2.day \
    --report  /tmp/s2.rep
```

**Expected report body:**
```
2003  6 Observed daily flow < 0,   Patched with file 1 2004  6 (target exceed%= 33.3, donor exceed%= 25.0)
2005  6 Observed daily flow < 0,   Patched with file 1 2002  6 (target exceed%= 83.3, donor exceed%= 75.0)
```

Reading these:

`target.MON` stores rows by **hydro year** (Oct–Sep), so calendar June
of year `Y` lives in the row labelled `Y − 1`. The six calendar Junes are:

| Calendar June | Volume (Mm³) | Rank | Exceed % |
|---------------|-------------:|:----:|:--------:|
| 2001 | 1.383 | 3 | 50.0 |
| 2002 | 1.959 | 1 | 16.7 |
| **2003** | **1.554** | 2 | **33.3** |
| 2004 | 0.870 | 6 | 100.0 |
| **2005** | **1.007** | 5 | **83.3** |
| 2006 | 1.223 | 4 | 66.7 |

So:

- **June 2003** at 1.554 Mm³ → `p_target = 33.3 %`. Gauge A's complete
  Junes (2001, 2002, 2004, 2006 — both 2003 and 2005 are gappy and so
  excluded) form a 4-value distribution. The donor volume closest to
  `p_target` is gauge A's **June 2004** at the 25 % rank.
- **June 2005** at 1.007 Mm³ → `p_target = 83.3 %`. Closest donor in
  the same 4-value pool is gauge A's **June 2002** at the 75 % rank.

The 4-value donor pool gives percentiles at {25, 50, 75, 100}, which is
why the donor percentiles in the report quantise to these values.

---

## Scenario 3 — Tier 1 + Tier 2 + Tier 3

Now we add `gauge_b_partial.DAY` as file 2. Gauge B has a complete June
2003 — so that month is filled day-by-day from gauge B at Tier 2 (no
log line, like all day-level patches). Gauge B does NOT cover June 2005,
so that month still falls through to Tier 3.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_with_gaps.DAY \
    --daily2  examples/method5_demo/data/gauge_b_partial.DAY \
    --output  /tmp/s3.day \
    --report  /tmp/s3.rep
```

**Expected report body:**
```
2005  6 Observed daily flow < 0,   Patched with file 1 2002  6 (target exceed%= 83.3, donor exceed%= 75.0)
```

Only **one** Tier-3 line. June 2003 was silently filled by Tier 2 (gauge B's
day values), which is exactly the design — Tier 2 is "just observations from
a different gauge," same as `PATCH_FILE` (Method 2), so it isn't logged
per-month. Tier 3 *is* logged because the donor is a synthetic statistical
analog and you need to know that.

---

## What the three runs prove

| Tier exercised | Scenario 1 | Scenario 2 | Scenario 3 |
|----------------|:----------:|:----------:|:----------:|
| Tier 1 (file 1) | ✓ | ✓ | ✓ |
| Tier 2 (file 2 day-level) | — | — | ✓ (June 2003) |
| Tier 3 (exceedance donor) | — | ✓ (Jun 2003, Jun 2005) | ✓ (Jun 2005) |
| Output months | 72 | 72 | 72 |
| Months marked missing | 0 | 0 | 0 |

If you want to break the algorithm to convince yourself it does fail
loudly when it should, edit `generate.py` to also gap-out **all the
other Junes** (so no donor exists), and rerun Scenario 2. The two
gappy Junes will land in the output as `-99.99` sentinels and the
report will show 0 adjustments (no donor was found, so nothing to
log).
