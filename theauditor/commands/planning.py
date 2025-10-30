"""Planning and verification commands for implementation workflows."""

import click
import json
from pathlib import Path
from datetime import datetime
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

    # Load task spec
    task_id = manager.get_task_id(plan_id, task_number)
    if not task_id:
        click.echo(f"Error: Task {task_number} not found in plan {plan_id}", err=True)
        return

    spec_yaml = manager.load_task_spec(task_id)
    if not spec_yaml:
        click.echo(f"Error: No verification spec for task {task_number}", err=True)
        return

    click.echo(f"Verifying task {task_number}...")

    # Run verification
    try:
        result = verification.verify_task_spec(spec_yaml, repo_index_db, Path.cwd())

        total_violations = result.total_violations()
        click.echo(f"\nVerification complete:")
        click.echo(f"  Total violations: {total_violations}")

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
            new_status = 'completed' if total_violations == 0 else 'in_progress'
            manager.update_task_status(task_id, new_status)
            click.echo(f"\nTask status updated: {new_status}")

        # Create snapshot if violations found
        if total_violations > 0:
            snapshot = snapshots.create_snapshot(
                plan_id=plan_id,
                checkpoint_name=f"verify-task-{task_number}-failed",
                repo_root=Path.cwd(),
                manager=manager
            )
            click.echo(f"Snapshot created: {snapshot['git_ref'][:8]}")

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
@click.option('--checkpoint', help='Specific checkpoint name to rewind to')
@handle_exceptions
def rewind(plan_id, checkpoint):
    """Show rollback instructions for a plan.

    Displays git commands to revert to a previous snapshot state.
    Does NOT execute the commands - only shows them for manual review.

    Example:
        aud planning rewind 1
        aud planning rewind 1 --checkpoint "pre-migration"
    """
    db_path = Path.cwd() / ".pf" / "planning.db"
    manager = PlanningManager(db_path)

    plan = manager.get_plan(plan_id)
    if not plan:
        click.echo(f"Error: Plan {plan_id} not found", err=True)
        return

    # Get snapshots for this plan
    cursor = manager.conn.cursor()
    if checkpoint:
        cursor.execute("""
            SELECT id, checkpoint_name, timestamp, git_ref
            FROM code_snapshots
            WHERE plan_id = ? AND checkpoint_name = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (plan_id, checkpoint))
    else:
        cursor.execute("""
            SELECT id, checkpoint_name, timestamp, git_ref
            FROM code_snapshots
            WHERE plan_id = ?
            ORDER BY timestamp DESC
        """, (plan_id,))

    snapshots_list = cursor.fetchall()

    if not snapshots_list:
        click.echo(f"No snapshots found for plan {plan_id}", err=True)
        return

    if checkpoint:
        # Show rewind commands for specific checkpoint
        snapshot = snapshots_list[0]
        click.echo(f"Rewind to checkpoint: {snapshot[1]}")
        click.echo(f"Timestamp: {snapshot[2]}")
        click.echo(f"Git ref: {snapshot[3]}")
        click.echo(f"\nTo revert to this state, run:")
        click.echo(f"  git checkout {snapshot[3]}")
        click.echo(f"\nOr to create a new branch from this state:")
        click.echo(f"  git checkout -b rewind-{snapshot[1]} {snapshot[3]}")
    else:
        # List all snapshots
        click.echo(f"Snapshots for plan {plan_id} ({plan['name']}):\n")
        for snapshot in snapshots_list:
            click.echo(f"  {snapshot[1]}")
            click.echo(f"    Timestamp: {snapshot[2]}")
            click.echo(f"    Git ref: {snapshot[3][:8]}")
            click.echo()

        if snapshots_list:
            click.echo("To rewind to a specific checkpoint:")
            click.echo(f"  aud planning rewind {plan_id} --checkpoint <name>")
