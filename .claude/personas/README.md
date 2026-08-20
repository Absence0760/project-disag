# Persona audits

A **persona** is a read-only Claude subagent (`.claude/agents/persona-*.md`) that
adopts a specific real-world point of view — a brand-new user, a daily heavy
user, an assistive-technology user, an attacker — and walks the app the way
that person would, looking for bugs, missing primitives, wrong assumptions, and
gaps that a generic code review never surfaces because it has no human stake.

Personas complement, not replace, the other reviewers:

- `code-reviewer` / `repo-security-auditor` ask *"is this code correct and safe?"*
- A persona asks *"does this app actually work for **me**, and would it embarrass
  me / lock me out / leak my data / let me cheat it?"*

These came from the estate `base` scaffolding as a generic panel; this repo
carries only the four that match what it actually ships (no accounts, no admin
surface, no personal data, no public API — see `.claude/README.md` § "Why this
set, and not more"). They do **not** know the stack — each persona discovers it
first (reads `CLAUDE.md`, the route/handler layout, the file formats) and then
audits. Add domain-specific personas as needed (see "Domain packs" below).

## How to run one

These are agents. Run one by asking for it by name, e.g.

> run the `persona-new-user` audit
> run `persona-power-user` and `persona-adversary`

or run the whole panel with the `/persona` command. Each persona writes its
findings to `reviews/<persona-name>.md` (git-ignored — see `reviews/README.md`).

## The output contract (every persona follows this)

### 1. Reconcile with reality *before* writing anything

This is the rule that keeps the reports trustworthy. On every run, a persona:

1. Captures the current commit: `git rev-parse --short HEAD`.
2. Reads its existing `reviews/<persona>.md` if one exists.
3. **Re-verifies every open finding against the code at HEAD.** For each one:
   - Still reproduces → keep it, refresh the `file:line` (line numbers drift).
   - Fixed since last run → move it to `## Resolved`, stamp the commit/date the
     fix landed (or "fixed by HEAD" if you can't pin it).
   - No longer applicable (feature removed, assumption changed) → delete it with
     a one-line note in `## Resolved` so the next run doesn't re-derive it.
4. Looks for *new* findings.
5. Rewrites the header stamp (commit + UTC date from `date -u`).

A finding asserted but not re-verified against current code is a bug in the
report. Stale findings are worse than none — they waste a fix cycle and erode
trust in the whole folder. **Never** copy a prior finding forward without opening
the file it cites.

This rule binds *any* session that touches a `reviews/*.md` file, not just the
persona agent — if you open one to act on a finding, confirm it still
reproduces at HEAD first.

### 2. File format

````markdown
---
persona: persona-new-user
last_reviewed_commit: 1a2b3c4
last_reviewed_at: 2026-01-01T00:00:00Z
---

> **Living document — reconcile before you trust.** Findings were verified at
> the commit above. Before acting on or citing any entry, re-verify it against
> the current code; a fix may have landed since. When you edit this file, follow
> the protocol in `.claude/personas/README.md` § "Reconcile with reality".

# persona-new-user — review

_One paragraph: who I am and what I came here to check._

## Open findings

### [High] path/to/file:42 — first-run flow dead-ends on an unverified email
- **What I tried:** <concrete steps / curl / click path>
- **What I expected:** <the correct behaviour>
- **What happened:** <the bug>
- **Why it matters to me (the persona):** <the human stake>
- **Invariant / rule:** <CLAUDE.md § ... if applicable>
- **Fix scope:** <file(s) that would change — I do not patch>

## Resolved
- [Med] ~~auth.ts:88 — ...~~ fixed by `abc1234` (2026-01-01).

## Out of scope / notes
- <assumptions, things I deliberately didn't test, follow-ups>
````

### 3. Severity rubric

- **Critical** — data loss, account/tenant cross-over, money moved wrongly, or a
  reportable compliance breach. Fix before next deploy.
- **High** — the persona cannot complete a core job, or the app shows a
  wrong-but-plausible result they'd act on.
- **Medium** — friction, a missing affordance, a defensible-but-wrong default.
- **Low** — cosmetic, wording, nice-to-have.

### 4. House rules

- **Read-only on app code.** A persona reports; it does not patch. The only file
  it writes is its own `reviews/<persona>.md`.
- No emojis, no preemptive abstractions in anything you write (see `CLAUDE.md`).
- Don't paste secrets, full card/account numbers, or government IDs into a report
  — identify the field by name and location.
- Prefer reproducible findings. If you can't confirm one, file it under "needs
  verification" and say exactly what you'd need.
- Distinguish *a real bug* from *a feature the app never claimed to have*. Both
  are worth recording, but label the second as a **gap**, not a **defect**.

## The panel in this repo

| Persona | Point of view |
|---|---|
| `persona-new-user` | First-run — landing on the site with a `.MON` file and no idea what "disaggregation" means |
| `persona-power-user` | Daily heavy user — many runs, large `.day` files, keyboard, speed, re-running with tweaked parameters |
| `persona-accessibility-user` | WCAG/keyboard/screen-reader/contrast/motion + responsive small-screen |
| `persona-adversary` | Attacker — `X-Client-Id` spoofing, pre-signed URL abuse, upload-size/cost abuse, path traversal, secret exposure |

The estate `base` panel also ships `persona-admin`, `persona-international-user`,
`persona-integrator`, and `persona-data-subject`. They are **deliberately not in
this repo** — there is no admin surface, no i18n layer, no third-party API
consumer, and no personal data to be a subject of. Add one if that changes.

## Domain packs — adding personas for *this* app

The generic panel is deliberately stack-agnostic. Most apps also deserve
personas tied to their domain. Copy the closest generic `persona-*.md`, then:

1. Rewrite the frontmatter `name` (`persona-<slug>`) and `description`.
2. Rewrite the identity paragraph and the "what I care about" list in that
   persona's real voice and incentives.
3. List the concrete app surfaces this persona exercises, with file starting
   points, so the agent doesn't burn a turn rediscovering the layout.
4. Add a "known bug shapes for this domain" list — the failure modes this
   persona is uniquely positioned to catch.
5. Keep the output-contract pointer (this file). Don't restate the whole
   protocol inline — reference it.

**Worked example — a finance / accounts-payable app** (the shape this framework
was extracted from): `persona-approver` (approval limits, segregation of duties),
`persona-cfo` (sign-off thresholds, dashboard math), `persona-accountant`
(GL coding, 2/3-way match, 1099), `persona-card-processor` and
`persona-payment-processor` (webhook idempotency, rebate/FX math), `persona-supplier`
(portal isolation), plus jurisdiction packs `persona-usa-business` /
`persona-uk-business` / `persona-south-africa-business` (tax, bank rails, date
and currency conventions). Other domains: a marketplace gets buyer/seller/
dispute personas; a healthcare app gets patient/clinician/billing; a CMS gets
author/editor/anonymous-reader.
