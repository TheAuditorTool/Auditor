# Actual Code Patterns Found (2025-11-14)

**Source**: Codebase analysis of TheAuditor Python extraction architecture
**Files Read**: python.py (1410 lines), core_extractors.py (1097 lines), python_schema.py (partial), flask_extractors.py (partial)
**Status**: VERIFIED - All patterns below are taken from actual production code

---

## CRITICAL FINDINGS: My Proposal Was Wrong

### What I Guessed vs What Actually Exists

| My Guess (tasks.md) | Reality (Verified) | Impact |
|---------------------|-------------------|--------|
| `def extract_X(tree, parser_self)` | ✅ **CORRECT** | Function signature accurate |
| Tree is `ast.AST` object | ❌ **WRONG** - Tree is `Dict` with key `"tree"` containing `ast.AST` | Must call `tree.get("tree")` |
| Return `List[Dict]` with file paths | ❌ **WRONG** - NO file paths in return | Orchestrator adds file paths |
| Tables defined with SQL DDL | ❌ **WRONG** - Uses `TableSchema` objects | Must use Column() pattern |
| 59 tables exist | ✅ **CORRECT** | Verified via Python query |
| Wiring via __init__.py registry | ❌ **WRONG** - Explicit calls in python.py | Must add calls to python.py:243-603 |

---

## Pattern 1: Extractor Function Signature (VERIFIED)

**Source**: core_extractors.py:110, flask_extractors.py:105

```python
def extract_python_X(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract X patterns from Python AST.

    ARCHITECTURAL CONTRACT:
    - RECEIVE: AST tree only (no file path context)
    - EXTRACT: Data with 'line' numbers and content
    - RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
    - MUST NOT: Include 'file' or 'file_path' keys in returned dicts

    File path context is provided by the INDEXER layer when storing to database.
    """
    actual_tree = tree.get("tree")  # CRITICAL: tree is a Dict, not ast.AST directly

    if not isinstance(actual_tree, ast.AST):
        return []

    results = []

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.TargetNodeType):
            # Extract pattern
            results.append({
                'line': node.lineno,
                # ... other keys (NO 'file' or 'file_path')
            })

    return results
```

**Key Points**:
1. Parameter is `tree: Dict`, NOT `tree: ast.AST`
2. MUST call `tree.get("tree")` to get actual AST
3. MUST check `if not isinstance(actual_tree, ast.AST):`
4. MUST return `List[Dict[str, Any]]`
5. MUST NOT include 'file' or 'file_path' in returned dicts
6. `parser_self` is typically named `parser_self` but is actually `self.ast_parser` reference

---

## Pattern 2: Helper Functions (VERIFIED)

**Source**: flask_extractors.py:71-99, core_extractors.py:26-31

```python
from ..base import (
    get_node_name,              # Get string name from AST node
    extract_vars_from_expr,      # Extract variable names from expression
    find_containing_function_python,  # Find function containing a line
    find_containing_class_python,     # Find class containing a line
)

# Local helpers (duplicated in each module for self-containment)
def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):  # Python 3.7 compat
        return node.s
    return None

def _keyword_arg(call: ast.Call, name: str) -> Optional[ast.AST]:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None
```

**Key Points**:
- Import from `..base` for shared helpers
- Duplicate `_get_str_constant` and `_keyword_arg` in each module (pattern across codebase)
- Use `get_node_name()` to get string representation of AST nodes

---

## Pattern 3: Wiring to Pipeline (VERIFIED)

**Source**: python.py:243-603

### Step 1: Import in python.py
```python
# python.py lines 30-40
from theauditor.ast_extractors.python import (
    async_extractors,
    cdk_extractor,
    core_extractors,
    django_advanced_extractors,
    flask_extractors,
    framework_extractors,
    security_extractors,
    testing_extractors,
    type_extractors,
    # ADD NEW MODULE HERE:
    # state_mutation_extractors,
)
```

### Step 2: Initialize result key in python.py extract()
```python
# python.py lines 62-147
def extract(self, file_info: Dict[str, Any], content: str, tree: Optional[Any] = None) -> Dict[str, Any]:
    result = {
        'imports': [],
        # ... existing keys ...
        # ADD NEW KEYS HERE:
        # 'python_instance_mutations': [],
        # 'python_class_mutations': [],
    }
```

### Step 3: Call extractor in python.py extract()
```python
# python.py lines 243-434 (inside `if self.ast_parser:` block)

# Example from line 328:
generators = core_extractors.extract_generators(tree, self.ast_parser)
if generators:
    result['python_generators'].extend(generators)

# ADD NEW EXTRACTOR CALLS HERE:
# instance_mutations = state_mutation_extractors.extract_instance_mutations(tree, self.ast_parser)
# if instance_mutations:
#     result['python_instance_mutations'].extend(instance_mutations)
```

**Key Points**:
1. Calls are EXPLICIT, not automatic via registry
2. Pattern: `results = module.extract_function(tree, self.ast_parser)`
3. Check if not empty: `if results:`
4. Extend to result dict: `result['key'].extend(results)`
5. All calls inside `if self.ast_parser:` guard (line 173)

---

## Pattern 4: Schema Table Definition (VERIFIED)

**Source**: python_schema.py:23-147

```python
from .utils import Column, TableSchema

PYTHON_INSTANCE_MUTATIONS = TableSchema(
    name="python_instance_mutations",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("target", "TEXT", nullable=False),  # 'self.counter'
        Column("operation", "TEXT", nullable=False),  # 'assignment' | 'augmented_assignment'
        Column("in_function", "TEXT", nullable=False),
        Column("is_init", "BOOLEAN", default="0"),  # True if in __init__
    ],
    primary_key=["file", "line", "target"],
    indexes=[
        ("idx_python_instance_mutations_file", ["file"]),
        ("idx_python_instance_mutations_function", ["in_function"]),
    ]
)
```

**Key Points**:
1. Use `TableSchema` object, NOT raw SQL
2. Use `Column(name, type, nullable, default)` pattern
3. `primary_key` is list of column names
4. `indexes` is list of tuples: `(index_name, [columns])`
5. Boolean columns use `default="0"` (SQL integer)
6. All tables get 'file' column automatically

### Registering Table
```python
# python_schema.py bottom (after all table definitions)
PYTHON_TABLES = {
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    # ... existing tables ...
    # ADD NEW TABLES HERE:
    # "python_instance_mutations": PYTHON_INSTANCE_MUTATIONS,
}
```

---

## Pattern 5: Context Tracking (VERIFIED)

**Source**: core_extractors.py:508-513, flask_extractors.py:703-715

### Function Ranges Pattern
```python
# Build function ranges for scope detection
function_ranges = {}
for node in ast.walk(actual_tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

# Find containing function for each extraction
def find_containing_function(line_no):
    """Find the function containing this line."""
    for fname, (start, end) in function_ranges.items():
        if start <= line_no <= end:
            return fname
    return "global"

# Use when extracting:
in_function = find_containing_function(node.lineno)
```

**Key Points**:
- First pass: Build `function_ranges` dict
- Second pass: Use `find_containing_function()` for each node
- Returns "global" if not in a function
- Can also use `find_containing_function_python(actual_tree, lineno)` from base

---

## Pattern 6: Deduplication (VERIFIED)

**Source**: core_extractors.py:452-468

```python
# CRITICAL FIX: Deduplicate by composite key
# WHY: ast.walk() can visit nodes multiple times
seen = set()
deduped = []
for item in results:
    key = (item['line'], item['target_var'], item['in_function'])
    if key not in seen:
        seen.add(key)
        deduped.append(item)

if os.environ.get("THEAUDITOR_DEBUG"):
    import sys
    if len(results) != len(deduped):
        print(f"[AST_DEBUG] Deduplication: {len(results)} -> {len(deduped)} ({len(results) - len(deduped)} duplicates removed)", file=sys.stderr)

return deduped
```

**Key Points**:
- ALWAYS deduplicate before returning
- Use composite key based on PRIMARY KEY columns (minus 'file')
- DEBUG logging if deduplication removes items

---

## Pattern 7: Complete Module Structure (VERIFIED)

**Source**: flask_extractors.py:1-300

```python
"""Module docstring with ARCHITECTURAL CONTRACT."""

import ast
import logging
from typing import Any, Dict, List, Optional

from ..base import get_node_name

logger = logging.getLogger(__name__)

# ============================================================================
# Detection Constants
# ============================================================================

PATTERN_IDENTIFIERS = {
    "pattern1",
    "pattern2",
}

# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    # ... implementation

def _keyword_arg(call: ast.Call, name: str) -> Optional[ast.AST]:
    # ... implementation

# ============================================================================
# Extractor Functions
# ============================================================================

def extract_pattern_X(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract pattern X.

    Detects:
    - Pattern detail 1
    - Pattern detail 2

    Security relevance:
    - Why this pattern matters for security

    (Include ARCHITECTURAL CONTRACT note)
    """
    results = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return results

    # Build context (function ranges, etc.)
    # ...

    # Extract patterns
    for node in ast.walk(actual_tree):
        # ...

    return results
```

---

## Verification Results (ACTUAL vs EXPECTED)

| Hypothesis | Expected | Actual (Verified) | Status |
|------------|----------|-------------------|--------|
| H1: No mutation extractors | No matches | ✅ **CONFIRMED** - grep found none | GAP EXISTS |
| H2: Assignments not categorized | No mutation_type field | ✅ **CONFIRMED** - core_extractors.py:428 has no type | GAP EXISTS |
| H3: No exception extractors | No file exists | ✅ **CONFIRMED** - No exception_flow_extractors.py | GAP EXISTS |
| H4: 59 tables exist | 59 tables | ✅ **CONFIRMED** - Python query returned 59 | BASELINE VALID |
| H5: AST nodes available | All nodes exist | ✅ **CONFIRMED** - Python stdlib has all | NO BLOCKER |
| H6: Tree is Dict with "tree" key | Tree is dict | ✅ **CONFIRMED** - core_extractors.py:121 | **MY GUESS WAS WRONG** |
| H7: Function signature correct | tree: Dict, parser_self | ✅ **CONFIRMED** - core_extractors.py:110 | PATTERN VALID |
| H8: Wiring via explicit calls | Explicit in python.py | ✅ **CONFIRMED** - python.py:243-603 | **MY GUESS WAS WRONG** |

---

## Corrected Implementation Approach

### What I Got Right ✅
1. Function signature: `def extract_X(tree: Dict, parser_self) -> List[Dict]`
2. Baseline: 59 Python tables exist
3. No mutation extractors currently exist (gap confirmed)
4. AST node types are available in Python stdlib

### What I Got WRONG ❌
1. **Tree structure**: Assumed `tree` is `ast.AST` → Actually `Dict` with `"tree"` key
2. **Return format**: Assumed include 'file' key → Actually NO file keys (orchestrator adds them)
3. **Wiring mechanism**: Assumed registry pattern → Actually explicit calls in python.py
4. **Schema definition**: Assumed SQL DDL → Actually `TableSchema` objects

### Impact on Tasks
- **All tasks referencing tree extraction**: MUST update to use `tree.get("tree")`
- **All tasks referencing file paths**: MUST remove file path from extractor returns
- **All wiring tasks**: MUST update to add explicit calls in python.py, not registry
- **All schema tasks**: MUST use TableSchema pattern, not SQL

---

## Next Steps

1. ✅ **DONE**: Read actual codebase (python.py, core_extractors.py, schema, flask_extractors.py)
2. ✅ **DONE**: Document actual patterns in ACTUAL_PATTERNS.md (this file)
3. ⏭️ **TODO**: Update verification.md with actual findings
4. ⏭️ **TODO**: Rewrite tasks.md with REAL implementation steps (not guesses)
5. ⏭️ **TODO**: Update proposal.md with corrected baselines

---

**STATUS**: Ready to rewrite tasks.md with professional, verified implementation details.
