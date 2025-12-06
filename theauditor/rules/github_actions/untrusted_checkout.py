"""GitHub Actions Untrusted Checkout Sequence Detection.

Detects untrusted code checkout in pull_request_target workflows where
attacker-controlled code can execute with elevated permissions.

Tables Used:
- github_workflows: Workflow triggers
- github_jobs: Job permissions
- github_steps: Checkout step details
- github_step_references: Expression references in checkout

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
    name="github_actions_untrusted_checkout",
    category="supply-chain",
    target_extensions=[".yml", ".yaml"],
    exclude_patterns=[".pf/", "test/", "__tests__/", "node_modules/"],
    execution_scope="database",
    primary_table="github_workflows",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect untrusted code checkout in pull_request_target workflows.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = _find_untrusted_checkouts(db)
        return RuleResult(findings=findings, manifest=db.get_manifest())


def find_untrusted_checkout_sequence(context: StandardRuleContext) -> list[StandardFinding]:
    """Legacy entry point - delegates to analyze()."""
    result = analyze(context)
    return result.findings


UNTRUSTED_CHECKOUT_TRIGGERS = frozenset(["pull_request_target", "workflow_run"])


def _find_untrusted_checkouts(db: RuleDB) -> list[StandardFinding]:
    """Core detection logic for untrusted checkout sequences."""
    findings: list[StandardFinding] = []

    workflow_rows = db.query(
        Q("github_workflows")
        .select("workflow_path", "workflow_name", "on_triggers")
        .where("on_triggers IS NOT NULL")
    )

    for workflow_path, workflow_name, on_triggers in workflow_rows:
        on_triggers = on_triggers or ""

        detected_triggers = [t for t in UNTRUSTED_CHECKOUT_TRIGGERS if t in on_triggers]
        if not detected_triggers:
            continue

        job_rows = db.query(
            Q("github_jobs")
            .select("job_id", "job_key", "permissions")
            .where("workflow_path = ?", workflow_path)
            .order_by("job_key")
        )

        for job_id, job_key, permissions_json in job_rows:
            step_rows = db.query(
                Q("github_steps")
                .select("step_id", "step_name", "sequence_order", "with_args")
                .where("job_id = ?", job_id)
                .where("uses_action = ?", "actions/checkout")
                .order_by("sequence_order")
            )

            for step_id, step_name, sequence_order, with_args in step_rows:
                is_untrusted, detected_pattern = _check_untrusted_ref(db, step_id, with_args)

                if is_untrusted:
                    permissions = {}
                    if permissions_json:
                        try:
                            permissions = json.loads(permissions_json)
                        except json.JSONDecodeError:
                            pass

                    findings.append(
                        _build_untrusted_checkout_finding(
                            workflow_path=workflow_path,
                            workflow_name=workflow_name,
                            job_key=job_key,
                            step_name=step_name or "Unnamed checkout",
                            sequence_order=sequence_order,
                            permissions=permissions,
                            with_args=with_args,
                            detected_triggers=detected_triggers,
                            detected_pattern=detected_pattern,
                        )
                    )

    return findings


UNTRUSTED_REF_PATTERNS = frozenset(
    [
        "github.event.pull_request.head.sha",
        "github.event.pull_request.head.ref",
        "github.head_ref",
        "github.event.workflow_run.head_sha",
        "github.event.workflow_run.head_branch",
        "github.event.workflow_run.head_commit.id",
    ]
)


def _check_untrusted_ref(db: RuleDB, step_id: str, with_args: str) -> tuple[bool, str]:
    """Check if checkout step uses untrusted ref.

    Returns:
        Tuple of (is_untrusted, detected_ref_pattern)
    """

    if with_args:
        try:
            args = json.loads(with_args)
            ref = args.get("ref", "")
            for pattern in UNTRUSTED_REF_PATTERNS:
                if pattern in ref:
                    return True, pattern

            if "github.event.pull_request.head" in ref:
                return True, "github.event.pull_request.head"
            if "github.event.workflow_run.head" in ref:
                return True, "github.event.workflow_run.head"
        except json.JSONDecodeError:
            pass

    ref_rows = db.query(
        Q("github_step_references")
        .select("reference_path")
        .where("step_id = ?", step_id)
        .where("reference_location = ?", "with")
        .where("reference_path IS NOT NULL")
    )

    for (reference_path,) in ref_rows:
        for pattern in UNTRUSTED_REF_PATTERNS:
            if reference_path.startswith(pattern.split(".")[0]) and pattern in reference_path:
                return True, reference_path

        if reference_path.startswith("github.event.pull_request.head"):
            return True, reference_path
        if reference_path.startswith("github.event.workflow_run.head"):
            return True, reference_path

    return False, ""


def _build_untrusted_checkout_finding(
    workflow_path: str,
    workflow_name: str,
    job_key: str,
    step_name: str,
    sequence_order: int,
    permissions: dict,
    with_args: str,
    detected_triggers: list[str],
    detected_pattern: str,
) -> StandardFinding:
    """Build finding for untrusted checkout vulnerability."""

    has_write_perms = any(
        perm in permissions and permissions[perm] in ("write", "write-all")
        for perm in ["contents", "packages", "pull-requests", "id-token", "actions"]
    )

    severity = Severity.CRITICAL if has_write_perms else Severity.HIGH

    try:
        args = json.loads(with_args) if with_args else {}
        ref_value = args.get("ref", detected_pattern or "github.event.pull_request.head.sha")
    except json.JSONDecodeError:
        ref_value = detected_pattern or "unknown"

    ", ".join(detected_triggers)
    is_workflow_run = "workflow_run" in detected_triggers

    if is_workflow_run:
        context_desc = "workflow_run trigger (can be triggered by untrusted PR workflows)"
    else:
        context_desc = "pull_request_target trigger (runs in target context with secrets)"

    message = (
        f"Workflow '{workflow_name}' checks out untrusted code at step #{sequence_order + 1} "
        f"in job '{job_key}' with {context_desc}. "
        f"Attacker-controlled code can execute with {'write permissions' if has_write_perms else 'read permissions'}."
    )

    primary_trigger = detected_triggers[0] if detected_triggers else "pull_request_target"

    code_snippet = f"""
# Vulnerable Pattern:
on:
  {primary_trigger}:  # {context_desc}

jobs:
  {job_key}:
    steps:
      - name: {step_name}
        uses: actions/checkout@v4
        with:
          ref: ${{{{{ref_value}}}}}  # VULN: Untrusted attacker code
    """

    details = {
        "workflow": workflow_path,
        "job_key": job_key,
        "step_name": step_name,
        "step_order": sequence_order,
        "permissions": permissions,
        "has_write_permissions": has_write_perms,
        "checkout_ref": ref_value,
        "detected_triggers": detected_triggers,
        "detected_pattern": detected_pattern,
        "mitigation": (
            "1. Use pull_request trigger instead of pull_request_target/workflow_run, or "
            "2. Add validation job that runs first with 'needs:' dependency, or "
            "3. Only checkout base branch code in early steps, or "
            "4. For workflow_run: validate artifact integrity before execution"
        ),
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,
        rule_name="untrusted_checkout_sequence",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-284",
        additional_info=details,
    )
