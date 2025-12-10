variable "name" {
  description = "Redis 集群名称前缀（用于 replication group id 等）"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Redis 所在子网（建议用 private subnets）"
  type        = list(string)
}

variable "allowed_security_group_ids" {
  description = "允许访问 Redis 的安全组（例如 ECS service SG）"
  type        = list(string)
}

variable "engine_version" {
  description = "Redis 引擎版本"
  type        = string
  default     = "7.1"
}

variable "node_type" {
  description = "Redis 节点实例类型"
  type        = string
  default     = "cache.t3.micro"
}

variable "tags" {
  description = "公共标签"
  type        = map(string)
  default     = {}
}
