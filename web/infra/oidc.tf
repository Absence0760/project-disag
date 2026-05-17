# GitHub Actions → AWS via OIDC. No long-lived access keys; the
# deploy workflow exchanges a short-lived OIDC token for the role
# below using aws-actions/configure-aws-credentials.
#
# Trust policy is scoped to:
#   - this GitHub repo (var.github_repository)
#   - the GitHub Actions environment `production` — environment
#     protection rules (required reviewers, branch restrictions) are
#     what actually gate the credentials. A push to a long-running
#     fork branch can't assume the role without going through the
#     environment.
#
# Permissions policy is least-priv:
#   - lambda:UpdateFunctionCode + GetFunction on the API function ARN
#   - s3:PutObject/DeleteObject/ListBucket on the frontend bucket only
#   - cloudfront:CreateInvalidation/GetDistribution on the site
#     distribution ARN only

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    # Well-known GitHub OIDC thumbprints. AWS validates the cert
    # chain against its own CA bundle so these are largely vestigial
    # in 2026, but keeping them avoids surprise behaviour changes.
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:environment:${var.github_deploy_environment}",
      ]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${local.name_prefix}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
  description        = "Assumed by GitHub Actions on release-published events to deploy the web app."
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid = "LambdaCodeUpdate"
    actions = [
      "lambda:UpdateFunctionCode",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
    ]
    resources = [aws_lambda_function.api.arn]
  }

  statement {
    sid = "FrontendSync"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:GetObject",
    ]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
  }

  statement {
    sid       = "FrontendList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.frontend.arn]
  }

  statement {
    sid = "CloudFrontInvalidate"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetDistribution",
      "cloudfront:GetInvalidation",
    ]
    resources = [aws_cloudfront_distribution.site.arn]
  }
}

resource "aws_iam_policy" "github_deploy" {
  name   = "${local.name_prefix}-github-deploy"
  policy = data.aws_iam_policy_document.github_deploy.json
}

resource "aws_iam_role_policy_attachment" "github_deploy" {
  role       = aws_iam_role.github_deploy.name
  policy_arn = aws_iam_policy.github_deploy.arn
}
