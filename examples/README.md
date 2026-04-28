# examples/

Runnable demos, one per disaggregation method (plus one for the
`exceed` tool). Each is a small, deterministic mock dataset plus a
walkthrough that shows what the tool does when invoked from the CLI.

## `disag` (disaggregation, monthly → daily)

| Method | Demo | What it shows |
|--------|------|---------------|
| 0 — `ONE_FILE`    | [method0_demo/](method0_demo/) | Whole month dropped when any day is missing |
| 1 — `PATCH_CAL`   | [method1_demo/](method1_demo/) | Closest-volume same-month patching from another year |
| 2 — `PATCH_FILE`  | [method2_demo/](method2_demo/) | Day-level fallback from file 1 to file 2 |
| 3 — `INCREMENTAL` | [method3_demo/](method3_demo/) | Sub-catchment runoff from `file 1 − file 2` |
| 4 — `EVEN`        | [method4_demo/](method4_demo/) | Equal flow on every day of the month |
| 5 — `PATCH_EXCEED`| [method5_demo/](method5_demo/) | Three-tier chain with cross-river exceedance-matched donor |

## `exceed` (flow-frequency / exceedance analysis)

| Demo | What it shows |
|------|---------------|
| [exceed_demo/](exceed_demo/) | Three modes in one folder — Basic per-calendar-month curves (CLI), Seasonal grouping (driver script), and monthly↔daily Matching (driver script). |

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

The `exceed_demo/` directory follows the same shape but also contains
a `seasonal.py` and `matching.py` driver because those two modes are
not in the exceed CLI today.

## What each demo proves

The end-to-end test suites drive every demo and assert the documented
counts and outputs, so each walkthrough README and the algorithm don't
drift apart:

- `tests/test_demo_methods.py` — disag methods 0–4 plus PATCH_CAL edge cases
- `tests/test_e2e.py` — disag method 5 (PATCH_EXCEED) scenarios
- `tests/test_exceed_demo.py` — exceed Basic / Seasonal / Matching modes
