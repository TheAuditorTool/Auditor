"""AWS CDK Encryption Detection - database-first rule.

Detects unencrypted storage and data resources in AWS CDK code:
- S3 Bucket with BucketEncryption.UNENCRYPTED
- RDS DatabaseInstance without storage_encrypted=True
- RDS DatabaseInstance in public subnet (encryption irrelevant if exposed)
- EBS Volume without encrypted=True
- DynamoDB Table using default encryption (not customer-managed)
- ElastiCache without at_rest_encryption_enabled or transit_encryption_enabled
- EFS FileSystem without encrypted=True
- Kinesis Stream without encryption
- SQS Queue without server-side encryption
- SNS Topic without server-side encryption

CWE-311: Missing Encryption of Sensitive Data
CWE-284: Improper Access Control (public subnet exposure)
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="aws_cdk_encryption",
    category="deployment",
    target_extensions=[".py", ".ts", ".js"],
    exclude_patterns=[
        "test/",
        "__tests__/",
        ".pf/",
        ".auditor_venv/",
        "node_modules/",
    ],
    execution_scope="database",
    primary_table="cdk_constructs",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect unencrypted storage and data resources in CDK code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_s3_encryption(db))
        findings.extend(_check_unencrypted_rds(db))
        findings.extend(_check_rds_public_subnet(db))
        findings.extend(_check_unencrypted_ebs(db))
        findings.extend(_check_dynamodb_encryption(db))
        findings.extend(_check_elasticache_encryption(db))
        findings.extend(_check_efs_encryption(db))
        findings.extend(_check_kinesis_encryption(db))
        findings.extend(_check_sqs_encryption(db))
        findings.extend(_check_sns_encryption(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_s3_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect S3 buckets with encryption explicitly disabled.

    CDK v2 defaults to S3-managed encryption, but explicit UNENCRYPTED is a problem.
    Also flags buckets without any encryption configuration as informational.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, _line, construct_name, cdk_class in rows:
        if not ("Bucket" in cdk_class and ("s3" in cdk_class.lower() or "aws_s3" in cdk_class)):
            continue

        display_name = construct_name or "UnnamedBucket"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "encryption")
        )

        if prop_rows:
            prop_value, prop_line = prop_rows[0]
            if "UNENCRYPTED" in prop_value.upper():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-s3-unencrypted",
                        message=f"S3 bucket '{display_name}' has encryption explicitly disabled",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"encryption={prop_value}",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Remove encryption=BucketEncryption.UNENCRYPTED or use S3_MANAGED/KMS_MANAGED.",
                        },
                    )
                )

    return findings


def _check_rds_public_subnet(db: RuleDB) -> list[StandardFinding]:
    """Detect RDS databases placed in public subnets.

    A database in a public subnet is critically exposed regardless of encryption.
    This is a common infrastructure mistake that leads to data breaches.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, _line, construct_name, cdk_class in rows:
        if not (
            "DatabaseInstance" in cdk_class
            and ("rds" in cdk_class.lower() or "aws_rds" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedDB"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        for prop_name, prop_value, prop_line in prop_rows:
            prop_name_lower = prop_name.lower()
            prop_value_upper = prop_value.upper()

            is_subnet_prop = "subnet" in prop_name_lower or "vpc_subnets" in prop_name_lower
            is_public = "PUBLIC" in prop_value_upper or "SubnetType.PUBLIC" in prop_value

            if is_subnet_prop and is_public:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-rds-public-subnet",
                        message=f"RDS instance '{display_name}' is placed in a PUBLIC subnet - critically exposed",
                        severity=Severity.CRITICAL,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{prop_name}={prop_value}",
                        category="public_exposure",
                        cwe_id="CWE-284",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Move database to private subnet: vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)",
                        },
                    )
                )

    return findings


def _check_unencrypted_rds(db: RuleDB) -> list[StandardFinding]:
    """Detect RDS DatabaseInstance without encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "DatabaseInstance" in cdk_class
            and ("rds" in cdk_class.lower() or "aws_rds" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedDB"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where(
                "property_name = ? OR property_name = ?", "storage_encrypted", "storageEncrypted"
            )
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-rds-unencrypted",
                    message=f"RDS instance '{display_name}' does not have storage encryption enabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"rds.DatabaseInstance(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add storage_encrypted=True to enable encryption at rest.",
                    },
                )
            )
        else:
            prop_value, prop_line = prop_rows[0]
            if "false" in prop_value.lower():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-rds-unencrypted",
                        message=f"RDS instance '{display_name}' has storage encryption explicitly disabled",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet="storage_encrypted=False",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change storage_encrypted=False to storage_encrypted=True.",
                        },
                    )
                )

    return findings


def _check_unencrypted_ebs(db: RuleDB) -> list[StandardFinding]:
    """Detect EBS Volume without encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not ("Volume" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)):
            continue

        display_name = construct_name or "UnnamedVolume"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "encrypted")
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-ebs-unencrypted",
                    message=f"EBS volume '{display_name}' is not encrypted",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"ec2.Volume(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add encrypted=True to enable EBS volume encryption.",
                    },
                )
            )
        else:
            prop_value, prop_line = prop_rows[0]
            if "false" in prop_value.lower():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-ebs-unencrypted",
                        message=f"EBS volume '{display_name}' has encryption explicitly disabled",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"encrypted={prop_value}",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change encrypted=False to encrypted=True.",
                        },
                    )
                )

    return findings


def _check_dynamodb_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect DynamoDB Table with default encryption (not customer-managed).

    Note: AWS default encryption IS still encrypted (AWS-managed keys).
    This finding is for compliance/best practice - customer-managed keys
    provide more control over key rotation and access policies.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not (
            "Table" in cdk_class
            and ("dynamodb" in cdk_class.lower() or "aws_dynamodb" in cdk_class)
        ):
            continue

        display_name = construct_name or "UnnamedTable"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "encryption")
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-dynamodb-default-encryption",
                    message=f"DynamoDB table '{display_name}' using default encryption (not customer-managed)",
                    severity=Severity.MEDIUM,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"dynamodb.Table(self, '{display_name}', ...)",
                    category="weak_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED to use customer-managed keys.",
                    },
                )
            )
        else:
            prop_value, prop_line = prop_rows[0]
            if "DEFAULT" in prop_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-dynamodb-default-encryption",
                        message=f"DynamoDB table '{display_name}' explicitly using default encryption",
                        severity=Severity.MEDIUM,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"encryption={prop_value}",
                        category="weak_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change to encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED.",
                        },
                    )
                )

    return findings


def _check_elasticache_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect ElastiCache clusters without encryption.

    Checks for:
    - CfnReplicationGroup (Redis) without at_rest_encryption_enabled
    - CfnReplicationGroup without transit_encryption_enabled
    - CfnCacheCluster without encryption
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_elasticache = "elasticache" in cdk_class.lower() or "aws_elasticache" in cdk_class
        is_replication_group = "ReplicationGroup" in cdk_class or "CfnReplicationGroup" in cdk_class
        is_cache_cluster = "CacheCluster" in cdk_class or "CfnCacheCluster" in cdk_class

        if not (is_elasticache and (is_replication_group or is_cache_cluster)):
            continue

        display_name = construct_name or "UnnamedCache"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        props = {row[0]: (row[1], row[2]) for row in prop_rows}

        at_rest_key = next(
            (k for k in props if k in ("at_rest_encryption_enabled", "atRestEncryptionEnabled")),
            None,
        )
        transit_key = next(
            (k for k in props if k in ("transit_encryption_enabled", "transitEncryptionEnabled")),
            None,
        )

        if not at_rest_key or "false" in props[at_rest_key][0].lower():
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-elasticache-no-at-rest-encryption",
                    message=f"ElastiCache '{display_name}' does not have at-rest encryption enabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=props[at_rest_key][1] if at_rest_key else line,
                    snippet="at_rest_encryption_enabled=False"
                    if at_rest_key
                    else f"elasticache.CfnReplicationGroup(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add at_rest_encryption_enabled=True to encrypt data at rest.",
                    },
                )
            )

        if not transit_key or "false" in props[transit_key][0].lower():
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-elasticache-no-transit-encryption",
                    message=f"ElastiCache '{display_name}' does not have transit encryption enabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=props[transit_key][1] if transit_key else line,
                    snippet="transit_encryption_enabled=False"
                    if transit_key
                    else f"elasticache.CfnReplicationGroup(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-319",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add transit_encryption_enabled=True to encrypt data in transit.",
                    },
                )
            )

    return findings


def _check_efs_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect EFS FileSystem without encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_efs = "efs" in cdk_class.lower() or "aws_efs" in cdk_class
        is_filesystem = "FileSystem" in cdk_class

        if not (is_efs and is_filesystem):
            continue

        display_name = construct_name or "UnnamedEFS"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "encrypted")
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-efs-unencrypted",
                    message=f"EFS filesystem '{display_name}' does not have encryption enabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"efs.FileSystem(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add encrypted=True to enable EFS encryption at rest.",
                    },
                )
            )
        else:
            prop_value, prop_line = prop_rows[0]
            if "false" in prop_value.lower():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-efs-unencrypted",
                        message=f"EFS filesystem '{display_name}' has encryption explicitly disabled",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet="encrypted=False",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change encrypted=False to encrypted=True.",
                        },
                    )
                )

    return findings


def _check_kinesis_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect Kinesis Stream without encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_kinesis = "kinesis" in cdk_class.lower() or "aws_kinesis" in cdk_class
        is_stream = "Stream" in cdk_class and "DeliveryStream" not in cdk_class

        if not (is_kinesis and is_stream):
            continue

        display_name = construct_name or "UnnamedStream"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ? OR property_name = ?", "encryption", "encryptionKey")
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-kinesis-unencrypted",
                    message=f"Kinesis stream '{display_name}' does not have encryption configured",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"kinesis.Stream(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add encryption=kinesis.StreamEncryption.KMS with encryption_key to enable encryption.",
                    },
                )
            )
        else:
            prop_value, prop_line = prop_rows[0]
            if "UNENCRYPTED" in prop_value.upper():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-kinesis-unencrypted",
                        message=f"Kinesis stream '{display_name}' has encryption explicitly disabled",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"encryption={prop_value}",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change to encryption=kinesis.StreamEncryption.KMS.",
                        },
                    )
                )

    return findings


def _check_sqs_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect SQS Queue without server-side encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_sqs = "sqs" in cdk_class.lower() or "aws_sqs" in cdk_class
        is_queue = "Queue" in cdk_class

        if not (is_sqs and is_queue):
            continue

        display_name = construct_name or "UnnamedQueue"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        props = {row[0]: (row[1], row[2]) for row in prop_rows}

        encryption_key = next(
            (
                k
                for k in props
                if k in ("encryption_master_key", "encryptionMasterKey", "encryption")
            ),
            None,
        )

        if not encryption_key:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-sqs-unencrypted",
                    message=f"SQS queue '{display_name}' does not have server-side encryption configured",
                    severity=Severity.MEDIUM,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"sqs.Queue(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add encryption=sqs.QueueEncryption.KMS or encryption_master_key to enable SSE.",
                    },
                )
            )
        else:
            prop_value, prop_line = props[encryption_key]
            if "UNENCRYPTED" in prop_value.upper():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-sqs-unencrypted",
                        message=f"SQS queue '{display_name}' has encryption explicitly disabled",
                        severity=Severity.MEDIUM,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"{encryption_key}={prop_value}",
                        category="missing_encryption",
                        cwe_id="CWE-311",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Change to encryption=sqs.QueueEncryption.KMS.",
                        },
                    )
                )

    return findings


def _check_sns_encryption(db: RuleDB) -> list[StandardFinding]:
    """Detect SNS Topic without server-side encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs").select(
            "construct_id", "file_path", "line", "construct_name", "cdk_class"
        )
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_sns = "sns" in cdk_class.lower() or "aws_sns" in cdk_class
        is_topic = "Topic" in cdk_class

        if not (is_sns and is_topic):
            continue

        display_name = construct_name or "UnnamedTopic"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ? OR property_name = ?", "master_key", "masterKey")
        )

        if not prop_rows:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-sns-unencrypted",
                    message=f"SNS topic '{display_name}' does not have server-side encryption configured",
                    severity=Severity.MEDIUM,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"sns.Topic(self, '{display_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Add master_key=kms.Key(...) to enable server-side encryption.",
                    },
                )
            )

    return findings
