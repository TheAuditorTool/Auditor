# Design: Add Polyglot Planning Support

## Context

TheAuditor indexes code from multiple languages (Python, JavaScript, TypeScript, Go, Rust, Bash) into a unified SQLite database. Multiple analysis commands query this database but currently only consume Python/JS/TS data due to hardcoded extension checks and language-specific queries.

**Stakeholders:**
- Developers using TheAuditor on polyglot codebases
- AI assistants using `aud` commands for code analysis

**Constraints:**
- ZERO FALLBACK POLICY: No fallback logic, no try-except alternatives
- Must query existing tables where available
- Must use existing schema patterns (e.g., `symbols` table for cross-language queries)

## Goals / Non-Goals

**Goals:**
- Surface Go/Rust/Bash data in `aud blueprint --structure` output
- Surface Go/Rust/Bash dependencies in `aud blueprint --deps` output
- Surface Go/Rust handler info in `aud explain <file>` output
- Detect Go/Rust/Bash entry points in `aud deadcode` analysis
- Detect Go/Rust entry points and validation patterns in `aud boundaries`
- Maintain performance (<100ms for typical queries)

**Non-Goals:**
- Changing output format (additive only)
- Wiring ORM detection to refactor command (future work)
- Adding Bash handler detection (Bash doesn't have HTTP handlers)
- Adding Bash boundary detection (Bash isn't used for web services)

---

## Schema Reference

### Existing Tables (use as-is)

**go_routes** (`theauditor/indexer/schemas/go_schema.py:257-271`):
```python
GO_ROUTES = TableSchema(
    name="go_routes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),  # gin/echo/chi/fiber
        Column("method", "TEXT"),                      # GET/POST/PUT/DELETE
        Column("path", "TEXT"),                        # Route pattern
        Column("handler_func", "TEXT"),                # Handler function name
    ],
    indexes=[
        ("idx_go_routes_file", ["file"]),
        ("idx_go_routes_framework", ["framework"]),
    ],
)
```

**go_func_params** (`theauditor/indexer/schemas/go_schema.py:135-150`):
```python
GO_FUNC_PARAMS = TableSchema(
    name="go_func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("func_line", "INTEGER", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT"),
        Column("param_type", "TEXT", nullable=False),  # For detecting *gin.Context
        Column("is_variadic", "BOOLEAN", default="0"),
    ],
)
```

**go_functions** (`theauditor/indexer/schemas/go_schema.py:97-113`):
```python
GO_FUNCTIONS = TableSchema(
    name="go_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("signature", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("is_async", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name", "line"],
)
# NOTE: Receivers are in go_methods table, NOT go_functions
```

**rust_macro_invocations** (`theauditor/indexer/schemas/rust_schema.py:197-210`):
```python
RUST_MACRO_INVOCATIONS = TableSchema(
    name="rust_macro_invocations",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("macro_name", "TEXT", nullable=False),  # get/post/put/delete/route
        Column("containing_function", "TEXT"),
        Column("args_sample", "TEXT"),                  # Route path from macro args
    ],
)
```

**rust_functions** (`theauditor/indexer/schemas/rust_schema.py:48-72`):
```python
RUST_FUNCTIONS = TableSchema(
    name="rust_functions",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("name", "TEXT", nullable=False),
        Column("visibility", "TEXT"),
        Column("is_async", "BOOLEAN", default="0"),
        Column("is_unsafe", "BOOLEAN", default="0"),
        Column("is_const", "BOOLEAN", default="0"),
        Column("is_extern", "BOOLEAN", default="0"),
        Column("abi", "TEXT"),
        Column("return_type", "TEXT"),
        Column("params_json", "TEXT"),
        Column("generics", "TEXT"),
        Column("where_clause", "TEXT"),
    ],
    primary_key=["file_path", "line"],
)
```

**bash_functions** (`theauditor/indexer/schemas/bash_schema.py:5-21`):
```python
BASH_FUNCTIONS = TableSchema(
    name="bash_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("style", "TEXT", nullable=False, default="'posix'"),
        Column("body_start_line", "INTEGER", nullable=True),
        Column("body_end_line", "INTEGER", nullable=True),
    ],
    primary_key=["file", "name", "line"],
)
```

### New Tables Required

**cargo_package_configs** (add to `theauditor/indexer/schemas/infrastructure_schema.py`):
```python
CARGO_PACKAGE_CONFIGS = TableSchema(
    name="cargo_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("package_name", "TEXT"),
        Column("version", "TEXT"),
        Column("edition", "TEXT"),
        Column("dependencies", "TEXT"),      # JSON dict of deps
        Column("dev_dependencies", "TEXT"),  # JSON dict of dev-deps
        Column("build_dependencies", "TEXT"), # JSON dict of build-deps
    ],
    indexes=[
        ("idx_cargo_configs_name", ["package_name"]),
    ],
)
```

**go_module_configs** (add to `theauditor/indexer/schemas/go_schema.py`):
```python
GO_MODULE_CONFIGS = TableSchema(
    name="go_module_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("module_path", "TEXT", nullable=False),
        Column("go_version", "TEXT"),
        Column("dependencies", "TEXT"),  # JSON array of require statements
        Column("replacements", "TEXT"),  # JSON dict of replace directives
    ],
    indexes=[
        ("idx_go_module_path", ["module_path"]),
    ],
)
```

**rust_attributes** (add to `theauditor/indexer/schemas/rust_schema.py`):
```python
RUST_ATTRIBUTES = TableSchema(
    name="rust_attributes",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("attribute_name", "TEXT", nullable=False),  # "get", "derive", "serde"
        Column("args", "TEXT"),  # '"/users"', 'Debug, Serialize'
        Column("target_type", "TEXT"),  # "function", "struct", "field", "module"
        Column("target_name", "TEXT"),  # name of the item the attribute is on
        Column("target_line", "INTEGER"),  # line of the item
    ],
    primary_key=["file_path", "line"],
    indexes=[
        ("idx_rust_attrs_name", ["attribute_name"]),
        ("idx_rust_attrs_target", ["target_type", "target_name"]),
    ],
)
```

---

## Decisions

### Decision 1: Query `symbols` table for naming conventions

**What:** For naming conventions, query the unified `symbols` table with extension-based filtering.

**Why:**
- `symbols` table already contains all functions/classes across languages
- Extension filtering via `files.ext` JOIN is consistent with existing pattern
- Avoids N+1 queries to language-specific tables

**Implementation** (`theauditor/commands/blueprint.py:362-424`):
```sql
-- Add these CASE clauses to existing query in _get_naming_conventions()
-- Go functions (snake_case for private, PascalCase for exported)
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_func_snake,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_camel,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_pascal,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' THEN 1 ELSE 0 END) AS go_func_total,

-- Rust/Bash similar patterns...
```

### Decision 2: ~~Create new tables~~ Wire existing tables for Cargo/Go dependencies

**What:** Use existing `cargo_package_configs` and `go_module_configs` tables for manifest data.

**Why:**
- Tables ALREADY EXIST (verified 2025-12-05):
  - `cargo_package_configs` at rust_schema.py:347-359
  - `cargo_dependencies` at rust_schema.py:361-374
  - `go_module_configs` at go_schema.py:362-373
  - `go_module_dependencies` at go_schema.py:375-387
- Tables exist but have 0 rows - need to wire extraction to populate them
- ZFP requires storing during indexing, not parsing at query time

**Implementation:**
1. ~~Add schema definitions~~ DONE - schemas exist
2. Add storage handlers called during `aud full` indexing phase (FOCUS HERE)
3. Query in `_get_dependencies()` same pattern as npm/pip

### Decision 3: Use `go_routes` table for Go handler detection

**What:** Query `go_routes` table for Go web framework handlers.

**Why:**
- Table schema exists with framework, method, path, handler_func columns
- Clean query pattern, no complex param-type matching needed

**BLOCKER:** `go_routes` table is NOT currently populated:
- `theauditor/ast_extractors/go_impl.py` has NO `extract_go_routes()` function
- Must implement Go route extraction before this works (see BLOCKER 2 in proposal.md)

**Implementation** (`theauditor/context/query.py:1375-1478`):
```python
if ext == "go":
    cursor.execute(
        """
        SELECT framework, method, path, handler_func, line
        FROM go_routes
        WHERE file LIKE ?
        """,
        (f"%{normalized_path}",),
    )
    routes = [dict(row) for row in cursor.fetchall()]
    if routes:
        result["framework"] = routes[0].get("framework", "go")
        result["routes"] = routes
```

### Decision 4: Create `rust_attributes` table for Rust handler detection

**What:** Add new `rust_attributes` table and use it for route attribute detection.

**Why:**
- `rust_macro_invocations` only captures `macro_invocation` nodes (like `println!()`)
- Route attributes like `#[get("/users")]` are `attribute_item` nodes in tree-sitter
- These are **different AST node types** - macros vs attributes
- Verified via tree-sitter: `#[get("/")]` parses as `attribute_item`, NOT `macro_invocation`

**BLOCKER:** Must implement `rust_attributes` table before these tasks:
- Task 3.2: Explain Rust handlers
- Task 4.x: Deadcode Rust entry points
- Task 5.x: Boundaries Rust entry points

### Decision 5: Add Go/Rust entry points to deadcode detection

**What:** Modify `deadcode_graph.py` to query Go/Rust tables for entry point detection.

**Why:**
- Current implementation only queries Python/JS tables
- Go main packages, web handlers are being reported as dead code
- Rust main.rs, route handlers are being reported as dead code

**Implementation** (`theauditor/context/deadcode_graph.py:255-269`):
```python
def _find_framework_entry_points(self) -> set[str]:
    """Query repo_index.db for framework-specific entry points."""
    cursor = self.repo_conn.cursor()
    entry_points = set()

    # Existing Python/JS queries...
    cursor.execute("SELECT DISTINCT file FROM react_components")
    entry_points.update(row[0] for row in cursor.fetchall())

    # ADD: Go routes
    cursor.execute("SELECT DISTINCT file FROM go_routes")
    entry_points.update(row[0] for row in cursor.fetchall())

    # ADD: Go main functions
    cursor.execute("""
        SELECT DISTINCT file FROM go_functions
        WHERE name = 'main'
    """)
    entry_points.update(row[0] for row in cursor.fetchall())

    # ADD: Rust route attributes (requires rust_attributes table)
    cursor.execute("""
        SELECT DISTINCT file_path FROM rust_attributes
        WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route')
    """)
    entry_points.update(row[0] for row in cursor.fetchall())

    # ADD: Rust main functions
    cursor.execute("""
        SELECT DISTINCT file_path FROM rust_functions
        WHERE name = 'main'
    """)
    entry_points.update(row[0] for row in cursor.fetchall())

    return entry_points
```

### Decision 6: Add Go/Rust entry points to boundaries detection

**What:** Modify `boundaries.py` to detect Go/Rust HTTP entry points.

**Why:**
- Current implementation only detects Python/JS routes
- Go gin/echo handlers need to be detected as entry points
- Rust actix-web/axum handlers need to be detected as entry points

**Implementation:**
```python
def _get_entry_points(self, db_path: str, boundary_type: str) -> list[dict]:
    """Get entry points for boundary analysis."""
    entry_points = []

    # Existing Python/JS detection...

    # ADD: Go routes
    cursor.execute("""
        SELECT file, line, framework, method, path, handler_func
        FROM go_routes
    """)
    for row in cursor.fetchall():
        entry_points.append({
            "file": row[0],
            "line": row[1],
            "language": "go",
            "framework": row[2],
            "method": row[3],
            "path": row[4],
            "handler": row[5],
        })

    # ADD: Rust routes (requires rust_attributes)
    cursor.execute("""
        SELECT a.file_path, a.line, a.attribute_name, a.args, f.name
        FROM rust_attributes a
        JOIN rust_functions f ON a.file_path = f.file_path AND a.target_line = f.line
        WHERE a.attribute_name IN ('get', 'post', 'put', 'delete', 'route')
    """)
    for row in cursor.fetchall():
        entry_points.append({
            "file": row[0],
            "line": row[1],
            "language": "rust",
            "framework": "actix-web",  # or detect from imports
            "method": row[2].upper(),
            "path": row[3],
            "handler": row[4],
        })

    return entry_points
```

### Decision 7: Add Go/Rust validation pattern detection

**What:** Detect Go/Rust validation patterns as control points in boundaries.

**Why:**
- Go uses `ShouldBindJSON`, `validator.Struct` patterns
- Rust uses `web::Json<T>` extractors, `#[validate]` derives
- These need to be detected to measure boundary distance

**Go validation patterns:**
```python
GO_VALIDATION_PATTERNS = [
    "ShouldBindJSON",
    "ShouldBindQuery",
    "ShouldBindUri",
    "BindJSON",
    "Bind",
    "validator.Struct",
    "validate.Struct",
]
```

**Rust validation patterns:**
```python
RUST_VALIDATION_PATTERNS = [
    "web::Json",
    "web::Path",
    "web::Query",
    "Json<",
    "Path<",
    "Query<",
    ".validate()",
]
```

### Decision 8: Extension-based language detection in explain

**What:** Add `.go` and `.rs` to the extension check in `get_file_framework_info()`.

**Why:**
- Existing pattern uses `ext == "py"` and `ext in ("ts", "js")` checks
- Simple, no new abstraction needed
- Maintains single code path per language

**Code location:** `theauditor/context/query.py:1375-1478`

---

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Go/Rust tables empty | Low | No output shown | Verify extraction working in task 0.2 |
| SQL REGEXP not supported | Low | Query fails | SQLite supports REGEXP via extension, already used for Py/JS |
| Performance degradation | Low | Slow queries | Single JOIN query, not N+1 pattern |
| go_routes not populated | HIGH | Go detection fails | BLOCKER 2 - must implement route extraction first |
| rust_attributes missing | HIGH | Rust detection fails | BLOCKER 1 - must implement first |

---

## Migration Plan

**Schema additions required:**
1. Add `CARGO_PACKAGE_CONFIGS` to `infrastructure_schema.py`
2. Add `GO_MODULE_CONFIGS` to `go_schema.py`
3. Add `RUST_ATTRIBUTES` to `rust_schema.py`
4. Add all to their respective `*_TABLES` dicts
5. Run `aud full` to create new tables

**No data migration needed.** All changes are additive:
- New CASE clauses in existing SQL query
- New dict keys in return values
- New extension checks in existing if-else chain
- New table queries in deadcode/boundaries

**Rollback:** Revert commits. Drop new tables if created.

---

## Resolved Questions

1. **Are Cargo.toml dependencies stored in database?**
   - **ANSWER: NO** - Verified no `cargo_package_configs` table exists in any schema file
   - **Action:** Create `CARGO_PACKAGE_CONFIGS` in `infrastructure_schema.py`

2. **Does Rust attribute extraction exist?**
   - **ANSWER: NO** - `rust_macro_invocations` only captures macro calls like `println!()`
   - Route attributes like `#[get("/")]` are `attribute_item` nodes in tree-sitter, NOT `macro_invocation`
   - **Action:** Create `rust_attributes` table and extraction function (see task 0.3)
   - **BLOCKER for tasks 3.2, 4.x, 5.x** - Cannot detect Rust handlers without this

3. **Should Bash be included in deps output?**
   - **ANSWER: NO** - Bash has no package manager (no Cargo.toml/go.mod/package.json equivalent)
   - **Action:** Only show Go and Rust in addition to existing npm/pip

4. **Should Bash be included in boundaries output?**
   - **ANSWER: NO** - Bash scripts are not HTTP services
   - **Action:** Deadcode only for Bash (shebang-based entry point detection)

5. **How to detect Go main packages?**
   - **ANSWER:** Query `go_functions` where `name = 'main'`
   - Alternatively: Check `package main` declaration, but function query is simpler

6. **How to detect Rust main functions?**
   - **ANSWER:** Query `rust_functions` where `name = 'main'`
   - Also detect `src/bin/*.rs` files as binary entry points
