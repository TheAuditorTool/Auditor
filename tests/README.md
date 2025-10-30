# TheAuditor Test Suite

Comprehensive test infrastructure for TheAuditor's static analysis engine.

## Directory Structure

```
tests/
├── README.md                              # This file
├── conftest.py                            # Pytest configuration and shared fixtures
├── pytest.ini                             # Pytest settings (in repo root)
│
├── fixtures/                              # Test fixtures (isolated code samples)
│   ├── planning/                          # Planning workflow fixtures
│   ├── python/                            # Python framework fixtures
│   ├── typescript/                        # TypeScript fixtures
│   ├── cdk_test_project/                  # AWS CDK Python/TypeScript parity
│   ├── github_actions/                    # GitHub Actions workflow security
│   ├── github_actions_node/               # Node-specific GHA patterns
│   ├── object_literals/                   # JavaScript object literal extraction
│   └── taint/                             # Taint analysis patterns
│
├── integration/                           # Integration tests
│   └── test_object_literal_taint.py       # Object literal taint flow tests
│
├── terraform_test/                        # Terraform security test fixtures
│   ├── main.tf, outputs.tf, variables.tf  # Base Terraform config
│   └── vulnerable.tf                      # Intentionally vulnerable patterns
│
├── test_rules/                            # Security rule tests
│   ├── test_jwt_analyze.py                # JWT security patterns
│   ├── test_sql_injection_analyze.py      # SQL injection detection
│   └── test_xss_analyze.py                # XSS vulnerability detection
│
└── test_*.py                              # Unit and integration tests
```

## Test Categories

### 1. Extractor Tests

Test AST parsing and data extraction for various languages:

- **test_extractors.py** (38,818 lines): Core extractor tests for Python, JavaScript, TypeScript
- **test_python_framework_extraction.py** (4,577 lines): Flask, FastAPI, SQLAlchemy, Pydantic extraction
- **test_python_realworld_project.py** (3,294 lines): Comprehensive multi-framework fixture tests
- **test_python_ast_fallback.py** (11,118 lines): AST parser fallback behavior
- **test_rust_extraction.py** (4,019 lines): Rust language support
- **test_rust_extractor.py** (18,456 lines): Comprehensive Rust AST tests
- **test_jsx_pass.py** (6,217 lines): JSX preservation mode tests
- **test_github_actions.py** (23,145 lines): GitHub Actions workflow extraction

### 2. Analysis Tests

Test security analysis engines:

- **test_rules/test_jwt_analyze.py** (10,226 lines): JWT token security
- **test_rules/test_sql_injection_analyze.py** (15,191 lines): SQL injection detection
- **test_rules/test_xss_analyze.py** (11,890 lines): XSS vulnerability detection
- **test_taint_e2e.py** (7,718 lines): End-to-end taint flow analysis
- **integration/test_object_literal_taint.py** (6,040 lines): Dynamic dispatch taint flows

### 3. Infrastructure Tests

Test core TheAuditor infrastructure:

- **test_database_integration.py** (14,858 lines): Schema, indexing, query tests
- **test_graph_builder.py** (11,491 lines): Call graph construction
- **test_schema_contract.py** (4,586 lines): Database schema contract validation
- **test_memory_cache.py** (8,546 lines): Caching layer tests

### 4. Feature Tests

Test specific TheAuditor features:

- **test_cdk_analysis.py** (12,322 lines): AWS CDK security analysis
- **test_planning_manager.py** (9,489 lines): Planning system tests
- **test_planning_workflow.py** (14,670 lines): Planning workflow integration
- **test_edge_cases.py** (38,682 lines): Edge case handling
- **test_e2e_smoke.py** (6,348 lines): End-to-end smoke tests

**Total Test Code**: ~6,726 lines across 18 test files

## Running Tests

### Run All Tests

```bash
cd C:/Users/santa/Desktop/TheAuditor
python -m pytest tests/
```

### Run Specific Test File

```bash
python -m pytest tests/test_extractors.py
```

### Run Specific Test Function

```bash
python -m pytest tests/test_python_framework_extraction.py::test_sqlalchemy_models_extracted
```

### Run Tests by Marker

```bash
# Run only integration tests
python -m pytest -m integration

# Run all tests except slow ones
python -m pytest -m "not slow"
```

### Run with Coverage

```bash
python -m pytest --cov=theauditor --cov-report=html tests/
```

### Run with Verbose Output

```bash
python -m pytest -v tests/
```

## Pytest Configuration

**Location**: `pytest.ini` (repo root)

```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v"
```

## Shared Fixtures (conftest.py)

### temp_db
Creates temporary SQLite database for testing. Auto-cleanup after test.

```python
def test_example(temp_db):
    cursor = temp_db.cursor()
    cursor.execute("CREATE TABLE test (id INTEGER)")
```

### golden_db
Path to golden snapshot database from 5 production runs. Used for non-dogfooding tests.

```python
def test_with_golden(golden_db):
    # golden_db is a Path object
    conn = sqlite3.connect(golden_db)
```

### golden_conn
Open read-only connection to golden snapshot. Auto-closes after test.

```python
def test_with_golden_conn(golden_conn):
    cursor = golden_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM symbols")
```

### sample_project
Creates minimal test project structure in temporary directory.

```python
def test_with_project(sample_project):
    # sample_project is a Path to temp directory with app.py
    assert (sample_project / "app.py").exists()
```

## Test Fixtures (fixtures/)

All test fixtures are comprehensively documented with:
- **README.md**: Purpose, patterns tested, usage examples
- **spec.yaml**: SQL verification queries with expected results
- **Source code**: Actual code samples to index and analyze

See individual fixture READMEs for details:
- [fixtures/python/README.md](fixtures/python/README.md)
- [fixtures/planning/README.md](fixtures/planning/README.md)
- [fixtures/cdk_test_project/README.md](fixtures/cdk_test_project/README.md)
- etc.

## Terraform Test Fixtures (terraform_test/)

Intentionally vulnerable Terraform configurations for testing infrastructure-as-code security rules.

**Vulnerabilities**:
1. Public S3 bucket (`acl = "public-read"`)
2. Unencrypted database (`storage_encrypted = false`)
3. Hardcoded password in resource
4. IAM wildcard policy (`Action = "*", Resource = "*"`)
5. Security group open to world (`cidr_blocks = ["0.0.0.0/0"]`)

**Files**:
- `main.tf`: Base configuration
- `variables.tf`: Input variables
- `outputs.tf`: Output values
- `vulnerable.tf`: Vulnerable resources

## Writing New Tests

### Unit Test Template

```python
def test_feature_name(temp_db):
    """Test description."""
    # Arrange
    cursor = temp_db.cursor()
    cursor.execute("CREATE TABLE example (id INTEGER)")

    # Act
    result = function_under_test(temp_db)

    # Assert
    assert result == expected_value
```

### Fixture Test Template

```python
from pathlib import Path
from theauditor.indexer import IndexerOrchestrator

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "category"

def test_extraction_feature(tmp_path: Path):
    # Copy fixture to temp location
    project_root = tmp_path / "project"
    project_root.mkdir()
    shutil.copy(FIXTURE_ROOT / "example.py", project_root / "example.py")

    # Index fixture
    pf_dir = project_root / ".pf"
    pf_dir.mkdir()
    db_path = pf_dir / "repo_index.db"

    orchestrator = IndexerOrchestrator(project_root, str(db_path))
    orchestrator.db_manager.create_schema()
    orchestrator.index()

    # Query extracted data
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM table_name")
        results = cursor.fetchall()

    # Assert expectations
    assert len(results) > 0
```

### Integration Test Template

```python
@pytest.mark.integration
def test_end_to_end_workflow(tmp_path: Path):
    """Test full workflow from indexing to analysis."""
    # Setup
    project = create_test_project(tmp_path)

    # Index
    orchestrator = IndexerOrchestrator(project, db_path)
    orchestrator.index()

    # Analyze
    analyzer = Analyzer(db_path)
    findings = analyzer.analyze()

    # Assert
    assert len(findings) > 0
    assert findings[0].severity == "HIGH"
```

## Test Best Practices

### 1. Use Fixtures, Not Globals
```python
# BAD
DATABASE_PATH = "/tmp/test.db"  # Global state

# GOOD
def test_example(temp_db):  # Fixture provides clean database
    pass
```

### 2. Test One Thing Per Test
```python
# BAD
def test_everything():
    assert extraction_works()
    assert analysis_works()
    assert reporting_works()

# GOOD
def test_extraction():
    assert extraction_works()

def test_analysis():
    assert analysis_works()
```

### 3. Use Descriptive Test Names
```python
# BAD
def test_1():
    pass

# GOOD
def test_flask_routes_extracted_with_auth_decorators():
    pass
```

### 4. Avoid Dogfooding (Testing TheAuditor with TheAuditor)
```python
# BAD - Circular logic
def test_indexer():
    aud index  # If indexer is broken, test can't run
    assert results

# GOOD - Direct testing
def test_indexer():
    orchestrator = IndexerOrchestrator(...)
    orchestrator.index()
    # Query database directly
    assert cursor.fetchall()
```

### 5. Clean Up After Tests
```python
# BAD
def test_creates_files():
    Path("/tmp/test.txt").write_text("data")
    # No cleanup - pollutes filesystem

# GOOD
def test_creates_files(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("data")
    # tmp_path auto-cleans up
```

## Continuous Integration

Tests run automatically on:
- Every commit (via pre-commit hooks if configured)
- Every pull request
- Scheduled nightly runs

**Expected Runtime**:
- Fast tests (<1s each): ~100 tests
- Medium tests (1-5s each): ~50 tests
- Slow tests (>5s each): ~10 tests
- **Total**: ~15-30 minutes for full suite

## Troubleshooting

### Tests Fail with "Golden snapshot not found"
```bash
# Create golden snapshot from 5 production runs
python scripts/create_golden_snapshot.py
```

### Import Errors
```bash
# Ensure TheAuditor is installed in development mode
pip install -e .
```

### Database Schema Mismatch
```bash
# Delete old test databases
find tests/ -name "repo_index.db" -delete

# Rerun tests
python -m pytest tests/
```

### Windows Path Issues
All fixtures use forward slashes (`C:/Users/...`) for WSL compatibility.

## Test Coverage Goals

| Component | Target | Current |
|---|---|---|
| Extractors | 90% | ~85% |
| Analyzers | 85% | ~80% |
| Rules | 95% | ~90% |
| Database | 80% | ~75% |
| CLI | 70% | ~65% |

Run `pytest --cov=theauditor --cov-report=html` to see detailed coverage.

## Adding New Test Categories

When adding a new language or framework:

1. **Create fixture** in `tests/fixtures/<category>/`
2. **Add spec.yaml** with verification queries
3. **Write README.md** documenting patterns
4. **Create test file** `tests/test_<category>_extraction.py`
5. **Update this README** with new test category

## Related Documentation

- [FIXTURE_ASSESSMENT.md](../FIXTURE_ASSESSMENT.md) - Fixture status and completion
- [fixtures/python/README.md](fixtures/python/README.md) - Python fixture guide
- [fixtures/planning/README.md](fixtures/planning/README.md) - Planning fixture guide
- [CLAUDE.md](../CLAUDE.md) - Project architecture and rules

---

**Maintained by**: TheAuditor development team
**Last Updated**: 2025-10-31
**Test Suite Version**: 1.3.0-RC1
