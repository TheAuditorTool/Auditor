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
    Uses single JOIN query instead of N+1 pattern.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_construct_properties.property_value_expr",
            "cdk_construct_properties.line",
        )
        .join("cdk_construct_properties", on=[("construct_id", "construct_id")])
        .where(
            "cdk_constructs.cdk_class LIKE ? AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%Bucket%",
            "%s3%",
            "%aws_s3%",
        )
        .where("cdk_construct_properties.property_name = ?", "encryption")
    )

    for construct_id, file_path, construct_name, prop_value, prop_line in rows:
        if not prop_value:
            continue
        if "UNENCRYPTED" in prop_value.upper():
            display_name = construct_name or "UnnamedBucket"
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
    Uses single JOIN query instead of N+1 pattern.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_construct_properties.property_name",
            "cdk_construct_properties.property_value_expr",
            "cdk_construct_properties.line",
        )
        .join("cdk_construct_properties", on=[("construct_id", "construct_id")])
        .where(
            "cdk_constructs.cdk_class LIKE ? AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%DatabaseInstance%",
            "%rds%",
            "%aws_rds%",
        )
    )

    for construct_id, file_path, construct_name, prop_name, prop_value, prop_line in rows:
        if not prop_name or not prop_value:
            continue

        prop_name_lower = prop_name.lower()
        prop_value_upper = prop_value.upper()

        is_subnet_prop = "subnet" in prop_name_lower or "vpc_subnets" in prop_name_lower
        is_public = "PUBLIC" in prop_value_upper or "SubnetType.PUBLIC" in prop_value

        if is_subnet_prop and is_public:
            display_name = construct_name or "UnnamedDB"
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
    """Detect RDS DatabaseInstance without encryption.

    Uses set difference for missing detection + JOIN for explicit false.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all RDS DatabaseInstance constructs
    all_rds = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "cdk_class LIKE ? AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%DatabaseInstance%",
            "%rds%",
            "%aws_rds%",
        )
    )

    if not all_rds:
        return []

    rds_map = {row[0]: (row[1], row[2], row[3]) for row in all_rds}

    # Query 2: Get constructs that have storage_encrypted property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_value_expr", "line")
        .where(
            "property_name IN (?, ?)",
            "storage_encrypted",
            "storageEncrypted",
        )
    )

    configured_map = {row[0]: (row[1], row[2]) for row in configured_rows}

    # Check each RDS construct
    for construct_id, (file_path, line, construct_name) in rds_map.items():
        display_name = construct_name or "UnnamedDB"

        if construct_id not in configured_map:
            # Missing encryption property
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
            prop_value, prop_line = configured_map[construct_id]
            if prop_value and "false" in prop_value.lower():
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
    """Detect EBS Volume without encryption.

    Uses set difference for missing detection + map lookup for explicit false.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all EBS Volume constructs
    all_volumes = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "cdk_class LIKE ? AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%Volume%",
            "%ec2%",
            "%aws_ec2%",
        )
    )

    if not all_volumes:
        return []

    volume_map = {row[0]: (row[1], row[2], row[3]) for row in all_volumes}

    # Query 2: Get constructs that have encrypted property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_value_expr", "line")
        .where("property_name = ?", "encrypted")
    )

    configured_map = {row[0]: (row[1], row[2]) for row in configured_rows}

    for construct_id, (file_path, line, construct_name) in volume_map.items():
        display_name = construct_name or "UnnamedVolume"

        if construct_id not in configured_map:
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
            prop_value, prop_line = configured_map[construct_id]
            if prop_value and "false" in prop_value.lower():
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
    Uses set difference for missing detection + map lookup for DEFAULT value.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all DynamoDB Table constructs
    all_tables = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "cdk_class LIKE ? AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%Table%",
            "%dynamodb%",
            "%aws_dynamodb%",
        )
    )

    if not all_tables:
        return []

    table_map = {row[0]: (row[1], row[2], row[3]) for row in all_tables}

    # Query 2: Get constructs that have encryption property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_value_expr", "line")
        .where("property_name = ?", "encryption")
    )

    configured_map = {row[0]: (row[1], row[2]) for row in configured_rows}

    for construct_id, (file_path, line, construct_name) in table_map.items():
        display_name = construct_name or "UnnamedTable"

        if construct_id not in configured_map:
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
            prop_value, prop_line = configured_map[construct_id]
            if prop_value and "DEFAULT" in prop_value:
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

    Uses 2-query pattern: get constructs, get all relevant properties, match in Python.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all ElastiCache constructs
    all_caches = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%elasticache%",
            "%aws_elasticache%",
            "%ReplicationGroup%",
            "%CacheCluster%",
        )
    )

    if not all_caches:
        return []

    cache_map = {row[0]: (row[1], row[2], row[3], row[4]) for row in all_caches}

    # Query 2: Get all encryption-related properties for these constructs
    prop_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_name", "property_value_expr", "line")
        .where(
            "property_name IN (?, ?, ?, ?)",
            "at_rest_encryption_enabled",
            "atRestEncryptionEnabled",
            "transit_encryption_enabled",
            "transitEncryptionEnabled",
        )
    )

    # Build property lookup: construct_id -> {prop_name: (value, line)}
    props_by_construct: dict[str, dict[str, tuple]] = {}
    for cid, pname, pval, pline in prop_rows:
        if cid not in props_by_construct:
            props_by_construct[cid] = {}
        props_by_construct[cid][pname] = (pval, pline)

    for construct_id, (file_path, line, construct_name, _cdk_class) in cache_map.items():
        display_name = construct_name or "UnnamedCache"
        props = props_by_construct.get(construct_id, {})

        # Check at-rest encryption
        at_rest_key = next(
            (k for k in props if k in ("at_rest_encryption_enabled", "atRestEncryptionEnabled")),
            None,
        )
        at_rest_val = props[at_rest_key][0] if at_rest_key else None

        if not at_rest_key or (at_rest_val and "false" in at_rest_val.lower()):
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

        # Check transit encryption
        transit_key = next(
            (k for k in props if k in ("transit_encryption_enabled", "transitEncryptionEnabled")),
            None,
        )
        transit_val = props[transit_key][0] if transit_key else None

        if not transit_key or (transit_val and "false" in transit_val.lower()):
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
    """Detect EFS FileSystem without encryption.

    Uses set difference for missing detection + map lookup for explicit false.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all EFS FileSystem constructs
    all_efs = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND cdk_class LIKE ?",
            "%efs%",
            "%aws_efs%",
            "%FileSystem%",
        )
    )

    if not all_efs:
        return []

    efs_map = {row[0]: (row[1], row[2], row[3]) for row in all_efs}

    # Query 2: Get constructs that have encrypted property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_value_expr", "line")
        .where("property_name = ?", "encrypted")
    )

    configured_map = {row[0]: (row[1], row[2]) for row in configured_rows}

    for construct_id, (file_path, line, construct_name) in efs_map.items():
        display_name = construct_name or "UnnamedEFS"

        if construct_id not in configured_map:
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
            prop_value, prop_line = configured_map[construct_id]
            if prop_value and "false" in prop_value.lower():
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
    """Detect Kinesis Stream without encryption.

    Uses set difference for missing detection + map lookup for UNENCRYPTED value.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all Kinesis Stream constructs (excluding DeliveryStream)
    all_streams = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND cdk_class LIKE ? AND cdk_class NOT LIKE ?",
            "%kinesis%",
            "%aws_kinesis%",
            "%Stream%",
            "%DeliveryStream%",
        )
    )

    if not all_streams:
        return []

    stream_map = {row[0]: (row[1], row[2], row[3]) for row in all_streams}

    # Query 2: Get constructs that have encryption or encryptionKey property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_value_expr", "line")
        .where("property_name IN (?, ?)", "encryption", "encryptionKey")
    )

    configured_map = {row[0]: (row[1], row[2]) for row in configured_rows}

    for construct_id, (file_path, line, construct_name) in stream_map.items():
        display_name = construct_name or "UnnamedStream"

        if construct_id not in configured_map:
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
            prop_value, prop_line = configured_map[construct_id]
            if prop_value and "UNENCRYPTED" in prop_value.upper():
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
    """Detect SQS Queue without server-side encryption.

    Uses 2-query pattern: get constructs, get all encryption properties, match in Python.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all SQS Queue constructs
    all_queues = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND cdk_class LIKE ?",
            "%sqs%",
            "%aws_sqs%",
            "%Queue%",
        )
    )

    if not all_queues:
        return []

    queue_map = {row[0]: (row[1], row[2], row[3]) for row in all_queues}

    # Query 2: Get all encryption-related properties
    prop_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_name", "property_value_expr", "line")
        .where(
            "property_name IN (?, ?, ?)",
            "encryption_master_key",
            "encryptionMasterKey",
            "encryption",
        )
    )

    # Build property lookup
    props_by_construct: dict[str, dict[str, tuple]] = {}
    for cid, pname, pval, pline in prop_rows:
        if cid not in props_by_construct:
            props_by_construct[cid] = {}
        props_by_construct[cid][pname] = (pval, pline)

    for construct_id, (file_path, line, construct_name) in queue_map.items():
        display_name = construct_name or "UnnamedQueue"
        props = props_by_construct.get(construct_id, {})

        encryption_key = next(
            (k for k in props if k in ("encryption_master_key", "encryptionMasterKey", "encryption")),
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
            if prop_value and "UNENCRYPTED" in prop_value.upper():
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
    """Detect SNS Topic without server-side encryption.

    Uses set difference for missing detection.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all SNS Topic constructs
    all_topics = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND cdk_class LIKE ?",
            "%sns%",
            "%aws_sns%",
            "%Topic%",
        )
    )

    if not all_topics:
        return []

    topic_map = {row[0]: (row[1], row[2], row[3]) for row in all_topics}

    # Query 2: Get constructs that have master_key property
    configured_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id")
        .where("property_name IN (?, ?)", "master_key", "masterKey")
    )

    configured_ids = {row[0] for row in configured_rows}

    for construct_id, (file_path, line, construct_name) in topic_map.items():
        if construct_id in configured_ids:
            continue

        display_name = construct_name or "UnnamedTopic"
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
