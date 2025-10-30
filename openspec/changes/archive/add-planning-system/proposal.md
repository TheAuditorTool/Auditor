# Proposal: Add Database-Centric Planning System

## Why

TheAuditor provides comprehensive code analysis and verification capabilities (taint tracking, pattern detection, CFG analysis, etc.), but lacks a structured approach to **planning and verifying multi-step refactorings**. Developers currently must:

1. Plan refactorings externally (notes, tickets, memory)
2. Manually track which code changes satisfy which requirements
3. Re-run full `aud full` to verify incomplete work
4. Lose context when switching between tasks

This creates **determinism gaps** where:
- We know HOW to verify code (RefactorRuleEngine, CodeQueryEngine)
- We lack WHERE to store plans, tasks, and verification specs
- We lack WHEN checkpoints to incrementally verify progress

### Evidence of Need

**Existing Infrastructure (Verified 2025-10-30)**:

1. **RefactorRuleEngine** (`theauditor/refactor/profiles.py:235-263`): YAML-driven verification engine that queries repo_index.db for code patterns. Currently used for incomplete refactoring detection. **Can verify task completion but has no persistent task storage.**

2. **CodeQueryEngine** (`theauditor/context/query.py:98-455`): SQL-based code navigation with symbol lookup, call graph traversal, dependency analysis. **Can find analogous patterns but has no greenfield planning workflow.**

3. **Git Integration** (`theauditor/workset.py:37-92`): Captures changed files via git diff. **Can detect changes but cannot checkpoint verification states.**

**Gap Analysis**:

| Capability | Exists? | Missing Component |
|------------|---------|------------------|
| Verify task completion (YAML specs) | ✅ | Persistent spec storage |
| Find analogous patterns | ✅ | Greenfield planning workflow |
| Checkpoint code states | ✅ (git) | Verification state storage |
| Track multi-task plans | ❌ | Planning database |
| Incremental verification | ❌ | Task-to-spec mapping |
| Plan archival/rewind | ❌ | Snapshot management |

### Real-World Impact

**Without Planning System**:
- User plans "Migrate Auth0 to Cognito" (12 tasks)
- Manually tracks which routes updated (lost after 2 days)
- Runs `aud full` to check progress (12 minute runtime, all or nothing)
- No record of what was verified at each checkpoint
- Cannot prove to reviewers that spec was satisfied

**With Planning System**:
- User runs `aud planning init --name "Auth0 to Cognito Migration"`
- Adds tasks with YAML specs: `aud planning add-task --title "Update login routes" --spec login_routes.yaml`
- Incrementally verifies: `aud planning verify-task 3` (queries repo_index.db, <1s)
- Checkpoints progress: `aud planning show` displays 7/12 tasks verified
- Archives completed plan: `aud planning archive 42` (immutable audit trail)

### Why This Matters

TheAuditor is positioned as a **deterministic, database-driven SAST platform**. The planning system completes this positioning by:

1. **Closing the workflow loop**: Analysis → Planning → Verification → Archival
2. **Enabling incremental verification**: Check task completion without full re-index
3. **Providing audit trails**: Immutable record of what was verified when
4. **Supporting greenfield development**: Find analogous patterns when no existing code exists

## What Changes

This proposal adds a database-centric planning system with three core components: planning database, CLI commands, and verification integration.

### Component 1: Planning Database (planning.db)

**Goal**: Separate database for planning data (independent of repo_index.db)

**Architecture**: Follows existing DatabaseManager + TableSchema pattern (verified in `verification.md` H3)

**New Tables** (added to `theauditor/indexer/schema.py` TABLES registry):

1. **plans** - Top-level plan metadata
   - Columns: id (PK), name, description, created_at, status, metadata_json
   - Indexes: status, created_at

2. **plan_tasks** - Individual tasks within plans
   - Columns: id (PK), plan_id (FK), task_number, title, description, status, assigned_to, spec_id (FK), created_at, completed_at
   - Indexes: plan_id, status, spec_id
   - Foreign Key: plan_id → plans.id

3. **plan_specs** - YAML verification specs for tasks
   - Columns: id (PK), plan_id (FK), spec_yaml (TEXT), spec_type, created_at
   - Indexes: plan_id, spec_type
   - Foreign Key: plan_id → plans.id
   - **Note**: spec_yaml contains RefactorProfile YAML compatible with RefactorRuleEngine

4. **code_snapshots** - Checkpoint metadata
   - Columns: id (PK), plan_id (FK), task_id (FK nullable), checkpoint_name, timestamp, git_ref, files_json (list of files affected)
   - Indexes: plan_id, task_id, timestamp
   - Foreign Keys: plan_id → plans.id, task_id → plan_tasks.id

5. **code_diffs** - Git diff storage for snapshots
   - Columns: id (PK), snapshot_id (FK), file_path, diff_text (TEXT), added_lines, removed_lines
   - Indexes: snapshot_id, file_path
   - Foreign Key: snapshot_id → code_snapshots.id

**Implementation**:

- New class: `theauditor/planning/manager.py::PlanningManager`
  - Follows DatabaseManager pattern (batching, schema-driven SQL)
  - Connects to `.pf/planning.db` (separate from repo_index.db)
  - Methods: create_plan(), add_task(), update_task(), load_spec(), create_snapshot()

**Database Impact**: New planning.db file (~1-5 MB for typical projects), **no changes to repo_index.db**

### Component 2: CLI Commands (aud planning)

**Goal**: Command group for plan management and verification

**Architecture**: Follows existing command group pattern (verified in `verification.md` H5)

**New File**: `theauditor/commands/planning.py`

**Commands**:

1. **aud planning init** - Create new plan
   - Options: --name (required), --description, --metadata-json
   - Creates plan record in planning.db
   - Returns plan ID

2. **aud planning show** - Display plan details
   - Arguments: [plan_id] (optional, defaults to active plan)
   - Options: --format (text|json), --tasks, --specs
   - Queries planning.db and displays plan, tasks, verification status

3. **aud planning add-task** - Add task to plan
   - Arguments: plan_id
   - Options: --title (required), --description, --spec (path to YAML file)
   - Validates spec YAML against RefactorProfile schema
   - Stores spec in plan_specs table

4. **aud planning update-task** - Update task status
   - Arguments: plan_id, task_number
   - Options: --status (pending|in-progress|completed|failed), --assigned-to
   - Updates plan_tasks table

5. **aud planning verify-task** - Verify task completion
   - Arguments: plan_id, task_number
   - Options: --verbose, --output (path to save verification report)
   - Loads spec from plan_specs table
   - **Calls RefactorRuleEngine.evaluate()** (existing, verified in H1)
   - Updates task status based on violations count
   - Creates checkpoint snapshot if --checkpoint flag set

6. **aud planning archive** - Archive completed plan
   - Arguments: plan_id
   - Creates final snapshot with all diffs
   - Sets plan status to 'archived'
   - Immutable record for audit trail

7. **aud planning rewind** - Rollback to checkpoint
   - Arguments: plan_id, checkpoint_name
   - Displays git commands to revert to snapshot state
   - Does NOT modify code (safety), only shows commands

**Integration**: Registered in `theauditor/cli.py:346` following graph/cfg pattern

### Component 3: Verification Integration

**Goal**: Bridge planning system with existing RefactorRuleEngine and CodeQueryEngine

**New Module**: `theauditor/planning/verification.py`

**Functions**:

1. **verify_task_spec()** - Wrapper around RefactorRuleEngine
   - Loads spec YAML from planning.db
   - Creates RefactorProfile instance
   - Calls RefactorRuleEngine.evaluate() (existing code, no changes)
   - Returns ProfileEvaluation with violations

2. **find_analogous_patterns()** - Greenfield planning support (Amendment 1)
   - Uses CodeQueryEngine to find similar implementations
   - Example: For "Add POST /users route", finds existing POST routes
   - Returns list of similar symbols/files for reference

**Implementation Details**:

```python
# theauditor/planning/verification.py
from theauditor.refactor import RefactorProfile, RefactorRuleEngine
from theauditor.context.query import CodeQueryEngine

def verify_task_spec(db_path: Path, spec_yaml: str, repo_root: Path) -> ProfileEvaluation:
    """Verify task completion using RefactorRuleEngine."""
    # Parse YAML into RefactorProfile
    profile = RefactorProfile.load_from_string(spec_yaml)

    # Use existing verification engine
    with RefactorRuleEngine(db_path, repo_root) as engine:
        evaluation = engine.evaluate(profile)

    return evaluation

def find_analogous_patterns(root: Path, pattern_type: str, filters: dict) -> List[SymbolInfo]:
    """Find similar code for greenfield tasks."""
    engine = CodeQueryEngine(root)

    if pattern_type == "api_route":
        return engine.get_api_handlers(filters.get("pattern", ""))
    elif pattern_type == "function":
        return engine.find_symbol(filters["name"], type_filter="function")
    # ... more pattern types
```

### Component 4: Snapshot Management (Amendment 2)

**Goal**: Checkpoint verification states with git diff storage

**New Module**: `theauditor/planning/snapshots.py`

**Functions**:

1. **create_snapshot()** - Capture current code state
   - Runs `git diff` to capture changes since last checkpoint
   - Stores diff in code_diffs table
   - Records affected files in code_snapshots.files_json

2. **load_snapshot()** - Retrieve checkpoint data
   - Queries code_snapshots and code_diffs tables
   - Returns snapshot metadata and diffs

**Implementation**: Extends `theauditor/workset.py::get_git_diff_files()` pattern (verified in H4)

## Impact

### Affected Specs

**New Capability Specs**:
- `specs/planning-database/spec.md` - Planning database schema requirements
- `specs/planning-commands/spec.md` - CLI command requirements
- `specs/planning-verification/spec.md` - Verification integration requirements

**No Changes to Existing Specs**: Planning system is additive, no modifications to existing capabilities.

### Affected Code

**New Files** (~1,200 lines total):

1. `theauditor/planning/manager.py` (~300 lines)
   - PlanningManager class
   - Database operations for planning.db

2. `theauditor/planning/verification.py` (~200 lines)
   - verify_task_spec() wrapper
   - find_analogous_patterns() implementation

3. `theauditor/planning/snapshots.py` (~150 lines)
   - create_snapshot() implementation
   - load_snapshot() implementation

4. `theauditor/commands/planning.py` (~500 lines)
   - Command group registration
   - 7 subcommands (init, show, add-task, update-task, verify-task, archive, rewind)

5. `theauditor/indexer/schema.py` (~50 lines added)
   - 5 new table definitions using @table() decorator

**Modified Files** (minimal changes):

1. `theauditor/cli.py` (+3 lines)
   - Import planning command group
   - Register with cli.add_command(planning)

**Zero Changes Required**:
- Indexer/extractors (verified in H8)
- RefactorRuleEngine (used as-is)
- CodeQueryEngine (used as-is)
- DatabaseManager (pattern reused, not modified)

### Performance Impact

**Database Size**:
- planning.db: ~1-5 MB for typical projects
  - 10 plans × 100 tasks × 5 KB spec = ~5 MB
  - Snapshots: ~10 MB per 1000-line diff (optional, prunable)
- **Total**: ~6-15 MB, negligible compared to repo_index.db (91 MB)

**Command Latency**:
- `aud planning init`: <100ms (single INSERT)
- `aud planning show`: <50ms (indexed queries)
- `aud planning verify-task`: <1s (RefactorRuleEngine queries repo_index.db)
- `aud planning archive`: <500ms (git diff + INSERT)

**No Impact on Existing Commands**: planning.db is separate, `aud full` unchanged

### Backward Compatibility

- **100% backward compatible** - all changes are additive
- Existing workflows (aud full, aud workset, aud refactor) unchanged
- planning.db optional - users who don't use planning commands see no difference

## Dependencies

**Existing Infrastructure (No New Dependencies)**:
- RefactorRuleEngine (theauditor/refactor/profiles.py)
- CodeQueryEngine (theauditor/context/query.py)
- DatabaseManager pattern (theauditor/indexer/database.py)
- Git integration (theauditor/workset.py)

**No External Dependencies Added**: Uses stdlib (sqlite3, subprocess, pathlib, click)

## Risks and Mitigations

**Risk 1**: planning.db schema evolution over time
- **Mitigation**: Use schema.py TABLES registry (same pattern as repo_index.db)
- **Mitigation**: Follow "no migrations" rule from CLAUDE.md (planning.db regenerated per-project)

**Risk 2**: Git diff storage fills disk for large projects
- **Mitigation**: Snapshots are optional (--checkpoint flag)
- **Mitigation**: Pruning command can clean old snapshots: `aud planning prune --days 30`

**Risk 3**: YAML spec validation errors
- **Mitigation**: Validate against RefactorProfile schema at add-task time
- **Mitigation**: Provide example specs in docs/planning/examples/

## Alternatives Considered

**Alternative 1**: Store plans in JSON files instead of database
- **Rejected**: Violates TheAuditor's database-centric architecture
- **Rejected**: No SQL query capabilities (e.g., "find all incomplete tasks")

**Alternative 2**: Extend repo_index.db instead of separate planning.db
- **Rejected**: Conceptual separation - planning data is NOT source code metadata
- **Rejected**: repo_index.db regenerated on `aud index`, planning data should persist

**Alternative 3**: Use external tool (Linear, Jira) for task tracking
- **Rejected**: Cannot verify task completion programmatically
- **Rejected**: No integration with RefactorRuleEngine

## Success Criteria

1. **Functional**: All 7 commands execute without errors
2. **Verification**: `aud planning verify-task` correctly evaluates YAML specs using RefactorRuleEngine
3. **Greenfield**: `find_analogous_patterns()` returns relevant code examples
4. **Checkpointing**: `aud planning archive` creates complete snapshot with diffs
5. **Performance**: Verification completes <1s for typical specs
6. **Documentation**: README includes planning workflow examples

## References

- **Original Proposal**: `aud_planning.md` in project root
- **Verification**: `verification.md` in this directory (hypothesis testing)
- **Team SOP**: `teamsop.md` template C-4.20 (verification protocol)
- **OpenSpec**: `openspec/AGENTS.md` (change management process)
