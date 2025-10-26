variable "environment" {
  type        = string
  description = "Environment name"
  default     = "dev"
}

variable "db_password" {
  type        = string
  description = "Database master password"
  sensitive   = true
}

variable "region" {
  type    = string
  default = "us-east-1"
}
