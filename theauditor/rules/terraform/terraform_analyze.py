"""Terraform IaC Security Analyzer - database-first rule.

Detects infrastructure security issues by querying Terraform extractor tables:
- terraform_resources
- terraform_variables
- terraform_variable_values (.tfvars)
- terraform_outputs

The rule mirrors the legacy TerraformAnalyzer checks while exposing findings via
StandardFinding so orchestrator and CLI can share a single source of truth.
"""
from __future__ import annotations



import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from theauditor.rules.base import (
    RuleMetadata,
    StandardFinding,
    StandardRuleContext,
    Severity,
)
from theauditor.rules.common.util import EntropyCalculator

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="terraform_security",
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


def find_terraform_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Terraform security issues using indexed data."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        findings.extend(_check_public_s3_buckets(cursor))
        findings.extend(_check_unencrypted_storage(cursor))
        findings.extend(_check_iam_wildcards(cursor))
        findings.extend(_check_resource_secrets(cursor))
        findings.extend(_check_tfvars_secrets(cursor))
        findings.extend(_check_missing_encryption(cursor))
        findings.extend(_check_security_groups(cursor))
    finally:
        conn.close()

    return findings


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_public_s3_buckets(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type = 'aws_s3_bucket'
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        resource_id = row['resource_id']
        snippet = f"resource \"aws_s3_bucket\" \"{row['resource_name']}\""
        line = row['line'] or 1

        acl = (properties.get('acl') or '').lower()
        if acl in {'public-read', 'public-read-write'}:
            findings.append(
                _build_finding(
                    rule_name='terraform-public-s3-acl',
                    message=f"S3 bucket '{row['resource_name']}' has public ACL '{acl}'",
                    file_path=row['file_path'],
                    line=line,
                    severity=Severity.HIGH,
                    category='public_exposure',
                    snippet=snippet,
                    additional_info={'resource_id': resource_id},
                )
            )

        if 'website' in properties:
            findings.append(
                _build_finding(
                    rule_name='terraform-public-s3-website',
                    message=(
                        f"S3 bucket '{row['resource_name']}' configured for website hosting "
                        f"(implies public access)"
                    ),
                    file_path=row['file_path'],
                    line=line,
                    severity=Severity.MEDIUM,
                    category='public_exposure',
                    snippet=snippet,
                    additional_info={'resource_id': resource_id},
                )
            )

    return findings


def _check_unencrypted_storage(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type IN ('aws_db_instance', 'aws_rds_cluster')
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        if not properties.get('storage_encrypted'):
            findings.append(
                _build_finding(
                    rule_name='terraform-db-unencrypted',
                    message=f"Database '{row['resource_name']}' not encrypted at rest",
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=Severity.HIGH,
                    category='missing_encryption',
                    snippet=(
                        f"resource \"{properties.get('engine', 'aws_db_instance')}\" "
                        f"\"{row['resource_name']}\""
                    ),
                    additional_info={'resource_id': row['resource_id']},
                )
            )

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type = 'aws_ebs_volume'
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        if not properties.get('encrypted'):
            findings.append(
                _build_finding(
                    rule_name='terraform-ebs-unencrypted',
                    message=f"EBS volume '{row['resource_name']}' not encrypted",
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=Severity.MEDIUM,
                    category='missing_encryption',
                    snippet=f"resource \"aws_ebs_volume\" \"{row['resource_name']}\"",
                    additional_info={'resource_id': row['resource_id']},
                )
            )

    return findings


def _check_iam_wildcards(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type IN ('aws_iam_policy', 'aws_iam_role_policy')
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        policy_str = properties.get('policy')
        policy = _load_json(policy_str) if isinstance(policy_str, str) else None
        if not policy:
            continue

        has_wildcard_action = False
        has_wildcard_resource = False

        statements = policy.get('Statement', [])
        if isinstance(statements, dict):
            statements = [statements]

        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            if any(action == '*' for action in actions):
                has_wildcard_action = True

            resources = statement.get('Resource', [])
            if isinstance(resources, str):
                resources = [resources]
            if any(res == '*' for res in resources):
                has_wildcard_resource = True

        if has_wildcard_action and has_wildcard_resource:
            findings.append(
                _build_finding(
                    rule_name='terraform-iam-wildcard',
                    message=f"IAM policy '{row['resource_name']}' grants * on all resources",
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=Severity.CRITICAL,
                    category='iam_wildcard',
                    snippet=f"resource \"{row['resource_name']}\"",
                    additional_info={'resource_id': row['resource_id']},
                    cwe='CWE-732',
                )
            )

    return findings


def _check_resource_secrets(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json,
               sensitive_flags_json, line
        FROM terraform_resources
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        sensitive_props = _load_json(row['sensitive_flags_json']) or []

        for prop_name in sensitive_props:
            prop_value = properties.get(prop_name)
            if isinstance(prop_value, str) and not prop_value.startswith('var.') and '${' not in prop_value:
                findings.append(
                    _build_finding(
                        rule_name='terraform-hardcoded-secret',
                        message=f"Hardcoded secret in {row['resource_name']}.{prop_name}",
                        file_path=row['file_path'],
                        line=row['line'] or 1,
                        severity=Severity.CRITICAL,
                        category='hardcoded_secret',
                        snippet=f"{prop_name} = [REDACTED]",
                        additional_info={'resource_id': row['resource_id']},
                        cwe='CWE-798',
                    )
                )

    return findings


def _check_tfvars_secrets(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT file_path, variable_name, variable_value_json, line
        FROM terraform_variable_values
        WHERE is_sensitive_context = 1
        """
    )

    for row in cursor.fetchall():
        value = _load_json(row['variable_value_json'])
        if isinstance(value, str) and _is_high_entropy_secret(value):
            findings.append(
                _build_finding(
                    rule_name='terraform-tfvars-secret',
                    message=(
                        f"Sensitive value for '{row['variable_name']}' hardcoded in .tfvars"
                    ),
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=Severity.CRITICAL,
                    category='hardcoded_secret',
                    snippet=f"{row['variable_name']} = [REDACTED]",
                    additional_info={'variable_name': row['variable_name']},
                    cwe='CWE-798',
                )
            )

    return findings


def _check_missing_encryption(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type = 'aws_sns_topic'
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json'])
        if 'kms_master_key_id' not in properties:
            findings.append(
                _build_finding(
                    rule_name='terraform-sns-no-kms',
                    message=f"SNS topic '{row['resource_name']}' missing KMS encryption",
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=Severity.LOW,
                    category='missing_encryption',
                    snippet=f"resource \"aws_sns_topic\" \"{row['resource_name']}\"",
                    additional_info={'resource_id': row['resource_id']},
                )
            )

    return findings


def _check_security_groups(cursor) -> list[StandardFinding]:
    findings: list[StandardFinding] = []

    cursor.execute(
        """
        SELECT resource_id, file_path, resource_name, properties_json, line
        FROM terraform_resources
        WHERE resource_type IN ('aws_security_group', 'aws_security_group_rule')
        """
    )

    for row in cursor.fetchall():
        properties = _load_json(row['properties_json']) or {}
        ingress_rules = properties.get('ingress', [])
        if isinstance(ingress_rules, dict):
            ingress_rules = [ingress_rules]

        for rule in ingress_rules:
            if not isinstance(rule, dict):
                continue

            cidr_blocks = rule.get('cidr_blocks', [])
            if '0.0.0.0/0' not in cidr_blocks:
                continue

            from_port = rule.get('from_port', 0)
            to_port = rule.get('to_port', from_port)
            severity = Severity.MEDIUM if from_port in (80, 443) else Severity.HIGH

            findings.append(
                _build_finding(
                    rule_name='terraform-open-security-group',
                    message=(
                        f"Security group '{row['resource_name']}' allows ingress from 0.0.0.0/0 "
                        f"on ports {from_port}-{to_port}"
                    ),
                    file_path=row['file_path'],
                    line=row['line'] or 1,
                    severity=severity,
                    category='public_exposure',
                    snippet=f"ingress {{ from_port = {from_port} to_port = {to_port} }}",
                    additional_info={'resource_id': row['resource_id']},
                    cwe='CWE-284',
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(raw: Any) -> Any:
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def _is_high_entropy_secret(value: str, threshold: float = 4.0) -> bool:
    if not value or len(value) < 10:
        return False
    if any(ch.isspace() for ch in value):
        return False
    entropy = EntropyCalculator.calculate(value)
    return entropy >= threshold


def _build_finding(
    rule_name: str,
    message: str,
    file_path: str,
    line: int,
    severity: Severity,
    category: str,
    snippet: str = "",
    additional_info: dict[str, Any] | None = None,
    cwe: str | None = None,
) -> StandardFinding:
    finding = StandardFinding(
        rule_name=rule_name,
        message=message,
        file_path=file_path,
        line=line,
        severity=severity,
        category=category,
        snippet=snippet,
    )

    if additional_info:
        finding.additional_info = additional_info
    if cwe:
        finding.cwe_id = cwe

    return finding
