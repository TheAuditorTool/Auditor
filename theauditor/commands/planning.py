"""Planning and verification commands for implementation workflows."""

import click
import json
from pathlib import Path
from datetime import datetime, UTC
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.logger import setup_logger
from theauditor.planning.manager import PlanningManager
from theauditor.planning import verification, snapshots

logger = setup_logger(__name__)


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
@click.option('--name', required=True, help='Plan name')
@click.option('--description', default='', help='Plan description')
@handle_exceptions
def init(name, description):
    """Create a new implementation plan.

    Example:
        aud planning init --name "Auth Migration" --description "Migrate to OAuth2"
    """
    # Get or create planning database
    db_path = Path.cwd() / ".pf" / "planning.db"

    # Ensure .pf directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize database if it doesn't exist
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
@click.argument('plan_id', type=int)
@click.option('--tasks', is_flag=True, help='Show task list')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@handle_exceptions
def show(plan_id, tasks, verbose):
    """Display plan details and task status.

    Example:
        aud planning show 1 --tasks
        aud planning show 1 --verbose
    """
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
        return

    click.echo(f"Plan {plan['id']}: {plan['name']}")
    click.echo(f"Status: {plan['status']}")
    click.echo(f"Created: {plan['created_at']}")
    if plan['description']:
        click.echo(f"Description: {plan['description']}")

    if verbose and plan['metadata_json']:
        metadata = json.loads(plan['metadata_json'])
        click.echo(f"\nMetadata:")
        for key, value in metadata.items():
            click.echo(f"  {key}: {value}")

    if tasks:
        task_list = manager.list_tasks(plan_id)
        click.echo(f"\nTasks ({len(task_list)}):")
        for task in task_list:
            status_icon = "[X]" if task['status'] == 'completed' else "[ ]"
            click.echo(f"  {status_icon} Task {task['task_number']}: {task['title']}")
            click.echo(f"    Status: {task['status']}")
            if task['assigned_to']:
                click.echo(f"    Assigned: {task['assigned_to']}")
            if verbose and task['description']:
                click.echo(f"    Description: {task['description']}")


@planning.command()
@click.argument('plan_id', type=int)
@click.option('--title', required=True, help='Task title')
@click.option('--description', default='', help='Task description')
@click.option('--spec', type=click.Path(exists=True), help='YAML verification spec file')
@click.option('--assigned-to', help='Assignee name')
@handle_exceptions
def add_task(plan_id, title, description, spec, assigned_to):
    """Add a task to a plan with optional verification spec.

    Example:
        aud planning add-task 1 --title "Migrate auth" --spec auth_spec.yaml
    """
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    # Load spec YAML if provided
    spec_yaml = None
    if spec:
        spec_path = Path(spec)
        spec_yaml = spec_path.read_text()

    task_id = manager.add_task(
        plan_id=plan_id,
        title=title,
        description=description,
        spec_yaml=spec_yaml,
        assigned_to=assigned_to
    )

    task_number = manager.get_task_number(task_id)
    click.echo(f"Added task {task_number} to plan {plan_id}: {title}")
    if spec:
        click.echo(f"Verification spec: {spec}")


@planning.command()
@click.argument('plan_id', type=int)
@click.argument('task_number', type=int)
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'blocked']), help='New status')
@click.option('--assigned-to', help='Reassign task')
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
@click.argument('plan_id', type=int)
@click.argument('task_number', type=int)
@click.option('--verbose', '-v', is_flag=True, help='Show detailed violations')
@click.option('--auto-update', is_flag=True, help='Auto-update task status based on result')
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
        click.echo("Error: repo_index.db not found. Run 'aud index' first.", err=True)
        return

    manager = PlanningManager(db_path)

    # Load task spec and current status
    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    # Get current task to check for regression
    cursor = manager.conn.cursor()
    cursor.execute("SELECT status, completed_at FROM plan_tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    was_previously_completed = task_row and task_row[0] == 'completed' and task_row[1] is not None

    spec_yaml = manager.load_task_spec(task_id)
    if not spec_yaml:
        click.echo(f"Error: No verification spec for task {task_number}", err=True)
        return

    click.echo(f"Verifying task {task_number}...")

    # Run verification
    try:
        result = verification.verify_task_spec(spec_yaml, repo_index_db, Path.cwd())

        total_violations = result.total_violations()

        # Detect regression (was completed, now has violations)
        is_regression = was_previously_completed and total_violations > 0

        click.echo(f"\nVerification complete:")
        click.echo(f"  Total violations: {total_violations}")

        if is_regression:
            click.echo(f"\n  WARNING: REGRESSION DETECTED", err=True)
            click.echo(f"  Task {task_number} was previously completed but now has {total_violations} violation(s)", err=True)
            click.echo(f"  Code changes since completion have broken verification", err=True)

        if verbose and total_violations > 0:
            click.echo(f"\nViolations by rule:")
            for rule_result in result.rule_results:
                if rule_result.violations:
                    click.echo(f"  {rule_result.rule.id}: {len(rule_result.violations)} violations")
                    for violation in rule_result.violations[:5]:  # Show first 5
                        click.echo(f"    - {violation['file']}:{violation.get('line', '?')}")
                    if len(rule_result.violations) > 5:
                        click.echo(f"    ... and {len(rule_result.violations) - 5} more")

        # Auto-update task status
        if auto_update:
            if total_violations == 0:
                new_status = 'completed'
                manager.update_task_status(task_id, new_status, datetime.now(UTC).isoformat())
            elif is_regression:
                new_status = 'failed'  # Regression = failed status
                manager.update_task_status(task_id, new_status, None)  # Clear completed_at
            else:
                new_status = 'in_progress'
                manager.update_task_status(task_id, new_status, None)
            click.echo(f"\nTask status updated: {new_status}")

        # Create snapshot if violations found
        if total_violations > 0:
            snapshot = snapshots.create_snapshot(
                plan_id=plan_id,
                checkpoint_name=f"verify-task-{task_number}-failed",
                repo_root=Path.cwd(),
                task_id=task_id,
                manager=manager
            )
            click.echo(f"Snapshot created: {snapshot['git_ref'][:8]}")
            if snapshot.get('sequence'):
                click.echo(f"Sequence: {snapshot['sequence']}")

    except ValueError as e:
        click.echo(f"Error: Invalid verification spec: {e}", err=True)
    except Exception as e:
        click.echo(f"Error during verification: {e}", err=True)
        raise


@planning.command()
@click.argument('plan_id', type=int)
@click.option('--notes', help='Archive notes')
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

    # Check for incomplete tasks
    all_tasks = manager.list_tasks(plan_id)
    incomplete_tasks = [t for t in all_tasks if t['status'] != 'completed']

    if incomplete_tasks:
        click.echo(f"Warning: Plan has {len(incomplete_tasks)} incomplete task(s):", err=True)
        for task in incomplete_tasks[:5]:  # Show first 5
            click.echo(f"  - Task {task['task_number']}: {task['title']} (status: {task['status']})", err=True)
        if len(incomplete_tasks) > 5:
            click.echo(f"  ... and {len(incomplete_tasks) - 5} more", err=True)

        if not click.confirm("\nArchive plan anyway?"):
            click.echo("Archive cancelled.")
            return

    # Create final snapshot
    click.echo("Creating final snapshot...")
    snapshot = snapshots.create_snapshot(
        plan_id=plan_id,
        checkpoint_name="archive",
        repo_root=Path.cwd(),
        manager=manager
    )

    # Update plan status and metadata
    from datetime import UTC
    metadata = json.loads(plan['metadata_json']) if plan['metadata_json'] else {}
    metadata['archived_at'] = datetime.now(UTC).isoformat()
    metadata['final_snapshot_id'] = snapshot.get('snapshot_id')
    if notes:
        metadata['archive_notes'] = notes

    manager.update_plan_status(plan_id, 'archived', json.dumps(metadata))

    click.echo(f"\nPlan {plan_id} archived successfully")
    click.echo(f"Final snapshot: {snapshot['git_ref'][:8]}")
    click.echo(f"Files affected: {len(snapshot['files_affected'])}")


@planning.command()
@click.argument('plan_id', type=int)
@click.argument('task_number', type=int, required=False)
@click.option('--checkpoint', help='Specific checkpoint name to rewind to')
@click.option('--to', 'to_sequence', type=int, help='Rewind to specific sequence number (e.g., --to 2 for edit_2)')
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

    # Task-level granular rewind
    if task_number is not None:
        task_id = manager.get_task_id(plan_id, task_number)
        if not task_id:
            click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
            return

        if to_sequence:
            # Granular rewind to specific sequence
            cursor.execute("""
                SELECT id, checkpoint_name, sequence, timestamp, git_ref
                FROM code_snapshots
                WHERE task_id = ? AND sequence <= ?
                ORDER BY sequence
            """, (task_id, to_sequence))

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

            # For now, show the git ref of the target sequence
            target_snapshot = snapshots_to_apply[-1]
            click.echo(f"To rewind to sequence {to_sequence}, run:")
            click.echo(f"  git checkout {target_snapshot[4]}")
            click.echo()
            click.echo("NOTE: Full incremental diff application not yet implemented.")
            click.echo("This will revert to the git state at checkpoint {target_snapshot[1]}")

        else:
            # List task checkpoints
            cursor.execute("""
                SELECT id, checkpoint_name, sequence, timestamp, git_ref
                FROM code_snapshots
                WHERE task_id = ?
                ORDER BY sequence
            """, (task_id,))

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

    # Plan-level rewind (original behavior)
    else:
        if checkpoint:
            cursor.execute("""
                SELECT id, checkpoint_name, timestamp, git_ref
                FROM code_snapshots
                WHERE plan_id = ? AND checkpoint_name = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (plan_id, checkpoint))

            snapshot_row = cursor.fetchone()
            if not snapshot_row:
                click.echo(f"Error: Checkpoint '{checkpoint}' not found", err=True)
                return

            click.echo(f"Rewind to checkpoint: {snapshot_row[1]}")
            click.echo(f"Timestamp: {snapshot_row[2]}")
            click.echo(f"Git ref: {snapshot_row[3]}")
            click.echo(f"\nTo revert to this state, run:")
            click.echo(f"  git checkout {snapshot_row[3]}")
            click.echo(f"\nOr to create a new branch from this state:")
            click.echo(f"  git checkout -b rewind-{snapshot_row[1]} {snapshot_row[3]}")
        else:
            cursor.execute("""
                SELECT id, checkpoint_name, timestamp, git_ref
                FROM code_snapshots
                WHERE plan_id = ? AND task_id IS NULL
                ORDER BY timestamp DESC
            """, (plan_id,))

            snapshots_list = cursor.fetchall()

            if not snapshots_list:
                click.echo(f"No plan-level snapshots found for plan {plan_id}")
                click.echo("(Task-level checkpoints exist - use: aud planning rewind <plan_id> <task_number>)")
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
@click.argument('plan_id', type=int)
@click.argument('task_number', type=int)
@click.option('--name', help='Checkpoint name (optional, auto-generates if not provided)')
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

    # Get task_id
    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    # Auto-generate checkpoint name if not provided
    if not name:
        # Get current sequence number
        cursor = manager.conn.cursor()
        cursor.execute("SELECT MAX(sequence) FROM code_snapshots WHERE task_id = ?", (task_id,))
        max_seq = cursor.fetchone()[0]
        next_seq = (max_seq or 0) + 1
        name = f"edit_{next_seq}"

    # Create snapshot
    click.echo(f"Creating checkpoint '{name}' for task {task_number}...")
    snapshot = snapshots.create_snapshot(
        plan_id=plan_id,
        checkpoint_name=name,
        repo_root=Path.cwd(),
        task_id=task_id,
        manager=manager
    )

    click.echo(f"Checkpoint created: {snapshot['git_ref'][:8]}")
    if snapshot.get('sequence'):
        click.echo(f"Sequence: {snapshot['sequence']}")
    click.echo(f"Files affected: {len(snapshot['files_affected'])}")
    if snapshot['files_affected']:
        for f in snapshot['files_affected'][:5]:
            click.echo(f"  - {f}")
        if len(snapshot['files_affected']) > 5:
            click.echo(f"  ... and {len(snapshot['files_affected']) - 5} more")


@planning.command()
@click.argument('plan_id', type=int)
@click.argument('task_number', type=int)
@click.option('--sequence', type=int, help='Show specific checkpoint by sequence number')
@click.option('--file', help='Show diff for specific file only')
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

    # Get task_id
    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    cursor = manager.conn.cursor()

    if sequence:
        # Show specific checkpoint diff
        cursor.execute("""
            SELECT id, checkpoint_name, sequence, timestamp, git_ref
            FROM code_snapshots
            WHERE task_id = ? AND sequence = ?
        """, (task_id, sequence))

        snapshot_row = cursor.fetchone()
        if not snapshot_row:
            click.echo(f"Error: No checkpoint with sequence {sequence} found", err=True)
            return

        snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

        click.echo(f"Checkpoint: {checkpoint_name} (sequence {seq})")
        click.echo(f"Timestamp: {timestamp}")
        click.echo(f"Git ref: {git_ref[:8]}")
        click.echo()

        # Load diffs
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
        # List all checkpoints for task
        cursor.execute("""
            SELECT id, checkpoint_name, sequence, timestamp, git_ref
            FROM code_snapshots
            WHERE task_id = ?
            ORDER BY sequence
        """, (task_id,))

        snapshots_list = cursor.fetchall()

        if not snapshots_list:
            click.echo(f"No checkpoints found for task {task_number}")
            return

        click.echo(f"Checkpoints for task {task_number}:\n")

        for snapshot_row in snapshots_list:
            snapshot_id, checkpoint_name, seq, timestamp, git_ref = snapshot_row

            # Count files affected
            cursor.execute("SELECT COUNT(DISTINCT file_path) FROM code_diffs WHERE snapshot_id = ?", (snapshot_id,))
            file_count = cursor.fetchone()[0]

            click.echo(f"  [{seq}] {checkpoint_name}")
            click.echo(f"      Timestamp: {timestamp}")
            click.echo(f"      Git ref: {git_ref[:8]}")
            click.echo(f"      Files: {file_count}")
            click.echo()

        click.echo("To view a specific checkpoint's diff:")
        click.echo(f"  aud planning show-diff {plan_id} {task_number} --sequence N")
