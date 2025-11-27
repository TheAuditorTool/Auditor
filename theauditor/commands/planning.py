"""Planning and verification commands for implementation workflows."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import click

from theauditor.planning import snapshots, verification
from theauditor.planning.manager import PlanningManager
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

# Agent trigger block markers for documentation injection
TRIGGER_START = "<!-- THEAUDITOR:START -->"
TRIGGER_END = "<!-- THEAUDITOR:END -->"

# Complete agent trigger block content for documentation injection
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
Run `aud init` to install the venv if agents are missing.

{TRIGGER_END}
"""


@click.group()
@click.help_option("-h", "--help")
def planning():
    """Planning and Verification System - Database-Centric Task Management

    PURPOSE:
      The planning system provides deterministic task tracking with spec-based
      verification. Unlike external tools (Jira, Linear), planning integrates
      directly with TheAuditor's indexed codebase for instant verification.

      Key benefits:
      - Verification specs query actual code (not developer self-assessment)
      - Git snapshots create immutable audit trail
      - Zero external dependencies (offline-first)
      - Works seamlessly with aud index / aud full workflow

    QUICK START:
      # Initialize your first plan
      aud planning init --name "Migration Plan"

      # Add tasks with verification specs
      aud planning add-task 1 --title "Task" --spec spec.yaml

      # Make code changes, then verify
      aud index && aud planning verify-task 1 1 --verbose

    COMMON WORKFLOWS:

      Greenfield Feature Development:
        1. aud planning init --name "New Feature"
        2. aud query --api "/users" --format json  # Find analogous patterns
        3. aud planning add-task 1 --title "Add /products endpoint"
        4. [Implement feature]
        5. aud index && aud planning verify-task 1 1

      Refactoring Migration:
        1. aud planning init --name "Auth0 to Cognito"
        2. aud planning add-task 1 --title "Migrate routes" --spec auth_spec.yaml
        3. [Make changes]
        4. aud index && aud planning verify-task 1 1 --auto-update
        5. aud planning archive 1 --notes "Deployed to prod"

      Checkpoint-Driven Development:
        1. aud planning add-task 1 --title "Complex Refactor"
        2. [Make partial changes]
        3. aud planning verify-task 1 1  # Creates snapshot on failure
        4. [Continue work]
        5. aud planning rewind 1  # Show rollback if needed

    DATABASE STRUCTURE:
      .pf/planning.db (separate from repo_index.db)
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
      - Run 'aud init' to create .pf/ directory
      - Run 'aud index' to build repo_index.db before verify-task
      - Verification queries indexed code (not raw files)

    COMMANDS:
      init         Create new plan (auto-creates planning.db)
      show         Display plan status and task list
      add-task     Add task with optional YAML spec
      update-task  Change task status or assignee
      verify-task  Run spec against indexed code
      archive      Create final snapshot and mark complete
      rewind       Show git commands to rollback

    For detailed help: aud planning <command> --help
    """
    pass


@planning.command()
@click.option("--name", required=True, help="Plan name")
@click.option("--description", default="", help="Plan description")
@handle_exceptions
def init(name, description):
    """Create a new implementation plan.

    Example:
        aud planning init --name "Auth Migration" --description "Migrate to OAuth2"
    """

    db_path = Path.cwd() / ".pf" / "planning.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        manager = PlanningManager.init_database(db_path)
        click.echo(f"Initialized planning database: {db_path}")
    else:
        manager = PlanningManager(db_path)

    plan_id = manager.create_plan(name, description)

    click.echo(f"Created plan {plan_id}: {name}")
    if description:
        click.echo(f"Description: {description}")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
        return

    click.echo("=" * 80)
    click.echo(f"Plan {plan['id']}: {plan['name']}")
    click.echo("=" * 80)
    click.echo(f"Status: {plan['status']}")
    click.echo(f"Created: {plan['created_at']}")
    if plan["description"]:
        click.echo(f"Description: {plan['description']}")
    click.echo(f"Database: {db_path}")

    if verbose and plan["metadata_json"]:
        metadata = json.loads(plan["metadata_json"])
        click.echo("\nMetadata:")
        for key, value in metadata.items():
            click.echo(f"  {key}: {value}")

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
                click.echo("\nPhase → Task → Job Hierarchy:")
                for phase in phases:
                    phase_id, phase_num, phase_title, phase_desc, success_criteria, phase_status = (
                        phase
                    )
                    status_icon = "[X]" if phase_status == "completed" else "[ ]"
                    click.echo(f"\n{status_icon} PHASE {phase_num}: {phase_title}")
                    if success_criteria:
                        click.echo(f"    Success Criteria: {success_criteria}")
                    if verbose and phase_desc:
                        click.echo(f"    Description: {phase_desc}")

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
                        click.echo(f"  {task_icon} Task {task_num}: {task_title}{audit_label}")
                        if verbose and task_desc:
                            click.echo(f"      Description: {task_desc}")

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
                            click.echo(f"    {job_icon} Job {job_num}: {job_desc}{audit_marker}")

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
                    click.echo("\nOrphaned Tasks (not in any phase):")
                    for task in orphaned_tasks:
                        task_id, task_num, task_title, task_status, audit_status = task
                        task_icon = "[X]" if task_status == "completed" else "[ ]"
                        audit_label = (
                            f" (audit: {audit_status})" if audit_status != "pending" else ""
                        )
                        click.echo(f"  {task_icon} Task {task_num}: {task_title}{audit_label}")
            else:
                click.echo(
                    "\nNo phases defined. Use --format flat or add phases with 'aud planning add-phase'"
                )

        else:
            task_list = manager.list_tasks(plan_id)
            click.echo(f"\nTasks ({len(task_list)}):")
            for task in task_list:
                status_icon = "[X]" if task["status"] == "completed" else "[ ]"
                click.echo(f"  {status_icon} Task {task['task_number']}: {task['title']}")
                click.echo(f"    Status: {task['status']}")
                if task["assigned_to"]:
                    click.echo(f"    Assigned: {task['assigned_to']}")
                if verbose and task["description"]:
                    click.echo(f"    Description: {task['description']}")

    click.echo("\n" + "=" * 80)
    click.echo("Commands:")
    click.echo(
        '  aud planning add-phase {plan_id} --phase-number N --title "..." --description "..."'
    )
    click.echo('  aud planning add-task {plan_id} --title "..." --description "..." --phase N')
    click.echo('  aud planning add-job {plan_id} <task_number> --description "..."')
    click.echo("  aud planning update-task {plan_id} <task_number> --status completed")
    click.echo("  aud planning verify-task {plan_id} <task_number> --pass")
    click.echo("  aud planning validate {plan_id}  # Validate against session logs")
    click.echo("\nFiles:")
    click.echo(f"  Database: {db_path}")
    click.echo("  Agent prompts: agents/planning.md, agents/refactor.md, etc.")
    click.echo("=" * 80)


@planning.command("list")
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
    db_path = Path.cwd() / ".pf" / "planning.db"

    if not db_path.exists():
        click.echo("No planning database found (.pf/planning.db)")
        click.echo("Run 'aud planning init --name \"Plan Name\"' to create your first plan")
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
            click.echo(f"No {status} plans found")
        else:
            click.echo("No plans found")
        return

    if format == "json":
        result = [{"id": p[0], "name": p[1], "status": p[2], "created_at": p[3]} for p in plans]
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("=" * 80)
        click.echo(f"{'ID':<5} {'Name':<40} {'Status':<15} {'Created':<20}")
        click.echo("=" * 80)
        for plan in plans:
            pid, name, pstatus, created = plan
            click.echo(f"{pid:<5} {name[:40]:<40} {pstatus:<15} {created:<20}")
        click.echo("=" * 80)
        click.echo(f"Total: {len(plans)} plans")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
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

    click.echo(f"Added phase {phase_number} to plan {plan_id}: {title}")
    if success_criteria:
        click.echo(f"Success Criteria: {success_criteria}")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
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
            click.echo(f"Warning: Phase {phase} not found in plan {plan_id}", err=True)
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
    click.echo(f"Added task {task_number} to plan {plan_id}: {title}")
    if phase is not None:
        click.echo(f"Associated with phase {phase}")
    if spec:
        click.echo(f"Verification spec: {spec}")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
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
    click.echo(f"Added {job_type} {job_number} to task {task_number}: {description}")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    if status:
        manager.update_task_status(task_id, status)
        click.echo(f"Updated task {task_number} status: {status}")

    if assigned_to:
        manager.update_task_assignee(task_id, assigned_to)
        click.echo(f"Reassigned task {task_number} to: {assigned_to}")


@planning.command()
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed violations")
@click.option("--auto-update", is_flag=True, help="Auto-update task status based on result")
@handle_exceptions
def verify_task(plan_id, task_number, verbose, auto_update):
    """Verify task completion against its spec.

    Runs verification spec against current codebase and reports violations.
    Optionally updates task status based on verification result.

    Example:
        aud planning verify-task 1 1 --verbose
        aud planning verify-task 1 1 --auto-update
    """
    db_path = Path.cwd() / ".pf" / "planning.db"
    repo_index_db = Path.cwd() / ".pf" / "repo_index.db"

    if not repo_index_db.exists():
        click.echo("Error: repo_index.db not found. Run 'aud full' first.", err=True)
        return

    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    cursor = manager.conn.cursor()
    cursor.execute("SELECT status, completed_at FROM plan_tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    was_previously_completed = task_row and task_row[0] == "completed" and task_row[1] is not None

    spec_yaml = manager.load_task_spec(task_id)
    if not spec_yaml:
        click.echo(f"Error: No verification spec for task {task_number}", err=True)
        return

    click.echo(f"Verifying task {task_number}...")

    try:
        result = verification.verify_task_spec(spec_yaml, repo_index_db, Path.cwd())

        total_violations = result.total_violations()

        is_regression = was_previously_completed and total_violations > 0

        click.echo("\nVerification complete:")
        click.echo(f"  Total violations: {total_violations}")

        if is_regression:
            click.echo("\n  WARNING: REGRESSION DETECTED", err=True)
            click.echo(
                f"  Task {task_number} was previously completed but now has {total_violations} violation(s)",
                err=True,
            )
            click.echo("  Code changes since completion have broken verification", err=True)

        if verbose and total_violations > 0:
            click.echo("\nViolations by rule:")
            for rule_result in result.rule_results:
                if rule_result.violations:
                    click.echo(f"  {rule_result.rule.id}: {len(rule_result.violations)} violations")
                    for violation in rule_result.violations[:5]:
                        click.echo(f"    - {violation['file']}:{violation.get('line', '?')}")
                    if len(rule_result.violations) > 5:
                        click.echo(f"    ... and {len(rule_result.violations) - 5} more")

        cursor = manager.conn.cursor()
        if total_violations == 0:
            audit_status = "pass"
        else:
            audit_status = "fail"

        cursor.execute(
            "UPDATE plan_tasks SET audit_status = ? WHERE id = ?", (audit_status, task_id)
        )
        manager.conn.commit()

        click.echo(f"\nAudit status: {audit_status}")

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
            click.echo(f"Task status updated: {new_status}")

        if total_violations > 0:
            snapshot = snapshots.create_snapshot(
                plan_id=plan_id,
                checkpoint_name=f"verify-task-{task_number}-failed",
                repo_root=Path.cwd(),
                task_id=task_id,
                manager=manager,
            )
            click.echo(f"Snapshot created: {snapshot['git_ref'][:8]}")
            if snapshot.get("sequence"):
                click.echo(f"Sequence: {snapshot['sequence']}")

    except ValueError as e:
        click.echo(f"Error: Invalid verification spec: {e}", err=True)
    except Exception as e:
        click.echo(f"Error during verification: {e}", err=True)
        raise


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
        return

    all_tasks = manager.list_tasks(plan_id)
    incomplete_tasks = [t for t in all_tasks if t["status"] != "completed"]

    if incomplete_tasks:
        click.echo(f"Warning: Plan has {len(incomplete_tasks)} incomplete task(s):", err=True)
        for task in incomplete_tasks[:5]:
            click.echo(
                f"  - Task {task['task_number']}: {task['title']} (status: {task['status']})",
                err=True,
            )
        if len(incomplete_tasks) > 5:
            click.echo(f"  ... and {len(incomplete_tasks) - 5} more", err=True)

        if not click.confirm("\nArchive plan anyway?"):
            click.echo("Archive cancelled.")
            return

    click.echo("Creating final snapshot...")
    snapshot = snapshots.create_snapshot(
        plan_id=plan_id, checkpoint_name="archive", repo_root=Path.cwd(), manager=manager
    )

    from datetime import UTC

    metadata = json.loads(plan["metadata_json"]) if plan["metadata_json"] else {}
    metadata["archived_at"] = datetime.now(UTC).isoformat()
    metadata["final_snapshot_id"] = snapshot.get("snapshot_id")
    if notes:
        metadata["archive_notes"] = notes

    manager.update_plan_status(plan_id, "archived", json.dumps(metadata))

    click.echo(f"\nPlan {plan_id} archived successfully")
    click.echo(f"Final snapshot: {snapshot['git_ref'][:8]}")
    click.echo(f"Files affected: {len(snapshot['files_affected'])}")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
        return

    cursor = manager.conn.cursor()

    if task_number is not None:
        task_id = manager.get_task_id(plan_id, task_number)
        if not task_id:
            click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
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
                click.echo(f"Error: No checkpoints found up to sequence {to_sequence}", err=True)
                return

            click.echo(f"Granular rewind to sequence {to_sequence} for task {task_number}")
            click.echo(f"This will apply {len(snapshots_to_apply)} checkpoint(s):")
            click.echo()

            for snapshot_row in snapshots_to_apply:
                snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row
                click.echo(f"  [{seq}] {checkpoint_name} ({git_ref[:8]})")

            click.echo()
            click.echo("WARNING: This requires applying diffs incrementally.")
            click.echo("Current implementation shows git checkout only.")
            click.echo()

            target_snapshot = snapshots_to_apply[-1]
            click.echo(f"To rewind to sequence {to_sequence}, run:")
            click.echo(f"  git checkout {target_snapshot[4]}")
            click.echo()
            click.echo("NOTE: Full incremental diff application not yet implemented.")
            click.echo("This will revert to the git state at checkpoint {target_snapshot[1]}")

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
                click.echo(f"No checkpoints found for task {task_number}")
                return

            click.echo(f"Checkpoints for task {task_number}:\n")
            for snapshot_row in task_snapshots:
                snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row
                click.echo(f"  [{seq}] {checkpoint_name}")
                click.echo(f"      Git ref: {git_ref[:8]}")
                click.echo(f"      Timestamp: {timestamp}")
                click.echo()

            click.echo("To rewind to a specific sequence:")
            click.echo(f"  aud planning rewind {plan_id} {task_number} --to N")

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
                click.echo(f"Error: Checkpoint '{checkpoint}' not found", err=True)
                return

            click.echo(f"Rewind to checkpoint: {snapshot_row[1]}")
            click.echo(f"Timestamp: {snapshot_row[2]}")
            click.echo(f"Git ref: {snapshot_row[3]}")
            click.echo("\nTo revert to this state, run:")
            click.echo(f"  git checkout {snapshot_row[3]}")
            click.echo("\nOr to create a new branch from this state:")
            click.echo(f"  git checkout -b rewind-{snapshot_row[1]} {snapshot_row[3]}")
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
                click.echo(f"No plan-level snapshots found for plan {plan_id}")
                click.echo(
                    "(Task-level checkpoints exist - use: aud planning rewind <plan_id> <task_number>)"
                )
                return

            click.echo(f"Plan-level snapshots for plan {plan_id} ({plan['name']}):\n")
            for snapshot in snapshots_list:
                click.echo(f"  {snapshot[1]}")
                click.echo(f"    Timestamp: {snapshot[2]}")
                click.echo(f"    Git ref: {snapshot[3][:8]}")
                click.echo()

            click.echo("To rewind to a specific checkpoint:")
            click.echo(f"  aud planning rewind {plan_id} --checkpoint <name>")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    if not name:
        cursor = manager.conn.cursor()
        cursor.execute("SELECT MAX(sequence) FROM code_snapshots WHERE task_id = ?", (task_id,))
        max_seq = cursor.fetchone()[0]
        next_seq = (max_seq or 0) + 1
        name = f"edit_{next_seq}"

    click.echo(f"Creating checkpoint '{name}' for task {task_number}...")
    snapshot = snapshots.create_snapshot(
        plan_id=plan_id,
        checkpoint_name=name,
        repo_root=Path.cwd(),
        task_id=task_id,
        manager=manager,
    )

    click.echo(f"Checkpoint created: {snapshot['git_ref'][:8]}")
    if snapshot.get("sequence"):
        click.echo(f"Sequence: {snapshot['sequence']}")
    click.echo(f"Files affected: {len(snapshot['files_affected'])}")
    if snapshot["files_affected"]:
        for f in snapshot["files_affected"][:5]:
            click.echo(f"  - {f}")
        if len(snapshot["files_affected"]) > 5:
            click.echo(f"  ... and {len(snapshot['files_affected']) - 5} more")


@planning.command()
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
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
            click.echo(f"Error: No checkpoint with sequence {sequence} found", err=True)
            return

        snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

        click.echo(f"Checkpoint: {checkpoint_name} (sequence {seq})")
        click.echo(f"Timestamp: {timestamp}")
        click.echo(f"Git ref: {git_ref[:8]}")
        click.echo()

        query = "SELECT file_path, diff_text, added_lines, removed_lines FROM code_diffs WHERE snapshot_id = ?"
        params = [snapshot_id]

        if file:
            query += " AND file_path LIKE ?"
            params.append(f"%{file}%")

        cursor.execute(query, params)
        diffs = cursor.fetchall()

        if not diffs:
            click.echo("No diffs found")
            return

        for diff_row in diffs:
            file_path, diff_text, added, removed = diff_row
            click.echo(f"File: {file_path} (+{added}/-{removed})")
            click.echo("=" * 80)
            click.echo(diff_text)
            click.echo()

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
            click.echo(f"No checkpoints found for task {task_number}")
            return

        click.echo(f"Checkpoints for task {task_number}:\n")

        for snapshot_row in snapshots_list:
            snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

            cursor.execute(
                "SELECT COUNT(DISTINCT file_path) FROM code_diffs WHERE snapshot_id = ?",
                (snapshot_id,),
            )
            file_count = cursor.fetchone()[0]

            click.echo(f"  [{seq}] {checkpoint_name}")
            click.echo(f"      Timestamp: {timestamp}")
            click.echo(f"      Git ref: {git_ref[:8]}")
            click.echo(f"      Files: {file_count}")
            click.echo()

        click.echo("To view a specific checkpoint's diff:")
        click.echo(f"  aud planning show-diff {plan_id} {task_number} --sequence N")


@planning.command("validate")
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
    db_path = Path.cwd() / ".pf" / "planning.db"
    session_db_path = Path.cwd() / ".pf" / "ml" / "session_history.db"

    if not session_db_path.exists():
        click.echo("Error: Session database not found (.pf/ml/session_history.db)", err=True)
        click.echo("Run 'aud session init' to enable session logging", err=True)
        click.echo("Planning validation requires session logs", err=True)
        raise click.ClickException("Session logging not enabled")

    manager = PlanningManager(db_path)
    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
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
        click.echo(f"Error: No session found for plan '{plan['name']}'", err=True)
        if session_id:
            click.echo(f"Session ID '{session_id}' not found in database", err=True)
        raise click.ClickException("No matching session found")

    (
        session_id_val,
        task_desc,
        workflow_compliant,
        compliance_score,
        files_modified_count,
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
        click.echo(json_module.dumps(result, indent=2))
    else:
        click.echo("=" * 80)
        click.echo(f"Plan Validation Report: {plan['name']}")
        click.echo("=" * 80)
        click.echo(f"Plan ID:              {plan_id}")
        click.echo(f"Session ID:           {session_id_val[:16]}...")
        click.echo(f"Validation Status:    {'PASSED' if validation_passed else 'NEEDS REVISION'}")
        click.echo()
        click.echo(f"Planned files:        {len(planned_files)}")
        click.echo(
            f"Actually touched:     {len(actual_files)} (+{len(extra_files)} extra, -{len(missing_files)} missing)"
        )
        click.echo(f"Blind edits:          {len(blind_edits)}")
        click.echo(f"Workflow compliant:   {'YES' if workflow_compliant else 'NO'}")
        click.echo(
            f"Compliance score:     {compliance_score:.2f} ({'above' if compliance_score >= 0.8 else 'below'} 0.8 threshold)"
        )
        click.echo(f"Deviation score:      {deviation_score:.2f}")
        click.echo()

        if extra_files:
            click.echo("Deviations - Extra files touched:")
            for f in extra_files:
                click.echo(f"  + {f}")
            click.echo()

        if missing_files:
            click.echo("Deviations - Planned files not touched:")
            for f in missing_files:
                click.echo(f"  - {f}")
            click.echo()

        if blind_edits:
            click.echo("Blind edits (edited without reading first):")
            for f in blind_edits:
                click.echo(f"  ! {f}")
            click.echo()

        click.echo(f"Status: {'COMPLETED' if validation_passed else 'NEEDS REVISION'}")
        click.echo("=" * 80)

    if validation_passed:
        manager.update_task(plan_id, 1, status="completed")
        click.echo("\nPlan status updated to: completed", err=True)
    else:
        manager.update_task(plan_id, 1, status="needs-revision")
        click.echo("\nPlan status updated to: needs-revision", err=True)

    session_conn.close()


@planning.command()
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
            click.echo(f"Created {file_path.name} with agent trigger block")
            return True

        content = file_path.read_text()

        if TRIGGER_START in content:
            click.echo(f"Trigger block already exists in {file_path.name}")
            return False

        new_content = TRIGGER_BLOCK + "\n" + content
        file_path.write_text(new_content)
        click.echo(f"Injected agent trigger block into {file_path.name}")
        return True

    root = Path.cwd()

    if target == "AGENTS.md" or target == "both":
        agents_md = root / "AGENTS.md"
        inject_into_file(agents_md)

    if target == "CLAUDE.md" or target == "both":
        claude_md = root / "CLAUDE.md"
        inject_into_file(claude_md)

    click.echo("\nAgent trigger setup complete!")
    click.echo("AI assistants will now automatically load specialized agent workflows.")
    click.echo("\nNext steps:")
    click.echo("  1. Run 'aud init' if .auditor_venv/ doesn't exist (copies agent files)")
    click.echo(
        "  2. Try triggering agents with keywords like 'refactor storage.py' or 'check for XSS'"
    )
