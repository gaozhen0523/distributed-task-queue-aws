#infra/terraform/envs/dev/variables.tf
variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "distributed-task-queue-aws"
}

variable "environment" {
  description = "Environment name (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR for the VPC"
  type        = string
  default     = "10.1.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = [
    "10.1.1.0/24",
    "10.1.2.0/24"
  ]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = [
    "10.1.101.0/24",
    "10.1.102.0/24"
  ]
}

variable "ecr_repository_names" {
  description = "ECR repositories for the distributed task queue services"
  type        = list(string)
  default = [
    "dist-api",
    "dist-scheduler",
    "dist-worker"
  ]
}

variable "alert_email" {
  description = "Email address to receive CloudWatch and billing alerts"
  type        = string
  default     = "gaozhen0516@gmail.com" # TODO: 换成你自己的邮箱
}

variable "billing_threshold_usd" {
  description = "Billing alarm threshold in USD"
  type        = number
  default     = 5
}

variable "root_domain" {
  description = "Root domain name managed in Route53 (must already exist)"
  type        = string
  default     = "zhencloud.com"
}

variable "dist_api_subdomain" {
  description = "Subdomain for dist-api"
  type        = string
  default     = "dist"
}
