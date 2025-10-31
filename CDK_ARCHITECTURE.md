# TheAuditor CDK Architecture

## Overview

CDK is TheAuditor's Infrastructure-as-Code security analysis module for AWS Cloud Development Kit Python code. It detects security misconfigurations in CDK constructs before deployment through a three-stage pipeline: extraction → database storage → rule analysis.

## CDK Purpose

- **What**: Infrastructure-as-Code security analyzer
- **Scope**: AWS CDK Python constructs and properties
- **When**: Use to audit cloud resource configurations before deployment
- **Output**: Security findings stored in cdk_findings database table

## Key Differences from Main Analysis

Main Analysis = Application Security (code logic, data flow, injection paths)
CDK Analysis = Infrastructure Security (resource config, IAM policies, encryption)

## Architecture

**Three-Stage Pipeline**:

1. **Extraction**: PythonExtractor walks AST, finds CDK construct calls
2. **Storage**: InfrastructureDatabase stores constructs + properties in SQLite
3. **Analysis**: RulesOrchestrator runs 4 CDK security rules, writes findings

## Database Tables

- **cdk_constructs**: Metadata for each CDK construct instantiation
- **cdk_construct_properties**: Keyword argument properties for constructs
- **cdk_findings**: Security findings from CDK rules

## CDK Rules (4 Total)

1. aws_cdk_s3_public - Detects public S3 buckets
2. aws_cdk_sg_open - Detects unrestricted security groups
3. aws_cdk_encryption - Detects unencrypted storage resources
4. aws_cdk_iam_wildcards - Detects overly permissive IAM policies

## Usage

```bash
aud index                    # Extract CDK constructs
aud cdk analyze              # Run security analysis
aud cdk analyze --severity critical  # Filter by severity
```

## Query Results

```sql
SELECT * FROM cdk_findings WHERE severity = 'critical';
```


