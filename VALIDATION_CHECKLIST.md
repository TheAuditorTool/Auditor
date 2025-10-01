# Database-First Architecture Validation Checklist

**Date:** 2025-10-01
**Task:** Validate database-first refactor (eliminate redundant parsing, fix internal consumers)

---

## Pre-Test Setup

```bash
# Clean slate
rm -rf .pf

# Ensure no stale processes
pkill -f theauditor || true
```

---

## Phase 1: Database Integrity Validation (P0)

### Test 1.1: CHECK Constraints Exist

```bash
# Run indexer to create fresh database
.venv/Scripts/python -m theauditor.cli index

# Verify sql_queries CHECK constraint
sqlite3 .pf/repo_index.db "SELECT sql FROM sqlite_master WHERE name='sql_queries'" | grep "CHECK(command != 'UNKNOWN')"
# Expected: Should show CHECK constraint

# Verify function_call_args CHECK constraint
sqlite3 .pf/repo_index.db "SELECT sql FROM sqlite_master WHERE name='function_call_args'" | grep "CHECK(callee_function"
# Expected: Should show CHECK constraint
```

**Success Criteria:**
- ✅ Both CHECK constraints present in schema
- ✅ No errors during indexing

### Test 1.2: No UNKNOWN Garbage in sql_queries

```bash
# Count UNKNOWN commands
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM sql_queries WHERE command='UNKNOWN'"
# Expected: 0

# Verify only valid commands exist
sqlite3 .pf/repo_index.db "SELECT DISTINCT command FROM sql_queries ORDER BY command"
# Expected: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, etc. (no UNKNOWN)
```

**Success Criteria:**
- ✅ Zero UNKNOWN rows (down from 97.6% garbage)
- ✅ All commands are valid SQL keywords or JWT_ prefixed

### Test 1.3: Performance Indexes Exist

```bash
# Check all new indexes exist
sqlite3 .pf/repo_index.db ".indexes symbols" | grep idx_symbols_name
# Expected: idx_symbols_name

sqlite3 .pf/repo_index.db ".indexes assignments" | grep idx_assignments_target
# Expected: idx_assignments_target

sqlite3 .pf/repo_index.db ".indexes function_call_args" | grep idx_function_call_args_file_line
# Expected: idx_function_call_args_file_line
```

**Success Criteria:**
- ✅ All 3 new indexes exist
- ✅ Existing indexes still present

---

## Phase 2: JsonConfigExtractor Routing Validation (P0)

### Test 2.1: Only Processes Package Files

```bash
# Enable debug mode
export THEAUDITOR_DEBUG=1

# Re-run indexer
.venv/Scripts/python -m theauditor.cli index 2>&1 | grep -i "json.*config\|package\.json"

# Should ONLY show:
# - Processing package.json
# - Processing yarn.lock (if exists)
# - Processing pnpm-lock.yaml (if exists)

# Should NOT show:
# - Processing tsconfig.json
# - Processing .eslintrc.json
# - Processing babel.config.json
```

**Success Criteria:**
- ✅ JsonConfigExtractor only processes package.json, yarn.lock, pnpm-lock.yaml
- ✅ tsconfig.json and other .json files NOT processed by JsonConfigExtractor

### Test 2.2: package_configs Table Populated

```bash
# Check table has data
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM package_configs"
# Expected: >=1 (depending on project)

sqlite3 .pf/repo_index.db "SELECT file_path, package_name FROM package_configs"
# Expected: Shows actual package.json files from project
```

**Success Criteria:**
- ✅ Table populated with package.json data
- ✅ Monorepo packages (backend/, frontend/) all captured

---

## Phase 3: Internal Consumers Read Database (P1)

### Test 3.1: taint/core.py Reads from Database

```bash
# Delete frameworks.json to prove taint doesn't need it
rm -f .pf/raw/frameworks.json

# Run taint analysis
.venv/Scripts/python -m theauditor.cli taint-analyze

# Should complete successfully WITHOUT frameworks.json
```

**Success Criteria:**
- ✅ Taint analysis runs successfully
- ✅ No errors about missing frameworks.json
- ✅ Framework enhancement still works (reads from DB)

### Test 3.2: summary.py Reads from Database

```bash
# Delete frameworks.json
rm -f .pf/raw/frameworks.json

# Run summary
.venv/Scripts/python -m theauditor.cli summary

# Should complete successfully and show framework metrics
```

**Success Criteria:**
- ✅ Summary runs successfully
- ✅ Frameworks section populated (if any detected)
- ✅ No errors about missing frameworks.json

---

## Phase 4: Output Generation (detect-frameworks, deps)

### Test 4.1: detect-frameworks Reads DB and Writes Output

```bash
# Ensure database exists
test -f .pf/repo_index.db || .venv/Scripts/python -m theauditor.cli index

# Delete old output
rm -f .pf/raw/frameworks.json

# Run detect-frameworks
.venv/Scripts/python -m theauditor.cli detect-frameworks

# Check output generated
test -f .pf/raw/frameworks.json && echo "✅ Output generated" || echo "❌ Output missing"

# Check output content
cat .pf/raw/frameworks.json | jq '.[0].framework'
# Expected: Shows framework name
```

**Success Criteria:**
- ✅ No FrameworkDetector import (check with grep)
- ✅ Reads from database
- ✅ Generates .pf/raw/frameworks.json
- ✅ Displays human-readable table

### Test 4.2: deps.py Reads DB First, Falls Back to Files

```bash
# Test 1: With database (should use DB)
export THEAUDITOR_DEBUG=1
.venv/Scripts/python -m theauditor.cli deps 2>&1 | grep "Reading.*from database"
# Expected: "Reading npm dependencies from database"

# Test 2: Without database (should fallback to files)
mv .pf/repo_index.db .pf/repo_index.db.backup
.venv/Scripts/python -m theauditor.cli deps 2>&1 | grep "parsing.*from files"
# Expected: "parsing npm dependencies from files"

# Restore database
mv .pf/repo_index.db.backup .pf/repo_index.db

# Check output generated
test -f .pf/raw/deps.json && echo "✅ Output generated" || echo "❌ Output missing"
```

**Success Criteria:**
- ✅ Database path used when DB exists
- ✅ File parsing fallback works when DB missing
- ✅ Generates .pf/raw/deps.json in both cases
- ✅ Output format identical (backward compatible)

---

## Phase 5: Full Pipeline Validation

### Test 5.1: Run Complete Pipeline

```bash
# Clean slate
rm -rf .pf

# Run full pipeline
.venv/Scripts/python -m theauditor.cli full

# Check for errors
tail -100 .pf/pipeline.log | grep -i "error\|failed"
# Expected: No critical errors
```

**Success Criteria:**
- ✅ Pipeline completes without errors
- ✅ All phases run successfully
- ✅ No redundant parsing messages in debug logs

### Test 5.2: Verify No Circular Dependencies

```bash
# Check that internal code doesn't read /raw
grep -r "\.pf/raw/frameworks\.json" theauditor --include="*.py" | grep -v "commands/detect_frameworks\|commands/summary\.py:.*load_json"
# Expected: ONLY in detect_frameworks.py write, and summary.py old commented code

# Check that /raw is only written by commands
grep -r "\.pf/raw/" theauditor --include="*.py" | grep "open.*'w'\|json\.dump" | grep -v "commands/"
# Expected: Empty (only commands should write to /raw)
```

**Success Criteria:**
- ✅ No internal modules read from /raw
- ✅ Only command modules write to /raw
- ✅ Database is single source of truth

---

## Phase 6: Performance Verification

### Test 6.1: Rules Query Performance

```bash
# Run pattern detection (exercises all indexes)
time .venv/Scripts/python -m theauditor.cli detect-patterns

# Should complete faster than before (hard to measure without baseline)
# Check that queries don't timeout
```

**Success Criteria:**
- ✅ No query timeouts
- ✅ Pattern detection completes in reasonable time

### Test 6.2: No Redundant Parsing

```bash
# Enable debug and run full pipeline
export THEAUDITOR_DEBUG=1
.venv/Scripts/python -m theauditor.cli full 2>&1 | grep -c "Found package.json"
# Expected: Low count (once per package.json file during index, not repeated)

# Check that FrameworkDetector only runs once
.venv/Scripts/python -m theauditor.cli full 2>&1 | grep -c "FrameworkDetector"
# Expected: 1 (during index phase only)
```

**Success Criteria:**
- ✅ package.json parsed once per file
- ✅ FrameworkDetector runs once per pipeline
- ✅ No redundant manifest parsing

---

## Success Metrics (From nightmare_fuel.md)

| Metric | Before | Target | Query |
|--------|--------|--------|-------|
| SQL garbage ratio | 97.6% | 0% | `SELECT COUNT(*) FROM sql_queries WHERE command='UNKNOWN'` |
| Refs table rows | 0 | >100 | `SELECT COUNT(*) FROM refs` |
| Package configs | 0 | >=1 | `SELECT COUNT(*) FROM package_configs` |
| Frameworks table | Variable | >=1 | `SELECT COUNT(*) FROM frameworks` |

---

## Rollback Plan (If Tests Fail)

```bash
# Revert all changes
git checkout theauditor/indexer/database.py
git checkout theauditor/indexer/extractors/__init__.py
git checkout theauditor/indexer/__init__.py
git checkout theauditor/taint/core.py
git checkout theauditor/commands/summary.py
git checkout theauditor/commands/detect_frameworks.py
git checkout theauditor/deps.py

# Clean and rebuild
rm -rf .pf
.venv/Scripts/python -m theauditor.cli full
```

---

## Files Modified (7 files)

1. `theauditor/indexer/database.py` - CHECK constraints + indexes
2. `theauditor/indexer/extractors/__init__.py` - should_extract() enforcement
3. `theauditor/indexer/__init__.py` - Updated get_extractor() calls
4. `theauditor/taint/core.py` - DB read for frameworks
5. `theauditor/commands/summary.py` - DB read for frameworks
6. `theauditor/commands/detect_frameworks.py` - Complete rewrite (DB → output)
7. `theauditor/deps.py` - DB-first with file fallback

---

## Sign-Off

- [ ] All P0 tests passed
- [ ] All P1 tests passed
- [ ] Full pipeline runs successfully
- [ ] No circular dependencies
- [ ] Performance acceptable
- [ ] Success metrics achieved

**Tester:** _________________
**Date:** _________________
**Approved:** ✅ / ❌
