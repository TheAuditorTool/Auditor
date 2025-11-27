"""GitHub Actions Unpinned Actions with Secrets Detection.

Detects supply chain risk where third-party actions are pinned to mutable
references (main, v1, develop) while having access to repository secrets.

Attack Pattern:
1. Action pinned to mutable ref like @main or @v1
2. Step has access to secrets (via env, with, or secrets: inherit)
3. Upstream maintainer compromise = instant secret theft

CWE-829: Inclusion of Functionality from Untrusted Control Sphere
"""

import json
import logging
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="github_actions_unpinned_actions",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    requires_jsx_pass=False,
    execution_scope="database",
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


GITHUB_FIRST_PARTY: set[str] = {
    "actions/checkout",
    "actions/setup-node",
    "actions/setup-python",
    "actions/setup-java",
    "actions/setup-go",
    "actions/cache",
    "actions/upload-artifact",
    "actions/download-artifact",
    "actions/github-script",
}


def find_unpinned_action_with_secrets(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect unpinned third-party actions with secret access.

    Detection Logic:
    1. Find steps using third-party actions (not github first-party)
    2. Check if action version is mutable (main, v1, etc.)
    3. Check if step has access to secrets (env, with, job secrets)
    4. Report high-severity finding for supply chain risk

    Args:
        context: Rule execution context with database path

    Returns:
        List of security findings
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.step_id, s.job_id, s.step_name, s.uses_action, s.uses_version,
                   s.env, s.with_args, j.workflow_path, j.job_key
            FROM github_steps s
            JOIN github_jobs j ON s.job_id = j.job_id
            WHERE s.uses_action IS NOT NULL
            AND s.uses_version IS NOT NULL
        """)

        for row in cursor.fetchall():
            uses_action = row["uses_action"]
            uses_version = row["uses_version"]

            if uses_action in GITHUB_FIRST_PARTY:
                continue

            if uses_version not in MUTABLE_VERSIONS:
                continue

            has_secrets = _check_secret_access(
                step_id=row["step_id"],
                step_env=row["env"],
                step_with=row["with_args"],
                job_id=row["job_id"],
                cursor=cursor,
            )

            if has_secrets:
                findings.append(
                    _build_unpinned_action_finding(
                        workflow_path=row["workflow_path"],
                        job_key=row["job_key"],
                        step_name=row["step_name"] or "Unnamed step",
                        uses_action=uses_action,
                        uses_version=uses_version,
                        secret_refs=has_secrets,
                    )
                )

    finally:
        conn.close()

    return findings


def _check_secret_access(
    step_id: str, step_env: str, step_with: str, job_id: str, cursor
) -> list[str]:
    """Check if step has access to secrets.

    Args:
        step_id: Step identifier
        step_env: JSON string of step env vars
        step_with: JSON string of step with args
        job_id: Parent job identifier
        cursor: Database cursor

    Returns:
        List of secret reference paths found (empty if no secrets)
    """
    secret_refs = []

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

    cursor.execute(
        """
        SELECT reference_path, reference_location
        FROM github_step_references
        WHERE step_id = ?
        AND reference_type = 'secrets'
    """,
        (step_id,),
    )

    for ref_row in cursor.fetchall():
        secret_refs.append(f"{ref_row['reference_location']}.{ref_row['reference_path']}")

    return secret_refs


def _build_unpinned_action_finding(
    workflow_path: str,
    job_key: str,
    step_name: str,
    uses_action: str,
    uses_version: str,
    secret_refs: list[str],
) -> StandardFinding:
    """Build finding for unpinned action vulnerability.

    Args:
        workflow_path: Path to workflow file
        job_key: Job key
        step_name: Step display name
        uses_action: Action reference (org/repo)
        uses_version: Mutable version tag
        secret_refs: List of secret reference paths

    Returns:
        StandardFinding object
    """

    is_external_org = "/" in uses_action and not uses_action.startswith("actions/")
    secret_count = len(secret_refs)

    if is_external_org and secret_count > 0:
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
