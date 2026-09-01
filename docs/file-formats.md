# File Formats

All files are plain text (ASCII). Values use `-99.99` (or any negative number)
as the missing-data sentinel.

---

## Daily file (`.day`)

### Header (12 lines)

```
--------------------------------------------------------------------------------
Description   : <filename>
Units         : m3/s
Disaggregated    (monthly) : <monthly input filename>
Disaggregator,1  (daily  ) : <daily file 1 filename>
Disaggregator,2  (daily  ) : <daily file 2 filename>
Disag method  : <method description>
-
-
Run Date      : <YYYY-MM-DD HH:MM:SS>
--------------------------------------------------------------------------------
<blank line>
```

### Data records — one per calendar month

**Line 1 — month header**

```
 YYYY MM   TTTTTT
```

| Field | Width | Columns | Description |
|-------|-------|---------|-------------|
| Year  | 5 chars (`%5d`, right-justified) | 1–5 | Calendar year |
| Month | 3 chars (`%3d`, right-justified) | 6–8 | Calendar month (1–12) |
| Total | 8 chars, 3 decimal places | 9–16 | Monthly total in Mm3 (sum of daily values converted from m3/s) |

The three fields are written with no separators
(`{year:5d}{month:3d}{total:8.3f}`), giving a **fixed 16-character line**;
the gaps you see in examples are just field padding.

The Pascal wrote this as `year:3, month:3, total:10:3`
(`delphi_files/uFiles.pas:372`), which also lands on 16 characters — but only
for the 2-digit years of the era (` 51  6     0.000`). A 4-digit year
overflows the 3-wide field to 4 characters, dropping the leading space and
shifting every column right by one, so the line runs to 17. Downstream
fixed-format readers mis-slice every field after the year. The widths above
keep the line at 16 for 4-digit years, which is what real files carry.

Readers should still tolerate a 2-digit year (`if year < 1900: year += 1900`)
— archive files predating the fix carry them.

**Lines 2–5 — daily values**

Each day value occupies exactly **7 characters**, right-justified:

- 3 decimal places for values 0–99
- 2 decimal places for values 100–999 or any negative (missing)
- 1 decimal place for values > 999

Values are right-justified into their 7-char fields with no separator between
them, so a value that fills the whole field abuts its neighbour (e.g. two
`12345.6`-style readings become `12345.612345.6`) — never `.split()` a daily
line; slice it in fixed 7-char columns. The missing-day sentinel `-99.99` is
only 6 characters, so it renders as ` -99.99` (one leading space).

Days 1–28 appear on four lines of 7 values each (49 characters per line).

| Line | Days |
|------|------|
| 2 | 1–7 |
| 3 | 8–14 |
| 4 | 15–21 |
| 5 | 22–28 |

For months with more than 28 days, a 6th line contains the remaining 1–3 values.
For February (28 days), line 6 is blank.

**Example — October (31 days)**

```
1990 10    37.336
 37.336 37.336 37.336 37.336 37.336 37.336 37.336
 37.336 37.336 37.336 37.336 37.336 37.336 37.336
 37.336 37.336 37.336 37.336 37.336 37.336 37.336
 37.336 37.336 37.336 37.336 37.336 37.336 37.336
 37.336 37.336 37.336
```

---

### Two-column export

`python -m disag.columns` flattens a `.day` file into one row per calendar
day, for downstream tools that want a plain time series rather than the block
layout:

```
1981/10/01      0.214
1981/10/02      0.225
```

Date column is left-justified in 10 characters, value right-justified in the
next 11. `--style csv` / `--style tab` swap the padding for a delimiter,
`--date-format` takes any `strftime` pattern, and `--header` adds a
`Date`/`Flow` title row.

The CSV form is also a standard output of a disaggregation run, so a consumer
that can't read the block layout needs no second step:

- `python -m disag … --columns` writes `<output>-columns.csv` next to the
  `.day` and `.rep` (`--columns PATH` to place it elsewhere).
- Every web `/disag` run publishes `output.csv` alongside `output.day` and
  `output.rep`, and the run page offers it as its own download.

Both flatten the `.day` file just written rather than the in-memory series, so
the CSV is provably the same numbers the `.day` carries. They emit the CSV
style with no header — for a different delimiter, date format or a title row,
run `python -m disag.columns` against the `.day` afterwards.

Every calendar day of every month in the source gets a row, **missing days
included** — they carry the `-99.99` sentinel. Dropping them would leave a
gap the consumer cannot distinguish from a month that was never in the file.
Values keep the decimal convention above, so they render identically in both
formats.

## Pitman monthly output (`.ANS`) — and converting to `.mon`

Some upstream tools (the Pitman stochastic streamflow model in particular)
emit monthly output in a `.ANS` file rather than the NinhamShand `.MON`
layout the disag tool reads. The `.ANS` layout is **fixed-width 8-character
columns** — year, then 12 monthly values, then total + average — with a
final `AVERAGE` summary row and optional blank padding.

Critically, the columns are **not whitespace-separated**: in wet years a
value can fill the full 8 characters and butt directly against the next
column (e.g. `14639.1213670.74`). Parsing with `.split()` silently
truncates the leading digit of the second value — we have seen
customer-side converters mis-record `14639.12` as `4639.12` this way.

The bundled converter slices by column position and handles this case:

```bash
python3 -m disag.convert path/to/input.ANS path/to/output.MON
python3 -m disag.convert path/to/input.ANS          # dst defaults to input.MON
```

The destination is optional — omit it and the converter writes alongside
the source with the extension swapped to `.MON`. It also skips the
trailing `AVERAGE` row and any blank lines, and prepends the five-line
NinhamShand `.MON` header (see below). The same logic is wired into the
disag GUI as a **Convert .ANS to .MON…** button. The output is keyed by
**hydro year** (Oct→Sep), matching the `.ANS` row layout exactly, so no
month reshuffling happens.

---

## Monthly file (`.mon` / `.nat` / `.cur`)

### Header (5 lines)

The first 5 lines are skipped by the reader. Real NinhamShand files (and the
`.ANS → .MON` converter's output) use a fixed shape: a `File name :` line, a
`Units     :` line, a blank line, a `Year  Oct … Sep` column-title row, and a
rule of dashes the same width as a data row. The reader only counts the lines,
so any 5-line header works, but the converter emits this layout so its output
is byte-compatible with the reference tooling.

```
File name : ef6-nat.mon
Units     : M.m3

Year      Oct      Nov      Dec      Jan      Feb      Mar      Apr      May      Jun      Jul      Aug      Sep
----------------------------------------------------------------------------------------------------------------
```

Data values are written as **contiguous 9-char columns** (year `%4d`, then
twelve `%9.3f` fields). In a wet year two full-width values can touch with no
separator (e.g. `14639.12013670.740`); `read_monthly_file` falls back to
fixed-width slicing for those rows, the same trap documented for `.day` files.

### Data records — one per hydro year

One line per hydro year, space-separated:

```
YYYY  V1  V2  V3  V4  V5  V6  V7  V8  V9  V10  V11  V12
```

| Field | Description |
|-------|-------------|
| `YYYY` | Hydro year start (the October of this year begins the record) |
| `V1`  | October — Mm3/month |
| `V2`  | November |
| `V3`  | December |
| `V4`  | January of year+1 |
| …     | … |
| `V12` | September of year+1 |

**Example**

```
1990  100.0  95.3  88.7  72.1  61.4  55.0  49.8  60.2  75.3  88.9  92.1  98.4
```

This record covers October 1990 through September 1991.

---

## Report file (`.rep`)

Plain text log produced alongside each output file. Its core is a
**decision log with one row per month, for every method** — so you can
read straight down it to see what happened to each month and why. Each
row carries:

- `F1` / `F2` / `OTH` — the number of days that month sourced from daily
  file 1, daily file 2, and a patched / donor / even source respectively.
- a `result / source` note — `disaggregated from file 1`, `patched from
  similar calendar month YYYY MM` (method 1), `patched from donor:
  file N YYYY MM (exceed% …)` (method 5), `even distribution`, or
  `MISSING — <reason>`. Method 5 also explains its file-2 fallbacks
  inline: `disaggregated from file 2 (file 1 fully missing; file-2 →
  file-1 scale ×N)` when file 1 has no usable day that month, and
  `disaggregated from file 1, gaps filled from file 2 (K day(s),
  file-2 → file-1 scale ×N)` when file 2 only patched some days — the
  `×N` is the per-month rescaling factor from the table above. When the
  `daily_fdc_mapping` knob is on, that scale-factor clause reads
  `file-2 → file-1 FDC-mapped` instead; when `seam_blend` corrected one
  or more gap runs in the month the note gains a `(seam-blended K
  gap(s))` suffix. A month that fell back to an even split because the
  observed monthly total was ≤ 0 is annotated inline.

Method 5 (PATCH_EXCEED) appends a tier coverage summary, a donor
match-quality block when any tier-3 donor fired, and an **injected-day
spike audit** (always present when any day was injected) listing how
many tier-2/tier-3 days exceed file 1's same-calendar-month observed
maximum, plus the worst offenders. When the corresponding knobs are on,
a daily-FDC-mapping summary (days mapped / extrapolated / fallback
months) and a seam-blending summary (gap runs blended) follow. Any
pre-run warnings (zero-target months, sparse/flat distributions,
file-2 → file-1 scale factors, enabled-knob banners) precede the log.
See [method5.md](method5.md#injected-day-normalisation-optional).

```
--------------------------------------------------------------------------------
Disag Report  : 2026-03-28 14:32:01
Method        : Distrib with file 1, Patched with similar month
--------------------------------------------------------------------------------
Decision log (one row per month):
YYYY MM   F1  F2  OTH   result / source
1975  2   28   0   0   disaggregated from file 1
1975  3    0   0  31   patched from similar calendar month 1982  3
1981  8   31   0   0   disaggregated from file 1 (Observed monthly flow <= 0 — even fill)
--------------------------------------------------------------------------------
Months written     : 840
  Disaggregated    : 838
  Missing (-99.99) : 2  (0.2%)
```
