## Context

TheAuditor supports Python (35 dedicated tables, full framework detection, security rules) and JavaScript/TypeScript (50+ tables, React/Vue/Angular detection). Go has zero support despite being the dominant language for cloud-native infrastructure.

Go presents unique characteristics vs Python/JS:
- **Goroutines/channels** - concurrency primitives need tracking for race condition analysis
- **Interfaces** - implicit satisfaction (no "implements" keyword), duck typing
- **Error handling** - explicit `error` returns, no exceptions
- **Defer** - cleanup mechanism that affects control flow
- **Pointers** - explicit but safe (no arithmetic), affects data flow

## Goals / Non-Goals

**Goals:**
- Parity with Python/JS for core extraction (symbols, calls, imports, data flow)
- Go-specific constructs (interfaces, goroutines, channels, defer, error returns)
- Framework detection for major web frameworks (Gin, Echo, Fiber, Chi)
- Security rules targeting Go-specific vulnerabilities
- Data stored in normalized tables, queryable via existing `aud context` commands

**Non-Goals:**
- Type inference (leave that to the Go compiler)
- CGO/FFI analysis (C interop is edge case)
- Build tag/constraint analysis (too fragile)
- Assembly files (.s)

**CRITICAL: Generics (Go 1.18+) ARE a goal.** The tree-sitter-go grammar MUST support Go 1.18+ syntax or parsing will fail completely on `func[T any]`. Store syntactic type parameter info even if we don't resolve them.

## Implementation Reference Points

These are the exact files to use as templates. Read these BEFORE implementing.

### Architecture Overview

```
ast_parser.py                      ← Add tree-sitter-go here
       │
       ▼ Returns type="tree_sitter" with parsed tree
       │
indexer/extractors/go.py           ← NEW: Thin wrapper (like terraform.py)
       │
       ▼ Calls extraction functions
       │
ast_extractors/go_impl.py          ← NEW: Tree-sitter queries (like hcl_impl.py)
```

**Key insight**: Go follows the HCL/Terraform pattern, NOT Python or JS/TS.
- Python uses built-in `ast` module (no tree-sitter)
- JS/TS uses external Node.js semantic parser (no tree-sitter)
- HCL uses tree-sitter directly → **Go will do the same**

### Reference Files

| Component | Reference File | What to Copy |
|-----------|----------------|--------------|
| **AST Extraction (tree-sitter)** | `ast_extractors/hcl_impl.py` | Tree-sitter node traversal pattern |
| **Extractor wrapper** | `indexer/extractors/terraform.py` | Calls *_impl.py, handles tree dict |
| Schema pattern | `indexer/schemas/python_schema.py:1-95` | TableSchema with Column, indexes |
| Database mixin | `indexer/database/python_database.py:6-60` | add_* methods using generic_batches |
| Mixin registration | `indexer/database/__init__.py:17-27` | Add GoDatabaseMixin to class composition |
| Storage handlers | `indexer/storage/python_storage.py:1-80` | Handler dict pattern |
| Storage wiring | `indexer/storage/__init__.py:20-30` | Add GoStorage to DataStorer |
| Extractor base | `indexer/extractors/__init__.py:12-31` | BaseExtractor interface |
| Extractor auto-discovery | `indexer/extractors/__init__.py:86-118` | Just create file, auto-registers |
| AST parser init | `ast_parser.py:52-103` | Add Go to _init_tree_sitter_parsers |
| Extension mapping | `ast_parser.py:240-253` | Add .go to ext_map |

**DO NOT reference**: `treesitter_impl.py` (deleted - was dead code)

## Decisions

### Decision 1: Schema design - 18 normalized tables

Full TableSchema definitions for `indexer/schemas/go_schema.py`:

```python
"""Go-specific schema definitions."""

from .utils import Column, TableSchema

GO_PACKAGES = TableSchema(
    name="go_packages",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("import_path", "TEXT"),
    ],
    primary_key=["file"],
    indexes=[
        ("idx_go_packages_name", ["name"]),
    ],
)

GO_IMPORTS = TableSchema(
    name="go_imports",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("path", "TEXT", nullable=False),
        Column("alias", "TEXT"),
        Column("is_dot_import", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_imports_file", ["file"]),
        ("idx_go_imports_path", ["path"]),
    ],
)

GO_STRUCTS = TableSchema(
    name="go_structs",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_structs_file", ["file"]),
        ("idx_go_structs_name", ["name"]),
    ],
)

GO_STRUCT_FIELDS = TableSchema(
    name="go_struct_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("struct_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT", nullable=False),
        Column("tag", "TEXT"),
        Column("is_embedded", "BOOLEAN", default="0"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "struct_name", "field_name"],
    indexes=[
        ("idx_go_struct_fields_struct", ["struct_name"]),
    ],
)

GO_INTERFACES = TableSchema(
    name="go_interfaces",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("doc_comment", "TEXT"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_interfaces_file", ["file"]),
        ("idx_go_interfaces_name", ["name"]),
    ],
)

GO_INTERFACE_METHODS = TableSchema(
    name="go_interface_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("interface_name", "TEXT", nullable=False),
        Column("method_name", "TEXT", nullable=False),
        Column("signature", "TEXT", nullable=False),
    ],
    primary_key=["file", "interface_name", "method_name"],
    indexes=[
        ("idx_go_interface_methods_interface", ["interface_name"]),
    ],
)

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
    indexes=[
        ("idx_go_functions_file", ["file"]),
        ("idx_go_functions_name", ["name"]),
    ],
)

GO_METHODS = TableSchema(
    name="go_methods",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("receiver_type", "TEXT", nullable=False),
        Column("receiver_name", "TEXT"),
        Column("is_pointer_receiver", "BOOLEAN", default="0"),
        Column("name", "TEXT", nullable=False),
        Column("signature", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "receiver_type", "name"],
    indexes=[
        ("idx_go_methods_file", ["file"]),
        ("idx_go_methods_receiver", ["receiver_type"]),
        ("idx_go_methods_name", ["name"]),
    ],
)

GO_FUNC_PARAMS = TableSchema(
    name="go_func_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("func_line", "INTEGER", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT"),
        Column("param_type", "TEXT", nullable=False),
        Column("is_variadic", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "func_name", "func_line", "param_index"],
    indexes=[
        ("idx_go_func_params_func", ["func_name"]),
    ],
)

GO_FUNC_RETURNS = TableSchema(
    name="go_func_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("func_line", "INTEGER", nullable=False),
        Column("return_index", "INTEGER", nullable=False),
        Column("return_name", "TEXT"),
        Column("return_type", "TEXT", nullable=False),
    ],
    primary_key=["file", "func_name", "func_line", "return_index"],
    indexes=[
        ("idx_go_func_returns_func", ["func_name"]),
    ],
)

GO_GOROUTINES = TableSchema(
    name="go_goroutines",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("containing_func", "TEXT"),
        Column("spawned_expr", "TEXT", nullable=False),
        Column("is_anonymous", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_go_goroutines_file", ["file"]),
        ("idx_go_goroutines_func", ["containing_func"]),
    ],
)

GO_CHANNELS = TableSchema(
    name="go_channels",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("element_type", "TEXT"),
        Column("direction", "TEXT"),  -- "send", "receive", "bidirectional"
        Column("buffer_size", "INTEGER"),
    ],
    indexes=[
        ("idx_go_channels_file", ["file"]),
        ("idx_go_channels_name", ["name"]),
    ],
)

GO_CHANNEL_OPS = TableSchema(
    name="go_channel_ops",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("channel_name", "TEXT"),
        Column("operation", "TEXT", nullable=False),  -- "send" or "receive"
        Column("containing_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_channel_ops_file", ["file"]),
        ("idx_go_channel_ops_channel", ["channel_name"]),
    ],
)

GO_DEFER_STATEMENTS = TableSchema(
    name="go_defer_statements",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("containing_func", "TEXT"),
        Column("deferred_expr", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_go_defer_file", ["file"]),
        ("idx_go_defer_func", ["containing_func"]),
    ],
)

GO_ERROR_RETURNS = TableSchema(
    name="go_error_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("func_name", "TEXT", nullable=False),
        Column("returns_error", "BOOLEAN", default="1"),
    ],
    indexes=[
        ("idx_go_error_returns_file", ["file"]),
        ("idx_go_error_returns_func", ["func_name"]),
    ],
)

GO_TYPE_ASSERTIONS = TableSchema(
    name="go_type_assertions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("expr", "TEXT", nullable=False),
        Column("asserted_type", "TEXT", nullable=False),
        Column("is_type_switch", "BOOLEAN", default="0"),
        Column("containing_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_type_assertions_file", ["file"]),
    ],
)

GO_ROUTES = TableSchema(
    name="go_routes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("method", "TEXT"),
        Column("path", "TEXT"),
        Column("handler_func", "TEXT"),
    ],
    indexes=[
        ("idx_go_routes_file", ["file"]),
        ("idx_go_routes_framework", ["framework"]),
    ],
)

GO_CONSTANTS = TableSchema(
    name="go_constants",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("value", "TEXT"),
        Column("type", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "name"],
    indexes=[
        ("idx_go_constants_file", ["file"]),
        ("idx_go_constants_name", ["name"]),
    ],
)

GO_VARIABLES = TableSchema(
    name="go_variables",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT"),
        Column("initial_value", "TEXT"),
        Column("is_exported", "BOOLEAN", default="0"),
        Column("is_package_level", "BOOLEAN", default="0"),  # Critical for race detection
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_go_variables_file", ["file"]),
        ("idx_go_variables_name", ["name"]),
        ("idx_go_variables_package_level", ["is_package_level"]),  # For security queries
    ],
)

GO_TYPE_PARAMS = TableSchema(
    name="go_type_params",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("parent_name", "TEXT", nullable=False),  # Function or type name
        Column("parent_kind", "TEXT", nullable=False),  # "function" or "type"
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("constraint", "TEXT"),  # "any", "comparable", interface name, etc.
    ],
    primary_key=["file", "parent_name", "param_index"],
    indexes=[
        ("idx_go_type_params_parent", ["parent_name"]),
    ],
)

GO_CAPTURED_VARS = TableSchema(
    name="go_captured_vars",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),  # Line of the goroutine spawn
        Column("goroutine_id", "INTEGER", nullable=False),  # Links to go_goroutines rowid
        Column("var_name", "TEXT", nullable=False),
        Column("var_type", "TEXT"),
        Column("is_loop_var", "BOOLEAN", default="0"),  # Critical for race detection
    ],
    indexes=[
        ("idx_go_captured_vars_file", ["file"]),
        ("idx_go_captured_vars_goroutine", ["goroutine_id"]),
    ],
)

GO_MIDDLEWARE = TableSchema(
    name="go_middleware",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("router_var", "TEXT"),  # e.g., "router", "r", "app"
        Column("middleware_func", "TEXT", nullable=False),  # The handler/middleware name
        Column("is_global", "BOOLEAN", default="0"),  # Applied to all routes vs specific
    ],
    indexes=[
        ("idx_go_middleware_file", ["file"]),
        ("idx_go_middleware_framework", ["framework"]),
    ],
)

# Export all tables
GO_TABLES = {
    "go_packages": GO_PACKAGES,
    "go_imports": GO_IMPORTS,
    "go_structs": GO_STRUCTS,
    "go_struct_fields": GO_STRUCT_FIELDS,
    "go_interfaces": GO_INTERFACES,
    "go_interface_methods": GO_INTERFACE_METHODS,
    "go_functions": GO_FUNCTIONS,
    "go_methods": GO_METHODS,
    "go_func_params": GO_FUNC_PARAMS,
    "go_func_returns": GO_FUNC_RETURNS,
    "go_goroutines": GO_GOROUTINES,
    "go_channels": GO_CHANNELS,
    "go_channel_ops": GO_CHANNEL_OPS,
    "go_defer_statements": GO_DEFER_STATEMENTS,
    "go_error_returns": GO_ERROR_RETURNS,
    "go_type_assertions": GO_TYPE_ASSERTIONS,
    "go_routes": GO_ROUTES,
    "go_constants": GO_CONSTANTS,
    "go_variables": GO_VARIABLES,
    "go_type_params": GO_TYPE_PARAMS,
    "go_captured_vars": GO_CAPTURED_VARS,
    "go_middleware": GO_MIDDLEWARE,
}
```

**Total: 22 tables** (18 original + go_variables + go_type_params + go_captured_vars + go_middleware)

### Decision 2: Tree-sitter-go node types reference

Verified via `tree-sitter-language-pack`. These are the exact node types to query:

| Go Construct | Tree-sitter Node Type | Child Nodes |
|--------------|----------------------|-------------|
| Package | `package_clause` | `package_identifier` |
| Import | `import_declaration` | `import_spec_list` > `import_spec` |
| Struct | `type_declaration` | `type_spec` > `struct_type` > `field_declaration_list` |
| Interface | `type_declaration` | `type_spec` > `interface_type` > `method_spec_list` |
| Function | `function_declaration` | `identifier`, `parameter_list`, `result` (return), `block` |
| Method | `method_declaration` | `parameter_list` (receiver), `field_identifier`, `parameter_list`, `result` |
| Go statement | `go_statement` | `call_expression` or `func_literal` |
| Channel make | `call_expression` | `identifier` == "make", `type_identifier` == "chan" |
| Channel send | `send_statement` | `identifier`, `<-`, expression |
| Channel receive | `receive_statement` | `<-`, `identifier` |
| Defer | `defer_statement` | `call_expression` |
| Const | `const_declaration` | `const_spec` > `identifier`, `expression` |
| Type assertion | `type_assertion_expression` | expression, `.(`, `type_identifier`, `)` |
| Type switch | `type_switch_statement` | `type_switch_guard`, `type_case_clause` |

**Extraction pattern** (from `ast_extractors/go_impl.py`):
```python
def extract_go_functions(tree, content: bytes, file_path: str) -> list[dict]:
    """Extract function declarations from Go AST."""
    functions = []

    # Query for function_declaration nodes
    query = tree.language.query("""
        (function_declaration
            name: (identifier) @name
            parameters: (parameter_list) @params
            result: (_)? @returns
            body: (block) @body
        ) @func
    """)

    for match in query.matches(tree.root_node):
        # Extract from captures...

    return functions
```

### Decision 3: Extraction architecture - tree-sitter single-pass (HCL pattern)

**Choice:** Use tree-sitter-go for AST extraction, single pass returning structured dict.

**Architecture follows HCL/Terraform pattern:**
- `ast_parser.py` → Parses .go files with tree-sitter-go, returns `type="tree_sitter"`
- `indexer/extractors/go.py` → Thin wrapper like `terraform.py`, calls go_impl functions
- `ast_extractors/go_impl.py` → Tree-sitter queries like `hcl_impl.py`

**NOT like Python** (which uses built-in ast module) or **JS/TS** (which uses Node.js semantic parser).

**AST Parser Integration Required** - tree-sitter-go is available in the package but NOT wired up:

```python
# Add to ast_parser.py:52-103 (_init_tree_sitter_parsers method):
try:
    go_lang = get_language("go")
    go_parser = get_parser("go")
    self.parsers["go"] = go_parser
    self.languages["go"] = go_lang
except Exception as e:
    print(f"[INFO] Go tree-sitter not available: {e}")

# Add to ast_parser.py:240-253 (_detect_language method):
ext_map = {
    # ... existing entries ...
    ".go": "go",
}
```

**Extractor output format** (matches storage handler expectations):
```python
def extract(self, file_info, content, tree) -> dict:
    return {
        "go_packages": [...],      # List[dict] with file, line, name, import_path
        "go_imports": [...],       # List[dict] with file, line, path, alias, is_dot_import
        "go_structs": [...],       # List[dict] with file, line, name, is_exported
        "go_struct_fields": [...], # List[dict] with file, struct_name, field_name, field_type, tag
        "go_interfaces": [...],
        "go_interface_methods": [...],
        "go_functions": [...],
        "go_methods": [...],
        "go_func_params": [...],
        "go_func_returns": [...],
        "go_goroutines": [...],
        "go_channels": [...],
        "go_channel_ops": [...],
        "go_defer_statements": [...],
        "go_error_returns": [...],
        "go_type_assertions": [...],
        "go_constants": [...],
    }
```

### Decision 4: Database mixin pattern

Follow `indexer/database/python_database.py` pattern exactly:

```python
# indexer/database/go_database.py
"""Go-specific database operations."""

class GoDatabaseMixin:
    """Mixin providing add_* methods for GO_TABLES."""

    def add_go_package(self, file_path: str, line: int, name: str, import_path: str | None):
        """Add a Go package declaration to the batch."""
        self.generic_batches["go_packages"].append((file_path, line, name, import_path))

    def add_go_import(self, file_path: str, line: int, path: str, alias: str | None, is_dot: bool):
        """Add a Go import statement to the batch."""
        self.generic_batches["go_imports"].append(
            (file_path, line, path, alias, 1 if is_dot else 0)
        )

    # ... one method per table, following exact column order from schema
```

**Registration** - Add to `indexer/database/__init__.py:17-27`:
```python
from .go_database import GoDatabaseMixin

class DatabaseManager(
    BaseDatabaseManager,
    CoreDatabaseMixin,
    PythonDatabaseMixin,
    NodeDatabaseMixin,
    GoDatabaseMixin,  # <-- ADD HERE
    # ...
):
```

### Decision 5: Storage handler pattern

Follow `indexer/storage/python_storage.py` pattern:

```python
# indexer/storage/go_storage.py
"""Go-specific storage handlers."""

class GoStorage:
    """Storage handlers for Go extraction data."""

    def __init__(self, db_manager, counts: dict[str, int]):
        self.db = db_manager
        self.counts = counts
        self._current_extracted = None

        self.handlers = {
            "go_packages": self._store_go_packages,
            "go_imports": self._store_go_imports,
            "go_structs": self._store_go_structs,
            "go_struct_fields": self._store_go_struct_fields,
            # ... one handler per extraction key
        }

    def _store_go_packages(self, file_path: str, data: list, jsx_pass: bool = False):
        for pkg in data:
            self.db.add_go_package(
                file_path=file_path,
                line=pkg["line"],
                name=pkg["name"],
                import_path=pkg.get("import_path"),
            )
        self.counts["go_packages"] = self.counts.get("go_packages", 0) + len(data)
```

**Wiring** - Add to `indexer/storage/__init__.py:20-30`:
```python
from .go_storage import GoStorage

class DataStorer:
    def __init__(self, db_manager, counts):
        # ...
        self.go = GoStorage(db_manager, counts)  # <-- ADD

        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.go.handlers,  # <-- ADD
            **self.infrastructure.handlers,
        }
```

### Decision 6: Interface satisfaction detection

**Choice:** Don't attempt interface satisfaction detection at extraction time.

**Rationale:** Go interfaces are implicitly satisfied - any type with matching methods implements the interface. Detecting this requires type resolution across the entire codebase. Store the syntactic information (interface definitions, method signatures) and let queries join on name matching.

### Decision 7: Framework detection patterns

| Framework | Import Path | API Patterns |
|-----------|-------------|--------------|
| Gin | `github.com/gin-gonic/gin` | `gin.Default()`, `r.GET()`, `r.POST()` |
| Echo | `github.com/labstack/echo/v4` | `echo.New()`, `e.GET()`, `e.POST()` |
| Fiber | `github.com/gofiber/fiber/v2` | `fiber.New()`, `app.Get()`, `app.Post()` |
| Chi | `github.com/go-chi/chi/v5` | `chi.NewRouter()`, `r.Get()`, `r.Post()` |
| GORM | `gorm.io/gorm` | `gorm.Open()`, `db.Find()`, `db.Create()` |
| sqlx | `github.com/jmoiron/sqlx` | `sqlx.Connect()`, `db.Select()` |
| gRPC | `google.golang.org/grpc` | `grpc.NewServer()`, `pb.Register*Server` |
| Cobra | `github.com/spf13/cobra` | `&cobra.Command{}`, `cmd.Execute()` |

### Decision 8: Security rule categories

| Category | Detection Pattern | Sink Functions |
|----------|-------------------|----------------|
| SQL injection | String concat/fmt in query | `db.Query()`, `db.Exec()`, `db.Raw()` |
| Command injection | User input to exec | `exec.Command()`, `exec.CommandContext()` |
| Template injection | User input to HTML | `template.HTML()`, `template.JS()`, `template.URL()` |
| Path traversal | User input to path | `filepath.Join()`, `os.Open()`, `ioutil.ReadFile()` |
| Crypto misuse | Wrong random source | `math/rand` in crypto context |
| Error ignoring | Blank identifier | `_ = someFunc()` where returns error |

### Decision 9: Vendor directory exclusion

**Choice:** Explicitly ignore `vendor/` directories during file walking.

**Rationale:** Go projects often vendor dependencies into `vendor/`. Indexing these would:
- Bloat database 10x-50x
- Duplicate symbols making search noisy
- Slow indexing significantly

**Implementation:**
```python
# In file walker / indexer
EXCLUDED_DIRS = {"vendor", "node_modules", ".git", "__pycache__"}
if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
    continue
```

### Decision 10: net/http standard library detection

**Choice:** Include `net/http` in framework detection alongside Gin/Echo/Fiber.

**Rationale:** `net/http` is used FAR more in Go than raw `http` in Node.js. Many production Go microservices use ONLY the standard library. Missing this would be a major gap.

**Detection patterns:**
```python
"net_http": {
    "language": "go",
    "detection_sources": {"imports": "exact_match"},
    "import_patterns": ["net/http"],
    "api_patterns": ["http.HandleFunc", "http.Handle", "http.ListenAndServe"],
}
```

### Decision 11: Captured variables in goroutines

**Choice:** Track variables captured by anonymous goroutine closures.

**Rationale:** This is the #1 source of data races in Go. When `go func() { use(x) }()` captures `x` from outer scope, and especially if `x` is a loop variable (pre-Go 1.22), race conditions occur.

**Implementation:**
1. When extracting `go func() {...}()` (anonymous goroutine)
2. Parse the closure body for identifier references
3. Check if identifiers are defined outside the closure
4. Store in `go_captured_vars` with `is_loop_var` flag

### Decision 12: Middleware detection

**Choice:** Detect `.Use()` calls on router variables to track middleware chains.

**Rationale:** Security auditing needs to know what middleware protects routes (auth, logging, CORS). `router.Use(AuthMiddleware)` applies to all subsequent routes.

**Detection pattern:**
- Gin: `r.Use(middleware)`
- Echo: `e.Use(middleware)`
- Chi: `r.Use(middleware)`
- Fiber: `app.Use(middleware)`

### Decision 13: Embedded struct field promotion

**Choice:** Store `is_embedded=1` in `go_struct_fields` but handle promotion in query layer.

**Rationale:** If Struct A embeds Struct B, A implicitly has all B's methods. This is a query-time concern:
```sql
-- Find all methods available on struct (including promoted)
WITH RECURSIVE embedded AS (
    SELECT struct_name, field_name, field_type, is_embedded
    FROM go_struct_fields WHERE struct_name = 'A'
    UNION ALL
    SELECT gsf.struct_name, gsf.field_name, gsf.field_type, gsf.is_embedded
    FROM go_struct_fields gsf
    JOIN embedded e ON gsf.struct_name = e.field_type AND e.is_embedded = 1
)
SELECT * FROM go_methods WHERE receiver_type IN (SELECT field_type FROM embedded WHERE is_embedded = 1);
```

### Decision 14: Package aggregation from files

**Choice:** Store `file` in `go_packages` but note multiple files form a package.

**Rationale:** Go packages are directories, not files. Multiple files in same directory declare same package (except `_test`).

**Query pattern:**
```sql
-- Aggregate files by package
SELECT name, GROUP_CONCAT(file) as files
FROM go_packages
GROUP BY name;
```

**Validation rule:** All non-test files in same directory MUST have same package name.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Interface satisfaction detection incomplete | Document limitation, store signatures for manual join |
| CGO analysis missing | Document as non-goal, rare in target codebases |
| Race detection limited without runtime | Track goroutine spawn + shared var access + captured vars |
| Generics parsing failure | CRITICAL: Verify tree-sitter-go version supports Go 1.18+ |
| Vendor bloat | Exclude vendor/ directories in file walker |
| Missing net/http routes | Add standard library detection in Phase 3 |

## Migration Plan

1. **Phase 1** (Foundation): Schema + AST parser + extraction + storage - delivers queryable data
2. **Phase 2** (Concurrency): Goroutines, channels, defer - enables concurrency analysis
3. **Phase 3** (Frameworks): Detection patterns - enables route/handler analysis
4. **Phase 4** (Security): Taint rules - enables vulnerability detection

Each phase is independently valuable. Phase 1 alone makes Go codebases queryable.
