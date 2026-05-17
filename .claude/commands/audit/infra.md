---
description: Audit the Terraform under web/infra/ — OIDC scope, IAM least-privilege, S3 + CloudFront hygiene, sops alignment, log retention, drift.
---

Audit the Terraform stack at `web/infra/` against the architecture documented in `web/README.md` (Provisioning + Releasing sections) and the conventions in this repo.

## Goal

The blast radius of a wrong line in `web/infra/` is high: a permissive OIDC trust policy makes the entire AWS account writable from any workflow in this repo; a public-access misconfig on the outputs bucket leaks every previous run's report; a missing `lifecycle.ignore_changes` makes `pnpm tf:plan` fight the deploy workflow on every release. Catch the high-cost mistakes before `terraform apply` reaches the real account.

## Files in scope

Every `.tf` file under `web/infra/`, plus the sops machinery:

- `versions.tf` — terraform + provider pins
- `providers.tf` — AWS provider + default_tags, alias for us_east_1
- `variables.tf` — inputs + the `github_repository` / `github_deploy_environment` knobs
- `outputs.tf` — exported values (the source of the GitHub repo vars via `pnpm tf:export-vars`)
- `s3.tf` — three buckets (inputs / outputs / frontend), encryption, PAB, lifecycle, CORS, versioning
- `lambda.tf` — function + log group + null_resource that rebuilds the zip
- `apigw.tf` — HTTP API v2 + catch-all route + access logs
- `cloudfront.tf` — distribution + OAC + S3 origin + API Gateway origin + SPA fallback
- `iam.tf` — Lambda execution role + S3 access policy
- `oidc.tf` — GitHub Actions OIDC provider + deploy role + per-resource policy
- `.sops.yaml` (repo root) — KMS creation rules
- `web/infra/secrets.enc.yaml.example` — sops shape; encrypted sibling is `web/infra/secrets.enc.yaml` (gitignored as a plaintext name; the `.enc.yaml` variant is explicitly allow-listed)

## What to check

1. **State backend.**
   - `versions.tf` has a `terraform { backend "s3" { ... } }` block — currently commented out per the bootstrap notes. Flag if uncommented without the bucket actually existing.
   - If the backend block is active, `use_lockfile = true` is preferred over the legacy DynamoDB lock table — saves a few cents/month and removes a moving part. Surface as a Low if you see a DynamoDB lock when `use_lockfile` would do.
   - The state bucket itself must have versioning + Public Access Block (bootstrap concern, not Terraform-managed). Flag if the README's bootstrap section doesn't mention it.

2. **OIDC trust policy (`oidc.tf`).** This is the highest-blast-radius file in the repo.
   - `aws_iam_role.github_deploy.assume_role_policy` has TWO `StringEquals` conditions:
     - `token.actions.githubusercontent.com:aud = "sts.amazonaws.com"`
     - `token.actions.githubusercontent.com:sub = "repo:${var.github_repository}:environment:${var.github_deploy_environment}"`
   - This is **environment-scoped**, not ref-scoped. Deploys must declare `environment: production` (see `.github/workflows/deploy.yml`) to assume the role. If the `:sub` condition gets weakened to a wildcard (`StringLike` with `*`) or removed entirely, that's the canonical "any workflow in the repo can assume the deploy role" footgun — **Critical**.
   - `aws_iam_openid_connect_provider.github` has `client_id_list = ["sts.amazonaws.com"]` and a non-empty `thumbprint_list`. The provider is one-per-account; if another project in the same AWS account already created it, this file would need to import it rather than create it — flag as a Critical if you see a duplicate `apply` error referenced anywhere in `web/README.md`.
   - `var.github_repository` matches the real GitHub repo (e.g. `Absence0760/project-disag`). A stale default — like `jaredhoward/project-disag` — means the trust policy doesn't match any real workflow. **Critical** if it doesn't match the `git remote -v` URL.
   - The attached policy in `aws_iam_policy.github_deploy` scopes every action to a specific ARN:
     - `lambda:UpdateFunctionCode` + `lambda:GetFunction*` → `aws_lambda_function.api.arn`
     - `s3:PutObject/DeleteObject/GetObject` → `aws_s3_bucket.frontend.arn/*` only
     - `s3:ListBucket` → `aws_s3_bucket.frontend.arn` only
     - `cloudfront:CreateInvalidation` + `Get*` → `aws_cloudfront_distribution.site.arn`
   - **No `iam:*`, `sts:AssumeRole`, `secretsmanager:*`, `kms:*` on the deploy role.** Any of those → Critical.

3. **S3 buckets (`s3.tf`).** Three buckets, all configured the same way:
   - `aws_s3_bucket_public_access_block` with all four flags `true` (inputs, outputs, frontend).
   - `aws_s3_bucket_server_side_encryption_configuration` with AES256 + `bucket_key_enabled = true`.
   - `aws_s3_bucket_versioning` enabled on `outputs` (so a Lambda bug can't overwrite a user's report silently). Inputs + frontend are throwaway; versioning optional.
   - `aws_s3_bucket_lifecycle_configuration`:
     - `inputs`: 7-day expiration + `abort_incomplete_multipart_upload` (presigned PUTs that never complete shouldn't accumulate).
     - `outputs`: 90-day non-current version expiration (cost guardrail).
     - `frontend`: lifecycle optional.
   - `aws_s3_bucket_cors_configuration` only on `inputs` — needed for the browser PUT to the presigned URL.
   - `aws_s3_bucket_policy` on `frontend` grants `Principal: { Service = "cloudfront.amazonaws.com" }` with a `StringEquals` condition on `AWS:SourceArn = aws_cloudfront_distribution.site.arn`. **Not `Principal: "*"`** — Critical if it ever is.
   - No legacy `aws_s3_bucket_acl` (modern API forbids ACLs).
   - `force_destroy = var.environment != "prod"` so a `pnpm tf:destroy` actually works in dev but won't blow away a prod bucket on a misclick.

4. **CloudFront distribution (`cloudfront.tf`).**
   - `viewer_protocol_policy = "redirect-to-https"` on default behavior; `"https-only"` on the `/api/*` behavior (the API origin doesn't speak HTTP).
   - The S3 origin uses `origin_access_control_id` (OAC), not the legacy `origin_access_identity` (OAI). OAC + sigv4 only.
   - `aws_cloudfront_origin_access_control.frontend.signing_behavior = "always"` and `signing_protocol = "sigv4"`.
   - `price_class = "PriceClass_100"` (NA + EU only). Bumping to `PriceClass_All` triples the per-request cost — flag if changed without a documented reason.
   - SPA fallback: `custom_error_response` rewrites 403 + 404 → 200 + `/index.html`. **Don't break this** — `/run`, `/history`, and any future client-side route depend on it.
   - The `/api/*` cache behavior uses the AWS-managed `CachingDisabled` policy + `AllViewerExceptHostHeader` origin-request policy. Wrong cache policy here can serve stale API responses to other users — Critical if `CachingDisabled` gets swapped for `CachingOptimized`.
   - No `web_acl_id` is set today; the project is small enough that WAF is over-engineering. Surface as a **Low / Note** if the audit is in a heightened-attention period (large traffic spike, public launch).
   - `aliases` empty (CloudFront default domain only). If a custom domain shows up here, the corresponding ACM cert ARN must come via `data "sops_file"` — Medium if it's in plaintext tfvars.

5. **Lambda function (`lambda.tf`).**
   - `runtime = "python3.14"` — must match the runtime the Lambda image actually offers. If AWS deprecates 3.14, the deploy fails silently until the user notices.
   - `architectures = ["arm64"]` (Graviton — ~20% cheaper for the same Python image).
   - `memory_size` ≤ 10240 (Lambda hard cap); default is 4096 in `variables.tf`. Bumping above the var should be documented.
   - `timeout` ≤ 900 (Lambda hard cap); default 300 in `variables.tf`. Past 5 min, the README suggests switching to Fargate.
   - The execution role attaches only `service-role/AWSLambdaBasicExecutionRole` plus the per-bucket policy in `iam.tf`. Anything else → flag.
   - `aws_cloudwatch_log_group.lambda` has `retention_in_days = 30`. **Infinite retention is the cost trap.** Flag if missing.
   - `source_code_hash` reads from `data.local_file.lambda_zip.content_base64sha256` so a code change actually replaces the function. The `null_resource.lambda_build` triggers the zip rebuild on any disag/exceed/handler change — flag if the trigger set drops one of those paths.

6. **API Gateway HTTP API (`apigw.tf`).**
   - HTTP API v2 (not REST API — cheaper, no edge cases we need).
   - `cors_configuration.allow_origins` matches what the frontend actually uses. The default is `var.allowed_origin = "*"`, which is fine for dev but should be narrowed to the CloudFront URL in prod. If `allowed_origin = "*"` is still set when `var.environment == "prod"`, **High**.
   - `route_settings` (the throttling block) is currently absent. Lambda has implicit concurrency; API Gateway throttling is the global cap. If the tool sees real traffic, add `throttling_burst_limit` + `throttling_rate_limit` per `$default`. Surface as Low today.
   - Access log group `aws_cloudwatch_log_group.apigw` has `retention_in_days = 30`. Same cost trap as Lambda.
   - The `$default` catch-all route forwards to the Lambda; the handler does its own routing on `rawPath + method`. Don't replace this with a per-route mapping unless the handler is also restructured.

7. **IAM (`iam.tf`).**
   - The Lambda execution role uses `data.aws_iam_policy_document.lambda_assume` with a single principal: `Service = "lambda.amazonaws.com"`. Anything more permissive → Critical.
   - `aws_iam_policy.lambda_s3` scopes:
     - `InputsRead`: `s3:GetObject` on `${aws_s3_bucket.inputs.arn}/*` only
     - `OutputsReadWrite`: `s3:GetObject/PutObject/DeleteObject` on `${aws_s3_bucket.outputs.arn}/*` only
     - `OutputsList`: `s3:ListBucket` on `${aws_s3_bucket.outputs.arn}` only
   - **No `s3:*` wildcards, no cross-bucket grants, no other accounts as principals.**

8. **sops alignment (`.sops.yaml` + `web/infra/secrets.enc.yaml.example`).**
   - `.sops.yaml` `creation_rules` includes a regex covering `web/infra/.*\.enc\.yaml$` and a real KMS ARN (not the `REPLACE_ME` placeholder). **Medium** if placeholder.
   - `encrypted_regex` covers `^(data|stringData|password|secret|token|key|.*_key|.*_secret)$` — adding a new sensitive key name not matching the regex means it leaks in plaintext inside the file (the YAML envelope is encrypted at the named-leaf level). **High** if a new key shape that should be secret isn't covered.
   - The Terraform `sops_file` data source is currently commented in `versions.tf` notes; uncommenting requires the secret to actually exist. If a `data.sops_file` reference shows up referencing a path that's not present, `terraform plan` fails — Medium.
   - `web/infra/secrets.enc.yaml` (the encrypted form) should be allow-listed in `web/infra/.gitignore` while `web/infra/secrets.yaml` and `.json` (plaintext siblings) stay ignored. Verify with `git check-ignore`.

9. **Tagging (`providers.tf` default_tags).**
   - The AWS provider sets `default_tags = { project, environment, managed-by = "terraform", component = "web" }`. Cost-attribution and audit-trail depend on these. Flag if the provider block drops one.

10. **Drift hygiene.** Read every `lifecycle { ignore_changes = [...] }` block — list each one. Confirm:
    - It's there because CI legitimately mutates the field (e.g. Lambda `filename` / `source_code_hash` after `update-function-code`).
    - The list is minimal. Anything broader silently allows infrastructure to drift away from git.

11. **Provider + Terraform pinning (`versions.tf`).**
    - `required_version = ">= 1.15.0"` (or current).
    - `required_providers` for `aws`, `random`, `sops` — all using `~> X.Y` ranges (allows patches) or exact pins. Loose `~> X` (major-only) is too broad — Medium.
    - `.terraform.lock.hcl` is committed.

## Report

- **Critical** — OIDC `:sub` wildcarded or `var.github_repository` wrong, IAM policy with `*` resources or `iam:*`/`sts:*` actions, S3 bucket policy with `Principal: "*"`, public-access-block disabled, `/api/*` cache policy not `CachingDisabled`.
- **High** — bucket versioning off on `outputs`, missing PAB on any bucket, `allowed_origin = "*"` in prod, new sensitive key shape not covered by `.sops.yaml` `encrypted_regex`, log retention infinite on Lambda or API Gateway.
- **Medium** — `.sops.yaml` still has `REPLACE_ME` ARN, plaintext sensitive value in `terraform.tfvars`, missing `lifecycle.ignore_changes` on a CI-mutated field, `PriceClass_All` without justification, provider pins too loose (`~> X` alone), missing `default_tags` entry.
- **Low** — no WAF (project is small; surface but don't block), no API Gateway throttling configured, suggesting `use_lockfile = true` over legacy DynamoDB locking, undocumented `lifecycle` choice.

For each finding: file:line + the concrete change to make. Don't apply fixes without explicit confirmation.

## Useful starting points

- `web/README.md § Provisioning infrastructure` — the apply-order walkthrough
- `web/infra/oidc.tf` — highest blast-radius file
- `web/infra/cloudfront.tf` + `web/infra/s3.tf` — the user-facing surface
- `.sops.yaml` — KMS recipient + creation rules

## Delegate to

`general-purpose` agent with this file as the prompt body. The audit reads ~10 small `.tf` files plus a couple of YAML configs — well within one agent's reading window.

Read-only. Findings only. Don't run `terraform plan` or `terraform apply` — those reach AWS.
