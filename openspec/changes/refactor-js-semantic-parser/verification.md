# Verification Protocol - JavaScript Semantic Parser Refactor

**Document Purpose**: Per teamsop.md SOP v4.20 Section 1.3 "Prime Directive: Verify Before Acting"

This document captures ALL hypotheses about the current codebase that must be proven or disproven by reading source code BEFORE any implementation begins. NO CODE MOVEMENT until verification is COMPLETE.

## Verification Status

- [ ] **VERIFICATION INCOMPLETE** - Do NOT proceed with implementation
- [ ] **VERIFICATION COMPLETE** - Safe to proceed

## Phase 1 Hypotheses: js_semantic_parser.py Movement

### H1.1: File Location and Size
**Hypothesis**: `js_semantic_parser.py` exists at `theauditor/js_semantic_parser.py` and is approximately 950 lines.

**Verification Method**: Read the file completely, count lines.

**Result**:
- [ ] CONFIRMED: File exists at expected location
- [ ] CONFIRMED: Line count matches estimate (+/- 50 lines)
- [ ] REJECTED: File location or size differs significantly

**Evidence**:
```
File: theauditor/js_semantic_parser.py
Lines: <TO BE FILLED>
Actual location: <TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H1.2: Import Consumers
**Hypothesis**: The primary consumer is `theauditor/indexer/extractors/javascript.py` which imports via:
```python
from theauditor.js_semantic_parser import JSSemanticParser, get_semantic_ast, get_semantic_ast_batch
```

**Verification Method**:
1. Grep for all imports of `js_semantic_parser` across codebase
2. Read each importing file to understand usage context
3. Document EXACT import statements

**Result**:
- [ ] CONFIRMED: Only expected files import this module
- [ ] REJECTED: Additional unexpected importers found

**Evidence**:
```bash
# Command: Grep results for 'from theauditor.js_semantic_parser' or 'import js_semantic_parser'
<TO BE FILLED>
```

**All Importers Found**:
1. <TO BE FILLED>
2. <TO BE FILLED>

**Discrepancies**: <TO BE FILLED>

---

### H1.3: Public API Surface
**Hypothesis**: The module exports:
- Class: `JSSemanticParser` (with methods: `__init__`, `get_semantic_ast`, `get_semantic_ast_batch`, `resolve_imports`, `extract_type_issues`)
- Function: `get_semantic_ast(file_path, project_root, jsx_mode)`
- Function: `get_semantic_ast_batch(file_paths, project_root, jsx_mode)`

**Verification Method**: Read `js_semantic_parser.py` lines 1-100 and 850-950 (module-level definitions).

**Result**:
- [ ] CONFIRMED: All expected exports present
- [ ] CONFIRMED: No additional public exports
- [ ] REJECTED: API surface differs

**Evidence**:
```python
# Actual public API (from reading file):
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H1.4: Internal Dependencies
**Hypothesis**: The module imports from:
- `theauditor.ast_extractors.js_helper_templates` (line 19)
- `theauditor.utils.temp_manager` (line 22-26, optional)
- Standard library: `json`, `os`, `platform`, `re`, `subprocess`, `sys`, `tempfile`, `pathlib.Path`, `typing`

**Verification Method**: Read import block (lines 1-40).

**Result**:
- [ ] CONFIRMED: Only expected imports present
- [ ] REJECTED: Additional internal dependencies found

**Evidence**:
```python
# Actual imports (from reading file):
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H1.5: Shim Feasibility
**Hypothesis**: A shim at `theauditor/js_semantic_parser.py` can re-export all public API via:
```python
"""Backward compatibility shim - imports from new location."""
from theauditor.ast_extractors.js_semantic_parser import (
    JSSemanticParser,
    get_semantic_ast,
    get_semantic_ast_batch,
)
__all__ = ['JSSemanticParser', 'get_semantic_ast', 'get_semantic_ast_batch']
```

**Verification Method**: Confirm no module-level side effects (global state, immediate execution).

**Result**:
- [ ] CONFIRMED: Module safe to re-export (no side effects)
- [ ] REJECTED: Module has side effects that prevent shimming

**Evidence**:
```
Side effects found: <TO BE FILLED>
Module-level code: <TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

## Phase 2 Hypotheses: typescript_impl.py Split

### H2.1: File Size and Structure
**Hypothesis**: `typescript_impl.py` is approximately 2000 lines and contains:
- 14 public `extract_*` functions
- 4 low-level node helpers (prefixed with `_`)
- 1 core symbol extractor
- 5+ JSX-specific functions
- 2 large complex functions (`build_scope_map`, `build_typescript_function_cfg`)

**Verification Method**: Read file completely, count functions, categorize by role.

**Result**:
- [ ] CONFIRMED: File size and structure match expectations
- [ ] REJECTED: Significant differences in structure

**Evidence**:
```
File: theauditor/ast_extractors/typescript_impl.py
Lines: <TO BE FILLED>
Function count: <TO BE FILLED>
Public API functions: <TO BE FILLED>
Helper functions: <TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H2.2: Functions to Move to typescript_ast_utils.py
**Hypothesis**: The following functions should be extracted to `typescript_ast_utils.py`:

**Low-Level Node Helpers**:
- `_strip_comment_prefix`
- `_identifier_from_node`
- `_canonical_member_name`
- `_canonical_callee_from_call`

**Core Symbol Extractor**:
- `extract_semantic_ast_symbols`

**JSX-Specific Logic**:
- `JSX_NODE_KINDS` (constant)
- `detect_jsx_in_node`
- `extract_jsx_tag_name`
- `analyze_create_element_component`
- `check_for_jsx` (alias)

**Big Helpers**:
- `build_scope_map` (and internal `collect_functions`)
- `build_typescript_function_cfg` (and all internal helpers like `process_node`, `get_child_by_kind`)

**Verification Method**:
1. Read `typescript_impl.py` completely
2. Locate each function by name
3. Verify function signatures and dependencies
4. Confirm no circular dependencies will be created

**Result**:
- [ ] CONFIRMED: All target functions exist and can be safely moved
- [ ] REJECTED: Functions missing, renamed, or have circular dependencies

**Evidence**:
```
Functions found in typescript_impl.py:
<TO BE FILLED - Document line numbers and signatures>

Dependency analysis:
<TO BE FILLED - Which functions call which>
```

**Discrepancies**: <TO BE FILLED>

---

### H2.3: Functions to Keep in typescript_impl.py
**Hypothesis**: The following functions remain in `typescript_impl.py`:

- `extract_typescript_functions_for_symbols`
- `extract_typescript_functions` (alias)
- `extract_typescript_function_nodes`
- `extract_typescript_classes`
- `extract_typescript_calls`
- `extract_typescript_imports`
- `extract_typescript_exports`
- `extract_typescript_properties`
- `extract_typescript_assignments`
- `extract_typescript_function_params`
- `extract_typescript_calls_with_args`
- `extract_typescript_returns`
- `extract_typescript_cfg`
- `extract_typescript_object_literals`

**Verification Method**: Read file, locate all `extract_*` functions, verify they're public API.

**Result**:
- [ ] CONFIRMED: All expected public functions present
- [ ] REJECTED: Functions missing or additional functions found

**Evidence**:
```
Public extract_* functions found:
<TO BE FILLED - Document signatures and line numbers>
```

**Discrepancies**: <TO BE FILLED>

---

### H2.4: Import Changes Required
**Hypothesis**: After split, `typescript_impl.py` will need:
```python
import os
from typing import Any, List, Dict, Optional

# NEW IMPORT - The key change
from . import typescript_ast_utils as ast_utils

# Existing imports from base
from .base import (
    extract_vars_from_typescript_node,
    sanitize_call_name,
)
```

**Verification Method**:
1. Read current import block in `typescript_impl.py`
2. Verify `.base` module exists and exports expected functions
3. Confirm no naming conflicts with `ast_utils` alias

**Result**:
- [ ] CONFIRMED: Import changes are safe
- [ ] REJECTED: Conflicts or missing dependencies

**Evidence**:
```
Current imports in typescript_impl.py:
<TO BE FILLED>

.base module verification:
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H2.5: Call Site Updates
**Hypothesis**: Functions in `typescript_impl.py` that call moved helpers will need updates:

**Example - Before**:
```python
scope_map = build_scope_map(ast_root)
```

**Example - After**:
```python
scope_map = ast_utils.build_scope_map(ast_root)
```

**Verification Method**:
1. Grep for all calls to functions being moved within `typescript_impl.py`
2. Document each call site with line number
3. Verify none are in conditional imports or dynamic calls

**Result**:
- [ ] CONFIRMED: All call sites identified and can be safely updated
- [ ] REJECTED: Complex call patterns found

**Evidence**:
```
Call sites for build_scope_map:
<TO BE FILLED>

Call sites for build_typescript_function_cfg:
<TO BE FILLED>

Call sites for helper functions:
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H2.6: Estimated Line Split
**Hypothesis**: After split:
- `typescript_impl.py`: ~1200 lines (14 public functions)
- `typescript_ast_utils.py`: ~800 lines (helpers + JSX + big functions)

**Verification Method**: After identifying all functions to move, estimate line counts.

**Result**:
- [ ] CONFIRMED: Split is roughly 60/40 as expected
- [ ] REJECTED: Split is unbalanced or estimates way off

**Evidence**:
```
Current file: <TOTAL_LINES> lines

Functions staying in typescript_impl.py: <ESTIMATED_LINES> lines
Functions moving to typescript_ast_utils.py: <ESTIMATED_LINES> lines
Imports and overhead: ~50 lines

Estimated split: <IMPL_LINES> / <UTILS_LINES>
```

**Discrepancies**: <TO BE FILLED>

---

## Phase 3 Hypotheses: ast_extractors/__init__.py Update

### H3.1: Current Exports
**Hypothesis**: `theauditor/ast_extractors/__init__.py` currently exports TypeScript implementation functions and does NOT export `js_semantic_parser`.

**Verification Method**: Read `__init__.py` completely.

**Result**:
- [ ] CONFIRMED: Current exports match expectations
- [ ] REJECTED: Unexpected exports or structure

**Evidence**:
```python
# Current __init__.py contents:
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

### H3.2: Required Export Addition
**Hypothesis**: Adding to `__init__.py`:
```python
from . import js_semantic_parser
```

Will make the module accessible as `theauditor.ast_extractors.js_semantic_parser` without breaking existing exports.

**Verification Method**: Review current exports for naming conflicts.

**Result**:
- [ ] CONFIRMED: No conflicts, safe to add
- [ ] REJECTED: Conflicts found

**Evidence**:
```
Current names in __init__.py namespace: <TO BE FILLED>
Conflicts with 'js_semantic_parser': <TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

## Critical Path Analysis

### Dependency Chain
**Hypothesis**: The refactor follows this dependency order:

1. **First**: Move `js_semantic_parser.py` to `ast_extractors/` (no dependencies on split)
2. **Second**: Update `ast_extractors/__init__.py` (depends on Step 1)
3. **Third**: Create shim at old location (depends on Steps 1-2)
4. **Fourth**: Create `typescript_ast_utils.py` (independent of Steps 1-3)
5. **Fifth**: Update `typescript_impl.py` imports and calls (depends on Step 4)

**Verification Method**: Analyze dependencies to confirm this order is safe.

**Result**:
- [ ] CONFIRMED: Order is correct and minimizes risk
- [ ] REJECTED: Dependencies require different order

**Evidence**:
```
Dependency analysis: <TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

## Test File Analysis

### H4.1: Test Coverage
**Hypothesis**: Tests exist that import and use `js_semantic_parser` and `typescript_impl` functions.

**Verification Method**:
1. Search `tests/` directory for imports
2. Read relevant test files
3. Document what they test

**Result**:
- [ ] CONFIRMED: Tests exist and will validate refactor
- [ ] REJECTED: No tests found (need to create validation tests)

**Evidence**:
```
Test files found:
<TO BE FILLED>

What they test:
<TO BE FILLED>
```

**Discrepancies**: <TO BE FILLED>

---

## Risk Assessment Based on Verification

### High Risk Items (MUST be verified)
- [ ] All import sites identified (missing one breaks production)
- [ ] No circular dependencies in split (causes import errors)
- [ ] Shim preserves all public API (breaks consumers)
- [ ] No module-level side effects (breaks initialization)

### Medium Risk Items (Should be verified)
- [ ] Test coverage exists (helps catch regressions)
- [ ] Line split is balanced (affects AI context window goal)
- [ ] Call site count is manageable (affects testing burden)

### Low Risk Items (Nice to verify)
- [ ] Function naming is clear (affects readability)
- [ ] Documentation is updated (affects maintainability)

---

## Verification Completion Checklist

Before marking verification complete, ALL of the following MUST be checked:

- [ ] H1.1: File location and size verified
- [ ] H1.2: All import consumers identified
- [ ] H1.3: Public API surface documented
- [ ] H1.4: Internal dependencies mapped
- [ ] H1.5: Shim feasibility confirmed
- [ ] H2.1: typescript_impl.py structure analyzed
- [ ] H2.2: Functions to move identified
- [ ] H2.3: Functions to keep identified
- [ ] H2.4: Import changes validated
- [ ] H2.5: All call sites documented
- [ ] H2.6: Line split estimated
- [ ] H3.1: ast_extractors/__init__.py exports verified
- [ ] H3.2: Export addition validated
- [ ] Dependency chain confirmed
- [ ] Test coverage assessed
- [ ] Risk assessment completed

**Verification Sign-Off**:
```
Verified by: <NAME>
Date: <DATE>
Discrepancies found: <COUNT>
All discrepancies resolved: YES/NO
Safe to proceed: YES/NO
```

---

## Notes and Observations

<Space for documenting unexpected findings during verification>

---

**CRITICAL REMINDER**: Per teamsop.md SOP v4.20, NO IMPLEMENTATION may begin until:
1. ALL hypotheses are tested
2. ALL discrepancies are documented and resolved
3. This document is marked VERIFICATION COMPLETE
4. Architect and Lead Auditor review and approve
