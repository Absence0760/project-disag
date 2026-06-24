# Security policy

## Supported versions

Disag-MD is a small, single-maintainer tool. The latest tagged
release on `main` is the only supported version; older tags are kept
for historical reference but don't receive security backports.

| Component       | Tag pattern  | Supported |
|-----------------|--------------|-----------|
| CLI / packages  | latest `v*`  | Yes       |
| Web app         | latest `web-v*` | Yes    |
| Earlier tags    | any older    | No        |

## Reporting a vulnerability

If you find a security issue, please use GitHub's private
vulnerability reporting:

1. Go to <https://github.com/Absence0760/project-disag/security/advisories/new>.
2. Describe the issue, the affected component, and a minimal
   reproduction if you have one.

I'll triage within a week and follow up with a planned fix window.
Please don't open a public issue or PR with vulnerability details
until a fix is available.

For non-vulnerability bug reports, the regular [issues
tracker](https://github.com/Absence0760/project-disag/issues) is
fine.

## What's in scope

- The `disag/` and `exceed/` Python packages (CLI + GUI entry points).
- The web app under `web/` (SvelteKit frontend, AWS Lambda backend,
  Terraform infra).
- The GitHub Actions workflows under `.github/workflows/`.

## What's out of scope

- The original 1991 Delphi/Pascal source under `delphi_files/` — it's
  read-only reference material and never executed.
- Test fixtures under `examples/` and `testfiles/` (the latter is
  gitignored).
- Third-party services (AWS Lambda runtime, S3, CloudFront,
  registered Dependabot ecosystems) — report those to the relevant
  provider.

## Posture

Automated controls already in place:

- CodeQL on Python, TypeScript/JavaScript, and GitHub Actions
  (`.github/workflows/security.yml`).
- gitleaks secret scanning on every push + a weekly full-history
  sweep (`.github/workflows/gitleaks.yml`).
- OpenSSF Scorecard (`.github/workflows/scorecard.yml`) results
  published to <https://scorecard.dev>.
- Dependabot for npm, terraform, and github-actions
  (`.github/dependabot.yml`), with minor/patch auto-merge gated on CI.
- sops + AWS KMS for infra secrets. Prod secrets are kept ENCRYPTED in
  the private `infra-secrets` repo (`disag/prod.sops.yaml`), never in
  this public repo — only public placeholders live in `web/infra`.
- GitHub Actions OIDC for deploys — no long-lived AWS access keys
  in the repo (`web/infra/oidc.tf`).
