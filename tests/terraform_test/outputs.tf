output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "db_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "Database endpoint"
  sensitive   = true
}

output "environment_name" {
  value       = var.environment
  description = "Current environment"
}
