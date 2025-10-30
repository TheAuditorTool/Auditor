data "aws_iam_policy_document" "wildcard_policy" {
  statement {
    effect    = "Allow"
    actions   = ["*"]       # Violation
    resources = ["*"]       # Violation
  }
}

resource "aws_iam_policy" "wildcard" {
  name   = "wildcard-policy"
  policy = data.aws_iam_policy_document.wildcard_policy.json
}
