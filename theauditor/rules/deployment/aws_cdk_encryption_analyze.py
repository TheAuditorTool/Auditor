"""AWS CDK Encryption Detection - database-first rule.

Detects unencrypted storage resources in AWS CDK code:
- RDS DatabaseInstance without storage_encrypted=True
- EBS Volume without encrypted=True
- DynamoDB Table using default encryption (not customer-managed)

CWE-311: Missing Encryption of Sensitive Data
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
    """Detect unencrypted storage resources in CDK code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_unencrypted_rds(db))
        findings.extend(_check_unencrypted_ebs(db))
        findings.extend(_check_dynamodb_encryption(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_unencrypted_rds(db: RuleDB) -> list[StandardFinding]:
    """Detect RDS DatabaseInstance without encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
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
            .where("property_name = ? OR property_name = ?", "storage_encrypted", "storageEncrypted")
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
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
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
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
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
