# Refactor: Split python_impl.py into Behavioral and Structural Layers

## Why

**Problem**: python_impl.py has grown to 2324 lines (89KB, 43 functions) mixing stateless structural extraction with stateful behavioral analysis in a single monolithic file. This violates the proven architecture pattern established by the TypeScript implementation split.

**Evidence**:
- python_impl.py: 2324 lines (deprecated but still fully implemented)
- typescript_impl.py: 1328 lines (behavioral layer)
- typescript_impl_structure.py: 1031 lines (structural layer)
- TypeScript split achieves clean separation of concerns with ~50/50 split

**Root Cause**: Despite Phase 2.1 modular refactor (commit 1315823) creating the python/ package, the original python_impl.py file remains as a complete 2324-line monolith marked "DEPRECATED - kept for rollback safety only" but never actually split or removed.

## What Changes

Apply the proven typescript_impl.py refactor pattern to python_impl.py:

1. **Create python_impl_structure.py** (Structural/Stateless Layer) - ~1150 lines
   - Core utility functions (_get_type_annotation, _analyze_annotation_flags, etc.)
   - Scope mapping utilities (if needed for Python)
   - Structural extractors: functions, classes, calls, imports, exports
   - Framework constants (SQLALCHEMY_BASE_IDENTIFIERS, DJANGO_MODEL_BASES, FASTAPI_HTTP_METHODS)
   - Helper functions (_get_str_constant, _keyword_arg, _get_bool_constant, etc.)
   - NO behavioral analysis (no assignments, no returns, no CFG)

2. **Refactor python_impl.py** (Behavioral/Context-Dependent Layer) - ~1174 lines
   - Assignments (needs function context via find_containing_function_python)
   - Returns (needs function context)
   - CFG extraction (build_python_function_cfg, process_python_statement)
   - Dict literals extraction (needs function context)
   - Framework extractors that require context (FastAPI dependencies, relationship inference)
   - Re-export structural extractors from python_impl_structure.py for backward compatibility

3. **Establish Dependency Contract**
   - python_impl.py imports from python_impl_structure.py
   - python_impl_structure.py is self-contained with NO imports from python_impl.py
   - Matches TypeScript pattern: typescript_impl.py → typescript_impl_structure.py

4. **Maintain Backward Compatibility**
   - All existing imports continue working: `from theauditor.ast_extractors import python_impl`
   - All function signatures unchanged
   - No changes to database schema or output format

## Impact

**Affected Code**:
- theauditor/ast_extractors/python_impl.py - **BREAKING**: Split into two files
- NEW: theauditor/ast_extractors/python_impl_structure.py
- NO changes to python/ package (already modular and actively used)
- NO changes to any imports (python_impl.py remains the public API)

**Affected Specs**:
- ast-extraction (MODIFIED: Add layer separation requirements)

**Risk Level**: **LOW**
- Import alias still points to python/ package (`from . import python as python_impl`)
- python_impl.py file is already deprecated and NOT used in production
- This is a refactor of the deprecated file to match TypeScript architecture before eventual removal
- Zero impact on active python/ package which is the actual production code

**Migration Path**: NONE - This is a refactor of deprecated code matching TypeScript pattern
