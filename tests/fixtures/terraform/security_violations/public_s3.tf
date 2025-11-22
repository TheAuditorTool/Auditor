resource "aws_s3_bucket" "public_read" {
  bucket = "my-public-read-bucket-for-testing"
  acl    = "public-read" # This is the violation
}
