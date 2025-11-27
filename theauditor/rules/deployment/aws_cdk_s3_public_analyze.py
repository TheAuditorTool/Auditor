"""AWS CDK S3 Public Access Detection - database-first rule.

Detects S3 buckets with public read access enabled in CDK Python code.

Checks:
- public_read_access=True (CRITICAL)
- Missing block_public_access configuration (HIGH)
"""

import logging
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    StandardFinding,
    StandardRuleContext,
    Severity,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="aws_cdk_s3_public",
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


def find_cdk_s3_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect S3 buckets with public access enabled in CDK code."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        findings.extend(_check_public_read_access(cursor))
        findings.extend(_check_missing_block_public_access(cursor))
    finally:
        conn.close()

    return findings


def _check_public_read_access(cursor) -> list[StandardFinding]:
    """Detect S3 buckets with explicit public_read_access=True."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        cdk_class = row["cdk_class"]
        if not ("Bucket" in cdk_class and ("s3" in cdk_class.lower() or "aws_s3" in cdk_class)):
            continue
        construct_id = row["construct_id"]
        construct_name = row["construct_name"] or "UnnamedBucket"

        cursor.execute(
            """
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND (property_name = 'public_read_access' OR property_name = 'publicReadAccess')
              AND LOWER(property_value_expr) = 'true'
        """,
            (construct_id,),
        )

        prop_row = cursor.fetchone()
        if prop_row:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-s3-public-read",
                    message=f"S3 bucket '{construct_name}' has public read access enabled",
                    severity=Severity.CRITICAL,
                    confidence="high",
                    file_path=row["file_path"],
                    line=prop_row["line"],
                    snippet=f"public_read_access=True",
                    category="public_exposure",
                    cwe_id="CWE-732",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Remove public_read_access=True or set to False. Use bucket policies with specific principals instead.",
                    },
                )
            )

    return findings


def _check_missing_block_public_access(cursor) -> list[StandardFinding]:
    """Detect S3 buckets missing block_public_access configuration."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        cdk_class = row["cdk_class"]
        if not ("Bucket" in cdk_class and ("s3" in cdk_class.lower() or "aws_s3" in cdk_class)):
            continue
        construct_id = row["construct_id"]
        construct_name = row["construct_name"] or "UnnamedBucket"

        cursor.execute(
            """
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND (property_name = 'block_public_access' OR property_name = 'blockPublicAccess')
        """,
            (construct_id,),
        )

        if not cursor.fetchone():
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-s3-missing-block-public-access",
                    message=f"S3 bucket '{construct_name}' missing block_public_access configuration",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=row["file_path"],
                    line=row["line"],
                    snippet=f"s3.Bucket(self, '{construct_name}', ...)",
                    category="missing_security_control",
                    cwe_id="CWE-732",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": construct_name,
                        "remediation": "Add block_public_access=s3.BlockPublicAccess.BLOCK_ALL to prevent accidental public exposure.",
                    },
                )
            )

    return findings
