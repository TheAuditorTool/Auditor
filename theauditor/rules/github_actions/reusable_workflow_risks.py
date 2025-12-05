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
# These can be force-pushed by upstream at any time, making supply chain attacks trivial
MUTABLE_VERSIONS = frozenset({
    # Branch names
    "main", "master", "develop", "dev", "trunk", "release", "stable",
    # Edge/nightly channels
    "edge", "nightly", "next", "lts", "latest", "canary",
    # Major version tags (not immutable - can be moved)
    "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10",
})


def _find_reusable_workflow_risks(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for reusable workflow risks."""
    findings: list[StandardFinding] = []

    # Get all jobs that use reusable workflows with JOIN to get workflow name
    # Also fetch secrets_config to detect "secrets: inherit" pattern
    sql, params = Q.raw(
        """
        SELECT j.job_id, j.workflow_path, j.job_key, j.job_name,
               j.reusable_workflow_path, j.secrets_config, w.workflow_name
        FROM github_jobs j
        JOIN github_workflows w ON j.workflow_path = w.workflow_path
        WHERE j.uses_reusable_workflow = 1
        AND j.reusable_workflow_path IS NOT NULL
        """,
        [],
    )
    job_rows = db.execute(sql, params)

    for row in job_rows:
        job_id, workflow_path, job_key, job_name, reusable_path, secrets_config, workflow_name = row

        # Parse reusable workflow path (e.g., "org/repo/.github/workflows/file.yml@v1")
        if "@" not in reusable_path:
            continue

        workflow_ref, version = reusable_path.rsplit("@", 1)

        # Only check external workflows (not local ./)
        if workflow_ref.startswith("./"):
            continue

        # Check if version is mutable
        is_mutable = version in MUTABLE_VERSIONS

        # Detect "secrets: inherit" pattern - most dangerous
        inherits_all_secrets = secrets_config == "inherit" if secrets_config else False

        # Count secrets passed to this job (explicit secret references)
        secret_rows = db.query(
            Q("github_step_references")
            .select("step_id")
            .where("reference_type = ?", "secrets")
            .where("step_id IS NOT NULL")
        )

        job_prefix = f"{job_id}::"
        secret_count = sum(1 for (step_id,) in secret_rows if step_id.startswith(job_prefix))

        # Flag if: mutable version, secrets passed, or inherits all secrets
        if is_mutable or secret_count > 0 or inherits_all_secrets:
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
                    inherits_all_secrets=inherits_all_secrets,
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
    inherits_all_secrets: bool = False,
) -> StandardFinding:
    """Build finding for reusable workflow risk."""

    # CRITICAL: secrets: inherit passes ALL secrets to external workflow
    # This is the most dangerous pattern - any upstream compromise gets everything
    if inherits_all_secrets and is_mutable:
        severity = Severity.CRITICAL
    # HIGH: mutable version + any secrets, or secrets: inherit without mutable
    elif (is_mutable and secret_count > 0) or inherits_all_secrets:
        severity = Severity.HIGH
    # MEDIUM: mutable version without secrets (still supply chain risk)
    elif is_mutable:
        severity = Severity.MEDIUM
    # LOW: pinned version but still external (minimal risk)
    else:
        severity = Severity.LOW

    risk_factors = []
    if inherits_all_secrets:
        risk_factors.append("secrets: inherit (ALL secrets exposed)")
    if is_mutable:
        risk_factors.append(f"mutable version ({version})")
    if secret_count > 0 and not inherits_all_secrets:
        risk_factors.append(f"{secret_count} secret(s) passed")

    risk_str = " + ".join(risk_factors) if risk_factors else "external workflow"

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' calls external reusable workflow "
        f"'{workflow_ref}' with {risk_str}. "
        f"External organization gains access to repository secrets."
    )

    secrets_line = "secrets: inherit  # VULN: ALL secrets exposed!" if inherits_all_secrets else "secrets: inherit  # or explicit secret passing"

    code_snippet = f"""
# Vulnerable Pattern:
name: {workflow_name}

jobs:
  {job_key}:
    uses: {reusable_path}  # VULN: External workflow{" with mutable version" if is_mutable else ""}
    {secrets_line}
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
        "inherits_all_secrets": inherits_all_secrets,
        "secret_count": secret_count,
        "mitigation": (
            f"1. Pin reusable workflow to immutable SHA: {workflow_ref}@<sha256>, and "
            "2. NEVER use 'secrets: inherit' - pass only required secrets explicitly, and "
            "3. Prefer internal reusable workflows (./.github/workflows/...) for sensitive operations"
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
