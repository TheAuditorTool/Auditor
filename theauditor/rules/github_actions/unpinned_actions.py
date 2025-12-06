"""GitHub Actions Unpinned Actions with Secrets Detection.

Detects third-party actions pinned to mutable versions with secret access.

Tables Used:
- github_steps: Step action usage
- github_jobs: Job metadata
- github_step_references: Secret references in steps

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
    name="github_actions_unpinned_actions",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_steps",
)


MUTABLE_VERSIONS: set[str] = {
    "main",
    "master",
    "develop",
    "dev",
    "trunk",
    "v1",
    "v2",
    "v3",
    "v4",
    "v5",
}


GITHUB_FIRST_PARTY: frozenset[str] = frozenset(
    {
        "actions/checkout",
        "actions/cache",
        "actions/upload-artifact",
        "actions/download-artifact",
        "actions/github-script",
        "actions/labeler",
        "actions/stale",
        "actions/first-interaction",
        "actions/create-release",
        "actions/setup-node",
        "actions/setup-python",
        "actions/setup-java",
        "actions/setup-go",
        "actions/setup-dotnet",
        "actions/setup-ruby",
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
        "actions/configure-pages",
        "actions/dependency-review-action",
        "actions/attest-build-provenance",
        "actions/attest",
        "github/codeql-action",
        "github/super-linter",
        "actions/add-to-project",
        "actions/delete-package-versions",
    }
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect unpinned third-party actions with secret access.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_unpinned_actions(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_unpinned_action_with_secrets(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


def _is_valid_sha(version: str) -> bool:
    """Check if version is a valid Git SHA (immutable reference).

    Args:
        version: The version string to check

    Returns:
        True if version is a valid SHA-1 (40 hex) or SHA-256 (64 hex)
    """

    if len(version) not in (40, 64):
        return False

    return all(c in "0123456789abcdefABCDEF" for c in version)


def _find_unpinned_actions(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for unpinned actions."""
    findings: list[StandardFinding] = []

    step_rows = db.query(
        Q("github_steps")
        .alias("s")
        .select(
            "s.step_id",
            "s.step_name",
            "s.uses_action",
            "s.uses_version",
            "s.env",
            "s.with_args",
            "github_jobs.workflow_path",
            "github_jobs.job_key",
        )
        .join("github_jobs", on=[("job_id", "job_id")])
        .where("s.uses_action IS NOT NULL")
        .where("s.uses_version IS NOT NULL")
    )

    for (
        step_id,
        step_name,
        uses_action,
        uses_version,
        step_env,
        step_with,
        workflow_path,
        job_key,
    ) in step_rows:
        if uses_action in GITHUB_FIRST_PARTY:
            continue
        if uses_action.startswith("actions/") or uses_action.startswith("github/"):
            continue

        if uses_version not in MUTABLE_VERSIONS:
            if _is_valid_sha(uses_version):
                continue

        secret_refs = _check_secret_access(db, step_id, step_env, step_with)

        if secret_refs:
            findings.append(
                _build_unpinned_action_finding(
                    workflow_path=workflow_path,
                    job_key=job_key,
                    step_name=step_name or "Unnamed step",
                    uses_action=uses_action,
                    uses_version=uses_version,
                    secret_refs=secret_refs,
                )
            )

    return findings


def _check_secret_access(db: RuleDB, step_id: str, step_env: str, step_with: str) -> list[str]:
    """Check if step has access to secrets."""
    secret_refs: list[str] = []

    if step_env:
        try:
            env_vars = json.loads(step_env)
            for key, value in env_vars.items():
                if "secrets." in str(value):
                    secret_refs.append(f"env.{key}")
        except json.JSONDecodeError:
            pass

    if step_with:
        try:
            with_args = json.loads(step_with)
            for key, value in with_args.items():
                if "secrets." in str(value):
                    secret_refs.append(f"with.{key}")
        except json.JSONDecodeError:
            pass

    ref_rows = db.query(
        Q("github_step_references")
        .select("reference_path", "reference_location")
        .where("step_id = ?", step_id)
        .where("reference_type = ?", "secrets")
    )

    for ref_path, ref_location in ref_rows:
        secret_refs.append(f"{ref_location}.{ref_path}")

    return secret_refs


def _build_unpinned_action_finding(
    workflow_path: str,
    job_key: str,
    step_name: str,
    uses_action: str,
    uses_version: str,
    secret_refs: list[str],
) -> StandardFinding:
    """Build finding for unpinned action vulnerability."""

    is_external_org = "/" in uses_action and not uses_action.startswith("actions/")
    secret_count = len(secret_refs)

    is_branch_ref = uses_version in MUTABLE_VERSIONS

    if is_external_org and is_branch_ref and secret_count > 0:
        severity = Severity.CRITICAL

    elif (is_external_org and secret_count > 0) or (is_branch_ref and secret_count > 0):
        severity = Severity.HIGH

    elif secret_count > 0:
        severity = Severity.MEDIUM

    else:
        severity = Severity.LOW

    message = (
        f"Step '{step_name}' in job '{job_key}' uses third-party action "
        f"'{uses_action}@{uses_version}' pinned to mutable ref with {secret_count} secret(s) exposed. "
        f"Upstream compromise could steal: {', '.join(secret_refs[:3])}"
    )

    code_snippet = f"""
# Vulnerable Pattern:
jobs:
  {job_key}:
    steps:
      - name: {step_name}
        uses: {uses_action}@{uses_version}  # VULN: Mutable version
        with:
          # Secrets exposed: {", ".join(secret_refs)}
    """

    details = {
        "workflow": workflow_path,
        "job_key": job_key,
        "step_name": step_name,
        "action": uses_action,
        "mutable_version": uses_version,
        "secret_references": secret_refs,
        "is_external": is_external_org,
        "mitigation": (
            f"Pin action to immutable SHA: uses: {uses_action}@<full-sha256> "
            f"instead of @{uses_version}"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="unpinned_action_with_secrets",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-829",
        additional_info=details,
    )
