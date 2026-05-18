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
    # Used by oidc.tf to fetch GitHub's current cert chain and
    # derive the OIDC provider's thumbprint dynamically, so a
    # GitHub-side cert rotation doesn't silently break deploys.
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state. Uncomment AND set `bucket = ` to the name printed
  # by `terraform output tfstate_bucket` (created by bootstrap.tf),
  # then run `terraform init -migrate-state` to push local state into
  # the bucket. `use_lockfile = true` uses S3 conditional writes for
  # locking (TF 1.10+ — no DynamoDB table needed).
  #
  # Order on a fresh account:
  #   1. `terraform init`                       (local state)
  #   2. `terraform apply -target=aws_s3_bucket.tfstate`
  #   3. Uncomment + edit `bucket =` below
  #   4. `terraform init -migrate-state`        (move state to S3)
  #   5. `terraform apply`                       (everything else)
  #
  # backend "s3" {
  #   bucket       = "disag-md-dev-tfstate-<account-id>"
  #   key          = "web/terraform.tfstate"
  #   region       = "us-east-1"
  #   use_lockfile = true
  #   encrypt      = true
  # }
}
