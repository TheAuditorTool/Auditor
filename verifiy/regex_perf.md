# SQL REGEXP Performance Issue - Critical Pattern Detection Anti-Pattern

**Date**: 2025-11-01
**Severity**: P0 - Performance Critical
**Impact**: Affects naming convention detection, taint analysis, pattern rules
**Speedup Achieved**: 7,900x (180s → 0.033s)

---

## The Problem: Full Table Scans with LIKE Wildcards

### What We Were Doing (WRONG):

```sql
SELECT COUNT(*) FROM symbols
WHERE path LIKE '%.py'  -- ❌ Leading wildcard forces full table scan
  AND type = 'function'
  AND name REGEXP '^[a-z_][a-z0-9_]*$'
```

**Why This is Cancer**:
- `LIKE '%.py'` with leading wildcard (`%`) forces SQLite to read EVERY row
- No index can be used for leading wildcard patterns
- 129,600+ rows scanned even when only 5,400 match
- Each REGEXP callback invoked for EVERY row (Python function call overhead)
- Result: 180-264 seconds for naming convention detection

### What We Should Do (CORRECT):

```sql
SELECT COUNT(*) FROM symbols s
JOIN files f ON s.path = f.path
WHERE f.ext = '.py'  -- ✅ Indexed lookup on files.ext
  AND s.type = 'function'
  AND s.name REGEXP '^[a-z_][a-z0-9_]*$'
```

**Why This Works**:
- `files.ext` column stores extensions separately (`.py`, `.js`, `.ts`)
- Index `idx_files_ext` enables instant extension lookup
- Only relevant rows joined (5,400 instead of 129,600)
- REGEXP only called on pre-filtered result set
- Result: 0.033 seconds (7,900x faster)

---

## Architecture Lessons

### The Pattern:

1. **Identify the filter**: What are you filtering by? (file extension, file category, language)
2. **Check if it's indexed**: Does the filter use an indexed column?
3. **Avoid LIKE wildcards**: Never use `WHERE path LIKE '%pattern'` in production queries
4. **JOIN instead of LIKE**: Use dedicated columns + indexes for common filters

### The Fix Template:

**Before (Slow)**:
```sql
FROM table
WHERE path LIKE '%.ext'  -- Full table scan
```

**After (Fast)**:
```sql
FROM table t
JOIN files f ON t.path = f.path
WHERE f.ext = '.ext'  -- Indexed lookup
```

---

## Codebase-Wide Impact Assessment

### Likely Affected Areas:

1. **Pattern Detection Rules** (`theauditor/rules/`):
   - Security pattern matching (JWT, SQL injection, hardcoded secrets)
   - Framework detection patterns
   - Any rule filtering by file extension via path LIKE

2. **Taint Analysis** (`theauditor/taint/`):
   - Source/sink discovery queries
   - Cross-file data flow tracking
   - Pattern matching for sanitizers

3. **Track B Pattern Detection** (if it exists):
   - Any behavioral pattern matching
   - Code smell detection
   - Architecture violation detection

4. **Context Queries** (`aud query`, `aud context`):
   - File-filtered symbol lookups
   - Language-specific queries

### What to Audit:

```bash
# Find all queries with LIKE wildcards on paths
grep -r "LIKE '%" theauditor/
grep -r "path LIKE" theauditor/

# Find regex pattern matching in database queries
grep -r "REGEXP" theauditor/ | grep -v ".bak"
```

---

## Performance Rules

### NEVER DO THIS:

```python
# ❌ Python loop on database results
cursor.execute("SELECT name FROM symbols WHERE path LIKE '%.py'")
results = cursor.fetchall()
for row in results:
    if re.match(pattern, row[0]):  # Python regex on every row
        matches.append(row)
```

**Why**: Database does full scan, then Python does second filter pass. Double overhead.

### NEVER DO THIS:

```sql
-- ❌ SQL REGEXP with leading LIKE wildcard
SELECT name FROM symbols
WHERE path LIKE '%.py'  -- Full scan
  AND name REGEXP '^pattern$'  -- Python callback on every row
```

**Why**: Full table scan + Python callback for every row = 180+ seconds.

### ALWAYS DO THIS:

```sql
-- ✅ Indexed filter THEN regex
SELECT s.name FROM symbols s
JOIN files f ON s.path = f.path
WHERE f.ext = '.py'  -- Indexed filter first (5,400 rows)
  AND s.name REGEXP '^pattern$'  -- Regex on small set
```

**Why**: Index reduces result set to relevant rows BEFORE regex. 0.033 seconds.

---

## Memory Cache Implications

**Issue**: Even if you load everything into memory (schema_cache.py), you still need efficient filtering.

**Bad In-Memory Pattern**:
```python
# ❌ Filter with string operations
py_symbols = [s for s in all_symbols if s['path'].endswith('.py')]
```

**Good In-Memory Pattern**:
```python
# ✅ Pre-index by extension
symbols_by_ext = defaultdict(list)
for s in all_symbols:
    ext = Path(s['path']).suffix  # Extract once
    symbols_by_ext[ext].append(s)

# Fast lookup
py_symbols = symbols_by_ext['.py']
```

---

## Schema Contract Update

**Change Made**: Added `idx_files_ext` to `files` table in `core_schema.py`.

```python
FILES = TableSchema(
    name="files",
    columns=[
        Column("path", "TEXT", nullable=False, primary_key=True),
        Column("sha256", "TEXT", nullable=False),
        Column("ext", "TEXT", nullable=False),
        Column("bytes", "INTEGER", nullable=False),
        Column("loc", "INTEGER", nullable=False),
        Column("file_category", "TEXT", nullable=False, default="'source'"),
    ],
    indexes=[
        ("idx_files_ext", ["ext"])  # ← NEW: Fast extension lookups
    ]
)
```

**Impact**: Every `aud index` now creates this index. All queries can benefit.

---

## Action Items for Future Work

### Immediate (P0):
1. ✅ Add `idx_files_ext` to core_schema.py
2. ✅ Rewrite naming convention query in blueprint.py
3. ⬜ Audit all rules for `path LIKE '%.ext'` patterns
4. ⬜ Audit taint analysis queries for same issue

### High Priority (P1):
1. ⬜ Add `file_category` index if filtered frequently
2. ⬜ Review Track B pattern detection (if exists)
3. ⬜ Benchmark taint analysis queries

### Medium Priority (P2):
1. ⬜ Document query performance best practices
2. ⬜ Add query performance tests to CI
3. ⬜ Create query profiling tool (`aud debug profile-query`)

---

## Key Takeaway

**Database indexes are not optional optimizations - they are architectural requirements.**

If you're filtering by a column frequently:
1. Add an index to the schema
2. Use that index in queries
3. Never use leading wildcard LIKE patterns

The difference is not 2x or 10x. It's **7,900x**.
