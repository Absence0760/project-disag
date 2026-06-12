# Glossary

Plain-language definitions of the hydrology and tool-specific terms used
throughout these docs. Cross-references link to the fuller write-ups.

### Catchment

The area of land that drains to a given point on a river. Two gauges on
the same river bound an *incremental catchment* — the land between them —
which is what method 3 isolates (`file 1 − file 2`).

### Daily flow

Streamflow measured as a rate, in **m³/s** (cubic metres per second).
This is what the disaggregator produces and what downstream models
(reservoirs, environmental-flow assessments) consume.

### Disaggregation

Turning a coarse **monthly volume** record into a **daily flow** series by
borrowing the day-to-day *shape* from an observed gauge and rescaling it
so the days still sum to the monthly volume. See [problem.md](problem.md)
and [algorithm.md](algorithm.md).

### Donor (month / year)

A complete observed month whose daily *pattern* is copied to fill a gap in
the target month. Method 1 picks a donor from the same calendar month in a
similar-volume year; method 5 picks one at the same *exceedance percentile*
— possibly from a different river. See [method5.md](method5.md).

### Exceedance percentage

For a given flow value, the fraction of the record that equals or exceeds
it. A flow at "Q95" is exceeded 95% of the time (a low-flow level); "Q50"
is the median. Plotted across all values you get a **flow-duration curve**.

### Flow-duration curve (FDC)

The plot of flow value against exceedance percentage — the workhorse plot
of practical hydrology. Exceed builds one per calendar month (or per
season). See [exceed.md](exceed.md).

### Hydro year

A 12-month water year running **October → September**, used because the
Southern-African dry season falls mid-year and you don't want to split a
wet season across two rows. The `.mon` file stores one row per hydro year;
the readers map those into calendar months for you. See
[file-formats.md](file-formats.md).

### Mm³

**Million cubic metres** (10⁶ m³). Monthly volumes are in **Mm³/month**.
The disaggregation formula's `1e6 / 86400` factor converts Mm³/day into
m³/s (there are 86 400 seconds in a day).

### Missing value / sentinel

A day with no observation is written as the sentinel **`-99.99`**. Any
negative value is treated as missing. How a method reacts to a missing day
is the whole point of choosing between methods 0–5.

### Monthly volume

The total flow over a calendar month, in **Mm³**. The input to
disaggregation and the unit of a `.mon` file.

### Naturalised flow

A streamflow sequence adjusted to remove the effect of dams, abstractions,
and other human influence — i.e. what the river *would* have done
undisturbed. A common source of the monthly records this tool starts from.

### Observed record / reference gauge

A real measured daily series from a stream gauge. Disaggregation borrows
its *shape*; it is the `--daily1` / `--daily2` input.

### `.rep` report

The decision-log file every disag run writes alongside its `.day` output.
It records, month by month, which days came from file 1, file 2, or a
donor — so you can see where the output is real versus synthetic.

### Seasonal grouping

Pooling the 12 calendar months into 2, 3, or 4 seasons before computing an
exceedance curve, so a short record gives a smoother curve with a larger
sample per season. See [exceed.md](exceed.md).

### Streamflow

The volume of water flowing past a point in a river over time — the
quantity everything here measures, whether as a monthly volume (Mm³) or a
daily rate (m³/s).
