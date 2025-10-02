# PHASE 4 ATOMIC ACTION PLAN
## Sequential Fix List for TheAuditor Rules Refactor Completion

**Total Estimated Time**: 10-14 hours
**Priority**: P0 tasks MUST be completed before Phase 4 closure
**Status Tracking**: Mark ✅ after each task completion

---


# PART 1: P0 CRITICAL FIXES (8-10 hours)

## SECTION A: Column Mismatch Fixes (2.5 hours)

These fixes prevent SQL runtime errors when database has data.

---

### Task 1: Fix async_concurrency_analyze.py Wrong Table Reference (30 min)

**Issue**: Queries `target_var` from wrong table (`function_call_args` instead of `assignments`)

**File**: `theauditor/rules/python/async_concurrency_analyze.py`

**Step 1**: Find the problematic query
```bash
grep -n "SELECT.*target_var.*FROM function_call_args" theauditor/rules/python/async_concurrency_analyze.py
```

**Step 2**: Open file and locate the query (likely around line 200-300)

**Step 3**: Change this pattern:
```python
# WRONG:
cursor.execute("""
    SELECT file, line, target_var, source_expr
    FROM function_call_args
    WHERE ...
""")
```

**To this:**
```python
# CORRECT:
cursor.execute("""
    SELECT file, line, target_var, source_expr
    FROM assignments
    WHERE ...
""")
```

**Verify**:
```bash
# Should find 0 matches:
grep "SELECT.*target_var.*FROM function_call_args" theauditor/rules/python/async_concurrency_analyze.py

# Should find the fixed query:
grep "SELECT.*target_var.*FROM assignments" theauditor/rules/python/async_concurrency_analyze.py
```

✅ **Done?**

---

### Task 2: Fix symbols Table Column Name (Global Fix) (1 hour)

**Issue**: Rules may query `symbols.file` but schema has `symbols.path`

**Files to Check** (verify each one):
1. `theauditor/rules/python/async_concurrency_analyze.py`
2. `theauditor/rules/security/pii_analyze.py`
3. `theauditor/rules/security/websocket_analyze.py`
4. `theauditor/rules/typescript/type_safety_analyze.py`
5. `theauditor/rules/vue/component_analyze.py`

**Step 1**: Search for problematic pattern
```bash
cd C:\Users\santa\Desktop\TheAuditor
grep -rn "SELECT.*file.*FROM symbols" theauditor/rules/
```

**Step 2**: For EACH match found, apply this fix pattern:

```python
# WRONG:
SELECT file, symbol_type FROM symbols WHERE ...

# CORRECT (Option A - Use alias):
SELECT path AS file, type AS symbol_type FROM symbols WHERE ...

# CORRECT (Option B - Change variable names):
SELECT path, type FROM symbols WHERE ...
# Then rename variables: file -> path, symbol_type -> type
```

**Recommendation**: Use Option A (alias) to minimize code changes.

**Verify**:
```bash
# Should find 0 raw matches:
grep -rn "SELECT file FROM symbols" theauditor/rules/

# Aliases are OK:
grep -rn "SELECT path AS file FROM symbols" theauditor/rules/
```

✅ **Done?**

---

### Task 3: Fix function_call_args Column Names (1 hour)

**Issue**: Rules may query wrong column names in `function_call_args`

**Common Mistakes**:
- `name` → Should be `callee_function`
- `path` → Should be `file`
- `args_json` → Should be `argument_expr`

**Step 1**: Find all queries
```bash
grep -rn "SELECT.*name.*FROM function_call_args" theauditor/rules/
grep -rn "SELECT.*path.*FROM function_call_args" theauditor/rules/
```

**Step 2**: For each match, verify against schema:
```python
# CORRECT COLUMNS (from schema.py):
file, line, caller_function, callee_function, argument_index, argument_expr, param_name
```

**Step 3**: Fix pattern:
```python
# WRONG:
SELECT name, path FROM function_call_args

# CORRECT:
SELECT callee_function AS name, file FROM function_call_args
```

**Verify**:
```bash
# Check theauditor/indexer/schema.py for ground truth:
grep -A 20 "FUNCTION_CALL_ARGS = TableSchema" theauditor/indexer/schema.py
```

✅ **Done?**

---

## SECTION B: Invalid Table Reference (15 min)

### Task 4: Remove Pickle Table Reference

**Issue**: `python_deserialization_analyze.py` may reference non-existent `pickle` table

**File**: `theauditor/rules/python/python_deserialization_analyze.py`

**Step 1**: Search for problematic query
```bash
grep -n "FROM pickle" theauditor/rules/python/python_deserialization_analyze.py
```

**Expected Result**: Should find 0 matches (agent report may have been false positive)

**If matches found**:
```python
# Remove or comment out the query:
# cursor.execute("SELECT * FROM pickle ...")
```

**Actual Status**: Based on grep results, file contains only "pickle" as string patterns (pickle.load, pickle.loads), NOT as table name. **This issue is RESOLVED**.

✅ **Done?** (Already resolved - verify with grep)

---

## SECTION C: Add METADATA to 15 Rules (3.75 hours)

**Impact**: Without METADATA, rules run on ALL files instead of targeted filtering.

**Template to Copy** (from `jwt_analyze.py:32-46`):
```python
from theauditor.rules.base import RuleMetadata

METADATA = RuleMetadata(
    name="rule_name_here",
    category="category_here",
    target_extensions=['.py', '.js', '.ts'],  # Adjust per rule
    exclude_patterns=[
        'test/',
        'spec.',
        '__tests__',
        'demo/',
        'example/'
    ],
    requires_jsx_pass=False  # Set True for JSX syntax rules
)
```

---

### Task 5-12: Security Rules - Add METADATA (2 hours, 15 min each)

#### Task 5: crypto_analyze.py
**File**: `theauditor/rules/security/crypto_analyze.py`

**Step 1**: Open file, add after imports (around line 24):
```python
from theauditor.rules.base import RuleMetadata

METADATA = RuleMetadata(
    name="crypto_security",
    category="security",
    target_extensions=['.py', '.js', '.ts', '.php'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'demo/'],
    requires_jsx_pass=False
)
```

**Verify**:
```bash
grep -A 8 "^METADATA =" theauditor/rules/security/crypto_analyze.py
```

✅ **Done?**

---

#### Task 6: api_auth_analyze.py
**File**: `theauditor/rules/security/api_auth_analyze.py`

```python
METADATA = RuleMetadata(
    name="api_authentication",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 7: cors_analyze.py
**File**: `theauditor/rules/security/cors_analyze.py`

```python
METADATA = RuleMetadata(
    name="cors_security",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 8: input_validation_analyze.py
**File**: `theauditor/rules/security/input_validation_analyze.py`

```python
METADATA = RuleMetadata(
    name="input_validation",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 9: pii_analyze.py
**File**: `theauditor/rules/security/pii_analyze.py`

```python
METADATA = RuleMetadata(
    name="pii_exposure",
    category="security",
    target_extensions=['.py', '.js', '.ts', '.jsx', '.tsx'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'demo/'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 10: rate_limit_analyze.py
**File**: `theauditor/rules/security/rate_limit_analyze.py`

```python
METADATA = RuleMetadata(
    name="rate_limiting",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 11: sourcemap_analyze.py
**File**: `theauditor/rules/security/sourcemap_analyze.py`

```python
METADATA = RuleMetadata(
    name="sourcemap_exposure",
    category="security",
    target_extensions=['.js', '.js.map', '.ts.map'],
    exclude_patterns=['node_modules/', 'test/'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 12: websocket_analyze.py
**File**: `theauditor/rules/security/websocket_analyze.py`

```python
METADATA = RuleMetadata(
    name="websocket_security",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

### Task 13-18: Framework Rules - Add METADATA (1.5 hours, 15 min each)

#### Task 13: express_analyze.py
**File**: `theauditor/rules/frameworks/express_analyze.py`

**Step 1**: Add after line 15:
```python
from theauditor.rules.base import RuleMetadata

METADATA = RuleMetadata(
    name="express_security",
    category="frameworks",
    target_extensions=['.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=['frontend/', 'client/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 14: fastapi_analyze.py
**File**: `theauditor/rules/frameworks/fastapi_analyze.py`

```python
METADATA = RuleMetadata(
    name="fastapi_security",
    category="frameworks",
    target_extensions=['.py'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'migrations/'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 15: flask_analyze.py
**File**: `theauditor/rules/frameworks/flask_analyze.py`

```python
METADATA = RuleMetadata(
    name="flask_security",
    category="frameworks",
    target_extensions=['.py'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'migrations/'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 16: nextjs_analyze.py
**File**: `theauditor/rules/frameworks/nextjs_analyze.py`

```python
METADATA = RuleMetadata(
    name="nextjs_security",
    category="frameworks",
    target_extensions=['.js', '.jsx', '.ts', '.tsx'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 17: react_analyze.py
**File**: `theauditor/rules/frameworks/react_analyze.py`

```python
METADATA = RuleMetadata(
    name="react_security",
    category="frameworks",
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

#### Task 18: vue_analyze.py
**File**: `theauditor/rules/frameworks/vue_analyze.py`

```python
METADATA = RuleMetadata(
    name="vue_security",
    category="frameworks",
    target_extensions=['.vue', '.js', '.ts'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

### Task 19: Build Rules - Add METADATA (15 min)

#### Task 19: bundle_analyze.py
**File**: `theauditor/rules/dependency/bundle_analyze.py` (or similar path)

**Step 1**: Find exact location
```bash
find theauditor/rules -name "bundle_analyze.py"
```

**Step 2**: Add METADATA
```python
METADATA = RuleMetadata(
    name="bundle_analysis",
    category="performance",
    target_extensions=['.js', '.ts', '.json'],
    exclude_patterns=['node_modules/', 'test/'],
    requires_jsx_pass=False
)
```

✅ **Done?**

---

## SECTION D: Add Table Existence Checks to 11 Rules (5.5 hours, 30 min each)

**Impact**: Prevents crashes when database tables don't exist.

**Template Pattern** (from `jwt_analyze.py`):
```python
def _check_tables(cursor) -> Set[str]:
    """Check which tables exist in database."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN ('function_call_args', 'assignments', 'symbols', 'frameworks')
    """)
    return {row[0] for row in cursor.fetchall()}

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    findings = []
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # Check table existence FIRST
    existing_tables = _check_tables(cursor)

    if 'function_call_args' not in existing_tables:
        return findings  # Graceful degradation

    # Proceed with queries...
```

---

### Task 20-30: Add Table Checks to XSS & Security Rules

**Files to Fix** (verify each has table checks):

#### Task 20: async_concurrency_analyze.py (Python)
**Tables needed**: `function_call_args`, `assignments`, `symbols`

#### Task 21: dom_xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `assignments`, `symbols`

#### Task 22: express_xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `assignments`, `frameworks`

#### Task 23: nginx_analyze.py (Deployment)
**Tables needed**: `nginx_configs`, `config_files`

#### Task 24: react_xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `react_hooks`, `symbols`

#### Task 25: reactivity_analyze.py (Vue)
**Tables needed**: `vue_components`, `vue_hooks`, `assignments`

#### Task 26: runtime_issue_analyze.py (Node)
**Tables needed**: `function_call_args`, `symbols`

#### Task 27: template_xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `assignments`

#### Task 28: vue_xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `vue_directives`, `symbols`

#### Task 29: websocket_analyze.py (Security)
**Tables needed**: `function_call_args`, `symbols`, `api_endpoints`

#### Task 30: xss_analyze.py (XSS)
**Tables needed**: `function_call_args`, `assignments`, `symbols`, `frameworks`

**For EACH file above**:

**Step 1**: Open file

**Step 2**: Add helper function at module level (after imports):
```python
def _check_tables(cursor) -> Set[str]:
    """Check which tables exist in database."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN ('function_call_args', 'assignments', 'symbols', 'frameworks')
    """)
    return {row[0] for row in cursor.fetchall()}
```

**Step 3**: In main analyze function, add check at start:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # ADD THIS:
    existing_tables = _check_tables(cursor)

    # Before EACH query, check table exists:
    if 'function_call_args' not in existing_tables:
        return findings

    # Now safe to query...
```

**Verify** (for each file):
```bash
grep -n "_check_tables" theauditor/rules/xss/xss_analyze.py
grep -n "existing_tables" theauditor/rules/xss/xss_analyze.py
```

✅ **Done all 11?**

---

## SECTION E: Fix refs Table Population (2 hours)

**Issue**: `SELECT COUNT(*) FROM refs` returns 0 (import tracking broken)

**Root Cause Investigation Needed**

### Task 31: Debug refs Table Insertion (2 hours)

**Step 1**: Verify schema has refs table
```bash
grep -A 10 "REFS = TableSchema" theauditor/indexer/schema.py
```

**Expected**: Should show table with columns: `src`, `kind`, `value`

**Step 2**: Verify DatabaseManager has add_ref method
```bash
grep -n "def add_ref" theauditor/indexer/database.py
```

**Expected**: Should find method around line 80-100

**Step 3**: Check if add_ref is called in extractors
```bash
grep -rn "add_ref" theauditor/indexer/extractors/
```

**Expected**: Should find calls in `python.py` and `javascript.py`

**Step 4**: Add debug logging to verify calls
```python
# In theauditor/indexer/database.py, add_ref method:
def add_ref(self, src, kind, value):
    print(f"[DEBUG] add_ref called: src={src}, kind={kind}, value={value}")  # ADD THIS
    self.refs_batch.append({
        'src': src,
        'kind': kind,
        'value': value
    })
```

**Step 5**: Run indexer on small test project
```bash
cd C:\Users\santa\Desktop\TheAuditor
aud index --target fakeproj/project_anarchy
```

**Step 6**: Check debug output and database
```bash
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM refs"
sqlite3 .pf/repo_index.db "SELECT * FROM refs LIMIT 10"
```

**Step 7**: If still 0, check batch flush
```bash
grep -A 20 "def flush_all" theauditor/indexer/database.py
```

**Verify refs_batch is flushed**:
```python
# Should have:
if self.refs_batch:
    self.cursor.executemany(
        "INSERT OR IGNORE INTO refs (src, kind, value) VALUES (?, ?, ?)",
        [(r['src'], r['kind'], r['value']) for r in self.refs_batch]
    )
    self.refs_batch.clear()
```

**Step 8**: If issue found, apply fix and re-test

✅ **Done?** Verify: `sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM refs"` returns > 0

---

## SECTION F: Fix JWT Data Storage (2 hours)

**Issue**: JWT patterns stored in `sql_queries` table causing SQL injection false positives

### Task 32: Create jwt_patterns Table (1 hour)

**Step 1**: Add table to schema
**File**: `theauditor/indexer/schema.py`

**Find**: Search for where `sql_queries` table is defined (around line 240)

**Add after sql_queries definition**:
```python
JWT_PATTERNS = TableSchema(
    name="jwt_patterns",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("line_number", "INTEGER", nullable=False),
        Column("pattern_type", "TEXT", nullable=False),  # 'sign', 'verify', 'decode'
        Column("pattern_text", "TEXT"),
        Column("secret_source", "TEXT"),  # 'hardcoded', 'env', 'var', 'config'
        Column("algorithm", "TEXT"),
    ],
    indexes=[
        ("idx_jwt_file", ["file_path"]),
        ("idx_jwt_type", ["pattern_type"]),
        ("idx_jwt_secret_source", ["secret_source"]),
    ]
)
```

**Step 2**: Add to TABLES registry
**Find**: `TABLES = {` (around line 900)

**Add**:
```python
TABLES = {
    # ... existing tables ...
    'jwt_patterns': JWT_PATTERNS,
    # ... rest of tables ...
}
```

✅ **Done?**

---

### Task 33: Add DatabaseManager Method (30 min)

**File**: `theauditor/indexer/database.py`

**Step 1**: Initialize batch list in `__init__`
**Find**: Other batch initializations (around line 40-80)

**Add**:
```python
self.jwt_patterns_batch = []
```

**Step 2**: Add method after other add_* methods (around line 400)
```python
def add_jwt_pattern(self, file_path, line_number, pattern_type,
                    pattern_text, secret_source, algorithm=None):
    """Add JWT pattern detection."""
    self.jwt_patterns_batch.append({
        'file_path': file_path,
        'line_number': line_number,
        'pattern_type': pattern_type,
        'pattern_text': pattern_text,
        'secret_source': secret_source,
        'algorithm': algorithm
    })

    if len(self.jwt_patterns_batch) >= self.batch_size:
        self._flush_jwt_patterns()

def _flush_jwt_patterns(self):
    """Flush JWT patterns batch."""
    if not self.jwt_patterns_batch:
        return

    self.cursor.executemany("""
        INSERT OR REPLACE INTO jwt_patterns
        (file_path, line_number, pattern_type, pattern_text, secret_source, algorithm)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (p['file_path'], p['line_number'], p['pattern_type'],
         p['pattern_text'], p['secret_source'], p['algorithm'])
        for p in self.jwt_patterns_batch
    ])
    self.jwt_patterns_batch.clear()
```

**Step 3**: Add to flush_all method
**Find**: `def flush_all(self)` (around line 1450)

**Add**:
```python
def flush_all(self):
    """Flush all batches."""
    # ... existing flushes ...
    self._flush_jwt_patterns()  # ADD THIS
```

✅ **Done?**

---

### Task 34: Update Orchestrator to Route JWT Patterns (30 min)

**File**: `theauditor/indexer/__init__.py`

**Find**: Where JWT data is currently stored (search for "JWT" or check around line 615-625)

**Change from**:
```python
# WRONG - storing in sql_queries:
self.db_manager.add_sql_query(
    file_path, jwt['line'], jwt['text'], 'JWT_PATTERN', ...
)
```

**To**:
```python
# CORRECT - storing in jwt_patterns:
self.db_manager.add_jwt_pattern(
    file_path=file_path,
    line_number=jwt['line'],
    pattern_type=jwt['type'],  # 'sign', 'verify', or 'decode'
    pattern_text=jwt['text'],
    secret_source=jwt.get('secret_source', 'unknown'),
    algorithm=jwt.get('algorithm')
)
```

**Verify**:
```bash
grep -n "add_jwt_pattern" theauditor/indexer/__init__.py
```

✅ **Done?**

---

# PART 2: P1 HIGH PRIORITY FIXES (2 hours)

## SECTION G: Performance - Convert to Frozensets (45 min, 15 min each)

### Task 35: bundle_analyze.py - Use Frozensets

**Find pattern lists**:
```bash
grep -n "= \[" theauditor/rules/dependency/bundle_analyze.py
```

**Change from**:
```python
LARGE_LIBS = [
    'moment', 'lodash', 'jquery', 'axios'
]
```

**To**:
```python
LARGE_LIBS = frozenset([
    'moment', 'lodash', 'jquery', 'axios'
])
```

**Then update usage**:
```python
# Change from:
if lib in LARGE_LIBS:

# To (no change needed - frozenset supports 'in'):
if lib in LARGE_LIBS:
```

✅ **Done?**

---

### Task 36: reactivity_analyze.py - Use Frozensets
**Same pattern as Task 35**

✅ **Done?**

---

### Task 37: websocket_analyze.py - Use Frozensets
**Same pattern as Task 35**

✅ **Done?**

---

## SECTION H: Database-First Violation (1 hour)

### Task 38: Fix hardcoded_secret_analyze.py File I/O

**File**: `theauditor/rules/secrets/hardcoded_secret_analyze.py`

**Find file I/O**:
```bash
grep -n "open(" theauditor/rules/secrets/hardcoded_secret_analyze.py
grep -n "read()" theauditor/rules/secrets/hardcoded_secret_analyze.py
```

**Change from**:
```python
# WRONG - file I/O:
with open(file_path, 'r') as f:
    content = f.read()
```

**To**:
```python
# CORRECT - database query:
cursor.execute("""
    SELECT content FROM config_files WHERE path = ?
    UNION
    SELECT path FROM files WHERE path = ?
""", (file_path, file_path))
```

**Alternative**: If scanning for secrets in source files, query `files` table and reconstruct from symbols/assignments tables.

✅ **Done?**

---

# PART 3: TESTING & VALIDATION (2 hours)

## Task 39: Create Test Database (30 min)

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Clean previous test data
rm -rf .pf/

# Run indexer on test project
aud index --target fakeproj/project_anarchy

# Verify all tables populated
sqlite3 .pf/repo_index.db <<EOF
SELECT name, COUNT(*) as rows FROM (
    SELECT 'files' as name, COUNT(*) FROM files
    UNION ALL
    SELECT 'symbols', COUNT(*) FROM symbols
    UNION ALL
    SELECT 'refs', COUNT(*) FROM refs
    UNION ALL
    SELECT 'assignments', COUNT(*) FROM assignments
    UNION ALL
    SELECT 'function_call_args', COUNT(*) FROM function_call_args
    UNION ALL
    SELECT 'sql_queries', COUNT(*) FROM sql_queries
    UNION ALL
    SELECT 'jwt_patterns', COUNT(*) FROM jwt_patterns
) GROUP BY name;
.quit
EOF
```

**Expected**:
- `files`: > 50
- `symbols`: > 500
- `refs`: > 100 (CRITICAL - was 0 before)
- `assignments`: > 200
- `function_call_args`: > 300
- `sql_queries`: > 10
- `jwt_patterns`: > 0 (NEW table)

✅ **Done?**

---

## Task 40: Run Full Pipeline (30 min)

```bash
# Run complete analysis
aud full --target fakeproj/project_anarchy

# Check for SQL errors in logs
grep -i "error\|exception\|traceback" .pf/pipeline.log

# Verify no crashes
echo $?  # Should be 0
```

✅ **Done?**

---

## Task 41: Validate Schema Compliance (30 min)

```bash
# Run validation script
cd C:\Users\santa\Desktop\TheAuditor
python validate_rules_schema.py

# Expected output: 0 errors, exit code 0
echo $?
```

**If errors found**: Go back and fix specific issues reported

✅ **Done?**

---

## Task 42: Check Rule Compliance (30 min)

```bash
# Count rules with METADATA
grep -r "^METADATA =" theauditor/rules/ | wc -l

# Expected: 43+ (28 existing + 15 we added)
```

**Verify each category**:
```bash
# Security rules (should be 8):
grep -l "^METADATA =" theauditor/rules/security/*.py | wc -l

# Framework rules (should be 6):
grep -l "^METADATA =" theauditor/rules/frameworks/*.py | wc -l
```

✅ **Done?**

---

# COMPLETION CHECKLIST

## P0 Tasks (Must Complete)
- [ ] Task 1: Fix async_concurrency_analyze.py wrong table
- [ ] Task 2: Fix symbols table column names (5 files)
- [ ] Task 3: Fix function_call_args column names
- [ ] Task 4: Remove pickle table reference (verified already fixed)
- [ ] Tasks 5-12: Add METADATA to 8 security rules
- [ ] Tasks 13-18: Add METADATA to 6 framework rules
- [ ] Task 19: Add METADATA to bundle_analyze.py
- [ ] Tasks 20-30: Add table checks to 11 rules
- [ ] Task 31: Fix refs table population
- [ ] Tasks 32-34: Fix JWT data storage (create table, add methods, update orchestrator)

## P1 Tasks (Recommended)
- [ ] Tasks 35-37: Convert 3 rules to frozensets
- [ ] Task 38: Fix hardcoded_secret_analyze.py file I/O

## Testing
- [ ] Task 39: Create test database
- [ ] Task 40: Run full pipeline
- [ ] Task 41: Validate schema compliance
- [ ] Task 42: Check rule compliance

---

# SUCCESS CRITERIA

**Phase 4 is complete when ALL of these are true:**

1. ✅ `validate_rules_schema.py` returns exit code 0
2. ✅ `sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM refs"` returns > 0
3. ✅ `grep -r "^METADATA =" theauditor/rules/ | wc -l` returns 43+
4. ✅ `aud full` completes without SQL errors
5. ✅ All P0 tasks checked off above

---

# TROUBLESHOOTING

## If refs table still has 0 rows:
1. Check `python.py` extractor line 48-52 (AST import extraction)
2. Check `javascript.py` extractor import handling
3. Add debug prints to `add_ref()` method
4. Verify batch flush in `flush_all()`

## If SQL errors during aud full:
1. Check `.pf/pipeline.log` for exact error
2. Identify which rule is failing
3. Verify table/column names against schema.py
4. Add missing table existence check

## If validation script fails:
1. Read error output for specific file:line
2. Check column name against schema.py
3. Apply fix pattern from this document
4. Re-run validation

---

# ESTIMATED TIMELINE

**Day 1 (4 hours)**:
- Section A: Column mismatches (2.5h)
- Section B: Invalid table reference (0.25h)
- Section C: First 5 METADATA additions (1.25h)

**Day 2 (4 hours)**:
- Section C: Remaining 10 METADATA additions (2.5h)
- Section D: First 5 table checks (1.5h)

**Day 3 (4 hours)**:
- Section D: Remaining 6 table checks (3h)
- Section E: refs table debug (1h)

**Day 4 (2-4 hours)**:
- Section E: refs table fix completion (1h)
- Section F: JWT storage fix (2h)
- Part 2: P1 fixes (1h if time)

**Day 5 (2 hours)**:
- Part 3: Testing & validation (2h)

**Total: 14-16 hours** (allows buffer for debugging)

---

**FINAL NOTE**: Mark each task ✅ as you complete it. Commit after each section completion. Good luck! 🚀
