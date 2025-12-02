# Tasks: Add Polyglot Planning Support

## 0. Verification (Pre-Implementation Checks)
- [ ] 0.1 Confirm Go/Rust/Bash symbols exist in `symbols` table
  ```sql
  SELECT f.ext, COUNT(*) FROM symbols s JOIN files f ON s.path = f.path
  WHERE f.ext IN ('.go', '.rs', '.sh') GROUP BY f.ext
  ```
- [ ] 0.2 Confirm `go_routes` table has data (if Go web frameworks used)
  ```sql
  SELECT framework, COUNT(*) FROM go_routes GROUP BY framework
  ```
- [ ] 0.3 **BLOCKER:** Rust attribute extraction does not exist yet

  **Problem:** `rust_macro_invocations` only captures macro calls like `println!()`.
  Route attributes like `#[get("/users")]` are `attribute_item` nodes in tree-sitter,
  NOT `macro_invocation` nodes. Task 3.2 depends on this data.

  **Required before task 3.2:**
  - Add `rust_attributes` table to `rust_schema.py`
  - Add `extract_rust_attributes()` to `rust_impl.py`
  - Wire into `RustExtractor` and storage handler

  **Schema design:**
  ```python
  RUST_ATTRIBUTES = TableSchema(
      name="rust_attributes",
      columns=[
          Column("file_path", "TEXT", nullable=False),
          Column("line", "INTEGER", nullable=False),
          Column("attribute_name", "TEXT", nullable=False),  # e.g., "get", "derive", "serde"
          Column("args", "TEXT"),  # e.g., '"/users"', 'Debug, Serialize'
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

  **Verification query (after implementation):**
  ```sql
  SELECT attribute_name, COUNT(*) FROM rust_attributes
  WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route') GROUP BY attribute_name
  ```

## 1. Blueprint Naming Conventions

### 1.1 Modify SQL query in `_get_naming_conventions()`
**File:** `theauditor/commands/blueprint.py:335-375`

Add these CASE clauses after TypeScript (line 371):
```sql
-- Go functions
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_func_snake,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_camel,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_pascal,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' THEN 1 ELSE 0 END) AS go_func_total,

-- Go structs (type = 'class' in symbols table)
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_struct_snake,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_struct_pascal,
SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' THEN 1 ELSE 0 END) AS go_struct_total,

-- Rust functions
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_func_snake,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_camel,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_pascal,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' THEN 1 ELSE 0 END) AS rs_func_total,

-- Rust structs
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_struct_snake,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_struct_pascal,
SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' THEN 1 ELSE 0 END) AS rs_struct_total,

-- Bash functions
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS bash_func_snake,
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' AND s.name REGEXP '^[A-Z_][A-Z0-9_]*$' THEN 1 ELSE 0 END) AS bash_func_screaming,
SUM(CASE WHEN f.ext = '.sh' AND s.type = 'function' THEN 1 ELSE 0 END) AS bash_func_total
```

- [ ] 1.1.1 Add Go CASE clauses (4 lines: snake, camel, pascal, total)
- [ ] 1.1.2 Add Go struct CASE clauses (3 lines: snake, pascal, total)
- [ ] 1.1.3 Add Rust function CASE clauses (4 lines)
- [ ] 1.1.4 Add Rust struct CASE clauses (3 lines)
- [ ] 1.1.5 Add Bash function CASE clauses (3 lines: snake, screaming, total)

### 1.2 Extend conventions dict return value
**File:** `theauditor/commands/blueprint.py:379-392`

Current row indices end at 23. New indices:
- Go: rows 24-30 (go_func_snake, camel, pascal, total, go_struct_snake, pascal, total)
- Rust: rows 31-37
- Bash: rows 38-40

```python
conventions = {
    "python": {...},      # rows 0-7
    "javascript": {...},  # rows 8-15
    "typescript": {...},  # rows 16-23
    "go": {
        "functions": _build_pattern_result(row[24], row[25], row[26], row[27]),
        "structs": _build_pattern_result(row[28], 0, row[29], row[30]),  # No camelCase for structs
    },
    "rust": {
        "functions": _build_pattern_result(row[31], row[32], row[33], row[34]),
        "structs": _build_pattern_result(row[35], 0, row[36], row[37]),
    },
    "bash": {
        "functions": _build_pattern_result_bash(row[38], row[39], row[40]),
    },
}
```

- [ ] 1.2.1 Add `"go"` dict with functions and structs keys
- [ ] 1.2.2 Add `"rust"` dict with functions and structs keys
- [ ] 1.2.3 Add `"bash"` dict with functions key only
- [ ] 1.2.4 Create `_build_pattern_result_bash()` helper for snake/screaming pattern

### 1.3 Manual test
- [ ] 1.3.1 Run `aud blueprint --structure` on this repo
- [ ] 1.3.2 Verify Go/Rust/Bash sections appear in output
- [ ] 1.3.3 Verify counts match expectations

## 2. Blueprint Dependencies

### 2.1 Add cargo_package_configs schema
**File:** `theauditor/indexer/schemas/infrastructure_schema.py` (after line 640)

```python
CARGO_PACKAGE_CONFIGS = TableSchema(
    name="cargo_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("package_name", "TEXT"),
        Column("version", "TEXT"),
        Column("edition", "TEXT"),
        Column("dependencies", "TEXT"),
        Column("dev_dependencies", "TEXT"),
        Column("build_dependencies", "TEXT"),
    ],
    indexes=[
        ("idx_cargo_configs_name", ["package_name"]),
    ],
)
```

- [ ] 2.1.1 Add `CARGO_PACKAGE_CONFIGS` TableSchema definition
- [ ] 2.1.2 Add to `INFRASTRUCTURE_TABLES` dict

### 2.2 Add go_module_configs schema
**File:** `theauditor/indexer/schemas/go_schema.py` (after line 358)

```python
GO_MODULE_CONFIGS = TableSchema(
    name="go_module_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False, primary_key=True),
        Column("module_path", "TEXT", nullable=False),
        Column("go_version", "TEXT"),
        Column("dependencies", "TEXT"),
        Column("replacements", "TEXT"),
    ],
    indexes=[
        ("idx_go_module_path", ["module_path"]),
    ],
)
```

- [ ] 2.2.1 Add `GO_MODULE_CONFIGS` TableSchema definition
- [ ] 2.2.2 Add to `GO_TABLES` dict

### 2.3 Wire Cargo.toml parsing to database storage
**File:** `theauditor/framework_detector.py:590-626`

The `_parse_cargo_toml()` function in `deps.py:405` parses Cargo.toml but doesn't store.

- [ ] 2.3.1 Add storage handler in indexer pipeline to call after Cargo.toml detection
- [ ] 2.3.2 Store parsed data to `cargo_package_configs` table
- [ ] 2.3.3 Call during `aud full` indexing phase

### 2.4 Wire go.mod parsing to database storage
**File:** `theauditor/manifest_parser.py`

- [ ] 2.4.1 Verify go.mod parsing exists (or add if missing)
- [ ] 2.4.2 Add storage handler to write to `go_module_configs`
- [ ] 2.4.3 Call during `aud full` indexing phase

### 2.5 Modify `_get_dependencies()` to query new tables
**File:** `theauditor/commands/blueprint.py:1264-1366`

Add after pip query block (line ~1364):

```python
# Cargo packages
cursor.execute("""
    SELECT file_path, package_name, version, dependencies, dev_dependencies
    FROM cargo_package_configs
""")
for row in cursor.fetchall():
    file_path = row["file_path"]
    pkg_name = row["package_name"]
    version = row["version"]

    prod_deps = json.loads(row["dependencies"]) if row["dependencies"] else {}
    dev_deps = json.loads(row["dev_dependencies"]) if row["dev_dependencies"] else {}

    workspace = {
        "file": file_path,
        "name": pkg_name,
        "version": version,
        "manager": "cargo",
        "prod_count": len(prod_deps),
        "dev_count": len(dev_deps),
    }
    deps["workspaces"].append(workspace)

    deps["by_manager"]["cargo"] = deps["by_manager"].get("cargo", 0) + len(prod_deps) + len(dev_deps)
    deps["total"] += len(prod_deps) + len(dev_deps)

# Go modules
cursor.execute("""
    SELECT file_path, module_path, go_version, dependencies
    FROM go_module_configs
""")
for row in cursor.fetchall():
    # Similar pattern...
```

- [ ] 2.5.1 Add Cargo query block after pip query
- [ ] 2.5.2 Add Go modules query block after Cargo
- [ ] 2.5.3 Update workspace and packages lists with results

### 2.6 Manual test
- [ ] 2.6.1 Run `aud full --offline` on a repo with Cargo.toml
- [ ] 2.6.2 Run `aud blueprint --deps` and verify cargo deps appear
- [ ] 2.6.3 Repeat for go.mod if available

## 3. Explain Framework Info

### 3.1 Add Go handler detection
**File:** `theauditor/context/query.py:1439-1478`

Add after Python decorator detection (around line 1463):

```python
if ext == "go":
    # Primary: Query go_routes table
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
    else:
        # Secondary: Detect handlers via param types
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

- [ ] 3.1.1 Add `if ext == "go":` block
- [ ] 3.1.2 Query `go_routes` table first
- [ ] 3.1.3 Query `go_func_params` for handler patterns if no routes found

### 3.2 Add Rust handler detection
**File:** `theauditor/context/query.py:1439-1478`

**DEPENDS ON:** Task 0.3 (rust_attributes table must be implemented first)

Add after Go handler detection:

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
        result["framework"] = "actix-web"  # Or detect from attributes
        result["handlers"] = handlers
```

- [ ] 3.2.1 Complete task 0.3 (rust_attributes implementation) first
- [ ] 3.2.2 Add `if ext == "rs":` block
- [ ] 3.2.3 Query `rust_attributes` joined with `rust_functions`
- [ ] 3.2.4 Filter by route attribute names

### 3.3 Manual test
- [ ] 3.3.1 Run `aud explain <go_handler.go>` and verify routes shown
- [ ] 3.3.2 Run `aud explain <rust_handler.rs>` and verify handlers shown
- [ ] 3.3.3 Run `aud explain <file.go>` with no handlers, verify no error

## 4. Testing

- [ ] 4.1 Add unit test for Go naming convention detection
- [ ] 4.2 Add unit test for Rust naming convention detection
- [ ] 4.3 Add unit test for Bash naming convention detection
- [ ] 4.4 Add unit test for Cargo dependency parsing
- [ ] 4.5 Add unit test for Go module dependency parsing
- [ ] 4.6 Add unit test for Go handler detection
- [ ] 4.7 Add unit test for Rust handler detection
- [ ] 4.8 Run full `aud full --offline` on test polyglot repo
- [ ] 4.9 Verify no regression in Python/JS/TS output

## 5. Cleanup

- [ ] 5.1 Run `ruff format` on modified Python files
- [ ] 5.2 Run `ruff check` for linting issues
- [ ] 5.3 Remove any TODO comments added during implementation
- [ ] 5.4 Final manual verification of all three commands
