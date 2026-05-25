# Custom-domain wiring for the CloudFront distribution.
#
# The disag.jaredhoward.com hosted zone lives in this same AWS account
# (the bootstrap baseline imported the manually-created zone). The
# wildcard ACM cert (*.disag.jaredhoward.com + disag.jaredhoward.com)
# also lives in this account, in us-east-1 (CloudFront requirement).
# Both are looked up by data source — neither resource is managed here.

data "aws_route53_zone" "this" {
  name = "disag.jaredhoward.com"
}

data "aws_acm_certificate" "wildcard" {
  provider    = aws.us_east_1
  domain      = "disag.jaredhoward.com"
  statuses    = ["ISSUED"]
  most_recent = true
}

resource "aws_route53_record" "site" {
  zone_id = data.aws_route53_zone.this.zone_id
  name    = local.fqdn
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}
