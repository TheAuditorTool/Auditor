# Tasks

## Goal

Make commands polyglot-aware so they produce correct results on Rust, Go, and Express projects by using the correct table columns and routing to framework-specific analyzers.

## Execution Order

```
Phase 1: Core Infrastructure
  1.1 Create theauditor/core/ package
  1.2 Create language_metadata.py with dataclasses
  1.3 Add metadata methods to BaseExtractor
  1.4 Add query methods to ExtractorRegistry

Phase 2: Extractor Query Metadata
  2.1 PythonExtractor - route table with standard columns
  2.2 JavaScriptExtractor - route table + Express framework override
  2.3 RustExtractor - route table with DIFFERENT columns (file_path, target_line, args)
  2.4 GoExtractor - route table with path column (not pattern)
  2.5 BashExtractor - no routes

Phase 3: Service Initialization
  3.1 Initialize LanguageMetadataService in orchestrator.py

Phase 4: Command Migrations (Make Commands Polyglot-Aware)
  4.1 explain.py - use service for extensions
  4.2 deadcode_graph.py - use service for entry points
  4.3 boundary_analyzer.py - use RouteTableInfo.build_query() for correct columns

Phase 5: Verification
  5.1-5.5 Test that Rust/Go/Express projects produce correct results
```

---

## 0. Verification (Completed)

- [x] 0.1 Route table columns differ per language (verified in verification.md)
- [x] 0.2 Express uses custom analyzer, not js_routes (lines 57-182)
- [x] 0.3 `_table_exists()` violates ZERO FALLBACK (lines 19-25)
- [x] 0.4 `theauditor/core/` directory does NOT exist

---

## 1. Core Infrastructure

### 1.1 Create theauditor/core/ directory
**File**: `theauditor/core/__init__.py` (NEW)

```python
"""Core utilities and services."""
```

- [ ] 1.1 Complete

### 1.2 Create LanguageMetadataService
**File**: `theauditor/core/language_metadata.py` (NEW)

**Purpose**: Provide column mappings so commands can query any language correctly.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from theauditor.indexer.extractors import ExtractorRegistry


@dataclass(frozen=True, slots=True)
class RouteTableInfo:
    """Column mapping for a language's route table.

    Different languages use different column names:
    - Python/JS: file, line, pattern, method
    - Go: file, line, path (not pattern!), method
    - Rust: file_path, target_line, args, attribute_name (all different!)
    """
    table_name: str
    file_column: str
    line_column: str
    pattern_column: str
    method_column: str
    filter_clause: str | None = None

    def build_query(self, limit: int | None = None) -> str:
        """Build SELECT with correct columns for this language."""
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
    """Framework-specific route source override.

    Express uses express_middleware_chains with custom analysis,
    not generic js_routes queries. This tells commands to route
    to the dedicated analyzer instead.
    """
    framework_name: str
    route_table: RouteTableInfo | None  # None = use custom analyzer
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
    """Query interface for polyglot-aware commands.

    Commands use this to get correct column names for each language
    and to check if frameworks have custom analyzers.
    """

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
        """Check if framework has dedicated analyzer (e.g., Express)."""
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
        return {
            m.id: list(m.entry_point_patterns)
            for m in cls._cache.values()
            if m.entry_point_patterns
        }

    @classmethod
    def get_flat_entry_point_patterns(cls) -> list[str]:
        """Get all entry point patterns as flat list."""
        patterns = []
        for meta in cls._cache.values():
            patterns.extend(meta.entry_point_patterns)
        return patterns
```

- [ ] 1.2 Complete

### 1.3 Add metadata methods to BaseExtractor
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: After line 77 (after `cleanup` method)

```python
    # === QUERY METADATA METHODS ===

    def get_language_id(self) -> str:
        """Return language identifier."""
        return self.__class__.__name__.replace("Extractor", "").lower()

    def get_display_name(self) -> str:
        """Return human-readable name."""
        return self.__class__.__name__.replace("Extractor", "")

    def get_entry_point_patterns(self) -> list[str]:
        """Return filename patterns that indicate entry points."""
        return []

    def get_route_table(self):
        """Return route table metadata with column mappings."""
        return None

    def get_framework_routes(self) -> dict:
        """Return framework-specific route overrides."""
        return {}

    def get_table_prefix(self) -> str:
        """Return prefix for language-specific tables."""
        return f"{self.get_language_id()}_"
```

- [ ] 1.3 Complete

### 1.4 Add query methods to ExtractorRegistry
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: End of ExtractorRegistry class

```python
    def get_language_id(self, ext: str) -> str | None:
        """Get language ID for an extension."""
        ext_clean = ext if ext.startswith(".") else f".{ext}"
        extractor = self.extractors.get(ext_clean)
        return extractor.get_language_id() if extractor else None

    def get_all_language_ids(self) -> set[str]:
        """Get all unique language IDs."""
        return {e.get_language_id() for e in set(self.extractors.values())}

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
                }
        return result
```

- [ ] 1.4 Complete

---

## 2. Extractor Query Metadata

### 2.1 PythonExtractor
**File**: `theauditor/indexer/extractors/python.py`

```python
def get_entry_point_patterns(self) -> list[str]:
    return ["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py", "manage.py"]

def get_route_table(self):
    from theauditor.core.language_metadata import RouteTableInfo
    return RouteTableInfo(
        table_name="python_routes",
        file_column="file",
        line_column="line",
        pattern_column="pattern",
        method_column="method",
    )
```

- [ ] 2.1 Complete

### 2.2 JavaScriptExtractor (WITH Express framework override)
**File**: `theauditor/indexer/extractors/javascript.py`

**CRITICAL**: Must include `get_framework_routes()` for Express integration.

```python
def get_entry_point_patterns(self) -> list[str]:
    return [
        "index.js", "index.ts", "index.tsx", "index.mjs",
        "main.js", "main.ts", "main.mjs",
        "App.tsx", "App.jsx", "App.js",
        "server.js", "server.ts", "app.js", "app.ts",
    ]

def get_route_table(self):
    from theauditor.core.language_metadata import RouteTableInfo
    return RouteTableInfo(
        table_name="js_routes",
        file_column="file",
        line_column="line",
        pattern_column="pattern",
        method_column="method",
    )

def get_framework_routes(self) -> dict:
    """Express uses express_middleware_chains with custom analysis.

    This tells commands to route Express projects to the dedicated
    _analyze_express_boundaries() analyzer instead of generic queries.
    """
    from theauditor.core.language_metadata import FrameworkRouteInfo
    return {
        "express": FrameworkRouteInfo(
            framework_name="express",
            route_table=None,  # Uses custom analyzer
            uses_custom_analyzer=True,
            analyzer_function="_analyze_express_boundaries",
        )
    }
```

- [ ] 2.2 Complete

### 2.3 RustExtractor (DIFFERENT column names!)
**File**: `theauditor/indexer/extractors/rust.py`

**This is the key fix** - Rust uses completely different column names:

```python
def get_entry_point_patterns(self) -> list[str]:
    return ["main.rs", "lib.rs"]

def get_route_table(self):
    """Rust route table uses DIFFERENT column names:
    - file_path (not file)
    - target_line (not line)
    - args (not pattern)
    - attribute_name (not method)
    """
    from theauditor.core.language_metadata import RouteTableInfo
    return RouteTableInfo(
        table_name="rust_attributes",
        file_column="file_path",       # NOT "file"
        line_column="target_line",     # NOT "line"
        pattern_column="args",         # NOT "pattern"
        method_column="attribute_name",# NOT "method"
        filter_clause="attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')",
    )
```

- [ ] 2.3 Complete

### 2.4 GoExtractor (path column, not pattern)
**File**: `theauditor/indexer/extractors/go.py`

```python
def get_entry_point_patterns(self) -> list[str]:
    return ["main.go"]

def get_route_table(self):
    """Go uses 'path' column instead of 'pattern'."""
    from theauditor.core.language_metadata import RouteTableInfo
    return RouteTableInfo(
        table_name="go_routes",
        file_column="file",
        line_column="line",
        pattern_column="path",  # NOT "pattern"
        method_column="method",
    )
```

- [ ] 2.4 Complete

### 2.5 BashExtractor (no routes)
**File**: `theauditor/indexer/extractors/bash.py`

```python
def get_entry_point_patterns(self) -> list[str]:
    return []  # All .sh files are potential entry points

def get_route_table(self):
    return None  # Bash has no routes
```

- [ ] 2.5 Complete

---

## 3. Service Initialization

### 3.1 Initialize service in orchestrator
**File**: `theauditor/indexer/orchestrator.py`
**Location**: After line 48 (after `self.extractor_registry = ExtractorRegistry(...)`)

**Add import:**
```python
from theauditor.core.language_metadata import LanguageMetadataService
```

**Add after line 48:**
```python
        # Initialize language metadata service from extractor registry
        LanguageMetadataService.initialize(self.extractor_registry)
```

- [ ] 3.1 Complete

---

## 4. Command Migrations (Make Polyglot-Aware)

### 4.1 explain.py - Replace FILE_EXTENSIONS
**File**: `theauditor/commands/explain.py`

**BEFORE (lines 33-45):** Hardcoded FILE_EXTENSIONS set

**AFTER:**
```python
from theauditor.core.language_metadata import LanguageMetadataService


def _get_supported_extensions() -> set[str]:
    """Get supported extensions from metadata service."""
    extensions = LanguageMetadataService.get_all_extensions()
    if not extensions:
        raise RuntimeError("LanguageMetadataService not initialized. Run aud full first.")
    return set(extensions)
```

Replace `FILE_EXTENSIONS` usage with `_get_supported_extensions()`.

- [ ] 4.1 Complete

### 4.2 deadcode_graph.py - Replace entry point patterns
**File**: `theauditor/context/deadcode_graph.py`
**Location**: `_find_entry_points` method (lines 299-326)

**BEFORE:** Hardcoded patterns

**AFTER:**
```python
def _find_entry_points(self, graph: nx.DiGraph) -> set[str]:
    """Multi-strategy entry point detection."""
    entry_points = set()

    from theauditor.core.language_metadata import LanguageMetadataService
    patterns = LanguageMetadataService.get_flat_entry_point_patterns()
    if not patterns:
        raise RuntimeError("LanguageMetadataService not initialized. Run aud full first.")

    for node in graph.nodes():
        if any(pattern in node for pattern in patterns):
            entry_points.add(node)

    entry_points.update(self._find_decorated_entry_points())
    entry_points.update(self._find_framework_entry_points())

    # Test files are always entry points
    for node in graph.nodes():
        if any(pattern in node for pattern in ["test_", ".test.", ".spec.", "_test.py"]):
            entry_points.add(node)

    return entry_points
```

- [ ] 4.2 Complete

### 4.3 boundary_analyzer.py - Use RouteTableInfo for correct columns
**File**: `theauditor/boundaries/boundary_analyzer.py`

**This is the main polyglot fix:**

#### Part 1: DELETE `_table_exists()` (lines 19-25)
```python
# DELETE THIS - ZERO FALLBACK VIOLATION
def _table_exists(cursor, table_name: str) -> bool:
    ...
```

#### Part 2: PRESERVE framework functions (NO CHANGES)
- Lines 28-54: `_detect_frameworks()` - **DO NOT MODIFY**
- Lines 57-182: `_analyze_express_boundaries()` - **DO NOT MODIFY**

#### Part 3: MODIFY generic fallback to use RouteTableInfo

**BEFORE:**
```python
if _table_exists(cursor, "python_routes"):
    cursor.execute("SELECT file, line, pattern, method FROM python_routes")
if _table_exists(cursor, "go_routes"):
    cursor.execute("SELECT file, line, path, method FROM go_routes")  # Different column!
if _table_exists(cursor, "rust_attributes"):
    cursor.execute("SELECT file_path, target_line, args, attribute_name FROM rust_attributes")  # All different!
```

**AFTER:**
```python
from theauditor.core.language_metadata import LanguageMetadataService

# In generic fallback section:
for route_info in LanguageMetadataService.get_all_route_tables():
    query = route_info.build_query(limit=entries_per_table)
    cursor.execute(query)
    for row in cursor.fetchall():
        # Columns are normalized: (file, line, pattern, method)
        entry_points.append({
            "file": row[0],
            "line": row[1] or 0,
            "pattern": row[2],
            "method": row[3],
            "language": route_info.table_name.replace("_routes", "").replace("_attributes", ""),
            "source": "route_table",
        })
```

**ZERO FALLBACK COMPLIANCE:**
- [ ] `_table_exists()` deleted
- [ ] NO `if _table_exists()` checks remain
- [ ] NO try-except fallbacks
- [ ] Express analyzer preserved

- [ ] 4.3 Complete

---

## 5. Verification

### 5.1 Run aud full --offline
```bash
aud full --offline
```
- [ ] 5.1 No errors

### 5.2 Test metadata service populated
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.core.language_metadata import LanguageMetadataService
print('Extensions:', len(LanguageMetadataService.get_all_extensions()))
print('Route tables:', len(LanguageMetadataService.get_all_route_tables()))
for rt in LanguageMetadataService.get_all_route_tables():
    print(f'  {rt.table_name}: {rt.file_column}, {rt.line_column}, {rt.pattern_column}')
print('Express custom analyzer:', LanguageMetadataService.has_custom_analyzer('javascript', 'express'))
"
```

**Expected:**
- Extensions: 15+
- Route tables: 4 (python_routes, js_routes, go_routes, rust_attributes)
- Rust shows: file_path, target_line, args (NOT file, line, pattern)
- Express custom analyzer: True

- [ ] 5.2 Complete

### 5.3 Test boundaries on multi-language project
```bash
aud boundaries --type input-validation
```
Verify it produces results for Python, JS, Go, Rust if present.

- [ ] 5.3 Complete

### 5.4 Verify Express routing still works
Run on an Express project - should use `_analyze_express_boundaries()` not generic queries.

- [ ] 5.4 Complete

### 5.5 Verify Rust column mapping
If Rust routes exist, verify query uses `file_path`, `target_line`, `args` columns.

- [ ] 5.5 Complete

---

## Summary

| Phase | Goal | Risk |
|-------|------|------|
| Phase 1 | Create infrastructure | LOW |
| Phase 2 | Define column mappings per language | LOW |
| Phase 3 | Initialize service | LOW |
| Phase 4 | Make commands use correct columns | MEDIUM |
| Phase 5 | Verify polyglot correctness | N/A |

**Key Deliverable**: Commands produce correct results on Rust/Go/Express projects by using `RouteTableInfo.build_query()` with language-specific column names.
