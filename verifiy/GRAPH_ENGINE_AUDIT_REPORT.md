# Graph Engine Audit Report
**Date:** 2025-01-19
**Auditor:** Claude (Opus)
**Scope:** Full due diligence of graph building engine (`theauditor/graph/`)
**Mandate:** Find bugs, CLAUDE.md violations, bad practices, modernization opportunities

---

## Executive Summary

**CRITICAL SYSTEM FAILURE DETECTED**

The graph building engine has a **99.1% false positive rate** for internal project imports. Out of 2,755 import edges, only 24 (0.9%) are correctly identified as internal - the rest are incorrectly marked as `external::`.

### Impact Assessment
- **Deadcode Detection:** Unusable (300 false positives out of 360 files)
- **Graph Analysis:** Severely degraded (dependency cycles undetectable)
- **Impact Analysis:** Unreliable (can't trace internal dependencies)
- **Architecture Visualization:** Misleading (shows external deps, hides internal structure)

### Root Cause
Python import resolution (builder.py:262-265) assumes import strings are module names (`theauditor.cli`), but refs table stores file paths (`theauditor/cli.py`). When resolution splits on `.`, it converts `theauditor/cli.py` → `theauditor/cli/py`, causing path mismatch.

**Status:** PRODUCTION BUG - Engine non-functional for Python projects

---

## Critical Bugs

### Bug #1: Python Import Path Resolution
**File:** `theauditor/graph/builder.py:262-265`
**Severity:** CRITICAL - 99.1% false positive rate
**Impact:** Graph building completely broken for Python projects

#### The Code
```python
def resolve_import_path(self, import_str: str, source_file: Path, lang: str) -> str:
    """Resolve import string to a normalized module path."""
    import_str = import_str.strip().strip('"\'`;')

    # Language-specific resolution
    if lang == "python":
        # Convert Python module path to file path
        parts = import_str.split(".")  # ← BUG HERE
        return "/".join(parts)  # ← AND HERE
```

#### The Problem
**Assumption:** Import strings are module names (e.g., `theauditor.cli`)
**Reality:** refs table stores file paths (e.g., `theauditor/cli.py`)

**What happens:**
```python
# Input from refs table
import_str = "theauditor/cli.py"

# Current code splits on ALL dots (including file extension)
parts = import_str.split(".")
# Result: ['theauditor/cli', 'py']

# Joins with slash
resolved = "/".join(parts)
# Result: "theauditor/cli/py"  ❌ WRONG

# Expected result: "theauditor/cli.py"  ✅ CORRECT
```

#### Verification
Database query confirms 99.1% false positive rate:
```sql
SELECT COUNT(*) FROM edges WHERE graph_type = 'import' AND target LIKE 'external::%'
-- Result: 2,731 / 2,755 edges (99.1%)
```

Sample incorrect externals:
```
external::theauditor/commands/deadcode/py  ← Should be internal
external::theauditor/rules/base/py         ← Should be internal
external::theauditor/indexer/schema/py     ← Should be internal
```

#### Impact Chain
1. Import path resolved incorrectly (`/py` suffix)
2. Path doesn't match files in `current_files` dict
3. `resolved_exists` returns False
4. Import marked as `external::` (line 568)
5. Deadcode detector can't find internal dependencies
6. 300 files flagged as dead when they're actively used

#### The Fix
```python
if lang == "python":
    # refs table already has file paths with forward slashes
    # Don't split if already a path (contains /)
    if "/" in import_str:
        # Already a file path, return as-is
        return import_str.replace("\\", "/")
    else:
        # Module name, convert to path
        parts = import_str.split(".")
        return "/".join(parts) + ".py"
```

---

### Bug #2: External Detection Logic
**File:** `theauditor/graph/builder.py:552-568`
**Severity:** HIGH - Incorrect external classification
**Impact:** Internal files in workset/subset builds marked as external

#### The Code
```python
# Build current_files from files being analyzed
for file_path, lang in files:
    rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
    current_files[rel_path] = {
        'hash': file_hash,
        'language': lang,
        'size': file_path.stat().st_size,
    }

# Later, check if resolved import exists
resolved_exists = resolved_norm in current_files  # ← BUG: Wrong source of truth

if resolved_exists:
    target_id = resolved_norm
    # ... create internal node
else:
    external_id = resolved_norm or raw_value or "unknown"
    target_id = f"external::{external_id}"  # ← Marks as external
```

#### The Problem
`current_files` only contains files in the current build batch. If:
- User runs `aud graph build --workset subset.json`
- File A imports File B
- File B is NOT in workset
- File B is marked as `external::` even though it's internal to project

#### The Fix
Use database as source of truth, not in-memory dict:
```python
# Query database for file existence
if self.db_path.exists():
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (resolved_norm,))
    resolved_exists = cursor.fetchone() is not None
    conn.close()
else:
    resolved_exists = False
```

---

## CLAUDE.md Violations (Forbidden Cancer)

### Violation Category: Database Query Fallbacks
**Count:** 6 instances
**Severity:** Architecture violation - violates zero fallback policy

#### Instance #1: Import Extraction Fallback
**Location:** builder.py:145-147
```python
if not self.db_path.exists():
    print(f"Warning: Database not found at {self.db_path}")
    return []  # ❌ FALLBACK - Should crash
```

**CLAUDE.md Rule (Lines 88-104):**
```python
# ❌ CANCER - Database migrations
def _run_migrations(self):
    try:
        cursor.execute("ALTER TABLE...")
    except sqlite3.OperationalError:
        pass  # NO! Database is fresh every run!

# ❌ CANCER - Table existence checking
if 'function_call_args' not in existing_tables:
    return findings  # NO! Tables MUST exist!
```

**What should happen:**
```python
if not self.db_path.exists():
    raise FileNotFoundError(
        f"repo_index.db not found: {self.db_path}\n"
        f"Run 'aud full' to create it."
    )
```

#### Instance #2: Import Query Error Fallback
**Location:** builder.py:171-173
```python
except sqlite3.Error as exc:
    print(f"Warning: Failed to read imports for {rel_path}: {exc}")
    return []  # ❌ FALLBACK - Should crash
```

#### Instance #3: Export Extraction Fallback
**Location:** builder.py:187-188
```python
if not self.db_path.exists():
    return []  # ❌ FALLBACK
```

#### Instance #4: Export Query Error Fallback
**Location:** builder.py:207-208
```python
except sqlite3.Error:
    return []  # ❌ FALLBACK
```

#### Instance #5: Call Args Extraction Fallback
**Location:** builder.py:222-223
```python
if not self.db_path.exists():
    return []  # ❌ FALLBACK
```

#### Instance #6: Call Args Query Error Fallback
**Location:** builder.py:241-242
```python
except sqlite3.Error:
    return []  # ❌ FALLBACK
```

### Why This is Cancer
From CLAUDE.md (lines 111-123):
```
**WHY NO FALLBACKS EVER:**

The database is regenerated FRESH on every `aud full` run. If data is missing:
- **The database is WRONG** → Fix the indexer
- **The query is WRONG** → Fix the query
- **The schema is WRONG** → Fix the schema

Fallbacks HIDE bugs. They create:
- Inconsistent behavior across runs
- Silent failures that compound
- Technical debt that spreads like cancer
- False sense of correctness
```

**Current behavior:** Returns empty list, graph builds with missing data, looks successful
**Correct behavior:** Crashes immediately with clear error, forces user to fix root cause

---

## Bad Practices

### BP #1: Metric Collection Fallbacks
**Location:** builder.py:393-431
**Severity:** MEDIUM - Hides data quality issues

#### Lines 393-398
```python
try:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        metrics["loc"] = sum(1 for _ in f)
except (IOError, UnicodeDecodeError, OSError) as e:
    print(f"Warning: Failed to read {file_path} for metrics: {e}")
    # Still return default metrics but LOG the failure  # ← Fallback
```

#### Lines 428-430
```python
except (subprocess.TimeoutExpired, OSError, IOError) as e:
    print(f"Warning: Failed to get git churn for {file_path}: {e}")
    # Still return default metrics but LOG the failure  # ← Fallback
```

**Problem:** Returns default metrics (LOC=0, churn=None) on failure. Graph shows incorrect data without user awareness.

**Correct pattern:** Either fail hard or mark node as "metrics_unavailable" in metadata.

---

### BP #2: Complex Nested Fallback Logic
**Location:** builder.py:299-325
**Severity:** MEDIUM - Multi-level fallbacks

```python
# Try ModuleResolver
resolved = self.module_resolver.resolve_with_context(import_str, str(source_file), context)

# Check if resolution succeeded
if resolved != import_str:
    # Resolution worked, now verify file exists in database
    if self.db_path.exists():
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Try with common extensions
            for ext in [".ts", ".tsx", ".js", ".jsx"]:
                cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (test_path,))
                if cursor.fetchone():
                    return test_path

            # If file check failed, return resolved anyway  # ← Fallback
            return resolved
```

**Problem:**
1. Try ModuleResolver resolution
2. If that works, try database query
3. If database query works, try each extension
4. If all fail, return unverified path anyway

This is fallback logic disguised as path resolution.

---

### BP #3: Path Normalization Inconsistency
**Severity:** LOW - Code smell

**Multiple inconsistent approaches:**
```python
# Approach 1 (line 182)
db_path = str(rel_path).replace("\\", "/")

# Approach 2 (line 217)
db_path = str(rel_path).replace("\\", "/")

# Approach 3 (line 551)
resolved_norm = resolved.replace('\\', '/') if resolved else None
```

**Problem:** Same operation repeated 10+ times across file. Should be centralized function.

---

## Technical Debt

### TD #1: Incomplete Python Import Resolution
**Impact:** Doesn't handle common patterns

**Missing cases:**
1. Package imports: `from theauditor.commands import deadcode`
2. __init__.py resolution: `from theauditor.commands import *`
3. Relative imports: `from . import sibling`
4. Namespace packages

**Current code only handles:**
- Absolute module names: `theauditor.cli`
- Full file paths: `theauditor/cli.py` (but incorrectly)

---

### TD #2: No Schema Contract Validation
**Impact:** Silent failures if database schema wrong

**Missing validation:**
- No check that `files` table exists
- No check that columns are correct type
- No check that indexes are present
- Assumes query results match expected format

**Should have:**
```python
def _validate_database_schema(self):
    """Validate repo_index.db has required tables and columns."""
    cursor = self.conn.cursor()

    # Check files table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
    if not cursor.fetchone():
        raise ValueError("files table not found in repo_index.db. Run 'aud full'.")

    # Check required columns
    cursor.execute("PRAGMA table_info(files)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'path' not in columns:
        raise ValueError("files table missing 'path' column. Database schema is wrong.")
```

---

### TD #3: current_files Dict Design Flaw
**Impact:** Memory inefficient, incorrect semantics

**Current approach:**
```python
# Build in-memory dict of all files
current_files = {}
for file_path, lang in files:
    rel_path = str(file_path.relative_to(root_path)).replace('\\', '/')
    current_files[rel_path] = {
        'hash': file_hash,
        'language': lang,
        'size': file_path.stat().st_size,
    }
```

**Problems:**
1. Duplicates data already in database (memory waste)
2. Only contains files in current batch (incorrect semantics)
3. Used as source of truth for internal/external detection (wrong)

**Should use:** Database query for file existence checks.

---

## Statistics

### Codebase Metrics
- **Total lines:** builder.py = 1,042 lines
- **Try/except blocks:** 36 across 3 files in `/graph` module
- **Fallback returns:** 6 explicit `return []` on database errors
- **Path normalization calls:** 10+ instances of `.replace("\\", "/")`

### Bug Impact
- **False positive rate:** 99.1% (2,731/2,755 edges marked as external)
- **Correct internal edges:** 24 / 2,755 (0.9%)
- **Deadcode false positives:** 300 / 360 files (83%)
- **Graph analysis degradation:** ~99% (can't detect cycles, hotspots in internal code)

---

## Modernization Recommendations

### Immediate Fixes (P0 - Required)

#### 1. Fix Python Import Resolution
**File:** builder.py:262-265

**Current:**
```python
if lang == "python":
    parts = import_str.split(".")
    return "/".join(parts)
```

**Fixed:**
```python
if lang == "python":
    # refs table stores file paths, not module names
    # Format: "theauditor/cli.py" NOT "theauditor.cli"
    if "/" in import_str:
        # Already a file path
        return import_str.replace("\\", "/")
    else:
        # Module name, convert to path
        parts = import_str.split(".")
        return "/".join(parts) + ".py"
```

**Test case:**
```python
assert resolve_import_path("theauditor/cli.py", ..., "python") == "theauditor/cli.py"
assert resolve_import_path("theauditor.cli", ..., "python") == "theauditor/cli.py"
```

---

#### 2. Remove ALL Fallback Logic
**Files:** builder.py (6 instances)

**Pattern to replace:**
```python
# BEFORE (CANCER)
if not self.db_path.exists():
    return []

# AFTER (CORRECT)
if not self.db_path.exists():
    raise FileNotFoundError(
        f"repo_index.db not found: {self.db_path}\n"
        f"Run 'aud full' to create it."
    )
```

**Apply to all:**
- Lines 145-147 (extract_imports_from_db)
- Lines 171-173 (extract_imports exception)
- Lines 187-188 (extract_exports_from_db)
- Lines 207-208 (extract_exports exception)
- Lines 222-223 (extract_call_args_from_db)
- Lines 241-242 (extract_call_args exception)

---

#### 3. Fix External Detection Logic
**File:** builder.py:552-568

**Current:**
```python
resolved_exists = resolved_norm in current_files  # ← Wrong source of truth
```

**Fixed:**
```python
# Query database for file existence
if not self.db_path.exists():
    raise FileNotFoundError(f"repo_index.db not found: {self.db_path}")

conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
cursor.execute("SELECT 1 FROM files WHERE path = ? LIMIT 1", (resolved_norm,))
resolved_exists = cursor.fetchone() is not None
conn.close()
```

**Alternative (cache database files once):**
```python
# In __init__ or build_import_graph start
self.all_indexed_files = self._load_all_indexed_files()

def _load_all_indexed_files(self) -> set[str]:
    """Load all indexed file paths from database."""
    if not self.db_path.exists():
        raise FileNotFoundError(f"repo_index.db not found: {self.db_path}")

    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM files")
    files = {row[0] for row in cursor.fetchall()}
    conn.close()
    return files

# Then use
resolved_exists = resolved_norm in self.all_indexed_files
```

---

### Architecture Improvements (P1 - Recommended)

#### 1. Centralize Path Normalization
**Create:** `theauditor/graph/path_utils.py`

```python
def normalize_path(path: str | Path) -> str:
    """Normalize path to forward-slash format.

    Args:
        path: File path (Windows or Unix format)

    Returns:
        Normalized path with forward slashes

    Examples:
        >>> normalize_path("C:\\Users\\santa\\Desktop\\file.py")
        "C:/Users/santa/Desktop/file.py"
        >>> normalize_path("theauditor\\cli.py")
        "theauditor/cli.py"
    """
    return str(path).replace("\\", "/")
```

Replace all 10+ instances of `.replace("\\", "/")` with this function.

---

#### 2. Add Schema Validation on Init
**File:** builder.py `__init__` method

```python
def __init__(self, batch_size: int = 200, exclude_patterns: list[str] = None, project_root: str = "."):
    self.batch_size = batch_size
    self.exclude_patterns = exclude_patterns or []
    self.project_root = Path(project_root).resolve()
    self.db_path = self.project_root / ".pf" / "repo_index.db"

    # Validate database exists and schema is correct
    self._validate_database()

    self.module_resolver = ModuleResolver(db_path=str(self.db_path))
    self.ast_parser = ASTParser()

def _validate_database(self):
    """Validate repo_index.db exists and has required schema."""
    if not self.db_path.exists():
        raise FileNotFoundError(
            f"repo_index.db not found: {self.db_path}\n"
            f"Run 'aud full' to create it."
        )

    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    # Check required tables exist
    required_tables = ['files', 'refs', 'symbols', 'function_call_args']
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    missing = set(required_tables) - existing_tables
    if missing:
        raise ValueError(
            f"Database schema incomplete. Missing tables: {missing}\n"
            f"Run 'aud full' to rebuild database."
        )

    conn.close()
```

---

#### 3. Separate External Dependency Detection
**Create:** `theauditor/graph/dependency_classifier.py`

```python
class DependencyClassifier:
    """Classify imports as internal project files or external dependencies."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.internal_files = self._load_internal_files()
        self.stdlib_modules = self._load_stdlib_modules()

    def _load_internal_files(self) -> set[str]:
        """Load all internal project files from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM files")
        files = {row[0] for row in cursor.fetchall()}
        conn.close()
        return files

    def _load_stdlib_modules(self) -> set[str]:
        """Load Python standard library module names."""
        import sys
        return set(sys.stdlib_module_names)

    def classify(self, import_path: str, lang: str) -> tuple[str, str]:
        """Classify import as internal or external.

        Returns:
            (classification, reason) where classification is:
            - 'internal': Project file
            - 'external_stdlib': Standard library
            - 'external_package': Third-party package
        """
        if lang == "python":
            # Check stdlib first
            module_root = import_path.split("/")[0].split(".")[0]
            if module_root in self.stdlib_modules:
                return ("external_stdlib", "Python standard library")

            # Check if internal file
            if import_path in self.internal_files:
                return ("internal", "Project file")

            # Try with .py extension
            if import_path + ".py" in self.internal_files:
                return ("internal", "Project file")

            # External package
            return ("external_package", "Third-party package")

        # Similar logic for JavaScript/TypeScript
        # ...
```

---

### Testing Recommendations

#### Unit Tests Required
```python
# tests/graph/test_import_resolution.py

def test_python_import_path_already_normalized():
    """Test that file paths in refs table are handled correctly."""
    builder = XGraphBuilder()

    # refs table format: "theauditor/cli.py"
    result = builder.resolve_import_path(
        "theauditor/cli.py",
        Path("theauditor/main.py"),
        "python"
    )

    assert result == "theauditor/cli.py"
    assert "/py" not in result  # BUG: Should not have /py suffix

def test_python_module_name_conversion():
    """Test that module names are converted correctly."""
    builder = XGraphBuilder()

    # Module name format: "theauditor.cli"
    result = builder.resolve_import_path(
        "theauditor.cli",
        Path("theauditor/main.py"),
        "python"
    )

    assert result == "theauditor/cli.py"

def test_external_detection_uses_database():
    """Test that external detection queries database, not in-memory dict."""
    # Mock database with known files
    # Verify internal files detected even if not in current_files dict
    # ...
```

#### Integration Tests Required
```python
# tests/graph/test_graph_build_integration.py

def test_graph_build_detects_internal_imports():
    """End-to-end test: build graph, verify internal imports not marked external."""
    # Run aud index
    # Run aud graph build
    # Query graphs.db
    # Verify theauditor.* imports are NOT external::

    conn = sqlite3.connect(".pf/graphs.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM edges
        WHERE graph_type = 'import'
          AND target LIKE 'external::theauditor/%'
    """)

    external_count = cursor.fetchone()[0]
    assert external_count == 0, f"Found {external_count} internal imports marked as external"
```

---

## Migration Plan

### Phase 1: Critical Bugs (P0)
**Timeline:** Immediate (1-2 hours)
**Risk:** LOW (pure bug fixes)

1. Fix Python import resolution (builder.py:262-265)
2. Fix external detection logic (builder.py:552-568)
3. Run integration tests
4. Verify deadcode detection works

**Success criteria:**
- `aud deadcode` shows <10 dead modules (not 300)
- Graph edges have <5% external rate (not 99%)

---

### Phase 2: Remove Fallbacks (P0)
**Timeline:** Immediate (30 minutes)
**Risk:** MEDIUM (changes error handling)

1. Replace all `return []` with `raise FileNotFoundError()`
2. Update error messages to guide users
3. Test error paths (missing database, missing tables)

**Success criteria:**
- `aud graph build` crashes if repo_index.db missing
- Error message tells user to run `aud full`

---

### Phase 3: Architecture Improvements (P1)
**Timeline:** 1-2 days
**Risk:** LOW (refactoring)

1. Create path_utils.py with normalize_path()
2. Replace all path normalization calls
3. Add schema validation to __init__
4. Create DependencyClassifier class
5. Add unit tests

**Success criteria:**
- All path normalization uses centralized function
- Builder crashes immediately if schema wrong
- Dependency classification is explicit

---

### Phase 4: Testing & Validation (P1)
**Timeline:** 1 day
**Risk:** NONE (testing only)

1. Write unit tests for import resolution
2. Write integration tests for graph building
3. Add regression tests for bug #1 and #2
4. Run full test suite

**Success criteria:**
- 100% test coverage for import resolution logic
- Integration tests verify <5% external edge rate
- All tests pass

---

## Conclusion

The graph building engine is currently **non-functional** for Python projects due to a critical bug in import path resolution. This bug has cascading effects throughout the system:

1. **Graph analysis** shows 99% external dependencies (should be ~50-70% internal)
2. **Deadcode detection** flags 83% of files as dead (should be <5%)
3. **Impact analysis** can't trace internal dependencies
4. **Architecture visualization** is misleading

The root cause is simple (incorrect string manipulation), but the impact is catastrophic because the bug is in a foundational component used by multiple analysis tools.

Additionally, the codebase violates CLAUDE.md's zero fallback policy in 6 places, hiding data quality issues and creating false confidence in results.

**Recommended action:** Deploy Phase 1 fixes immediately (1-2 hours work), then proceed with Phase 2 the same day. The bugs are straightforward to fix and the impact is critical.

---

## Appendix: Database Evidence

### Query 1: External Edge Rate
```sql
SELECT
    COUNT(*) FILTER (WHERE target LIKE 'external::%') as external_edges,
    COUNT(*) as total_edges,
    ROUND(100.0 * COUNT(*) FILTER (WHERE target LIKE 'external::%') / COUNT(*), 1) as pct_external
FROM edges
WHERE graph_type = 'import';
```

**Result:**
```
external_edges | total_edges | pct_external
-------------- | ----------- | ------------
2731           | 2755        | 99.1
```

---

### Query 2: Sample Incorrectly Marked Externals
```sql
SELECT DISTINCT target
FROM edges
WHERE graph_type = 'import'
  AND target LIKE 'external::theauditor/%'
LIMIT 10;
```

**Result:**
```
external::theauditor/commands/deadcode/py
external::theauditor/rules/base/py
external::theauditor/indexer/schema/py
external::theauditor/ast_extractors/base/py
external::theauditor/indexer/extractors/python/py
```

**Analysis:** All have `/py` suffix instead of `.py` extension. Confirms bug in string split logic.

---

### Query 3: Actual Import Values in refs Table
```sql
SELECT DISTINCT value
FROM refs
WHERE kind IN ('import', 'from')
  AND value LIKE 'theauditor%'
LIMIT 10;
```

**Result:**
```
theauditor/indexer/__init__.py
theauditor/indexer/schema.py
theauditor/ast_extractors/base.py
theauditor/boundaries/distance.py
theauditor/deps.py
```

**Analysis:** refs table already has file paths with `.py`, not module names. Confirms assumption mismatch in builder.py.

---

**End of Report**
