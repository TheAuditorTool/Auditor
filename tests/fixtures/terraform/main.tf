# Call a local module and pass in variables
module "networking" {
  source      = "./modules/vpc"
  app_name    = var.app_name
  common_tags = var.common_tags
}

# Call a module from the Terraform Registry
module "public_s3_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "3.15.1"

  bucket = "${var.app_name}-registry-bucket"
  acl    = "private"
}

# Call another local module with complex dependencies
module "database" {
  source           = "./modules/rds_db"
  db_password      = var.db_password # Tainted: sensitive var
  subnet_ids       = module.networking.private_subnets # Module-to-module dependency
  vpc_security_group_ids = [module.networking.db_sg_id]
}

# Resource with implicit dependency (via interpolation)
resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t2.micro"
  subnet_id     = module.networking.public_subnets[0] # Depends on module
  tags          = merge(
    var.common_tags,
    {
      "Name" = "${var.app_name}-web-instance" # Interpolation
    }
  )
}

# Resource with explicit dependency
resource "null_resource" "app_provisioner" {
  depends_on = [aws_instance.web]

  provisioner "local-exec" {
    command = "echo 'Instance is up'"
  }
}

# Resource with for_each
resource "aws_route53_record" "app_records" {
  for_each = toset(["primary", "secondary"])
  zone_id  = "Z0123456789ABCDEFGHIJ"
  name     = "${each.key}.${var.app_name}.example.com"
  type     = "A"
  records  = [aws_instance.web.primary_ip] # Fictional attribute for testing
}
