# Audit commands

Project-curated slash commands for running security, dependency, infra, cost-control, and accessibility audits across the repo. Each is read-only by default — they report findings, they don't apply fixes without explicit confirmation.

Invoke from a Claude Code session as `/audit/<name>`.

## Index

### Security

| Command | What it checks |
|---|---|
| [/audit/secrets](secrets.md) | SOPS encryption status, plaintext-in-git history, server-only env in client paths, GitHub Actions secret hygiene |
| [/audit/xss](xss.md) | Svelte `{@html}`, dynamic `href` / `src`, user-supplied file names and error strings round-tripping through the backend |

### Health

| Command | What it checks |
|---|---|
| [/audit/deps](deps.md) | `pnpm audit` on `web/frontend`, Dependabot coverage, GitHub Actions pin status, pnpm override hygiene, Terraform provider pins |
| [/audit/infra](infra.md) | Terraform under `web/infra/` — IAM least-privilege, OIDC subject conditions, S3 PAB, CloudFront / WAF / OAC, alarms + budget, SOPS, drift hygiene |
| [/audit/cost-controls](cost-controls.md) | WAF rate limit, API Gateway throttling, AWS budget alarms, Lambda concurrency + memory caps, S3 lifecycle, CloudWatch log retention |
| [/audit/accessibility](accessibility.md) | WCAG 2.2 AA pass on the SvelteKit frontend |

### Dispatcher

| Command | What it does |
|---|---|
| [/audit/all](all.md) | Spawns the full sweep in parallel + consolidated report. Optional arg: `security` / `deps` / `infra` / `cost` / `a11y`. |

## Conventions

- Every audit is **read-only by default**. The deliverable is a findings report, not a diff.
- Findings are grouped by severity: **Critical / High / Medium / Low**.
- Each command is a **self-contained prompt** — runnable from a fresh session with no prior context.

## Agent delegation

The **secrets** and **xss** commands delegate to the `repo-security-auditor` agent (under `.claude/agents/`). That agent has the four trust boundaries baked in (frontend ↔ user, API Gateway → Lambda ↔ caller via anonymous `X-Client-Id`, Lambda ↔ S3 via pre-signed URLs, CI/CD ↔ AWS via GitHub OIDC) plus the audit-area routing table — it picks up the project's conventions without re-reading them every run.

The **deps**, **infra**, **cost-controls**, and **accessibility** commands use a `general-purpose` agent with the command body as the prompt — they cross-cut code + IaC + docs and don't need the security-auditor's specialised context.

`/audit/all` spawns one agent per area in parallel.

## Diff-time enforcement (complementary)

For per-PR enforcement (as opposed to periodic broad sweeps), use:

- [/check](../check.md) — pre-commit gate: `code-reviewer` + `test-gap-checker` + `doc-hygiene-checker` in parallel against the working diff.
- [/safe-edit](../safe-edit.md) — coder ↔ reviewer loop for non-trivial changes (~2-3x cost; use for security-sensitive or algorithm changes).
- [/release-readiness](../release-readiness.md) — pre-tag gate before publishing a release (working tree, CI, per-workspace deltas).

These are for per-PR / pre-deploy enforcement; the audit commands here are for periodic broad sweeps.

## When to run

- **Before a release** — `/audit/all` once, fix Critical / High before tagging. Then `/release-readiness`.
- **After bumping a dependency major** — `/audit/deps` + `/audit/secrets`.
- **After editing anything under `web/infra/`** — `/audit/infra` before `terraform apply`.
- **After adding a new backend route** — `/audit/secrets` (catches new env-var leaks) + `/audit/xss` (catches new HTML response surfaces).
- **After a UI change of any size** — `/audit/accessibility` on the touched routes.
- **Periodically (monthly)** — `/audit/all` to catch slow-moving drift.
