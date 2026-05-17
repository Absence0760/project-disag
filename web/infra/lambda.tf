# Build the deployment package via the backend's build.sh and let
# Terraform hash the zip so a code change triggers `aws_lambda_function`
# replacement. The null_resource keeps the zip rebuild in the plan
# graph instead of relying on a manual step before `terraform apply`.

resource "null_resource" "lambda_build" {
  triggers = {
    # Rehash on any source change.
    handler    = filemd5("${path.module}/../backend/handler.py")
    builder    = filemd5("${path.module}/../backend/build.sh")
    disag_dir  = sha256(join("", [for f in fileset("${path.module}/../../disag", "**/*.py") : filemd5("${path.module}/../../disag/${f}")]))
    exceed_dir = sha256(join("", [for f in fileset("${path.module}/../../exceed", "**/*.py") : filemd5("${path.module}/../../exceed/${f}")]))
  }

  provisioner "local-exec" {
    command     = "${path.module}/../backend/build.sh"
    working_dir = path.module
  }
}

data "local_file" "lambda_zip" {
  filename   = "${path.module}/../backend/lambda.zip"
  depends_on = [null_resource.lambda_build]
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.lambda.arn
  filename         = data.local_file.lambda_zip.filename
  source_code_hash = data.local_file.lambda_zip.content_base64sha256
  handler          = "handler.lambda_handler"
  runtime          = "python3.14"
  memory_size      = var.lambda_memory_mb
  timeout          = var.lambda_timeout_seconds
  architectures    = ["arm64"] # Graviton — ~20% cheaper per ms, same Python 3.14 image.

  environment {
    variables = {
      INPUTS_BUCKET    = aws_s3_bucket.inputs.id
      OUTPUTS_BUCKET   = aws_s3_bucket.outputs.id
      PRESIGN_TTL      = tostring(var.presign_ttl_seconds)
      ALLOWED_ORIGIN   = var.allowed_origin
      PYTHONUNBUFFERED = "1"
    }
  }

  # CloudWatch logs default to never expire; the log group is created
  # by the first invocation, so claim it here and set retention.
  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 30
}
