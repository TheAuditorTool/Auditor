"""GitHub Actions Untrusted Checkout Sequence Detection.

Detects the critical vulnerability where pull_request_target workflows check out
untrusted PR code before any validation, allowing attacker code execution with
write permissions and access to repository secrets.

Attack Pattern:
1. Workflow triggers on pull_request_target (runs in target repo context)
2. Early checkout step uses github.event.pull_request.head.sha (attacker code)
3. Attacker code executes with GITHUB_TOKEN write permissions

CWE-284: Improper Access Control
"""


import json
import logging
import sqlite3

from theauditor.rules.base import (
    RuleMetadata,
    StandardFinding,
    StandardRuleContext,
    Severity,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="github_actions_untrusted_checkout",
    category="supply-chain",
    target_extensions=['.yml', '.yaml'],
    exclude_patterns=['.pf/', 'test/', '__tests__/', 'node_modules/'],
    requires_jsx_pass=False,
    execution_scope='database',
)


def find_untrusted_checkout_sequence(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect untrusted code checkout in pull_request_target workflows.

    Detection Logic:
    1. Identify workflows triggered by pull_request_target
    2. Find jobs with early actions/checkout steps
    3. Check if checkout uses untrusted ref (github.event.pull_request.head.*)
    4. Report if checkout occurs before validation job

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
        # Step 1: Find all workflows triggered by pull_request_target
        cursor.execute("""
            SELECT workflow_path, workflow_name, on_triggers
            FROM github_workflows
            WHERE on_triggers IS NOT NULL
        """)

        for workflow_row in cursor.fetchall():
            workflow_path = workflow_row['workflow_path']
            workflow_name = workflow_row['workflow_name']
            on_triggers = workflow_row['on_triggers'] or ''

            # Filter in Python: Check for pull_request_target trigger
            if 'pull_request_target' not in on_triggers:
                continue

            # Step 2: Check all jobs in this workflow for early checkout
            cursor.execute("""
                SELECT j.job_id, j.job_key, j.job_name, j.permissions
                FROM github_jobs j
                WHERE j.workflow_path = ?
                ORDER BY j.job_key
            """, (workflow_path,))

            for job_row in cursor.fetchall():
                job_id = job_row['job_id']
                job_key = job_row['job_key']

                # Step 3: Find actions/checkout steps in this job
                cursor.execute("""
                    SELECT s.step_id, s.step_name, s.sequence_order, s.with_args
                    FROM github_steps s
                    WHERE s.job_id = ?
                    AND s.uses_action = 'actions/checkout'
                    ORDER BY s.sequence_order
                """, (job_id,))

                for step_row in cursor.fetchall():
                    step_id = step_row['step_id']
                    step_name = step_row['step_name'] or 'Unnamed checkout'
                    sequence_order = step_row['sequence_order']
                    with_args = step_row['with_args']

                    # Step 4: Check if checkout uses untrusted ref
                    is_untrusted = _check_untrusted_ref(step_id, with_args, cursor)

                    if is_untrusted:
                        # Check if this is an early checkout (sequence < 3 means no validation)
                        if sequence_order < 3:
                            permissions_json = job_row['permissions']
                            permissions = json.loads(permissions_json) if permissions_json else {}

                            # Build detailed finding
                            findings.append(_build_untrusted_checkout_finding(
                                workflow_path=workflow_path,
                                workflow_name=workflow_name,
                                job_key=job_key,
                                step_name=step_name,
                                sequence_order=sequence_order,
                                permissions=permissions,
                                with_args=with_args
                            ))

    finally:
        conn.close()

    return findings


def _check_untrusted_ref(step_id: str, with_args: str, cursor) -> bool:
    """Check if checkout step uses untrusted PR ref.

    Args:
        step_id: Step identifier
        with_args: JSON string of with: arguments
        cursor: Database cursor

    Returns:
        True if checkout uses untrusted ref
    """
    # Check with_args for 'ref' parameter
    if with_args:
        try:
            args = json.loads(with_args)
            ref = args.get('ref', '')

            # Check for direct untrusted refs
            if 'github.event.pull_request.head' in ref:
                return True

        except json.JSONDecodeError:
            pass

    # Check step references for github.event.pull_request.head.*
    cursor.execute("""
        SELECT reference_path
        FROM github_step_references
        WHERE step_id = ?
        AND reference_location = 'with'
        AND reference_path IS NOT NULL
    """, (step_id,))

    # Filter in Python: Check if reference_path starts with untrusted prefix
    for (reference_path,) in cursor.fetchall():
        if reference_path.startswith('github.event.pull_request.head'):
            return True

    return False


def _build_untrusted_checkout_finding(workflow_path: str, workflow_name: str,
                                      job_key: str, step_name: str,
                                      sequence_order: int, permissions: dict,
                                      with_args: str) -> StandardFinding:
    """Build finding for untrusted checkout vulnerability.

    Args:
        workflow_path: Path to workflow file
        workflow_name: Workflow display name
        job_key: Job key
        step_name: Step display name
        sequence_order: Step order in job
        permissions: Job permissions dict
        with_args: Checkout arguments JSON

    Returns:
        StandardFinding object
    """
    # Analyze permission risk
    has_write_perms = any(
        perm in permissions and permissions[perm] in ('write', 'write-all')
        for perm in ['contents', 'packages', 'pull-requests', 'id-token']
    )

    severity = Severity.CRITICAL if has_write_perms else Severity.HIGH

    # Parse with_args for code snippet
    try:
        args = json.loads(with_args) if with_args else {}
        ref_value = args.get('ref', 'github.event.pull_request.head.sha')
    except json.JSONDecodeError:
        ref_value = 'unknown'

    message = (
        f"Workflow '{workflow_name}' checks out untrusted PR code at step #{sequence_order + 1} "
        f"in job '{job_key}' with pull_request_target trigger. "
        f"Attacker-controlled code can execute with {'write permissions' if has_write_perms else 'read permissions'}."
    )

    code_snippet = f"""
# Vulnerable Pattern:
on:
  pull_request_target:  # Runs in target context with secrets

jobs:
  {job_key}:
    steps:
      - name: {step_name}
        uses: actions/checkout@v4
        with:
          ref: {ref_value}  # VULN: Untrusted attacker code
    """

    details = {
        'workflow': workflow_path,
        'job_key': job_key,
        'step_name': step_name,
        'step_order': sequence_order,
        'permissions': permissions,
        'has_write_permissions': has_write_perms,
        'checkout_ref': ref_value,
        'mitigation': (
            "1. Use pull_request trigger instead of pull_request_target, or "
            "2. Add validation job that runs first with 'needs:' dependency, or "
            "3. Only checkout base branch code in early steps"
        )
    }

    return StandardFinding(
        file_path=workflow_path,
        line=0,  # Workflow-level finding (could enhance with line lookup)
        rule_name="untrusted_checkout_sequence",
        message=message,
        severity=severity,
        category="supply-chain",
        confidence="high",
        snippet=code_snippet.strip(),
        cwe_id="CWE-284",
        additional_info=details
    )
