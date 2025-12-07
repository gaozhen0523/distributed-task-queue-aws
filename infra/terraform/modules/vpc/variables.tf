variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Whether to create a single NAT gateway"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Base tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "availability_zones" {
  type = list(string)
}
