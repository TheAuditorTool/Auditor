# Proposal: Add Polyglot Planning Support

## Why

TheAuditor recently added Go, Rust, and Bash language support at the extraction layer (AST extractors, schemas, taint engine). However, multiple analysis commands still only consume Python/JavaScript/TypeScript data. This creates an incomplete developer experience where new languages are indexed but not surfaced in command output.

**Current State:**
- Go/Rust/Bash extractors: WORKING (committed Nov 30)
- Go/Rust/Bash schemas: WORKING (22 Go tables, 28 Rust tables, 8 Bash tables)
- Taint engine Go/Rust detection: WORKING (committed Nov 30)
- Analysis commands: **NOT WIRED** (hardcoded for Py/JS/TS)

## Scope

This proposal covers polyglot support for ALL affected commands:

| Command | Current State | Changes Required |
|---------|---------------|------------------|
| `aud blueprint` | Hardcoded Py/JS/TS | Add Go/Rust/Bash naming + Cargo/go.mod deps |
| `aud explain` | Hardcoded Py/JS/TS | Add Go/Rust handler detection |
| `aud deadcode` | Hardcoded Py/JS | Add Go/Rust/Bash entry point detection |
| `aud boundaries` | Hardcoded Py/JS | Add Go/Rust entry points + validation patterns |
| `aud query` | Generic tables | Verify polyglot data flows through |
| `aud graph` | Generic tables | Verify polyglot edges populate correctly |

**Out of Scope (future work):**
- `aud refactor` - Go/Rust ORM detection (separate proposal)
- `aud planning` - Language-agnostic, no changes needed

---

## What Changes

### 1. Blueprint Naming Conventions (`blueprint.py:362-424`)
- **MODIFY** `_get_naming_conventions()` to include Go, Rust, Bash
- Add extension mappings: `.go`, `.rs`, `.sh`
- Query `symbols` table with file extension filtering (existing pattern)
- Go: snake_case functions (private), PascalCase (exported)
- Rust: snake_case functions, PascalCase types
- Bash: snake_case functions, SCREAMING_CASE constants

### 2. Blueprint Dependencies (`blueprint.py:1338-1440`)
- **TABLES EXIST** - `cargo_package_configs` in `rust_schema.py:347`, `go_module_configs` in `go_schema.py:362`
- **WIRE** Cargo.toml and go.mod parsing to database storage during indexing (tables exist but unpopulated)
- **MODIFY** `_get_dependencies()` to query existing tables
- Add `cargo` and `go` to `by_manager` dict

### 3. Explain Framework Info (`query.py:1375-1478`)
- **MODIFY** `get_file_framework_info()` to include Go/Rust handlers
- Go: Query `go_routes` table (extraction already implemented)
- Rust: Query `rust_attributes` for `#[get]`, `#[post]` macros (REQUIRES BLOCKER 1)
- Detect Go web frameworks: gin, echo, chi, fiber, net/http
- Detect Rust web frameworks: actix-web, axum, rocket

### 4. Deadcode Entry Point Detection (`deadcode_graph.py:237-269`)
- **MODIFY** `_find_decorated_entry_points()` (lines 237-253) to query Go/Rust tables
- **MODIFY** `_find_framework_entry_points()` (lines 255-269) to include:
  - `go_routes` for Go web handlers
  - `rust_attributes` for Rust route attributes
  - `go_functions` for Go main functions
  - `rust_functions` for Rust main functions
- **ADD** Bash shebang detection for executable scripts

### 5. Boundaries Entry Point Detection (`boundaries/boundary_analyzer.py`)
- **MODIFY** `analyze_input_validation_boundaries()` to query `go_routes`, `rust_attributes`
- **ADD** Go validation pattern detection (ShouldBindJSON, validator.Struct)
- **ADD** Rust validation pattern detection (web::Json extractors, Validate derive)
- **ADD** Go/Rust multi-tenant boundary detection

### 6. Graph Edge Verification
- **VERIFY** `aud graph build` populates edges for Go/Rust/Bash files
- **VERIFY** import edges flow from Go `import`, Rust `use`, Bash `source`
- **VERIFY** call edges flow from Go/Rust/Bash function calls

---

## Blockers

### BLOCKER 1: Rust Attribute Extraction (Task 0.3)
- `rust_macro_invocations` only captures macro calls like `println!()`
- Route attributes like `#[get("/users")]` are `attribute_item` nodes in tree-sitter
- **Required:** Create `rust_attributes` table and extraction function
- **Blocks:** Tasks 3.2 (explain), 4.4-4.6 (deadcode Rust), 5.3-5.6 (boundaries Rust)

### ~~BLOCKER 2: Go Route Extraction Missing~~ RESOLVED
- **Status:** IMPLEMENTED as of 2025-12-03
- **Location:** `theauditor/indexer/extractors/go.py:106-131`
- **Verification:** `go_routes` table has 5 gin routes populated
- **Frameworks supported:** gin, echo, fiber, chi, gorilla

### BLOCKER 2: Unified Table Population (Task 0.5)
- Go/Rust/Bash extractors populate language-specific tables but NOT unified `symbols`/`refs` tables
- **Verification results:**
  ```
  symbols: .py=52321, .ts=7206, .js=5369, .go=0, .rs=0, .sh=0
  refs:    .py=8117,  .ts=465,  .js=250,  .go=0, .rs=0, .sh=0
  ```
- **Data EXISTS** in language-specific tables: `go_imports` (146), `rust_use_statements` (203), `bash_sources` (10)
- **Required:** Modify extractors to ALSO populate `symbols` and `refs` during indexing
- **Blocks:** Tasks 1.x (blueprint naming), 6.x (graph edges)

---

## Impact

- **Affected specs:**
  - `polyglot-planning` - Blueprint + Explain
  - `polyglot-deadcode` - Dead code entry point detection
  - `polyglot-boundaries` - Security boundary detection
- **Affected code:**
  - `theauditor/commands/blueprint.py` (2 functions)
  - `theauditor/context/query.py` (1 function)
  - `theauditor/context/deadcode_graph.py` (3 functions)
  - `theauditor/boundaries/boundary_analyzer.py` (entry point + control detection)
  - `theauditor/indexer/schemas/infrastructure_schema.py` (new table)
  - `theauditor/indexer/schemas/go_schema.py` (new table)
  - `theauditor/indexer/schemas/rust_schema.py` (new table + rust_attributes)
  - `theauditor/indexer/extractors/go.py` (unified table population)
  - `theauditor/ast_extractors/rust_impl.py` (unified table population + attribute extraction)
  - `theauditor/ast_extractors/bash_impl.py` (unified table population)
- **Risk:** LOW - additive changes only, no breaking changes
- **Dependencies:** Relies on Go/Rust/Bash extractors populating language-specific tables (already done)
- **Soft dependency:** Tasks 2.1-2.4 overlap with `add-polyglot-package-managers` proposal (Cargo/Go parsing)

---

## Success Criteria

### Blueprint
1. `aud blueprint --structure` shows naming conventions for Go/Rust/Bash files
2. `aud blueprint --deps` shows Cargo.toml and go.mod dependencies
3. All existing Python/JS/TS functionality remains unchanged

### Explain
4. `aud explain <file.go>` shows Go framework routes/handlers if present
5. `aud explain <file.rs>` shows Rust framework handlers if present

### Deadcode
6. `aud deadcode` does NOT report Go main packages as dead
7. `aud deadcode` does NOT report Rust main.rs/bin/*.rs as dead
8. `aud deadcode` does NOT report Go/Rust web handlers as dead
9. `aud deadcode` does NOT report Bash executable scripts as dead

### Boundaries
10. `aud boundaries` detects Go HTTP routes as entry points
11. `aud boundaries` detects Rust route attributes as entry points
12. `aud boundaries` measures distance to Go/Rust validation controls
13. `aud boundaries --type multi-tenant` works for Go/Rust codebases

### Graph
14. `aud graph build` creates edges for Go import statements
15. `aud graph build` creates edges for Rust use statements
16. `aud graph build` creates edges for Bash source statements

---

## Example Output

### `aud blueprint --structure` (naming conventions section)

```json
{
  "naming_conventions": {
    "python": {
      "functions": {"snake_case": {"count": 150, "percentage": 95.0}},
      "classes": {"PascalCase": {"count": 45, "percentage": 100.0}}
    },
    "go": {
      "functions": {
        "snake_case": {"count": 80, "percentage": 60.0},
        "PascalCase": {"count": 50, "percentage": 40.0}
      },
      "structs": {"PascalCase": {"count": 25, "percentage": 100.0}}
    },
    "rust": {
      "functions": {"snake_case": {"count": 45, "percentage": 98.0}},
      "structs": {"PascalCase": {"count": 12, "percentage": 100.0}}
    },
    "bash": {
      "functions": {
        "snake_case": {"count": 20, "percentage": 85.0},
        "SCREAMING_CASE": {"count": 3, "percentage": 15.0}
      }
    }
  }
}
```

### `aud deadcode` (Go entry points excluded)

```
Dead Code Analysis Report
=========================
Total dead code items: 3

Isolated Modules (never imported):
----------------------------------
[HIGH] internal/deprecated/old_utils.go
   Symbols: 5
   Reason: Module never imported

[MED ] scripts/one_time_migration.go
   Symbols: 2
   Reason: CLI script (may be external entry)

Excluded as entry points:
- cmd/api/main.go (Go main package)
- internal/handlers/*.go (Go web handlers - 12 files)
- *_test.go (Go test files - 45 files)
```

### `aud boundaries` (Go validation detection)

```json
{
  "entry_point": "POST /api/users",
  "entry_file": "internal/handlers/users.go",
  "entry_line": 45,
  "language": "go",
  "framework": "gin",
  "controls": [
    {
      "control_function": "ShouldBindJSON",
      "control_file": "internal/handlers/users.go",
      "control_line": 48,
      "distance": 0,
      "pattern": "json_binding"
    }
  ],
  "quality": {
    "quality": "clear",
    "reason": "Validation at entry via ShouldBindJSON"
  }
}
```

---

## Key Tables Used

| Table | Source | Purpose |
|-------|--------|---------|
| `symbols` | Core schema | Naming convention analysis via extension filter |
| `go_routes` | go_schema.py:257 | Go web framework route detection |
| `go_func_params` | go_schema.py:135 | Go handler detection via param types |
| `go_functions` | go_schema.py | Go main function detection |
| `rust_attributes` | NEW - rust_schema.py | Rust route attribute detection |
| `rust_functions` | rust_schema.py | Rust main function detection |
| `cargo_package_configs` | NEW - infrastructure_schema.py | Cargo.toml dependency storage |
| `go_module_configs` | NEW - go_schema.py | go.mod dependency storage |
| `bash_functions` | bash_schema.py | Bash function detection |
| `files` | Core schema | Shebang detection for Bash entry points |
