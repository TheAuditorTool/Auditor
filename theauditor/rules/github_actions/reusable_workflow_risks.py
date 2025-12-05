"""GitHub Actions Reusable Workflow Security Risks Detection.

Detects external reusable workflows with mutable versions or secret access.

Tables Used:
- github_jobs: Job definitions with reusable workflow references
- github_workflows: Workflow metadata
- github_step_references: Secret references in steps

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
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
    name="github_actions_reusable_workflow_risks",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_jobs",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect external reusable workflows with secret access.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_reusable_workflow_risks(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_external_reusable_with_secrets(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


# =============================================================================
# DETECTION LOGIC
# =============================================================================

# Mutable version references that can change without notice
MUTABLE_VERSIONS = frozenset({"main", "master", "develop", "v1", "v2", "v3"})


def _find_reusable_workflow_risks(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for reusable workflow risks."""
    findings: list[StandardFinding] = []

    # Get all jobs that use reusable workflows with JOIN to get workflow name
    sql, params = Q.raw(
        """
        SELECT j.job_id, j.workflow_path, j.job_key, j.job_name,
               j.reusable_workflow_path, w.workflow_name
        FROM github_jobs j
        JOIN github_workflows w ON j.workflow_path = w.workflow_path
        WHERE j.uses_reusable_workflow = 1
        AND j.reusable_workflow_path IS NOT NULL
        """,
        [],
    )
    job_rows = db.execute(sql, params)

    for job_id, workflow_path, job_key, job_name, reusable_path, workflow_name in job_rows:
        # Parse reusable workflow path (e.g., "org/repo/.github/workflows/file.yml@v1")
        if "@" not in reusable_path:
            continue

        workflow_ref, version = reusable_path.rsplit("@", 1)

        # Only check external workflows (not local ./)
        if workflow_ref.startswith("./"):
            continue

        # Check if version is mutable
        is_mutable = version in MUTABLE_VERSIONS

        # Count secrets passed to this job
        secret_rows = db.query(
            Q("github_step_references")
            .select("step_id")
            .where("reference_type = ?", "secrets")
            .where("step_id IS NOT NULL")
        )

        job_prefix = f"{job_id}::"
        secret_count = sum(1 for (step_id,) in secret_rows if step_id.startswith(job_prefix))

        # Flag if mutable version or secrets are passed
        if is_mutable or secret_count > 0:
            findings.append(
                _build_reusable_workflow_finding(
                    workflow_path=workflow_path,
                    workflow_name=workflow_name,
                    job_key=job_key,
                    job_name=job_name,
                    reusable_path=reusable_path,
                    workflow_ref=workflow_ref,
                    version=version,
                    is_mutable=is_mutable,
                    secret_count=secret_count,
                )
            )

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
