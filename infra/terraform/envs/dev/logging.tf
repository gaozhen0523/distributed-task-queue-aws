#############################
# SNS Topic for alerts
#############################

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

#############################
# Log Metric Filters
#############################

# dist-api：按 ERROR 计数
resource "aws_cloudwatch_log_metric_filter" "dist_api_error" {
  name           = "dist-api-error-count"
  log_group_name = "/ecs/dist-api"
  pattern        = "\"ERROR\""

  metric_transformation {
    name      = "dist-api-error-count"
    namespace = "DistributedTaskQueue"
    value     = "1"
  }
}

# dist-worker：按 task_failed 计数（你日志里最好打这个关键字）
resource "aws_cloudwatch_log_metric_filter" "dist_worker_failed" {
  name           = "dist-worker-failed-count"
  log_group_name = "/ecs/dist-worker"
  pattern        = "\"task_failed\""

  metric_transformation {
    name      = "dist-worker-failed-count"
    namespace = "DistributedTaskQueue"
    value     = "1"
  }
}

# dist-scheduler：按 retry 计数（重试量）
resource "aws_cloudwatch_log_metric_filter" "dist_scheduler_retry" {
  name           = "dist-scheduler-retry-count"
  log_group_name = "/ecs/dist-scheduler"
  pattern        = "\"retry\""

  metric_transformation {
    name      = "dist-scheduler-retry-count"
    namespace = "DistributedTaskQueue"
    value     = "1"
  }
}

#############################
# CloudWatch Alarms
#############################

# API 错误 5 分钟内 >= 5 次
resource "aws_cloudwatch_metric_alarm" "dist_api_error_high" {
  alarm_name          = "${var.project_name}-${var.environment}-dist-api-error-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.dist_api_error.metric_transformation[0].name
  namespace           = aws_cloudwatch_log_metric_filter.dist_api_error.metric_transformation[0].namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 5

  alarm_description = "dist-api has >=5 ERROR logs in 5 minutes"
  alarm_actions     = [aws_sns_topic.alerts.arn]
}

# worker 失败 5 分钟内 >= 5 次
resource "aws_cloudwatch_metric_alarm" "dist_worker_failed_high" {
  alarm_name          = "${var.project_name}-${var.environment}-dist-worker-failed-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.dist_worker_failed.metric_transformation[0].name
  namespace           = aws_cloudwatch_log_metric_filter.dist_worker_failed.metric_transformation[0].namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 5

  alarm_description = "dist-worker has >=5 failed tasks in 5 minutes"
  alarm_actions     = [aws_sns_topic.alerts.arn]
}

# scheduler 重试 5 分钟内 >= 20 次（示例阈值）
resource "aws_cloudwatch_metric_alarm" "dist_scheduler_retry_high" {
  alarm_name          = "${var.project_name}-${var.environment}-dist-scheduler-retry-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.dist_scheduler_retry.metric_transformation[0].name
  namespace           = aws_cloudwatch_log_metric_filter.dist_scheduler_retry.metric_transformation[0].namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 20

  alarm_description = "dist-scheduler has >=20 retries in 5 minutes"
  alarm_actions     = [aws_sns_topic.alerts.arn]
}
