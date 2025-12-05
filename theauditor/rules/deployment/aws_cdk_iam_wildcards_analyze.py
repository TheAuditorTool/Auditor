"""AWS CDK IAM Wildcard Detection - database-first rule.

Detects IAM policies with overly permissive wildcards in CDK code:
- Wildcard actions (actions: ["*"])
- Wildcard resources (resources: ["*"])
- AdministratorAccess managed policy attached to roles

CWE-269: Improper Privilege Management
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
    name="aws_cdk_iam_wildcards",
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
    """Detect IAM policies with overly permissive wildcards in CDK code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_wildcard_actions(db))
        findings.extend(_check_wildcard_resources(db))
        findings.extend(_check_administrator_access(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_wildcard_actions(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM policies with wildcard actions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_policy = "Policy" in cdk_class or "PolicyStatement" in cdk_class
        is_iam = "iam" in cdk_class.lower() or "aws_iam" in cdk_class
        if not (is_policy and is_iam):
            continue

        display_name = construct_name or "UnnamedPolicy"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "actions")
        )

        if prop_rows:
            prop_value, prop_line = prop_rows[0]
            if "'*'" in prop_value or '"*"' in prop_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-iam-wildcard-actions",
                        message=f"IAM policy '{display_name}' grants wildcard actions (*)",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"actions={prop_value}",
                        category="excessive_permissions",
                        cwe_id="CWE-269",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": 'Replace wildcard actions with specific actions following least privilege principle (e.g., ["s3:GetObject", "s3:PutObject"]).',
                        },
                    )
                )

    return findings


def _check_wildcard_resources(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM policies with wildcard resources."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        is_policy = "Policy" in cdk_class or "PolicyStatement" in cdk_class
        is_iam = "iam" in cdk_class.lower() or "aws_iam" in cdk_class
        if not (is_policy and is_iam):
            continue

        display_name = construct_name or "UnnamedPolicy"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "resources")
        )

        if prop_rows:
            prop_value, prop_line = prop_rows[0]
            if "'*'" in prop_value or '"*"' in prop_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-iam-wildcard-resources",
                        message=f"IAM policy '{display_name}' grants access to all resources (*)",
                        severity=Severity.HIGH,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"resources={prop_value}",
                        category="excessive_permissions",
                        cwe_id="CWE-269",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": 'Replace wildcard resources with specific ARNs (e.g., ["arn:aws:s3:::my-bucket/*"]).',
                        },
                    )
                )

    return findings


def _check_administrator_access(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM roles with AdministratorAccess managed policy attached.

    AdministratorAccess grants full AWS account access - this is almost never
    appropriate for application roles and represents a significant security risk.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name", "cdk_class")
    )

    for construct_id, file_path, line, construct_name, cdk_class in rows:
        if not ("Role" in cdk_class and ("iam" in cdk_class.lower() or "aws_iam" in cdk_class)):
            continue

        display_name = construct_name or "UnnamedRole"

        prop_rows = db.query(
            Q("cdk_construct_properties")
            .select("property_value_expr", "line")
            .where("construct_id = ?", construct_id)
            .where("property_name = ?", "managed_policies")
        )

        if prop_rows:
            prop_value, prop_line = prop_rows[0]
            if "AdministratorAccess" in prop_value:
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-iam-administrator-access",
                        message=f"IAM role '{display_name}' has AdministratorAccess policy attached",
                        severity=Severity.CRITICAL,
                        confidence="high",
                        file_path=file_path,
                        line=prop_line,
                        snippet=f"managed_policies={prop_value}",
                        category="excessive_permissions",
                        cwe_id="CWE-269",
                        additional_info={
                            "construct_id": construct_id,
                            "construct_name": display_name,
                            "remediation": "Create custom policies with only the permissions required for this role. AdministratorAccess grants full AWS account access.",
                        },
                    )
                )

    return findings
