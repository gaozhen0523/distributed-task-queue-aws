variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "tags" {
  description = "Base tags for ECS cluster"
  type        = map(string)
  default     = {}
}
