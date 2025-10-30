# This output exposes a sensitive variable, and is NOT marked sensitive
# This is a critical taint-tracking finding
output "database_password" {
  value = var.db_password
  # sensitive = true  <-- This is missing!
}
