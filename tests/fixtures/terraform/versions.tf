terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    null = {
      source = "hashicorp/null"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket = "my-tf-state-bucket"
    key    = "global/s3/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
  }
}
