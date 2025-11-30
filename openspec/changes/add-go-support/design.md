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
- **Graph strategies for HTTP/ORM data flow** *(See specs/graph/spec.md)*
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
EXTRACTION PIPELINE (specs/indexer/spec.md)
============================================
ast_parser.py                      <-- Add tree-sitter-go here
       |
       v Returns type="tree_sitter" with parsed tree
       |
indexer/extractors/go.py           <-- NEW: Thin wrapper (like terraform.py)
       |
       v Calls extraction functions
       |
ast_extractors/go_impl.py          <-- NEW: Tree-sitter queries (like hcl_impl.py)
       |
       v Returns dict of extracted data
       |
indexer/storage/go_storage.py      <-- NEW: GoStorage handlers
       |
       v Calls db_manager.add_go_* methods
       |
indexer/database/go_database.py    <-- NEW: GoDatabaseMixin
       |
       v Batch insert into normalized tables
       |
go_* tables in repo_index.db


GRAPH STRATEGIES PIPELINE (specs/graph/spec.md) **<-- CRITICAL: WAS MISSING**
================================================
repo_index.db (go_* tables)
       |
       v Reads normalized data
       |
graph/strategies/go_http.py        <-- NEW: HTTP handler data flow
graph/strategies/go_orm.py         <-- NEW: GORM/sqlx relationship expansion
       |
       v Produces DFG nodes/edges
       |
graph/dfg_builder.py               <-- Add Go strategies to self.strategies list
       |
       v Stores in graphs.db
       |
graphs.db


RULES PIPELINE (specs/rules/spec.md - TBD)
==========================================
repo_index.db (go_* tables)
       |
       v Reads normalized data
       |
rules/go/                          <-- NEW: Go-specific rule directory
  injection_analyze.py             <-- SQL/command injection
  crypto_analyze.py                <-- Crypto misuse
  concurrency_analyze.py           <-- Race condition patterns
       |
       v Produces findings
       |
findings_consolidated table
```

**Key insight**: Go follows the HCL/Terraform pattern, NOT Python or JS/TS.
- Python uses built-in `ast` module (no tree-sitter)
- JS/TS uses external Node.js semantic parser (no tree-sitter)
- HCL uses tree-sitter directly -> **Go will do the same**

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
| **Graph ORM strategy** | `graph/strategies/python_orm.py` | ORM context + relationship expansion |
| **Graph HTTP strategy** | `graph/strategies/node_express.py` | Middleware chain + controller flow |
| **DFG registration** | `graph/dfg_builder.py:27-32` | Add strategies to self.strategies list |
| **Rules structure** | `rules/python/` | Language-specific rule directory pattern |
| **Rules base** | `rules/python/python_injection_analyze.py` | Analyzer pattern |

**DO NOT reference**: `treesitter_impl.py` (deleted - was dead code)

## Decisions

### Decision 1: Schema design - 22 normalized tables

*(See specs/indexer/spec.md: Go Schema Definitions)*

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
        Column("direction", "TEXT"),  # "send", "receive", "bidirectional"
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
        Column("operation", "TEXT", nullable=False),  # "send" or "receive"
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

*(See specs/indexer/spec.md: Tree-sitter Node Mapping)*

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

### Decision 3: Extraction architecture - tree-sitter single-pass (HCL pattern)

*(See specs/indexer/spec.md: Go Extractor Architecture)*

**Choice:** Use tree-sitter-go for AST extraction, single pass returning structured dict.

**Architecture follows HCL/Terraform pattern:**
- `ast_parser.py` -> Parses .go files with tree-sitter-go, returns `type="tree_sitter"`
- `indexer/extractors/go.py` -> Thin wrapper like `terraform.py`, calls go_impl functions
- `ast_extractors/go_impl.py` -> Tree-sitter queries like `hcl_impl.py`

**NOT like Python** (which uses built-in ast module) or **JS/TS** (which uses Node.js semantic parser).

### Decision 4: Database mixin pattern

*(See specs/indexer/spec.md: Database Mixin Implementation)*

Follow `indexer/database/python_database.py` pattern exactly.

### Decision 5: Storage handler pattern

*(See specs/indexer/spec.md: Storage Handler Implementation)*

Follow `indexer/storage/python_storage.py` pattern exactly.

### Decision 6: Interface satisfaction detection

**Choice:** Don't attempt interface satisfaction detection at extraction time.

**Rationale:** Go interfaces are implicitly satisfied - any type with matching methods implements the interface. Detecting this requires type resolution across the entire codebase. Store the syntactic information (interface definitions, method signatures) and let queries join on name matching.

### Decision 7: Framework detection patterns

*(See specs/indexer/spec.md: Framework Detection)*

| Framework | Import Path | API Patterns |
|-----------|-------------|--------------|
| net/http | `net/http` | `http.HandleFunc`, `http.Handle`, `http.ListenAndServe` |
| Gin | `github.com/gin-gonic/gin` | `gin.Default()`, `r.GET()`, `r.POST()` |
| Echo | `github.com/labstack/echo/v4` | `echo.New()`, `e.GET()`, `e.POST()` |
| Fiber | `github.com/gofiber/fiber/v2` | `fiber.New()`, `app.Get()`, `app.Post()` |
| Chi | `github.com/go-chi/chi/v5` | `chi.NewRouter()`, `r.Get()`, `r.Post()` |
| GORM | `gorm.io/gorm` | `gorm.Open()`, `db.Find()`, `db.Create()` |
| sqlx | `github.com/jmoiron/sqlx` | `sqlx.Connect()`, `db.Select()` |
| gRPC | `google.golang.org/grpc` | `grpc.NewServer()`, `pb.Register*Server` |
| Cobra | `github.com/spf13/cobra` | `&cobra.Command{}`, `cmd.Execute()` |

### Decision 8: Security rule categories

*(See specs/rules/spec.md - TBD)*

| Category | Detection Pattern | Sink Functions |
|----------|-------------------|----------------|
| SQL injection | String concat/fmt in query | `db.Query()`, `db.Exec()`, `db.Raw()` |
| Command injection | User input to exec | `exec.Command()`, `exec.CommandContext()` |
| Template injection | User input to HTML | `template.HTML()`, `template.JS()`, `template.URL()` |
| Path traversal | User input to path | `filepath.Join()`, `os.Open()`, `ioutil.ReadFile()` |
| Crypto misuse | Wrong random source | `math/rand` in crypto context |
| Error ignoring | Blank identifier | `_ = someFunc()` where returns error |

### Decision 9: Vendor directory exclusion

*(See specs/indexer/spec.md: File Walker Configuration)*

**Choice:** Explicitly ignore `vendor/` directories during file walking.

**Implementation location:** `theauditor/indexer/config.py:23-53` - Add to SKIP_DIRS set.

### Decision 10: net/http standard library detection

**Choice:** Include `net/http` in framework detection alongside Gin/Echo/Fiber.

**Rationale:** `net/http` is used FAR more in Go than raw `http` in Node.js. Many production Go microservices use ONLY the standard library.

### Decision 11: Captured variables in goroutines

**Choice:** Track variables captured by anonymous goroutine closures.

**Rationale:** This is the #1 source of data races in Go.

### Decision 12: Middleware detection

**Choice:** Detect `.Use()` calls on router variables to track middleware chains.

### Decision 13: Embedded struct field promotion

**Choice:** Store `is_embedded=1` in `go_struct_fields` but handle promotion in query layer.

### Decision 14: Package aggregation from files

**Choice:** Store `file` in `go_packages` but note multiple files form a package.

### Decision 15: Graph Strategies for Data Flow Analysis **<-- CRITICAL ADDITION**

*(See specs/graph/spec.md)*

**Choice:** Create two Go-specific graph strategies following the existing pattern.

**Rationale:** Graph strategies enable cross-function data flow analysis. Without them, taint analysis cannot track data through HTTP handlers or ORM operations.

**Implementation:**

```python
# graph/strategies/go_http.py
"""Go HTTP Strategy - Handles net/http and framework middleware chains."""

from .base import GraphStrategy
from ..types import DFGEdge, DFGNode, create_bidirectional_edges

class GoHttpStrategy(GraphStrategy):
    """Strategy for building Go HTTP handler data flow edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go HTTP handlers and middleware."""
        # 1. Load go_routes and go_middleware from database
        # 2. Build middleware chain edges (similar to node_express.py)
        # 3. Build handler parameter edges (req -> handler params)
        # 4. Return nodes and edges
```

```python
# graph/strategies/go_orm.py
"""Go ORM Strategy - Handles GORM/sqlx relationship expansion."""

from .base import GraphStrategy

class GoOrmStrategy(GraphStrategy):
    """Strategy for building Go ORM relationship edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go ORM relationships."""
        # 1. Load go_structs with `gorm` or `db` tags
        # 2. Parse relationship tags (belongs_to, has_many, etc.)
        # 3. Build relationship edges between models
        # 4. Return nodes and edges
```

**Registration in `graph/dfg_builder.py:27-32`:**
```python
from .strategies.go_http import GoHttpStrategy
from .strategies.go_orm import GoOrmStrategy

self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    GoHttpStrategy(),      # <-- ADD
    GoOrmStrategy(),       # <-- ADD
    InterceptorStrategy(),
]
```

### Decision 16: Rules Directory Structure **<-- CRITICAL ADDITION**

*(See specs/rules/spec.md - TBD)*

**Choice:** Create `rules/go/` directory following the existing Python/Node pattern.

**Implementation:**

```
theauditor/rules/go/
    __init__.py
    injection_analyze.py      # SQL/command injection (copy from python_injection_analyze.py)
    crypto_analyze.py         # Crypto misuse (copy from python_crypto_analyze.py)
    concurrency_analyze.py    # Go-specific: race conditions, channel misuse
    error_handling_analyze.py # Go-specific: error ignoring patterns
```

**Rule registration:** Rules are auto-discovered by `RulesOrchestrator` via directory scan. Just creating the files in `rules/go/` registers them.

### Decision 17: Framework Registry Integration **<-- CRITICAL ADDITION**

**Choice:** Add Go frameworks to `theauditor/framework_registry.py`.

**Implementation:**
```python
FRAMEWORK_REGISTRY = {
    # ... existing entries ...

    # Go Frameworks
    "net_http": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["net/http"],
        "file_markers": [],
    },
    "gin": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["github.com/gin-gonic/gin"],
        "file_markers": [],
    },
    "echo": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["github.com/labstack/echo"],
        "file_markers": [],
    },
    "fiber": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["github.com/gofiber/fiber"],
        "file_markers": [],
    },
    "chi": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["github.com/go-chi/chi"],
        "file_markers": [],
    },
    "gorm": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["gorm.io/gorm"],
        "file_markers": [],
    },
    "cobra": {
        "language": "go",
        "detection_sources": {"imports": "exact_match"},
        "import_patterns": ["github.com/spf13/cobra"],
        "file_markers": [],
    },
}
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Interface satisfaction detection incomplete | Document limitation, store signatures for manual join |
| CGO analysis missing | Document as non-goal, rare in target codebases |
| Race detection limited without runtime | Track goroutine spawn + shared var access + captured vars |
| Generics parsing failure | CRITICAL: Verify tree-sitter-go version supports Go 1.18+ |
| Vendor bloat | Exclude vendor/ directories in file walker |
| Missing net/http routes | Add standard library detection in Phase 3 |
| **Graph strategies not built** | **CRITICAL: Must implement go_http.py and go_orm.py** |
| **Rules not discoverable** | **CRITICAL: Must create rules/go/ directory** |

## Migration Plan

1. **Phase 1** (Foundation): Schema + AST parser + extraction + storage - delivers queryable data
2. **Phase 2** (Concurrency): Goroutines, channels, defer - enables concurrency analysis
3. **Phase 3** (Frameworks + Graph): Detection patterns + **graph strategies** - enables route/handler/taint analysis
4. **Phase 4** (Security): Rules in `rules/go/` - enables vulnerability detection

Each phase is independently valuable. Phase 1 alone makes Go codebases queryable.

## Spec References

All implementation details are documented in specs:

| Spec | Contents | Status |
|------|----------|--------|
| `specs/indexer/spec.md` | Schema, extraction, storage, database | EXISTS |
| `specs/graph/spec.md` | Graph strategies (go_http.py, go_orm.py) | **NEW - TO CREATE** |
| `specs/rules/spec.md` | Security rules (rules/go/) | **NEW - TO CREATE** |
