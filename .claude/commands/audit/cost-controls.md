---
description: Verify spend safeguards across AWS — Lambda, CloudFront, API Gateway, S3 — so no single failure produces a runaway bill
---

Audit every layer that bounds runaway spend on AWS. The realistic cost-vector accidents for this project: an unauthenticated burst against the Lambda from a botnet, a CloudFront egress flood, an S3 lifecycle policy that lets old runs accumulate forever, a Lambda log group with infinite retention quietly bleeding $0.50/GB/month.

## Goal

The whole stack is small and the legitimate traffic is low. A finding is anything that lets the bill exceed normal baseline by an order of magnitude before any alarm fires.

## What to check

### 1. WAF rate limit on CloudFront

`web/infra/waf.tf` should declare an `aws_wafv2_web_acl` attached via `cloudfront.tf`'s `web_acl_id`. The ACL's `RateLimitPerIP` rule is the cheap, first-line cap on a flood-source IP. Verify:

- The rule exists and the limit is the value of `var.waf_rate_limit_per_ip` (AWS minimum 100, evaluated over a rolling 5-minute window).
- The ACL is actually attached to the distribution (`cloudfront.tf` references `aws_wafv2_web_acl.site.arn`). A WAF that exists but isn't attached is the most common misconfig.
- `default_action = allow` (the rate rule plus the attached `AWSManagedRulesCommonRuleSet` managed rule group do the gating). Verify the managed rule group is still attached — flag if it's ever removed without a documented decision.

WAF costs ~$7/month ($5 base + $1 × 2 rules); if the project ever decides that's too much, the rule is also documented as "comment out and delete this file" in the file's header. Surface as a Low / Note if a future audit sees the WAF (or its managed rule set) removed without a documented decision.

### 2. API Gateway throttling

`web/infra/apigw.tf` — verify the `$default` route has `throttling_burst_limit` and `throttling_rate_limit` set, or that the stage-level defaults are explicitly bounded. API Gateway is the cross-instance cap; the WAF in front handles per-IP, but API Gateway is what saves you if WAF is misconfigured.

- Limits set: green.
- Unbounded throttling on `$default`: flag as High.

### 3. AWS Budget + CloudWatch alarms (`web/infra/alarms.tf`)

The cost-defence file is `web/infra/alarms.tf` (single file carrying SNS topic + Budget + per-resource CloudWatch alarms). Verify:

- **`aws_budgets_budget`** declared with a monthly limit (currently `var.budget_monthly_usd`, default $50). Confirm the limit is in the low-tens-of-dollars range for a hobby-scale deployment — anything materially higher should have a documented reason.
- **Three notifications minimum**: `ACTUAL > 50 %`, `ACTUAL > 100 %`, and a `FORECASTED` notification at ≤ 100 % (currently `> 90 %` — stricter thresholds pass). Forecasted is the only one that catches a runaway *during* the month — actual lags by up to 24h. Missing forecasted → High.
- **`aws_sns_topic` + `aws_sns_topic_subscription`** wired to `var.budget_alert_email`. The subscription is `count = 0` when the var is empty (alarms still fire visibly but no one gets paged) — that's tolerable in dev, flag as Medium if it ships to prod without a real email.
- **Per-resource CloudWatch alarms** (Lambda errors / throttles / duration, CloudFront 5xx rate, API Gateway 5xx rate) all publish to the same SNS topic. Missing any of these is Medium — they catch a problem before the budget alarm does.

### 4. CloudWatch log retention

Every `aws_cloudwatch_log_group` in `web/infra/*.tf` must have `retention_in_days` set to a finite value (≤ 90 is reasonable; default = `null` = forever = $0.50/GB/month forever). Check:

- `/aws/lambda/<function-name>` (declared in `lambda.tf`).
- API Gateway access log group (declared in `apigw.tf`).
- Any WAF logging destination (if `aws_wafv2_web_acl_logging_configuration` is wired in `waf.tf`).

Missing retention on any of these → High.

### 5. CloudFront cost guardrails

- `price_class = "PriceClass_100"` or `_200` (not `_All`). PriceClass_All bills from every edge location regardless of where users actually live. Flag a bump to `_All` without a documented reason.
- `viewer_protocol_policy = "redirect-to-https"` — HTTP traffic still costs egress; redirecting funnels it to the encrypted path which is what the cache key expects.
- S3 lifecycle on the `frontend` bucket expiring non-current versions — if versioning is enabled and lifecycle isn't, version count grows forever at $0.023/GB/month.

### 6. Lambda compute ceiling

`web/infra/lambda.tf`:

- `memory_size` ≤ 10240 (Lambda hard cap); default 3008 per `variables.tf` (the max a fresh AWS account can allocate without a Service Quotas increase). The handler is sized this way because Method 5 (`PATCH_EXCEED`) on a large monthly file gets CPU-bound; flag a memory increase above the var without a documented reason.
- `timeout` ≤ 900 (Lambda hard cap); default 29 per `variables.tf`, matching API Gateway HTTP API's 30 s integration cap (`apigw.tf`) — anything longer keeps billing after the caller has already seen a 504. Past ~29 s, `web/README.md` says move off the synchronous API path (e.g. Fargate).
- `reserved_concurrent_executions` — if unset, the function shares the account-wide concurrency pool (1000 by default). A runaway loop on a ~3 GB function can still clear $1k+/day at full concurrency. Setting `reserved_concurrent_executions` to a low number (e.g. 20) bounds the worst case. Flag as Medium if unset on prod.

### 7. S3 lifecycle on `inputs` and `outputs` buckets

`web/infra/s3.tf`:

- `inputs/` bucket: lifecycle should expire objects after 7 days + `abort_incomplete_multipart_upload`. Presigned PUT URLs that never complete shouldn't accumulate.
- `outputs/` bucket: lifecycle should bound both current and non-current versions, with expiry at most 90 days for each (currently 30-day current + 7-day noncurrent per `s3.tf` — stricter is fine). Versioning enabled on this bucket guards against a Lambda bug silently overwriting a user's report; lifecycle keeps the cost bounded.
- `frontend/` bucket: lifecycle on non-current versions; versioning optional.

Missing lifecycle on `inputs/` → High (presigned-POST flood with `abort_incomplete_multipart_upload` disabled is a real DoS vector). Missing lifecycle on `outputs/` non-current → Medium.

### 8. Denial-of-wallet via the public Lambda routes

The public Lambda routes (`POST /upload`, `POST /disag`, `POST /exceed`, `GET /runs`, `GET /runs/{run_id}`) take no auth. The defences are:

- **WAF rate limit** (check 1) → caps per-IP per 5-minute window.
- **API Gateway throttling** (check 2) → caps cross-instance globally.
- **`MAX_UPLOAD_BYTES`** in `handler.py` → caps per-upload size, enforced via the presigned-POST condition.
- **`reserved_concurrent_executions`** (check 6) → caps the worst-case Lambda spend during a sustained attack.

A finding is any of those four being unbounded, mis-set, or only-bounded-in-one-place. Two layers of defence is the bar.

### 9. Documentation matches reality

This audit's value depends on the docs being honest:

- `web/README.md`'s "Compute notes" section quotes Lambda sizing — confirm it matches the current `lambda.tf` + `variables.tf`.
- `web/infra/alarms.tf` file-top comment claims it's the cost-runaway gate — confirm the resources it declares are still wired.

## Report

- **Critical** — `aws_budgets_budget` missing entirely, WAF not attached to CloudFront, API Gateway throttling unbounded on `$default`, `MAX_UPLOAD_BYTES` unbounded.
- **High** — log retention infinite anywhere, AWS budget exists but no `FORECASTED` notification, missing lifecycle on `inputs/` bucket, CloudFront `PriceClass_All` without justification.
- **Medium** — `reserved_concurrent_executions` unset, missing lifecycle on `outputs/` non-current versions, `budget_alert_email` empty in prod, missing per-resource CloudWatch alarm, doc drift between `web/README.md` and `lambda.tf` sizing.
- **Low** — WAF or its managed rule set removed without a documented decision, no documented `lifecycle` choice, alarm exists but the SNS subscription is unconfirmed.

For each finding: file:line + the concrete change. Don't apply fixes without explicit confirmation.

## Useful starting points

- `web/infra/alarms.tf` — Budget + SNS + per-resource CloudWatch alarms (single file)
- `web/infra/waf.tf` — per-IP rate limit on CloudFront
- `web/infra/apigw.tf` — request-rate cap + access log retention
- `web/infra/lambda.tf` — memory / timeout / reserved-concurrency / log retention
- `web/infra/s3.tf` — bucket lifecycle policies
- `web/infra/cloudfront.tf` — `price_class` + WAF attachment
- `web/backend/handler.py` — `MAX_UPLOAD_BYTES`, `UPLOAD_TTL`, `DOWNLOAD_TTL`
- `web/README.md § Compute notes` — claimed sizing baseline

## Delegate to

`general-purpose` agent with this file as the prompt body. Cross-cuts code + IaC + docs, so it doesn't fit one of the specialised auditors.

Read-only. Findings only. The audit must NOT mutate IaC, run `terraform plan` against the real account, or load-test the backend — a load test against `POST /upload` is itself a small spend event.
