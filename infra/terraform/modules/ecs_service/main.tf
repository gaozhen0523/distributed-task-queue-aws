locals {
  name_prefix = "${var.service_name}"
  tags        = var.tags

  env_vars = [
    for k, v in var.environment_variables :
    {
      name  = k
      value = v
    }
  ]
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 14

  tags = local.tags
}

# IAM: task execution role (pull image, push logs)
data "aws_iam_policy_document" "execution_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name_prefix}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.execution_assume_role.json
  tags               = local.tags
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM: task role (业务访问权限，先占位空角色，后续可加 S3/Redis 等)
data "aws_iam_policy_document" "task_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-task-role"
  assume_role_policy = data.aws_iam_policy_document.task_assume_role.json
  tags               = local.tags
}

# Task Definition
resource "aws_ecs_task_definition" "this" {
  family                   = local.name_prefix
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = local.name_prefix
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = local.env_vars

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = local.name_prefix
        }
      }

      # prod 环境不要用 --reload，这里直接用 uvicorn 正式启动
      command = [
        "uvicorn",
        "services.api_gateway.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        tostring(var.container_port)
      ]
    }
  ])
}

data "aws_region" "current" {}

# ALB
resource "aws_lb" "this" {
  name               = "${local.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false

  security_groups = [var.alb_security_group_id]
  subnets         = var.public_subnet_ids

  tags = merge(local.tags, { Name = "${local.name_prefix}-alb" })
}

# Target Group
resource "aws_lb_target_group" "this" {
  name     = "${substr(local.name_prefix, 0, 20)}-tg" # TG 名称有长度限制
  port     = var.container_port
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path
    port                = "traffic-port"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
    interval            = 30
    timeout             = 5
    protocol            = "HTTP"
  }

  tags = merge(local.tags, { Name = "${local.name_prefix}-tg" })
}

# Listener HTTP 80
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

# ECS Service
resource "aws_ecs_service" "this" {
  name            = local.name_prefix
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = var.security_group_ids

    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = local.name_prefix
    container_port   = var.container_port
  }

  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }

  depends_on = [
    aws_lb_listener.http
  ]

  tags = local.tags
}
