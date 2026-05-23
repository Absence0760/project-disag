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
  # Inputs bucket: read uploaded objects + the PutObject the Lambda's
  # presigned POST policy delegates to the browser. AWS requires the
  # signing principal (this Lambda role) to hold every action the
  # presigned URL permits, so PutObject HAS to be here even though
  # only the browser ever exercises it.
  #
  # Resource is scoped to `inputs/*` so that even a compromised
  # handler can't read or write outside the intended namespace.
  statement {
    sid = "InputsReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [
      "${aws_s3_bucket.inputs.arn}/inputs/*",
    ]
  }

  # Outputs bucket: read + write run artefacts. Scoped to `runs/*`
  # so a logic bug that lets a caller smuggle a stray key can't
  # land objects outside the runs namespace.
  #
  # No s3:DeleteObject — the handler never deletes outputs; lifecycle
  # rules handle expiry. Granting Delete would let a compromised
  # handler wipe every run.
  statement {
    sid = "OutputsReadWrite"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.outputs.arn}/runs/*"]
  }

  # Listing is scoped via a `s3:prefix` condition so a compromised
  # handler can't enumerate the global runs/ tree (which would leak
  # client_id values via key structure). The handler only ever lists
  # under `runs/<tool>/<client_id>/` prefixes, which all start with
  # `runs/`.
  statement {
    sid       = "OutputsList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.outputs.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["runs/*"]
    }
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
