"""AWS CDK IAM Wildcard Detection - database-first rule.

Detects IAM policies with overly permissive wildcards and privilege escalation
patterns in CDK code:
- Wildcard actions (actions: ["*"])
- Wildcard resources (resources: ["*"])
- AdministratorAccess/PowerUserAccess managed policies
- Privilege escalation actions (iam:PassRole/*, sts:AssumeRole/*, iam:Create*/*)
- NotAction usage (inverted logic often grants more than intended)

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

DANGEROUS_MANAGED_POLICIES = frozenset([
    "AdministratorAccess",
    "PowerUserAccess",
    "IAMFullAccess",
])

PRIVILEGE_ESCALATION_ACTIONS = frozenset([
    "iam:PassRole",
    "iam:CreateUser",
    "iam:CreateAccessKey",
    "iam:AttachUserPolicy",
    "iam:AttachRolePolicy",
    "iam:AttachGroupPolicy",
    "iam:PutUserPolicy",
    "iam:PutRolePolicy",
    "iam:PutGroupPolicy",
    "iam:CreatePolicyVersion",
    "iam:SetDefaultPolicyVersion",
    "iam:CreateLoginProfile",
    "iam:UpdateLoginProfile",
    "sts:AssumeRole",
    "lambda:CreateFunction",
    "lambda:InvokeFunction",
    "lambda:UpdateFunctionCode",
])


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
        findings.extend(_check_dangerous_managed_policies(db))
        findings.extend(_check_privilege_escalation_actions(db))
        findings.extend(_check_not_action_usage(db))

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


def _check_dangerous_managed_policies(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM roles with dangerous managed policies attached.

    Detects AdministratorAccess, PowerUserAccess, and IAMFullAccess which
    grant excessive permissions and are rarely appropriate for application roles.
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
            for policy_name in DANGEROUS_MANAGED_POLICIES:
                if policy_name in prop_value:
                    severity = Severity.CRITICAL if policy_name == "AdministratorAccess" else Severity.HIGH
                    findings.append(
                        StandardFinding(
                            rule_name=f"aws-cdk-iam-{policy_name.lower().replace('access', '-access')}",
                            message=f"IAM role '{display_name}' has {policy_name} policy attached",
                            severity=severity,
                            confidence="high",
                            file_path=file_path,
                            line=prop_line,
                            snippet=f"managed_policies={prop_value}",
                            category="excessive_permissions",
                            cwe_id="CWE-269",
                            additional_info={
                                "construct_id": construct_id,
                                "construct_name": display_name,
                                "policy_name": policy_name,
                                "remediation": f"Remove {policy_name} and create custom policies with only required permissions.",
                            },
                        )
                    )

    return findings


def _check_privilege_escalation_actions(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM policies with privilege escalation actions.

    These actions can be used to escalate privileges if granted with wildcards:
    - iam:PassRole - allows passing any role to services
    - iam:CreateUser/AttachUserPolicy - create users with arbitrary permissions
    - sts:AssumeRole - assume any role in the account
    - lambda:CreateFunction - create functions that run with any role
    """
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
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        props = {row[0]: (row[1], row[2]) for row in prop_rows}

        actions_key = "actions"
        resources_key = "resources"

        if actions_key not in props:
            continue

        actions_value, actions_line = props[actions_key]
        resources_value = props.get(resources_key, ("", line))[0]
        has_wildcard_resource = "'*'" in resources_value or '"*"' in resources_value or not resources_value

        for action in PRIVILEGE_ESCALATION_ACTIONS:
            if action.lower() in actions_value.lower():
                if has_wildcard_resource:
                    findings.append(
                        StandardFinding(
                            rule_name="aws-cdk-iam-privilege-escalation",
                            message=f"IAM policy '{display_name}' grants '{action}' with wildcard resources - privilege escalation risk",
                            severity=Severity.CRITICAL,
                            confidence="high",
                            file_path=file_path,
                            line=actions_line,
                            snippet=f"actions containing {action}",
                            category="privilege_escalation",
                            cwe_id="CWE-269",
                            additional_info={
                                "construct_id": construct_id,
                                "construct_name": display_name,
                                "dangerous_action": action,
                                "remediation": f"Restrict '{action}' to specific resource ARNs instead of wildcards.",
                            },
                        )
                    )

    return findings


def _check_not_action_usage(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM policies using NotAction.

    NotAction with Allow effect grants all actions EXCEPT those listed,
    which often grants far more permissions than intended. This is a
    common IAM misconfiguration pattern.
    """
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
            .select("property_name", "property_value_expr", "line")
            .where("construct_id = ?", construct_id)
        )

        props = {row[0]: (row[1], row[2]) for row in prop_rows}

        not_actions_key = next(
            (k for k in props if k in ("not_actions", "notActions")),
            None,
        )

        if not_actions_key:
            prop_value, prop_line = props[not_actions_key]
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-iam-not-action",
                    message=f"IAM policy '{display_name}' uses NotAction - grants all actions except those listed",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=prop_line,
                    snippet=f"{not_actions_key}={prop_value}",
                    category="excessive_permissions",
                    cwe_id="CWE-269",
                    additional_info={
                        "construct_id": construct_id,
                        "construct_name": display_name,
                        "remediation": "Replace NotAction with explicit 'actions' list. NotAction often grants more permissions than intended.",
                    },
                )
            )

    return findings
