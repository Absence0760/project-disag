---
description: Pre-tag readiness gate for a release. Checks main is clean, CI green, tests pass, demo generators don't drift, and (for web releases) e2e green + tf plan clean + GitHub repo variables aligned. Read-only — never tags or deploys.
argument-hint: <kind> (python | web)
---

Run a pre-tag readiness audit. Report a green/red checklist; never tag, push, or publish. The user does the actual `git tag` after they've reviewed the report.

## Why this exists

The repo has two independent release flows:

- **`v*` tags** trigger [`.github/workflows/release.yml`](../../.github/workflows/release.yml) — PyInstaller binaries for `disag` and `exceed` on Linux + macOS + Windows, published as a GitHub Release.
- **`web-v*` tags** trigger [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) — `aws lambda update-function-code` + `aws s3 sync` + `cloudfront create-invalidation`, gated by the `production` GitHub environment.

Both are irreversible-ish (the Python release can be deleted; the Lambda + S3 deploy needs a rollback tag to undo). This command catches the obvious "you forgot to push", "CI is red", "you have uncommitted work" failures before the tag goes out.

## When to use

**Right fit:** you're about to cut a release and want a single yes/no.

**Wrong fit — refuse:**
- Argument doesn't match `python` or `web`.
- The user is on a feature branch (not `main`) — explain that releases tag from `main`, ask whether to switch.

## Procedure

### 1. Validate the argument

Accept exactly one of: `python`, `web`. Aliases: `cli` / `v` → `python`; `frontend` / `backend` / `web-v` → `web`.

If `$ARGUMENTS` is empty, ask the user which kind — don't guess.

### 2. Confirm we're on main

```
git rev-parse --abbrev-ref HEAD
```

If not `main`, abort with: "release tags must be cut from `main`; you're on `<branch>`. Switch with `git checkout main && git pull`, then re-run."

### 3. Universal gates (every release)

Mark **green** / **red** and capture a one-line reason for any red.

#### 3a. Working tree is clean

```
git status --porcelain
```

Empty → green. Anything → red ("uncommitted changes in: <files>").

#### 3b. main is up to date with origin

```
git fetch origin main
git rev-list --count HEAD..origin/main
git rev-list --count origin/main..HEAD
```

Both `0` → green. Behind → red ("origin is ahead — pull first"). Ahead → red ("local main has unpushed commits — push first, wait for CI, then re-run").

#### 3c. Latest CI run on main is green

```
gh run list --branch main --limit 5 --json status,conclusion,workflowName,headSha,createdAt
```

The relevant workflows are `Tests` (tests.yml) and `Web CI` (web-ci.yml). Security workflows (security/gitleaks/scorecard) and dependabot-auto-merge are informational — note their status but don't block.

For each blocking workflow:
- `status=completed` and `conclusion=success` → green.
- Anything else → red ("CI workflow `<name>` on HEAD is `<status>/<conclusion>` — wait for green or investigate").

If `gh` isn't logged in, mark this gate `⚠ skipped — gh not authenticated` and continue.

#### 3d. Python tests pass locally

```
python3 -m unittest discover tests
```

Green if exit 0. Red with a one-line failure summary otherwise.

#### 3e. Demo generators are deterministic

For each `examples/methodN_demo/generate.py`, re-run it and verify nothing changed:

```
for demo in examples/method*_demo; do
    [ -f "$demo/generate.py" ] && python3 "$demo/generate.py"
done
git diff --exit-code -- examples/
```

Clean → green. Any diff → red ("demo data drift — re-commit `examples/` before tagging").

### 4. Kind-specific gates

#### `python` (tag pattern: `v*`)

**4a. Last `v*` tag and commit delta**

```
last=$(git describe --tags --match 'v*' --abbrev=0 2>/dev/null || echo '(none)')
git rev-list --count "$last"..HEAD -- disag exceed tests examples packaging
```

Zero touching the relevant paths → red ("no new code since `<last>` — nothing to release").

**4b. Changelog draft**

```
git log --oneline "$last"..HEAD -- disag exceed tests examples packaging
```

List as the changelog draft for the GitHub Release notes.

**4c. PyInstaller build sanity**

The release workflow runs `python packaging/build.py --clean` on three OSes. A local Linux build is a cheap pre-flight:

```
python3 packaging/build.py --clean 2>/dev/null && ls dist/disag dist/exceed
```

Both binaries present → green. Failure → red. Skippable with `⚠ skipped — PyInstaller not installed` if `pyinstaller` isn't on PATH.

**4d. tk-availability note**

`stock macOS Python's _tkinter is broken` — confirm root `CLAUDE.md`'s macOS guidance hasn't drifted. This is a note (⚠), not a gate.

#### `web` (tag pattern: `web-v*`)

**4a. Last `web-v*` tag and commit delta**

```
last=$(git describe --tags --match 'web-v*' --abbrev=0 2>/dev/null || echo '(none)')
git rev-list --count "$last"..HEAD -- disag exceed web examples
```

Zero → red ("no code changes affecting the deployed app since `<last>`"). Include `disag/` and `exceed/` in the path filter — they ship inside the Lambda zip, so a change there warrants a web release.

**4b. Changelog draft**

```
git log --oneline "$last"..HEAD -- disag exceed web examples
```

**4c. Mocked + integration Playwright pass locally**

```
pnpm e2e
pnpm e2e:integration
```

Both green → gate green. Any failure → red ("`pnpm e2e<:integration>` failing — fix before deploying").

If the venv isn't built yet, `pnpm e2e:integration` will bootstrap it on first run — note that and continue rather than failing.

**4d. Build succeeds (zip + static)**

```
pnpm build
```

Both `web/backend/lambda.zip` and `web/frontend/build/` produced → green.

**4e. Terraform plan is clean (no live drift)**

```
cd web/infra && terraform plan -detailed-exitcode -lock=false
```

Exit code:
- `0` → green ("no infra changes pending").
- `2` → red ("infra drift — `terraform apply` locally before deploying, so the live state matches the tag's source"). List the resources that would change.
- `1` → ⚠ skipped, report stderr ("terraform plan failed — likely SSO creds expired, run `pnpm tf:login`").

This is the most important `web` gate. `deploy.yml` uses AWS CLI to push code, not Terraform — so drift between git and live infra survives the deploy. Catching it here is the only routine check.

**4f. GitHub repo variables match current terraform outputs**

```
gh variable list --json name,value | python3 -c "import json,sys; print(json.load(sys.stdin))"
```

For each of `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `LAMBDA_FUNCTION_NAME`, `FRONTEND_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, compare the value to the current `terraform output -raw <name>`. Mismatch → red ("`<var>` in GitHub doesn't match terraform — re-run `pnpm tf:export-vars`").

Missing variable → red ("`<var>` not set in repo variables — run `pnpm tf:export-vars`").

#### 4g. `production` environment exists

```
gh api repos/:owner/:repo/environments/production --silent
```

200 → green. 404 → red ("no `production` environment configured in repo Settings → Environments. Without it, the OIDC trust policy can't match and deploys will fail. Create the environment and add required reviewers before tagging.").

#### 4h. sops file is well-formed (if it exists)

If `web/infra/secrets.enc.yaml` exists, verify it decrypts cleanly:

```
sops -d web/infra/secrets.enc.yaml >/dev/null
```

Exit 0 → green. Failure → red ("sops decrypt failing — SSO creds for the KMS key may be expired (`pnpm tf:login`), or the file is corrupted").

### 5. Build the report

```
# Release readiness — `<kind>`

Proposed tag: `<v|web-v><x.y.z>` (suggest based on the user's input or last tag)

## Universal gates

| Gate | Status | Detail |
|---|---|---|
| On main | ✓ / ✗ | ... |
| Tree clean | ✓ / ✗ | ... |
| Pushed to origin | ✓ / ✗ | ... |
| CI green on HEAD | ✓ / ✗ | ... |
| Python tests | ✓ / ✗ | ... |
| Demo generators no-drift | ✓ / ✗ | ... |

## Kind-specific (`<kind>`)

| Gate | Status | Detail |
|---|---|---|
| Last tag | — | `<v|web-v><x.y.z>` (<n> days ago) |
| Commits since last tag | ✓ / ✗ | <count> |
| ...kind-specific extras... | | |

## Changelog draft

- abcd123 commit subject
- ...

## Verdict

<ALL GREEN — ready to tag>
or
<NOT READY — fix the red items above first>
```

### 6. Hand off

End with:

> If everything's green, the next step is:
> ```
> gh release create <v|web-v><x.y.z> \
>     --title '<short title>' \
>     --generate-notes
> ```
> I won't run that — that's your call.

**Do not tag, do not push, do not auto-fix any of the red gates.** This command is read-only.

## Notes

- The whole thing should take under two minutes; the slowest step is `pnpm e2e:integration` (~30s). If a gate hangs (e.g. `gh` on a slow connection), skip it with a `⚠ skipped — <reason>` row rather than blocking the report.
- `gh` is required for CI status, repo variables, and the `production` environment check. If unavailable, fall back to: "install + authenticate `gh`; manual: open the Actions tab and confirm green on the head commit".
- `pnpm tf:plan` (gate 4e) needs SSO creds. If they're stale the gate skips with a clear "run `pnpm tf:login`" hint, not a red.
