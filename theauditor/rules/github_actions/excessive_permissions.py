"""GitHub Actions Excessive Permissions Detection."""

import json
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.utils.logging import logger

METADATA = RuleMetadata(
    name="github_actions_excessive_permissions",
    category="access-control",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database")


UNTRUSTED_TRIGGERS: set[str] = {
    "pull_request_target",
    "issue_comment",
    "workflow_run",
}


DANGEROUS_WRITE_PERMISSIONS: set[str] = {
    "contents",
    "packages",
    "id-token",
    "deployments",
}


def find_excessive_pr_permissions(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect excessive write permissions in untrusted workflows."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT workflow_path, workflow_name, on_triggers, permissions
            FROM github_workflows
        """)

        for workflow_row in cursor.fetchall():
            workflow_path = workflow_row["workflow_path"]
            workflow_name = workflow_row["workflow_name"]

            try:
                triggers = (
                    json.loads(workflow_row["on_triggers"]) if workflow_row["on_triggers"] else []
                )
            except json.JSONDecodeError:
                triggers = []

            has_untrusted = any(trigger in UNTRUSTED_TRIGGERS for trigger in triggers)
            if not has_untrusted:
                continue

            workflow_perms = _parse_permissions(workflow_row["permissions"])
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

            cursor.execute(
                """
                SELECT job_id, job_key, job_name, permissions
                FROM github_jobs
                WHERE workflow_path = ?
            """,
                (workflow_path,),
            )

            for job_row in cursor.fetchall():
                job_perms = _parse_permissions(job_row["permissions"])
                if job_perms:
                    dangerous = _check_dangerous_permissions(job_perms)
                    if dangerous:
                        findings.append(
                            _build_permission_finding(
                                workflow_path=workflow_path,
                                workflow_name=workflow_name,
                                scope="job",
                                job_key=job_row["job_key"],
                                triggers=triggers,
                                dangerous_perms=dangerous,
                                all_perms=job_perms,
                            )
                        )

    finally:
        conn.close()

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

    if "write-all" in dangerous_perms or "id-token" in dangerous_perms:
        severity = Severity.CRITICAL
    elif "contents" in dangerous_perms or "packages" in dangerous_perms:
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
