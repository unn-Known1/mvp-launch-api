# AWS WAF Web ACL for ALB protection

resource "aws_wafv2_web_acl" "main" {
  name        = "${var.project_name}-${var.environment}-waf"
  description = "WAF Web ACL for protecting the ALB against OWASP Top 10 attacks"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action {
      count {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "${var.project_name}-${var.environment}-waf-common"
      sampled_requests_enabled  = true
    }
  }

  rule {
    name     = "RateLimitRule"
    priority = 2
    action {
      block {
        custom_response {
          response_code = 429
        }
      }
    }
    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "${var.project_name}-${var.environment}-waf-rate"
      sampled_requests_enabled  = true
    }
  }

  rule {
    name     = "SQLInjectionRule"
    priority = 3
    action {
      block {}
    }
    statement {
      sqli_match_statement {
        field_to_match {
          query_string {}
        }
        confidence_level = "HIGH"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "${var.project_name}-${var.environment}-waf-sql"
      sampled_requests_enabled  = true
    }
  }

  rule {
    name     = "XSSRule"
    priority = 4
    action {
      block {}
    }
    statement {
      xss_match_statement {
        field_to_match {
          query_string {}
        }
        confidence_level = "HIGH"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name               = "${var.project_name}-${var.environment}-waf-xss"
      sampled_requests_enabled  = true
    }
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-waf"
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name               = "${var.project_name}-${var.environment}-waf-metrics"
    sampled_requests_enabled  = true
  }
}

resource "aws_wafv2_web_acl_association" "main" {
  web_acl_arn  = aws_wafv2_web_acl.main.arn
  resource_arn = aws_lb.backend.arn
}
