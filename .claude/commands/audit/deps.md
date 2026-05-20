---
description: Cross-workspace dependency audit (pnpm + Dependabot config + GitHub Actions pinning)
---

Sweep dependencies for known CVEs and version drift; verify Dependabot covers everything and CI workflow pins aren't a supply-chain risk.

## What this is

The repo has one Node workspace and several non-npm dependency surfaces:

- **`web/frontend/`** — SvelteKit, Vite, Playwright (the only `package.json` under `web/`).
- **`web/backend/`** — Python Lambda. Production dependencies are limited to what the Lambda runtime ships (currently `boto3` + stdlib). `web/backend/requirements-dev.txt` is for the local dev shim only.
- **`web/infra/`** — Terraform; no npm deps. Provider versions live in `versions.tf`.
- **`disag/` and `exceed/`** — stdlib-only Python packages, by repo policy. No `requirements.txt`, no `pyproject.toml` declaring dependencies.

Plus:

- **Root `package.json`** — pnpm workspace orchestration + pnpm overrides (currently the `cookie >= 0.7.0` override pinned via GHSA — see `pnpm-workspace.yaml`).
- **GitHub Actions** — `.github/workflows/*.yml` — action SHA pinning vs `@v6` floating tags.
- **Dependabot config** — `.github/dependabot.yml` — must cover the npm workspace + Terraform + GitHub Actions.

## What to check

1. **`pnpm audit` on the frontend.** Run from the repo root:
   ```
   pnpm --filter disag-md-web audit --audit-level=moderate
   ```
   `disag-md-web` is the workspace name declared in `web/frontend/package.json`. Collect moderate+ findings. For each: package, version, CVE, fix version, manifest path. The canonical resolution shape in this repo is the `cookie` override in `pnpm-workspace.yaml`'s `overrides` block — a transitive that upstream hasn't fixed gets pinned there, with a comment referencing the GHSA.

2. **Dependabot coverage.** Read `.github/dependabot.yml`. The expected shape for this repo is:
   - `package-ecosystem: "npm"` for `web/frontend` (the only npm workspace).
   - `package-ecosystem: "terraform"` for `web/infra` (Dependabot bumps Terraform provider versions inside `versions.tf`).
   - `package-ecosystem: "github-actions"` for `/` (Dependabot scans `.github/workflows/` from this root).
   - Schedule weekly; group where it reduces PR churn (svelte-ecosystem grouping is the usual win).
   - **No npm entry at `/`** — the root `package.json` only holds workspace orchestration + pnpm overrides; nothing for Dependabot to bump there.
   - Flag any missing surface, any non-weekly schedule, or any ungrouped flood of related packages.

3. **Lockfile-sync workflow.** Dependabot edits `web/frontend/package.json` but never touches the root `pnpm-lock.yaml`, which breaks `web-ci.yml`'s `pnpm install --frozen-lockfile`. If this repo runs a compensating `dependabot-lockfile.yml` workflow that regenerates the lockfile on Dependabot PRs and commits the result back, verify:
   - The workflow file exists.
   - It uses a fine-grained PAT (with `Contents: Write`), not `GITHUB_TOKEN` — GitHub blocks the latter from retriggering `pull_request` events.
   - The PAT is scoped to this repo and has an expiry. If it's stale or revoked, dep PRs pile up unmerged.

   If the workflow doesn't exist, surface as Medium — Dependabot PRs will fail CI until a human regenerates the lockfile by hand.

4. **GitHub Actions pinning.** Grep `.github/workflows/` for `uses: <action>@<ref>`.
   - Floating refs (`@main`, `@v6`) are supply-chain risks for actions that can be force-pushed by the publisher.
   - SHA pins (`@<sha>`) are the safer default for workflows that touch `${{ secrets.* }}` or deploy.
   - Flag floating refs on `deploy.yml` (the production-environment deploy workflow), `gitleaks.yml`, `scorecard.yml`. `web-ci.yml`, `security.yml`, `dependabot-auto-merge.yml` are lower-stakes but worth surfacing too.
   - The SHA pin pattern this repo uses is `uses: foo/bar@<40-char-sha> # vX.Y.Z` — the trailing comment carries the human-readable version. Flag if a SHA pin lacks the comment (the next reviewer can't tell what version they're auditing).

5. **Override hygiene.** Read `pnpm-workspace.yaml`'s `overrides` block. For each override:
   - Confirm it's still needed — has upstream shipped a fix that lets us drop the override? Pull the latest version of the package from npm and check.
   - Confirm the override range is tight (e.g. `>=0.7.0` is what the `cookie` override uses; tighter is better if upstream is stable).
   - Confirm there's a comment naming the GHSA / CVE — that's the only way a future reader knows whether the pin is still load-bearing.

6. **Node engines.** Root `package.json` declares an `engines.node` constraint (currently `>=24`). Confirm:
   - CI workflows use a matching `node-version:` (not `18`, not `20`, not `22` — not unspecified).
   - `.tool-versions` (`nodejs <N>`) lines up with `engines.node` so `asdf install` / `mise install` shims a compatible version.
   - The pinned version is one that's still in maintenance — Node 24 is the active LTS as of mid-2026.

7. **Python deps in the Lambda zip.** `web/backend/build.sh` should NOT include `requirements-dev.txt` in the zip — only `handler.py` + the `disag/` and `exceed/` packages (minus `gui.py`). Flag if the build script pip-installs anything into the zip directory.

8. **Terraform provider versions (`web/infra/versions.tf`).** `required_providers` for `aws`, `random`, `sops` should use `~> X.Y` ranges (allows patches) or exact pins. Loose `~> X` (major-only) is too broad. `.terraform.lock.hcl` is committed.

9. **Local toolchain drift.** Optional but worth flagging if obvious: check whether the local pnpm + node versions match `.tool-versions` and `package.json`'s `engines`. The `update-all` function in the user's `~/.bashrc.d/32-functions-update.sh` covers system tools; if local node/pnpm versions are wildly out of sync with what CI uses, flag it.

## Report

- **Critical** — known-exploited CVE in a runtime path (the production Lambda or the deployed frontend bundle), not just a dev-only transitive.
- **High** — a CVE with a fix available; a deploy workflow using a floating action ref; Dependabot missing the npm workspace or the Terraform directory.
- **Medium** — version drift with no CVE but the upgrade is overdue; loose override range; Node engines mismatch between repo and CI; missing `dependabot-lockfile.yml` if Dependabot PRs are currently failing CI.
- **Low** — undocumented override, floating ref in a non-deploy workflow, dependabot grouping that could be tightened, SHA pin missing its `# vX.Y.Z` comment.

For each finding: package + version + advisory link + the file to change + the upgrade command (or the override expression).

## Useful starting points

- `package.json` (root) — workspace orchestration
- `pnpm-workspace.yaml` — workspace declaration + `overrides` block
- `web/frontend/package.json` — the only npm workspace
- `web/infra/versions.tf` — Terraform + provider pins
- `.github/workflows/*.yml`
- `.github/dependabot.yml`
- `.tool-versions` — local toolchain pins

## Delegate to

Use a `general-purpose` agent — the work is mostly running each tool in turn and reading the output. Pass this file as the prompt body.

Read-only audit. Recommend upgrades; don't apply them without instruction (a major bump is its own conversation).
