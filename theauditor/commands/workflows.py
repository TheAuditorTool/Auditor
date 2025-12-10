"""GitHub Actions workflow security analysis.

Commands for analyzing GitHub Actions workflows, detecting CI/CD security
vulnerabilities, and reporting on workflow misconfigurations.
"""

import json
import sqlite3
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.logging import logger

from .. import __version__
from ..utils.error_handler import handle_exceptions


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def workflows():
    """GitHub Actions CI/CD pipeline security analysis (supply chain attacks, permission escalation).

    Group command for analyzing GitHub Actions workflows to detect CI/CD-specific vulnerabilities
    including untrusted code execution, command injection from PR data, overprivileged workflows,
    and supply chain risks from external actions. Focuses on .github/workflows/*.yml files.

    AI ASSISTANT CONTEXT:
      Purpose: Detect CI/CD security issues in GitHub Actions workflows
      Input: .github/workflows/*.yml files (extracted by 'aud full')
      Output: Console or JSON (--json), findings stored in database
      Prerequisites: aud full (extracts workflow files)
      Integration: CI/CD security audits, supply chain validation
      Performance: ~2-5 seconds (workflow parsing + rule matching)

    SUBCOMMANDS:
      analyze: Extract workflow data and run security rules
      report:  Generate consolidated workflow security report

    VULNERABILITY CLASSES DETECTED:
      - Untrusted code execution (pull_request_target with checkout)
      - Unpinned actions with secret access
      - Command injection from ${{github.event.*}} interpolation
      - Excessive permissions (write-all in untrusted contexts)
      - Supply chain risks (external reusable workflows)

    TYPICAL WORKFLOW:
      aud full
      aud workflows analyze

    EXAMPLES:
      aud workflows analyze
      aud workflows analyze --severity critical

    RELATED COMMANDS:
      aud detect-patterns  # Includes workflow security rules
      aud full             # Runs all analysis including workflows

    NOTE: GitHub Actions security requires understanding CI/CD attack vectors.
    See GitHub Security Lab for vulnerability research and patterns.

    SEE ALSO:
      aud manual workflows   Learn about common analysis workflows
    """
    pass


@workflows.command("analyze", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--workset", is_flag=True, help="Analyze workset files only")
@click.option(
    "--severity",
    type=click.Choice(["critical", "high", "medium", "low", "all"]),
    default="all",
    help="Minimum severity to report",
)
@click.option("--db", default="./.pf/repo_index.db", help="Database path")
@click.option(
    "--chunk-size", default=60000, type=int, help="Max chunk size for AI consumption (bytes)"
)
@handle_exceptions
def analyze(root, workset, severity, db, chunk_size):
    """Analyze GitHub Actions workflows for security issues.

    Extracts workflow data from the database and generates AI-optimized
    reports for vulnerability analysis. Combines workflow structure data
    with security findings from rules.

    The analysis includes:
    - Workflow triggers and permissions
    - Job dependencies and execution order
    - Step-level action usage and versions
    - Secret and credential exposure
    - External dependency risks

    Examples:
      aud workflows analyze                      # Analyze all workflows
      aud workflows analyze --workset            # Changed files only
      aud workflows analyze --severity critical  # Critical findings only

    Prerequisites:
      - Must run 'aud full' first to extract workflows
      - Optionally run 'aud detect-patterns' for security findings

    Output:
      Console or JSON (--json)           # Workflow analysis to stdout
      Data stored in database            # Query with aud query --findings
    """
    try:
        db_path = Path(db)
        if not db_path.exists():
            err_console.print(f"[error]Error: Database not found: {db}[/error]", highlight=False)
            err_console.print(
                "[error]Run 'aud full' first to extract GitHub Actions workflows.[/error]",
            )
            raise click.Abort()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        file_filter = None
        if workset:
            workset_path = Path(".pf/workset.json")
            if not workset_path.exists():
                err_console.print(
                    "[error]Error: Workset file not found. Run 'aud workset' first.[/error]",
                )
                raise click.Abort()

            with open(workset_path) as f:
                workset_data = json.load(f)
                workset_files = {p["path"] for p in workset_data.get("paths", [])}
                file_filter = workset_files
                console.print(
                    f"Analyzing {len(workset_files)} workset workflows...", highlight=False
                )

        console.print("Extracting GitHub Actions workflows from database...")
        workflow_data = _extract_workflow_data(cursor, file_filter)

        findings = _extract_findings(cursor, severity)

        analysis = {
            "metadata": {
                "tool": "TheAuditor",
                "version": __version__,
                "analysis_type": "github_actions_workflows",
                "severity_filter": severity,
                "workset_only": workset,
            },
            "summary": {
                "total_workflows": len(workflow_data),
                "total_jobs": sum(len(w.get("jobs", [])) for w in workflow_data),
                "total_steps": sum(
                    len(j.get("steps", [])) for w in workflow_data for j in w.get("jobs", [])
                ),
                "total_findings": len(findings),
                "severity_counts": _count_by_severity(findings),
            },
            "workflows": workflow_data,
            "findings": findings,
        }

        console.print("\nGitHub Actions Workflow Analysis:")
        console.print(f"  Workflows: {analysis['summary']['total_workflows']}", highlight=False)
        console.print(f"  Jobs: {analysis['summary']['total_jobs']}", highlight=False)
        console.print(f"  Steps: {analysis['summary']['total_steps']}", highlight=False)

        if findings:
            console.print(f"\n  Security Findings: {len(findings)}", highlight=False)
            for sev, count in analysis["summary"]["severity_counts"].items():
                if count > 0:
                    console.print(f"    {sev.title()}: {count}", highlight=False)

        critical_workflows = [
            w for w in workflow_data if "pull_request_target" in w.get("on_triggers", [])
        ]
        if critical_workflows:
            console.print(
                f"\nCritical Workflows Detected: {len(critical_workflows)}", highlight=False
            )
            console.print("  (Uses pull_request_target trigger)")
            for workflow in critical_workflows[:3]:
                console.print(
                    f"  - {workflow['workflow_name']} ({workflow['workflow_path']})",
                    highlight=False,
                )

        conn.close()

    except sqlite3.Error as e:
        err_console.print(f"[error]Database error: {e}[/error]", highlight=False)
        raise click.Abort() from e
    except Exception as e:
        logger.error(f"Failed to analyze workflows: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.Abort() from e


def _extract_workflow_data(cursor, file_filter=None):
    """Extract workflow data from database.

    Args:
        cursor: Database cursor
        file_filter: Optional set of file paths to filter by

    Returns:
        List of workflow dicts with jobs, steps, references
    """

    if file_filter:
        placeholders = ",".join("?" * len(file_filter))
        cursor.execute(
            f"""
            SELECT workflow_path, workflow_name, on_triggers, permissions, concurrency, env
            FROM github_workflows
            WHERE workflow_path IN ({placeholders})
        """,
            tuple(file_filter),
        )
    else:
        cursor.execute("""
            SELECT workflow_path, workflow_name, on_triggers, permissions, concurrency, env
            FROM github_workflows
        """)

    workflows = []
    for row in cursor.fetchall():
        workflow_path, workflow_name, on_triggers, permissions, concurrency, env = row

        workflow = {
            "workflow_path": workflow_path,
            "workflow_name": workflow_name,
            "on_triggers": json.loads(on_triggers) if on_triggers else [],
            "permissions": json.loads(permissions) if permissions else None,
            "concurrency": json.loads(concurrency) if concurrency else None,
            "env": json.loads(env) if env else None,
            "jobs": [],
        }

        cursor.execute(
            """
            SELECT job_id, job_key, job_name, runs_on, strategy, permissions, env,
                   if_condition, timeout_minutes, uses_reusable_workflow, reusable_workflow_path
            FROM github_jobs
            WHERE workflow_path = ?
        """,
            (workflow_path,),
        )

        for job_row in cursor.fetchall():
            (
                job_id,
                job_key,
                job_name,
                runs_on,
                strategy,
                job_perms,
                job_env,
                if_cond,
                timeout,
                uses_reusable,
                reusable_path,
            ) = job_row

            job = {
                "job_id": job_id,
                "job_key": job_key,
                "job_name": job_name,
                "runs_on": json.loads(runs_on) if runs_on else [],
                "strategy": json.loads(strategy) if strategy else None,
                "permissions": json.loads(job_perms) if job_perms else None,
                "env": json.loads(job_env) if job_env else None,
                "if_condition": if_cond,
                "timeout_minutes": timeout,
                "uses_reusable_workflow": bool(uses_reusable),
                "reusable_workflow_path": reusable_path,
                "dependencies": [],
                "steps": [],
            }

            cursor.execute(
                """
                SELECT needs_job_id FROM github_job_dependencies WHERE job_id = ?
            """,
                (job_id,),
            )
            job["dependencies"] = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT step_id, sequence_order, step_name, uses_action, uses_version,
                       run_script, shell, env, with_args, if_condition, timeout_minutes,
                       continue_on_error
                FROM github_steps
                WHERE job_id = ?
                ORDER BY sequence_order
            """,
                (job_id,),
            )

            for step_row in cursor.fetchall():
                (
                    step_id,
                    seq,
                    step_name,
                    uses_action,
                    uses_version,
                    run_script,
                    shell,
                    step_env,
                    with_args,
                    step_if,
                    step_timeout,
                    continue_err,
                ) = step_row

                step = {
                    "step_id": step_id,
                    "sequence_order": seq,
                    "step_name": step_name,
                    "uses_action": uses_action,
                    "uses_version": uses_version,
                    "run_script": run_script,
                    "shell": shell,
                    "env": json.loads(step_env) if step_env else None,
                    "with_args": json.loads(with_args) if with_args else None,
                    "if_condition": step_if,
                    "timeout_minutes": step_timeout,
                    "continue_on_error": bool(continue_err),
                    "references": [],
                }

                cursor.execute(
                    """
                    SELECT reference_location, reference_type, reference_path
                    FROM github_step_references
                    WHERE step_id = ?
                """,
                    (step_id,),
                )

                for ref_row in cursor.fetchall():
                    ref_location, ref_type, ref_path = ref_row
                    step["references"].append(
                        {"location": ref_location, "type": ref_type, "path": ref_path}
                    )

                job["steps"].append(step)

            workflow["jobs"].append(job)

        workflows.append(workflow)

    return workflows


def _extract_findings(cursor, severity_filter):
    """Extract security findings from database.

    Args:
        cursor: Database cursor
        severity_filter: Severity level filter ('critical', 'high', etc. or 'all')

    Returns:
        List of finding dicts
    """

    severity_map = {
        "critical": "severity = 'critical'",
        "high": "severity IN ('critical', 'high')",
        "medium": "severity IN ('critical', 'high', 'medium')",
        "low": "severity IN ('critical', 'high', 'medium', 'low')",
        "all": "1=1",
    }

    severity_condition = severity_map.get(severity_filter, "1=1")

    cursor.execute(f"""
        SELECT file, line, rule, tool, message, severity, category, confidence,
               code_snippet, cwe, timestamp
        FROM findings_consolidated
        WHERE tool = 'github-actions-rules'
        AND {severity_condition}
        ORDER BY severity, file, line
    """)

    findings = []
    for row in cursor.fetchall():
        file, line, rule, tool, message, severity, category, confidence, snippet, cwe, timestamp = (
            row
        )

        findings.append(
            {
                "file": file,
                "line": line,
                "rule": rule,
                "tool": tool,
                "message": message,
                "severity": severity,
                "category": category,
                "confidence": confidence,
                "code_snippet": snippet,
                "cwe": cwe,
                "timestamp": timestamp,
                "details": {},
            }
        )

    return findings


def _count_by_severity(findings):
    """Count findings by severity level.

    Args:
        findings: List of finding dicts

    Returns:
        Dict of severity -> count
    """
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        severity = finding.get("severity", "low")
        if severity in counts:
            counts[severity] += 1
    return counts


def _create_chunks(workflows, findings, chunk_size):
    """Create AI-optimized chunks for LLM consumption.

    Splits workflow data into chunks under chunk_size bytes.
    Each chunk is self-contained with metadata.

    Args:
        workflows: List of workflow dicts
        findings: List of finding dicts
        chunk_size: Max size in bytes per chunk

    Returns:
        List of chunk dicts
    """
    chunks = []
    current_chunk = {
        "metadata": {
            "chunk_number": 1,
            "total_chunks": None,
            "content_type": "github_actions_workflows",
        },
        "workflows": [],
        "findings": [],
    }
    current_size = len(json.dumps(current_chunk))

    for workflow in workflows:
        workflow_json = json.dumps(workflow)
        workflow_size = len(workflow_json)

        if current_size + workflow_size > chunk_size and current_chunk["workflows"]:
            chunks.append(current_chunk)
            current_chunk = {
                "metadata": {
                    "chunk_number": len(chunks) + 1,
                    "total_chunks": None,
                    "content_type": "github_actions_workflows",
                },
                "workflows": [],
                "findings": [],
            }
            current_size = len(json.dumps(current_chunk))

        current_chunk["workflows"].append(workflow)
        current_size += workflow_size

    if findings:
        findings_size = len(json.dumps(findings))
        if current_size + findings_size > chunk_size and current_chunk["workflows"]:
            chunks.append(current_chunk)
            current_chunk = {
                "metadata": {
                    "chunk_number": len(chunks) + 1,
                    "total_chunks": None,
                    "content_type": "github_actions_findings",
                },
                "workflows": [],
                "findings": findings,
            }
        else:
            current_chunk["findings"] = findings

    if current_chunk["workflows"] or current_chunk["findings"]:
        chunks.append(current_chunk)

    total = len(chunks)
    for chunk in chunks:
        chunk["metadata"]["total_chunks"] = total

    return chunks
