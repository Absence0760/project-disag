---
description: Pick one app area (random if none given), audit it for real bugs, fix at the root, and back the fix with as much unit/integration/e2e coverage as the change warrants. Commits scoped; never pushes.
argument-hint: "[optional area — a path, glob, module, or feature, e.g. src/retention.ts or 'the payment-run execute path']"
---

Deep-audit a single area of the project, fix the real issues you find, and ship tests with the fix. Unlike `/audit/*` (read-only sweeps that write a review doc) and `/check` (advisory pre-commit gate), this command **lands changes**: fix + tests + scoped commits.

`$ARGUMENTS` is the area to audit. If empty, you pick one (see step 1).

**When to use this vs the siblings:** `/audit-and-fix` = deep-audit ONE named area, fix it, ship tests (depth on a chosen target). `/bug-hunt` = go wide across many targets, prove each bug with a probe, sweep siblings (breadth). `/coverage-hunt` = harden behaviour that already works but isn't tested (deliverable: tests, no bug required). `/perf-hunt`, `/ux-hunt`, `/a11y-hunt` = the same shape aimed at performance, UX, and accessibility.

## Operating rules (non-negotiable)

- **Fix the root cause — never mask.** No inflated timeouts, sleeps, retries, loosened assertions, `skip`/`xfail`, or swallowed errors to make something pass. If you can't fix it now, surface it explicitly and file a tracked follow-up. (Root `CLAUDE.md` guard rails; "Fix bugs at the source".)
- **Be honest when there's no bug.** If the area is sound, say so plainly and make the deliverable the *test coverage gap* you closed — do **not** invent a "fix" to justify the command. A no-bug-found result with new tests is a success.
- **Respect the project's documented invariants.** Don't bypass tenancy/isolation, don't log PII or secrets, don't loosen an auth or authorization check. If the area is auth, tenancy, migrations, the money/payment path, webhook handlers, PII, or approval/RBAC, treat it as **load-bearing** (mandatory review pass in step 5).
- **Docs-as-code.** If you change a behaviour, command, env var, port, or convention, update its docs in the same commit.
- **Commit each logical unit, path-scoped; never push.** Fix and tests are separate commits. Use `git commit -m "…" -- <paths>` (the scope-guard hook blocks bare/whole-tree commits). No `Co-Authored-By` / AI-attribution trailer.

## Procedure

### 1. Resolve the area

- **If `$ARGUMENTS` is given:** that's the scope. Resolve it to concrete files (a path, glob, module name, or a feature described in prose — map prose to files first).
- **If `$ARGUMENTS` is empty:** pick one yourself. Favour **self-contained, testable, bug-prone, under-covered** code over breadth. A good heuristic:
  - Map source modules to their dedicated test files across the project's layers (source vs its unit/integration/e2e tests).
  - Rank candidates by: **few/no dedicated tests** × **hot path or recent bug activity** (`git log --oneline -20 <file>`) × **logic density** (not pure config/types).
  - Skip: generated files, pure type/schema-only files, config, migration files, seed scripts, anything needing live cloud creds, and areas already covered by a recent commit in this session.
  - State your pick and *why* in one line before diving in. Treat "random" as "an area I haven't been steered to" — variety across invocations is the point, so don't keep landing on the same module.

### 2. Audit for real issues

- Use a recon pass to **map the area before judging it**: the data model / call sites / invariants it must hold. For anything non-trivial, spawn an `Explore` agent to map callers, schema, and the invariants — or `repo-security-auditor` / `code-reviewer` for a strict written review. Don't guess at a hot path's contract.
- Hunt for **correctness** bugs first (wrong results, broken invariants, race conditions, inconsistent logic across paths, edge cases: null/empty/overflow/unicode/concurrent), then security/tenancy, then robustness. Stylistic nits are out of scope unless they hide a bug.
- For each candidate finding, **confirm it's real** by tracing the code — read the schema/migration/caller across files, don't assert from a single file. Discard plausible-but-wrong findings.

### 3. Fix the real issues at the root

- Apply the durable fix. Match surrounding code style, comment density, and idiom.
- If a quick patch and the durable fix diverge, name the durable fix even if you ship the patch.
- Keep the fix tightly scoped to the issue — resist refactoring the whole area.

### 4. Add as much coverage as the change warrants

Pick the right layer per the repo's conventions — the project's test layers (unit / integration / e2e — whatever this repo actually uses):

- **Pure logic** → the fast unit layer (no DB/network).
- **DB / HTTP behaviour** → the integration/smoke layer (spawn the server, register a fresh tenant, hit real endpoints; use the project's test-DB bring-up).
- **User-visible behaviour** → the browser/e2e layer against the running stack + seed.
- Write tests that **lock in the fixed behaviour and the invariant it restores** (a regression would fail them), plus the obvious edge cases. If the area was sound, still backfill the missing coverage — that's the deliverable.
- If something is genuinely untestable, say *why* rather than skipping silently.

### 5. Verify + review

- Run the project's type/lint gate for the layer you touched (e.g. `pnpm check`) and the **new** tests.
- Run the **nearby existing** tests that exercise the same path to prove no regression — report the pass/fail counts faithfully.
- If the change is **load-bearing** (`disag/files.py` and the fixed-width `.day`/`.mon` readers, the patching methods in `disag/algorithm.py`, the Lambda handler's request/response contract, the Terraform under `web/infra/`), run the `code-reviewer` agent on the diff — and `repo-security-auditor` for a security-sensitive area — and apply or push back on its findings before committing.

### 6. Commit (scoped) — never push

- Commit the **fix** and the **tests** as separate path-scoped commits (conventional-commit style, no AI/co-author trailer). If a behaviour/doc changed, the doc edit rides with the commit that caused it.
- If you only added tests (no bug), one `test(...)` commit is fine.
- Do **not** `git push`.

## Report

End with a tight summary:

```
## /audit-and-fix — <area>

**Picked:** <area> — <one-line why> (omit the "why" if the user named it)

**Issue(s) found:** <each real bug: what was wrong + the root-cause fix>  — or "none; area is sound"

**Tests added:** <files + what they lock in (layer: unit/integration/e2e, count)>

**Verification:** <type/lint gate result; new tests N/N; nearby existing suites N/N; review verdict if run>

**Commits:** <hash + subject, one per line>

**Deferred / recommended:** <anything you intentionally didn't do, with the long-term fix named + tracked follow-up — or "nothing outstanding">
```

## Tone

Don't narrate the agent fan-out. Lead with the pick and the verdict. If you found and fixed a real bug, state it plainly; if you didn't, say the area was sound and the coverage was the gap — don't dress up a non-finding.
