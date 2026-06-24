terraform {
  required_version = "~> 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.45"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    # Prod secrets live ENCRYPTED in the private ../infra-secrets repo
    # (this repo is public), under disag/prod.sops.yaml, keyed by
    # alias/disag-sops. Edit them from THAT repo: `sops disag/prod.sops.yaml`.
    # When the first real secret lands, read it in Terraform via:
    #   data "sops_file" "secrets" {
    #     source_file = "${path.module}/../../../infra-secrets/disag/prod.sops.yaml"
    #   }
    #   ... = data.sops_file.secrets.data["allowed_origin_prod"]
    # sops decrypts in-memory at plan/apply using the active AWS profile's
    # KMS access. Nothing's encrypted today (all current values are public),
    # so the data source is intentionally omitted — uncomment when needed.
    sops = {
      source  = "carlpett/sops"
      version = "~> 1.2"
    }
  }

  # Remote state in the bootstrap-created S3 bucket. Locking via S3
  # conditional writes (Terraform 1.10+'s `use_lockfile`) — no DynamoDB
  # needed. Bucket was created by ~/repos/templates/infra/bootstrap/2-baseline.
  #
  # The bucket name is partial-config: passed via `terraform init
  # -backend-config=backend.config` (file is gitignored — see
  # backend.config.example for the shape). This keeps the AWS account
  # ID out of source control so the repo can be made public without
  # broadcasting it.
  backend "s3" {
    key          = "web/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
