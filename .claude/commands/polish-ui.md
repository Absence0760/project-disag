---
description: Polish the UI/UX of a single page or component under web/frontend/ — hierarchy, archetype fit, mobile stacking, design-token discipline, accessibility. Delegates to the `ui-polisher` agent.
argument-hint: <page-route or component path>
---

Polish the UI/UX of `$ARGUMENTS` using the `ui-polisher` agent.

## When to use this command

**Right fit:**

- A page where the hierarchy is muddled — the most important thing isn't at the top, or chrome competes with content for the first viewport.
- A page whose archetype doesn't match its data — a flat prose page where a `<dl>` would surface structure, a 3-column grid for two items, a long unstructured form with no section breaks.
- A page that doesn't collapse cleanly on mobile (two-column desktop layouts must stack, touch targets must be ≥44px).
- A page leaking raw ISO dates, arbitrary hex colors that should be design tokens, arbitrary `rem` spacing that breaks vertical rhythm.

**Wrong fit — tell the user and stop:**

- A purely-functional dev/admin page with no real-estate or scanability problem.
- A request that's really a feature, not a polish — "add a comparison view to the run page" needs a content plan, not the polish agent.
- An asks-for-everything sweep ("polish all the pages"). Pick one and tell the user to invoke this command again for the next.
- A load-bearing piece of infra (the Lambda handler, the `api.ts` client, the upload flow). Polish is for visual / hierarchical changes; structural rewrites need `/safe-edit`.

## Resolving the target

`$ARGUMENTS` can be:

- A **route slug** (`/`, `/run`, `/history`) — resolves to `web/frontend/src/routes/<slug>/+page.svelte`. The home page is `web/frontend/src/routes/+page.svelte`.
- A **file path** (`web/frontend/src/lib/FileDrop.svelte`) — used as-is.
- A **component name** (`FileDrop`) — resolve via `find web/frontend/src/lib -maxdepth 1 -name "<name>.svelte"`.

If the argument is empty or "audit", list the candidate pages with a one-line "why this one matters most right now" and ask the user to pick. Don't blanket-sweep.

## The flow

1. **Pre-flight:**
   - Confirm the target file exists. If not, stop and report.
   - Confirm `pnpm check:web` passes on the working tree before you start — if it's already failing, something else is broken; fix that first.
   - The repo convention is "don't run the dev server to visually verify UI/frontend changes" (per `CLAUDE.md`). The agent doesn't take screenshots; the operator reviews the page in their own browser session.

2. **Resolve target → invoke the agent:**

   Spawn the `ui-polisher` agent with a prompt like:

   > "Polish the UI/UX of `<resolved file path>`. The user's stated intent was: `<the original argument string>`. Follow your agent spec: audit, plan, edit, verify, report. Do not commit."

   The agent's spec covers the methodology, type-check, and any e2e selector updates. Trust it.

3. **Relay the agent's report.** When it returns, surface:

   - The list of files changed (run `git diff --stat` to confirm matches).
   - Any e2e selector updates the agent applied so the user can sanity-check those edits.
   - The "Notes for the human" section verbatim — including the agent's request that the user open `pnpm dev:web` and review the page visually.

4. **Wait for the user's call on the commit.** Do not pre-stage or pre-commit. When the user says yes:

   - Stage the changed files explicitly (don't `git add -A` — risks pulling in scratch output an experimental run may have left behind).
   - Commit message follows the repo's conventional-commit style seen in `git log --oneline` (e.g. `feat(web):` for a new piece of UI, `fix(web):` for a regression, `chore(web):` for a tidy). **No `Co-Authored-By` / "Generated with Claude Code" / robot-emoji footers** — the user-level rule in `~/.claude/CLAUDE.md` wins.

## Cost reality

This command costs more than a normal edit — a full type-check, possibly an e2e re-run, an agent context. Don't burn it on a 5-pixel padding tweak — for that, the user edits directly. The command earns its cost on archetype-level or hierarchy-level changes.

## What this command does NOT replace

- `/check` for a pre-commit gate (code-review + test-gap + doc-hygiene).
- `/safe-edit` for security- or correctness-sensitive changes (the Lambda handler, the `.day` / `.mon` parser, the disag/exceed algorithm).
- `/audit/*` for periodic broad sweeps (secrets, XSS, deps, infra, cost-controls).
- Visual verification. The operator runs `pnpm dev:web` and reviews the page themselves — that's the repo convention.

## Tone

Don't narrate the agent's internal steps. The user sees:

- A one-sentence "Resolving target → `<path>`. Spawning the polisher."
- The agent's structured report (audit findings + changes + verification + notes), relayed.
- A "Want me to commit?" question with the suggested commit message.
