# Tasks

## Execution Order

Execute in order. Each task has acceptance criteria. DO NOT skip.

```
Phase 1: Core Infrastructure
  1.1 Create theauditor/core/ package
  1.2 Create language_metadata.py with dataclasses (including FrameworkRouteInfo)
  1.3 Create LanguageMetadataService

Phase 2: Extractor Extensions
  2.1 Add metadata methods to BaseExtractor
  2.2 Add query methods to ExtractorRegistry
  2.3 Add metadata overrides to PythonExtractor
  2.4 Add metadata overrides to JavaScriptExtractor (WITH framework_routes for Express)
  2.5 Add metadata overrides to RustExtractor
  2.6 Add metadata overrides to GoExtractor
  2.7 Add metadata overrides to BashExtractor

Phase 3: Service Initialization
  3.1 Initialize LanguageMetadataService in orchestrator.py

Phase 4: Command Migrations
  4.1 Migrate explain.py (FILE_EXTENSIONS)
  4.2 Migrate deadcode_graph.py (entry point patterns)
  4.3 Migrate boundary_analyzer.py (GENERIC FALLBACK ONLY - preserve Express analyzer)

Phase 5: Verification
  5.1 Run full test suite
  5.2 Run integration test
```

---

## 0. Verification (TEAMSOP REQUIRED)

Before implementation, verify these hypotheses against live code:

- [x] 0.1 Verify `theauditor/core/` directory does NOT exist (must create) - CONFIRMED
- [x] 0.2 Verify BaseExtractor ends at line 77 with `cleanup()` method - CONFIRMED
- [x] 0.3 Verify ExtractorRegistry ends at line 136 with `supported_extensions()` - CONFIRMED
- [x] 0.4 Verify route table column names differ per language - CONFIRMED (see verification.md)
- [x] 0.5 Verify all 12 extractors exist in `theauditor/indexer/extractors/` - CONFIRMED
- [x] 0.6 Verify boundary_analyzer.py has framework-aware Express analyzer (lines 57-182) - CONFIRMED
- [x] 0.7 Verify _table_exists() violates ZERO FALLBACK (lines 19-25) - CONFIRMED

---

## 1. Core Infrastructure

### 1.1 Create theauditor/core/ directory and __init__.py
**File**: `theauditor/core/__init__.py` (NEW)

```python
"""Core utilities and services."""
```

- [ ] 1.1 Complete

### 1.2 Create LanguageMetadataService
**File**: `theauditor/core/language_metadata.py` (NEW)

**Create with FULL implementation from design.md including:**
- RouteTableInfo dataclass with `build_query()` method
- FrameworkRouteInfo dataclass (NEW - for Express integration)
- LanguageMetadata dataclass
- LanguageMetadataService singleton with all methods

**See design.md Decision 5 for complete implementation (~170 lines).**

Key methods:
- `initialize(registry)` - Call once at startup
- `get_all_extensions()` - Replaces FILE_EXTENSIONS
- `get_all_route_tables()` - For ZERO FALLBACK boundary queries
- `get_flat_entry_point_patterns()` - For deadcode detection
- `has_custom_analyzer(lang_id, framework)` - For framework routing
- `get_framework_info(lang_id, framework)` - Get FrameworkRouteInfo

- [ ] 1.2 Complete

### 1.3 Add metadata methods to BaseExtractor
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: After line 77 (after `cleanup` method)

**Add 6 metadata methods with defaults:**
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

    def get_route_table(self):
        """Return route table metadata with column mappings. Default: None."""
        return None

    def get_framework_routes(self) -> dict:
        """Return framework-specific route overrides. Default: empty.

        Key is framework name (lowercase), value is FrameworkRouteInfo.
        When framework is detected, its route info takes precedence over get_route_table().
        """
        return {}

    def get_table_prefix(self) -> str:
        """Return prefix for language-specific tables. Default: {language_id}_."""
        return f"{self.get_language_id()}_"
```

- [ ] 1.3 Complete

### 1.4 Add query methods to ExtractorRegistry
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: After line 136 (end of ExtractorRegistry class)

**Add 5 query methods:**
```python
    def get_language_id(self, ext: str) -> str | None:
        """Get language ID for an extension."""
        ext_clean = ext if ext.startswith(".") else f".{ext}"
        extractor = self.extractors.get(ext_clean)
        return extractor.get_language_id() if extractor else None

    def get_all_language_ids(self) -> set[str]:
        """Get all unique language IDs."""
        return {e.get_language_id() for e in set(self.extractors.values())}

    def get_extractor_by_language(self, lang_id: str):
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

- [ ] 1.4 Complete

---

## 2. Extractor Metadata Overrides (5 Main Extractors)

### 2.1 PythonExtractor
**File**: `theauditor/indexer/extractors/python.py`
**Location**: Inside class, after `supported_extensions`

**Add methods:**
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

### 2.2 JavaScriptExtractor (WITH framework_routes)
**File**: `theauditor/indexer/extractors/javascript.py`
**Location**: Inside class, after `supported_extensions`

**CRITICAL**: This extractor MUST include `get_framework_routes()` for Express integration.

**Add methods:**
```python
    def get_entry_point_patterns(self) -> list[str]:
        return [
            "index.js", "index.ts", "index.tsx", "index.mjs",
            "main.js", "main.ts", "main.mjs",
            "App.tsx", "App.jsx", "App.js",
            "server.js", "server.ts",
            "app.js", "app.ts",
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
        """Return Express framework override.

        Express uses express_middleware_chains table with custom analysis
        in boundary_analyzer.py::_analyze_express_boundaries() instead of
        generic js_routes queries. This tells consumers to route Express
        projects to the dedicated analyzer.
        """
        from theauditor.core.language_metadata import FrameworkRouteInfo
        return {
            "express": FrameworkRouteInfo(
                framework_name="express",
                route_table=None,  # Uses custom analyzer, not table query
                uses_custom_analyzer=True,
                analyzer_function="_analyze_express_boundaries",
            )
        }
```

- [ ] 2.2 Complete

### 2.3 RustExtractor
**File**: `theauditor/indexer/extractors/rust.py`
**Location**: Inside class, after `supported_extensions`

**Note**: Rust uses DIFFERENT column names!

**Add methods:**
```python
    def get_entry_point_patterns(self) -> list[str]:
        return ["main.rs", "lib.rs"]

    def get_route_table(self):
        """Return Rust route table metadata.

        IMPORTANT: Rust uses different column names:
        - file_path (not file)
        - target_line (not line)
        - args (not pattern)
        - attribute_name (not method)
        """
        from theauditor.core.language_metadata import RouteTableInfo
        return RouteTableInfo(
            table_name="rust_attributes",
            file_column="file_path",
            line_column="target_line",
            pattern_column="args",
            method_column="attribute_name",
            filter_clause="attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')",
        )
```

- [ ] 2.3 Complete

### 2.4 GoExtractor
**File**: `theauditor/indexer/extractors/go.py`
**Location**: Inside class, after `supported_extensions`

**Note**: Go uses 'path' instead of 'pattern'!

**Add methods:**
```python
    def get_entry_point_patterns(self) -> list[str]:
        return ["main.go"]

    def get_route_table(self):
        """Return Go route table metadata.

        Note: Go uses 'path' column instead of 'pattern'.
        """
        from theauditor.core.language_metadata import RouteTableInfo
        return RouteTableInfo(
            table_name="go_routes",
            file_column="file",
            line_column="line",
            pattern_column="path",  # NOT 'pattern'!
            method_column="method",
        )
```

- [ ] 2.4 Complete

### 2.5 BashExtractor
**File**: `theauditor/indexer/extractors/bash.py`
**Location**: Inside class, after `supported_extensions`

**Add methods (NO route table - bash has no routes):**
```python
    def get_entry_point_patterns(self) -> list[str]:
        """All .sh/.bash files are entry points - return empty to signal this."""
        return []

    def get_route_table(self):
        """Bash has no route table."""
        return None
```

- [ ] 2.5 Complete

---

## 3. Service Initialization

### 3.1 Initialize service in orchestrator
**File**: `theauditor/indexer/orchestrator.py`
**Location**: After line 48 (after `self.extractor_registry = ExtractorRegistry(...)`)

**Add import at top:**
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

## 4. Command Migration

### 4.1 Migrate explain.py FILE_EXTENSIONS
**File**: `theauditor/commands/explain.py`

**BEFORE (lines 33-45):**
```python
FILE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".vue",
    ".rb",
    ".php",
}
```

**AFTER:**
```python
from theauditor.core.language_metadata import LanguageMetadataService


def _get_supported_extensions() -> set[str]:
    """Get supported extensions from metadata service.

    ZERO FALLBACK: Raises RuntimeError if service not initialized.
    """
    extensions = LanguageMetadataService.get_all_extensions()
    if not extensions:
        raise RuntimeError(
            "LanguageMetadataService not initialized. "
            "Run indexing first (aud full)."
        )
    return set(extensions)


# Lazy initialization - computed on first use
_FILE_EXTENSIONS_CACHE: set[str] | None = None


def get_supported_extensions() -> set[str]:
    """Get file extensions, initializing lazily."""
    global _FILE_EXTENSIONS_CACHE
    if _FILE_EXTENSIONS_CACHE is None:
        _FILE_EXTENSIONS_CACHE = _get_supported_extensions()
    return _FILE_EXTENSIONS_CACHE
```

**Update all usages**: Replace `FILE_EXTENSIONS` with `get_supported_extensions()`.

- [ ] 4.1 Complete

### 4.2 Migrate deadcode_graph.py entry points
**File**: `theauditor/context/deadcode_graph.py`
**Location**: `_find_entry_points` method (lines 299-326)

**BEFORE (lines 303-316):** Hardcoded patterns

**AFTER:** Replace with service call
```python
def _find_entry_points(self, graph: nx.DiGraph) -> set[str]:
    """Multi-strategy entry point detection."""
    entry_points = set()

    # Get entry point patterns from metadata service
    from theauditor.core.language_metadata import LanguageMetadataService

    patterns = LanguageMetadataService.get_flat_entry_point_patterns()
    if not patterns:
        # Fallback for standalone usage (service not initialized)
        patterns = [
            "cli.py", "__main__.py", "main.py",
            "index.ts", "index.js", "index.tsx", "App.tsx",
            "main.rs", "lib.rs", "main.go",
        ]

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

### 4.3 Migrate boundary_analyzer.py (GENERIC FALLBACK ONLY)
**File**: `theauditor/boundaries/boundary_analyzer.py`

**CRITICAL**: This migration has 3 parts:
1. DELETE `_table_exists()` function (ZERO FALLBACK violation)
2. PRESERVE `_analyze_express_boundaries()` (framework analyzer - DO NOT TOUCH)
3. MODIFY generic fallback section to use RouteTableInfo queries

---

#### Part 1: DELETE _table_exists() (lines 19-25)

```python
# DELETE THIS ENTIRE FUNCTION - ZERO FALLBACK VIOLATION
def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None
```

---

#### Part 2: PRESERVE framework functions (NO CHANGES)

**Lines 28-54**: `_detect_frameworks()` - **DO NOT MODIFY**
**Lines 57-182**: `_analyze_express_boundaries()` - **DO NOT MODIFY**

These functions contain specialized framework logic that should NOT be replaced.
The Express analyzer uses `express_middleware_chains` table with custom distance
calculation based on middleware execution order.

---

#### Part 3: MODIFY generic fallback in `analyze_input_validation_boundaries()`

**Current structure (lines 185-418):**
```
analyze_input_validation_boundaries()
├── Framework detection (lines 201-206) - KEEP
├── Framework routing (lines 208-226)
│   └── Express routing (lines 210-214) - KEEP (uses _analyze_express_boundaries)
└── Generic fallback (lines 227-413)
    └── Multiple _table_exists checks - FIX THIS
```

**Only modify the generic fallback section.** The framework detection and Express routing STAY.

**BEFORE (generic fallback, lines 229-323):**
```python
    # Generic fallback - queries each route table with _table_exists check
    if _table_exists(cursor, "python_routes"):
        cursor.execute("SELECT file, line, pattern, method FROM python_routes ...")
        ...
    if _table_exists(cursor, "js_routes"):
        cursor.execute("SELECT file, line, pattern, method FROM js_routes ...")
        ...
    if _table_exists(cursor, "go_routes"):
        cursor.execute("SELECT file, line, path, method FROM go_routes ...")
        ...
    if _table_exists(cursor, "rust_attributes"):
        cursor.execute("SELECT file_path, target_line, args, attribute_name FROM rust_attributes ...")
        ...
```

**AFTER (generic fallback):**
```python
    # Import at top of file
    from theauditor.core.language_metadata import LanguageMetadataService

    # In generic fallback section (AFTER framework routing):

    # Get all route tables from metadata service (ZERO FALLBACK compliant)
    # These tables are KNOWN to exist - no existence checks needed
    route_tables = LanguageMetadataService.get_all_route_tables()
    if route_tables:
        entries_per_table = max(1, remaining_entries // len(route_tables))

        for route_info in route_tables:
            # Build query with correct column names for this language
            query = route_info.build_query(limit=entries_per_table)
            cursor.execute(query)

            for row in cursor.fetchall():
                # Columns are normalized by build_query(): file, line, pattern, method
                entry_points.append({
                    "file": row[0],
                    "line": row[1] or 0,
                    "pattern": row[2],
                    "method": row[3],
                    "language": route_info.table_name.replace("_routes", "").replace("_attributes", ""),
                    "source": "route_table",
                })

            remaining_entries -= cursor.rowcount
            if remaining_entries <= 0:
                break
```

**IMPORTANT**: The `api_endpoints` table query should REMAIN as a separate query
because it's a normalized endpoint table, not a language-specific route table.

---

#### Framework Integration Pattern

The updated function structure should be:

```python
def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """Analyze input validation boundaries across entry points.

    Uses framework-aware routing:
    1. Detect frameworks (Express, FastAPI, etc.)
    2. Route to framework-specific analyzers if available
    3. Fall back to generic RouteTableInfo queries for other languages
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        # Step 1: Detect frameworks (KEEP - uses _detect_frameworks)
        frameworks = _detect_frameworks(cursor)

        # Step 2: Route to framework-specific analyzers (KEEP)
        if "express" in frameworks:
            # Check if framework has custom analyzer via metadata service
            from theauditor.core.language_metadata import LanguageMetadataService
            if LanguageMetadataService.has_custom_analyzer("javascript", "express"):
                # Use existing dedicated Express analyzer
                results.extend(_analyze_express_boundaries(cursor, frameworks["express"], max_entries))
                # Reduce remaining entries
                remaining_entries = max_entries - len(results)
            else:
                remaining_entries = max_entries
        else:
            remaining_entries = max_entries

        # Step 3: Generic fallback (FIX THIS SECTION)
        # Use RouteTableInfo queries instead of _table_exists checks
        if remaining_entries > 0:
            route_tables = LanguageMetadataService.get_all_route_tables()
            # ... process route tables using build_query() ...

    finally:
        conn.close()

    return results
```

---

**ZERO FALLBACK COMPLIANCE CHECKLIST:**
- [ ] `_table_exists()` function DELETED
- [ ] NO `if _table_exists(cursor, "xxx"):` checks remain
- [ ] NO try-except around `cursor.execute()` with fallback
- [ ] `_analyze_express_boundaries()` UNCHANGED (preserves middleware chain analysis)
- [ ] Generic fallback uses RouteTableInfo.build_query()

- [ ] 4.3 Complete

---

## 5. Validation

### 5.1 Run aud full --offline
```bash
cd C:/Users/santa/Desktop/TheAuditor
aud full --offline
```
- [ ] 5.1 Complete (no errors)

### 5.2 Test explain command
```bash
aud explain --help
aud explain theauditor/cli.py
```
- [ ] 5.2 Complete

### 5.3 Test deadcode command
```bash
aud deadcode --help
aud deadcode
```
- [ ] 5.3 Complete

### 5.4 Test boundaries command (including Express)
```bash
aud boundaries --help
aud boundaries --type input-validation
```
Verify Express middleware analysis still works.
- [ ] 5.4 Complete

### 5.5 Verify metadata service populated
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.core.language_metadata import LanguageMetadataService
print('Extensions:', len(LanguageMetadataService.get_all_extensions()))
print('Route tables:', len(LanguageMetadataService.get_all_route_tables()))
print('Entry points:', list(LanguageMetadataService.get_all_entry_points().keys()))
print('Express has custom analyzer:', LanguageMetadataService.has_custom_analyzer('javascript', 'express'))
"
```
Expected output:
- Extensions: 15+ (all supported file types)
- Route tables: 4 (python, js, go, rust)
- Entry points: ['python', 'javascript', 'rust', 'go']
- Express has custom analyzer: True

- [ ] 5.5 Complete

---

## 6. Post-Implementation Audit (TEAMSOP REQUIRED)

### 6.1 Re-read all modified files
- [ ] 6.1 Verify `theauditor/core/__init__.py` syntax correct
- [ ] 6.2 Verify `theauditor/core/language_metadata.py` syntax correct
- [ ] 6.3 Verify `theauditor/indexer/extractors/__init__.py` syntax correct
- [ ] 6.4 Verify all 5 extractor files syntax correct
- [ ] 6.5 Verify `theauditor/indexer/orchestrator.py` syntax correct
- [ ] 6.6 Verify `theauditor/commands/explain.py` syntax correct
- [ ] 6.7 Verify `theauditor/context/deadcode_graph.py` syntax correct
- [ ] 6.8 Verify `theauditor/boundaries/boundary_analyzer.py` syntax correct

### 6.2 Confirm ZERO FALLBACK compliance
- [ ] 6.9 No try-except fallbacks in any migration code
- [ ] 6.10 No _table_exists() checks remain in generic fallback
- [ ] 6.11 No multiple query attempts with fallback

### 6.3 Confirm framework integration
- [ ] 6.12 Express analyzer preserved (_analyze_express_boundaries unchanged)
- [ ] 6.13 JavaScriptExtractor.get_framework_routes() returns Express info
- [ ] 6.14 LanguageMetadataService.has_custom_analyzer("javascript", "express") returns True

---

## Summary

| Phase | Tasks | Est. Lines Changed | Risk |
|-------|-------|-------------------|------|
| Phase 1 | 4 tasks | +200 (new files) | LOW |
| Phase 2 | 5 tasks | +100 (metadata methods) | LOW |
| Phase 3 | 1 task | +3 (initialization) | LOW |
| Phase 4 | 3 tasks | -150 / +50 (net -100) | MEDIUM |
| Phase 5 | 5 tasks | 0 (verification) | N/A |
| Phase 6 | 3 audits | 0 (verification) | N/A |

**Total**: ~300 lines added, ~150 lines deleted = net +150 lines
**Key Risk**: boundary_analyzer.py migration - mitigated by preserving framework analyzers
**Framework Preservation**: Express analyzer (_analyze_express_boundaries) remains intact
