"""GitHub Actions Artifact Code Execution Detection.

Detects code execution via build tools on downloaded artifacts in untrusted contexts.
This is a variant of artifact poisoning where the attacker doesn't need deployment
permissions - just the ability to inject malicious code into build artifacts.

Attack chain:
1. Attacker submits PR with malicious package.json/Makefile/setup.py
2. CI builds in pull_request_target context, uploads poisoned artifact
3. Trusted job downloads artifact and runs `npm install`/`make`/`pip install`
4. Malicious postinstall/Makefile/setup.py executes with elevated permissions

Tables Used:
- github_workflows: Workflow metadata and triggers
- github_jobs: Job definitions
- github_steps: Step actions and run scripts
- github_job_dependencies: Job dependency graph

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
    name="github_actions_artifact_code_execution",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_workflows",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect code execution via build tools on downloaded artifacts.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_artifact_code_execution(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_artifact_code_execution(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


UNTRUSTED_ARTIFACT_TRIGGERS = frozenset(["pull_request_target", "workflow_run"])


CODE_EXECUTION_PATTERNS: dict[str, list[str]] = {
    "javascript": [
        "npm install",
        "npm ci",
        "npm run",
        "npm test",
        "npm start",
        "yarn install",
        "yarn",
        "yarn run",
        "yarn test",
        "yarn start",
        "pnpm install",
        "pnpm run",
        "pnpm test",
        "npx ",
        "bunx ",
    ],
    "python": [
        "pip install",
        "pip install -e",
        "pip install .",
        "python setup.py",
        "python -m pip install",
        "poetry install",
        "pdm install",
        "uv pip install",
        "pytest",
        "python -m pytest",
    ],
    "make": [
        "make",
        "make install",
        "make build",
        "make test",
        "cmake --build",
        "ninja",
    ],
    "ruby": [
        "bundle install",
        "bundle exec",
        "gem install",
        "rake",
    ],
    "rust": [
        "cargo build",
        "cargo run",
        "cargo test",
        "cargo install",
    ],
    "go": [
        "go build",
        "go run",
        "go test",
        "go install",
        "go generate",
    ],
    "dotnet": [
        "dotnet build",
        "dotnet run",
        "dotnet test",
        "dotnet restore",
        "nuget restore",
        "msbuild",
    ],
    "java": [
        "mvn ",
        "mvn install",
        "mvn package",
        "mvn test",
        "gradle ",
        "./gradlew",
        "ant ",
    ],
    "shell": [
        "bash ",
        "sh ",
        "chmod +x",
        "./",
        "source ",
        ". ./",
    ],
}


def _find_artifact_code_execution(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for artifact code execution."""
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

        download_jobs = _get_artifact_download_jobs(db, workflow_path)
        if not download_jobs:
            continue

        for job_id, job_key in download_jobs:
            execution_patterns = _check_code_execution_patterns(db, job_id)

            if execution_patterns:
                findings.append(
                    _build_code_execution_finding(
                        workflow_path=workflow_path,
                        workflow_name=workflow_name,
                        job_key=job_key,
                        execution_patterns=execution_patterns,
                        untrusted_triggers=detected_triggers,
                    )
                )

    return findings


def _get_artifact_download_jobs(db: RuleDB, workflow_path: str) -> list[tuple[str, str]]:
    """Get jobs that download artifacts in this workflow."""
    rows = db.query(
        Q("github_jobs")
        .select("github_jobs.job_id", "job_key")
        .join("github_steps", on=[("job_id", "job_id")])
        .where("github_jobs.workflow_path = ?", workflow_path)
        .where("github_steps.uses_action = ?", "actions/download-artifact")
    )

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for row in rows:
        key = (row[0], row[1])
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _check_code_execution_patterns(db: RuleDB, job_id: str) -> list[tuple[str, str]]:
    """Check if job performs code execution operations.

    Returns:
        List of (category, matched_pattern) tuples
    """
    rows = db.query(
        Q("github_steps")
        .select("run_script")
        .where("job_id = ?", job_id)
        .where("run_script IS NOT NULL")
    )

    matches: list[tuple[str, str]] = []
    seen_categories: set[str] = set()

    for (run_script,) in rows:
        script_lower = run_script.lower()

        for category, patterns in CODE_EXECUTION_PATTERNS.items():
            if category in seen_categories:
                continue

            for pattern in patterns:
                if pattern in script_lower:
                    matches.append((category, pattern.strip()))
                    seen_categories.add(category)
                    break

    return matches


def _build_code_execution_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    execution_patterns: list[tuple[str, str]],
    untrusted_triggers: list[str],
) -> StandardFinding:
    """Build finding for artifact code execution vulnerability."""

    num_ecosystems = len(execution_patterns)
    if num_ecosystems >= 3:
        severity = Severity.CRITICAL
    elif num_ecosystems >= 2:
        severity = Severity.HIGH
    else:
        severity = Severity.HIGH

    patterns_str = ", ".join(f"{cat}:{pat}" for cat, pat in execution_patterns)
    trigger_str = ", ".join(untrusted_triggers)

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' downloads artifacts and executes "
        f"build tools ({patterns_str}) in {trigger_str} context. "
        f"Attacker can inject malicious postinstall/Makefile/setup.py code."
    )

    code_snippet = f"""
# Vulnerable Pattern:
on:
  {untrusted_triggers[0]}:  # VULN: Untrusted context

jobs:
  build:
    # Builds with attacker-controlled code
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.event.pull_request.head.sha }}}}
      - run: npm run build  # Attacker controls package.json
      - uses: actions/upload-artifact@v4

  {job_key}:
    steps:
      - uses: actions/download-artifact@v4
      - run: |
          {execution_patterns[0][1]}  # VULN: Executes poisoned code
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "job_key": job_key,
        "execution_patterns": execution_patterns,
        "untrusted_triggers": untrusted_triggers,
        "ecosystems_affected": [cat for cat, _ in execution_patterns],
        "mitigation": (
            "1. Never run build tools on untrusted artifacts, or "
            "2. Build in isolated environment (container, sandbox), or "
            "3. Use --ignore-scripts for npm/yarn, --no-deps for pip, or "
            "4. Separate untrusted builds from trusted execution"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="artifact_code_execution",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-94",
        additional_info=details,
    )
