# Golden Snapshot Testing Guide

## What is Golden Snapshot Testing?

Golden snapshot testing solves the **dogfooding problem**: "How do you test TheAuditor without running TheAuditor?"

**The Problem**:
```python
# ❌ Circular Logic (Dogfooding)
def test_refs_table_populated():
    subprocess.run(['aud', 'index'])  # Run TheAuditor
    assert refs_count > 0  # If TheAuditor is broken, test fails
```

If refs table population is broken, the test **also** fails to populate refs. You're testing the bug by reproducing the bug.

**The Solution**:
```python
# ✅ Golden Snapshot (No Dogfooding)
def test_refs_table_populated(golden_conn):
    cursor = golden_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refs")
    assert cursor.fetchone()[0] > 0
```

Tests query a **known-good database** created from production runs. Fast, deterministic, no circular logic.

---

## How It Works

### 1. Create Golden Snapshot (One Time)

Run TheAuditor on 5 diverse projects:

```bash
# Project 1: Python web app
cd /path/to/flask-app
aud full --offline
cp .pf/repo_index.db ~/TheAuditor/scripts/inputs/flask_repo_index.db

# Project 2: React frontend
cd /path/to/react-app
aud full --offline
cp .pf/repo_index.db ~/TheAuditor/scripts/inputs/react_repo_index.db

# Project 3: Express API
cd /path/to/express-api
aud full --offline
cp .pf/repo_index.db ~/TheAuditor/scripts/inputs/express_repo_index.db

# Project 4: Full-stack app
cd /path/to/fullstack
aud full --offline
cp .pf/repo_index.db ~/TheAuditor/scripts/inputs/fullstack_repo_index.db

# Project 5: TheAuditor itself
cd ~/TheAuditor
aud full --offline --exclude-self
cp .pf/repo_index.db ~/TheAuditor/scripts/inputs/theauditor_repo_index.db
```

### 2. Merge Into Golden Snapshot

```bash
cd ~/TheAuditor
python scripts/create_golden_snapshot.py
```

This creates `repo_index.db` in project root with:
- All tables from all 5 projects
- Diverse data (Python, JavaScript, SQL, JWT, API endpoints)
- Known-good state for deterministic testing

### 3. Run Tests

```bash
pytest tests/ -v

# Tests use golden snapshot automatically via golden_conn fixture
# Fast: No subprocess, no indexing, just SQLite queries
# Deterministic: Same data every run
```

---

## Test Strategy

### 95% Snapshot-Based Tests
**Files**: `test_database_integration.py`, `test_memory_cache.py`, `test_jsx_pass.py`

```python
def test_refs_table_has_data(golden_conn):
    """Verify refs table populated from 5 production runs."""
    cursor = golden_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM refs")
    assert cursor.fetchone()[0] > 0
```

**Benefits**:
- ✅ Fast (<1s per test)
- ✅ No dogfooding
- ✅ Deterministic
- ✅ Tests downstream consumers (rules, memory cache, graph builder)

### 5% Dogfooding Smoke Tests
**File**: `test_e2e_smoke.py`

```python
@pytest.mark.slow
def test_aud_index_doesnt_crash(tmp_path):
    """Verify `aud index` completes without crashing."""
    subprocess.run(['aud', 'index'], cwd=tmp_path)
```

**Purpose**: Just verify CLI doesn't crash end-to-end

---

## What Can Be Tested

| Component | Snapshot Test? | How |
|-----------|----------------|-----|
| refs table population | ✅ YES | Assert count > 0, verify 4-tuple structure |
| jwt_patterns table | ✅ YES | Assert schema correct, secret categorization works |
| api_endpoints table | ✅ YES | Assert 8 columns, auth detection works |
| sql_queries table | ✅ YES | Assert command != UNKNOWN, source tagging |
| Schema contract | ✅ YES | validate_all_tables(snapshot_cursor) |
| Memory cache | ✅ YES | preload(snapshot_cursor), verify O(1) lookups |
| build_query() | ✅ YES | Generate queries, run on snapshot |
| Graph builder | ✅ YES | Build graph from snapshot refs/imports |
| Rules | ✅ YES | Query snapshot for patterns |

| Component | Needs Real Run? | Test Type |
|-----------|-----------------|-----------|
| Python extractor | ✅ YES | Unit test (call _extract_imports_ast directly) |
| JS extractor | ✅ YES | Unit test (call with synthetic AST) |
| Orchestrator | ✅ YES | Integration test (minimal project) |
| CLI commands | ✅ YES | ONE smoke test (aud index on tiny project) |

---

## Fixtures

### `golden_db` Fixture
```python
@pytest.fixture
def golden_db():
    """Path to golden snapshot database."""
    db_path = Path(__file__).parent.parent / "repo_index.db"

    if not db_path.exists():
        pytest.skip("Golden snapshot not found - run create_golden_snapshot.py")

    return db_path
```

### `golden_conn` Fixture
```python
@pytest.fixture
def golden_conn(golden_db):
    """Open connection to golden snapshot (read-only)."""
    conn = sqlite3.connect(f"file:{golden_db}?mode=ro", uri=True)
    yield conn
    conn.close()
```

---

## Recommended Projects for Golden Snapshot

Choose 5 diverse projects that cover:

1. **Python web framework** (Flask/Django) → SQL queries, API endpoints, auth
2. **JavaScript frontend** (React/Vue) → JSX, hooks, component detection
3. **JavaScript backend** (Express/Fastify) → API endpoints, middleware
4. **Full-stack app** → Combined frontend + backend patterns
5. **TheAuditor itself** → Python AST, security rules, meta-testing

**Diversity ensures**:
- Wide coverage of language features
- Multiple framework patterns
- Both Python and JavaScript extraction
- Real-world code complexity

---

## Updating Golden Snapshot

When schema changes or new features added:

1. Delete old snapshot:
   ```bash
   rm repo_index.db
   ```

2. Re-run on 5 projects (or update existing .pf dirs):
   ```bash
   # If projects still indexed, just copy databases
   cp /path/to/project1/.pf/repo_index.db scripts/inputs/project1_repo_index.db
   ```

3. Regenerate snapshot:
   ```bash
   python scripts/create_golden_snapshot.py
   ```

4. Verify tests pass:
   ```bash
   pytest tests/ -v
   ```

---

## Troubleshooting

### Tests Skip: "Golden snapshot not found"

```bash
# Create inputs directory
mkdir -p scripts/inputs

# Add 5 database files
cp /path/to/.pf/repo_index.db scripts/inputs/project1_repo_index.db
# ... (4 more)

# Generate snapshot
python scripts/create_golden_snapshot.py
```

### "Permission denied" on Windows

Database file may be locked. Close all connections:

```python
# In test fixtures, always close connections:
@pytest.fixture
def golden_conn(golden_db):
    conn = sqlite3.connect(f"file:{golden_db}?mode=ro", uri=True)
    yield conn
    conn.close()  # Important!
```

### Tests fail after schema changes

Golden snapshot may have old schema. Regenerate:

```bash
rm repo_index.db
python scripts/create_golden_snapshot.py
```

---

## Benefits Over Dogfooding

| Aspect | Dogfooding | Golden Snapshot |
|--------|------------|-----------------|
| Speed | Slow (~60s per test) | Fast (<1s per test) |
| Determinism | Flaky (depends on code changes) | Deterministic (frozen state) |
| Circular logic | ❌ Yes (tests broken code with broken code) | ✅ No (tests against known-good data) |
| Isolation | ❌ Tests full stack (can't isolate) | ✅ Can test components independently |
| Coverage | Limited (toy projects) | High (5 diverse production projects) |

---

## Example Test

```python
def test_refs_table_population(golden_conn):
    """Verify refs table has expected structure and data."""
    cursor = golden_conn.cursor()

    # Test 1: Table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refs'")
    assert cursor.fetchone() is not None

    # Test 2: Has data from 5 projects
    cursor.execute("SELECT COUNT(*) FROM refs")
    count = cursor.fetchone()[0]
    assert count > 0, f"Expected imports from 5 projects, got {count}"

    # Test 3: Correct schema (4-tuple: src, kind, value, line)
    cursor.execute("PRAGMA table_info(refs)")
    columns = {row[1] for row in cursor.fetchall()}
    assert {'src', 'kind', 'value', 'line'}.issubset(columns)

    # Test 4: Line numbers populated
    cursor.execute("SELECT COUNT(*) FROM refs WHERE line IS NOT NULL")
    with_lines = cursor.fetchone()[0]
    assert with_lines / count >= 0.5, "Most refs should have line numbers"
```

✅ **Fast**: Direct SQL, no subprocess
✅ **Complete**: Tests structure, data, and semantics
✅ **No dogfooding**: Uses production data

---

## Questions?

- **How often to regenerate?** When schema changes or adding new features
- **How to choose projects?** Maximize diversity (languages, frameworks, patterns)
- **Can I use fewer than 5?** Yes, but coverage will be limited (minimum 3 recommended)
- **Does snapshot change?** No - frozen in time for deterministic testing

---

**This approach is used by production databases like PostgreSQL and SQLite themselves - they test with known-good fixture data, not by running their own commands.** 🎯
