# .claude/ — Claude Code tooling for project-disag

Project-specific agents, commands, and settings that Claude Code (and the slash-command UI) picks up when running in this repo.

## What's here

### Agents (`agents/`)

- **`code-reviewer.md`** — invoked at PR / pre-commit time by `/safe-edit` and `/check` to review the working diff against the project's documented conventions (root `CLAUDE.md`, `disag/CLAUDE.md`, `exceed/CLAUDE.md`, `web/README.md`, file-format gotchas, fail-closed defaults). Read-only.
- **`doc-hygiene-checker.md`** — flags docs that need updating when a code change lands. Reads only.
- **`test-gap-checker.md`** — flags missing unit / e2e coverage when a source surface changes without a matching test. Reads only.
- **`repo-security-auditor.md`** — the read-only security auditor. Knows the project's four trust boundaries (CloudFront → user, API Gateway → Lambda with anonymous `X-Client-Id` scoping, Lambda → S3 via pre-signed URLs, GitHub OIDC → AWS) and the audit-area routing table. Invoked by `/audit/secrets` and `/audit/xss`.
- **`ui-polisher.md`** — applies hierarchy + archetype + accessibility polish to a single SvelteKit page / component. The project does not yet have a mature design system, so the agent is biased toward reading whatever exists in `web/frontend/src/app.css` before applying changes.

**Personas (`agents/persona-*.md`)** — read-only auditors that walk the app from one real-world point of view and file findings to `reviews/<persona>.md` (git-ignored). Dispatched by [/persona](commands/persona.md); protocol and output contract in [personas/README.md](personas/README.md).

- **`persona-new-user.md`** — first run: landing on the site with a `.MON` file and no idea what "disaggregation" means. Empty states, error clarity, "what do I do now".
- **`persona-power-user.md`** — daily heavy user: many runs, large `.day` files, keyboard, speed, re-running with tweaked parameters.
- **`persona-accessibility-user.md`** — assistive-tech walkthrough. The narrative counterpart to the rule-driven `/audit/accessibility` and `/a11y-hunt`.
- **`persona-adversary.md`** — attack narratives against the trust boundaries `repo-security-auditor` enumerates: `X-Client-Id` spoofing, pre-signed URL abuse, upload-size/cost abuse, path traversal.

Only four of the estate's eight base personas are carried here — see "Why this set, and not more" below.

### Commands (`commands/`)

| Command | Purpose |
|---|---|
| [/check](commands/check.md) | Pre-commit gate — `code-reviewer` + `test-gap-checker` + `doc-hygiene-checker` in parallel. Advisory output. |
| [/safe-edit](commands/safe-edit.md) | Coder ↔ reviewer loop for non-trivial changes (~2-3x cost; for security / algorithm / file-format edits). |
| [/polish-ui](commands/polish-ui.md) | Polish a single page or component under `web/frontend/` — delegates to the `ui-polisher` agent. |
| [/release-readiness](commands/release-readiness.md) | Pre-tag gate before publishing a `v*` (python) or `web-v*` (web) release. Working tree, CI, deltas. Read-only. |
| [/persona](commands/persona.md) | Run one, several, or all of the persona auditors in parallel; consolidates their reports. Read-only. |

### Fix-and-land loops (`commands/`)

The `/audit/*` sweeps above are read-only reporters. These **land changes** — fix, test, scoped commits, never push.

| Command | Purpose |
|---|---|
| [/fix-ci](commands/fix-ci.md) | Root-cause a failing GitHub Actions run and fix it without band-aids (no bumped timeouts, no `skip`, no loosened assertions). |
| [/bug-hunt](commands/bug-hunt.md) | Go wide for correctness bugs; prove each with a runnable probe before believing it, fix at root, add a regression test, sweep sibling paths. |
| [/audit-and-fix](commands/audit-and-fix.md) | Deep-audit ONE named area, fix, ship tests. The depth counterpart to `/bug-hunt`'s breadth. |
| [/coverage-hunt](commands/coverage-hunt.md) | Backfill tests for behaviour that works but isn't covered. The area-scoped counterpart to the diff-scoped `test-gap-checker`. |
| [/improve-round](commands/improve-round.md) | Ship one meaningful improvement to an area, then self-audit via `code-reviewer` until clean. |
| [/perf-hunt](commands/perf-hunt.md) | Measure-first performance work — O(n²) paths in the patching methods, oversized Lambda payloads, render thrash. No before/after number, no claim. |
| [/ux-hunt](commands/ux-hunt.md) | Interaction defects — dead-ends, broken back/forward + URL state, missing empty/loading/error states. Fixes objective bugs with an e2e test. |
| [/a11y-hunt](commands/a11y-hunt.md) | The fix side of the read-only `/audit/accessibility`: compute every contrast/size claim, fix violations, pin with a guard. |

### Audit commands (`commands/audit/`)

Focused read-only sweeps; each delegates either to `repo-security-auditor` or to a `general-purpose` agent. See [commands/audit/README.md](commands/audit/README.md) for the index.

| Command | What it checks |
|---|---|
| `/audit/secrets` | SOPS encryption, plaintext-in-git, server-only env in client paths, GitHub Actions secret hygiene |
| `/audit/xss` | Svelte `{@html}`, dynamic `href` / `src`, user-supplied file names / error strings |
| `/audit/deps` | `pnpm audit`, Dependabot coverage, GitHub Actions pin status, override hygiene, Terraform provider pins |
| `/audit/infra` | Terraform under `web/infra/` — IAM, OIDC, S3, CloudFront, WAF, alarms + budget, SOPS, drift |
| `/audit/cost-controls` | WAF rate limit, API Gateway throttling, budget alarms, Lambda concurrency caps, S3 lifecycle, log retention |
| `/audit/accessibility` | WCAG 2.2 AA pass on the SvelteKit frontend |
| `/audit/all` | All of the above in parallel + consolidated report. Optional area filter. |

### Hooks (`hooks/`)

- **`git-scope-guard.py`** — a `PreToolUse` Bash guard (wired in `settings.json`) for when more than one Claude session shares this checkout. It denies git commands that would sweep up working-tree changes the current session did not make — bare `git commit` (no pathspec), `git add -A`/`.`/`-u`, `git commit -a`, `git reset --hard`, `git checkout/restore .`, `git rm .`, `git clean -f`, whole-tree `git stash`, and `git commit --amend` with a staged index. Each denial names the path-scoped alternative (e.g. `git commit -m "…" -- path/to/file`). Read-only git and path-scoped writes pass untouched. Self-contained (computes the repo root from its own location) — copied verbatim from the sibling `project-running` / `project-flakey` repos.
  - **Practical effect:** commit by naming paths — `git add <paths>` then `git commit -m "…" -- <paths>` — not bare `git commit`.
  - **Test:** `python3 .claude/hooks/git-scope-guard.test.py` (32 subprocess + 5 white-box cases; not in CI — the hook itself is the live guard, the test just pins its logic).
- **`unmerged-worktree-check.sh`** — a `SessionStart` hook (wired in `settings.json`) that lists every local branch holding commits not yet on `main`, mapped to its worktree path where one exists. Claude Code injects the output as session context, so stranded `claude --worktree` work gets surfaced instead of forgotten. Silent when everything is merged; fail-open (any error exits 0 with no output, never wedging startup).

### `settings.json`

The per-project permission allowlist (and denylist). Things on the allowlist run without a prompt; things on the denylist refuse outright. The `hooks.PreToolUse` block wires up `hooks/git-scope-guard.py` (above). See the comments on the file itself.

## Why this set, and not more

The two Python packages (`disag/` and `exceed/`) are stdlib-only by repo policy and have no auth / database / multi-tenant concerns. The `web/` workspace is a SvelteKit static frontend + a single Python Lambda behind API Gateway, with anonymous `X-Client-Id` scoping (no accounts, no PII collection beyond what the user uploads in their own files), no payment processor, no CMS, and no email service.

So this `.claude/` tree intentionally omits the kinds of agents/commands a full SaaS would carry — migration coordination, GDPR / cookie-consent / data-export / account-deletion audits, LLM-endpoint and WebSocket-hub audits, third-party data-flow mapping, endpoint inventories, mobile-twin parity, auth-middleware gating, and the `persona-admin` / `persona-international-user` / `persona-integrator` / `persona-data-subject` half of the estate persona panel. If the project ever grows in any of those directions, add the relevant command then; don't pre-create empty ones.

**This is load-bearing when syncing from the `templates` `base` branch.** That sync is additive-by-default and will happily re-add every one of the above. PR #95 did exactly that; the irrelevant two-thirds were stripped before merge. Re-read this section when reviewing the next sync — a file arriving from `base` is not evidence that this repo needs it.
