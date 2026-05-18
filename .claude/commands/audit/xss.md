---
description: Audit Svelte rendering paths for XSS — `{@html}`, dynamic `href` / `src`, user-supplied file names and error messages
---

Find every place user-supplied text is rendered as HTML or as a URL-shaped attribute, and verify it's either escaped (Svelte's default) or sanitised.

## Goal

The frontend is a static SvelteKit site (`adapter-static`). Most strings are rendered as text via `{value}` — safe by default. The risk surfaces are: anything using `{@html}`, dynamically constructed `href` / `src` attributes, SVG content, and any user-supplied data that round-trips through the backend (file names from uploaded `.mon` / `.day` files, error messages echoed back from `handler.py`).

There is no CMS, no rich-text rendering, no email template, and no server-rendered HTML in this project. If the audit ever surfaces one of those, treat it as a new surface to spec rather than mapping it to an existing pattern.

## What to check

1. **Svelte `{@html}`.** Grep `web/frontend/src/` for `{@html`. For every hit, trace the source of the rendered string. If it originates from user input or any backend response, the rendered value must come out of a sanitiser. Static / build-time strings are fine. Today this should return zero hits — flag every one.

2. **Dynamic `href` / `src` attributes.** Grep `web/frontend/src/` for `href={` and `src={` inside `<a>` and `<img>`. For each, trace the source. If user/backend-controlled, the value must be validated to reject `javascript:` and `data:` schemes. The pre-signed S3 download URLs come from the Lambda — `https://`-only by construction, but cross-check that the backend has no path that could return a `javascript:` URL through `RunResult.download_url`.

3. **File names round-tripping through the backend.** Uploaded file names appear in the `RunResult` payload, in the history list (`GET /runs`), and on the run detail page. The backend sanitises with `safe_filename` (per `handler.py`) but the frontend should never `{@html}` them. Confirm they render as text via `{value}`.

4. **Error messages echoed back.** When the Lambda returns an error JSON (`{"error": "..."}`), the frontend renders that string in the run page's status area. Confirm it's rendered as text, not HTML. A bad actor uploading a file whose contents the backend echoes verbatim in an error could otherwise smuggle markup back into the page.

5. **SVG content.** SVG can carry script. Today the frontend uses no inline SVG sourced from user input. If that ever becomes a renderable surface (e.g. a chart from a generated report), confirm:
   - The SVG is rendered via `<img src="data:image/svg+xml,...">` (browser treats `<img>`-loaded SVG as image, no script execution), OR
   - The SVG goes through an inline sanitiser before any `{@html}` use.

6. **HTML in any future report renderer.** The `.rep` text reports currently render as a downloadable file, not in-page HTML. If a future change starts rendering report contents directly in the DOM, that's a new surface — verify it goes through `{value}` and a `<pre>` block, not `{@html}`.

## Report

- **High** — user/backend input reaches the DOM as HTML without sanitisation. Provide a payload that would prove it (e.g. a `.mon` file whose name contains `<img src=x onerror=alert(1)>` renders as a script-trigger after a failed upload).
- **Medium** — sanitisation exists but is bypassable, or `href` / `src` validation accepts a borderline scheme (`data:`, `vbscript:`).
- **Low** — escaping is correct but the surrounding code makes future XSS easy to introduce (e.g. a helper that returns a string sometimes-as-HTML, sometimes-as-text).

For each: file:line, the source of the user-supplied text, the rendering site, the missing sanitiser.

## Useful starting points

- `web/frontend/src/routes/run/+page.svelte` — primary in-app surface for backend responses
- `web/frontend/src/routes/history/+page.svelte` — file-name display
- `web/frontend/src/lib/FileDrop.svelte` — file-name display on the upload widget
- `web/frontend/src/lib/api.ts` — the layer that parses backend responses
- `web/backend/handler.py` — the `safe_filename` helper + error-response shape

## Delegate to

Use the `repo-security-auditor` agent: `"Audit Svelte rendering paths for XSS — {@html}, dynamic href/src, SVG, user-supplied file names and error strings round-tripping through the backend."`

Read-only. Report findings; don't patch without confirmation.
