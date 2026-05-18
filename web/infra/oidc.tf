# GitHub Actions → AWS via OIDC.
#
# The OIDC provider and the deploy role are created by the cross-project
# bootstrap (~/repos/templates/scripts/new-project-account.sh) in the
# project's AWS account. The role's trust policy is already scoped to
#   repo:<github_repo>:environment:<github_environment>
# at bootstrap time (values come from the per-project tfvars on the
# templates side, not from this repo's variables).
#
# This file only adds the *permissions* the deploy workflow needs:
#   - lambda:UpdateFunctionCode + GetFunction on the API function ARN
#   - s3:PutObject/DeleteObject/ListBucket on the frontend bucket only
#   - cloudfront:CreateInvalidation/GetDistribution on the site
#     distribution ARN only
#
# Security note: the OIDC trust policy alone is necessary but not
# sufficient. Configure required reviewers on the GitHub Actions
# environment (Settings → Environments → production) — otherwise any
# maintainer who pushes a workflow that requests `environment: production`
# can assume the role.

data "aws_iam_role" "github_deploy" {
  name = "${var.project}-deploy"
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
  role       = data.aws_iam_role.github_deploy.name
  policy_arn = aws_iam_policy.github_deploy.arn
}
