variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "allowed_cidrs" {
  type        = list(string)
  description = "Allowed CIDRs for inbound traffic"
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  type        = map(string)
  default     = {}
}
