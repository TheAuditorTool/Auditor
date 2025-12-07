"""Planning and verification commands for implementation workflows."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.planning import verification
from theauditor.planning.manager import PlanningManager
from theauditor.utils.error_handler import handle_exceptions

TRIGGER_START = "<!-- THEAUDITOR:START -->"
TRIGGER_END = "<!-- THEAUDITOR:END -->"


TRIGGER_BLOCK = f"""{TRIGGER_START}
# TheAuditor Planning Agent System

When user mentions planning, refactoring, security, or dataflow keywords, load specialized agents:

**Agent Triggers:**
- "refactor", "split", "extract", "merge", "modularize" => @/.theauditor_tools/agents/refactor.md
- "security", "vulnerability", "XSS", "SQL injection", "CSRF", "taint", "sanitize" => @/.theauditor_tools/agents/security.md
- "plan", "architecture", "design", "organize", "structure", "approach" => @/.theauditor_tools/agents/planning.md
- "dataflow", "trace", "track", "flow", "source", "sink", "propagate" => @/.theauditor_tools/agents/dataflow.md

**Agent Purpose:**
These agents enforce query-driven workflows using TheAuditor's database:
- NO file reading - use `aud query`, `aud blueprint`, `aud context`
- NO guessing patterns - follow detected precedents from blueprint
- NO assuming conventions - match detected naming/frameworks
- MANDATORY sequence: blueprint => query => synthesis
- ALL recommendations cite database query results

**Agent Files Location:**
Agents are copied to .auditor_venv/.theauditor_tools/agents/ during venv setup.
Run `aud setup-ai --target . --sync` to reinstall agents if missing.

{TRIGGER_END}
"""


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def planning():
    """Planning and Verification System - Database-Centric Task Management

    AI ASSISTANT CONTEXT:
      Purpose: Database-centric task tracking with spec-based verification
      Input: .pf/planning/planning.db (plan/task/job hierarchy), .pf/repo_index.db (verification)
      Output: Plan status, verification results, git snapshots for rollback
      Prerequisites: aud full (for verify-task to query indexed code)
      Integration: Works with aud refactor profiles, session logging, git snapshots
      Performance: <1 second (database queries only)

    PURPOSE:
      The planning system provides deterministic task tracking with spec-based
      verification. Unlike external tools (Jira, Linear), planning integrates
      directly with TheAuditor's indexed codebase for instant verification.

      Key benefits:
      - Verification specs query actual code (not developer self-assessment)
      - Git snapshots create immutable audit trail
      - Zero external dependencies (offline-first)
      - Works seamlessly with aud full workflow

    QUICK START:
      # Initialize your first plan
      aud planning init --name "Migration Plan"

      # Add tasks with verification specs
      aud planning add-task 1 --title "Task" --spec spec.yaml

      # Make code changes, then verify
      aud full --index && aud planning verify-task 1 1 --verbose

    COMMON WORKFLOWS:

      Greenfield Feature Development:
        1. aud planning init --name "New Feature"
        2. aud query --api "/users" --format json  # Find analogous patterns
        3. aud planning add-task 1 --title "Add /products endpoint"
        4. [Implement feature]
        5. aud full --index && aud planning verify-task 1 1

      Refactoring Migration:
        1. aud planning init --name "Auth0 to Cognito"
        2. aud planning add-task 1 --title "Migrate routes" --spec auth_spec.yaml
        3. [Make changes]
        4. aud full --index && aud planning verify-task 1 1 --auto-update
        5. aud planning archive 1 --notes "Deployed to prod"

      Checkpoint-Driven Development:
        1. aud planning add-task 1 --title "Complex Refactor"
        2. [Make partial changes]
        3. aud planning verify-task 1 1  # Creates snapshot on failure
        4. [Continue work]
        5. aud planning rewind 1  # Show rollback if needed

    DATABASE STRUCTURE:
      .pf/planning/planning.db (separate from repo_index.db, persists across aud full)
      - plans              # Top-level plan metadata
      - plan_tasks         # Individual tasks (auto-numbered 1,2,3...)
      - plan_specs         # YAML verification specs (RefactorProfile format)
      - code_snapshots     # Git checkpoint metadata
      - code_diffs         # Full unified diffs for rollback

    VERIFICATION SPECS:
      Specs use RefactorProfile YAML format (compatible with aud refactor):

      Example - JWT Secret Migration:
        refactor_name: Secure JWT Implementation
        description: Ensure all JWT signing uses env vars
        rules:
          - id: jwt-secret-env
            description: JWT must use process.env.JWT_SECRET
            match:
              identifiers: [jwt.sign]
            expect:
              identifiers: [process.env.JWT_SECRET]

      See: docs/planning/examples/ for more spec templates

    PREREQUISITES:
      - Run 'aud full' to create .pf/ directory and build repo_index.db
      - Verification queries indexed code (not raw files)

    COMMANDS:
      init         Create new plan (--name required)
      show         Display plan status and task list
      list         List all plans in database
      add-phase    Add phase to group tasks (--phase-number, --title required)
      add-task     Add task with optional spec (--title required)
      add-job      Add checkbox item to task (--description required)
      update-task  Change task status or assignee
      verify-task  Run spec against indexed code
      archive      Create final snapshot and mark complete
      rewind       Show git commands to rollback
      checkpoint   Create incremental snapshot
      show-diff    View stored diffs for a task
      validate     Validate against session logs

    SUBCOMMAND QUICK REFERENCE:
      aud planning init --name "Plan Name"
      aud planning add-phase 1 --phase-number 1 --title "Phase Title"
      aud planning add-task 1 --title "Task Title" --phase 1
      aud planning add-job 1 1 --description "Checkbox item"
      aud planning update-task 1 1 --status completed
      aud planning verify-task 1 1 --verbose --auto-update
      aud planning show 1 --format phases

    FLAG NOTE: init uses --name, add-phase/add-task use --title

    For detailed help: aud planning <command> --help

    SEE ALSO:
      aud manual planning   Learn about database-centric task management
    """
    pass


@planning.command(cls=RichCommand)
@click.option("--name", required=True, help="Plan name")
@click.option("--description", default="", help="Plan description")
@handle_exceptions
def init(name, description):
    """Create a new implementation plan.

    Example:
        aud planning init --name "Auth Migration" --description "Migrate to OAuth2"
    """

    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        manager = PlanningManager.init_database(db_path)
        console.print(f"Initialized planning database: {db_path}", highlight=False)
    else:
        manager = PlanningManager(db_path)

    plan_id = manager.create_plan(name, description)

    console.print(f"Created plan {plan_id}: {name}", highlight=False)
    if description:
        console.print(f"Description: {description}", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.option("--tasks/--no-tasks", default=True, help="Show task list (default: True)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
@click.option(
    "--format",
    type=click.Choice(["flat", "phases"]),
    default="phases",
    help="Display format (default: phases)",
)
@handle_exceptions
def show(plan_id, tasks, verbose, format):
    """Display plan details and task status.

    By default shows full hierarchy (phases → tasks → jobs).

    Example:
        aud planning show 1                           # Full hierarchy (default)
        aud planning show 1 --format flat             # Flat task list
        aud planning show 1 --no-tasks                # Basic info only
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        err_console.print(f"[error]Error: Plan {plan_id} not found[/error]", highlight=False)
        return

    console.rule()
    console.print(f"Plan {plan['id']}: {plan['name']}", highlight=False)
    console.rule()
    console.print(f"Status: {plan['status']}", highlight=False)
    console.print(f"Created: {plan['created_at']}", highlight=False)
    if plan["description"]:
        console.print(f"Description: {plan['description']}", highlight=False)
    console.print(f"Database: {db_path}", highlight=False)

    if verbose and plan["metadata_json"]:
        metadata = json.loads(plan["metadata_json"])
        console.print("\nMetadata:")
        for key, value in metadata.items():
            console.print(f"  {key}: {value}", highlight=False)

    if tasks:
        if format == "phases":
            cursor = manager.conn.cursor()

            cursor.execute(
                """
                SELECT id, phase_number, title, description, success_criteria, status
                FROM plan_phases
                WHERE plan_id = ?
                ORDER BY phase_number
            """,
                (plan_id,),
            )
            phases = cursor.fetchall()

            if phases:
                console.print("\nPhase -> Task -> Job Hierarchy:")
                for phase in phases:
                    phase_id, phase_num, phase_title, phase_desc, success_criteria, phase_status = (
                        phase
                    )
                    status_icon = "[X]" if phase_status == "completed" else "[ ]"
                    console.print(
                        f"\n{status_icon} PHASE {phase_num}: {phase_title}", highlight=False
                    )
                    if success_criteria:
                        console.print(f"    Success Criteria: {success_criteria}", highlight=False)
                    if verbose and phase_desc:
                        console.print(f"    Description: {phase_desc}", highlight=False)

                    cursor.execute(
                        """
                        SELECT id, task_number, title, description, status, audit_status
                        FROM plan_tasks
                        WHERE plan_id = ? AND phase_id = ?
                        ORDER BY task_number
                    """,
                        (plan_id, phase_id),
                    )
                    tasks_in_phase = cursor.fetchall()

                    for task in tasks_in_phase:
                        task_id, task_num, task_title, task_desc, task_status, audit_status = task
                        task_icon = "[X]" if task_status == "completed" else "[ ]"
                        audit_label = (
                            f" (audit: {audit_status})" if audit_status != "pending" else ""
                        )
                        console.print(
                            f"  {task_icon} Task {task_num}: {task_title}{audit_label}",
                            highlight=False,
                        )
                        if verbose and task_desc:
                            console.print(f"      Description: {task_desc}", highlight=False)

                        cursor.execute(
                            """
                            SELECT job_number, description, completed, is_audit_job
                            FROM plan_jobs
                            WHERE task_id = ?
                            ORDER BY job_number
                        """,
                            (task_id,),
                        )
                        jobs = cursor.fetchall()

                        for job in jobs:
                            job_num, job_desc, completed, is_audit = job
                            job_icon = "[X]" if completed else "[ ]"
                            audit_marker = " [AUDIT]" if is_audit else ""
                            console.print(
                                f"    {job_icon} Job {job_num}: {job_desc}{audit_marker}",
                                highlight=False,
                            )

                cursor.execute(
                    """
                    SELECT id, task_number, title, status, audit_status
                    FROM plan_tasks
                    WHERE plan_id = ? AND (phase_id IS NULL OR phase_id NOT IN (SELECT id FROM plan_phases WHERE plan_id = ?))
                    ORDER BY task_number
                """,
                    (plan_id, plan_id),
                )
                orphaned_tasks = cursor.fetchall()

                if orphaned_tasks:
                    console.print("\nOrphaned Tasks (not in any phase):")
                    for task in orphaned_tasks:
                        task_id, task_num, task_title, task_status, audit_status = task
                        task_icon = "[X]" if task_status == "completed" else "[ ]"
                        audit_label = (
                            f" (audit: {audit_status})" if audit_status != "pending" else ""
                        )
                        console.print(
                            f"  {task_icon} Task {task_num}: {task_title}{audit_label}",
                            highlight=False,
                        )
            else:
                console.print(
                    "\nNo phases defined. Use --format flat or add phases with 'aud planning add-phase'"
                )

        else:
            task_list = manager.list_tasks(plan_id)
            console.print(f"\nTasks ({len(task_list)}):", highlight=False)
            for task in task_list:
                status_icon = "[X]" if task["status"] == "completed" else "[ ]"
                console.print(
                    f"  {status_icon} Task {task['task_number']}: {task['title']}", highlight=False
                )
                console.print(f"    Status: {task['status']}", highlight=False)
                if task["assigned_to"]:
                    console.print(f"    Assigned: {task['assigned_to']}", highlight=False)
                if verbose and task["description"]:
                    console.print(f"    Description: {task['description']}", highlight=False)

    console.print("\n" + "=" * 80, markup=False)
    console.print("Commands:")
    console.print(
        '  aud planning add-phase {plan_id} --phase-number N --title "..." --description "..."'
    )
    console.print('  aud planning add-task {plan_id} --title "..." --description "..." --phase N')
    console.print('  aud planning add-job {plan_id} <task_number> --description "..."')
    console.print("  aud planning update-task {plan_id} <task_number> --status completed")
    console.print("  aud planning verify-task {plan_id} <task_number> --auto-update")
    console.print("  aud planning validate {plan_id}  # Validate against session logs")
    console.print("\nFiles:")
    console.print(f"  Database: {db_path}", highlight=False)
    console.print("  Agent prompts: agents/planning.md, agents/refactor.md, etc.")
    console.rule()


@planning.command("list", cls=RichCommand)
@click.option("--status", help="Filter by status (active/completed/archived)")
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
@handle_exceptions
def list_plans(status, format):
    """List all plans in the database.

    Example:
        aud planning list
        aud planning list --status active
        aud planning list --format json
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"

    if not db_path.exists():
        console.print("No planning database found (.pf/planning/planning.db)")
        console.print("Run 'aud planning init --name \"Plan Name\"' to create your first plan")
        return

    manager = PlanningManager(db_path)
    cursor = manager.conn.cursor()

    query = "SELECT id, name, status, created_at FROM plans"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    plans = cursor.fetchall()

    if not plans:
        if status:
            console.print(f"No {status} plans found", highlight=False)
        else:
            console.print("No plans found")
        return

    if format == "json":
        result = [{"id": p[0], "name": p[1], "status": p[2], "created_at": p[3]} for p in plans]
        console.print(json.dumps(result, indent=2), markup=False)
    else:
        console.rule()
        console.print(f"{'ID':<5} {'Name':<40} {'Status':<15} {'Created':<20}", highlight=False)
        console.rule()
        for plan in plans:
            pid, name, pstatus, created = plan
            console.print(f"{pid:<5} {name[:40]:<40} {pstatus:<15} {created:<20}", highlight=False)
        console.rule()
        console.print(f"Total: {len(plans)} plans", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.option("--phase-number", type=int, required=True, help="Phase number")
@click.option("--title", required=True, help="Phase title")
@click.option("--description", default="", help="Phase description")
@click.option("--success-criteria", help="What completion looks like for this phase (criteria)")
@handle_exceptions
def add_phase(plan_id, phase_number, title, description, success_criteria):
    """Add a phase to a plan (hierarchical planning structure).

    Phases group related tasks and explicitly state success criteria.

    Example:
        aud planning add-phase 1 --phase-number 1 --title "Load Context" \\
            --success-criteria "Blueprint analysis complete. Precedents extracted from database."
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    from datetime import UTC

    manager.add_plan_phase(
        plan_id=plan_id,
        phase_number=phase_number,
        title=title,
        description=description,
        success_criteria=success_criteria,
        status="pending",
        created_at=datetime.now(UTC).isoformat(),
    )
    manager.commit()

    console.print(f"Added phase {phase_number} to plan {plan_id}: {title}", highlight=False)
    if success_criteria:
        console.print(f"Success Criteria: {success_criteria}", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.option("--title", required=True, help="Task title")
@click.option("--description", default="", help="Task description")
@click.option("--spec", type=click.Path(exists=True), help="YAML verification spec file")
@click.option("--assigned-to", help="Assignee name")
@click.option("--phase", type=int, help="Phase number to associate this task with (optional)")
@handle_exceptions
def add_task(plan_id, title, description, spec, assigned_to, phase):
    """Add a task to a plan with optional verification spec.

    Can optionally associate task with a phase (hierarchical planning).

    Example:
        aud planning add-task 1 --title "Migrate auth" --spec auth_spec.yaml
        aud planning add-task 1 --title "Query patterns" --phase 2
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    spec_yaml = None
    if spec:
        spec_path = Path(spec)
        spec_yaml = spec_path.read_text()

    phase_id = None
    if phase is not None:
        cursor = manager.conn.cursor()
        cursor.execute(
            "SELECT id FROM plan_phases WHERE plan_id = ? AND phase_number = ?", (plan_id, phase)
        )
        phase_row = cursor.fetchone()
        if phase_row:
            phase_id = phase_row[0]
        else:
            err_console.print(
                f"[error]Warning: Phase {phase} not found in plan {plan_id}[/error]",
                highlight=False,
            )
            return

    task_id = manager.add_task(
        plan_id=plan_id,
        title=title,
        description=description,
        spec_yaml=spec_yaml,
        assigned_to=assigned_to,
    )

    if phase_id is not None:
        cursor = manager.conn.cursor()
        cursor.execute("UPDATE plan_tasks SET phase_id = ? WHERE id = ?", (phase_id, task_id))
        manager.conn.commit()

    task_number = manager.get_task_number(task_id)
    console.print(f"Added task {task_number} to plan {plan_id}: {title}", highlight=False)
    if phase is not None:
        console.print(f"Associated with phase {phase}", highlight=False)
    if spec:
        console.print(f"Verification spec: {spec}", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--description", required=True, help="Job description (checkbox item)")
@click.option("--is-audit", is_flag=True, help="Mark this job as an audit job")
@handle_exceptions
def add_job(plan_id, task_number, description, is_audit):
    """Add a job (checkbox item) to a task (hierarchical task breakdown).

    Jobs are atomic checkbox actions within a task. Audit jobs verify work completion.

    Example:
        aud planning add-job 1 1 --description "Execute aud blueprint --structure"
        aud planning add-job 1 1 --description "Verify blueprint ran successfully" --is-audit
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        err_console.print(
            f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
            highlight=False,
        )
        return

    cursor = manager.conn.cursor()
    cursor.execute("SELECT MAX(job_number) FROM plan_jobs WHERE task_id = ?", (task_id,))
    max_job = cursor.fetchone()[0]
    job_number = (max_job or 0) + 1

    from datetime import UTC

    manager.add_plan_job(
        task_id=task_id,
        job_number=job_number,
        description=description,
        completed=0,
        is_audit_job=1 if is_audit else 0,
        created_at=datetime.now(UTC).isoformat(),
    )
    manager.commit()

    job_type = "audit job" if is_audit else "job"
    console.print(
        f"Added {job_type} {job_number} to task {task_number}: {description}", highlight=False
    )


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option(
    "--status",
    type=click.Choice(["pending", "in_progress", "completed", "blocked"]),
    help="New status",
)
@click.option("--assigned-to", help="Reassign task")
@handle_exceptions
def update_task(plan_id, task_number, status, assigned_to):
    """Update task status or assignment.

    Example:
        aud planning update-task 1 1 --status completed
        aud planning update-task 1 2 --assigned-to "Alice"
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        err_console.print(
            f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
            highlight=False,
        )
        return

    if status:
        manager.update_task_status(task_id, status)
        console.print(f"Updated task {task_number} status: {status}", highlight=False)

    if assigned_to:
        manager.update_task_assignee(task_id, assigned_to)
        console.print(f"Reassigned task {task_number} to: {assigned_to}", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed violations")
@click.option("--auto-update", is_flag=True, help="Auto-update task status based on result")
@click.option(
    "--emit-reads",
    is_flag=True,
    help="Output JSON with file:line ranges for AI-assisted fixing",
)
@handle_exceptions
def verify_task(plan_id, task_number, verbose, auto_update, emit_reads):
    """Verify task completion against its spec.

    Runs verification spec against current codebase and reports violations.
    Optionally updates task status based on verification result.

    Example:
        aud planning verify-task 1 1 --verbose
        aud planning verify-task 1 1 --auto-update
        aud planning verify-task 1 1 --emit-reads  # JSON for AI batch-reading
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    repo_index_db = Path.cwd() / ".pf" / "repo_index.db"

    if not repo_index_db.exists():
        err_console.print(
            "[error]Error: repo_index.db not found. Run 'aud full' first.[/error]",
        )
        return

    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        err_console.print(
            f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
            highlight=False,
        )
        return

    cursor = manager.conn.cursor()
    cursor.execute("SELECT status, completed_at FROM plan_tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    was_previously_completed = task_row and task_row[0] == "completed" and task_row[1] is not None

    spec_yaml = manager.load_task_spec(task_id)
    if not spec_yaml:
        err_console.print(
            f"[error]Error: No verification spec for task {task_number}[/error]",
            highlight=False,
        )
        return

    console.print(f"Verifying task {task_number}...", highlight=False)

    try:
        result = verification.verify_task_spec(spec_yaml, repo_index_db, Path.cwd())

        total_violations = result.total_violations()

        is_regression = was_previously_completed and total_violations > 0

        console.print("\nVerification complete:")
        console.print(f"  Total violations: {total_violations}", highlight=False)

        if is_regression:
            err_console.print(
                "[error]\n  WARNING: REGRESSION DETECTED[/error]",
            )
            err_console.print(
                f"[error]  Task {task_number} was previously completed but now has {total_violations} violation(s)[/error]",
                highlight=False,
            )
            err_console.print(
                "[error]  Code changes since completion have broken verification[/error]",
            )

        if verbose and total_violations > 0:
            console.print("\nViolations by rule:")
            for rule_result in result.rule_results:
                if rule_result.violations:
                    console.print(
                        f"  {rule_result.rule.id}: {len(rule_result.violations)} violations",
                        highlight=False,
                    )
                    for violation in rule_result.violations[:5]:
                        console.print(
                            f"    - {violation['file']}:{violation.get('line', '?')}",
                            highlight=False,
                        )
                    if len(rule_result.violations) > 5:
                        console.print(
                            f"    ... and {len(rule_result.violations) - 5} more", highlight=False
                        )

        if emit_reads and total_violations > 0:
            # Build structured output for AI-assisted fixing
            import json as json_lib
            from collections import defaultdict

            # Group violations by file
            file_violations = defaultdict(list)
            for rule_result in result.rule_results:
                for v in rule_result.violations:
                    file_path = v.get("file", "unknown")
                    line = v.get("line")
                    if line:
                        file_violations[file_path].append({
                            "line": line,
                            "rule": rule_result.rule.id,
                            "message": v.get("message", rule_result.rule.id),
                        })

            # Build read ranges (group nearby lines, add context)
            context_lines = 5
            reads = []
            for file_path, violations in sorted(file_violations.items()):
                # Sort by line and merge overlapping ranges
                lines = sorted(set(v["line"] for v in violations))
                ranges = []
                for line in lines:
                    start = max(1, line - context_lines)
                    end = line + context_lines
                    # Merge with previous range if overlapping
                    if ranges and start <= ranges[-1]["end"] + 1:
                        ranges[-1]["end"] = max(ranges[-1]["end"], end)
                        ranges[-1]["violations"].extend(
                            [v for v in violations if v["line"] == line]
                        )
                    else:
                        ranges.append({
                            "start": start,
                            "end": end,
                            "violations": [v for v in violations if v["line"] == line],
                        })

                for r in ranges:
                    reads.append({
                        "file": file_path,
                        "start_line": r["start"],
                        "end_line": r["end"],
                        "violations": r["violations"],
                    })

            output = {
                "task": {"plan_id": plan_id, "task_number": task_number},
                "total_violations": total_violations,
                "reads": reads,
                "next_step": f"Read the files above, fix violations, then run: aud planning verify-task {plan_id} {task_number}",
            }
            console.print("\n--- EMIT-READS JSON ---", highlight=False)
            console.print(json_lib.dumps(output, indent=2), markup=False)
            console.print("--- END JSON ---\n", highlight=False)

        cursor = manager.conn.cursor()
        audit_status = "pass" if total_violations == 0 else "fail"

        cursor.execute(
            "UPDATE plan_tasks SET audit_status = ? WHERE id = ?", (audit_status, task_id)
        )
        manager.conn.commit()

        console.print(f"\nAudit status: {audit_status}", highlight=False)

        if auto_update:
            if total_violations == 0:
                new_status = "completed"
                manager.update_task_status(task_id, new_status, datetime.now(UTC).isoformat())
            elif is_regression:
                new_status = "failed"
                manager.update_task_status(task_id, new_status, None)
            else:
                new_status = "in_progress"
                manager.update_task_status(task_id, new_status, None)
            console.print(f"Task status updated: {new_status}", highlight=False)

        if total_violations > 0:
            snapshot = manager.create_snapshot(
                plan_id=plan_id,
                checkpoint_name=f"verify-task-{task_number}-failed",
                project_root=Path.cwd(),
                task_id=task_id,
            )
            console.print(f"Snapshot created: {snapshot['shadow_sha'][:8]}", highlight=False)
            if snapshot.get("sequence"):
                console.print(f"Sequence: {snapshot['sequence']}", highlight=False)

    except ValueError as e:
        err_console.print(f"[error]Error: Invalid verification spec: {e}[/error]", highlight=False)
    except Exception as e:
        err_console.print(f"[error]Error during verification: {e}[/error]", highlight=False)
        raise


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.option("--notes", help="Archive notes")
@handle_exceptions
def archive(plan_id, notes):
    """Archive completed plan with final snapshot.

    Creates a final snapshot of the codebase state and marks the plan
    as archived. This creates an immutable audit trail.

    Example:
        aud planning archive 1 --notes "Migration completed successfully"
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        err_console.print(f"[error]Error: Plan {plan_id} not found[/error]", highlight=False)
        return

    all_tasks = manager.list_tasks(plan_id)
    incomplete_tasks = [t for t in all_tasks if t["status"] != "completed"]

    if incomplete_tasks:
        err_console.print(
            f"[error]Warning: Plan has {len(incomplete_tasks)} incomplete task(s):[/error]",
            highlight=False,
        )
        for task in incomplete_tasks[:5]:
            err_console.print(
                f"[error]  - Task {task['task_number']}: {task['title']} (status: {task['status']})[/error]",
                highlight=False,
            )
        if len(incomplete_tasks) > 5:
            err_console.print(
                f"[error]  ... and {len(incomplete_tasks) - 5} more[/error]",
                highlight=False,
            )

        if not click.confirm("\nArchive plan anyway?"):
            console.print("Archive cancelled.")
            return

    console.print("Creating final snapshot...")
    snapshot = manager.create_snapshot(
        plan_id=plan_id, checkpoint_name="archive", project_root=Path.cwd()
    )

    metadata = json.loads(plan["metadata_json"]) if plan["metadata_json"] else {}
    metadata["archived_at"] = datetime.now(UTC).isoformat()
    metadata["final_snapshot_id"] = snapshot.get("snapshot_id")
    if notes:
        metadata["archive_notes"] = notes

    manager.update_plan_status(plan_id, "archived", json.dumps(metadata))

    console.print(f"\nPlan {plan_id} archived successfully", highlight=False)
    console.print(f"Final snapshot: {snapshot['shadow_sha'][:8]}", highlight=False)
    console.print(f"Files affected: {len(snapshot['files_affected'])}", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int, required=False)
@click.option("--checkpoint", help="Specific checkpoint name to rewind to")
@click.option(
    "--to",
    "to_sequence",
    type=int,
    help="Rewind to specific sequence number (e.g., --to 2 for edit_2)",
)
@handle_exceptions
def rewind(plan_id, task_number, checkpoint, to_sequence):
    """Show rollback instructions for a plan or task.

    Displays git commands to revert to a previous snapshot state.
    Does NOT execute the commands - only shows them for manual review.

    For task-level granular rewind, use --to with sequence number.

    Example:
        aud planning rewind 1                    # List all plan snapshots
        aud planning rewind 1 --checkpoint "pre-migration"  # Plan-level rewind
        aud planning rewind 1 1 --to 2           # Task-level: rewind to edit_2
        aud planning rewind 1 1                  # List all task checkpoints
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        err_console.print(f"[error]Error: Plan {plan_id} not found[/error]", highlight=False)
        return

    cursor = manager.conn.cursor()

    if task_number is not None:
        task_id = manager.get_task_id(plan_id, task_number)
        if not task_id:
            err_console.print(
                f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
                highlight=False,
            )
            return

        if to_sequence:
            cursor.execute(
                """
                SELECT id, checkpoint_name, sequence, timestamp, git_ref
                FROM code_snapshots
                WHERE task_id = ? AND sequence <= ?
                ORDER BY sequence
            """,
                (task_id, to_sequence),
            )

            snapshots_to_apply = cursor.fetchall()

            if not snapshots_to_apply:
                err_console.print(
                    f"[error]Error: No checkpoints found up to sequence {to_sequence}[/error]",
                    highlight=False,
                )
                return

            console.print(
                f"Granular rewind to sequence {to_sequence} for task {task_number}", highlight=False
            )
            console.print(
                f"This will apply {len(snapshots_to_apply)} checkpoint(s):", highlight=False
            )
            console.print()

            for snapshot_row in snapshots_to_apply:
                _snapshot_id, checkpoint_name, seq, _timestamp, git_ref = snapshot_row
                console.print(f"  \\[{seq}] {checkpoint_name} ({git_ref[:8]})", highlight=False)

            console.print()
            console.print("WARNING: This requires applying diffs incrementally.")
            console.print("Current implementation shows git checkout only.")
            console.print()

            target_snapshot = snapshots_to_apply[-1]
            console.print(f"To rewind to sequence {to_sequence}, run:", highlight=False)
            console.print(f"  git checkout {target_snapshot[4]}", highlight=False)
            console.print()
            console.print("NOTE: Full incremental diff application not yet implemented.")
            console.print("This will revert to the git state at checkpoint {target_snapshot\\[1]}")

        else:
            cursor.execute(
                """
                SELECT id, checkpoint_name, sequence, timestamp, git_ref
                FROM code_snapshots
                WHERE task_id = ?
                ORDER BY sequence
            """,
                (task_id,),
            )

            task_snapshots = cursor.fetchall()

            if not task_snapshots:
                console.print(f"No checkpoints found for task {task_number}", highlight=False)
                return

            console.print(f"Checkpoints for task {task_number}:\n", highlight=False)
            for snapshot_row in task_snapshots:
                _snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row
                console.print(f"  \\[{seq}] {checkpoint_name}", highlight=False)
                console.print(f"      Git ref: {git_ref[:8]}", highlight=False)
                console.print(f"      Timestamp: {timestamp}", highlight=False)
                console.print()

            console.print("To rewind to a specific sequence:")
            console.print(f"  aud planning rewind {plan_id} {task_number} --to N", highlight=False)

    else:
        if checkpoint:
            cursor.execute(
                """
                SELECT id, checkpoint_name, timestamp, git_ref
                FROM code_snapshots
                WHERE plan_id = ? AND checkpoint_name = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (plan_id, checkpoint),
            )

            snapshot_row = cursor.fetchone()
            if not snapshot_row:
                err_console.print(
                    f"[error]Error: Checkpoint '{checkpoint}' not found[/error]",
                    highlight=False,
                )
                return

            console.print(f"Rewind to checkpoint: {snapshot_row[1]}", highlight=False)
            console.print(f"Timestamp: {snapshot_row[2]}", highlight=False)
            console.print(f"Git ref: {snapshot_row[3]}", highlight=False)
            console.print("\nTo revert to this state, run:")
            console.print(f"  git checkout {snapshot_row[3]}", highlight=False)
            console.print("\nOr to create a new branch from this state:")
            console.print(
                f"  git checkout -b rewind-{snapshot_row[1]} {snapshot_row[3]}", highlight=False
            )
        else:
            cursor.execute(
                """
                SELECT id, checkpoint_name, timestamp, git_ref
                FROM code_snapshots
                WHERE plan_id = ? AND task_id IS NULL
                ORDER BY timestamp DESC
            """,
                (plan_id,),
            )

            snapshots_list = cursor.fetchall()

            if not snapshots_list:
                console.print(f"No plan-level snapshots found for plan {plan_id}", highlight=False)
                console.print(
                    "(Task-level checkpoints exist - use: aud planning rewind <plan_id> <task_number>)"
                )
                return

            console.print(
                f"Plan-level snapshots for plan {plan_id} ({plan['name']}):\n", highlight=False
            )
            for snapshot in snapshots_list:
                console.print(f"  {snapshot[1]}", highlight=False)
                console.print(f"    Timestamp: {snapshot[2]}", highlight=False)
                console.print(f"    Git ref: {snapshot[3][:8]}", highlight=False)
                console.print()

            console.print("To rewind to a specific checkpoint:")
            console.print(f"  aud planning rewind {plan_id} --checkpoint <name>", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--name", help="Checkpoint name (optional, auto-generates if not provided)")
@handle_exceptions
def checkpoint(plan_id, task_number, name):
    """Create incremental snapshot after editing code.

    Use this command after making changes to track incremental edits.
    Each checkpoint is numbered sequentially (edit_1, edit_2, etc.).

    Example:
        # Make code changes
        aud planning checkpoint 1 1 --name "add-imports"
        # Make more changes
        aud planning checkpoint 1 1 --name "update-function"
        # View all checkpoints
        aud planning show-diff 1 1
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        err_console.print(
            f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
            highlight=False,
        )
        return

    if not name:
        cursor = manager.conn.cursor()
        cursor.execute("SELECT MAX(sequence) FROM code_snapshots WHERE task_id = ?", (task_id,))
        max_seq = cursor.fetchone()[0]
        next_seq = (max_seq or 0) + 1
        name = f"edit_{next_seq}"

    console.print(f"Creating checkpoint '{name}' for task {task_number}...", highlight=False)
    snapshot = manager.create_snapshot(
        plan_id=plan_id,
        checkpoint_name=name,
        project_root=Path.cwd(),
        task_id=task_id,
    )

    console.print(f"Checkpoint created: {snapshot['shadow_sha'][:8]}", highlight=False)
    if snapshot.get("sequence"):
        console.print(f"Sequence: {snapshot['sequence']}", highlight=False)
    console.print(f"Files affected: {len(snapshot['files_affected'])}", highlight=False)
    if snapshot["files_affected"]:
        for f in snapshot["files_affected"][:5]:
            console.print(f"  - {f}", highlight=False)
        if len(snapshot["files_affected"]) > 5:
            console.print(f"  ... and {len(snapshot['files_affected']) - 5} more", highlight=False)


@planning.command(cls=RichCommand)
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--sequence", type=int, help="Show specific checkpoint by sequence number")
@click.option("--file", help="Show diff for specific file only")
@handle_exceptions
def show_diff(plan_id, task_number, sequence, file):
    """View stored diffs for a task.

    Shows incremental checkpoints and diffs for the specified task.
    Use --sequence to view a specific checkpoint's diff.

    Example:
        aud planning show-diff 1 1              # List all checkpoints
        aud planning show-diff 1 1 --sequence 2 # Show edit_2 diff
        aud planning show-diff 1 1 --file auth.py  # Show diffs for auth.py only
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        err_console.print(
            f"[error]Error: Task {task_number} not found in plan {plan_id}[/error]",
            highlight=False,
        )
        return

    cursor = manager.conn.cursor()

    if sequence:
        cursor.execute(
            """
            SELECT id, checkpoint_name, sequence, timestamp, git_ref
            FROM code_snapshots
            WHERE task_id = ? AND sequence = ?
        """,
            (task_id, sequence),
        )

        snapshot_row = cursor.fetchone()
        if not snapshot_row:
            err_console.print(
                f"[error]Error: No checkpoint with sequence {sequence} found[/error]",
                highlight=False,
            )
            return

        snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

        console.print(f"Checkpoint: {checkpoint_name} (sequence {seq})", highlight=False)
        console.print(f"Timestamp: {timestamp}", highlight=False)
        console.print(f"Git ref: {git_ref[:8]}", highlight=False)
        console.print()

        query = "SELECT file_path, diff_text, added_lines, removed_lines FROM code_diffs WHERE snapshot_id = ?"
        params = [snapshot_id]

        if file:
            query += " AND file_path LIKE ?"
            params.append(f"%{file}%")

        cursor.execute(query, params)
        diffs = cursor.fetchall()

        if not diffs:
            console.print("No diffs found")
            return

        for diff_row in diffs:
            file_path, diff_text, added, removed = diff_row
            console.print(f"File: {file_path} (+{added}/-{removed})", highlight=False)
            console.rule()
            console.print(diff_text, markup=False)
            console.print()

    else:
        cursor.execute(
            """
            SELECT id, checkpoint_name, sequence, timestamp, git_ref
            FROM code_snapshots
            WHERE task_id = ?
            ORDER BY sequence
        """,
            (task_id,),
        )

        snapshots_list = cursor.fetchall()

        if not snapshots_list:
            console.print(f"No checkpoints found for task {task_number}", highlight=False)
            return

        console.print(f"Checkpoints for task {task_number}:\n", highlight=False)

        for snapshot_row in snapshots_list:
            snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

            cursor.execute(
                "SELECT COUNT(DISTINCT file_path) FROM code_diffs WHERE snapshot_id = ?",
                (snapshot_id,),
            )
            file_count = cursor.fetchone()[0]

            console.print(f"  \\[{seq}] {checkpoint_name}", highlight=False)
            console.print(f"      Timestamp: {timestamp}", highlight=False)
            console.print(f"      Git ref: {git_ref[:8]}", highlight=False)
            console.print(f"      Files: {file_count}", highlight=False)
            console.print()

        console.print("To view a specific checkpoint's diff:")
        console.print(
            f"  aud planning show-diff {plan_id} {task_number} --sequence N", highlight=False
        )


@planning.command("validate", cls=RichCommand)
@click.argument("plan_id", type=int)
@click.option("--session-id", help="Specific session ID to validate against (defaults to latest)")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@handle_exceptions
def validate_plan(plan_id, session_id, format):
    """Validate plan execution against session logs.

    Compares planned files vs actually modified files from session history.
    Checks workflow compliance and blind edit rate.

    Example:
        aud planning validate 1                    # Validate latest session
        aud planning validate 1 --session-id abc123  # Validate specific session
        aud planning validate 1 --format json     # JSON output
    """
    db_path = Path.cwd() / ".pf" / "planning" / "planning.db"
    session_db_path = Path.cwd() / ".pf" / "ml" / "session_history.db"

    if not session_db_path.exists():
        err_console.print(
            "[error]Error: Session database not found (.pf/ml/session_history.db)[/error]",
        )
        err_console.print(
            "[error]Run 'aud session analyze' to create session database[/error]",
        )
        err_console.print(
            "[error]Planning validation requires session logs[/error]",
        )
        raise click.ClickException("Session logging not enabled")

    manager = PlanningManager(db_path)
    plan = manager.get_plan(plan_id)
    if not plan:
        err_console.print(f"[error]Error: Plan {plan_id} not found[/error]", highlight=False)
        raise click.ClickException(f"Plan {plan_id} not found")

    session_conn = sqlite3.connect(session_db_path)
    session_cursor = session_conn.cursor()

    if session_id:
        session_cursor.execute(
            """
            SELECT session_id, task_description, workflow_compliant, compliance_score,
                   files_modified, diffs_scored
            FROM session_executions
            WHERE session_id = ?
        """,
            (session_id,),
        )
    else:
        session_cursor.execute(
            """
            SELECT session_id, task_description, workflow_compliant, compliance_score,
                   files_modified, diffs_scored
            FROM session_executions
            WHERE task_description LIKE ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (f"%{plan['name']}%",),
        )

    session_row = session_cursor.fetchone()
    if not session_row:
        err_console.print(
            f"[error]Error: No session found for plan '{plan['name']}'[/error]",
            highlight=False,
        )
        if session_id:
            err_console.print(
                f"[error]Session ID '{session_id}' not found in database[/error]",
                highlight=False,
            )
        raise click.ClickException("No matching session found")

    (
        session_id_val,
        _task_desc,
        workflow_compliant,
        compliance_score,
        _files_modified_count,
        diffs_json,
    ) = session_row

    import json as json_module

    diffs = json_module.loads(diffs_json) if diffs_json else []

    actual_files = [diff["file"] for diff in diffs]
    blind_edits = [diff["file"] for diff in diffs if diff.get("blind_edit", False)]

    plan_cursor = manager.conn.cursor()
    plan_cursor.execute(
        """
        SELECT description
        FROM plan_tasks
        WHERE plan_id = ?
    """,
        (plan_id,),
    )

    import re

    planned_files = set()
    for row in plan_cursor.fetchall():
        desc = row[0]

        file_matches = re.findall(r"[\w/]+\.(?:py|js|ts|tsx|jsx|md)", desc)
        planned_files.update(file_matches)

    actual_files_set = set(actual_files)
    extra_files = actual_files_set - planned_files
    missing_files = planned_files - actual_files_set

    deviation_score = (len(extra_files) + len(missing_files)) / max(len(planned_files), 1)
    validation_passed = workflow_compliant and len(blind_edits) == 0 and deviation_score < 0.2

    if format == "json":
        result = {
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "session_id": session_id_val,
            "validation_passed": validation_passed,
            "workflow_compliant": bool(workflow_compliant),
            "compliance_score": compliance_score,
            "files": {
                "planned": list(planned_files),
                "actual": actual_files,
                "extra": list(extra_files),
                "missing": list(missing_files),
            },
            "blind_edits": blind_edits,
            "deviation_score": deviation_score,
            "status": "completed" if validation_passed else "needs-revision",
        }
        console.print(json_module.dumps(result, indent=2), markup=False)
    else:
        console.rule()
        console.print(f"Plan Validation Report: {plan['name']}", highlight=False)
        console.rule()
        console.print(f"Plan ID:              {plan_id}", highlight=False)
        console.print(f"Session ID:           {session_id_val[:16]}...", highlight=False)
        console.print(
            f"Validation Status:    {'PASSED' if validation_passed else 'NEEDS REVISION'}",
            highlight=False,
        )
        console.print()
        console.print(f"Planned files:        {len(planned_files)}", highlight=False)
        console.print(
            f"Actually touched:     {len(actual_files)} (+{len(extra_files)} extra, -{len(missing_files)} missing)",
            highlight=False,
        )
        console.print(f"Blind edits:          {len(blind_edits)}", highlight=False)
        console.print(
            f"Workflow compliant:   {'YES' if workflow_compliant else 'NO'}", highlight=False
        )
        console.print(
            f"Compliance score:     {compliance_score:.2f} ({'above' if compliance_score >= 0.8 else 'below'} 0.8 threshold)",
            highlight=False,
        )
        console.print(f"Deviation score:      {deviation_score:.2f}", highlight=False)
        console.print()

        if extra_files:
            console.print("Deviations - Extra files touched:")
            for f in extra_files:
                console.print(f"  + {f}", highlight=False)
            console.print()

        if missing_files:
            console.print("Deviations - Planned files not touched:")
            for f in missing_files:
                console.print(f"  - {f}", highlight=False)
            console.print()

        if blind_edits:
            console.print("Blind edits (edited without reading first):")
            for f in blind_edits:
                console.print(f"  ! {f}", highlight=False)
            console.print()

        console.print(
            f"Status: {'COMPLETED' if validation_passed else 'NEEDS REVISION'}", highlight=False
        )
        console.rule()

    if validation_passed:
        manager.update_task(plan_id, 1, status="completed")
        err_console.print(
            "[error]\nPlan status updated to: completed[/error]",
        )
    else:
        manager.update_task(plan_id, 1, status="needs-revision")
        err_console.print(
            "[error]\nPlan status updated to: needs-revision[/error]",
        )

    session_conn.close()


@planning.command(cls=RichCommand)
@click.option(
    "--target",
    type=click.Choice(["AGENTS.md", "CLAUDE.md", "both"]),
    default="AGENTS.md",
    help="Target file for injection",
)
@handle_exceptions
def setup_agents(target):
    """Inject TheAuditor agent trigger block into project documentation.

    Adds agent trigger instructions to AGENTS.md or CLAUDE.md that tell
    AI assistants when to load specialized agent workflows for planning,
    refactoring, security analysis, and dataflow tracing.

    The trigger block references agent files in .auditor_venv/.theauditor_tools/agents/
    which are copied during venv setup (via venv_install.py).

    Example:
        aud planning setup-agents                      # Inject into AGENTS.md
        aud planning setup-agents --target CLAUDE.md   # Inject into CLAUDE.md
        aud planning setup-agents --target both        # Inject into both files
    """

    def inject_into_file(file_path: Path) -> bool:
        """Inject trigger block into file if not already present."""
        if not file_path.exists():
            file_path.write_text(TRIGGER_BLOCK + "\n")
            console.print(f"Created {file_path.name} with agent trigger block", highlight=False)
            return True

        content = file_path.read_text()

        if TRIGGER_START in content:
            console.print(f"Trigger block already exists in {file_path.name}", highlight=False)
            return False

        new_content = TRIGGER_BLOCK + "\n" + content
        file_path.write_text(new_content)
        console.print(f"Injected agent trigger block into {file_path.name}", highlight=False)
        return True

    root = Path.cwd()

    if target == "AGENTS.md" or target == "both":
        agents_md = root / "AGENTS.md"
        inject_into_file(agents_md)

    if target == "CLAUDE.md" or target == "both":
        claude_md = root / "CLAUDE.md"
        inject_into_file(claude_md)

    console.print("\nAgent trigger setup complete!")
    console.print("AI assistants will now automatically load specialized agent workflows.")
    console.print("\nNext steps:")
    console.print("  1. Run 'aud setup-ai --target . --sync' to install agent files")
    console.print(
        "  2. Try triggering agents with keywords like 'refactor storage.py' or 'check for XSS'"
    )
