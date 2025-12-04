"""GitHub Actions Artifact Poisoning Detection."""

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
    name="github_actions_artifact_poisoning",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def find_artifact_poisoning_risk(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect artifact poisoning via untrusted build → trusted deploy chain."""
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
                SELECT DISTINCT j.job_id, j.job_key
                FROM github_jobs j
                JOIN github_steps s ON j.job_id = s.job_id
                WHERE j.workflow_path = ?
                AND s.uses_action = 'actions/upload-artifact'
            """,
                (workflow_path,),
            )

            upload_jobs = [
                {"job_id": row["job_id"], "job_key": row["job_key"]} for row in cursor.fetchall()
            ]

            if not upload_jobs:
                continue

            cursor.execute(
                """
                SELECT DISTINCT j.job_id, j.job_key, j.permissions
                FROM github_jobs j
                JOIN github_steps s ON j.job_id = s.job_id
                WHERE j.workflow_path = ?
                AND s.uses_action = 'actions/download-artifact'
            """,
                (workflow_path,),
            )

            for download_row in cursor.fetchall():
                download_job_id = download_row["job_id"]
                download_job_key = download_row["job_key"]

                has_dependency = _check_job_dependency(
                    download_job_id=download_job_id,
                    upload_jobs=[uj["job_id"] for uj in upload_jobs],
                    cursor=cursor,
                )

                if not has_dependency:
                    pass

                dangerous_ops = _check_dangerous_operations(download_job_id, cursor)

                if dangerous_ops:
                    permissions = _parse_permissions(download_row["permissions"])

                    findings.append(
                        _build_artifact_poisoning_finding(
                            workflow_path=workflow_path,
                            workflow_name=workflow_name,
                            upload_jobs=[uj["job_key"] for uj in upload_jobs],
                            download_job_key=download_job_key,
                            dangerous_ops=dangerous_ops,
                            permissions=permissions,
                            has_dependency=has_dependency,
                        )
                    )

    finally:
        conn.close()

    return findings


def _check_job_dependency(download_job_id: str, upload_jobs: list[str], cursor) -> bool:
    """Check if download job depends on any upload job."""
    cursor.execute(
        """
        SELECT needs_job_id
        FROM github_job_dependencies
        WHERE job_id = ?
    """,
        (download_job_id,),
    )

    dependencies = [row["needs_job_id"] for row in cursor.fetchall()]

    return any(upload_job in dependencies for upload_job in upload_jobs)


def _check_dangerous_operations(job_id: str, cursor) -> list[str]:
    """Check if job performs dangerous operations on downloaded artifacts."""
    dangerous_ops = []

    cursor.execute(
        """
        SELECT run_script, step_name
        FROM github_steps
        WHERE job_id = ?
        AND run_script IS NOT NULL
    """,
        (job_id,),
    )

    dangerous_patterns = {
        "deploy": ["aws s3 sync", "kubectl apply", "terraform apply", "gcloud", "az deployment"],
        "sign": ["cosign sign", "gpg --sign", "signtool", "codesign"],
        "publish": ["npm publish", "pip upload", "docker push", "gh release create"],
    }

    for row in cursor.fetchall():
        script = row["run_script"].lower()

        for op_type, patterns in dangerous_patterns.items():
            if any(pattern in script for pattern in patterns) and op_type not in dangerous_ops:
                dangerous_ops.append(op_type)

    return dangerous_ops


def _parse_permissions(permissions_json: str) -> dict:
    """Parse permissions JSON string."""
    if not permissions_json:
        return {}

    try:
        return json.loads(permissions_json)
    except json.JSONDecodeError:
        return {}


def _build_artifact_poisoning_finding(
    workflow_path: str,
    workflow_name: str,
    upload_jobs: list[str],
    download_job_key: str,
    dangerous_ops: list[str],
    permissions: dict,
    has_dependency: bool,
) -> StandardFinding:
    """Build finding for artifact poisoning vulnerability."""

    has_write_perms = any(
        perm in permissions and permissions[perm] in ("write", "write-all")
        for perm in ["contents", "packages", "id-token", "deployments"]
    )

    if "deploy" in dangerous_ops or "publish" in dangerous_ops or "sign" in dangerous_ops:
        severity = Severity.CRITICAL
    elif has_write_perms:
        severity = Severity.HIGH
    else:
        severity = Severity.MEDIUM

    ops_str = ", ".join(dangerous_ops)
    upload_str = ", ".join(upload_jobs[:3])
    if len(upload_jobs) > 3:
        upload_str += f" (+{len(upload_jobs) - 3} more)"

    message = (
        f"Workflow '{workflow_name}' job '{download_job_key}' downloads artifacts from "
        f"untrusted build job(s) [{upload_str}] and performs dangerous operations: {ops_str}. "
        f"Attacker can poison artifacts in pull_request_target context."
    )

    code_snippet = f"""
# Vulnerable Pattern:
on:
  pull_request_target:  # VULN: Untrusted context

jobs:
  {upload_jobs[0] if upload_jobs else "build"}:
    # Builds with attacker-controlled code
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: npm run build  # Attacker controls this
      - uses: actions/upload-artifact@v3  # Uploads poisoned artifact

  {download_job_key}:
    needs: [{upload_str}]
    steps:
      - uses: actions/download-artifact@v3  # Downloads poisoned artifact
      - run: |
          # VULN: Deploys/signs without validation
          {ops_str}
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "upload_jobs": upload_jobs,
        "download_job": download_job_key,
        "dangerous_operations": dangerous_ops,
        "permissions": permissions,
        "has_direct_dependency": has_dependency,
        "mitigation": (
            "1. Validate artifact integrity before deployment (checksums, signatures), or "
            "2. Build artifacts in trusted context (push trigger, not pull_request_target), or "
            "3. Require manual approval before deploying PR artifacts, or "
            "4. Use separate workflows: PR for testing, push for deployment"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="artifact_poisoning_risk",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-494",
        additional_info=details,
    )
