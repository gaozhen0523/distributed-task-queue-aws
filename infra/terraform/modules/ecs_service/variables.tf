variable "service_name" {
  description = "Name of the ECS service and task family"
  type        = string
}

variable "cluster_arn" {
  description = "ARN of the ECS cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for ALB target group"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets for ECS tasks"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnets for ALB"
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups attached to ECS tasks"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group for ALB"
  type        = string
}

variable "container_image" {
  description = "Container image for the ECS task"
  type        = string
}

variable "container_port" {
  description = "Container port exposed by the task"
  type        = number
}

variable "task_cpu" {
  description = "CPU units for the task definition (e.g. 256, 512, 1024)"
  type        = number
}

variable "task_memory" {
  description = "Memory for the task definition (MiB)"
  type        = number
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "health_check_path" {
  description = "Health check path for ALB target group"
  type        = string
  default     = "/health"
}

variable "environment_variables" {
  description = "Environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
