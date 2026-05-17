provider "aws" {
  region = var.region

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
