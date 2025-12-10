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

output "dist_scheduler_alb_dns_name" {
  value = module.dist_scheduler_service.alb_dns_name
}

output "dist_worker_alb_dns_name" {
  value = module.dist_worker_service.alb_dns_name
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint for this environment"
  value       = module.redis.redis_endpoint
}
