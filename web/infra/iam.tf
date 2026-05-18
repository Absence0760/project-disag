data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_s3" {
  # Inputs bucket: read uploaded objects + presign PUT.
  statement {
    sid     = "InputsRead"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.inputs.arn}/*",
    ]
  }

  # Outputs bucket: read + write run artefacts, list for /runs.
  # No s3:DeleteObject — the handler never deletes outputs; lifecycle
  # rules handle expiry. Granting Delete would let a compromised
  # handler wipe every run.
  statement {
    sid = "OutputsReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.outputs.arn}/*"]
  }

  statement {
    sid       = "OutputsList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.outputs.arn]
  }
}

resource "aws_iam_policy" "lambda_s3" {
  name   = "${local.name_prefix}-lambda-s3"
  policy = data.aws_iam_policy_document.lambda_s3.json
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_s3.arn
}
