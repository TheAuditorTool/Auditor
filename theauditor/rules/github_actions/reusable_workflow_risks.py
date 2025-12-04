"""GitHub Actions Reusable Workflow Security Risks Detection."""
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.utils.logging import logger

METADATA = RuleMetadata(
    name="github_actions_reusable_workflow_risks",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def find_external_reusable_with_secrets(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect external reusable workflows with secret access."""
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT j.job_id, j.workflow_path, j.job_key, j.job_name,
                   j.uses_reusable_workflow, j.reusable_workflow_path,
                   w.workflow_name
            FROM github_jobs j
            JOIN github_workflows w ON j.workflow_path = w.workflow_path
            WHERE j.uses_reusable_workflow = 1
            AND j.reusable_workflow_path IS NOT NULL
        """)

        for row in cursor.fetchall():
            reusable_path = row["reusable_workflow_path"]

            if "@" not in reusable_path:
                continue

            workflow_ref, version = reusable_path.rsplit("@", 1)

            is_external = not workflow_ref.startswith("./")

            if not is_external:
                continue

            is_mutable = version in {"main", "master", "develop", "v1", "v2", "v3"}

            cursor.execute("""
                SELECT step_id
                FROM github_step_references
                WHERE reference_type = 'secrets'
                AND step_id IS NOT NULL
            """)

            job_prefix = f"{row['job_id']}::"
            secret_count = sum(
                1 for (step_id,) in cursor.fetchall() if step_id.startswith(job_prefix)
            )

            if is_mutable or secret_count > 0:
                findings.append(
                    _build_reusable_workflow_finding(
                        workflow_path=row["workflow_path"],
                        workflow_name=row["workflow_name"],
                        job_key=row["job_key"],
                        job_name=row["job_name"],
                        reusable_path=reusable_path,
                        workflow_ref=workflow_ref,
                        version=version,
                        is_mutable=is_mutable,
                        secret_count=secret_count,
                    )
                )

    finally:
        conn.close()

    return findings


def _build_reusable_workflow_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    job_name: str,
    reusable_path: str,
    workflow_ref: str,
    version: str,
    is_mutable: bool,
    secret_count: int,
) -> StandardFinding:
    """Build finding for reusable workflow risk."""

    if is_mutable and secret_count > 0 or secret_count > 2:
        severity = Severity.HIGH
    elif is_mutable:
        severity = Severity.MEDIUM
    else:
        severity = Severity.MEDIUM

    risk_factors = []
    if is_mutable:
        risk_factors.append(f"mutable version ({version})")
    if secret_count > 0:
        risk_factors.append(f"{secret_count} secret(s) passed")

    risk_str = " + ".join(risk_factors) if risk_factors else "external workflow"

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' calls external reusable workflow "
        f"'{workflow_ref}' with {risk_str}. "
        f"External organization gains access to repository secrets."
    )

    code_snippet = f"""
# Vulnerable Pattern:
name: {workflow_name}

jobs:
  {job_key}:
    uses: {reusable_path}  # VULN: External workflow with secrets
    secrets: inherit  # or explicit secret passing
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "job_key": job_key,
        "job_name": job_name,
        "reusable_workflow_path": reusable_path,
        "reusable_workflow_ref": workflow_ref,
        "version": version,
        "is_mutable_version": is_mutable,
        "secret_count": secret_count,
        "mitigation": (
            f"1. Pin reusable workflow to immutable SHA: {workflow_ref}@<sha256>, or "
            "2. Pass only required secrets explicitly (not secrets: inherit), or "
            "3. Use internal reusable workflows (./.github/workflows/...) instead"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="external_reusable_with_secrets",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-200",
        additional_info=details,
    )
