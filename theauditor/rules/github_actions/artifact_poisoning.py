"""GitHub Actions Artifact Poisoning Detection.

Detects artifact poisoning via untrusted build -> trusted deploy chain
in pull_request_target workflows.

Tables Used:
- github_workflows: Workflow metadata and triggers
- github_jobs: Job definitions and permissions
- github_steps: Step actions (upload/download artifact)
- github_job_dependencies: Job dependency graph

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
    name="github_actions_artifact_poisoning",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_workflows",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect artifact poisoning via untrusted build -> trusted deploy chain.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_artifact_poisoning(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_artifact_poisoning_risk(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze().

    Maintained for backwards compatibility with __init__.py exports.
    """
    result = analyze(context)
    return result.findings


# =============================================================================
# DETECTION LOGIC
# =============================================================================


def _find_artifact_poisoning(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for artifact poisoning."""
    findings: list[StandardFinding] = []

    # Get all workflows with triggers
    workflow_rows = db.query(
        Q("github_workflows")
        .select("workflow_path", "workflow_name", "on_triggers")
        .where("on_triggers IS NOT NULL")
    )

    for workflow_path, workflow_name, on_triggers in workflow_rows:
        on_triggers = on_triggers or ""

        # Only check pull_request_target workflows (untrusted context)
        if "pull_request_target" not in on_triggers:
            continue

        # Find jobs that upload artifacts
        upload_jobs = _get_upload_jobs(db, workflow_path)
        if not upload_jobs:
            continue

        # Find jobs that download artifacts
        download_jobs = _get_download_jobs(db, workflow_path)

        for download_job_id, download_job_key, permissions_json in download_jobs:
            # Check if download depends on upload (explicit dependency chain)
            has_dependency = _check_job_dependency(
                db, download_job_id, [uj[0] for uj in upload_jobs]
            )

            # Check for dangerous operations on downloaded artifacts
            dangerous_ops = _check_dangerous_operations(db, download_job_id)

            if dangerous_ops:
                permissions = _parse_permissions(permissions_json)

                findings.append(
                    _build_artifact_poisoning_finding(
                        workflow_path=workflow_path,
                        workflow_name=workflow_name,
                        upload_jobs=[uj[1] for uj in upload_jobs],
                        download_job_key=download_job_key,
                        dangerous_ops=dangerous_ops,
                        permissions=permissions,
                        has_dependency=has_dependency,
                    )
                )

    return findings


def _get_upload_jobs(db: RuleDB, workflow_path: str) -> list[tuple[str, str]]:
    """Get jobs that upload artifacts in this workflow."""
    # JOIN github_jobs with github_steps to find upload-artifact usage
    sql, params = Q.raw(
        """
        SELECT DISTINCT j.job_id, j.job_key
        FROM github_jobs j
        JOIN github_steps s ON j.job_id = s.job_id
        WHERE j.workflow_path = ?
        AND s.uses_action = 'actions/upload-artifact'
        """,
        [workflow_path],
    )
    rows = db.execute(sql, params)
    return [(row[0], row[1]) for row in rows]


def _get_download_jobs(db: RuleDB, workflow_path: str) -> list[tuple[str, str, str]]:
    """Get jobs that download artifacts in this workflow."""
    sql, params = Q.raw(
        """
        SELECT DISTINCT j.job_id, j.job_key, j.permissions
        FROM github_jobs j
        JOIN github_steps s ON j.job_id = s.job_id
        WHERE j.workflow_path = ?
        AND s.uses_action = 'actions/download-artifact'
        """,
        [workflow_path],
    )
    rows = db.execute(sql, params)
    return [(row[0], row[1], row[2]) for row in rows]


def _check_job_dependency(db: RuleDB, download_job_id: str, upload_job_ids: list[str]) -> bool:
    """Check if download job depends on any upload job."""
    rows = db.query(
        Q("github_job_dependencies")
        .select("needs_job_id")
        .where("job_id = ?", download_job_id)
    )

    dependencies = {row[0] for row in rows}
    return any(upload_id in dependencies for upload_id in upload_job_ids)


def _check_dangerous_operations(db: RuleDB, job_id: str) -> list[str]:
    """Check if job performs dangerous operations on downloaded artifacts."""
    rows = db.query(
        Q("github_steps")
        .select("run_script")
        .where("job_id = ?", job_id)
        .where("run_script IS NOT NULL")
    )

    dangerous_patterns = {
        "deploy": ["aws s3 sync", "kubectl apply", "terraform apply", "gcloud", "az deployment"],
        "sign": ["cosign sign", "gpg --sign", "signtool", "codesign"],
        "publish": ["npm publish", "pip upload", "docker push", "gh release create"],
    }

    dangerous_ops: list[str] = []
    for (run_script,) in rows:
        script_lower = run_script.lower()

        for op_type, patterns in dangerous_patterns.items():
            if op_type not in dangerous_ops:
                if any(pattern in script_lower for pattern in patterns):
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
