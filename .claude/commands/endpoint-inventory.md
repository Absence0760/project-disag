---
description: Generate a canonical HTTP-route inventory table by reading the router source — the ground-truth list of what endpoints exist. Feeds the persona-integrator agent and an /audit/auth pass.
---

Produce a canonical, table-shaped inventory of every backend HTTP endpoint by **reading the route source** — not by trusting any doc.

Where there is no maintained API spec (or the spec is derived, runtime-generated state rather than the contract), the route source itself is the only authority for "what endpoints exist." This command flattens that into one artifact — a single Markdown table that consumers can read without spelunking the router internals.

This is a **generator**, not a findings audit. It describes what the API *is*; it does not flag bugs. Read-only on the codebase except for writing the one output file.

## What it produces

`reviews/endpoint-inventory.md` — one row per registered route, in router-mount order (the order the routes are wired up at the app's mounting entrypoint). Columns:

| Method | Path | Auth | Tenant/authz scope | Request params | Response shape | Notes |
|--------|------|------|--------------------|----------------|----------------|-------|

Fill each column from the **actual handler code**, never inferred from a doc or a name:

- **Method** — `GET` / `POST` / `PATCH` / `PUT` / `DELETE`, from the route registration.
- **Path** — the full path: the mount prefix joined to the router's own prefix and the in-handler path (e.g. a `/users` mount + a `/:id` handler → `GET /users/:id`).
- **Auth** — `public` or the auth requirement the handler actually enforces, read from the handler itself (middleware, decorator/dependency, or an explicit in-body check). Where one router mixes public and protected handlers, classify **each row by inspecting that specific handler**, not by the router it lives in.
- **Tenant/authz scope** — how the handler scopes data access: the tenant-scoping mechanism (a scoped query helper, a tenant-resolved DB/connection, a row-level filter) and any role/permission requirement. Flag the exceptions explicitly — a handler that touches tenant data through a raw/un-scoped path, hardcodes a tenant, or resolves the tenant from an unusual source (a URL path segment or token instead of the normal header/claim). These are inputs for `/audit/auth`; note them, don't fix them here.
- **Request params** — path params, query params (the real casing the handler reads), and the request body shape for writes. Use the names the handler actually reads, not the doc's names.
- **Response shape** — the response type/schema the handler returns when one is declared; for surfaces with no typed client (webhooks, redirects, raw payloads) say so plainly (e.g. `204 No Content`, `302 → …`, `{ status: "ok" }`, `SVG`).

Then two short cross-reference sections against the client/consumers:

- **Server-only routes (no client function).** Routes with no matching call in the app's client — typically the integrator-facing surface (webhook receivers, upload/ingest endpoints, provisioning, embeds) consumed by external callers rather than the app's own UI. Call these out as the integrator-facing surface.
- **Client calls with no matching route (drift).** Client functions whose URL no longer resolves to a registered route. Each is a real bug — a dead client call. List them with their source location.

## Procedure

1. **Find the route-mounting entrypoint.** Locate where the app wires routers to their mount prefixes and applies any app-level middleware/auth gating (e.g. `app.include_router(...)` in FastAPI, `router.<verb>(...)` mounted via `app.use(...)` in Express, the routes file in Rails, the `mux`/`ServeMux` registrations in Go `net/http`, the blueprint registrations in Flask). This is the source of truth for which routers mount where and what's gated globally. Note the special cases — public mounts, per-handler-gated routers, and routes mounted before a shared middleware.
2. **Read every router / route module.** For each router the entrypoint mounts, open it and enumerate every handler. Don't sample — read them all.
3. **Classify auth + tenant/authz scope per handler** by reading each handler's middleware / decorators / dependencies / in-body checks: what auth it requires (if any), how it scopes tenant data, and any role/permission gate.
4. **Cross-reference the client / consumers.** Match each client call's URL to a registered route to populate the response-shape column and build the two drift sections.
5. **Write `reviews/endpoint-inventory.md`** (overwrite if present). Lead with a one-line note: *generated from the route source on `<date>`; regenerate after adding routes.* This artifact can be **promoted to `docs/`** as a maintained, committed inventory if the team wants it under version control — `reviews/` is typically gitignored, so by default it's a working snapshot.

**Delegate to** the `Explore` (or `general-purpose`) agent: pass this file as the prompt. The agent reads the mounting entrypoint + all route modules + the client, and writes the single output file. Read-only on the rest of the codebase — no other edits, no git.

## Notes

- This is a generator, not an audit. It records the current state; it does not grade auth coverage or tenant-isolation discipline. For findings, pair it with **`/audit/auth`** (route gating + tenant-scope discipline), and hand the table to the **`persona-integrator`** agent, which consumes the integrator-facing surface it surfaces.
- An **API-contract** check (request/response shapes matching across the backend types ↔ client ↔ data model, where there's no codegen) is the natural companion when one exists.
- **Re-run after adding or moving routes** — a new mount or a new handler makes the inventory stale immediately, and any consumer working from it starts from an out-of-date list.

## Guard rails

Read-only / generator — no commits required beyond writing the one artifact. If you do commit it, path-scope the commit (`git commit -m "…" -- reviews/endpoint-inventory.md`). **Never `git push`.**
