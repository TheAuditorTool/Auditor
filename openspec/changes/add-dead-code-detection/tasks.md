# Implementation Tasks: Dead Code Detection

**Change ID**: `add-dead-code-detection`
**Team Protocol**: SOP v4.20 (Architect-Auditor-Coder Workflow)
**Report Template**: Template C-4.20 (MANDATORY after each phase)

---

## Important Notes

### Reporting Requirements (SOP v4.20)

After **EACH PHASE**, the Coder MUST submit a report using **Template C-4.20** to the Lead Auditor containing:

1. **Verification Phase Report** (what assumptions were tested)
2. **Deep Root Cause Analysis** (why this code is needed)
3. **Implementation Details & Rationale** (what was implemented, why)
4. **Edge Case & Failure Mode Analysis** (what could go wrong)
5. **Post-Implementation Integrity Audit** (re-read files, confirm correctness)
6. **Impact, Reversion, & Testing** (what changed, how to revert, tests run)
7. **Confirmation of Understanding** (summary + confidence level)

**DO NOT PROCEED** to the next phase until Lead Auditor approves the current phase report.

### Prohibited Actions (per CLAUDE.md)

- ❌ **NO FALLBACKS**: Do not write `try/except` with fallback logic
- ❌ **NO REGEX**: Do not use regex on file content (database queries only)
- ❌ **NO TABLE CHECKS**: Do not check if tables exist (schema contract guarantees)
- ❌ **NO MIGRATIONS**: Database is regenerated fresh every run
- ❌ **NO GIT COMMITS**: with "Co-Authored-By: Claude" (absolute rule)

---

## Phase 0: Verification (REQUIRED FIRST)

**Objective**: Verify all hypotheses about the codebase BEFORE writing code.

**SOP Requirement**: "The Coder MUST first perform a Verification Phase. You must explicitly list your initial hypotheses and then present the evidence from the code that confirms or refutes them."

### Hypothesis 1: CLI Command Registration Pattern

**Hypothesis**: CLI commands are imported around lines 249-273 in `cli.py` and registered around lines 300-352.

**Verification Steps**:
```bash
# Step 1: Read cli.py to find import section
.venv/Scripts/python.exe -c "
with open('theauditor/cli.py', 'r') as f:
    lines = f.readlines()
    for i in range(240, 280):
        print(f'{i+1:3d}: {lines[i]}', end='')
"

# Step 2: Find registration section
.venv/Scripts/python.exe -c "
with open('theauditor/cli.py', 'r') as f:
    lines = f.readlines()
    for i in range(290, 360):
        print(f'{i+1:3d}: {lines[i]}', end='')
"
```

**Expected Evidence**:
- Import lines should have pattern: `from theauditor.commands.X import Y`
- Registration lines should have pattern: `cli.add_command(Y)`

**Document Result**:
```
✅ CONFIRMED: Imports at lines 249-296
✅ CONFIRMED: Registrations at lines 300-352
OR
❌ DISCREPANCY: Imports actually at lines 260-310 (update tasks accordingly)
```

### Hypothesis 2: Graph Analyzer Isolated Node Detection

**Hypothesis**: `analyzer.py:291-296` counts isolated nodes but doesn't list them.

**Verification Steps**:
```bash
# Read exact code at lines 291-296
.venv/Scripts/python.exe -c "
with open('theauditor/graph/analyzer.py', 'r') as f:
    lines = f.readlines()
    print('Lines 291-296:')
    for i in range(290, 296):
        print(f'{i+1:3d}: {lines[i]}', end='')
"
```

**Expected Evidence**:
```python
isolated_count = len([n for n in nodes if n["id"] not in connected_nodes])
```

**Document Result**:
```
✅ CONFIRMED: Line 296 has isolated_count calculation
✅ CONFIRMED: No isolated_nodes_list variable
```

### Hypothesis 3: Rule Function Naming Requirement

**Hypothesis**: Rules MUST start with `find_` prefix (per TEMPLATE_STANDARD_RULE.py:8-13).

**Verification Steps**:
```bash
# Check template documentation
grep -n "MUST start with" theauditor/rules/TEMPLATE_STANDARD_RULE.py
```

**Expected Evidence**:
```
10:  ✅ def find_sql_injection(context: StandardRuleContext)
12:  ❌ def analyze(context: StandardRuleContext)  # WRONG - Won't be discovered!
```

**Document Result**:
```
✅ CONFIRMED: Function name MUST start with find_
```

### Hypothesis 4: Database Path Pattern

**Hypothesis**: Database path is always `{project_path}/.pf/repo_index.db`.

**Verification Steps**:
```bash
# Check example from detect_frameworks.py:26
grep -n "db_path.*repo_index.db" theauditor/commands/detect_frameworks.py
```

**Expected Evidence**:
```python
db_path = project_path / ".pf" / "repo_index.db"
```

**Document Result**:
```
✅ CONFIRMED: Pattern is Path.cwd() / ".pf" / "repo_index.db"
```

### Hypothesis 5: StandardFinding Parameter Names

**Hypothesis**: Use `file_path=` not `file=`, `rule_name=` not `rule=` (per base.py:163-174).

**Verification Steps**:
```bash
# Check StandardFinding.to_dict() method
.venv/Scripts/python.exe -c "
with open('theauditor/rules/base.py', 'r') as f:
    lines = f.readlines()
    for i in range(154, 186):
        print(f'{i+1:3d}: {lines[i]}', end='')
"
```

**Expected Evidence**:
```python
def to_dict(self) -> Dict[str, Any]:
    result = {
        "rule": self.rule_name,  # Schema expects 'rule'
        "file": self.file_path,  # Schema expects 'file'
```

**Document Result**:
```
✅ CONFIRMED: Use file_path= and rule_name= in constructor
✅ CONFIRMED: to_dict() converts to 'file' and 'rule' for DB
```

### Deliverable: `verification.md`

**Create File**: `openspec/changes/add-dead-code-detection/verification.md`

**Template**:
```markdown
# Verification Report - Phase 0

## Hypothesis Testing Results

### Hypothesis 1: CLI Command Registration
- **Status**: [CONFIRMED | DISCREPANCY]
- **Evidence**: [Exact line numbers and code snippets]
- **Action**: [Update tasks OR proceed as planned]

### Hypothesis 2: Graph Analyzer Isolated Nodes
- **Status**: [CONFIRMED | DISCREPANCY]
- **Evidence**: [Code at lines 291-296]
- **Action**: [...]

[Continue for all 5 hypotheses]

## Discrepancies Found

[List any mismatches between assumptions and reality]

## Recommended Task Adjustments

[If discrepancies found, list task changes needed]

## Approval Request

This verification is complete. Ready to proceed to Phase 1 upon Lead Auditor approval.

**Coder Signature**: [Your name]
**Date**: 2025-10-31
```

**Completion Criteria**:
- [ ] All 5 hypotheses tested
- [ ] Evidence documented with line numbers
- [ ] Discrepancies (if any) noted
- [ ] verification.md created
- [ ] Template C-4.20 report submitted to Lead Auditor
- [ ] **Lead Auditor approval received**

---

## Phase 1: Data Layer Implementation

**Prerequisites**: Phase 0 verification complete and approved.

**Objective**: Create SQL query layer with NO business logic.

**Time Estimate**: 1 hour

### Task 1.1: Create Queries File

**File**: `theauditor/queries/dead_code.py` (NEW FILE)

**Command**:
```bash
# Create queries directory if it doesn't exist
mkdir -p theauditor/queries

# Create __init__.py to make it a package
cat > theauditor/queries/__init__.py << 'EOF'
"""Query modules for database access."""
EOF
```

**Completion Criteria**:
- [ ] Directory `theauditor/queries/` exists
- [ ] File `theauditor/queries/__init__.py` exists

### Task 1.2: Implement DeadCodeQueries Class

**File**: `theauditor/queries/dead_code.py`

**Full Code** (write exactly as shown):
```python
"""Dead code detection queries - pure SQL with NO business logic.

This module contains ONLY SQL queries for dead code detection.
NO classification, NO recommendations, NO formatting - just queries.

Pattern: Similar to theauditor/context/query.py (direct SQL queries).
"""

import sqlite3
from pathlib import Path
from typing import Set, List, Dict, Optional


class DeadCodeQueries:
    """Pure SQL queries for dead code detection.

    Design Principle: This class ONLY executes SQL queries. It does NOT:
    - Classify findings (that's analysis layer)
    - Format output (that's presentation layer)
    - Make recommendations (that's analysis layer)

    All methods return raw data (sets, dicts, lists).
    """

    def __init__(self, db_path: str):
        """Initialize database connection.

        Args:
            db_path: Path to repo_index.db (e.g., .pf/repo_index.db)

        Raises:
            FileNotFoundError: If database doesn't exist
        """
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Database not found: {db_path}. Run 'aud index' first."
            )

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def get_files_with_symbols(self, path_filter: Optional[str] = None) -> Set[str]:
        """Query symbols table for files with code definitions.

        SQL Logic:
            SELECT DISTINCT path FROM symbols WHERE path LIKE ?

        Args:
            path_filter: Optional SQL LIKE pattern (e.g., 'theauditor/%')

        Returns:
            Set of file paths that have at least one symbol

        Example:
            >>> queries = DeadCodeQueries('.pf/repo_index.db')
            >>> files = queries.get_files_with_symbols('theauditor/%')
            >>> 'theauditor/journal.py' in files
            True
        """
        if path_filter:
            self.cursor.execute(
                "SELECT DISTINCT path FROM symbols WHERE path LIKE ?",
                (path_filter,)
            )
        else:
            self.cursor.execute("SELECT DISTINCT path FROM symbols")

        return {row[0] for row in self.cursor.fetchall()}

    def get_imported_files(self) -> Set[str]:
        """Query refs table for files that are imported somewhere.

        SQL Logic:
            SELECT DISTINCT value FROM refs WHERE kind IN ('import', 'from')

        Returns:
            Set of module paths that are imported

        Example:
            >>> queries = DeadCodeQueries('.pf/repo_index.db')
            >>> imported = queries.get_imported_files()
            >>> 'theauditor.cli' in imported  # cli.py IS imported
            True
            >>> 'theauditor.journal' in imported  # journal.py NOT imported
            False
        """
        self.cursor.execute("""
            SELECT DISTINCT value
            FROM refs
            WHERE kind IN ('import', 'from')
        """)

        return {row[0] for row in self.cursor.fetchall()}

    def get_symbol_counts_by_file(self, files: Set[str]) -> Dict[str, int]:
        """Count symbols per file for impact analysis.

        SQL Logic:
            SELECT path, COUNT(*) FROM symbols
            WHERE path IN (?, ?, ...) GROUP BY path

        Args:
            files: Set of file paths to count

        Returns:
            Dict mapping file path -> symbol count

        Example:
            >>> queries = DeadCodeQueries('.pf/repo_index.db')
            >>> counts = queries.get_symbol_counts_by_file({'theauditor/journal.py'})
            >>> counts['theauditor/journal.py']
            3  # get_journal_writer, JournalWriter, integrate_with_pipeline
        """
        if not files:
            return {}

        # Build parameterized query with IN clause
        placeholders = ','.join('?' * len(files))
        query = f"""
            SELECT path, COUNT(*) as symbol_count
            FROM symbols
            WHERE path IN ({placeholders})
            GROUP BY path
        """

        self.cursor.execute(query, tuple(files))
        return {row[0]: row[1] for row in self.cursor.fetchall()}

    def get_called_functions(self) -> Set[str]:
        """Query function_call_args for all called functions.

        SQL Logic:
            SELECT DISTINCT callee_function FROM function_call_args

        Returns:
            Set of function names that are called somewhere

        Note: This is for FUTURE function-level dead code detection.
              Not used in initial module-level implementation.
        """
        self.cursor.execute("""
            SELECT DISTINCT callee_function
            FROM function_call_args
        """)

        return {row[0] for row in self.cursor.fetchall()}

    def get_functions_by_file(self, file_path: str) -> List[Dict[str, any]]:
        """Get all functions/classes defined in a file.

        SQL Logic:
            SELECT name, type, line, end_line FROM symbols
            WHERE path = ? AND type IN ('function', 'method', 'class')

        Args:
            file_path: File to query

        Returns:
            List of dicts with {name, type, line, end_line}

        Example:
            >>> queries = DeadCodeQueries('.pf/repo_index.db')
            >>> funcs = queries.get_functions_by_file('theauditor/journal.py')
            >>> [f['name'] for f in funcs]
            ['get_journal_writer', 'JournalWriter', 'integrate_with_pipeline']
        """
        self.cursor.execute("""
            SELECT name, type, line, end_line
            FROM symbols
            WHERE path = ? AND type IN ('function', 'method', 'class')
            ORDER BY line
        """, (file_path,))

        return [
            {
                'name': row[0],
                'type': row[1],
                'line': row[2],
                'end_line': row[3]
            }
            for row in self.cursor.fetchall()
        ]

    def close(self):
        """Close database connection.

        IMPORTANT: Always call this in a finally block or use context manager.
        """
        self.conn.close()
```

**Completion Criteria**:
- [ ] File `theauditor/queries/dead_code.py` created
- [ ] All 6 methods implemented (get_files_with_symbols, get_imported_files, etc.)
- [ ] Docstrings include SQL logic, examples, return types
- [ ] NO business logic (no classification, no recommendations)
- [ ] NO try/except fallbacks (hard fail if table missing)

### Task 1.3: Create Unit Tests for Queries

**File**: `tests/test_dead_code_queries.py` (NEW FILE)

**Create Mock Database Fixture**:
```python
# File: tests/test_dead_code_queries.py
import pytest
import sqlite3
from pathlib import Path
from theauditor.queries.dead_code import DeadCodeQueries


@pytest.fixture
def mock_db(tmp_path):
    """Create mock database with test data."""
    db_path = tmp_path / "test_repo_index.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create symbols table (schema from indexer/schema.py)
    cursor.execute("""
        CREATE TABLE symbols (
            file TEXT NOT NULL,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT,
            line INTEGER,
            end_line INTEGER
        )
    """)

    # Create refs table
    cursor.execute("""
        CREATE TABLE refs (
            file TEXT NOT NULL,
            line INTEGER,
            kind TEXT,
            value TEXT
        )
    """)

    # Create function_call_args table
    cursor.execute("""
        CREATE TABLE function_call_args (
            file TEXT NOT NULL,
            line INTEGER,
            caller_function TEXT,
            callee_function TEXT
        )
    """)

    # Insert test data
    test_symbols = [
        ('theauditor/journal.py', 'theauditor/journal.py', 'get_journal_writer', 'function', 10, 20),
        ('theauditor/journal.py', 'theauditor/journal.py', 'JournalWriter', 'class', 25, 100),
        ('theauditor/journal.py', 'theauditor/journal.py', 'integrate_with_pipeline', 'function', 105, 150),
        ('theauditor/cli.py', 'theauditor/cli.py', 'main', 'function', 357, 359),
    ]

    cursor.executemany(
        "INSERT INTO symbols (file, path, name, type, line, end_line) VALUES (?, ?, ?, ?, ?, ?)",
        test_symbols
    )

    # Insert refs (cli.py IS imported, journal.py NOT imported)
    test_refs = [
        ('some_file.py', 5, 'import', 'theauditor.cli'),
    ]

    cursor.executemany(
        "INSERT INTO refs (file, line, kind, value) VALUES (?, ?, ?, ?)",
        test_refs
    )

    conn.commit()
    conn.close()

    return str(db_path)


def test_get_files_with_symbols(mock_db):
    """Test SQL query for files with symbols."""
    queries = DeadCodeQueries(mock_db)

    files = queries.get_files_with_symbols()

    assert 'theauditor/journal.py' in files
    assert 'theauditor/cli.py' in files
    assert len(files) == 2

    queries.close()


def test_get_files_with_symbols_filtered(mock_db):
    """Test path filtering."""
    queries = DeadCodeQueries(mock_db)

    files = queries.get_files_with_symbols('theauditor/journal%')

    assert 'theauditor/journal.py' in files
    assert 'theauditor/cli.py' not in files

    queries.close()


def test_get_imported_files(mock_db):
    """Test SQL query for imported files."""
    queries = DeadCodeQueries(mock_db)

    imported = queries.get_imported_files()

    assert 'theauditor.cli' in imported
    assert 'theauditor.journal' not in imported  # NOT imported

    queries.close()


def test_get_symbol_counts_by_file(mock_db):
    """Test symbol count aggregation."""
    queries = DeadCodeQueries(mock_db)

    counts = queries.get_symbol_counts_by_file({'theauditor/journal.py'})

    assert counts['theauditor/journal.py'] == 3  # 3 symbols

    queries.close()


def test_get_functions_by_file(mock_db):
    """Test function listing."""
    queries = DeadCodeQueries(mock_db)

    funcs = queries.get_functions_by_file('theauditor/journal.py')

    assert len(funcs) == 3
    assert funcs[0]['name'] == 'get_journal_writer'
    assert funcs[1]['name'] == 'JournalWriter'
    assert funcs[2]['name'] == 'integrate_with_pipeline'

    queries.close()


def test_database_not_found():
    """Test error handling for missing database."""
    with pytest.raises(FileNotFoundError):
        DeadCodeQueries('/nonexistent/path.db')
```

**Run Tests**:
```bash
# Activate virtualenv
.venv/Scripts/activate

# Install pytest if not already installed
pip install pytest

# Run tests
pytest tests/test_dead_code_queries.py -v

# Expected output:
# test_get_files_with_symbols PASSED
# test_get_files_with_symbols_filtered PASSED
# test_get_imported_files PASSED
# test_get_symbol_counts_by_file PASSED
# test_get_functions_by_file PASSED
# test_database_not_found PASSED
```

**Completion Criteria**:
- [ ] File `tests/test_dead_code_queries.py` created
- [ ] Mock database fixture created
- [ ] 6 unit tests written and passing
- [ ] Test coverage ≥90% for queries/dead_code.py

### Task 1.4: Submit Phase 1 Report

**Deliverable**: Template C-4.20 report to Lead Auditor

**Required Sections**:
1. **Verification Phase Report**: "Hypothesis: Data layer queries work correctly. Verification: All 6 tests pass."
2. **Deep Root Cause Analysis**: "Why SQL-only layer? Separation of concerns - reusable across CLI, rules, graph analyzer."
3. **Implementation Details**: "Created DeadCodeQueries class with 6 methods. File paths: queries/dead_code.py (NEW), tests/test_dead_code_queries.py (NEW)."
4. **Edge Cases**: "Missing database → hard fail with FileNotFoundError (no fallback). Missing table → crash exposes schema bug."
5. **Post-Implementation Audit**: "Re-read queries/dead_code.py - syntax correct, no typos, docstrings complete."
6. **Impact & Testing**: "6 tests pass. Zero production code changes yet (queries not used anywhere)."
7. **Confirmation**: "Phase 1 complete. Confidence: HIGH."

**WAIT FOR LEAD AUDITOR APPROVAL BEFORE PROCEEDING TO PHASE 2.**

---

## Phase 2: Analysis Layer Implementation

**Prerequisites**: Phase 1 complete and approved.

**Objective**: Create business logic layer (uses Data Layer).

**Time Estimate**: 1 hour

### Task 2.1: Create Analysis File

**File**: `theauditor/analysis/isolation.py` (NEW FILE)

**Command**:
```bash
# Create analysis directory
mkdir -p theauditor/analysis

# Create __init__.py
cat > theauditor/analysis/__init__.py << 'EOF'
"""Analysis modules for business logic."""
EOF
```

**Completion Criteria**:
- [ ] Directory `theauditor/analysis/` exists
- [ ] File `theauditor/analysis/__init__.py` exists

### Task 2.2: Implement IsolationAnalyzer Class

**File**: `theauditor/analysis/isolation.py`

**Full Code** (this is LONG - write exactly as shown):

```python
"""Isolation analysis - business logic for dead code detection.

This module contains classification, confidence scoring, and recommendations.
It uses DeadCodeQueries for data access (NO SQL in this file).

Pattern: Similar to theauditor/graph/analyzer.py (business logic layer).
"""

from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from theauditor.queries.dead_code import DeadCodeQueries


@dataclass
class IsolatedModule:
    """Result of dead code detection for a single module.

    This is the OUTPUT of the analysis layer.
    """
    path: str
    symbol_count: int
    lines_estimated: int
    recommendation: str  # 'remove' | 'investigate'
    confidence: str      # 'high' | 'medium' | 'low'
    reason: str


@dataclass
class DeadCodeReport:
    """Complete dead code detection report.

    This is the FINAL output of isolation analysis.
    """
    isolated_modules: List[IsolatedModule]
    total_files_analyzed: int
    total_files_with_code: int
    total_dead_code_files: int
    estimated_wasted_loc: int


class IsolationAnalyzer:
    """Business logic for dead code detection.

    Design Principle: This class ONLY contains business logic. It does NOT:
    - Execute SQL queries (that's data layer - DeadCodeQueries)
    - Format output for users (that's presentation layer - CLI commands)
    - Parse files or ASTs (uses database only)

    All methods return structured data (dataclasses).
    """

    def __init__(self, db_path: str):
        """Initialize analyzer with database connection.

        Args:
            db_path: Path to repo_index.db
        """
        self.queries = DeadCodeQueries(db_path)

    def detect_isolated_modules(
        self,
        path_filter: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> DeadCodeReport:
        """Detect modules that are never imported.

        Algorithm:
            1. Get all files with symbols (CODE_FILES) from database
            2. Get all imported files (IMPORTED_FILES) from database
            3. Isolated = CODE_FILES - IMPORTED_FILES (set difference)
            4. Filter exclusions (tests, migrations, __init__.py)
            5. Classify each isolated module (confidence + recommendation)
            6. Build report with summary statistics

        Args:
            path_filter: Only analyze paths matching filter (e.g., 'theauditor/%')
            exclude_patterns: Skip paths containing these patterns

        Returns:
            DeadCodeReport with findings and statistics

        Example:
            >>> analyzer = IsolationAnalyzer('.pf/repo_index.db')
            >>> report = analyzer.detect_isolated_modules('theauditor/%')
            >>> report.total_dead_code_files
            1  # journal.py
        """
        # Step 1: Get files with code (database query)
        files_with_code = self.queries.get_files_with_symbols(path_filter)

        # Step 2: Get files that are imported (database query)
        imported_files = self.queries.get_imported_files()

        # Step 3: Set difference (Python set operation)
        # This is the core dead code detection logic
        isolated_paths = files_with_code - self._normalize_imported_to_paths(imported_files)

        # Step 4: Apply exclusions
        if exclude_patterns:
            isolated_paths = self._filter_exclusions(isolated_paths, exclude_patterns)

        # Step 5: Get symbol counts for impact analysis (database query)
        symbol_counts = self.queries.get_symbol_counts_by_file(isolated_paths)

        # Step 6: Classify each isolated module (business logic)
        isolated_modules = []
        for path in sorted(isolated_paths):
            module = self._classify_isolated_module(path, symbol_counts.get(path, 0))
            isolated_modules.append(module)

        # Step 7: Build report with summary statistics
        estimated_loc = sum(m.lines_estimated for m in isolated_modules)

        return DeadCodeReport(
            isolated_modules=isolated_modules,
            total_files_analyzed=len(files_with_code),
            total_files_with_code=len(files_with_code),
            total_dead_code_files=len(isolated_modules),
            estimated_wasted_loc=estimated_loc
        )

    def _normalize_imported_to_paths(self, imported: Set[str]) -> Set[str]:
        """Convert imported module names to file paths.

        Examples:
            'theauditor.cli' -> 'theauditor/cli.py'
            'theauditor.utils.logger' -> 'theauditor/utils/logger.py'

        Args:
            imported: Set of module names (e.g., 'theauditor.cli')

        Returns:
            Set of file paths (e.g., 'theauditor/cli.py')
        """
        normalized = set()
        for module in imported:
            # Replace dots with slashes, add .py extension
            path = module.replace('.', '/') + '.py'
            normalized.add(path)
        return normalized

    def _filter_exclusions(
        self,
        paths: Set[str],
        exclude_patterns: List[str]
    ) -> Set[str]:
        """Remove paths matching exclusion patterns.

        Args:
            paths: Set of file paths
            exclude_patterns: List of patterns to exclude

        Returns:
            Filtered set of paths

        Example:
            >>> analyzer._filter_exclusions(
            ...     {'a/test.py', 'b/real.py'},
            ...     ['test']
            ... )
            {'b/real.py'}
        """
        filtered = set()
        for path in paths:
            excluded = False
            for pattern in exclude_patterns:
                if pattern in path:
                    excluded = True
                    break
            if not excluded:
                filtered.add(path)
        return filtered

    def _classify_isolated_module(
        self,
        path: str,
        symbol_count: int
    ) -> IsolatedModule:
        """Classify isolated module with confidence and recommendation.

        Classification Logic:
            Confidence Levels:
            - LOW: __init__.py with 0 symbols (might be package marker)
            - MEDIUM: test files, migrations, CLI entry points (external entry)
            - HIGH: all other files with 1+ symbols

            Recommendation Logic:
            - 'remove': High confidence + ≥10 symbols (significant dead code)
            - 'investigate': Low/medium confidence OR <10 symbols

        Args:
            path: File path
            symbol_count: Number of symbols in file

        Returns:
            Classified IsolatedModule

        Example:
            >>> analyzer._classify_isolated_module('foo.py', 15)
            IsolatedModule(
                path='foo.py',
                symbol_count=15,
                lines_estimated=150,
                recommendation='remove',
                confidence='high',
                reason='No imports found'
            )
        """
        confidence = 'high'
        reason = 'No imports found'

        # Reduce confidence for known false positives
        path_lower = path.lower()

        if path.endswith('__init__.py') and symbol_count == 0:
            confidence = 'low'
            reason = 'Empty package marker'
        elif 'test' in path_lower:
            confidence = 'medium'
            reason = 'Test file (might be entry point)'
        elif 'migration' in path_lower:
            confidence = 'medium'
            reason = 'Migration script (external entry)'
        elif path.endswith(('cli.py', '__main__.py', 'main.py')):
            confidence = 'medium'
            reason = 'CLI entry point (external invocation)'

        # Recommendation logic
        if confidence == 'high' and symbol_count >= 10:
            recommendation = 'remove'
        else:
            recommendation = 'investigate'

        # Estimate LOC (rough: 10 lines per symbol average)
        lines_estimated = symbol_count * 10

        return IsolatedModule(
            path=path,
            symbol_count=symbol_count,
            lines_estimated=lines_estimated,
            recommendation=recommendation,
            confidence=confidence,
            reason=reason
        )

    def close(self):
        """Close database connection.

        IMPORTANT: Always call this when done.
        """
        self.queries.close()
```

**Completion Criteria**:
- [ ] File `theauditor/analysis/isolation.py` created
- [ ] `IsolatedModule` dataclass defined
- [ ] `DeadCodeReport` dataclass defined
- [ ] `IsolationAnalyzer` class implemented
- [ ] Algorithm documented in docstring
- [ ] NO SQL queries (uses DeadCodeQueries)

### Task 2.3: Create Unit Tests for Analysis

**File**: `tests/test_isolation_analyzer.py` (NEW FILE)

```python
# File: tests/test_isolation_analyzer.py
import pytest
from theauditor.analysis.isolation import IsolationAnalyzer


def test_detect_isolated_modules(mock_db):
    """Test full dead code detection algorithm."""
    analyzer = IsolationAnalyzer(mock_db)

    report = analyzer.detect_isolated_modules()

    # journal.py should be detected as dead code
    assert report.total_dead_code_files >= 1
    isolated_paths = [m.path for m in report.isolated_modules]
    assert 'theauditor/journal.py' in isolated_paths

    # cli.py should NOT be detected (it's imported)
    assert 'theauditor/cli.py' not in isolated_paths

    analyzer.close()


def test_filter_exclusions():
    """Test exclusion pattern filtering."""
    analyzer = IsolationAnalyzer(mock_db)  # Uses fixture from test_dead_code_queries.py

    paths = {'a/test.py', 'b/real.py', 'c/migration.py'}
    filtered = analyzer._filter_exclusions(paths, ['test', 'migration'])

    assert filtered == {'b/real.py'}

    analyzer.close()


def test_classify_high_confidence():
    """Test high-confidence classification."""
    analyzer = IsolationAnalyzer(mock_db)

    module = analyzer._classify_isolated_module('foo.py', symbol_count=15)

    assert module.confidence == 'high'
    assert module.recommendation == 'remove'
    assert module.reason == 'No imports found'
    assert module.lines_estimated == 150  # 15 symbols * 10 lines/symbol

    analyzer.close()


def test_classify_low_confidence_empty_init():
    """Test low-confidence classification for empty __init__.py."""
    analyzer = IsolationAnalyzer(mock_db)

    module = analyzer._classify_isolated_module('pkg/__init__.py', symbol_count=0)

    assert module.confidence == 'low'
    assert module.recommendation == 'investigate'
    assert module.reason == 'Empty package marker'

    analyzer.close()


def test_classify_medium_confidence_test_file():
    """Test medium-confidence classification for test files."""
    analyzer = IsolationAnalyzer(mock_db)

    module = analyzer._classify_isolated_module('tests/test_foo.py', symbol_count=5)

    assert module.confidence == 'medium'
    assert module.recommendation == 'investigate'
    assert module.reason == 'Test file (might be entry point)'

    analyzer.close()
```

**Run Tests**:
```bash
# Re-run full test suite
pytest tests/test_*.py -v

# Expected: All tests pass (10+ tests total)
```

**Completion Criteria**:
- [ ] File `tests/test_isolation_analyzer.py` created
- [ ] 5 unit tests written and passing
- [ ] Test coverage ≥90% for analysis/isolation.py

### Task 2.4: Submit Phase 2 Report

**Deliverable**: Template C-4.20 report to Lead Auditor

**Required Sections**: (same structure as Phase 1)

**WAIT FOR LEAD AUDITOR APPROVAL BEFORE PROCEEDING TO PHASE 3.**

---

## Phase 3: Presentation Layer (CLI Command)

**Prerequisites**: Phase 2 complete and approved.

**Objective**: Create user-facing CLI command.

**Time Estimate**: 1.5 hours

### Task 3.1: Create CLI Command File

**File**: `theauditor/commands/deadcode.py` (NEW FILE)

**Full Code** (approximately 250 lines):

```python
"""Dead code detection CLI command.

Command: aud deadcode
Pattern: Similar to theauditor/commands/detect_frameworks.py
"""

import click
import json
from pathlib import Path
from theauditor.analysis.isolation import IsolationAnalyzer
from theauditor.utils.error_handler import handle_exceptions


@click.command("deadcode")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option("--path-filter", help="Only analyze paths matching filter (e.g., 'theauditor/%')")
@click.option(
    "--exclude",
    multiple=True,
    default=['test', '__tests__', 'migrations', 'node_modules', '.venv'],
    help="Exclude paths matching patterns (can specify multiple times)"
)
@click.option(
    "--format",
    type=click.Choice(['text', 'json', 'summary']),
    default='text',
    help="Output format (text=human, json=CI/CD, summary=counts only)"
)
@click.option("--save", type=click.Path(), help="Save output to file")
@click.option("--fail-on-dead-code", is_flag=True, help="Exit 1 if dead code found (for CI/CD)")
@handle_exceptions
def deadcode(project_path, path_filter, exclude, format, save, fail_on_dead_code):
    """Detect dead code (modules never imported, functions never called).

    [FULL DOCSTRING FROM design.md - approximately 100 lines]
    """
    project_path = Path(project_path).resolve()
    db_path = project_path / ".pf" / "repo_index.db"

    # Validate database exists
    if not db_path.exists():
        click.echo("Error: Database not found. Run 'aud index' first.", err=True)
        raise click.ClickException("Database not found - run 'aud index' first")

    try:
        # Run analysis
        analyzer = IsolationAnalyzer(str(db_path))
        report = analyzer.detect_isolated_modules(
            path_filter=path_filter,
            exclude_patterns=list(exclude)
        )
        analyzer.close()

        # Format output
        if format == 'json':
            output = _format_json(report)
        elif format == 'summary':
            output = _format_summary(report)
        else:  # text
            output = _format_text(report)

        # Print to stdout
        click.echo(output)

        # Save if requested
        if save:
            save_path = Path(save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(output)
            click.echo(f"\nSaved to: {save_path}", err=True)

        # Exit code logic
        if fail_on_dead_code and report.total_dead_code_files > 0:
            raise click.ClickException(
                f"Dead code detected: {report.total_dead_code_files} files"
            )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e


def _format_text(report) -> str:
    """Format report as human-readable ASCII table.

    IMPORTANT: NO EMOJIS (per CLAUDE.md - Windows CP1252 encoding).
    Use plain ASCII text only.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("Dead Code Analysis Report")
    lines.append("=" * 80)
    lines.append(f"Files analyzed: {report.total_files_analyzed}")
    lines.append(f"Dead code files: {report.total_dead_code_files}")
    lines.append(f"Estimated wasted LOC: {report.estimated_wasted_loc}")
    lines.append("")

    if not report.isolated_modules:
        lines.append("[OK] No dead code detected!")
        return "\n".join(lines)

    lines.append("Isolated Modules (never imported):")
    lines.append("-" * 80)

    for module in report.isolated_modules:
        # Use plain text indicators (no emojis)
        confidence_marker = {
            'high': '[HIGH]',
            'medium': '[MED ]',
            'low': '[LOW ]'
        }.get(module.confidence, '[????]')

        lines.append(f"{confidence_marker} {module.path}")
        lines.append(f"   Symbols: {module.symbol_count}")
        lines.append(f"   Estimated LOC: {module.lines_estimated}")
        lines.append(f"   Confidence: {module.confidence.upper()}")
        lines.append(f"   Reason: {module.reason}")
        lines.append(f"   Recommendation: {module.recommendation.upper()}")
        lines.append("")

    return "\n".join(lines)


def _format_json(report) -> str:
    """Format report as JSON for CI/CD integration."""
    data = {
        'summary': {
            'total_files_analyzed': report.total_files_analyzed,
            'total_dead_code_files': report.total_dead_code_files,
            'estimated_wasted_loc': report.estimated_wasted_loc
        },
        'isolated_modules': [
            {
                'path': m.path,
                'symbol_count': m.symbol_count,
                'lines_estimated': m.lines_estimated,
                'confidence': m.confidence,
                'recommendation': m.recommendation,
                'reason': m.reason
            }
            for m in report.isolated_modules
        ]
    }
    return json.dumps(data, indent=2)


def _format_summary(report) -> str:
    """Format report as counts only (quick check)."""
    return f"""Dead Code Summary:
  Files analyzed: {report.total_files_analyzed}
  Dead code files: {report.total_dead_code_files}
  Estimated wasted LOC: {report.estimated_wasted_loc}
"""
```

**Completion Criteria**:
- [ ] File `theauditor/commands/deadcode.py` created
- [ ] Command function implemented with all options
- [ ] Three formatters implemented (text, json, summary)
- [ ] NO EMOJIS in output (Windows compatibility)

### Task 3.2: Register Command in CLI

**File**: `theauditor/cli.py`

**Step 1: Add Import** (around line 265):
```python
# Find this section (around line 249-273):
from theauditor.commands.init import init
from theauditor.commands.index import index
# ... (more imports) ...
from theauditor.commands.explain import explain

# ADD THIS LINE (after line 264 or wherever explain is imported):
from theauditor.commands.deadcode import deadcode
```

**Step 2: Register Command** (around line 315):
```python
# Find this section (around line 300-315):
cli.add_command(init)
cli.add_command(index)
# ... (more registrations) ...
cli.add_command(explain)

# ADD THIS LINE (after line 313 or wherever explain is registered):
cli.add_command(deadcode)
```

**Exact Line Numbers** (verify in Phase 0):
```bash
# Find exact import line number
grep -n "from theauditor.commands.explain import" theauditor/cli.py
# Output: 264:from theauditor.commands.explain import explain

# Find exact registration line number
grep -n "cli.add_command(explain)" theauditor/cli.py
# Output: 313:cli.add_command(explain)

# Add import AFTER line 264, registration AFTER line 313
```

**Completion Criteria**:
- [ ] Import added to cli.py (around line 265)
- [ ] Registration added to cli.py (around line 315)
- [ ] Command discoverable: `aud --help` shows "deadcode"

### Task 3.3: Manual Testing

**Test 1: Help Text**:
```bash
aud deadcode --help

# Expected output:
# Usage: aud deadcode [OPTIONS]
#
# Detect dead code (modules never imported, functions never called).
# ...
```

**Test 2: Basic Usage** (requires indexed database):
```bash
# First, ensure database exists
aud index

# Then run deadcode
aud deadcode

# Expected output:
# ================================================================================
# Dead Code Analysis Report
# ================================================================================
# Files analyzed: 410
# Dead code files: 1
# Estimated wasted LOC: 446
#
# Isolated Modules (never imported):
# --------------------------------------------------------------------------------
# [HIGH] theauditor/journal.py
#    Symbols: 3
#    Estimated LOC: 446
#    Confidence: HIGH
#    Reason: No imports found
#    Recommendation: REMOVE
```

**Test 3: JSON Format**:
```bash
aud deadcode --format json

# Expected output:
# {
#   "summary": {
#     "total_files_analyzed": 410,
#     "total_dead_code_files": 1,
#     "estimated_wasted_loc": 446
#   },
#   "isolated_modules": [
#     {
#       "path": "theauditor/journal.py",
#       "symbol_count": 3,
#       "lines_estimated": 446,
#       "confidence": "high",
#       "recommendation": "remove",
#       "reason": "No imports found"
#     }
#   ]
# }
```

**Test 4: Path Filter**:
```bash
aud deadcode --path-filter 'theauditor/%'

# Should only analyze theauditor/ directory
```

**Test 5: Exclusions**:
```bash
aud deadcode --exclude test --exclude migration

# Should skip test files and migrations
```

**Test 6: Fail on Dead Code**:
```bash
aud deadcode --fail-on-dead-code
echo $?

# Expected exit code: 1 (if dead code found)
```

**Completion Criteria**:
- [ ] All 6 manual tests pass
- [ ] Help text displays correctly
- [ ] Text format shows ASCII table
- [ ] JSON format outputs valid JSON
- [ ] Path filter works
- [ ] Exclusions work
- [ ] Fail-on-dead-code exits with code 1

### Task 3.4: Submit Phase 3 Report

**Deliverable**: Template C-4.20 report to Lead Auditor

**WAIT FOR LEAD AUDITOR APPROVAL BEFORE PROCEEDING TO PHASE 4.**

---

## Phase 4: Integration Layer (Graph + Rules)

**Prerequisites**: Phase 3 complete and approved.

**Objective**: Integrate with graph analyzer and quality rules.

**Time Estimate**: 1 hour

### Task 4.1: Modify Graph Analyzer

**File**: `theauditor/graph/analyzer.py`

**Location**: Line 296 (after `isolated_count` calculation)

**Current Code** (line 291-296):
```python
# Find isolated nodes
connected_nodes = set()
for edge in edges:
    connected_nodes.add(edge["source"])
    connected_nodes.add(edge["target"])
isolated_count = len([n for n in nodes if n["id"] not in connected_nodes])
```

**New Code** (ADD AFTER LINE 296):
```python
# Store isolated node IDs (not just count) - NEW
isolated_nodes_list = [
    n["id"] for n in nodes if n["id"] not in connected_nodes
]
```

**Update Return Value** (line 299, inside `summary` dict):

**Find This** (around line 299-305):
```python
summary = {
    "statistics": {
        "total_nodes": node_count,
        "total_edges": edge_count,
        "graph_density": round(density, 4),
        "isolated_nodes": isolated_count,  # Existing
        "average_connections": round(edge_count / node_count, 2) if node_count > 0 else 0
    },
```

**Change To**:
```python
summary = {
    "statistics": {
        "total_nodes": node_count,
        "total_edges": edge_count,
        "graph_density": round(density, 4),
        "isolated_nodes": isolated_count,  # Keep for backwards compatibility
        "isolated_nodes_list": isolated_nodes_list[:100],  # NEW: List first 100
        "average_connections": round(edge_count / node_count, 2) if node_count > 0 else 0
    },
```

**Completion Criteria**:
- [ ] Line added after line 296: `isolated_nodes_list = [...]`
- [ ] Return dict updated with `"isolated_nodes_list": isolated_nodes_list[:100]`
- [ ] No syntax errors

### Task 4.2: Add --show-isolated Flag to Graph Command

**File**: `theauditor/commands/graph.py`

**Find `analyze` Subcommand** (around line 80-120):
```bash
# Search for analyze function
grep -n "def analyze" theauditor/commands/graph.py
```

**Add Option** (around line 100):

**Find This**:
```python
@click.command("analyze")
@click.option("--format", ...)
@click.option("--save", ...)
def analyze(format, save):
    """Analyze dependency graph for cycles and hotspots."""
```

**Add This Line** (after other @click.option decorators):
```python
@click.option('--show-isolated', is_flag=True, help='List isolated nodes in output')
```

**Update Function Signature**:
```python
def analyze(format, save, show_isolated):  # ADD show_isolated parameter
```

**Add Logic** (inside `analyze` function, after summary is generated):

**Find This** (around line 140):
```python
# Generate summary
summary = analyzer.get_graph_summary(graph_data)

# Format output
if format == 'json':
    output = json.dumps(summary, indent=2)
else:
    output = _format_summary(summary)
```

**Add This** (AFTER the above block):
```python
# Display isolated nodes if requested
if show_isolated:
    isolated = summary['statistics'].get('isolated_nodes_list', [])
    click.echo("\n" + "="*60)
    click.echo("Isolated Nodes (no connections):")
    click.echo("="*60)
    if isolated:
        for node_id in isolated:
            click.echo(f"  - {node_id}")
    else:
        click.echo("  (none)")
```

**Completion Criteria**:
- [ ] `--show-isolated` option added
- [ ] Parameter added to function signature
- [ ] Logic added to display isolated nodes
- [ ] No syntax errors

### Task 4.3: Create Quality Rule

**File**: `theauditor/rules/quality/dead_code.py` (NEW FILE)

**Create Directory**:
```bash
mkdir -p theauditor/rules/quality

# Create __init__.py
cat > theauditor/rules/quality/__init__.py << 'EOF'
"""Quality rules - code quality issues (not security)."""
EOF
```

**Full Code** (approximately 100 lines):

```python
"""Dead code detection rule - finds modules never imported.

Integrated into 'aud full' pipeline via orchestrator.
Generates findings with severity='info' (not a security issue, but quality concern).

Pattern: Follows TEMPLATE_STANDARD_RULE.py
"""

import sqlite3
from typing import List
from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    RuleMetadata
)


# Rule metadata for orchestrator filtering
METADATA = RuleMetadata(
    name="dead_code",
    category="quality",
    target_extensions=['.py', '.js', '.ts', '.tsx', '.jsx'],
    exclude_patterns=['node_modules/', '.venv/', '__pycache__/', 'dist/', 'build/'],
    requires_jsx_pass=False,  # Uses standard tables
    execution_scope='database'  # Run once per database, not per file
)


def find_dead_code(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect dead code using database queries.

    Detection Strategy:
        1. Query symbols table for files with code definitions
        2. Query refs table for imported files
        3. Set difference identifies dead code
        4. Filter exclusions (__init__.py, tests, migrations)

    Database Tables Used:
        - symbols (read: path, name)
        - refs (read: value, kind)

    Known Limitations:
        - Does NOT detect dynamically imported modules (importlib.import_module)
        - Does NOT detect getattr() dynamic calls
        - Static analysis only

    Returns:
        List of findings with severity=INFO
    """
    findings = []

    # Only run if database exists
    if not context.db_path:
        return findings

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        # Query 1: Get files with symbols
        cursor.execute("SELECT DISTINCT path FROM symbols")
        files_with_code = {row[0] for row in cursor.fetchall()}

        # Query 2: Get imported files
        cursor.execute("""
            SELECT DISTINCT value
            FROM refs
            WHERE kind IN ('import', 'from')
        """)
        imported_modules = {row[0] for row in cursor.fetchall()}

        # Normalize imported modules to file paths
        imported_files = set()
        for module in imported_modules:
            # Convert 'theauditor.cli' -> 'theauditor/cli.py'
            path = module.replace('.', '/') + '.py'
            imported_files.add(path)

        # Set difference: dead code
        dead_files = files_with_code - imported_files

        # Filter exclusions (tests, migrations, __init__.py)
        for file_path in dead_files:
            # Skip known false positives
            if any(x in file_path for x in [
                '__init__.py',
                'test',
                'migration',
                '__pycache__',
                'node_modules',
                '.venv'
            ]):
                continue

            # Create finding (severity=INFO)
            findings.append(StandardFinding(
                rule_name="dead_code",
                message=f"Module never imported: {file_path}",
                file_path=str(file_path),
                line=1,
                severity=Severity.INFO,  # Not a security issue
                category="quality",
                snippet="",
                additional_info={'type': 'isolated_module'}
            ))

        conn.close()

    except Exception:
        # Hard fail if database query fails (no fallback)
        raise

    return findings
```

**Completion Criteria**:
- [ ] Directory `theauditor/rules/quality/` created
- [ ] File `theauditor/rules/quality/__init__.py` created
- [ ] File `theauditor/rules/quality/dead_code.py` created
- [ ] `METADATA` defined
- [ ] `find_dead_code` function implemented
- [ ] NO try/except fallbacks (raises on error)

### Task 4.4: Test Quality Rule Integration

**Test 1: Verify Rule Discovered**:
```bash
# Run aud full to trigger orchestrator
aud full

# Check findings_consolidated table
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()
cursor.execute(\"\"\"
    SELECT rule, file, message
    FROM findings_consolidated
    WHERE rule = 'dead_code'
\"\"\")
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} - {row[2]}')
conn.close()
"

# Expected output:
# dead_code: theauditor/journal.py - Module never imported: theauditor/journal.py
```

**Test 2: Verify Severity=INFO**:
```bash
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()
cursor.execute(\"\"\"
    SELECT severity
    FROM findings_consolidated
    WHERE rule = 'dead_code'
\"\"\")
print(cursor.fetchone()[0])  # Should be 'info'
conn.close()
"

# Expected output: info
```

**Completion Criteria**:
- [ ] Rule runs during `aud full`
- [ ] Findings written to `findings_consolidated` table
- [ ] Severity is "info" (not "high" or "critical")
- [ ] journal.py detected as dead code

### Task 4.5: Submit Phase 4 Report

**Deliverable**: Template C-4.20 report to Lead Auditor

**WAIT FOR LEAD AUDITOR APPROVAL BEFORE PROCEEDING TO PHASE 5.**

---

## Phase 5: Testing & Validation

**Prerequisites**: Phase 4 complete and approved.

**Objective**: Comprehensive testing and validation.

**Time Estimate**: 1.5 hours

### Task 5.1: Create Integration Test

**File**: `tests/test_dead_code_integration.py` (NEW FILE)

```python
"""Integration test for dead code detection full pipeline."""

import pytest
from click.testing import CliRunner
from theauditor.commands.deadcode import deadcode
import json


def test_full_pipeline(tmpdir):
    """Test full dead code detection pipeline with real database.

    This test requires running 'aud index' first to generate database.
    """
    runner = CliRunner()

    # Run command
    result = runner.invoke(deadcode, [
        '--project-path', '.',
        '--format', 'json'
    ])

    # Check exit code
    assert result.exit_code == 0

    # Parse JSON output
    data = json.loads(result.output)

    # Validate structure
    assert 'summary' in data
    assert 'isolated_modules' in data

    # Validate summary
    assert data['summary']['total_files_analyzed'] > 0
    assert isinstance(data['summary']['total_dead_code_files'], int)

    # Validate modules
    for module in data['isolated_modules']:
        assert 'path' in module
        assert 'confidence' in module
        assert 'recommendation' in module
        assert module['confidence'] in ['high', 'medium', 'low']
        assert module['recommendation'] in ['remove', 'investigate']


def test_text_format():
    """Test text format output."""
    runner = CliRunner()

    result = runner.invoke(deadcode, ['--format', 'text'])

    assert result.exit_code == 0
    assert '=' in result.output  # Header separator
    assert 'Dead Code Analysis Report' in result.output


def test_summary_format():
    """Test summary format output."""
    runner = CliRunner()

    result = runner.invoke(deadcode, ['--format', 'summary'])

    assert result.exit_code == 0
    assert 'Dead Code Summary:' in result.output
    assert 'Files analyzed:' in result.output


def test_fail_on_dead_code():
    """Test --fail-on-dead-code flag."""
    runner = CliRunner()

    result = runner.invoke(deadcode, ['--fail-on-dead-code'])

    # If dead code exists, exit code should be 1
    # If no dead code, exit code should be 0
    assert result.exit_code in [0, 1]
```

**Run Test**:
```bash
# Ensure database is fresh
aud index

# Run integration test
pytest tests/test_dead_code_integration.py -v

# Expected: All tests pass
```

**Completion Criteria**:
- [ ] Integration test file created
- [ ] 4 integration tests implemented
- [ ] All tests pass

### Task 5.2: Run Full Test Suite

```bash
# Run ALL tests
pytest tests/test_dead_code*.py -v --cov=theauditor --cov-report=term-missing

# Expected output:
# tests/test_dead_code_queries.py::test_get_files_with_symbols PASSED
# tests/test_dead_code_queries.py::test_get_imported_files PASSED
# tests/test_isolation_analyzer.py::test_detect_isolated_modules PASSED
# tests/test_isolation_analyzer.py::test_classify_high_confidence PASSED
# tests/test_dead_code_integration.py::test_full_pipeline PASSED
# tests/test_dead_code_integration.py::test_text_format PASSED
# ...
#
# ---------- coverage: 95% ----------
```

**Completion Criteria**:
- [ ] All unit tests pass (queries, analysis)
- [ ] All integration tests pass
- [ ] Coverage ≥90% for new code

### Task 5.3: OpenSpec Validation

```bash
# Validate strict mode
openspec validate add-dead-code-detection --strict

# Expected output:
# ✓ Proposal structure valid
# ✓ Tasks checklist valid
# ✓ Design document exists
# ✓ Spec deltas valid
# ✓ All requirements have scenarios
# ✓ Validation PASSED
```

**If Validation Fails**:
- Read error messages carefully
- Fix issues (missing scenarios, invalid delta headers, etc.)
- Re-run validation

**Completion Criteria**:
- [ ] `openspec validate --strict` passes

### Task 5.4: Manual Validation on TheAuditor

**Test**: Run deadcode on TheAuditor itself

```bash
# Ensure fresh database
aud index

# Run deadcode
aud deadcode

# Expected: Detects journal.py as dead code
# Output should include:
#   [HIGH] theauditor/journal.py
#   Symbols: 3
#   Recommendation: REMOVE
```

**Verify**:
- [ ] journal.py detected
- [ ] Confidence is HIGH
- [ ] Recommendation is REMOVE
- [ ] Output is readable (no emojis, plain ASCII)

### Task 5.5: Post-Implementation Integrity Audit (SOP Requirement)

**Objective**: Re-read ALL modified files to confirm correctness.

**Files to Re-read**:
```bash
# Query layer
cat theauditor/queries/dead_code.py | wc -l  # Should be ~200 lines

# Analysis layer
cat theauditor/analysis/isolation.py | wc -l  # Should be ~250 lines

# CLI command
cat theauditor/commands/deadcode.py | wc -l  # Should be ~250 lines

# Graph analyzer
git diff theauditor/graph/analyzer.py | less  # Review changes

# Graph command
git diff theauditor/commands/graph.py | less

# CLI registration
git diff theauditor/cli.py | less

# Quality rule
cat theauditor/rules/quality/dead_code.py | wc -l  # Should be ~100 lines
```

**Check for**:
- [ ] Syntax errors (run `python -m py_compile <file>`)
- [ ] Typos in docstrings
- [ ] Correct imports
- [ ] No emoji characters (use grep)
- [ ] No fallback logic (no try/except with pass)
- [ ] No regex on file content

**Run Syntax Check**:
```bash
# Compile all new files
python -m py_compile theauditor/queries/dead_code.py
python -m py_compile theauditor/analysis/isolation.py
python -m py_compile theauditor/commands/deadcode.py
python -m py_compile theauditor/rules/quality/dead_code.py

# If any fails, fix syntax errors
```

**Completion Criteria**:
- [ ] All files re-read
- [ ] No syntax errors found
- [ ] No unintended changes
- [ ] No emojis in output code

### Task 5.6: Submit Phase 5 Final Report

**Deliverable**: Template C-4.20 comprehensive final report

**Required Sections** (extended for final report):
1. **Verification Phase Report**: "All hypotheses tested in Phase 0. Evidence documented."
2. **Deep Root Cause Analysis**: "Dead code detection solves blind spot where journal.py sat unused. Root cause: No analysis layer exposed database evidence."
3. **Implementation Details**: "Created 4 new files (queries, analysis, CLI, rule). Modified 3 files (graph analyzer, graph command, CLI registration). Total: 800 LOC."
4. **Edge Cases & Failure Modes**: "False positives: Dynamic imports (confidence=medium). CLI entry points (confidence=medium). Empty __init__.py (confidence=low). Failure modes: Database missing (hard fail, exit 2). Table missing (hard crash, exposes schema bug)."
5. **Post-Implementation Integrity Audit**: "Re-read all 7 files. Syntax checks pass. No emojis. No fallbacks. No regex."
6. **Impact, Reversion, & Testing**: "16 unit tests, 4 integration tests, all pass. Coverage 95%. Manual test detected journal.py. Reversion: `git revert <commit>`. Breaking changes: None."
7. **Confidence**: "HIGH. All tests pass. Manual validation confirms journal.py detected."

**SUBMIT TO LEAD AUDITOR FOR FINAL APPROVAL.**

---

## Phase 6: Archive (After Deployment)

**Prerequisites**: Phase 5 complete, approved, and deployed to production.

**Objective**: Archive proposal and update specs.

**Time Estimate**: 30 minutes

### Task 6.1: Move to Archive

```bash
# Create archive directory with date stamp
mkdir -p openspec/changes/archive/2025-10-31-add-dead-code-detection

# Move proposal
mv openspec/changes/add-dead-code-detection/* \
   openspec/changes/archive/2025-10-31-add-dead-code-detection/

# Remove empty directory
rmdir openspec/changes/add-dead-code-detection
```

**Completion Criteria**:
- [ ] Directory moved to archive/
- [ ] Date stamp added (YYYY-MM-DD format)
- [ ] Original directory removed

### Task 6.2: Update Spec (If New Capability)

**File**: `openspec/specs/code-quality/spec.md` (NEW FILE if doesn't exist)

```markdown
# Capability: Code Quality Analysis

## Overview

Code quality analysis for maintainability and technical debt.

## Requirements

### Requirement: Dead Code Detection

The system SHALL detect code that is defined but never imported or called.

#### Scenario: Isolated module detection
- **WHEN** a module has symbols but zero imports
- **THEN** the system reports it as isolated

#### Scenario: Confidence classification
- **WHEN** analyzing isolated modules
- **THEN** the system assigns confidence (high/medium/low)

#### Scenario: Actionable recommendations
- **WHEN** dead code is detected
- **THEN** the system provides recommendations (remove vs investigate)
```

**Completion Criteria**:
- [ ] Spec file created or updated
- [ ] Requirements documented
- [ ] Scenarios added

### Task 6.3: Validate Archive

```bash
# Validate archived change
openspec validate --strict

# Expected: Passes (archive validation)
```

**Completion Criteria**:
- [ ] Archive validation passes

---

## Final Deliverables Checklist

### Code Deliverables

- [ ] `theauditor/queries/__init__.py` (NEW)
- [ ] `theauditor/queries/dead_code.py` (NEW, ~200 LOC)
- [ ] `theauditor/analysis/__init__.py` (NEW)
- [ ] `theauditor/analysis/isolation.py` (NEW, ~250 LOC)
- [ ] `theauditor/commands/deadcode.py` (NEW, ~250 LOC)
- [ ] `theauditor/rules/quality/__init__.py` (NEW)
- [ ] `theauditor/rules/quality/dead_code.py` (NEW, ~100 LOC)
- [ ] `theauditor/graph/analyzer.py` (MODIFIED, +5 lines)
- [ ] `theauditor/commands/graph.py` (MODIFIED, +15 lines)
- [ ] `theauditor/cli.py` (MODIFIED, +2 lines)

### Test Deliverables

- [ ] `tests/test_dead_code_queries.py` (NEW, 6 tests)
- [ ] `tests/test_isolation_analyzer.py` (NEW, 5 tests)
- [ ] `tests/test_dead_code_integration.py` (NEW, 4 tests)

### Documentation Deliverables

- [ ] `openspec/changes/add-dead-code-detection/proposal.md`
- [ ] `openspec/changes/add-dead-code-detection/design.md`
- [ ] `openspec/changes/add-dead-code-detection/tasks.md` (this file)
- [ ] `openspec/changes/add-dead-code-detection/verification.md` (created in Phase 0)
- [ ] `openspec/changes/add-dead-code-detection/specs/code-quality/spec.md`
- [ ] `openspec/specs/code-quality/spec.md` (archived version)

### Report Deliverables (SOP v4.20)

- [ ] Phase 0: Verification report (Template C-4.20)
- [ ] Phase 1: Data layer report (Template C-4.20)
- [ ] Phase 2: Analysis layer report (Template C-4.20)
- [ ] Phase 3: CLI layer report (Template C-4.20)
- [ ] Phase 4: Integration layer report (Template C-4.20)
- [ ] Phase 5: Final comprehensive report (Template C-4.20)

### Acceptance Criteria

- [ ] All unit tests pass (15+ tests)
- [ ] All integration tests pass (4 tests)
- [ ] Coverage ≥90%
- [ ] `aud deadcode` command works
- [ ] `aud graph analyze --show-isolated` works
- [ ] Quality rule generates findings
- [ ] Manual test detects journal.py
- [ ] OpenSpec validation passes
- [ ] NO emojis in output
- [ ] NO fallback logic
- [ ] NO regex on file content
- [ ] Post-implementation audit complete

---

**Document Version**: 1.0
**Status**: READY FOR EXECUTION
**Team Protocol**: SOP v4.20 (Architect-Auditor-Coder Workflow)
**Estimated Total Time**: 6 hours (across 6 phases)
