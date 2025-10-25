resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Name        = "vpc-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
  
  tags = {
    Name = "public-subnet-${var.environment}"
  }
  
  depends_on = [aws_vpc.main]
}

resource "aws_db_instance" "postgres" {
  identifier     = "mydb-${var.environment}"
  engine         = "postgres"
  instance_class = "db.t3.micro"
  password       = var.db_password
  vpc_id         = aws_vpc.main.id
  
  tags = {
    Environment = var.environment
  }
}
