# Remote-state bootstrap.
#
# Terraform's S3 backend can't manage its own state bucket — chicken
# and egg. The standard fix: first apply creates the bucket here with
# *local* state, then `terraform init -migrate-state` moves state into
# the bucket. After that this file is mostly cosmetic — the bucket
# exists, Terraform manages it, and the backend block in versions.tf
# uses it.
#
# Steps for a fresh repo (one-time):
#   1. `cd web/infra && terraform init`         (local state)
#   2. `terraform apply -target=aws_s3_bucket.tfstate`
#                                                (creates the bucket)
#   3. Uncomment the `backend "s3"` block in versions.tf and replace
#      <account-id> in the `bucket =` line below + in versions.tf.
#   4. `terraform init -migrate-state`           (moves to S3)
#   5. `terraform apply`                          (everything else)
#
# Steps for an already-configured stack:
#   - The bucket name in versions.tf must match `aws_s3_bucket.tfstate.id`.
#   - State locking uses S3 conditional writes (Terraform 1.10+'s
#     `use_lockfile = true`); no DynamoDB table needed.

resource "aws_s3_bucket" "tfstate" {
  bucket = "${local.name_prefix}-tfstate-${local.account_id}"

  # Even non-prod loses state if this is deleted accidentally.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

# State files churn rarely but accumulate forever. Keep noncurrent
# versions for 30 days as a safety net then drop them.
resource "aws_s3_bucket_lifecycle_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

output "tfstate_bucket" {
  description = "Name of the Terraform state bucket; copy into versions.tf's backend block when migrating."
  value       = aws_s3_bucket.tfstate.id
}
