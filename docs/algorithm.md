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
Dec, Jan, …, Sep). Processing always starts on 1 October of the first complete
hydro year covered by all input files.

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
taken from the patch year's daily record. The substitution is logged once per
month in the report file.

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

## Processing order

1. Read all input files into memory.
2. Determine the start date: the latest of:
   - The hydro-year start implied by each daily file's first record.
   - The first October in the monthly file.
3. Determine the end date: the earliest last record across all files.
4. Iterate month by month from start to end, applying the chosen method.
5. Write the output `.day` file and the `.rep` report.
