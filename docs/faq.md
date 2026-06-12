# FAQ & troubleshooting

Common questions and the fixes for the errors people actually hit. If
something here points at a deeper write-up, follow the link.

### My whole month came out as `-99.99` (missing)

You're almost certainly on **method 0**, which drops *any* month that has
even one missing day in the daily reference. If the gauge has gaps, switch
to a patching method:

- **Method 1** backfills missing days from the closest same-calendar-month
  year.
- **Method 5** fills from an exceedance-matched donor — and works even when
  the donor is a different river.

The CLI prints this same nudge when a method-0 run loses more than half its
months. See [the method guide](algorithm.md).

### Which method should I use?

Pick the cheapest one that still gives a usable signal:

- One clean gauge, happy to drop gappy months → **0**
- One gauge with occasional gaps → **1**
- A second gauge to fall back on → **2**
- You want the runoff *between* two gauges → **3**
- No daily record anywhere → **4**
- Both gauges have holes / you want to borrow another river → **5**

The [Choosing a method](/docs#methods) section of the overview has a
decision diagram, and [method5.md](method5.md) covers the cross-river case.

### How many daily files does each method need?

| Method | Daily files |
|--------|-------------|
| 0 One file | 1 |
| 1 Patch (calendar) | 1 |
| 2 Patch (file) | 2 |
| 3 Incremental | 2 |
| 4 Even | 0 |
| 5 Patch (exceedance) | 1 (file 2 optional) |

The tool only asks for the files a method actually uses.

### Method 5 ran fine but warns that most days are "tier-3 synthetic"

That's expected when both your daily files have large gaps. Tier-3 days are
filled by copying the *shape* of a percentile-matched donor month; only the
monthly **volume** comes from your input. The `.rep` report logs every
donor choice so you can judge how much of the output is borrowed. See
[method5.md](method5.md).

### Exceed said "analysis complete but nothing was written"

Exceed computed the curves but you didn't give it anywhere to put them.
Pass `--output FILE.rep` (and/or `--svg FILE.svg`). See
[Using Disag-MD](usage.md).

### The GUI won't open — `tkinter` import error

On macOS, Apple's stock Python ships a broken `_tkinter`. Install Homebrew
Python and its Tk bindings:

```bash
brew install python@3.14 python-tk@3.14
python3.14 -m disag
```

If you can't get a GUI at all, every feature is available from the command
line with `--no-gui`.

### My `.day` file parsed wrong — one month has a huge value count

`.day` files are **fixed-width** (7-character columns), not
whitespace-separated, and the first number on each record is a *monthly
total*, not a daily value. If you hand-edited the file or ran it through a
tool that re-spaced the columns, the layout breaks silently. Re-export it
cleanly. The exact rules are in [file formats](file-formats.md).

### Disag won't read my Pitman `.ANS` file

It isn't meant to — `.ANS` is the Pitman model's own format. Convert it to
`.MON` first:

```bash
python3 -m disag.convert PUNRQ6.ANS PUNRQ6.MON
```

See the [converter guide](converter.md).

### What's the `.rep` file for?

It's the decision log — a per-month record of which days came from file 1,
file 2, or a donor, plus any warnings. It's how you tell real output from
synthetic. Always keep it next to the `.day` it describes.

### What does a negative flow value mean?

Nothing physical — it's the **`-99.99` missing-data sentinel**. Any
negative value is treated as missing. See the [glossary](glossary.md).
