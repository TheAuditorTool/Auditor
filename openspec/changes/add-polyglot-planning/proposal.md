# Proposal: Add Polyglot Planning Support

## Why

TheAuditor recently added Go, Rust, and Bash language support at the extraction layer (AST extractors, schemas, taint engine). However, the planning commands (`aud blueprint`, `aud explain`, `aud refactor`) still only consume Python/JavaScript/TypeScript data. This creates an incomplete developer experience where new languages are indexed but not surfaced in planning output.

**Current State:**
- Go/Rust/Bash extractors: WORKING (committed Nov 30)
- Go/Rust/Bash schemas: WORKING (22 Go tables, 28 Rust tables, 8 Bash tables)
- Taint engine Go/Rust detection: WORKING (committed Nov 30)
- Planning commands: **NOT WIRED** (hardcoded for Py/JS/TS)

## What Changes

### 1. Blueprint Naming Conventions (`blueprint.py:332-394`)
- **MODIFY** `_get_naming_conventions()` to include Go, Rust, Bash
- Add extension mappings: `.go`, `.rs`, `.sh`
- Query `symbols` table with file extension filtering (existing pattern)
- Go: snake_case functions (private), PascalCase (exported)
- Rust: snake_case functions, PascalCase types
- Bash: snake_case functions, SCREAMING_CASE constants

### 2. Blueprint Dependencies (`blueprint.py:1264-1366`)
- **CREATE** `cargo_package_configs` table in `infrastructure_schema.py`
- **CREATE** `go_module_configs` table in `go_schema.py`
- **WIRE** Cargo.toml and go.mod parsing to database storage during indexing
- **MODIFY** `_get_dependencies()` to query new tables
- Add `cargo` and `go` to `by_manager` dict

### 3. Explain Framework Info (`query.py:1439-1478`)
- **MODIFY** `get_file_framework_info()` to include Go/Rust handlers
- Go: Query existing `go_routes` table (already populated by extractor)
- Rust: Query `rust_macro_invocations` for `#[get]`, `#[post]` macros
- Detect Go web frameworks: gin, echo, chi, fiber, net/http
- Detect Rust web frameworks: actix-web, axum, rocket

### 4. (Future) Refactor ORM Detection
- The `go_orm.py` graph strategy exists but is not wired to `aud refactor`
- **OUT OF SCOPE** for this proposal - focus on planning commands first
- Can be addressed in follow-up proposal after core planning is complete

## Impact

- **Affected specs:** NEW `polyglot-planning` capability
- **Affected code:**
  - `theauditor/commands/blueprint.py` (2 functions)
  - `theauditor/context/query.py` (1 function)
  - `theauditor/indexer/schemas/infrastructure_schema.py` (new table)
  - `theauditor/indexer/schemas/go_schema.py` (new table)
- **Risk:** LOW - additive changes only, no breaking changes
- **Dependencies:** Relies on Go/Rust/Bash tables being populated (already done)

## Success Criteria

1. `aud blueprint --structure` shows naming conventions for Go/Rust/Bash files
2. `aud blueprint --deps` shows Cargo.toml and go.mod dependencies
3. `aud explain <file.go>` shows Go framework routes/handlers if present
4. `aud explain <file.rs>` shows Rust framework handlers if present
5. All existing Python/JS/TS functionality remains unchanged

## Example Output

### `aud blueprint --structure` (naming conventions section)

```json
{
  "naming_conventions": {
    "python": {
      "functions": {"snake_case": {"count": 150, "percentage": 95.0}},
      "classes": {"PascalCase": {"count": 45, "percentage": 100.0}}
    },
    "javascript": {
      "functions": {"camelCase": {"count": 200, "percentage": 85.0}},
      "classes": {"PascalCase": {"count": 30, "percentage": 100.0}}
    },
    "typescript": {
      "functions": {"camelCase": {"count": 180, "percentage": 90.0}},
      "classes": {"PascalCase": {"count": 50, "percentage": 100.0}}
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

### `aud blueprint --deps` (dependencies section)

```json
{
  "dependencies": {
    "total": 245,
    "by_manager": {
      "npm": 120,
      "pip": 45,
      "cargo": 50,
      "go": 30
    },
    "workspaces": [
      {"file": "package.json", "name": "frontend", "manager": "npm", "prod_count": 15, "dev_count": 10},
      {"file": "pyproject.toml", "name": "backend", "manager": "pip", "prod_count": 20, "dev_count": 5},
      {"file": "Cargo.toml", "name": "rust-service", "manager": "cargo", "prod_count": 30, "dev_count": 10},
      {"file": "go.mod", "name": "github.com/org/api", "manager": "go", "prod_count": 25, "dev_count": 5}
    ]
  }
}
```

### `aud explain handlers.go` (Go handler detection)

```
FRAMEWORK INFO
==============
Framework: gin
Routes:
  1. GET  /api/users     -> GetUsers     (line 25)
  2. POST /api/users     -> CreateUser   (line 45)
  3. GET  /api/users/:id -> GetUser      (line 65)

Handlers (detected via param types):
  1. AuthMiddleware (*gin.Context) - line 15
```

### `aud explain routes.rs` (Rust handler detection)

```
FRAMEWORK INFO
==============
Framework: actix-web
Handlers:
  1. #[get("/users")]     -> get_users     (line 12)
  2. #[post("/users")]    -> create_user   (line 28)
  3. #[get("/users/{id}")]-> get_user      (line 44)
```

## Key Tables Used

| Table | Source | Purpose |
|-------|--------|---------|
| `symbols` | Core schema | Naming convention analysis via extension filter |
| `go_routes` | go_schema.py:257 | Go web framework route detection |
| `go_func_params` | go_schema.py:135 | Go handler detection via param types |
| `rust_macro_invocations` | rust_schema.py:197 | Rust route attribute detection |
| `cargo_package_configs` | NEW - infrastructure_schema.py | Cargo.toml dependency storage |
| `go_module_configs` | NEW - go_schema.py | go.mod dependency storage |
