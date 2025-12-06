variable "repository_names" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "tags" {
  description = "Base tags for ECR repositories"
  type        = map(string)
  default     = {}
}
