locals {
  name_prefix = "${var.project}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
}

# 4-char suffix → keeps bucket names stable across `terraform apply`s
# but unique across accounts so the global S3 namespace doesn't bite.
resource "random_id" "bucket_suffix" {
  byte_length = 2
}

resource "aws_s3_bucket" "inputs" {
  bucket        = "${local.name_prefix}-inputs-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket" "outputs" {
  bucket        = "${local.name_prefix}-outputs-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name_prefix}-frontend-${random_id.bucket_suffix.hex}"
  force_destroy = var.environment != "prod"
}

# ── Block public access on every bucket. Static site is served via
# CloudFront with an Origin Access Control — S3 itself never goes
# public.
resource "aws_s3_bucket_public_access_block" "inputs" {
  bucket                  = aws_s3_bucket.inputs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "outputs" {
  bucket                  = aws_s3_bucket.outputs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "inputs" {
  bucket = aws_s3_bucket.inputs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "outputs" {
  bucket = aws_s3_bucket.outputs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

# Versioning on the outputs bucket so a Lambda bug can't overwrite a
# user's earlier report silently. Inputs are throwaway — once a run is
# scheduled the input is no longer load-bearing.
resource "aws_s3_bucket_versioning" "outputs" {
  bucket = aws_s3_bucket.outputs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle: clear inputs after a week, expire old output versions
# after 90 days so the bill doesn't grow forever on tier-1 storage.
resource "aws_s3_bucket_lifecycle_configuration" "inputs" {
  bucket = aws_s3_bucket.inputs.id
  rule {
    id     = "purge-stale-uploads"
    status = "Enabled"
    filter {}
    expiration { days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "outputs" {
  bucket = aws_s3_bucket.outputs.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

# CORS on the inputs bucket — the browser PUTs upload bytes directly
# to S3 using the pre-signed URL the Lambda returns.
resource "aws_s3_bucket_cors_configuration" "inputs" {
  bucket = aws_s3_bucket.inputs.id
  cors_rule {
    allowed_methods = ["PUT"]
    allowed_origins = [var.allowed_origin]
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
