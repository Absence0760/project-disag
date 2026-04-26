# examples/

Runnable demos, one per disaggregation method. Each is a small,
deterministic mock dataset plus a walkthrough that shows what the
method does when invoked from the CLI.

| Method | Demo | What it shows |
|--------|------|---------------|
| 0 — `ONE_FILE`    | [method0_demo/](method0_demo/) | Whole month dropped when any day is missing |
| 1 — `PATCH_CAL`   | [method1_demo/](method1_demo/) | Closest-volume same-month patching from another year |
| 2 — `PATCH_FILE`  | [method2_demo/](method2_demo/) | Day-level fallback from file 1 to file 2 |
| 3 — `INCREMENTAL` | [method3_demo/](method3_demo/) | Sub-catchment runoff from `file 1 − file 2` |
| 4 — `EVEN`        | [method4_demo/](method4_demo/) | Equal flow on every day of the month |
| 5 — `PATCH_EXCEED`| [method5_demo/](method5_demo/) | Three-tier chain with cross-river exceedance-matched donor |

## How each demo is structured

```
methodN_demo/
├── README.md     — walkthrough: what the demo shows, the CLI command,
│                   the expected report output
├── generate.py   — deterministic generator (fixed RNG seeds)
└── data/
    ├── target.MON        — mock monthly volumes
    └── *.DAY             — mock daily records, possibly with engineered gaps
```

Re-run any generator with `python3 examples/methodN_demo/generate.py`;
output files are byte-identical between runs.

## What each demo proves

The end-to-end test suite (`tests/test_demo_methods.py`) drives every
demo and asserts the documented coverage / patch counts, so the
walkthrough README and the algorithm don't drift apart.
