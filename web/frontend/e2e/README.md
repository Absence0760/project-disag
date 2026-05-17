# E2E tests (Playwright)

Browser tests for the SvelteKit frontend. Run from the repo root:

```bash
pnpm e2e                # all browsers, headless
pnpm e2e:ui             # interactive runner
pnpm --filter disag-md-web exec playwright test --debug   # one-off debug
```

The config (`web/frontend/playwright.config.ts`) builds the SPA and
serves it via `vite preview` on port 4173. All backend traffic is
intercepted with `page.route()` — these tests never touch AWS.

Files:

- `landing.spec.ts` — hero, nav, theme tokens, feature cards.
- `run.spec.ts` — tool/method/file form behaviour, mocked submit.
- `history.spec.ts` — loading skeleton, empty state, populated table, error state.

Add new specs as `*.spec.ts` files in this directory.
