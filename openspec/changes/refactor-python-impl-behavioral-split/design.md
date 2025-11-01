# Technical Design: Python Implementation Behavioral Split

## Context

**Current Architecture (Problematic)**:
- python_impl.py: 2324 lines, 89KB, 43 functions
- Mixes stateless structural extraction with stateful behavioral analysis
- Marked DEPRECATED since Phase 2.1 (Oct 2025) but never actually split
- Still contains complete implementation despite deprecation notice

**Proven Pattern (TypeScript Implementation)**:
- typescript_impl.py: 1328 lines (behavioral layer)
- typescript_impl_structure.py: 1031 lines (structural layer)
- Clean separation: behavioral imports from structural (one-way dependency)
- ~55%/45% split ratio

**Python Package Reality**:
- python/ package exists and is ACTIVE (used in production via import alias)
- python_impl.py file is DEPRECATED (NOT used in production)
- Import alias: `from . import python as python_impl` (points to python/ package)

## Goals / Non-Goals

### Goals
1. Split python_impl.py into two layers matching TypeScript pattern:
   - python_impl_structure.py: Structural/stateless extraction (~1150 lines)
   - python_impl.py: Behavioral/context-dependent extraction (~1174 lines)
2. Establish one-way dependency: python_impl.py → python_impl_structure.py
3. Maintain 100% backward compatibility (no API changes)
4. Achieve ~50/50 split ratio (±5%)
5. Match TypeScript architecture documentation pattern

### Non-Goals
- NOT modifying the active python/ package (already modular)
- NOT changing any database schemas or output formats
- NOT affecting production code (python_impl.py is deprecated)
- NOT creating new extractors or adding functionality
- NOT removing python_impl.py yet (Phase 2.2 task)

## Decisions

### Decision 1: Split Boundary - Stateless vs Stateful

**Chosen Approach**: Separate by scope context dependency

**python_impl_structure.py** (Stateless/No Context Required):
- Core utilities: _get_type_annotation, _analyze_annotation_flags, _parse_function_type_comment
- Helper functions: _get_str_constant, _keyword_arg, _get_bool_constant
- Framework helpers: _cascade_implies_delete, _infer_relationship_type, _inverse_relationship_type
- Structural extractors: functions, classes, imports, exports, calls, properties
- Framework extractors (stateless): SQLAlchemy, Django, Pydantic, Flask, pytest, Celery, Marshmallow, WTForms
- Constants: SQLALCHEMY_BASE_IDENTIFIERS, DJANGO_MODEL_BASES, FASTAPI_HTTP_METHODS

**python_impl.py** (Stateful/Context-Dependent):
- Assignments: Uses find_containing_function_python() for scope resolution
- Returns: Uses find_containing_function_python() for function context
- Dict literals: Builds function_ranges for scope detection
- Calls with args: Builds function_ranges for caller context
- CFG: Stateful graph construction (build_python_function_cfg, process_python_statement)

**Rationale**:
- Matches TypeScript split exactly: structural (no scope map) vs behavioral (uses scope map)
- Clear separation of concerns
- Prevents circular dependencies
- Enables testing structural layer independently

**Alternatives Considered**:
- Split by feature domain (ORM, routes, etc.) - Rejected: Already done in python/ package
- Split by file size only - Rejected: Would mix concerns arbitrarily

### Decision 2: Import Strategy - One-Way Dependency

**Chosen Approach**: python_impl.py imports from python_impl_structure.py

```python
# python_impl_structure.py (self-contained)
from .base import get_node_name, extract_vars_from_expr

# python_impl.py (imports from structure)
from .base import find_containing_function_python, find_containing_class_python
from .python_impl_structure import (
    # Utilities
    _get_type_annotation,
    _analyze_annotation_flags,
    # Constants
    SQLALCHEMY_BASE_IDENTIFIERS,
    # Structural extractors (re-export for backward compatibility)
    extract_python_functions,
    extract_python_classes,
    # ... etc
)
```

**Rationale**:
- Prevents circular dependencies
- Matches TypeScript pattern exactly
- Structural layer can be tested independently
- Behavioral layer has clear dependencies

**Alternatives Considered**:
- Bi-directional imports - Rejected: Creates circular dependency risk
- Shared utilities module - Rejected: Over-engineering for 2-file split

### Decision 3: Backward Compatibility - Re-Export Pattern

**Chosen Approach**: Re-export all structural functions from python_impl.py

```python
# python_impl.py
from .python_impl_structure import (
    extract_python_functions,
    extract_python_classes,
    # ... all structural extractors
)

# Existing code continues working:
from theauditor.ast_extractors.python_impl import extract_python_functions  # ✓ Works
```

**Rationale**:
- Zero breaking changes for existing code
- python_impl.py remains single entry point
- Follows TypeScript pattern (typescript_impl.py re-exports from typescript_impl_structure.py)

**Alternatives Considered**:
- Require explicit imports from python_impl_structure.py - Rejected: Breaking change
- Use __all__ for selective exports - Rejected: Over-complicated

### Decision 4: Documentation Pattern - Match TypeScript

**Chosen Approach**: Mirror TypeScript module docstrings exactly

**python_impl_structure.py**:
```python
"""Python Structural AST Extraction Layer.

This module is Part 1 of the Python implementation layer split.

RESPONSIBILITY: Structural Extraction (Stateless AST Traversal)
=================================================================
...
CONSUMERS:
- python_impl.py (behavioral analysis layer)
- ast_extractors/__init__.py (orchestrator router)
"""
```

**python_impl.py**:
```python
"""Python Behavioral AST Extraction Layer.

This module is Part 2 of the Python implementation layer split.

RESPONSIBILITY: Behavioral Analysis (Context-Dependent Semantic Extraction)
================================================================================
...
DEPENDENCIES:
- find_containing_function_python: Function context resolution
- python_impl_structure.py: All structural extractors and utilities
"""
```

**Rationale**:
- Consistency across TypeScript and Python implementations
- Clear architectural contract
- Easy for developers to understand layer separation

## Risks / Trade-offs

### Risk 1: Split Complexity
**Risk**: Splitting may introduce subtle bugs if functions are miscategorized
**Mitigation**:
- Comprehensive verification checklist (tasks.md section 0)
- Read entire file before splitting (teamsop.md requirement)
- Test all re-exports work
- Side-by-side comparison with TypeScript split

### Risk 2: Future Confusion
**Risk**: Developers may not understand why deprecated file is being refactored
**Mitigation**:
- Extensive documentation in module docstrings
- Update DEPRECATION NOTICE explaining the split
- Reference TypeScript pattern in comments
- Clear "Phase 2.2 removal" plan

### Risk 3: Maintenance Burden
**Risk**: Two files to maintain instead of one (temporarily)
**Mitigation**:
- python_impl.py is already deprecated (not actively developed)
- Will be removed in Phase 2.2 per roadmap
- Active development happens in python/ package only

### Trade-off: Temporary Duplication
**Accepted**: python_impl.py (split) AND python/ package (modular) both exist temporarily
**Justification**:
- python/ package is production code (via import alias)
- python_impl.py is rollback safety net (deprecated)
- TypeScript has similar pattern (typescript_impl.py + javascript_extractor.js)
- Clear removal plan reduces long-term duplication

## Migration Plan

### Implementation Steps
1. Verification phase (tasks.md section 0) - Read, analyze, document
2. Create python_impl_structure.py with structural extractors
3. Refactor python_impl.py to behavioral + re-exports
4. Test imports and backward compatibility
5. Document architectural changes

### Testing Strategy
1. Static analysis (py_compile)
2. Import chain verification
3. Re-export verification
4. Line count verification (~50/50 split)
5. Dependency direction verification (no circular imports)

### Rollback Plan
**If issues occur**:
1. Revert commit (git revert)
2. python_impl.py remains as 2324-line monolith (unchanged from before)
3. Zero impact on production (python/ package unaffected)

### Deployment
- No deployment needed (refactor of deprecated code)
- No database changes
- No configuration changes
- No service restarts

## Open Questions

1. **Should we add scope mapping to Python like TypeScript has build_scope_map()?**
   - Decision: NO - Python already uses find_containing_function_python() directly
   - Rationale: Different AST structure, existing pattern works

2. **Should we split framework_extractors.py in python/ package similarly?**
   - Decision: OUT OF SCOPE for this proposal
   - Rationale: This proposal only affects deprecated python_impl.py file
   - Future work: Separate proposal for python/ package optimization

3. **When will python_impl.py be fully removed?**
   - Decision: Phase 2.2 (future milestone, not this proposal)
   - Rationale: Extended verification period per original Phase 2.1 plan
