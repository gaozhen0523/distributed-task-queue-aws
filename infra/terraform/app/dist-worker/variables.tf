variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "image_tag" {
  type        = string
  description = "Docker image tag to deploy for dist-worker"
}

variable "task_cpu" {
  type    = number
  default = 512
}

variable "task_memory" {
  type    = number
  default = 1024
}
