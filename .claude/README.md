# .claude/ — Claude Code tooling

These agents and commands were derived from real working projects (primarily `meryl-green-designs`, a SvelteKit + Hono + DynamoDB e-commerce site) and **lightly generalized** with placeholder names: `<payment-processor>`, `<CMS>`, `<email-service>`, `<aws-region>`, `<EMAIL_SERVICE>_API_KEY`, etc.

**They will not be 100% accurate for your project out of the box.** Each new project should re-read these and replace placeholder examples with the actual services / routes / file paths in use. Treat them as templates of *structure and rigor*, not as fully-portable boilerplate.

## What's here

### Agents (`agents/`)

- **`code-reviewer.md`** — invoked at PR / pre-commit time to review the diff against the project's documented rules.
- **`doc-hygiene-checker.md`** — checks that code changes update docs and tests in the same change.
- **`test-gap-checker.md`** — finds modules / routes without test coverage.
- **`ui-polisher.md`** — applies typography / layout polish to frontend surfaces. Heavily SvelteKit-flavoured; adapt for other frontend frameworks.
- **`repo-security-auditor.md`** — read-only security auditor. The "trust boundaries" section needs rewriting per project — the example boundaries (frontend ↔ user, backend ↔ caller, backend ↔ <CMS>, backend ↔ <payment-processor>) are meryl-shape, not universal.

### Commands (`commands/`)

- **`check.md`** — run typecheck + tests + format + lint and report.
- **`safe-edit.md`** — workflow for edits to security-sensitive or load-bearing files.
- **`polish-ui.md`** — orchestrates the `ui-polisher` agent against a target surface.
- **`release-readiness.md`** — go/no-go checklist before tagging a release.
- **`audit/`** — directory of focused security audits. Each command delegates to the `repo-security-auditor` agent with a specific area:
  - `secrets.md`, `infra.md`, `deps.md`, `xss.md`, `cost-controls.md`
  - `all.md` runs them all in sequence
  - `README.md` is the index

## Adapting these for a new project

1. Rewrite the trust-boundary map in `agents/repo-security-auditor.md` to match your stack's actual third-party integrations.
2. Update route tables in `audit/cost-controls.md` and `audit/infra.md` to match your `backend/src/routes/*` and `infra/*.tf`.
3. Replace the `<placeholder>` tokens (`<payment-processor>`, `<CMS>`, `<email-service>`, `<aws-region>`) with real service names so the agents stop emitting them in reports.
4. Add stack-specific audits not covered here (Postgres RLS? Edge functions? Mobile-twin parity? — see `project-running`'s `.claude/commands/audit/` for ideas).
5. Remove audits that don't apply (e.g. `cost-controls.md` doesn't apply to a static-only site with no Lambda / no third-party APIs).
