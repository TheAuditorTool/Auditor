# Tasks: Planning System Implementation

## Overview

Implementation organized in 4 phases that can be executed independently. Each task includes acceptance criteria and verification steps.

**Prerequisites**:
- Branch: `planning-system` (create from `pythonparity`)
- Python: 3.11+ (existing requirement)
- Dependencies: No new external dependencies

**Total Estimate**: ~1,200 lines of code, ~12-16 hours of implementation

---

## Phase 1: Database Schema and Manager (Foundation)

### Task 1.1: Add planning tables to schema.py

**File**: `theauditor/indexer/schema.py`

**Changes**:
```python
# Add after existing table definitions (~line 1100)

@table("plans")
def _(t: T):
    t.int_pk()
    t.text("name", nullable=False)
    t.text("description")
    t.timestamp("created_at")
    t.text("status")
    t.json("metadata_json")
    t.index("status")
    t.index("created_at")


@table("plan_tasks")
def _(t: T):
    t.int_pk()
    t.int("plan_id", nullable=False)
    t.int("task_number", nullable=False)
    t.text("title", nullable=False)
    t.text("description")
    t.text("status")
    t.text("assigned_to")
    t.int("spec_id")
    t.timestamp("created_at")
    t.timestamp("completed_at")
    t.foreign_key("plan_id", "plans", "id")
    t.foreign_key("spec_id", "plan_specs", "id")
    t.index("plan_id")
    t.index("status")
    t.index("spec_id")
    t.unique("plan_id", "task_number")


@table("plan_specs")
def _(t: T):
    t.int_pk()
    t.int("plan_id", nullable=False)
    t.text("spec_yaml", nullable=False)
    t.text("spec_type")
    t.timestamp("created_at")
    t.foreign_key("plan_id", "plans", "id")
    t.index("plan_id")
    t.index("spec_type")


@table("code_snapshots")
def _(t: T):
    t.int_pk()
    t.int("plan_id", nullable=False)
    t.int("task_id")
    t.text("checkpoint_name", nullable=False)
    t.timestamp("timestamp")
    t.text("git_ref")
    t.json("files_json")
    t.foreign_key("plan_id", "plans", "id")
    t.foreign_key("task_id", "plan_tasks", "id")
    t.index("plan_id")
    t.index("task_id")
    t.index("timestamp")


@table("code_diffs")
def _(t: T):
    t.int_pk()
    t.int("snapshot_id", nullable=False)
    t.text("file_path", nullable=False)
    t.text("diff_text")
    t.int("added_lines")
    t.int("removed_lines")
    t.foreign_key("snapshot_id", "code_snapshots", "id")
    t.index("snapshot_id")
    t.index("file_path")
```

**Acceptance Criteria**:
- [ ] All 5 tables defined with @table() decorator
- [ ] Foreign keys configured correctly
- [ ] Indexes on plan_id, status, timestamps
- [ ] UNIQUE constraint on (plan_id, task_number)

**Verification**:
```bash
# Check schema registration
.venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
assert 'plans' in TABLES
assert 'plan_tasks' in TABLES
assert 'plan_specs' in TABLES
assert 'code_snapshots' in TABLES
assert 'code_diffs' in TABLES
print('Schema registration: PASS')
"
```

**Lines**: ~50 lines

---

### Task 1.2: Create PlanningManager class

**File**: `theauditor/planning/manager.py` (new file)

**Implementation**:
1. Create `theauditor/planning/` directory
2. Add `__init__.py` with exports
3. Implement `PlanningManager` class following `DatabaseManager` pattern

**Methods to Implement**:
- `__init__(db_path)` - Connect to planning.db
- `create_schema()` - Create tables using schema.py definitions
- `create_plan(name, description, metadata)` - Insert plan, return plan_id
- `add_task(plan_id, title, description, spec_yaml)` - Insert task with spec
- `update_task_status(task_id, status, completed_at)` - Update task
- `load_task_spec(task_id)` - Get spec YAML for task
- `get_plan(plan_id)` - Get plan details
- `list_tasks(plan_id, status_filter)` - Get tasks for plan
- `_insert_spec(plan_id, spec_yaml)` - Internal helper

**Acceptance Criteria**:
- [ ] PlanningManager initializes planning.db connection
- [ ] create_schema() generates all 5 tables
- [ ] create_plan() returns valid plan_id
- [ ] add_task() auto-increments task_number correctly
- [ ] load_task_spec() returns YAML or None
- [ ] NO FALLBACKS - hard fail on missing DB or malformed data

**Verification**:
```bash
# Create test planning.db
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.manager import PlanningManager

db_path = Path('test_planning.db')
manager = PlanningManager.init_database(db_path)
plan_id = manager.create_plan('Test Plan', 'Test description')
task_id = manager.add_task(plan_id, 'Task 1', spec_yaml='test: yaml')
assert task_id > 0
print('PlanningManager: PASS')
" && rm test_planning.db
```

**Lines**: ~300 lines

---

## Phase 2: Verification Integration

### Task 2.1: Create verification wrapper module

**File**: `theauditor/planning/verification.py` (new file)

**Implementation**:
1. Import RefactorProfile, RefactorRuleEngine from theauditor.refactor
2. Import CodeQueryEngine from theauditor.context.query
3. Implement verify_task_spec() function
4. Implement find_analogous_patterns() function

**Function Signatures**:
```python
def verify_task_spec(
    spec_yaml: str,
    db_path: Path,
    repo_root: Path
) -> ProfileEvaluation:
    """Verify task using RefactorRuleEngine."""
    # Create temp file for spec YAML (RefactorProfile.load needs path)
    # Load RefactorProfile from spec_yaml
    # Initialize RefactorRuleEngine with db_path
    # Call engine.evaluate(profile)
    # Return ProfileEvaluation


def find_analogous_patterns(
    root: Path,
    pattern_spec: Dict
) -> List[Union[SymbolInfo, Dict]]:
    """Find similar code for greenfield tasks."""
    # Initialize CodeQueryEngine
    # Match pattern_spec["type"] (api_route, function, component)
    # Query appropriate CodeQueryEngine method
    # Return results
```

**Acceptance Criteria**:
- [ ] verify_task_spec() calls RefactorRuleEngine.evaluate()
- [ ] verify_task_spec() raises ValueError for invalid YAML
- [ ] find_analogous_patterns() handles api_route, function, component types
- [ ] NO FALLBACKS - hard fail if CodeQueryEngine or RefactorRuleEngine errors

**Verification**:
```bash
# Test verification with fixture spec
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.verification import verify_task_spec

spec_yaml = '''
refactor_name: Test Spec
description: Test verification
rules:
  - id: test-rule
    description: Test rule
    match:
      identifiers: [oldFunction]
    expect:
      identifiers: [newFunction]
'''

db_path = Path('.pf/repo_index.db')
result = verify_task_spec(spec_yaml, db_path, Path.cwd())
assert result is not None
print('Verification integration: PASS')
"
```

**Lines**: ~200 lines

---

### Task 2.2: Create snapshot management module

**File**: `theauditor/planning/snapshots.py` (new file)

**Implementation**:
1. Import subprocess, platform from stdlib
2. Implement create_snapshot() function
3. Implement load_snapshot() helper

**Function Signatures**:
```python
def create_snapshot(
    plan_id: int,
    checkpoint_name: str,
    repo_root: Path
) -> Dict:
    """Create git snapshot with diff storage."""
    # Run git rev-parse HEAD (get current commit)
    # Run git diff --name-only HEAD (get modified files)
    # For each file: run git diff HEAD -- file_path
    # Count added/removed lines
    # Return dict with git_ref, files_affected, diffs


def load_snapshot(
    snapshot_id: int,
    manager: PlanningManager
) -> Dict:
    """Load snapshot from planning.db."""
    # Query code_snapshots table
    # Query code_diffs table
    # Reconstruct snapshot dict
    # Return metadata + diffs
```

**Acceptance Criteria**:
- [ ] create_snapshot() executes git commands successfully
- [ ] create_snapshot() handles Windows (shell=IS_WINDOWS)
- [ ] create_snapshot() counts added/removed lines correctly
- [ ] load_snapshot() reconstructs full snapshot from DB
- [ ] NO FALLBACKS - hard fail if git commands fail

**Verification**:
```bash
# Test snapshot creation
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.snapshots import create_snapshot

snapshot = create_snapshot(1, 'test-checkpoint', Path.cwd())
assert 'git_ref' in snapshot
assert 'files_affected' in snapshot
assert 'diffs' in snapshot
print('Snapshot management: PASS')
"
```

**Lines**: ~150 lines

---

## Phase 3: CLI Commands

### Task 3.1: Create planning command group

**File**: `theauditor/commands/planning.py` (new file)

**Implementation**:
1. Create Click command group @click.group()
2. Implement 7 subcommands
3. Add @handle_exceptions decorator to all commands
4. Import PlanningManager, verification, snapshots modules

**Commands to Implement**:

**3.1a: init command**
```python
@planning.command()
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--metadata-json")
@handle_exceptions
def init(name, description, metadata_json):
    # Check if planning.db exists, create if not
    # Create plan via PlanningManager
    # Display plan_id and path
```

**3.1b: show command**
```python
@planning.command()
@click.argument("plan_id", type=int, default=None, required=False)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--tasks", is_flag=True)
@handle_exceptions
def show(plan_id, format, tasks):
    # Load plan from planning.db
    # If --tasks: load tasks with status
    # Display in text or JSON format
```

**3.1c: add-task command**
```python
@planning.command()
@click.argument("plan_id", type=int)
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--spec", type=click.Path(exists=True))
@handle_exceptions
def add_task(plan_id, title, description, spec):
    # Load spec YAML from file if provided
    # Add task via PlanningManager
    # Optionally: find analogous patterns if --analogous flag
    # Display task_id
```

**3.1d: update-task command**
```python
@planning.command()
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--status", type=click.Choice(["pending", "in_progress", "completed", "failed"]))
@click.option("--assigned-to")
@handle_exceptions
def update_task(plan_id, task_number, status, assigned_to):
    # Get task_id from plan_id + task_number
    # Update task via PlanningManager
    # Display confirmation
```

**3.1e: verify-task command** (most complex)
```python
@planning.command()
@click.argument("plan_id", type=int)
@click.argument("task_number", type=int)
@click.option("--verbose", is_flag=True)
@click.option("--checkpoint", is_flag=True)
@click.option("--output", type=click.Path())
@handle_exceptions
def verify_task(plan_id, task_number, verbose, checkpoint, output):
    # Get task_id from plan_id + task_number
    # Load spec YAML via PlanningManager
    # Call verify_task_spec() from verification module
    # If 0 violations: update status to 'completed'
    # If violations and --verbose: display violations
    # If --checkpoint: create snapshot via snapshots module
    # If --output: save evaluation to JSON file
```

**3.1f: archive command**
```python
@planning.command()
@click.argument("plan_id", type=int)
@handle_exceptions
def archive(plan_id):
    # Create final snapshot with all diffs
    # Update plan status to 'archived'
    # Display confirmation
```

**3.1g: rewind command**
```python
@planning.command()
@click.argument("plan_id", type=int)
@click.argument("checkpoint_name")
@handle_exceptions
def rewind(plan_id, checkpoint_name):
    # Load snapshot via snapshots.load_snapshot()
    # Display git commands to revert (DO NOT execute)
    # Safety: show commands, user executes manually
```

**Acceptance Criteria**:
- [ ] All 7 commands registered under @planning group
- [ ] All commands use @handle_exceptions decorator
- [ ] init creates planning.db if missing
- [ ] verify-task integrates with verification module
- [ ] verify-task updates task status based on violations
- [ ] archive creates final snapshot
- [ ] rewind displays (but does not execute) git commands

**Verification**:
```bash
# Test all commands
aud planning --help  # Should list 7 subcommands
aud planning init --name "Test Plan"  # Should create plan
aud planning add-task 1 --title "Test Task"  # Should add task
aud planning show 1 --tasks  # Should display plan with tasks
```

**Lines**: ~500 lines

---

### Task 3.2: Register planning command group in CLI

**File**: `theauditor/cli.py`

**Changes**:
```python
# Add import (around line 287)
from theauditor.commands.planning import planning

# Add registration (around line 346)
cli.add_command(planning)
```

**Acceptance Criteria**:
- [ ] planning command group appears in `aud --help`
- [ ] `aud planning --help` displays all subcommands

**Verification**:
```bash
aud --help | grep planning  # Should show planning command
aud planning --help  # Should list init, show, add-task, etc.
```

**Lines**: ~3 lines

---

## Phase 4: Testing and Documentation

### Task 4.1: Create unit tests for PlanningManager

**File**: `tests/test_planning_manager.py` (new file)

**Test Cases**:
```python
def test_create_schema():
    """Test planning.db schema creation."""

def test_create_plan():
    """Test plan creation returns valid plan_id."""

def test_add_task_auto_increment():
    """Test task_number auto-increments correctly."""

def test_add_task_with_spec():
    """Test task with YAML spec."""

def test_load_task_spec():
    """Test loading spec YAML from task."""

def test_update_task_status():
    """Test updating task status."""

def test_list_tasks_filter_by_status():
    """Test filtering tasks by status."""

def test_missing_planning_db_error():
    """Test error when planning.db missing."""
```

**Acceptance Criteria**:
- [ ] All 8 test cases pass
- [ ] Uses temporary planning.db (cleanup after tests)
- [ ] Tests hard failure when DB missing

**Verification**:
```bash
pytest tests/test_planning_manager.py -v
# Should show 8 passed tests
```

**Lines**: ~200 lines

---

### Task 4.2: Create integration test for full workflow

**File**: `tests/test_planning_workflow.py` (new file)

**Test Workflow**:
```python
def test_full_planning_workflow(tmp_path):
    """Test complete planning workflow."""
    # Setup: Create test planning.db
    # Step 1: Create plan
    # Step 2: Add task with spec
    # Step 3: Verify task (expect violations)
    # Step 4: Update task status to in_progress
    # Step 5: Simulate code changes (modify fixture)
    # Step 6: Verify task again (expect 0 violations)
    # Step 7: Archive plan
    # Assertions: Check all statuses correct
```

**Acceptance Criteria**:
- [ ] Workflow test passes end-to-end
- [ ] Uses fixtures for spec YAML and test code
- [ ] Verifies status transitions (pending → in_progress → completed)

**Verification**:
```bash
pytest tests/test_planning_workflow.py -v
# Should pass full workflow test
```

**Lines**: ~150 lines

---

### Task 4.3: Create example specs and documentation

**Files**:
- `docs/planning/README.md` (new file)
- `docs/planning/examples/auth_migration.yaml` (new file)
- `docs/planning/examples/api_refactor.yaml` (new file)

**Content for README.md**:
```markdown
# Planning System

Database-centric plan management with deterministic verification.

## Quick Start

1. Initialize plan:
   ```bash
   aud planning init --name "Migrate Auth0 to Cognito"
   ```

2. Add tasks with specs:
   ```bash
   aud planning add-task 1 --title "Update login routes" --spec auth_routes.yaml
   ```

3. Verify task completion:
   ```bash
   aud planning verify-task 1 1 --verbose
   ```

4. Archive completed plan:
   ```bash
   aud planning archive 1
   ```

## YAML Spec Format

See `examples/` directory for sample specs.

## Commands Reference

- `aud planning init` - Create new plan
- `aud planning show` - Display plan details
- `aud planning add-task` - Add task to plan
- `aud planning update-task` - Update task status
- `aud planning verify-task` - Verify task completion
- `aud planning archive` - Archive completed plan
- `aud planning rewind` - Show revert commands

## Database Schema

Planning data stored in `.pf/planning.db` (separate from repo_index.db).

Tables: plans, plan_tasks, plan_specs, code_snapshots, code_diffs
```

**Example Spec** (auth_migration.yaml):
```yaml
refactor_name: Auth0 Login Route Migration
description: Migrate login routes from Auth0 to AWS Cognito
version: 1.0

rules:
  - id: remove-auth0-imports
    description: Remove Auth0 SDK imports
    severity: high
    match:
      identifiers: [auth0, Auth0Client]
    expect:
      identifiers: [CognitoIdentityClient]

  - id: update-login-endpoint
    description: Update /login endpoint to use Cognito
    severity: critical
    match:
      api_routes: ['/auth/login']
    expect:
      identifiers: [cognito_login]
```

**Acceptance Criteria**:
- [ ] README.md documents all commands with examples
- [ ] Example specs follow RefactorProfile YAML format
- [ ] Examples cover common use cases (API migration, model rename)

**Lines**: ~200 lines (docs + examples)

---

## Phase 5: Validation and Cleanup

### Task 5.1: Run OpenSpec validation

**Command**:
```bash
python -m openspec.cli validate openspec/changes/add-planning-system --strict
```

**Acceptance Criteria**:
- [ ] Validation passes with --strict flag
- [ ] All spec deltas valid (ADDED requirements with scenarios)
- [ ] proposal.md, tasks.md, design.md, verification.md present

**Fix any validation errors before proceeding.**

---

### Task 5.2: Run full test suite

**Commands**:
```bash
# Unit tests
pytest tests/test_planning_manager.py -v
pytest tests/test_planning_verification.py -v
pytest tests/test_planning_snapshots.py -v

# Integration test
pytest tests/test_planning_workflow.py -v

# Full suite
pytest tests/ -k planning -v
```

**Acceptance Criteria**:
- [ ] All planning tests pass
- [ ] No regressions in existing tests
- [ ] Test coverage >80% for planning/ module

---

### Task 5.3: Create PR and final validation

**Steps**:
1. Ensure all tasks marked complete
2. Run `aud full --offline` to verify no regressions
3. Create PR from `planning-system` branch to `main`
4. Include OpenSpec change ID in PR description
5. Tag for review

**PR Description Template**:
```markdown
# Add Planning System

OpenSpec Change: `add-planning-system`

## Summary

Adds database-centric planning system with 7 CLI commands:
- aud planning init - Create plans
- aud planning add-task - Add tasks with YAML specs
- aud planning verify-task - Verify completion via RefactorRuleEngine
- aud planning show - Display plan status
- aud planning update-task - Update task metadata
- aud planning archive - Create immutable audit trail
- aud planning rewind - Show revert commands

## Implementation

- planning.db: 5 new tables (plans, plan_tasks, plan_specs, code_snapshots, code_diffs)
- PlanningManager: Database operations following DatabaseManager pattern
- Verification: Leverages existing RefactorRuleEngine and CodeQueryEngine
- Snapshots: Git diff storage for checkpointing

## Testing

- 8 unit tests (PlanningManager CRUD)
- 1 integration test (full workflow)
- Example specs in docs/planning/examples/

## Verification

See openspec/changes/add-planning-system/verification.md for hypothesis testing of existing infrastructure.

## References

- Proposal: openspec/changes/add-planning-system/proposal.md
- Design: openspec/changes/add-planning-system/design.md
- Tasks: openspec/changes/add-planning-system/tasks.md
```

**Acceptance Criteria**:
- [ ] PR created with OpenSpec change reference
- [ ] All tests passing in CI
- [ ] No merge conflicts with main branch

---

## Summary

**Total Lines of Code**: ~1,200 lines
- Phase 1: ~350 lines (schema + manager)
- Phase 2: ~350 lines (verification + snapshots)
- Phase 3: ~503 lines (CLI commands)
- Phase 4: ~550 lines (tests + docs)
- Phase 5: Validation only

**Estimated Time**: 12-16 hours
- Phase 1: 3-4 hours
- Phase 2: 3-4 hours
- Phase 3: 4-5 hours
- Phase 4: 2-3 hours
- Phase 5: 1 hour

**Dependencies**: None (uses existing infrastructure)

**Risks**: Low (additive feature, no breaking changes)
