variable "project" {
  type        = string
  description = "Short name used as a prefix for all named resources (Lambda function, S3 buckets, CloudFront distribution, etc.)."
  default     = "disag-md"
}

variable "bootstrap_slug" {
  type        = string
  description = <<EOT
Slug used by the cross-project AWS account bootstrap
(~/repos/templates/scripts/new-project-account.sh). Distinct from
`project` — the bootstrap slug names the AWS account itself, the
deploy IAM role (`<slug>-deploy`), the KMS alias (`alias/<slug>-sops`),
and the delegated subdomain (`<slug>.<parent_zone_root>`). This repo
looks up bootstrap-created resources by this slug, then names its
*own* resources with `project` for brand consistency (`disag-md-dev-*`).
EOT
  default     = "disag"
}

variable "parent_domain" {
  type        = string
  description = <<EOT
Delegated Route 53 hosted zone that this project owns (e.g.
"project.example.com"). The bootstrap baseline created the zone;
this repo references it via data source. Prod CloudFront serves at
this fqdn; non-prod environments serve at "<env>.<parent_domain>".

Required — no default, so a fresh clone can't accidentally apply
against the wrong domain. Set in your local terraform.tfvars
(gitignored).
EOT

  validation {
    condition     = can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.parent_domain))
    error_message = "parent_domain must be a valid lowercase domain name (e.g. project.example.com)."
  }
}

variable "environment" {
  type        = string
  description = <<EOT
Environment suffix (dev / staging / prod). Drives resource naming
(`disag-md-<env>-*`) and the resolved fqdn (prod → <parent_domain>,
others → <env>.<parent_domain>).

Default is "prod" so the single-environment state in this repo lands
at the canonical apex of the delegated zone. To stand up a parallel
dev environment, create a new Terraform workspace and override:
  terraform workspace new dev
  terraform apply -var environment=dev -var allowed_origin='*'
EOT
  default     = "prod"
}

variable "region" {
  type        = string
  description = "AWS region for all resources."
  default     = "us-east-1"
}

variable "lambda_memory_mb" {
  type        = number
  description = <<EOT
Lambda memory size. CPU scales linearly with memory in Lambda:
  ~1769 MB  = 1 vCPU
  ~3009 MB  = 1.7 vCPU
  ~5308 MB  = 3 vCPU
  ~10240 MB = ~6 vCPU

Default is 3008 — the maximum Lambda memory a freshly-provisioned AWS
account is allowed to allocate without a Service Quotas increase. Once
the quota is raised (AWS Console → Service Quotas → AWS Lambda → search
"Memory" → request increase, usually approved within minutes), bump
this back up to 4096+ for the extra CPU headroom on compute-bound
disag/exceed runs.
EOT
  default     = 3008
}

variable "lambda_timeout_seconds" {
  type        = number
  description = <<EOT
Per-invocation cap. API Gateway HTTP API hard-limits integration
responses to 30s, so anything beyond ~29s is pure compute waste — the
caller will see a 504 from API GW while the Lambda keeps billing.
EOT
  default     = 29
}

variable "lambda_reserved_concurrency" {
  type        = number
  description = <<EOT
Reserved concurrent executions for the API Lambda. A hard ceiling that
prevents one client's burst from exhausting the account-level Lambda
concurrency quota and starving the rest of the account, and caps the
worst-case compute bill from an abuser.

Default is -1 (no reservation, uses the shared unreserved pool) because
newly-provisioned AWS accounts cap Lambda concurrency at 10 total, and
AWS requires unreserved concurrency >= 10 at all times — so any positive
reservation on a brand-new account fails apply with
InvalidParameterValueException. Once the account-level "Concurrent
executions" quota is raised via Service Quotas (default 1000 for
established accounts), set this to ~10–50 to add a real ceiling.
EOT
  default     = -1
}

variable "allowed_origin" {
  type        = string
  description = <<EOT
CORS allow-origin header — must be a concrete https:// URL in prod.
Set in terraform.tfvars to "https://<your-parent-domain>" for prod;
in dev/staging "*" is allowed (validation only blocks it for prod).
EOT

  # No default — prod refuses to apply without an explicit value,
  # forcing every contributor to think about it. For dev/staging
  # set "*" in your tfvars.
  validation {
    condition     = !(var.environment == "prod" && var.allowed_origin == "*")
    error_message = "allowed_origin must be narrowed when environment = \"prod\". Set it to your CloudFront URL (e.g. https://d12345.cloudfront.net) or the custom domain."
  }
}

variable "upload_ttl_seconds" {
  type        = number
  description = "Presigned POST URL TTL for uploads (kept short — captured-URL replay is the main risk)."
  default     = 300
}

variable "download_ttl_seconds" {
  type        = number
  description = "Presigned GET URL TTL for downloads."
  default     = 600
}

variable "max_upload_bytes" {
  type        = number
  description = "Per-file upload size cap enforced via the presigned POST policy."
  default     = 10485760 # 10 MiB
}

variable "budget_monthly_usd" {
  type        = number
  description = <<EOT
Monthly AWS spend ceiling that triggers an alert (0 disables the budget).

Default is 0 because newly-org-created member accounts can't create
AWS Budgets until the account owner enables "IAM user and role access
to billing information" — a root-only operation that the bootstrap
can't perform. Until that's done (Account → Billing settings → toggle
on), any budget create attempt fails with AccessDeniedException +
"ask the payer account to enable budgets first." Once the toggle is
on, bump this back up to ~50 to enable the tripwire.
EOT
  default     = 0
}

variable "budget_alert_email" {
  type        = string
  description = "Email subscriber for budget + Lambda alarms. Empty = no SNS subscription created (alarms still fire, you just won't be paged)."
  default     = ""
}

variable "waf_rate_limit_per_ip" {
  type        = number
  description = "5-minute rolling request count per source IP that triggers a 403 from CloudFront. AWS recommends 100–2000 for typical APIs."
  default     = 500
}

variable "frontend_build_dir" {
  type        = string
  description = "Path to SvelteKit's static build output (relative to this dir)."
  default     = "../frontend/build"
}

# Note: github_repository and github_deploy_environment used to live here.
# They're now set at bootstrap time (~/repos/templates/infra/bootstrap/projects/disag.tfvars)
# and baked into the deploy role's trust policy by the cross-project
# bootstrap. This repo only needs to look the role up by name and
# attach permissions to it.
