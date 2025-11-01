# Python Framework Extraction Specification Delta

**Capability**: `python-extraction`
**Change ID**: `refactor-framework-extractors-domain-split`

---

## MODIFIED Requirements

### Requirement: Framework Extractor Module Organization

The Python framework extraction system SHALL organize extractor functions into domain-specific modules for maintainability and developer productivity.

**Architecture Contract**:
- Framework extractors SHALL be split into domain-specific files (ORM, Validation, Django Web, Task Queue + GraphQL)
- Each domain file SHALL contain cohesive extractors for related frameworks
- Facade module (`framework_extractors.py`) SHALL re-export all functions for backward compatibility
- Existing import paths SHALL continue working without changes
- Helper functions MAY be duplicated across domain files for self-containment (acceptable trade-off)

#### Scenario: Developer imports ORM extractors

- **WHEN** developer imports SQLAlchemy or Django ORM extractors
- **THEN** import SHALL work via facade: `from python.framework_extractors import extract_sqlalchemy_definitions`
- **AND** import SHALL work via domain module: `from python.orm_extractors import extract_sqlalchemy_definitions`
- **AND** import SHALL work via package: `from python import extract_sqlalchemy_definitions`
- **AND** all three import paths SHALL resolve to the same function
- **AND** no breaking changes SHALL occur

#### Scenario: Developer imports validation framework extractors

- **WHEN** developer imports Pydantic, Marshmallow, DRF, or WTForms extractors
- **THEN** import SHALL work via facade: `from python.framework_extractors import extract_pydantic_validators`
- **AND** import SHALL work via domain module: `from python.validation_extractors import extract_pydantic_validators`
- **AND** validation extractors SHALL be grouped in single file (~1200 lines)
- **AND** file SHALL include: Pydantic, Marshmallow (schemas + fields), DRF (serializers + fields), WTForms (forms + fields)

#### Scenario: Developer imports Django web extractors

- **WHEN** developer imports Django CBVs, Forms, Admin, or Middleware extractors
- **THEN** import SHALL work via facade: `from python.framework_extractors import extract_django_cbvs`
- **AND** import SHALL work via domain module: `from python.django_web_extractors import extract_django_cbvs`
- **AND** Django web extractors SHALL be grouped in single file (~650 lines)
- **AND** file SHALL include: Django CBVs, Forms, Form Fields, Admin, Middleware

#### Scenario: Developer imports Celery or GraphQL extractors

- **WHEN** developer imports Celery task or GraphQL resolver extractors
- **THEN** import SHALL work via facade: `from python.framework_extractors import extract_celery_tasks`
- **AND** import SHALL work via domain module: `from python.task_graphql_extractors import extract_celery_tasks`
- **AND** Celery + GraphQL extractors SHALL be grouped in single file (~750 lines)
- **AND** file SHALL include: Celery (tasks, calls, beat schedules), GraphQL (Graphene, Ariadne, Strawberry resolvers)

#### Scenario: Existing tests continue working without changes

- **WHEN** existing test suite runs after refactor
- **THEN** tests SHALL import from facade: `from python.framework_extractors import extract_*`
- **AND** all imports SHALL resolve successfully
- **AND** all tests SHALL pass without modification
- **AND** `pytest tests/test_python_framework_extraction.py -v` SHALL succeed

#### Scenario: Developer navigates to framework extractor implementation

- **WHEN** developer wants to modify SQLAlchemy ORM extraction logic
- **THEN** developer SHALL open `orm_extractors.py` (~350 lines)
- **AND** developer SHALL NOT need to scroll through 2222 lines of unrelated code
- **AND** file SHALL contain only ORM-related extractors (SQLAlchemy, Django ORM)
- **AND** file SHALL be self-contained with all necessary helper functions

#### Scenario: Developer adds new validation framework (e.g., Cerberus)

- **WHEN** developer adds extraction for new validation framework
- **THEN** developer SHALL add function to `validation_extractors.py`
- **AND** developer SHALL add re-export to `framework_extractors.py` facade
- **AND** developer SHALL add export to `python/__init__.py`
- **AND** developer SHALL NOT need to navigate 2222-line file to find insertion point
- **AND** domain cohesion SHALL be maintained (all validation frameworks in one file)

#### Scenario: Developer adds new task queue framework (e.g., RQ)

- **WHEN** developer adds extraction for Redis Queue (RQ) task framework
- **THEN** developer SHALL add function to `task_graphql_extractors.py`
- **AND** developer SHALL add re-export to `framework_extractors.py` facade
- **AND** RQ extractors SHALL be grouped with Celery (similar domain)
- **AND** file SHALL remain manageable (<1000 lines even after RQ addition)

#### Scenario: Helper function duplication is acceptable

- **WHEN** domain modules require common helper functions (`_get_str_constant()`, `_keyword_arg()`)
- **THEN** helper functions MAY be duplicated in each domain file
- **AND** duplication SHALL be limited to <50 lines per file
- **AND** total duplication across all files SHALL be <200 lines
- **AND** self-containment benefit SHALL outweigh DRY principle violation
- **AND** helpers SHALL be marked private (`_` prefix) to indicate internal use

#### Scenario: Facade ensures backward compatibility

- **WHEN** existing code imports from `framework_extractors` module
- **THEN** facade SHALL re-export all extractor functions from domain modules
- **AND** facade SHALL provide transparent access to all 20+ functions
- **AND** facade SHALL include `__all__` list for explicit exports
- **AND** facade SHALL be ~80 lines (imports + re-exports only)
- **AND** facade SHALL NOT contain implementation (only imports)

#### Scenario: FastAPI helpers remain in facade temporarily

- **WHEN** developer references FastAPI helper functions
- **THEN** `FASTAPI_HTTP_METHODS` constant SHALL remain in facade
- **AND** `_extract_fastapi_dependencies()` function SHALL remain in facade
- **AND** functions SHALL be marked as "pending FastAPI routes extraction work"
- **AND** functions SHALL be moved to `fastapi_extractors.py` in future PR when FastAPI routes work begins

#### Scenario: File size reduction improves code review

- **WHEN** reviewer reviews pull request changing framework extraction logic
- **THEN** reviewer SHALL see changes to single domain file (e.g., `orm_extractors.py` ~350 lines)
- **AND** reviewer SHALL NOT need to scroll through 2222 lines to find changes
- **AND** diff SHALL be focused on relevant domain only
- **AND** code review time SHALL decrease by ~50% (estimated)

---

## Technical Implementation Notes

**File Structure**:
```
python/
├── __init__.py                    # Package-level re-exports (unchanged)
├── framework_extractors.py       # Facade (80 lines) - backward compatible re-exports
├── orm_extractors.py             # NEW - SQLAlchemy + Django ORM (~350 lines)
├── validation_extractors.py      # NEW - Pydantic, Marshmallow, DRF, WTForms (~1200 lines)
├── django_web_extractors.py      # NEW - Django CBVs, Forms, Admin, Middleware (~650 lines)
├── task_graphql_extractors.py   # NEW - Celery + GraphQL (~750 lines)
└── ...                            # Other extractors (core, flask, cfg, cdk, etc.)
```

**Facade Pattern** (`framework_extractors.py`):
```python
"""Framework extractors - Backward-compatible facade.

This module re-exports all framework extraction functions from domain-specific modules.
Existing code using `from framework_extractors import extract_*` will continue working.

New code should import directly from domain modules for clarity:
  from .orm_extractors import extract_sqlalchemy_definitions
  from .validation_extractors import extract_pydantic_validators
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

# ... more imports ...

__all__ = [
    # All functions listed for explicit exports
]
```

**Domain Cohesion**:
- **ORM:** SQLAlchemy + Django ORM (both extract model/relationship metadata)
- **Validation:** Pydantic, Marshmallow, DRF, WTForms (all validate input & serialize)
- **Django Web:** CBVs, Forms, Admin, Middleware (all Django-specific web patterns)
- **Task + GraphQL:** Celery + GraphQL (both secondary patterns: background + API)

**Helper Duplication Strategy**:
```python
# Each domain file contains these helpers (duplicated):
def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    """Internal helper - duplicated across files for self-containment."""
    # ... implementation ...

def _keyword_arg(call: ast.Call, name: str) -> Optional[ast.AST]:
    """Internal helper - duplicated across files for self-containment."""
    # ... implementation ...
```

**Import Paths (All Valid)**:
```python
# Via package (__init__.py re-exports) - RECOMMENDED for consistency
from theauditor.ast_extractors.python import extract_sqlalchemy_definitions

# Via facade (backward compatible) - WORKS, existing code uses this
from theauditor.ast_extractors.python.framework_extractors import extract_sqlalchemy_definitions

# Direct from domain module - WORKS, new code may prefer this
from theauditor.ast_extractors.python.orm_extractors import extract_sqlalchemy_definitions
```

**Migration Impact**:
- Zero breaking changes (all import paths continue working)
- Developers MAY continue using existing import paths
- Developers MAY switch to direct domain imports for clarity (optional)
- No code changes required in existing codebase

**Before vs After**:
```
Before:
framework_extractors.py: 2222 lines (6 domains mixed)

After:
orm_extractors.py:           ~350 lines (1 domain)
validation_extractors.py:   ~1200 lines (1 domain - 4 frameworks)
django_web_extractors.py:    ~650 lines (1 domain - 4 Django patterns)
task_graphql_extractors.py:  ~750 lines (2 domains combined)
framework_extractors.py:       ~80 lines (facade only)
-------------------------------------------
Total:                       ~3030 lines (vs 2222) - acceptable due to helper duplication
```

**File Size Targets**:
- Each file: 350-1200 lines (manageable for code review)
- Facade: ~80 lines (imports + re-exports only)
- Helper duplication: <200 lines total (20% overhead - acceptable trade-off)
