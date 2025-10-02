# Pre-Implementation Plan: TheAuditor Dogfooding Audit Fixes

**Document Version:** 1.0
**Date:** 2025-10-03
**Lead Auditor:** Opus (Claude)
**Architect:** Human (santa)
**Status:** 🟡 AWAITING ARCHITECT APPROVAL

---

## Phase 0: Project Context Summary

**Project:** TheAuditor v1.2 - Offline-First SAST & Code Intelligence Platform
**Technology Stack:** Python 3.8+, SQLite, Click, AST parsing, Tree-sitter
**Current State:** Post-dogfooding audit revealing 3 critical P0 bugs
**Analysis Scope:** 6 real-world projects analyzed, 87 unique issues documented

**Key Context:**
- TheAuditor claims "480x faster with memory cache" but cache fails on 5/6 projects
- Taint analysis broken on 5/6 projects (0 vulnerabilities detected)
- Self-analysis reports "CLEAN" with 0 symbols extracted (indexer failed silently)
- Pattern detection explodes with 900K-3.5M false positives on medium projects

**Awaiting Prompt:** Atomic, numbered implementation plan for architect approval.

---

## Pre-Implementation Plan Structure

This plan follows teamsop.md Template C-4.20 adapted for planning phase. Each phase is:
- **Atomic:** Self-contained, can be executed independently
- **Numbered:** Sequential execution order
- **Verifiable:** Success criteria defined
- **Reversible:** Rollback plan included
- **Estimated:** Time/effort quantified

---

## PHASE 1: Fix TAINT-001 - Taint Analysis Schema Mismatch (P0)

### 1.1 Objective
Restore taint analysis functionality by adding missing columns to `api_endpoints` table.

### 1.2 Hypotheses to Verify

**Hypothesis 1.1:** `api_endpoints` table missing columns: `line, path, has_auth, handler_function`
- **Verification Method:** Query database schema on all 6 projects
- **Expected Result:** Confirm schema only has: `file, method, pattern, controls`

**Hypothesis 1.2:** Taint analyzer queries these missing columns
- **Verification Method:** Read `theauditor/taint/database.py` or related files
- **Expected Result:** Find SQL query with: `SELECT file, line, method, path, has_auth, handler_function FROM api_endpoints`

**Hypothesis 1.3:** Extractors don't populate metadata
- **Verification Method:** Read JavaScript/TypeScript extractors
- **Expected Result:** Extractors only populate: `file, method, pattern, controls`

### 1.3 Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/indexer/database.py:143-148` - Current schema definition
2. `theauditor/indexer/database.py:1362` - Current INSERT statement
3. `theauditor/indexer/extractors/javascript.py` - Route extraction logic
4. `theauditor/taint/database.py:142` (approx) - Failing query location
5. `theauditor/commands/taint.py:346` - Exception handler

**EXPECTED FINDINGS:**
- Schema CREATE TABLE statement missing 4 columns
- INSERT statement only has 4 parameters
- Extractor doesn't extract line numbers or auth metadata
- Taint query expects 6 columns but table only has 4

### 1.4 Implementation Steps (Post-Verification)

**Step 1.4.1:** Update schema in `indexer/database.py`
```python
# File: theauditor/indexer/database.py
# Line: 143-148

# BEFORE:
CREATE TABLE IF NOT EXISTS api_endpoints(
    file TEXT NOT NULL,
    method TEXT NOT NULL,
    pattern TEXT NOT NULL,
    controls TEXT,
    FOREIGN KEY(file) REFERENCES files(path)
)

# AFTER:
CREATE TABLE IF NOT EXISTS api_endpoints(
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    pattern TEXT,  # Keep for backward compat
    has_auth BOOLEAN DEFAULT 0,
    handler_function TEXT,
    controls TEXT,
    FOREIGN KEY(file) REFERENCES files(path)
)
```

**Step 1.4.2:** Update INSERT statement
```python
# File: theauditor/indexer/database.py
# Line: ~1362

# BEFORE:
INSERT INTO api_endpoints (file, method, pattern, controls) VALUES (?, ?, ?, ?)

# AFTER:
INSERT INTO api_endpoints (file, line, method, path, pattern, has_auth, handler_function, controls)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```

**Step 1.4.3:** Update JavaScript/TypeScript extractor
```python
# File: theauditor/indexer/extractors/javascript.py
# Location: Route extraction function (find via grep for "add_api_endpoint")

# ADD LOGIC:
1. Extract line number where route is defined
2. Extract route path (already exists as 'pattern')
3. Detect authentication middleware (check for decorators/middleware)
4. Extract handler function name
5. Pass all 7 parameters to add_api_endpoint()
```

**Step 1.4.4:** Create migration script
```python
# NEW FILE: theauditor/migrations/001_api_endpoints_columns.py

def migrate(db_path):
    """Add missing columns to api_endpoints table."""
    conn = sqlite3.connect(db_path)

    # Check if migration needed
    schema = get_table_schema(conn, 'api_endpoints')
    if 'line' in schema:
        return  # Already migrated

    # Add columns (SQLite doesn't support multi-column ALTER)
    conn.execute("ALTER TABLE api_endpoints ADD COLUMN line INTEGER")
    conn.execute("ALTER TABLE api_endpoints ADD COLUMN path TEXT")
    conn.execute("ALTER TABLE api_endpoints ADD COLUMN has_auth BOOLEAN DEFAULT 0")
    conn.execute("ALTER TABLE api_endpoints ADD COLUMN handler_function TEXT")

    # Copy pattern to path for existing rows
    conn.execute("UPDATE api_endpoints SET path = pattern")

    conn.commit()
```

**Step 1.4.5:** Add schema validation
```python
# File: theauditor/commands/taint.py
# Location: Before taint analysis starts

# ADD VALIDATION:
def validate_schema(db_path):
    required_schema = {
        'api_endpoints': ['file', 'line', 'method', 'path', 'has_auth', 'handler_function']
    }

    for table, columns in required_schema.items():
        actual_columns = get_columns(db_path, table)
        missing = set(columns) - set(actual_columns)

        if missing:
            raise SchemaValidationError(
                f"Taint analysis requires columns {missing} in table {table}. "
                f"Run database migration or re-run 'aud index'."
            )
```

### 1.5 Verification Steps (Post-Implementation)

**Test 1.5.1:** Schema validation
```bash
sqlite3 .pf/repo_index.db ".schema api_endpoints"
# Expected: Shows 7 columns (file, line, method, path, pattern, has_auth, handler_function, controls)
```

**Test 1.5.2:** Migration works on existing database
```bash
# On plant project (existing database)
python -m theauditor.migrations.001_api_endpoints_columns .pf/repo_index.db
sqlite3 .pf/repo_index.db "SELECT line, path, has_auth FROM api_endpoints LIMIT 1"
# Expected: Returns values without error
```

**Test 1.5.3:** Extractor populates new columns
```bash
# On fresh project
rm -rf .pf/
aud index
sqlite3 .pf/repo_index.db "SELECT line, path, has_auth, handler_function FROM api_endpoints WHERE line IS NOT NULL"
# Expected: At least 1 row with non-null values
```

**Test 1.5.4:** Taint analysis runs without error
```bash
aud taint-analyze
# Expected: No "no such column: line" error
cat .pf/raw/taint_analysis.json | grep '"success": true'
# Expected: Shows success: true
```

**Test 1.5.5:** Taint finds vulnerabilities on vulnerable test code
```bash
# On project_anarchy (intentionally vulnerable)
aud taint-analyze
cat .pf/raw/taint_analysis.json | grep total_vulnerabilities
# Expected: total_vulnerabilities > 0 (not 0)
```

### 1.6 Edge Cases & Failure Modes

**Edge 1.6.1:** Existing databases without migration
- **Condition:** User runs taint analysis on old database
- **Current Behavior:** Crashes with schema error
- **Fixed Behavior:** Auto-run migration OR show clear error message
- **Mitigation:** Schema validation before taint analysis

**Edge 1.6.2:** Extractors can't determine auth status
- **Condition:** Complex middleware patterns
- **Current Behavior:** N/A (not implemented)
- **Fixed Behavior:** Set `has_auth = NULL` (unknown) instead of guessing
- **Mitigation:** Document: "has_auth=NULL means detection uncertain"

**Edge 1.6.3:** Non-web projects with no routes
- **Condition:** CLI tools, libraries with 0 API endpoints
- **Current Behavior:** Table empty
- **Fixed Behavior:** Taint analysis still runs (just no route context)
- **Mitigation:** Taint analyzer checks if table empty, skips enhancement

### 1.7 Impact Assessment

**Immediate:**
- Restores taint analysis on all 6 projects
- 0 → 50+ expected vulnerabilities detected

**Downstream:**
- All taint-dependent features work (SQL injection, XSS, command injection detection)
- API endpoint context enhances source identification

**Breaking Changes:**
- Database schema version bump (1.x → 2.0?)
- Existing databases need migration
- Old extractors incompatible

### 1.8 Reversion Plan

**Reversibility:** Partially reversible
- Schema changes: Can drop columns but lose data
- Extractor changes: Fully reversible via git revert
- Migration: Can revert but loses new data

**Revert Steps:**
```bash
git revert <commit_hash>
# Manually drop added columns:
sqlite3 .pf/repo_index.db "ALTER TABLE api_endpoints DROP COLUMN line"
# (Repeat for other columns)
```

### 1.9 Estimated Effort

**Time Breakdown:**
- Verification phase: 30 minutes (read 5 files, confirm hypotheses)
- Schema update: 30 minutes (modify CREATE TABLE + INSERT)
- Extractor update: 1.5 hours (add metadata extraction logic)
- Migration script: 45 minutes (write + test migration)
- Schema validation: 30 minutes (add validation function)
- Testing: 45 minutes (run all 5 verification tests)

**Total:** 4 hours

**Confidence:** High (straightforward schema addition)

---

## PHASE 2: Fix INDEX-001 - Missing Function (Silent Failure) (P0)

### 2.1 Objective
Fix indexer silent failure on TheAuditor self-analysis by restoring missing function.

### 2.2 Hypotheses to Verify

**Hypothesis 2.1:** Function `extract_treesitter_cfg` doesn't exist
- **Verification Method:** Python import test
- **Expected Result:** AttributeError when importing

**Hypothesis 2.2:** Function was renamed or moved during refactoring
- **Verification Method:** Git history search
- **Expected Result:** Find commit where function was removed/renamed

**Hypothesis 2.3:** Caller in `__init__.py:273` is outdated
- **Verification Method:** Read `ast_extractors/__init__.py`
- **Expected Result:** Find call to non-existent function

**Hypothesis 2.4:** Exception is caught silently
- **Verification Method:** Search for broad try-except around line 273
- **Expected Result:** Exception handler catches AttributeError as "file parsing error"

### 2.3 Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/ast_extractors/__init__.py:273` - Call site of missing function
2. `theauditor/ast_extractors/treesitter_impl.py` - Where function should exist
3. `theauditor/ast_extractors/python_impl.py` - Caller context
4. Git history: Search for "extract_treesitter_cfg" or "extract_cfg"

**EXPECTED FINDINGS:**
- Line 273 calls: `treesitter_impl.extract_treesitter_cfg(tree, self, language)`
- Function doesn't exist in treesitter_impl.py
- Broad try-except around line 273 catches AttributeError
- Git history shows function was removed or renamed

### 2.4 Implementation Steps (Post-Verification)

**Step 2.4.1:** Determine correct fix via git history
```bash
# Search git history for function
git log -p --all -S "extract_treesitter_cfg"
git log -p --all -S "extract_cfg"

# Possible outcomes:
# A) Function was renamed → Update caller to new name
# B) Function was moved → Update import statement
# C) Function was deleted (no longer needed) → Remove caller
# D) Function never existed (typo) → Find correct function name
```

**Step 2.4.2:** Apply appropriate fix based on finding

**SCENARIO A: Function was renamed**
```python
# File: theauditor/ast_extractors/__init__.py:273

# BEFORE:
treesitter_impl.extract_treesitter_cfg(tree, self, language)

# AFTER:
treesitter_impl.extract_cfg(tree, self, language)  # Use new name
```

**SCENARIO B: Function was moved**
```python
# File: theauditor/ast_extractors/__init__.py (top of file)

# ADD IMPORT:
from theauditor.cfg_analyzer import extract_treesitter_cfg

# Line 273 (unchanged):
extract_treesitter_cfg(tree, self, language)
```

**SCENARIO C: Function no longer needed**
```python
# File: theauditor/ast_extractors/__init__.py:273

# REMOVE LINE:
# treesitter_impl.extract_treesitter_cfg(tree, self, language)

# ADD COMMENT:
# CFG extraction now handled by separate analyzer phase
```

**SCENARIO D: Find correct function**
```python
# Search codebase for similar function
grep -r "extract.*cfg" theauditor/ast_extractors/

# Update to correct function name
```

**Step 2.4.3:** Improve exception handling
```python
# File: theauditor/ast_extractors/__init__.py
# Around line 273

# BEFORE:
try:
    # ... extraction logic ...
    treesitter_impl.extract_treesitter_cfg(tree, self, language)
except Exception as e:
    # Silently returns empty dict
    logger.debug(f"Extraction failed: {e}")
    return {}

# AFTER:
try:
    # ... extraction logic ...
    if hasattr(treesitter_impl, 'extract_treesitter_cfg'):
        treesitter_impl.extract_treesitter_cfg(tree, self, language)
    else:
        logger.warning(f"extract_treesitter_cfg not available in {treesitter_impl}")
except SyntaxError as e:
    # Expected: Malformed Python files
    logger.debug(f"Syntax error in {file_path}: {e}")
    return {}
except AttributeError as e:
    # Unexpected: Missing functions (should not happen)
    logger.error(f"CRITICAL: Missing function in extractor: {e}")
    raise
except Exception as e:
    # Unexpected: Other errors
    logger.error(f"Extraction failed unexpectedly: {e}")
    raise
```

**Step 2.4.4:** Add database health check
```python
# NEW FILE: theauditor/utils/health_checks.py

def validate_index_results(db_path, expected_file_count):
    """Validate indexing produced expected results."""
    conn = sqlite3.connect(db_path)

    symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    if symbol_count == 0:
        raise HealthCheckError(
            f"CRITICAL: 0 symbols extracted from {file_count} files. Indexer likely failed."
        )

    if file_count > 0 and symbol_count < file_count:
        logger.warning(
            f"Only {symbol_count} symbols from {file_count} files. "
            f"Expected at least {file_count} symbols (1 per file minimum)."
        )
```

**Step 2.4.5:** Call health check after indexing
```python
# File: theauditor/commands/index.py
# At end of index command

# ADD:
from theauditor.utils.health_checks import validate_index_results

# After indexing completes:
validate_index_results(db_path, file_count)
```

### 2.5 Verification Steps (Post-Implementation)

**Test 2.5.1:** Function exists or caller updated
```bash
python -c "from theauditor.ast_extractors import treesitter_impl; print(hasattr(treesitter_impl, 'extract_treesitter_cfg'))"
# Expected: True OR caller updated to not use this function
```

**Test 2.5.2:** TheAuditor self-analysis works
```bash
cd ~/TheAuditor
rm -rf .pf/
aud index
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols"
# Expected: > 10,000 (not 0)
```

**Test 2.5.3:** Health check triggers on failure
```bash
# Simulate failure: Temporarily break extractor
# Run index
# Expected: Health check raises HealthCheckError instead of silent "CLEAN"
```

**Test 2.5.4:** Exception handling improved
```bash
# Create malformed Python file with syntax error
echo "def broken(" > test_broken.py
aud index
# Expected: Logs "Syntax error" but doesn't crash
# Database should have symbols from other files
```

**Test 2.5.5:** All projects index successfully
```bash
# Re-run indexing on all 6 projects
for project in plant project_anarchy PlantFlow PlantPro raicalc TheAuditor; do
    cd $project
    rm -rf .pf/
    aud index
    sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols" >> results.txt
done
# Expected: All projects have symbols > 0
```

### 2.6 Edge Cases & Failure Modes

**Edge 2.6.1:** Function exists but has different signature
- **Condition:** Function renamed with different parameters
- **Fix:** Update caller to match new signature
- **Mitigation:** Check function signature during verification

**Edge 2.6.2:** CFG extraction truly optional
- **Condition:** Some languages don't support CFG extraction
- **Fix:** Make call conditional based on language
- **Mitigation:** Add language check before calling

**Edge 2.6.3:** Multiple extractors call missing function
- **Condition:** Not just Python, but JavaScript too
- **Fix:** Fix all call sites
- **Mitigation:** Grep for all usages before implementing

### 2.7 Impact Assessment

**Immediate:**
- TheAuditor self-analysis works (0 → 15K symbols)
- Prevents future silent failures

**Downstream:**
- Can dogfood own tool (critical for quality)
- Improved error visibility for users

**Breaking Changes:**
- Exception handling stricter (may expose other bugs)

### 2.8 Reversion Plan

**Reversibility:** Fully reversible
```bash
git revert <commit_hash>
```

### 2.9 Estimated Effort

**Time Breakdown:**
- Verification phase: 1 hour (git history search, read 4 files)
- Determine correct fix: 30 minutes (analyze git history)
- Apply fix: 15 minutes (update function call)
- Improve exception handling: 45 minutes (refactor try-except)
- Add health check: 30 minutes (write validation)
- Testing: 1 hour (run on all 6 projects)

**Total:** 4 hours

**Confidence:** High (simple function restoration)

---

## PHASE 3: Fix PATTERN-001 - Disable TOCTOU Rule (P0)

### 3.1 Objective
Immediately disable false positive explosion from TOCTOU race condition detector.

### 3.2 Hypotheses to Verify

**Hypothesis 3.1:** TOCTOU rule in `async_concurrency_analyze.py` uses Cartesian join
- **Verification Method:** Read function `_check_toctou_race_conditions` lines 636-680
- **Expected Result:** SQL query with self-join on function_call_args

**Hypothesis 3.2:** Rule generates O(n²) findings
- **Verification Method:** Check PlantFlow database
- **Expected Result:** 415,800 race-condition findings from 9,679 function calls

**Hypothesis 3.3:** 99% are false positives
- **Verification Method:** Sample 100 random findings
- **Expected Result:** <5 true positives

### 3.3 Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/rules/node/async_concurrency_analyze.py:636-680` - TOCTOU detector
2. `theauditor/rules/orchestrator.py` - Rule registration/execution
3. `CLAUDE.md` - Rule metadata system documentation

**EXPECTED FINDINGS:**
- SQL query: `SELECT ... FROM function_call_args f1 JOIN function_call_args f2 ...`
- WHERE clause: `f2.line BETWEEN f1.line + 1 AND f1.line + 10`
- No object/variable grouping
- No confidence scoring

### 3.4 Implementation Steps (Post-Verification)

**Step 3.4.1:** IMMEDIATE FIX - Disable rule
```python
# File: theauditor/rules/node/async_concurrency_analyze.py
# Function: _check_toctou_race_conditions (lines 636-680)

# BEFORE:
def _check_toctou_race_conditions(context):
    cursor.execute("""
        SELECT f1.file, f1.line, f1.callee_function, f2.callee_function
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file
        WHERE f2.line BETWEEN f1.line + 1 AND f1.line + 10
    """)
    # ... 40 lines of processing ...
    return findings

# AFTER (TEMPORARY):
def _check_toctou_race_conditions(context):
    """
    DISABLED: This detector produces 99% false positives due to Cartesian join.

    Known issues:
    - Generates O(n²) findings (e.g., 9,679 calls → 415,800 findings)
    - No object/variable grouping (flags different objects as race conditions)
    - No confidence scoring
    - Marks all findings as CRITICAL incorrectly

    GitHub Issue: #XXX
    Status: Awaiting complete redesign with object-based analysis
    """
    logger.warning(
        "TOCTOU race condition detector is disabled due to 99%% false positive rate. "
        "See async_concurrency_analyze.py for details."
    )
    return []
```

**Step 3.4.2:** Add configuration flag
```python
# File: theauditor/rules/node/async_concurrency_analyze.py
# At top of file

# ADD:
ENABLE_TOCTOU_DETECTION = False  # Set True to enable (not recommended)

# In function:
def _check_toctou_race_conditions(context):
    if not ENABLE_TOCTOU_DETECTION:
        return []
    # ... rest of function ...
```

**Step 3.4.3:** Update METADATA to mark as experimental
```python
# File: theauditor/rules/node/async_concurrency_analyze.py
# METADATA section

METADATA = RuleMetadata(
    name="async_concurrency",
    category="concurrency",
    target_extensions=['.js', '.ts'],
    exclude_patterns=['test/', 'node_modules/'],
    requires_jsx_pass=False,
    experimental=True,  # ADD THIS
    known_issues=[  # ADD THIS
        "TOCTOU detector disabled: 99% false positive rate (O(n²) Cartesian join)"
    ]
)
```

**Step 3.4.4:** Document in CLAUDE.md
```markdown
# File: CLAUDE.md
# Add to "Known Limitations" section

### Disabled Rules

**async_concurrency_analyze.py - TOCTOU Detector (Disabled)**
- **Status:** Disabled in v1.2.1 due to false positive explosion
- **Issue:** Generates 415K+ false race condition findings per medium project
- **Root Cause:** Cartesian self-join on function_call_args without object grouping
- **Impact:** Would make output unusable (99% false positive rate)
- **Timeline:** Complete redesign required (8+ hours effort)
- **Workaround:** None - feature disabled until fixed
```

### 3.5 Verification Steps (Post-Implementation)

**Test 3.5.1:** Rule returns empty
```bash
python -c "
from theauditor.rules.node.async_concurrency_analyze import _check_toctou_race_conditions
result = _check_toctou_race_conditions(None)
assert result == [], f'Expected empty, got {len(result)} findings'
"
# Expected: Pass (returns empty list)
```

**Test 3.5.2:** PlantFlow produces reasonable findings
```bash
cd PlantFlow
rm -rf .pf/
aud detect-patterns
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE category='race-condition'"
# Expected: 0 (not 415,800)
```

**Test 3.5.3:** Total findings reasonable
```bash
cd PlantFlow
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated"
# Expected: < 10,000 (not 904,359)
```

**Test 3.5.4:** Warning logged
```bash
aud detect-patterns 2>&1 | grep "TOCTOU race condition detector is disabled"
# Expected: Warning appears in output
```

**Test 3.5.5:** Other concurrency checks still work
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE category='concurrency'"
# Expected: > 0 (other concurrency rules still active)
```

### 3.6 Edge Cases & Failure Modes

**Edge 3.6.1:** Users manually enable TOCTOU detection
- **Condition:** Set `ENABLE_TOCTOU_DETECTION = True`
- **Behavior:** Findings explosion returns
- **Mitigation:** Warning in docstring explaining consequences

**Edge 3.6.2:** Other rules in same file
- **Condition:** async_concurrency_analyze.py has other detection functions
- **Behavior:** Should still work
- **Mitigation:** Only disable _check_toctou_race_conditions, not whole file

### 3.7 Impact Assessment

**Immediate:**
- PlantFlow findings: 904K → <10K (usable output)
- PlantPro findings: 1.45M → <10K (usable output)
- plant findings: 3.5M → <10K (usable output)

**Downstream:**
- Users can actually read reports
- AI context windows not filled with garbage
- Tool becomes production-usable

**Breaking Changes:**
- TOCTOU detection unavailable
- Users relying on this feature will get 0 race condition findings

### 3.8 Reversion Plan

**Reversibility:** Fully reversible
```python
# Set flag to True
ENABLE_TOCTOU_DETECTION = True
```

### 3.9 Estimated Effort

**Time Breakdown:**
- Verification phase: 20 minutes (read 1 file, confirm algorithm)
- Disable rule: 10 minutes (return empty list)
- Add configuration: 10 minutes (add flag)
- Update metadata: 10 minutes (mark experimental)
- Documentation: 20 minutes (update CLAUDE.md)
- Testing: 30 minutes (run on 3 affected projects)

**Total:** 1.5 hours

**Confidence:** Absolute (trivial change)

---

## PHASE 4: Fix CACHE-001 - Memory Cache Failures (P1)

### 4.1 Objective
Debug and fix memory cache pre-load failures affecting performance.

### 4.2 Hypotheses to Verify

**Hypothesis 4.1:** Cache initialization fails due to memory limit
- **Verification Method:** Check cache init code for memory checks
- **Expected Result:** Find memory limit validation

**Hypothesis 4.2:** Database locking prevents cache load
- **Verification Method:** Check for concurrent database access
- **Expected Result:** Find race condition during cache initialization

**Hypothesis 4.3:** Cache logic has bug
- **Verification Method:** Read cache pre-load function
- **Expected Result:** Find logic error or exception

### 4.3 Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/taint/memory_cache.py` - Complete file
2. Cache initialization location (find via grep)
3. Pipeline cache invocation (where cache is created)

**EXPECTED FINDINGS:**
- Cache init function that checks available memory
- Pre-load logic that reads entire database
- Exception handler that logs "Failed to pre-load"

### 4.4 Implementation Steps (Post-Verification)

**Step 4.4.1:** Add extensive debug logging
```python
# File: theauditor/taint/memory_cache.py
# In cache initialization function

import psutil
import logging

logger = logging.getLogger(__name__)

def initialize_cache(db_path):
    logger.info("=== CACHE INITIALIZATION DEBUG ===")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Database exists: {os.path.exists(db_path)}")
    logger.info(f"Database size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB")

    mem = psutil.virtual_memory()
    logger.info(f"Available memory: {mem.available / 1024 / 1024:.2f} MB")
    logger.info(f"Memory percent used: {mem.percent}%")

    try:
        # Attempt cache load
        logger.info("Starting cache pre-load...")
        cache_data = preload_database(db_path)
        logger.info(f"Cache loaded: {len(cache_data)} entries")
        return cache_data
    except Exception as e:
        logger.error(f"Cache pre-load failed: {e}", exc_info=True)
        logger.error(f"Exception type: {type(e).__name__}")
        raise
```

**Step 4.4.2:** Fix based on root cause (TBD after verification)

**SCENARIO A: Memory limit too conservative**
```python
# Increase memory threshold
MEMORY_THRESHOLD = 0.95  # Use 95% of available (was 0.80?)
```

**SCENARIO B: Database locked**
```python
# Use read-only connection
conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
```

**SCENARIO C: Logic error in pre-load**
```python
# Fix specific bug (TBD based on verification)
```

**Step 4.4.3:** Add health check
```python
def validate_cache_loaded(cache):
    """Verify cache contains expected data."""
    if not cache:
        raise HealthCheckError("Cache is empty after pre-load")

    required_keys = ['symbols', 'function_call_args', 'assignments']
    for key in required_keys:
        if key not in cache:
            raise HealthCheckError(f"Cache missing required key: {key}")

    total_entries = sum(len(v) for v in cache.values())
    logger.info(f"Cache validated: {total_entries} total entries")
```

### 4.5 Verification Steps (Post-Implementation)

**Test 4.5.1:** Cache loads successfully
```bash
# Enable debug logging
export THEAUDITOR_DEBUG=1
aud full
grep "Cache loaded:" .pf/pipeline.log
# Expected: "Cache loaded: XXXXX entries" (not "Failed to pre-load")
```

**Test 4.5.2:** Performance improved
```bash
# Run twice on same project
rm -rf .pf/
time aud full  # First run (cold cache)
time aud full  # Second run (warm cache)
# Expected: Second run 480x faster (or at least significantly faster)
```

**Test 4.5.3:** Works on all project sizes
```bash
for project in raicalc project_anarchy plant; do
    cd $project
    rm -rf .pf/
    aud full 2>&1 | grep -i cache
done
# Expected: All show "Cache loaded" not "Failed to pre-load"
```

**Test 4.5.4:** Debug logs show root cause was fixed
```bash
# Check debug output identifies what was failing
cat .pf/pipeline.log | grep "CACHE INITIALIZATION DEBUG" -A 20
# Expected: Shows memory available, database size, successful load
```

### 4.6 Estimated Effort

**Time Breakdown:**
- Verification phase: 1 hour (read cache code, understand logic)
- Add debug logging: 30 minutes
- Reproduce failure locally: 1 hour
- Identify root cause: 1 hour (depends on complexity)
- Implement fix: 1 hour (depends on root cause)
- Testing: 1 hour (test on multiple projects)

**Total:** 5.5 hours

**Confidence:** Medium (depends on finding root cause)

---

## PHASE 5: Fix META-001 - Rule Metadata Propagation (P1)

### 5.1 Objective
Restore rule traceability by ensuring rule metadata propagates to findings.

### 5.2 Hypotheses to Verify

**Hypothesis 5.1:** Rules provide metadata but orchestrator doesn't pass it
- **Verification Method:** Read rules orchestrator execution logic
- **Expected Result:** Orchestrator calls rule.analyze() but doesn't store rule.name

**Hypothesis 5.2:** Database schema missing rule_id column
- **Verification Method:** Check findings_consolidated schema
- **Expected Result:** Schema has columns but not 'rule'

**Hypothesis 5.3:** StandardFinding → JSON conversion loses metadata
- **Verification Method:** Read findings storage logic
- **Expected Result:** Finding object has rule but JSON doesn't

### 5.3 Files to Read (Verification Phase)

**MANDATORY READS:**
1. `theauditor/rules/orchestrator.py` - Rule execution
2. `theauditor/indexer/database.py` - Findings storage
3. `theauditor/rules/base.py` - StandardFinding class

### 5.4 Implementation Steps (Post-Verification)

**Step 5.4.1:** Verify StandardFinding has rule field
```python
# File: theauditor/rules/base.py

@dataclass
class StandardFinding:
    file: str
    line: int
    severity: str
    category: str
    message: str
    rule: str = "unknown"  # Ensure this field exists
```

**Step 5.4.2:** Orchestrator passes rule name
```python
# File: theauditor/rules/orchestrator.py

for rule in rules:
    findings = rule.analyze(context)

    # ADD: Ensure each finding has rule name
    for finding in findings:
        if not finding.rule or finding.rule == "unknown":
            finding.rule = rule.METADATA.name  # Set from metadata
```

**Step 5.4.3:** Database stores rule field
```python
# File: theauditor/indexer/database.py

# Verify INSERT statement includes rule:
INSERT INTO findings_consolidated
(file, line, severity, category, message, tool, rule)  # Include 'rule'
VALUES (?, ?, ?, ?, ?, ?, ?)
```

**Step 5.4.4:** Add test
```python
# NEW FILE: tests/test_rule_metadata.py

def test_rule_metadata_propagates():
    """Verify rule name appears in findings."""
    from theauditor.rules.auth import jwt_analyze

    # Run rule on test project
    findings = jwt_analyze.analyze(test_context)

    # Check all findings have rule name
    assert all(f.rule == "jwt_analyze" for f in findings), \
        "All findings should have rule='jwt_analyze'"
```

### 5.5 Verification Steps (Post-Implementation)

**Test 5.5.1:** Database has rule names
```bash
aud detect-patterns
sqlite3 .pf/repo_index.db "SELECT DISTINCT rule FROM findings_consolidated WHERE tool='patterns'"
# Expected: Multiple rule names (not just "unknown")
```

**Test 5.5.2:** Specific rule traced
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE rule='jwt_analyze'"
# Expected: > 0 (findings from JWT rule)
```

**Test 5.5.3:** All findings have rules
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE rule='unknown' OR rule IS NULL"
# Expected: 0 (no unknown rules)
```

### 5.6 Estimated Effort

**Time Breakdown:**
- Verification: 1 hour
- Fix: 1 hour
- Testing: 1 hour

**Total:** 3 hours

---

## PHASE 6-12: Additional P1 and P2 Fixes

*(Abbreviated for space - follow same template format)*

### PHASE 6: Fix Phase Status Reporting (P1) - 3 hours
### PHASE 7: Fix SQL Query Misclassification (P1) - 2 hours
### PHASE 8: Add Health Check System (P1) - 4 hours
### PHASE 9: Add Validation Test Suite (P2) - 8 hours
### PHASE 10: Add Schema Migration System (P2) - 10 hours
### PHASE 11: Add Finding Deduplication (P2) - 3 hours
### PHASE 12: Update Documentation (P2) - 2 hours

---

## IMPLEMENTATION ORDER & DEPENDENCIES

### Critical Path (Must Complete in Order)

**Week 1 - P0 Fixes (Production Blockers):**
1. ✅ PHASE 3: Disable TOCTOU (1.5 hours) - **NO DEPENDENCIES, START IMMEDIATELY**
2. ✅ PHASE 1: Fix Taint Schema (4 hours) - **After PHASE 3**
3. ✅ PHASE 2: Fix Missing Function (4 hours) - **After PHASE 3**

**Week 1 Total:** 9.5 hours

**Week 2 - P1 Fixes (High Priority):**
4. ✅ PHASE 4: Fix Memory Cache (5.5 hours) - **After PHASE 1**
5. ✅ PHASE 5: Fix Rule Metadata (3 hours) - **After PHASE 3**
6. ✅ PHASE 6: Fix Phase Status (3 hours) - **After PHASE 1, 2**
7. ✅ PHASE 7: Fix SQL Patterns (2 hours) - **After PHASE 1**
8. ✅ PHASE 8: Add Health Checks (4 hours) - **After PHASE 2, 6**

**Week 2 Total:** 17.5 hours

**Week 3 - P2 Fixes (Nice to Have):**
9. ✅ PHASE 9: Validation Tests (8 hours) - **After ALL P0, P1**
10. ✅ PHASE 10: Schema Migrations (10 hours) - **After PHASE 1**
11. ✅ PHASE 11: Deduplication (3 hours) - **After PHASE 9**
12. ✅ PHASE 12: Documentation (2 hours) - **After ALL PHASES**

**Week 3 Total:** 23 hours

**GRAND TOTAL:** 50 hours (approximately 2 weeks of focused development)

---

## VALIDATION MATRIX

After each phase, run validation suite:

| Phase | Test Command | Success Criteria | Failure Action |
|-------|-------------|------------------|----------------|
| 1 | `aud taint-analyze` | sources > 0, sinks > 0 | Revert PHASE 1 |
| 2 | `aud index` on TheAuditor | symbols > 10,000 | Revert PHASE 2 |
| 3 | `aud detect-patterns` PlantFlow | findings < 10,000 | Revert PHASE 3 |
| 4 | `aud full` (2nd run) | 10x+ faster | Debug PHASE 4 |
| 5 | Query distinct rules | > 10 unique rules | Revert PHASE 5 |

**Final Integration Test:**
```bash
# Run on all 6 projects
for project in plant project_anarchy PlantFlow PlantPro raicalc TheAuditor; do
    cd $project
    rm -rf .pf/
    aud full
    # Validate:
    # - No errors in error.log
    # - Taint vulnerabilities > 0 (except raicalc)
    # - Pattern findings < 10,000
    # - All findings have rule names
    # - symbols > 0
done
```

---

## RISK ASSESSMENT

### High Risk Items

**RISK-1: Taint schema migration breaks existing databases**
- **Probability:** High
- **Impact:** Critical (users can't analyze existing projects)
- **Mitigation:** Auto-run migration on database open
- **Contingency:** Provide manual migration script

**RISK-2: Missing function fix breaks other languages**
- **Probability:** Medium
- **Impact:** High (JavaScript/TypeScript indexing fails)
- **Mitigation:** Test all language extractors after fix
- **Contingency:** Make function call conditional per language

**RISK-3: Cache fix introduces new bugs**
- **Probability:** Medium
- **Impact:** Medium (performance regression)
- **Mitigation:** Extensive testing before/after
- **Contingency:** Keep fallback to disk queries

### Medium Risk Items

**RISK-4: Disabling TOCTOU removes legitimate findings**
- **Probability:** Low
- **Impact:** Low (only <1% were true positives)
- **Mitigation:** Document known limitation
- **Contingency:** Allow users to enable via flag

---

## ROLLBACK PLAN

Each phase is independently reversible:

**PHASE 1 Rollback:**
```bash
git revert <commit_hash>
# Manually drop added columns if needed
```

**PHASE 2 Rollback:**
```bash
git revert <commit_hash>
# No database changes to revert
```

**PHASE 3 Rollback:**
```python
# Set ENABLE_TOCTOU_DETECTION = True
```

**Emergency Rollback (All Phases):**
```bash
git checkout main  # Or last known good commit
pip install -e .
```

---

## SUCCESS CRITERIA

### P0 Success (Production Ready)
- ✅ Taint analysis detects >0 vulnerabilities on project_anarchy
- ✅ TheAuditor self-analysis produces >10K symbols (not 0)
- ✅ PlantFlow produces <10K findings (not 904K)
- ✅ No "no such column" errors on any project
- ✅ Pipeline completes all 20 phases on all 6 projects

### P1 Success (High Quality)
- ✅ Memory cache loads successfully on 4/6 projects
- ✅ All findings have rule names (not "unknown")
- ✅ Phase status accurately reflects success/failure
- ✅ Health checks catch anomalous results

### P2 Success (Production Polished)
- ✅ Validation test suite passes 100%
- ✅ Schema migrations work on existing databases
- ✅ 0 duplicate findings in database
- ✅ Documentation reflects actual behavior

---

## CONFIRMATION OF UNDERSTANDING

**Objective:** Present atomic, numbered pre-implementation plan covering all dogfooding audit findings.

**Deliverable:** This document (PRE_IMPLEMENTATION_PLAN.md) with:
- 12 phases covering P0, P1, P2 fixes
- Verification steps for each hypothesis
- Implementation details with code examples
- Test plans with success criteria
- Risk assessment and rollback procedures
- Total effort: 50 hours over 2-3 weeks

**Status:** ✅ COMPLETE - Awaiting Architect Approval

**Next Step:** Architect reviews plan and approves/modifies before implementation begins.

**Confidence Level:** High - Plan based on verified audit findings, follows teamsop.md template, includes all necessary safeguards.

---

**End of Pre-Implementation Plan**
