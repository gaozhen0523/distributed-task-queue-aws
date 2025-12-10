#infra/terraform/modules/ecs_service_internal/outputs.tf
output "service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.this.name
}

output "task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.this.arn
}

output "task_role_arn" {
  description = "IAM role ARN used by ECS tasks"
  value       = aws_iam_role.task.arn
}

output "task_execution_role_arn" {
  description = "IAM execution role ARN used by ECS tasks"
  value       = aws_iam_role.execution.arn
}

output "environment_variables" {
  description = "Environment variables for the container"
  value       = var.environment_variables
}
