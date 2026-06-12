# What problem does this project solve?

This is a hydrology / water-resources tool. It addresses two distinct
problems that come up whenever an engineer or hydrologist has streamflow
data at one time resolution but needs analysis at another.

---

## Problem 1 — Disaggregation: monthly volume, daily shape

### The setup

Long streamflow records are usually available as **monthly totals** in
Mm³/month (million cubic metres, 10⁶ m³, per month). Common sources:

- Stochastic monthly streamflow models (e.g., the WRYM / WRSM family used
  in Southern Africa).
- Historical records summarised to monthly totals.
- Naturalised flow sequences produced for water-resource yield studies.

But many downstream applications need **daily flow** in m³/s:

- Reservoir simulation that responds to short floods.
- Environmental-flow assessments (which days of the month does the flow
  drop below the ecological threshold?).
- Hydropower modelling, water-treatment-plant intake design, irrigation
  abstraction analysis.

You **cannot** just divide the monthly volume by 30 days — that erases all
the within-month variability that drives the engineering decision.

### The idea

Borrow the *shape* from an observed daily record and *scale* it so the
month sums to the desired monthly total.

```
                                Qobs_daily[d]
Qgen_daily[d] = Qgen_monthly × ─────────────── × (1e6 / 86400)
                                ΣQobs_daily
```

The factor `1e6 / 86400` converts Mm³/day to m³/s.

### Worked example

Suppose your stochastic model produced **6.000 Mm³ for June** of some
generated year. You don't have daily data for that month — but you do
have an observed daily record from **June 1964** at a nearby gauge, which
you'll use as the *shape*:

| Day | Observed (m³/s) |
|----|-----|
| 1  | 5.498 |
| 2  | 5.437 |
| 3  | 5.532 |
| …  | …     |
| 30 | 4.083 |

Sum over all 30 days: **141.86 m³/s** (this is `ΣQobs_daily`).

For day 1, the disaggregated daily flow is

```
Qgen_daily[1] = 6.000 × (5.498 / 141.86) × (1e6 / 86400)
             = 6.000 × 0.03876 × 11.574
             = 2.692 m³/s
```

Repeat for each day. The output preserves the *relative* day-to-day
variation of the observed record while matching the *absolute* monthly
volume of the generated record.

### What if the observed record has gaps?

This is the messy part of the problem. Real gauges fail, get vandalised,
or were only installed partway through the period of interest. The tool
gives you six methods to handle it:

| # | Method | What it does when day *d* is missing in file 1 |
|---|--------|------------------------------------------------|
| 0 | One disaggregator | Mark the **whole month** as missing |
| 1 | Patch with similar month | Fill in each missing day from another year whose generated volume for that calendar month is closest, provided that year's instance of the same month is complete |
| 2 | Patch with file 2 | Use file 1 where present, fall back to file 2 otherwise |
| 3 | Incremental | Use `(file 1 − file 2)` as the shape (sub-catchment runoff) |
| 4 | Even distribution | Constant flow on every day — used when no observed record exists at all |
| 5 | Patch with exceedance-matched donor | Use file 1, then file 2; for any day still missing, fill from a donor year whose monthly volume sits at the same exceedance percentile within the donor's distribution as the target's volume does within `gen_monthly`'s. Lets you borrow daily shape from a different river in the same area, since percentile rank carries across rivers when absolute volume does not. See [method5.md](method5.md) for a full write-up and [examples/method5_demo/](../examples/method5_demo/) for a runnable walkthrough. |

The `.rep` report logs every patch and fallback so the user can see where
the output is "real" vs. synthetic.

See [algorithm.md](algorithm.md) for the per-method details and
[file-formats.md](file-formats.md) for the input layouts.

---

## Problem 2 — Exceedance: how often is flow ≥ X?

### The setup

The **flow-duration curve** (FDC) is the workhorse plot of practical
hydrology. It answers: *for what fraction of time does the flow equal or
exceed value X?*

Engineers and ecologists use it constantly:

- **Q95** (the flow exceeded 95% of the time) is the standard low-flow
  index for environmental-flow studies and abstraction licensing.
- **Q50** (the median) is a baseline for water-supply reliability.
- The slope of the FDC at the dry end is a proxy for catchment storage.
- Comparing FDCs by month or season exposes seasonal water-availability
  patterns that an annual FDC averages out.

### The idea

Sort the values, count how many are ≥ each threshold, divide by the total
count, and you have an exceedance %. The tool does this in *interval* form:

1. Divide the value range `[min, max]` into N equal intervals (default 20).
2. Bucket every input value into one interval.
3. Walk down from the top, accumulating counts.
4. Report `(flow_threshold, exceedance_%)` pairs.

Crucially, the tool does this **per calendar month** so January is analysed
separately from July — because in seasonal climates you can't lump them.

### Worked example

`testfiles/SINDILA.MON` has 70 years of monthly volumes. The 70 January
values range roughly 0.29 – 3.82 Mm³. Splitting that range into 20
intervals (`Δ = (max − min) / 20 ≈ 0.177 Mm³`) and bucketing all 70
January values produces:

```
MONTHLY - JANUARY
Total values: 70  Below range: 0  Above range: 1

Exceedance%    Flow Value
  100.00%        0.290 Mm³    ← every January is ≥ 0.29
   97.14%        1.034
   75.71%        2.336
   50.00%        2.708         ← median January volume ≈ 2.7 Mm³
   24.29%        3.080
    8.57%        3.638
    4.29%        3.824         ← only 3 of 70 Januarys exceed 3.82
```

Reading this: in 50% of years, January's flow volume was at least
2.7 Mm³; in only ~4% of years was it ≥ 3.8 Mm³. That's the kind of
statement a yield study or environmental-flow assessment is built on.

### Seasonal grouping

Pure-monthly FDCs are sometimes too noisy with short records. The
`Seasonal` mode lets you pool months into 2 / 3 / 4 seasons before
computing the FDC — so you get one curve for "wet season" and one for
"dry season", each with 6× the sample size.

### Monthly ↔ daily matching

When you've used the disaggregator from Problem 1, a natural sanity check
is: *does the daily output have the same shape as the daily input at
matched exceedance levels?* The `Matching` mode pairs entries from the
monthly and daily exceedance curves where the exceedance % agrees within
a tolerance, so you can spot where the disaggregation distorts the
distribution.

See [exceed.md](exceed.md) for the formulae and [file-formats.md](file-formats.md)
for the input layouts.

---

## Why a dedicated tool?

You could in principle do all of this in a spreadsheet or a few lines of
pandas. The reason a stand-alone tool exists:

1. **The file formats are domain-specific.** `.mon` files are organised by
   *hydro year* (Oct → Sep), not calendar year. `.day` files use a
   fixed-width 7-character daily column with concatenated negative
   sentinels (`-99.990-99.990`) and a monthly-total field on each record's
   header line. Getting these wrong is silent and easy — see
   [../CLAUDE.md](../CLAUDE.md) for the gotchas. A dedicated reader makes
   sure every analysis starts from the same correctly-parsed data.
2. **The patching / fallback logic is non-trivial.** Method 1 in
   particular requires searching across years for a complete observed
   month with the closest generated volume — and logging the substitution
   in a report file. That doesn't fit on a spreadsheet.
3. **Reproducibility.** The same `.day` and `.rep` outputs can be diffed
   between runs; an ad-hoc spreadsheet pipeline cannot.

The original tool — Disag-MD, written in Delphi/Pascal by AJ Greyling
(1991) and maintained by H Beuster (2007) — has been used in Southern
African water-resource studies for decades. This Python port preserves
the file formats and methods so existing inputs and downstream tools keep
working, while making the code easier to read, fix, and extend.
