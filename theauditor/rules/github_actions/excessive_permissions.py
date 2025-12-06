"""GitHub Actions Excessive Permissions Detection.

Detects workflows with dangerous write permissions in untrusted trigger contexts
(pull_request_target, issue_comment, workflow_run).

Tables Used:
- github_workflows: Workflow metadata, triggers, and permissions
- github_jobs: Job-level permissions

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
"""

import json

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
    name="github_actions_excessive_permissions",
    category="access-control",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_workflows",
)


UNTRUSTED_TRIGGERS = frozenset(
    [
        "pull_request_target",
        "issue_comment",
        "workflow_run",
        "discussion_comment",
    ]
)


DANGEROUS_WRITE_PERMISSIONS = frozenset(
    [
        "contents",
        "actions",
        "id-token",
        "security-events",
        "packages",
        "deployments",
        "statuses",
        "checks",
        "pull-requests",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect excessive write permissions in untrusted workflows.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_excessive_permissions(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_excessive_pr_permissions(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


def _find_excessive_permissions(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for excessive permissions."""
    findings: list[StandardFinding] = []

    workflow_rows = db.query(
        Q("github_workflows").select("workflow_path", "workflow_name", "on_triggers", "permissions")
    )

    for workflow_path, workflow_name, on_triggers_json, permissions_json in workflow_rows:
        try:
            triggers = json.loads(on_triggers_json) if on_triggers_json else []
        except json.JSONDecodeError:
            triggers = []

        has_untrusted = any(trigger in UNTRUSTED_TRIGGERS for trigger in triggers)
        if not has_untrusted:
            continue

        workflow_perms = _parse_permissions(permissions_json)
        if workflow_perms:
            dangerous = _check_dangerous_permissions(workflow_perms)
            if dangerous:
                findings.append(
                    _build_permission_finding(
                        workflow_path=workflow_path,
                        workflow_name=workflow_name,
                        scope="workflow",
                        job_key=None,
                        triggers=triggers,
                        dangerous_perms=dangerous,
                        all_perms=workflow_perms,
                    )
                )

        job_rows = db.query(
            Q("github_jobs")
            .select("job_key", "permissions")
            .where("workflow_path = ?", workflow_path)
        )

        for job_key, job_perms_json in job_rows:
            job_perms = _parse_permissions(job_perms_json)
            if job_perms:
                dangerous = _check_dangerous_permissions(job_perms)
                if dangerous:
                    findings.append(
                        _build_permission_finding(
                            workflow_path=workflow_path,
                            workflow_name=workflow_name,
                            scope="job",
                            job_key=job_key,
                            triggers=triggers,
                            dangerous_perms=dangerous,
                            all_perms=job_perms,
                        )
                    )

    return findings


def _parse_permissions(permissions_json: str) -> dict:
    """Parse permissions JSON string."""
    if not permissions_json:
        return {}

    try:
        perms = json.loads(permissions_json)
        if isinstance(perms, dict):
            return perms
        elif isinstance(perms, str) and perms in ["write-all", "read-all"]:
            return {"__all__": perms}
    except json.JSONDecodeError:
        pass

    return {}


def _check_dangerous_permissions(permissions: dict) -> list[str]:
    """Check for dangerous write permissions."""
    dangerous = []

    if permissions.get("__all__") == "write-all":
        return ["write-all"]

    for perm_name, perm_level in permissions.items():
        if perm_name in DANGEROUS_WRITE_PERMISSIONS and perm_level in ["write", "write-all"]:
            dangerous.append(perm_name)

    return dangerous


CRITICAL_PERMISSIONS = frozenset(
    ["write-all", "contents", "actions", "id-token", "security-events"]
)

HIGH_PERMISSIONS = frozenset(["packages", "deployments", "statuses", "checks", "pull-requests"])


def _build_permission_finding(
    workflow_path: str,
    workflow_name: str,
    scope: str,
    job_key: str,
    triggers: list[str],
    dangerous_perms: list[str],
    all_perms: dict,
) -> StandardFinding:
    """Build finding for excessive permissions vulnerability."""

    perms_set = set(dangerous_perms)
    if perms_set & CRITICAL_PERMISSIONS:
        severity = Severity.CRITICAL
    elif perms_set & HIGH_PERMISSIONS:
        severity = Severity.HIGH
    else:
        severity = Severity.MEDIUM

    trigger_str = ", ".join(triggers)
    perms_str = ", ".join(dangerous_perms)

    location = "workflow-level" if scope == "workflow" else f"job '{job_key}'"

    message = (
        f"Workflow '{workflow_name}' grants dangerous write permissions ({perms_str}) at {location} "
        f"with untrusted trigger ({trigger_str}). Attacker PR can abuse these permissions."
    )

    code_snippet = f"""
# Vulnerable Pattern:
name: {workflow_name}

on:
  {trigger_str}  # VULN: Untrusted trigger

{"jobs:" if scope == "job" else ""}
{f"  {job_key}:" if scope == "job" else ""}

permissions:  # VULN: Excessive permissions in untrusted context
  {chr(10).join(f"  {k}: {v}" for k, v in all_perms.items() if k != "__all__")}
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "scope": scope,
        "job_key": job_key,
        "triggers": triggers,
        "dangerous_permissions": dangerous_perms,
        "all_permissions": all_perms,
        "mitigation": (
            "1. Use pull_request trigger instead of pull_request_target, or "
            "2. Reduce permissions to 'read' or remove entirely, or "
            "3. Add validation job with 'needs:' dependency before granting write access"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="excessive_pr_permissions",
        message=message,
        severity=severity,
        category="access-control",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-269",
        additional_info=details,
    )
