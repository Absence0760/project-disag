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
    # sops decrypts web/infra/secrets.enc.yaml at plan/apply time using
    # the active AWS profile's KMS access. Edit secrets via:
    #   sops web/infra/secrets.enc.yaml
    # Read in Terraform via:
    #   data "sops_file" "secrets" { source_file = "secrets.enc.yaml" }
    #   ... = data.sops_file.secrets.data["allowed_origin_prod"]
    # Nothing's encrypted today (all current values are public), so
    # the data source is intentionally omitted — uncomment when the
    # first real secret lands.
    sops = {
      source  = "carlpett/sops"
      version = "~> 1.2"
    }
  }

  # Remote state in the bootstrap-created S3 bucket. Locking via S3
  # conditional writes (Terraform 1.10+'s `use_lockfile`) — no DynamoDB
  # needed. Bucket was created by ~/repos/templates/infra/bootstrap/2-baseline.
  backend "s3" {
    bucket       = "disag-tfstate-406460434695"
    key          = "web/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
