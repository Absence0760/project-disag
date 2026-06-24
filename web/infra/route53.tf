# Custom-domain wiring for the CloudFront distribution.
#
# The delegated hosted zone (var.parent_domain) lives in this same
# AWS account — the bootstrap baseline imported the manually-created
# zone. The wildcard ACM cert (*.<parent_domain> + <parent_domain>)
# also lives in this account, in us-east-1 (CloudFront requirement).
# Both are looked up by data source — neither resource is managed here.
#
# CROSS-REPO DELEGATION — read before destroying/recreating this zone.
# var.parent_domain (disag.jaredhoward.com) is a CHILD zone delegated from
# the jaredhoward.com apex, which lives in a DIFFERENT account
# (project-personal-website, 136758763748). That apex holds an NS record
# pointing at THIS zone's name servers, codified in
# project-personal-website/infra/dns (aws_route53_record.disag_ns). Those
# name servers are assigned by AWS when this zone is created — so if this
# zone is ever destroyed/recreated (account rebuild, region move), AWS
# issues a NEW NS set and disag.jaredhoward.com stops resolving until the
# parent's disag_delegation_ns is updated to match. Recreate this zone
# only in lockstep with updating that record. See
# project-personal-website/docs/todo.md §2.

data "aws_route53_zone" "this" {
  name = var.parent_domain
}

data "aws_acm_certificate" "wildcard" {
  provider    = aws.us_east_1
  domain      = var.parent_domain
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
