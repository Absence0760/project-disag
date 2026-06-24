---
description: Find anything that looks like a secret outside the sops-encrypted store — committed plaintext, AWS keys in workflows, leaked git history, Lambda zip carrying credentials.
---

Audit for secrets / env vars / API keys that should live only in sops-encrypted files or short-lived OIDC tokens, but are reachable from git history, a workflow log, a public asset, or the deployed Lambda zip.

## Goal

This repo's secrets posture is small but specific:

- **sops + AWS KMS** for any sensitive infra value — but kept in the PRIVATE sibling repo `../infra-secrets/disag/prod.sops.yaml` (keyed by `alias/disag-sops`), never in this public repo. No `.sops.yaml` or `secrets.enc.yaml` should exist in this tree.
- **OIDC** for AWS deploys (`web/infra/oidc.tf` → `.github/workflows/deploy.yml`). No long-lived AWS access keys.
- **stdlib-only Python** in `disag/` / `exceed/` — no `.env` of any kind.
- **SvelteKit static frontend** — only `VITE_*` vars ship to the client; everything else is server-only.

Find anything on the wrong side, and confirm the patterns are actually being honoured.

## What to check

1. **No secret material lives in THIS repo.**
   - Prod secrets belong in the private `../infra-secrets/disag/`, encrypted under `alias/disag-sops`. This public repo should contain NO sops-encrypted files, NO `.sops.yaml`, and NO plaintext `secrets.*`.
   - Scan the tree: any `.sops.yaml`, `secrets.enc.yaml`, `secrets.yaml`, or `secrets.json` present is a convention violation — **High** (or **Critical** if it's a *decrypted* secret in plaintext).

2. **Secrets absent from git history.**
   - `git log --all --full-history -- web/infra/secrets.yaml web/infra/secrets.json web/infra/secrets.enc.yaml .sops.yaml` should return zero commits with real secret material. The old `.sops.yaml`/`.example` scaffolding may appear in pre-migration history — that's a removed-template, not a leaked secret; a *decrypted* value is **Critical** and needs rotation.
   - `web/infra/.gitignore` blocks `*.enc.yaml` / `secrets.yaml` / `secrets.json`. Verify with `git check-ignore web/infra/secrets.enc.yaml`.

3. **Sibling private repo, if present.**
   - If `../infra-secrets/disag/prod.sops.yaml` exists, confirm it has the sops shape: a `sops:` metadata block with `kms:` recipient ARNs, `mac`, and `version`; sensitive leaf values are `ENC[AES256_GCM,data:...]`. A file edited with a plain `$EDITOR` instead of `sops <file>` fails `mac` validation — flag.
   - This is a separate private repo; if it isn't checked out, note that and move on (not a finding).

4. **`.env*` files at workspace roots.**
   - `web/frontend/.env`: gitignored. The committed template is `web/frontend/.env.example`; it should only contain `VITE_*` keys (currently just `VITE_API_BASE`). Any non-`VITE_*` key in the example file is a finding — it's a hint someone tried to put a server-only secret on the client side.
   - No other `.env` files should exist anywhere — `disag/` and `exceed/` are stdlib-only by policy.
   - `git log --all --full-history -- web/frontend/.env` should return zero commits. Critical if it returns any.

5. **Client-bundle leakage (SvelteKit).**
   - The frontend uses `adapter-static`, so `$env/static/private` and `$env/dynamic/*` aren't accessible from client code. Grep `web/frontend/src/` for `$env/static/private`, `$env/dynamic/`. Every hit is a finding — likely Critical because it implies an SSR adapter snuck in.
   - Grep `web/frontend/src/` for raw `process.env` references. The static build doesn't expose `process.env` to the client; any reference is either dead code or a bug.
   - Vite inlines `import.meta.env.VITE_*` into the bundle — confirm any new `VITE_*` is intentionally public.

6. **Lambda zip hygiene.**
   - `web/backend/build.sh` ships `disag/` and `exceed/` minus `gui.py`. Any other file under those packages that smells like an env / secret (`.env`, `*.key`, `credentials*`, `*.pem`, `*.p12`) should be stripped — verify the `build.sh` exclusion list.
   - The handler's only "secrets" are the bucket names from env vars (`INPUTS_BUCKET`, `OUTPUTS_BUCKET`) — those are populated by Terraform at deploy time, not committed.
   - `web/backend/requirements-dev.txt` is for the local dev venv only; confirm it's NOT included in the zip (it shouldn't be — `build.sh` only copies `handler.py` + the two packages).

7. **GitHub Actions workflow secrets.**
   - `.github/workflows/*.yml`: every `env:` value should be either a literal non-secret, `${{ secrets.X }}`, or `${{ vars.X }}`. A literal AWS key in any workflow → **Critical**.
   - Deploy steps must use OIDC (`aws-actions/configure-aws-credentials@<SHA> # v6+` with `role-to-assume:`), never `aws-access-key-id` / `aws-secret-access-key`. A long-lived AWS key reference anywhere → **Critical**.
   - The `dependabot-lockfile.yml` PAT (`DEPENDABOT_LOCKFILE_PAT`) is stored in the **Dependabot** secrets store, not the Actions store (per the workflow's own header comment). Verify with `gh api repos/:owner/:repo/dependabot/secrets`.
   - Steps that touch a secret must not `echo` it or run with `set -x` in scope. Grep for `echo $\{` or `echo \"\$\{\{ secrets` patterns.

8. **Public asset leak.**
   - `web/frontend/static/` (Vite-served as `/`) — any committed file containing key shapes (`AKIA[0-9A-Z]{16}`, `sk_`, `Bearer `, hex strings ≥ 40 chars, `-----BEGIN.*PRIVATE KEY-----`) is a finding.
   - The favicon SVG in `web/frontend/src/app.html` is inline and harmless; ignore.

9. **Git history pickaxe.**
   - `git log --all -S 'AKIA' -S 'aws_secret_access_key' -S 'BEGIN PRIVATE KEY' -S 'BEGIN RSA' -S 'sk_live_' -S 'GHSA' --source --pretty=fuller`
   - The `-S` pickaxe finds commits that added or removed the literal string. A single touch on a real secret means the value is permanently exposed and needs rotation regardless of subsequent removal — flag as **Critical** with the recommendation "rotate the underlying credential, the value can be recovered from git history."

10. **OIDC trust policy scope (cross-check with `audit/infra`).**
    - `web/infra/oidc.tf`'s `:sub` condition pins `environment:production`. If it's been weakened to `*` or a ref pattern that matches any branch, that's the headline finding for this audit — Critical. (The full IAM check belongs in `audit/infra`; here we just flag the secrets-adjacent half.)

11. **`.gitignore` coverage.**
    - Confirm `.gitignore` ignores: `web/frontend/.env`, `web/infra/*.tfvars` (with `!*.tfvars.example` exception), `.sops.yaml`, `secrets.enc.yaml`, `web/infra/secrets.enc.yaml`, `web/infra/secrets.yaml`, `web/infra/secrets.json`, `web/infra/*.tfstate*`, `web/backend/.local-s3/`, `web/backend/lambda.zip`. Any missing → Medium.

## Report

- **Critical** — real secret in git history, a long-lived AWS access key in any workflow, an SSR adapter that exposes server-only env to the client, a decrypted plaintext secret committed anywhere, OIDC `:sub` condition wildcarded.
- **High** — any sops/secret file (`.sops.yaml`, `*.enc.yaml`, `secrets.*`) committed into this public repo instead of `../infra-secrets`, server-only env referenced from a non-server frontend path, workflow logs an env var, non-`VITE_*` key in `web/frontend/.env.example`.
- **Medium** — env var named in an example file but missing from the encrypted file, key in the encrypted file with no documented purpose, `.gitignore` missing a path.
- **Low** — undocumented env intent, missing example entry, broader-than-needed `encrypted_regex` match.

For each: the literal env-var name and the file:line, what should change. **Never paste a found key value into the report — identify by name + location only.**

## Useful starting points

- `../infra-secrets/disag/` — where prod secrets actually live (private repo); `../infra-secrets/.sops.yaml` holds the creation rule + KMS recipient
- `web/frontend/.env.example` — the only `.env` that should exist
- `web/backend/build.sh` — what gets shipped in the Lambda zip
- `.github/workflows/deploy.yml` — OIDC reference pattern
- `web/README.md § Provisioning infrastructure` — the sops workflow

## Delegate to

`general-purpose` agent (or `repo-security-auditor` if it's been ported) with this file as the prompt body.

Read-only. Recommendations only — never paste a found key into the report. Identify by name + location.
