# Terraform Security Test Fixtures

Intentionally vulnerable Terraform configurations for testing infrastructure-as-code (IaC) security analysis.

## Purpose

Tests TheAuditor's ability to detect common Terraform security misconfigurations across AWS resources. Each vulnerability represents a real-world security risk that should be flagged by static analysis.

## File Structure

```
terraform_test/
├── main.tf          # Base Terraform configuration
├── variables.tf     # Input variable declarations
├── outputs.tf       # Output value declarations
├── vulnerable.tf    # Vulnerable resource definitions (test target)
├── spec.yaml        # Verification rules
└── README.md        # This file
```

## Vulnerability Patterns

### 1. Public S3 Bucket (CRITICAL)

**File**: `vulnerable.tf:4-7`

```hcl
resource "aws_s3_bucket" "public_data" {
  bucket = "my-public-bucket"
  acl    = "public-read"  # ← CRITICAL: Anyone can read bucket
}
```

**Risk**: Sensitive data (credentials, PII, backups) exposed to internet

**Detection Rule**: Flag `acl = "public-read"` on s3_bucket resources

**Compliance Impact**:
- PCI-DSS 1.2.1 (restrict public access)
- HIPAA 164.312(a)(1) (access controls)
- SOC 2 CC6.1 (logical access)

---

### 2. Unencrypted Database (HIGH)

**File**: `vulnerable.tf:10-15`

```hcl
resource "aws_db_instance" "unencrypted_db" {
  identifier     = "mydb"
  engine         = "postgres"
  instance_class = "db.t3.micro"
  storage_encrypted = false  # ← HIGH: No encryption at rest
}
```

**Risk**: Database contents readable if storage media is compromised

**Detection Rule**: Flag `storage_encrypted = false` on aws_db_instance

**Compliance Impact**:
- PCI-DSS 3.4 (encrypt stored data)
- HIPAA 164.312(a)(2)(iv) (encryption)
- SOC 2 CC6.1 (data encryption)

---

### 3. Hardcoded Password (CRITICAL)

**File**: `vulnerable.tf:18-24`

```hcl
resource "aws_db_instance" "hardcoded_secret" {
  identifier     = "secret-db"
  engine         = "postgres"
  instance_class = "db.t3.micro"
  password       = "MyHardcodedPassword123!"  # ← CRITICAL: Credential in code
}
```

**Risk**:
- Password committed to version control (Git history)
- Visible to anyone with code access
- Can't rotate without code changes

**Detection Rule**: Flag literal string values in `password`, `secret`, `token` attributes

**Best Practice**: Use AWS Secrets Manager or `random_password` resource

---

### 4. IAM Wildcard Policy (HIGH)

**File**: `vulnerable.tf:27-38`

```hcl
resource "aws_iam_policy" "admin_policy" {
  name = "admin-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"        # ← HIGH: All actions
      Resource = "*"        # ← HIGH: All resources
    }]
  })
}
```

**Risk**: Principal with this policy has full AWS account access (privilege escalation)

**Detection Rule**: Flag `Action = "*"` AND `Resource = "*"` in IAM policies

**Compliance Impact**:
- CIS AWS 1.22 (least privilege)
- SOC 2 CC6.3 (authorization)

---

### 5. Security Group Open to World (MEDIUM)

**File**: `vulnerable.tf:41-51`

```hcl
resource "aws_security_group" "open_sg" {
  name = "open-security-group"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # ← MEDIUM: SSH open to internet
  }
}
```

**Risk**: SSH brute-force attacks, unauthorized access

**Detection Rule**: Flag `cidr_blocks = ["0.0.0.0/0"]` on sensitive ports (22, 3389, 3306, 5432, etc.)

**Compliance Impact**:
- PCI-DSS 1.3 (restrict connections)
- CIS AWS 5.2 (restrict SSH)

## Expected Detections

When TheAuditor analyzes this Terraform project, it should find:

| Vulnerability | Severity | Resource | Line | Rule |
|---|---|---|---|---|
| Public S3 bucket | CRITICAL | aws_s3_bucket.public_data | 6 | s3-public-read |
| Unencrypted database | HIGH | aws_db_instance.unencrypted_db | 14 | rds-unencrypted |
| Hardcoded password | CRITICAL | aws_db_instance.hardcoded_secret | 22 | hardcoded-secret |
| IAM wildcard policy | HIGH | aws_iam_policy.admin_policy | 31-35 | iam-wildcard-policy |
| Open security group | MEDIUM | aws_security_group.open_sg | 49 | sg-open-to-world |

**Total Expected Findings**: 5

## Sample Verification Queries

### Query 1: Find All Terraform Resources

```sql
SELECT
    resource_type,
    resource_name,
    file
FROM terraform_resources
WHERE file LIKE '%terraform_test%'
ORDER BY resource_type;
```

**Expected Results**: 5 resources (s3_bucket, 2x db_instance, iam_policy, security_group)

### Query 2: Find Public S3 Buckets

```sql
SELECT
    tr.resource_name,
    ta.attribute_name,
    ta.attribute_value
FROM terraform_resources tr
JOIN terraform_attributes ta
    ON tr.resource_id = ta.resource_id
WHERE tr.resource_type = 'aws_s3_bucket'
  AND ta.attribute_name = 'acl'
  AND ta.attribute_value = 'public-read';
```

**Expected Results**: 1 bucket (public_data)

### Query 3: Find Unencrypted Databases

```sql
SELECT
    tr.resource_name,
    ta.attribute_value AS encryption_status
FROM terraform_resources tr
JOIN terraform_attributes ta
    ON tr.resource_id = ta.resource_id
WHERE tr.resource_type = 'aws_db_instance'
  AND ta.attribute_name = 'storage_encrypted'
  AND ta.attribute_value = 'false';
```

**Expected Results**: 1 database (unencrypted_db)

### Query 4: Find Hardcoded Secrets

```sql
SELECT
    tr.resource_type,
    tr.resource_name,
    ta.attribute_name,
    ta.line
FROM terraform_resources tr
JOIN terraform_attributes ta
    ON tr.resource_id = ta.resource_id
WHERE ta.attribute_name IN ('password', 'secret_key', 'api_token')
  AND ta.attribute_value NOT LIKE 'var.%'
  AND ta.attribute_value NOT LIKE 'data.%';
```

**Expected Results**: 1 hardcoded password (hardcoded_secret)

### Query 5: Find IAM Wildcard Policies

```sql
SELECT
    tr.resource_name,
    ta.attribute_value
FROM terraform_resources tr
JOIN terraform_attributes ta
    ON tr.resource_id = ta.resource_id
WHERE tr.resource_type = 'aws_iam_policy'
  AND ta.attribute_name = 'policy'
  AND ta.attribute_value LIKE '%"Action"%:%"*"%'
  AND ta.attribute_value LIKE '%"Resource"%:%"*"%';
```

**Expected Results**: 1 policy (admin_policy)

## How to Use This Fixture

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Run Terraform Security Analysis

```bash
# Run all security rules
aud detect-patterns --file tests/terraform_test/vulnerable.tf

# Run specific rule
aud detect-patterns --rule terraform-s3-public --file tests/terraform_test/
```

### 3. Query Extracted Data

```bash
aud context query --file vulnerable.tf
```

### 4. Verify Expected Findings

```sql
-- Count findings by severity
SELECT severity, COUNT(*)
FROM findings
WHERE file LIKE '%terraform_test%'
GROUP BY severity;
```

## Testing Use Cases

This fixture enables testing:

1. **Terraform Parsing**: Verify HCL parser extracts resources correctly
2. **Attribute Extraction**: Confirm nested JSON attributes in policies are parsed
3. **Security Rule Coverage**: Validate all 5 vulnerability patterns are detected
4. **False Positive Rate**: Ensure no false positives on main.tf, variables.tf, outputs.tf
5. **Severity Classification**: Verify correct severity levels (CRITICAL, HIGH, MEDIUM)

## Adding New Vulnerability Patterns

To add a new Terraform vulnerability test:

1. **Add resource** to `vulnerable.tf`:
   ```hcl
   resource "aws_resource_type" "vulnerable_name" {
     # Vulnerable configuration
   }
   ```

2. **Document vulnerability** in this README with:
   - Code snippet
   - Risk description
   - Detection rule
   - Compliance impact

3. **Add verification query** to spec.yaml

4. **Update expected findings** table above

## Related Terraform Best Practices

**DO**:
- ✅ Use `storage_encrypted = true` for databases
- ✅ Store secrets in AWS Secrets Manager
- ✅ Use least-privilege IAM policies
- ✅ Restrict security groups to specific CIDR blocks
- ✅ Set S3 buckets to private by default

**DON'T**:
- ❌ Use `acl = "public-read"` on S3 buckets
- ❌ Hardcode passwords, tokens, or API keys
- ❌ Use wildcard `*` in IAM policies
- ❌ Allow `0.0.0.0/0` on SSH/RDP ports
- ❌ Disable encryption on databases or storage

## Compliance Mapping

| Pattern | PCI-DSS | HIPAA | SOC 2 | CIS AWS |
|---|---|---|---|---|
| Public S3 | 1.2.1 | 164.312(a)(1) | CC6.1 | 2.1.5 |
| Unencrypted DB | 3.4 | 164.312(a)(2)(iv) | CC6.1 | 2.3.1 |
| Hardcoded Secret | 8.2.1 | 164.308(a)(5)(ii)(D) | CC6.1 | 1.12 |
| IAM Wildcard | 7.1 | 164.308(a)(3)(i) | CC6.3 | 1.22 |
| Open SSH | 1.3 | 164.312(e)(1) | CC6.6 | 5.2 |

## Why This Fixture Matters

Terraform is ubiquitous in cloud infrastructure:
- **97% of cloud teams** use IaC (Terraform, CloudFormation, etc.)
- **Average org**: 1000+ Terraform resources across 50+ modules
- **Common issues**: 60% of breaches involve misconfigured cloud resources

If TheAuditor can't detect these patterns in Terraform, it misses:
- Most cloud security vulnerabilities
- Compliance violations before deployment
- Infrastructure drift and configuration errors

**This fixture validates TheAuditor can secure cloud infrastructure as code.**

---

**Vulnerability Count**: 5 patterns (CRITICAL: 2, HIGH: 2, MEDIUM: 1)
**Lines of Code**: ~50 lines of vulnerable Terraform
**Compliance Standards**: PCI-DSS, HIPAA, SOC 2, CIS AWS Benchmarks
