variable "project" {
  type        = string
  description = "Short name used as a prefix for all named resources."
  default     = "disag-md"
}

variable "environment" {
  type        = string
  description = "Environment suffix (dev / staging / prod)."
  default     = "dev"
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
Default sized for compute-bound disag/exceed runs without overpaying
on idle.
EOT
  default     = 4096
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Per-invocation cap. Hard ceiling 900 (15 min)."
  default     = 300
}

variable "allowed_origin" {
  type        = string
  description = "CORS allow-origin header — must be a concrete https:// URL."
  default     = "*"

  # `*` is convenient for the very first `terraform apply` (before
  # the CloudFront URL is known) but a real leak in any longer-lived
  # environment. Apply fails fast in prod so wildcard never lands
  # there; dev/staging keep the escape hatch.
  validation {
    condition     = !(var.environment == "prod" && var.allowed_origin == "*")
    error_message = "allowed_origin must be narrowed when environment = \"prod\". Set it to your CloudFront URL (e.g. https://d12345.cloudfront.net)."
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
  description = "Monthly AWS spend ceiling that triggers an alert (0 disables the budget)."
  default     = 50
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
