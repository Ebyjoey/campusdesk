# CloudWatch resources live here so `terraform destroy` removes them too
# (log groups created by hand or by the agent would otherwise outlive the project).

resource "aws_sns_topic" "alerts" {
  name = "campusdesk-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # AWS emails a confirmation link; click it once
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/campusdesk/app"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "system" {
  name              = "/campusdesk/system"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "campusdesk-error-lines"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = "ERROR"

  metric_transformation {
    name      = "AppErrorCount"
    namespace = "CampusDesk"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "worker_cpu" {
  alarm_name          = "campusdesk-worker-cpu-high"
  alarm_description   = "Worker CPU above 70% for 10 minutes"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  dimensions          = { InstanceId = aws_instance.worker.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 70
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "app_errors" {
  alarm_name          = "campusdesk-app-errors"
  alarm_description   = "Five or more ERROR lines in the application log within 5 minutes"
  namespace           = "CampusDesk"
  metric_name         = "AppErrorCount"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "status_check" {
  for_each = {
    jenkins = aws_instance.jenkins.id
    master  = aws_instance.master.id
    worker  = aws_instance.worker.id
    db      = aws_instance.db.id
  }

  alarm_name          = "campusdesk-${each.key}-status-check-failed"
  alarm_description   = "EC2 status check failed on ${each.key}"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = each.value }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "campusdesk"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "CPU utilisation by instance"
          region = var.region
          view   = "timeSeries"
          stat   = "Average"
          period = 300
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.jenkins.id, { label = "jenkins" }],
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.master.id, { label = "k3s-master" }],
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.worker.id, { label = "k3s-worker" }],
            ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.db.id, { label = "db" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "Memory used % (CloudWatch agent)"
          region = var.region
          view   = "timeSeries"
          stat   = "Average"
          period = 300
          metrics = [
            ["CWAgent", "mem_used_percent", "InstanceId", aws_instance.jenkins.id, { label = "jenkins" }],
            ["CWAgent", "mem_used_percent", "InstanceId", aws_instance.master.id, { label = "k3s-master" }],
            ["CWAgent", "mem_used_percent", "InstanceId", aws_instance.worker.id, { label = "k3s-worker" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title   = "Application ERROR lines"
          region  = var.region
          view    = "timeSeries"
          stat    = "Sum"
          period  = 300
          metrics = [["CampusDesk", "AppErrorCount"]]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "Network in (bytes), worker and master"
          region = var.region
          view   = "timeSeries"
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.master.id, { label = "k3s-master" }],
            ["AWS/EC2", "NetworkIn", "InstanceId", aws_instance.worker.id, { label = "k3s-worker" }],
          ]
        }
      },
    ]
  })
}
