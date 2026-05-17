# E2E tests (Playwright)

Two suites live here. Both run from the repo root.

## Mocked (fast, no backend) — `pnpm e2e`

Browser-level checks for the SvelteKit frontend. The Playwright
config builds the SPA and serves it with `vite preview` on port 4173. All backend calls are intercepted with `page.route()` — no
Python, no AWS.

```bash
pnpm e2e                # chromium + firefox, headless
pnpm e2e:ui             # interactive runner
```

- `landing.spec.ts` — hero, nav, theme tokens, feature cards.
- `run.spec.ts` — tool/method/file form behaviour, mocked submit.
- `history.spec.ts` — loading skeleton, empty state, populated table,
  error state.

## Integration (real backend) — `pnpm e2e:integration`

Same Playwright runner, but the config also boots
`web/backend/local_server.py` with `LOCAL_S3=1`. That swaps boto3
for an on-disk S3 stub and handles `/_local-s3/{put,get}/...` URLs
in-process, so the real `disag.algorithm` / `exceed.algorithm`
code runs against the deterministic fixtures under
`examples/methodN_demo/data/`. No AWS required.

```bash
pnpm setup              # one-time: pnpm install + Python venv
pnpm e2e:install        # one-time: download Chromium + Firefox
pnpm e2e:integration    # boots vite preview + local_server, runs the suite
pnpm e2e:all            # mocked + integration in sequence
```

- `integration/disag.spec.ts` — one round-trip per method 0–5, plus
  a `/runs` listing check.
- `integration/exceed.spec.ts` — monthly-only, monthly+daily, and a
  400-on-empty-payload check.
- `integration/_fixtures.ts` — shared upload / fetch helpers.

These tests overlap conceptually with the Python suite
(`tests/test_demo_methods.py`, `tests/test_exceed.py`) but assert
on the _user-visible_ artefacts (the `.day` and `.rep` files
fetched through the HTTP layer), not on internal data structures.
Keep the Python tests for algorithm correctness; the integration
specs catch breakage in the handler, S3 wiring, or report writers.

## Adding tests

Drop new specs as `*.spec.ts` (or under `integration/` for the real-
backend suite). Playwright auto-discovers them. The fixtures
directory `examples/methodN_demo/data/` is committed and
deterministic — prefer those over `testfiles/` which is gitignored.
