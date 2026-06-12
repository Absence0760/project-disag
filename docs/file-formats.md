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
YYY MM  TTTTTTTTTT
```

| Field | Width | Description |
|-------|-------|-------------|
| Year  | 3 chars (`%3d`; a 4-digit year ≥ 1000 simply overflows to 4) | Calendar year |
| Month | 3 chars (`%3d`, right-justified) | Calendar month (1–12) |
| Total | 10 chars, 3 decimal places | Monthly total in Mm3 (sum of daily values converted from m3/s) |

The three fields are written with no separators (`{year:3d}{month:3d}{total:10.3f}`);
the gaps you see in examples are just field padding.

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
  `×N` is the per-month rescaling factor from the table above. A month
  that fell back to an even split because the observed monthly total was
  ≤ 0 is annotated inline.

Method 5 (PATCH_EXCEED) appends a tier coverage summary; any pre-run
warnings (zero-target months, sparse/flat distributions, file-2 → file-1
scale factors) precede the log.

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
