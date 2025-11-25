"""AWS CDK IAM Wildcard Detection - database-first rule.

Detects IAM policies with overly permissive wildcard actions or resources in CDK Python code.

Checks:
- IAM policies with actions containing '*' (HIGH)
- IAM policies with resources containing '*' (HIGH)
- IAM roles with AdministratorAccess policy attached (CRITICAL)
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
    name="aws_cdk_iam_wildcards",
    category="deployment",
    target_extensions=[],  # Database-level rule
    exclude_patterns=[
        'test/',
        '__tests__/',
        '.pf/',
        '.auditor_venv/',
    ],
    requires_jsx_pass=False,
    execution_scope='database',
)


def find_cdk_iam_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect IAM policies with overly permissive wildcards in CDK code."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        findings.extend(_check_wildcard_actions(cursor))
        findings.extend(_check_wildcard_resources(cursor))
        findings.extend(_check_administrator_access(cursor))
    finally:
        conn.close()

    return findings


def _check_wildcard_actions(cursor) -> list[StandardFinding]:
    """Detect IAM policies with wildcard actions."""
    findings: list[StandardFinding] = []

    # Find all CDK constructs, filter for IAM Policy in Python
    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        # Filter for IAM Policy/PolicyStatement in Python (not SQL LIKE)
        cdk_class = row['cdk_class']
        is_policy = 'Policy' in cdk_class or 'PolicyStatement' in cdk_class
        is_iam = 'iam' in cdk_class.lower() or 'aws_iam' in cdk_class
        if not (is_policy and is_iam):
            continue
        construct_id = row['construct_id']
        construct_name = row['construct_name'] or 'UnnamedPolicy'

        # Check for actions property containing wildcard
        cursor.execute("""
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'actions'
        """, (construct_id,))

        prop_row = cursor.fetchone()
        if prop_row and ("'*'" in prop_row['property_value_expr'] or '"*"' in prop_row['property_value_expr']):
            findings.append(StandardFinding(
                rule_name='aws-cdk-iam-wildcard-actions',
                message=f"IAM policy '{construct_name}' grants wildcard actions (*)",
                severity=Severity.HIGH,
                confidence='high',
                file_path=row['file_path'],
                line=prop_row['line'],
                snippet=f"actions={prop_row['property_value_expr']}",
                category='excessive_permissions',
                cwe_id='CWE-269',
                additional_info={
                    'construct_id': construct_id,
                    'construct_name': construct_name,
                    'remediation': 'Replace wildcard actions with specific actions following least privilege principle (e.g., ["s3:GetObject", "s3:PutObject"]).'
                }
            ))

    return findings


def _check_wildcard_resources(cursor) -> list[StandardFinding]:
    """Detect IAM policies with wildcard resources."""
    findings: list[StandardFinding] = []

    # Find all CDK constructs, filter for IAM Policy in Python
    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        # Filter for IAM Policy/PolicyStatement in Python (not SQL LIKE)
        cdk_class = row['cdk_class']
        is_policy = 'Policy' in cdk_class or 'PolicyStatement' in cdk_class
        is_iam = 'iam' in cdk_class.lower() or 'aws_iam' in cdk_class
        if not (is_policy and is_iam):
            continue
        construct_id = row['construct_id']
        construct_name = row['construct_name'] or 'UnnamedPolicy'

        # Check for resources property containing wildcard
        cursor.execute("""
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'resources'
        """, (construct_id,))

        prop_row = cursor.fetchone()
        if prop_row and ("'*'" in prop_row['property_value_expr'] or '"*"' in prop_row['property_value_expr']):
            findings.append(StandardFinding(
                rule_name='aws-cdk-iam-wildcard-resources',
                message=f"IAM policy '{construct_name}' grants access to all resources (*)",
                severity=Severity.HIGH,
                confidence='high',
                file_path=row['file_path'],
                line=prop_row['line'],
                snippet=f"resources={prop_row['property_value_expr']}",
                category='excessive_permissions',
                cwe_id='CWE-269',
                additional_info={
                    'construct_id': construct_id,
                    'construct_name': construct_name,
                    'remediation': 'Replace wildcard resources with specific ARNs (e.g., ["arn:aws:s3:::my-bucket/*"]).'
                }
            ))

    return findings


def _check_administrator_access(cursor) -> list[StandardFinding]:
    """Detect IAM roles with AdministratorAccess managed policy attached."""
    findings: list[StandardFinding] = []

    # Find all CDK constructs, filter for IAM Role in Python
    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        # Filter for IAM Role in Python (not SQL LIKE)
        cdk_class = row['cdk_class']
        if not ('Role' in cdk_class and ('iam' in cdk_class.lower() or 'aws_iam' in cdk_class)):
            continue
        construct_id = row['construct_id']
        construct_name = row['construct_name'] or 'UnnamedRole'

        # Check for managed_policies property containing AdministratorAccess
        cursor.execute("""
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'managed_policies'
        """, (construct_id,))

        prop_row = cursor.fetchone()
        if prop_row and 'AdministratorAccess' in prop_row['property_value_expr']:
            findings.append(StandardFinding(
                rule_name='aws-cdk-iam-administrator-access',
                message=f"IAM role '{construct_name}' has AdministratorAccess policy attached",
                severity=Severity.CRITICAL,
                confidence='high',
                file_path=row['file_path'],
                line=prop_row['line'],
                snippet=f"managed_policies={prop_row['property_value_expr']}",
                category='excessive_permissions',
                cwe_id='CWE-269',
                additional_info={
                    'construct_id': construct_id,
                    'construct_name': construct_name,
                    'remediation': 'Create custom policies with only the permissions required for this role. AdministratorAccess grants full AWS account access.'
                }
            ))

    return findings
