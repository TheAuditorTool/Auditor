# Design: Planning System Architecture

## Overview

The planning system adds database-centric plan management and verification to TheAuditor by **reusing existing infrastructure** (RefactorRuleEngine, CodeQueryEngine, DatabaseManager patterns) and adding a separate planning database with CLI commands.

**Design Principles**:
1. **Zero Fallback Policy**: Hard fail if planning.db or spec YAML is malformed (CLAUDE.md)
2. **Schema-Driven**: Use TableSchema registry pattern (schema.py)
3. **Separation of Concerns**: planning.db for plan data, repo_index.db for code data
4. **Existing Infrastructure**: Leverage RefactorRuleEngine and CodeQueryEngine as-is

## Database Architecture

### planning.db Schema

Location: `.pf/planning.db` (separate from `.pf/repo_index.db`)

**Rationale for Separate Database**:
- Planning data is conceptually distinct from code metadata
- repo_index.db regenerated on `aud index`, planning data persists across re-indexes
- Follows existing pattern: repo_index.db (91 MB), graphs.db (79 MB), planning.db (~5 MB)

**Table Definitions** (added to `theauditor/indexer/schema.py`):

```python
# theauditor/indexer/schema.py (additions)

@table("plans")
def _(t: T):
    """Top-level plan metadata.

    Plans contain multiple tasks and specs. Status values:
    - 'active': Currently being worked on
    - 'completed': All tasks verified
    - 'archived': Immutable historical record
    """
    t.int_pk()  # id
    t.text("name", nullable=False)
    t.text("description")
    t.timestamp("created_at")
    t.text("status")  # active | completed | archived
    t.json("metadata_json")  # Flexible metadata storage

    t.index("status")
    t.index("created_at")


@table("plan_tasks")
def _(t: T):
    """Individual tasks within a plan.

    Each task has optional verification spec (RefactorProfile YAML).
    Status values: pending | in_progress | completed | failed
    """
    t.int_pk()  # id
    t.int("plan_id", nullable=False)
    t.int("task_number", nullable=False)  # Sequential within plan
    t.text("title", nullable=False)
    t.text("description")
    t.text("status")  # pending | in_progress | completed | failed
    t.text("assigned_to")  # Optional assignee
    t.int("spec_id")  # FK to plan_specs (nullable - not all tasks have specs)
    t.timestamp("created_at")
    t.timestamp("completed_at")

    t.foreign_key("plan_id", "plans", "id")
    t.foreign_key("spec_id", "plan_specs", "id")
    t.index("plan_id")
    t.index("status")
    t.index("spec_id")
    t.unique("plan_id", "task_number")  # Prevent duplicate task numbers


@table("plan_specs")
def _(t: T):
    """YAML verification specs for tasks.

    spec_yaml contains RefactorProfile YAML compatible with RefactorRuleEngine.
    Multiple tasks can share same spec (reusable verification logic).
    """
    t.int_pk()  # id
    t.int("plan_id", nullable=False)
    t.text("spec_yaml", nullable=False)  # Full YAML text
    t.text("spec_type")  # e.g., "api_migration", "model_rename"
    t.timestamp("created_at")

    t.foreign_key("plan_id", "plans", "id")
    t.index("plan_id")
    t.index("spec_type")


@table("code_snapshots")
def _(t: T):
    """Checkpoint metadata for verification states.

    Snapshots capture git state at verification time.
    task_id nullable - can checkpoint entire plan, not just single task.
    """
    t.int_pk()  # id
    t.int("plan_id", nullable=False)
    t.int("task_id")  # Nullable - can checkpoint entire plan
    t.text("checkpoint_name", nullable=False)
    t.timestamp("timestamp")
    t.text("git_ref")  # Git commit SHA or branch name
    t.json("files_json")  # List of files affected

    t.foreign_key("plan_id", "plans", "id")
    t.foreign_key("task_id", "plan_tasks", "id")
    t.index("plan_id")
    t.index("task_id")
    t.index("timestamp")


@table("code_diffs")
def _(t: T):
    """Git diff storage for snapshots.

    Stores full diff text per file for checkpoint rollback.
    """
    t.int_pk()  # id
    t.int("snapshot_id", nullable=False)
    t.text("file_path", nullable=False)
    t.text("diff_text")  # Full git diff output
    t.int("added_lines")
    t.int("removed_lines")

    t.foreign_key("snapshot_id", "code_snapshots", "id")
    t.index("snapshot_id")
    t.index("file_path")
```

**Size Estimates**:
- plans: ~1 KB per plan × 10 plans = 10 KB
- plan_tasks: ~500 bytes per task × 100 tasks = 50 KB
- plan_specs: ~5 KB per spec × 20 specs = 100 KB
- code_snapshots: ~500 bytes per snapshot × 50 snapshots = 25 KB
- code_diffs: ~10 KB per diff × 100 diffs = 1 MB
- **Total**: ~1.2 MB typical, ~10 MB with extensive snapshots

## Module Architecture

### planning/ Package Structure

```
theauditor/planning/
├── __init__.py           # Package exports
├── manager.py            # PlanningManager (database operations)
├── verification.py       # Verification integration (RefactorRuleEngine wrapper)
└── snapshots.py          # Git snapshot management
```

### theauditor/planning/manager.py

**Purpose**: Database operations for planning.db

**Key Class**: `PlanningManager`

```python
# theauditor/planning/manager.py

from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, UTC

from theauditor.indexer.schema import TABLES, get_table_schema


class PlanningManager:
    """Manages planning database operations.

    Follows DatabaseManager pattern from theauditor/indexer/database.py
    but operates on planning.db instead of repo_index.db.

    NO FALLBACKS. Hard failure if planning.db is malformed or missing.
    """

    def __init__(self, db_path: Path):
        """Initialize planning database connection.

        Args:
            db_path: Path to planning.db (typically .pf/planning.db)

        Raises:
            FileNotFoundError: If planning.db doesn't exist (must init first)
        """
        if not db_path.exists():
            raise FileNotFoundError(
                f"Planning database not found: {db_path}\n"
                "Run 'aud planning init' first."
            )

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access


    def create_plan(self, name: str, description: str = "", metadata: dict = None) -> int:
        """Create new plan and return plan ID.

        Args:
            name: Plan name (required)
            description: Plan description
            metadata: Optional metadata dict (stored as JSON)

        Returns:
            plan_id: ID of created plan

        NO FALLBACKS. Raises sqlite3.IntegrityError if name is duplicate.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plans (name, description, created_at, status, metadata_json)
               VALUES (?, ?, ?, 'active', ?)""",
            (name, description, datetime.now(UTC).isoformat(),
             json.dumps(metadata) if metadata else None)
        )
        self.conn.commit()
        return cursor.lastrowid


    def add_task(self, plan_id: int, title: str, description: str = "",
                 spec_yaml: str = None) -> int:
        """Add task to plan and return task ID.

        Args:
            plan_id: ID of plan to add task to
            title: Task title (required)
            description: Task description
            spec_yaml: Optional YAML spec for verification

        Returns:
            task_id: ID of created task

        NO FALLBACKS. Raises sqlite3.IntegrityError if plan_id invalid.
        """
        cursor = self.conn.cursor()

        # Get next task number for this plan
        cursor.execute(
            "SELECT MAX(task_number) FROM plan_tasks WHERE plan_id = ?",
            (plan_id,)
        )
        max_task_num = cursor.fetchone()[0]
        task_number = (max_task_num or 0) + 1

        # Insert spec if provided
        spec_id = None
        if spec_yaml:
            spec_id = self._insert_spec(plan_id, spec_yaml)

        # Insert task
        cursor.execute(
            """INSERT INTO plan_tasks
               (plan_id, task_number, title, description, status, spec_id, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (plan_id, task_number, title, description, spec_id,
             datetime.now(UTC).isoformat())
        )
        self.conn.commit()
        return cursor.lastrowid


    def update_task_status(self, task_id: int, status: str, completed_at: str = None):
        """Update task status.

        Args:
            task_id: ID of task to update
            status: New status (pending|in_progress|completed|failed)
            completed_at: Optional completion timestamp

        NO FALLBACKS. Raises sqlite3.IntegrityError if task_id invalid.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE plan_tasks SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed_at, task_id)
        )
        self.conn.commit()


    def load_task_spec(self, task_id: int) -> Optional[str]:
        """Load verification spec YAML for task.

        Args:
            task_id: ID of task

        Returns:
            spec_yaml: YAML text or None if no spec

        NO FALLBACKS. Returns None if task has no spec (not an error).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT ps.spec_yaml
               FROM plan_tasks pt
               JOIN plan_specs ps ON pt.spec_id = ps.id
               WHERE pt.id = ?""",
            (task_id,)
        )
        row = cursor.fetchone()
        return row['spec_yaml'] if row else None


    def _insert_spec(self, plan_id: int, spec_yaml: str) -> int:
        """Insert spec and return spec ID (internal helper)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO plan_specs (plan_id, spec_yaml, created_at)
               VALUES (?, ?, ?)""",
            (plan_id, spec_yaml, datetime.now(UTC).isoformat())
        )
        return cursor.lastrowid


    # ... additional methods: get_plan(), list_tasks(), create_snapshot(), etc.
```

### theauditor/planning/verification.py

**Purpose**: Bridge planning system with RefactorRuleEngine and CodeQueryEngine

**Integration Points**:
- `theauditor/refactor/profiles.py:235` - RefactorRuleEngine
- `theauditor/refactor/profiles.py:110` - RefactorProfile
- `theauditor/context/query.py:98` - CodeQueryEngine

```python
# theauditor/planning/verification.py

from pathlib import Path
from typing import List, Dict
from theauditor.refactor import RefactorProfile, RefactorRuleEngine, ProfileEvaluation
from theauditor.context.query import CodeQueryEngine, SymbolInfo


def verify_task_spec(spec_yaml: str, db_path: Path, repo_root: Path) -> ProfileEvaluation:
    """Verify task completion using RefactorRuleEngine.

    Args:
        spec_yaml: YAML specification (RefactorProfile format)
        db_path: Path to repo_index.db
        repo_root: Project root directory

    Returns:
        ProfileEvaluation with violations and expected_references

    Integration:
        - Uses RefactorProfile.load_from_string() (refactor/profiles.py:121)
        - Uses RefactorRuleEngine.evaluate() (refactor/profiles.py:257)

    NO FALLBACKS. Raises ValueError if spec_yaml is malformed.
    """
    # Parse YAML into RefactorProfile
    # This validates YAML structure and rule format
    import tempfile
    import os

    # RefactorProfile.load expects a file path, create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(spec_yaml)
        temp_path = Path(f.name)

    try:
        profile = RefactorProfile.load(temp_path)
    finally:
        os.unlink(temp_path)

    # Run verification using existing engine
    with RefactorRuleEngine(db_path, repo_root) as engine:
        evaluation = engine.evaluate(profile)

    return evaluation


def find_analogous_patterns(root: Path, pattern_spec: Dict) -> List[SymbolInfo]:
    """Find similar code patterns for greenfield tasks (Amendment 1).

    Args:
        root: Project root (contains .pf/)
        pattern_spec: Dict describing pattern to find
          Example: {"type": "api_route", "method": "POST"}

    Returns:
        List of SymbolInfo matching pattern

    Integration:
        - Uses CodeQueryEngine.find_symbol() (context/query.py:158)
        - Uses CodeQueryEngine.get_api_handlers() (context/query.py:412)
        - Uses CodeQueryEngine.get_component_tree() (context/query.py:456)

    Use Case:
        Task: "Add POST /users route"
        Greenfield: No existing /users routes
        Analogous: find_analogous_patterns({"type": "api_route", "method": "POST"})
        Result: All existing POST routes for reference
    """
    engine = CodeQueryEngine(root)
    pattern_type = pattern_spec.get("type")

    if pattern_type == "api_route":
        # Find similar API routes
        handlers = engine.get_api_handlers("")  # All routes
        method = pattern_spec.get("method")
        if method:
            handlers = [h for h in handlers if h['method'] == method]
        return handlers

    elif pattern_type == "function":
        # Find similar functions by name pattern
        name_pattern = pattern_spec.get("name")
        symbols = engine.find_symbol(name_pattern)
        return [s for s in symbols if s.type == "function"]

    elif pattern_type == "component":
        # Find similar React components
        component_name = pattern_spec.get("name")
        tree = engine.get_component_tree(component_name)
        return [tree] if tree and "error" not in tree else []

    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")
```

### theauditor/planning/snapshots.py

**Purpose**: Git snapshot management for checkpointing

**Integration Points**:
- `theauditor/workset.py:37` - get_git_diff_files() pattern

```python
# theauditor/planning/snapshots.py

from pathlib import Path
import subprocess
import platform
from typing import List, Dict

IS_WINDOWS = platform.system() == "Windows"


def create_snapshot(plan_id: int, checkpoint_name: str, repo_root: Path) -> Dict:
    """Create code snapshot with git diff.

    Args:
        plan_id: ID of plan to snapshot
        checkpoint_name: Descriptive name (e.g., "post-task-3")
        repo_root: Project root directory

    Returns:
        Dict with snapshot metadata:
            - git_ref: Current commit SHA
            - files_affected: List of modified files
            - diffs: Dict[file_path, diff_text]

    Integration:
        Extends theauditor/workset.py:37 get_git_diff_files() pattern

    NO FALLBACKS. Raises RuntimeError if git command fails.
    """
    # Get current commit SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        shell=IS_WINDOWS
    )
    git_ref = result.stdout.strip()

    # Get list of modified files
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        shell=IS_WINDOWS
    )
    files_affected = [f.strip() for f in result.stdout.split('\n') if f.strip()]

    # Get full diff for each file
    diffs = {}
    for file_path in files_affected:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", file_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            shell=IS_WINDOWS
        )
        diffs[file_path] = result.stdout

        # Count added/removed lines
        added_lines = result.stdout.count('\n+')
        removed_lines = result.stdout.count('\n-')

    return {
        "git_ref": git_ref,
        "files_affected": files_affected,
        "diffs": diffs
    }
```

## CLI Command Architecture

### theauditor/commands/planning.py

**Structure**: Click command group with 7 subcommands

**Integration Point**: Registered in `theauditor/cli.py:346`

```python
# theauditor/commands/planning.py

import click
from pathlib import Path
from theauditor.utils.decorators import handle_exceptions
from theauditor.planning.manager import PlanningManager
from theauditor.planning.verification import verify_task_spec, find_analogous_patterns
from theauditor.planning.snapshots import create_snapshot


@click.group()
def planning():
    """Planning and verification commands.

    Database-centric plan management with deterministic verification.

    Examples:
        aud planning init --name "Auth0 Migration"
        aud planning add-task 1 --title "Update routes" --spec routes.yaml
        aud planning verify-task 1 3
        aud planning archive 1
    """
    pass


@planning.command()
@click.option("--name", required=True, help="Plan name")
@click.option("--description", default="", help="Plan description")
@click.option("--metadata-json", help="Metadata JSON string")
@handle_exceptions
def init(name, description, metadata_json):
    """Initialize new plan.

    Creates plan record in .pf/planning.db

    Example:
        aud planning init --name "Migrate to PostgreSQL"
    """
    import json
    from theauditor.config_runtime import load_runtime_config

    # Load config for .pf directory location
    config = load_runtime_config(".")
    pf_dir = Path(config["paths"]["pf_dir"])
    planning_db_path = pf_dir / "planning.db"

    # Initialize planning.db if doesn't exist
    if not planning_db_path.exists():
        _initialize_planning_db(planning_db_path)

    # Parse metadata
    metadata = json.loads(metadata_json) if metadata_json else {}

    # Create plan
    manager = PlanningManager(planning_db_path)
    plan_id = manager.create_plan(name, description, metadata)

    click.echo(f"Created plan {plan_id}: {name}")
    click.echo(f"Database: {planning_db_path}")


@planning.command()
@click.argument("plan_id", type=int)
@click.option("--title", required=True, help="Task title")
@click.option("--description", default="", help="Task description")
@click.option("--spec", type=click.Path(exists=True), help="Path to YAML spec file")
@handle_exceptions
def add_task(plan_id, title, description, spec):
    """Add task to plan.

    Example:
        aud planning add-task 1 --title "Update auth routes" --spec auth_spec.yaml
    """
    from theauditor.config_runtime import load_runtime_config

    config = load_runtime_config(".")
    planning_db_path = Path(config["paths"]["pf_dir"]) / "planning.db"

    # Load spec YAML if provided
    spec_yaml = None
    if spec:
        spec_yaml = Path(spec).read_text()

    # Add task
    manager = PlanningManager(planning_db_path)
    task_id = manager.add_task(plan_id, title, description, spec_yaml)

    click.echo(f"Added task {task_id} to plan {plan_id}: {title}")
    if spec:
        click.echo(f"Verification spec loaded from {spec}")


@planning.command()
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--verbose", is_flag=True, help="Show detailed violations")
@click.option("--checkpoint", is_flag=True, help="Create snapshot after verification")
@click.option("--output", type=click.Path(), help="Save verification report to file")
@handle_exceptions
def verify_task(plan_id, task_number, verbose, checkpoint, output):
    """Verify task completion using YAML spec.

    Queries repo_index.db using RefactorRuleEngine to check if
    task spec requirements are satisfied.

    Example:
        aud planning verify-task 1 3 --verbose
    """
    from theauditor.config_runtime import load_runtime_config
    import json

    config = load_runtime_config(".")
    pf_dir = Path(config["paths"]["pf_dir"])
    planning_db_path = pf_dir / "planning.db"
    repo_index_db_path = pf_dir / "repo_index.db"

    # Load task and spec
    manager = PlanningManager(planning_db_path)
    # ... get task_id from plan_id + task_number
    # spec_yaml = manager.load_task_spec(task_id)

    # Verify using RefactorRuleEngine
    evaluation = verify_task_spec(spec_yaml, repo_index_db_path, Path.cwd())

    # Update task status based on violations
    if evaluation.total_violations() == 0:
        manager.update_task_status(task_id, "completed", datetime.now(UTC).isoformat())
        click.echo(f"Task {task_number} VERIFIED (0 violations)")
    else:
        click.echo(f"Task {task_number} INCOMPLETE ({evaluation.total_violations()} violations)")
        if verbose:
            # ... print violations

    # Create checkpoint if requested
    if checkpoint:
        snapshot = create_snapshot(plan_id, f"task-{task_number}-verified", Path.cwd())
        # ... save snapshot to planning.db
        click.echo(f"Created checkpoint: {snapshot['git_ref'][:8]}")


# ... additional commands: show, update-task, archive, rewind
```

## Data Flow Diagrams

### Verification Flow

```
User: aud planning verify-task 1 3
   │
   ├─→ theauditor/commands/planning.py::verify_task()
   │     │
   │     ├─→ PlanningManager.load_task_spec(task_id)
   │     │     └─→ planning.db: SELECT spec_yaml FROM plan_specs
   │     │
   │     ├─→ verification.verify_task_spec(spec_yaml, db_path, root)
   │     │     │
   │     │     ├─→ RefactorProfile.load_from_string(spec_yaml)
   │     │     │     └─→ Parse YAML, validate structure
   │     │     │
   │     │     └─→ RefactorRuleEngine.evaluate(profile)
   │     │           └─→ repo_index.db: SELECT ... WHERE ... (existing queries)
   │     │
   │     └─→ PlanningManager.update_task_status(task_id, status)
   │           └─→ planning.db: UPDATE plan_tasks SET status = 'completed'
   │
   └─→ Output: Task 3 VERIFIED (0 violations)
```

### Analogous Pattern Detection Flow

```
User: aud planning add-task 1 --title "Add GET /products route"
   │
   ├─→ theauditor/commands/planning.py::add_task()
   │     │
   │     ├─→ find_analogous_patterns(root, {"type": "api_route", "method": "GET"})
   │     │     │
   │     │     └─→ CodeQueryEngine.get_api_handlers("")
   │     │           └─→ repo_index.db: SELECT ... FROM api_endpoints WHERE method = 'GET'
   │     │
   │     └─→ Display: Found 12 similar GET routes for reference
   │
   └─→ PlanningManager.add_task(plan_id, title, ...)
         └─→ planning.db: INSERT INTO plan_tasks
```

## Error Handling

Following CLAUDE.md "Zero Fallback Policy":

**NO FALLBACKS**:
- Planning.db malformed → Hard fail with error message
- Spec YAML invalid → Hard fail with YAML parse error
- Git commands fail → Hard fail with subprocess error
- Missing planning.db → Error: "Run 'aud planning init' first"

**NO GRACEFUL DEGRADATION**:
- If RefactorRuleEngine fails → Propagate exception (don't return "unknown")
- If CodeQueryEngine fails → Propagate exception (don't return empty list with warning)
- If database query fails → Crash with sqlite3 error (don't skip verification)

## Performance Considerations

**Database Size**:
- planning.db: ~1-5 MB typical, ~10 MB with extensive snapshots
- Separate from repo_index.db (91 MB) - no performance impact on indexing

**Query Latency**:
- `aud planning verify-task`: <1s (RefactorRuleEngine queries indexed repo_index.db)
- `aud planning show`: <50ms (indexed queries on planning.db)
- `aud planning add-task`: <100ms (single INSERT)

**Indexing Strategy**:
- Primary keys: All tables have int PK with AUTOINCREMENT
- Foreign keys: plan_id, spec_id, task_id, snapshot_id indexed
- Status index: Fast filtering for `SELECT ... WHERE status = 'pending'`
- Timestamp index: Fast range queries for recent snapshots

## Security Considerations

**SQL Injection**:
- All queries use parameterized SQL (? placeholders)
- No string interpolation for user input

**YAML Injection**:
- YAML loaded with yaml.safe_load (not yaml.load)
- RefactorProfile validates structure

**Git Command Injection**:
- subprocess.run with list args (no shell interpolation for user input)
- shell=IS_WINDOWS only for fixed git commands

## Testing Strategy

**Unit Tests**:
- `tests/test_planning_manager.py` - PlanningManager CRUD operations
- `tests/test_planning_verification.py` - verify_task_spec() integration
- `tests/test_planning_snapshots.py` - Git snapshot creation

**Integration Tests**:
- `tests/test_planning_workflow.py` - Full workflow: init → add-task → verify → archive

**Fixtures**:
- `tests/fixtures/planning/` - Example YAML specs
- Mock planning.db with sample data

## Future Enhancements

**Phase 2 (Not in this proposal)**:
- `aud planning prune --days 30` - Clean old snapshots
- `aud planning export --format markdown` - Export plan to Markdown
- `aud planning import --from jira.json` - Import from external tools
- Plan templates: `aud planning init --template auth-migration`

**NOT PLANNED**:
- GUI for plan management (CLI-first tool)
- Real-time collaboration (single developer workflow)
- Integration with external APIs (offline-first philosophy)
