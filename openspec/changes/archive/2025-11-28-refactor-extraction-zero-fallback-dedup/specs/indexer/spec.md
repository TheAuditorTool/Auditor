# Indexer Capability Spec Delta

## ADDED Requirements

### Requirement: Extraction Duplicate Detection
The extraction pipeline SHALL detect duplicate entities and fail immediately with an actionable error message.

Duplicates are identified by unique identity keys:
- Assignments: `(file_path, line, target_var)`
- Function Returns: `(file_path, line, function_name)`
- Environment Variable Usage: `(file_path, line, var_name, access_type)`
- Files: `(path,)`
- Nginx Configs: `(file_path, block_type, block_context)`

When a duplicate is detected, the system MUST raise a `ValueError` with:
- Error type: "EXTRACTOR BUG"
- File path where duplicate occurred
- Identity key that was duplicated
- Reference to the fix pattern (`typescript_impl.py:535-545`)

#### Scenario: Duplicate assignment detected
- **WHEN** an extractor produces two assignments with the same `(file_path, line, target_var)` identity
- **THEN** the storage layer raises `ValueError` with message containing "EXTRACTOR BUG: Duplicate assignment detected"
- **AND** the error message includes the file path and identity key
- **AND** the pipeline halts (no silent data loss)

#### Scenario: Duplicate function return detected
- **WHEN** an extractor produces two function returns with the same `(file_path, line, function_name)` identity
- **THEN** the storage layer raises `ValueError` with message containing "EXTRACTOR BUG: Duplicate function_return detected"
- **AND** the error message includes the file path and identity key

#### Scenario: Duplicate env_var_usage detected
- **WHEN** an extractor produces two env_var_usage records with the same `(file_path, line, var_name, access_type)` identity
- **THEN** the storage layer raises `ValueError` with message containing "EXTRACTOR BUG: Duplicate env_var_usage detected"
- **AND** the error message includes the file path and identity key

#### Scenario: No duplicates present
- **WHEN** an extractor produces entities with unique identity keys
- **THEN** all entities are stored successfully
- **AND** no errors are raised

---

### Requirement: Type Validation at Storage Boundary
The storage layer SHALL validate entity types before database insertion and fail immediately on type violations.

Required type constraints:
- `symbol.name`: non-empty string
- `symbol.type`: non-empty string
- `symbol.line`: integer >= 1
- `symbol.col`: integer >= 0
- `assignment.line`: integer >= 1
- `assignment.target_var`: non-empty string
- `assignment.source_expr`: string
- `assignment.in_function`: string
- `call.line`: integer >= 1
- `call.caller_function`: string
- `call.callee_function`: non-empty string
- `return.line`: integer >= 1
- `return.function_name`: string
- `return.return_expr`: string

When a type violation is detected, the system MUST raise a `TypeError` with:
- Error type: "EXTRACTOR BUG"
- Field name that failed validation
- Expected type
- Actual value received
- File path context

#### Scenario: Symbol with invalid name type
- **WHEN** an extractor produces a symbol where `name` is not a string or is empty
- **THEN** the storage layer raises `TypeError` with message containing "Symbol.name must be non-empty str"
- **AND** the error message includes the actual value received

#### Scenario: Symbol with invalid line type
- **WHEN** an extractor produces a symbol where `line` is not an integer or is less than 1
- **THEN** the storage layer raises `TypeError` with message containing "Symbol.line must be int >= 1"
- **AND** the error message includes the actual value received

#### Scenario: Assignment with invalid target_var
- **WHEN** an extractor produces an assignment where `target_var` is not a string or is empty
- **THEN** the storage layer raises `TypeError` with message containing "Assignment.target_var must be non-empty str"

#### Scenario: Function call with invalid callee_function
- **WHEN** an extractor produces a function call where `callee_function` is not a string or is empty
- **THEN** the storage layer raises `TypeError` with message containing "Call.callee_function must be non-empty str"

#### Scenario: All types valid
- **WHEN** an extractor produces entities with correct types for all required fields
- **THEN** entities are stored successfully
- **AND** no type errors are raised

---

### Requirement: Foreign Key Enforcement
The database layer SHALL enforce foreign key constraints to prevent orphaned records.

Foreign key relationships enforced:
- `assignment_sources` references `assignments`
- `function_return_sources` references `function_returns`
- All tables referencing `files` (implicit via file path)

When a foreign key violation occurs, the system MUST raise a `ValueError` with:
- Error type: "ORPHAN DATA ERROR"
- Table name where violation occurred
- Suggestion to check flush order

The flush order MUST ensure parent tables are populated before child tables:
1. `files`, `config_files` (no FK dependencies)
2. `refs`, `symbols`, `class_properties` (children of files)
3. `assignments`, `function_call_args`, `function_returns` (depend on symbols)
4. `assignment_sources`, `function_return_sources` (junction tables)

#### Scenario: FK violation on junction table insert
- **WHEN** the database attempts to insert an `assignment_sources` record referencing a non-existent `assignments` row
- **THEN** the database raises `ValueError` with message containing "ORPHAN DATA ERROR"
- **AND** the error message suggests checking flush order

#### Scenario: Correct insertion order
- **WHEN** parent tables are flushed before child tables
- **THEN** all inserts succeed
- **AND** no FK violations occur

#### Scenario: Unique constraint violation
- **WHEN** the database attempts to insert a duplicate row (same primary key)
- **THEN** the database raises `ValueError` with message containing "DATABASE INTEGRITY ERROR"
- **AND** the error message suggests checking storage layer deduplication

---

### Requirement: No Silent Data Loss
The extraction pipeline SHALL NOT silently skip, filter, or deduplicate data.

Prohibited patterns:
- `if key not in seen: ... else: continue` (silent skip)
- `if not any(item[0] == x for item in batch):` (conditional append)
- `try: ... except: return []` (silent exception swallowing)
- `if table_name in existing_tables:` (table existence checks)

Every data anomaly MUST result in an exception that halts the pipeline.

#### Scenario: Extractor produces invalid data
- **WHEN** an extractor returns data that violates type or uniqueness constraints
- **THEN** the pipeline halts with an exception
- **AND** no partial data is committed to the database
- **AND** the error message identifies the root cause

#### Scenario: Database constraint violation
- **WHEN** a database INSERT violates a UNIQUE or FOREIGN KEY constraint
- **THEN** the pipeline halts with an exception
- **AND** the error message is actionable (not raw SQL error)

---

## REMOVED Requirements

### Requirement: Deduplication in Storage Layer
**Reason**: Deduplication masks extractor bugs by silently dropping data. This causes incomplete analysis results.

**Migration**: Extractors must be fixed to not produce duplicates. Use language-appropriate `visited_nodes` patterns:
- TypeScript/JS: `typescript_impl.py:535-545` - `node.get("line"), node.get("kind")`
- Python: `node.lineno, type(node).__name__`
- Rust/HCL: `node.start_point[0], node.type`

### Requirement: Deduplication in Database Layer
**Reason**: The `add_file` method's `if not any(...)` check is a fallback that hides upstream bugs.

**Migration**: Symlink/junction point handling belongs in FileWalker, not database layer.

### Requirement: Generated Validators
**Reason**: `generated_validators.py` contains decorator-based validators that are never called. Dead code.

**Migration**: Explicit `isinstance` checks in `_store_*` methods replace the unused validators.
