# Pre-Implementation Plan: Planning System
**OpenSpec Change**: add-planning-system
**Coder**: Codex (Lead Coder)
**Branch**: planning-system (from pythonparity)
**SOP Version**: 4.20
**Date**: 2025-10-30

---

## Phase 0: Verification Phase ✅ COMPLETE

**Status**: ✅ COMPLETE (2025-10-30)
**Output**: `verification.md`

**Hypotheses Verified**:
- ✅ H1: RefactorRuleEngine can execute YAML-based verification specs (refactor/profiles.py:235)
- ✅ H2: CodeQueryEngine provides code navigation (context/query.py:98)
- ✅ H3: DatabaseManager uses schema-driven batching (indexer/database.py:28)
- ✅ H4: Git diff integration pattern exists (workset.py:37)
- ✅ H5: CLI command group pattern supports subcommands (cli.py:257)
- ✅ H6: handle_exceptions decorator exists (utils/decorators.py)
- ✅ H7: Architecture supports separate planning.db (context/query.py:139)
- ✅ H8: No indexer/extractor changes needed

**Discrepancies**: None identified
**Integration Points Confirmed**: All existing infrastructure verified and ready

**Deliverables**:
- [x] verification.md (8 hypotheses with evidence)
- [x] proposal.md (anchored in verified infrastructure)
- [x] design.md (integration points with file:line references)
- [x] tasks.md (5 phases, 14 tasks)
- [x] 3 spec deltas (planning-database, planning-commands, planning-verification)
- [x] OpenSpec validation passed: `openspec validate add-planning-system --strict`

**Next**: Phase 1 Implementation

---

## Phase 1: Database Schema and Manager (Foundation)

**Objective**: Create planning.db schema and PlanningManager class
**Duration**: 3-4 hours
**Lines**: ~350 lines
**Prerequisites**: Branch `planning-system` created from `pythonparity`

### Task 1.1: Add Planning Tables to schema.py

**Prompt for Architect**:
```
Phase 1.1: Add Planning Database Schema

Add 5 planning tables to theauditor/indexer/schema.py using @table() decorator pattern.

Tables:
- plans (id, name, description, created_at, status, metadata_json)
- plan_tasks (id, plan_id FK, task_number, title, description, status, assigned_to, spec_id FK, created_at, completed_at)
- plan_specs (id, plan_id FK, spec_yaml TEXT, spec_type, created_at)
- code_snapshots (id, plan_id FK, task_id FK nullable, checkpoint_name, timestamp, git_ref, files_json)
- code_diffs (id, snapshot_id FK, file_path, diff_text TEXT, added_lines, removed_lines)

Requirements per design.md lines 22-157.
Foreign keys, indexes, UNIQUE constraints as specified.

Expected: ~50 lines added to schema.py after line 1100 (after existing tables).
```

**Verification Steps**:
```bash
# 1. Verify schema registration
.venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
assert 'plans' in TABLES, 'plans table missing'
assert 'plan_tasks' in TABLES, 'plan_tasks table missing'
assert 'plan_specs' in TABLES, 'plan_specs table missing'
assert 'code_snapshots' in TABLES, 'code_snapshots table missing'
assert 'code_diffs' in TABLES, 'code_diffs table missing'
print('✅ All 5 tables registered')
"

# 2. Test table creation
.venv/Scripts/python.exe -c "
from pathlib import Path
import sqlite3
from theauditor.indexer.schema import TABLES

db_path = Path('test_planning.db')
conn = sqlite3.connect(db_path)

for table_name in ['plans', 'plan_tasks', 'plan_specs', 'code_snapshots', 'code_diffs']:
    schema = TABLES[table_name]
    create_sql = schema.create_table_sql()
    conn.execute(create_sql)

    # Verify table exists
    cursor = conn.execute(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'\")
    assert cursor.fetchone(), f'{table_name} table not created'

print('✅ All tables created successfully')
conn.close()
" && rm test_planning.db
```

**Acceptance Criteria**:
- [ ] All 5 tables defined with @table() decorator
- [ ] Foreign keys: plan_tasks.plan_id → plans.id, plan_tasks.spec_id → plan_specs.id, etc.
- [ ] Indexes: status, created_at, plan_id, task_id, timestamp
- [ ] UNIQUE constraint: (plan_id, task_number)
- [ ] Verification commands pass

**Coder Deliverable** (Template C-4.20):
```
Phase: 1.1
Objective: Add planning database schema
Status: COMPLETE

1. Verification Phase Report
   Hypotheses:
   - H1: schema.py uses @table() decorator pattern ✅ Confirmed (schema.py:93-143)
   - H2: Tables registry is Dict[str, TableSchema] ✅ Confirmed (schema.py:74)

2. Implementation Details
   File Modified: theauditor/indexer/schema.py (+50 lines after line 1100)

   ADDED: 5 table definitions using @table() decorator
   Location: schema.py:1101-1151

3. Post-Implementation Integrity Audit
   Files Audited: theauditor/indexer/schema.py
   Result: ✅ SUCCESS - All tables registered, syntax correct

4. Testing Performed
   [Verification commands output here]
```

---

### Task 1.2: Create PlanningManager Class

**Prompt for Architect**:
```
Phase 1.2: Create PlanningManager Class

Create theauditor/planning/manager.py with PlanningManager class.

Requirements:
- Follow DatabaseManager pattern (indexer/database.py:28-83)
- Connect to .pf/planning.db (separate from repo_index.db)
- Methods: __init__, create_schema, create_plan, add_task, update_task_status, load_task_spec, get_plan, list_tasks
- Use sqlite3.Row for dict-like access
- Hard fail if planning.db missing (NO FALLBACKS)

Expected: ~300 lines in new file theauditor/planning/manager.py
Design reference: design.md lines 159-308
```

**Verification Steps**:
```bash
# 1. Test PlanningManager initialization
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.manager import PlanningManager
import sqlite3

# Create test DB
db_path = Path('test_planning.db')
conn = sqlite3.connect(db_path)
manager = PlanningManager.__new__(PlanningManager)
manager.db_path = db_path
manager.conn = conn
manager.create_schema()

# Verify schema created
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]
assert 'plans' in tables
assert 'plan_tasks' in tables
print('✅ PlanningManager.create_schema() works')
conn.close()
" && rm test_planning.db

# 2. Test plan creation
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.manager import PlanningManager

db_path = Path('test_planning.db')
# Assuming create_schema initializes DB
manager = PlanningManager.init_database(db_path)
plan_id = manager.create_plan('Test Plan', 'Test description')
assert plan_id > 0, 'Plan ID not returned'
print(f'✅ Created plan with ID: {plan_id}')

# Test task creation
task_id = manager.add_task(plan_id, 'Task 1', 'Test task')
assert task_id > 0, 'Task ID not returned'
print(f'✅ Created task with ID: {task_id}')
" && rm test_planning.db
```

**Acceptance Criteria**:
- [ ] PlanningManager class exists in theauditor/planning/manager.py
- [ ] create_schema() creates all 5 tables
- [ ] create_plan() returns plan_id
- [ ] add_task() auto-increments task_number (1, 2, 3...)
- [ ] load_task_spec() returns YAML or None
- [ ] Hard fails if DB missing (FileNotFoundError raised)
- [ ] Verification commands pass

**Coder Deliverable**: Template C-4.20 format with implementation details

---

## Phase 2: Verification Integration

**Objective**: Bridge planning with RefactorRuleEngine and CodeQueryEngine
**Duration**: 3-4 hours
**Lines**: ~350 lines
**Prerequisites**: Phase 1 complete

### Task 2.1: Create Verification Wrapper Module

**Prompt for Architect**:
```
Phase 2.1: Create Verification Integration Module

Create theauditor/planning/verification.py with two functions:
1. verify_task_spec(spec_yaml, db_path, repo_root) -> ProfileEvaluation
2. find_analogous_patterns(root, pattern_spec) -> List[SymbolInfo]

Requirements:
- Import RefactorProfile, RefactorRuleEngine from theauditor.refactor
- Import CodeQueryEngine from theauditor.context.query
- verify_task_spec() wraps RefactorRuleEngine.evaluate() (NO modifications to engine)
- find_analogous_patterns() queries CodeQueryEngine for similar code
- Support pattern types: api_route, function, component
- Hard fail on invalid YAML (ValueError)

Expected: ~200 lines in new file theauditor/planning/verification.py
Design reference: design.md lines 310-389
```

**Verification Steps**:
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
assert result is not None, 'ProfileEvaluation not returned'
assert hasattr(result, 'total_violations'), 'Missing total_violations method'
print(f'✅ Verification returned {result.total_violations()} violations')
"

# Test analogous pattern detection
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.verification import find_analogous_patterns

pattern_spec = {'type': 'api_route', 'method': 'POST'}
results = find_analogous_patterns(Path.cwd(), pattern_spec)
print(f'✅ Found {len(results)} analogous POST routes')
"
```

**Acceptance Criteria**:
- [ ] verify_task_spec() calls RefactorRuleEngine.evaluate()
- [ ] verify_task_spec() raises ValueError for invalid YAML
- [ ] find_analogous_patterns() queries CodeQueryEngine
- [ ] Supports api_route, function, component pattern types
- [ ] Verification commands pass

---

### Task 2.2: Create Snapshot Management Module

**Prompt for Architect**:
```
Phase 2.2: Create Snapshot Management Module

Create theauditor/planning/snapshots.py with functions:
1. create_snapshot(plan_id, checkpoint_name, repo_root) -> Dict
2. load_snapshot(snapshot_id, manager) -> Dict

Requirements:
- Extend workset.py:37 git diff pattern (subprocess.run)
- Run git rev-parse HEAD, git diff HEAD
- Store full unified diff in code_diffs table
- Count added/removed lines (lines starting with +/-)
- Handle Windows (shell=IS_WINDOWS)
- Hard fail if git commands fail

Expected: ~150 lines in new file theauditor/planning/snapshots.py
Design reference: design.md lines 391-475
```

**Verification Steps**:
```bash
# Test snapshot creation
.venv/Scripts/python.exe -c "
from pathlib import Path
from theauditor.planning.snapshots import create_snapshot

snapshot = create_snapshot(1, 'test-checkpoint', Path.cwd())
assert 'git_ref' in snapshot, 'git_ref missing'
assert 'files_affected' in snapshot, 'files_affected missing'
assert 'diffs' in snapshot, 'diffs missing'
assert len(snapshot['git_ref']) == 40, 'Invalid git SHA'  # Full SHA is 40 chars
print(f'✅ Created snapshot at {snapshot[\"git_ref\"][:8]}')
print(f'✅ {len(snapshot[\"files_affected\"])} files affected')
"
```

**Acceptance Criteria**:
- [ ] create_snapshot() executes git commands
- [ ] Handles Windows (IS_WINDOWS flag)
- [ ] Returns dict with git_ref, files_affected, diffs
- [ ] Counts added/removed lines correctly
- [ ] Hard fails if git commands fail
- [ ] Verification commands pass

---

## Phase 3: CLI Commands

**Objective**: Create `aud planning` command group with 7 subcommands
**Duration**: 4-5 hours
**Lines**: ~503 lines
**Prerequisites**: Phases 1 & 2 complete

### Task 3.1: Create Planning Command Group

**Prompt for Architect**:
```
Phase 3.1: Create Planning CLI Commands

Create theauditor/commands/planning.py with Click command group and 7 subcommands:
1. init - Create new plan
2. show - Display plan details
3. add-task - Add task to plan
4. update-task - Update task status
5. verify-task - Verify task completion
6. archive - Archive completed plan
7. rewind - Show rollback instructions

Requirements:
- Use @click.group() for command group
- Apply @handle_exceptions decorator to all commands
- Follow existing command pattern (commands/graph.py:1-20)
- Import PlanningManager, verification, snapshots modules
- verify-task integrates with verify_task_spec()

Expected: ~500 lines in new file theauditor/commands/planning.py
Design reference: design.md lines 477-625
Spec reference: specs/planning-commands/spec.md
```

**Verification Steps**:
```bash
# Test command registration (after Phase 3.2)
aud planning --help
# Should list 7 subcommands

# Test init command
aud planning init --name "Test Plan" --description "Test"
# Should output: Created plan 1: Test Plan

# Test add-task command
aud planning add-task 1 --title "Test Task"
# Should output: Added task 1 to plan 1: Test Task

# Test show command
aud planning show 1
# Should display plan details

# Test verify-task (with fixture spec)
echo "refactor_name: Test
rules:
  - id: test
    description: Test
    match:
      identifiers: [nonexistent]
    expect:
      identifiers: [newFunction]" > test_spec.yaml

aud planning add-task 1 --title "Verify Test" --spec test_spec.yaml
aud planning verify-task 1 2
# Should show violation count
```

**Acceptance Criteria**:
- [ ] All 7 commands implemented
- [ ] All use @handle_exceptions decorator
- [ ] init creates planning.db if missing
- [ ] verify-task calls verify_task_spec()
- [ ] verify-task updates task status based on violations
- [ ] archive creates final snapshot
- [ ] rewind displays git commands (does NOT execute)
- [ ] Verification commands pass

---

### Task 3.2: Register Planning Command Group

**Prompt for Architect**:
```
Phase 3.2: Register Planning Command Group in CLI

Modify theauditor/cli.py:
- Add import: from theauditor.commands.planning import planning
- Add registration: cli.add_command(planning)

Expected: 3 lines modified (1 import, 1 blank, 1 registration)
Location: After line 287 (imports), after line 346 (registrations)
```

**Verification Steps**:
```bash
# Test CLI registration
aud --help | grep planning
# Should show: planning    Planning and verification commands

aud planning --help
# Should list 7 subcommands
```

**Acceptance Criteria**:
- [ ] planning command appears in `aud --help`
- [ ] `aud planning --help` lists 7 subcommands
- [ ] Verification commands pass

---

## Phase 4: Testing and Documentation

**Objective**: Create test suite and documentation
**Duration**: 2-3 hours
**Lines**: ~550 lines
**Prerequisites**: Phases 1, 2, 3 complete

### Task 4.1: Create Unit Tests

**Prompt for Architect**:
```
Phase 4.1: Create PlanningManager Unit Tests

Create tests/test_planning_manager.py with 8 test cases:
1. test_create_schema - Verify table creation
2. test_create_plan - Verify plan creation returns plan_id
3. test_add_task_auto_increment - Verify task_number increments
4. test_add_task_with_spec - Verify spec storage
5. test_load_task_spec - Verify spec retrieval
6. test_update_task_status - Verify status update
7. test_list_tasks_filter_by_status - Verify filtering
8. test_missing_planning_db_error - Verify hard failure

Requirements:
- Use pytest with tmp_path fixture
- Cleanup test DB after each test
- Test hard failure when DB missing

Expected: ~200 lines in new file tests/test_planning_manager.py
```

**Verification Steps**:
```bash
pytest tests/test_planning_manager.py -v
# Should show: 8 passed
```

**Acceptance Criteria**:
- [ ] All 8 tests pass
- [ ] Uses tmp_path for test DB
- [ ] Tests hard failure (FileNotFoundError)

---

### Task 4.2: Create Integration Test

**Prompt for Architect**:
```
Phase 4.2: Create Full Workflow Integration Test

Create tests/test_planning_workflow.py with end-to-end workflow test:
- Create plan
- Add task with spec
- Verify task (expect violations)
- Update task status
- Simulate code changes
- Re-verify task (expect 0 violations)
- Archive plan

Expected: ~150 lines in new file tests/test_planning_workflow.py
```

**Verification Steps**:
```bash
pytest tests/test_planning_workflow.py -v
# Should pass full workflow test
```

**Acceptance Criteria**:
- [ ] Workflow test passes end-to-end
- [ ] Verifies status transitions
- [ ] Tests verification success/failure

---

### Task 4.3: Create Documentation

**Prompt for Architect**:
```
Phase 4.3: Create Planning System Documentation

Create:
1. docs/planning/README.md - Quick start guide
2. docs/planning/examples/auth_migration.yaml - Example spec
3. docs/planning/examples/api_refactor.yaml - Example spec

Requirements:
- README documents all 7 commands with examples
- Example specs follow RefactorProfile YAML format
- Cover common use cases (API migration, model rename)

Expected: ~200 lines across 3 files
```

**Acceptance Criteria**:
- [ ] README includes quick start and command reference
- [ ] Example specs are valid RefactorProfile YAML
- [ ] Examples cover API migration and refactoring

---

## Phase 5: Validation and Cleanup

**Objective**: Validate OpenSpec proposal and test suite
**Duration**: 1 hour
**Prerequisites**: All phases complete

### Task 5.1: Run OpenSpec Validation

**Command**:
```bash
openspec validate add-planning-system --strict
```

**Expected**: Change 'add-planning-system' is valid

**Acceptance Criteria**:
- [ ] Validation passes with --strict flag
- [ ] All spec deltas valid

---

### Task 5.2: Run Full Test Suite

**Commands**:
```bash
# Planning tests
pytest tests/test_planning_manager.py -v
pytest tests/test_planning_workflow.py -v

# Full suite (ensure no regressions)
pytest tests/ -v

# Optional: Test coverage
pytest tests/ -k planning --cov=theauditor.planning --cov-report=term-missing
```

**Acceptance Criteria**:
- [ ] All planning tests pass
- [ ] No regressions in existing tests
- [ ] Test coverage >80% for planning module

---

### Task 5.3: Final Verification

**Steps**:
1. Run `aud full --offline` to verify no regressions
2. Test all 7 planning commands manually
3. Create example plan with real spec
4. Verify task with real codebase

**Commands**:
```bash
# Full audit (verify no regressions)
aud full --offline

# Manual workflow test
aud planning init --name "Example Plan"
aud planning add-task 1 --title "Example Task" --spec docs/planning/examples/auth_migration.yaml
aud planning show 1 --tasks
aud planning verify-task 1 1 --verbose
aud planning archive 1
```

**Acceptance Criteria**:
- [ ] `aud full --offline` completes successfully
- [ ] All 7 commands execute without errors
- [ ] Verification produces correct results
- [ ] Archive creates snapshot

---

## Execution Timeline

**Total Estimate**: 12-16 hours over 2-3 days

**Day 1** (4-5 hours):
- Phase 1: Database schema and PlanningManager (3-4 hours)
- Phase 2.1: Verification wrapper (1-1.5 hours)

**Day 2** (5-6 hours):
- Phase 2.2: Snapshot management (1-1.5 hours)
- Phase 3: CLI commands (4-5 hours)

**Day 3** (3-5 hours):
- Phase 4: Testing and docs (2-3 hours)
- Phase 5: Validation and cleanup (1-2 hours)

---

## Success Criteria

**Functional**:
- [ ] All 7 commands execute without errors
- [ ] Verification correctly evaluates YAML specs
- [ ] Analogous patterns return relevant code
- [ ] Checkpointing creates snapshots with diffs
- [ ] Archive creates immutable audit trail

**Quality**:
- [ ] OpenSpec validation passes --strict
- [ ] All unit/integration tests pass
- [ ] No regressions in existing tests
- [ ] Test coverage >80% for planning module

**Performance**:
- [ ] Verification completes <1s for typical specs
- [ ] Command latency <100ms (init, show, add-task)
- [ ] Archive with 50 snapshots <5s

**Documentation**:
- [ ] README includes workflow examples
- [ ] Example specs cover common use cases
- [ ] Help text clear and comprehensive

---

## Communication Protocol

**For Each Phase**:

1. **Architect provides prompt** (from tasks above)
2. **Coder executes** following Prime Directive (verify first, then implement)
3. **Coder reports** using Template C-4.20:
   - Verification Phase Report
   - Implementation Details
   - Post-Implementation Integrity Audit
   - Testing Performed
4. **Architect relays to Auditor** for validation
5. **Proceed to next phase** only after approval

**Blocking Issues**:
- If verification reveals discrepancy → Update tasks.md and re-plan
- If test fails → Fix immediately before next phase
- If validation fails → Address issues before continuing

---

## Branch Strategy

**Current State**:
```
main
 └─ pythonparity (Gemini's branch)
     └─ planning-system (CREATE THIS - our branch)
```

**Before Phase 1**:
```bash
# Ensure on pythonparity branch
git checkout pythonparity
git pull origin pythonparity

# Create planning-system branch
git checkout -b planning-system

# Verify branch
git branch --show-current
# Should output: planning-system
```

**After Each Phase**:
```bash
# Commit changes
git add .
git commit -m "Phase N: [Description]

OpenSpec: add-planning-system
Phase: N
Status: COMPLETE

[Brief summary of changes]
"
```

**Final Merge**:
1. Gemini merges pythonparity → main
2. Codex rebases planning-system on main
3. Resolve conflicts (schema.py, cli.py)
4. Codex merges planning-system → main

---

## Ready to Begin?

**Pre-Flight Checklist**:
- [x] Verification phase complete (verification.md)
- [x] OpenSpec proposal validated
- [x] Branch strategy defined
- [x] Execution plan documented
- [ ] planning-system branch created from pythonparity

**First Command**:
```
Create branch and begin Phase 1.1: Add Planning Database Schema
```

Awaiting architect's approval to proceed.
