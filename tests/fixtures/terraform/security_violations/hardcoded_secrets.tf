resource "aws_iam_user" "bad_user" {
  name = "bad-user"
}

resource "aws_iam_access_key" "bad_key" {
  user = aws_iam_user.bad_user.name
  secret = "AKIAIOSFODNN7EXAMPLE" # This is a hardcoded secret
}
