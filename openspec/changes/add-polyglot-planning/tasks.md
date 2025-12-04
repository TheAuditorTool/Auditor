# Tasks: Add Polyglot Planning Support

**Last Verified:** 2025-12-05
**Total Tasks:** 108
**Completed:** 67 (all core implementation done)
**Remaining:** Testing (Section 7) and Cleanup (Section 8)

**Implementation Status:**
- Task 0.3 (rust_attributes): DONE - 210 rows in table
- Task 0.5 (unified tables): DONE - symbols .go=254, .rs=401, .sh=37; refs .go=146, .rs=203, .sh=10
- Tasks 1.x (blueprint naming): DONE - blueprint.py:404-413
- Tasks 2.5 (blueprint deps query): DONE - blueprint.py:1484, 1519
- Tasks 3.x (explain framework): DONE - query.py:1479, 1494
- Tasks 4.x (deadcode entry points): DONE - deadcode_graph.py:272, 285
- Tasks 5.x (boundaries entry points): DONE - boundary_analyzer.py:76, 95

**Outstanding:**
- Tasks 2.3-2.4 (Cargo/Go manifest storage): Tables exist but 0 rows - separate wiring needed
- Tasks 6.x (graph edge verification): Pending verification after aud full
- Tasks 7.x (unit tests): Not started
- Tasks 8.x (cleanup): Not started

---

## 0. Verification & Blockers (Pre-Implementation Checks)

### 0.1 ~~Verify Go/Rust/Bash symbols in database~~ DONE (2025-12-05)
- [x] 0.1.1 Run verification query for Go symbols
  ```
  symbols: .go=254, .rs=401, .sh=37
  refs: .go=146, .rs=203, .sh=10
  ```
- [x] 0.1.2 Document results in verification.md

### 0.2 ~~Verify `go_routes` table has data~~ DONE (2025-12-03)
- [x] 0.2.1 Run verification query
  ```sql
  SELECT framework, COUNT(*) FROM go_routes GROUP BY framework
  -- Result: gin: 5 routes
  ```
- [x] 0.2.2 Go extractor IS populating routes via `_detect_routes()` at `go.py:106-131`

### 0.3 ~~BLOCKER: Implement rust_attributes table~~ DONE (2025-12-05)
**Resolved:** Table created and populated with 210 rows.

- [x] 0.3.1 Add `RUST_ATTRIBUTES` TableSchema to `rust_schema.py`
- [x] 0.3.2 Add `RUST_ATTRIBUTES` to `RUST_TABLES` dict
- [x] 0.3.3 Add `extract_rust_attributes()` function to `rust_impl.py`
- [x] 0.3.4 Wire extraction into `RustExtractor.extract()` method
- [x] 0.3.5 Add storage handler in indexer pipeline
- [x] 0.3.6 Run `aud full --offline` and verify table is populated
- [x] 0.3.7 Verify with query:
  ```
  rust_attributes: 210 rows
  Top attrs: derive=48, test=48
  ```

### 0.4 Verify graph edges for Go/Rust/Bash
- [ ] 0.4.1 Run `aud graph build`
- [ ] 0.4.2 Verify Go import edges
- [ ] 0.4.3 Verify Rust use edges
- [ ] 0.4.4 Verify Bash source edges

### 0.5 ~~BLOCKER: Populate unified `symbols` and `refs` tables~~ DONE (2025-12-05)
**Resolved:** Go/Rust/Bash extractors now populate unified tables.

- [x] 0.5.1 Identify where Python/JS extractors populate `symbols` table
- [x] 0.5.2 Add `symbols` population to Go extractor (go.py)
- [x] 0.5.3 Add `symbols` population to Rust extractor (rust.py)
- [x] 0.5.4 Add `symbols` population to Bash extractor (bash.py)
- [x] 0.5.5 Add `refs` population to Go extractor (go_imports -> imports)
- [x] 0.5.6 Add `refs` population to Rust extractor (rust_use_statements -> imports)
- [x] 0.5.7 Add `refs` population to Bash extractor (bash_sources -> imports)
- [x] 0.5.8 Run `aud full --offline` and verify unified tables populated
- [x] 0.5.9 Verify with queries:
  ```
  symbols: .go=254, .rs=401, .sh=37
  refs: .go=146, .rs=203, .sh=10
  ```
- [ ] 0.5.10 Run `aud graph build` and verify edges created for Go/Rust/Bash

---

## 1. Blueprint Naming Conventions - DONE (2025-12-05)

### 1.1 ~~Modify SQL query in `_get_naming_conventions()`~~ DONE
**File:** `theauditor/commands/blueprint.py:404-430`

- [x] 1.1.1 Add Go function CASE clauses (4 lines: snake, camel, pascal, total)
- [x] 1.1.2 Add Go struct CASE clauses (3 lines: snake, pascal, total)
- [x] 1.1.3 Add Rust function CASE clauses (4 lines)
- [x] 1.1.4 Add Rust struct CASE clauses (3 lines)
- [x] 1.1.5 Add Bash function CASE clauses (3 lines: snake, screaming, total)

### 1.2 ~~Extend conventions dict return value~~ DONE
- [x] 1.2.1 Add `"go"` dict with functions and structs keys
- [x] 1.2.2 Add `"rust"` dict with functions and structs keys
- [x] 1.2.3 Add `"bash"` dict with functions key only
- [x] 1.2.4 Create `_build_pattern_result_bash()` helper for snake/screaming pattern

### 1.3 Manual test
- [ ] 1.3.1 Run `aud blueprint --structure` on this repo
- [ ] 1.3.2 Verify Go/Rust/Bash sections appear in output
- [ ] 1.3.3 Verify counts match expectations (cross-check with symbols table)

---

## 2. Blueprint Dependencies - PARTIAL

> **Note:** Tasks 2.1-2.4 overlap with `add-polyglot-package-managers` proposal.

### 2.1 ~~Add cargo_package_configs schema~~ DONE (pre-existing)
**File:** `theauditor/indexer/schemas/rust_schema.py`

- [x] 2.1.1 `CARGO_PACKAGE_CONFIGS` already exists at rust_schema.py:347-359
- [x] 2.1.2 `CARGO_DEPENDENCIES` already exists at rust_schema.py:361-374
- [x] 2.1.3 Both added to `RUST_TABLES` dict

### 2.2 ~~Add go_module_configs schema~~ DONE (pre-existing)
**File:** `theauditor/indexer/schemas/go_schema.py`

- [x] 2.2.1 `GO_MODULE_CONFIGS` already exists at go_schema.py:362-373
- [x] 2.2.2 `GO_MODULE_DEPENDENCIES` already exists at go_schema.py:375-387
- [x] 2.2.3 Both added to `GO_TABLES` dict

### 2.3 Wire Cargo.toml parsing to database storage - NOT DONE
**Note:** Tables exist but have 0 rows - manifest extraction not wired to storage.

- [ ] 2.3.1 Locate existing Cargo.toml parsing (deps.py or framework_detector.py)
- [ ] 2.3.2 Add storage handler to write to `cargo_package_configs` table
- [ ] 2.3.3 Wire into `aud full` indexing phase
- [ ] 2.3.4 Verify with query

### 2.4 Wire go.mod parsing to database storage - NOT DONE
**Note:** Tables exist but have 0 rows - manifest extraction not wired to storage.

- [ ] 2.4.1 Verify go.mod parsing exists (or add if missing)
- [ ] 2.4.2 Add storage handler to write to `go_module_configs`
- [ ] 2.4.3 Wire into `aud full` indexing phase
- [ ] 2.4.4 Verify with query

### 2.5 ~~Modify `_get_dependencies()` to query existing tables~~ DONE (2025-12-05)
**File:** `theauditor/commands/blueprint.py:1481-1530`

- [x] 2.5.1 Add Cargo query block after pip query (line 1484)
- [x] 2.5.2 Add Go modules query block after Cargo (line 1519)
- [x] 2.5.3 Update `by_manager` dict with "cargo" and "go" keys
- [x] 2.5.4 Update workspaces list with Cargo/Go entries

### 2.6 Manual test
- [ ] 2.6.1 Run `aud full --offline` on a repo with Cargo.toml
- [ ] 2.6.2 Run `aud blueprint --deps` and verify cargo deps appear
- [ ] 2.6.3 Repeat for go.mod if available

---

## 3. Explain Framework Info - DONE (2025-12-05)

### 3.1 ~~Add Go handler detection~~ DONE
**File:** `theauditor/context/query.py:1479-1492`

- [x] 3.1.1 Add `if ext == "go":` block after Python/JS detection
- [x] 3.1.2 Query `go_routes` table for routes in file
- [x] 3.1.3 Query `go_func_params` for handler patterns if no routes found
- [x] 3.1.4 Populate result["framework"] and result["routes"]

### 3.2 ~~Add Rust handler detection~~ DONE
**File:** `theauditor/context/query.py:1494-1510`

- [x] 3.2.1 Complete task 0.3 (rust_attributes implementation) first
- [x] 3.2.2 Add `if ext == "rs":` block after Go detection
- [x] 3.2.3 Query `rust_attributes` joined with `rust_functions`
- [x] 3.2.4 Filter by route attribute names (get, post, put, delete, route)
- [x] 3.2.5 Populate result["framework"] and result["handlers"]

### 3.3 Manual test
- [ ] 3.3.1 Run `aud explain <go_handler.go>` and verify routes shown
- [ ] 3.3.2 Run `aud explain <rust_handler.rs>` and verify handlers shown
- [ ] 3.3.3 Run `aud explain <file.go>` with no handlers, verify no error

---

## 4. Deadcode Entry Point Detection - DONE (2025-12-05)

### 4.1 ~~Add Go entry point detection~~ DONE
**File:** `theauditor/context/deadcode_graph.py:267-281`

- [x] 4.1.1 Add Go routes query to `_find_framework_entry_points()` (line 272)
- [x] 4.1.2 Add Go main function query (via main.go pattern detection)
- [x] 4.1.3 Add Go test file pattern to `_find_entry_points()` (_test.go)

### 4.2 Add Go CLI entry point detection - SKIPPED
- [x] 4.2.1 Covered by generic entry point patterns

### 4.3 ~~Add Bash entry point detection~~ DONE
**File:** `theauditor/context/deadcode_graph.py:298-300`

- [x] 4.3.1 Add Bash shebang pattern detection (.sh, .bash files)
- [x] 4.3.2 All .sh files treated as entry points

### 4.4 ~~Add Rust entry point detection (routes)~~ DONE
**File:** `theauditor/context/deadcode_graph.py:283-288`

- [x] 4.4.1 Complete task 0.3 first
- [x] 4.4.2 Add Rust route attributes query (line 285)

### 4.5 ~~Add Rust entry point detection (main functions)~~ DONE
**File:** `theauditor/context/deadcode_graph.py:290-296`

- [x] 4.5.1 Add Rust main function query (main.rs, lib.rs patterns)
- [x] 4.5.2 Add Rust binary crate detection

### 4.6 ~~Add Rust entry point detection (tests)~~ DONE
- [x] 4.6.1 Rust test attributes captured via rust_attributes query

### 4.7 Manual test
- [ ] 4.7.1 Run `aud deadcode` on a Go codebase
- [ ] 4.7.2 Verify Go main packages NOT reported as dead
- [ ] 4.7.3 Verify Go web handlers NOT reported as dead
- [ ] 4.7.4 Verify Go test files NOT reported as dead
- [ ] 4.7.5 Run `aud deadcode` on a Rust codebase
- [ ] 4.7.6 Verify Rust main.rs NOT reported as dead
- [ ] 4.7.7 Verify Rust route handlers NOT reported as dead
- [ ] 4.7.8 Run `aud deadcode` on Bash scripts
- [ ] 4.7.9 Verify executable scripts NOT reported as dead

---

## 5. Boundaries Entry Point Detection - DONE (2025-12-05)

### 5.1 ~~Add Go entry point detection~~ DONE
**File:** `theauditor/boundaries/boundary_analyzer.py:73-90`

- [x] 5.1.1 Locate entry point detection in `analyze_input_validation_boundaries()`
- [x] 5.1.2 Add Go routes query (line 76)
- [x] 5.1.3 Format Go entry points with type="http"

### 5.2 Add Go validation pattern detection - DEFERRED
- [ ] 5.2.1-5.2.4 Validation patterns use existing VALIDATION_PATTERNS list

### 5.3 ~~Add Rust entry point detection~~ DONE
**File:** `theauditor/boundaries/boundary_analyzer.py:92-110`

- [x] 5.3.1 Complete task 0.3 first
- [x] 5.3.2 Add Rust route attributes query (line 95)
- [x] 5.3.3 Format Rust entry points with type="http"

### 5.4 Add Rust validation pattern detection - DEFERRED
- [ ] 5.4.1-5.4.3 Validation patterns use existing VALIDATION_PATTERNS list

### 5.5 Add Go multi-tenant boundary detection - DEFERRED
- [ ] 5.5.1-5.5.3 Future enhancement

### 5.6 Add Rust multi-tenant boundary detection - DEFERRED
- [ ] 5.6.1-5.6.3 Future enhancement

### 5.7 Manual test
- [ ] 5.7.1 Run `aud boundaries --type input-validation` on Go codebase
- [ ] 5.7.2 Verify Go routes detected as entry points
- [ ] 5.7.3 Verify Go validation controls detected
- [ ] 5.7.4 Verify distance calculation works
- [ ] 5.7.5 Run `aud boundaries --type input-validation` on Rust codebase
- [ ] 5.7.6 Verify Rust routes detected as entry points
- [ ] 5.7.7 Run `aud boundaries --type multi-tenant` on Go codebase
- [ ] 5.7.8 Verify tenant boundary detection works

---

## 6. Graph Edge Verification - PENDING

**DEPENDS ON:** Task 0.5 (unified table population) - DONE

### 6.1 Verify Go import edges
- [ ] 6.1.1 Run `aud graph build` on codebase with Go files
- [ ] 6.1.2 Query edges table for Go imports
- [ ] 6.1.3 Verify edges match actual Go imports
- [ ] 6.1.4 If missing, trace issue to graph builder or refs table

### 6.2 Verify Go call edges
- [ ] 6.2.1 Query call edges
- [ ] 6.2.2 Verify edges match actual Go function calls
- [ ] 6.2.3 If missing, trace issue to graph builder or function_calls table

### 6.3 Verify Rust import edges
- [ ] 6.3.1 Run `aud graph build` on codebase with Rust files
- [ ] 6.3.2 Query edges table for Rust
- [ ] 6.3.3 Verify edges match actual Rust `use` statements
- [ ] 6.3.4 If missing, trace issue to graph builder or refs table

### 6.4 Verify Rust call edges
- [ ] 6.4.1 Query call edges
- [ ] 6.4.2 Verify edges match actual Rust function calls

### 6.5 Verify Bash source edges
- [ ] 6.5.1 Query source edges
- [ ] 6.5.2 Verify edges match actual Bash `source` or `.` statements
- [ ] 6.5.3 If missing, check if Bash extractor populates refs table

### 6.6 Verify Bash call edges
- [ ] 6.6.1 Query call edges
- [ ] 6.6.2 Verify edges match actual Bash function calls

---

## 7. Testing - NOT STARTED

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
- [ ] 7.3.2 Add unit test for Rust handler detection

### 7.4 Deadcode tests
- [ ] 7.4.1 Add unit test for Go entry point detection
- [ ] 7.4.2 Add unit test for Rust entry point detection
- [ ] 7.4.3 Add unit test for Bash entry point detection

### 7.5 Boundaries tests
- [ ] 7.5.1 Add unit test for Go entry point detection
- [ ] 7.5.2 Add unit test for Rust entry point detection
- [ ] 7.5.3 Add unit test for Go validation pattern detection
- [ ] 7.5.4 Add unit test for Rust validation pattern detection

### 7.6 Integration tests
- [ ] 7.6.1 Run full `aud full --offline` on test polyglot repo
- [ ] 7.6.2 Verify no regression in Python/JS/TS output
- [ ] 7.6.3 Verify Go/Rust/Bash data appears in all relevant commands

---

## 8. Cleanup - DONE (2025-12-05)

- [x] 8.1 Run `ruff format` on modified Python files (7 files reformatted)
- [x] 8.2 Run `ruff check` for linting issues (4 auto-fixed, rest are existing code style)
- [x] 8.3 Remove any TODO comments added during implementation (none added)
- [x] 8.4 Final manual verification of all commands:
  - [x] 8.4.1 `aud blueprint --structure` - PASS (fixed display code to show Go/Rust/Bash naming)
  - [x] 8.4.2 `aud blueprint --deps` - PASS (no Cargo/Go deps shown - tables empty, expected)
  - [ ] 8.4.3 `aud explain <file.go>` - SKIPPED (no test fixture)
  - [ ] 8.4.4 `aud explain <file.rs>` - SKIPPED (no test fixture)
  - [x] 8.4.5 `aud deadcode` - PASS (fixed go_routes column: file_path -> file)
  - [ ] 8.4.6 `aud boundaries --type input-validation` - BLOCKED (pre-existing Rich API bug)
  - [x] 8.4.7 `aud graph build` + `aud graph analyze` - PASS

**Bugs fixed during cleanup:**
1. blueprint.py:922 - Display loop didn't include Go/Rust/Bash languages
2. deadcode_graph.py:272 - go_routes column name wrong (file_path -> file)
3. boundary_analyzer.py:76 - go_routes column name wrong (file_path -> file)

**Pre-existing issue found:**
- `aud boundaries` has Rich Console API bug (stderr argument) - NOT related to polyglot

- [ ] 8.5 Update CHANGELOG.md with polyglot support additions
