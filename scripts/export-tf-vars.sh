#!/usr/bin/env bash
# Push Terraform outputs into GitHub repo variables so the
# release-gated deploy workflow can read them. Idempotent — re-run
# after every `terraform apply` that changes a bucket/function/role
# name.
#
# Requires:
#   - gh CLI authenticated against the repo (gh auth login)
#   - terraform state already exists (run `pnpm tf:apply` first)
#
# Outputs mapped → GitHub variables (non-sensitive identifiers):
#   region (from tfvars)        → AWS_REGION
#   lambda_function_name        → LAMBDA_FUNCTION_NAME
#   frontend_bucket             → FRONTEND_BUCKET
#   cloudfront_distribution_id  → CLOUDFRONT_DISTRIBUTION_ID
#
# Outputs mapped → GitHub secrets (embeds AWS account ID):
#   github_deploy_role_arn      → AWS_DEPLOY_ROLE_ARN

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/web/infra"

if ! command -v gh >/dev/null 2>&1; then
    echo "error: gh CLI not on PATH. Install from https://cli.github.com/" >&2
    exit 1
fi

# `terraform output -json` blows up if the state isn't initialised.
if ! terraform output -json >/tmp/disag-tf-outputs.json 2>/dev/null; then
    echo "error: no terraform state — run \`pnpm tf:apply\` first." >&2
    exit 1
fi

read_output() {
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d['$1']['value'])" </tmp/disag-tf-outputs.json
}

declare -A vars=(
    [LAMBDA_FUNCTION_NAME]="$(read_output lambda_function_name)"
    [FRONTEND_BUCKET]="$(read_output frontend_bucket)"
    [CLOUDFRONT_DISTRIBUTION_ID]="$(read_output cloudfront_distribution_id)"
)

declare -A secrets=(
    [AWS_DEPLOY_ROLE_ARN]="$(read_output github_deploy_role_arn)"
)

# AWS_REGION isn't a terraform output (the provider takes a var, not
# the other way round). Read it from the tfvars file if present, else
# fall back to the variable default.
if [ -f terraform.tfvars ]; then
    region=$(awk -F'=' '/^[[:space:]]*region[[:space:]]*=/ { gsub(/[" ]/, "", $2); print $2; exit }' terraform.tfvars)
fi
vars[AWS_REGION]="${region:-us-east-1}"

for name in "${!vars[@]}"; do
    value="${vars[$name]}"
    if [ -z "$value" ]; then
        echo "skip var $name (empty)"
        continue
    fi
    echo "set var $name = $value"
    gh variable set "$name" --body "$value"
done

for name in "${!secrets[@]}"; do
    value="${secrets[$name]}"
    if [ -z "$value" ]; then
        echo "skip secret $name (empty)"
        continue
    fi
    echo "set secret $name (value hidden)"
    gh secret set "$name" --body "$value"
done

rm -f /tmp/disag-tf-outputs.json
echo
echo "Done. Verify with: gh variable list && gh secret list"
