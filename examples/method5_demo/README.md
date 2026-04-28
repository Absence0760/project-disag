# Method 5 demo — five scenarios

This directory contains a small synthetic dataset and five CLI commands
that exercise each combination of `PATCH_EXCEED` (`--method 5`) tiers.
The dataset is deliberately tiny — six hydro years (2000-10 through
2006-09), 72 months total — so you can read the entire `.rep` output
and verify the result by hand.

## Files

| File | Contents |
|------|----------|
| [`generate.py`](generate.py) | Deterministic generator. Re-run any time to reproduce the data. |
| [`data/target.MON`](data/target.MON) | Monthly volumes (Mm³/month) for "River A" — the file we want to disaggregate to daily. |
| [`data/gauge_a_complete.DAY`](data/gauge_a_complete.DAY) | Daily file 1 — primary gauge, no gaps. |
| [`data/gauge_a_with_gaps.DAY`](data/gauge_a_with_gaps.DAY) | Same as above but with **two whole-month gaps**: June 2003 and June 2005. |
| [`data/gauge_b_full.DAY`](data/gauge_b_full.DAY) | Daily file 2 — different river, smaller absolute scale, covers hydro years **2002 and 2004** (so it covers cal Jun 2003 *and* cal Jun 2005). |
| [`data/gauge_b_partial.DAY`](data/gauge_b_partial.DAY) | Same different river, but only covers hydro year **2002** (so it covers cal Jun 2003 only — not cal Jun 2005). |
| [`data/gauge_a_scattered.DAY`](data/gauge_a_scattered.DAY) | Daily file 1 — primary gauge, with **scattered per-day gaps** in cal Jun 2003 (days 11..20 of 30 missing). All other months complete. |
| [`data/gauge_b_scattered.DAY`](data/gauge_b_scattered.DAY) | Daily file 2 — covers hydro year 2002 (so cal Jun 2003), but with days 15..20 of cal Jun 2003 also missing. Used together with `gauge_a_scattered.DAY` so all three tiers fire on different days of the same month. |

To regenerate: `python3 examples/method5_demo/generate.py`

The two mock rivers share regional seasonality (wet ≈ Dec–Feb, dry
≈ Jun–Aug). Their absolute discharge differs: gauge B is ≈ 30% of
gauge A, simulating "different river, same area."

## The 2 × 2 of scenarios

The first four scenarios cover every combination of *(does file 1 have
gaps?)* × *(is file 2 supplied, and how completely does it cover those
gaps?)*:

|   | No file 2 | File 2 covers all gaps | File 2 covers some gaps |
|---|---|---|---|
| **File 1 complete** | Scenario 1: Tier 1 only | (file 2 unused) | (file 2 unused) |
| **File 1 has gaps** | Scenario 4: Tier 1 + 3 | Scenario 2: Tier 1 + 2 | Scenario 3: Tier 1 + 2 + 3 |

In Scenarios 1–4 each gappy month is a *whole-month* gap, so all of its
days come from a single tier — Tier 2 day-by-day if file 2 has a record
there, otherwise Tier 3 from one exceedance-matched donor. Jun 2003 in
Scenarios 3 and 4 is therefore a **"Tier 3 only" month** — every day
comes from the donor.

**Scenario 5** zooms into a single month with *scattered per-day gaps*
in both files. It's the only scenario where Tier 1, Tier 2, and Tier 3
all fire on different days of the same month — i.e. the algorithm's
per-day fallback chain is visible inside one record.

---

## Scenario 1 — Tier 1 only

`gauge_a_complete.DAY` has every day for every month, so every output day
comes straight from real data.

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

## Scenario 2 — Tier 1 + Tier 2 (no Tier 3 fires)

`gauge_a_with_gaps.DAY` is missing all of June 2003 and June 2005.
`gauge_b_full.DAY` happens to have **complete** records for both of
those months, so every gap fills from file 2 day-by-day.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_with_gaps.DAY \
    --daily2  examples/method5_demo/data/gauge_b_full.DAY \
    --output  /tmp/s2.day \
    --report  /tmp/s2.rep
```

**Expected:**
```
Done — 72 months written (72 disaggregated, 0 missing).
```

The `.rep` body has **zero** `Patched with file …` lines. Tier 2
day-level patching is *not* logged, by design — it's just observations
from a different gauge.

How to *prove* that something happened anyway: the daily values for Jun
2003 and Jun 2005 in `/tmp/s2.day` will differ from the corresponding
days in Scenario 1's output, because their shape now comes from gauge
B's record at a smaller absolute scale (rescaled to River A's monthly
volume).

---

## Scenario 3 — Tier 1 + Tier 2 + Tier 3 (the full chain)

Same gappy file 1 as Scenario 2, but file 2 is now `gauge_b_partial.DAY`
which only covers hydro year 2002 (cal Jun 2003). The cal Jun 2005 gap
is therefore **not** filled by file 2 and falls through to Tier 3.

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

One Tier-3 line. Cal Jun 2003 was silently filled by Tier 2 (gauge B's
day values). Cal Jun 2005 had no Tier-2 source, so the algorithm
percentile-matched it to gauge A's June 2002 — see the table below for
the rank arithmetic.

---

## Scenario 4 — Tier 1 + Tier 3 (no file 2 supplied)

Same gappy file 1 as Scenarios 2 and 3, but **no file 2**. Both gaps
fall through to Tier 3.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_with_gaps.DAY \
    --output  /tmp/s4.day \
    --report  /tmp/s4.rep
```

**Expected report body:**
```
2003  6 Observed daily flow < 0,   Patched with file 1 2004  6 (target exceed%= 33.3, donor exceed%= 25.0)
2005  6 Observed daily flow < 0,   Patched with file 1 2002  6 (target exceed%= 83.3, donor exceed%= 75.0)
```

Two Tier-3 lines — one per gappy month.

---

## Scenario 5 — All three tiers in a single month

`gauge_a_scattered.DAY` is identical to `gauge_a_complete.DAY` except
that **days 11..20 of cal Jun 2003 are missing**. `gauge_b_scattered.DAY`
covers cal Jun 2003 but **days 15..20 are missing in file 2 as well**.
Days 11..14 of Jun 2003 are therefore fillable from file 2 (Tier 2);
days 15..20 are missing in *both* files and have to fall through to
Tier 3.

```bash
python3 -m disag --no-gui --method 5 \
    --monthly examples/method5_demo/data/target.MON \
    --daily1  examples/method5_demo/data/gauge_a_scattered.DAY \
    --daily2  examples/method5_demo/data/gauge_b_scattered.DAY \
    --output  /tmp/s5.day \
    --report  /tmp/s5.rep
```

**Expected per-day breakdown for cal Jun 2003 in `/tmp/s5.day`:**

| Days (1-indexed) | Source | Tier |
|---|---|---|
|  1..10 | gauge A real value             | 1 |
| 11..14 | gauge B real value (rescaled)  | 2 |
| 15..20 | gauge A's Jun 2005 (donor)     | 3 |
| 21..30 | gauge A real value             | 1 |

**Expected report body:**
```
2003  6 Observed daily flow < 0,   Patched with file 1 2005  6 (target exceed%= 33.3, donor exceed%= 40.0)
```

**Expected tier coverage summary:**
```
Tier 1 (file 1)        :   2181 day(s)
Tier 2 (file 2)        :      4 day(s)  across   1 month(s)
Tier 3 (donor month)   :      6 day(s)  across   1 month(s)
```

The 4 + 6 = 10 non-Tier-1 days line up exactly with the 10 days that
were missing from file 1 in cal Jun 2003. The split between them (4
Tier-2, 6 Tier-3) is determined by which days were *also* missing from
file 2.

The donor for the Tier-3 days is gauge A's Jun 2005, picked the same
way as in Scenarios 3 and 4: by closest exceedance percentile within
gauge A's 5-value June pool ({2001, 2002, 2004, 2005, 2006}, since
Jun 2003 has gaps and is excluded). Target percentile is 33.3 % (same
as Scenario 4), and the closest available rank in a 5-value pool is
40 %.

---

## Why those donor years? — the rank arithmetic

`target.MON` stores rows by **hydro year** (Oct–Sep), so calendar June
of year `Y` lives in the row labelled `Y − 1`. The six calendar Junes are:

| Calendar June | Volume (Mm³) | Rank | Exceed % (= 100·rank/6) |
|---------------|-------------:|:----:|:-----------------------:|
| 2001 | 1.383 | 3 | 50.0 |
| 2002 | 1.959 | 1 | 16.7 |
| **2003** | **1.554** | 2 | **33.3** |
| 2004 | 0.870 | 6 | 100.0 |
| **2005** | **1.007** | 5 | **83.3** |
| 2006 | 1.223 | 4 | 66.7 |

So the gappy targets are Jun 2003 at 33.3 % and Jun 2005 at 83.3 %.

Gauge A's complete Junes (excluding 2003 and 2005) are 2001, 2002, 2004,
and 2006 — four candidates. Their per-file rank percentiles are
necessarily {25, 50, 75, 100}.

- **Jun 2003** (target 33.3 %) → closest donor percentile is 25 % → that
  rank in gauge A's 4-value pool is the *largest* candidate June → which
  is gauge A's **June 2004**. `|33.3 − 25| = 8.3`.
- **Jun 2005** (target 83.3 %) → closest donor percentile is 75 % → that
  rank is the second-lowest candidate June → gauge A's **June 2002**.
  `|83.3 − 75| = 8.3`.

These match the donor years in the `.rep` lines exactly.

The 4-value pool gives percentiles at 25 % increments, which is why
`donor exceed%` quantises to {25, 50, 75, 100}. With more candidate
years in the daily file the resolution would tighten.

---

## What the five runs prove

| | Scenario 1 | Scenario 2 | Scenario 3 | Scenario 4 | Scenario 5 |
|---|:-:|:-:|:-:|:-:|:-:|
| Tier 1 days fire | ✓ | ✓ | ✓ | ✓ | ✓ |
| Tier 2 days fire | — | ✓ (Jun 2003 + 2005) | ✓ (Jun 2003) | — | ✓ (Jun 2003 days 11–14) |
| Tier 3 days fire | — | — | ✓ (Jun 2005) | ✓ (Jun 2003 + 2005) | ✓ (Jun 2003 days 15–20) |
| All three tiers within one month | — | — | — | — | ✓ |
| Output months | 72 | 72 | 72 | 72 | 72 |
| Months marked missing | 0 | 0 | 0 | 0 | 0 |
| Tier-3 log lines | 0 | 0 | 1 | 2 | 1 |

If you want to break the algorithm to convince yourself it does fail
loudly when it should, edit `generate.py` to also gap-out **all the
other Junes** (so no donor exists), and rerun Scenario 4. The two
gappy Junes will land in the output as `-99.99` sentinels, and the
report will log a `No tier-3 donor available — month marked missing`
line for each one (added by the algorithm-hardening pass — silent
failure used to be possible and was a real footgun).
