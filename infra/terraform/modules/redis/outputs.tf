output "redis_endpoint" {
  description = "Redis 主节点访问地址"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "security_group_id" {
  description = "Redis 安全组 ID"
  value       = aws_security_group.redis.id
}
