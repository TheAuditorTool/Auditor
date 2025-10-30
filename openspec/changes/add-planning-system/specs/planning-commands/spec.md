# Planning Commands Capability

## ADDED Requirements

### Requirement: Planning Command Group

The system SHALL provide a Click command group `aud planning` with 7 subcommands.

The system SHALL register the planning command group in `theauditor/cli.py`.

The system SHALL display all 7 subcommands when user runs `aud planning --help`.

The system SHALL apply `@handle_exceptions` decorator to all planning commands.

#### Scenario: Command group registration
- **GIVEN** TheAuditor CLI is installed
- **WHEN** user runs `aud --help`
- **THEN** output includes "planning" in the commands list
- **WHEN** user runs `aud planning --help`
- **THEN** output lists 7 subcommands: init, show, add-task, update-task, verify-task, archive, rewind

---

### Requirement: aud planning init Command

The system SHALL provide `aud planning init` command to create new plans.

The system SHALL require --name option (plan name).

The system SHALL accept optional --description and --metadata-json options.

The system SHALL create `.pf/planning.db` if it doesn't exist.

The system SHALL initialize planning database schema on first init.

The system SHALL return plan_id after successful creation.

#### Scenario: First-time init
- **GIVEN** project with no planning.db
- **WHEN** user runs `aud planning init --name "Auth Migration"`
- **THEN** planning.db is created at `.pf/planning.db`
- **AND** all 5 tables are created
- **AND** plan is inserted with name "Auth Migration"
- **AND** output displays "Created plan 1: Auth Migration"

#### Scenario: Init with metadata
- **GIVEN** user provides metadata JSON
- **WHEN** user runs `aud planning init --name "Test" --metadata-json '{"owner": "alice"}'`
- **THEN** plan is created with metadata {"owner": "alice"}
- **AND** metadata is stored in plans.metadata_json column

#### Scenario: Init without required name
- **GIVEN** user runs `aud planning init` without --name
- **THEN** Click raises error "Missing option '--name'"
- **AND** no plan is created

---

### Requirement: aud planning show Command

The system SHALL provide `aud planning show` command to display plan details.

The system SHALL accept optional plan_id argument (defaults to active plan if only one exists).

The system SHALL accept --format option with choices 'text' or 'json'.

The system SHALL accept --tasks flag to include task list.

The system SHALL display plan name, description, status, created_at, and task count.

The system SHALL display task list with task_number, title, status, completed_at when --tasks flag is set.

#### Scenario: Show plan in text format
- **GIVEN** plan 1 with name "Auth Migration", 5 tasks (3 completed, 2 pending)
- **WHEN** user runs `aud planning show 1`
- **THEN** output displays:
  ```
  Plan 1: Auth Migration
  Status: active
  Created: 2025-10-30T12:00:00Z
  Tasks: 5 total (3 completed, 2 pending)
  ```

#### Scenario: Show plan with tasks
- **GIVEN** plan 1 with 3 tasks
- **WHEN** user runs `aud planning show 1 --tasks`
- **THEN** output includes task list:
  ```
  Tasks:
    1. [completed] Update login routes (completed at 2025-10-30T13:00:00Z)
    2. [in_progress] Update auth middleware
    3. [pending] Add tests
  ```

#### Scenario: Show plan in JSON format
- **GIVEN** plan 1
- **WHEN** user runs `aud planning show 1 --format json`
- **THEN** output is valid JSON with plan details
- **AND** JSON includes fields: id, name, description, status, created_at, tasks

#### Scenario: Show without plan_id (auto-detect)
- **GIVEN** only one active plan exists (plan_id=1)
- **WHEN** user runs `aud planning show` (no plan_id)
- **THEN** plan 1 is displayed automatically
- **GIVEN** multiple active plans exist
- **WHEN** user runs `aud planning show` (no plan_id)
- **THEN** error "Multiple active plans found, specify plan_id"

---

### Requirement: aud planning add-task Command

The system SHALL provide `aud planning add-task` command to add tasks to plans.

The system SHALL require plan_id argument and --title option.

The system SHALL accept optional --description and --spec options.

The system SHALL auto-increment task_number for the plan.

The system SHALL load YAML spec from file if --spec option provided.

The system SHALL validate spec YAML against RefactorProfile schema before storage.

The system SHALL return task_id after successful creation.

#### Scenario: Add task without spec
- **GIVEN** plan 1 with 2 existing tasks
- **WHEN** user runs `aud planning add-task 1 --title "Update tests"`
- **THEN** task is created with task_number=3
- **AND** spec_id is NULL
- **AND** output displays "Added task 3 to plan 1: Update tests"

#### Scenario: Add task with YAML spec
- **GIVEN** plan 1 and spec file `auth_routes.yaml` exists
- **WHEN** user runs `aud planning add-task 1 --title "Update routes" --spec auth_routes.yaml`
- **THEN** YAML is loaded from file
- **AND** spec is stored in plan_specs table
- **AND** task.spec_id references new spec row
- **AND** output displays "Verification spec loaded from auth_routes.yaml"

#### Scenario: Add task with invalid spec
- **GIVEN** spec file contains malformed YAML
- **WHEN** user runs `aud planning add-task 1 --title "Test" --spec invalid.yaml`
- **THEN** YAML parse error is raised
- **AND** task is NOT created
- **AND** error message shows YAML syntax error

#### Scenario: Add task to non-existent plan
- **GIVEN** plan 99 does not exist
- **WHEN** user runs `aud planning add-task 99 --title "Test"`
- **THEN** error "Plan 99 not found"
- **AND** no task is created

---

### Requirement: aud planning update-task Command

The system SHALL provide `aud planning update-task` command to modify task metadata.

The system SHALL require plan_id and task_number arguments.

The system SHALL accept --status option with choices: pending, in_progress, completed, failed.

The system SHALL accept --assigned-to option to set assignee.

The system SHALL update task status and/or assignee in planning.db.

#### Scenario: Update task status
- **GIVEN** plan 1, task 2 with status 'pending'
- **WHEN** user runs `aud planning update-task 1 2 --status in_progress`
- **THEN** task status is updated to 'in_progress'
- **AND** output displays "Task 2 updated: status=in_progress"

#### Scenario: Assign task
- **GIVEN** plan 1, task 3 with assigned_to=NULL
- **WHEN** user runs `aud planning update-task 1 3 --assigned-to alice`
- **THEN** task.assigned_to is set to "alice"
- **AND** output displays "Task 3 updated: assigned_to=alice"

#### Scenario: Update both status and assignee
- **GIVEN** plan 1, task 1
- **WHEN** user runs `aud planning update-task 1 1 --status completed --assigned-to bob`
- **THEN** both status and assigned_to are updated
- **AND** output displays "Task 1 updated: status=completed, assigned_to=bob"

---

### Requirement: aud planning verify-task Command

The system SHALL provide `aud planning verify-task` command to verify task completion.

The system SHALL require plan_id and task_number arguments.

The system SHALL accept --verbose flag to display detailed violations.

The system SHALL accept --checkpoint flag to create code snapshot.

The system SHALL accept --output option to save verification report to file.

The system SHALL load task spec from planning.db.

The system SHALL call RefactorRuleEngine.evaluate() with loaded spec.

The system SHALL update task status to 'completed' if 0 violations found.

The system SHALL display violation count and status.

#### Scenario: Successful verification (0 violations)
- **GIVEN** plan 1, task 2 has spec expecting new function `cognito_login`
- **AND** code now contains `cognito_login` function
- **WHEN** user runs `aud planning verify-task 1 2`
- **THEN** RefactorRuleEngine.evaluate() is called
- **AND** evaluation returns 0 violations
- **AND** task status is updated to 'completed'
- **AND** output displays "Task 2 VERIFIED (0 violations)"

#### Scenario: Failed verification (violations found)
- **GIVEN** plan 1, task 3 has spec expecting removal of `auth0` imports
- **AND** code still contains `auth0` imports
- **WHEN** user runs `aud planning verify-task 1 3`
- **THEN** evaluation returns 5 violations
- **AND** task status remains 'in_progress' (not updated to completed)
- **AND** output displays "Task 3 INCOMPLETE (5 violations)"

#### Scenario: Verbose violation output
- **GIVEN** task verification returns 3 violations
- **WHEN** user runs `aud planning verify-task 1 2 --verbose`
- **THEN** output includes violation details:
  ```
  Violations:
    - src/auth.py:12: Found 'auth0' import (expected removal)
    - src/routes.py:45: Missing 'cognito_login' function
    - src/models.py:30: Found 'Auth0Client' reference
  ```

#### Scenario: Verification with checkpoint
- **GIVEN** task verification succeeds (0 violations)
- **WHEN** user runs `aud planning verify-task 1 2 --checkpoint`
- **THEN** task is marked completed
- **AND** code snapshot is created in code_snapshots table
- **AND** git diff is stored in code_diffs table
- **AND** output displays "Created checkpoint: abc123de"

#### Scenario: Verification without spec
- **GIVEN** plan 1, task 5 has spec_id=NULL (no spec)
- **WHEN** user runs `aud planning verify-task 1 5`
- **THEN** error "Task 5 has no verification spec"
- **AND** task status is not updated

#### Scenario: Save verification report
- **GIVEN** task verification completes (with or without violations)
- **WHEN** user runs `aud planning verify-task 1 2 --output report.json`
- **THEN** ProfileEvaluation is serialized to JSON
- **AND** JSON file is written to report.json
- **AND** output displays "Verification report saved: report.json"

---

### Requirement: aud planning archive Command

The system SHALL provide `aud planning archive` command to archive completed plans.

The system SHALL require plan_id argument.

The system SHALL create final code snapshot with all diffs.

The system SHALL update plan status to 'archived'.

The system SHALL prevent adding new tasks to archived plans.

#### Scenario: Archive completed plan
- **GIVEN** plan 1 with all tasks completed
- **WHEN** user runs `aud planning archive 1`
- **THEN** final snapshot is created with checkpoint_name="final-archive"
- **AND** plan.status is updated to 'archived'
- **AND** output displays "Plan 1 archived with final snapshot"

#### Scenario: Archive prevents new tasks
- **GIVEN** plan 1 is archived
- **WHEN** user runs `aud planning add-task 1 --title "New task"`
- **THEN** error "Cannot add tasks to archived plan 1"
- **AND** no task is created

#### Scenario: Archive incomplete plan (warning)
- **GIVEN** plan 1 with 2 tasks pending, 3 tasks completed
- **WHEN** user runs `aud planning archive 1`
- **THEN** warning displayed "Plan has 2 incomplete tasks"
- **AND** user is prompted to confirm archival
- **IF** user confirms
- **THEN** plan is archived anyway (allows archiving failed plans)

---

### Requirement: aud planning rewind Command

The system SHALL provide `aud planning rewind` command to show rollback instructions.

The system SHALL require plan_id and checkpoint_name arguments.

The system SHALL load snapshot from code_snapshots table.

The system SHALL display git commands to revert to snapshot state.

The system SHALL NOT execute git commands automatically (safety).

#### Scenario: Rewind to checkpoint
- **GIVEN** plan 1 has checkpoint "task-3-verified" with git_ref abc123
- **WHEN** user runs `aud planning rewind 1 task-3-verified`
- **THEN** output displays git commands:
  ```
  To revert to checkpoint 'task-3-verified':
    git checkout abc123
  Or to create branch:
    git checkout -b rewind-task-3 abc123
  ```
- **AND** git commands are NOT executed (user runs manually)

#### Scenario: Rewind non-existent checkpoint
- **GIVEN** plan 1 has no checkpoint named "task-99-verified"
- **WHEN** user runs `aud planning rewind 1 task-99-verified`
- **THEN** error "Checkpoint 'task-99-verified' not found for plan 1"
- **AND** no git commands displayed

#### Scenario: Rewind with file diffs
- **GIVEN** checkpoint "task-2-verified" has code_diffs for 3 files
- **WHEN** user runs `aud planning rewind 1 task-2-verified`
- **THEN** output includes affected files:
  ```
  Checkpoint 'task-2-verified' (abc123):
    Files affected:
      - src/auth.py (+12, -8)
      - src/routes.py (+5, -3)
      - src/models.py (+20, -15)
  ```

---

### Requirement: Error Handling and User Experience

The system SHALL follow "Zero Fallback Policy" - hard fail on errors.

The system SHALL display clear error messages for common mistakes.

The system SHALL validate inputs before database operations.

The system SHALL use Click's built-in validation for option types.

#### Scenario: Missing planning.db
- **GIVEN** user has not run `aud planning init`
- **WHEN** user runs `aud planning show 1`
- **THEN** error "Planning database not found. Run 'aud planning init' first."

#### Scenario: Invalid status value
- **GIVEN** user provides invalid status "unknown"
- **WHEN** user runs `aud planning update-task 1 1 --status unknown`
- **THEN** Click validation error "Invalid value for '--status': 'unknown' is not one of 'pending', 'in_progress', 'completed', 'failed'"

#### Scenario: Non-existent spec file
- **GIVEN** spec file `missing.yaml` does not exist
- **WHEN** user runs `aud planning add-task 1 --title "Test" --spec missing.yaml`
- **THEN** Click file validation error "Path 'missing.yaml' does not exist"

---

### Requirement: Help Text and Documentation

The system SHALL provide comprehensive help text for all commands.

The system SHALL include examples in command help text.

The system SHALL document all options with clear descriptions.

#### Scenario: Command help text
- **WHEN** user runs `aud planning verify-task --help`
- **THEN** output includes:
  - Description: "Verify task completion using YAML spec"
  - Arguments: plan_id (INTEGER), task_number (INTEGER)
  - Options: --verbose, --checkpoint, --output
  - Example: "aud planning verify-task 1 3 --verbose"
