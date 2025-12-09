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

Route tables have DIFFERENT column names per language:

| Table | file column | line column | pattern column | method column |
|-------|-------------|-------------|----------------|---------------|
| `python_routes` | `file` | `line` | `pattern` | `method` |
| `js_routes` | `file` | `line` | `pattern` | `method` |
| `go_routes` | `file` | `line` | `path` (NOT pattern!) | `method` |
| `rust_attributes` | `file_path` (NOT file!) | `target_line` (NOT line!) | `args` (NOT pattern!) | `attribute_name` (NOT method!) |

A unified query approach is IMPOSSIBLE without column mapping.
We need column mapping metadata.

### CRITICAL: Framework-Specific Route Sources

**Discovered during due diligence review.** The current `boundary_analyzer.py` already implements framework-aware routing:

```
boundary_analyzer.py structure:
├── _table_exists() [lines 19-25] - ZERO FALLBACK VIOLATION (delete)
├── _detect_frameworks() [lines 28-54] - Detects Express, FastAPI, etc.
├── _analyze_express_boundaries() [lines 57-182] - Express-specific (PRESERVE)
└── analyze_input_validation_boundaries() [lines 185-418]
    ├── Framework routing [lines 201-226] - Routes to framework analyzers
    └── Generic fallback [lines 227-413] - Uses _table_exists (FIX THIS)
```

**Key insight**: Express routes come from `express_middleware_chains` table, NOT `js_routes`.
The LanguageMetadataService must be **framework-aware** to handle this correctly.

## Goals / Non-Goals

**Goals:**
- Single source of truth for language metadata
- Framework-aware route source selection
- Adding new language = 1 extractor file, 0 command changes
- Zero breaking changes to existing extractors
- Gradual migration (commands can migrate incrementally)
- Column mapping for route tables (critical fix)
- Preserve existing framework-specific analyzers (Express)

**Non-Goals:**
- Changing extraction behavior
- Modifying database schema
- Creating parallel registries (extend existing)
- Changing how extractors are discovered
- Rewriting framework-specific analyzers (just integrate with them)

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

### Decision 2: Add FrameworkRouteInfo Dataclass (NEW)

**Location**: `theauditor/core/language_metadata.py`

**NEW CODE:**
```python
@dataclass(frozen=True, slots=True)
class FrameworkRouteInfo:
    """Framework-specific route source override.

    When a framework is detected, it may override the default language route table
    with a framework-specific source. For example, Express uses middleware chains
    instead of the generic js_routes table.
    """
    framework_name: str
    route_table: RouteTableInfo | None  # None = use custom analyzer, not table query
    uses_custom_analyzer: bool = False  # True = boundary_analyzer has special handling
    analyzer_function: str | None = None  # e.g., "_analyze_express_boundaries"
```

**Why:** Express routes don't come from `js_routes` - they come from `express_middleware_chains` with
custom analysis logic. We need to tell consumers "this framework has special handling, use the
dedicated analyzer instead of generic table queries."

### Decision 3: Extend BaseExtractor with Optional Methods

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

    def get_framework_routes(self) -> dict[str, FrameworkRouteInfo]:
        """Return framework-specific route overrides. Default: empty.

        Key is framework name (lowercase), value is FrameworkRouteInfo.
        When framework is detected, its route info takes precedence over get_route_table().
        """
        return {}

    def get_table_prefix(self) -> str:
        """Return prefix for language-specific tables. Default: {language_id}_."""
        return f"{self.get_language_id()}_"
```

**Import required:**
```python
from theauditor.core.language_metadata import RouteTableInfo, FrameworkRouteInfo
```

**Why:** Non-breaking. Existing extractors work unchanged. New extractors can override.

### Decision 4: Extend ExtractorRegistry with Query Methods

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
                    "framework_routes": extractor.get_framework_routes(),
                    "table_prefix": extractor.get_table_prefix(),
                }
        return result
```

### Decision 5: Create LanguageMetadataService

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
class FrameworkRouteInfo:
    """Framework-specific route source override."""
    framework_name: str
    route_table: RouteTableInfo | None
    uses_custom_analyzer: bool = False
    analyzer_function: str | None = None


@dataclass(frozen=True, slots=True)
class LanguageMetadata:
    """Immutable language metadata."""
    id: str
    display_name: str
    extensions: tuple[str, ...]
    entry_point_patterns: tuple[str, ...]
    route_table: RouteTableInfo | None
    framework_routes: dict[str, FrameworkRouteInfo]
    table_prefix: str


class LanguageMetadataService:
    """Unified query interface for language metadata.

    Framework-aware: When querying routes, checks if a framework override exists
    and returns the appropriate route source.
    """

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
                    framework_routes=extractor.get_framework_routes(),
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
    def get_route_table_for_framework(
        cls, lang_id: str, framework: str | None = None
    ) -> RouteTableInfo | None:
        """Get route table, respecting framework overrides.

        If framework is specified and has an override, return framework's route table.
        If framework uses custom analyzer, return None (caller should use dedicated analyzer).
        Otherwise, return language's default route table.
        """
        meta = cls._cache.get(lang_id)
        if not meta:
            return None

        if framework:
            fw_info = meta.framework_routes.get(framework.lower())
            if fw_info:
                if fw_info.uses_custom_analyzer:
                    # Framework has dedicated analyzer (e.g., Express)
                    # Caller should check uses_custom_analyzer and route accordingly
                    return None
                return fw_info.route_table

        return meta.route_table

    @classmethod
    def get_framework_info(cls, lang_id: str, framework: str) -> FrameworkRouteInfo | None:
        """Get framework-specific route info."""
        meta = cls._cache.get(lang_id)
        if not meta:
            return None
        return meta.framework_routes.get(framework.lower())

    @classmethod
    def get_all_route_tables(cls, exclude_custom_analyzers: bool = True) -> list[RouteTableInfo]:
        """Get all route tables with column mappings. ZERO FALLBACK compliant.

        Args:
            exclude_custom_analyzers: If True (default), excludes languages where
                                      framework detection should route to custom analyzer.
        """
        tables = []
        for meta in cls._cache.values():
            if meta.route_table is not None:
                tables.append(meta.route_table)
        return tables

    @classmethod
    def get_all_entry_points(cls) -> dict[str, list[str]]:
        """Get all entry points. Replaces hardcoded deadcode patterns."""
        return {
            meta.id: list(meta.entry_point_patterns)
            for meta in cls._cache.values()
            if meta.entry_point_patterns
        }

    @classmethod
    def has_custom_analyzer(cls, lang_id: str, framework: str) -> bool:
        """Check if a framework has custom boundary analyzer logic."""
        fw_info = cls.get_framework_info(lang_id, framework)
        return fw_info.uses_custom_analyzer if fw_info else False
```

### Decision 6: Extractor Metadata Values (with Framework Overrides)

Each extractor overrides metadata methods. Complete table with framework awareness:

| Extractor | language_id | entry_point_patterns | route_table | framework_routes |
|-----------|-------------|---------------------|-------------|------------------|
| PythonExtractor | `python` | `["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py"]` | `RouteTableInfo("python_routes", ...)` | `{}` (FastAPI/Django use default) |
| JavaScriptExtractor | `javascript` | `["index.js", "index.ts", "index.tsx", "App.tsx", "main.js", "main.ts"]` | `RouteTableInfo("js_routes", ...)` | `{"express": FrameworkRouteInfo("express", None, uses_custom_analyzer=True, analyzer_function="_analyze_express_boundaries")}` |
| RustExtractor | `rust` | `["main.rs", "lib.rs"]` | `RouteTableInfo("rust_attributes", ...)` | `{}` |
| GoExtractor | `go` | `["main.go"]` | `RouteTableInfo("go_routes", ...)` | `{}` |
| BashExtractor | `bash` | `[]` (all .sh/.bash are entry points) | `None` | `{}` |

**Key insight for JavaScript**: Express framework uses `uses_custom_analyzer=True` because the existing
`_analyze_express_boundaries()` function in `boundary_analyzer.py` provides superior analysis using
middleware chains. We don't want to replace it - we want to integrate with it.

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
| Service not initialized | Medium | High | Fail fast with clear error message |
| Performance overhead | Low | Low | Cache metadata at startup |
| Column mapping incorrect | Low | High | Verified against actual schema |
| Framework analyzer integration | Medium | Medium | Preserve existing analyzers, integrate via flags |

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
- Add RouteTableInfo, FrameworkRouteInfo dataclasses
- Add methods to BaseExtractor, ExtractorRegistry
- Create LanguageMetadataService
- Add metadata overrides to 5 main extractors (including framework_routes for JavaScript)

**Phase 2**: Initialize service
- Call `LanguageMetadataService.initialize(registry)` in orchestrator after line 48

**Phase 3**: Migrate commands (one at a time, delete hardcoded data)
- `explain.py`: Replace FILE_EXTENSIONS with service call
- `deadcode_graph.py`: Replace entry point patterns with service call
- `boundary_analyzer.py`:
  - PRESERVE `_analyze_express_boundaries()` (lines 57-182)
  - MODIFY `_detect_frameworks()` to use LanguageMetadataService
  - REPLACE `_table_exists()` checks in generic fallback (lines 229-323) with RouteTableInfo queries

## ZERO FALLBACK Compliance

**CRITICAL**: The current `boundary_analyzer.py` uses `_table_exists()` checks in the generic fallback section.
This violates ZERO FALLBACK.

**The fix:** Route tables that exist are KNOWN via LanguageMetadataService. We query ONLY those tables.
No existence checks needed.

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

## Framework Integration Pattern

**For boundary_analyzer.py**, the integration pattern is:

```python
def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    # Step 1: Detect frameworks (KEEP existing logic)
    frameworks = _detect_frameworks(cursor)

    # Step 2: Route to framework-specific analyzers (KEEP existing logic)
    if "express" in frameworks:
        # Check if framework has custom analyzer
        if LanguageMetadataService.has_custom_analyzer("javascript", "express"):
            # Use existing dedicated analyzer
            results.extend(_analyze_express_boundaries(cursor, frameworks["express"], max_entries))

    # Step 3: Generic fallback - USE METADATA SERVICE (FIX THIS SECTION)
    # Instead of: if _table_exists(cursor, "python_routes"):
    # Use: for route_info in LanguageMetadataService.get_all_route_tables():
    for route_info in LanguageMetadataService.get_all_route_tables():
        query = route_info.build_query(limit=remaining_entries)
        cursor.execute(query)
        # ... process results ...
```

## Open Questions

None - all decisions made based on code investigation and due diligence review.
