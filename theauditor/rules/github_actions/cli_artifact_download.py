"""GitHub Actions CLI Artifact Download Detection.

Detects artifact downloads via CLI tools that bypass the official GitHub Action.
These downloads are not tracked by artifact_poisoning.py which only checks for
actions/download-artifact usage.

Attack chain:
1. Attacker submits PR with malicious build artifacts
2. CI builds and uploads to S3/GCS/Azure Storage (or GitHub via gh CLI)
3. Trusted job downloads artifact using CLI tools (not official action)
4. Existing artifact_poisoning rule misses this because it only checks uses_action

CLI tools detected:
- gh run download (GitHub CLI)
- aws s3 cp/sync (AWS S3)
- gsutil cp (Google Cloud Storage)
- az storage blob download (Azure Blob Storage)
- curl/wget to artifact URLs

Tables Used:
- github_workflows: Workflow metadata and triggers
- github_jobs: Job definitions
- github_steps: Step run scripts

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
    name="github_actions_cli_artifact_download",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_workflows",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect CLI-based artifact downloads in untrusted contexts.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_cli_artifact_downloads(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_cli_artifact_download(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


UNTRUSTED_TRIGGERS = frozenset(["pull_request_target", "workflow_run"])


CLI_DOWNLOAD_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r"gh\s+run\s+download", re.IGNORECASE), "gh run download", 2),
    (re.compile(r"gh\s+api\s+.*artifacts", re.IGNORECASE), "gh api artifacts", 1),
    (re.compile(r"aws\s+s3\s+cp\b", re.IGNORECASE), "aws s3 cp", 1),
    (re.compile(r"aws\s+s3\s+sync\b", re.IGNORECASE), "aws s3 sync", 1),
    (re.compile(r"aws\s+s3api\s+get-object", re.IGNORECASE), "aws s3api get-object", 1),
    (re.compile(r"gsutil\s+cp\b", re.IGNORECASE), "gsutil cp", 1),
    (re.compile(r"gcloud\s+storage\s+cp\b", re.IGNORECASE), "gcloud storage cp", 1),
    (re.compile(r"az\s+storage\s+blob\s+download", re.IGNORECASE), "az storage blob download", 1),
    (re.compile(r"azcopy\s+copy\b", re.IGNORECASE), "azcopy copy", 1),
    (re.compile(r"curl\s+.*-[oO]\s", re.IGNORECASE), "curl download", 0),
    (re.compile(r"wget\s+", re.IGNORECASE), "wget", 0),
    (re.compile(r"artifactory\s+dl\b", re.IGNORECASE), "artifactory download", 1),
    (re.compile(r"jfrog\s+rt\s+dl\b", re.IGNORECASE), "jfrog rt download", 1),
]


def _find_cli_artifact_downloads(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for CLI artifact downloads."""
    findings: list[StandardFinding] = []

    workflow_rows = db.query(
        Q("github_workflows")
        .select("workflow_path", "workflow_name", "on_triggers")
        .where("on_triggers IS NOT NULL")
    )

    for workflow_path, workflow_name, on_triggers in workflow_rows:
        on_triggers = on_triggers or ""

        detected_triggers = [t for t in UNTRUSTED_TRIGGERS if t in on_triggers]
        if not detected_triggers:
            continue

        job_rows = db.query(
            Q("github_jobs").select("job_id", "job_key").where("github_jobs.workflow_path = ?", workflow_path)
        )

        for job_id, job_key in job_rows:
            cli_downloads = _check_cli_download_patterns(db, job_id)

            if cli_downloads:
                findings.append(
                    _build_cli_download_finding(
                        workflow_path=workflow_path,
                        workflow_name=workflow_name,
                        job_key=job_key,
                        cli_downloads=cli_downloads,
                        untrusted_triggers=detected_triggers,
                    )
                )

    return findings


def _check_cli_download_patterns(db: RuleDB, job_id: str) -> list[tuple[str, int]]:
    """Check if job contains CLI artifact download commands.

    Returns:
        List of (tool_name, severity_boost) tuples
    """
    rows = db.query(
        Q("github_steps")
        .select("run_script")
        .where("job_id = ?", job_id)
        .where("run_script IS NOT NULL")
    )

    matches: list[tuple[str, int]] = []
    seen_tools: set[str] = set()

    for (run_script,) in rows:
        for pattern, tool_name, severity_boost in CLI_DOWNLOAD_PATTERNS:
            if tool_name in seen_tools:
                continue

            if pattern.search(run_script):
                matches.append((tool_name, severity_boost))
                seen_tools.add(tool_name)

    return matches


def _build_cli_download_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    cli_downloads: list[tuple[str, int]],
    untrusted_triggers: list[str],
) -> StandardFinding:
    """Build finding for CLI artifact download vulnerability."""

    total_boost = sum(boost for _, boost in cli_downloads)
    if total_boost >= 3 or len(cli_downloads) >= 2:
        severity = Severity.HIGH
    elif total_boost >= 1:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW

    tools_str = ", ".join(tool for tool, _ in cli_downloads)
    trigger_str = ", ".join(untrusted_triggers)

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' downloads artifacts via CLI "
        f"({tools_str}) in {trigger_str} context. "
        f"This bypasses actions/download-artifact detection and may enable artifact poisoning."
    )

    primary_tool = cli_downloads[0][0] if cli_downloads else "cli tool"

    code_snippet = f"""
# Vulnerable Pattern - CLI artifact download bypasses standard detection:
on:
  {untrusted_triggers[0]}:  # VULN: Untrusted context

jobs:
  build:
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: npm run build
      # Uploads to external storage instead of GitHub Artifacts
      - run: aws s3 cp dist/ s3://bucket/artifacts/

  {job_key}:
    steps:
      # VULN: Downloads from external source - not detected by artifact_poisoning rule
      - run: {primary_tool} ...
      - run: npm install  # Executes poisoned artifact
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "job_key": job_key,
        "cli_tools_detected": [tool for tool, _ in cli_downloads],
        "untrusted_triggers": untrusted_triggers,
        "mitigation": (
            "1. Use actions/download-artifact instead of CLI tools for traceability, or "
            "2. Validate artifact integrity (checksums, signatures) before use, or "
            "3. Restrict external storage access in untrusted workflow contexts, or "
            "4. Use read-only credentials for artifact storage in PR workflows"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="cli_artifact_download",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="medium",
        snippet=code_snippet.strip(),
        cwe_id="CWE-494",
        additional_info=details,
    )
