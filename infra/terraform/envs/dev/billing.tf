#############################
# Billing alarm using AWS/Billing
#############################

resource "aws_cloudwatch_metric_alarm" "billing_high" {
  alarm_name          = "${var.project_name}-${var.environment}-billing-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1

  metric_name = "EstimatedCharges"
  namespace   = "AWS/Billing"
  period      = 21600 # 6 hours
  statistic   = "Maximum"
  threshold   = var.billing_threshold_usd

  alarm_description = "AWS estimated charges exceed threshold in USD"
  alarm_actions     = [aws_sns_topic.alerts.arn]

  dimensions = {
    Currency = "USD"
  }
}
