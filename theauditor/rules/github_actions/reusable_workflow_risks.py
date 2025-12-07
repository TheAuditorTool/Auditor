"""GitHub Actions Reusable Workflow Security Risks Detection.

Detects external reusable workflows with mutable versions or secret access.

Tables Used:
- github_jobs: Job definitions with reusable workflow references
- github_workflows: Workflow metadata
- github_step_references: Secret references in steps

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
"""

import re

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


SHA_COMMIT_PATTERN = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)


MAJOR_ONLY_VERSION_PATTERN = re.compile(r"^v\d+$", re.IGNORECASE)


MUTABLE_BRANCH_NAMES = frozenset(
    {
        "main",
        "master",
        "develop",
        "dev",
        "trunk",
        "release",
        "stable",
        "edge",
        "nightly",
        "next",
        "lts",
        "latest",
        "canary",
        "head",
    }
)


def _is_mutable_version(version: str) -> bool:
    """Determine if a version reference is mutable (can change without notice).

    Immutable: 40-char SHA commit hash, exact semver tags (v1.2.3)
    Mutable: Branch names, major-only tags (v1, v2), edge/nightly channels

    Args:
        version: Version string from workflow reference (e.g., "v4", "main", "abc123...")

    Returns:
        True if version can be changed by upstream maintainer
    """
    version_lower = version.lower()

    if SHA_COMMIT_PATTERN.match(version):
        return False

    if version_lower in MUTABLE_BRANCH_NAMES:
        return True

    return bool(MAJOR_ONLY_VERSION_PATTERN.match(version))


def _find_reusable_workflow_risks(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for reusable workflow risks."""
    findings: list[StandardFinding] = []

    job_rows = db.query(
        Q("github_jobs")
        .select(
            "job_id",
            "github_jobs.workflow_path",
            "job_key",
            "job_name",
            "reusable_workflow_path",
            "github_workflows.workflow_name",
        )
        .join("github_workflows", on=[("workflow_path", "workflow_path")])
        .where("uses_reusable_workflow = ?", 1)
        .where("reusable_workflow_path IS NOT NULL")
    )

    for row in job_rows:
        job_id, workflow_path, job_key, job_name, reusable_path, workflow_name = row

        if "@" not in reusable_path:
            continue

        workflow_ref, version = reusable_path.rsplit("@", 1)

        if workflow_ref.startswith("./"):
            continue

        is_mutable = _is_mutable_version(version)

        inherits_all_secrets = False

        secret_rows = db.query(
            Q("github_step_references")
            .select("step_id")
            .where("reference_type = ?", "secrets")
            .where("step_id IS NOT NULL")
        )

        job_prefix = f"{job_id}::"
        secret_count = sum(1 for (step_id,) in secret_rows if step_id.startswith(job_prefix))

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

    if inherits_all_secrets and is_mutable:
        severity = Severity.CRITICAL

    elif (is_mutable and secret_count > 0) or inherits_all_secrets:
        severity = Severity.HIGH

    elif is_mutable:
        severity = Severity.MEDIUM

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

    secrets_line = (
        "secrets: inherit  # VULN: ALL secrets exposed!"
        if inherits_all_secrets
        else "secrets: inherit  # or explicit secret passing"
    )

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
