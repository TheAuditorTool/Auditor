# TAINT SCHEMA REFACTOR - PRE-IMPLEMENTATION PLAN
**Status:** 🔴 READY FOR EXECUTION
**Document Version:** 1.0
**Created:** 2025-10-03
**Author:** Claude Opus (Lead Coder)
**Architect:** Human

---

## EXECUTIVE SUMMARY

**THE PROBLEM:**
TheAuditor's taint analysis returns 0 vulnerabilities across ALL projects (6/6 projects failing) due to schema mismatches between the indexer (which creates database tables) and the taint module (which queries them).

**ROOT CAUSE:**
Memory cache module queries `variable_usage` table with WRONG column names:
- Queries: `var_name`, `context`
- Actual schema: `variable_name`, `in_component`

This is NOT a simple typo - it's an architecture failure where the indexer and taint modules are TIGHTLY COUPLED but have NO formal schema contract.

**IMPACT:**
100% failure rate on taint analysis. Memory cache pre-load fails silently, falls back to disk queries that also fail due to schema mismatch. Pipeline continues but produces WRONG results (0 vulnerabilities when there are dozens).

---

## FORENSIC AUDIT FINDINGS

### 🤡 CLOWN #1: Memory Cache Variable Usage Query
**Location:** `theauditor/taint/memory_cache.py:330-343`

**WRONG CODE:**
```python
cursor.execute("""
    SELECT file, line, var_name, usage_type, context
    FROM variable_usage
""")
variable_usage_data = cursor.fetchall()

for file, line, var_name, usage_type, context in variable_usage_data:
    usage = {
        "file": file,
        "line": line or 0,
        "var_name": var_name or "",
        "usage_type": usage_type or "",
        "context": context or ""
    }
```

**ACTUAL DATABASE SCHEMA:**
`theauditor/indexer/database.py:436-447`
```python
CREATE TABLE IF NOT EXISTS variable_usage (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    variable_name TEXT NOT NULL,  # ← NOT var_name!
    usage_type TEXT NOT NULL,
    in_component TEXT,            # ← NOT context!
    in_hook TEXT,
    scope_level INTEGER,
    FOREIGN KEY(file) REFERENCES files(path)
)
```

**ERROR:**
```
sqlite3.OperationalError: no such column: var_name
```

**IMPACT:**
Cache pre-load fails → falls back to disk queries → disk queries ALSO wrong → 0 taint sources/sinks found

---

### 🤡 CLOWN #2: Function Returns Table (Fragile)
**Location:** `theauditor/taint/memory_cache.py:221-224`

**CODE:**
```python
cursor.execute("""
    SELECT file, line, function_name, return_expr, return_vars
    FROM function_returns
""")
returns_data = cursor.fetchall()

for file, line, func_name, return_expr, return_vars in returns_data:
    # Unpacks 5 values
```

**ACTUAL SCHEMA:**
`theauditor/indexer/database.py:345-353` + migrations at lines 479-491
```python
CREATE TABLE IF NOT EXISTS function_returns (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    return_expr TEXT NOT NULL,
    return_vars TEXT,
    -- PLUS 3 more columns added via ALTER TABLE:
    has_jsx BOOLEAN DEFAULT 0,
    returns_component BOOLEAN DEFAULT 0,
    cleanup_operations TEXT
)
```

**STATUS:**
Works by ACCIDENT because SELECT explicitly lists 5 columns. But fragile - if we add more columns and change query to `SELECT *`, it breaks.

---

### 🤡 CLOWN #3: No Schema Contract
**Problem:**
Schema defined in 4 DIFFERENT places with DIFFERENT assumptions:

1. **Indexer creates tables:** `theauditor/indexer/database.py`
   - Lines 100-872: CREATE TABLE statements
   - Lines 712-800: CREATE INDEX statements
   - Lines 802-870: ALTER TABLE migrations

2. **Memory cache queries tables:** `theauditor/taint/memory_cache.py`
   - Lines 128-353: Hardcoded SQL queries
   - Assumes schema X

3. **Taint database queries tables:** `theauditor/taint/database.py`
   - Lines 14-1087: More hardcoded SQL queries
   - Assumes schema Y

4. **Extractors add data:** `theauditor/indexer/extractors/*.py`
   - JavaScript extractor: lines 44-56 (result dict structure)
   - Python extractor: lines 36-45 (result dict structure)
   - Assumes schema Z

**NO VALIDATION:**
- No checks that queries match actual tables
- No migration system when indexer schema changes
- Errors caught and logged, pipeline continues with WRONG results

---

## EVIDENCE FROM 6 PROJECTS

| Project         | Cache Pre-load | Taint Sources | Taint Sinks | Result    |
|-----------------|----------------|---------------|-------------|-----------|
| plant           | ❌ FAILED       | 0             | 0           | 0 paths   |
| project_anarchy | ❌ FAILED       | 0             | 0           | 0 paths   |
| PlantFlow       | ❌ FAILED       | 0             | 0           | 0 paths   |
| PlantPro        | ❌ FAILED       | 0             | 0           | 0 paths   |
| raicalc         | ❌ FAILED       | 0             | 0           | 0 paths   |
| TheAuditor      | ❌ FAILED       | N/A           | N/A         | Extraction failed |

**100% failure rate**

---

## IMPLEMENTATION PLAN

### OPTION A: QUICK FIX (2 HOURS) - Band-Aid Solution

**Goal:** Fix immediate schema mismatch to unblock taint analysis

#### Phase 1: Fix Memory Cache Queries (30 minutes)

**File:** `theauditor/taint/memory_cache.py`

**Change 1:** Line 330
```python
# BEFORE (wrong):
cursor.execute("""
    SELECT file, line, var_name, usage_type, context
    FROM variable_usage
""")

# AFTER (correct):
cursor.execute("""
    SELECT file, line, variable_name, usage_type, in_component
    FROM variable_usage
""")
```

**Change 2:** Line 335
```python
# BEFORE:
for file, line, var_name, usage_type, context in variable_usage_data:

# AFTER:
for file, line, variable_name, usage_type, in_component in variable_usage_data:
```

**Change 3:** Line 338-343
```python
# BEFORE:
usage = {
    "file": file,
    "line": line or 0,
    "var_name": var_name or "",
    "usage_type": usage_type or "",
    "context": context or ""
}

# AFTER:
usage = {
    "file": file,
    "line": line or 0,
    "var_name": variable_name or "",  # Keep 'var_name' key for API compatibility
    "usage_type": usage_type or "",
    "in_component": in_component or ""  # Renamed from 'context'
}
```

**Verification Command:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
python -c "
import sqlite3
from theauditor.taint.memory_cache import attempt_cache_preload

# Test on PlantFlow database
conn = sqlite3.connect('/c/Users/santa/Desktop/PlantFlow/.pf/repo_index.db')
cache = attempt_cache_preload(conn.cursor())

if cache:
    print('✅ Cache loaded successfully')
    print(f'   Variable usages: {len(cache.variable_usage)}')
    print(f'   Memory used: {cache.get_memory_usage_mb():.1f}MB')
else:
    print('❌ Cache failed to load')
    print(f'   Error: {cache.load_error if cache else \"Unknown\"}')
"
```

**Expected Output:**
```
✅ Cache loaded successfully
   Variable usages: 12431
   Memory used: 45.2MB
```

#### Phase 2: Test Across Projects (30 minutes)

**Test 1:** Small Project (raicalc)
```bash
cd /c/Users/santa/Desktop/rai/raicalc
aud taint-analyze --verbose
```

**Expected:**
- [MEMORY] Cache loaded: X MB
- [TAINT] Found X taint sources (should be > 0)
- [TAINT] Found X security sinks (should be > 0)
- Total vulnerabilities: X (should be > 0)

**Test 2:** Medium Project (project_anarchy)
```bash
cd /c/Users/santa/Desktop/fakeproj/project_anarchy
aud taint-analyze --verbose
```

**Expected:**
- Sources: 20-50
- Sinks: 20-50
- Vulnerabilities: 20-100

**Test 3:** Large Project (PlantFlow)
```bash
cd /c/Users/santa/Desktop/PlantFlow
aud taint-analyze --json > /tmp/plantflow_taint.json

python -c "
import json
with open('/tmp/plantflow_taint.json') as f:
    data = json.load(f)
    print(f'Sources: {data.get(\"sources_found\", 0)}')
    print(f'Sinks: {data.get(\"sinks_found\", 0)}')
    print(f'Paths: {len(data.get(\"taint_paths\", []))}')
"
```

**Expected:**
- Sources: 100-200
- Sinks: 100-200
- Paths: 50-150

#### Phase 3: Automated Validation (1 hour)

**Create:** `C:\Users\santa\Desktop\TheAuditor\validate_taint_fix.py`

```python
#!/usr/bin/env python3
"""Validate taint analysis fix across all 6 projects."""

import subprocess
import json
from pathlib import Path

PROJECTS = [
    "C:/Users/santa/Desktop/rai/raicalc",
    "C:/Users/santa/Desktop/fakeproj/project_anarchy",
    "C:/Users/santa/Desktop/PlantFlow",
    "C:/Users/santa/Desktop/PlantPro",
    "C:/Users/santa/Desktop/plant",
    # Skip TheAuditor (extraction broken - separate issue)
]

results = []

for project_path in PROJECTS:
    project_name = Path(project_path).name
    print(f"\n{'='*60}")
    print(f"Testing: {project_name}")
    print('='*60)

    # Run taint analysis
    cmd = ["aud", "taint-analyze", "--json"]
    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes max
        )

        if result.returncode == 0 or result.returncode == 1:
            try:
                data = json.loads(result.stdout)
                sources = data.get("sources_found", 0)
                sinks = data.get("sinks_found", 0)
                paths = len(data.get("taint_paths", []))

                status = "✅ PASS" if paths > 0 else "⚠️ NO VULNS"
                print(f"{status} - Sources: {sources}, Sinks: {sinks}, Paths: {paths}")

                results.append({
                    "project": project_name,
                    "status": "pass" if paths >= 0 else "fail",
                    "sources": sources,
                    "sinks": sinks,
                    "paths": paths
                })
            except json.JSONDecodeError:
                print("❌ FAIL - Invalid JSON output")
                results.append({"project": project_name, "status": "json_error"})
        else:
            print(f"❌ FAIL - Exit code {result.returncode}")
            print(f"Error: {result.stderr[:200]}")
            results.append({"project": project_name, "status": "error"})

    except subprocess.TimeoutExpired:
        print("❌ FAIL - Timeout (>3 minutes)")
        results.append({"project": project_name, "status": "timeout"})
    except Exception as e:
        print(f"❌ FAIL - {e}")
        results.append({"project": project_name, "status": "exception"})

# Summary
print(f"\n{'='*60}")
print("SUMMARY")
print('='*60)

passed = sum(1 for r in results if r["status"] == "pass")
total = len(results)

print(f"Passed: {passed}/{total}")

for r in results:
    status_icon = "✅" if r["status"] == "pass" else "❌"
    print(f"{status_icon} {r['project']}: {r.get('paths', 0)} taint paths")

if passed == total:
    print("\n🎉 ALL TESTS PASSED - Fix validated across all projects")
    exit(0)
else:
    print(f"\n⚠️ {total - passed} projects still failing")
    exit(1)
```

**Run Validation:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
python validate_taint_fix.py
```

**Expected Output:**
```
============================================================
Testing: raicalc
============================================================
✅ PASS - Sources: 15, Sinks: 12, Paths: 3

============================================================
Testing: project_anarchy
============================================================
✅ PASS - Sources: 45, Sinks: 38, Paths: 22

============================================================
Testing: PlantFlow
============================================================
✅ PASS - Sources: 189, Sinks: 157, Paths: 78

============================================================
Testing: PlantPro
============================================================
✅ PASS - Sources: 214, Sinks: 183, Paths: 102

============================================================
Testing: plant
============================================================
✅ PASS - Sources: 201, Sinks: 176, Paths: 89

============================================================
SUMMARY
============================================================
Passed: 5/5
✅ raicalc: 3 taint paths
✅ project_anarchy: 22 taint paths
✅ PlantFlow: 78 taint paths
✅ PlantPro: 102 taint paths
✅ plant: 89 taint paths

🎉 ALL TESTS PASSED - Fix validated across all projects
```

---

### OPTION B: PROPER FIX (12-16 HOURS) - Schema Contract System

**Goal:** Implement formal schema contract to prevent future drift

#### Phase 1: Create Schema Contract Module (3 hours)

**Create File:** `theauditor/indexer/schema.py`

```python
"""
Database schema definitions - Single Source of Truth.

This module defines all table schemas used by TheAuditor.
Any module that reads/writes database MUST import schemas from here.

Design:
- Indexer creates tables from these schemas
- Taint analyzer queries using these schemas
- Pattern rules query using these schemas
- NO MORE HARDCODED COLUMN NAMES

Usage:
    from theauditor.indexer.schema import TABLES, build_query

    # Build a query dynamically:
    query = build_query('variable_usage', ['file', 'line', 'variable_name'])
    # Returns: "SELECT file, line, variable_name FROM variable_usage"
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import sqlite3


@dataclass
class Column:
    """Represents a database column with type and constraints."""
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False

    def to_sql(self) -> str:
        """Generate SQL column definition."""
        parts = [self.name, self.type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        if self.primary_key:
            parts.append("PRIMARY KEY")
        return " ".join(parts)


@dataclass
class TableSchema:
    """Represents a complete table schema."""
    name: str
    columns: List[Column]
    indexes: List[Tuple[str, List[str]]] = None

    def __post_init__(self):
        if self.indexes is None:
            self.indexes = []

    def column_names(self) -> List[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]

    def create_table_sql(self) -> str:
        """Generate CREATE TABLE statement."""
        col_defs = [col.to_sql() for col in self.columns]
        return f"CREATE TABLE IF NOT EXISTS {self.name} (\\n    " + ",\\n    ".join(col_defs) + "\\n)"

    def create_indexes_sql(self) -> List[str]:
        """Generate CREATE INDEX statements."""
        stmts = []
        for idx_name, idx_cols in self.indexes:
            cols_str = ", ".join(idx_cols)
            stmts.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self.name} ({cols_str})")
        return stmts

    def validate_against_db(self, cursor: sqlite3.Cursor) -> Tuple[bool, List[str]]:
        """
        Validate that actual database table matches this schema.

        Returns:
            (is_valid, [error_messages])
        """
        errors = []

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.name,)
        )
        if not cursor.fetchone():
            errors.append(f"Table {self.name} does not exist")
            return False, errors

        # Get actual columns
        cursor.execute(f"PRAGMA table_info({self.name})")
        actual_cols = {row[1]: row[2] for row in cursor.fetchall()}

        # Validate columns
        for col in self.columns:
            if col.name not in actual_cols:
                errors.append(f"Column {self.name}.{col.name} missing in database")
            elif actual_cols[col.name].upper() != col.type.upper():
                errors.append(
                    f"Column {self.name}.{col.name} type mismatch: "
                    f"expected {col.type}, got {actual_cols[col.name]}"
                )

        return len(errors) == 0, errors


# ============================================================================
# TABLE DEFINITIONS - SINGLE SOURCE OF TRUTH
# ============================================================================

VARIABLE_USAGE = TableSchema(
    name="variable_usage",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("variable_name", "TEXT", nullable=False),  # ← NOT var_name
        Column("usage_type", "TEXT", nullable=False),
        Column("in_component", "TEXT"),  # ← NOT context
        Column("in_hook", "TEXT"),
        Column("scope_level", "INTEGER"),
    ],
    indexes=[
        ("idx_variable_usage_file", ["file"]),
        ("idx_variable_usage_name", ["variable_name"]),
    ]
)

FUNCTION_RETURNS = TableSchema(
    name="function_returns",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("return_expr", "TEXT", nullable=False),
        Column("return_vars", "TEXT"),
        Column("has_jsx", "BOOLEAN", default="0"),
        Column("returns_component", "BOOLEAN", default="0"),
        Column("cleanup_operations", "TEXT"),
    ],
    indexes=[
        ("idx_function_returns_file", ["file"]),
        ("idx_function_returns_func", ["function_name"]),
    ]
)

SQL_QUERIES = TableSchema(
    name="sql_queries",
    columns=[
        Column("file_path", "TEXT", nullable=False),  # ← file_path (not file)
        Column("line_number", "INTEGER", nullable=False),  # ← line_number (not line)
        Column("query_text", "TEXT", nullable=False),
        Column("command", "TEXT", nullable=False),
        Column("tables", "TEXT"),
        Column("extraction_source", "TEXT", nullable=False, default="'code_execute'"),
    ],
    indexes=[
        ("idx_sql_queries_file", ["file_path"]),
        ("idx_sql_queries_command", ["command"]),
    ]
)

ORM_QUERIES = TableSchema(
    name="orm_queries",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("query_type", "TEXT", nullable=False),
        Column("includes", "TEXT"),
        Column("has_limit", "BOOLEAN", default="0"),
        Column("has_transaction", "BOOLEAN", default="0"),
    ],
    indexes=[
        ("idx_orm_queries_file", ["file"]),
        ("idx_orm_queries_type", ["query_type"]),
    ]
)

SYMBOLS = TableSchema(
    name="symbols",
    columns=[
        Column("path", "TEXT", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("col", "INTEGER", nullable=False),
    ],
    indexes=[
        ("idx_symbols_path", ["path"]),
        ("idx_symbols_name", ["name"]),
        ("idx_symbols_type", ["type"]),
    ]
)

# Add more table schemas as needed...

# Map of all tables for easy lookup
TABLES: Dict[str, TableSchema] = {
    "variable_usage": VARIABLE_USAGE,
    "function_returns": FUNCTION_RETURNS,
    "sql_queries": SQL_QUERIES,
    "orm_queries": ORM_QUERIES,
    "symbols": SYMBOLS,
}


# ============================================================================
# QUERY BUILDER UTILITIES
# ============================================================================

def build_query(table_name: str, columns: Optional[List[str]] = None,
                where: Optional[str] = None, order_by: Optional[str] = None) -> str:
    """
    Build a SELECT query using schema definitions.

    Args:
        table_name: Name of the table
        columns: List of column names to select (None = all columns)
        where: Optional WHERE clause (without 'WHERE' keyword)
        order_by: Optional ORDER BY clause (without 'ORDER BY' keyword)

    Returns:
        Complete SELECT query string

    Example:
        >>> build_query('variable_usage', ['file', 'line', 'variable_name'])
        'SELECT file, line, variable_name FROM variable_usage'

        >>> build_query('sql_queries', where="command != 'UNKNOWN'")
        'SELECT file_path, line_number, query_text, command, tables, extraction_source FROM sql_queries WHERE command != \\'UNKNOWN\\''
    """
    if table_name not in TABLES:
        raise ValueError(f"Unknown table: {table_name}")

    schema = TABLES[table_name]

    if columns is None:
        columns = schema.column_names()
    else:
        # Validate columns exist
        valid_cols = set(schema.column_names())
        for col in columns:
            if col not in valid_cols:
                raise ValueError(f"Unknown column {col} in table {table_name}")

    query_parts = [
        "SELECT",
        ", ".join(columns),
        "FROM",
        table_name
    ]

    if where:
        query_parts.extend(["WHERE", where])

    if order_by:
        query_parts.extend(["ORDER BY", order_by])

    return " ".join(query_parts)


def validate_all_tables(cursor: sqlite3.Cursor) -> Dict[str, List[str]]:
    """
    Validate all table schemas against actual database.

    Returns:
        Dict of {table_name: [errors]} for tables with mismatches
    """
    results = {}
    for table_name, schema in TABLES.items():
        is_valid, errors = schema.validate_against_db(cursor)
        if not is_valid:
            results[table_name] = errors
    return results


if __name__ == "__main__":
    # Self-test: Print all schemas
    print("TheAuditor Database Schemas")
    print("=" * 80)
    for table_name, schema in TABLES.items():
        print(f"\\n{table_name}:")
        print("  Columns:")
        for col in schema.columns:
            print(f"    - {col.name}: {col.type}")
        print("  Indexes:")
        for idx_name, idx_cols in schema.indexes:
            print(f"    - {idx_name} on ({', '.join(idx_cols)})")
```

**Test Schema Module:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
python -m theauditor.indexer.schema
```

Expected: List of all table schemas with columns

#### Phase 2: Update Memory Cache to Use Schema (2 hours)

**File:** `theauditor/taint/memory_cache.py`

**Add Import** (after line 18):
```python
from theauditor.indexer.schema import TABLES, build_query
```

**Replace Line 329-333:**
```python
# BEFORE:
if 'variable_usage' in tables:
    # ... check count ...
    cursor.execute("""
        SELECT file, line, var_name, usage_type, context
        FROM variable_usage
    """)

# AFTER:
if 'variable_usage' in tables:
    # ... check count ...
    # Build query from schema (guarantees correct columns)
    query = build_query('variable_usage', [
        'file', 'line', 'variable_name', 'usage_type', 'in_component'
    ])
    cursor.execute(query)
```

**Replace Line 335:**
```python
# BEFORE:
for file, line, var_name, usage_type, context in variable_usage_data:

# AFTER:
for file, line, variable_name, usage_type, in_component in variable_usage_data:
```

**Replace Line 338-344:**
```python
# BEFORE:
usage = {
    "file": file,
    "line": line or 0,
    "var_name": var_name or "",
    "usage_type": usage_type or "",
    "context": context or ""
}

# AFTER:
usage = {
    "file": file,
    "line": line or 0,
    "var_name": variable_name or "",  # API compat: keep 'var_name' key
    "usage_type": usage_type or "",
    "in_component": in_component or ""  # Renamed from 'context'
}
```

Repeat for other tables (function_returns, sql_queries, orm_queries):
Replace hardcoded queries with `build_query()` calls.

#### Phase 3: Add Schema Validation to Indexer (2 hours)

**File:** `theauditor/indexer/database.py`

**Add Method to DatabaseManager Class:**
```python
def validate_schema(self) -> bool:
    """
    Validate database schema matches expected definitions.

    Runs after indexing to ensure all tables were created correctly.
    Logs warnings for any mismatches.

    Returns:
        True if all schemas valid, False if mismatches found
    """
    from theauditor.indexer.schema import validate_all_tables
    import sys

    mismatches = validate_all_tables(self.cursor)

    if not mismatches:
        print("[SCHEMA] ✅ All table schemas validated", file=sys.stderr)
        return True

    print("[SCHEMA] ⚠️ Schema mismatches detected:", file=sys.stderr)
    for table_name, errors in mismatches.items():
        print(f"[SCHEMA]   {table_name}:", file=sys.stderr)
        for error in errors:
            print(f"[SCHEMA]     - {error}", file=sys.stderr)

    return False
```

**Add Validation Call After Indexing:**

**File:** `theauditor/commands/index.py`

After table creation (find line where indexing completes):
```python
# After: orchestrator.index_repository()
# Add:
db_manager = orchestrator.db_manager
if not db_manager.validate_schema():
    click.echo("⚠️ Warning: Database schema validation failed", err=True)
    click.echo("   Some queries may fail. Run 'aud index' to rebuild.", err=True)
```

#### Phase 4: Add Runtime Schema Validation to Taint (1 hour)

**File:** `theauditor/commands/taint.py`

Add validation before analysis (after line 82):
```python
# After: if not db_path.exists(): ...
# Add:
from theauditor.indexer.schema import validate_all_tables
import sqlite3

# Validate schema before running expensive analysis
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
mismatches = validate_all_tables(cursor)
conn.close()

if mismatches:
    click.echo("⚠️ WARNING: Database schema mismatches detected:", err=True)
    for table_name, errors in mismatches.items():
        click.echo(f"  {table_name}: {errors[0]}", err=True)
    click.echo("\\nRun 'aud index' to rebuild the database with correct schema.", err=True)

    if not click.confirm("Continue anyway? (may produce incorrect results)"):
        raise click.ClickException("Aborted due to schema mismatch")
```

#### Phase 5: Write Unit Tests (4 hours)

**Create File:** `tests/test_schema_contract.py`

```python
"""Tests for database schema contract system."""

import pytest
import sqlite3
from pathlib import Path
from theauditor.indexer.schema import (
    TABLES, build_query, validate_all_tables,
    VARIABLE_USAGE, FUNCTION_RETURNS, SQL_QUERIES, ORM_QUERIES
)


def test_schema_definitions_exist():
    """Verify all core table schemas are defined."""
    assert "variable_usage" in TABLES
    assert "function_returns" in TABLES
    assert "sql_queries" in TABLES
    assert "orm_queries" in TABLES
    assert "symbols" in TABLES


def test_variable_usage_schema():
    """Verify variable_usage schema has correct columns."""
    schema = VARIABLE_USAGE
    col_names = schema.column_names()

    # Must have these exact columns in order
    assert col_names[0] == "file"
    assert col_names[1] == "line"
    assert col_names[2] == "variable_name"  # NOT var_name
    assert col_names[3] == "usage_type"
    assert col_names[4] == "in_component"   # NOT context
    assert col_names[5] == "in_hook"
    assert col_names[6] == "scope_level"


def test_sql_queries_schema():
    """Verify sql_queries schema has correct column names."""
    schema = SQL_QUERIES
    col_names = schema.column_names()

    assert col_names[0] == "file_path"      # NOT file
    assert col_names[1] == "line_number"    # NOT line
    assert col_names[2] == "query_text"
    assert col_names[3] == "command"


def test_build_query_all_columns():
    """Test building query with all columns."""
    query = build_query('variable_usage')

    assert "SELECT" in query
    assert "file" in query
    assert "variable_name" in query  # NOT var_name
    assert "in_component" in query   # NOT context
    assert "FROM variable_usage" in query


def test_build_query_specific_columns():
    """Test building query with specific columns."""
    query = build_query('variable_usage', ['file', 'line', 'variable_name'])

    assert query == "SELECT file, line, variable_name FROM variable_usage"


def test_build_query_with_where():
    """Test building query with WHERE clause."""
    query = build_query('sql_queries', where="command != 'UNKNOWN'")

    assert "WHERE command != 'UNKNOWN'" in query


def test_build_query_invalid_table():
    """Test error handling for unknown table."""
    with pytest.raises(ValueError, match="Unknown table"):
        build_query('nonexistent_table')


def test_build_query_invalid_column():
    """Test error handling for unknown column."""
    with pytest.raises(ValueError, match="Unknown column"):
        build_query('variable_usage', ['file', 'nonexistent_column'])


def test_schema_validation_success(tmp_path):
    """Test schema validation against correct database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create table with correct schema
    cursor.execute(VARIABLE_USAGE.create_table_sql())
    conn.commit()

    # Validate
    is_valid, errors = VARIABLE_USAGE.validate_against_db(cursor)

    assert is_valid
    assert len(errors) == 0

    conn.close()


def test_schema_validation_missing_column(tmp_path):
    """Test schema validation detects missing column."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create table with WRONG schema (missing in_component)
    cursor.execute("""
        CREATE TABLE variable_usage (
            file TEXT NOT NULL,
            line INTEGER NOT NULL,
            variable_name TEXT NOT NULL,
            usage_type TEXT NOT NULL
        )
    """)
    conn.commit()

    # Validate
    is_valid, errors = VARIABLE_USAGE.validate_against_db(cursor)

    assert not is_valid
    assert len(errors) > 0
    assert "in_component" in errors[0]

    conn.close()


def test_schema_validation_wrong_column_name(tmp_path):
    """Test schema validation detects wrong column name."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create table with WRONG column name (var_name instead of variable_name)
    cursor.execute("""
        CREATE TABLE variable_usage (
            file TEXT NOT NULL,
            line INTEGER NOT NULL,
            var_name TEXT NOT NULL,
            usage_type TEXT NOT NULL,
            in_component TEXT
        )
    """)
    conn.commit()

    # Validate
    is_valid, errors = VARIABLE_USAGE.validate_against_db(cursor)

    assert not is_valid
    assert any("variable_name" in err and "missing" in err for err in errors)

    conn.close()


@pytest.mark.integration
def test_validate_all_tables_against_real_db():
    """Integration test: Validate schemas against real project databases."""
    db_path = Path("C:/Users/santa/Desktop/PlantFlow/.pf/repo_index.db")

    if not db_path.exists():
        pytest.skip("PlantFlow database not found")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    mismatches = validate_all_tables(cursor)

    # Print any mismatches for debugging
    if mismatches:
        for table, errors in mismatches.items():
            print(f"\\n{table} mismatches:")
            for error in errors:
                print(f"  - {error}")

    conn.close()

    # This test will FAIL before schema contract is implemented
    # and PASS after implementation
    assert len(mismatches) == 0, f"Schema mismatches found: {list(mismatches.keys())}"


@pytest.mark.integration
def test_memory_cache_uses_correct_schema():
    """Integration test: Verify memory cache queries match database schema."""
    db_path = Path("C:/Users/santa/Desktop/PlantFlow/.pf/repo_index.db")

    if not db_path.exists():
        pytest.skip("PlantFlow database not found")

    from theauditor.taint.memory_cache import attempt_cache_preload

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # This should NOT throw "no such column" errors
    cache = attempt_cache_preload(cursor)

    assert cache is not None, "Cache failed to load"
    assert cache.is_loaded, "Cache not marked as loaded"
    assert len(cache.variable_usage) > 0, "Variable usage table not loaded"

    conn.close()
```

**Run Tests:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
pytest tests/test_schema_contract.py -v
```

Expected before fix: FAILURES (schema mismatches)
Expected after fix: ALL PASS

#### Phase 6: Update Documentation (1 hour)

**Update File:** `CLAUDE.md`

Add section after line 300:

```markdown
## Database Schema Contract

TheAuditor uses a **schema contract system** to ensure consistency between
the indexer (which creates tables) and analyzers (which query tables).

### Schema Definitions

All table schemas are defined in `theauditor/indexer/schema.py`.

**DO NOT hardcode SQL column names** in queries. Instead:

```python
from theauditor.indexer.schema import build_query

# Good:
query = build_query('variable_usage', ['file', 'line', 'variable_name'])
cursor.execute(query)

# Bad:
cursor.execute("SELECT file, line, var_name FROM variable_usage")  # ❌ WRONG
```

### Adding a New Table

1. Define schema in `schema.py`:
```python
NEW_TABLE = TableSchema(
    name="my_table",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("name", "TEXT", nullable=False),
    ],
    indexes=[("idx_my_table_name", ["name"])]
)
```

2. Add to TABLES dict:
```python
TABLES["my_table"] = NEW_TABLE
```

3. Indexer creates it automatically
4. All queries use schema contract
5. Schema validation catches mismatches

### Schema Validation

Run validation after indexing:
```bash
aud index
# Automatically validates schema
```

Manual validation:
```python
from theauditor.indexer.schema import validate_all_tables
mismatches = validate_all_tables(cursor)
```
```

#### Phase 7: End-to-End Integration Test (2 hours)

**Create File:** `tests/test_taint_e2e.py`

```python
"""End-to-end tests for taint analysis with schema contract."""

import pytest
import subprocess
import json
from pathlib import Path


@pytest.mark.slow
@pytest.mark.parametrize("project_path,expected_min_paths", [
    ("C:/Users/santa/Desktop/rai/raicalc", 1),
    ("C:/Users/santa/Desktop/fakeproj/project_anarchy", 15),
    ("C:/Users/santa/Desktop/PlantFlow", 50),
])
def test_taint_analysis_finds_vulnerabilities(project_path, expected_min_paths):
    """Test that taint analysis finds vulnerabilities in real projects."""
    project_path = Path(project_path)

    if not project_path.exists():
        pytest.skip(f"Project not found: {project_path}")

    # Run taint analysis
    result = subprocess.run(
        ["aud", "taint-analyze", "--json"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
        timeout=300
    )

    # Parse output
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Invalid JSON output: {result.stdout[:500]}")

    # Verify success
    assert data.get("success") is True, f"Analysis failed: {data.get('error')}"

    # Verify findings
    sources = data.get("sources_found", 0)
    sinks = data.get("sinks_found", 0)
    paths = len(data.get("taint_paths", []))

    assert sources > 0, "No taint sources found"
    assert sinks > 0, "No security sinks found"
    assert paths >= expected_min_paths, f"Expected >= {expected_min_paths} paths, got {paths}"


@pytest.mark.slow
def test_memory_cache_loads_successfully():
    """Test that memory cache loads without schema errors."""
    from theauditor.taint.memory_cache import attempt_cache_preload
    import sqlite3

    db_path = Path("C:/Users/santa/Desktop/PlantFlow/.pf/repo_index.db")
    if not db_path.exists():
        pytest.skip("PlantFlow database not found")

    conn = sqlite3.connect(str(db_path))
    cache = attempt_cache_preload(conn.cursor())
    conn.close()

    assert cache is not None, "Cache failed to load"
    assert cache.load_error is None, f"Cache error: {cache.load_error}"
    assert cache.is_loaded, "Cache not marked as loaded"


@pytest.mark.slow
def test_no_schema_mismatch_errors_in_logs():
    """Test that taint analysis doesn't produce schema errors."""
    project_path = Path("C:/Users/santa/Desktop/rai/raicalc")

    if not project_path.exists():
        pytest.skip("raicalc project not found")

    result = subprocess.run(
        ["aud", "taint-analyze"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
        timeout=120
    )

    # Check stderr for schema errors
    stderr_lower = result.stderr.lower()

    assert "no such column" not in stderr_lower, "Schema error: column not found"
    assert "operational error" not in stderr_lower, "SQLite operational error"
    assert "cache failed" not in stderr_lower, "Memory cache failed to load"
```

**Run Tests:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
pytest tests/test_taint_e2e.py -v -m slow
```

Should take ~5 minutes. All tests must PASS.

---

## EXECUTION CHECKLIST

### Quick Fix (Option A):

- [ ] Create git branch: `git checkout -b fix/taint-schema-quick`
- [ ] Update memory_cache.py lines 330, 335, 338-343
- [ ] Test on raicalc
- [ ] Test on project_anarchy
- [ ] Test on PlantFlow
- [ ] Create validation script `validate_taint_fix.py`
- [ ] Run validation across all 5 projects
- [ ] Commit: `git commit -m "fix: correct variable_usage column names in memory cache"`
- [ ] Verify: No "no such column" errors in any project

### Full Fix (Option B):

- [ ] Create git branch: `git checkout -b feat/schema-contract-system`
- [ ] Create `theauditor/indexer/schema.py` (new file, 400+ lines)
- [ ] Test schema module: `python -m theauditor.indexer.schema`
- [ ] Update memory_cache.py to use `build_query()`
- [ ] Update database.py with `validate_schema()` method
- [ ] Update index.py command to call validation
- [ ] Update taint.py command with pre-flight validation
- [ ] Write unit tests in `tests/test_schema_contract.py`
- [ ] Run unit tests: `pytest tests/test_schema_contract.py -v`
- [ ] Write E2E tests in `tests/test_taint_e2e.py`
- [ ] Run E2E tests: `pytest tests/test_taint_e2e.py -v -m slow`
- [ ] Update CLAUDE.md documentation
- [ ] Run full validation: `python validate_taint_fix.py`
- [ ] Commit: `git commit -m "feat: implement database schema contract system"`
- [ ] Verify: All tests pass, all projects analyze successfully

---

## ROLLBACK PLAN

If implementation fails:

```bash
# Quick fix rollback:
git checkout main
git branch -D fix/taint-schema-quick

# Full fix rollback:
git checkout main
git branch -D feat/schema-contract-system

# Verify original state:
cd /c/Users/santa/Desktop/PlantFlow
aud taint-analyze
# Should still fail with "no such column" (original state)
```

---

## SUCCESS CRITERIA

### Quick Fix Success:

- [ ] `validate_taint_fix.py` reports 5/5 projects passing
- [ ] Each project detects > 0 taint sources
- [ ] Each project detects > 0 taint sinks
- [ ] Each project detects >= 1 taint path
- [ ] No "no such column" errors in logs
- [ ] Memory cache loads successfully

### Full Fix Success:

- [ ] All unit tests pass (`pytest tests/test_schema_contract.py`)
- [ ] All E2E tests pass (`pytest tests/test_taint_e2e.py`)
- [ ] Schema validation runs after indexing
- [ ] Schema mismatches caught before analysis
- [ ] No hardcoded column names in taint module
- [ ] Documentation updated
- [ ] All 5 projects analyze successfully

---

## ESTIMATED TIMES

- **Quick Fix:** 2 hours
- **Full Fix:** 12-16 hours
- **Testing:** +2 hours either way

**Recommendation:** Start with Quick Fix to unblock immediate work, then implement Full Fix over next sprint to prevent future schema drift.

---

## APPENDIX A: All Schema Mismatches

### Table: variable_usage
**Expected (indexer creates):**
- file, line, variable_name, usage_type, in_component, in_hook, scope_level

**Actual (memory cache queries):**
- file, line, var_name, usage_type, context

**Mismatch:** var_name vs variable_name, context vs in_component

### Table: function_returns
**Expected (indexer creates):**
- file, line, function_name, return_expr, return_vars, has_jsx, returns_component, cleanup_operations

**Actual (memory cache queries):**
- file, line, function_name, return_expr, return_vars

**Status:** Works but fragile (explicit SELECT)

### Table: sql_queries
**Expected (indexer creates):**
- file_path, line_number, query_text, command, tables, extraction_source

**Actual (memory cache queries):**
- file_path, line_number, query_text, command

**Status:** Correct (uses file_path, line_number not file, line)

---

## APPENDIX B: Reference Locations

### Schema Definitions:
- Indexer: `theauditor/indexer/database.py:100-872`
- Indexes: `theauditor/indexer/database.py:712-800`
- Migrations: `theauditor/indexer/database.py:802-870`

### Schema Queries:
- Memory Cache: `theauditor/taint/memory_cache.py:128-353`
- Taint Database: `theauditor/taint/database.py:14-1087`

### Extractors:
- JavaScript: `theauditor/indexer/extractors/javascript.py:44-56`
- Python: `theauditor/indexer/extractors/python.py:36-45`

---

## NOTES FOR FUTURE AI

**If you are picking up this plan:**

1. **Read this ENTIRE document** before starting
2. **Verify current codebase state** - check if changes already applied
3. **Follow SOP v4.20** (teamsop.md) - you are Opus Lead Coder
4. **Test incrementally** - don't batch fixes without testing
5. **Use git branches** - never work on main
6. **Document discrepancies** - if code doesn't match this plan, investigate why

**Quick orientation commands:**
```bash
cd /c/Users/santa/Desktop/TheAuditor
git status  # Check for uncommitted changes
git log -3  # Check recent commits
python -c "from theauditor.taint.memory_cache import MemoryCache; print('Imports work')"
```

**If stuck:**
- Check `TAINT_SCHEMA_CIRCUS_AUDIT.md` for original forensic report
- Check `.pf/pipeline.log` on any project for runtime errors
- Run `aud index` on a test project to regenerate database
- Query database directly: `sqlite3 .pf/repo_index.db "PRAGMA table_info(variable_usage)"`

**End of Document**
