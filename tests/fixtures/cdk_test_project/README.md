# CDK Test Project - Python/TypeScript Parity Fixture

## Purpose
Tests AWS CDK extraction **parity** between Python and TypeScript implementations.

Contains **identical security vulnerabilities** in both languages:
- `vulnerable_stack.py` - Python CDK (aws-cdk-lib)
- `vulnerable_stack.ts` - TypeScript CDK (aws-cdk-lib)

Validates that TheAuditor extracts the **same security findings** regardless of CDK language choice.

## Security Vulnerabilities (Intentional)

### 1. Public S3 Bucket (CRITICAL)
```python
# Python
public_bucket = s3.Bucket(self, "PublicBucket",
    public_read_access=True,  # ← CRITICAL: Anyone can read
    versioned=False
)
```

```typescript
// TypeScript
const publicBucket = new s3.Bucket(this, 'PublicBucket', {
  publicReadAccess: true,  // ← CRITICAL: Anyone can read
  versioned: false
});
```

**Risk**: Sensitive data exposed to internet (e.g., customer PII, credentials, backups)

### 2. Unencrypted RDS Database (HIGH)
```python
# Python
unencrypted_db = rds.DatabaseInstance(self, "UnencryptedDB",
    engine=rds.DatabaseInstanceEngine.POSTGRES,
    storage_encrypted=False,  # ← HIGH: No encryption at rest
    instance_type=ec2.InstanceType.of(
        ec2.InstanceClass.BURSTABLE3,
        ec2.InstanceSize.MICRO
    ),
    vpc=None  # Placeholder for testing
)
```

```typescript
// TypeScript
const unencryptedDb = new rds.DatabaseInstance(this, 'UnencryptedDB', {
  engine: rds.DatabaseInstanceEngine.POSTGRES,
  storageEncrypted: false,  // ← HIGH: No encryption at rest
  instanceType: ec2.InstanceType.of(
    ec2.InstanceClass.BURSTABLE3,
    ec2.InstanceSize.MICRO
  ),
  vpc: undefined  // Placeholder for testing
});
```

**Risk**: Violates compliance (PCI-DSS 3.4, HIPAA 164.312, SOC 2)

### 3. Open Security Group (MEDIUM)
```python
# Python
open_sg = ec2.SecurityGroup(self, "OpenSecurityGroup",
    vpc=None,  # Placeholder
    allow_all_outbound=True  # ← MEDIUM: Unrestricted egress
)
```

```typescript
// TypeScript
const openSg = new ec2.SecurityGroup(this, 'OpenSecurityGroup', {
  vpc: undefined,  // Placeholder
  allowAllOutbound: true  // ← MEDIUM: Unrestricted egress
});
```

**Risk**: Allows data exfiltration if instance is compromised

## Populated Database Tables

After `aud index`:

| Table | Python Count | TypeScript Count | What It Tests |
|---|---|---|---|
| **cdk_constructs** | 3 | 3 | Construct extraction (Bucket, DatabaseInstance, SecurityGroup) |
| **cdk_construct_properties** | 9+ | 9+ | Property extraction (publicReadAccess, storageEncrypted, etc.) |
| **security_findings** | 3 | 3 | Misconfig detection (public S3, unencrypted RDS, open SG) |

**Parity Requirement**: Python and TypeScript counts MUST match exactly

## Sample Verification Queries

### Query 1: Find All CDK Constructs (Both Languages)

```sql
SELECT
    file,
    construct_type,
    construct_id
FROM cdk_constructs
WHERE file LIKE '%cdk_test_project%'
ORDER BY file, construct_id;
```

**Expected Results**:
- vulnerable_stack.py: PublicBucket (s3.Bucket), UnencryptedDB (rds.DatabaseInstance), OpenSecurityGroup (ec2.SecurityGroup)
- vulnerable_stack.ts: PublicBucket (s3.Bucket), UnencryptedDB (rds.DatabaseInstance), OpenSecurityGroup (ec2.SecurityGroup)

### Query 2: Find Public S3 Buckets (CRITICAL)

```sql
SELECT
    c.construct_id,
    c.file,
    p.property_name,
    p.property_value
FROM cdk_constructs c
JOIN cdk_construct_properties p
    ON c.construct_id = p.construct_id AND c.file = p.file
WHERE c.construct_type LIKE '%s3.Bucket%'
  AND p.property_name = 'publicReadAccess'
  AND p.property_value = 'true'
ORDER BY c.file;
```

**Expected Results**: 2 buckets (Python + TypeScript), both with `publicReadAccess=true`

### Query 3: Find Unencrypted Databases (HIGH)

```sql
SELECT
    c.construct_id,
    c.file,
    p.property_value AS encryption_status
FROM cdk_constructs c
JOIN cdk_construct_properties p
    ON c.construct_id = p.construct_id AND c.file = p.file
WHERE c.construct_type LIKE '%rds.DatabaseInstance%'
  AND p.property_name = 'storageEncrypted'
  AND p.property_value = 'false'
ORDER BY c.file;
```

**Expected Results**: 2 databases (Python + TypeScript), both with `storageEncrypted=false`

### Query 4: Verify Parity (Same Constructs in Both Languages)

```sql
SELECT
    py.construct_type,
    py.construct_id AS python_construct,
    ts.construct_id AS typescript_construct
FROM cdk_constructs py
JOIN cdk_constructs ts
    ON py.construct_type = ts.construct_type
WHERE py.file LIKE '%vulnerable_stack.py'
  AND ts.file LIKE '%vulnerable_stack.ts'
ORDER BY py.construct_type;
```

**Expected Results**: 3 matching pairs (Bucket, DatabaseInstance, SecurityGroup)

### Query 5: Count Security Findings by Language

```sql
SELECT
    CASE
        WHEN file LIKE '%.py' THEN 'Python'
        WHEN file LIKE '%.ts' THEN 'TypeScript'
    END AS language,
    COUNT(*) AS vulnerability_count
FROM cdk_construct_properties
WHERE file LIKE '%cdk_test_project%'
  AND (
    (property_name = 'publicReadAccess' AND property_value = 'true')
    OR (property_name = 'storageEncrypted' AND property_value = 'false')
    OR (property_name = 'allowAllOutbound' AND property_value = 'true')
  )
GROUP BY language;
```

**Expected Results**: Both Python and TypeScript should have 3 vulnerabilities

## Testing Use Cases

This fixture enables testing:

1. **CDK Extraction Parity**: Verify Python and TypeScript CDK extract identically
2. **Security Property Extraction**: Confirm boolean flags (true/false) are captured correctly
3. **Multi-Language Support**: Validate indexer handles both Python and TypeScript CDK syntax
4. **Construct Identification**: Test CDK construct type detection (s3.Bucket, rds.DatabaseInstance, etc.)
5. **Security Rule Consistency**: Ensure same vulnerabilities flagged in both languages

## Expected Extraction

When indexed, both `vulnerable_stack.py` and `vulnerable_stack.ts` should produce:

✅ **3 CDK Constructs**:
- PublicBucket (s3.Bucket)
- UnencryptedDB (rds.DatabaseInstance)
- OpenSecurityGroup (ec2.SecurityGroup)

✅ **3 CRITICAL/HIGH Findings**:
- publicReadAccess=true (CRITICAL)
- storageEncrypted=false (HIGH)
- allowAllOutbound=true (MEDIUM)

✅ **Parity Verification**: Python and TypeScript results MUST be identical

## How to Use

1. **Index from TheAuditor root**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Query Python CDK findings**:
   ```bash
   aud context query --file vulnerable_stack.py
   ```

3. **Query TypeScript CDK findings**:
   ```bash
   aud context query --file vulnerable_stack.ts
   ```

4. **Compare parity**:
   ```sql
   -- Run verification queries from spec.yaml
   ```

## Why This Fixture Matters

Real-world CDK projects use either Python OR TypeScript, but:
- Teams may migrate from one to the other
- Monorepos may contain both
- Security rules should apply consistently regardless of language

This fixture proves TheAuditor can detect **the same security risks** in CDK code regardless of whether developers choose Python or TypeScript.

## Project Structure

```
cdk_test_project/
├── cdk.json                 # CDK configuration
├── package.json             # TypeScript dependencies
├── tsconfig.json            # TypeScript config
├── vulnerable_stack.py      # Python CDK stack (INTENTIONALLY VULNERABLE)
├── vulnerable_stack.ts      # TypeScript CDK stack (INTENTIONALLY VULNERABLE)
├── spec.yaml                # Verification rules
└── README.md                # This file
```

## Compliance Impact

These vulnerabilities would fail:

| Vulnerability | Failed Standards |
|---|---|
| Public S3 bucket | PCI-DSS 1.2.1, HIPAA 164.312(a)(1), SOC 2 CC6.1 |
| Unencrypted RDS | PCI-DSS 3.4, HIPAA 164.312(a)(2)(iv), SOC 2 CC6.1 |
| Open security group | PCI-DSS 1.3, CIS AWS 5.2 |

TheAuditor must detect these in **both Python and TypeScript** to provide consistent security coverage.
