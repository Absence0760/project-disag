# web/ — Disag-MD web UI

A SvelteKit single-page app in front of an AWS Lambda backend that
wraps the `disag/` and `exceed/` Python packages from this repo.

Files flow through S3: the browser uploads to a pre-signed PUT URL,
Lambda processes the inputs in `/tmp`, writes outputs back to a second
S3 bucket, and the browser downloads via pre-signed GETs. Previous
runs live under `runs/<tool>/<run-id>/` and surface on the History
page.

## Layout

```
package.json            pnpm workspace root, orchestration scripts (dev / build / deploy)
pnpm-workspace.yaml     declares web/frontend as the JS workspace
web/
  frontend/   SvelteKit + TypeScript + adapter-static
  backend/    Lambda handler (handler.py) + local dev shim + build.sh
  infra/      Terraform: S3 × 3, Lambda, API Gateway HTTP API, CloudFront
```

## Scripts (run from anywhere in the repo)

| Script | What it does |
|--------|--------------|
| `pnpm setup` | One-time install: pnpm deps + Python venv (`web/backend/.venv`) with `boto3`. |
| `pnpm dev` | Frontend + local Lambda backend in parallel. Auto-bootstraps the venv on first run. |
| `pnpm dev:web` / `pnpm dev:api` | Either one on its own. |
| `pnpm build` | SvelteKit static build **and** Lambda zip. |
| `pnpm preview:web` | Serve the production frontend build locally. |
| `pnpm check` | Python tests + SvelteKit `check`/`lint` + Terraform `fmt`/`validate`. |
| `pnpm e2e` | Playwright E2E (mocked backend) — fast, no Python needed. |
| `pnpm e2e:integration` | Playwright E2E that boots `local_server.py` with `LOCAL_S3=1` and runs real disag/exceed code against `examples/methodN_demo/data/`. |
| `pnpm e2e:all` | Mocked + integration in sequence. |
| `pnpm e2e:ui` | Playwright interactive runner. |
| `pnpm e2e:install` | One-time browser install (chromium + firefox). |
| `pnpm format` | Prettier on `web/frontend`, `terraform fmt` on `web/infra`. |
| `pnpm tf:login` | `aws sso login --profile $AWS_PROFILE` — refresh SSO creds before infra work. |
| `pnpm tf:init` / `tf:plan` / `tf:apply` / `tf:destroy` | Terraform lifecycle. |
| `pnpm tf:outputs` | Dump terraform outputs as JSON (function name, buckets, role ARN, etc.). |
| `pnpm tf:export-vars` | Push Terraform outputs into GitHub repo variables so `deploy.yml` can read them. |
| `pnpm sops:bootstrap` | Replace the `REPLACE_ME` account-id placeholder in `.sops.yaml` with the active AWS account (via `aws sts get-caller-identity`). Idempotent. |
| `pnpm sops:edit` | `sops web/infra/secrets.enc.yaml` — edit in `$EDITOR`, re-encrypt on save. |
| `pnpm sops:rotate` | Re-encrypt with the keys in `.sops.yaml` after a key rotation. |
| `pnpm deploy` | Local one-shot deploy: build → `terraform apply` → sync site → invalidate. |
| `pnpm deploy:web` | Just resync the static site + invalidate (no backend redeploy). |

The Python packages (`disag/`, `exceed/`) are not duplicated — the
Lambda zip is built by `backend/build.sh`, which copies them into the
package alongside `handler.py`.

## Running locally

The repo root is a pnpm workspace; every dev/build/deploy verb is a
`pnpm` script. Run from anywhere in the tree.

### One-time setup

```bash
corepack enable                # if pnpm isn't on PATH yet
pnpm setup                     # installs frontend deps + creates web/backend/.venv with boto3
```

(`pnpm setup` = `pnpm install` + `pnpm setup:py`. The venv only matters
for the local dev shim — production Lambda uses the runtime's boto3.)

### Dev loop (frontend + backend together)

```bash
pnpm dev
```

That's it — no AWS creds, no env vars. `dev:api` defaults to
`LOCAL_S3=1`, so the backend uses an in-process S3 stub rooted at
`/tmp/disag-local-s3/`. SvelteKit runs on `http://localhost:5173` and
the Lambda shim on `http://localhost:8000`; concurrently labels them
`web` / `api`. Kill one, both go down.

The frontend talks to the backend via Vite's `/api/*` proxy
(see `web/frontend/vite.config.ts`) — no `VITE_API_BASE` needed.

### Pointing at real AWS instead

If you want pre-signed URLs to hit actual S3 buckets (e.g. to
reproduce a prod-shaped run):

```bash
LOCAL_S3=0 \
  INPUTS_BUCKET=<dev-bucket> OUTPUTS_BUCKET=<dev-bucket> \
  AWS_PROFILE=<profile> \
  pnpm dev
```

`LOCAL_S3=0` opts out of the stub; the named buckets need read/write
under the chosen AWS profile.

### Frontend only / backend only

```bash
pnpm dev:web                   # SvelteKit only — http://localhost:5173
pnpm dev:api                   # local Lambda shim only — http://localhost:8000 (LOCAL_S3=1 by default)
```

## Provisioning infrastructure (local, with AWS SSO)

This project runs in its own AWS sub-account under an organisation
parent, with a delegated Route 53 subdomain (e.g. `project.example.com`).
**The account and its baseline are provisioned by the cross-project
bootstrap tooling**, not by this repo's Terraform.

### One-time bootstrap (cross-project tooling)

The account itself, plus tfstate bucket, sops KMS key, GitHub OIDC
provider + scoped deploy role, child Route 53 zone, and budget alarm,
are all created by:

```bash
cd ~/repos/templates
cp infra/bootstrap/projects/example.tfvars infra/bootstrap/projects/disag.tfvars
$EDITOR infra/bootstrap/projects/disag.tfvars        # project=disag, github_repo=…, etc.
./scripts/new-project-account.sh disag --plan        # dry-run
./scripts/new-project-account.sh disag               # apply (~3-5 min)
```

The script prints the new account ID, state bucket, KMS alias, deploy
role ARN, hosted zone ID, etc. Source of truth:
[~/repos/templates/infra/bootstrap/README.md](../../templates/infra/bootstrap/README.md).

### Wire up this repo

After bootstrap completes:

```bash
# 1. Add an SSO profile for the new account.
aws configure sso --profile disag
#    SSO start URL: same as mgmt; account: <bootstrap output>; role: AdministratorAccess

# 2. Fill in the project's bootstrap-derived values.
cp web/infra/terraform.tfvars.example web/infra/terraform.tfvars
$EDITOR web/infra/terraform.tfvars
#    bootstrap_slug must match the slug new-project-account.sh was run
#    with (so this repo finds the bootstrap-owned deploy role + KMS key);
#    allowed_origin gets a real CloudFront URL after the first apply.

# 3. Uncomment the backend "s3" block in web/infra/versions.tf and fill in
#    the tfstate bucket name from bootstrap (locking uses S3 conditional
#    writes — `use_lockfile = true` — no DynamoDB needed).

# 4. Rewrite .sops.yaml's REPLACE_ME placeholder with the project account
#    ID. `pnpm sops:bootstrap` does this automatically by calling
#    `aws sts get-caller-identity` against the active AWS profile.

# 5. Apply this repo's Terraform (creates the CloudFront distribution on
#    its default cloudfront.net domain, three S3 buckets, Lambda + API
#    Gateway, WAF + alarms, and attaches this repo's deploy policy to the
#    bootstrap-owned OIDC role).
export AWS_PROFILE=disag
pnpm tf:login
pnpm tf:init
pnpm tf:apply
```

A custom domain + ACM cert isn't in the Terraform yet — the
distribution serves from its `*.cloudfront.net` default. When a real
domain lands, the ACM cert + CloudFront alias belong here (not in the
bootstrap), because DNS validation needs the bootstrap's delegated zone
to be live first.

### Editing sensitive infra config

Nothing in `variables.tf` today needs encrypting — every value is
public. When that changes (custom-domain ACM ARN, private origin,
third-party API key, etc.), put it in `web/infra/secrets.enc.yaml`:

```bash
# First time:
cp web/infra/secrets.enc.yaml.example web/infra/secrets.enc.yaml
sops -e -i web/infra/secrets.enc.yaml

# Edit any time:
pnpm sops:edit                  # sops handles decrypt → $EDITOR → re-encrypt
```

Then uncomment the `data "sops_file"` block sketched in
`versions.tf` and reference values as
`data.sops_file.secrets.data["key_name"]`. The file is decrypted on
each `terraform plan`/`apply` using the active AWS profile's KMS
access — `pnpm tf:login` first if creds are stale.

### Hand off to CI

After the first apply, push the resource names + role ARN into
GitHub repo variables so the release workflow can use them:

```bash
pnpm tf:export-vars             # sets AWS_DEPLOY_ROLE_ARN, AWS_REGION,
                                # LAMBDA_FUNCTION_NAME, FRONTEND_BUCKET,
                                # CLOUDFRONT_DISTRIBUTION_ID via gh CLI
```

Verify with `gh variable list`. Re-run after any apply that renames
resources (e.g. the `random_id` suffix changes).

### Pre-launch checklist (root-account / outside-Terraform steps)

A handful of safeguards aren't expressible in this repo's Terraform —
they're root-account toggles or Service Quotas raises that the
bootstrap can't do for you. Run through these once per project
account; the audit-report items they close are noted in brackets.

1. **GitHub `production` environment with required reviewers.**
   Repo Settings → Environments → New environment "production" →
   add yourself (or a small group) as Required reviewers. **This is
   the only thing standing between any merged workflow and the
   deploy role.** The OIDC trust policy gates on `environment:
   production`, but without a reviewer requirement on the GitHub
   side any maintainer who pushes a workflow that requests that
   environment can assume the role. [audit/infra Medium]

2. **Enable IAM billing access on the member account** so Budgets
   can be created. Root login → Account → Billing settings → toggle
   on "IAM user and role access to billing information". Until
   that's done, `aws_budgets_budget` resources fail apply with
   AccessDeniedException. Once done, set `budget_monthly_usd` in
   your local `terraform.tfvars`. [audit/cost-controls Critical]

3. **Raise the "Concurrent executions" Service Quota** above the
   new-account 10-cap so `lambda_reserved_concurrency` can be set
   without AWS rejecting the apply for `unreserved >= 10`. Service
   Quotas → AWS Lambda → Concurrent executions → request increase
   (any value ≥ 100 lets you reserve 5–20). [audit/cost-controls High]

4. **Confirm the SNS subscription** AWS emails on first apply with
   the budget alarm. An unconfirmed subscription is a silent failure
   — alarms still fire in the console but no one is paged. Check
   in the AWS Console → SNS → Topics → `<project>-prod-alerts` →
   Subscriptions → status should read `Confirmed`. [audit/cost-controls Low]

## Releasing

The web app is deployed by tagging a release. The Python tool's
release flow uses `v*` tags (see `release.yml`); the web app uses
the `web-v*` prefix so they don't collide.

```bash
# Tag and publish a release.
gh release create web-v0.2.0 \
  --title "web v0.2.0" \
  --generate-notes
```

`.github/workflows/deploy.yml` fires on `release: published`,
checks the tag matches `web-v*` and is not a pre-release, then runs
two jobs both targeting the `production` environment:

1. **deploy-backend** — rebuilds the Lambda zip from the tagged ref
   and runs `aws lambda update-function-code` followed by
   `wait function-updated`.
2. **deploy-frontend** — `pnpm build:web`, `aws s3 sync`,
   `aws cloudfront create-invalidation`, then waits for the
   invalidation to complete.

Backend deploys first so the static site never points at a stale
API contract. Both jobs use OIDC (`id-token: write`) to assume
the bootstrap-owned deploy role that `oidc.tf` looks up and
attaches this repo's deploy policy to. No long-lived access keys
exist in the repo.

To deploy out-of-band (no release) or replay a specific tag:

```bash
gh workflow run deploy.yml -f tag=web-v0.2.0
```

### Manual / break-glass deploy

If GitHub Actions is down, the same actions can run locally:

```bash
export AWS_PROFILE=disag
pnpm tf:login
pnpm deploy                     # build → tf:apply → deploy:web
```

## What's wired

| Route | Method | Purpose |
|-------|--------|---------|
| `/upload` | POST | Returns a pre-signed S3 PUT URL for one input file. |
| `/disag`  | POST | Runs `disag.algorithm.disaggregate`. |
| `/exceed` | POST | Flow-frequency curves per calendar month (or per free-form `seasons` group). Returns an SVG curve as `output` plus the tabular `.rep`. |
| `/runs`   | GET  | Lists stored runs. |
| `/runs/{run_id}` | GET | Returns pre-signed download URLs for a run's output + report. |

## Compute notes

The Lambda is sized at 4 GB / 5 min by default (see
`lambda_memory_mb` and `lambda_timeout_seconds` in
`infra/variables.tf`). Lambda hands out CPU in proportion to memory —
4 GB ≈ 2.2 vCPU, 10 GB ≈ 6 vCPU — so bump memory if Method 5
(`PATCH_EXCEED`) on a large monthly file pushes past the 5-minute
budget. Hard ceiling is 900 s (15 min); past that, switch to Fargate.

Architecture is `arm64` (Graviton) — same Python 3.14 image, ~20%
cheaper per millisecond.

## Security / dependency posture

Workflows added at the repo root in `.github/workflows/`:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `security.yml` | push / PR / Mondays | CodeQL on python, javascript-typescript, actions. |
| `gitleaks.yml` | push / PR / Mondays | Secret scan, full history weekly. |
| `scorecard.yml` | push / Mondays | OpenSSF Scorecard → Security tab + scorecard.dev. |
| `dependabot-auto-merge.yml` | dependabot PRs | Auto-merge minor + patch updates. |
| `web-ci.yml` | push / PR touching `web/**` | Frontend lint/check/build, backend zip smoke build, terraform fmt+validate, mocked + integration Playwright. |
| `deploy.yml` | release `web-v*` published, or `workflow_dispatch` | Backend → Lambda update; frontend → S3 sync + CloudFront invalidate. OIDC, no static creds. |

`.github/dependabot.yml` covers npm (`web/frontend`), terraform
(`web/infra`), and github-actions. The Python packages are
intentionally not listed — they're stdlib-only by repo policy.

## Caveats

- The first `terraform apply` opens the inputs bucket and API to
  `allowed_origin = "*"`. Narrow it to the CloudFront URL after the
  first apply (re-run apply).
- The Lambda zip ships `disag/` and `exceed/` minus their `gui.py`
  modules. If you add another GUI-only module, strip it in
  `backend/build.sh` so the zip stays small.
- Existing local file paths in the CLI (`--monthly file.mon`) become
  S3 keys in the API surface (`monthly_key: "inputs/<uuid>/file.mon"`).
  The Lambda downloads each input to `/tmp/<run-id>/` before calling
  into the package — `disag.files.read_*` only knows local paths.
