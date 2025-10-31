# CRITICAL: DO NOT RE-INDEX FIXTURES IN TESTS

## The Problem

**BAD (WASTEFUL) Pattern:**
```python
def index_fixtures(tmp_path: Path, fixtures: list[str]) -> Path:
    # Copies fixtures to temp dir
    # Runs full indexer (parse AST, extract symbols, write DB)
    # Returns temp database path

def test_something(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["fixture.py"])  # ❌ RE-INDEXES
    results = fetchall(db_path, "SELECT ...")
```

**Why This is CANCER:**
- If you have 50 tests calling `index_fixtures()`, you index the SAME files 50 times
- Each indexer run parses AST, extracts symbols, writes database
- Wastes time, wastes CPU, increases test runtime from seconds to minutes
- Creates 50 temporary databases instead of using 1 shared database

## The Solution

**Database Already Exists:**
```bash
cd /path/to/TheAuditor
aud full  # Indexes ALL fixtures ONCE to .pf/repo_index.db
```

**Tests Just Query:**
```python
# At top of test file
DB_PATH = Path(".pf/repo_index.db")

def test_something():  # ❌ NO tmp_path parameter
    db_path = DB_PATH  # ✅ Use existing database
    results = fetchall(db_path, "SELECT ...")
```

## Why This Works

1. `aud full` indexes TheAuditor repo INCLUDING all fixtures in `tests/fixtures/`
2. Fixtures are real Python/JS/TS files that get indexed like any other code
3. `.pf/repo_index.db` contains extracted data for ALL fixtures
4. Tests query the existing database, NO re-indexing needed

## File Filtering

If your test needs data from a specific fixture file:

**BAD (SQL LIKE clause):**
```python
# ❌ BANNED - SQL pattern matching violates schema normalization
query = "SELECT * FROM symbols WHERE file LIKE '%django_app.py%'"
```

**GOOD (Python filtering):**
```python
# ✅ CORRECT - Fetch ALL, filter in Python
all_symbols = fetchall(db_path, "SELECT name, path FROM symbols")
django_symbols = [s for s in all_symbols if 'django_app.py' in s[1]]
```

## Migration From Old Pattern

**Before:**
```python
def index_fixtures(tmp_path: Path, fixtures: list[str]) -> Path:
    # 40 lines of copying files and running indexer

def test_django_models(tmp_path: Path):
    db_path = index_fixtures(tmp_path, ["django_app.py"])
    models = fetchall(db_path, "SELECT * FROM python_orm_models")
```

**After:**
```python
# No index_fixtures function needed!

DB_PATH = Path(".pf/repo_index.db")

def test_django_models():  # No tmp_path
    db_path = DB_PATH
    models = fetchall(db_path, "SELECT * FROM python_orm_models")
```

## Multi-Fixture Comparisons

If you need to compare data from multiple fixtures:

**Before (2 separate databases):**
```python
def test_django_vs_sqlalchemy_parity(tmp_path: Path):
    django_db = index_fixtures(tmp_path / "django", ["django_app.py"])
    sqlalchemy_db = index_fixtures(tmp_path / "sqlalchemy", ["sqlalchemy_app.py"])

    django_count = fetchall(django_db, "SELECT COUNT(*) FROM python_orm_models")[0][0]
    sqlalchemy_count = fetchall(sqlalchemy_db, "SELECT COUNT(*) FROM python_orm_models")[0][0]
```

**After (1 database, Python filtering):**
```python
def test_django_vs_sqlalchemy_parity():
    db_path = DB_PATH

    all_models = fetchall(db_path, "SELECT model_name, file FROM python_orm_models")
    django_models = [m for m, f in all_models if 'django_app.py' in f]
    sqlalchemy_models = [m for m, f in all_models if 'sqlalchemy_app.py' in f]

    assert len(django_models) >= 10
    assert len(sqlalchemy_models) >= 5
```

## Performance Impact

**Old Pattern (50 tests):**
- Each test calls `index_fixtures()`
- Each call runs full indexer pipeline
- Total indexer runs: **50 times**
- Test runtime: **5-10 minutes**

**New Pattern (50 tests):**
- `aud full` runs ONCE before tests
- All tests query same database
- Total indexer runs: **1 time**
- Test runtime: **10-30 seconds**

## Enforcement

If you add `index_fixtures()` back or re-index in tests:
- Tests will be DELETED
- You will be publicly shamed
- Your commit will be reverted

**DO NOT FUCKING DO IT.**
