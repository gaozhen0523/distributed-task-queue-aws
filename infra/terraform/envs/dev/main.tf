terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 后面如果你想用 remote state (S3 + DynamoDB)，可以在这里加 backend "s3" 块
}

provider "aws" {
  region = var.aws_region
}

locals {
  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

module "vpc" {
  source = "../../modules/vpc"

  vpc_cidr            = var.vpc_cidr
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones = ["us-east-1a", "us-east-1c"]

  enable_nat_gateway = true
  tags               = local.tags
}

module "ecs_cluster" {
  source = "../../modules/ecs_cluster"

  cluster_name = "${var.project_name}-${var.environment}-cluster"
  tags         = local.tags
}

module "ecr" {
  source = "../../modules/ecr"

  repository_names = var.ecr_repository_names
  tags             = local.tags
}

module "sg" {
  source = "../../modules/sg"

  vpc_id        = module.vpc.vpc_id
  allowed_cidrs = ["0.0.0.0/0"]
  tags          = local.tags
}
