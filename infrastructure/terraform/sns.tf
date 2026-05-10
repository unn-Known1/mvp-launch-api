# SNS Topic for CloudWatch Alarm notifications

resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-${var.environment}-alarms"

  tags = {
    Name = "${var.project_name}-${var.environment}-alarms"
  }
}

# Email subscription for alarm notifications
resource "aws_sns_topic_subscription" "alarms_email" {
  count  = var.environment == "production" ? 1 : 0
  topic  = aws_sns_topic.alarms.arn
  protocol = "email"
  endpoint = "ops-team@${var.project_name}.com"
}

# CloudWatch Alarm - ECS High CPU with SNS notification
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
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-high-cpu-alarm"
  }
}

# CloudWatch Alarm - RDS High CPU with SNS notification
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
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-high-cpu-alarm"
  }
}
