## Context

### Current Architecture

**ExtractorRegistry** (`theauditor/indexer/extractors/__init__.py:79-136`):
- Maps file extensions to extractor instances
- Provides `get_extractor(file_path, ext)` and `supported_extensions()`
- NO metadata query capability

**BaseExtractor** (`theauditor/indexer/extractors/__init__.py:13-77`):
- Abstract base class for all extractors
- Only requires `supported_extensions()` and `extract()`
- NO language metadata methods

**Commands** hardcode everything inline - no central source of truth.

### Existing Infrastructure We Leverage

| Component | Location | What It Has | What We Add |
|-----------|----------|-------------|-------------|
| ExtractorRegistry | `extractors/__init__.py:79-136` | Extension mapping | Query methods |
| BaseExtractor | `extractors/__init__.py:13-77` | Extension declaration | Metadata methods |
| SemanticTableRegistry | `fce/registry.py` | Table categorization | (read-only) |
| FrameworkRegistry | `framework_registry.py` | Framework detection | (read-only) |

### CRITICAL: Route Table Column Differences

**This was missed in initial analysis.** Route tables have DIFFERENT column names:

| Table | file column | line column | pattern column | method column |
|-------|-------------|-------------|----------------|---------------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` | `method` |
| `rust_attributes` | `file_path` | `target_line` | `args` | `attribute_name` |

A unified "SELECT file, line, pattern, method FROM {table}" query DOES NOT WORK.
We need column mapping metadata.

## Goals / Non-Goals

**Goals:**
- Single source of truth for language metadata
- Adding new language = 1 extractor file, 0 command changes
- Zero breaking changes to existing extractors
- Gradual migration (commands can migrate incrementally)
- Column mapping for route tables (critical fix)

**Non-Goals:**
- Changing extraction behavior
- Modifying database schema
- Creating parallel registries (extend existing)
- Changing how extractors are discovered

## Decisions

### Decision 1: Add RouteTableInfo Dataclass

**Location**: `theauditor/core/language_metadata.py` (NEW FILE)

**NEW CODE:**
```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    """Metadata for a route table including column mappings."""
    table_name: str
    file_column: str
    line_column: str
    pattern_column: str
    method_column: str
    filter_clause: str | None = None

    def build_query(self, limit: int | None = None) -> str:
        """Build SELECT query with correct column names."""
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

**Why:** Different route tables have different column names. Without column mapping, unified queries fail.

### Decision 2: Extend BaseExtractor with Optional Methods

**Location**: `theauditor/indexer/extractors/__init__.py:13-77`

**CURRENT CODE (ends at line 77):**
```python
class BaseExtractor(ABC):
    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        self.root_path = root_path
        self.ast_parser = ast_parser

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass

    @abstractmethod
    def extract(self, file_info: dict, content: str, tree: Any | None = None) -> dict:
        pass

    # ... extract_routes, extract_sql_objects, cleanup ...
```

**NEW CODE (add after cleanup at line 77):**
```python
    # === METADATA METHODS (optional, all have defaults) ===

    def get_language_id(self) -> str:
        """Return language identifier. Default: class name without 'Extractor', lowercased."""
        return self.__class__.__name__.replace("Extractor", "").lower()

    def get_display_name(self) -> str:
        """Return human-readable name. Default: class name without 'Extractor'."""
        return self.__class__.__name__.replace("Extractor", "")

    def get_entry_point_patterns(self) -> list[str]:
        """Return filename patterns that indicate entry points. Default: empty."""
        return []

    def get_route_table(self) -> RouteTableInfo | None:
        """Return route table metadata with column mappings. Default: None."""
        return None

    def get_table_prefix(self) -> str:
        """Return prefix for language-specific tables. Default: {language_id}_."""
        return f"{self.get_language_id()}_"
```

**Import required:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Why:** Non-breaking. Existing extractors work unchanged. New extractors can override.

### Decision 3: Extend ExtractorRegistry with Query Methods

**Location**: `theauditor/indexer/extractors/__init__.py:79-136`

**NEW CODE (add at end of ExtractorRegistry class):**
```python
    def get_language_id(self, ext: str) -> str | None:
        """Get language ID for an extension."""
        ext_clean = ext if ext.startswith(".") else f".{ext}"
        extractor = self.extractors.get(ext_clean)
        return extractor.get_language_id() if extractor else None

    def get_all_language_ids(self) -> set[str]:
        """Get all unique language IDs."""
        return {e.get_language_id() for e in set(self.extractors.values())}

    def get_extractor_by_language(self, lang_id: str) -> BaseExtractor | None:
        """Reverse lookup: language ID -> extractor."""
        for extractor in set(self.extractors.values()):
            if extractor.get_language_id() == lang_id:
                return extractor
        return None

    def get_entry_points(self, ext: str) -> list[str]:
        """Get entry point patterns for an extension."""
        ext_clean = ext if ext.startswith(".") else f".{ext}"
        extractor = self.extractors.get(ext_clean)
        return extractor.get_entry_point_patterns() if extractor else []

    def get_all_metadata(self) -> dict[str, dict]:
        """Get metadata for all languages."""
        result = {}
        for extractor in set(self.extractors.values()):
            lang_id = extractor.get_language_id()
            if lang_id not in result:
                result[lang_id] = {
                    "id": lang_id,
                    "display_name": extractor.get_display_name(),
                    "extensions": extractor.supported_extensions(),
                    "entry_points": extractor.get_entry_point_patterns(),
                    "route_table": extractor.get_route_table(),
                    "table_prefix": extractor.get_table_prefix(),
                }
        return result
```

### Decision 4: Create LanguageMetadataService

**Location**: `theauditor/core/language_metadata.py` (NEW FILE)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from theauditor.indexer.extractors import ExtractorRegistry


@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    """Metadata for a route table including column mappings."""
    table_name: str
    file_column: str
    line_column: str
    pattern_column: str
    method_column: str
    filter_clause: str | None = None

    def build_query(self, limit: int | None = None) -> str:
        """Build SELECT query with correct column names."""
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


@dataclass(frozen=True, slots=True)
class LanguageMetadata:
    """Immutable language metadata."""
    id: str
    display_name: str
    extensions: tuple[str, ...]
    entry_point_patterns: tuple[str, ...]
    route_table: RouteTableInfo | None
    table_prefix: str


class LanguageMetadataService:
    """Unified query interface for language metadata."""

    _instance: LanguageMetadataService | None = None
    _cache: dict[str, LanguageMetadata] = {}
    _ext_map: dict[str, str] = {}  # extension -> language_id

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, registry: ExtractorRegistry) -> None:
        """Initialize from ExtractorRegistry. Call once at startup."""
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
                    table_prefix=extractor.get_table_prefix(),
                )
            for ext in extractor.supported_extensions():
                cls._ext_map[ext] = lang_id

    @classmethod
    def get_by_extension(cls, ext: str) -> LanguageMetadata | None:
        """Get metadata for a file extension."""
        ext_clean = ext if ext.startswith(".") else f".{ext}"
        lang_id = cls._ext_map.get(ext_clean)
        return cls._cache.get(lang_id) if lang_id else None

    @classmethod
    def get_by_language(cls, lang_id: str) -> LanguageMetadata | None:
        """Get metadata by language ID."""
        return cls._cache.get(lang_id)

    @classmethod
    def get_all_extensions(cls) -> list[str]:
        """Get all supported extensions. Replaces hardcoded FILE_EXTENSIONS."""
        return list(cls._ext_map.keys())

    @classmethod
    def get_all_route_tables(cls) -> list[RouteTableInfo]:
        """Get all route tables with column mappings. ZERO FALLBACK compliant."""
        return [
            meta.route_table
            for meta in cls._cache.values()
            if meta.route_table is not None
        ]

    @classmethod
    def get_all_entry_points(cls) -> dict[str, list[str]]:
        """Get all entry points. Replaces hardcoded deadcode patterns."""
        return {
            meta.id: list(meta.entry_point_patterns)
            for meta in cls._cache.values()
            if meta.entry_point_patterns
        }
```

### Decision 5: Extractor Metadata Values

Each extractor overrides metadata methods. Complete table with column mappings:

| Extractor | language_id | display_name | entry_point_patterns | route_table |
|-----------|-------------|--------------|---------------------|-------------|
| PythonExtractor | `python` | `Python` | `["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py"]` | `RouteTableInfo("python_routes", "file", "line", "pattern", "method", None)` |
| JavaScriptExtractor | `javascript` | `JavaScript/TypeScript` | `["index.js", "index.ts", "index.tsx", "App.tsx", "main.js", "main.ts"]` | `RouteTableInfo("js_routes", "file", "line", "pattern", "method", None)` |
| RustExtractor | `rust` | `Rust` | `["main.rs", "lib.rs"]` | `RouteTableInfo("rust_attributes", "file_path", "target_line", "args", "attribute_name", "attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')")` |
| GoExtractor | `go` | `Go` | `["main.go"]` | `RouteTableInfo("go_routes", "file", "line", "path", "method", None)` |
| BashExtractor | `bash` | `Bash` | `[]` (all .sh/.bash are entry points) | `None` |

**Secondary extractors use defaults (no overrides needed):**
- TerraformExtractor → `terraform`, no routes
- SQLExtractor → `sql`, no routes
- GraphQLExtractor → `graphql`, no routes
- PrismaExtractor → `prisma`, no routes
- DockerExtractor → `docker`, no routes
- GitHubWorkflowExtractor → `githubworkflow`, no routes
- GenericExtractor → `generic`, no routes

## Risks / Trade-offs

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Extractors don't override methods | Low | Low | Defaults return sensible values |
| Service not initialized | Medium | High | Fail fast with clear error message (see below) |
| Performance overhead | Low | Low | Cache metadata at startup |
| Column mapping incorrect | Low | High | Verified against actual schema |

### Service Not Initialized: Fail-Fast Implementation

**ZERO FALLBACK requires fail-fast behavior.** The service itself returns empty results when
not initialized (empty list, None). The CALLER code is responsible for fail-fast:

```python
# In explain.py - CALLER implements fail-fast
def get_supported_extensions() -> set[str]:
    extensions = LanguageMetadataService.get_all_extensions()
    if not extensions:
        raise RuntimeError("LanguageMetadataService not initialized.")
    return set(extensions)
```

**Why this design:**
- Service methods stay pure (no side effects, no exceptions for empty data)
- Caller decides failure mode based on context
- Test code can check for empty without try-except
- ZERO FALLBACK is enforced at usage site, not service level

## Migration Strategy

**Phase 1**: Add infrastructure (non-breaking)
- Add RouteTableInfo dataclass
- Add methods to BaseExtractor, ExtractorRegistry
- Create LanguageMetadataService
- Add metadata overrides to 5 main extractors

**Phase 2**: Initialize service
- Call `LanguageMetadataService.initialize(registry)` in orchestrator line 48

**Phase 3**: Migrate commands (one at a time, delete hardcoded data)
- `explain.py`: Replace FILE_EXTENSIONS with service call
- `deadcode_graph.py`: Replace entry point patterns with service call
- `boundary_analyzer.py`: Replace hardcoded route queries with RouteTableInfo queries

## ZERO FALLBACK Compliance

**CRITICAL**: The current `boundary_analyzer.py` uses `_table_exists()` checks (lines 16-22, 35, 55, 75, 95, 115). This violates ZERO FALLBACK.

**The fix:** Route tables that exist are KNOWN via LanguageMetadataService. We query ONLY those tables. No existence checks needed.

**FORBIDDEN patterns (do NOT use):**
```python
# FORBIDDEN: try-except fallback
try:
    cursor.execute(query)
except Exception:
    continue  # CANCER

# FORBIDDEN: table existence check
if _table_exists(cursor, "python_routes"):  # CANCER
    cursor.execute(...)
```

**CORRECT pattern:**
```python
# Get route tables from metadata service (known to exist)
for route_info in LanguageMetadataService.get_all_route_tables():
    query = route_info.build_query(limit=max_entries // 4)
    cursor.execute(query)
    for row in cursor.fetchall():
        # row is (file, line, pattern, method) regardless of actual column names
        entry_points.append({...})
```

## Open Questions

None - all decisions made based on code investigation.
