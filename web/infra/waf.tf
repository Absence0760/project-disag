# WAFv2 web ACL attached to the CloudFront distribution.
#
# Scope is CLOUDFRONT, which means the ACL is a global resource
# (CloudFront is global) and the API insists the resource be created
# in us-east-1. Hence the `provider = aws.us_east_1` alias.
#
# Cost: $5/month base for the ACL, plus $1/month per rule
# ($1 × 1 = $1 here, so $6/month flat), plus $0.60 per million
# requests. For a low-traffic hydrology tool the per-request slice
# rounds to zero — call it ~$6/mo. If that's too much for the
# project's budget, comment out the cloudfront.tf:web_acl_id line
# and delete this file.

resource "aws_wafv2_web_acl" "site" {
  provider = aws.us_east_1
  name     = "${local.name_prefix}-cloudfront"
  scope    = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # Priority 0 — per-IP rate limit. Runs before the managed rule set
  # so a flood-source IP gets shed cheaply (no rules evaluated, no
  # CloudFront cache miss). 5-minute rolling window per
  # var.waf_rate_limit_per_ip; AWS minimum is 100.
  rule {
    name     = "RateLimitPerIP"
    priority = 0

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit_per_ip
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedCommonRuleSet"
    priority = 1

    # AWSManagedRulesCommonRuleSet covers the OWASP basics: SQL
    # injection-shaped patterns, LFI/path-traversal, oversized request
    # bodies, etc. Defensive defaults; rarely false-positives on a
    # JSON-only API with a static SPA.
    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-common-rule-set"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-cloudfront"
    sampled_requests_enabled   = true
  }
}

# WAF logging — without this, blocked requests have no audit trail
# beyond CloudWatch counters, so there's no way to tell a brute-force
# probe from a legitimate burst, or to debug a false-positive on the
# managed rule set.
#
# CloudWatch log group name MUST start with `aws-waf-logs-` and live
# in us-east-1 for CLOUDFRONT-scoped ACLs. 30-day retention matches
# the rest of this stack (apigw + lambda log groups).
resource "aws_cloudwatch_log_group" "waf" {
  provider          = aws.us_east_1
  name              = "aws-waf-logs-${local.name_prefix}-cloudfront"
  retention_in_days = 30
}

resource "aws_wafv2_web_acl_logging_configuration" "site" {
  provider                = aws.us_east_1
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
  resource_arn            = aws_wafv2_web_acl.site.arn
}
