# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "${var.tags["Project"]}-${var.tags["Environment"]}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "alb-sg" })
}

# ECS Service Security Group
resource "aws_security_group" "ecs_service" {
  name        = "${var.tags["Project"]}-${var.tags["Environment"]}-ecs-sg"
  description = "Security group for ECS services"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id] # allow inbound only from ALB
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "ecs-sg" })
}

# Internal Worker / Redis / Milvus Security Group
resource "aws_security_group" "internal" {
  name        = "${var.tags["Project"]}-${var.tags["Environment"]}-internal-sg"
  description = "Internal communication"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    cidr_blocks     = ["10.0.0.0/8"] # internal traffic only
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "internal-sg" })
}
