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
  description = "CORS allow-origin header — narrow to the CloudFront URL in prod."
  default     = "*"
}

variable "presign_ttl_seconds" {
  type        = number
  description = "How long pre-signed PUT/GET URLs stay valid."
  default     = 3600
}

variable "frontend_build_dir" {
  type        = string
  description = "Path to SvelteKit's static build output (relative to this dir)."
  default     = "../frontend/build"
}

variable "github_repository" {
  type        = string
  description = <<EOT
GitHub repo in `owner/name` form. Used to scope the OIDC trust policy
so only this repo's release-published workflows can assume the deploy
role. Override via terraform.tfvars when forking.
EOT
  default     = "jaredhoward/project-disag"
}

variable "github_deploy_environment" {
  type        = string
  description = <<EOT
GitHub Actions environment name allowed to assume the deploy role.
Restricting on `environment:<name>` (rather than the ref) means the
GitHub-side environment protection rules — required reviewers,
branch restrictions — gate the AWS credentials.
EOT
  default     = "production"
}
