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
| Year  | ≥ 3 chars (right-justified) | Calendar year |
| Month | 3 chars (right-justified) | Calendar month (1–12) |
| Total | 10 chars, 3 decimal places | Monthly total in Mm3 (sum of daily values converted from m3/s) |

**Lines 2–5 — daily values**

Each day value occupies exactly **7 characters**, right-justified:

- 3 decimal places for values 0–99
- 2 decimal places for values 100–999 or any negative (missing)
- 1 decimal place for values > 999

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

## Monthly file (`.mon` / `.nat` / `.cur`)

### Header (5 lines)

The first 5 lines are free-form text (description, units, source, etc.) and are
skipped by the reader.

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

Plain text log produced alongside each output file. It records:

- Any month where daily data was missing and a patch year was used
  (methods 1 and 2).
- Any month where the observed monthly total was zero but the generated flow
  was positive (fallback to even distribution).

```
--------------------------------------------------------------------------------
Disag Report  : 2026-03-28 14:32:01
Method        : Distrib with file 1, Patched with similar month
--------------------------------------------------------------------------------
1975   3 Observed daily flow < 0,   Patched with 1982   3
1981   8 Observed monthly flow <= 0,   Gen Flow=   5.123
--------------------------------------------------------------------------------
Total adjustments : 2
```
