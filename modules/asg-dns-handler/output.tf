output "autoscale_handling_sns_topic_arn" {
  description = "SNS topic ARN for autoscaling group"
  value       = aws_sns_topic.autoscale_handling.arn
}

output "autoscale_iam_role_arn" {
  description = "IAM role ARN for autoscaling group"
  value       = aws_iam_role.autoscale_handling.arn
}

output "agent_lifecycle_iam_role_arn" {
  description = "IAM Role ARN for lifecycle_hooks"
  value       = aws_iam_role.lifecycle.arn
}

output autoscale_lambda_arn {
    description = "Lambda Autoscale ARN for autoscaling group"
    value = aws_lambda_function.autoscale_handling.arn
}