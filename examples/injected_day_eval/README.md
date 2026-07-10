# Injected-day normalisation — ground-truth evaluation

The runnable source of the results table in
[docs/method5.md → Injected-day normalisation](../../docs/method5.md#injected-day-normalisation-optional).

Method 5's fills borrow days from a different river. This harness
measures how *wrong* those fills are under each knob combination, on
synthetic data where the truth is known: a smooth target river and a
flashy cross-river donor gauge share the same regional rain, the target's
true daily series is punched with gaps, and every filled day is compared
against the value that was punched out.

```bash
python3 examples/injected_day_eval/evaluate.py            # seeds 42 7 123
python3 examples/injected_day_eval/evaluate.py --seed 5   # any other seed
```

Nothing is written to disk — the world is built in memory and the table
prints to stdout. Unlike the other `examples/` directories there is no
committed `data/`; determinism comes from the fixed seeds.

## What the columns mean

| column | meaning |
|---|---|
| `injMAE` / `injRMSE` | error on the injected (punched) days, m³/s |
| `r_p95` / `r_max` | P95 / max of output ÷ truth on injected days — the "normal flows, then one huge day" symptom is a large `r_max` |
| `realMAE` | error on the *real* days of months containing fills — the monthly-sum normalisation spreads an inflated fill onto the observed days too |
| `seamMAE` | \|output step − true step\| across each gap boundary |
| `flags` | injected-day spike-audit count from the `.rep` |

## What it shows

- **FDC mapping is the main win** — fill error drops 60–67 %, the spike
  audit goes to zero, and contamination of real days roughly halves.
- **Seam blending only helps on top of FDC mapping** (best `seamMAE` and
  `realMAE`); alone it *amplifies* mis-scaled fills — which is why the
  report warns when it's enabled without FDC mapping.

The related invariant tests live in
[tests/test_injected_day_properties.py](../../tests/test_injected_day_properties.py),
which reuses the same world construction at a smaller scale.
