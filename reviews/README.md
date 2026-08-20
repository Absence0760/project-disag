# reviews/

Output folder for the persona auditors (`.claude/agents/persona-*.md`). Each
persona writes its findings to `reviews/<persona-name>.md`.

**Everything in here except this README is git-ignored.** The reports are
per-clone working notes, not a committed artifact — they go stale the moment
code lands, so they're regenerated, not version-controlled.

## If you open a report to act on it

These are **living documents**. A finding is only as good as the commit it was
verified against (see the header stamp in each file). Before you act on, cite,
or hand off any finding:

1. Open the `file:line` it points at and confirm it still reproduces at HEAD.
2. If it's already fixed, move it to `## Resolved` with the fixing commit.
3. If you changed code that a report covers, re-run that persona so the report
   reconciles instead of drifting.

The full protocol — file format, severity rubric, the reconcile-before-you-trust
rule, and how to add project-specific domain personas — lives in
`.claude/personas/README.md`. Read it before editing a report by hand.

## Running the personas

Ask for one by name (`run persona-new-user`), several at once, or the whole
panel via the `/persona` command. The panel in this repo: `persona-new-user`,
`persona-power-user`, `persona-accessibility-user`, `persona-adversary`. Add
domain personas alongside these — `.claude/personas/README.md` § "Domain packs"
explains how, and why the other four estate personas are not carried here.
