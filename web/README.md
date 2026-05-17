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
| `pnpm e2e` | Playwright E2E tests (`web/frontend/e2e/`) against the production build. |
| `pnpm e2e:ui` | Playwright interactive runner. |
| `pnpm e2e:install` | One-time browser install (chromium + firefox). |
| `pnpm format` | Prettier on `web/frontend`, `terraform fmt` on `web/infra`. |
| `pnpm tf:init` / `tf:plan` / `tf:apply` / `tf:destroy` | Terraform lifecycle. |
| `pnpm deploy` | Build everything → `terraform apply` → sync site → CloudFront invalidate. |
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

## Deploying

### One-time bootstrap

```bash
cp web/infra/terraform.tfvars.example web/infra/terraform.tfvars   # edit values
# Optional: set up a remote backend before the first apply.
# See the commented-out `backend "s3"` block in versions.tf and a
# bootstrap module (not included) for the state bucket itself.
pnpm tf:init
pnpm tf:apply
```

The first apply will:

1. Create the three S3 buckets (inputs, outputs, frontend).
2. Build the Lambda zip via `backend/build.sh` (the `null_resource`
   in `lambda.tf` triggers this automatically on every source change).
3. Wire up API Gateway and CloudFront.

### Push a new frontend build

```bash
pnpm deploy:web                # build → sync to S3 → invalidate CloudFront
```

### Push a new backend build

```bash
pnpm tf:apply                  # rehashes the zip and replaces the function code
```

### Full deploy

```bash
pnpm deploy                    # build everything, terraform apply, sync frontend
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
| `web-ci.yml` | push / PR touching `web/**` | Frontend lint/check/build, backend zip smoke build, terraform fmt+validate. |

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
