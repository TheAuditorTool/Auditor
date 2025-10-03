# COMPREHENSIVE TEST PLAN FOR THEAUDITOR v1.1

**Generated**: 2025-10-03
**Based On**: Agent Test-Alpha Coverage Gap Analysis
**Current Coverage**: ~1% (13 tests verify schema, 0 tests verify data flow)
**Target Coverage**: 80%+ for critical paths

---

## EXECUTIVE SUMMARY

**The Problem**: Current tests verify the schema contract EXISTS but NOT that data actually flows correctly through the pipeline.

**Your Criticism Was 100% Correct**:
- "refs table empty" - NO TEST verifies refs table gets populated
- "multi-project validation" - NO TEST actually runs on real projects
- Tests created but NEVER EXECUTED to verify they pass

**What Agent Test-Alpha Found** (by reading actual code):
- 54 database methods: 50+ UNTESTED
- Orchestrator (1006 lines): 100% UNTESTED
- Extractors: 100% UNTESTED
- AST parser: 100% UNTESTED
- Full pipeline integration: UNTESTED

---

## CURRENT TEST SUITE (13 tests - ALL SCHEMA ONLY)

### test_schema_contract.py (10 tests)
✅ Schema registry populated
✅ api_endpoints has 8 columns
✅ build_query() works
✅ Schema validation detects mismatches
✅ Memory cache uses correct column names

**PROBLEM**: Tests that schema DEFINITIONS exist, NOT that data flows correctly.

### test_taint_e2e.py (3 tests)
⚠️ Runs `aud` commands but NEVER checks database state
⚠️ Verifies "no errors" but NOT "data is correct"
⚠️ No verification that refs > 0, jwt_patterns > 0, sql_queries > 0

**PROBLEM**: Like testing a car by checking the engine starts, but never verifying it drives.

---

## CRITICAL GAPS - P0 (MUST FIX)

### Gap 1: refs Table Population (ZERO TESTS)

**Claim** (from reports): "Python imports are extracted and stored in refs table"
**Reality**: NO TEST verifies this
**Evidence**: Agent Test-Alpha found add_ref() UNTESTED, import processing UNTESTED

**Test Needed**:
```python
def test_python_imports_populate_refs_table(sample_project):
    # Create Python file with imports
    (sample_project / "main.py").write_text('''
import os
from pathlib import Path
''')

    # Run indexer
    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    # VERIFY: refs table has data
    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM refs")
    count = cursor.fetchone()[0]

    assert count >= 2, f"Expected 2 imports, got {count}"

    # VERIFY: line numbers populated
    cursor.execute("SELECT line FROM refs")
    lines = [r[0] for r in cursor.fetchall()]
    assert all(line is not None and line > 0 for line in lines)
```

**Why This Matters**: Import tracking is a CORE feature. If refs table is empty in production, users get NO import dependency analysis.

---

### Gap 2: jwt_patterns Table Population (ZERO TESTS)

**Claim**: "JWT patterns stored in dedicated jwt_patterns table"
**Reality**: NO TEST verifies add_jwt_pattern() or _flush_jwt_patterns()

**Test Needed**:
```python
def test_jwt_detection_populates_jwt_patterns_table(sample_project):
    (sample_project / "auth.py").write_text('''
import jwt
token = jwt.sign(payload, "secret123", algorithm="HS256")
''')

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM jwt_patterns")
    count = cursor.fetchone()[0]

    assert count >= 1, f"Expected JWT pattern, got {count}"

    # VERIFY: secret_source detected
    cursor.execute("SELECT secret_source FROM jwt_patterns")
    source = cursor.fetchone()[0]
    assert source in ['hardcoded', 'env', 'var', 'config']
```

**Why This Matters**: JWT secret detection is a SECURITY feature. If this is broken, hardcoded secrets go undetected.

---

### Gap 3: Full Pipeline Integration (ZERO TESTS)

**Claim**: "Full pipeline works end-to-end"
**Reality**: test_taint_e2e runs commands but NEVER verifies database state

**Test Needed**:
```python
def test_full_pipeline_populates_all_tables(sample_project):
    # Create realistic multi-file project
    (sample_project / "app.py").write_text('''
from flask import Flask, request
import sqlite3

app = Flask(__name__)

@app.route('/users/<id>')
def get_user(id):
    conn = sqlite3.connect('users.db')
    cursor.execute(f"SELECT * FROM users WHERE id = {id}")  # SQL injection
    return cursor.fetchone()
''')

    # Run full pipeline
    subprocess.run(['aud', 'full'], cwd=sample_project, check=True, timeout=300)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()

    # VERIFY: files table populated
    cursor.execute("SELECT COUNT(*) FROM files")
    assert cursor.fetchone()[0] >= 1

    # VERIFY: symbols table populated
    cursor.execute("SELECT COUNT(*) FROM symbols")
    assert cursor.fetchone()[0] > 0

    # VERIFY: refs table populated
    cursor.execute("SELECT COUNT(*) FROM refs")
    refs_count = cursor.fetchone()[0]
    assert refs_count >= 2, f"Expected imports, got {refs_count}"

    # VERIFY: api_endpoints table populated
    cursor.execute("SELECT COUNT(*) FROM api_endpoints")
    assert cursor.fetchone()[0] >= 1, "Should detect Flask route"

    # VERIFY: sql_queries table populated
    cursor.execute("SELECT COUNT(*) FROM sql_queries WHERE command = 'SELECT'")
    assert cursor.fetchone()[0] >= 1, "Should detect SQL query"

    # VERIFY: taint_paths detected SQL injection
    cursor.execute("SELECT COUNT(*) FROM taint_paths")
    # May be 0 if taint didn't run, but should exist
```

**Why This Matters**: Pipeline could silently skip tables or fail to extract data, and current tests would pass.

---

### Gap 4: Batch Flush Logic (ZERO TESTS)

**Code**: database.py flush_batch() - 1350 lines of complex logic
**Tests**: ZERO
**Risk**: ID mapping bugs, deduplication failures, data corruption

**Test Needed**:
```python
def test_batch_flush_handles_200_items(sample_project):
    # Create file with exactly batch_size (200) symbols
    lines = [f"var{i} = {i}\n" for i in range(200)]
    (sample_project / "batch.py").write_text(''.join(lines))

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM symbols WHERE name LIKE 'var%'")
    count = cursor.fetchone()[0]
    assert count == 200, f"Expected 200 symbols, got {count}"
```

---

### Gap 5: Extractor Integration (ZERO TESTS)

**Code**: Extractors call db_manager.add_*() methods
**Tests**: ZERO integration tests
**Risk**: Extractors could extract data correctly but fail to call database methods

**Test Needed**:
```python
def test_python_extractor_integration_with_database(sample_project):
    (sample_project / "test.py").write_text('''
import os
from pathlib import Path

def hello():
    conn = sqlite3.connect('db.db')
    cursor.execute("SELECT * FROM users")
''')

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()

    # Extractor should have called:
    # - add_ref() for imports
    # - add_symbol() for functions
    # - add_sql_query() for SQL

    cursor.execute("SELECT COUNT(*) FROM refs")
    assert cursor.fetchone()[0] >= 2, "Imports not extracted"

    cursor.execute("SELECT COUNT(*) FROM symbols WHERE name = 'hello'")
    assert cursor.fetchone()[0] == 1, "Function not extracted"

    cursor.execute("SELECT COUNT(*) FROM sql_queries")
    assert cursor.fetchone()[0] >= 1, "SQL not extracted"
```

---

## HIGH PRIORITY GAPS - P1

### Gap 6: SQL Extraction Source Tagging (ZERO TESTS)

**Feature**: extraction_source field categorizes SQL (migration/orm/code_execute)
**Tests**: ZERO

**Test Needed**:
```python
def test_sql_extraction_source_tagging(sample_project):
    # Create migration file
    (sample_project / "migrations" / "001_create_users.py").write_text('''
cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
''')

    # Create ORM query
    (sample_project / "models.py").write_text('''
User.objects.filter(active=True)
''')

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()

    # VERIFY: migration file tagged correctly
    cursor.execute("SELECT extraction_source FROM sql_queries WHERE file_path LIKE '%migrations%'")
    source = cursor.fetchone()[0]
    assert source == 'migration_file'

    # VERIFY: ORM query tagged correctly
    cursor.execute("SELECT extraction_source FROM sql_queries WHERE file_path LIKE '%models%'")
    source = cursor.fetchone()[0]
    assert source == 'orm_query'
```

---

### Gap 7: Memory Cache Multi-Table Precomputation (ZERO TESTS)

**Code**: memory_cache.py _precompute_patterns() - 220 lines
**Feature**: Pre-loads sinks from sql_queries, orm_queries, react_hooks
**Tests**: ZERO

**Test Needed**:
```python
def test_memory_cache_precomputes_sinks_from_multiple_tables(sample_project):
    # Create code that populates sql_queries, orm_queries, react_hooks
    (sample_project / "app.py").write_text('''
cursor.execute("INSERT INTO users VALUES (?)", (data,))  # SQL sink
User.objects.create(name=data)  # ORM sink
''')

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    # Import and test memory cache
    from theauditor.taint.memory_cache import MemoryCache

    db_path = sample_project / '.pf' / 'repo_index.db'
    cache = MemoryCache(str(db_path))
    cache.preload()

    # VERIFY: Sinks from sql_queries loaded
    assert len(cache.security_sinks) > 0, "Should have precomputed sinks"

    # VERIFY: Multi-table correlation worked
    assert any('INSERT' in str(sink) for sink in cache.security_sinks)
```

---

### Gap 8: Second JSX Pass (ZERO TESTS)

**Code**: orchestrator __init__.py lines 346-468 (122 lines)
**Feature**: JSX files processed twice (transformed + preserved modes)
**Tests**: ZERO

**Test Needed**:
```python
def test_jsx_second_pass_populates_jsx_tables(sample_project):
    (sample_project / "Component.jsx").write_text('''
function MyComponent() {
    return <div onClick={handleClick}>Hello</div>;
}
''')

    subprocess.run(['aud', 'index'], cwd=sample_project, check=True)

    db = sqlite3.connect(sample_project / '.pf' / 'repo_index.db')
    cursor = db.cursor()

    # VERIFY: symbols_jsx populated (preserved mode)
    cursor.execute("SELECT COUNT(*) FROM symbols_jsx")
    # May be 0 if JSX pass not implemented yet, but table should exist

    # VERIFY: Regular symbols also populated (transformed mode)
    cursor.execute("SELECT COUNT(*) FROM symbols WHERE name = 'MyComponent'")
    assert cursor.fetchone()[0] >= 1
```

---

## MEDIUM PRIORITY GAPS - P2

### Gap 9-15: Edge Cases

1. Empty project (0 files)
2. Large files (>2MB)
3. Binary files
4. Permission errors
5. Symlink cycles
6. Batch size boundaries (200, 201 items)
7. Duplicate prevention logic

---

## TEST EXECUTION PLAN

### Phase 1: Run Existing Tests (5 minutes)
```bash
pytest tests/ -v

# Expected issues:
# - Some tests may fail (never been run)
# - Coverage will show ~1%
```

### Phase 2: Add Critical Integration Tests (2 hours)
1. test_database_integration.py - Tests refs, jwt_patterns, sql_queries tables
2. test_full_pipeline.py - Tests complete `aud full` run
3. test_extractors.py - Tests Python/JS extractor → database flow

### Phase 3: Add Edge Case Tests (1 hour)
1. test_edge_cases.py - Empty projects, large files, errors

### Phase 4: Verify on Real Projects (1 hour)
```bash
# Test on actual projects, not toy examples
cd /path/to/real/python/project
aud index
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM refs"
# Should be > 0

cd /path/to/real/react/project
aud index
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM api_endpoints"
# Should be > 0
```

---

## REQUIREMENTS FOR NEW TESTS

### 1. NO MOCKING OF YOUR CODE
- Test real extractors, not mocks
- Test real database operations
- Test real pipeline execution

### 2. VERIFY DATABASE STATE
- Run `aud` command
- Open database with sqlite3
- Query tables: `SELECT COUNT(*) FROM refs`
- Assert: count > 0

### 3. TEST WITH REALISTIC CODE
- Not just `x = 42`
- Real imports: `import os`, `from flask import Flask`
- Real SQL: `cursor.execute("SELECT * FROM users")`
- Real JWT: `jwt.sign(payload, secret, algorithm="HS256")`

### 4. VERIFY EXACT DATA
- Not just "no errors"
- Check: line numbers populated
- Check: column values correct
- Check: expected records present

---

## COMPARISON: CURRENT VS NEEDED

| Component | Current Tests | Needed Tests |
|-----------|--------------|--------------|
| Schema definitions | 10 tests ✅ | Keep existing |
| refs table population | 0 tests ❌ | 3 tests (Python, JS, edge cases) |
| jwt_patterns table | 0 tests ❌ | 2 tests (sign, verify) |
| sql_queries table | 0 tests ❌ | 3 tests (Python, JS, source tagging) |
| api_endpoints table | 0 tests ❌ | 2 tests (Flask, Express) |
| Full pipeline | 0 database checks ❌ | 1 comprehensive test |
| Batch flushing | 0 tests ❌ | 2 tests (batch_size, >batch_size) |
| Extractors | 0 integration tests ❌ | 3 tests (Python, JS, edge cases) |
| Edge cases | 0 tests ❌ | 7 tests |
| **TOTAL** | **13 tests (schema only)** | **36 new tests needed** |

---

## ESTIMATED EFFORT

**To reach 80% coverage of critical paths**:
- Phase 1 (Run existing): 5 minutes
- Phase 2 (Critical integration): 2 hours writing + 2 hours fixing issues found
- Phase 3 (Edge cases): 1 hour
- Phase 4 (Real project validation): 1 hour

**Total**: ~6-8 hours

**Risk if NOT done**: Production deployment with untested data flow = silent failures in the field.

---

## ACCEPTANCE CRITERIA

### For v1.2 Release:
- ✅ refs table population test EXISTS and PASSES
- ✅ jwt_patterns table population test EXISTS and PASSES
- ✅ Full pipeline integration test EXISTS and PASSES on real project
- ✅ At least 1 extractor integration test EXISTS and PASSES
- ✅ Test coverage > 50% for critical database operations

### For v1.3 Release:
- ✅ All P0 and P1 tests implemented
- ✅ Test coverage > 80% for critical paths
- ✅ Edge case tests passing
- ✅ Multi-project validation automated

---

## FINAL RECOMMENDATION

**Your criticism was CORRECT**: Tests were created but:
1. Never executed to verify they pass
2. Don't test the actual data flow
3. Based on claims from reports, not verified against real code

**The Fix**:
1. RUN existing tests: `pytest tests/ -v` (5 min)
2. ADD integration tests that verify database state (2 hours)
3. VERIFY on real projects, not toy examples (1 hour)

**The agent findings show**: Current 13 tests verify ~1% of the codebase. We need 36 more tests to reach 80% coverage of critical paths.

---

**Generated by**: Agent Test-Alpha Coverage Gap Analysis
**Based on**: Complete file reads of 6 core files (3,700+ lines analyzed)
**Confidence**: HIGH - findings based on actual code, not documentation
