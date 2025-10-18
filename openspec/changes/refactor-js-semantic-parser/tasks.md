# Implementation Tasks - JavaScript Semantic Parser Refactor

## 0. Verification (MANDATORY - Must Complete FIRST)

Per teamsop.md SOP v4.20, verification MUST happen before ANY code changes.

- [ ] 0.1 Read `js_semantic_parser.py` completely (all ~950 lines)
  - [ ] 0.1.1 Document exact line count
  - [ ] 0.1.2 Document all public API (classes, functions)
  - [ ] 0.1.3 Document all imports (internal and external)
  - [ ] 0.1.4 Verify no module-level side effects
  - [ ] 0.1.5 Update verification.md H1.1, H1.3, H1.4 with evidence

- [ ] 0.2 Find ALL import sites for `js_semantic_parser`
  - [ ] 0.2.1 Run: `grep -r "from theauditor.js_semantic_parser" --include="*.py"`
  - [ ] 0.2.2 Run: `grep -r "from theauditor import js_semantic_parser" --include="*.py"`
  - [ ] 0.2.3 Run: `grep -r "import theauditor.js_semantic_parser" --include="*.py"`
  - [ ] 0.2.4 Read EACH importing file to understand usage
  - [ ] 0.2.5 Document ALL importers in verification.md H1.2

- [ ] 0.3 Read `typescript_impl.py` completely (all ~2000 lines)
  - [ ] 0.3.1 Document exact line count
  - [ ] 0.3.2 Count and list all `extract_*` functions (public API)
  - [ ] 0.3.3 Count and list all helper functions (with `_` prefix)
  - [ ] 0.3.4 Identify ALL JSX-specific functions and constants
  - [ ] 0.3.5 Locate `build_scope_map` and ALL internal helpers
  - [ ] 0.3.6 Locate `build_typescript_function_cfg` and ALL internal helpers
  - [ ] 0.3.7 Update verification.md H2.1 with evidence

- [ ] 0.4 Map functions to move vs keep
  - [ ] 0.4.1 Create list of ALL functions to move to `typescript_ast_utils.py`
  - [ ] 0.4.2 Create list of ALL functions to keep in `typescript_impl.py`
  - [ ] 0.4.3 Estimate line count for each file after split
  - [ ] 0.4.4 Update verification.md H2.2, H2.3, H2.6 with evidence

- [ ] 0.5 Map function dependencies
  - [ ] 0.5.1 For EACH function being moved, identify what it calls
  - [ ] 0.5.2 For EACH function staying, identify what moved functions it calls
  - [ ] 0.5.3 Verify NO circular dependencies (utils never call impl)
  - [ ] 0.5.4 Document ALL call sites that need updating
  - [ ] 0.5.5 Update verification.md H2.4, H2.5 with evidence

- [ ] 0.6 Verify current imports in `typescript_impl.py`
  - [ ] 0.6.1 Document current import block (exact text)
  - [ ] 0.6.2 Verify `.base` module exists and exports expected functions
  - [ ] 0.6.3 Confirm no naming conflicts with `ast_utils` alias
  - [ ] 0.6.4 Update verification.md H2.4 with evidence

- [ ] 0.7 Read and analyze `ast_extractors/__init__.py`
  - [ ] 0.7.1 Document current exports (exact text)
  - [ ] 0.7.2 Verify no conflicts with `js_semantic_parser` name
  - [ ] 0.7.3 Update verification.md H3.1, H3.2 with evidence

- [ ] 0.8 Identify existing tests
  - [ ] 0.8.1 Search `tests/` for imports of `js_semantic_parser`
  - [ ] 0.8.2 Search `tests/` for imports from `typescript_impl`
  - [ ] 0.8.3 Read identified test files to understand coverage
  - [ ] 0.8.4 Update verification.md H4.1 with evidence

- [ ] 0.9 Complete verification document
  - [ ] 0.9.1 Fill in ALL evidence sections in verification.md
  - [ ] 0.9.2 Resolve ALL discrepancies found
  - [ ] 0.9.3 Mark verification.md as COMPLETE
  - [ ] 0.9.4 Request Architect and Lead Auditor review

- [ ] 0.10 **APPROVAL GATE**: DO NOT PROCEED TO SECTION 1 UNTIL:
  - [ ] Verification.md is 100% complete
  - [ ] All discrepancies are documented and resolved
  - [ ] Architect has reviewed and approved
  - [ ] Lead Auditor has reviewed and approved

---

## 1. Pre-Implementation Setup

- [ ] 1.1 Create backup branch
  ```bash
  git checkout -b backup/pre-js-parser-refactor
  git add .
  git commit -m "Backup before js_semantic_parser refactor"
  git checkout v1.1
  ```

- [ ] 1.2 Ensure working directory is clean
  ```bash
  git status  # Should show no uncommitted changes
  ```

- [ ] 1.3 Document baseline test results
  - [ ] 1.3.1 Run: `pytest tests/ -v` and save output
  - [ ] 1.3.2 Run: `aud index --exclude-self` and verify success
  - [ ] 1.3.3 Save `.pf/pipeline.log` as baseline

---

## 2. Phase 1 - Move js_semantic_parser.py

- [ ] 2.1 Move file to new location
  ```bash
  git mv theauditor/js_semantic_parser.py theauditor/ast_extractors/js_semantic_parser.py
  ```

- [ ] 2.2 Update internal imports in moved file
  - [ ] 2.2.1 Open `theauditor/ast_extractors/js_semantic_parser.py`
  - [ ] 2.2.2 Find: `from theauditor.ast_extractors import js_helper_templates`
  - [ ] 2.2.3 Replace with: `from . import js_helper_templates`
  - [ ] 2.2.4 Verify no other absolute imports of `theauditor.ast_extractors.*`
  - [ ] 2.2.5 Save file

- [ ] 2.3 Create shim at original location
  - [ ] 2.3.1 Create file: `theauditor/js_semantic_parser.py`
  - [ ] 2.3.2 Add content:
    ```python
    """Backward compatibility shim - imports from new location."""
    from theauditor.ast_extractors.js_semantic_parser import (
        JSSemanticParser,
        get_semantic_ast,
        get_semantic_ast_batch,
    )

    __all__ = ['JSSemanticParser', 'get_semantic_ast', 'get_semantic_ast_batch']
    ```
  - [ ] 2.3.3 Verify exports match verification.md H1.3 findings

- [ ] 2.4 Update ast_extractors/__init__.py
  - [ ] 2.4.1 Open `theauditor/ast_extractors/__init__.py`
  - [ ] 2.4.2 Add line: `from . import js_semantic_parser`
  - [ ] 2.4.3 Save file

- [ ] 2.5 Test Phase 1 changes
  - [ ] 2.5.1 Run import test (old location):
    ```bash
    python -c "from theauditor.js_semantic_parser import JSSemanticParser; print('✓ Old import works')"
    ```
  - [ ] 2.5.2 Run import test (new location):
    ```bash
    python -c "from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser; print('✓ New import works')"
    ```
  - [ ] 2.5.3 Run equivalence test:
    ```bash
    python -c "
    from theauditor.js_semantic_parser import JSSemanticParser as Old
    from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser as New
    assert Old is New, 'Shim broken!'
    print('✓ Import equivalence verified')
    "
    ```
  - [ ] 2.5.4 Run basic functionality test:
    ```bash
    aud index --exclude-self
    ```
  - [ ] 2.5.5 Check for errors in `.pf/pipeline.log`

- [ ] 2.6 Commit Phase 1
  ```bash
  git add .
  git commit -m "refactor(ast): move js_semantic_parser to ast_extractors/

  - Move js_semantic_parser.py to ast_extractors/ (logical location)
  - Create backward compatibility shim at original location
  - Update ast_extractors/__init__.py to export module

  BACKWARD COMPATIBLE: All existing imports work via shim.
  "
  ```

---

## 3. Phase 2 - Split typescript_impl.py

- [ ] 3.1 Create typescript_ast_utils.py
  - [ ] 3.1.1 Create file: `theauditor/ast_extractors/typescript_ast_utils.py`
  - [ ] 3.1.2 Add module docstring:
    ```python
    """TypeScript AST traversal utilities and low-level helpers.

    This module contains the implementation layer for TypeScript semantic analysis:
    - Low-level node inspection helpers
    - Core AST symbol extraction
    - JSX-specific detection and parsing
    - Complex algorithms (scope mapping, CFG building)

    This is an internal module - consumers should use typescript_impl.py instead.
    """
    ```
  - [ ] 3.1.3 Copy import block from `typescript_impl.py`:
    ```python
    import os
    from typing import Any, List, Dict, Optional
    from .base import (
        extract_vars_from_typescript_node,
        sanitize_call_name,
    )
    ```

- [ ] 3.2 Move low-level helper functions
  - [ ] 3.2.1 Copy `_strip_comment_prefix` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.2.2 Copy `_identifier_from_node` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.2.3 Copy `_canonical_member_name` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.2.4 Copy `_canonical_callee_from_call` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.2.5 Verify all 4 functions copied completely with no truncation

- [ ] 3.3 Move core symbol extractor
  - [ ] 3.3.1 Copy `extract_semantic_ast_symbols` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.3.2 Verify function copied completely with all internal logic

- [ ] 3.4 Move JSX-specific logic
  - [ ] 3.4.1 Copy `JSX_NODE_KINDS` constant from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.4.2 Copy `detect_jsx_in_node` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.4.3 Copy `extract_jsx_tag_name` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.4.4 Copy `analyze_create_element_component` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.4.5 Copy `check_for_jsx` alias from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.4.6 Verify all JSX functions copied completely

- [ ] 3.5 Move big algorithm: build_scope_map
  - [ ] 3.5.1 Copy `build_scope_map` function from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.5.2 Verify internal `collect_functions` helper is included
  - [ ] 3.5.3 Verify ALL logic within build_scope_map is copied

- [ ] 3.6 Move big algorithm: build_typescript_function_cfg
  - [ ] 3.6.1 Copy `build_typescript_function_cfg` from typescript_impl.py to typescript_ast_utils.py
  - [ ] 3.6.2 Verify ALL internal helpers are copied:
    - [ ] `process_node` (if internal to CFG builder)
    - [ ] `get_child_by_kind` (if internal to CFG builder)
    - [ ] Any other internal helpers (document if found)
  - [ ] 3.6.3 Verify entire CFG builder is copied

- [ ] 3.7 Verify typescript_ast_utils.py is complete
  - [ ] 3.7.1 Count lines in new file (should be ~800 lines per verification.md)
  - [ ] 3.7.2 Verify no syntax errors: `python -m py_compile theauditor/ast_extractors/typescript_ast_utils.py`
  - [ ] 3.7.3 Verify all moved functions are documented in comments

- [ ] 3.8 Update typescript_impl.py imports
  - [ ] 3.8.1 Open `theauditor/ast_extractors/typescript_impl.py`
  - [ ] 3.8.2 Add import after existing imports:
    ```python
    # Import low-level utilities from implementation layer
    from . import typescript_ast_utils as ast_utils
    ```
  - [ ] 3.8.3 Verify no naming conflicts with existing code

- [ ] 3.9 Remove moved functions from typescript_impl.py
  - [ ] 3.9.1 Delete `_strip_comment_prefix` definition
  - [ ] 3.9.2 Delete `_identifier_from_node` definition
  - [ ] 3.9.3 Delete `_canonical_member_name` definition
  - [ ] 3.9.4 Delete `_canonical_callee_from_call` definition
  - [ ] 3.9.5 Delete `extract_semantic_ast_symbols` definition
  - [ ] 3.9.6 Delete `JSX_NODE_KINDS` constant
  - [ ] 3.9.7 Delete `detect_jsx_in_node` definition
  - [ ] 3.9.8 Delete `extract_jsx_tag_name` definition
  - [ ] 3.9.9 Delete `analyze_create_element_component` definition
  - [ ] 3.9.10 Delete `check_for_jsx` alias
  - [ ] 3.9.11 Delete `build_scope_map` definition (and internal helpers)
  - [ ] 3.9.12 Delete `build_typescript_function_cfg` definition (and internal helpers)

- [ ] 3.10 Update call sites in typescript_impl.py
  - [ ] 3.10.1 Use verification.md H2.5 call site map as reference
  - [ ] 3.10.2 Find and replace ALL calls to moved functions:
    - [ ] `build_scope_map(` → `ast_utils.build_scope_map(`
    - [ ] `build_typescript_function_cfg(` → `ast_utils.build_typescript_function_cfg(`
    - [ ] `detect_jsx_in_node(` → `ast_utils.detect_jsx_in_node(`
    - [ ] `extract_jsx_tag_name(` → `ast_utils.extract_jsx_tag_name(`
    - [ ] `analyze_create_element_component(` → `ast_utils.analyze_create_element_component(`
    - [ ] `check_for_jsx(` → `ast_utils.check_for_jsx(`
    - [ ] `extract_semantic_ast_symbols(` → `ast_utils.extract_semantic_ast_symbols(`
    - [ ] `_canonical_member_name(` → `ast_utils._canonical_member_name(`
    - [ ] `_canonical_callee_from_call(` → `ast_utils._canonical_callee_from_call(`
    - [ ] `_identifier_from_node(` → `ast_utils._identifier_from_node(`
    - [ ] `_strip_comment_prefix(` → `ast_utils._strip_comment_prefix(`
  - [ ] 3.10.3 Verify ALL call sites updated (grep for each function name)

- [ ] 3.11 Verify typescript_impl.py after refactor
  - [ ] 3.11.1 Count lines (should be ~1200 lines per verification.md)
  - [ ] 3.11.2 Verify no syntax errors: `python -m py_compile theauditor/ast_extractors/typescript_impl.py`
  - [ ] 3.11.3 Verify ALL public `extract_*` functions still present
  - [ ] 3.11.4 Verify no undefined function calls (all use `ast_utils.` prefix)

- [ ] 3.12 Test Phase 2 changes
  - [ ] 3.12.1 Run import test:
    ```bash
    python -c "
    from theauditor.ast_extractors.typescript_impl import extract_typescript_functions
    from theauditor.ast_extractors import typescript_ast_utils
    print('✓ Imports successful')
    "
    ```
  - [ ] 3.12.2 Run basic functionality test:
    ```bash
    aud index --exclude-self
    ```
  - [ ] 3.12.3 Check for errors in `.pf/pipeline.log`
  - [ ] 3.12.4 Verify JavaScript/TypeScript files indexed:
    ```bash
    sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols WHERE file LIKE '%.ts' OR file LIKE '%.js';"
    ```

- [ ] 3.13 Commit Phase 2
  ```bash
  git add .
  git commit -m "refactor(ast): split typescript_impl into API and utils layers

  - Extract low-level helpers to typescript_ast_utils.py (~800 lines)
  - Keep public extract_* functions in typescript_impl.py (~1200 lines)
  - Update all call sites to use ast_utils namespace

  BACKWARD COMPATIBLE: All public API signatures unchanged.
  Improves AI discoverability - both files now fit in context window.
  "
  ```

---

## 4. Post-Implementation Testing

- [ ] 4.1 Create import validation test
  - [ ] 4.1.1 Create file: `tests/test_js_parser_refactor.py`
  - [ ] 4.1.2 Add test functions:
    ```python
    def test_shim_imports():
        """Verify old import location still works via shim."""
        from theauditor.js_semantic_parser import (
            JSSemanticParser,
            get_semantic_ast,
            get_semantic_ast_batch,
        )
        assert JSSemanticParser is not None
        assert callable(get_semantic_ast)
        assert callable(get_semantic_ast_batch)

    def test_new_imports():
        """Verify new import location works."""
        from theauditor.ast_extractors.js_semantic_parser import (
            JSSemanticParser,
            get_semantic_ast,
            get_semantic_ast_batch,
        )
        assert JSSemanticParser is not None
        assert callable(get_semantic_ast)
        assert callable(get_semantic_ast_batch)

    def test_import_equivalence():
        """Verify old and new imports resolve to same objects."""
        from theauditor.js_semantic_parser import JSSemanticParser as Old
        from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser as New
        assert Old is New, "Shim does not preserve object identity"

    def test_typescript_impl_split():
        """Verify typescript_impl can access utils."""
        from theauditor.ast_extractors import typescript_impl
        from theauditor.ast_extractors import typescript_ast_utils

        # Verify impl imports utils
        assert hasattr(typescript_impl, 'ast_utils')

        # Verify utils has expected functions
        assert hasattr(typescript_ast_utils, 'build_scope_map')
        assert hasattr(typescript_ast_utils, 'build_typescript_function_cfg')
    ```
  - [ ] 4.1.3 Run test: `pytest tests/test_js_parser_refactor.py -v`
  - [ ] 4.1.4 Verify ALL tests pass

- [ ] 4.2 Run full test suite
  - [ ] 4.2.1 Run: `pytest tests/ -v`
  - [ ] 4.2.2 Compare to baseline from task 1.3.1
  - [ ] 4.2.3 Verify no NEW failures
  - [ ] 4.2.4 Document any differences

- [ ] 4.3 Test on JavaScript/TypeScript project
  - [ ] 4.3.1 Navigate to test project with JS/TS code
  - [ ] 4.3.2 Run: `aud full`
  - [ ] 4.3.3 Verify pipeline completes successfully
  - [ ] 4.3.4 Check `.pf/pipeline.log` for errors
  - [ ] 4.3.5 Verify JS/TS files indexed:
    ```bash
    sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols WHERE file LIKE '%.ts' OR file LIKE '%.js';"
    ```

- [ ] 4.4 Test taint analysis on JS/TS
  - [ ] 4.4.1 Run: `aud taint-analyze`
  - [ ] 4.4.2 Verify taint analysis completes
  - [ ] 4.4.3 Check for JS/TS taint findings:
    ```bash
    sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE tool='taint' AND (file LIKE '%.ts' OR file LIKE '%.js');"
    ```
  - [ ] 4.4.4 Compare count to baseline (should be same or similar)

- [ ] 4.5 Test pattern detection on JS/TS
  - [ ] 4.5.1 Run: `aud detect-patterns`
  - [ ] 4.5.2 Verify pattern detection completes
  - [ ] 4.5.3 Check for JS/TS pattern findings:
    ```bash
    sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE tool='patterns' AND (file LIKE '%.ts' OR file LIKE '%.js');"
    ```
  - [ ] 4.5.4 Compare count to baseline (should be same or similar)

- [ ] 4.6 Verify file sizes meet AI context window goal
  - [ ] 4.6.1 Check `typescript_impl.py`: `wc -l theauditor/ast_extractors/typescript_impl.py`
  - [ ] 4.6.2 Verify <1500 lines (goal: ~1200)
  - [ ] 4.6.3 Check `typescript_ast_utils.py`: `wc -l theauditor/ast_extractors/typescript_ast_utils.py`
  - [ ] 4.6.4 Verify <1500 lines (goal: ~800)
  - [ ] 4.6.5 Document actual line counts

---

## 5. Post-Implementation Audit (Per teamsop.md SOP v4.20)

- [ ] 5.1 Re-read ALL modified files
  - [ ] 5.1.1 Read: `theauditor/js_semantic_parser.py` (shim)
  - [ ] 5.1.2 Read: `theauditor/ast_extractors/js_semantic_parser.py` (moved file)
  - [ ] 5.1.3 Read: `theauditor/ast_extractors/__init__.py`
  - [ ] 5.1.4 Read: `theauditor/ast_extractors/typescript_impl.py` (refactored)
  - [ ] 5.1.5 Read: `theauditor/ast_extractors/typescript_ast_utils.py` (new file)

- [ ] 5.2 Verify syntax correctness
  - [ ] 5.2.1 No syntax errors in any modified files
  - [ ] 5.2.2 No undefined variables or functions
  - [ ] 5.2.3 All imports resolve correctly
  - [ ] 5.2.4 No circular import issues

- [ ] 5.3 Verify logical correctness
  - [ ] 5.3.1 Shim exports match original module exports
  - [ ] 5.3.2 All moved functions have same signatures
  - [ ] 5.3.3 All call sites updated to use ast_utils prefix
  - [ ] 5.3.4 No duplicate function definitions

- [ ] 5.4 Verify no unintended side effects
  - [ ] 5.4.1 No new dependencies introduced
  - [ ] 5.4.2 No behavior changes in functions
  - [ ] 5.4.3 No performance regressions (test with timing if possible)
  - [ ] 5.4.4 No new warnings or deprecations

- [ ] 5.5 Document audit results
  - [ ] 5.5.1 All files syntactically correct: YES/NO
  - [ ] 5.5.2 All files logically correct: YES/NO
  - [ ] 5.5.3 No unintended side effects: YES/NO
  - [ ] 5.5.4 Ready for final commit: YES/NO

---

## 6. Documentation Updates

- [ ] 6.1 Update CLAUDE.md
  - [ ] 6.1.1 Update file structure diagram in "Indexer Package" section
  - [ ] 6.1.2 Document `js_semantic_parser.py` location change
  - [ ] 6.1.3 Document `typescript_impl.py` split
  - [ ] 6.1.4 Add note about backward compatibility shim

- [ ] 6.2 Update openspec/project.md (if applicable)
  - [ ] 6.2.1 Update any references to file locations
  - [ ] 6.2.2 Document new structure for future proposals

- [ ] 6.3 Add inline documentation
  - [ ] 6.3.1 Ensure shim has clear docstring explaining purpose
  - [ ] 6.3.2 Ensure `typescript_ast_utils.py` has module docstring
  - [ ] 6.3.3 Update `typescript_impl.py` docstring if needed

---

## 7. Final Commit and Validation

- [ ] 7.1 Final code quality checks
  - [ ] 7.1.1 Run: `ruff check theauditor/ast_extractors/ --fix`
  - [ ] 7.1.2 Run: `ruff format theauditor/ast_extractors/`
  - [ ] 7.1.3 Run: `black theauditor/ast_extractors/` (if preferred)
  - [ ] 7.1.4 Verify no linting errors remain

- [ ] 7.2 Commit documentation updates
  ```bash
  git add .
  git commit -m "docs: update documentation for js_semantic_parser refactor

  - Update CLAUDE.md file structure diagrams
  - Document shim pattern and new locations
  - Add module docstrings for new files
  "
  ```

- [ ] 7.3 Final validation checklist
  - [ ] All verification hypotheses tested and resolved
  - [ ] All implementation tasks completed
  - [ ] All tests passing (import, regression, functional)
  - [ ] Both split files fit in AI context window
  - [ ] Documentation updated
  - [ ] Code quality checks passed
  - [ ] Post-implementation audit completed
  - [ ] No syntax errors or warnings
  - [ ] Full pipeline runs successfully on test project

- [ ] 7.4 Create completion report (per teamsop.md Template C-4.20)
  - [ ] 7.4.1 Document verification findings
  - [ ] 7.4.2 Document root cause (discoverability + monolith)
  - [ ] 7.4.3 Document implementation details
  - [ ] 7.4.4 Document edge cases considered
  - [ ] 7.4.5 Document post-implementation audit results
  - [ ] 7.4.6 Document impact assessment
  - [ ] 7.4.7 Document testing performed
  - [ ] 7.4.8 Confirm understanding and confidence level

- [ ] 7.5 Request final review
  - [ ] 7.5.1 Submit completion report to Architect
  - [ ] 7.5.2 Submit completion report to Lead Auditor
  - [ ] 7.5.3 Address any feedback or concerns
  - [ ] 7.5.4 Obtain final approval

---

## 8. Success Criteria

Refactor is considered COMPLETE when ALL of the following are true:

- [x] **Verification Complete**: All hypotheses tested, all evidence documented
- [x] **Phase 1 Complete**: js_semantic_parser.py moved with working shim
- [x] **Phase 2 Complete**: typescript_impl.py split into two files
- [x] **Backward Compatible**: All existing imports work unchanged
- [x] **Tests Pass**: Import tests, regression tests, functional tests all pass
- [x] **AI Context Goal**: Both typescript files <1500 lines each
- [x] **Documentation Updated**: CLAUDE.md and inline docs reflect changes
- [x] **Audit Complete**: Post-implementation audit confirms correctness
- [x] **Approved**: Architect and Lead Auditor approve completion

---

## Rollback Procedure (If Needed)

If ANY critical issue is discovered:

1. **Stop immediately** - Do not proceed with remaining tasks
2. **Document the issue** - What went wrong and why
3. **Revert changes**:
   ```bash
   # Option 1: Revert last commit(s)
   git log  # Find commit hashes
   git revert <commit-hash>

   # Option 2: Restore from backup
   git checkout backup/pre-js-parser-refactor
   git checkout -b v1.1-rollback
   ```
4. **Verify rollback**: Run tests to confirm system is back to working state
5. **Analyze failure**: Update verification.md with findings
6. **Revise plan**: Update proposal and design docs based on learnings
7. **Retry**: Only after approval of revised plan

---

**Total Estimated Time**: 7-11 hours
- Verification: 4-6 hours
- Implementation: 2-3 hours
- Testing: 1-2 hours

**Priority**: CRITICAL - 50% of tool depends on JavaScript/TypeScript analysis
