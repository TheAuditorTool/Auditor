# Planning Database Capability

## ADDED Requirements

### Requirement: Planning Database Schema

The system SHALL maintain a separate planning database at `.pf/planning.db` independent from `repo_index.db`.

The system SHALL create planning.db using the same schema-driven architecture as repo_index.db (TableSchema registry in `theauditor/indexer/schema.py`).

The system SHALL define five planning tables: `plans`, `plan_tasks`, `plan_specs`, `code_snapshots`, `code_diffs`.

The system SHALL NOT regenerate planning.db when `aud index` is run (planning data persists across code re-indexing).

#### Scenario: Planning database creation
- **GIVEN** a project with `.pf/` directory
- **WHEN** user runs `aud planning init --name "Migration Plan"`
- **THEN** planning.db is created at `.pf/planning.db`
- **AND** all 5 tables exist with correct schema
- **AND** repo_index.db remains unchanged

#### Scenario: Planning database persistence
- **GIVEN** a planning.db with 3 plans and 10 tasks
- **WHEN** user runs `aud index` to re-index codebase
- **THEN** planning.db data remains intact
- **AND** all plans and tasks still exist
- **AND** repo_index.db is regenerated (existing behavior)

---

### Requirement: Plans Table

The system SHALL store top-level plan metadata in the `plans` table.

The system SHALL include columns: id (PK), name, description, created_at, status, metadata_json.

The system SHALL enforce NOT NULL constraint on name column.

The system SHALL support status values: 'active', 'completed', 'archived'.

The system SHALL create indexes on status and created_at columns.

#### Scenario: Plan creation with metadata
- **GIVEN** user provides plan name "Auth Migration" and metadata {"owner": "alice"}
- **WHEN** PlanningManager.create_plan() is called
- **THEN** a new row is inserted into plans table
- **AND** plan_id is returned as INTEGER
- **AND** status is set to 'active' by default
- **AND** metadata_json stores {"owner": "alice"} as JSON

#### Scenario: Plan status transition
- **GIVEN** a plan with status 'active' and 10 tasks (all completed)
- **WHEN** user runs `aud planning archive <plan_id>`
- **THEN** plan status is updated to 'archived'
- **AND** plan becomes read-only (no new tasks can be added)

---

### Requirement: Plan Tasks Table

The system SHALL store individual tasks in the `plan_tasks` table.

The system SHALL include columns: id (PK), plan_id (FK), task_number, title, description, status, assigned_to, spec_id (FK), created_at, completed_at.

The system SHALL enforce UNIQUE constraint on (plan_id, task_number) to prevent duplicate task numbers within a plan.

The system SHALL auto-increment task_number sequentially within each plan (1, 2, 3, ...).

The system SHALL support status values: 'pending', 'in_progress', 'completed', 'failed'.

The system SHALL create indexes on plan_id, status, and spec_id columns.

The system SHALL set spec_id to NULL if task has no verification spec.

#### Scenario: Task auto-numbering
- **GIVEN** a plan with 3 existing tasks (task_number 1, 2, 3)
- **WHEN** user adds new task with `aud planning add-task`
- **THEN** new task is assigned task_number 4
- **AND** UNIQUE constraint prevents manual duplicate task_number

#### Scenario: Task with verification spec
- **GIVEN** user provides YAML spec file for task
- **WHEN** task is added with `--spec routes.yaml`
- **THEN** spec YAML is stored in plan_specs table
- **AND** task.spec_id references the spec row
- **AND** spec can be loaded via plan_tasks JOIN plan_specs

#### Scenario: Task without verification spec
- **GIVEN** user adds task without --spec flag
- **WHEN** task is created
- **THEN** task.spec_id is NULL
- **AND** no spec row is created
- **AND** verify-task command reports "No spec for task"

#### Scenario: Task status lifecycle
- **GIVEN** a new task with status 'pending'
- **WHEN** user runs `aud planning update-task <plan_id> <task_num> --status in_progress`
- **THEN** task status is updated to 'in_progress'
- **AND** completed_at remains NULL
- **WHEN** `aud planning verify-task` succeeds (0 violations)
- **THEN** status is updated to 'completed'
- **AND** completed_at is set to current timestamp

---

### Requirement: Plan Specs Table

The system SHALL store verification specs in the `plan_specs` table.

The system SHALL include columns: id (PK), plan_id (FK), spec_yaml (TEXT), spec_type, created_at.

The system SHALL enforce NOT NULL constraint on spec_yaml column.

The system SHALL store full YAML text in spec_yaml column (no truncation).

The system SHALL allow multiple tasks to reference same spec (reusable verification logic).

The system SHALL create indexes on plan_id and spec_type columns.

#### Scenario: Spec storage and retrieval
- **GIVEN** user provides YAML spec file with RefactorProfile format
- **WHEN** spec is added to task
- **THEN** full YAML text is stored in spec_yaml column
- **AND** spec can be loaded via PlanningManager.load_task_spec()
- **AND** YAML is identical to original file (no data loss)

#### Scenario: Reusable specs
- **GIVEN** a spec for "API route migration" (spec_id=5)
- **WHEN** user adds task 1 with --spec api_migration.yaml
- **AND** user adds task 2 with same --spec api_migration.yaml
- **THEN** both tasks reference same spec_id=5
- **AND** only one spec row is created (deduplication)

#### Scenario: Invalid YAML rejection
- **GIVEN** user provides malformed YAML file
- **WHEN** task is added with --spec invalid.yaml
- **THEN** YAML parse error is raised (hard failure)
- **AND** task is NOT created
- **AND** no spec row is inserted

---

### Requirement: Code Snapshots Table

The system SHALL store checkpoint metadata in the `code_snapshots` table.

The system SHALL include columns: id (PK), plan_id (FK), task_id (FK nullable), checkpoint_name, timestamp, git_ref, files_json.

The system SHALL allow task_id to be NULL (plan-level snapshots, not task-specific).

The system SHALL store git commit SHA or branch name in git_ref column.

The system SHALL store list of affected files as JSON array in files_json column.

The system SHALL create indexes on plan_id, task_id, and timestamp columns.

#### Scenario: Task-level snapshot
- **GIVEN** task 3 is verified successfully
- **WHEN** user runs `aud planning verify-task <plan_id> 3 --checkpoint`
- **THEN** snapshot row is created with task_id=3
- **AND** git_ref contains current commit SHA
- **AND** files_json contains list of files modified since last checkpoint

#### Scenario: Plan-level snapshot
- **GIVEN** a plan ready for archival
- **WHEN** user runs `aud planning archive <plan_id>`
- **THEN** snapshot row is created with task_id=NULL
- **AND** checkpoint_name is "final-archive"
- **AND** files_json contains all files modified during entire plan

#### Scenario: Snapshot without git repository
- **GIVEN** project directory is not a git repository
- **WHEN** user runs verify-task with --checkpoint flag
- **THEN** error is raised "Git repository required for checkpointing"
- **AND** task verification still proceeds (checkpoint is optional)

---

### Requirement: Code Diffs Table

The system SHALL store git diffs in the `code_diffs` table.

The system SHALL include columns: id (PK), snapshot_id (FK), file_path, diff_text (TEXT), added_lines, removed_lines.

The system SHALL store full git diff output in diff_text column (unified diff format).

The system SHALL count added lines (lines starting with '+') and removed lines (lines starting with '-').

The system SHALL create indexes on snapshot_id and file_path columns.

The system SHALL create one code_diffs row per file per snapshot.

#### Scenario: Diff storage for modified file
- **GIVEN** file `src/auth.py` modified with 5 added lines and 3 removed lines
- **WHEN** snapshot is created
- **THEN** code_diffs row is created with snapshot_id
- **AND** file_path is "src/auth.py"
- **AND** diff_text contains full unified diff
- **AND** added_lines=5, removed_lines=3

#### Scenario: Multiple files in snapshot
- **GIVEN** 3 files modified (auth.py, routes.py, models.py)
- **WHEN** snapshot is created
- **THEN** 3 code_diffs rows are created
- **AND** all rows reference same snapshot_id
- **AND** each row has unique file_path

#### Scenario: Large diff handling
- **GIVEN** file with 10,000 line diff
- **WHEN** snapshot is created
- **THEN** full diff is stored in diff_text (no truncation)
- **AND** TEXT column supports large content

---

### Requirement: Foreign Key Integrity

The system SHALL enforce foreign key constraints between tables.

The system SHALL cascade deletes from plans to plan_tasks, plan_specs, code_snapshots.

The system SHALL cascade deletes from code_snapshots to code_diffs.

The system SHALL prevent deletion of plan_specs if tasks still reference spec_id.

#### Scenario: Plan deletion cascades
- **GIVEN** plan 1 with 5 tasks, 3 specs, 2 snapshots
- **WHEN** plan 1 is deleted
- **THEN** all 5 tasks are deleted
- **AND** all 3 specs are deleted
- **AND** all 2 snapshots are deleted
- **AND** all code_diffs for those snapshots are deleted

#### Scenario: Spec deletion protection
- **GIVEN** spec 5 referenced by tasks 1, 2, 3
- **WHEN** attempt to delete spec 5
- **THEN** deletion fails with foreign key constraint error
- **AND** spec remains in database
- **AND** user must delete tasks first

---

### Requirement: Index Performance

The system SHALL create indexes for common query patterns.

The system SHALL index plans.status for filtering active/completed/archived plans.

The system SHALL index plan_tasks.plan_id for fast task listing per plan.

The system SHALL index plan_tasks.status for filtering pending/in_progress/completed tasks.

The system SHALL index code_snapshots.timestamp for chronological snapshot ordering.

#### Scenario: Fast task filtering
- **GIVEN** 100 plans with 1000 total tasks
- **WHEN** user runs `aud planning show <plan_id> --tasks --status pending`
- **THEN** query uses plan_id + status indexes
- **AND** query completes in <50ms

#### Scenario: Chronological snapshot listing
- **GIVEN** 50 snapshots for plan 1
- **WHEN** user lists snapshots ordered by timestamp DESC
- **THEN** query uses timestamp index
- **AND** most recent snapshot returned first
