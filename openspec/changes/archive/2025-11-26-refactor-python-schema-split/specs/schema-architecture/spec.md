# Schema Architecture Specification Delta

## ADDED Requirements

### Requirement: Domain-Specific Schema File Organization

Each schema file SHALL contain tables belonging to exactly ONE domain. Tables SHALL NOT be placed in files outside their domain.

Domain boundaries:
- `python_schema.py`: Python core patterns (ORM, async, testing, typing, generators) - 28 tables
- `security_schema.py`: Cross-language security vulnerability patterns (OWASP Top 10) - 15 tables
- `frameworks_schema.py`: Cross-language web framework patterns (Django, Flask, Express, etc.) - 33 tables
- `causal_schema.py`: Causal learning patterns (mutations, exceptions, data flow, behavior) - 18 tables
- `python_coverage_schema.py`: Python language construct coverage (AST-level syntax patterns) - 68 tables

#### Scenario: Security tables live in security_schema.py

- **WHEN** a table tracks security vulnerabilities (SQL injection, XSS, auth bypass, crypto misuse)
- **THEN** the table definition SHALL exist in `security_schema.py`
- **AND** the table SHALL be registered in `SECURITY_TABLES` dict
- **AND** the table SHALL NOT exist in `python_schema.py`

#### Scenario: Framework tables live in frameworks_schema.py

- **WHEN** a table tracks framework-specific patterns (Django views, Flask routes, Celery tasks)
- **THEN** the table definition SHALL exist in `frameworks_schema.py`
- **AND** the table SHALL be registered in `FRAMEWORKS_TABLES` dict
- **AND** the table SHALL NOT exist in `python_schema.py`

#### Scenario: Causal learning tables live in causal_schema.py

- **WHEN** a table tracks causal patterns (mutations, exception flow, closures, recursion)
- **THEN** the table definition SHALL exist in `causal_schema.py`
- **AND** the table SHALL be registered in `CAUSAL_TABLES` dict

#### Scenario: Python coverage tables live in python_coverage_schema.py

- **WHEN** a table tracks Python language syntax constructs (comprehensions, operators, protocols)
- **THEN** the table definition SHALL exist in `python_coverage_schema.py`
- **AND** the table SHALL be registered in `PYTHON_COVERAGE_TABLES` dict

### Requirement: Schema File Size Limits

No schema file SHALL exceed 1200 lines to maintain readability and cognitive load limits.

#### Scenario: python_schema.py size after refactor

- **WHEN** the refactor is complete
- **THEN** `python_schema.py` SHALL contain fewer than 800 lines
- **AND** `python_schema.py` SHALL contain exactly 28 table definitions

#### Scenario: New schema files within limits

- **WHEN** new schema files are created
- **THEN** `causal_schema.py` SHALL contain fewer than 300 lines
- **AND** `python_coverage_schema.py` SHALL contain fewer than 1200 lines

### Requirement: TABLES Registry Completeness

The `TABLES` dict in `theauditor/indexer/schema.py` SHALL contain all table definitions from all schema files.

#### Scenario: Table count unchanged after refactor

- **WHEN** the refactor is complete
- **THEN** `len(TABLES)` SHALL equal 250
- **AND** all tables SHALL be queryable via `aud` commands
- **AND** `aud full --index` SHALL create all 250 tables in repo_index.db

#### Scenario: No duplicate table names

- **WHEN** schema files are loaded
- **THEN** no table name SHALL appear in more than one `*_TABLES` registry dict
- **AND** merging all dicts into `TABLES` SHALL NOT overwrite any table

### Requirement: causal_schema.py File Structure

The `causal_schema.py` file SHALL contain 18 tables organized into 4 categories for causal learning analysis.

#### Scenario: Side effect detection tables present (5 tables)

- **WHEN** `causal_schema.py` is imported
- **THEN** `CAUSAL_TABLES` SHALL contain keys:
  - `python_argument_mutations`
  - `python_augmented_assignments`
  - `python_class_mutations`
  - `python_global_mutations`
  - `python_instance_mutations`

#### Scenario: Exception flow tables present (4 tables)

- **WHEN** `causal_schema.py` is imported
- **THEN** `CAUSAL_TABLES` SHALL contain keys:
  - `python_context_managers_enhanced`
  - `python_exception_catches`
  - `python_exception_raises`
  - `python_finally_blocks`

#### Scenario: Data flow tables present (5 tables)

- **WHEN** `causal_schema.py` is imported
- **THEN** `CAUSAL_TABLES` SHALL contain keys:
  - `python_closure_captures`
  - `python_conditional_calls`
  - `python_io_operations`
  - `python_nonlocal_access`
  - `python_parameter_return_flow`

#### Scenario: Behavioral pattern tables present (4 tables)

- **WHEN** `causal_schema.py` is imported
- **THEN** `CAUSAL_TABLES` SHALL contain keys:
  - `python_dynamic_attributes`
  - `python_generator_yields`
  - `python_property_patterns`
  - `python_recursion_patterns`

### Requirement: python_coverage_schema.py File Structure

The `python_coverage_schema.py` file SHALL contain 68 tables organized into 8 categories for Python language coverage.

#### Scenario: Coverage table count verification

- **WHEN** `python_coverage_schema.py` is imported
- **THEN** `len(PYTHON_COVERAGE_TABLES)` SHALL equal 68

#### Scenario: All coverage categories present

- **WHEN** `python_coverage_schema.py` is imported
- **THEN** `PYTHON_COVERAGE_TABLES` SHALL contain tables for:
  - Fundamentals (8): comprehensions, lambdas, slices, tuples, unpacking, none, truthiness, formatting
  - Operators (6): operators, membership, chained comparisons, ternary, walrus, matrix multiplication
  - Collections (8): dict, list, set, string methods, builtins, itertools, functools, collections
  - Advanced class features (10): metaclasses, descriptors, dataclasses, enums, slots, abstract, method types, multiple inheritance, dunders, visibility
  - Stdlib patterns (8): regex, json, datetime, path, logging, threading, contextlib, type checking
  - Control flow (10): for, while, async for, if, match, break/continue/pass, assert, del, import, with
  - Protocols (10): iterator, container, callable, comparison, arithmetic, pickle, weakref, contextvar, module attrs, class decorators
  - Advanced patterns (8): namespace packages, cached property, descriptor protocol, attribute access, copy, ellipsis, bytes, exec/eval/compile

### Requirement: Security Schema Additions

The `security_schema.py` file SHALL be extended with 8 Python-specific security tables.

#### Scenario: Python security tables added

- **WHEN** the refactor is complete
- **THEN** `SECURITY_TABLES` SHALL contain keys:
  - `python_auth_decorators`
  - `python_command_injection`
  - `python_crypto_operations`
  - `python_dangerous_eval`
  - `python_jwt_operations`
  - `python_password_hashing`
  - `python_path_traversal`
  - `python_sql_injection`
- **AND** `len(SECURITY_TABLES)` SHALL equal 15 (was 7, +8)

### Requirement: Frameworks Schema Additions

The `frameworks_schema.py` file SHALL be extended with 27 Python framework tables.

#### Scenario: Django tables added (9 tables)

- **WHEN** the refactor is complete
- **THEN** `FRAMEWORKS_TABLES` SHALL contain Django table keys:
  - `python_django_admin`
  - `python_django_form_fields`
  - `python_django_forms`
  - `python_django_managers`
  - `python_django_middleware`
  - `python_django_querysets`
  - `python_django_receivers`
  - `python_django_signals`
  - `python_django_views`

#### Scenario: Flask tables added (9 tables)

- **WHEN** the refactor is complete
- **THEN** `FRAMEWORKS_TABLES` SHALL contain Flask table keys:
  - `python_flask_apps`
  - `python_flask_cache`
  - `python_flask_cli_commands`
  - `python_flask_cors`
  - `python_flask_error_handlers`
  - `python_flask_extensions`
  - `python_flask_hooks`
  - `python_flask_rate_limits`
  - `python_flask_websockets`

#### Scenario: Validation framework tables added (6 tables)

- **WHEN** the refactor is complete
- **THEN** `FRAMEWORKS_TABLES` SHALL contain validation table keys:
  - `python_drf_serializer_fields`
  - `python_drf_serializers`
  - `python_marshmallow_fields`
  - `python_marshmallow_schemas`
  - `python_wtforms_fields`
  - `python_wtforms_forms`

#### Scenario: Celery tables added (3 tables)

- **WHEN** the refactor is complete
- **THEN** `FRAMEWORKS_TABLES` SHALL contain Celery table keys:
  - `python_celery_beat_schedules`
  - `python_celery_task_calls`
  - `python_celery_tasks`

#### Scenario: Total frameworks table count

- **WHEN** the refactor is complete
- **THEN** `len(FRAMEWORKS_TABLES)` SHALL equal 33 (was 6, +27)

### Requirement: Zero Runtime Breaking Changes

The refactor SHALL NOT change any table names, column definitions, or indexes.

#### Scenario: Existing databases remain compatible

- **WHEN** `aud full --index` runs after the refactor
- **THEN** all INSERT statements SHALL succeed
- **AND** all SELECT queries in existing code SHALL work unchanged
- **AND** no migration script SHALL be required

#### Scenario: Table names unchanged

- **WHEN** comparing table names before and after refactor
- **THEN** the set of table names SHALL be identical
- **AND** no table SHALL be renamed

### Requirement: Aggregation in schema.py

The aggregation file `theauditor/indexer/schema.py` SHALL import all registry dicts and merge them into `TABLES`.

#### Scenario: New schema imports added

- **WHEN** schema.py is modified
- **THEN** it SHALL import `CAUSAL_TABLES` from `schemas.causal_schema`
- **AND** it SHALL import `PYTHON_COVERAGE_TABLES` from `schemas.python_coverage_schema`

#### Scenario: TABLES dict includes new registries

- **WHEN** `TABLES` dict is constructed
- **THEN** it SHALL unpack `**CAUSAL_TABLES`
- **AND** it SHALL unpack `**PYTHON_COVERAGE_TABLES`
