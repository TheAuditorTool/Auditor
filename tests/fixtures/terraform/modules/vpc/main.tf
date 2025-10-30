resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags       = merge(var.common_tags, { "Name" = "${var.app_name}-vpc" })
}

resource "aws_subnet" "public" {
  count      = 2
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.${count.index}.0/24"
}

resource "aws_subnet" "private" {
  count      = 2
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.${100 + count.index}.0/24"
}

resource "aws_security_group" "db_sg" {
  name   = "${var.app_name}-db-sg"
  vpc_id = aws_vpc.main.id
}
