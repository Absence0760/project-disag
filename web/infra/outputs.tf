output "api_endpoint" {
  description = "Direct API Gateway invoke URL (useful for local dev)."
  value       = aws_apigatewayv2_api.http.api_endpoint
  # The URL is the only thing standing between an attacker and a
  # direct hit on the API Gateway that bypasses CloudFront + WAF.
  # The CLOUDFRONT_SHARED_SECRET header check still blocks the
  # request, but redacting the URL from Terraform plan/output keeps
  # casual leakage out of CI logs.
  sensitive = true
}

output "cloudfront_url" {
  description = "Public site URL (frontend + /api/* proxy)."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "inputs_bucket" {
  value = aws_s3_bucket.inputs.id
}

output "outputs_bucket" {
  value = aws_s3_bucket.outputs.id
}

output "frontend_bucket" {
  description = "Sync the SvelteKit build to s3://<this>/."
  value       = aws_s3_bucket.frontend.id
}

output "lambda_function_name" {
  value = aws_lambda_function.api.function_name
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "github_deploy_role_arn" {
  description = <<EOT
ARN of the role GitHub Actions assumes on release-published events.
Push this into a GitHub repo variable (e.g. via `pnpm tf:export-vars`)
so .github/workflows/deploy.yml can pick it up.
EOT
  value       = data.aws_iam_role.github_deploy.arn
}
