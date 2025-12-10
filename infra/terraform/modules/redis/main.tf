resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = var.tags
}

resource "aws_security_group" "redis" {
  name        = "${var.name}-sg"
  description = "Security group for Redis ${var.name}"
  vpc_id      = var.vpc_id

  # 仅允许来自指定 SG 的 6379 访问
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = var.name
  description          = "Redis for ${var.name}"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type

  # 关闭集群模式，单节点开发环境
  automatic_failover_enabled = false

  subnet_group_name = aws_elasticache_subnet_group.this.name
  security_group_ids = [
    aws_security_group.redis.id
  ]

  at_rest_encryption_enabled  = false
  transit_encryption_enabled  = false
  apply_immediately           = true
  port                        = 6379

  tags = var.tags
}
