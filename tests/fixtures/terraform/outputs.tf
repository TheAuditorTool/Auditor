output "web_instance_id" {
  description = "ID of the web instance"
  value       = aws_instance.web.id # Resource attribute
}

output "vpc_id" {
  description = "ID of the VPC created by the module"
  value       = module.networking.vpc_id # Module output
}

output "app_name_passthrough" {
  description = "Pass-through of the app_name variable"
  value       = var.app_name # Variable reference
}
