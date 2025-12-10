#infra/terraform/modules/ecs_service/outputs.tf
output "service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.this.name
}

output "service_arn" {
  description = "ARN of the ECS service"
  value       = aws_ecs_service.this.id
}

output "task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.this.arn
}

output "alb_dns_name" {
  description = "DNS name of the ALB"
  value       = aws_lb.this.dns_name
}

output "target_group_arn" {
  description = "ARN of the ALB target group"
  value       = aws_lb_target_group.this.arn
}

# 新增：task 角色
output "task_role_arn" {
  description = "IAM role ARN used by ECS tasks"
  value       = aws_iam_role.task.arn
}

# 新增：execution 角色
output "task_execution_role_arn" {
  description = "IAM execution role ARN used by ECS tasks"
  value       = aws_iam_role.execution.arn
}

output "environment_variables" {
  description = "Environment variables for the container"
  value       = var.environment_variables
}
