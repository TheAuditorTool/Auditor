# Tasks: Add Polyglot Planning Support

**Total Tasks:** 108
**Completed:** 0
**Blocked:**
- Tasks 3.2, 4.4-4.6, 5.3-5.6 (waiting on rust_attributes - Task 0.3)
- Tasks 1.x, 6.x (waiting on unified table population - Task 0.5)

**Unblocked (2025-12-03):**
- Tasks 3.1, 4.1-4.3, 5.1-5.2 (Go route extraction now implemented)

---

## 0. Verification & Blockers (Pre-Implementation Checks)

### 0.1 Verify Go/Rust/Bash symbols in database
- [ ] 0.1.1 Run verification query for Go symbols
  ```sql
  SELECT f.ext, COUNT(*) FROM symbols s JOIN files f ON s.path = f.path
  WHERE f.ext IN ('.go', '.rs', '.sh') GROUP BY f.ext
  ```
- [ ] 0.1.2 Document results in verification.md

### 0.2 ~~Verify `go_routes` table has data~~ DONE (2025-12-03)
- [x] 0.2.1 Run verification query
  ```sql
  SELECT framework, COUNT(*) FROM go_routes GROUP BY framework
  -- Result: gin: 5 routes
  ```
- [x] 0.2.2 Go extractor IS populating routes via `_detect_routes()` at `go.py:106-131`

### 0.3 **BLOCKER:** Implement rust_attributes table
**Problem:** `rust_macro_invocations` only captures macro calls like `println!()`.
Route attributes like `#[get("/users")]` are `attribute_item` nodes in tree-sitter,
NOT `macro_invocation` nodes. Tasks 3.2, 4.4-4.6, 5.3-5.6 depend on this.

- [ ] 0.3.1 Add `RUST_ATTRIBUTES` TableSchema to `rust_schema.py`
  ```python
  RUST_ATTRIBUTES = TableSchema(
      name="rust_attributes",
      columns=[
          Column("file_path", "TEXT", nullable=False),
          Column("line", "INTEGER", nullable=False),
          Column("attribute_name", "TEXT", nullable=False),
          Column("args", "TEXT"),
          Column("target_type", "TEXT"),
          Column("target_name", "TEXT"),
          Column("target_line", "INTEGER"),
      ],
      primary_key=["file_path", "line"],
      indexes=[
          ("idx_rust_attrs_name", ["attribute_name"]),
          ("idx_rust_attrs_target", ["target_type", "target_name"]),
      ],
  )
  ```
- [ ] 0.3.2 Add `RUST_ATTRIBUTES` to `RUST_TABLES` dict
- [ ] 0.3.3 Add `extract_rust_attributes()` function to `rust_impl.py`
- [ ] 0.3.4 Wire extraction into `RustExtractor.extract()` method
- [ ] 0.3.5 Add storage handler in indexer pipeline
- [ ] 0.3.6 Run `aud full --offline` and verify table is populated
- [ ] 0.3.7 Verify with query:
  ```sql
  SELECT attribute_name, COUNT(*) FROM rust_attributes
  WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route', 'derive')
  GROUP BY attribute_name
  ```

### 0.4 Verify graph edges for Go/Rust/Bash
- [ ] 0.4.1 Run `aud graph build`
- [ ] 0.4.2 Verify Go import edges:
  ```sql
  SELECT COUNT(*) FROM edges WHERE source LIKE '%.go' AND graph_type = 'import'
  ```
- [ ] 0.4.3 Verify Rust use edges:
  ```sql
  SELECT COUNT(*) FROM edges WHERE source LIKE '%.rs' AND graph_type = 'import'
  ```
- [ ] 0.4.4 Verify Bash source edges:
  ```sql
  SELECT COUNT(*) FROM edges WHERE source LIKE '%.sh' AND graph_type = 'import'
  ```

### 0.5 **BLOCKER:** Populate unified `symbols` and `refs` tables for Go/Rust/Bash

**Problem:** Go/Rust/Bash extractors populate their language-specific tables but NOT the
unified `symbols` and `refs` tables. This breaks:
- Blueprint naming conventions (queries `symbols` table)
- Graph edge building (queries `refs` table)

**Verification results:**
```
symbols table:   .py=52321, .ts=7206, .js=5369, .go=0, .rs=0, .sh=0
refs table:      .py=8117,  .ts=465,  .js=250,  .go=0, .rs=0, .sh=0
```

**Data EXISTS in language-specific tables:**
- `go_imports`: 146 rows
- `go_functions`: populated (includes 3 main functions)
- `rust_use_statements`: 203 rows
- `rust_functions`: populated (includes 3 main functions)
- `bash_sources`: 10 rows
- `bash_functions`: 37 rows

**Solution:** Modify extractors to ALSO populate unified tables during indexing.

- [ ] 0.5.1 Identify where Python/JS extractors populate `symbols` table
- [ ] 0.5.2 Add `symbols` population to Go extractor
  - Map `go_functions` -> `symbols` (type='function')
  - Map `go_structs` -> `symbols` (type='class')
  - Map `go_interfaces` -> `symbols` (type='class')
- [ ] 0.5.3 Add `symbols` population to Rust extractor
  - Map `rust_functions` -> `symbols` (type='function')
  - Map `rust_structs` -> `symbols` (type='class')
  - Map `rust_enums` -> `symbols` (type='class')
  - Map `rust_traits` -> `symbols` (type='class')
- [ ] 0.5.4 Add `symbols` population to Bash extractor
  - Map `bash_functions` -> `symbols` (type='function')
- [ ] 0.5.5 Add `refs` population to Go extractor
  - Map `go_imports` -> `refs` (kind='import')
- [ ] 0.5.6 Add `refs` population to Rust extractor
  - Map `rust_use_statements` -> `refs` (kind='import')
- [ ] 0.5.7 Add `refs` population to Bash extractor
  - Map `bash_sources` -> `refs` (kind='import')
- [ ] 0.5.8 Run `aud full --offline` and verify unified tables populated
- [ ] 0.5.9 Verify with queries:
  ```sql
  SELECT f.ext, COUNT(*) FROM symbols s JOIN files f ON s.path = f.path
  WHERE f.ext IN ('.go', '.rs', '.sh') GROUP BY f.ext;

  SELECT
    CASE WHEN src LIKE '%.go' THEN '.go'
         WHEN src LIKE '%.rs' THEN '.rs'
         WHEN src LIKE '%.sh' THEN '.sh'
    END as ext, COUNT(*)
  FROM refs WHERE src LIKE '%.go' OR src LIKE '%.rs' OR src LIKE '%.sh'
  GROUP BY ext;
  ```
- [ ] 0.5.10 Run `aud graph build` and verify edges created for Go/Rust/Bash

---

## 1. Blueprint Naming Conventions

**DEPENDS ON:** Task 0.5 (unified table population) for `symbols` table queries

### 1.1 Modify SQL query in `_get_naming_conventions()`
**File:** `theauditor/commands/blueprint.py:335-375`

Add these CASE clauses after TypeScript (line 371):

- [ ] 1.1.1 Add Go function CASE clauses (4 lines: snake, camel, pascal, total)
- [ ] 1.1.2 Add Go struct CASE clauses (3 lines: snake, pascal, total)
- [ ] 1.1.3 Add Rust function CASE clauses (4 lines)
- [ ] 1.1.4 Add Rust struct CASE clauses (3 lines)
- [ ] 1.1.5 Add Bash function CASE clauses (3 lines: snake, screaming, total)

### 1.2 Extend conventions dict return value
**File:** `theauditor/commands/blueprint.py:379-392`

Current row indices end at 23. New indices:
- Go: rows 24-30
- Rust: rows 31-37
- Bash: rows 38-40

- [ ] 1.2.1 Add `"go"` dict with functions and structs keys
- [ ] 1.2.2 Add `"rust"` dict with functions and structs keys
- [ ] 1.2.3 Add `"bash"` dict with functions key only
- [ ] 1.2.4 Create `_build_pattern_result_bash()` helper for snake/screaming pattern

### 1.3 Manual test
- [ ] 1.3.1 Run `aud blueprint --structure` on this repo
- [ ] 1.3.2 Verify Go/Rust/Bash sections appear in output
- [ ] 1.3.3 Verify counts match expectations (cross-check with symbols table)

---

## 2. Blueprint Dependencies

> **Note:** Tasks 2.1-2.4 overlap with `add-polyglot-package-managers` proposal. Coordinate or defer.

### 2.1 Add cargo_package_configs schema
**File:** `theauditor/indexer/schemas/infrastructure_schema.py`

- [ ] 2.1.1 Add `CARGO_PACKAGE_CONFIGS` TableSchema definition
- [ ] 2.1.2 Add to `INFRASTRUCTURE_TABLES` dict

### 2.2 Add go_module_configs schema
**File:** `theauditor/indexer/schemas/go_schema.py`

- [ ] 2.2.1 Add `GO_MODULE_CONFIGS` TableSchema definition
- [ ] 2.2.2 Add to `GO_TABLES` dict

### 2.3 Wire Cargo.toml parsing to database storage
**File:** `theauditor/framework_detector.py` or new `cargo_parser.py`

- [ ] 2.3.1 Locate existing Cargo.toml parsing (deps.py or framework_detector.py)
- [ ] 2.3.2 Add storage handler to write to `cargo_package_configs` table
- [ ] 2.3.3 Wire into `aud full` indexing phase
- [ ] 2.3.4 Verify with query:
  ```sql
  SELECT file_path, package_name, version FROM cargo_package_configs
  ```

### 2.4 Wire go.mod parsing to database storage
**File:** `theauditor/manifest_parser.py` or new `gomod_parser.py`

- [ ] 2.4.1 Verify go.mod parsing exists (or add if missing)
- [ ] 2.4.2 Add storage handler to write to `go_module_configs`
- [ ] 2.4.3 Wire into `aud full` indexing phase
- [ ] 2.4.4 Verify with query:
  ```sql
  SELECT file_path, module_path, go_version FROM go_module_configs
  ```

### 2.5 Modify `_get_dependencies()` to query new tables
**File:** `theauditor/commands/blueprint.py:1264-1366`

- [ ] 2.5.1 Add Cargo query block after pip query
- [ ] 2.5.2 Add Go modules query block after Cargo
- [ ] 2.5.3 Update `by_manager` dict with "cargo" and "go" keys
- [ ] 2.5.4 Update workspaces list with Cargo/Go entries

### 2.6 Manual test
- [ ] 2.6.1 Run `aud full --offline` on a repo with Cargo.toml
- [ ] 2.6.2 Run `aud blueprint --deps` and verify cargo deps appear
- [ ] 2.6.3 Repeat for go.mod if available

---

## 3. Explain Framework Info

### 3.1 Add Go handler detection
**File:** `theauditor/context/query.py:1439-1478`

- [ ] 3.1.1 Add `if ext == "go":` block after Python/JS detection
- [ ] 3.1.2 Query `go_routes` table for routes in file
- [ ] 3.1.3 Query `go_func_params` for handler patterns if no routes found
- [ ] 3.1.4 Populate result["framework"] and result["routes"]

### 3.2 Add Rust handler detection
**File:** `theauditor/context/query.py:1439-1478`

**DEPENDS ON:** Task 0.3 (rust_attributes table must be implemented first)

- [ ] 3.2.1 Complete task 0.3 (rust_attributes implementation) first
- [ ] 3.2.2 Add `if ext == "rs":` block after Go detection
- [ ] 3.2.3 Query `rust_attributes` joined with `rust_functions`
- [ ] 3.2.4 Filter by route attribute names (get, post, put, delete, route)
- [ ] 3.2.5 Populate result["framework"] and result["handlers"]

### 3.3 Manual test
- [ ] 3.3.1 Run `aud explain <go_handler.go>` and verify routes shown
- [ ] 3.3.2 Run `aud explain <rust_handler.rs>` and verify handlers shown
- [ ] 3.3.3 Run `aud explain <file.go>` with no handlers, verify no error

---

## 4. Deadcode Entry Point Detection

### 4.1 Add Go entry point detection
**File:** `theauditor/context/deadcode_graph.py:255-268`

- [ ] 4.1.1 Add Go routes query to `_find_framework_entry_points()`:
  ```python
  cursor.execute("SELECT DISTINCT file FROM go_routes")
  entry_points.update(row[0] for row in cursor.fetchall())
  ```
- [ ] 4.1.2 Add Go main function query:
  ```python
  cursor.execute("SELECT DISTINCT file FROM go_functions WHERE name = 'main'")
  entry_points.update(row[0] for row in cursor.fetchall())
  ```
- [ ] 4.1.3 Add Go test file pattern to `_find_entry_points()`:
  ```python
  if "_test.go" in node:
      entry_points.add(node)
  ```

### 4.2 Add Go CLI entry point detection
**File:** `theauditor/context/deadcode_graph.py:237-253`

- [ ] 4.2.1 Add Go CLI patterns to `_find_decorated_entry_points()`:
  - cobra.Command handlers
  - urfave/cli handlers
  - flag.Parse patterns

### 4.3 Add Bash entry point detection
**File:** `theauditor/context/deadcode_graph.py:208-235`

- [ ] 4.3.1 Add Bash shebang pattern detection to `_find_entry_points()`:
  ```python
  for node in graph.nodes():
      if node.endswith(".sh"):
          # Check if file has shebang (query files table or check content)
          entry_points.add(node)
  ```
- [ ] 4.3.2 Add Bash script patterns:
  - `*.sh` with `#!/bin/bash` or `#!/usr/bin/env bash`
  - Files in `scripts/`, `bin/` directories

### 4.4 Add Rust entry point detection (routes)
**File:** `theauditor/context/deadcode_graph.py:255-268`

**DEPENDS ON:** Task 0.3 (rust_attributes table)

- [ ] 4.4.1 Complete task 0.3 first
- [ ] 4.4.2 Add Rust route attributes query:
  ```python
  cursor.execute("""
      SELECT DISTINCT file_path FROM rust_attributes
      WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route')
  """)
  entry_points.update(row[0] for row in cursor.fetchall())
  ```

### 4.5 Add Rust entry point detection (main functions)
**File:** `theauditor/context/deadcode_graph.py:255-268`

**DEPENDS ON:** Task 0.3 (rust_attributes table)

- [ ] 4.5.1 Add Rust main function query:
  ```python
  cursor.execute("SELECT DISTINCT file_path FROM rust_functions WHERE name = 'main'")
  entry_points.update(row[0] for row in cursor.fetchall())
  ```
- [ ] 4.5.2 Add Rust binary crate detection:
  ```python
  # Files matching src/bin/*.rs or src/main.rs
  for node in graph.nodes():
      if "/src/bin/" in node or node.endswith("/src/main.rs"):
          entry_points.add(node)
  ```

### 4.6 Add Rust entry point detection (tests)
**File:** `theauditor/context/deadcode_graph.py:237-253`

**DEPENDS ON:** Task 0.3 (rust_attributes table)

- [ ] 4.6.1 Add Rust test attribute detection:
  ```python
  cursor.execute("""
      SELECT DISTINCT file_path FROM rust_attributes
      WHERE attribute_name IN ('test', 'tokio::test', 'cfg')
        AND (args IS NULL OR args LIKE '%test%')
  """)
  entry_points.update(row[0] for row in cursor.fetchall())
  ```

### 4.7 Manual test
- [ ] 4.7.1 Run `aud deadcode` on a Go codebase
- [ ] 4.7.2 Verify Go main packages NOT reported as dead
- [ ] 4.7.3 Verify Go web handlers NOT reported as dead
- [ ] 4.7.4 Verify Go test files NOT reported as dead (or marked medium confidence)
- [ ] 4.7.5 Run `aud deadcode` on a Rust codebase (after task 0.3)
- [ ] 4.7.6 Verify Rust main.rs NOT reported as dead
- [ ] 4.7.7 Verify Rust route handlers NOT reported as dead
- [ ] 4.7.8 Run `aud deadcode` on Bash scripts
- [ ] 4.7.9 Verify executable scripts NOT reported as dead

---

## 5. Boundaries Entry Point Detection

### 5.1 Add Go entry point detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

- [ ] 5.1.1 Locate entry point detection in `analyze_input_validation_boundaries()` (line 10+)
- [ ] 5.1.2 Add Go routes query:
  ```python
  cursor.execute("""
      SELECT file, line, framework, method, path, handler_func
      FROM go_routes
  """)
  ```
- [ ] 5.1.3 Format Go entry points with language="go" field

### 5.2 Add Go validation pattern detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

- [ ] 5.2.1 Locate control point detection function
- [ ] 5.2.2 Add Go validation patterns:
  ```python
  GO_VALIDATION_PATTERNS = [
      "ShouldBindJSON", "ShouldBindQuery", "ShouldBindUri",
      "BindJSON", "Bind", "validator.Struct", "validate.Struct",
  ]
  ```
- [ ] 5.2.3 Query `function_calls` table for these patterns
- [ ] 5.2.4 Calculate distance from entry to validation

### 5.3 Add Rust entry point detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

**DEPENDS ON:** Task 0.3 (rust_attributes table)

- [ ] 5.3.1 Complete task 0.3 first
- [ ] 5.3.2 Add Rust route attributes query:
  ```python
  cursor.execute("""
      SELECT a.file_path, a.line, a.attribute_name, a.args, f.name
      FROM rust_attributes a
      JOIN rust_functions f ON a.file_path = f.file_path AND a.target_line = f.line
      WHERE a.attribute_name IN ('get', 'post', 'put', 'delete', 'route')
  """)
  ```
- [ ] 5.3.3 Format Rust entry points with language="rust" field

### 5.4 Add Rust validation pattern detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

**DEPENDS ON:** Task 0.3 (rust_attributes table)

- [ ] 5.4.1 Add Rust validation patterns:
  ```python
  RUST_VALIDATION_PATTERNS = [
      "web::Json", "web::Path", "web::Query",
      "Json<", "Path<", "Query<", ".validate()",
  ]
  ```
- [ ] 5.4.2 Query `rust_attributes` for `#[validate]` derive
- [ ] 5.4.3 Calculate distance from entry to validation

### 5.5 Add Go multi-tenant boundary detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

**DEPENDS ON:** Task 5.1, 5.2

- [ ] 5.5.1 Add Go tenant patterns:
  ```python
  GO_TENANT_PATTERNS = [
      "ctx.Value", "tenant_id", "tenantId", "TenantID",
  ]
  ```
- [ ] 5.5.2 Query for tenant injection middleware
- [ ] 5.5.3 Calculate distance from entry to tenant check

### 5.6 Add Rust multi-tenant boundary detection
**File:** `theauditor/boundaries/boundary_analyzer.py`

**DEPENDS ON:** Task 0.3, 5.3, 5.4

- [ ] 5.6.1 Add Rust tenant patterns:
  ```python
  RUST_TENANT_PATTERNS = [
      "extensions().get", "TenantId", "tenant_id",
  ]
  ```
- [ ] 5.6.2 Query for tenant extractor patterns
- [ ] 5.6.3 Calculate distance from entry to tenant check

### 5.7 Manual test
- [ ] 5.7.1 Run `aud boundaries --type input-validation` on Go codebase
- [ ] 5.7.2 Verify Go routes detected as entry points
- [ ] 5.7.3 Verify Go validation controls detected
- [ ] 5.7.4 Verify distance calculation works
- [ ] 5.7.5 Run `aud boundaries --type input-validation` on Rust codebase (after task 0.3)
- [ ] 5.7.6 Verify Rust routes detected as entry points
- [ ] 5.7.7 Run `aud boundaries --type multi-tenant` on Go codebase
- [ ] 5.7.8 Verify tenant boundary detection works

---

## 6. Graph Edge Verification

**DEPENDS ON:** Task 0.5 (unified table population) - graph builder uses `refs` table

### 6.1 Verify Go import edges
**File:** `theauditor/commands/graph.py` (build subcommand)

- [ ] 6.1.1 Run `aud graph build` on codebase with Go files
- [ ] 6.1.2 Query edges table:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'import' AND source LIKE '%.go'
  LIMIT 20
  ```
- [ ] 6.1.3 Verify edges match actual Go imports
- [ ] 6.1.4 If missing, trace issue to graph builder or refs table

### 6.2 Verify Go call edges
- [ ] 6.2.1 Query call edges:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'call' AND source LIKE '%.go%'
  LIMIT 20
  ```
- [ ] 6.2.2 Verify edges match actual Go function calls
- [ ] 6.2.3 If missing, trace issue to graph builder or function_calls table

### 6.3 Verify Rust import edges
- [ ] 6.3.1 Run `aud graph build` on codebase with Rust files
- [ ] 6.3.2 Query edges table for Rust:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'import' AND source LIKE '%.rs'
  LIMIT 20
  ```
- [ ] 6.3.3 Verify edges match actual Rust `use` statements
- [ ] 6.3.4 If missing, trace issue to graph builder or refs table

### 6.4 Verify Rust call edges
- [ ] 6.4.1 Query call edges:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'call' AND source LIKE '%.rs%'
  LIMIT 20
  ```
- [ ] 6.4.2 Verify edges match actual Rust function calls

### 6.5 Verify Bash source edges
- [ ] 6.5.1 Query source edges:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'import' AND source LIKE '%.sh'
  LIMIT 20
  ```
- [ ] 6.5.2 Verify edges match actual Bash `source` or `.` statements
- [ ] 6.5.3 If missing, check if Bash extractor populates refs table

### 6.6 Verify Bash call edges
- [ ] 6.6.1 Query call edges:
  ```sql
  SELECT source, target, type FROM edges
  WHERE graph_type = 'call' AND source LIKE '%.sh%'
  LIMIT 20
  ```
- [ ] 6.6.2 Verify edges match actual Bash function calls

---

## 7. Testing

### 7.1 Blueprint naming convention tests
- [ ] 7.1.1 Add unit test for Go naming convention detection
- [ ] 7.1.2 Add unit test for Rust naming convention detection
- [ ] 7.1.3 Add unit test for Bash naming convention detection

### 7.2 Blueprint dependency tests
- [ ] 7.2.1 Add unit test for Cargo.toml parsing
- [ ] 7.2.2 Add unit test for go.mod parsing
- [ ] 7.2.3 Add unit test for dependency aggregation (cargo + go added to by_manager)

### 7.3 Explain tests
- [ ] 7.3.1 Add unit test for Go handler detection
- [ ] 7.3.2 Add unit test for Rust handler detection (after task 0.3)

### 7.4 Deadcode tests
- [ ] 7.4.1 Add unit test for Go entry point detection
- [ ] 7.4.2 Add unit test for Rust entry point detection (after task 0.3)
- [ ] 7.4.3 Add unit test for Bash entry point detection

### 7.5 Boundaries tests
- [ ] 7.5.1 Add unit test for Go entry point detection
- [ ] 7.5.2 Add unit test for Rust entry point detection (after task 0.3)
- [ ] 7.5.3 Add unit test for Go validation pattern detection
- [ ] 7.5.4 Add unit test for Rust validation pattern detection (after task 0.3)

### 7.6 Integration tests
- [ ] 7.6.1 Run full `aud full --offline` on test polyglot repo
- [ ] 7.6.2 Verify no regression in Python/JS/TS output
- [ ] 7.6.3 Verify Go/Rust/Bash data appears in all relevant commands

---

## 8. Cleanup

- [ ] 8.1 Run `ruff format` on modified Python files
- [ ] 8.2 Run `ruff check` for linting issues
- [ ] 8.3 Remove any TODO comments added during implementation
- [ ] 8.4 Final manual verification of all commands:
  - [ ] 8.4.1 `aud blueprint --structure`
  - [ ] 8.4.2 `aud blueprint --deps`
  - [ ] 8.4.3 `aud explain <file.go>`
  - [ ] 8.4.4 `aud explain <file.rs>`
  - [ ] 8.4.5 `aud deadcode`
  - [ ] 8.4.6 `aud boundaries --type input-validation`
  - [ ] 8.4.7 `aud graph build` + `aud graph analyze`
- [ ] 8.5 Update CHANGELOG.md with polyglot support additions
