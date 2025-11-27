"""AWS CDK Encryption Detection - database-first rule.

Detects unencrypted storage resources in CDK Python code.

Checks:
- RDS DatabaseInstance without storage_encrypted
- EBS Volume without encrypted
- DynamoDB Table with default encryption (not customer-managed)
"""

import logging
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="aws_cdk_encryption",
    category="deployment",
    target_extensions=[],
    exclude_patterns=[
        "test/",
        "__tests__/",
        ".pf/",
        ".auditor_venv/",
    ],
    requires_jsx_pass=False,
    execution_scope="database",
)


def find_cdk_encryption_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect unencrypted storage resources in CDK code."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        findings.extend(_check_unencrypted_rds(cursor))
        findings.extend(_check_unencrypted_ebs(cursor))
        findings.extend(_check_dynamodb_encryption(cursor))
    finally:
        conn.close()

    return findings


def _check_unencrypted_rds(cursor) -> list[StandardFinding]:
    """Detect RDS DatabaseInstance without encryption."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        cdk_class = row["cdk_class"]
        if not (
            "DatabaseInstance" in cdk_class
            and ("rds" in cdk_class.lower() or "aws_rds" in cdk_class)
        ):
            continue
        construct_id = row["construct_id"]
        construct_name = row["construct_name"] or "UnnamedDB"

        cursor.execute(
            """
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND (property_name = 'storage_encrypted' OR property_name = 'storageEncrypted')
        """,
            (construct_id,),
        )

        prop_row = cursor.fetchone()

        if not prop_row:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-rds-unencrypted",
                    message=f"RDS instance '{construct_name}' does not have storage encryption enabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=row["file_path"],
                    line=row["line"],
                    snippet=f"rds.DatabaseInstance(self, '{construct_name}', ...)",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Add storage_encrypted=True to enable encryption at rest.",
                    },
                )
            )
        elif "false" in prop_row["property_value_expr"].lower():
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-rds-unencrypted",
                    message=f"RDS instance '{construct_name}' has storage encryption explicitly disabled",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=row["file_path"],
                    line=prop_row["line"],
                    snippet="storage_encrypted=False",
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Change storage_encrypted=False to storage_encrypted=True.",
                    },
                )
            )

    return findings


def _check_unencrypted_ebs(cursor) -> list[StandardFinding]:
    """Detect EBS Volume without encryption."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        cdk_class = row["cdk_class"]
        if not ("Volume" in cdk_class and ("ec2" in cdk_class.lower() or "aws_ec2" in cdk_class)):
            continue
        construct_id = row["construct_id"]
        construct_name = row["construct_name"] or "UnnamedVolume"

        cursor.execute(
            """
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'encrypted'
        """,
            (construct_id,),
        )

        prop_row = cursor.fetchone()

        if not prop_row or "false" in prop_row["property_value_expr"].lower():
            line = prop_row["line"] if prop_row else row["line"]
            snippet = (
                f"encrypted={prop_row['property_value_expr']}"
                if prop_row
                else f"ec2.Volume(self, '{construct_name}', ...)"
            )

            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-ebs-unencrypted",
                    message=f"EBS volume '{construct_name}' is not encrypted",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=row["file_path"],
                    line=line,
                    snippet=snippet,
                    category="missing_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Add encrypted=True to enable EBS volume encryption.",
                    },
                )
            )

    return findings


def _check_dynamodb_encryption(cursor) -> list[StandardFinding]:
    """Detect DynamoDB Table with default encryption (not customer-managed)."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        cdk_class = row["cdk_class"]
        if not (
            "Table" in cdk_class
            and ("dynamodb" in cdk_class.lower() or "aws_dynamodb" in cdk_class)
        ):
            continue
        construct_id = row["construct_id"]
        construct_name = row["construct_name"] or "UnnamedTable"

        cursor.execute(
            """
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'encryption'
        """,
            (construct_id,),
        )

        prop_row = cursor.fetchone()

        if not prop_row:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-dynamodb-default-encryption",
                    message=f"DynamoDB table '{construct_name}' using default encryption (not customer-managed)",
                    severity=Severity.MEDIUM,
                    confidence="high",
                    file_path=row["file_path"],
                    line=row["line"],
                    snippet=f"dynamodb.Table(self, '{construct_name}', ...)",
                    category="weak_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Add encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED to use customer-managed keys.",
                    },
                )
            )
        elif "DEFAULT" in prop_row["property_value_expr"]:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-dynamodb-default-encryption",
                    message=f"DynamoDB table '{construct_name}' explicitly using default encryption",
                    severity=Severity.MEDIUM,
                    confidence="high",
                    file_path=row["file_path"],
                    line=prop_row["line"],
                    snippet=f"encryption={prop_row['property_value_expr']}",
                    category="weak_encryption",
                    cwe_id="CWE-311",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Change to encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED.",
                    },
                )
            )

    return findings
