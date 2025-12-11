## Context

### The Core Problem: Language-Blind Commands

TheAuditor commands don't know how to query different languages. They assume Python-style schemas and produce wrong results or fail silently on Rust, Go, and framework-specific projects.

**Example - `aud boundaries` on a Rust project:**
```python
# Current code assumes Python column names
cursor.execute("SELECT file, line, pattern FROM rust_attributes")  # FAILS!
# Rust uses: file_path, target_line, args
```

**Example - `aud boundaries` on an Express project:**
```python
# Current code queries js_routes
cursor.execute("SELECT file, line, pattern FROM js_routes")  # WRONG!
# Express uses: express_middleware_chains with custom analysis
```

### Route Table Column Differences (The Actual Problem)

| Table | file column | line column | pattern column | method column |
|-------|-------------|-------------|----------------|---------------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` (NOT pattern!) | `method` |
| `rust_attributes` | `file_path` (NOT file!) | `target_line` (NOT line!) | `args` (NOT pattern!) | `attribute_name` (NOT method!) |

Commands cannot use a unified query. They need to know **which columns to use for each language**.

### Framework-Specific Route Sources (Complicates Further)

Express.js doesn't use `js_routes` at all. The current `boundary_analyzer.py` already handles this:

```
boundary_analyzer.py structure:
├── _table_exists() [lines 19-25] - ZERO FALLBACK VIOLATION (delete)
├── _detect_frameworks() [lines 28-54] - Detects Express, FastAPI, etc.
├── _analyze_express_boundaries() [lines 57-182] - Express-specific (PRESERVE)
└── analyze_input_validation_boundaries() [lines 185-418]
    ├── Framework routing [lines 201-226] - Routes to framework analyzers
    └── Generic fallback [lines 227-413] - Uses _table_exists (FIX THIS)
```

**Key insight**: Express routes come from `express_middleware_chains` table with custom middleware chain analysis, NOT generic table queries. The service must tell commands "use the dedicated analyzer, not table queries."

### Current Architecture

**ExtractorRegistry** (`theauditor/indexer/extractors/__init__.py:79-136`):
- Maps file extensions to extractor instances
- NO language query metadata (doesn't know Rust uses `file_path`)

**BaseExtractor** (`theauditor/indexer/extractors/__init__.py:13-77`):
- Abstract base class for all extractors
- NO route table metadata methods

**Commands**: Hardcode column names inline, use `_table_exists()` checks, produce wrong results on non-Python projects.

## Goals / Non-Goals

**Goals:**
- Commands produce correct results on Rust projects (use `file_path`, `target_line`, `args`)
- Commands produce correct results on Go projects (use `path` not `pattern`)
- Commands route Express projects to dedicated analyzer (not generic js_routes queries)
- Remove ZERO FALLBACK violating `_table_exists()` pattern
- Extractors declare their own query metadata (column names, table names)
- Preserve existing framework-specific analyzers (Express)

**Non-Goals:**
- Changing extraction behavior
- Modifying database schema
- Rewriting framework-specific analyzers (just integrate with them)
- Making "adding new languages easy" (that's a side effect, not the goal)

## Decisions

### Decision 1: RouteTableInfo Dataclass with Column Mapping

**Location**: `theauditor/core/language_metadata.py` (NEW FILE)

**Purpose**: Tell commands which columns to use for each language's route table.

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    """Column mapping for a language's route table."""
    table_name: str
    file_column: str       # "file" for Python, "file_path" for Rust
    line_column: str       # "line" for Python, "target_line" for Rust
    pattern_column: str    # "pattern" for Python, "path" for Go, "args" for Rust
    method_column: str     # "method" for Python, "attribute_name" for Rust
    filter_clause: str | None = None

    def build_query(self, limit: int | None = None) -> str:
        """Build SELECT query with correct column names for this language."""
        query = f"""
            SELECT {self.file_column}, {self.line_column}, {self.pattern_column}, {self.method_column}
            FROM {self.table_name}
            WHERE {self.pattern_column} IS NOT NULL
        """
        if self.filter_clause:
            query += f" AND {self.filter_clause}"
        if limit:
            query += f" LIMIT {limit}"
        return query
```

**Why:** Commands call `route_info.build_query()` and get correct SQL for that language. No more hardcoded column guessing.

### Decision 2: FrameworkRouteInfo for Custom Analyzers

**Location**: `theauditor/core/language_metadata.py`

**Purpose**: Tell commands when to use a dedicated analyzer instead of generic table queries.

```python
@dataclass(frozen=True, slots=True)
class FrameworkRouteInfo:
    """Framework-specific route source override.

    Express uses middleware chains with custom analysis, not js_routes.
    This tells commands: "don't query tables, use the dedicated analyzer."
    """
    framework_name: str
    route_table: RouteTableInfo | None  # None = use custom analyzer
    uses_custom_analyzer: bool = False  # True = route to dedicated function
    analyzer_function: str | None = None  # e.g., "_analyze_express_boundaries"
```

**Why:** When `has_custom_analyzer("javascript", "express")` returns `True`, commands route to `_analyze_express_boundaries()` instead of querying `js_routes`.

### Decision 3: Extractors Declare Their Query Metadata

**Location**: `theauditor/indexer/extractors/__init__.py:13-77`

**Add after `cleanup()` method at line 77:**
```python
    # === QUERY METADATA METHODS ===

    def get_language_id(self) -> str:
        """Return language identifier."""
        return self.__class__.__name__.replace("Extractor", "").lower()

    def get_route_table(self) -> RouteTableInfo | None:
        """Return route table metadata with column mappings."""
        return None

    def get_framework_routes(self) -> dict[str, FrameworkRouteInfo]:
        """Return framework-specific route overrides."""
        return {}

    def get_entry_point_patterns(self) -> list[str]:
        """Return filename patterns that indicate entry points."""
        return []

    def get_display_name(self) -> str:
        """Return human-readable name."""
        return self.__class__.__name__.replace("Extractor", "")

    def get_table_prefix(self) -> str:
        """Return prefix for language-specific tables."""
        return f"{self.get_language_id()}_"
```

**Why:** Each extractor knows its own schema. RustExtractor knows it uses `file_path`, `target_line`. Commands ask extractors, not hardcode.

### Decision 4: LanguageMetadataService

**Location**: `theauditor/core/language_metadata.py`

**Purpose**: Unified interface for commands to query language metadata.

```python
class LanguageMetadataService:
    """Query interface for polyglot-aware commands."""

    _cache: dict[str, LanguageMetadata] = {}
    _ext_map: dict[str, str] = {}

    @classmethod
    def initialize(cls, registry: ExtractorRegistry) -> None:
        """Initialize from ExtractorRegistry."""
        cls._cache.clear()
        cls._ext_map.clear()
        for extractor in set(registry.extractors.values()):
            lang_id = extractor.get_language_id()
            if lang_id not in cls._cache:
                cls._cache[lang_id] = LanguageMetadata(
                    id=lang_id,
                    display_name=extractor.get_display_name(),
                    extensions=tuple(extractor.supported_extensions()),
                    entry_point_patterns=tuple(extractor.get_entry_point_patterns()),
                    route_table=extractor.get_route_table(),
                    framework_routes=extractor.get_framework_routes(),
                    table_prefix=extractor.get_table_prefix(),
                )
            for ext in extractor.supported_extensions():
                cls._ext_map[ext] = lang_id

    @classmethod
    def get_all_route_tables(cls) -> list[RouteTableInfo]:
        """Get all route tables with correct column mappings."""
        return [m.route_table for m in cls._cache.values() if m.route_table]

    @classmethod
    def has_custom_analyzer(cls, lang_id: str, framework: str) -> bool:
        """Check if framework has dedicated analyzer."""
        meta = cls._cache.get(lang_id)
        if not meta:
            return False
        fw_info = meta.framework_routes.get(framework.lower())
        return fw_info.uses_custom_analyzer if fw_info else False

    @classmethod
    def get_all_extensions(cls) -> list[str]:
        """Get all supported extensions."""
        return list(cls._ext_map.keys())

    @classmethod
    def get_all_entry_points(cls) -> dict[str, list[str]]:
        """Get entry point patterns by language."""
        return {m.id: list(m.entry_point_patterns) for m in cls._cache.values() if m.entry_point_patterns}
```

### Decision 5: Concrete Extractor Overrides

Each language extractor declares its specific query metadata:

**RustExtractor:**
```python
def get_route_table(self) -> RouteTableInfo:
    return RouteTableInfo(
        table_name="rust_attributes",
        file_column="file_path",       # NOT "file"!
        line_column="target_line",     # NOT "line"!
        pattern_column="args",         # NOT "pattern"!
        method_column="attribute_name",# NOT "method"!
        filter_clause="attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')"
    )
```

**GoExtractor:**
```python
def get_route_table(self) -> RouteTableInfo:
    return RouteTableInfo(
        table_name="go_routes",
        file_column="file",
        line_column="line",
        pattern_column="path",  # NOT "pattern"!
        method_column="method",
    )
```

**JavaScriptExtractor:**
```python
def get_route_table(self) -> RouteTableInfo:
    return RouteTableInfo(
        table_name="js_routes",
        file_column="file",
        line_column="line",
        pattern_column="pattern",
        method_column="method",
    )

def get_framework_routes(self) -> dict[str, FrameworkRouteInfo]:
    return {
        "express": FrameworkRouteInfo(
            framework_name="express",
            route_table=None,  # Don't use table queries
            uses_custom_analyzer=True,  # Use dedicated analyzer
            analyzer_function="_analyze_express_boundaries",
        )
    }
```

## Command Migration Pattern

### boundary_analyzer.py - Generic Fallback Fix

**BEFORE (ZERO FALLBACK VIOLATION):**
```python
if _table_exists(cursor, "python_routes"):
    cursor.execute("SELECT file, line, pattern, method FROM python_routes")
if _table_exists(cursor, "go_routes"):
    cursor.execute("SELECT file, line, path, method FROM go_routes")  # Different!
if _table_exists(cursor, "rust_attributes"):
    cursor.execute("SELECT file_path, target_line, args, attribute_name FROM rust_attributes")  # All different!
```

**AFTER (Polyglot-Aware):**
```python
for route_info in LanguageMetadataService.get_all_route_tables():
    query = route_info.build_query(limit=max_entries // 4)
    cursor.execute(query)
    for row in cursor.fetchall():
        # Columns are always (file, line, pattern, method) regardless of actual names
        entry_points.append({
            "file": row[0],
            "line": row[1],
            "pattern": row[2],
            "method": row[3],
        })
```

### Framework Routing (Express)

```python
def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50):
    frameworks = _detect_frameworks(cursor)

    # Route Express to dedicated analyzer
    if "express" in frameworks:
        if LanguageMetadataService.has_custom_analyzer("javascript", "express"):
            results.extend(_analyze_express_boundaries(cursor, frameworks["express"], max_entries))

    # Generic fallback for other languages - uses correct columns
    for route_info in LanguageMetadataService.get_all_route_tables():
        query = route_info.build_query(limit=remaining)
        cursor.execute(query)
        # ... process results ...
```

## ZERO FALLBACK Compliance

**DELETE:** `_table_exists()` function and all usages in generic fallback
**KEEP:** Framework-specific analyzers (`_analyze_express_boundaries`)
**REPLACE:** Hardcoded queries with `RouteTableInfo.build_query()`

**FORBIDDEN:**
```python
if _table_exists(cursor, "python_routes"):  # CANCER
try:
    cursor.execute(query)
except:
    continue  # CANCER
```

**CORRECT:**
```python
for route_info in LanguageMetadataService.get_all_route_tables():
    query = route_info.build_query()
    cursor.execute(query)  # Tables are KNOWN, no existence check needed
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Column mapping incorrect | Wrong query results | Verified against actual schema in verification.md |
| Service not initialized | Empty results | Fail-fast at caller site |
| Framework analyzer integration | Routing bugs | Preserve existing analyzer, integrate via flags |

## Open Questions

None - design complete based on due diligence review.
