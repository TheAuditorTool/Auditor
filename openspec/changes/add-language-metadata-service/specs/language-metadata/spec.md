## ADDED Requirements

### Requirement: LanguageMetadata Dataclass

The system SHALL provide a `LanguageMetadata` frozen dataclass at `theauditor/core/language_metadata.py`.

**Fields:**
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | `str` | Language identifier | `"python"` |
| `display_name` | `str` | Human-readable name | `"Python"` |
| `extensions` | `tuple[str, ...]` | File extensions | `(".py", ".pyx")` |
| `entry_point_patterns` | `tuple[str, ...]` | Entry point filenames | `("main.py", "__main__.py")` |
| `route_table` | `RouteTableInfo \| None` | Route table metadata | See RouteTableInfo |
| `framework_routes` | `dict[str, FrameworkRouteInfo]` | Framework-specific route overrides | See FrameworkRouteInfo |
| `table_prefix` | `str` | Prefix for language tables | `"python_"` |

**Implementation:**
```python
@dataclass(frozen=True, slots=True)
class LanguageMetadata:
    id: str
    display_name: str
    extensions: tuple[str, ...]
    entry_point_patterns: tuple[str, ...]
    route_table: RouteTableInfo | None
    framework_routes: dict[str, FrameworkRouteInfo]
    table_prefix: str
```

#### Scenario: Dataclass is immutable
- **WHEN** code attempts to modify a LanguageMetadata field
- **THEN** FrozenInstanceError is raised
- **AND** metadata integrity is preserved

#### Scenario: Dataclass uses slots
- **WHEN** LanguageMetadata instances are created
- **THEN** memory usage is optimized via `__slots__`

---

### Requirement: RouteTableInfo Dataclass

The system SHALL provide a `RouteTableInfo` frozen dataclass to handle column name differences across route tables.

**RATIONALE:** Route tables have DIFFERENT column names per language:
- `python_routes`: file, line, pattern, method
- `js_routes`: file, line, pattern, method
- `go_routes`: file, line, path (NOT pattern!), method
- `rust_attributes`: file_path (NOT file!), target_line (NOT line!), args (NOT pattern!), attribute_name (NOT method!)

A unified query approach is IMPOSSIBLE without column mapping.

**Fields:**
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `table_name` | `str` | Database table name | `"python_routes"` |
| `file_column` | `str` | Column for file path | `"file"` or `"file_path"` |
| `line_column` | `str` | Column for line number | `"line"` or `"target_line"` |
| `pattern_column` | `str` | Column for route pattern | `"pattern"`, `"path"`, or `"args"` |
| `method_column` | `str` | Column for HTTP method | `"method"` or `"attribute_name"` |
| `filter_clause` | `str \| None` | Optional WHERE filter | `"attribute_name IN ('get', 'post', ...)"` |

**Methods:**
| Method | Return Type | Description |
|--------|-------------|-------------|
| `build_query(limit)` | `str` | Build SELECT query with correct column names |

**Implementation:**
```python
@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    table_name: str
    file_column: str
    line_column: str
    pattern_column: str
    method_column: str
    filter_clause: str | None = None

    def build_query(self, limit: int | None = None) -> str:
        """Build SELECT query with correct column names."""
        query = f"""
            SELECT {self.file_column} AS file, {self.line_column} AS line,
                   {self.pattern_column} AS pattern, {self.method_column} AS method
            FROM {self.table_name}
            WHERE {self.pattern_column} IS NOT NULL
        """
        if self.filter_clause:
            query += f" AND {self.filter_clause}"
        if limit:
            query += f" LIMIT {limit}"
        return query
```

#### Scenario: Python route table info
- **WHEN** `PythonExtractor.get_route_table()` is called
- **THEN** returns `RouteTableInfo("python_routes", "file", "line", "pattern", "method", None)`

#### Scenario: Rust route table info with filter
- **WHEN** `RustExtractor.get_route_table()` is called
- **THEN** returns `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name", "attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')")`

#### Scenario: build_query normalizes column names
- **WHEN** `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name").build_query()` is called
- **THEN** returns SQL with `SELECT file_path AS file, target_line AS line, args AS pattern, attribute_name AS method`
- **AND** consumer receives rows with consistent column positions regardless of source table

---

### Requirement: FrameworkRouteInfo Dataclass

The system SHALL provide a `FrameworkRouteInfo` frozen dataclass to handle framework-specific route source overrides.

**RATIONALE:** Frameworks may override the default language route table with framework-specific sources.
For example, Express uses `express_middleware_chains` table with custom analysis instead of the generic
`js_routes` table. The boundary analyzer has a dedicated `_analyze_express_boundaries()` function for this.

**Fields:**
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `framework_name` | `str` | Framework identifier | `"express"` |
| `route_table` | `RouteTableInfo \| None` | Framework's route table (None if custom analyzer) | `None` |
| `uses_custom_analyzer` | `bool` | True if boundary_analyzer has dedicated function | `True` |
| `analyzer_function` | `str \| None` | Name of custom analyzer function | `"_analyze_express_boundaries"` |

**Implementation:**
```python
@dataclass(frozen=True, slots=True)
class FrameworkRouteInfo:
    """Framework-specific route source override."""
    framework_name: str
    route_table: RouteTableInfo | None
    uses_custom_analyzer: bool = False
    analyzer_function: str | None = None
```

#### Scenario: Express framework uses custom analyzer
- **WHEN** `JavaScriptExtractor.get_framework_routes()` is called
- **THEN** returns `{"express": FrameworkRouteInfo("express", None, True, "_analyze_express_boundaries")}`
- **AND** `uses_custom_analyzer=True` signals that consumers should route to dedicated analyzer

#### Scenario: Framework info signals custom analyzer to consumers
- **WHEN** `LanguageMetadataService.has_custom_analyzer("javascript", "express")` is called
- **THEN** returns `True`
- **AND** boundary_analyzer routes Express projects to `_analyze_express_boundaries()` instead of generic queries

#### Scenario: Framework without custom analyzer uses route table
- **WHEN** a framework has `uses_custom_analyzer=False` and `route_table` is set
- **THEN** consumers use the framework's `route_table` via `build_query()`
- **AND** generic query processing is used

---

### Requirement: BaseExtractor Metadata Methods

The system SHALL add 6 optional metadata methods to `BaseExtractor` at `theauditor/indexer/extractors/__init__.py:13-77`.

**Methods:**
| Method | Return Type | Default Value | Purpose |
|--------|-------------|---------------|---------|
| `get_language_id()` | `str` | Class name minus "Extractor", lowercased | Unique identifier |
| `get_display_name()` | `str` | Class name minus "Extractor" | Human-readable name |
| `get_entry_point_patterns()` | `list[str]` | `[]` | Entry point filenames |
| `get_route_table()` | `RouteTableInfo \| None` | `None` | Route table metadata |
| `get_framework_routes()` | `dict[str, FrameworkRouteInfo]` | `{}` | Framework-specific overrides |
| `get_table_prefix()` | `str` | `"{language_id}_"` | Table name prefix |

**Default Implementation:**
```python
def get_language_id(self) -> str:
    return self.__class__.__name__.replace("Extractor", "").lower()

def get_display_name(self) -> str:
    return self.__class__.__name__.replace("Extractor", "")

def get_entry_point_patterns(self) -> list[str]:
    return []

def get_route_table(self):
    return None

def get_framework_routes(self) -> dict:
    return {}

def get_table_prefix(self) -> str:
    return f"{self.get_language_id()}_"
```

#### Scenario: Default language ID derived from class name
- **WHEN** `TerraformExtractor` does not override `get_language_id()`
- **THEN** `get_language_id()` returns `"terraform"`

#### Scenario: Default table prefix derived from language ID
- **WHEN** `GraphQLExtractor` does not override `get_table_prefix()`
- **THEN** `get_table_prefix()` returns `"graphql_"`

#### Scenario: Existing extractor works unchanged
- **WHEN** an extractor does not implement any metadata methods
- **THEN** default implementations provide sensible values
- **AND** extraction behavior is unchanged

#### Scenario: Default framework routes is empty
- **WHEN** `BashExtractor.get_framework_routes()` is called (no override)
- **THEN** returns `{}`
- **AND** no framework-specific routing occurs

---

### Requirement: ExtractorRegistry Query Methods

The system SHALL add 5 query methods to `ExtractorRegistry` at `theauditor/indexer/extractors/__init__.py:79-136`.

**Methods:**
| Method | Return Type | Purpose |
|--------|-------------|---------|
| `get_language_id(ext)` | `str \| None` | Get language ID for extension |
| `get_all_language_ids()` | `set[str]` | Get all unique language IDs |
| `get_extractor_by_language(lang_id)` | `BaseExtractor \| None` | Reverse lookup |
| `get_entry_points(ext)` | `list[str]` | Get entry points for extension |
| `get_all_metadata()` | `dict[str, dict]` | Get all language metadata |

#### Scenario: Query language ID by extension
- **WHEN** `registry.get_language_id(".rs")` is called
- **THEN** returns `"rust"`

#### Scenario: Query unknown extension returns None
- **WHEN** `registry.get_language_id(".unknown")` is called
- **THEN** returns `None`
- **AND** no exception is raised

#### Scenario: Get all language IDs
- **WHEN** `registry.get_all_language_ids()` is called
- **THEN** returns set containing `"python"`, `"javascript"`, `"rust"`, `"go"`, `"bash"`, `"terraform"`, `"sql"`, `"graphql"`, `"prisma"`, etc.

#### Scenario: Reverse lookup by language ID
- **WHEN** `registry.get_extractor_by_language("python")` is called
- **THEN** returns the `PythonExtractor` instance

#### Scenario: Get all metadata includes framework routes
- **WHEN** `registry.get_all_metadata()` is called
- **THEN** each language dict includes `"framework_routes"` key
- **AND** JavaScript entry includes Express framework info

---

### Requirement: LanguageMetadataService Singleton

The system SHALL provide a `LanguageMetadataService` singleton at `theauditor/core/language_metadata.py`.

**Methods:**
| Method | Return Type | Purpose | Replaces |
|--------|-------------|---------|----------|
| `initialize(registry)` | `None` | Initialize from ExtractorRegistry | N/A |
| `is_initialized()` | `bool` | Check if service initialized | N/A |
| `get_by_extension(ext)` | `LanguageMetadata \| None` | Get metadata by extension | N/A |
| `get_by_language(lang_id)` | `LanguageMetadata \| None` | Get metadata by language ID | N/A |
| `get_all_extensions()` | `list[str]` | All supported extensions | `explain.py:33-45 FILE_EXTENSIONS` |
| `get_all_route_tables()` | `list[RouteTableInfo]` | All route tables with column mapping | `boundary_analyzer.py:229-323` |
| `get_all_entry_points()` | `dict[str, list[str]]` | All entry points by language | `deadcode_graph.py:303-316` |
| `get_flat_entry_point_patterns()` | `list[str]` | All entry points as flat list | `deadcode_graph.py:303-316` |
| `get_route_table_for_framework(lang_id, framework)` | `RouteTableInfo \| None` | Get route table respecting framework override | N/A |
| `get_framework_info(lang_id, framework)` | `FrameworkRouteInfo \| None` | Get framework-specific route info | N/A |
| `has_custom_analyzer(lang_id, framework)` | `bool` | Check if framework has custom analyzer | N/A |

#### Scenario: Service is singleton
- **WHEN** `LanguageMetadataService()` is called multiple times
- **THEN** same instance is returned each time

#### Scenario: Get all extensions replaces FILE_EXTENSIONS
- **WHEN** `LanguageMetadataService.get_all_extensions()` is called
- **THEN** returns list containing `.py`, `.pyx`, `.js`, `.jsx`, `.ts`, `.tsx`, `.rs`, `.go`, `.sh`, `.bash`, `.tf`, `.sql`, `.graphql`, `.prisma`, etc.
- **AND** `explain.py` uses this instead of hardcoded set

#### Scenario: Get all route tables with column mapping
- **WHEN** `LanguageMetadataService.get_all_route_tables()` is called
- **THEN** returns list of `RouteTableInfo` objects with correct column names per language
- **AND** `boundary_analyzer.py` uses these to build language-specific queries

#### Scenario: Get all entry points replaces hardcoded patterns
- **WHEN** `LanguageMetadataService.get_all_entry_points()` is called
- **THEN** returns `{"python": ["main.py", "__main__.py", ...], "javascript": ["index.js", ...], ...}`
- **AND** `deadcode_graph.py` uses this instead of hardcoded patterns at lines 303-316

#### Scenario: Get flat entry point patterns for simple matching
- **WHEN** `LanguageMetadataService.get_flat_entry_point_patterns()` is called
- **THEN** returns flat list: `["main.py", "__main__.py", "index.js", "index.ts", ...]`
- **AND** suitable for simple `any(pattern in node for pattern in patterns)` checks

#### Scenario: Check if framework has custom analyzer
- **WHEN** `LanguageMetadataService.has_custom_analyzer("javascript", "express")` is called
- **THEN** returns `True`
- **AND** boundary_analyzer routes to `_analyze_express_boundaries()` instead of generic queries

#### Scenario: Get route table respects framework override (custom analyzer)
- **WHEN** `LanguageMetadataService.get_route_table_for_framework("javascript", "express")` is called
- **AND** Express has `uses_custom_analyzer=True`
- **THEN** returns `None` (caller should use dedicated analyzer)

#### Scenario: Get route table respects framework override (table override)
- **WHEN** a framework has `uses_custom_analyzer=False` and custom `route_table`
- **THEN** `get_route_table_for_framework()` returns the framework's `route_table`
- **AND** NOT the default language route table

---

### Requirement: Concrete Extractor Metadata Overrides

Each language extractor SHALL override metadata methods with language-specific values.

**Complete Metadata Table (5 Main Extractors):**
| Extractor | File | language_id | entry_point_patterns | route_table | framework_routes |
|-----------|------|-------------|---------------------|-------------|------------------|
| PythonExtractor | `extractors/python.py` | `python` | `["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py", "manage.py"]` | `RouteTableInfo("python_routes", ...)` | `{}` |
| JavaScriptExtractor | `extractors/javascript.py` | `javascript` | `["index.js", "index.ts", "index.tsx", "App.tsx", ...]` | `RouteTableInfo("js_routes", ...)` | `{"express": FrameworkRouteInfo(..., uses_custom_analyzer=True)}` |
| RustExtractor | `extractors/rust.py` | `rust` | `["main.rs", "lib.rs"]` | `RouteTableInfo("rust_attributes", ...)` | `{}` |
| GoExtractor | `extractors/go.py` | `go` | `["main.go"]` | `RouteTableInfo("go_routes", ...)` | `{}` |
| BashExtractor | `extractors/bash.py` | `bash` | `[]` | `None` | `{}` |

**Secondary Extractors (use defaults):**
| Extractor | File | Notes |
|-----------|------|-------|
| TerraformExtractor | `extractors/terraform.py` | Default: `terraform`, no entry points, no routes |
| SQLExtractor | `extractors/sql.py` | Default: `sql`, no entry points, no routes |
| GraphQLExtractor | `extractors/graphql.py` | Default: `graphql`, no entry points, no routes |
| PrismaExtractor | `extractors/prisma.py` | Default: `prisma`, no entry points, no routes |
| DockerExtractor | `extractors/docker.py` | Default: `docker`, no entry points, no routes |
| GitHubWorkflowExtractor | `extractors/github_actions.py` | Default: `githubworkflow`, no entry points, no routes |
| GenericExtractor | `extractors/generic.py` | Default: `generic`, no entry points, no routes |

#### Scenario: Python extractor returns correct metadata
- **WHEN** `PythonExtractor.get_entry_point_patterns()` is called
- **THEN** returns `["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py", "manage.py"]`

#### Scenario: Rust extractor returns route table with column mapping
- **WHEN** `RustExtractor.get_route_table()` is called
- **THEN** returns `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name", "attribute_name IN (...)")`

#### Scenario: JavaScript extractor returns Express framework override
- **WHEN** `JavaScriptExtractor.get_framework_routes()` is called
- **THEN** returns `{"express": FrameworkRouteInfo("express", None, True, "_analyze_express_boundaries")}`
- **AND** Express projects route to dedicated analyzer

#### Scenario: Terraform extractor uses defaults
- **WHEN** `TerraformExtractor.get_language_id()` is called
- **THEN** returns `"terraform"` (derived from class name)
- **AND** `get_route_table()` returns `None`
- **AND** `get_framework_routes()` returns `{}`

---

### Requirement: Zero Breaking Changes

The system SHALL maintain backward compatibility with existing code.

#### Scenario: Existing extractor works unchanged
- **WHEN** an extractor does not implement new metadata methods
- **THEN** default implementations provide sensible values
- **AND** extraction behavior is unchanged
- **AND** all existing tests pass

#### Scenario: Gradual migration supported
- **WHEN** some commands still use hardcoded values
- **THEN** system continues to function
- **AND** migration can be done incrementally

#### Scenario: Service not initialized raises error (ZERO FALLBACK)
- **WHEN** `LanguageMetadataService.get_all_extensions()` is called before `initialize()`
- **THEN** returns empty list `[]`
- **AND** caller code (e.g., `get_supported_extensions()` in explain.py) raises `RuntimeError`
- **AND** error message clearly states "Service not initialized"

**RATIONALE**: ZERO FALLBACK requires fail-fast behavior. Returning None silently would
mask initialization bugs and allow code to proceed with wrong data.

---

### Requirement: ZERO FALLBACK Compliance

The system SHALL NOT use any fallback patterns. This is CRITICAL.

#### Scenario: No try-except fallbacks in migrations
- **WHEN** `boundary_analyzer.py` queries route tables
- **THEN** it queries ONLY tables that are known to exist via `LanguageMetadataService`
- **AND** NO try-except blocks wrap query execution
- **AND** NO `_table_exists()` checks are used

#### Scenario: No default query fallbacks
- **WHEN** a route table has no entries
- **THEN** an empty list is returned
- **AND** NO fallback to alternative tables occurs

#### Scenario: Unknown extension returns None (not a fallback)
- **WHEN** `get_by_extension(".unknown")` is called on an initialized service
- **THEN** returns `None`
- **AND** does NOT try alternative lookups

**NOTE**: Returning None for unknown extensions is NOT a fallback - it's the correct "not found"
response. A fallback would be trying a different lookup method or returning a default value.
ZERO FALLBACK prohibits alternatives, not legitimate "not found" responses.

---

### Requirement: Framework Analyzer Preservation

The system SHALL preserve existing framework-specific analyzers in boundary_analyzer.py.

**RATIONALE:** The Express analyzer (`_analyze_express_boundaries()` at lines 57-182) uses the
`express_middleware_chains` table with custom distance calculation based on middleware execution
order. This provides superior analysis compared to generic table queries and MUST be preserved.

#### Scenario: Express analyzer unchanged
- **WHEN** boundary_analyzer.py is migrated
- **THEN** `_analyze_express_boundaries()` function remains unchanged (lines 57-182)
- **AND** continues to use `express_middleware_chains` table
- **AND** middleware distance calculation is preserved

#### Scenario: Framework routing via metadata service
- **WHEN** boundary_analyzer detects Express framework
- **AND** `LanguageMetadataService.has_custom_analyzer("javascript", "express")` returns `True`
- **THEN** routes to `_analyze_express_boundaries()` instead of generic queries

#### Scenario: Generic fallback uses RouteTableInfo
- **WHEN** no framework-specific analyzer exists
- **THEN** boundary_analyzer uses `LanguageMetadataService.get_all_route_tables()`
- **AND** queries each table using `RouteTableInfo.build_query()`
- **AND** NO `_table_exists()` checks are used

#### Scenario: Mixed analysis for multi-framework projects
- **WHEN** a project has both Express and Python routes
- **THEN** Express routes use `_analyze_express_boundaries()`
- **AND** Python routes use generic `RouteTableInfo` queries
- **AND** results are combined correctly
