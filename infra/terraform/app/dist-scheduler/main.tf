terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "distributed-task-queue-tfstate"
    key            = "app/dist-scheduler.tfstate"
    region         = "us-east-1"
    dynamodb_table = "distributed-task-queue-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

# 读取 dev 层 remote state
data "terraform_remote_state" "dev" {
  backend = "s3"
  config = {
    bucket = "distributed-task-queue-tfstate"
    key    = "envs/dev/terraform.tfstate"
    region = "us-east-1"
  }
}

locals {
  dev_outputs = data.terraform_remote_state.dev.outputs

  # dev 里 map(string) → list(object{name,value})
  environment = [
    for k, v in local.dev_outputs.dist_scheduler_environment_variables :
    {
      name  = k
      value = v
    }
  ]
}

resource "aws_ecs_task_definition" "dist_scheduler" {
  family                   = "dist-scheduler"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]

  execution_role_arn = local.dev_outputs.dist_scheduler_task_execution_role_arn
  task_role_arn      = local.dev_outputs.dist_scheduler_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "dist-scheduler"
      image     = "${local.dev_outputs.ecr_repository_urls["dist-scheduler"]}:${var.image_tag}"
      essential = true

      environment = local.environment

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/dist-scheduler"
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# 给 GitHub Actions 用的输出
output "task_definition_arn" {
  description = "New ECS task definition ARN for dist-scheduler"
  value       = aws_ecs_task_definition.dist_scheduler.arn
}

output "ecs_cluster_name" {
  value = local.dev_outputs.ecs_cluster_name
}

output "dist_scheduler_service_name" {
  value = local.dev_outputs.dist_scheduler_service_name
}
