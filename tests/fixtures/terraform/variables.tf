variable "app_name" {
  description = "Name of the application"
  type        = string
  default     = "myapp"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {
    "Environment" = "dev"
    "Project"     = "Terraform Fixture"
  }
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true # This is critical for taint tracking
  # No default, will be provided by .tfvars
}

variable "instance_count" {
  description = "Number of instances"
  type        = number
  default     = 1
}

variable "ami_id_list" {
  description = "List of AMIs"
  type        = list(string)
  default     = ["ami-123", "ami-456"]
}
