"""AWS CDK Security Group Detection - database-first rule.

Detects security groups with overly permissive ingress/egress rules in CDK Python code.

Checks:
- Ingress rules from 0.0.0.0/0 (CRITICAL)
- Ingress rules from ::/0 IPv6 (CRITICAL)
- allow_all_outbound=True (LOW - informational)
"""

from __future__ import annotations

import logging
import sqlite3
from typing import List

from theauditor.rules.base import (
    RuleMetadata,
    StandardFinding,
    StandardRuleContext,
    Severity,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="aws_cdk_security_groups",
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


def find_cdk_sg_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect overly permissive security groups in CDK code."""
    findings: List[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        findings.extend(_check_unrestricted_ingress(cursor))
        findings.extend(_check_allow_all_outbound(cursor))
    finally:
        conn.close()

    return findings


def _check_unrestricted_ingress(cursor) -> List[StandardFinding]:
    """Detect security groups allowing unrestricted ingress (0.0.0.0/0 or ::/0)."""
    findings: List[StandardFinding] = []

    # Find all CDK constructs, filter for SecurityGroup in Python
    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        # Filter for SecurityGroup in Python (not SQL LIKE)
        cdk_class = row['cdk_class']
        if not ('SecurityGroup' in cdk_class and ('ec2' in cdk_class.lower() or 'aws_ec2' in cdk_class)):
            continue
        construct_id = row['construct_id']
        construct_name = row['construct_name'] or 'UnnamedSecurityGroup'

        # Check all properties for ingress-related configurations
        # CDK uses add_ingress_rule() calls, but constructor may have inline peer definitions
        cursor.execute("""
            SELECT property_name, property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
        """, (construct_id,))

        for prop_row in cursor.fetchall():
            property_value = prop_row['property_value_expr']

            # Check for 0.0.0.0/0 (IPv4 unrestricted)
            if '0.0.0.0/0' in property_value or 'Peer.anyIpv4' in property_value:
                findings.append(StandardFinding(
                    rule_name='aws-cdk-sg-unrestricted-ingress-ipv4',
                    message=f"Security group '{construct_name}' allows unrestricted ingress from 0.0.0.0/0",
                    severity=Severity.CRITICAL,
                    confidence='high',
                    file_path=row['file_path'],
                    line=prop_row['line'],
                    snippet=f"{prop_row['property_name']}={property_value}",
                    category='unrestricted_access',
                    cwe_id='CWE-284',
                    additional_info={
                        'construct_id': construct_id,
                        'construct_name': construct_name,
                        'remediation': 'Restrict ingress to specific IP ranges or security groups. Use ec2.Peer.ipv4("10.0.0.0/8") instead of 0.0.0.0/0.'
                    }
                ))

            # Check for ::/0 (IPv6 unrestricted)
            if '::/0' in property_value or 'Peer.anyIpv6' in property_value:
                findings.append(StandardFinding(
                    rule_name='aws-cdk-sg-unrestricted-ingress-ipv6',
                    message=f"Security group '{construct_name}' allows unrestricted IPv6 ingress from ::/0",
                    severity=Severity.CRITICAL,
                    confidence='high',
                    file_path=row['file_path'],
                    line=prop_row['line'],
                    snippet=f"{prop_row['property_name']}={property_value}",
                    category='unrestricted_access',
                    cwe_id='CWE-284',
                    additional_info={
                        'construct_id': construct_id,
                        'construct_name': construct_name,
                        'remediation': 'Restrict IPv6 ingress to specific ranges or security groups.'
                    }
                ))

    return findings


def _check_allow_all_outbound(cursor) -> List[StandardFinding]:
    """Detect security groups with allow_all_outbound=True (informational)."""
    findings: List[StandardFinding] = []

    # Find all CDK constructs, filter for SecurityGroup in Python
    cursor.execute("""
        SELECT c.construct_id, c.file_path, c.line, c.construct_name, c.cdk_class
        FROM cdk_constructs c
    """)

    for row in cursor.fetchall():
        # Filter for SecurityGroup in Python (not SQL LIKE)
        cdk_class = row['cdk_class']
        if not ('SecurityGroup' in cdk_class and ('ec2' in cdk_class.lower() or 'aws_ec2' in cdk_class)):
            continue
        construct_id = row['construct_id']
        construct_name = row['construct_name'] or 'UnnamedSecurityGroup'

        # Check for allow_all_outbound=True
        cursor.execute("""
            SELECT property_value_expr, line
            FROM cdk_construct_properties
            WHERE construct_id = ?
              AND property_name = 'allow_all_outbound'
              AND LOWER(property_value_expr) = 'true'
        """, (construct_id,))

        prop_row = cursor.fetchone()
        if prop_row:
            findings.append(StandardFinding(
                rule_name='aws-cdk-sg-allow-all-outbound',
                message=f"Security group '{construct_name}' allows all outbound traffic",
                severity=Severity.LOW,
                confidence='high',
                file_path=row['file_path'],
                line=prop_row['line'],
                snippet=f"allow_all_outbound=True",
                category='broad_permissions',
                cwe_id='CWE-284',
                additional_info={
                    'construct_id': construct_id,
                    'construct_name': construct_name,
                    'remediation': 'Consider restricting outbound traffic to specific destinations if defense-in-depth is required.'
                }
            ))

    return findings
