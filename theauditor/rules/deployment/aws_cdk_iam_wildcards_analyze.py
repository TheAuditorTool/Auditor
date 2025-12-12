"""AWS CDK IAM Wildcard Detection - database-first rule.

Detects IAM policies with overly permissive wildcards and privilege escalation
patterns in CDK code:
- Wildcard actions (actions: ["*"])
- Wildcard resources (resources: ["*"])
- AdministratorAccess/PowerUserAccess managed policies
- Privilege escalation actions (iam:PassRole/*, sts:AssumeRole/*, iam:Create*/*)
- NotAction usage (inverted logic often grants more than intended)
- Dynamic add_to_policy() method calls with wildcards

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

DANGEROUS_MANAGED_POLICIES = frozenset(
    [
        "AdministratorAccess",
        "PowerUserAccess",
        "IAMFullAccess",
    ]
)

PRIVILEGE_ESCALATION_ACTIONS = frozenset(
    [
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
    ]
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
        findings.extend(_check_dangerous_managed_policies(db))
        findings.extend(_check_privilege_escalation_actions(db))
        findings.extend(_check_not_action_usage(db))
        findings.extend(_check_add_to_policy(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_wildcard_actions(db: RuleDB) -> list[StandardFinding]:
    """Detect IAM policies with wildcard actions.

    Uses single JOIN query instead of N+1 pattern.
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("cdk_constructs")
        .select(
            "cdk_constructs.construct_id",
            "cdk_constructs.file_path",
            "cdk_constructs.construct_name",
            "cdk_constructs.cdk_class",
            "cdk_construct_properties.property_value_expr",
            "cdk_construct_properties.line",
        )
        .join("cdk_construct_properties", on=[("construct_id", "construct_id")])
        .where(
            "(cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?) AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%Policy%",
            "%PolicyStatement%",
            "%iam%",
            "%aws_iam%",
        )
        .where("cdk_construct_properties.property_name = ?", "actions")
    )

    for construct_id, file_path, construct_name, _cdk_class, prop_value, prop_line in rows:
        if not prop_value:
            continue
        if "'*'" in prop_value or '"*"' in prop_value:
            display_name = construct_name or "UnnamedPolicy"
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
    """Detect IAM policies with wildcard resources.

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
            "(cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?) AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%Policy%",
            "%PolicyStatement%",
            "%iam%",
            "%aws_iam%",
        )
        .where("cdk_construct_properties.property_name = ?", "resources")
    )

    for construct_id, file_path, construct_name, prop_value, prop_line in rows:
        if not prop_value:
            continue
        if "'*'" in prop_value or '"*"' in prop_value:
            display_name = construct_name or "UnnamedPolicy"
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
            "%Role%",
            "%iam%",
            "%aws_iam%",
        )
        .where("cdk_construct_properties.property_name = ?", "managed_policies")
    )

    for construct_id, file_path, construct_name, prop_value, prop_line in rows:
        if not prop_value:
            continue

        display_name = construct_name or "UnnamedRole"

        for policy_name in DANGEROUS_MANAGED_POLICIES:
            if policy_name in prop_value:
                severity = (
                    Severity.CRITICAL if policy_name == "AdministratorAccess" else Severity.HIGH
                )
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

    Uses 2-query pattern: get policy constructs, get all their properties, match in Python.
    """
    findings: list[StandardFinding] = []

    # Query 1: Get all IAM Policy/PolicyStatement constructs
    all_policies = db.query(
        Q("cdk_constructs")
        .select("construct_id", "file_path", "line", "construct_name")
        .where(
            "(cdk_class LIKE ? OR cdk_class LIKE ?) AND (cdk_class LIKE ? OR cdk_class LIKE ?)",
            "%Policy%",
            "%PolicyStatement%",
            "%iam%",
            "%aws_iam%",
        )
    )

    if not all_policies:
        return []

    policy_map = {row[0]: (row[1], row[2], row[3]) for row in all_policies}

    # Query 2: Get actions and resources properties for all policies
    prop_rows = db.query(
        Q("cdk_construct_properties")
        .select("construct_id", "property_name", "property_value_expr", "line")
        .where("property_name IN (?, ?)", "actions", "resources")
    )

    # Build property lookup
    props_by_construct: dict[str, dict[str, tuple]] = {}
    for cid, pname, pval, pline in prop_rows:
        if cid not in props_by_construct:
            props_by_construct[cid] = {}
        props_by_construct[cid][pname] = (pval, pline)

    for construct_id, (file_path, line, construct_name) in policy_map.items():
        props = props_by_construct.get(construct_id, {})

        if "actions" not in props:
            continue

        actions_value, actions_line = props["actions"]
        if not actions_value:
            continue

        resources_value = props.get("resources", ("", line))[0] or ""
        has_wildcard_resource = (
            "'*'" in resources_value or '"*"' in resources_value or not resources_value
        )

        display_name = construct_name or "UnnamedPolicy"

        for action in PRIVILEGE_ESCALATION_ACTIONS:
            if action.lower() in actions_value.lower() and has_wildcard_resource:
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
            "(cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?) AND (cdk_constructs.cdk_class LIKE ? OR cdk_constructs.cdk_class LIKE ?)",
            "%Policy%",
            "%PolicyStatement%",
            "%iam%",
            "%aws_iam%",
        )
        .where(
            "cdk_construct_properties.property_name IN (?, ?)",
            "not_actions",
            "notActions",
        )
    )

    for construct_id, file_path, construct_name, prop_name, prop_value, prop_line in rows:
        display_name = construct_name or "UnnamedPolicy"
        findings.append(
            StandardFinding(
                rule_name="aws-cdk-iam-not-action",
                message=f"IAM policy '{display_name}' uses NotAction - grants all actions except those listed",
                severity=Severity.HIGH,
                confidence="high",
                file_path=file_path,
                line=prop_line,
                snippet=f"{prop_name}={prop_value}",
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


def _check_add_to_policy(db: RuleDB) -> list[StandardFinding]:
    """Detect wildcards in dynamic add_to_policy() method calls.

    Uses single query + Python filtering instead of 6 leading-wildcard queries.
    """
    findings: list[StandardFinding] = []

    policy_methods = frozenset({
        "add_to_policy",
        "addToPolicy",
        "add_to_principal_policy",
        "addToPrincipalPolicy",
        "attach_inline_policy",
        "attachInlinePolicy",
    })

    # Single query to get all function calls - filter in Python
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
    )

    for file_path, line, callee, args in rows:
        if not callee or not args:
            continue

        # Extract method name from callee (e.g., "role.add_to_policy" -> "add_to_policy")
        method_name = callee.rsplit(".", 1)[-1] if "." in callee else callee

        if method_name not in policy_methods:
            continue

        args_str = args

        has_wildcard_action = "'*'" in args_str or '"*"' in args_str
        has_actions_context = "actions" in args_str.lower() or "Actions" in args_str

        if has_wildcard_action and has_actions_context:
            findings.append(
                StandardFinding(
                    rule_name="aws-cdk-iam-add-to-policy-wildcard",
                    message=f"Dynamic policy addition '{callee}' contains wildcard permissions",
                    severity=Severity.HIGH,
                    confidence="high",
                    file_path=file_path,
                    line=line,
                    snippet=f"{callee}(...)" if len(args_str) > 50 else f"{callee}({args_str})",
                    category="excessive_permissions",
                    cwe_id="CWE-269",
                    additional_info={
                        "method": callee,
                        "remediation": "Replace wildcard actions with specific actions following least privilege principle.",
                    },
                )
            )

        for action in PRIVILEGE_ESCALATION_ACTIONS:
            if action.lower() in args_str.lower():
                findings.append(
                    StandardFinding(
                        rule_name="aws-cdk-iam-add-to-policy-privilege-escalation",
                        message=f"Dynamic policy addition '{callee}' contains privilege escalation action: {action}",
                        severity=Severity.CRITICAL,
                        confidence="high",
                        file_path=file_path,
                        line=line,
                        snippet=f"{callee}(...)",
                        category="privilege_escalation",
                        cwe_id="CWE-269",
                        additional_info={
                            "method": callee,
                            "dangerous_action": action,
                            "remediation": f"Restrict '{action}' to specific resource ARNs instead of wildcards.",
                        },
                    )
                )
                break

    return findings
