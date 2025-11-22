# VIOLATION: SNS topic without KMS encryption
# Should be detected by terraform_security rule (_check_missing_encryption)

resource "aws_sns_topic" "unencrypted_notifications" {
  name = "app-notifications"
  # kms_master_key_id = aws_kms_key.example.id  <- Missing KMS encryption
}
