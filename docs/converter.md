# Converting Pitman `.ANS` files

Disag and Exceed read monthly data in the **NinhamShand `.MON`** layout.
But a lot of monthly streamflow comes out of the **Pitman model** as a
`.ANS` file. The converter bridges the two so you don't have to retype a
record by hand.

```bash
python3 -m disag.convert PUNRQ6.ANS PUNRQ6.MON
```

The desktop Disag GUI wires the same step to a **Convert .ANS to .MON…**
button.

## Why a dedicated converter (the format trap)

A `.ANS` file *looks* whitespace-separated, but it is really
**fixed-width 8-character columns** (a year, then 12 hydro-year monthly
values, then a total and an average). In a wet year a single monthly
value can fill the entire 8-character field and run straight into the
next column:

```
14639.1213670.74
```

Here `14639.12` and `13670.74` are two separate values with no space
between them. A naïve `.split()` reads that as one token and silently
corrupts the row — exactly the kind of error that produces a plausible
but wrong answer downstream. The converter always slices by column
position, so wet years survive intact.

## What it does (and doesn't) change

The `.ANS` hydro-year layout (October → September, row labelled by its
start year) already matches the `.MON` convention, so **no month
reshuffling is needed**. The converter only:

- prepends the 5-line `.MON` header (titles in `Oct … Sep` order), and
- drops the trailing total/average columns and the `AVERAGE` summary row.

Everything else — the monthly volumes, the year labels, the row order —
passes through unchanged.

## Command-line options

```bash
python3 -m disag.convert SRC.ANS [DST.MON] [--quiet]
```

| Argument | Meaning |
|----------|---------|
| `SRC` | Source `.ANS` file (required) |
| `DST` | Destination `.MON` file (optional — defaults to the source name with a `.MON` extension) |
| `--quiet`, `-q` | Suppress the summary printed to stderr |

On success it reports how many hydro-year rows it wrote and the year
range, plus a count of any non-data lines it skipped (the `AVERAGE`
trailer and blank lines — normally 0–2):

```
wrote 73 hydro-year rows (1920–1992) to PUNRQ6.MON
skipped 1 non-data line(s) (AVERAGE trailer / blanks)
```

If no parseable data rows are found, the converter exits with an error
rather than writing an empty file.

## Related

- [File formats](file-formats.md) — the full `.MON` and `.ANS` column
  layouts.
- [Using Disag-MD](usage.md) — once converted, feed the `.MON` into
  `disag` or `exceed`.
