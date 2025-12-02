# Design: Add Polyglot Planning Support

## Context

TheAuditor indexes code from multiple languages (Python, JavaScript, TypeScript, Go, Rust, Bash) into a unified SQLite database. The planning commands (`aud blueprint`, `aud explain`) query this database but currently only consume Python/JS/TS data due to hardcoded extension checks and language-specific queries.

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
- Maintain performance (<100ms for typical queries)

**Non-Goals:**
- Changing output format (additive only)
- Wiring ORM detection to refactor command (future work)
- Adding Bash handler detection (Bash doesn't have HTTP handlers)

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

**rust_functions** (`theauditor/indexer/schemas/rust_schema.py:49-73`):
```python
RUST_FUNCTIONS = TableSchema(
    name="rust_functions",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("is_async", "BOOLEAN", default="0"),
        Column("return_type", "TEXT"),
        Column("params_json", "TEXT"),  # JSON array of params
    ],
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

## Decisions

### Decision 1: Query `symbols` table for naming conventions

**What:** For naming conventions, query the unified `symbols` table with extension-based filtering.

**Why:**
- `symbols` table already contains all functions/classes across languages
- Extension filtering via `files.ext` JOIN is consistent with existing pattern
- Avoids N+1 queries to language-specific tables

**Implementation** (`theauditor/commands/blueprint.py:335-375`):
```sql
-- Add these CASE clauses to existing query in _get_naming_conventions()
-- Go functions (snake_case for private, PascalCase for exported)
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_func_snake,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_camel,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_pascal,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' THEN 1 ELSE 0 END) AS go_func_total,

-- Go structs
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_struct_snake,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_struct_pascal,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' THEN 1 ELSE 0 END) AS go_struct_total,

-- Rust functions (snake_case standard)
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_func_snake,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_camel,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_pascal,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' THEN 1 ELSE 0 END) AS rs_func_total,

-- Rust structs (PascalCase standard)
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_struct_snake,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_struct_pascal,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' THEN 1 ELSE 0 END) AS rs_struct_total,

-- Bash functions (snake_case standard)
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS bash_func_snake,
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' AND s.name REGEXP '^[A-Z_][A-Z0-9_]*$' THEN 1 ELSE 0 END) AS bash_func_screaming,
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' THEN 1 ELSE 0 END) AS bash_func_total,
```

### Decision 2: Create new tables for Cargo/Go dependencies

**What:** Add `cargo_package_configs` and `go_module_configs` tables to store manifest data.

**Why:**
- These tables DO NOT currently exist (verified against all schema files)
- `framework_detector.py` parses Cargo.toml and go.mod but stores results in-memory only
- ZFP requires storing during indexing, not parsing at query time

**Implementation:**
1. Add schema definitions (see Schema Reference above)
2. Add storage handlers called during `aud full` indexing phase
3. Query in `_get_dependencies()` same pattern as npm/pip

### Decision 3: Use `go_routes` table for Go handler detection

**What:** Query existing `go_routes` table for Go web framework handlers.

**Why:**
- Table already exists with framework, method, path, handler_func columns
- Populated during Go extraction phase
- No need for complex param-type pattern matching

**Implementation** (`theauditor/context/query.py:1439-1478`):
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

**Fallback for files without routes** (use `go_func_params` for handler detection):
```python
if not routes:
    cursor.execute(
        """
        SELECT DISTINCT f.name, f.line, p.param_type
        FROM go_functions f
        JOIN go_func_params p ON f.file = p.file AND f.name = p.func_name
        WHERE f.file LIKE ?
          AND (p.param_type LIKE '%gin.Context%'
            OR p.param_type LIKE '%echo.Context%'
            OR p.param_type LIKE '%http.ResponseWriter%')
        """,
        (f"%{normalized_path}",),
    )
    handlers = [dict(row) for row in cursor.fetchall()]
    if handlers:
        result["handlers"] = handlers
```

### Decision 4: Create `rust_attributes` table for Rust handler detection

**What:** Add new `rust_attributes` table and use it for route attribute detection.

**Why:**
- `rust_macro_invocations` only captures `macro_invocation` nodes (like `println!()`)
- Route attributes like `#[get("/users")]` are `attribute_item` nodes in tree-sitter
- These are **different AST node types** - macros vs attributes
- Verified via tree-sitter: `#[get("/")]` parses as `attribute_item`, NOT `macro_invocation`

**BLOCKER:** Must implement `rust_attributes` table before this task. See task 0.3 in tasks.md.

**Schema** (add to `theauditor/indexer/schemas/rust_schema.py`):
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

**Implementation** (after rust_attributes exists):
```python
if ext == "rs":
    cursor.execute(
        """
        SELECT f.name, f.line, a.attribute_name, a.args
        FROM rust_functions f
        JOIN rust_attributes a
          ON f.file_path = a.file_path
          AND f.line = a.target_line
        WHERE f.file_path LIKE ?
          AND a.attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route', 'head', 'options')
        """,
        (f"%{normalized_path}",),
    )
    handlers = [dict(row) for row in cursor.fetchall()]
    if handlers:
        result["framework"] = "actix-web"  # or detect from attributes
        result["handlers"] = handlers
```

### Decision 5: Extension-based language detection in explain

**What:** Add `.go` and `.rs` to the extension check in `get_file_framework_info()`.

**Why:**
- Existing pattern uses `ext == "py"` and `ext in ("ts", "js")` checks
- Simple, no new abstraction needed
- Maintains single code path per language

**Code location:** `theauditor/context/query.py:1439-1478`

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Go/Rust tables empty | Low | No output shown | Verify extraction working in task 0.2 |
| SQL REGEXP not supported | Low | Query fails | SQLite supports REGEXP via extension, already used for Py/JS |
| Performance degradation | Low | Slow queries | Single JOIN query, not N+1 pattern |
| go_routes not populated | Medium | Fall back to param detection | Use go_func_params as secondary source |

## Migration Plan

**Schema additions required:**
1. Add `CARGO_PACKAGE_CONFIGS` to `infrastructure_schema.py`
2. Add `GO_MODULE_CONFIGS` to `go_schema.py`
3. Add both to their respective `*_TABLES` dicts
4. Run `aud full` to create new tables

**No data migration needed.** All changes are additive:
- New CASE clauses in existing SQL query
- New dict keys in return values
- New extension checks in existing if-else chain

**Rollback:** Revert commits. Drop new tables if created.

## Resolved Questions

1. **Are Cargo.toml dependencies stored in database?**
   - **ANSWER: NO** - Verified no `cargo_package_configs` table exists in any schema file
   - **Action:** Create `CARGO_PACKAGE_CONFIGS` in `infrastructure_schema.py`

2. **Does Rust attribute extraction exist?**
   - **ANSWER: NO** - `rust_macro_invocations` only captures macro calls like `println!()`
   - Route attributes like `#[get("/")]` are `attribute_item` nodes in tree-sitter, NOT `macro_invocation`
   - **Action:** Create `rust_attributes` table and extraction function (see task 0.3)
   - **BLOCKER for task 3.2** - Cannot detect Rust handlers without this

3. **Should Bash be included in deps output?**
   - **ANSWER: NO** - Bash has no package manager (no Cargo.toml/go.mod/package.json equivalent)
   - **Action:** Only show Go and Rust in addition to existing npm/pip
