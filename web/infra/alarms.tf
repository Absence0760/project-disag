# Cost + availability alarms.
#
# The audit flagged "no AWS Budget alert anywhere" as the top P0 — a
# runaway loop on Lambda at 4 GB × 5 min can clear $1k/day before the
# bill page even loads. This file fixes that, plus adds per-resource
# CloudWatch alarms that catch problems *before* they show up on the
# monthly invoice.
#
# Wiring: one SNS topic carries every alarm; the operator subscribes
# via `var.budget_alert_email`. If the variable is empty, alarms still
# fire (visible in the AWS console) but no one gets paged.

# ── SNS topic — single channel for budget + alarms ────────────────────

resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.budget_alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.budget_alert_email
  # AWS sends a confirmation email on first apply — accept it once;
  # Terraform doesn't otherwise touch the subscription afterwards.
}

# Allow CloudWatch + Budgets to publish to the topic. SNS topic
# policies are union'd, so granting both services in one document is
# the cleanest form.
data "aws_iam_policy_document" "alerts_publish" {
  statement {
    sid     = "AllowCloudWatchAlarms"
    actions = ["sns:Publish"]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com", "budgets.amazonaws.com"]
    }
    resources = [aws_sns_topic.alerts.arn]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_publish.json
}

# ── AWS Budget — monthly spend ceiling ───────────────────────────────
#
# Account-wide because shared services (CloudFront, WAF, KMS) aren't
# all tagged with the project label. Two notifications: forecasted to
# exceed (early warning) and actual exceeded (you've blown the budget).

resource "aws_budgets_budget" "monthly" {
  count             = var.budget_monthly_usd > 0 ? 1 : 0
  name              = "${local.name_prefix}-monthly"
  budget_type       = "COST"
  time_unit         = "MONTHLY"
  limit_amount      = tostring(var.budget_monthly_usd)
  limit_unit        = "USD"
  time_period_start = "2026-01-01_00:00"

  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    subscriber_email_addresses = var.budget_alert_email == "" ? [] : [var.budget_alert_email]
  }

  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    subscriber_email_addresses = var.budget_alert_email == "" ? [] : [var.budget_alert_email]
  }
}

# ── Lambda alarms — invocations, errors, throttles, concurrency ──────
#
# Thresholds tuned for a small hydrology tool. Re-tune upward if real
# usage grows past the alarm — the alarm should be a "something has
# changed" signal, not a steady-state notification.

resource "aws_cloudwatch_metric_alarm" "lambda_high_invocations" {
  alarm_name          = "${local.name_prefix}-lambda-high-invocations"
  alarm_description   = "Lambda invocation rate > 1000 in 5 min — likely abuse or a stuck client loop."
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 1000
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Lambda errors > 10 in 5 min — investigate via CloudWatch Logs."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_concurrent_executions" {
  alarm_name          = "${local.name_prefix}-lambda-concurrency"
  alarm_description   = "Lambda concurrent executions > 50 — abnormal load, may hit account limits soon."
  namespace           = "AWS/Lambda"
  metric_name         = "ConcurrentExecutions"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  comparison_operator = "GreaterThanThreshold"
  threshold           = 50
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.name_prefix}-lambda-throttles"
  alarm_description   = "Lambda throttled — account concurrency limit reached; users are seeing failures."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

# Lambda Duration — catches a runaway compute (e.g. Method 5 on a huge
# monthly file) that stays within the concurrency cap but bills near
# the timeout per invocation. P99 > 25s flags requests creeping toward
# the 29s API Gateway ceiling before they start 504'ing.
resource "aws_cloudwatch_metric_alarm" "lambda_duration_p99" {
  alarm_name          = "${local.name_prefix}-lambda-duration-p99"
  alarm_description   = "Lambda P99 duration > 25 s — approaching the 29 s API Gateway ceiling; investigate before 504s land."
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  extended_statistic  = "p99"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 25000
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

# ── Edge alarms — CloudFront + API Gateway 5xx ───────────────────────
#
# These fire when failures occur before reaching the Lambda — cache
# storms, integration timeouts, or 503s from a reserved-concurrency
# cap being hit. The Lambda alarms above don't catch any of those.

# CloudFront publishes its global metrics to us-east-1 only — the
# alarm has to be created there too (hence the us_east_1 provider
# alias declared in providers.tf).
resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  provider            = aws.us_east_1
  alarm_name          = "${local.name_prefix}-cloudfront-5xx"
  alarm_description   = "CloudFront 5xx rate > 1 % over 10 min — origin failures or cache-miss storms."
  namespace           = "AWS/CloudFront"
  metric_name         = "5xxErrorRate"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    DistributionId = aws_cloudfront_distribution.site.id
    Region         = "Global"
  }
}

# API Gateway HTTP API v2 emits `5xx` (not the REST API `5XXError`).
# Catches integration-layer failures the Lambda metric doesn't see —
# e.g. 503s when reserved_concurrency is exhausted, or 504s when an
# invocation overruns the 30 s integration timeout.
resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  alarm_name          = "${local.name_prefix}-apigw-5xx"
  alarm_description   = "API Gateway 5xx > 10 in 5 min — integration failures, throttling, or timeouts."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    ApiId = aws_apigatewayv2_api.http.id
    Stage = "$default"
  }
}
