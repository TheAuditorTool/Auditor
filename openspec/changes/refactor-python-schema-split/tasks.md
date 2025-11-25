# Tasks: python_schema.py Split Implementation

## Pre-Flight Checklist

**STOP. Before ANY code changes, verify these:**

- [ ] **PRIME DIRECTIVE ACKNOWLEDGED**: Read-first, act-second. No assumptions.
- [ ] Read `design.md` completely (all sections)
- [ ] Read `proposal.md` completely (all sections)
- [ ] Run baseline verification command below

**Baseline Verification Command:**
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
from theauditor.indexer.schemas.security_schema import SECURITY_TABLES
from theauditor.indexer.schemas.frameworks_schema import FRAMEWORKS_TABLES
print('=== BASELINE (must match before starting) ===')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 149)')
print(f'SECURITY_TABLES: {len(SECURITY_TABLES)} (expect 7)')
print(f'FRAMEWORKS_TABLES: {len(FRAMEWORKS_TABLES)} (expect 6)')
print(f'TABLES: {len(TABLES)} (expect 250)')
"
```

- [ ] PYTHON_TABLES: 149
- [ ] SECURITY_TABLES: 7
- [ ] FRAMEWORKS_TABLES: 6
- [ ] TABLES: 250
- [ ] `aud full --offline` passes
- [ ] `pytest tests/test_code_snippets.py tests/test_explain_command.py -v --tb=short` passes

**RECORD BASELINE STATE:**
```
Date: _______________
PYTHON_TABLES: ___
SECURITY_TABLES: ___
FRAMEWORKS_TABLES: ___
TABLES: ___
aud full --offline: PASS/FAIL
pytest: PASS/FAIL
```

---

## Phase 1: Create causal_schema.py (18 tables)

### Task 1.1: Create file with header
**File**: `theauditor/indexer/schemas/causal_schema.py`

**EXACT content to copy:**
```python
"""
Causal learning schema definitions - Side effects, exceptions, data flow.

This module contains table schemas for causal analysis patterns:
- Side effect detection (mutations to instance, class, global, arguments)
- Exception flow (raise, catch, finally, context managers)
- Data flow (IO, parameter-return, closures, nonlocal)
- Behavioral patterns (recursion, generators, properties, dynamic attrs)

Design Philosophy:
- Semantic analysis patterns for understanding causality
- NOT Python language syntax coverage (see python_coverage_schema.py)
- Used by causal learning ML pipelines and taint analysis
- Cross-function and cross-file effect tracking

These tables are populated by the Python extractor during causal analysis pass.
"""

from typing import Dict
from .utils import Column, TableSchema, ForeignKey
```

- [ ] File created at `theauditor/indexer/schemas/causal_schema.py`
- [ ] Docstring matches exactly
- [ ] Imports match exactly

### Task 1.2: Copy Side Effect Detection tables (5 tables)
**Source**: `python_schema.py` - search for each table name

- [ ] `PYTHON_ARGUMENT_MUTATIONS` - copied with full TableSchema definition
- [ ] `PYTHON_AUGMENTED_ASSIGNMENTS` - copied with full TableSchema definition
- [ ] `PYTHON_CLASS_MUTATIONS` - copied with full TableSchema definition
- [ ] `PYTHON_GLOBAL_MUTATIONS` - copied with full TableSchema definition
- [ ] `PYTHON_INSTANCE_MUTATIONS` - copied with full TableSchema definition
- [ ] Section header added: `# SIDE EFFECT DETECTION`

### Task 1.3: Copy Exception Flow tables (4 tables)
- [ ] `PYTHON_CONTEXT_MANAGERS_ENHANCED` - copied
- [ ] `PYTHON_EXCEPTION_CATCHES` - copied
- [ ] `PYTHON_EXCEPTION_RAISES` - copied
- [ ] `PYTHON_FINALLY_BLOCKS` - copied
- [ ] Section header added: `# EXCEPTION FLOW`

### Task 1.4: Copy Data Flow tables (5 tables)
- [ ] `PYTHON_CLOSURE_CAPTURES` - copied
- [ ] `PYTHON_CONDITIONAL_CALLS` - copied
- [ ] `PYTHON_IO_OPERATIONS` - copied
- [ ] `PYTHON_NONLOCAL_ACCESS` - copied
- [ ] `PYTHON_PARAMETER_RETURN_FLOW` - copied
- [ ] Section header added: `# DATA FLOW`

### Task 1.5: Copy Behavioral Pattern tables (4 tables)
- [ ] `PYTHON_DYNAMIC_ATTRIBUTES` - copied
- [ ] `PYTHON_GENERATOR_YIELDS` - copied
- [ ] `PYTHON_PROPERTY_PATTERNS` - copied
- [ ] `PYTHON_RECURSION_PATTERNS` - copied
- [ ] Section header added: `# BEHAVIORAL PATTERNS`

### Task 1.6: Add CAUSAL_TABLES registry
**EXACT code to add at end of file:**
```python
# ============================================================================
# CAUSAL LEARNING TABLES REGISTRY
# ============================================================================

CAUSAL_TABLES: dict[str, TableSchema] = {
    # Side Effect Detection
    "python_argument_mutations": PYTHON_ARGUMENT_MUTATIONS,
    "python_augmented_assignments": PYTHON_AUGMENTED_ASSIGNMENTS,
    "python_class_mutations": PYTHON_CLASS_MUTATIONS,
    "python_global_mutations": PYTHON_GLOBAL_MUTATIONS,
    "python_instance_mutations": PYTHON_INSTANCE_MUTATIONS,
    # Exception Flow
    "python_context_managers_enhanced": PYTHON_CONTEXT_MANAGERS_ENHANCED,
    "python_exception_catches": PYTHON_EXCEPTION_CATCHES,
    "python_exception_raises": PYTHON_EXCEPTION_RAISES,
    "python_finally_blocks": PYTHON_FINALLY_BLOCKS,
    # Data Flow
    "python_closure_captures": PYTHON_CLOSURE_CAPTURES,
    "python_conditional_calls": PYTHON_CONDITIONAL_CALLS,
    "python_io_operations": PYTHON_IO_OPERATIONS,
    "python_nonlocal_access": PYTHON_NONLOCAL_ACCESS,
    "python_parameter_return_flow": PYTHON_PARAMETER_RETURN_FLOW,
    # Behavioral Patterns
    "python_dynamic_attributes": PYTHON_DYNAMIC_ATTRIBUTES,
    "python_generator_yields": PYTHON_GENERATOR_YIELDS,
    "python_property_patterns": PYTHON_PROPERTY_PATTERNS,
    "python_recursion_patterns": PYTHON_RECURSION_PATTERNS,
}
```

- [ ] Registry added
- [ ] **VERIFY**: 18 entries in dict

### Task 1.7: Verify causal_schema.py imports
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "from theauditor.indexer.schemas.causal_schema import CAUSAL_TABLES; print(f'CAUSAL_TABLES: {len(CAUSAL_TABLES)} (expect 18)')"
```

- [ ] Imports without error
- [ ] Reports exactly 18 tables

---

## Phase 2: Create python_coverage_schema.py (68 tables)

### Task 2.1: Create file with header
**File**: `theauditor/indexer/schemas/python_coverage_schema.py`

```python
"""
Python language coverage schema definitions - AST-level syntax patterns.

This module contains table schemas for Python language construct tracking:
- Fundamentals: comprehensions, lambdas, slicing, tuples, unpacking
- Operators: arithmetic, comparison, walrus, matrix multiplication
- Collections: dict, list, set operations, builtins, itertools
- Class features: metaclasses, descriptors, dataclasses, enums, slots
- Control flow: for, while, if, match, with statements
- Protocols: iterator, callable, comparison, arithmetic, pickle

Design Philosophy:
- AST-level language coverage (not semantic analysis)
- Used for Python language feature profiling
- Enables "Python idiom" detection and modernization suggestions
- NOT framework patterns (see frameworks_schema.py)
- NOT security patterns (see security_schema.py)

These tables are populated by the Python extractor's coverage pass.
"""

from typing import Dict
from .utils import Column, TableSchema, ForeignKey
```

- [ ] File created
- [ ] Docstring correct
- [ ] Imports correct

### Task 2.2: Copy Fundamentals tables (8 tables)
- [ ] `PYTHON_COMPREHENSIONS` - copied
- [ ] `PYTHON_LAMBDA_FUNCTIONS` - copied
- [ ] `PYTHON_NONE_PATTERNS` - copied
- [ ] `PYTHON_SLICE_OPERATIONS` - copied
- [ ] `PYTHON_STRING_FORMATTING` - copied
- [ ] `PYTHON_TRUTHINESS_PATTERNS` - copied
- [ ] `PYTHON_TUPLE_OPERATIONS` - copied
- [ ] `PYTHON_UNPACKING_PATTERNS` - copied
- [ ] Section header: `# FUNDAMENTALS`

### Task 2.3: Copy Operators tables (6 tables)
- [ ] `PYTHON_CHAINED_COMPARISONS` - copied
- [ ] `PYTHON_MATRIX_MULTIPLICATION` - copied
- [ ] `PYTHON_MEMBERSHIP_TESTS` - copied
- [ ] `PYTHON_OPERATORS` - copied
- [ ] `PYTHON_TERNARY_EXPRESSIONS` - copied
- [ ] `PYTHON_WALRUS_OPERATORS` - copied
- [ ] Section header: `# OPERATORS`

### Task 2.4: Copy Collections tables (8 tables)
- [ ] `PYTHON_BUILTIN_USAGE` - copied
- [ ] `PYTHON_COLLECTIONS_USAGE` - copied
- [ ] `PYTHON_DICT_OPERATIONS` - copied
- [ ] `PYTHON_FUNCTOOLS_USAGE` - copied
- [ ] `PYTHON_ITERTOOLS_USAGE` - copied
- [ ] `PYTHON_LIST_MUTATIONS` - copied
- [ ] `PYTHON_SET_OPERATIONS` - copied
- [ ] `PYTHON_STRING_METHODS` - copied
- [ ] Section header: `# COLLECTIONS`

### Task 2.5: Copy Advanced Class tables (10 tables)
- [ ] `PYTHON_ABSTRACT_CLASSES` - copied
- [ ] `PYTHON_DATACLASSES` - copied
- [ ] `PYTHON_DESCRIPTORS` - copied
- [ ] `PYTHON_DUNDER_METHODS` - copied
- [ ] `PYTHON_ENUMS` - copied
- [ ] `PYTHON_METACLASSES` - copied
- [ ] `PYTHON_METHOD_TYPES` - copied
- [ ] `PYTHON_MULTIPLE_INHERITANCE` - copied
- [ ] `PYTHON_SLOTS` - copied
- [ ] `PYTHON_VISIBILITY_CONVENTIONS` - copied
- [ ] Section header: `# ADVANCED CLASS FEATURES`

### Task 2.6: Copy Stdlib tables (8 tables)
- [ ] `PYTHON_CONTEXTLIB_PATTERNS` - copied
- [ ] `PYTHON_DATETIME_OPERATIONS` - copied
- [ ] `PYTHON_JSON_OPERATIONS` - copied
- [ ] `PYTHON_LOGGING_PATTERNS` - copied
- [ ] `PYTHON_PATH_OPERATIONS` - copied
- [ ] `PYTHON_REGEX_PATTERNS` - copied
- [ ] `PYTHON_THREADING_PATTERNS` - copied
- [ ] `PYTHON_TYPE_CHECKING` - copied
- [ ] Section header: `# STDLIB PATTERNS`

### Task 2.7: Copy Control Flow tables (10 tables)
- [ ] `PYTHON_ASSERT_STATEMENTS` - copied
- [ ] `PYTHON_ASYNC_FOR_LOOPS` - copied
- [ ] `PYTHON_BREAK_CONTINUE_PASS` - copied
- [ ] `PYTHON_DEL_STATEMENTS` - copied
- [ ] `PYTHON_FOR_LOOPS` - copied
- [ ] `PYTHON_IF_STATEMENTS` - copied
- [ ] `PYTHON_IMPORT_STATEMENTS` - copied
- [ ] `PYTHON_MATCH_STATEMENTS` - copied
- [ ] `PYTHON_WHILE_LOOPS` - copied
- [ ] `PYTHON_WITH_STATEMENTS` - copied
- [ ] Section header: `# CONTROL FLOW`

### Task 2.8: Copy Protocol tables (10 tables)
- [ ] `PYTHON_ARITHMETIC_PROTOCOL` - copied
- [ ] `PYTHON_CALLABLE_PROTOCOL` - copied
- [ ] `PYTHON_CLASS_DECORATORS` - copied
- [ ] `PYTHON_COMPARISON_PROTOCOL` - copied
- [ ] `PYTHON_CONTAINER_PROTOCOL` - copied
- [ ] `PYTHON_CONTEXTVAR_USAGE` - copied
- [ ] `PYTHON_ITERATOR_PROTOCOL` - copied
- [ ] `PYTHON_MODULE_ATTRIBUTES` - copied
- [ ] `PYTHON_PICKLE_PROTOCOL` - copied
- [ ] `PYTHON_WEAKREF_USAGE` - copied
- [ ] Section header: `# PROTOCOL PATTERNS`

### Task 2.9: Copy Advanced Pattern tables (8 tables)
- [ ] `PYTHON_ATTRIBUTE_ACCESS_PROTOCOL` - copied
- [ ] `PYTHON_BYTES_OPERATIONS` - copied
- [ ] `PYTHON_CACHED_PROPERTY` - copied
- [ ] `PYTHON_COPY_PROTOCOL` - copied
- [ ] `PYTHON_DESCRIPTOR_PROTOCOL` - copied
- [ ] `PYTHON_ELLIPSIS_USAGE` - copied
- [ ] `PYTHON_EXEC_EVAL_COMPILE` - copied
- [ ] `PYTHON_NAMESPACE_PACKAGES` - copied
- [ ] Section header: `# ADVANCED PATTERNS`

### Task 2.10: Add PYTHON_COVERAGE_TABLES registry
**EXACT code:**
```python
# ============================================================================
# PYTHON COVERAGE TABLES REGISTRY
# ============================================================================

PYTHON_COVERAGE_TABLES: dict[str, TableSchema] = {
    # Fundamentals (8)
    "python_comprehensions": PYTHON_COMPREHENSIONS,
    "python_lambda_functions": PYTHON_LAMBDA_FUNCTIONS,
    "python_none_patterns": PYTHON_NONE_PATTERNS,
    "python_slice_operations": PYTHON_SLICE_OPERATIONS,
    "python_string_formatting": PYTHON_STRING_FORMATTING,
    "python_truthiness_patterns": PYTHON_TRUTHINESS_PATTERNS,
    "python_tuple_operations": PYTHON_TUPLE_OPERATIONS,
    "python_unpacking_patterns": PYTHON_UNPACKING_PATTERNS,
    # Operators (6)
    "python_chained_comparisons": PYTHON_CHAINED_COMPARISONS,
    "python_matrix_multiplication": PYTHON_MATRIX_MULTIPLICATION,
    "python_membership_tests": PYTHON_MEMBERSHIP_TESTS,
    "python_operators": PYTHON_OPERATORS,
    "python_ternary_expressions": PYTHON_TERNARY_EXPRESSIONS,
    "python_walrus_operators": PYTHON_WALRUS_OPERATORS,
    # Collections (8)
    "python_builtin_usage": PYTHON_BUILTIN_USAGE,
    "python_collections_usage": PYTHON_COLLECTIONS_USAGE,
    "python_dict_operations": PYTHON_DICT_OPERATIONS,
    "python_functools_usage": PYTHON_FUNCTOOLS_USAGE,
    "python_itertools_usage": PYTHON_ITERTOOLS_USAGE,
    "python_list_mutations": PYTHON_LIST_MUTATIONS,
    "python_set_operations": PYTHON_SET_OPERATIONS,
    "python_string_methods": PYTHON_STRING_METHODS,
    # Advanced Class (10)
    "python_abstract_classes": PYTHON_ABSTRACT_CLASSES,
    "python_dataclasses": PYTHON_DATACLASSES,
    "python_descriptors": PYTHON_DESCRIPTORS,
    "python_dunder_methods": PYTHON_DUNDER_METHODS,
    "python_enums": PYTHON_ENUMS,
    "python_metaclasses": PYTHON_METACLASSES,
    "python_method_types": PYTHON_METHOD_TYPES,
    "python_multiple_inheritance": PYTHON_MULTIPLE_INHERITANCE,
    "python_slots": PYTHON_SLOTS,
    "python_visibility_conventions": PYTHON_VISIBILITY_CONVENTIONS,
    # Stdlib (8)
    "python_contextlib_patterns": PYTHON_CONTEXTLIB_PATTERNS,
    "python_datetime_operations": PYTHON_DATETIME_OPERATIONS,
    "python_json_operations": PYTHON_JSON_OPERATIONS,
    "python_logging_patterns": PYTHON_LOGGING_PATTERNS,
    "python_path_operations": PYTHON_PATH_OPERATIONS,
    "python_regex_patterns": PYTHON_REGEX_PATTERNS,
    "python_threading_patterns": PYTHON_THREADING_PATTERNS,
    "python_type_checking": PYTHON_TYPE_CHECKING,
    # Control Flow (10)
    "python_assert_statements": PYTHON_ASSERT_STATEMENTS,
    "python_async_for_loops": PYTHON_ASYNC_FOR_LOOPS,
    "python_break_continue_pass": PYTHON_BREAK_CONTINUE_PASS,
    "python_del_statements": PYTHON_DEL_STATEMENTS,
    "python_for_loops": PYTHON_FOR_LOOPS,
    "python_if_statements": PYTHON_IF_STATEMENTS,
    "python_import_statements": PYTHON_IMPORT_STATEMENTS,
    "python_match_statements": PYTHON_MATCH_STATEMENTS,
    "python_while_loops": PYTHON_WHILE_LOOPS,
    "python_with_statements": PYTHON_WITH_STATEMENTS,
    # Protocols (10)
    "python_arithmetic_protocol": PYTHON_ARITHMETIC_PROTOCOL,
    "python_callable_protocol": PYTHON_CALLABLE_PROTOCOL,
    "python_class_decorators": PYTHON_CLASS_DECORATORS,
    "python_comparison_protocol": PYTHON_COMPARISON_PROTOCOL,
    "python_container_protocol": PYTHON_CONTAINER_PROTOCOL,
    "python_contextvar_usage": PYTHON_CONTEXTVAR_USAGE,
    "python_iterator_protocol": PYTHON_ITERATOR_PROTOCOL,
    "python_module_attributes": PYTHON_MODULE_ATTRIBUTES,
    "python_pickle_protocol": PYTHON_PICKLE_PROTOCOL,
    "python_weakref_usage": PYTHON_WEAKREF_USAGE,
    # Advanced (8)
    "python_attribute_access_protocol": PYTHON_ATTRIBUTE_ACCESS_PROTOCOL,
    "python_bytes_operations": PYTHON_BYTES_OPERATIONS,
    "python_cached_property": PYTHON_CACHED_PROPERTY,
    "python_copy_protocol": PYTHON_COPY_PROTOCOL,
    "python_descriptor_protocol": PYTHON_DESCRIPTOR_PROTOCOL,
    "python_ellipsis_usage": PYTHON_ELLIPSIS_USAGE,
    "python_exec_eval_compile": PYTHON_EXEC_EVAL_COMPILE,
    "python_namespace_packages": PYTHON_NAMESPACE_PACKAGES,
}
```

- [ ] Registry added
- [ ] **VERIFY**: 68 entries in dict

### Task 2.11: Verify python_coverage_schema.py imports
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "from theauditor.indexer.schemas.python_coverage_schema import PYTHON_COVERAGE_TABLES; print(f'PYTHON_COVERAGE_TABLES: {len(PYTHON_COVERAGE_TABLES)} (expect 68)')"
```

- [ ] Imports without error
- [ ] Reports exactly 68 tables

---

## Phase 3: Modify security_schema.py (+8 tables)

### Task 3.1: Add Python security tables
**Add to end of file, BEFORE SECURITY_TABLES dict:**

Section header:
```python
# ============================================================================
# PYTHON SECURITY PATTERNS - OWASP Top 10
# ============================================================================
```

Copy these tables from python_schema.py:
- [ ] `PYTHON_AUTH_DECORATORS` - copied
- [ ] `PYTHON_COMMAND_INJECTION` - copied
- [ ] `PYTHON_CRYPTO_OPERATIONS` - copied
- [ ] `PYTHON_DANGEROUS_EVAL` - copied
- [ ] `PYTHON_JWT_OPERATIONS` - copied
- [ ] `PYTHON_PASSWORD_HASHING` - copied
- [ ] `PYTHON_PATH_TRAVERSAL` - copied
- [ ] `PYTHON_SQL_INJECTION` - copied

### Task 3.2: Update SECURITY_TABLES registry
**Add these 8 entries to existing SECURITY_TABLES dict:**
```python
    # Python Security Patterns
    "python_auth_decorators": PYTHON_AUTH_DECORATORS,
    "python_command_injection": PYTHON_COMMAND_INJECTION,
    "python_crypto_operations": PYTHON_CRYPTO_OPERATIONS,
    "python_dangerous_eval": PYTHON_DANGEROUS_EVAL,
    "python_jwt_operations": PYTHON_JWT_OPERATIONS,
    "python_password_hashing": PYTHON_PASSWORD_HASHING,
    "python_path_traversal": PYTHON_PATH_TRAVERSAL,
    "python_sql_injection": PYTHON_SQL_INJECTION,
```

- [ ] 8 entries added to registry
- [ ] **VERIFY**: `len(SECURITY_TABLES) == 15` (was 7)

---

## Phase 4: Modify frameworks_schema.py (+27 tables)

### Task 4.1: Add Django tables (9 tables)
Section header: `# DJANGO FRAMEWORK PATTERNS`

- [ ] `PYTHON_DJANGO_ADMIN` - copied
- [ ] `PYTHON_DJANGO_FORM_FIELDS` - copied
- [ ] `PYTHON_DJANGO_FORMS` - copied
- [ ] `PYTHON_DJANGO_MANAGERS` - copied
- [ ] `PYTHON_DJANGO_MIDDLEWARE` - copied
- [ ] `PYTHON_DJANGO_QUERYSETS` - copied
- [ ] `PYTHON_DJANGO_RECEIVERS` - copied
- [ ] `PYTHON_DJANGO_SIGNALS` - copied
- [ ] `PYTHON_DJANGO_VIEWS` - copied

### Task 4.2: Add Flask tables (9 tables)
Section header: `# FLASK FRAMEWORK PATTERNS`

- [ ] `PYTHON_FLASK_APPS` - copied
- [ ] `PYTHON_FLASK_CACHE` - copied
- [ ] `PYTHON_FLASK_CLI_COMMANDS` - copied
- [ ] `PYTHON_FLASK_CORS` - copied
- [ ] `PYTHON_FLASK_ERROR_HANDLERS` - copied
- [ ] `PYTHON_FLASK_EXTENSIONS` - copied
- [ ] `PYTHON_FLASK_HOOKS` - copied
- [ ] `PYTHON_FLASK_RATE_LIMITS` - copied
- [ ] `PYTHON_FLASK_WEBSOCKETS` - copied

### Task 4.3: Add Validation framework tables (6 tables)
Section header: `# VALIDATION/SERIALIZATION FRAMEWORKS`

- [ ] `PYTHON_DRF_SERIALIZER_FIELDS` - copied
- [ ] `PYTHON_DRF_SERIALIZERS` - copied
- [ ] `PYTHON_MARSHMALLOW_FIELDS` - copied
- [ ] `PYTHON_MARSHMALLOW_SCHEMAS` - copied
- [ ] `PYTHON_WTFORMS_FIELDS` - copied
- [ ] `PYTHON_WTFORMS_FORMS` - copied

### Task 4.4: Add Celery tables (3 tables)
Section header: `# TASK QUEUE FRAMEWORKS`

- [ ] `PYTHON_CELERY_BEAT_SCHEDULES` - copied
- [ ] `PYTHON_CELERY_TASK_CALLS` - copied
- [ ] `PYTHON_CELERY_TASKS` - copied

### Task 4.5: Update FRAMEWORKS_TABLES registry
**Add these 27 entries:**
```python
    # Django Framework
    "python_django_admin": PYTHON_DJANGO_ADMIN,
    "python_django_form_fields": PYTHON_DJANGO_FORM_FIELDS,
    "python_django_forms": PYTHON_DJANGO_FORMS,
    "python_django_managers": PYTHON_DJANGO_MANAGERS,
    "python_django_middleware": PYTHON_DJANGO_MIDDLEWARE,
    "python_django_querysets": PYTHON_DJANGO_QUERYSETS,
    "python_django_receivers": PYTHON_DJANGO_RECEIVERS,
    "python_django_signals": PYTHON_DJANGO_SIGNALS,
    "python_django_views": PYTHON_DJANGO_VIEWS,
    # Flask Framework
    "python_flask_apps": PYTHON_FLASK_APPS,
    "python_flask_cache": PYTHON_FLASK_CACHE,
    "python_flask_cli_commands": PYTHON_FLASK_CLI_COMMANDS,
    "python_flask_cors": PYTHON_FLASK_CORS,
    "python_flask_error_handlers": PYTHON_FLASK_ERROR_HANDLERS,
    "python_flask_extensions": PYTHON_FLASK_EXTENSIONS,
    "python_flask_hooks": PYTHON_FLASK_HOOKS,
    "python_flask_rate_limits": PYTHON_FLASK_RATE_LIMITS,
    "python_flask_websockets": PYTHON_FLASK_WEBSOCKETS,
    # Validation
    "python_drf_serializer_fields": PYTHON_DRF_SERIALIZER_FIELDS,
    "python_drf_serializers": PYTHON_DRF_SERIALIZERS,
    "python_marshmallow_fields": PYTHON_MARSHMALLOW_FIELDS,
    "python_marshmallow_schemas": PYTHON_MARSHMALLOW_SCHEMAS,
    "python_wtforms_fields": PYTHON_WTFORMS_FIELDS,
    "python_wtforms_forms": PYTHON_WTFORMS_FORMS,
    # Task Queues
    "python_celery_beat_schedules": PYTHON_CELERY_BEAT_SCHEDULES,
    "python_celery_task_calls": PYTHON_CELERY_TASK_CALLS,
    "python_celery_tasks": PYTHON_CELERY_TASKS,
```

- [ ] 27 entries added
- [ ] **VERIFY**: `len(FRAMEWORKS_TABLES) == 33` (was 6)

---

## Phase 5: Update schema.py (Critical)

### Task 5.1: Add imports for new schema files
**File**: `theauditor/indexer/schema.py`

Add after line 63 (after GRAPHQL_TABLES import):
```python
from .schemas.causal_schema import CAUSAL_TABLES
from .schemas.python_coverage_schema import PYTHON_COVERAGE_TABLES
```

- [ ] Import for CAUSAL_TABLES added
- [ ] Import for PYTHON_COVERAGE_TABLES added

### Task 5.2: Update TABLES dict
**Modify the TABLES dict (around line 70-79) to include new registries:**
```python
TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,           # 24 tables
    **SECURITY_TABLES,       # 15 tables (was 7)
    **FRAMEWORKS_TABLES,     # 33 tables (was 6)
    **PYTHON_TABLES,         # 28 tables (was 149)
    **NODE_TABLES,           # 29 tables
    **INFRASTRUCTURE_TABLES, # 18 tables
    **PLANNING_TABLES,       # 9 tables
    **GRAPHQL_TABLES,        # 8 tables
    **CAUSAL_TABLES,         # 18 tables (NEW)
    **PYTHON_COVERAGE_TABLES, # 68 tables (NEW)
}
```

- [ ] CAUSAL_TABLES added to dict
- [ ] PYTHON_COVERAGE_TABLES added to dict
- [ ] Comments updated with new counts

### Task 5.3: Update assertion
The existing assertion `assert len(TABLES) == 250` should still pass.

- [ ] Assertion unchanged (still 250)

---

## Phase 6: Clean python_schema.py

### Task 6.1: Delete Security tables (8 tables)
- [ ] `PYTHON_AUTH_DECORATORS` definition deleted
- [ ] `PYTHON_COMMAND_INJECTION` definition deleted
- [ ] `PYTHON_CRYPTO_OPERATIONS` definition deleted
- [ ] `PYTHON_DANGEROUS_EVAL` definition deleted
- [ ] `PYTHON_JWT_OPERATIONS` definition deleted
- [ ] `PYTHON_PASSWORD_HASHING` definition deleted
- [ ] `PYTHON_PATH_TRAVERSAL` definition deleted
- [ ] `PYTHON_SQL_INJECTION` definition deleted

### Task 6.2: Delete Framework tables (27 tables)
Django (9):
- [ ] `PYTHON_DJANGO_ADMIN` deleted
- [ ] `PYTHON_DJANGO_FORM_FIELDS` deleted
- [ ] `PYTHON_DJANGO_FORMS` deleted
- [ ] `PYTHON_DJANGO_MANAGERS` deleted
- [ ] `PYTHON_DJANGO_MIDDLEWARE` deleted
- [ ] `PYTHON_DJANGO_QUERYSETS` deleted
- [ ] `PYTHON_DJANGO_RECEIVERS` deleted
- [ ] `PYTHON_DJANGO_SIGNALS` deleted
- [ ] `PYTHON_DJANGO_VIEWS` deleted

Flask (9):
- [ ] `PYTHON_FLASK_APPS` deleted
- [ ] `PYTHON_FLASK_CACHE` deleted
- [ ] `PYTHON_FLASK_CLI_COMMANDS` deleted
- [ ] `PYTHON_FLASK_CORS` deleted
- [ ] `PYTHON_FLASK_ERROR_HANDLERS` deleted
- [ ] `PYTHON_FLASK_EXTENSIONS` deleted
- [ ] `PYTHON_FLASK_HOOKS` deleted
- [ ] `PYTHON_FLASK_RATE_LIMITS` deleted
- [ ] `PYTHON_FLASK_WEBSOCKETS` deleted

Validation (6):
- [ ] `PYTHON_DRF_SERIALIZER_FIELDS` deleted
- [ ] `PYTHON_DRF_SERIALIZERS` deleted
- [ ] `PYTHON_MARSHMALLOW_FIELDS` deleted
- [ ] `PYTHON_MARSHMALLOW_SCHEMAS` deleted
- [ ] `PYTHON_WTFORMS_FIELDS` deleted
- [ ] `PYTHON_WTFORMS_FORMS` deleted

Celery (3):
- [ ] `PYTHON_CELERY_BEAT_SCHEDULES` deleted
- [ ] `PYTHON_CELERY_TASK_CALLS` deleted
- [ ] `PYTHON_CELERY_TASKS` deleted

### Task 6.3: Delete Causal Learning tables (18 tables)
- [ ] `PYTHON_ARGUMENT_MUTATIONS` deleted
- [ ] `PYTHON_AUGMENTED_ASSIGNMENTS` deleted
- [ ] `PYTHON_CLASS_MUTATIONS` deleted
- [ ] `PYTHON_CLOSURE_CAPTURES` deleted
- [ ] `PYTHON_CONDITIONAL_CALLS` deleted
- [ ] `PYTHON_CONTEXT_MANAGERS_ENHANCED` deleted
- [ ] `PYTHON_DYNAMIC_ATTRIBUTES` deleted
- [ ] `PYTHON_EXCEPTION_CATCHES` deleted
- [ ] `PYTHON_EXCEPTION_RAISES` deleted
- [ ] `PYTHON_FINALLY_BLOCKS` deleted
- [ ] `PYTHON_GENERATOR_YIELDS` deleted
- [ ] `PYTHON_GLOBAL_MUTATIONS` deleted
- [ ] `PYTHON_INSTANCE_MUTATIONS` deleted
- [ ] `PYTHON_IO_OPERATIONS` deleted
- [ ] `PYTHON_NONLOCAL_ACCESS` deleted
- [ ] `PYTHON_PARAMETER_RETURN_FLOW` deleted
- [ ] `PYTHON_PROPERTY_PATTERNS` deleted
- [ ] `PYTHON_RECURSION_PATTERNS` deleted

### Task 6.4: Delete Coverage tables (68 tables)
Fundamentals (8):
- [ ] `PYTHON_COMPREHENSIONS` deleted
- [ ] `PYTHON_LAMBDA_FUNCTIONS` deleted
- [ ] `PYTHON_NONE_PATTERNS` deleted
- [ ] `PYTHON_SLICE_OPERATIONS` deleted
- [ ] `PYTHON_STRING_FORMATTING` deleted
- [ ] `PYTHON_TRUTHINESS_PATTERNS` deleted
- [ ] `PYTHON_TUPLE_OPERATIONS` deleted
- [ ] `PYTHON_UNPACKING_PATTERNS` deleted

Operators (6):
- [ ] `PYTHON_CHAINED_COMPARISONS` deleted
- [ ] `PYTHON_MATRIX_MULTIPLICATION` deleted
- [ ] `PYTHON_MEMBERSHIP_TESTS` deleted
- [ ] `PYTHON_OPERATORS` deleted
- [ ] `PYTHON_TERNARY_EXPRESSIONS` deleted
- [ ] `PYTHON_WALRUS_OPERATORS` deleted

Collections (8):
- [ ] `PYTHON_BUILTIN_USAGE` deleted
- [ ] `PYTHON_COLLECTIONS_USAGE` deleted
- [ ] `PYTHON_DICT_OPERATIONS` deleted
- [ ] `PYTHON_FUNCTOOLS_USAGE` deleted
- [ ] `PYTHON_ITERTOOLS_USAGE` deleted
- [ ] `PYTHON_LIST_MUTATIONS` deleted
- [ ] `PYTHON_SET_OPERATIONS` deleted
- [ ] `PYTHON_STRING_METHODS` deleted

Advanced Class (10):
- [ ] `PYTHON_ABSTRACT_CLASSES` deleted
- [ ] `PYTHON_DATACLASSES` deleted
- [ ] `PYTHON_DESCRIPTORS` deleted
- [ ] `PYTHON_DUNDER_METHODS` deleted
- [ ] `PYTHON_ENUMS` deleted
- [ ] `PYTHON_METACLASSES` deleted
- [ ] `PYTHON_METHOD_TYPES` deleted
- [ ] `PYTHON_MULTIPLE_INHERITANCE` deleted
- [ ] `PYTHON_SLOTS` deleted
- [ ] `PYTHON_VISIBILITY_CONVENTIONS` deleted

Stdlib (8):
- [ ] `PYTHON_CONTEXTLIB_PATTERNS` deleted
- [ ] `PYTHON_DATETIME_OPERATIONS` deleted
- [ ] `PYTHON_JSON_OPERATIONS` deleted
- [ ] `PYTHON_LOGGING_PATTERNS` deleted
- [ ] `PYTHON_PATH_OPERATIONS` deleted
- [ ] `PYTHON_REGEX_PATTERNS` deleted
- [ ] `PYTHON_THREADING_PATTERNS` deleted
- [ ] `PYTHON_TYPE_CHECKING` deleted

Control Flow (10):
- [ ] `PYTHON_ASSERT_STATEMENTS` deleted
- [ ] `PYTHON_ASYNC_FOR_LOOPS` deleted
- [ ] `PYTHON_BREAK_CONTINUE_PASS` deleted
- [ ] `PYTHON_DEL_STATEMENTS` deleted
- [ ] `PYTHON_FOR_LOOPS` deleted
- [ ] `PYTHON_IF_STATEMENTS` deleted
- [ ] `PYTHON_IMPORT_STATEMENTS` deleted
- [ ] `PYTHON_MATCH_STATEMENTS` deleted
- [ ] `PYTHON_WHILE_LOOPS` deleted
- [ ] `PYTHON_WITH_STATEMENTS` deleted

Protocols (10):
- [ ] `PYTHON_ARITHMETIC_PROTOCOL` deleted
- [ ] `PYTHON_CALLABLE_PROTOCOL` deleted
- [ ] `PYTHON_CLASS_DECORATORS` deleted
- [ ] `PYTHON_COMPARISON_PROTOCOL` deleted
- [ ] `PYTHON_CONTAINER_PROTOCOL` deleted
- [ ] `PYTHON_CONTEXTVAR_USAGE` deleted
- [ ] `PYTHON_ITERATOR_PROTOCOL` deleted
- [ ] `PYTHON_MODULE_ATTRIBUTES` deleted
- [ ] `PYTHON_PICKLE_PROTOCOL` deleted
- [ ] `PYTHON_WEAKREF_USAGE` deleted

Advanced (8):
- [ ] `PYTHON_ATTRIBUTE_ACCESS_PROTOCOL` deleted
- [ ] `PYTHON_BYTES_OPERATIONS` deleted
- [ ] `PYTHON_CACHED_PROPERTY` deleted
- [ ] `PYTHON_COPY_PROTOCOL` deleted
- [ ] `PYTHON_DESCRIPTOR_PROTOCOL` deleted
- [ ] `PYTHON_ELLIPSIS_USAGE` deleted
- [ ] `PYTHON_EXEC_EVAL_COMPILE` deleted
- [ ] `PYTHON_NAMESPACE_PACKAGES` deleted

### Task 6.5: Update PYTHON_TABLES registry
**Replace entire PYTHON_TABLES dict with:**
```python
PYTHON_TABLES: dict[str, TableSchema] = {
    # Core ORM/Routes (6)
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_routes": PYTHON_ROUTES,
    "python_blueprints": PYTHON_BLUEPRINTS,
    "python_validators": PYTHON_VALIDATORS,
    "python_package_configs": PYTHON_PACKAGE_CONFIGS,
    # Async Patterns (5)
    "python_decorators": PYTHON_DECORATORS,
    "python_context_managers": PYTHON_CONTEXT_MANAGERS,
    "python_async_functions": PYTHON_ASYNC_FUNCTIONS,
    "python_await_expressions": PYTHON_AWAIT_EXPRESSIONS,
    "python_async_generators": PYTHON_ASYNC_GENERATORS,
    # Testing (8)
    "python_pytest_fixtures": PYTHON_PYTEST_FIXTURES,
    "python_pytest_parametrize": PYTHON_PYTEST_PARAMETRIZE,
    "python_pytest_markers": PYTHON_PYTEST_MARKERS,
    "python_mock_patterns": PYTHON_MOCK_PATTERNS,
    "python_unittest_test_cases": PYTHON_UNITTEST_TEST_CASES,
    "python_assertion_patterns": PYTHON_ASSERTION_PATTERNS,
    "python_pytest_plugin_hooks": PYTHON_PYTEST_PLUGIN_HOOKS,
    "python_hypothesis_strategies": PYTHON_HYPOTHESIS_STRATEGIES,
    # Typing (5)
    "python_protocols": PYTHON_PROTOCOLS,
    "python_generics": PYTHON_GENERICS,
    "python_typed_dicts": PYTHON_TYPED_DICTS,
    "python_literals": PYTHON_LITERALS,
    "python_overloads": PYTHON_OVERLOADS,
    # Generators/Performance (4)
    "python_generators": PYTHON_GENERATORS,
    "python_loop_complexity": PYTHON_LOOP_COMPLEXITY,
    "python_resource_usage": PYTHON_RESOURCE_USAGE,
    "python_memoization_patterns": PYTHON_MEMOIZATION_PATTERNS,
}
```

- [ ] Registry replaced
- [ ] **VERIFY**: `len(PYTHON_TABLES) == 28`

---

## Phase 7: Verification

### Task 7.1: Table count verification
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
from theauditor.indexer.schemas.security_schema import SECURITY_TABLES
from theauditor.indexer.schemas.frameworks_schema import FRAMEWORKS_TABLES
from theauditor.indexer.schemas.causal_schema import CAUSAL_TABLES
from theauditor.indexer.schemas.python_coverage_schema import PYTHON_COVERAGE_TABLES

print('=== POST-REFACTOR COUNTS ===')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 28)')
print(f'SECURITY_TABLES: {len(SECURITY_TABLES)} (expect 15)')
print(f'FRAMEWORKS_TABLES: {len(FRAMEWORKS_TABLES)} (expect 33)')
print(f'CAUSAL_TABLES: {len(CAUSAL_TABLES)} (expect 18)')
print(f'PYTHON_COVERAGE_TABLES: {len(PYTHON_COVERAGE_TABLES)} (expect 68)')
print(f'TABLES: {len(TABLES)} (expect 250)')
"
```

- [ ] PYTHON_TABLES: 28
- [ ] SECURITY_TABLES: 15
- [ ] FRAMEWORKS_TABLES: 33
- [ ] CAUSAL_TABLES: 18
- [ ] PYTHON_COVERAGE_TABLES: 68
- [ ] TABLES: 250

### Task 7.2: Database creation verification
```bash
cd C:/Users/santa/Desktop/TheAuditor && rm -f .pf/repo_index.db && aud full --index
```

- [ ] `aud full --index` completes without errors
- [ ] repo_index.db created
- [ ] All 250 tables exist

### Task 7.3: Test suite verification
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/test_code_snippets.py tests/test_explain_command.py -v --tb=short
```

- [ ] All tests pass

### Task 7.4: File size verification
```bash
cd C:/Users/santa/Desktop/TheAuditor && powershell -Command "Get-ChildItem theauditor/indexer/schemas/*.py | Where-Object {$_.Name -notlike 'generated*'} | Select-Object Name, @{n='Lines';e={(Get-Content $_.FullName).Count}} | Format-Table"
```

Expected:
| File | Lines |
|------|-------|
| python_schema.py | ~750 |
| security_schema.py | ~370 |
| frameworks_schema.py | ~860 |
| causal_schema.py | ~280 |
| python_coverage_schema.py | ~1100 |

- [ ] python_schema.py < 800 lines
- [ ] No file > 1200 lines

---

## Rollback Procedure

If ANY verification fails:

```bash
cd C:/Users/santa/Desktop/TheAuditor
git checkout -- theauditor/indexer/schemas/
git checkout -- theauditor/indexer/schema.py
rm -f theauditor/indexer/schemas/causal_schema.py
rm -f theauditor/indexer/schemas/python_coverage_schema.py
rm -f .pf/repo_index.db
aud full --index
```

---

## Completion Checklist

- [ ] All 7 phases completed
- [ ] All 121 table moves verified (8 + 27 + 18 + 68)
- [ ] All verification tasks pass
- [ ] Code reviewed by Lead Auditor (Gemini)
- [ ] Architect approval received
- [ ] PR created with clear description
- [ ] CI/CD pipeline passes
