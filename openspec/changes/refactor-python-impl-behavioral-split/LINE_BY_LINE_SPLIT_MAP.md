# Line-by-Line Split Map: python_impl.py → Two Files

**Source File**: `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py` (2324 lines)

**Target Files**:
1. `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py` (NEW - ~1150 lines)
2. `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py` (REFACTORED - ~1174 lines)

---

## Part 1: python_impl_structure.py (Structural Layer)

### Section 1: Module Docstring (NEW - ~90 lines)
**Action**: WRITE NEW (inspired by typescript_impl_structure.py lines 1-25)

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

### Section 2: Constants (COPY from source lines 110-131)
**Source Lines**: 110-131
**Action**: COPY EXACT

```python
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

### Section 3: Utility Functions (COPY from source lines 44-282)
**Source Lines**: 44-282 (15 functions)
**Action**: COPY EXACT

Functions to copy:
- Line 44: `_get_type_annotation`
- Line 60: `_analyze_annotation_flags`
- Line 77: `_parse_function_type_comment`
- Line 133: `_get_str_constant`
- Line 144: `_keyword_arg`
- Line 152: `_get_bool_constant`
- Line 164: `_cascade_implies_delete`
- Line 172: `_extract_backref_name`
- Line 184: `_extract_backref_cascade`
- Line 200: `_infer_relationship_type`
- Line 222: `_inverse_relationship_type`
- Line 234: `_is_truthy`
- Line 242: `_dependency_name`
- Line 257: `_extract_fastapi_dependencies`

**Copy Command**:
```python
# Lines 44-282 from python_impl.py → python_impl_structure.py
# (14 utility functions + docstrings)
```

### Section 4: Core Structural Extractors (COPY from source lines 283-1585)
**Source Lines**: 283-1585 (19 functions)
**Action**: COPY EXACT

Functions to copy:
- Line 283: `extract_python_functions`
- Line 439: `extract_python_classes`
- Line 460: `extract_python_attribute_annotations` (uses find_containing_class_python - OK)
- Line 500: `extract_sqlalchemy_definitions`
- Line 689: `extract_django_definitions`
- Line 774: `extract_pydantic_validators`
- Line 824: `extract_marshmallow_schemas`
- Line 928: `extract_marshmallow_fields`
- Line 1026: `extract_wtforms_forms`
- Line 1080: `extract_wtforms_fields`
- Line 1164: `extract_celery_tasks`
- Line 1236: `extract_celery_task_calls`
- Line 1290: `extract_celery_beat_schedules`
- Line 1370: `extract_pytest_fixtures`
- Line 1434: `extract_pytest_parametrize`
- Line 1491: `extract_pytest_markers`
- Line 1554: `extract_flask_blueprints`

**Copy Command**:
```python
# Lines 283-1585 from python_impl.py → python_impl_structure.py
# (17 framework + core extractors)
```

### Section 5: Simple Extractors (COPY from source lines 1586-1681, 1752-1766, 1875-1882)
**Source Lines**: Non-contiguous sections
**Action**: COPY EXACT

Functions to copy:
- Line 1586: `extract_python_calls`
- Line 1608: `extract_python_imports`
- Line 1643: `extract_python_exports`
- Line 1752: `extract_python_function_params` (needed by behavioral layer)
- Line 1875: `extract_python_properties`

**Copy Commands**:
```python
# Lines 1586-1643 from python_impl.py → python_impl_structure.py
# (extract_python_calls, extract_python_imports, extract_python_exports)

# Lines 1752-1766 from python_impl.py → python_impl_structure.py
# (extract_python_function_params)

# Lines 1875-1882 from python_impl.py → python_impl_structure.py
# (extract_python_properties - placeholder)
```

### Section 6: File Footer
**Action**: WRITE NEW

```python
# End of python_impl_structure.py
# Total: ~1150 lines (49.5% of 2324)
```

---

## Part 2: python_impl.py (Behavioral Layer - REFACTORED)

### Section 1: Module Docstring (REWRITE - ~100 lines)
**Action**: REPLACE lines 1-27 with NEW content (inspired by typescript_impl.py lines 1-43)

```python
"""Python Behavioral AST Extraction Layer.

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

### Section 2: Behavioral Extractors (COPY from source - specific lines)
**Action**: COPY EXACT behavioral functions

#### Extract 1: extract_python_assignments
**Source Lines**: 1682-1749
**Action**: COPY EXACT

#### Extract 2: extract_python_calls_with_args
**Source Lines**: 1768-1811
**Action**: COPY EXACT

#### Extract 3: extract_python_returns
**Source Lines**: 1814-1870
**Action**: COPY EXACT

#### Extract 4: extract_python_dicts
**Source Lines**: 1884-2032
**Action**: COPY EXACT

#### Extract 5: extract_python_cfg
**Source Lines**: 2035-2053
**Action**: COPY EXACT

#### Extract 6: build_python_function_cfg
**Source Lines**: 2056-2116
**Action**: COPY EXACT

#### Extract 7: process_python_statement
**Source Lines**: 2119-2324
**Action**: COPY EXACT (through end of file)

### Section 3: File Footer
**Action**: WRITE NEW

```python
# End of python_impl.py (Behavioral Layer)
# Total: ~1174 lines (50.5% of 2324)
#
# Re-exported from python_impl_structure.py:
# - All constants (SQLALCHEMY_BASE_IDENTIFIERS, etc.)
# - All utilities (_get_type_annotation, etc.)
# - All structural extractors (extract_python_functions, etc.)
#
# Defined in this file (behavioral layer):
# - extract_python_assignments (uses find_containing_function_python)
# - extract_python_calls_with_args (builds function_ranges)
# - extract_python_returns (builds function_ranges)
# - extract_python_dicts (builds function_ranges)
# - extract_python_cfg (CFG construction)
# - build_python_function_cfg (CFG builder)
# - process_python_statement (CFG processor)
```

---

## Mechanical Copy Instructions

### Step 1: Create python_impl_structure.py

```bash
# WINDOWS PATHS - Use backslashes
cd C:\Users\santa\Desktop\TheAuditor

# Create new file with module docstring (see Section 1 above)
# Use Write tool with content from Section 1

# Copy utilities
# Lines 44-282 → python_impl_structure.py

# Copy constants
# Lines 110-131 → python_impl_structure.py

# Copy structural extractors
# Lines 283-1585 → python_impl_structure.py

# Copy simple extractors
# Lines 1586-1643, 1752-1766, 1875-1882 → python_impl_structure.py
```

### Step 2: Refactor python_impl.py

```bash
# WINDOWS PATHS - Use backslashes
cd C:\Users\santa\Desktop\TheAuditor

# Replace lines 1-43 with new docstring (see Section 1 above)
# Use Edit tool to replace module header

# Delete lines 44-1681 (moved to python_impl_structure.py)
# Keep lines 1682-2324 (behavioral functions)

# Add imports from python_impl_structure.py (see Section 1 above)
```

### Step 3: Verification

```bash
# Check line counts
wc -l C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl_structure.py
# Expected: ~1150 lines (48-52% of 2324)

wc -l C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python_impl.py
# Expected: ~1174 lines (48-52% of 2324)

# Check imports work
cd C:\Users\santa\Desktop\TheAuditor
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl_structure import extract_python_functions; print('OK')"

.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_assignments; print('OK')"

.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python_impl import extract_python_functions; print('OK - re-export works')"
```

---

## Gap Analysis

### Lines Moved to python_impl_structure.py
- 44-282 (utilities)
- 110-131 (constants - overlaps with utilities, OK)
- 283-1585 (core structural extractors)
- 1586-1643 (simple extractors)
- 1752-1766 (function params)
- 1875-1882 (properties placeholder)

**Total moved**: ~1150 lines

### Lines Kept in python_impl.py
- 1-43 (module header - REPLACED with new docstring)
- 1682-1749 (extract_python_assignments)
- 1768-1811 (extract_python_calls_with_args)
- 1814-1870 (extract_python_returns)
- 1884-2032 (extract_python_dicts)
- 2035-2053 (extract_python_cfg)
- 2056-2116 (build_python_function_cfg)
- 2119-2324 (process_python_statement)

**Total kept**: ~1174 lines (includes new imports section ~100 lines)

### Lines Skipped (Neither File)
- Lines 1644-1681: Gap between extract_python_exports and extract_python_assignments
- Lines 1750-1751: Gap between extract_python_assignments and extract_python_function_params
- Lines 1767: Gap between extract_python_function_params and extract_python_calls_with_args
- Lines 1812-1813: Gap between extract_python_calls_with_args and extract_python_returns
- Lines 1871-1874: Gap between extract_python_returns and extract_python_properties
- Lines 1883: Gap between extract_python_properties and extract_python_dicts
- Lines 2033-2034: Gap between extract_python_dicts and extract_python_cfg
- Lines 2054-2055: Gap between extract_python_cfg and build_python_function_cfg
- Lines 2117-2118: Gap between build_python_function_cfg and process_python_statement

**Total gaps**: ~50 lines (blank lines, comments between functions)

**Verification**: 1150 + 1174 - 100 (new imports) + 50 (gaps) ≈ 2274 ≈ 2324 ✓

---

## Critical Notes

1. **Windows Paths**: When implementing, use `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\` (backslashes)
2. **No Direct File Copying**: Use Read + Write tools, NOT `cp` or `cat` commands
3. **Import Updates**: python_impl.py must import from python_impl_structure (one-way dependency)
4. **Re-exports**: python_impl.py re-exports ALL structural functions for backward compatibility
5. **Line Counts**: Target 50/50 split (±5%), expect ~1150 structural + ~1174 behavioral

---

## Next Document

See `IMPLEMENTATION_GUIDE.md` for step-by-step execution commands.
