# Capability: AWS CDK Infrastructure-as-Code Security Analysis

**Capability ID**: `cdk-analysis`
**Version**: 1.0.0
**Status**: Proposed
**Category**: Security Analysis

---

## Overview

This specification defines TheAuditor's capability to analyze AWS Cloud Development Kit (CDK) Python code for infrastructure security misconfigurations. The system extracts CDK construct definitions from Python AST, stores them in a normalized database schema, and applies security detection rules to identify vulnerabilities before deployment.

---

## ADDED Requirements

### Requirement: CDK Construct Extraction from Python AST

The system SHALL extract AWS CDK construct instantiations from Python source code using AST parsing.

#### Scenario: S3 Bucket Construct Extraction
- **WHEN** parsing Python file containing:
  ```python
  from aws_cdk import aws_s3 as s3
  bucket = s3.Bucket(self, "MyBucket", public_read_access=True)
  ```
- **THEN** extract:
  - Construct class: `s3.Bucket`
  - Construct name: `MyBucket`
  - Line number: 2
  - Properties: `[{name: 'public_read_access', value_expr: 'True', line: 2}]`

#### Scenario: Multiple Constructs in Single File
- **WHEN** parsing Python file containing 3 different CDK constructs
- **THEN** extract all 3 constructs with unique construct_ids
- **AND** each property linked to correct construct via construct_id foreign key

#### Scenario: Nested Property Values
- **WHEN** construct has property `encryption=s3.BucketEncryption.UNENCRYPTED`
- **THEN** serialize property value as string: `"s3.BucketEncryption.UNENCRYPTED"`
- **AND** use `ast.unparse()` for serialization (no string manipulation)

#### Scenario: Missing Construct Name
- **WHEN** CDK construct instantiated without explicit name argument
- **THEN** extract construct_name as `None` (nullable field)
- **AND** still generate unique construct_id using file:line:class

#### Scenario: Non-CDK Python File
- **WHEN** Python file has no `import aws_cdk` statement
- **THEN** skip CDK extraction entirely (zero overhead)
- **AND** leave cdk_constructs table empty for that file

---

### Requirement: Normalized Database Schema for CDK Constructs

The system SHALL store extracted CDK constructs in a normalized database schema with separate tables for constructs and properties.

#### Scenario: cdk_constructs Table Structure
- **WHEN** schema is created
- **THEN** table has columns:
  - `construct_id` (TEXT, PRIMARY KEY)
  - `file_path` (TEXT, NOT NULL)
  - `line` (INTEGER, NOT NULL)
  - `cdk_class` (TEXT, NOT NULL)
  - `construct_name` (TEXT, nullable)
- **AND** indexes on: `file_path`, `cdk_class`

#### Scenario: cdk_construct_properties Table Structure
- **WHEN** schema is created
- **THEN** table has columns:
  - `id` (INTEGER, PRIMARY KEY, autoincrement)
  - `construct_id` (TEXT, NOT NULL, foreign key)
  - `property_name` (TEXT, NOT NULL)
  - `property_value_expr` (TEXT, NOT NULL)
  - `line` (INTEGER, NOT NULL)
- **AND** indexes on: `construct_id`, `property_name`

#### Scenario: Composite Primary Key for Constructs
- **WHEN** generating construct_id
- **THEN** use format: `{file_path}::L{line}::{cdk_class}::{construct_name}`
- **AND** ensure uniqueness across entire project

#### Scenario: Batch Database Writes
- **WHEN** writing 500 CDK constructs
- **THEN** use batched inserts with 200 records per batch
- **AND** match existing DatabaseManager pattern

---

### Requirement: Public S3 Bucket Detection

The system SHALL detect S3 buckets with public read access enabled.

#### Scenario: Detect Explicit Public Read Access
- **WHEN** S3 Bucket has property `public_read_access=True`
- **THEN** create CRITICAL severity finding
- **AND** message: "S3 bucket {name} has public read access enabled"
- **AND** CWE: CWE-732

#### Scenario: Ignore Private Buckets
- **WHEN** S3 Bucket has property `public_read_access=False`
- **THEN** create no finding (bucket is private)

#### Scenario: Detect Missing Block Public Access
- **WHEN** S3 Bucket has no `block_public_access` property
- **THEN** create HIGH severity finding
- **AND** message: "S3 bucket {name} missing block_public_access configuration"

#### Scenario: Ignore Buckets with Block Public Access
- **WHEN** S3 Bucket has `block_public_access=s3.BlockPublicAccess.BLOCK_ALL`
- **THEN** create no finding (bucket protected)

---

### Requirement: Unencrypted Storage Detection

The system SHALL detect cloud storage resources without encryption at rest.

#### Scenario: Detect Unencrypted RDS Instance
- **WHEN** RDS DatabaseInstance has no `storage_encrypted` property
- **OR** property value is `False`
- **THEN** create HIGH severity finding
- **AND** message: "RDS instance {name} does not have storage encryption enabled"
- **AND** CWE: CWE-311

#### Scenario: Detect Unencrypted EBS Volume
- **WHEN** EBS Volume has no `encrypted` property
- **OR** property value is `False`
- **THEN** create HIGH severity finding
- **AND** message: "EBS volume {name} is not encrypted"

#### Scenario: Detect Unencrypted DynamoDB Table
- **WHEN** DynamoDB Table has no `encryption` property
- **OR** property value is `dynamodb.TableEncryption.DEFAULT`
- **THEN** create MEDIUM severity finding
- **AND** message: "DynamoDB table {name} using default encryption (not customer-managed)"

#### Scenario: Ignore Encrypted Resources
- **WHEN** RDS DatabaseInstance has `storage_encrypted=True`
- **THEN** create no finding (encryption enabled)

---

### Requirement: Open Security Group Detection

The system SHALL detect security groups allowing unrestricted ingress traffic.

#### Scenario: Detect 0.0.0.0/0 Ingress Rule
- **WHEN** SecurityGroup has ingress rule with `peer` containing `0.0.0.0/0`
- **THEN** create CRITICAL severity finding
- **AND** message: "Security group {name} allows unrestricted ingress from 0.0.0.0/0"
- **AND** CWE: CWE-284

#### Scenario: Detect ::/0 IPv6 Ingress Rule
- **WHEN** SecurityGroup has ingress rule with `peer` containing `::/0`
- **THEN** create CRITICAL severity finding
- **AND** message: "Security group {name} allows unrestricted IPv6 ingress from ::/0"

#### Scenario: Ignore Restricted Ingress
- **WHEN** SecurityGroup has ingress rule with specific CIDR (e.g., `10.0.0.0/8`)
- **THEN** create no finding (restricted access)

#### Scenario: Detect Allow All Outbound
- **WHEN** SecurityGroup has `allow_all_outbound=True`
- **THEN** create LOW severity finding (informational - common pattern but worth flagging)

---

### Requirement: IAM Wildcard Permission Detection

The system SHALL detect IAM policies with overly permissive wildcard actions or resources.

#### Scenario: Detect Wildcard Action
- **WHEN** IAM Policy has `actions` property containing `'*'`
- **THEN** create HIGH severity finding
- **AND** message: "IAM policy {name} grants wildcard actions (*)"
- **AND** CWE: CWE-269

#### Scenario: Detect Wildcard Resource
- **WHEN** IAM Policy has `resources` property containing `'*'`
- **THEN** create HIGH severity finding
- **AND** message: "IAM policy {name} grants access to all resources (*)"

#### Scenario: Detect Admin Policy Attachment
- **WHEN** IAM Role attached to policy with name containing `AdministratorAccess`
- **THEN** create CRITICAL severity finding
- **AND** message: "IAM role {name} has AdministratorAccess policy attached"

#### Scenario: Ignore Least Privilege Policies
- **WHEN** IAM Policy has specific actions and resources (no wildcards)
- **THEN** create no finding (follows least privilege)

---

### Requirement: Auto-Discovery via Rules Orchestrator

The system SHALL automatically discover CDK rules without manual registration.

#### Scenario: Rule Discovery at Runtime
- **WHEN** RulesOrchestrator initializes
- **THEN** scan `theauditor/rules/deployment/` directory
- **AND** find all files matching pattern `aws_cdk_*_analyze.py`
- **AND** detect `analyze(context: StandardRuleContext)` signature
- **AND** add to rules registry

#### Scenario: Metadata-Based Filtering
- **WHEN** rule has `METADATA` with `target_extensions=['.py']`
- **THEN** only execute rule on Python files
- **AND** skip all non-Python files

#### Scenario: Execution Scope Optimization
- **WHEN** rule has `METADATA` with `execution_scope='database'`
- **THEN** run rule ONCE per project (not per file)
- **AND** query database tables directly

---

### Requirement: Pipeline Integration in Stage 2

The system SHALL integrate CDK analysis into the existing 4-stage pipeline at Stage 2 (Data Preparation).

#### Scenario: CDK Analysis Execution Order
- **WHEN** running `aud full` pipeline
- **THEN** execute commands in order:
  1. `index` (Stage 1)
  2. `graph build-dfg` (Stage 2)
  3. `terraform provision` (Stage 2)
  4. **`cdk analyze` (Stage 2)** ← NEW
  5. `graph analyze` (Stage 2)
  6. `taint-analyze` (Stage 3A)
  7. `fce` (Stage 4)

#### Scenario: CDK Findings Written to Consolidated Table
- **WHEN** CDK analysis completes
- **THEN** write findings to `cdk_findings` table
- **AND** write findings to `findings_consolidated` table with `tool='cdk'`
- **AND** findings available for FCE correlation

#### Scenario: Pipeline Continues on Zero CDK Findings
- **WHEN** project has no CDK code
- **THEN** CDK analyzer returns empty list
- **AND** pipeline continues to next stage (no errors)

---

### Requirement: CLI Command Interface

The system SHALL provide a command-line interface for CDK analysis.

#### Scenario: Run Full CDK Analysis
- **WHEN** user runs `aud cdk analyze`
- **THEN** execute all CDK security rules
- **AND** display findings count
- **AND** return exit code 0 if clean, 1 if findings, 2 if critical findings

#### Scenario: Run Category-Specific Analysis
- **WHEN** user runs `aud cdk analyze --category deployment`
- **THEN** execute only CDK rules in `deployment` category
- **AND** skip rules in other categories

#### Scenario: Error on Missing Database
- **WHEN** user runs `aud cdk analyze` without prior indexing
- **THEN** display error: "Database not found. Run `aud index` first."
- **AND** return exit code 1

---

### Requirement: Zero Fallback Policy Compliance

The system SHALL follow TheAuditor's NO FALLBACKS architecture prohibition.

#### Scenario: Hard Fail on Missing Table
- **WHEN** CDK rule queries `cdk_constructs` table
- **AND** table does not exist
- **THEN** allow exception to propagate (crash)
- **AND** do NOT catch exception
- **AND** do NOT check table existence
- **REASONING**: Schema contract guarantees table exists; missing table indicates bug

#### Scenario: Empty Results on No CDK Code
- **WHEN** CDK rule queries `cdk_constructs` table
- **AND** table exists but is empty
- **THEN** return empty findings list (graceful - not a bug)

#### Scenario: No Regex on File Content
- **WHEN** detecting CDK patterns
- **THEN** use database queries ONLY
- **AND** never use regex on file content
- **AND** never read files directly

---

### Requirement: 3-Layer File Path Responsibility

The system SHALL follow TheAuditor's 3-layer file path architecture.

#### Scenario: Extractor Returns No File Path
- **WHEN** AWSCdkExtractor.extract() returns data
- **THEN** returned dict has NO `file_path` or `file` keys
- **AND** only contains: `construct_id`, `line`, `cdk_class`, `construct_name`, `properties`

#### Scenario: Orchestrator Adds File Path
- **WHEN** IndexerOrchestrator calls db_manager.add_cdk_construct()
- **THEN** orchestrator provides `file_path` parameter
- **AND** file_path comes from `file_info` context
- **AND** extractor data provides `line`, `cdk_class`, etc.

#### Scenario: Implementation Has No File Context
- **WHEN** extract_python_cdk_constructs() in python_impl.py executes
- **THEN** function receives ONLY AST tree (no file context)
- **AND** returns data with line numbers but NO file paths

---

### Requirement: Performance Constraints

The system SHALL meet performance targets for CDK analysis.

#### Scenario: Indexing Overhead for 50-File CDK Project
- **WHEN** running `aud index` on project with 50 CDK files
- **THEN** CDK extraction adds <5 seconds to total indexing time
- **AND** overhead is <10% of baseline indexing time

#### Scenario: Analysis Time for 500 Constructs
- **WHEN** running `aud cdk analyze` on database with 500 constructs
- **THEN** complete analysis in <5 seconds
- **AND** use indexed database queries (no full table scans)

#### Scenario: Zero Overhead for Non-CDK Projects
- **WHEN** running `aud index` on pure Python project (no CDK imports)
- **THEN** CDK extractor skipped (0% overhead)
- **AND** cdk_constructs table remains empty

---

### Requirement: Test Coverage

The system SHALL have comprehensive test coverage for CDK analysis.

#### Scenario: Unit Tests for Extraction
- **WHEN** running unit tests
- **THEN** test `extract_python_cdk_constructs()` with 10+ code samples
- **AND** verify correct extraction of constructs, properties, line numbers

#### Scenario: Integration Tests for End-to-End Pipeline
- **WHEN** running integration tests
- **THEN** test full pipeline on sample CDK project
- **AND** verify findings written to database
- **AND** verify findings appear in final report

#### Scenario: Regression Tests for Non-CDK Projects
- **WHEN** running regression tests
- **THEN** verify zero impact on non-CDK projects
- **AND** verify no performance degradation

#### Scenario: Rule Accuracy Tests
- **WHEN** running accuracy tests
- **THEN** achieve >95% precision (no false positives)
- **AND** achieve >90% recall (catch most vulnerabilities)

---

### Requirement: Documentation

The system SHALL provide comprehensive documentation for CDK analysis.

#### Scenario: User Guide Documentation
- **WHEN** user reads CDK documentation
- **THEN** documentation explains:
  - What CDK analysis detects
  - How to interpret findings
  - How to suppress false positives
  - Known limitations

#### Scenario: Developer Documentation
- **WHEN** developer reads architecture documentation
- **THEN** documentation explains:
  - Schema design decisions
  - Rule implementation patterns
  - How to add new CDK rules
  - Integration with orchestrator

#### Scenario: README Update
- **WHEN** user reads main README
- **THEN** README lists CDK analysis as supported capability
- **AND** includes CDK example in quickstart section

---

## Known Limitations (Documented)

### Limitation: CDK v1 Not Supported

**Description**: Only AWS CDK v2 (Python) is supported. CDK v1 uses different import structure (`@aws-cdk/aws-s3` vs `aws_cdk.aws_s3`).

**Workaround**: Upgrade to CDK v2 (v1 is deprecated since June 2023).

**Future**: Separate OpenSpec proposal if community requests v1 support.

---

### Limitation: Dynamic Property Values Not Evaluated

**Description**: Properties set via function calls or variables cannot be analyzed.

**Example**:
```python
bucket = s3.Bucket(self, "MyBucket",
    public_read_access=config.get_public_access()  # ← Cannot evaluate
)
```

**Behavior**: Property stored as string `"config.get_public_access()"`, not evaluated.

**Impact**: False negatives (some vulnerabilities not detected).

---

### Limitation: Custom Constructs Not Analyzed

**Description**: User-defined constructs that extend AWS constructs are not analyzed.

**Example**:
```python
class MyCustomBucket(s3.Bucket):
    pass

bucket = MyCustomBucket(...)  # ← Not detected
```

**Behavior**: Only built-in AWS constructs analyzed (class name matches `aws_cdk.*`).

**Workaround**: Use built-in constructs directly, or manually review custom constructs.

---

### Limitation: Cross-Stack References Not Resolved

**Description**: References to resources defined in other stacks are not resolved.

**Example**:
```python
# stack1.py
vpc = ec2.Vpc(...)

# stack2.py
sg = ec2.SecurityGroup(..., vpc=stack1.vpc)  # ← Reference not resolved
```

**Behavior**: Property stored as `"stack1.vpc"`, not resolved to actual VPC.

**Impact**: False negatives for cross-stack security issues.

---

## Success Metrics

### Must Achieve (Release Criteria)

- ✅ Detect public S3 buckets (100% recall on test fixtures)
- ✅ Detect unencrypted RDS instances (100% recall)
- ✅ Detect open security groups (100% recall)
- ✅ Detect IAM wildcard permissions (100% recall)
- ✅ Zero false positives on secure CDK projects
- ✅ <5 seconds overhead for 50-file CDK projects
- ✅ Pipeline integration complete (Stage 2)
- ✅ Auto-discovery functional (no manual registration)
- ✅ Documentation complete (user + developer)

### Nice to Have (Phase 2)

- Additional rules (VPC config, Lambda security, etc.)
- CDK v1 support (if community requests)
- Custom construct analysis (inheritance tracking)
- Cross-stack reference resolution

---

## References

- **AWS CDK v2 API**: https://docs.aws.amazon.com/cdk/api/v2/python/
- **AWS Security Best Practices**: https://docs.aws.amazon.com/security/
- **CWE References**:
  - CWE-732: Incorrect Permission Assignment
  - CWE-311: Missing Encryption of Sensitive Data
  - CWE-284: Improper Access Control
  - CWE-269: Improper Privilege Management

---

**Status**: Proposed (awaiting approval)
**Next Steps**: Implement according to `tasks.md` checklist
