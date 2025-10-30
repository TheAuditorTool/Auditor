# VIOLATIONS: Unencrypted storage resources
# These should be detected by terraform_security rule (_check_unencrypted_storage)

# VULN: RDS instance without storage_encrypted
resource "aws_db_instance" "unencrypted_rds" {
  allocated_storage    = 20
  engine               = "postgres"
  engine_version       = "13.7"
  instance_class       = "db.t3.micro"
  db_name              = "testdb"
  username             = "admin"
  password             = var.db_password
  skip_final_snapshot  = true
  # storage_encrypted = false  <- Missing or explicitly false (both are violations)
}

# VULN: EBS volume without encryption
resource "aws_ebs_volume" "unencrypted_ebs" {
  availability_zone = "us-east-1a"
  size              = 10
  # encrypted = false  <- Missing or explicitly false (both are violations)
}
