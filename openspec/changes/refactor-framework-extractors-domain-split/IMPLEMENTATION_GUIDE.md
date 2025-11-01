# IMPLEMENTATION GUIDE: Framework Extractors Domain Split

**For AI Executors:** This is your assembly manual. Follow it step-by-step. NO THINKING REQUIRED.

**Current File:** `C:\Users\santa\Desktop\TheAuditor\theauditor\ast_extractors\python\framework_extractors.py` (2222 lines)

---

## PART 1: Function Inventory (What Exists Now)

### Helper Functions (13 total)

| Line | Function | Used By | Destination |
|------|----------|---------|-------------|
| 61 | `_get_str_constant()` | ALL | Duplicate in all 4 files |
| 72 | `_keyword_arg()` | ALL | Duplicate in all 4 files |
| 80 | `_get_bool_constant()` | SQLAlchemy, Django ORM, Celery | orm_extractors.py + task_graphql_extractors.py |
| 92 | `_cascade_implies_delete()` | SQLAlchemy only | orm_extractors.py |
| 100 | `_extract_backref_name()` | SQLAlchemy only | orm_extractors.py |
| 112 | `_extract_backref_cascade()` | SQLAlchemy only | orm_extractors.py |
| 128 | `_infer_relationship_type()` | SQLAlchemy only | orm_extractors.py |
| 150 | `_inverse_relationship_type()` | SQLAlchemy only | orm_extractors.py |
| 162 | `_is_truthy()` | SQLAlchemy only | orm_extractors.py |
| 170 | `_dependency_name()` | GraphQL (future FastAPI) | task_graphql_extractors.py |
| 185 | `_extract_fastapi_dependencies()` | NOT USED YET | KEEP IN FACADE |
| 404 | `_get_type_annotation()` | SQLAlchemy only | orm_extractors.py |
| 1021 | `_extract_list_of_strings()` | Django Admin, DRF | django_web_extractors.py + validation_extractors.py |

### Constants (3 total)

| Line | Constant | Used By | Destination |
|------|----------|---------|-------------|
| 34 | `SQLALCHEMY_BASE_IDENTIFIERS` | SQLAlchemy | orm_extractors.py |
| 41 | `DJANGO_MODEL_BASES` | Django ORM | orm_extractors.py |
| 46 | `FASTAPI_HTTP_METHODS` | NOT USED YET | KEEP IN FACADE |
| 600 | `DJANGO_CBV_TYPES` | Django CBVs | django_web_extractors.py |

### Extractor Functions (20 total)

| Line | Function | Destination File |
|------|----------|-----------------|
| 215 | `extract_sqlalchemy_definitions()` | orm_extractors.py |
| 416 | `extract_django_definitions()` | orm_extractors.py |
| 517 | `extract_pydantic_validators()` | validation_extractors.py |
| 567 | `extract_flask_blueprints()` | orm_extractors.py (TEMP - see notes) |
| 620 | `extract_django_cbvs()` | django_web_extractors.py |
| 757 | `extract_django_forms()` | django_web_extractors.py |
| 828 | `extract_django_form_fields()` | django_web_extractors.py |
| 909 | `extract_django_admin()` | django_web_extractors.py |
| 1035 | `extract_django_middleware()` | django_web_extractors.py |
| 1123 | `extract_marshmallow_schemas()` | validation_extractors.py |
| 1199 | `extract_marshmallow_fields()` | validation_extractors.py |
| 1300 | `extract_drf_serializers()` | validation_extractors.py |
| 1385 | `extract_drf_serializer_fields()` | validation_extractors.py |
| 1497 | `extract_wtforms_forms()` | validation_extractors.py |
| 1567 | `extract_wtforms_fields()` | validation_extractors.py |
| 1656 | `extract_celery_tasks()` | task_graphql_extractors.py |
| 1763 | `extract_celery_task_calls()` | task_graphql_extractors.py |
| 1865 | `extract_celery_beat_schedules()` | task_graphql_extractors.py |
| 1987 | `extract_graphene_resolvers()` | task_graphql_extractors.py |
| 2058 | `extract_ariadne_resolvers()` | task_graphql_extractors.py |
| 2144 | `extract_strawberry_resolvers()` | task_graphql_extractors.py |

---

## PART 2: File-by-File Instructions

### File 1: orm_extractors.py (~400 lines)

**Copy these lines from framework_extractors.py:**
```
Lines 1-27:   Module docstring (EDIT to say "ORM extractors")
Lines 21-25:  Imports (keep as-is)
Lines 34-44:  Constants: SQLALCHEMY_BASE_IDENTIFIERS, DJANGO_MODEL_BASES
Lines 61-69:  Helper: _get_str_constant()
Lines 72-77:  Helper: _keyword_arg()
Lines 80-89:  Helper: _get_bool_constant()
Lines 92-97:  Helper: _cascade_implies_delete()
Lines 100-109: Helper: _extract_backref_name()
Lines 112-125: Helper: _extract_backref_cascade()
Lines 128-147: Helper: _infer_relationship_type()
Lines 150-159: Helper: _inverse_relationship_type()
Lines 162-167: Helper: _is_truthy()
Lines 404-413: Helper: _get_type_annotation()
Lines 215-400: Function: extract_sqlalchemy_definitions()
Lines 416-514: Function: extract_django_definitions()
Lines 567-596: Function: extract_flask_blueprints() (TEMPORARY - add TODO comment)
```

**Expected Line Count:** ~400 lines

**Skeleton Template:**
```python
"""ORM framework extractors - SQLAlchemy and Django ORM.

This module extracts database ORM patterns:
- SQLAlchemy: Models, fields, relationships (1:1, 1:N, M:N)
- Django ORM: Models, relationships, ForeignKey/ManyToMany
- Flask: Blueprints (TEMPORARY - will move to flask_extractors.py)

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'model_name', 'field_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# ORM Detection Constants
# ============================================================================

# TODO: Copy SQLALCHEMY_BASE_IDENTIFIERS from line 34
# TODO: Copy DJANGO_MODEL_BASES from line 41


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

# TODO: Copy _get_str_constant() from line 61
# TODO: Copy _keyword_arg() from line 72
# TODO: Copy _get_bool_constant() from line 80
# TODO: Copy _cascade_implies_delete() from line 92
# TODO: Copy _extract_backref_name() from line 100
# TODO: Copy _extract_backref_cascade() from line 112
# TODO: Copy _infer_relationship_type() from line 128
# TODO: Copy _inverse_relationship_type() from line 150
# TODO: Copy _is_truthy() from line 162
# TODO: Copy _get_type_annotation() from line 404


# ============================================================================
# ORM Extractors
# ============================================================================

# TODO: Copy extract_sqlalchemy_definitions() from line 215
# TODO: Copy extract_django_definitions() from line 416
# TODO: Copy extract_flask_blueprints() from line 567 (add comment: "TEMP - move to flask_extractors.py in future PR")
```

---

### File 2: validation_extractors.py (~1200 lines)

**Copy these lines from framework_extractors.py:**
```
Lines 1-27:   Module docstring (EDIT to say "Validation extractors")
Lines 21-25:  Imports (keep as-is)
Lines 61-69:  Helper: _get_str_constant()
Lines 72-77:  Helper: _keyword_arg()
Lines 1021-1032: Helper: _extract_list_of_strings()
Lines 517-564: Function: extract_pydantic_validators()
Lines 1123-1196: Function: extract_marshmallow_schemas()
Lines 1199-1297: Function: extract_marshmallow_fields()
Lines 1300-1382: Function: extract_drf_serializers()
Lines 1385-1494: Function: extract_drf_serializer_fields()
Lines 1497-1564: Function: extract_wtforms_forms()
Lines 1567-1653: Function: extract_wtforms_fields()
```

**Expected Line Count:** ~1200 lines

**Skeleton Template:**
```python
"""Validation and serialization framework extractors.

This module extracts input validation and data serialization patterns:
- Pydantic: BaseModel validators (@validator, @root_validator)
- Marshmallow: Schema definitions and field validations
- Django REST Framework: Serializers and field definitions
- WTForms: Form definitions and field validators

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'model_name', 'field_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

# TODO: Copy _get_str_constant() from line 61
# TODO: Copy _keyword_arg() from line 72
# TODO: Copy _extract_list_of_strings() from line 1021


# ============================================================================
# Validation Framework Extractors
# ============================================================================

# TODO: Copy extract_pydantic_validators() from line 517
# TODO: Copy extract_marshmallow_schemas() from line 1123
# TODO: Copy extract_marshmallow_fields() from line 1199
# TODO: Copy extract_drf_serializers() from line 1300
# TODO: Copy extract_drf_serializer_fields() from line 1385
# TODO: Copy extract_wtforms_forms() from line 1497
# TODO: Copy extract_wtforms_fields() from line 1567
```

---

### File 3: django_web_extractors.py (~700 lines)

**Copy these lines from framework_extractors.py:**
```
Lines 1-27:   Module docstring (EDIT to say "Django web extractors")
Lines 21-25:  Imports (keep as-is)
Lines 61-69:  Helper: _get_str_constant()
Lines 72-77:  Helper: _keyword_arg()
Lines 1021-1032: Helper: _extract_list_of_strings()
Lines 600-617: Constant: DJANGO_CBV_TYPES
Lines 620-754: Function: extract_django_cbvs()
Lines 757-825: Function: extract_django_forms()
Lines 828-906: Function: extract_django_form_fields()
Lines 909-1018: Function: extract_django_admin()
Lines 1035-1120: Function: extract_django_middleware()
```

**Expected Line Count:** ~700 lines

**Skeleton Template:**
```python
"""Django web framework extractors (non-ORM patterns).

This module extracts Django-specific web patterns:
- Class-Based Views (CBVs): ListView, DetailView, CreateView, UpdateView, DeleteView, etc.
- Forms: Django Form and ModelForm definitions with field validation
- Admin: ModelAdmin customizations (list_display, list_filter, search_fields, etc.)
- Middleware: Middleware class definitions and hooks

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'view_class_name', 'form_class_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Django CBV Type Mapping
# ============================================================================

# TODO: Copy DJANGO_CBV_TYPES from line 600


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

# TODO: Copy _get_str_constant() from line 61
# TODO: Copy _keyword_arg() from line 72
# TODO: Copy _extract_list_of_strings() from line 1021


# ============================================================================
# Django Web Extractors
# ============================================================================

# TODO: Copy extract_django_cbvs() from line 620
# TODO: Copy extract_django_forms() from line 757
# TODO: Copy extract_django_form_fields() from line 828
# TODO: Copy extract_django_admin() from line 909
# TODO: Copy extract_django_middleware() from line 1035
```

---

### File 4: task_graphql_extractors.py (~800 lines)

**Copy these lines from framework_extractors.py:**
```
Lines 1-27:   Module docstring (EDIT to say "Task queue and GraphQL extractors")
Lines 21-25:  Imports (keep as-is)
Lines 61-69:  Helper: _get_str_constant()
Lines 72-77:  Helper: _keyword_arg()
Lines 80-89:  Helper: _get_bool_constant()
Lines 170-182: Helper: _dependency_name()
Lines 1656-1760: Function: extract_celery_tasks()
Lines 1763-1862: Function: extract_celery_task_calls()
Lines 1865-1980: Function: extract_celery_beat_schedules()
Lines 1987-2055: Function: extract_graphene_resolvers()
Lines 2058-2141: Function: extract_ariadne_resolvers()
Lines 2144-2222: Function: extract_strawberry_resolvers()
```

**Expected Line Count:** ~800 lines

**Skeleton Template:**
```python
"""Task queue and GraphQL resolver extractors.

This module extracts async task queue and GraphQL resolver patterns:
- Celery: Task definitions (@task, @shared_task), task invocations (.delay, .apply_async), Beat schedules
- GraphQL (Graphene): resolve_* methods in ObjectType classes
- GraphQL (Ariadne): @query.field, @mutation.field decorators
- GraphQL (Strawberry): @strawberry.field decorators

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'task_name', 'resolver_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

# TODO: Copy _get_str_constant() from line 61
# TODO: Copy _keyword_arg() from line 72
# TODO: Copy _get_bool_constant() from line 80
# TODO: Copy _dependency_name() from line 170


# ============================================================================
# Celery Task Queue Extractors
# ============================================================================

# TODO: Copy extract_celery_tasks() from line 1656
# TODO: Copy extract_celery_task_calls() from line 1763
# TODO: Copy extract_celery_beat_schedules() from line 1865


# ============================================================================
# GraphQL Resolver Extractors
# ============================================================================

# TODO: Copy extract_graphene_resolvers() from line 1987
# TODO: Copy extract_ariadne_resolvers() from line 2058
# TODO: Copy extract_strawberry_resolvers() from line 2144
```

---

### File 5: framework_extractors.py (FACADE - ~120 lines)

**REPLACE ENTIRE FILE** with this facade:

```python
"""Framework extractors - Backward-compatible facade.

This module re-exports all framework extraction functions from domain-specific modules.
Existing code using `from framework_extractors import extract_*` will continue working.

New code should import directly from domain modules for clarity:
  from .orm_extractors import extract_sqlalchemy_definitions
  from .validation_extractors import extract_pydantic_validators
  from .django_web_extractors import extract_django_cbvs
  from .task_graphql_extractors import extract_celery_tasks

REFACTOR NOTE:
This file was reduced from 2222 lines to ~120 lines as part of refactor-framework-extractors-domain-split.
All implementation moved to domain-specific files. This file now serves as a re-export facade only.
"""

# ============================================================================
# Re-exports from ORM Extractors
# ============================================================================

from .orm_extractors import (
    extract_sqlalchemy_definitions,
    extract_django_definitions,
    extract_flask_blueprints,  # TEMP - will move to flask_extractors.py
)


# ============================================================================
# Re-exports from Validation Extractors
# ============================================================================

from .validation_extractors import (
    extract_pydantic_validators,
    extract_marshmallow_schemas,
    extract_marshmallow_fields,
    extract_drf_serializers,
    extract_drf_serializer_fields,
    extract_wtforms_forms,
    extract_wtforms_fields,
)


# ============================================================================
# Re-exports from Django Web Extractors
# ============================================================================

from .django_web_extractors import (
    extract_django_cbvs,
    extract_django_forms,
    extract_django_form_fields,
    extract_django_admin,
    extract_django_middleware,
)


# ============================================================================
# Re-exports from Task Queue + GraphQL Extractors
# ============================================================================

from .task_graphql_extractors import (
    extract_celery_tasks,
    extract_celery_task_calls,
    extract_celery_beat_schedules,
    extract_graphene_resolvers,
    extract_ariadne_resolvers,
    extract_strawberry_resolvers,
)


# ============================================================================
# FastAPI Constants and Helpers (TEMPORARY - Pending FastAPI Routes Work)
# ============================================================================

# These will move to fastapi_extractors.py when FastAPI routes extraction is implemented
FASTAPI_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}


def _extract_fastapi_dependencies(func_node):
    """Collect dependency call targets from FastAPI route parameters.

    TEMPORARY: This function is not yet used but will be needed for FastAPI routes extraction.
    Will be moved to fastapi_extractors.py in future PR.
    """
    # TODO: Copy implementation from original file lines 185-208
    # For now, keeping as placeholder
    pass


# ============================================================================
# Explicit Exports
# ============================================================================

__all__ = [
    # ORM
    'extract_sqlalchemy_definitions',
    'extract_django_definitions',
    'extract_flask_blueprints',
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
    # FastAPI (temp)
    'FASTAPI_HTTP_METHODS',
    '_extract_fastapi_dependencies',
]
```

**Expected Line Count:** ~120 lines

---

## PART 3: Execution Checklist

### Step 1: Backup Original File
```bash
cd C:\Users\santa\Desktop\TheAuditor
cp theauditor\ast_extractors\python\framework_extractors.py theauditor\ast_extractors\python\framework_extractors.py.bak
```

### Step 2: Create New Files

Execute in this order:

**2.1: Create orm_extractors.py**
```bash
cd C:\Users\santa\Desktop\TheAuditor
# Use Write tool to create theauditor\ast_extractors\python\orm_extractors.py
# Copy skeleton template from above, then fill in TODOs by copying specified line ranges
```

**2.2: Create validation_extractors.py**
```bash
# Use Write tool to create theauditor\ast_extractors\python\validation_extractors.py
```

**2.3: Create django_web_extractors.py**
```bash
# Use Write tool to create theauditor\ast_extractors\python\django_web_extractors.py
```

**2.4: Create task_graphql_extractors.py**
```bash
# Use Write tool to create theauditor\ast_extractors\python\task_graphql_extractors.py
```

**2.5: Replace framework_extractors.py with facade**
```bash
# Use Edit tool to REPLACE ENTIRE framework_extractors.py with facade template from above
```

### Step 3: Verify Compilation

```bash
cd C:\Users\santa\Desktop\TheAuditor
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python\orm_extractors.py
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python\validation_extractors.py
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python\django_web_extractors.py
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python\task_graphql_extractors.py
.venv\Scripts\python.exe -m py_compile theauditor\ast_extractors\python\framework_extractors.py
```

All 5 commands should complete without errors.

### Step 4: Verify Imports

```bash
cd C:\Users\santa\Desktop\TheAuditor
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python.orm_extractors import extract_sqlalchemy_definitions; print('orm_extractors: OK')"
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python.validation_extractors import extract_pydantic_validators; print('validation_extractors: OK')"
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python.django_web_extractors import extract_django_cbvs; print('django_web_extractors: OK')"
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python.task_graphql_extractors import extract_celery_tasks; print('task_graphql_extractors: OK')"
.venv\Scripts\python.exe -c "from theauditor.ast_extractors.python.framework_extractors import extract_sqlalchemy_definitions; print('facade: OK')"
```

All 5 commands should print "OK".

### Step 5: Run Tests

```bash
cd C:\Users\santa\Desktop\TheAuditor
.venv\Scripts\python.exe -m pytest tests\test_python_framework_extraction.py -v
```

All tests should pass (same as before refactor).

### Step 6: Verify Line Counts

```bash
cd C:\Users\santa\Desktop\TheAuditor
wc -l theauditor\ast_extractors\python\orm_extractors.py
wc -l theauditor\ast_extractors\python\validation_extractors.py
wc -l theauditor\ast_extractors\python\django_web_extractors.py
wc -l theauditor\ast_extractors\python\task_graphql_extractors.py
wc -l theauditor\ast_extractors\python\framework_extractors.py
```

**Expected Output:**
```
~400 orm_extractors.py
~1200 validation_extractors.py
~700 django_web_extractors.py
~800 task_graphql_extractors.py
~120 framework_extractors.py (facade)
```

---

## PART 4: Common Issues and Fixes

### Issue 1: ImportError - cannot import get_node_name

**Cause:** Wrong import path in new file
**Fix:** Ensure import is `from ..base import get_node_name` (two dots - relative import from parent package)

### Issue 2: SyntaxError - missing helper function

**Cause:** Forgot to copy a helper that a function depends on
**Fix:** Check helper dependency table in Part 1, copy missing helper

### Issue 3: Test failure - function not found

**Cause:** Facade not re-exporting function
**Fix:** Add function to facade's import list and `__all__` list

### Issue 4: Line count way off from expected

**Cause:** Copied wrong line range
**Fix:** Double-check line numbers in Part 1 inventory, re-copy correct range

---

## PART 5: Rollback Instructions

If anything goes wrong:

```bash
cd C:\Users\santa\Desktop\TheAuditor
cp theauditor\ast_extractors\python\framework_extractors.py.bak theauditor\ast_extractors\python\framework_extractors.py
del theauditor\ast_extractors\python\orm_extractors.py
del theauditor\ast_extractors\python\validation_extractors.py
del theauditor\ast_extractors\python\django_web_extractors.py
del theauditor\ast_extractors\python\task_graphql_extractors.py
.venv\Scripts\python.exe -m pytest tests\test_python_framework_extraction.py -v
```

Tests should pass with original file restored.

---

## DONE

If all 6 verification steps pass, refactor is complete. Update `tasks.md` to mark all tasks as completed.
