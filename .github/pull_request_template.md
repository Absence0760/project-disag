## Summary

<!-- 1–3 sentences on what this PR does and why. -->

## Changes

<!-- Bulleted list of the user-visible or developer-visible changes. -->

-
-

## Surface touched

- [ ] `disag/` (disaggregation package)
- [ ] `exceed/` (exceedance package)
- [ ] `tests/` (Python unittest suite)
- [ ] `examples/` (per-method demos and their generators)
- [ ] `web/frontend/` (SvelteKit)
- [ ] `web/backend/` (Python Lambda handler + local shim)
- [ ] `web/infra/` (Terraform)
- [ ] `web/frontend/e2e/` (Playwright)
- [ ] `packaging/` (PyInstaller build)
- [ ] CI / GitHub Actions (`.github/`)
- [ ] Docs only (`docs/`, `*.md`, `CLAUDE.md`)

## Correctness checklist

<!-- Tick what applies. Untick lines that genuinely don't apply, but
     don't delete the row — so the next reviewer can see you considered
     it. -->

- [ ] Daily-file parsing changes preserve the fixed-width 7-char column rule (no `.split()` on data lines)
- [ ] Hydro-year ↔ calendar-year conversion still correct at the Oct/Sep boundary
- [ ] If touching `PATCH_CAL` / `PATCH_FILE` / `PATCH_EXCEED`, the behaviour was re-derived from `docs/algorithm.md` (the Delphi source has a known backfill bug)
- [ ] Demo data under `examples/methodN_demo/data/` was regenerated via the sibling `generate.py` if its generator changed (the test suite asserts no drift)
- [ ] New `disag/` or `exceed/` code is stdlib-only (no new pip dependencies)
- [ ] Tk-using code stays inside `gui.py` modules (no `import tkinter` at module top-level elsewhere — CI has no display server)

## Web-app safety (if `web/` is touched)

- [ ] `X-Client-Id` is treated as a scoping bucket, not as authentication — no route returns another client's runs
- [ ] Pre-signed URLs keep their TTL + size-condition limits; no `s3:*` wildcard slipped into the Lambda IAM policy
- [ ] No secret has a hardcoded fallback (`os.environ.get('X', '...')`); secrets stay in `web/infra/secrets.enc.yaml` (sops + KMS)
- [ ] No new SSR adapter or `+page.server.ts` (`adapter-static` is non-negotiable for the S3 + CloudFront deploy)
- [ ] CORS, WAF rate limit, CloudWatch log retention, and budget alarms all still bounded after any infra change

## Test plan

<!-- How this was verified. Delete rows that don't apply. -->

- [ ] `python3 -m unittest discover tests` passes locally
- [ ] `pnpm check` passes locally (web stack only)
- [ ] `pnpm e2e` passes locally (mocked backend)
- [ ] `pnpm e2e:integration` passes locally (real local backend against `examples/methodN_demo/data/`)
- [ ] Manual walkthrough on the affected surface (describe below)

<!-- Manual walkthrough notes: -->
