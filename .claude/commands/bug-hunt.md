---
description: Go wide hunting for real correctness bugs across the project — reproduce each with a probe, confirm it's real, fix at the root, lock it with a regression test, then sweep sibling paths. Multi-round; commits scoped; never pushes.
argument-hint: "[optional scope — a layer, feature, or path, e.g. 'the normalizers', 'live ingestion', src/routes/runs.ts; omit to let it choose high-yield targets]"
---

Hunt for genuine correctness bugs and land the fixes. This is the **cross-cutting, multi-round** companion to `/audit-and-fix` (which deep-audits a single named area) and the read-only `/audit/*` sweeps: `/bug-hunt` ranks high-yield targets, finds bugs in each, **proves them with a runnable probe before believing them**, fixes the root cause, ships a regression test that would fail on the old code, and then sweeps the sibling paths that share the same pattern.

`$ARGUMENTS` is an optional scope (a layer, feature, or path). If empty, you pick targets (step 1).

**When to use this vs the siblings:** `/bug-hunt` = go wide, prove each bug with a probe, fix at root, sweep siblings (breadth, multi-round). `/audit-and-fix` = deep-audit ONE named area (depth). `/coverage-hunt` = harden behaviour that works but isn't tested (no bug required). `/perf-hunt`, `/ux-hunt`, `/a11y-hunt` = the same hunt shape aimed at performance, UX, and accessibility.

## Operating rules (non-negotiable — root `CLAUDE.md` guard rails)

- **Prove it before you believe it.** A bug isn't real until you've reproduced it — a failing probe (a throwaway unit/integration test, a replay of a recorded payload, a browser snippet, or a direct query). Discard plausible-but-wrong findings; a hypothesis you can't reproduce is not a finding. Delete throwaway probes before committing.
- **Fix the root cause — never mask.** No inflated timeouts, sleeps, retries, loosened assertions, or swallowed errors. If you can't fix it now, surface it explicitly and file a tracked follow-up. ("Fix bugs at the source.")
- **Be honest when there's no bug.** If a target is sound, say so and make the deliverable the coverage gap you closed — never invent a "fix" to justify the command.
- **Respect the project's documented invariants.** Never bypass tenancy/isolation, log PII/secrets, or leak credentials. Treat auth/tenancy/migrations/gate-signals/money/audit-trail/PII as load-bearing (mandatory review pass, step 7).
- **Docs-as-code.** A behaviour/command/env/port/convention change updates its docs in the same commit.
- **Commit each logical unit, path-scoped; never push.** Fix and tests are separate commits (`git commit -m "…" -- <paths>`; the scope-guard hook blocks bare/whole-tree commits). No `Co-Authored-By` / AI-attribution trailer. (Git workflow.)

## Where bugs tend to live

Bias the hunt toward the classes that recur in a system like this:

- **Inconsistent logic across paths that should agree.** Two code paths computing "the same" thing differently (one query scopes by a column its sibling forgets; money math that rounds in one place and not the other). Find the canonical version, diff the others against it.
- **Idempotency / at-least-once.** A re-delivered event or retried request that double-inserts, double-counts, double-pays, or clobbers (ingestion, webhook delivery, upload/merge, money-moving writes). Every such write must be idempotent at the boundary; every webhook must verify its signature, dedupe, and fail closed.
- **Structural recursion gaps.** A parser/normalizer that handles the flat case but silently drops nested input (false-pass risk — a hidden failure rendered green).
- **State-machine / workflow gaps.** A transition that isn't in the allowed set, or code that reads live config instead of a snapshot frozen at creation. A status mutated directly instead of through the transition helper — so state changes but no audit row lands.
- **URL/filter-state asymmetry (frontend).** State written but never restored (or vice-versa); `if (v && v !== def)` truthiness dropping a legitimate empty value; a "Clear"/reset that a downstream handler silently coerces back to a default.
- **Edge cases:** null/empty/zero, unicode / separator-in-names, overflow, divide-by-zero, pagination boundaries, oversized/unbounded payloads, N+1 in list endpoints, concurrent writers, out-of-order arrival.
- **Gate signals that lie or fail open.** Anything feeding a ship/merge/authorization decision (a badge, a status/readiness endpoint, an approval threshold, a compliance check) must fail *closed*. A gate that defaults to "allowed" on missing/ambiguous input is the bug.

## Procedure

### 1. Pick targets

- **If `$ARGUMENTS` is given:** resolve it to concrete files/paths and hunt within.
- **If empty:** rank candidates by **logic density × under-coverage × hot-path/recent-bug-activity** (`git log --oneline -20 <file>`), skipping generated/type/schema/seed files and anything needing live cloud creds. Favour ingestion/normalization, stat/aggregate or money math, state machines, gate signals, and shared helpers (a bug there has blast radius). State each pick + why in one line. Prefer targets you haven't hit in a recent session — variety is the point.

### 2. Map before judging

Recon the target's contract first — data model, call sites, the invariants it must hold. For anything non-trivial spawn an `Explore` agent to map callers/schema/siblings rather than guessing from one file. Note the **canonical** version of any logic that appears in more than one place.

### 3. Hunt + reproduce

For each candidate: trace the code to confirm the mechanism, then **write a probe that fails on the current code**. No probe, no finding. A probe is a throwaway test, a replayed payload, a browser snippet, or a direct query against the running stack. Keep probes throwaway and named so they're easy to delete (e.g. `_probe.*`).

### 4. Fix at the root

Apply the durable fix, matched to surrounding style/idiom and tightly scoped to the issue. If a quick patch and the durable fix diverge, name the durable fix even if you ship the patch.

### 5. Lock it with a regression test

Promote the probe into a real test at the right layer — the project's test layers (unit / integration / e2e — whatever this repo actually uses): pure logic → the fast unit layer; DB/HTTP behaviour → the integration/smoke layer (fresh tenant, real endpoints); user-visible → the browser/e2e layer. The test must **fail on the old code and pass on the fix**, and assert the invariant the bug violated. Wait on real signals, never sleeps.

### 6. Sweep the siblings

The bug you found is rarely unique. Grep for the same shape elsewhere (the other normalizers, the other stat/money queries, the other event handlers, the other list endpoints) and either fix-and-test them too, or state explicitly that they're already correct (with the one-line reason). This sibling sweep is where `/bug-hunt` earns its keep over a one-off fix.

### 7. Verify + review

- Run the project's type/lint gate (e.g. `pnpm check`) and the new tests.
- Run the **nearby existing** suites on the same path to prove no regression — report pass/fail counts faithfully.
- For load-bearing diffs (auth, tenancy, migrations, money, webhooks, audit trail), run the `code-reviewer` agent and apply/push back before committing.

### 8. Commit (scoped) — never push

Fix and tests as separate path-scoped commits, conventional-commit style, no AI/co-author trailer. Docs ride with the commit that changed the behaviour. Then go back to step 3 for the next target until you've covered the scope (or the user's round budget). **Never `git push`.**

## Report

```
## /bug-hunt — <scope or "self-selected">

**Targets:** <each pick + one-line why>

**Bugs found & fixed:**
- <file:line> — <what was wrong> → <root-cause fix> | repro: <how> | test: <file (layer)>
- … (or "none — targets were sound; coverage backfilled where thin")

**Sibling sweep:** <same-shape paths checked — fixed too / confirmed correct + why>

**Verification:** <type/lint gate; new tests N/N; nearby suites N/N; review verdict if run>

**Commits:** <hash + subject, one per line>

**Deferred / recommended:** <out-of-scope leads with the long-term fix named + tracked follow-up — or "nothing outstanding">
```

## Tone

Lead with the verdict, not the process. State a real bug plainly with its repro; if a target was sound, say so and point at the coverage you added. Don't dress up a non-finding as a fix.
