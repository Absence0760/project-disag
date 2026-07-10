# Prod cost-guardrail checks.
#
# The cost-control variables all default to their "off" position
# (budget_monthly_usd = 0, budget_alert_email = "",
# lambda_reserved_concurrency = -1) because a freshly-bootstrapped AWS
# account can't accept the "on" values — see each variable's docstring
# in variables.tf. That's deliberately fail-open, so nothing enforces
# turning them on once the account prerequisites are met. These checks
# close that gap without blocking: `check` blocks emit warnings on
# plan/apply rather than errors, so a brand-new prod account still
# applies cleanly while every run nags until the ceilings are real.

check "prod_budget_configured" {
  assert {
    condition     = var.environment != "prod" || var.budget_monthly_usd > 0
    error_message = "budget_monthly_usd is 0 in prod, so aws_budgets_budget.monthly is skipped and nothing alerts on runaway spend. Once the payer account enables 'IAM user and role access to billing information' (see the budget_monthly_usd docstring in variables.tf), set it to a real ceiling (~50)."
  }
}

check "prod_budget_alert_email_set" {
  assert {
    condition     = var.environment != "prod" || var.budget_alert_email != ""
    error_message = "budget_alert_email is empty in prod, so no SNS email subscription is created — budget and CloudWatch alarms fire but page no one. Set it in terraform.tfvars (see the budget_alert_email docstring in variables.tf)."
  }
}

check "prod_lambda_concurrency_capped" {
  assert {
    condition     = var.environment != "prod" || var.lambda_reserved_concurrency > 0
    error_message = "lambda_reserved_concurrency is -1 in prod, so the API Lambda has no concurrency ceiling and an abuser's burst sets the worst-case bill. Once the account's 'Concurrent executions' quota is raised via Service Quotas (see the lambda_reserved_concurrency docstring in variables.tf), set it to ~10-50."
  }
}
