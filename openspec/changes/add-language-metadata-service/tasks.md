## 0. Verification (TEAMSOP REQUIRED)

Before implementation, verify these hypotheses against live code:

- [ ] 0.1 Verify `theauditor/core/` directory does NOT exist (must create)
- [ ] 0.2 Verify BaseExtractor ends at line 77 with `cleanup()` method
- [ ] 0.3 Verify ExtractorRegistry ends at line 136 with `supported_extensions()`
- [ ] 0.4 Verify route table column names match spec (check boundary_analyzer.py:36-130)
- [ ] 0.5 Verify all 12 extractors exist in `theauditor/indexer/extractors/`

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
- LanguageMetadata dataclass
- LanguageMetadataService singleton with all methods

- [ ] 1.2 Complete

### 1.3 Add metadata methods to BaseExtractor
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: After line 77 (after `cleanup` method)

**Add import at top:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Add after cleanup() method:**
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

- [ ] 1.3 Complete

### 1.4 Add query methods to ExtractorRegistry
**File**: `theauditor/indexer/extractors/__init__.py`
**Location**: After line 136 (end of ExtractorRegistry class)

**Add this code:**
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

- [ ] 1.4 Complete

---

## 2. Extractor Metadata Overrides (5 Main Extractors)

### 2.1 PythonExtractor
**File**: `theauditor/indexer/extractors/python.py`
**Location**: Inside class, after `supported_extensions` (around line 21)

**Add import at top:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Add methods:**
```python
    def get_language_id(self) -> str:
        return "python"

    def get_display_name(self) -> str:
        return "Python"

    def get_entry_point_patterns(self) -> list[str]:
        return ["main.py", "__main__.py", "cli.py", "wsgi.py", "asgi.py"]

    def get_route_table(self) -> RouteTableInfo | None:
        return RouteTableInfo("python_routes", "file", "line", "pattern", "method", None)
```

- [ ] 2.1 Complete

### 2.2 JavaScriptExtractor
**File**: `theauditor/indexer/extractors/javascript.py`
**Location**: Inside class, after `supported_extensions` (around line 19)

**Add import at top:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Add methods:**
```python
    def get_language_id(self) -> str:
        return "javascript"

    def get_display_name(self) -> str:
        return "JavaScript/TypeScript"

    def get_entry_point_patterns(self) -> list[str]:
        return ["index.js", "index.ts", "index.tsx", "App.tsx", "main.js", "main.ts"]

    def get_route_table(self) -> RouteTableInfo | None:
        return RouteTableInfo("js_routes", "file", "line", "pattern", "method", None)
```

- [ ] 2.2 Complete

### 2.3 RustExtractor
**File**: `theauditor/indexer/extractors/rust.py`
**Location**: Inside class, after `supported_extensions` (around line 23)

**Add import at top:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Add methods:**
```python
    def get_language_id(self) -> str:
        return "rust"

    def get_display_name(self) -> str:
        return "Rust"

    def get_entry_point_patterns(self) -> list[str]:
        return ["main.rs", "lib.rs"]

    def get_route_table(self) -> RouteTableInfo | None:
        return RouteTableInfo(
            "rust_attributes",
            "file_path",
            "target_line",
            "args",
            "attribute_name",
            "attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')"
        )
```

- [ ] 2.3 Complete

### 2.4 GoExtractor
**File**: `theauditor/indexer/extractors/go.py`
**Location**: Inside class, after `supported_extensions` (around line 22)

**Add import at top:**
```python
from theauditor.core.language_metadata import RouteTableInfo
```

**Add methods:**
```python
    def get_language_id(self) -> str:
        return "go"

    def get_display_name(self) -> str:
        return "Go"

    def get_entry_point_patterns(self) -> list[str]:
        return ["main.go"]

    def get_route_table(self) -> RouteTableInfo | None:
        return RouteTableInfo("go_routes", "file", "line", "path", "method", None)
```

- [ ] 2.4 Complete

### 2.5 BashExtractor
**File**: `theauditor/indexer/extractors/bash.py`
**Location**: Inside class, after `supported_extensions` (around line 17)

**Add methods (NO import needed - no route table):**
```python
    def get_language_id(self) -> str:
        return "bash"

    def get_display_name(self) -> str:
        return "Bash"

    def get_entry_point_patterns(self) -> list[str]:
        return []  # All .sh/.bash files are considered entry points by convention

    def get_route_table(self) -> None:
        return None  # Bash has no routes
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

def get_supported_extensions() -> set[str]:
    """Get supported extensions from metadata service.

    ZERO FALLBACK: Raises RuntimeError if service not initialized.
    Must be called from command context (after orchestrator init).
    """
    extensions = LanguageMetadataService.get_all_extensions()
    if not extensions:
        raise RuntimeError(
            "LanguageMetadataService not initialized. "
            "This function must be called from command execution context, not at module import time."
        )
    return set(extensions)
```

**MIGRATION NOTE**: The old `FILE_EXTENSIONS` constant was evaluated at module import time.
Replace all usages of `FILE_EXTENSIONS` with `get_supported_extensions()` calls inside command
functions (where orchestrator has already run). Do NOT call at module level.

**Find usages:**
```bash
grep -n "FILE_EXTENSIONS" theauditor/commands/explain.py
```

**Replace pattern:**
```python
# BEFORE (module level)
if ext in FILE_EXTENSIONS:

# AFTER (inside function, after service is initialized)
if ext in get_supported_extensions():
```

**ZERO FALLBACK COMPLIANCE**: No fallback. If service not initialized, fail loud with clear error.

- [ ] 4.1 Complete

### 4.2 Migrate deadcode_graph.py entry points
**File**: `theauditor/context/deadcode_graph.py`

**Location**: `_find_entry_points` method (lines 282-309)

**BEFORE (lines 287-298):** Hardcoded patterns inline

**AFTER:** Replace the hardcoded pattern check with service call

```python
from theauditor.core.language_metadata import LanguageMetadataService

def _find_entry_points(self, graph: nx.DiGraph) -> set[str]:
    """Multi-strategy entry point detection."""
    entry_points = set()

    # Get all entry point patterns from metadata service
    all_entry_points = LanguageMetadataService.get_all_entry_points()

    for node in graph.nodes():
        # Check against all language entry point patterns
        for lang_id, patterns in all_entry_points.items():
            if any(pattern in node for pattern in patterns):
                entry_points.add(node)
                break

        # BASH EDGE CASE: BashExtractor returns [] for entry_point_patterns
        # because ALL .sh/.bash files are entry points by convention.
        # This logic must remain here (not in extractor) because it's a
        # "match all files of this type" rule, not a filename pattern.
        if node.endswith(".sh") or node.endswith(".bash"):
            entry_points.add(node)

    entry_points.update(self._find_decorated_entry_points())
    entry_points.update(self._find_framework_entry_points())

    # Test files are always entry points
    for node in graph.nodes():
        if any(pattern in node for pattern in ["test_", ".test.", ".spec.", "_test.py"]):
            entry_points.add(node)

    return entry_points
```

**BASH EDGE CASE DOCUMENTED**: BashExtractor.get_entry_point_patterns() returns `[]` because
the rule is "all .sh/.bash files are entry points" - not specific filename patterns. This
extension-based check remains in deadcode_graph.py because the metadata service pattern
matching is filename-based, not extension-based.

- [ ] 4.2 Complete

### 4.3 Migrate boundary_analyzer.py route tables (ZERO FALLBACK FIX)
**File**: `theauditor/boundaries/boundary_analyzer.py`

**CRITICAL**: Current code uses `_table_exists()` checks which VIOLATES ZERO FALLBACK.

**Step 1: DELETE `_table_exists` function (lines 16-22)**
```python
# DELETE THIS ENTIRE FUNCTION
def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None
```

**Step 2: Add import at top of file (after existing imports):**
```python
from theauditor.core.language_metadata import LanguageMetadataService
```

**Step 3: REPLACE entire `analyze_input_validation_boundaries` function (lines 25-215):**
```python
def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """Analyze input validation boundaries across all entry points.

    ZERO FALLBACK: Queries only route tables that are registered via LanguageMetadataService.
    No _table_exists() checks. No try-except around queries.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        entry_points = []

        # Get all route tables from metadata service (ZERO FALLBACK compliant)
        # These tables are GUARANTEED to exist because they're defined by loaded extractors
        route_tables = LanguageMetadataService.get_all_route_tables()
        entries_per_table = max_entries // max(len(route_tables), 1)

        for route_info in route_tables:
            query = route_info.build_query(limit=entries_per_table)
            cursor.execute(query)
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append({
                    "type": "http",
                    "name": f"{method or 'GET'} {pattern}",
                    "file": file,
                    "line": line or 0,
                })

        # Load graph ONCE before loop (O(1) instead of O(N) disk I/O)
        graph_db_path = str(Path(db_path).parent / "graphs.db")
        store = XGraphStore(graph_db_path)
        call_graph = store.load_call_graph()

        if not call_graph.get("nodes") or not call_graph.get("edges"):
            raise RuntimeError(
                f"Graph DB empty or missing at {graph_db_path}. "
                "Run 'aud graph build' to generate the call graph."
            )

        # Build index ONCE for O(1) node lookups (instead of O(N) per lookup)
        _build_graph_index(call_graph)

        for entry in entry_points[:max_entries]:
            controls = find_all_paths_to_controls(
                db_path=db_path,
                entry_file=entry["file"],
                entry_line=entry["line"],
                control_patterns=VALIDATION_PATTERNS,
                max_depth=5,
                call_graph=call_graph,
            )

            quality = measure_boundary_quality(controls)

            violations = []

            if quality["quality"] == "missing":
                violations.append(
                    {
                        "type": "NO_VALIDATION",
                        "severity": "CRITICAL",
                        "message": "Entry point accepts external data without validation control in call chain",
                        "facts": quality["facts"],
                    }
                )

            elif quality["quality"] == "fuzzy":
                if len(controls) > 1:
                    control_names = [c["control_function"] for c in controls]
                    violations.append(
                        {
                            "type": "SCATTERED_VALIDATION",
                            "severity": "MEDIUM",
                            "message": f"Multiple validation controls: {', '.join(control_names)}",
                            "facts": quality["facts"],
                        }
                    )

                for control in controls:
                    if control["distance"] >= 3:
                        violations.append(
                            {
                                "type": "VALIDATION_DISTANCE",
                                "severity": "HIGH",
                                "message": f"Validation '{control['control_function']}' occurs at distance {control['distance']}",
                                "control": control,
                                "facts": [
                                    f"Data flows through {control['distance']} functions before validation",
                                    f"Call path: {' -> '.join(control['path'])}",
                                    f"Distance {control['distance']} creates {control['distance']} potential unvalidated code paths",
                                ],
                            }
                        )

            results.append(
                {
                    "entry_point": entry["name"],
                    "entry_file": entry["file"],
                    "entry_line": entry["line"],
                    "controls": controls,
                    "quality": quality,
                    "violations": violations,
                }
            )

    finally:
        conn.close()

    return results
```

**ZERO FALLBACK COMPLIANCE:**
- NO `_table_exists()` checks - DELETED
- NO try-except around `cursor.execute()` - queries fail loud if tables missing
- Route tables from `get_all_route_tables()` are KNOWN to exist (defined by extractors)

**NOTE**: The `generate_report` function (lines 218-288) remains UNCHANGED.

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

### 5.4 Test boundaries command
```bash
aud boundaries --help
aud boundaries --type input-validation
```
- [ ] 5.4 Complete

### 5.5 Verify metadata service populated
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.core.language_metadata import LanguageMetadataService
print('Extensions:', len(LanguageMetadataService.get_all_extensions()))
print('Route tables:', len(LanguageMetadataService.get_all_route_tables()))
print('Entry points:', LanguageMetadataService.get_all_entry_points().keys())
"
```
- [ ] 5.5 Complete

---

## 6. Cleanup (Delete Hardcoded Data)

### 6.1 Delete FILE_EXTENSIONS constant from explain.py
After validation, remove the static fallback set if no longer needed.
- [ ] 6.1 Complete

### 6.2 Delete _table_exists function from boundary_analyzer.py
- [ ] 6.2 Complete

### 6.3 Simplify deadcode_graph.py _find_framework_entry_points
The framework entry points query (lines 329-376) can also be simplified
using metadata service, but this is OPTIONAL (separate ticket).
- [ ] 6.3 Complete (or deferred)

---

## 7. Post-Implementation Audit (TEAMSOP REQUIRED)

### 7.1 Re-read all modified files
- [ ] 7.1 Verify `theauditor/core/__init__.py` syntax correct
- [ ] 7.2 Verify `theauditor/core/language_metadata.py` syntax correct
- [ ] 7.3 Verify `theauditor/indexer/extractors/__init__.py` syntax correct
- [ ] 7.4 Verify all 5 extractor files syntax correct
- [ ] 7.5 Verify `theauditor/indexer/orchestrator.py` syntax correct
- [ ] 7.6 Verify `theauditor/commands/explain.py` syntax correct
- [ ] 7.7 Verify `theauditor/context/deadcode_graph.py` syntax correct
- [ ] 7.8 Verify `theauditor/boundaries/boundary_analyzer.py` syntax correct

### 7.2 Confirm ZERO FALLBACK compliance
- [ ] 7.9 No try-except fallbacks in any migration code
- [ ] 7.10 No _table_exists() checks remain
- [ ] 7.11 No multiple query attempts with fallback
