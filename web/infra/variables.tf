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
