---
description: Polish the UI/UX of a single page or component to this site's quality bar — section-rhythm layouts, image-led product cards, dl-based legal disclosures, mobile-first stacking, leaf-and-cream design tokens. Delegates to the `ui-polisher` agent.
argument-hint: <page-route or component path>
---

Polish the UI/UX of `$ARGUMENTS` using the `ui-polisher` agent.

## When to use this command

**Right fit:**

- A page where the hierarchy is muddled — the most important thing isn't at the top, or chrome / boilerplate competes with content for the first viewport.
- A page whose archetype doesn't match its data — flat prose where a `<dl>` would surface structure, a 3-column grid for two items, a long unstructured policy doc.
- A page that doesn't collapse cleanly on mobile (SA traffic skews mobile — two-column desktop layouts must stack, touch targets must be ≥44px).
- A page leaking raw ISO dates, arbitrary hex colors that should be design tokens, arbitrary `rem` spacing that breaks the `--space-*` rhythm.
- A component used in multiple places (`Button`, `Cart`, `<payment-processor>Redirecting`) where consistency across surfaces matters.

**Wrong fit — tell the user and stop:**

- A purely-functional admin / settings / dev page with no real-estate or scanability problem.
- A payment surface (`/payment/cancelled`, the retry CTA in `/track`, the `Cart.svelte` <payment-processor> form construction). These are inside the payment-retry threat model in `docs/payment-retry-plan.md` — they need `/safe-edit`, not polish.
- A request that's really a feature, not a polish — "add an FAQ section to the home page" needs a content plan, not the polish agent.
- An asks-for-everything sweep ("polish all the pages"). Pick one and tell the user to invoke this command again for the next.

## Resolving the target

`$ARGUMENTS` can be:

- A **route slug** (`/shop`, `/gallery`, `/returns`, `/contact`) — resolves to `frontend/src/routes/<slug>/+page.svelte`. The home page is `frontend/src/routes/+page.svelte`. Nested routes follow the obvious pattern (`/shop/[slug]` → `frontend/src/routes/shop/[slug]/+page.svelte`).
- A **file path** (`frontend/src/lib/Cart.svelte`) — used as-is.
- A **component name** (`Cart`, `Button`, `<payment-processor>Redirecting`) — resolve via `find frontend/src/lib -maxdepth 1 -name "<name>.svelte"`.

If the argument is empty or "audit", list the candidate pages with a one-line "why this one matters most right now" and ask the user to pick. Don't blanket-sweep.

## The flow

1. **Pre-flight:**
   - Confirm the target file exists. If not, stop and report.
   - Confirm `pnpm frontend check` passes on the working tree before you start — if it's already failing, something else is broken; fix that first.
   - The repo convention is "don't run the dev server to visually verify UI/frontend changes" (per `CLAUDE.md`). The agent does not take screenshots; the operator reviews the page in their own browser session. No pre-flight check on a running dev server.

2. **Resolve target → invoke the agent:**

   Spawn the `ui-polisher` agent with a prompt like:

   > "Polish the UI/UX of `<resolved file path>`. The user's stated intent was: `<the original argument string>`. Follow your agent spec: audit, plan, edit, verify, report. Do not commit. Respect the safety-critical guards in the cart and payment surfaces if your target overlaps with them."

   The agent's spec covers the design language, type-check, and any e2e selector updates. Trust it.

3. **Relay the agent's report.** When it returns, surface:

   - The list of files changed (run `git diff --stat` to confirm matches).
   - Any e2e selector updates the agent applied so the user can sanity-check those edits.
   - The "Notes for the human" section verbatim — including the agent's request that the user open `pnpm frontend dev` and review the page visually.

4. **Wait for the user's call on the commit.** Do not pre-stage or pre-commit. When the user says yes:

   - Stage the changed files explicitly (don't `git add -A` — risks pulling in scratch test output or screenshots an experimental run may have left behind).
   - Commit message follows the repo's `content(<scope>):` convention seen in `git log --oneline` (the most recent UI polish to the cart was `content(cart): visual treatment for the CPA s49 clickwrap`). **No `Co-Authored-By` / "Generated with Claude Code" / robot-emoji footers** — the user-level rule in `~/.claude/CLAUDE.md` wins.
   - Example: `git commit -m "content(<scope>): <one-liner>" -m "<3–5 line body explaining what archetype + which patterns applied + why>"`.

## Cost reality

This command costs more than a normal edit — a full type-check, possibly an e2e re-run, an agent context. Don't burn it on a 5-pixel padding tweak — for that, the user edits directly. The command earns its cost on archetype-level or hierarchy-level changes (a flat product list that should be a card grid, a comma-list of materials that should be a `<dl>`, a clickwrap label that needs to clear CPA s49 conspicuousness, etc.).

## What this command does NOT replace

- `/check` for a pre-commit gate (code-review + test-gap + doc-hygiene).
- `/safe-edit` for security- or payment-sensitive changes (cart submit, ITN handling, <payment-processor> form construction, anything inside `docs/payment-retry-plan.md`'s threat model).
- `/audit/*` for periodic broad sweeps (secrets, XSS, deps, infra, cost-controls).
- Visual verification. The operator runs `pnpm frontend dev` and reviews the page themselves — that's the repo convention.

## Tone

Don't narrate the agent's internal steps. The user sees:

- A one-sentence "Resolving target → `<path>`. Spawning the polisher."
- The agent's structured report (audit findings + changes + verification + notes), relayed.
- A "Want me to commit?" question with the suggested commit message.
