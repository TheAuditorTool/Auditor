# Implementation Guide: Step-by-Step Execution

**CRITICAL**: Use Windows paths with backslashes for all file operations.
**CRITICAL**: Use Read + Write + Edit tools, NOT bash `cp`, `cat`, or heredoc.

---

## Prerequisites

### 1. Verify Current State
```bash
cd C:\Users\santa\Desktop\TheAuditor

# Confirm file exists and line count
wc -l theauditor\ast_extractors\python_impl.py
# Expected: 2324 theauditor\ast_extractors\python_impl.py

# Confirm python/ package is active (not python_impl.py file)
.venv\Scripts\python.exe -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__)"
# Expected: ...\theauditor\ast_extractors\python\__init__.py
```

### 2. Create Backup
```bash
cd C:\Users\santa\Desktop\TheAuditor
git status
# Confirm clean working tree or commit current work

# No need for manual backup - git handles this
# If rollback needed: git checkout theauditor/ast_extractors/python_impl.py
```

---

## Phase 1: Create python_impl_structure.py

### Step 1.1: Create File with Module Docstring

**Action**: Use Write tool to create new file

**File**: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py`

**Content Template** (copy from LINE_BY_LINE_SPLIT_MAP.md Section "Part 1, Section 1"):
```python
"""Python Structural AST Extraction Layer.

This module is Part 1 of the Python implementation layer split.

RESPONSIBILITY: Structural Extraction (Stateless AST Traversal)
=================================================================

Core Components:
- AST Utilities: Type annotation helpers, constant extractors, boolean parsers
- Framework Constants: SQLAlchemy, Django, FastAPI identifiers
- Structural Extractors: Functions, classes, calls, imports, exports, parameters
- Framework Extractors: ORM models (SQLAlchemy, Django), validators (Pydantic),
  forms (Marshmallow, WTForms), tasks (Celery), tests (pytest), routes (Flask)

ARCHITECTURAL CONTRACT:
- NO function context required (no find_containing_function_python calls)
- NO scope resolution (no function_ranges building)
- Stateless operations only (pure AST traversal)

CONSUMERS:
- python_impl.py (behavioral analysis layer)
- ast_extractors/__init__.py (orchestrator router)

CRITICAL: This layer provides structural facts about code. Behavioral analysis
(assignments, returns, CFG) belongs in python_impl.py which imports from here.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Set

from .base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_class_python,  # Used by extract_python_attribute_annotations
)

logger = logging.getLogger(__name__)

```

**Command**:
```
Use Write tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py
content: <paste module docstring + imports above>
```

### Step 1.2: Copy Constants (Lines 110-131)

**Action**: Read python_impl.py lines 110-131, then Edit python_impl_structure.py to append

**Read Command**:
```
Use Read tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
offset: 110
limit: 22
```

**Edit Command**:
```
Use Edit tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py
old_string: logger = logging.getLogger(__name__)

new_string: logger = logging.getLogger(__name__)

SQLALCHEMY_BASE_IDENTIFIERS = {
    "DeclarativeBase", "declarative_base", "Base"
}

DJANGO_MODEL_BASES = {
    "models.Model", "Model"
}

FASTAPI_HTTP_METHODS = {
    "get", "post", "put", "delete", "patch", "options", "head", "trace"
}

```

### Step 1.3: Copy Utility Functions (Lines 44-282)

**Action**: Read python_impl.py in chunks, append to python_impl_structure.py

**Read Commands** (execute sequentially):
```
Read tool: file_path C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py, offset 44, limit 100
Read tool: file_path C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py, offset 144, limit 100
Read tool: file_path C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py, offset 244, limit 50
```

**Edit Commands**:
For each chunk, use Edit tool to append after the constants section.

**Note**: This is tedious but necessary. 14 utility functions total.

### Step 1.4: Copy Core Structural Extractors (Lines 283-1585)

**Action**: Read python_impl.py in 300-line chunks, append to python_impl_structure.py

**Read Commands**:
```
Read: offset 283, limit 300
Read: offset 583, limit 300
Read: offset 883, limit 300
Read: offset 1183, limit 300
Read: offset 1483, limit 103
```

**Edit Commands**: Append each chunk to python_impl_structure.py after utilities.

**Functions Copied** (17 total):
- extract_python_functions
- extract_python_classes
- extract_python_attribute_annotations
- extract_sqlalchemy_definitions
- extract_django_definitions
- extract_pydantic_validators
- extract_marshmallow_schemas
- extract_marshmallow_fields
- extract_wtforms_forms
- extract_wtforms_fields
- extract_celery_tasks
- extract_celery_task_calls
- extract_celery_beat_schedules
- extract_pytest_fixtures
- extract_pytest_parametrize
- extract_pytest_markers
- extract_flask_blueprints

### Step 1.5: Copy Simple Extractors (Lines 1586-1643, 1752-1766, 1875-1882)

**Action**: Read and append three non-contiguous sections

**Read Commands**:
```
Read: offset 1586, limit 58  # extract_python_calls, extract_python_imports, extract_python_exports
Read: offset 1752, limit 15  # extract_python_function_params
Read: offset 1875, limit 8   # extract_python_properties
```

**Edit Commands**: Append each section to python_impl_structure.py

### Step 1.6: Verify python_impl_structure.py

**Commands**:
```bash
cd C:\Users\santa\Desktop\TheAuditor

# Check line count
wc -l theauditor\ast_extractors\python_impl_structure.py
# Expected: ~1150 lines (1105-1195 acceptable)

# Check syntax
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python_impl_structure.py
# Expected: No output (success)

# Check imports work
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl_structure import extract_python_functions, SQLALCHEMY_BASE_IDENTIFIERS; print('OK')"
# Expected: OK
```

---

## Phase 2: Refactor python_impl.py

### Step 2.1: Replace Module Docstring (Lines 1-43)

**Action**: Use Edit tool to replace old docstring with new "Part 2" docstring

**Edit Command**:
```
Use Edit tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
old_string: """Python AST extraction implementations.

DEPRECATION NOTICE (2025-10-30 - Phase 2.1)
============================================
This module is DEPRECATED and kept for rollback safety only.
All functionality has been refactored into modular structure:
  - theauditor/ast_extractors/python/core_extractors.py
  - theauditor/ast_extractors/python/framework_extractors.py
  - theauditor/ast_extractors/python/cfg_extractor.py

Use: `from theauditor.ast_extractors import python as python_impl`

This file will be removed in Phase 2.2 after verification period.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an IMPLEMENTATION layer module. All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer (indexer/__init__.py)
when storing to database. See indexer/__init__.py:952 for example.

This separation ensures single source of truth for file paths.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Set

from .base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_function_python,
    find_containing_class_python,
)

logger = logging.getLogger(__name__)

new_string: """Python Behavioral AST Extraction Layer.

This module is Part 2 of the Python implementation layer split.

RESPONSIBILITY: Behavioral Analysis (Context-Dependent Semantic Extraction)
================================================================================

Core Components:
- Assignments: Variable assignments with function context (find_containing_function_python)
- Returns: Return statements with function scope resolution
- Calls with Args: Function calls with argument mapping (builds function_ranges)
- Dict Literals: Dictionary literals with scope detection (builds function_ranges)
- Control Flow Graphs: CFG construction (stateful graph building)

ARCHITECTURAL CONTRACT:
- REQUIRES function context utilities (find_containing_function_python)
- REQUIRES structural layer (imports from python_impl_structure.py)
- Stateful operations (scope resolution, graph construction)

DEPENDENCIES:
- find_containing_function_python: Function context resolution from base.py
- find_containing_class_python: Class context resolution from base.py
- python_impl_structure.py: All structural extractors and utilities

CONSUMERS:
- indexer/extractors/python.py (orchestrator)
- ast_extractors/__init__.py (router)

BACKWARD COMPATIBILITY:
All functions from python_impl_structure.py are re-exported here for backward
compatibility. Existing code using `from python_impl import extract_python_functions`
will continue working via re-exports.

CRITICAL: This layer depends on python_impl_structure.py (one-way dependency).
python_impl_structure.py MUST NOT import from this file to avoid circular dependencies.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Set

from .base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_function_python,
    find_containing_class_python,
)

# Import ALL structural extractors and utilities from structural layer
from .python_impl_structure import (
    # Constants
    SQLALCHEMY_BASE_IDENTIFIERS,
    DJANGO_MODEL_BASES,
    FASTAPI_HTTP_METHODS,

    # Utilities
    _get_type_annotation,
    _analyze_annotation_flags,
    _parse_function_type_comment,
    _get_str_constant,
    _keyword_arg,
    _get_bool_constant,
    _cascade_implies_delete,
    _extract_backref_name,
    _extract_backref_cascade,
    _infer_relationship_type,
    _inverse_relationship_type,
    _is_truthy,
    _dependency_name,
    _extract_fastapi_dependencies,

    # Structural Extractors (re-exported for backward compatibility)
    extract_python_functions,
    extract_python_classes,
    extract_python_attribute_annotations,
    extract_sqlalchemy_definitions,
    extract_django_definitions,
    extract_pydantic_validators,
    extract_marshmallow_schemas,
    extract_marshmallow_fields,
    extract_wtforms_forms,
    extract_wtforms_fields,
    extract_celery_tasks,
    extract_celery_task_calls,
    extract_celery_beat_schedules,
    extract_pytest_fixtures,
    extract_pytest_parametrize,
    extract_pytest_markers,
    extract_flask_blueprints,
    extract_python_calls,
    extract_python_imports,
    extract_python_exports,
    extract_python_function_params,
    extract_python_properties,
)

logger = logging.getLogger(__name__)

```

### Step 2.2: Delete Structural Functions (Lines 44-1681)

**Action**: Use Edit tool to delete everything between logger and extract_python_assignments

**Edit Command**:
```
Use Edit tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
old_string: logger = logging.getLogger(__name__)


def _get_type_annotation(node: Optional[ast.AST]) -> Optional[str]:
<... everything through line 1681 ...>

def extract_python_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:

new_string: logger = logging.getLogger(__name__)


def extract_python_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
```

**Note**: This is a LARGE edit. You may need to do it in chunks:
1. Delete lines 44-500
2. Delete lines 44-500 again (now showing 501-1000)
3. Continue until only behavioral functions remain

**Alternative Approach**: Use multiple Edit operations targeting specific function blocks.

### Step 2.3: Delete extract_python_function_params (Lines 1752-1766)

**Action**: Delete this function since it's now imported from python_impl_structure

**Edit Command**:
```
Use Edit tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
old_string: def extract_python_function_params(tree: Dict, parser_self) -> Dict[str, List[str]]:
    """Extract function definitions and their parameter names from Python AST."""
    func_params = {}
    actual_tree = tree.get("tree")

    if not actual_tree:
        return func_params

    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            func_params[node.name] = params

    return func_params


def extract_python_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:

new_string: def extract_python_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:
```

### Step 2.4: Delete extract_python_properties (Lines 1875-1882)

**Action**: Delete this function since it's now imported from python_impl_structure

**Edit Command**:
```
Use Edit tool:
file_path: C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
old_string: # Python doesn't have property accesses in the same way as JS
# This is a placeholder for consistency
def extract_python_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from Python AST.

    In Python, these would be attribute accesses.
    Currently returns empty list for consistency.
    """
    return []


def extract_python_dicts(tree: Dict, parser_self) -> List[Dict[str, Any]]:

new_string: def extract_python_dicts(tree: Dict, parser_self) -> List[Dict[str, Any]]:
```

### Step 2.5: Verify python_impl.py Refactored

**Commands**:
```bash
cd C:\Users\santa\Desktop\TheAuditor

# Check line count
wc -l theauditor\ast_extractors\python_impl.py
# Expected: ~1174 lines (1105-1195 acceptable)

# Check syntax
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python_impl.py
# Expected: No output (success)

# Check behavioral imports work
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_assignments; print('OK')"
# Expected: OK

# Check re-exports work
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_functions; print('OK - re-export')"
# Expected: OK - re-export
```

---

## Phase 3: Integration Testing

### Step 3.1: Test Import Chain

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Test direct structural import
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl_structure import extract_python_functions, SQLALCHEMY_BASE_IDENTIFIERS; print('Structural: OK')"

# Test direct behavioral import
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_assignments, extract_python_cfg; print('Behavioral: OK')"

# Test backward compatibility (re-export)
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_functions, extract_sqlalchemy_definitions; print('Re-export: OK')"

# Test orchestrator still works (production import path)
.venv\Scripts\python.exe -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__); print('Orchestrator uses python/ package, NOT python_impl.py file')"
# Expected: ...\theauditor\ast_extractors\python\__init__.py
```

### Step 3.2: Test Dependency Direction

```bash
# Verify one-way dependency (behavioral → structural)
cd C:\Users\santa\Desktop\TheAuditor

# python_impl.py imports from python_impl_structure.py (OK)
grep "from .python_impl_structure import" theauditor\ast_extractors\python_impl.py
# Expected: Found

# python_impl_structure.py does NOT import from python_impl.py (REQUIRED)
grep "from .python_impl import" theauditor\ast_extractors\python_impl_structure.py
# Expected: No matches

# python_impl_structure.py does NOT import find_containing_function_python (REQUIRED)
grep "find_containing_function_python" theauditor\ast_extractors\python_impl_structure.py
# Expected: No matches
```

### Step 3.3: Test Split Ratio

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Check line counts
wc -l theauditor\ast_extractors\python_impl_structure.py theauditor\ast_extractors\python_impl.py

# Calculate ratio
# Structural: ~1150 / 2324 = 49.5%
# Behavioral: ~1174 / 2324 = 50.5%
# Target: 50/50 ± 5% = 48-52%

# Verify within tolerance
# If both files are 48-52% of original 2324 lines: PASS
```

### Step 3.4: Test No Duplicate Functions

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Extract function names from both files
grep "^def " theauditor\ast_extractors\python_impl_structure.py | awk '{print $2}' | sort > /tmp/struct_funcs.txt
grep "^def " theauditor\ast_extractors\python_impl.py | awk '{print $2}' | sort > /tmp/behav_funcs.txt

# Check for duplicates
comm -12 /tmp/struct_funcs.txt /tmp/behav_funcs.txt
# Expected: No output (no duplicates)

# Count functions
wc -l /tmp/struct_funcs.txt
# Expected: ~36 functions (structural)

wc -l /tmp/behav_funcs.txt
# Expected: ~7 functions (behavioral)

# Total should equal original 43
# 36 + 7 = 43 ✓
```

---

## Phase 4: Final Verification

### Step 4.1: Static Analysis

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Compile both files
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python_impl_structure.py
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python_impl.py

# Check for syntax errors
echo "If no output above, syntax is OK"
```

### Step 4.2: Pattern Comparison with TypeScript

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Check TypeScript split for reference
wc -l theauditor\ast_extractors\typescript_impl_structure.py theauditor\ast_extractors\typescript_impl.py
# TypeScript: 1031 + 1328 = 2359 lines (44% / 56%)

wc -l theauditor\ast_extractors\python_impl_structure.py theauditor\ast_extractors\python_impl.py
# Python: ~1150 + ~1174 = ~2324 lines (49.5% / 50.5%)

# Pattern matches: ✓
```

### Step 4.3: Architectural Contract Verification

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Verify docstrings match pattern
head -30 theauditor\ast_extractors\python_impl_structure.py | grep "Part 1"
# Expected: Found

head -30 theauditor\ast_extractors\python_impl.py | grep "Part 2"
# Expected: Found

# Verify RESPONSIBILITY sections exist
grep "RESPONSIBILITY:" theauditor\ast_extractors\python_impl_structure.py
# Expected: Found

grep "RESPONSIBILITY:" theauditor\ast_extractors\python_impl.py
# Expected: Found
```

### Step 4.4: Document Results

Create `openspec/changes/refactor-python-impl-behavioral-split/IMPLEMENTATION_RESULTS.md`:

```markdown
# Implementation Results

**Date**: <current date>
**Implementer**: <your name>

## Files Created/Modified

1. **CREATED**: python_impl_structure.py
   - Line count: <actual count>
   - Functions: <actual count>
   - Ratio: <actual %>

2. **MODIFIED**: python_impl.py
   - Line count: <actual count>
   - Functions: <actual count>
   - Ratio: <actual %>

## Verification Results

- [ ] Syntax check (py_compile): PASS/FAIL
- [ ] Import chain test: PASS/FAIL
- [ ] Dependency direction: PASS/FAIL
- [ ] Split ratio (48-52%): PASS/FAIL
- [ ] No duplicate functions: PASS/FAIL
- [ ] Docstring pattern matches TypeScript: PASS/FAIL

## Issues Encountered

<list any issues>

## Resolution

<how issues were resolved>
```

---

## Rollback Procedure

If something goes wrong:

```bash
cd C:\Users\santa\Desktop\TheAuditor

# Revert all changes
git checkout theauditor/ast_extractors/python_impl.py

# Remove new file
rm theauditor/ast_extractors/python_impl_structure.py

# Verify rollback
wc -l theauditor/ast_extractors/python_impl.py
# Expected: 2324 (original)

# Test imports still work
.venv\Scripts\python.exe -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__)"
# Expected: ...\python\__init__.py (unaffected)
```

---

## Success Criteria

All of the following must be TRUE:

1. ✅ python_impl_structure.py created (~1150 lines, 48-52%)
2. ✅ python_impl.py refactored (~1174 lines, 48-52%)
3. ✅ Total lines: ~2324 (within ±50 lines)
4. ✅ No syntax errors (py_compile passes)
5. ✅ Import chain works (structural, behavioral, re-export)
6. ✅ One-way dependency (behavioral → structural)
7. ✅ No duplicate function definitions
8. ✅ Docstrings match TypeScript pattern
9. ✅ No circular imports
10. ✅ Backward compatibility maintained

If all 10 criteria pass → **IMPLEMENTATION COMPLETE** ✅

---

## Notes

- **Windows Paths**: Always use `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\`
- **No Bash File Ops**: Use Read/Write/Edit tools, never `cp`, `cat`, heredoc
- **Chunked Operations**: Large edits may need to be done in chunks
- **Verify Frequently**: Run tests after each phase
- **Git Commits**: Commit after each phase for easy rollback
