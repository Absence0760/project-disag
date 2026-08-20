---
description: Hunt for untested behaviour and invariants and backfill the right layer of tests — no bug required. The proactive, area-scoped counterpart to the diff-scoped test-gap-checker. Commits scoped; never pushes.
argument-hint: "[optional scope — a module, route, feature, or path, e.g. src/retention.ts, 'the audit hash chain'; omit to pick an under-covered area]"
---

Find behaviour that *works but isn't tested* and lock it in with tests at the layer the repo's conventions call for. Unlike `/bug-hunt` (whose deliverable is a fix) and the diff-scoped `test-gap-checker` agent (which reviews a working diff), `/coverage-hunt` proactively hardens an **area** of already-landed code — the honest "the deliverable is the coverage gap" command. If you trip over a real bug while writing the tests, fix it (that's a `/bug-hunt`-style win) — but the goal here is durable coverage, not a fix.

`$ARGUMENTS` is an optional scope. If empty, pick an under-covered area (step 1).

**When to use this vs the siblings:** `/coverage-hunt` = behaviour that works but isn't tested (deliverable: tests). `/bug-hunt` = go wide, find real correctness bugs (deliverable: fix + regression test). `/audit-and-fix` = deep-audit ONE named area, fix, ship tests. `/perf-hunt`, `/ux-hunt`, `/a11y-hunt` = the same hunt shape aimed at performance, UX, and accessibility respectively.

## Operating rules (non-negotiable — root `CLAUDE.md` guard rails)

- **Test real behaviour, not the implementation.** Assert the observable contract and the invariant a regression would break — not internal call shapes. A test that only restates the code teaches nothing and breaks on every refactor.
- **It must be able to fail.** A test that can't fail is worse than none. Sanity-check by reverting the behaviour mentally (or briefly in fact) — if the test stays green, it's not testing anything. Cover the edges (null/empty/zero/unicode/boundary/concurrent/out-of-order), not just the happy path.
- **No masking, ever.** No sleeps, inflated timeouts, retries, or loosened assertions to make a test pass. Wait on real signals (a `data-ready` attribute backed by real state, an exposed status, a sentinel event, a network response). If a deterministic wait needs a new app affordance, add it as a real readiness signal. ("Fix bugs at the source.")
- **Match the layer + the tooling.** Put each test at the layer that owns the behaviour, using the repo's own runner and package manager — the project's test layers (unit / integration / e2e — whatever this repo actually uses). Pure logic → the fast unit layer (no DB/network). DB/HTTP behaviour → the integration/smoke layer (spawn the server, hit real endpoints, use the project's test-DB bring-up). User-visible behaviour → the browser/e2e layer against the running stack. Follow the conventions and directory layout the project already documents.
- **Deterministic + parallel-safe.** e2e specs may run against shared or per-worker seed data — prefer read-only assertions, unique nonces for any writes, and don't depend on additive-seed counts being exact. Wait on real readiness signals, never sleeps.
- **Commit scoped; never push.** `test(...)` commits, path-scoped (`git commit -m "…" -- <paths>`). No `Co-Authored-By` / AI-attribution trailer. (Git workflow.)

## Procedure

### 1. Find the gap

- **If `$ARGUMENTS` is given:** that's the area.
- **If empty:** map source → tests and rank by exposure. For each layer, list the source modules and match them against their dedicated test files; the modules with the thinnest coverage relative to their logic density are the candidates. Rank by **logic density × thin-or-no coverage × hot path**. Skip generated / type / config / migration / seed files. State your pick + why in one line. (The `Explore` agent is the fast way to map source ↔ tests across layers.)
- For the chosen area, **enumerate the untested behaviours**: each branch, each error path, each documented invariant (the project's `CLAUDE.md` invariants / "Key constraints" and inline comments are a checklist of promises that should each have a test), each edge case. List them before writing — that list is the work.

### 2. Confirm current behaviour

Run the code / read the contract so the test encodes what the app *actually does today* (not what you assume). For a backend service or pure fn, call it under the test runner; for an HTTP route, hit the endpoint; for frontend, drive it in the running stack. If today's behaviour looks wrong, that's a `/bug-hunt` finding — fix it and test the corrected behaviour (don't enshrine a bug in a test).

### 3. Write tests that lock the contract

- One assertion cluster per behaviour/invariant from the step-1 list. Name tests so a failure reads as a sentence about what broke.
- Include the edges and the failure paths (4xx/empty/duplicate/out-of-order/concurrent), not just the happy path.
- For e2e, anchor on stable selectors + real readiness signals; keep writes nonce-tagged and assertions tolerant of additive-seed volume.

### 4. Verify

- Run the new tests (they pass) **and** prove they can fail — flip the behaviour briefly or reason it through explicitly; a test you haven't seen fail is unverified.
- Run the nearby existing suite to prove no collision; report pass/fail counts faithfully.
- Run the project's type/lint gate (e.g. `pnpm check`) if you touched any non-test code (e.g. added a readiness attribute).

### 5. Commit (scoped) — never push

`test(<area>): …` commits, path-scoped. If you added a real app affordance for determinism (a readiness signal), that's a separate non-test commit with its doc update. **Never `git push`.** No co-author / "Generated with" trailer.

## Report

```
## /coverage-hunt — <area>

**Picked:** <area> — <one-line why it was under-covered> (omit if named)

**Behaviours/invariants now covered:** <bulleted list — each with its layer (unit/integration/e2e)>

**Tests added:** <files + count>

**Bug found while testing:** <if any: what + fix — else "none; behaviour matched the contract">

**Verification:** <new tests N/N; can-fail check done; nearby suites N/N; type/lint gate if touched>

**Commits:** <hash + subject>

**Still uncovered (recommended next):** <behaviours intentionally left — or "area is now well-covered">
```

## Tone

The deliverable is honest coverage, not a vanity green. Name what's now locked in and what you deliberately left. If you couldn't make a test able to fail, say why and don't ship it.
