## Why

TheAuditor commands are **language-blind**. They assume Python-style schemas and fail silently or produce garbage results on Rust, Go, and framework-specific projects.

### The Problem: Commands Don't Know How to Query Different Languages

**Route tables have DIFFERENT column names per language:**

| Table | file | line | pattern | method |
|-------|------|------|---------|--------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` (NOT pattern!) | `method` |
| `rust_attributes` | `file_path` (NOT file!) | `target_line` (NOT line!) | `args` (NOT pattern!) | `attribute_name` (NOT method!) |

A command that runs `SELECT file, line, pattern FROM go_routes` **gets wrong data** because Go uses `path` not `pattern`.

A command that runs `SELECT file, line FROM rust_attributes` **fails** because Rust uses `file_path` and `target_line`.

### The Problem: Frameworks Override Language Defaults

Express.js projects don't use `js_routes` at all. They use `express_middleware_chains` with completely different analysis logic. The current `boundary_analyzer.py` has a dedicated `_analyze_express_boundaries()` function (lines 57-182) for this.

Commands need to know: "This is an Express project, don't query js_routes - route to the Express analyzer instead."

### The Problem: ZERO FALLBACK Violations

The current `boundary_analyzer.py` uses `_table_exists()` checks (lines 19-25) to handle language differences:

```python
if _table_exists(cursor, "python_routes"):
    cursor.execute("SELECT file, line, pattern...")
if _table_exists(cursor, "go_routes"):
    cursor.execute("SELECT file, line, path...")  # Different column!
if _table_exists(cursor, "rust_attributes"):
    cursor.execute("SELECT file_path, target_line, args...")  # All different!
```

This violates ZERO FALLBACK policy and is unmaintainable.

### What Commands Need

Commands need a service that answers:
1. **"What route table does this language use?"** → `RouteTableInfo` with correct column names
2. **"Does this framework have custom analysis?"** → `FrameworkRouteInfo` with `uses_custom_analyzer=True`
3. **"How do I build a query for this language?"** → `RouteTableInfo.build_query()` with column mapping
4. **"What are entry points for this language?"** → Language-specific patterns (main.rs, main.go, etc.)

## What Changes

### NEW: LanguageMetadataService

A polyglot-aware service that provides language-specific query patterns:

```python
# Instead of hardcoded column guessing:
cursor.execute("SELECT file, line, pattern FROM python_routes")
cursor.execute("SELECT file, line, path FROM go_routes")  # Different!
cursor.execute("SELECT file_path, target_line, args FROM rust_attributes")  # All different!

# Commands use the service:
for route_info in LanguageMetadataService.get_all_route_tables():
    query = route_info.build_query()  # Correct columns for each language
    cursor.execute(query)
```

### NEW: RouteTableInfo with Column Mapping

```python
@dataclass
class RouteTableInfo:
    table_name: str       # "rust_attributes"
    file_column: str      # "file_path" (not "file"!)
    line_column: str      # "target_line" (not "line"!)
    pattern_column: str   # "args" (not "pattern"!)
    method_column: str    # "attribute_name" (not "method"!)

    def build_query(self, limit: int = None) -> str:
        """Build SELECT with correct columns for this language."""
```

### NEW: FrameworkRouteInfo for Framework-Specific Routing

```python
@dataclass
class FrameworkRouteInfo:
    framework_name: str           # "express"
    route_table: RouteTableInfo | None  # None = use custom analyzer
    uses_custom_analyzer: bool    # True = route to dedicated function
    analyzer_function: str | None # "_analyze_express_boundaries"
```

When `LanguageMetadataService.has_custom_analyzer("javascript", "express")` returns `True`, commands route to the dedicated Express analyzer instead of generic table queries.

### MODIFIED: boundary_analyzer.py Generic Fallback

**DELETE:** `_table_exists()` function and all 10 usage sites in generic fallback
**KEEP:** `_detect_frameworks()` and `_analyze_express_boundaries()` (framework-specific logic)
**REPLACE:** Hardcoded route table queries with `RouteTableInfo.build_query()` loop

### MODIFIED: Extractors Provide Metadata

Each extractor declares its language-specific query patterns:

```python
class RustExtractor(BaseExtractor):
    def get_route_table(self) -> RouteTableInfo:
        return RouteTableInfo(
            table_name="rust_attributes",
            file_column="file_path",      # Rust-specific
            line_column="target_line",    # Rust-specific
            pattern_column="args",        # Rust-specific
            method_column="attribute_name",
            filter_clause="attribute_name IN ('get', 'post', 'put', 'delete')"
        )
```

## Impact

- **Affected code**: `boundary_analyzer.py`, `explain.py`, `deadcode_graph.py`, all 5 main extractors
- **Breaking changes**: NONE - additive metadata methods with defaults
- **ZERO FALLBACK fix**: Removes `_table_exists()` pattern from generic fallback
- **Risk level**: LOW - framework-specific analyzers preserved, only generic fallback changes

## Success Criteria

1. `aud boundaries` produces correct results on Rust projects (uses `file_path`, `target_line`)
2. `aud boundaries` produces correct results on Go projects (uses `path` not `pattern`)
3. Express projects route to `_analyze_express_boundaries()` via metadata service
4. NO `_table_exists()` checks remain in generic fallback
5. Adding a new language's route support = 1 extractor method override
