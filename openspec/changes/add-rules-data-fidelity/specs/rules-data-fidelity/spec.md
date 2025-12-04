# Capability: Rules Data Fidelity

Data access layer for TheAuditor rules with schema validation and fidelity tracking.

## ADDED Requirements

### Requirement: Composable Query Builder

The system SHALL provide a composable query builder class `Q` that constructs SQL queries with schema validation.

The query builder MUST:
1. Accept a table name on construction and validate it exists in `TABLES`
2. Provide chainable methods: `.select()`, `.where()`, `.join()`, `.with_cte()`, `.order_by()`, `.limit()`, `.group_by()`
3. Validate all column references against `TABLES` schema at `.build()` time
4. Return a tuple of `(sql_string, params_list)` from `.build()`
5. Raise `ValueError` with detailed message when validation fails
6. Support CTE (Common Table Expression) queries via `.with_cte(name, subquery)`
7. Support automatic foreign key detection for joins when `on` parameter is omitted
8. Provide `Q.raw(sql, params)` escape hatch for edge cases

#### Scenario: Single table SELECT with validation

- **WHEN** user creates `Q("symbols").select("name", "line").where("type = ?", "function").build()`
- **THEN** returns `("SELECT name, line FROM symbols WHERE type = ?", ["function"])`

#### Scenario: Unknown table raises error

- **WHEN** user creates `Q("nonexistent_table")`
- **THEN** raises `ValueError` with message containing "Unknown table: nonexistent_table"

#### Scenario: Unknown column raises error at build time

- **WHEN** user creates `Q("symbols").select("invalid_column").build()`
- **THEN** raises `ValueError` with message containing "Unknown column 'invalid_column'" and listing valid columns

#### Scenario: JOIN with explicit on condition (list of tuples)

- **WHEN** user creates `Q("function_call_args").select("file", "line").join("assignments", on=[("file", "file")]).build()`
- **THEN** returns SQL with `INNER JOIN assignments ON function_call_args.file = assignments.file`

#### Scenario: JOIN with explicit on condition (raw string)

- **WHEN** user creates `Q("function_call_args").join("assignments", on="function_call_args.file = assignments.file AND function_call_args.line < assignments.line")`
- **THEN** uses the string verbatim in ON clause without column validation (escape hatch for complex conditions)

#### Scenario: JOIN with FK auto-detection

- **WHEN** user creates `Q("base_table").join("related_table")` where FK relationship exists in schema
- **THEN** automatically determines join condition from `ForeignKey` metadata in `TABLES[base_table].foreign_keys`

#### Scenario: CTE query construction

- **WHEN** user creates:
  ```python
  sub = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")
  Q("function_call_args").with_cte("tainted", sub).select("file", "line").join("tainted", on=[("file", "file")]).build()
  ```
- **THEN** returns SQL beginning with `WITH tainted AS (SELECT file, target_var FROM assignments WHERE source_expr LIKE ?)`

#### Scenario: Multiple WHERE conditions ANDed together

- **WHEN** user creates `Q("symbols").where("type = ?", "function").where("name LIKE ?", "%test%").build()`
- **THEN** returns SQL with `WHERE type = ? AND name LIKE ?` and params `["function", "%test%"]`

#### Scenario: Raw SQL escape hatch

- **WHEN** user creates `Q.raw("SELECT * FROM custom WHERE x = ?", ["value"])`
- **THEN** returns `("SELECT * FROM custom WHERE x = ?", ["value"])` without validation
- **AND** logs warning "Q.raw() bypassing validation: SELECT * FROM custom..."

---

### Requirement: Rule Result with Fidelity Manifest

The system SHALL provide a `RuleResult` dataclass that wraps rule findings with a fidelity manifest.

The RuleResult MUST:
1. Contain `findings: list[StandardFinding]`
2. Contain `manifest: dict` with fidelity tracking data
3. Be returnable from any rule function as alternative to bare list

The manifest MUST track:
- `rule_name`: Name of the executed rule
- `items_scanned`: Count of items processed (rows returned from queries)
- `tables_queried`: List of table names accessed
- `queries_executed`: Count of queries run
- `execution_time_ms`: Milliseconds elapsed

#### Scenario: Rule returns RuleResult with manifest

- **WHEN** rule function returns `RuleResult(findings=[...], manifest={"items_scanned": 100, ...})`
- **THEN** orchestrator extracts findings for output AND stores manifest for verification

#### Scenario: Backward compatibility with list return

- **WHEN** rule function returns `list[StandardFinding]` (old style)
- **THEN** orchestrator wraps in `RuleResult` with empty manifest for backward compatibility

---

### Requirement: Rule Database Helper

The system SHALL provide a `RuleDB` helper class that manages database connections and tracks fidelity.

The RuleDB MUST:
1. Accept `db_path: str` on construction
2. Open sqlite3 connection on construction
3. Provide `.query(q: Q)` method that builds query, executes, and returns results as `list[tuple]`
4. Provide `.execute(sql, params)` method for raw queries (escape hatch)
5. Track all queries in internal `RuleManifest`
6. Provide `.get_manifest()` method returning manifest dict
7. Provide `.close()` method to close connection
8. Support context manager protocol (`with RuleDB(path) as db:`)

#### Scenario: Query execution with tracking

- **WHEN** user calls `db.query(Q("symbols").select("name").where("type = ?", "function"))`
- **THEN** executes query against database AND increments `queries_executed` in manifest AND adds "symbols" to `tables_queried`

#### Scenario: Items scanned tracks row count

- **WHEN** `db.query(Q("symbols").select("name"))` returns 50 rows
- **THEN** `items_scanned` in manifest increments by 50 (count of rows returned by `cursor.fetchall()`)

#### Scenario: Context manager cleanup

- **WHEN** user uses `with RuleDB(path) as db: ...`
- **THEN** connection is automatically closed on exit, even if exception raised

#### Scenario: Manifest reflects all activity

- **WHEN** user executes 3 queries against 2 tables, processing 500 rows total
- **THEN** `db.get_manifest()` returns `{"queries_executed": 3, "tables_queried": ["table1", "table2"], "items_scanned": 500, ...}`

---

### Requirement: Fidelity Verification

The system SHALL provide fidelity verification that compares rule manifests against expected behavior.

The verification MUST:
1. Check `items_scanned > 0` unless target table is empty
2. Log warnings for fidelity mismatches
3. In strict mode (env `THEAUDITOR_FIDELITY_STRICT=1`), raise `FidelityError`
4. Return `(passed: bool, errors: list[str])` tuple

Expected values are computed by the orchestrator:
- `table_row_count`: Count from `SELECT COUNT(*) FROM {primary_table}` (if rule METADATA specifies `primary_table`)
- `expected_tables`: List from rule METADATA (if specified)
- If no METADATA, verification only checks `items_scanned > 0`

#### Scenario: Fidelity pass - items scanned

- **WHEN** rule manifest shows `items_scanned: 100` for non-empty table
- **THEN** verification passes with `(True, [])`

#### Scenario: Fidelity fail - zero items scanned

- **WHEN** rule manifest shows `items_scanned: 0` but computed `table_row_count` is 500
- **THEN** verification fails with `(False, ["Rule scanned 0 items but table has 500 rows"])`

#### Scenario: Strict mode raises exception

- **WHEN** `THEAUDITOR_FIDELITY_STRICT=1` AND rule fails fidelity verification
- **THEN** raises `FidelityError` with error messages

#### Scenario: Warn mode logs warning

- **WHEN** `THEAUDITOR_FIDELITY_STRICT=0` (default) AND rule fails fidelity verification
- **THEN** logs warning with error messages AND returns `(False, errors)` without raising

---

### Requirement: Orchestrator Integration

The rules orchestrator SHALL integrate with the fidelity system.

The orchestrator MUST:
1. Accept `RuleResult` return type from rules (in addition to `list`)
2. Call fidelity verification after each rule execution
3. Aggregate manifests for debugging output
4. Respect strict mode configuration
5. Store fidelity failures in `self._fidelity_failures: list[tuple[str, list[str]]]`

Integration point: `theauditor/rules/orchestrator.py:490` inside `_execute_rule()` method.

#### Scenario: RuleResult handling

- **WHEN** rule returns `RuleResult` object
- **THEN** orchestrator extracts `.findings` for output AND passes `.manifest` to fidelity verification

#### Scenario: Legacy list handling

- **WHEN** rule returns `list[StandardFinding]` (old style)
- **THEN** orchestrator processes findings normally AND skips fidelity verification (no manifest)

#### Scenario: Manifest aggregation

- **WHEN** `run_all_rules()` completes
- **THEN** combined manifest available via `orchestrator.get_aggregated_manifests()` showing all rules executed, total items scanned, total queries

---

### Requirement: Zero Fallback Enforcement

The query builder SHALL enforce zero fallback policy.

The builder MUST:
1. Never attempt alternative queries on failure
2. Never check if tables exist before querying (validate against `TABLES` dict, not live DB)
3. Raise immediately on any validation error
4. Provide single code path - no retry logic

#### Scenario: Invalid query fails immediately

- **WHEN** `Q("nonexistent").select("col").build()` is called
- **THEN** raises `ValueError` immediately, no fallback attempted

#### Scenario: No table existence checks against live DB

- **WHEN** `Q("symbols")` is constructed
- **THEN** validates table name against in-memory `TABLES` dict only, never queries `sqlite_master`
