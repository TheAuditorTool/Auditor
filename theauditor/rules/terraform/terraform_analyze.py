"""Terraform IaC Security Analyzer - database-first rule.

Detects Terraform security issues including:
- Public S3 buckets (ACL and website hosting)
- Unencrypted storage (RDS, EBS volumes)
- IAM wildcard permissions
- Hardcoded secrets in resources and tfvars
- Missing KMS encryption on SNS topics
- Overly permissive security groups

CWE-732: Incorrect Permission Assignment for Critical Resource
CWE-798: Use of Hard-coded Credentials
CWE-284: Improper Access Control
CWE-311: Missing Encryption of Sensitive Data
"""

import ast
import json
from typing import Any

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.common.util import EntropyCalculator
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="terraform_security",
    category="deployment",
    execution_scope="database",
    primary_table="terraform_resources",
    target_extensions=[".tf", ".tfvars"],
    exclude_patterns=[
        "test/",
        "__tests__/",
        ".pf/",
        ".auditor_venv/",
    ],
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Terraform security issues using indexed data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        all_props = _bulk_load_all_properties(db)
        sensitive_props = _bulk_load_sensitive_props(db)

        findings: list[StandardFinding] = []
        findings.extend(_check_public_s3_buckets(db, all_props))
        findings.extend(_check_unencrypted_storage(db, all_props))
        findings.extend(_check_iam_wildcards(db, all_props))
        findings.extend(_check_resource_secrets(db, all_props, sensitive_props))
        findings.extend(_check_tfvars_secrets(db))
        findings.extend(_check_missing_encryption(db, all_props))
        findings.extend(_check_security_groups(db, all_props))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_public_s3_buckets(
    db: RuleDB, all_props: dict[str, dict[str, Any]]
) -> list[StandardFinding]:
    """Check for public S3 buckets via ACL or website hosting."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type = ?", "aws_s3_bucket")
    )

    for resource_id, file_path, resource_name, line in rows:
        properties = all_props.get(resource_id, {})
        snippet = f'resource "aws_s3_bucket" "{resource_name}"'
        line_num = line or 1

        acl = (properties.get("acl") or "").lower()
        if acl in {"public-read", "public-read-write"}:
            findings.append(
                StandardFinding(
                    rule_name="terraform-public-s3-acl",
                    message=f"S3 bucket '{resource_name}' has public ACL '{acl}'",
                    file_path=file_path,
                    line=line_num,
                    severity=Severity.HIGH,
                    category="public_exposure",
                    snippet=snippet,
                    cwe_id="CWE-284",
                    additional_info={"resource_id": resource_id},
                )
            )

        if "website" in properties:
            findings.append(
                StandardFinding(
                    rule_name="terraform-public-s3-website",
                    message=(
                        f"S3 bucket '{resource_name}' configured for website hosting "
                        f"(implies public access)"
                    ),
                    file_path=file_path,
                    line=line_num,
                    severity=Severity.MEDIUM,
                    category="public_exposure",
                    snippet=snippet,
                    cwe_id="CWE-284",
                    additional_info={"resource_id": resource_id},
                )
            )

    return findings


def _check_unencrypted_storage(
    db: RuleDB, all_props: dict[str, dict[str, Any]]
) -> list[StandardFinding]:
    """Check for unencrypted RDS databases and EBS volumes."""
    findings: list[StandardFinding] = []

    db_rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type IN ('aws_db_instance', 'aws_rds_cluster')")
    )

    for resource_id, file_path, resource_name, line in db_rows:
        properties = all_props.get(resource_id, {})
        if not properties.get("storage_encrypted"):
            findings.append(
                StandardFinding(
                    rule_name="terraform-db-unencrypted",
                    message=f"Database '{resource_name}' not encrypted at rest",
                    file_path=file_path,
                    line=line or 1,
                    severity=Severity.HIGH,
                    category="missing_encryption",
                    snippet=(
                        f'resource "{properties.get("engine", "aws_db_instance")}" '
                        f'"{resource_name}"'
                    ),
                    cwe_id="CWE-311",
                    additional_info={"resource_id": resource_id},
                )
            )

    ebs_rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type = ?", "aws_ebs_volume")
    )

    for resource_id, file_path, resource_name, line in ebs_rows:
        properties = all_props.get(resource_id, {})
        if not properties.get("encrypted"):
            findings.append(
                StandardFinding(
                    rule_name="terraform-ebs-unencrypted",
                    message=f"EBS volume '{resource_name}' not encrypted",
                    file_path=file_path,
                    line=line or 1,
                    severity=Severity.MEDIUM,
                    category="missing_encryption",
                    snippet=f'resource "aws_ebs_volume" "{resource_name}"',
                    cwe_id="CWE-311",
                    additional_info={"resource_id": resource_id},
                )
            )

    return findings


def _check_iam_wildcards(db: RuleDB, all_props: dict[str, dict[str, Any]]) -> list[StandardFinding]:
    """Check for IAM policies with wildcard permissions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type IN ('aws_iam_policy', 'aws_iam_role_policy')")
    )

    for resource_id, file_path, resource_name, line in rows:
        properties = all_props.get(resource_id, {})
        policy = properties.get("policy")
        if not isinstance(policy, dict):
            continue

        has_wildcard_action = False
        has_wildcard_resource = False

        statements = policy.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]

        for statement in statements:
            actions = statement.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if any(action == "*" for action in actions):
                has_wildcard_action = True

            resources = statement.get("Resource", [])
            if isinstance(resources, str):
                resources = [resources]
            if any(res == "*" for res in resources):
                has_wildcard_resource = True

        if has_wildcard_action and has_wildcard_resource:
            findings.append(
                StandardFinding(
                    rule_name="terraform-iam-wildcard",
                    message=f"IAM policy '{resource_name}' grants * on all resources",
                    file_path=file_path,
                    line=line or 1,
                    severity=Severity.CRITICAL,
                    category="iam_wildcard",
                    snippet=f'resource "{resource_name}"',
                    cwe_id="CWE-732",
                    additional_info={"resource_id": resource_id},
                )
            )

    return findings


def _check_resource_secrets(
    db: RuleDB,
    all_props: dict[str, dict[str, Any]],
    sensitive_props: dict[str, set[str]],
) -> list[StandardFinding]:
    """Check for hardcoded secrets in Terraform resources."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_resources").select("resource_id", "file_path", "resource_name", "line")
    )

    for resource_id, file_path, resource_name, line in rows:
        properties = all_props.get(resource_id, {})
        resource_sensitive_props = sensitive_props.get(resource_id, set())

        for prop_name in resource_sensitive_props:
            prop_value = properties.get(prop_name)
            if (
                isinstance(prop_value, str)
                and not prop_value.startswith("var.")
                and "${" not in prop_value
            ):
                findings.append(
                    StandardFinding(
                        rule_name="terraform-hardcoded-secret",
                        message=f"Hardcoded secret in {resource_name}.{prop_name}",
                        file_path=file_path,
                        line=line or 1,
                        severity=Severity.CRITICAL,
                        category="hardcoded_secret",
                        snippet=f"{prop_name} = [REDACTED]",
                        cwe_id="CWE-798",
                        additional_info={"resource_id": resource_id},
                    )
                )

    return findings


def _check_tfvars_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for hardcoded secrets in .tfvars files."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_variable_values")
        .select("file_path", "variable_name", "variable_value_json", "line")
        .where("is_sensitive_context = 1")
    )

    for file_path, variable_name, variable_value_json, line in rows:
        value = _load_json(variable_value_json)
        if isinstance(value, str) and _is_high_entropy_secret(value):
            findings.append(
                StandardFinding(
                    rule_name="terraform-tfvars-secret",
                    message=f"Sensitive value for '{variable_name}' hardcoded in .tfvars",
                    file_path=file_path,
                    line=line or 1,
                    severity=Severity.CRITICAL,
                    category="hardcoded_secret",
                    snippet=f"{variable_name} = [REDACTED]",
                    cwe_id="CWE-798",
                    additional_info={"variable_name": variable_name},
                )
            )

    return findings


def _check_missing_encryption(
    db: RuleDB, all_props: dict[str, dict[str, Any]]
) -> list[StandardFinding]:
    """Check for resources missing KMS encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type = ?", "aws_sns_topic")
    )

    for resource_id, file_path, resource_name, line in rows:
        properties = all_props.get(resource_id, {})
        if "kms_master_key_id" not in properties:
            findings.append(
                StandardFinding(
                    rule_name="terraform-sns-no-kms",
                    message=f"SNS topic '{resource_name}' missing KMS encryption",
                    file_path=file_path,
                    line=line or 1,
                    severity=Severity.LOW,
                    category="missing_encryption",
                    snippet=f'resource "aws_sns_topic" "{resource_name}"',
                    cwe_id="CWE-311",
                    additional_info={"resource_id": resource_id},
                )
            )

    return findings


def _check_security_groups(
    db: RuleDB, all_props: dict[str, dict[str, Any]]
) -> list[StandardFinding]:
    """Check for overly permissive security groups."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("terraform_resources")
        .select("resource_id", "file_path", "resource_name", "line")
        .where("resource_type IN ('aws_security_group', 'aws_security_group_rule')")
    )

    for resource_id, file_path, resource_name, line in rows:
        properties = all_props.get(resource_id, {})
        ingress_rules = properties.get("ingress", [])
        if isinstance(ingress_rules, dict):
            ingress_rules = [ingress_rules]

        for rule in ingress_rules:
            if not isinstance(rule, dict):
                continue

            cidr_blocks = rule.get("cidr_blocks", [])
            if "0.0.0.0/0" not in cidr_blocks:
                continue

            from_port = rule.get("from_port", 0)
            to_port = rule.get("to_port", from_port)
            severity = Severity.MEDIUM if from_port in (80, 443) else Severity.HIGH

            findings.append(
                StandardFinding(
                    rule_name="terraform-open-security-group",
                    message=(
                        f"Security group '{resource_name}' allows ingress from 0.0.0.0/0 "
                        f"on ports {from_port}-{to_port}"
                    ),
                    file_path=file_path,
                    line=line or 1,
                    severity=severity,
                    category="public_exposure",
                    snippet=f"ingress {{ from_port = {from_port} to_port = {to_port} }}",
                    cwe_id="CWE-284",
                    additional_info={"resource_id": resource_id},
                )
            )

    return findings


def _load_json(raw: Any) -> Any:
    """Parse structured value or return as-is.

    Database contains mixed formats from Terraform parser:
    - None/empty: return empty dict
    - Already parsed (dict/list): return as-is
    - JSON string (double quotes): parse with json.loads
    - Python literal (single quotes): parse with ast.literal_eval
    - Plain string (Terraform expression): return as-is
    """
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return {}
        # Only parse if it looks like a structured value (object/array)
        if stripped.startswith("{") or stripped.startswith("["):
            # Try JSON first (double quotes), then Python literal (single quotes)
            if '"' in stripped:
                return json.loads(raw)
            else:
                return ast.literal_eval(raw)
        # Plain string (Terraform expression like "data.aws_ami.id")
        return raw
    # Unknown type - return as-is
    return raw


def _bulk_load_all_properties(db: RuleDB) -> dict[str, dict[str, Any]]:
    """Load ALL resource properties in one query. O(1) lookup after."""
    rows = db.query(
        Q("terraform_resource_properties").select("resource_id", "property_name", "property_value")
    )

    props_map: dict[str, dict[str, Any]] = {}
    for resource_id, property_name, property_value in rows:
        if resource_id not in props_map:
            props_map[resource_id] = {}
        if property_value:
            props_map[resource_id][property_name] = _load_json(property_value)
        else:
            props_map[resource_id][property_name] = property_value
    return props_map


def _bulk_load_sensitive_props(db: RuleDB) -> dict[str, set[str]]:
    """Load ALL sensitive property names in one query. O(1) lookup after."""
    rows = db.query(
        Q("terraform_resource_properties")
        .select("resource_id", "property_name")
        .where("is_sensitive = 1")
    )

    sensitive_map: dict[str, set[str]] = {}
    for resource_id, property_name in rows:
        if resource_id not in sensitive_map:
            sensitive_map[resource_id] = set()
        sensitive_map[resource_id].add(property_name)
    return sensitive_map


def _is_high_entropy_secret(value: str, threshold: float = 4.0) -> bool:
    """Check if value has high entropy indicating a secret."""
    if not value or len(value) < 10:
        return False
    if any(ch.isspace() for ch in value):
        return False
    entropy = EntropyCalculator.calculate(value)
    return entropy >= threshold
