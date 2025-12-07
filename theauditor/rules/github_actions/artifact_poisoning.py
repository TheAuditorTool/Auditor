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


UNTRUSTED_ARTIFACT_TRIGGERS = frozenset(["pull_request_target", "workflow_run"])


def _find_artifact_poisoning(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for artifact poisoning."""
    findings: list[StandardFinding] = []

    workflow_rows = db.query(
        Q("github_workflows")
        .select("workflow_path", "workflow_name", "on_triggers")
        .where("on_triggers IS NOT NULL")
    )

    for workflow_path, workflow_name, on_triggers in workflow_rows:
        on_triggers = on_triggers or ""

        detected_triggers = [t for t in UNTRUSTED_ARTIFACT_TRIGGERS if t in on_triggers]
        if not detected_triggers:
            continue

        upload_jobs = _get_upload_jobs(db, workflow_path)
        if not upload_jobs:
            continue

        download_jobs = _get_download_jobs(db, workflow_path)

        for download_job_id, download_job_key, permissions_json in download_jobs:
            has_dependency = _check_job_dependency(
                db, download_job_id, [uj[0] for uj in upload_jobs]
            )

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
                        untrusted_triggers=detected_triggers,
                    )
                )

    return findings


def _get_upload_jobs(db: RuleDB, workflow_path: str) -> list[tuple[str, str]]:
    """Get jobs that upload artifacts in this workflow."""
    rows = db.query(
        Q("github_jobs")
        .select("github_jobs.job_id", "job_key")
        .join("github_steps", on=[("job_id", "job_id")])
        .where("github_jobs.workflow_path = ?", workflow_path)
        .where("github_steps.uses_action = ?", "actions/upload-artifact")
    )

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for row in rows:
        key = (row[0], row[1])
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _get_download_jobs(db: RuleDB, workflow_path: str) -> list[tuple[str, str, str]]:
    """Get jobs that download artifacts in this workflow."""
    rows = db.query(
        Q("github_jobs")
        .select("github_jobs.job_id", "job_key", "github_jobs.permissions")
        .join("github_steps", on=[("job_id", "job_id")])
        .where("github_jobs.workflow_path = ?", workflow_path)
        .where("github_steps.uses_action = ?", "actions/download-artifact")
    )

    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str]] = []
    for row in rows:
        key = (row[0], row[1], row[2] or "")
        if key not in seen:
            seen.add(key)
            result.append((row[0], row[1], row[2]))
    return result


def _check_job_dependency(db: RuleDB, download_job_id: str, upload_job_ids: list[str]) -> bool:
    """Check if download job depends on any upload job."""
    rows = db.query(
        Q("github_job_dependencies").select("needs_job_id").where("job_id = ?", download_job_id)
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
        "deploy": [
            "aws s3 sync",
            "aws s3 cp",
            "aws cloudformation deploy",
            "kubectl apply",
            "kubectl create",
            "kubectl replace",
            "helm install",
            "helm upgrade",
            "terraform apply",
            "terraform plan -out",
            "tofu apply",
            "gcloud app deploy",
            "gcloud run deploy",
            "gcloud functions deploy",
            "az deployment",
            "az webapp deploy",
            "az functionapp deploy",
            "vercel deploy",
            "vercel --prod",
            "netlify deploy",
            "firebase deploy",
            "fly deploy",
            "heroku container:push",
            "heroku deploy",
            "railway up",
            "rsync",
            "scp ",
        ],
        "sign": [
            "cosign sign",
            "cosign attest",
            "gpg --sign",
            "gpg --detach-sign",
            "gpg -s",
            "signtool sign",
            "codesign -s",
            "jarsigner",
            "apksigner sign",
        ],
        "publish": [
            "npm publish",
            "yarn publish",
            "pnpm publish",
            "twine upload",
            "pip upload",
            "flit publish",
            "poetry publish",
            "docker push",
            "docker buildx build --push",
            "podman push",
            "gh release create",
            "gh release upload",
            "cargo publish",
            "gem push",
            "nuget push",
            "dotnet nuget push",
            "mvn deploy",
            "gradle publish",
            "./gradlew publish",
            "go-release",
        ],
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
    untrusted_triggers: list[str],
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

    trigger_str = ", ".join(untrusted_triggers)

    message = (
        f"Workflow '{workflow_name}' job '{download_job_key}' downloads artifacts from "
        f"untrusted build job(s) [{upload_str}] and performs dangerous operations: {ops_str}. "
        f"Attacker can poison artifacts via {trigger_str} trigger."
    )

    primary_trigger = untrusted_triggers[0] if untrusted_triggers else "pull_request_target"

    code_snippet = f"""
# Vulnerable Pattern:
on:
  {primary_trigger}:  # VULN: Untrusted context

jobs:
  {upload_jobs[0] if upload_jobs else "build"}:
    # Builds with attacker-controlled code
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: npm run build  # Attacker controls this
      - uses: actions/upload-artifact@v4  # Uploads poisoned artifact

  {download_job_key}:
    needs: [{upload_str}]
    steps:
      - uses: actions/download-artifact@v4  # Downloads poisoned artifact
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
        "untrusted_triggers": untrusted_triggers,
        "mitigation": (
            "1. Validate artifact integrity before deployment (checksums, signatures), or "
            "2. Build artifacts in trusted context (push trigger, not pull_request_target/workflow_run), or "
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
