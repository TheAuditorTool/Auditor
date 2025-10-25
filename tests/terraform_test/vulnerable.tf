# Vulnerable Terraform configuration for testing

# ISSUE: Public S3 bucket
resource "aws_s3_bucket" "public_data" {
  bucket = "my-public-bucket"
  acl    = "public-read"
}

# ISSUE: Unencrypted database
resource "aws_db_instance" "unencrypted_db" {
  identifier     = "mydb"
  engine         = "postgres"
  instance_class = "db.t3.micro"
  storage_encrypted = false
}

# ISSUE: Hardcoded password
resource "aws_db_instance" "hardcoded_secret" {
  identifier     = "secret-db"
  engine         = "postgres"
  instance_class = "db.t3.micro"
  password       = "MyHardcodedPassword123!"
}

# ISSUE: IAM wildcard policy
resource "aws_iam_policy" "admin_policy" {
  name = "admin-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# ISSUE: Security group open to world
resource "aws_security_group" "open_sg" {
  name = "open-security-group"
  
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
