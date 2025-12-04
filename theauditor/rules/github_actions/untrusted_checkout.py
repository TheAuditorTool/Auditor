"""GitHub Actions Untrusted Checkout Sequence Detection."""

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
    name="github_actions_untrusted_checkout",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def find_untrusted_checkout_sequence(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect untrusted code checkout in pull_request_target workflows."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT workflow_path, workflow_name, on_triggers
            FROM github_workflows
            WHERE on_triggers IS NOT NULL
        """)

        for workflow_row in cursor.fetchall():
            workflow_path = workflow_row["workflow_path"]
            workflow_name = workflow_row["workflow_name"]
            on_triggers = workflow_row["on_triggers"] or ""

            if "pull_request_target" not in on_triggers:
                continue

            cursor.execute(
                """
                SELECT j.job_id, j.job_key, j.job_name, j.permissions
                FROM github_jobs j
                WHERE j.workflow_path = ?
                ORDER BY j.job_key
            """,
                (workflow_path,),
            )

            for job_row in cursor.fetchall():
                job_id = job_row["job_id"]
                job_key = job_row["job_key"]

                cursor.execute(
                    """
                    SELECT s.step_id, s.step_name, s.sequence_order, s.with_args
                    FROM github_steps s
                    WHERE s.job_id = ?
                    AND s.uses_action = 'actions/checkout'
                    ORDER BY s.sequence_order
                """,
                    (job_id,),
                )

                for step_row in cursor.fetchall():
                    step_id = step_row["step_id"]
                    step_name = step_row["step_name"] or "Unnamed checkout"
                    sequence_order = step_row["sequence_order"]
                    with_args = step_row["with_args"]

                    is_untrusted = _check_untrusted_ref(step_id, with_args, cursor)

                    if is_untrusted and sequence_order < 3:
                        permissions_json = job_row["permissions"]
                        permissions = json.loads(permissions_json) if permissions_json else {}

                        findings.append(
                            _build_untrusted_checkout_finding(
                                workflow_path=workflow_path,
                                workflow_name=workflow_name,
                                job_key=job_key,
                                step_name=step_name,
                                sequence_order=sequence_order,
                                permissions=permissions,
                                with_args=with_args,
                            )
                        )

    finally:
        conn.close()

    return findings


def _check_untrusted_ref(step_id: str, with_args: str, cursor) -> bool:
    """Check if checkout step uses untrusted PR ref."""

    if with_args:
        try:
            args = json.loads(with_args)
            ref = args.get("ref", "")

            if "github.event.pull_request.head" in ref:
                return True

        except json.JSONDecodeError:
            pass

    cursor.execute(
        """
        SELECT reference_path
        FROM github_step_references
        WHERE step_id = ?
        AND reference_location = 'with'
        AND reference_path IS NOT NULL
    """,
        (step_id,),
    )

    for (reference_path,) in cursor.fetchall():
        if reference_path.startswith("github.event.pull_request.head"):
            return True

    return False


def _build_untrusted_checkout_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    step_name: str,
    sequence_order: int,
    permissions: dict,
    with_args: str,
) -> StandardFinding:
    """Build finding for untrusted checkout vulnerability."""

    has_write_perms = any(
        perm in permissions and permissions[perm] in ("write", "write-all")
        for perm in ["contents", "packages", "pull-requests", "id-token"]
    )

    severity = Severity.CRITICAL if has_write_perms else Severity.HIGH

    try:
        args = json.loads(with_args) if with_args else {}
        ref_value = args.get("ref", "github.event.pull_request.head.sha")
    except json.JSONDecodeError:
        ref_value = "unknown"

    message = (
        f"Workflow '{workflow_name}' checks out untrusted PR code at step #{sequence_order + 1} "
        f"in job '{job_key}' with pull_request_target trigger. "
        f"Attacker-controlled code can execute with {'write permissions' if has_write_perms else 'read permissions'}."
    )

    code_snippet = f"""
# Vulnerable Pattern:
on:
  pull_request_target:  # Runs in target context with secrets

jobs:
  {job_key}:
    steps:
      - name: {step_name}
        uses: actions/checkout@v4
        with:
          ref: {ref_value}  # VULN: Untrusted attacker code
    """

    details = {
        "workflow": workflow_path,
        "job_key": job_key,
        "step_name": step_name,
        "step_order": sequence_order,
        "permissions": permissions,
        "has_write_permissions": has_write_perms,
        "checkout_ref": ref_value,
        "mitigation": (
            "1. Use pull_request trigger instead of pull_request_target, or "
            "2. Add validation job that runs first with 'needs:' dependency, or "
            "3. Only checkout base branch code in early steps"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="untrusted_checkout_sequence",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-284",
        additional_info=details,
    )
