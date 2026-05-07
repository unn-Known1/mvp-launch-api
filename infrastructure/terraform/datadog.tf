# Datadog monitoring integration

variable "datadog_api_key" {
  description = "Datadog API key for monitoring integration"
  type        = string
  sensitive   = true
  default     = ""
}

variable "datadog_site" {
  description = "Datadog site (us1, us3, eu1, etc.)"
  type        = string
  default     = "datadoghq.com"
}

resource "aws_iam_role" "datadog" {
  count = var.datadog_api_key != "" ? 1 : 0
  name  = "${var.project_name}-${var.environment}-datadog-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::464622532012:root"
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.datadog_api_key
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-datadog-role"
  }
}

resource "aws_iam_role_policy_attachment" "datadog" {
  count      = var.datadog_api_key != "" ? 1 : 0
  role       = aws_iam_role.datadog[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.backend.name],
            ["AWS/ECS", "MemoryUtilization", "ServiceName", aws_ecs_service.backend.name]
          ]
          view   = "timeSeries"
          title  = "ECS Service Utilization"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.postgres.id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", aws_db_instance.postgres.id]
          ]
          view   = "timeSeries"
          title  = "RDS Metrics"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.backend.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_2XX_Count", "LoadBalancer", aws_lb.backend.arn_suffix]
          ]
          view   = "timeSeries"
          title  = "ALB Request Metrics"
          region = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", aws_elasticache_cluster.redis.id],
            ["AWS/ElastiCache", "EngineCPUUtilization", "CacheClusterId", aws_elasticache_cluster.redis.id]
          ]
          view   = "timeSeries"
          title  = "ElastiCache Metrics"
          region = var.aws_region
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "ecs_high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-ecs-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "ECS service CPU utilization is above 80%"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU utilization is above 80%"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-high-cpu-alarm"
  }
}
