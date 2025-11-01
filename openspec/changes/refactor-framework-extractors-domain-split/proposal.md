# Proposal: Refactor framework_extractors.py - Domain Split

**Change ID:** `refactor-framework-extractors-domain-split`
**Type:** Refactor
**Status:** Proposed
**Created:** 2025-11-01
**Author:** AI Lead Coder (Opus), Architect (Human)

---

## Executive Summary

Split `framework_extractors.py` (2222 lines) into domain-specific modules to improve maintainability and align with the existing modular Python extraction architecture. This refactor mirrors the successful `refactor-taint-schema-driven-architecture` pattern but focuses on file organization rather than algorithmic changes.

**Problem:** The file has grown 4x beyond its original scope as framework parity work added Django, Celery, GraphQL, validation frameworks, and serializers. Six distinct framework domains are now mixed in a single file.

**Solution:** Split into 4 domain-specific files + 1 backward-compatible re-export facade:
- `orm_extractors.py` - SQLAlchemy + Django ORM (~300 lines)
- `validation_extractors.py` - Pydantic, Marshmallow, DRF, WTForms (~1100 lines)
- `django_web_extractors.py` - CBVs, Forms, Admin, Middleware (~600 lines)
- `task_graphql_extractors.py` - Celery + GraphQL (Graphene, Ariadne, Strawberry) (~700 lines)
- `framework_extractors.py` - Re-export facade for backward compatibility

**Impact:** Zero breaking changes (backward-compatible re-exports). Code organization only.

---

## Context & Motivation

### Historical Background

**Previous Refactor (Oct 2024):**
The `refactor-taint-schema-driven-architecture` change successfully split taint analysis from 8,691 lines across 8 layers into ~2,000 lines across 3 layers. This established the pattern for large-scale Python refactors in TheAuditor.

**Framework Extractors Growth:**
- **Initial state (Phase 2.1):** 568 lines - SQLAlchemy, Django ORM, Flask, Pydantic basics
- **After Phase 2.2:** ~1200 lines - Added Celery task queue extraction
- **After Phase 3 (Framework Parity):** 2222 lines - Added Django CBVs, Forms, Admin, Middleware, Marshmallow, DRF, WTForms, GraphQL (Graphene/Ariadne/Strawberry)
- **Current state:** Unmanageable - 6 distinct framework domains in one file

### Why Now?

1. **Immediate Pain Point:** File is too large for effective code review and modification
2. **Pattern Established:** `python/__init__.py` already uses modular imports (core_extractors, flask_extractors, cfg_extractor, etc.)
3. **Future Growth:** FastAPI routes extraction (pending) would push file past 2500 lines
4. **Maintenance Burden:** Adding/modifying one framework requires scrolling through unrelated code

### The "Same Same But Different" Problem

Like the taint refactor, this is:
- **Same:** Large monolithic file grown beyond maintainability
- **Same:** Clear domain boundaries exist but are mixed together
- **Same:** Backward compatibility required (re-export pattern)
- **Different:** No algorithmic changes, only file organization
- **Different:** No schema generation, just moving code blocks

---

## Proposed Solution

### Domain Boundaries Analysis

**Current file structure (framework_extractors.py: 2222 lines):**
```
Lines 1-209:    Helper functions (shared across all)
Lines 215-514:  ORM extractors (SQLAlchemy, Django ORM)
Lines 517-1653: Validation/Serialization (Pydantic, Marshmallow, DRF, WTForms)
Lines 620-1120: Django Web (CBVs, Forms, Admin, Middleware) - interleaved!
Lines 1656-1980: Celery Task Queue (tasks, calls, schedules)
Lines 1987-2222: GraphQL (Graphene, Ariadne, Strawberry resolvers)
```

**Problem:** Django Web extractors (lines 620-1120) are INTERLEAVED with validation extractors (lines 517-1653). This indicates the file was grown organically without clear separation.

### File Split Strategy

Split into **4 domain files** + **1 facade**:

#### 1. `orm_extractors.py` (~350 lines)
**Scope:** Database ORM frameworks
- `extract_sqlalchemy_definitions()` - Models, fields, relationships
- `extract_django_definitions()` - Django ORM models, relationships
- **Shared helpers:** `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()`, `_cascade_implies_delete()`, `_extract_backref_name()`, `_extract_backref_cascade()`, `_infer_relationship_type()`, `_inverse_relationship_type()`, `_get_type_annotation()`
- **Rationale:** Both SQLAlchemy and Django extract ORM models/relationships. Shared semantic domain.

#### 2. `validation_extractors.py` (~1200 lines)
**Scope:** Input validation and data serialization frameworks
- `extract_pydantic_validators()` - Pydantic BaseModel validators
- `extract_marshmallow_schemas()` + `extract_marshmallow_fields()` - Marshmallow schemas
- `extract_drf_serializers()` + `extract_drf_serializer_fields()` - Django REST Framework
- `extract_wtforms_forms()` + `extract_wtforms_fields()` - WTForms
- **Shared helpers:** `_get_str_constant()`, `_keyword_arg()`, `_extract_list_of_strings()`
- **Rationale:** All frameworks validate user input and serialize data. Functional cohesion.

#### 3. `django_web_extractors.py` (~650 lines)
**Scope:** Django web framework patterns (non-ORM)
- `extract_django_cbvs()` - Class-Based Views (ListView, DetailView, etc.)
- `extract_django_forms()` + `extract_django_form_fields()` - Django forms
- `extract_django_admin()` - Django Admin customizations
- `extract_django_middleware()` - Django middleware classes
- **Shared helpers:** `_get_str_constant()`, `_keyword_arg()`, `_extract_list_of_strings()`, `DJANGO_CBV_TYPES` constant
- **Rationale:** All Django-specific web patterns. Framework cohesion.

#### 4. `task_graphql_extractors.py` (~750 lines)
**Scope:** Async task queues + GraphQL resolvers
- **Celery:** `extract_celery_tasks()`, `extract_celery_task_calls()`, `extract_celery_beat_schedules()`
- **GraphQL:** `extract_graphene_resolvers()`, `extract_ariadne_resolvers()`, `extract_strawberry_resolvers()`
- **Shared helpers:** `_get_str_constant()`, `_keyword_arg()`, `_dependency_name()` (FastAPI-related but used in GraphQL too)
- **Rationale:** Both are secondary framework patterns (background processing + API). Grouping reduces file count while maintaining domain separation.

#### 5. `framework_extractors.py` (FACADE - ~80 lines)
**Scope:** Backward-compatible re-exports
- Import all functions from the 4 new modules
- Re-export at module level for `from framework_extractors import extract_*` compatibility
- Keep `FASTAPI_HTTP_METHODS`, `_extract_fastapi_dependencies()` here (referenced by FastAPI route extraction in separate work)
- **Critical:** This file becomes the PUBLIC API. Existing code continues working unchanged.

### Helper Function Strategy

**Problem:** Many extractors share helpers like `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()`.

**Solution Options:**
1. **Duplicate helpers** in each file (simple, but violates DRY)
2. **Create `framework_helpers.py`** (adds indirection, extra import)
3. **Place helpers in each domain file** (use private `_` prefix, document as internal)

**Chosen:** Option 3 - **Place helpers in domain files**
- **Rationale:** Helpers are <50 lines total. Duplication is acceptable for 4-5 simple functions. Keeps files self-contained.
- **Implementation:** Copy `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()` into each of the 4 files. Mark as private (`_` prefix). Add docstring: "Internal helper - duplicated across files for self-containment."

---

## Implementation Plan

### Phase 1: Create New Files (No Breaking Changes)

1. **Create `orm_extractors.py`:**
   - Copy lines 215-514 (SQLAlchemy, Django ORM)
   - Copy shared helpers: `_get_str_constant()`, `_keyword_arg()`, `_get_bool_constant()`, etc.
   - Add module docstring explaining scope
   - Test imports: `from .orm_extractors import extract_sqlalchemy_definitions`

2. **Create `validation_extractors.py`:**
   - Copy lines 517-564 (Pydantic)
   - Copy lines 1123-1653 (Marshmallow, DRF, WTForms)
   - Copy shared helpers
   - Add module docstring

3. **Create `django_web_extractors.py`:**
   - Copy lines 620-1120 (CBVs, Forms, Admin, Middleware)
   - Copy shared helpers + `DJANGO_CBV_TYPES` constant
   - Add module docstring

4. **Create `task_graphql_extractors.py`:**
   - Copy lines 1656-1980 (Celery)
   - Copy lines 1987-2222 (GraphQL)
   - Copy shared helpers
   - Add module docstring

### Phase 2: Update `framework_extractors.py` to Re-Export

Replace current implementation with:
```python
"""Framework extractors - Backward-compatible facade.

This module re-exports all framework extraction functions from domain-specific modules.
Existing code using `from framework_extractors import extract_*` will continue working.

New code should import directly from domain modules:
  from .orm_extractors import extract_sqlalchemy_definitions
  from .validation_extractors import extract_pydantic_validators
  from .django_web_extractors import extract_django_cbvs
  from .task_graphql_extractors import extract_celery_tasks
"""

from .orm_extractors import (
    extract_sqlalchemy_definitions,
    extract_django_definitions,
)

from .validation_extractors import (
    extract_pydantic_validators,
    extract_marshmallow_schemas,
    extract_marshmallow_fields,
    extract_drf_serializers,
    extract_drf_serializer_fields,
    extract_wtforms_forms,
    extract_wtforms_fields,
)

from .django_web_extractors import (
    extract_django_cbvs,
    extract_django_forms,
    extract_django_form_fields,
    extract_django_admin,
    extract_django_middleware,
)

from .task_graphql_extractors import (
    extract_celery_tasks,
    extract_celery_task_calls,
    extract_celery_beat_schedules,
    extract_graphene_resolvers,
    extract_ariadne_resolvers,
    extract_strawberry_resolvers,
)

# Flask blueprints extraction (will be moved to flask_extractors.py in future PR)
from .orm_extractors import extract_flask_blueprints  # Temp: keep for backward compat

# FastAPI helpers (used by route extraction - keep here for now)
FASTAPI_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}

def _extract_fastapi_dependencies(func_node):
    # Implementation stays here (needed for FastAPI routes work)
    pass

__all__ = [
    # ORM
    'extract_sqlalchemy_definitions',
    'extract_django_definitions',
    # Validation
    'extract_pydantic_validators',
    'extract_marshmallow_schemas',
    'extract_marshmallow_fields',
    'extract_drf_serializers',
    'extract_drf_serializer_fields',
    'extract_wtforms_forms',
    'extract_wtforms_fields',
    # Django Web
    'extract_django_cbvs',
    'extract_django_forms',
    'extract_django_form_fields',
    'extract_django_admin',
    'extract_django_middleware',
    # Tasks + GraphQL
    'extract_celery_tasks',
    'extract_celery_task_calls',
    'extract_celery_beat_schedules',
    'extract_graphene_resolvers',
    'extract_ariadne_resolvers',
    'extract_strawberry_resolvers',
    # Flask (temp)
    'extract_flask_blueprints',
    # FastAPI helpers
    'FASTAPI_HTTP_METHODS',
    '_extract_fastapi_dependencies',
]
```

### Phase 3: Update `__init__.py` Imports

**Current (`python/__init__.py` lines 111-134):**
```python
from .framework_extractors import (
    # Framework extraction functions
    extract_sqlalchemy_definitions,
    extract_django_definitions,
    # ... 20+ functions ...
)
```

**After refactor (NO CHANGE):**
- Imports remain identical! Facade pattern ensures `from .framework_extractors import` still works
- Optional optimization: Import directly from domain modules (but not required for Phase 1)

### Phase 4: Verification & Testing

1. **Import verification:**
   ```bash
   python -c "from theauditor.ast_extractors.python import extract_sqlalchemy_definitions; print('OK')"
   python -c "from theauditor.ast_extractors.python.framework_extractors import extract_celery_tasks; print('OK')"
   ```

2. **Run existing tests:**
   ```bash
   pytest tests/test_python_framework_extraction.py -v
   ```

3. **Index test project:**
   ```bash
   cd tests/fixtures/python/realworld_project && aud index
   # Verify ORM, validation, Celery, Django patterns are extracted correctly
   ```

4. **Verify line counts:**
   ```bash
   wc -l theauditor/ast_extractors/python/orm_extractors.py
   wc -l theauditor/ast_extractors/python/validation_extractors.py
   wc -l theauditor/ast_extractors/python/django_web_extractors.py
   wc -l theauditor/ast_extractors/python/task_graphql_extractors.py
   wc -l theauditor/ast_extractors/python/framework_extractors.py  # Should be ~80 lines
   ```

---

## Risks & Mitigation

### Risk 1: Helper Function Duplication
**Risk:** Duplicating `_get_str_constant()` etc. in 4 files violates DRY.
**Mitigation:** Accept this trade-off. Functions are <10 lines each. Self-contained modules are worth the duplication. If helpers grow beyond 50 lines total, revisit with `framework_helpers.py`.

### Risk 2: Import Path Confusion
**Risk:** Developers unsure whether to import from facade or domain modules.
**Mitigation:**
- Document in facade docstring: "Existing code: use facade. New code: import from domain modules."
- Update `python/__init__.py` docstring with import guidelines
- No enforcement - both patterns work

### Risk 3: Flask Blueprints Misplacement
**Risk:** `extract_flask_blueprints()` is currently in `framework_extractors.py` but logically belongs in `flask_extractors.py`.
**Mitigation:** Keep in `orm_extractors.py` temporarily (it's only ~30 lines). Move to `flask_extractors.py` in separate PR to avoid scope creep.

### Risk 4: FastAPI Dependencies Function
**Risk:** `_extract_fastapi_dependencies()` is used by upcoming FastAPI route extraction but lives in `framework_extractors.py`.
**Mitigation:** Keep in facade file (`framework_extractors.py`). When FastAPI routes extraction is implemented, move it to a new `fastapi_extractors.py` file.

---

## Success Criteria

1. ✅ All 4 new domain files created with correct line counts
2. ✅ `framework_extractors.py` reduced from 2222 → ~80 lines (facade only)
3. ✅ All existing imports continue working (backward compatibility)
4. ✅ `pytest tests/test_python_framework_extraction.py` passes
5. ✅ `aud index tests/fixtures/python/realworld_project` extracts all framework patterns
6. ✅ No changes to database schema or extraction logic (code move only)
7. ✅ OpenSpec validation passes: `openspec validate --strict refactor-framework-extractors-domain-split`

---

## Alternative Approaches Considered

### Option A: 6-File Split (Rejected)
Split into 6 files: ORM, Validation, Django, Celery, GraphQL, Helpers
**Rejected:** Too granular. Celery + GraphQL are both <400 lines each. Combining them keeps file count manageable.

### Option B: 3-File Split (Rejected)
Split into: ORM, Web Frameworks (Django/Flask), Background Processing (Celery/GraphQL)
**Rejected:** "Web Frameworks" bucket is too broad - Django has 6 different extractors. Validation frameworks (Pydantic, Marshmallow, DRF, WTForms) deserve their own file.

### Option C: Extract All Helpers to `framework_helpers.py` (Rejected)
Create shared helper module.
**Rejected:** Adds indirection. Helpers are <10 lines each. Duplication is acceptable for self-contained modules.

---

## Alignment with Existing Patterns

This refactor aligns with established TheAuditor patterns:

1. **Modular Python Architecture:** `python/__init__.py` already splits extractors into `core_extractors.py`, `flask_extractors.py`, `cfg_extractor.py`, etc. This extends that pattern.

2. **Facade Re-Export Pattern:** `python/__init__.py` itself is a facade that re-exports from domain modules. We're applying the same pattern one level down.

3. **Backward Compatibility:** Like `python_impl.py` → `python/` package refactor, existing imports continue working. No breaking changes.

4. **File Size Targets:** Other extractor files range 200-800 lines. This refactor brings framework extractors into that range.

---

## Teamsop.md Protocol Compliance

This proposal follows **teamsop.md Prime Directive 1.2** (Assume Nothing, Verify Everything):

- ✅ Measured actual line counts (2222 lines)
- ✅ Traced import dependencies (`__init__.py` lines 111-134)
- ✅ Identified shared helpers by grepping for function usage
- ✅ Verified backward compatibility requirements (facade pattern)
- ✅ Checked existing tests (`test_python_framework_extraction.py`)

This proposal follows **teamsop.md Section 3** (OpenSpec Change Management):

- ✅ Created change directory: `openspec/changes/refactor-framework-extractors-domain-split/`
- ✅ Includes `proposal.md` (this file), `tasks.md` (next), `verification.md` (next)
- ✅ Will validate with `openspec validate --strict`

---

## Next Steps

1. **Architect Review:** Approve domain split strategy and file count (4 files + facade)
2. **Create `tasks.md`:** Checklist of implementation steps for AI Lead Coder
3. **Create `verification.md`:** Evidence that file split is necessary and proposed boundaries are correct
4. **Validate Proposal:** Run `openspec validate --strict refactor-framework-extractors-domain-split`
5. **Await Approval:** Wait for architect's GO/NO-GO decision before implementation

---

## References

- **Previous refactor:** `openspec/changes/refactor-taint-schema-driven-architecture/`
- **Python modular architecture:** `theauditor/ast_extractors/python/__init__.py`
- **Framework parity work:** `openspec/changes/add-framework-extraction-parity/`
- **Teamsop.md:** Project-level AI agent protocols
- **OpenSpec AGENTS.md:** Change management workflow
