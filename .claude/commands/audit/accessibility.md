---
description: WCAG 2.2 AA pass on the SvelteKit frontend under web/frontend/
---

Audit accessibility across the web frontend. The legal floor for consumer apps (EU EAA in force from 2025-06-28, US ADA Title III, state laws like Colorado Privacy Act §6-1-1305) all converge on WCAG 2.2 AA.

## Goal

Find every place the frontend misses the WCAG 2.2 AA bar. This project ships only a web surface (no mobile, no watch, no native apps), so the audit narrows to SvelteKit-specific patterns and the small surface under `web/frontend/src/`.

## What to check

### Semantic HTML

1. **Buttons vs divs.** `<button>` for every interactive element; `<div onClick>` is a finding. Every interactive icon-only button needs `aria-label` or visually-hidden text. Walk `web/frontend/src/lib/` and `web/frontend/src/routes/`.
2. **Links vs buttons.** `<a href>` navigates; `<button>` triggers action. Mixing them breaks keyboard and screen-reader expectations.
3. **Form labels.** Every input has a `<label>` (visible or `aria-labelledby`). Required fields use `required` (not just a visual asterisk). Validation errors are associated via `aria-describedby`.

### Focus + keyboard

4. **`:focus-visible` style on every focusable element.** Removing the default outline without replacing it is a finding.
5. **Tab order matches visual order.** A grid that reads left-to-right visually shouldn't tab top-to-bottom.
6. **Every flow reachable without a pointer.** Drag-and-drop file upload (`FileDrop.svelte`) needs a keyboard alternative — a click-through `<input type="file">` is the standard one.
7. **Modal / dialog focus management.** If a dialog exists, focus traps inside it on open and restores to the trigger element on close. Escape closes it.

### Colour contrast

8. **≥ 4.5:1 on text, ≥ 3:1 on UI components.** Walk `web/frontend/src/app.css` and any inline styles in page `<style>` blocks. Both light theme and (if present) dark theme.
9. **Don't convey state by colour alone.** A red border on an invalid field needs text or an icon too.

### Headings + structure

10. **One `<h1>` per page; descending order without skips.** Walk every `+page.svelte` and confirm.
11. **Landmarks.** `<header>`, `<main>`, `<footer>`, `<nav>` in the layout. Single `<main>` per page.
12. **Skip link.** "Skip to main content" at the top of `+layout.svelte` — first focusable element, visually hidden until focused.

### Live regions + motion

13. **Toasts / status / error live regions.** Status: `role="status"` / `aria-live="polite"`. Errors: `aria-live="assertive"`. The run-progress and history pages are the likely homes for these.
14. **`@media (prefers-reduced-motion: reduce)`** honoured for any transition or animation. A spinning loader becomes a static icon; a fade-in becomes instant.

### Forms specifically

15. **Submit-button states.** Disabled while submitting; loading state announced. The Pay / Run button on the run page is the canonical example.
16. **Error summaries.** Form-level errors live above the form with `role="alert"` so a screen-reader announces them.
17. **Touch targets.** Min 44×44 px on small viewports.

### File upload (the project's distinctive surface)

18. **`<input type="file">` is the fallback** for the drag-and-drop region in `FileDrop.svelte`. Confirm the visible drag target *and* the keyboard-reachable input both exist and accept the same MIME constraints.
19. **Selected-file display has accessible text.** "RUKOKI-l.DAY (12.4 KB) selected" is readable; an icon alone is not.

### Page-level signal

20. **`<title>` is set per page**, not the static "App" everywhere. The first thing a screen-reader announces on navigation.
21. **`lang="en"` (or whatever the page language is) on `<html>`** in `app.html`. Missing language → assistive tech can't pick a voice.

## Report

- **Critical** — flow is unreachable without sight or without pointer (image-only flow, modal that traps focus on the close button, drag-only upload with no `<input type="file">` fallback).
- **High** — WCAG 2.2 AA fail that's clearly testable (contrast ratio < 4.5:1, missing `aria-label` on an icon button, missing `<label>` on an input, no keyboard alternative for a pointer flow).
- **Medium** — best practice gap (no skip link, headings out of order, missing live region on a toast, page-level `<title>` not set per route).
- **Low** — polish (focus ring style, motion-reduce on non-critical animation, `lang` attribute missing on a one-off block).

For each: file:line, the success criterion (e.g. WCAG 2.4.7 Focus Visible, 1.4.3 Contrast Minimum, 1.3.1 Info and Relationships), and the fix.

End with a **clean** list of surfaces you confirmed pass — easier to detect a regression on the next run.

## Useful starting points

- `web/frontend/src/routes/+layout.svelte` — site chrome, skip link, landmarks
- `web/frontend/src/routes/+page.svelte` — landing page
- `web/frontend/src/routes/run/+page.svelte` — primary interactive surface
- `web/frontend/src/routes/history/+page.svelte` — list rendering
- `web/frontend/src/lib/FileDrop.svelte` — the drag-and-drop accessibility hotspot
- `web/frontend/src/app.css` — shared design tokens, focus styles, contrast
- `web/frontend/src/app.html` — `<html lang>`, default `<title>`

## Delegate to

Use a `general-purpose` agent with this file as the prompt body. The frontend is small enough that one agent can walk every file in a single pass.

Read-only. Findings only.
