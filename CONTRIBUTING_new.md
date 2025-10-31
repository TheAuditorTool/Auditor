###

Contributing to TheAuditor

Thank you for your interest in contributing!

Contributions for TheAuditor are temporarily PAUSED.

We are currently in the process of setting up a new, formal legal entity to hold the project's IP. This is a necessary step to support our dual-licensing model (AGPL + Commercial).

During this legal transition, we cannot accept or merge ANY pull requests.

We will be implementing a formal Contributor License Agreement (CLA) bot shortly. Once that is active, we will happily review all contributions.

Please feel free to fork the repo and work on your changes, but we will not be able to merge them until our new legal structure is in place.

Thank you for your understanding.

###


# Contributing to TheAuditor

**Version 1.4.2-RC1** | Developer Guidelines & Best Practices

> Precision engineering for security analysis - strict standards ensure reliability

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment](#development-environment)
3. [Architecture Overview](#architecture-overview)
4. [Coding Standards](#coding-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Adding New Features](#adding-new-features)
7. [Pull Request Process](#pull-request-process)
8. [Code Review Checklist](#code-review-checklist)

---

## Getting Started

### Prerequisites

- **Python**: 3.11+ (3.12 recommended)
- **Git**: For version control and temporal analysis
- **Node.js**: 18+ (for JavaScript/TypeScript analysis)
- **SQLite**: 3.35+ (usually bundled with Python)
- **WSL/PowerShell 7** (Windows users)

### Quick Setup

```bash
# Clone repository
git clone https://github.com/yourusername/theauditor.git
cd theauditor

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev,linters]"

# Verify installation
aud --version
```

### Windows-Specific Setup

**Critical**: TheAuditor runs in WSL/PowerShell 7, not pure Linux

**Environment Notes**:
- Use `python`, NOT `python3`
- Use Windows paths: `C:\Users\...`, NOT `/mnt/c/Users/...`
- Use `.venv\Scripts\activate`, NOT `.venv/bin/activate`
- Forward slashes work in code: `C:/Users/...`

**PowerShell 7 Setup**:
```powershell
# Install PowerShell 7 (if needed)
winget install Microsoft.PowerShell

# Set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Activate venv
.venv\Scripts\activate
```

---

## Development Environment

### Project Structure

```
C:\TheAuditor\
├── theauditor\                # Main package
│   ├── __init__.py
│   ├── cli.py                 # CLI entry point
│   ├── commands\              # 40+ command modules
│   ├── indexer\               # Core indexing (Layers 1-4)
│   │   ├── orchestrator.py    # Layer 1
│   │   ├── extractors\        # Layer 2
│   │   ├── storage.py         # Layer 3
│   │   └── database\          # Layer 4
│   ├── rules\                 # Rule engine (52 rules)
│   ├── taint\                 # Taint analysis
│   ├── graph\                 # Graph analysis
│   ├── fce.py                 # Correlation engine
│   ├── insights\              # ML intelligence
│   ├── planning\              # Planning system
│   ├── utils\                 # Utilities (9 modules)
│   └── ast_extractors\        # Stateless AST logic
├── tests\                     # Test suite
│   ├── conftest.py            # Pytest fixtures
│   ├── fixtures\              # 20+ test projects
│   └── test_*.py              # Test modules
├── docs\                      # Documentation
├── .pf\                       # Working directory (gitignored)
├── pyproject.toml             # Package configuration
├── pytest.ini                 # Test configuration
└── CLAUDE.md                  # Critical architecture rules
```

### IDE Setup

**VS Code** (recommended):
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "editor.formatOnSave": true,
  "editor.rulers": [100]
}
```

**PyCharm**:
- Set Python interpreter to `.venv\Scripts\python.exe`
- Enable pytest as test runner
- Configure ruff and mypy as external tools

---

## Architecture Overview

### 4-Layer Pipeline

```
Layer 1: ORCHESTRATOR
  └─> File discovery, AST parsing, extractor selection

Layer 2: EXTRACTORS (12 languages)
  └─> Python, JavaScript, Terraform, Docker, Prisma, Rust, SQL, etc.

Layer 3: STORAGE (Handler dispatch)
  └─> 60+ handlers mapping data types to database operations

Layer 4: DATABASE (Multiple inheritance)
  └─> 90+ methods across 7 domain-specific mixins
```

**File References**:
- Layer 1: `theauditor\indexer\orchestrator.py` (740 lines)
- Layer 2: `theauditor\indexer\extractors\*.py` (5,075 lines total)
- Layer 3: `theauditor\indexer\storage.py` (1,200+ lines)
- Layer 4: `theauditor\indexer\database\__init__.py` + mixins (2,313 lines)

### Data Flow

```
Source Files → Orchestrator → Extractor → Storage → Database → repo_index.db (108 tables)
                                                                      ↓
                                                          Rule Engine, Taint Analysis, etc.
                                                                      ↓
                                                           findings_consolidated
```

**Critical Principle**: **Single Source of Truth**
- File paths: ONLY in Orchestrator
- Line numbers: ONLY in Implementation layer
- Data flow: ONE direction (never circular)

---

## Coding Standards

### ABSOLUTE RULES (from CLAUDE.md)

#### 1. ZERO FALLBACK POLICY

**MOST IMPORTANT RULE**: NO fallbacks, NO exceptions, NO "just in case" logic

**BANNED PATTERNS**:
```python
# ❌ CANCER - Database query fallback
cursor.execute("SELECT * FROM table WHERE name = ?", (normalized_name,))
result = cursor.fetchone()
if not result:
    cursor.execute("SELECT * FROM table WHERE name = ?", (original_name,))  # BANNED

# ❌ CANCER - Try/except fallback
try:
    data = load_from_database()
except Exception:
    data = load_from_json()  # BANNED

# ❌ CANCER - Table existence check
if 'function_call_args' in existing_tables:
    cursor.execute("SELECT ...")  # BANNED

# ❌ CANCER - Conditional fallback
result = method_a()
if not result:
    result = method_b()  # BANNED
```

**CORRECT PATTERN**:
```python
# ✅ CORRECT - Single query, hard fail if wrong
cursor.execute("SELECT * FROM symbols WHERE name = ?", (name,))
result = cursor.fetchone()
if not result:
    if debug:
        print(f"Symbol not found: {name}")
    continue  # Skip, DO NOT try alternative query
```

**Rationale**: Database regenerated fresh every run. If data missing, pipeline is broken and SHOULD crash immediately.

#### 2. NO REGEX FOR CODE ANALYSIS

**Rule**: Use AST parsing, NOT regex

**BANNED**:
```python
# ❌ BANNED - Regex on code
pattern = re.compile(r'password\s*=\s*["\'](.+)["\']')
matches = pattern.findall(content)
```

**CORRECT**:
```python
# ✅ CORRECT - AST parsing
cursor.execute("SELECT * FROM assignments WHERE target_var = 'password'")
```

**Exception**: Regex allowed ONLY for:
- Route patterns in web frameworks (`@app.route('/users/<id>')`)
- SQL DDL parsing (`CREATE TABLE users ...`)
- Configuration files (YAML/JSON parsing)

#### 3. NEVER USE SQLITE3 COMMAND DIRECTLY

**Rule**: Always use Python sqlite3 module

**BANNED**:
```bash
# ❌ BANNED - sqlite3 command not installed in WSL
sqlite3 database.db "SELECT ..."
```

**CORRECT**:
```bash
# ✅ CORRECT - Python with sqlite3 import
cd C:/Users/santa/Desktop/TheAuditor && .venv\Scripts\python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/path/to/database.db')
c = conn.cursor()
c.execute('SELECT ...')
for row in c.fetchall():
    print(row)
conn.close()
"
```

#### 4. NO EMOJIS IN PYTHON OUTPUT

**Rule**: Windows Command Prompt uses CP1252 encoding. Emojis cause `UnicodeEncodeError`.

**BANNED**:
```python
# ❌ BANNED - Will crash on Windows
print('Status: ✅ PASS')
print('Cross-file: ❌')
```

**CORRECT**:
```python
# ✅ CORRECT - Use plain ASCII
print('Status: PASS')
print('Cross-file: NO')
```

#### 5. WINDOWS PATH HANDLING

**Rule**: Use complete absolute Windows paths with drive letters

**Format**: `C:\Users\santa\Desktop\TheAuditor\file.py`

**BANNED**:
- `/mnt/c/Users/...` (WSL mount paths)
- `python3` (use `python`)
- `source .venv/bin/activate` (use `.venv\Scripts\activate`)

**CORRECT**:
```python
# ✅ CORRECT - Windows paths with forward slashes (work in WSL)
db_path = "C:/Users/santa/Desktop/TheAuditor/.pf/repo_index.db"
```

### Code Style

**PEP 8 Compliant** with these modifications:

#### Line Length
```python
# Maximum 100 characters (not 79)
MAX_LINE_LENGTH = 100
```

#### Imports
```python
# Standard library
import os
import sys
from typing import List, Dict, Optional

# Third-party
import click
import sqlite3

# Local
from theauditor.utils.logger import setup_logger
from theauditor.indexer.database import DatabaseManager
```

#### Naming Conventions
```python
# Classes: PascalCase
class DatabaseManager:
    pass

# Functions: snake_case
def analyze_taint_flow():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_FILE_SIZE = 2097152

# Private: _leading_underscore
def _internal_method():
    pass
```

#### Type Hints
```python
# Always use type hints for public APIs
def find_sql_injection(context: StandardRuleContext) -> List[StandardFinding]:
    findings: List[StandardFinding] = []
    # ...
    return findings
```

#### Docstrings
```python
def extract_symbols(tree: ast.AST, file_path: str) -> List[dict]:
    """Extract symbols (functions, classes, variables) from AST.

    Args:
        tree: Python AST tree
        file_path: Path to source file

    Returns:
        List of symbol dicts with keys: name, type, line, col

    Example:
        >>> tree = ast.parse("def foo(): pass")
        >>> extract_symbols(tree, "test.py")
        [{'name': 'foo', 'type': 'function', 'line': 1, 'col': 0}]
    """
    # Implementation
```

### Error Handling

**Pattern**: Use `@handle_exceptions` decorator

```python
import click
from theauditor.utils.decorators import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

@click.command()
@click.option('--workset', is_flag=True)
@handle_exceptions
def command_name(workset):
    """Command description."""
    logger.info("Starting command...")

    # NO try/except with fallbacks
    # Let exceptions propagate to decorator
```

**Exception to no-fallback rule**: Network operations can retry
```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_documentation(package: str) -> str:
    response = requests.get(f"https://pypi.org/pypi/{package}/json")
    response.raise_for_status()
    return response.json()
```

### Logging

**Pattern**: Use `setup_logger(__name__)`

```python
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

def analyze():
    logger.info("Starting analysis")
    logger.debug("Processing 1000 files")
    logger.warning("Missing configuration, using defaults")
    logger.error("Failed to parse file: %s", file_path)
    logger.critical("Database corrupted, aborting")
```

**Levels**:
- `DEBUG`: Verbose information for debugging
- `INFO`: Normal operation (default level)
- `WARNING`: Unexpected but handled situations
- `ERROR`: Errors that prevent specific operations
- `CRITICAL`: Fatal errors requiring immediate attention

---

## Testing Guidelines

### Test Organization

```
tests\
├── conftest.py                 # Pytest fixtures
├── fixtures\                   # Test projects (20+)
│   ├── python\
│   │   ├── async\
│   │   ├── django\
│   │   ├── flask\
│   │   └── ...
│   ├── node\
│   │   ├── express\
│   │   ├── react\
│   │   └── ...
│   └── infrastructure\
│       ├── terraform\
│       └── docker\
├── test_extractors.py          # Extractor tests
├── test_database.py            # Database tests
├── test_rules.py               # Rule tests
├── test_taint.py               # Taint analysis tests
└── test_e2e.py                 # End-to-end tests
```

### Writing Tests

**Naming Convention**:
```python
# File: test_module_name.py
# Class: TestClassName
# Method: test_specific_behavior

def test_python_extractor_extracts_functions():
    """Test that PythonExtractor extracts function definitions."""
    # Arrange
    code = "def foo(): pass"
    tree = ast.parse(code)

    # Act
    result = extractor.extract(file_info, code, tree)

    # Assert
    assert 'symbols' in result
    assert len(result['symbols']) == 1
    assert result['symbols'][0]['name'] == 'foo'
    assert result['symbols'][0]['type'] == 'function'
```

**Fixtures** (`conftest.py`):
```python
import pytest
import sqlite3
import tempfile

@pytest.fixture
def temp_db():
    """Create temporary database with schema."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    # Create schema
    # ...
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def golden_db():
    """Read-only golden database from production runs."""
    return "tests/golden_databases/repo_index.db"
```

**Golden Database Tests**:
```python
def test_rule_against_golden_database(golden_conn):
    """Test rule against golden database snapshot."""
    from theauditor.rules.security.sql_injection_analyze import find_sql_injection

    context = StandardRuleContext(db_path=golden_conn)
    findings = find_sql_injection(context)

    # Golden snapshots should have known vulnerabilities
    assert len(findings) >= 5
    assert any(f.severity == Severity.CRITICAL for f in findings)
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_extractors.py

# Specific test
pytest tests/test_extractors.py::test_python_extractor

# With coverage
pytest --cov=theauditor --cov-report=html

# Verbose
pytest -v

# Show print statements
pytest -s

# Parallel execution
pytest -n auto
```

### Test Markers

```python
import pytest

@pytest.mark.slow
def test_full_pipeline():
    """Mark slow tests (>5 seconds)."""
    pass

@pytest.mark.integration
def test_database_integration():
    """Mark integration tests."""
    pass

# Run only fast tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration
```

---

## Adding New Features

### Adding a New Language Extractor

**Steps**:

1. **Create Implementation Module** (`theauditor\ast_extractors\language_impl.py`):
```python
def extract_functions(tree, ast_parser):
    """Extract function definitions.

    Args:
        tree: AST tree
        ast_parser: ASTParser instance

    Returns:
        List of function dicts (NO file_path keys)
    """
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, FunctionDef):
            functions.append({
                'name': node.name,
                'line': node.lineno,
                'col': node.col_offset
            })
    return functions
```

2. **Create Extractor** (`theauditor\indexer\extractors\language.py`):
```python
from theauditor.indexer.extractors import BaseExtractor, register_extractor
from theauditor.ast_extractors import language_impl

@register_extractor
class LanguageExtractor(BaseExtractor):
    @property
    def supported_extensions(self):
        return ['.ext', '.ext2']

    def extract(self, file_info, content, tree):
        # Delegate to implementation
        functions = language_impl.extract_functions(tree, self.ast_parser)

        return {
            'symbols': functions,
            'imports': [],
            # ... other data
        }
```

3. **Add Schema Tables** (`theauditor\indexer\schemas\language_schema.py`):
```python
from theauditor.indexer.schemas.utils import TableSchema, ColumnSchema

LANGUAGE_SPECIFIC_TABLE = TableSchema(
    name="language_specific",
    columns=[
        ColumnSchema("file_path", "TEXT", nullable=False),
        ColumnSchema("line", "INTEGER", nullable=False),
        ColumnSchema("name", "TEXT", nullable=False),
    ],
    indexes=[
        IndexSchema(name="idx_language_specific_file", columns=["file_path"])
    ]
)
```

4. **Add Database Methods** (`theauditor\indexer\database\language_mixin.py`):
```python
class LanguageDatabaseMixin:
    def add_language_specific(self, file_path, line, name):
        self._add_generic_row('language_specific', {
            'file_path': file_path,
            'line': line,
            'name': name
        })
```

5. **Add Storage Handlers** (`theauditor\indexer\storage.py`):
```python
def _store_language_specific(self, file_path, items):
    for item in items:
        self.db_manager.add_language_specific(
            file_path=file_path,
            line=item['line'],
            name=item['name']
        )
```

6. **Write Tests** (`tests\test_language_extractor.py`):
```python
def test_language_extractor():
    code = "..."
    tree = parse_tree(code)
    extractor = LanguageExtractor()
    result = extractor.extract({'path': 'test.ext'}, code, tree)
    assert 'symbols' in result
```

### Adding a New Security Rule

**Steps**:

1. **Create Rule Module** (`theauditor\rules\security\my_rule_analyze.py`):
```python
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata, Severity, Confidence

# Declare metadata
METADATA = RuleMetadata(
    name="my_rule",
    category="security",
    target_extensions=['.py', '.js'],
    exclude_patterns=['test/', 'migrations/'],
    requires_jsx_pass=False
)

# Define function (MUST start with find_)
def find_my_vulnerability(context: StandardRuleContext) -> List[StandardFinding]:
    findings = []
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # Query database unconditionally (NO table checks!)
    cursor.execute("""
        SELECT file_path, line, arg_expr
        FROM function_call_args
        WHERE callee_function = 'dangerous_func'
    """)

    for file_path, line, arg_expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='my-rule-id',
            message=f'Dangerous call: {arg_expr}',
            file_path=file_path,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            category='security',
            cwe_id='CWE-XXX'
        ))

    conn.close()
    return findings
```

2. **Write Tests** (`tests\test_my_rule.py`):
```python
def test_my_rule_detects_vulnerability(temp_db):
    # Populate database with test data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO function_call_args (file_path, line, callee_function, arg_expr)
        VALUES ('test.py', 10, 'dangerous_func', 'user_input')
    """)
    conn.commit()
    conn.close()

    # Run rule
    context = StandardRuleContext(db_path=temp_db)
    findings = find_my_vulnerability(context)

    # Assert
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH
```

3. **NO REGISTRATION NEEDED** - Orchestrator auto-discovers `find_*` functions

### Adding a New CLI Command

**Steps**:

1. **Create Command Module** (`theauditor\commands\my_command.py`):
```python
import click
from theauditor.utils.decorators import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

@click.command()
@click.option('--workset', is_flag=True, help='Use workset files')
@click.option('--output', type=click.Path(), help='Output file')
@handle_exceptions
def my_command(workset, output):
    """Command description with examples.

    Examples:
        aud my-command --workset
        aud my-command --output results.json
    """
    logger.info("Starting my_command")

    # Implementation
    # ...

    logger.info("Completed successfully")
    return 0  # Exit code
```

2. **Register in CLI** (`theauditor\cli.py`):
```python
from theauditor.commands.my_command import my_command
cli.add_command(my_command)
```

3. **Write Tests** (`tests\test_my_command.py`):
```python
from click.testing import CliRunner
from theauditor.commands.my_command import my_command

def test_my_command_basic():
    runner = CliRunner()
    result = runner.invoke(my_command, [])
    assert result.exit_code == 0
    assert "Starting my_command" in result.output
```

---

## Pull Request Process

### Before Submitting

**Checklist**:
- [ ] Code follows ABSOLUTE RULES (zero fallback, no regex for code, etc.)
- [ ] All tests pass (`pytest`)
- [ ] Code formatted with Black (`black theauditor/ tests/`)
- [ ] Linted with Ruff (`ruff check --fix theauditor/ tests/`)
- [ ] Type-checked with MyPy (`mypy theauditor/`)
- [ ] No emojis in Python output
- [ ] Windows paths used correctly
- [ ] New features have tests (>=80% coverage)
- [ ] Documentation updated (if public API changes)

**Run Pre-commit Checks**:
```bash
# Format
black theauditor/ tests/

# Lint
ruff check --fix theauditor/ tests/

# Type check
mypy theauditor/

# Test
pytest --cov=theauditor

# Security
bandit -r theauditor/
```

### Commit Message Format

**Pattern**: `type(scope): description`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring (no behavior change)
- `test`: Test additions/modifications
- `docs`: Documentation changes
- `perf`: Performance improvements
- `chore`: Build/tooling changes

**Examples**:
```
feat(extractor): Add Rust extractor with tree-sitter
fix(taint): Handle None values in assignment tracking
refactor(database): Consolidate batch lists into generic system
test(rules): Add golden database tests for SQL injection
docs(architecture): Update 4-layer pipeline diagram
```

### PR Title & Description

**Title**: Same format as commit messages

**Description Template**:
```markdown
## Summary
Brief description of changes (1-2 sentences)

## Motivation
Why is this change needed?

## Changes
- Bullet list of specific changes
- Include file references

## Testing
- How was this tested?
- Include test cases added

## Breaking Changes
- List any breaking changes (or "None")

## Checklist
- [ ] Tests pass
- [ ] Code formatted
- [ ] Documentation updated
- [ ] No ABSOLUTE RULES violations
```

### Review Process

1. **Automated Checks**: GitHub Actions runs tests, linting, type checking
2. **Code Review**: Maintainer reviews code
3. **Approval**: At least 1 approval required
4. **Merge**: Squash and merge (clean history)

---

## Code Review Checklist

### Architecture

- [ ] Follows 4-layer pipeline pattern
- [ ] File paths ONLY in Orchestrator
- [ ] Line numbers ONLY in Implementation layer
- [ ] No circular dependencies

### ABSOLUTE RULES

- [ ] **ZERO FALLBACKS**: No try/except with alternatives
- [ ] **NO REGEX FOR CODE**: AST parsing only
- [ ] **DATABASE-FIRST**: Queries, not file reads
- [ ] **SCHEMA CONTRACT**: No table existence checks
- [ ] **HARD FAILURES**: Crashes expose bugs

### Code Quality

- [ ] Type hints for public APIs
- [ ] Docstrings for public functions
- [ ] Tests cover new code (>=80%)
- [ ] No performance regressions
- [ ] Memory usage reasonable

### Security

- [ ] No SQL injection vulnerabilities
- [ ] No command injection vulnerabilities
- [ ] No hardcoded secrets
- [ ] Input validation for user-provided data

### Platform Compatibility

- [ ] Windows paths handled correctly
- [ ] No emojis in Python output
- [ ] Works on Windows/Linux/macOS
- [ ] No platform-specific assumptions

---

## Development Workflow

### Feature Branch Workflow

```bash
# Update main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feat/my-feature

# Make changes
# ...

# Commit frequently
git add .
git commit -m "feat(scope): description"

# Push branch
git push -u origin feat/my-feature

# Open PR on GitHub
```

### Testing During Development

```bash
# Watch mode (auto-rerun on changes)
pytest-watch

# Test specific file
pytest tests/test_extractors.py

# Debug test
pytest -s -vv tests/test_extractors.py::test_specific

# Coverage report
pytest --cov=theauditor --cov-report=term-missing
```

### Debugging

**Database Inspection**:
```bash
# Open database
cd .pf
sqlite3 repo_index.db

# Show tables
.tables

# Show schema
.schema symbols

# Query data
SELECT name, file_path, line FROM symbols WHERE type='function' LIMIT 10;

# Exit
.quit
```

**Logging**:
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

logger = setup_logger(__name__)
logger.debug("Variable value: %s", var)
```

**Environment Variables**:
```bash
# Debug mode
set THEAUDITOR_DEBUG=1

# Taint analysis debug
set THEAUDITOR_TAINT_DEBUG=1

# CDK debug
set THEAUDITOR_CDK_DEBUG=1
```

---

## Performance Optimization

### Guidelines

1. **Database Queries**: Use indexes, avoid N+1 queries
2. **Batch Operations**: Batch database writes (5,000 rows)
3. **Memory**: Monitor memory usage, use generators for large datasets
4. **Caching**: Cache AST trees, avoid re-parsing
5. **Parallelization**: Use multiprocessing for independent operations

**Example**:
```python
# ❌ BAD - N+1 query
for symbol in symbols:
    cursor.execute("SELECT * FROM refs WHERE symbol_name = ?", (symbol,))

# ✅ GOOD - Single query with IN clause
symbol_names = [s['name'] for s in symbols]
placeholders = ','.join('?' * len(symbol_names))
cursor.execute(f"SELECT * FROM refs WHERE symbol_name IN ({placeholders})", symbol_names)
```

---

## Release Process

**Semantic Versioning**: `MAJOR.MINOR.PATCH-RC`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes
- **RC**: Release candidate

**Steps**:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Build distribution: `python -m build`
5. Tag release: `git tag v1.4.2-RC1`
6. Push tag: `git push origin v1.4.2-RC1`
7. Upload to PyPI: `twine upload dist/*`

---

## Resources

### Documentation
- [ARCHITECTURE_new.md](C:\Users\santa\Desktop\TheAuditor\ARCHITECTURE_new.md) - Complete system architecture
- [HOWTOUSE_new.md](C:\Users\santa\Desktop\TheAuditor\HOWTOUSE_new.md) - All 40 commands
- [CLAUDE.md](C:\Users\santa\Desktop\TheAuditor\CLAUDE.md) - Critical architecture rules

### External Resources
- [Python AST Documentation](https://docs.python.org/3/library/ast.html)
- [tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Click Documentation](https://click.palletsprojects.com/)

### Community
- GitHub Issues: https://github.com/yourusername/theauditor/issues
- Discussions: https://github.com/yourusername/theauditor/discussions

---

**Thank you for contributing to TheAuditor!**

Every contribution helps make software more secure. We appreciate your precision and attention to detail in maintaining TheAuditor's high standards.
