# .claude/ — Claude Code tooling for project-disag

Project-specific agents, commands, and settings that Claude Code (and the slash-command UI) picks up when running in this repo.

## What's here

### Agents (`agents/`)

- **`code-reviewer.md`** — invoked at PR / pre-commit time by `/safe-edit` and `/check` to review the working diff against the project's documented conventions (root `CLAUDE.md`, `disag/CLAUDE.md`, `exceed/CLAUDE.md`, `web/README.md`, file-format gotchas, fail-closed defaults). Read-only.
- **`doc-hygiene-checker.md`** — flags docs that need updating when a code change lands. Reads only.
- **`test-gap-checker.md`** — flags missing unit / e2e coverage when a source surface changes without a matching test. Reads only.
- **`repo-security-auditor.md`** — the read-only security auditor. Knows the project's four trust boundaries (CloudFront → user, API Gateway → Lambda with anonymous `X-Client-Id` scoping, Lambda → S3 via pre-signed URLs, GitHub OIDC → AWS) and the audit-area routing table. Invoked by `/audit/secrets` and `/audit/xss`.
- **`ui-polisher.md`** — applies hierarchy + archetype + accessibility polish to a single SvelteKit page / component. The project does not yet have a mature design system, so the agent is biased toward reading whatever exists in `web/frontend/src/app.css` before applying changes.

### Commands (`commands/`)

| Command | Purpose |
|---|---|
| [/check](commands/check.md) | Pre-commit gate — `code-reviewer` + `test-gap-checker` + `doc-hygiene-checker` in parallel. Advisory output. |
| [/safe-edit](commands/safe-edit.md) | Coder ↔ reviewer loop for non-trivial changes (~2-3x cost; for security / algorithm / file-format edits). |
| [/polish-ui](commands/polish-ui.md) | Polish a single page or component under `web/frontend/` — delegates to the `ui-polisher` agent. |
| [/release-readiness](commands/release-readiness.md) | Pre-tag gate before publishing a `v*` (python) or `web-v*` (web) release. Working tree, CI, deltas. Read-only. |

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

### `settings.json`

The per-project permission allowlist (and denylist). Things on the allowlist run without a prompt; things on the denylist refuse outright. The `hooks.PreToolUse` block wires up `hooks/git-scope-guard.py` (above). See the comments on the file itself.

## Why this set, and not more

The two Python packages (`disag/` and `exceed/`) are stdlib-only by repo policy and have no auth / database / multi-tenant concerns. The `web/` workspace is a SvelteKit static frontend + a single Python Lambda behind API Gateway, with anonymous `X-Client-Id` scoping (no accounts, no PII collection beyond what the user uploads in their own files), no payment processor, no CMS, and no email service.

So this `.claude/` tree intentionally omits the kinds of agents/commands a full SaaS would carry — migration coordination, GDPR / cookie-consent / data-export / account-deletion audits, third-party data-flow mapping, mobile-twin parity, auth-middleware gating. If the project ever grows in any of those directions, add the relevant command then; don't pre-create empty ones.
