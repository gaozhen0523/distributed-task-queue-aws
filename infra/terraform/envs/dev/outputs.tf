#infra/terraform/envs/dev/outputs.tf
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs_cluster.cluster_name
}

output "ecr_repository_urls" {
  description = "Map of ECR repository URLs"
  value       = module.ecr.repository_urls
}

output "dist_api_alb_dns_name" {
  value = module.dist_api_service.alb_dns_name
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint for this environment"
  value       = module.redis.redis_endpoint
}


output "dist_api_task_role_arn" {
  description = "Task IAM role ARN for distributed-task-queue"
  value       = module.dist_api_service.task_role_arn
}

output "dist_api_task_execution_role_arn" {
  description = "Task execution IAM role ARN for distributed-task-queue"
  value       = module.dist_api_service.task_execution_role_arn
}

output "dist_api_service_name" {
  description = "ECS service name for distributed-task-queue"
  value       = module.dist_api_service.service_name
}

output "dist_api_environment_variables" {
  description = "Env vars for dist-api ECS service"
  value       = module.dist_api_service.environment_variables
  sensitive = true
}

# dist-scheduler ECS outputs
output "dist_scheduler_service_name" {
  value = module.dist_scheduler_service.service_name
}

output "dist_scheduler_task_definition_arn" {
  value = module.dist_scheduler_service.task_definition_arn
}

output "dist_scheduler_task_role_arn" {
  value = module.dist_scheduler_service.task_role_arn
}

output "dist_scheduler_task_execution_role_arn" {
  value = module.dist_scheduler_service.task_execution_role_arn
}

output "dist_scheduler_environment_variables" {
  value     = module.dist_scheduler_service.environment_variables
  sensitive = true
}

# dist-worker ECS outputs
output "dist_worker_service_name" {
  value = module.dist_worker_service.service_name
}

output "dist_worker_task_definition_arn" {
  value = module.dist_worker_service.task_definition_arn
}

output "dist_worker_task_role_arn" {
  value = module.dist_worker_service.task_role_arn
}

output "dist_worker_task_execution_role_arn" {
  value = module.dist_worker_service.task_execution_role_arn
}

output "dist_worker_environment_variables" {
  value     = module.dist_worker_service.environment_variables
  sensitive = true
}

output "github_actions_role_arn" {
  description = "IAM Role ARN for GitHub Actions OIDC"
  value       = aws_iam_role.github_actions.arn
}
