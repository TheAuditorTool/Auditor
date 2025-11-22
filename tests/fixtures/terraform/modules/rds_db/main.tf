resource "aws_db_instance" "default" {
  allocated_storage    = 10
  engine               = "mysql"
  engine_version       = "5.7"
  instance_class       = "db.t3.micro"
  db_name              = "myappdb"
  username             = "admin"
  password             = var.db_password # Tainted by sensitive variable
  db_subnet_group_name = "my-db-subnet-group" # Assume this exists
  vpc_security_group_ids = var.vpc_security_group_ids
  skip_final_snapshot  = true
}
