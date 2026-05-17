terraform {
  required_version = ">= 1.15.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.45"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Initialise the S3-backed state separately (see web/README.md) and
  # uncomment after `terraform apply` once the bootstrap bucket exists.
  # backend "s3" {
  #   bucket       = "disag-md-tfstate-<account-id>"
  #   key          = "web/terraform.tfstate"
  #   region       = "us-east-1"
  #   use_lockfile = true
  #   encrypt      = true
  # }
}
