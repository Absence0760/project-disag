provider "aws" {
  region = var.region

  # No explicit profile — falls through to the standard AWS credential
  # chain. Locally, run `aws sso login --profile <prof>` then export
  # AWS_PROFILE before `terraform apply`. In CI, OIDC drops short-lived
  # creds via aws-actions/configure-aws-credentials.

  default_tags {
    tags = {
      project     = var.project
      environment = var.environment
      managed-by  = "terraform"
      component   = "web"
    }
  }
}

# CloudFront requires ACM certs in us-east-1. Aliased provider for any
# cert resources added later (custom domain) so the main region can
# move without rewiring.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      project     = var.project
      environment = var.environment
      managed-by  = "terraform"
      component   = "web"
    }
  }
}

data "aws_caller_identity" "current" {}
