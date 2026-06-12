# Disaggregation Algorithm

## Core formula

For each day `d` of month `(y, m)`:

```
Qgen_daily[d] = Qgen_monthly × (Qobs_daily[d] / ΣQobs_daily) × 1e6 / 86400
```

| Symbol | Units | Description |
|--------|-------|-------------|
| `Qgen_monthly` | Mm3/month | Generated monthly flow from the input `.mon` file |
| `Qobs_daily[d]` | m3/s | Observed daily flow used as the distributional shape |
| `ΣQobs_daily` | m3/s | Sum of all daily observed values over the month (the denominator) |
| `Qgen_daily[d]` | m3/s | Output disaggregated daily flow |

The factor `1e6 / 86400` converts Mm3/day to m3/s.

If the observed monthly total (`ΣQobs_daily`) is zero but the generated monthly
flow is positive, the month falls back to even distribution and the event is
logged in the report file.

---

## Hydro year convention

The tool uses a **hydro year** that runs from **October to September**.
The monthly input file stores one record per hydro year (12 values: Oct, Nov,
Dec, Jan, …, Sep). Processing always starts on 1 October of the first hydro
year present in the monthly (`gen_monthly`) file and runs to its last month;
the daily reference files do not clamp this window (they only gate patching).

---

## Missing data sentinel

Any value `< 0` is treated as missing. The output sentinel is `-99.99`.

---

## Methods

### 0 — One disaggregator

```
Qobs_daily[d] = daily_file_1[d]
```

The entire month is marked missing if any day in file 1 is missing.

---

### 1 — Patch with similar month (`PATCH_CAL`)

Same as method 0, but if any day in file 1 is missing the tool searches all
other years for a **complete** month of the same calendar month whose generated
monthly volume is closest to the target month. If a suitable year is found, it
is used as a day-level patch: on each day where file 1 is valid, file 1 is
used; on each day where file 1 is missing (value `< 0`), that day's value is
taken from the patch year's daily record. Candidate months whose length differs
from the target month (the leap-February case) are filtered out, mirroring
method 5. The substitution is logged once per month in the report file.

If no complete substitute month exists, the output month is set to missing.

---

### 2 — Patch with file 2 (`PATCH_FILE`)

```
Qobs_daily[d] = file_1[d]   if file_1[d] >= 0
              = file_2[d]   otherwise
```

A day is only marked missing if **both** files are missing on that day.

Before the start date of file 2 the method falls back to method 0 (file 1 only).

---

### 3 — Incremental catchment (`INCREMENTAL`)

```
Qobs_daily[d] = file_1[d] − file_2[d]
```

Both files must be present for every day; any missing value in either file
marks the month as missing.

Negative differences are clamped to zero before summing.

---

### 4 — Even distribution (`EVEN`)

```
Qobs_daily[d] = 1   for all d
```

No daily file is required. Each day receives an equal share of the monthly
total, so the output daily flow is constant within a month.

---

### 5 — Patch with exceedance-matched donor (`PATCH_EXCEED`)

> **See also** [method5.md](method5.md) for the rationale, worked
> numerical example, and edge-case discussion, and
> [examples/method5_demo/](../examples/method5_demo/) for a runnable
> demo on small mock data.

A three-tier chain that combines methods 0/2 with a cross-river donor
month for the case where neither daily file has any data for the target
month. Designed for the common situation where the **target river**
(the one supplied as `gen_monthly`) and the **donor river** (the one
supplied as daily files) are different rivers in the same area: their
absolute volumes differ but their wet/dry years track each other, so a
match by **exceedance percentile** carries across rivers in a way that a
match by absolute volume does not.

Accepts 1 or 2 daily files. With one file, tier 2 is skipped.

**Tier 1 — file 1.**
```
Qobs_daily[d] = file_1[d]   if file_1[d] >= 0
```

**Tier 2 — file 2.** For each day still missing after tier 1:
```
Qobs_daily[d] = file_2[d]   if file_2[d] >= 0
```

**Tier 3 — exceedance-matched donor.** If any day is still missing in
the target month after tiers 1 and 2:

1. Let `V_target = gen_monthly[(year, month)]`. Compute its exceedance
   percentile `p_target` within the distribution of `gen_monthly`
   restricted to the same calendar month — that is, rank `V_target`
   among all years' volumes for this calendar month and convert the
   rank to a percentile.
2. Aggregate each daily file into per-`(year, month)` totals, restricted
   to the same calendar month. Pool the years from file 1 and file 2
   whose daily record for that month is **complete** (no missing days).
   Compute each candidate's exceedance percentile within its own daily
   file's per-calendar-month distribution. Candidates whose donor month
   has a different number of days than the target (the Feb leap-year
   case) are filtered out so day-d copying always lands inside the
   donor's record.
3. Pick the candidate whose percentile is closest to `p_target`.
   Tie-break in order: smallest `|donor_year − year|`, then smaller
   file index (so file 1 wins over file 2 on otherwise-equal matches).
4. For each day still missing in the target month, copy the donor's
   day-d value into `Qobs_daily[d]`. Days already filled by tier 1 or
   tier 2 are kept as observed.
5. If no eligible donor exists (no candidate year has a complete record
   for that calendar month in either daily file, or `gen_monthly` has
   fewer than two values for this calendar month), mark the whole
   month as missing.

The substitution is logged once per month in the report file, recording
the donor file, donor year, `p_target`, and the donor's matched
percentile.

The percentile is computed by **rank**, not by binning:

```
p = 100 × (count of values ≥ value) / n
```

So the smallest value in a distribution gets `p = 100 %`, the largest
`p = 100 / n %`. Both `p_target` and `p_donor` use this same formula on
their respective distributions, so the comparison `|p_donor − p_target|`
is well-defined. This is independent of the binned exceedance computation
in the `exceed` tool and avoids interval-edge artefacts.

**Run window.** Every method (0–5) iterates over the full hydro-year
span of `gen_monthly` — the daily files do **not** clamp the window
on either end. Output length therefore always equals `gen_monthly`'s
hydro span, so the `.day` file is self-describing: months outside the
daily file's coverage are emitted explicitly rather than silently
dropped. What gets emitted depends on the method:

- **Method 5** backfills via tier-3 percentile-matched donor months
  where possible, using the same logic as for internal gaps.
- **Method 1 (`PATCH_CAL`)** opportunistically patches via its
  existing same-calendar-month / closest-volume search, which now
  applies to backfilled months too if a complete same-month exists
  somewhere in file 1.
- **Method 2 (`PATCH_FILE`)** uses file 2 wherever it covers; days
  with neither file produce a `-99.99` sentinel.
- **Methods 0 and 3** emit `-99.99` sentinels for clipped months
  (no patching logic).

Method 5's tier-3 backfill is still the only mechanism that produces
synthetic-but-plausible daily *shape*; the others just propagate
real data or sentinels. When `gen_monthly` is much longer than the
daily record, Method 5's percentile-match accuracy degrades with
short donor pools — see the limitations in [method5.md](method5.md).

**Cross-river rescaling (tiers 2 and 3).** When file 1 and file 2 are
on different rivers (different absolute scales), file-2 day values
must be brought up to file-1's scale before they enter `qD`. The
algorithm multiplies them by `mean(file_1[m]) / mean(file_idx[m])`
(per calendar month, with global-mean fallback) at both:

- **Tier 2** — every file-2 day used to patch a missing file-1 day;
- **Tier 3** — every donor day copied from a file-2 donor month.

Without this rescale, a mixed-source month (some days file-1, some
days file-2 via tier 2 or tier 3) gets a distorted daily shape: the
file-2 days appear as an artificial drop or spike purely because of
the cross-river scale mismatch. Whole-month tier-2 or tier-3 fills
where every day comes from file 2 are unaffected — the constant
factor cancels in the disag formula's `qD/qM` ratio.

**Report contents (PATCH_EXCEED specifically).** The `.rep` file logs:

- per-month tier-3 patches (donor file, donor year, `p_target`, donor
  percentile);
- per-month "no tier-3 donor available" failures, when the algorithm
  cannot find any eligible donor month;
- per-month "donor file N YYYY MM missing day(s) D — month marked
  missing" failures, when a percentile-matched donor turns out to lack
  coverage on a day the target still needs (defence-in-depth in case
  the upstream completeness filter ever changes);
- pre-run warnings: calendar months too sparse for tier 3 in
  `gen_monthly`, **per-file** calendar months too sparse in any daily
  file's donor pool, all-zero target months, and identically-valued
  calendar-month distributions;
- the per-calendar-month tier-2 scale factors (when file 2 is supplied
  and the rescale factor is non-trivial);
- a **per-month tier breakdown table** with one row per iterated month
  showing T1 / T2 / T3 day counts plus the donor info or missing-reason;
- a tier coverage summary at the end (Tier 1 / 2 / 3 day counts and
  month counts).

Contrast with method 1 (`PATCH_CAL`), which matches on absolute
volume within `gen_monthly` only and assumes the donor's daily file
shares the same scale. Method 5 is the right choice when the donor
file is from a different river than the monthly target.

---

## Processing order

1. Read all input files into memory.
2. Determine the run window — **always the full hydro-year span of
   `gen_monthly`**, regardless of how short or long the daily files are.
   This was tightened from the old "intersection of all inputs" rule so
   the output `.day` file is self-describing: months outside the daily
   record are emitted explicitly (with patching, donor backfill, or
   `-99.99` sentinels per the per-method behaviour above) rather than
   silently clipped.
3. Iterate month by month from October of the first hydro year to the
   last `(year, month)` key in `gen_monthly`, applying the chosen
   method.
4. Write the output `.day` file and the `.rep` report.
