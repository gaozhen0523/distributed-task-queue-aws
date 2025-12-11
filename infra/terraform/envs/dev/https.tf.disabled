#############################
# Route53 Hosted Zone
#############################

# 要求你已经在 Route53 里有 public hosted zone: zhencloud.com
data "aws_route53_zone" "root" {
  name         = var.root_domain
  private_zone = false
}

#############################
# ACM certificate for dist-api
#############################

resource "aws_acm_certificate" "dist_api" {
  domain_name       = "${var.dist_api_subdomain}.${var.root_domain}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# DNS 验证记录
resource "aws_route53_record" "dist_api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.dist_api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = data.aws_route53_zone.root.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "dist_api" {
  certificate_arn         = aws_acm_certificate.dist_api.arn
  validation_record_fqdns = [for r in aws_route53_record.dist_api_cert_validation : r.fqdn]
}

#############################
# ALB data source (to get zone_id)
#############################

data "aws_lb" "dist_api" {
  arn = module.dist_api_service.alb_arn
}

#############################
# Route53 A record -> ALB
#############################

resource "aws_route53_record" "dist_api_alias" {
  zone_id = data.aws_route53_zone.root.zone_id
  name    = "${var.dist_api_subdomain}.${var.root_domain}"
  type    = "A"

  alias {
    name                   = data.aws_lb.dist_api.dns_name
    zone_id                = data.aws_lb.dist_api.zone_id
    evaluate_target_health = true
  }
}

#############################
# HTTPS Listener on dist-api ALB
#############################

resource "aws_lb_listener" "dist_api_https" {
  load_balancer_arn = module.dist_api_service.alb_arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate_validation.dist_api.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = module.dist_api_service.target_group_arn
  }
}
