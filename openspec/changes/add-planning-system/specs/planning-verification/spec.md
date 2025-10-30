# Planning Verification Capability

## ADDED Requirements

### Requirement: RefactorRuleEngine Integration

The system SHALL integrate with existing RefactorRuleEngine for task verification.

The system SHALL use RefactorProfile YAML format for task specs.

The system SHALL call RefactorRuleEngine.evaluate() without modifications to the engine.

The system SHALL pass repo_index.db path to RefactorRuleEngine (existing database).

The system SHALL return ProfileEvaluation with violations and expected_references.

#### Scenario: Verification using RefactorRuleEngine
- **GIVEN** task spec YAML in RefactorProfile format:
  ```yaml
  refactor_name: Update Login Routes
  rules:
    - id: remove-auth0
      match:
        identifiers: [auth0, Auth0Client]
      expect:
        identifiers: [CognitoIdentityClient]
  ```
- **WHEN** verify_task_spec() is called
- **THEN** RefactorProfile.load_from_string() parses YAML
- **AND** RefactorRuleEngine connects to repo_index.db
- **AND** engine.evaluate(profile) is called
- **AND** evaluation queries symbols, function_call_args, assignments tables
- **AND** ProfileEvaluation is returned with violation count

#### Scenario: Verification with 0 violations
- **GIVEN** spec expects `cognito_login` function
- **AND** repo_index.db contains symbol `cognito_login`
- **WHEN** verification runs
- **THEN** evaluation.total_violations() returns 0
- **AND** task status is updated to 'completed'

#### Scenario: Verification with violations
- **GIVEN** spec expects removal of `auth0` imports
- **AND** repo_index.db still contains `auth0` imports
- **WHEN** verification runs
- **THEN** evaluation.total_violations() returns 3 (3 files with auth0)
- **AND** violations list includes file paths and line numbers
- **AND** task status remains 'in_progress' (not completed)

---

### Requirement: YAML Spec Validation

The system SHALL validate YAML specs before storage in planning.db.

The system SHALL reject specs with invalid YAML syntax.

The system SHALL reject specs missing required RefactorProfile fields.

The system SHALL reject specs with invalid rule structures.

The system SHALL provide clear error messages for validation failures.

#### Scenario: Invalid YAML syntax
- **GIVEN** spec file contains malformed YAML (e.g., invalid indentation)
- **WHEN** user adds task with `--spec invalid.yaml`
- **THEN** yaml.YAMLError is raised
- **AND** error message shows line number of syntax error
- **AND** task is NOT created

#### Scenario: Missing required fields
- **GIVEN** spec YAML missing `refactor_name` field
- **WHEN** validation occurs
- **THEN** ValueError is raised "Missing 'refactor_name' in refactor profile"
- **AND** spec is NOT stored

#### Scenario: Invalid rule structure
- **GIVEN** spec YAML has rule without `id` field
- **WHEN** validation occurs
- **THEN** ValueError is raised "Each refactor rule must include 'id' and 'description'"
- **AND** spec is NOT stored

#### Scenario: Invalid severity value
- **GIVEN** rule has severity: "super-high" (not in valid set)
- **WHEN** validation occurs
- **THEN** ValueError is raised "Invalid severity 'super-high'"
- **AND** valid severities are listed: critical, high, medium, low

---

### Requirement: CodeQueryEngine Integration for Analogous Patterns

The system SHALL integrate with existing CodeQueryEngine for pattern discovery.

The system SHALL provide find_analogous_patterns() function for greenfield tasks.

The system SHALL support pattern types: api_route, function, component.

The system SHALL query repo_index.db via CodeQueryEngine methods.

The system SHALL return list of similar symbols/endpoints for reference.

#### Scenario: Find analogous API routes
- **GIVEN** user adding task "Add POST /products route" (greenfield - no /products exists)
- **AND** pattern_spec = {"type": "api_route", "method": "POST"}
- **WHEN** find_analogous_patterns(root, pattern_spec) is called
- **THEN** CodeQueryEngine.get_api_handlers("") is called
- **AND** results filtered to method="POST"
- **AND** returns list of all existing POST routes:
  ```
  [
    {"path": "/users", "method": "POST", "handler": "create_user", ...},
    {"path": "/orders", "method": "POST", "handler": "create_order", ...}
  ]
  ```

#### Scenario: Find analogous functions
- **GIVEN** user adding task "Implement validate_email function" (greenfield)
- **AND** pattern_spec = {"type": "function", "name": "validate"}
- **WHEN** find_analogous_patterns(root, pattern_spec) is called
- **THEN** CodeQueryEngine.find_symbol("validate") is called
- **AND** results filtered to type="function"
- **AND** returns list of existing validate_* functions for reference

#### Scenario: Find analogous components
- **GIVEN** user adding task "Create ProductCard component" (greenfield)
- **AND** pattern_spec = {"type": "component", "name": "Card"}
- **WHEN** find_analogous_patterns(root, pattern_spec) is called
- **THEN** CodeQueryEngine.get_component_tree("*Card") is called
- **AND** returns list of existing *Card components

#### Scenario: No analogous patterns found
- **GIVEN** pattern_spec for unique functionality (no similar code exists)
- **WHEN** find_analogous_patterns() is called
- **THEN** empty list is returned
- **AND** no error is raised (empty result is valid)

---

### Requirement: Verification Report Generation

The system SHALL generate verification reports in JSON format.

The system SHALL serialize ProfileEvaluation to JSON.

The system SHALL include violations, expected_references, and rule details.

The system SHALL support saving reports to file with --output option.

#### Scenario: JSON report structure
- **GIVEN** verification completes with 2 violations
- **WHEN** report is generated
- **THEN** JSON includes:
  ```json
  {
    "profile": {
      "refactor_name": "Update Login Routes",
      "rule_count": 3
    },
    "summary": {
      "total_rules": 3,
      "total_violations": 2
    },
    "rules": [
      {
        "rule_id": "remove-auth0",
        "violations": [
          {"file": "src/auth.py", "line": 12, "match": "auth0"}
        ],
        "expected_references": [],
        "status": "needs_migration"
      }
    ]
  }
  ```

#### Scenario: Save report to file
- **GIVEN** verification completes
- **WHEN** user runs verify-task with `--output report.json`
- **THEN** JSON report is written to report.json
- **AND** file contains valid JSON
- **AND** file is readable by external tools

---

### Requirement: Snapshot Integration with Verification

The system SHALL support creating snapshots during verification.

The system SHALL create snapshot only if --checkpoint flag is set.

The system SHALL create snapshot only if verification succeeds (0 violations).

The system SHALL store git diff in code_diffs table.

The system SHALL link snapshot to verified task (snapshot.task_id = task.id).

#### Scenario: Checkpoint on successful verification
- **GIVEN** task verification succeeds (0 violations)
- **AND** --checkpoint flag is set
- **WHEN** verification completes
- **THEN** code snapshot is created via snapshots.create_snapshot()
- **AND** snapshot.task_id references verified task
- **AND** snapshot.checkpoint_name = "task-{task_number}-verified"
- **AND** git diffs are stored in code_diffs table
- **AND** output displays "Created checkpoint: abc123de"

#### Scenario: No checkpoint on failed verification
- **GIVEN** task verification fails (3 violations)
- **AND** --checkpoint flag is set
- **WHEN** verification completes
- **THEN** no snapshot is created (verification failed)
- **AND** output displays "Skipped checkpoint (verification incomplete)"

#### Scenario: No checkpoint without flag
- **GIVEN** task verification succeeds (0 violations)
- **AND** --checkpoint flag is NOT set
- **WHEN** verification completes
- **THEN** no snapshot is created (optional feature)
- **AND** task is still marked completed

---

### Requirement: Transitive Verification Queries

The system SHALL support transitive queries via RefactorRuleEngine.

The system SHALL query symbols, function_call_args, assignments, api_endpoints tables.

The system SHALL support pattern specs with identifiers, expressions, sql_tables, api_routes.

The system SHALL respect scope filters (include/exclude file patterns).

#### Scenario: Identifier matching across files
- **GIVEN** spec with match.identifiers = ["auth0"]
- **AND** repo_index.db has 5 files with "auth0" symbols
- **WHEN** verification runs
- **THEN** all 5 files are found via symbols table query
- **AND** violations list includes all 5 file paths

#### Scenario: Expression matching in assignments
- **GIVEN** spec with match.expressions = ["Auth0Client()"]
- **AND** repo_index.db has 3 assignments with "Auth0Client()"
- **WHEN** verification runs
- **THEN** all 3 assignments are found via assignments table query
- **AND** violations include file paths and line numbers

#### Scenario: API route matching
- **GIVEN** spec with expect.api_routes = ["/auth/cognito"]
- **AND** repo_index.db has 0 routes matching "/auth/cognito"
- **WHEN** verification runs
- **THEN** violation is reported: "Expected API route '/auth/cognito' not found"

#### Scenario: Scope filtering
- **GIVEN** spec with scope.include = ["src/auth/*"]
- **AND** repo_index.db has "auth0" symbols in src/auth/ and src/routes/
- **WHEN** verification runs
- **THEN** only src/auth/* files are checked
- **AND** src/routes/ violations are excluded (outside scope)

---

### Requirement: Verification Error Handling

The system SHALL follow "Zero Fallback Policy" for verification errors.

The system SHALL propagate RefactorRuleEngine exceptions without catching.

The system SHALL propagate CodeQueryEngine exceptions without catching.

The system SHALL fail hard if repo_index.db is missing or malformed.

The system SHALL provide clear error messages for database errors.

#### Scenario: Missing repo_index.db
- **GIVEN** .pf/repo_index.db does not exist
- **WHEN** verify-task is called
- **THEN** FileNotFoundError is raised
- **AND** error message: "Database not found: .pf/repo_index.db. Run 'aud index' first."
- **AND** task status is NOT updated

#### Scenario: RefactorRuleEngine query failure
- **GIVEN** spec queries table that doesn't exist (schema mismatch)
- **WHEN** RefactorRuleEngine.evaluate() runs
- **THEN** sqlite3.OperationalError is propagated
- **AND** error message shows SQL error
- **AND** verification does NOT continue with partial results

#### Scenario: CodeQueryEngine query failure
- **GIVEN** find_analogous_patterns() queries missing table
- **WHEN** CodeQueryEngine method is called
- **THEN** sqlite3.OperationalError is propagated
- **AND** error message shows SQL error
- **AND** empty list is NOT returned as graceful degradation

---

### Requirement: Performance Considerations

The system SHALL complete verification in <1 second for typical specs.

The system SHALL leverage existing indexes on repo_index.db.

The system SHALL avoid full table scans where possible.

The system SHALL limit transitive queries to prevent infinite loops (existing RefactorRuleEngine behavior).

#### Scenario: Fast verification query
- **GIVEN** spec with 3 rules querying symbols table
- **AND** repo_index.db has 33k symbol rows (typical project)
- **AND** symbols.name is indexed
- **WHEN** verification runs
- **THEN** query uses indexed lookup (not full scan)
- **AND** verification completes in <1 second

#### Scenario: Multiple pattern queries
- **GIVEN** spec with 10 rules (identifiers + expressions + api_routes)
- **WHEN** verification runs
- **THEN** RefactorRuleEngine executes 10 queries in parallel (existing behavior)
- **AND** total verification time <2 seconds

---

### Requirement: Compatibility with Existing Refactor System

The system SHALL use same YAML format as `aud refactor` command.

The system SHALL reuse RefactorProfile, RefactorRule, PatternSpec dataclasses.

The system SHALL NOT modify RefactorRuleEngine code.

The system SHALL allow specs to be used for both planning AND refactor detection.

#### Scenario: Cross-compatible YAML spec
- **GIVEN** YAML spec created for planning system
- **WHEN** user runs `aud refactor --file same_spec.yaml`
- **THEN** RefactorRuleEngine loads spec successfully
- **AND** spec works for both planning verification AND refactor detection

#### Scenario: Existing refactor spec for planning
- **GIVEN** existing refactor spec from `aud refactor` command
- **WHEN** user adds spec to planning task with `--spec existing_spec.yaml`
- **THEN** spec is loaded successfully
- **AND** no modifications needed to YAML

---

### Requirement: Verification State Tracking

The system SHALL track verification results in planning.db.

The system SHALL store verification timestamp with completed tasks.

The system SHALL allow re-verification of completed tasks (idempotent).

The system SHALL update task.completed_at only when verification succeeds.

#### Scenario: First verification success
- **GIVEN** task status 'in_progress', completed_at=NULL
- **WHEN** verification succeeds (0 violations)
- **THEN** task status updated to 'completed'
- **AND** completed_at set to current timestamp

#### Scenario: Re-verification of completed task
- **GIVEN** task status 'completed', completed_at=2025-10-30T12:00:00Z
- **WHEN** user runs verify-task again
- **THEN** verification runs again (idempotent)
- **AND** if still 0 violations: status remains 'completed'
- **AND** if new violations found: status updated to 'failed'
- **AND** completed_at cleared to NULL

#### Scenario: Verification regression detection
- **GIVEN** task previously verified (0 violations) on 2025-10-30
- **AND** code changed since then (new commit added auth0 import)
- **WHEN** user re-runs verify-task
- **THEN** verification fails (1 violation)
- **AND** task status updated to 'failed'
- **AND** output displays "REGRESSION: Task 3 previously completed but now has 1 violation"
