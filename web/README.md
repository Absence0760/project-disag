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
INPUTS_BUCKET=<dev-bucket> OUTPUTS_BUCKET=<dev-bucket> AWS_PROFILE=<profile> \
  pnpm dev
```

`pnpm dev` runs SvelteKit on `http://localhost:5173` and the local
Lambda shim on `http://localhost:8000` side-by-side (concurrently
labels them `web` / `api`). Kill one, both go down.

Point the frontend at the local backend by setting
`VITE_API_BASE=http://localhost:8000` in `web/frontend/.env`.

### Frontend only / backend only

```bash
pnpm dev:web                   # SvelteKit only — http://localhost:5173
pnpm dev:api                   # local Lambda shim only — http://localhost:8000
```

You need real S3 buckets (or LocalStack) for pre-signed URLs to work
end-to-end; the rest of the routes work against any S3-compatible
endpoint your AWS profile resolves to.

## Provisioning infrastructure (local, with AWS SSO)

This project runs in its own AWS sub-account (`disag-prod`) under the
`jaredhoward` AWS Organization, with `disag.jaredhoward.com` as a
delegated Route 53 subdomain. **The account and its baseline are
provisioned by the cross-project bootstrap tooling**, not by this
repo's Terraform.

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
#    domain_name, hosted_zone_id, deploy_role_arn — all from the bootstrap output

# 3. Uncomment the backend "s3" block in web/infra/versions.tf and fill in
#    the tfstate bucket name from bootstrap (locking uses S3 conditional
#    writes — `use_lockfile = true` — no DynamoDB needed).

# 4. Rewrite .sops.yaml's REPLACE_ME placeholder with the project account
#    ID. `pnpm sops:bootstrap` does this automatically by calling
#    `aws sts get-caller-identity` against the active AWS profile.

# 5. Apply this repo's Terraform (creates the us-east-1 ACM cert for the
#    subdomain, CloudFront distribution with the alias, three S3 buckets,
#    Lambda + API Gateway, and attaches deploy policies to the OIDC role).
export AWS_PROFILE=disag
pnpm tf:login
pnpm tf:init
pnpm tf:apply
```

The ACM cert is created here (not in the bootstrap baseline) because
its DNS validation requires the parent zone's NS delegation to be live,
which only happens after the bootstrap's final stage.

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

You should also create a GitHub `production` environment in repo
Settings → Environments and add required reviewers — that's what
gates the OIDC trust policy. Without it, the role can be assumed by
any job in the repo that requests the `production` environment.

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
the deploy role created in `oidc.tf`. No long-lived access keys
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
| `/exceed` | POST | Runs `exceed.algorithm.calculate_monthly_exceedance` per calendar month. |
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
