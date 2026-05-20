---
description: Run the full audit sweep — secrets + xss + deps + infra + cost-controls + accessibility — in parallel
argument-hint: [security|deps|infra|cost|a11y] (optional area filter)
---

Run the project's audit sweep. By default, runs every audit; with an argument, runs the named subset.

## Areas

- **security** — `audit/secrets`, `audit/xss`
- **deps** — `audit/deps`
- **infra** — `audit/infra`
- **cost** — `audit/cost-controls`
- **a11y** — `audit/accessibility`

## Procedure

1. Decide which audits to run based on `$ARGUMENTS`:
   - No argument → all six audits
   - `security` → secrets + xss
   - `deps` → deps only
   - `infra` → infra only
   - `cost` → cost-controls only
   - `a11y` → accessibility only
2. **Spawn the right agent per audit area, in parallel.** Send all dispatches in a single message with multiple Agent tool calls.
   - `secrets` and `xss`: each is a separate `repo-security-auditor` invocation, with the audit area passed as the prompt's first sentence. The agent already has the trust boundaries baked in; the prompt just steers it.
   - `deps`: a single `general-purpose` agent with the `deps.md` body as prompt — the work is mostly running `pnpm audit` per workspace + reviewing Dependabot config + GitHub Actions pin status.
   - `infra`: a single `general-purpose` agent (or `repo-security-auditor`) with the `infra.md` body as prompt — reads ~13 small `.tf` files plus matches against documented expectations.
   - `cost-controls`: a single `general-purpose` agent with the `cost-controls.md` body as prompt — cross-cuts code + IaC + docs.
   - `accessibility`: a single `general-purpose` agent with the `accessibility.md` body as prompt — walks the small SvelteKit surface under `web/frontend/src/`.
3. **Consolidate findings** into a single report grouped by severity (Critical / High / Medium / Low), then by audit area. For each finding: file:line, what's wrong, the audit that found it.
4. **Recommend a fix order**, but don't apply fixes without explicit confirmation. Critical/High findings should be flagged with "fix this before next deploy"; Medium/Low can be batched.

## Output shape

```
# Audit report — <date>

## Critical (N)
- [audit/<area>] file:line — <one-line>
- ...

## High (N)
- ...

## Medium (N)
- ...

## Low (N)
- ...

## Clean (no findings)
- [audit/<area>] no issues

## Recommended order
1. ...
2. ...
```

## Notes

- This is read-only. Each sub-audit is read-only by default.
- The report is the deliverable; do not edit code based on findings without asking the user first.
- If an audit finds no issues, list it under the `## Clean` section — easier to spot regression on the next run.
- For changes to **just** dependencies or **just** the frontend, the relevant subset is usually enough — full sweep is for release prep and periodic drift checks.
