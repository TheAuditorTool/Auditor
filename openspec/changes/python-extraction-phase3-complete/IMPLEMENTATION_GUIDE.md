# Python Extraction - IRONCLAD IMPLEMENTATION GUIDE

**Version**: 1.0
**Date**: 2025-11-01
**Audience**: Any AI starting fresh with ZERO context
**Pass Condition**: Read this → Immediately code new extractors

---

## TABLE OF CONTENTS

1. [Quick Start](#quick-start) - Start here
2. [Architecture Overview](#architecture-overview) - How it works
3. [Adding a New Extractor](#adding-a-new-extractor) - Step-by-step
4. [API Reference](#api-reference) - Exact signatures
5. [Verification](#verification) - How to test
6. [Troubleshooting](#troubleshooting) - Common issues
7. [Examples](#examples) - Real code

---

## QUICK START

**What is this?** TheAuditor extracts patterns from Python code and stores them in SQLite for security analysis.

**Where are you?** The `python/` extractor package processes Python AST nodes and returns structured data.

**What you'll do**:
1. Write an `extract_X()` function that walks AST
2. Add table schema for data
3. Add database writer method
4. Wire extractor into indexer
5. Wire storage into indexer
6. Test with fixture

**Time to first extraction**: 30-45 minutes

---

## ARCHITECTURE OVERVIEW

### The 5-Layer Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: EXTRACTOR                                              │
│ theauditor/ast_extractors/python/framework_extractors.py        │
│                                                                  │
│ def extract_celery_tasks(tree: Dict, parser_self) ->            │
│     List[Dict[str, Any]]:                                       │
│     """Walk AST, return list of dicts"""                        │
│     return [{'task_name': 'foo', 'line': 10, ...}]             │
└────────────────────┬────────────────────────────────────────────┘
                     │ Called by
┌────────────────────▼────────────────────────────────────────────┐
│ Layer 2: INDEXER EXTRACTOR                                      │
│ theauditor/indexer/extractors/python.py                         │
│                                                                  │
│ result['python_celery_tasks'] = []                              │
│ celery_tasks = python_impl.extract_celery_tasks(tree, parser)  │
│ result['python_celery_tasks'].extend(celery_tasks)             │
└────────────────────┬────────────────────────────────────────────┘
                     │ Passes to
┌────────────────────▼────────────────────────────────────────────┐
│ Layer 3: STORAGE                                                 │
│ theauditor/indexer/storage.py                                   │
│                                                                  │
│ def _store_python_celery_tasks(file_path, tasks):              │
│     for task in tasks:                                          │
│         db_manager.add_python_celery_task(file_path, ...)      │
└────────────────────┬────────────────────────────────────────────┘
                     │ Calls
┌────────────────────▼────────────────────────────────────────────┐
│ Layer 4: DATABASE WRITER                                         │
│ theauditor/indexer/database/python_database.py                  │
│                                                                  │
│ def add_python_celery_task(self, file_path, line, ...):        │
│     self.generic_batches['python_celery_tasks'].append(...)    │
└────────────────────┬────────────────────────────────────────────┘
                     │ Batch commits to
┌────────────────────▼────────────────────────────────────────────┐
│ Layer 5: DATABASE SCHEMA                                         │
│ theauditor/indexer/schemas/python_schema.py                     │
│                                                                  │
│ PYTHON_CELERY_TASKS = TableSchema(                              │
│     name="python_celery_tasks",                                 │
│     columns=[Column("file", "TEXT"), ...]                       │
│ )                                                                │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Python File → AST Parser → extract_X() → [dicts] → Indexer → Storage → Database Writer → SQLite
```

---

## ADDING A NEW EXTRACTOR

### Step 1: Write the Extractor Function

**Location**: `theauditor/ast_extractors/python/framework_extractors.py` (or `core_extractors.py`, `async_extractors.py`, etc.)

**Template**:
```python
def extract_python_my_pattern(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract my custom pattern from Python AST.

    Args:
        tree: Dict with "tree" key containing ast.Module
        parser_self: AST parser instance (has helper methods)

    Returns:
        List of dicts, one per found pattern
        Each dict MUST contain 'line' key (integer)
        Each dict can contain any other keys (str, int, bool, None only)
    """
    results = []

    # Get actual AST
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return results

    # Walk AST nodes
    for node in ast.walk(actual_tree):
        # Filter to relevant nodes
        if isinstance(node, ast.FunctionDef):
            # Check for your pattern
            if has_my_pattern(node):
                results.append({
                    'line': node.lineno,
                    'name': node.name,
                    'pattern_specific_data': extract_specific(node)
                })

    return results
```

**Critical Rules**:
1. **Signature MUST match**: `(tree: Dict, parser_self) -> List[Dict[str, Any]]`
2. **First line MUST be**: `actual_tree = tree.get("tree")`
3. **Always check**: `if not isinstance(actual_tree, ast.AST): return results`
4. **Return empty list**, not None
5. **Each dict MUST have `line` key** (integer)
6. **Only primitive types**: str, int, bool, None (no lists/dicts in values)

### Step 2: Export from Package

**Location**: `theauditor/ast_extractors/python/__init__.py`

**Add two lines**:
```python
# Near line 100 (imports)
from .framework_extractors import (
    # ... existing imports ...
    extract_python_my_pattern,  # ADD THIS
)

# Near line 180 (exports)
__all__ = [
    # ... existing exports ...
    'extract_python_my_pattern',  # ADD THIS
]
```

### Step 3: Define Database Schema

**Location**: `theauditor/indexer/schemas/python_schema.py`

**Add schema definition**:
```python
PYTHON_MY_PATTERN = TableSchema(
    name="python_my_pattern",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("pattern_specific_data", "TEXT"),  # Use TEXT for optional strings
    ],
    primary_key=["file", "line", "name"],  # Unique identifier
    indexes=[
        ("idx_python_my_pattern_file", ["file"]),
        ("idx_python_my_pattern_name", ["name"]),
    ]
)
```

**Register in PYTHON_TABLES dict** (bottom of file):
```python
PYTHON_TABLES: Dict[str, TableSchema] = {
    # ... existing tables ...
    "python_my_pattern": PYTHON_MY_PATTERN,  # ADD THIS
}
```

**Column Types**:
- `"TEXT"` - Strings (nullable by default)
- `"INTEGER"` - Integers (nullable by default)
- `"BOOLEAN"` - Booleans (stored as 0/1)
- Add `nullable=False` to require values
- Add `default="..."` for defaults

### Step 4: Add Database Writer

**Location**: `theauditor/indexer/database/python_database.py`

**Add writer method**:
```python
def add_python_my_pattern(self, file_path: str, line: int, name: str, pattern_specific_data: str):
    """Add my pattern to the batch."""
    self.generic_batches['python_my_pattern'].append((
        file_path,
        line,
        name,
        pattern_specific_data  # nullable
    ))
```

**Critical Rules**:
1. **Method name**: `add_python_{table_name}`
2. **First param**: Always `file_path: str`
3. **Append tuple**: Order MUST match schema column order exactly
4. **Boolean conversion**: Use `1 if flag else 0` for booleans
5. **Nullable fields**: Pass None or the value (no conversion needed)

### Step 5: Wire Extractor into Indexer

**Location**: `theauditor/indexer/extractors/python.py`

**Step 5a: Initialize result dict** (around line 50-110):
```python
result = {
    # ... existing keys ...
    'python_my_pattern': [],  # ADD THIS
}
```

**Step 5b: Call extractor** (around line 265-290):
```python
# My Pattern
my_patterns = python_impl.extract_python_my_pattern(tree, self.ast_parser)
if my_patterns:
    result['python_my_pattern'].extend(my_patterns)
```

### Step 6: Wire Storage Logic

**Location**: `theauditor/indexer/storage.py`

**Step 6a: Register handler** (around line 50-100):
```python
self.field_handlers = {
    # ... existing handlers ...
    'python_my_pattern': self._store_python_my_pattern,  # ADD THIS
}
```

**Step 6b: Implement storage method** (around line 800-900):
```python
def _store_python_my_pattern(self, file_path: str, python_my_pattern: List, jsx_pass: bool):
    """Store my custom pattern."""
    for pattern in python_my_pattern:
        self.db_manager.add_python_my_pattern(
            file_path,
            pattern.get('line', 0),
            pattern.get('name', ''),
            pattern.get('pattern_specific_data')
        )
        if 'python_my_pattern' not in self.counts:
            self.counts['python_my_pattern'] = 0
        self.counts['python_my_pattern'] += 1
```

**Critical Rules**:
1. **Method name**: `_store_python_{table_name}`
2. **Signature**: `(self, file_path: str, python_X: List, jsx_pass: bool)`
3. **Call db_manager**: Pass file_path as first arg
4. **Use .get()**: Always use dict.get() with defaults
5. **Count tracking**: Initialize counts dict if missing

### Step 7: Create Test Fixture

**Location**: `tests/fixtures/python/realworld_project/my_patterns.py`

**Create example file**:
```python
"""Test fixtures for my_pattern extraction."""

# Example 1: Basic pattern
def my_basic_pattern():
    """Basic usage of the pattern."""
    pass

# Example 2: Complex pattern
class MyClass:
    @my_decorator
    def my_complex_pattern(self):
        """Complex usage."""
        pass

# Example 3: Edge case
def my_edge_case():
    """Edge case that should be handled."""
    pass
```

**Critical Rules**:
1. **Comprehensive coverage**: Cover all pattern variations
2. **Edge cases**: Include edge cases that might break
3. **Security patterns**: Include vulnerable and secure examples
4. **Comments**: Explain what each example tests

### Step 8: Verify Extraction

**Run indexing**:
```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

**Query results**:
```bash
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
count = c.execute('SELECT COUNT(*) FROM python_my_pattern').fetchone()[0]
print(f'python_my_pattern: {count} records')

# Show sample records
c.execute('SELECT * FROM python_my_pattern LIMIT 5')
for row in c.fetchall():
    print(row)
conn.close()
"
```

**Expected**: Non-zero count, sensible data

---

## API REFERENCE

### Extractor Function Signature

```python
def extract_X(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """
    Args:
        tree: Dict with "tree" key containing ast.Module
              Example: {'tree': <ast.Module object>}

        parser_self: AST parser instance
                     Has helper methods like get_node_name()

    Returns:
        List of dicts representing found patterns
        Each dict represents ONE occurrence

        Required keys:
        - 'line': int (line number, REQUIRED)

        Optional keys:
        - Any string, int, bool, or None values
        - NO nested lists/dicts
        - NO objects

    Example return:
        [
            {'line': 10, 'name': 'foo', 'has_decorator': True},
            {'line': 25, 'name': 'bar', 'has_decorator': False}
        ]
    """
```

### Database Writer Signature

```python
def add_python_X(self, file_path: str, <schema_columns>):
    """
    Args:
        file_path: Absolute path to source file (provided by storage layer)
        <schema_columns>: One parameter per schema column (excluding file)
                          Order MUST match schema definition

    Returns:
        None (side effect: appends to batch)

    Example:
        def add_python_celery_task(self, file_path: str, line: int, task_name: str,
                                   decorator_name: str, arg_count: int, ...):
            self.generic_batches['python_celery_tasks'].append((
                file_path, line, task_name, decorator_name, arg_count, ...
            ))
    """
```

### Storage Method Signature

```python
def _store_python_X(self, file_path: str, python_X: List, jsx_pass: bool):
    """
    Args:
        file_path: Absolute path to source file
        python_X: List of dicts from extractor (result['python_X'])
        jsx_pass: Boolean flag (always False for Python, ignore it)

    Returns:
        None (side effect: calls db_manager, updates counts)

    Pattern:
        for item in python_X:
            self.db_manager.add_python_X(
                file_path,
                item.get('line', 0),
                item.get('field1', ''),
                item.get('field2')  # nullable
            )
            if 'python_X' not in self.counts:
                self.counts['python_X'] = 0
            self.counts['python_X'] += 1
    """
```

### Schema Definition

```python
TableSchema(
    name: str,              # Table name (lowercase, underscore_separated)
    columns: List[Column],  # List of Column objects
    primary_key: List[str], # Column names forming unique identifier
    indexes: List[Tuple],   # (index_name, [columns]) tuples
)

Column(
    name: str,              # Column name
    type: str,              # "TEXT", "INTEGER", "BOOLEAN"
    nullable: bool,         # Default: True
    default: str,           # Default value (as SQL string)
)
```

---

## VERIFICATION

### Method 1: Direct Testing (Fast)

Test extractor function directly:

```python
cd C:/Users/santa/Desktop/TheAuditor
.venv/Scripts/python.exe -c "
from theauditor.ast_extractors.python import framework_extractors
import ast

code = '''
from celery import shared_task

@shared_task(max_retries=3)
def process_order(order_id):
    pass
'''

tree_dict = {'tree': ast.parse(code)}
result = framework_extractors.extract_celery_tasks(tree_dict, None)
print(f'Found {len(result)} tasks')
if result:
    print(f'Task: {result[0]}')
"
```

**Expected**: Non-empty list with correct structure

### Method 2: Full Pipeline (Comprehensive)

Run full extraction:

```bash
cd C:/Users/santa/Desktop/TheAuditor

# Index entire project
aud index

# Query specific table
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Count records
count = c.execute('SELECT COUNT(*) FROM python_my_pattern').fetchone()[0]
print(f'Records: {count}')

# Show samples
c.execute('SELECT * FROM python_my_pattern LIMIT 5')
for row in c.fetchall():
    print(row)

conn.close()
"
```

**Expected**:
- Non-zero count from test fixtures
- Data matches fixture patterns
- No NULL values in non-nullable columns

### Method 3: Historical Database (Verification)

Check if your pattern exists in verified database:

```bash
cd C:/Users/santa/Desktop/TheAuditor

# Check most recent verified database
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/history/full/20251101_034938/repo_index.db')
c = conn.cursor()

# List Python tables
c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'python_%' ORDER BY name\")
tables = [row[0] for row in c.fetchall()]

print(f'Python tables: {len(tables)}')
for table in tables:
    count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    if count > 0:
        print(f'  {table}: {count}')

conn.close()
"
```

**Expected**: Your new table appears with non-zero count

---

## TROUBLESHOOTING

### Problem: "AttributeError: 'Module' object has no attribute 'get'"

**Cause**: Passed `ast.Module` directly instead of `{'tree': ast.Module}`

**Fix**: Always wrap AST in dict:
```python
tree_dict = {'tree': ast.parse(code)}  # Correct
result = extract_X(tree_dict, None)

# NOT:
result = extract_X(ast.parse(code), None)  # Wrong
```

### Problem: "Table does not exist"

**Cause**: Schema not registered or database not rebuilt

**Fix**:
1. Check schema registration in `python_schema.py` PYTHON_TABLES dict
2. Delete database: `rm .pf/repo_index.db`
3. Rebuild: `aud index`

### Problem: "Zero records extracted"

**Cause**: Extractor not wired or pattern not matching

**Debug**:
```python
# Test extractor directly
result = extract_my_pattern(tree_dict, None)
print(f'Extractor returned: {result}')

# Check if wired in indexer
grep "my_pattern" theauditor/indexer/extractors/python.py

# Check if wired in storage
grep "my_pattern" theauditor/indexer/storage.py
```

### Problem: "Column count mismatch"

**Cause**: Database writer tuple doesn't match schema columns

**Fix**: Count columns in schema, count tuple elements, ensure exact match:
```python
# Schema has 5 columns: file, line, name, type, flag
# Tuple must have 5 elements:
self.generic_batches['table'].append((
    file_path,  # 1
    line,       # 2
    name,       # 3
    type,       # 4
    1 if flag else 0  # 5
))
```

### Problem: "Windows file modification bug"

**Symptom**: "File unexpectedly modified" errors

**Fix**: Use absolute Windows paths with backslashes:
```python
# Correct
file_path = "C:\\Users\\santa\\Desktop\\TheAuditor\\file.py"

# Wrong
file_path = "C:/Users/santa/Desktop/TheAuditor/file.py"  # Forward slashes
file_path = "file.py"  # Relative
```

---

## EXAMPLES

### Example 1: Simple Pattern (Decorators)

**Extractor** (`core_extractors.py:78`):
```python
def extract_python_decorators(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    decorators = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return decorators

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                decorator_name = get_node_name(dec)
                decorators.append({
                    'line': dec.lineno,
                    'decorator_name': decorator_name,
                    'target_name': node.name,
                    'target_type': 'function' if isinstance(node, ast.FunctionDef) else 'class'
                })

    return decorators
```

**Schema** (`python_schema.py:150`):
```python
PYTHON_DECORATORS = TableSchema(
    name="python_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("target_name", "TEXT", nullable=False),
        Column("target_type", "TEXT", nullable=False),
    ],
    primary_key=["file", "line", "decorator_name", "target_name"],
    indexes=[
        ("idx_python_decorators_file", ["file"]),
        ("idx_python_decorators_name", ["decorator_name"]),
    ]
)
```

**Database Writer** (`python_database.py:150`):
```python
def add_python_decorator(self, file_path: str, line: int, decorator_name: str,
                         target_name: str, target_type: str):
    self.generic_batches['python_decorators'].append((
        file_path, line, decorator_name, target_name, target_type
    ))
```

**Storage** (`storage.py:550`):
```python
def _store_python_decorators(self, file_path: str, python_decorators: List, jsx_pass: bool):
    for decorator in python_decorators:
        self.db_manager.add_python_decorator(
            file_path,
            decorator.get('line', 0),
            decorator.get('decorator_name', ''),
            decorator.get('target_name', ''),
            decorator.get('target_type', 'function')
        )
        if 'python_decorators' not in self.counts:
            self.counts['python_decorators'] = 0
        self.counts['python_decorators'] += 1
```

### Example 2: Complex Pattern (Celery Tasks)

**Extractor** (`framework_extractors.py:1641`, simplified):
```python
def extract_celery_tasks(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    tasks = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return tasks

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators
        for decorator in node.decorator_list:
            if is_celery_decorator(decorator):
                # Extract security parameters
                serializer = extract_kwarg(decorator, 'serializer')
                max_retries = extract_kwarg(decorator, 'max_retries')
                rate_limit = extract_kwarg(decorator, 'rate_limit')

                tasks.append({
                    'line': node.lineno,
                    'task_name': node.name,
                    'arg_count': len(node.args.args),
                    'serializer': serializer,
                    'max_retries': max_retries,
                    'rate_limit': rate_limit
                })

    return tasks
```

**Key Pattern**: Extract security-relevant metadata from decorator arguments

### Example 3: Relationship Pattern (Django Forms + Fields)

**Two extractors**:
1. `extract_django_forms()` - Extract form classes
2. `extract_django_form_fields()` - Extract fields within forms

**Two tables**:
1. `python_django_forms` - One row per form class
2. `python_django_form_fields` - Many rows per form (one per field)

**Relationship**: Foreign key `form_class_name` links fields to form

**Why separate**: Enables queries like "Find forms without validators" vs "Find fields without max_length"

---

## HELPER FUNCTIONS

### get_node_name(node) - Extract Name from AST Node

**Location**: `theauditor/ast_extractors/base.py`

**Usage**:
```python
from theauditor.ast_extractors.base import get_node_name

# For decorators
decorator_name = get_node_name(decorator_node)
# Returns: "property", "staticmethod", "app.task", etc.

# For attributes
attr_name = get_node_name(attribute_node)
# Returns: "obj.method", "module.Class", etc.
```

### AST Walker Pattern

**Basic walker**:
```python
for node in ast.walk(actual_tree):
    if isinstance(node, ast.FunctionDef):
        # Process function node
        pass
```

**Nested walker** (for specific contexts):
```python
for class_node in ast.walk(actual_tree):
    if isinstance(class_node, ast.ClassDef):
        for method_node in class_node.body:
            if isinstance(method_node, ast.FunctionDef):
                # Process method within class
                pass
```

### Decorator Argument Extraction

```python
def extract_decorator_kwarg(decorator, arg_name):
    """Extract keyword argument from decorator call."""
    if not isinstance(decorator, ast.Call):
        return None

    for keyword in decorator.keywords:
        if keyword.arg == arg_name:
            # Handle different value types
            if isinstance(keyword.value, ast.Constant):
                return keyword.value.value
            elif isinstance(keyword.value, ast.Str):
                return keyword.value.s
            elif isinstance(keyword.value, ast.Num):
                return keyword.value.n

    return None
```

---

## PERFORMANCE CONSIDERATIONS

### Extractor Performance

**Target**: <10ms per file
**Bottlenecks**: Multiple ast.walk() passes

**Good**:
```python
# Single pass
for node in ast.walk(actual_tree):
    if isinstance(node, ast.FunctionDef):
        check_for_pattern(node)
    elif isinstance(node, ast.ClassDef):
        check_for_other_pattern(node)
```

**Bad**:
```python
# Multiple passes (slow)
for node in ast.walk(actual_tree):
    if isinstance(node, ast.FunctionDef):
        check_for_pattern(node)

for node in ast.walk(actual_tree):  # Second walk
    if isinstance(node, ast.ClassDef):
        check_for_other_pattern(node)
```

### Database Performance

**Indexes**: Add indexes for common queries
```python
indexes=[
    ("idx_table_file", ["file"]),           # File-based queries
    ("idx_table_name", ["name"]),           # Name lookups
    ("idx_table_type_flag", ["type", "has_flag"]),  # Composite
]
```

**Batch Size**: Writers use batch inserts (automatic, no action needed)

---

## SECURITY PATTERNS TO EXTRACT

When adding extractors, prioritize security-relevant patterns:

1. **Authentication/Authorization**
   - Login decorators
   - Permission checks
   - Auth middleware

2. **Input Validation**
   - Validator decorators
   - Sanitization functions
   - Max length constraints

3. **Resource Limits**
   - Rate limits
   - Timeout settings
   - Queue configurations

4. **Serialization**
   - Pickle usage (RCE risk)
   - JSON vs unsafe serializers
   - Deserialization calls

5. **Database Access**
   - Raw SQL queries
   - ORM bypasses
   - Mass assignment risks

---

## COLD START CHECKLIST

New AI session? Run through this:

- [ ] Read this document top to bottom
- [ ] Understand 5-layer pipeline
- [ ] Review Example 1 (decorators)
- [ ] Review Example 2 (Celery tasks)
- [ ] Check current Python tables: `grep "PYTHON_" theauditor/indexer/schemas/python_schema.py | grep "= TableSchema"`
- [ ] Verify database state: Query `.pf/repo_index.db` for table counts
- [ ] Test extraction: Run `aud index` and verify non-zero counts
- [ ] Ready to code: Follow "Adding a New Extractor" step-by-step

---

## FAQ

**Q: Can I modify existing extractors?**
A: Yes, but re-run full indexing to update database.

**Q: What if my pattern needs nested data structures?**
A: Serialize as JSON string, store in TEXT column.

**Q: How do I handle optional fields?**
A: Use `Column(nullable=True)` and pass `None` for missing values.

**Q: Why separate tables for forms and fields?**
A: Enables independent queries and reduces duplication.

**Q: How do I test without full indexing?**
A: Use Method 1 (Direct Testing) in Verification section.

**Q: What's the typical extractor size?**
A: 50-150 lines for simple patterns, 200-300 for complex frameworks.

**Q: Can I add foreign keys between tables?**
A: Yes, use `Column(foreign_key=("other_table", "column"))` in schema.

---

## APPENDIX: File Locations Reference

```
theauditor/
├── ast_extractors/
│   └── python/
│       ├── __init__.py           (exports, line 100 + line 180)
│       ├── core_extractors.py    (16 functions, basic patterns)
│       ├── framework_extractors.py (21 functions, Django/Flask/Celery/etc)
│       ├── async_extractors.py   (3 functions, async patterns)
│       ├── testing_extractors.py (4 functions, pytest patterns)
│       └── type_extractors.py    (5 functions, Protocol/Generic/etc)
│
├── indexer/
│   ├── extractors/
│   │   └── python.py             (Line 50-110: result dict init)
│   │                             (Line 265-290: extractor calls)
│   │
│   ├── schemas/
│   │   └── python_schema.py      (34 Python table schemas)
│   │
│   ├── database/
│   │   └── python_database.py    (add_python_X methods)
│   │
│   └── storage.py                (Line 50-100: handler registry)
│                                 (Line 800-900: storage methods)
│
└── tests/
    └── fixtures/
        └── python/
            └── realworld_project/ (38 test fixture files, 2,512 lines)
```

---

**END OF IMPLEMENTATION GUIDE**

**Next Step**: If you understand this, you can immediately code a new extractor. Start with Step 1.

**Still Confused?**: Re-read Architecture Overview and Example 1. The pattern is identical for all extractors.

**Verified Working**: This exact pattern was used for all 49 extractors, extracting 2,723 records from TheAuditor's codebase.
