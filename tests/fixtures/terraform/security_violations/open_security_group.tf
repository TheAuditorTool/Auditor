# VIOLATIONS: Security groups with overly permissive ingress rules
# Should be detected by terraform_security rule (_check_security_groups)

# VULN: Security group allowing SSH from anywhere
resource "aws_security_group" "allow_ssh_from_anywhere" {
  name        = "allow_ssh_0.0.0.0"
  description = "Allow SSH from anywhere (BAD!)"
  vpc_id      = "vpc-12345678"

  ingress {
    description = "SSH from internet"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # CRITICAL VULN
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# VULN: Security group with multiple ports open to internet (including HTTP/HTTPS)
resource "aws_security_group" "open_web_server" {
  name        = "open_web_server"
  description = "Web server with open ingress"
  vpc_id      = "vpc-12345678"

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # MEDIUM severity (HTTP is expected to be public sometimes)
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # MEDIUM severity (HTTPS is expected to be public sometimes)
  }

  ingress {
    description = "Custom app port from internet"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # HIGH severity (custom ports shouldn't be open)
  }
}
