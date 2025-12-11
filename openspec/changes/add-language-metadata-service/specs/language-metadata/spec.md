# Spec: Language Metadata Service

## Problem Statement

TheAuditor commands are **language-blind**. They assume Python-style database schemas and produce wrong results or fail silently on Rust, Go, and framework-specific projects.

### Route Tables Have Different Column Names

| Table | file | line | pattern | method |
|-------|------|------|---------|--------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | **`path`** | `method` |
| `rust_attributes` | **`file_path`** | **`target_line`** | **`args`** | **`attribute_name`** |

A command that runs `SELECT file, line, pattern FROM rust_attributes` **fails** because Rust uses `file_path`, `target_line`, `args`.

### Frameworks Override Language Defaults

Express.js projects don't use `js_routes` at all. They use `express_middleware_chains` with custom middleware chain analysis in `_analyze_express_boundaries()`. Commands need to know "this is Express, route to the dedicated analyzer."

---

## Requirements

### Requirement: RouteTableInfo Column Mapping

The system SHALL provide column mappings for each language's route table.

```python
@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    table_name: str       # "rust_attributes"
    file_column: str      # "file_path"
    line_column: str      # "target_line"
    pattern_column: str   # "args"
    method_column: str    # "attribute_name"
    filter_clause: str | None = None

    def build_query(self, limit: int = None) -> str:
        """Build SELECT with correct columns for this language."""
```

#### Scenario: Rust routes queried with correct columns

- **WHEN** `aud boundaries` queries Rust route data
- **THEN** query uses `file_path`, `target_line`, `args`, `attribute_name`
- **AND** NOT `file`, `line`, `pattern`, `method`

#### Scenario: Go routes queried with correct columns

- **WHEN** `aud boundaries` queries Go route data
- **THEN** query uses `path` column for route pattern
- **AND** NOT `pattern` column

#### Scenario: build_query produces correct SQL

- **WHEN** `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name").build_query()` is called
- **THEN** returns `SELECT file_path, target_line, args, attribute_name FROM rust_attributes WHERE args IS NOT NULL`

---

### Requirement: FrameworkRouteInfo for Custom Analyzers

The system SHALL route framework-detected projects to dedicated analyzers.

```python
@dataclass(frozen=True, slots=True)
class FrameworkRouteInfo:
    framework_name: str           # "express"
    route_table: RouteTableInfo | None  # None = use custom analyzer
    uses_custom_analyzer: bool    # True
    analyzer_function: str | None # "_analyze_express_boundaries"
```

#### Scenario: Express routes to dedicated analyzer

- **WHEN** `aud boundaries` runs on Express project
- **AND** `has_custom_analyzer("javascript", "express")` returns `True`
- **THEN** routes to `_analyze_express_boundaries()` function
- **AND** does NOT query generic `js_routes` table

#### Scenario: Non-Express JS uses generic route table

- **WHEN** `aud boundaries` runs on non-Express JS project
- **THEN** queries `js_routes` table with standard columns

---

### Requirement: Extractor Metadata Declaration

Each extractor SHALL declare its query metadata.

**5 Main Extractors:**

| Extractor | route_table columns | framework_routes |
|-----------|---------------------|------------------|
| PythonExtractor | file, line, pattern, method | `{}` |
| JavaScriptExtractor | file, line, pattern, method | `{"express": uses_custom_analyzer=True}` |
| RustExtractor | **file_path, target_line, args, attribute_name** | `{}` |
| GoExtractor | file, line, **path**, method | `{}` |
| BashExtractor | None (no routes) | `{}` |

#### Scenario: RustExtractor declares different columns

- **WHEN** `RustExtractor.get_route_table()` is called
- **THEN** returns `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name", ...)`

#### Scenario: JavaScriptExtractor declares Express override

- **WHEN** `JavaScriptExtractor.get_framework_routes()` is called
- **THEN** returns `{"express": FrameworkRouteInfo("express", None, True, "_analyze_express_boundaries")}`

---

### Requirement: LanguageMetadataService Query Interface

```python
class LanguageMetadataService:
    @classmethod
    def initialize(cls, registry: ExtractorRegistry) -> None

    @classmethod
    def get_all_route_tables(cls) -> list[RouteTableInfo]

    @classmethod
    def has_custom_analyzer(cls, lang_id: str, framework: str) -> bool

    @classmethod
    def get_all_extensions(cls) -> list[str]

    @classmethod
    def get_flat_entry_point_patterns(cls) -> list[str]
```

#### Scenario: get_all_route_tables returns correct column mappings

- **WHEN** `get_all_route_tables()` is called
- **THEN** returns list of RouteTableInfo for Python, JS, Go, Rust
- **AND** Rust entry has `file_path`, `target_line`, `args` columns
- **AND** Go entry has `path` for pattern column

#### Scenario: has_custom_analyzer checks framework routing

- **WHEN** `has_custom_analyzer("javascript", "express")` is called
- **THEN** returns `True`
- **AND** caller routes to `_analyze_express_boundaries()`

---

### Requirement: ZERO FALLBACK Compliance

The system SHALL NOT use `_table_exists()` checks or try-except fallbacks.

#### Scenario: No table existence checks in generic fallback

- **BEFORE**: `if _table_exists(cursor, "python_routes"): cursor.execute(...)`
- **AFTER**: `for route_info in LanguageMetadataService.get_all_route_tables(): cursor.execute(route_info.build_query())`

#### Scenario: Service not initialized fails fast

- **WHEN** `get_all_extensions()` is called before `initialize()`
- **THEN** returns empty list
- **AND** caller raises `RuntimeError("Service not initialized")`

---

### Requirement: Framework Analyzer Preservation

The system SHALL preserve `_analyze_express_boundaries()` at lines 57-182.

#### Scenario: Express analyzer unchanged

- **WHEN** boundary_analyzer.py is migrated
- **THEN** `_analyze_express_boundaries()` is NOT modified
- **AND** continues to use `express_middleware_chains` table
- **AND** middleware chain analysis is preserved

#### Scenario: Framework routing via metadata service

- **WHEN** Express framework is detected
- **THEN** `has_custom_analyzer("javascript", "express")` returns `True`
- **AND** routes to dedicated Express analyzer

---

## Acceptance Criteria

1. `aud boundaries` produces correct results on **Rust projects** (uses `file_path`, `target_line`, `args`)
2. `aud boundaries` produces correct results on **Go projects** (uses `path` not `pattern`)
3. **Express projects** route to `_analyze_express_boundaries()` via `has_custom_analyzer()` check
4. **NO `_table_exists()` checks** remain in generic fallback section
5. `get_all_route_tables()` returns 4 entries with correct column names per language
6. Rust RouteTableInfo shows `file_path`, `target_line`, `args` (NOT `file`, `line`, `pattern`)

---

## Non-Goals

- Changing extraction behavior
- Modifying database schema
- Rewriting framework-specific analyzers (just integrate with them)
- Making "adding new languages easy" (that's a side effect)
