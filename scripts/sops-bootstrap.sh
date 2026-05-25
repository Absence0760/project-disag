#!/usr/bin/env bash
# Replace the REPLACE_ME placeholder in .sops.yaml with the active AWS
# account ID, so `sops -e` and `sops -d` against web/infra/*.enc.yaml
# work out of the box.
#
# Re-runnable. If .sops.yaml is already pointing at a real account
# (no REPLACE_ME) the script is a no-op + prints what's there.
#
# Pre-reqs:
#   - aws CLI on PATH
#   - active SSO session (run `pnpm tf:login` first if creds are stale)
#   - sed-with-GNU-extensions (Fedora default; macOS users may need
#     `brew install gnu-sed` or to tweak the in-place flag)
#
# What this does NOT do:
#   - Create the KMS key itself. That's a one-time bootstrap step;
#     see web/README.md § Provisioning infrastructure step 2.
#   - Update encrypted files. If `secrets.enc.yaml` already exists,
#     re-encrypting with the new key is `sops updatekeys
#     web/infra/secrets.enc.yaml`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOPS_FILE="$REPO_ROOT/.sops.yaml"
SOPS_EXAMPLE="$REPO_ROOT/.sops.yaml.example"

if [ ! -f "$SOPS_FILE" ]; then
    if [ -f "$SOPS_EXAMPLE" ]; then
        echo ".sops.yaml not found — seeding from .sops.yaml.example"
        cp "$SOPS_EXAMPLE" "$SOPS_FILE"
    else
        echo "error: neither .sops.yaml nor .sops.yaml.example found at $REPO_ROOT" >&2
        exit 1
    fi
fi

if ! command -v aws >/dev/null 2>&1; then
    echo "error: aws CLI not on PATH" >&2
    exit 1
fi

if ! grep -q 'REPLACE_ME' "$SOPS_FILE"; then
    echo "already configured — no REPLACE_ME placeholders in .sops.yaml" >&2
    grep -E 'kms:' "$SOPS_FILE" >&2 || true
    exit 0
fi

account=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo "error: aws sts get-caller-identity failed — run 'pnpm tf:login' to refresh SSO creds" >&2
    exit 1
}

if [[ ! "$account" =~ ^[0-9]{12}$ ]]; then
    echo "error: unexpected account-id format '$account' — refusing to write to .sops.yaml" >&2
    exit 1
fi

sed -i "s/REPLACE_ME/$account/g" "$SOPS_FILE"
echo "updated $SOPS_FILE with account-id $account"
grep -E 'kms:' "$SOPS_FILE"
