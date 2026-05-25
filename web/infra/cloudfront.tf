# CloudFront fronts both the static SvelteKit build (S3 origin) and
# the API Gateway HTTP API (so the browser sees a single origin and
# CORS stops mattering for prod). The /api/* path strips the prefix
# before forwarding.

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Security headers policy applied to every response. Without this, the
# audit flagged CloudFront responses as missing HSTS, X-Content-Type-
# Options, X-Frame-Options, and Referrer-Policy. CSP is intentionally
# strict for a no-third-party-script SPA — relax only when adding a
# new origin (analytics, fonts, etc.) and re-run the audit.
resource "aws_cloudfront_response_headers_policy" "security" {
  name = "${local.name_prefix}-security-headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 63072000 # 2 years
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    content_security_policy {
      content_security_policy = join("; ", [
        "default-src 'self'",
        # SvelteKit's adapter-static emits an inline bootstrap <script>
        # (`Promise.all([import(...)]).then(kit.start)`) whose content
        # changes per build (module hashes are baked into the import
        # paths). Without 'unsafe-inline' the browser refuses to run
        # it and the page stays blank.
        #
        # A nonce-based CSP would be stronger but can't be set from a
        # static CloudFront response_headers_policy — it needs per-request
        # generation, which means moving CSP into the SvelteKit handler.
        # Worth doing if user-generated content ever lands in the page;
        # not worth it today.
        "script-src 'self' 'unsafe-inline'",
        # SvelteKit's adapter-static emits inline <style> blocks per
        # component — 'unsafe-inline' is required for them to apply.
        # Switch to nonces/hashes if a CSP report-uri ever shows abuse.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        # API XHR to CloudFront's /api/* (same origin) AND direct POST
        # to S3 for pre-signed uploads.
        "connect-src 'self' https://*.s3.amazonaws.com https://*.s3.${var.region}.amazonaws.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self' https://*.s3.amazonaws.com https://*.s3.${var.region}.amazonaws.com",
        "object-src 'none'",
      ])
      override = true
    }
  }
}

# Shared secret between CloudFront and Lambda. CloudFront stamps every
# /api/* request with this header at the origin layer; the handler
# checks it and rejects (403) anything missing it. Without this, the
# bare API Gateway endpoint (a long .execute-api host) is reachable
# directly — bypassing WAF + the rate-limit rule.
resource "random_password" "cloudfront_shared_secret" {
  length  = 48
  special = false
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # NA + EU only; cheap default.
  comment             = "${local.name_prefix} site"
  web_acl_id          = aws_wafv2_web_acl.site.arn
  aliases             = [local.fqdn]

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  origin {
    domain_name = replace(aws_apigatewayv2_api.http.api_endpoint, "https://", "")
    origin_id   = "api-gw"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
    # Shared secret — the handler rejects requests without it, so the
    # API Gateway URL is not reachable directly. See lambda.tf for
    # how CLOUDFRONT_SHARED_SECRET reaches the handler.
    custom_header {
      name  = "X-CloudFront-Shared-Secret"
      value = random_password.cloudfront_shared_secret.result
    }
  }

  default_cache_behavior {
    target_origin_id           = "frontend-s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    # AWS-managed: CachingOptimized.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  ordered_cache_behavior {
    path_pattern               = "/api/*"
    target_origin_id           = "api-gw"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
    # AWS-managed: CachingDisabled + AllViewerExceptHostHeader.
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  # SPA fallback — SvelteKit's adapter-static fallback file handles
  # client-side routing. 403 means the key didn't exist in S3 (e.g.
  # /run requested directly); rewrite to index.html and let the SPA
  # take it.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = data.aws_acm_certificate.wildcard.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# Bucket policy: only this distribution can read frontend objects.
data "aws_iam_policy_document" "frontend_oac" {
  statement {
    sid       = "AllowCloudFrontReadViaOAC"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_oac.json
}
