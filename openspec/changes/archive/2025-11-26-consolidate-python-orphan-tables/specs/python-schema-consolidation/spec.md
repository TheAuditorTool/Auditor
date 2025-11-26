# Python Schema Consolidation Specification Delta

## REMOVED Requirements

### Requirement: Delete Orphan Python Tables

All Python tables that have ZERO consumers (no SELECT queries in rules, commands, taint, or context code) SHALL be deleted from the schema.

#### Scenario: Orphan tables removed from python_schema.py

- **WHEN** the consolidation is complete
- **THEN** `python_schema.py` SHALL NOT contain definitions for any of the 141 orphan tables
- **AND** `PYTHON_TABLES` dict SHALL contain exactly 8 entries
- **AND** the file SHALL be reduced from ~2800 lines to ~300 lines

#### Scenario: Orphan storage handlers removed

- **WHEN** the consolidation is complete
- **THEN** `python_storage.py` SHALL NOT contain handler methods for orphan tables
- **AND** `self.handlers` dict SHALL contain exactly 8 entries
- **AND** the file SHALL be reduced from ~2500 lines to ~300 lines

#### Scenario: Orphan extractor files removed

- **WHEN** the consolidation is complete
- **THEN** the following extractor files SHALL NOT exist:
  - `behavioral_extractors.py`
  - `class_feature_extractors.py`
  - `collection_extractors.py`
  - `control_flow_extractors.py`
  - `data_flow_extractors.py`
  - `exception_flow_extractors.py`
  - `fundamental_extractors.py`
  - `operator_extractors.py`
  - `performance_extractors.py`
  - `protocol_extractors.py`
  - `security_extractors.py`
  - `state_mutation_extractors.py`
  - `stdlib_pattern_extractors.py`
  - `type_extractors.py`

### Requirement: Delete Framework Orphan Tables (31 tables)

Framework-specific tables that are never queried SHALL be deleted.

#### Scenario: Django orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_django_admin`
  - `python_django_form_fields`
  - `python_django_forms`
  - `python_django_managers`
  - `python_django_querysets`
  - `python_django_receivers`
  - `python_django_signals`
- **AND** `python_django_middleware` and `python_django_views` SHALL be KEPT (have consumers)

#### Scenario: Flask orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_flask_apps`
  - `python_flask_cache`
  - `python_flask_cli_commands`
  - `python_flask_cors`
  - `python_flask_error_handlers`
  - `python_flask_extensions`
  - `python_flask_hooks`
  - `python_flask_rate_limits`
  - `python_flask_websockets`
  - `python_blueprints`
- **AND** `python_routes` SHALL be KEPT (has consumers)

#### Scenario: Celery orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_celery_beat_schedules`
  - `python_celery_task_calls`
  - `python_celery_tasks`

#### Scenario: Validation framework orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_drf_serializer_fields`
  - `python_drf_serializers`
  - `python_marshmallow_fields`
  - `python_marshmallow_schemas`
  - `python_wtforms_fields`
  - `python_wtforms_forms`
- **AND** `python_validators` SHALL be KEPT (has consumers)

### Requirement: Delete Security Orphan Tables (8 tables)

Security pattern tables that are extracted but never queried by rules SHALL be deleted.

#### Scenario: Security orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_auth_decorators`
  - `python_command_injection`
  - `python_crypto_operations`
  - `python_dangerous_eval`
  - `python_jwt_operations`
  - `python_password_hashing`
  - `python_path_traversal`
  - `python_sql_injection`

### Requirement: Delete Testing Orphan Tables

Testing framework tables that are never queried SHALL be deleted.

#### Scenario: Testing orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_hypothesis_strategies`
  - `python_mock_patterns`
  - `python_pytest_fixtures`
  - `python_pytest_markers`
  - `python_pytest_parametrize`
  - `python_pytest_plugin_hooks`
  - `python_unittest_test_cases`
  - `python_assertion_patterns`

### Requirement: Delete Control Flow Orphan Tables (10 tables)

Control flow pattern tables that are never queried SHALL be deleted.

#### Scenario: Control flow orphan tables removed

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES` SHALL NOT contain:
  - `python_assert_statements`
  - `python_async_for_loops`
  - `python_break_continue_pass`
  - `python_del_statements`
  - `python_for_loops`
  - `python_if_statements`
  - `python_import_statements`
  - `python_match_statements`
  - `python_while_loops`
  - `python_with_statements`

---

## MODIFIED Requirements

### Requirement: TABLES Registry Count

The `TABLES` dict total count SHALL be updated to reflect orphan table deletion.

#### Scenario: Total table count reduced

- **WHEN** the consolidation is complete
- **THEN** `len(TABLES)` SHALL equal 109 (was 250)
- **AND** the assertion in `schema.py` SHALL be updated to `assert len(TABLES) == 109`

#### Scenario: PYTHON_TABLES count reduced

- **WHEN** the consolidation is complete
- **THEN** `len(PYTHON_TABLES)` SHALL equal 8 (was 149)
- **AND** all other `*_TABLES` dicts SHALL remain unchanged

### Requirement: Generated Code Regeneration

Generated schema code SHALL be regenerated after orphan table deletion.

#### Scenario: Generated types updated

- **WHEN** the consolidation is complete
- **THEN** `generated_types.py` SHALL NOT contain TypedDict classes for deleted tables
- **AND** running codegen SHALL produce identical output

#### Scenario: Generated accessors updated

- **WHEN** the consolidation is complete
- **THEN** `generated_accessors.py` SHALL NOT contain accessor classes for deleted tables
- **AND** running codegen SHALL produce identical output

#### Scenario: Generated cache updated

- **WHEN** the consolidation is complete
- **THEN** `SchemaMemoryCache` SHALL only load 109 tables
- **AND** memory usage SHALL be reduced by ~56%

---

## ADDED Requirements

### Requirement: Used Tables Preserved

Tables with verified consumers SHALL be preserved intact.

#### Scenario: python_decorators preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_decorators']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumers in `interceptors.py`, `deadcode_graph.py`, `query.py` SHALL work

#### Scenario: python_django_middleware preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_django_middleware']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumer in `interceptors.py` SHALL work

#### Scenario: python_django_views preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_django_views']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumer in `interceptors.py` SHALL work

#### Scenario: python_orm_fields preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_orm_fields']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumer in `graphql/overfetch.py` SHALL work

#### Scenario: python_orm_models preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_orm_models']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumers in `overfetch.py`, `discovery.py` SHALL work

#### Scenario: python_package_configs preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_package_configs']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumers in `deps.py`, `blueprint.py` SHALL work

#### Scenario: python_routes preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_routes']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumers in `boundary_analyzer.py`, `deadcode_graph.py`, `query.py` SHALL work

#### Scenario: python_validators preserved

- **WHEN** the consolidation is complete
- **THEN** `PYTHON_TABLES['python_validators']` SHALL exist
- **AND** the table schema SHALL be unchanged
- **AND** consumer in `discovery.py` (via cache) SHALL work

### Requirement: Zero Breaking Changes

The consolidation SHALL NOT break any existing functionality.

#### Scenario: No consumer code changes required

- **WHEN** the consolidation is complete
- **THEN** no code outside schema/storage/extractor layers SHALL require modification
- **AND** all rules SHALL continue working
- **AND** all commands SHALL continue working
- **AND** taint analysis SHALL continue working

#### Scenario: Full pipeline succeeds

- **WHEN** `aud full --offline` runs after consolidation
- **THEN** the pipeline SHALL complete without errors
- **AND** all 109 tables SHALL be created in `repo_index.db`
- **AND** data SHALL be inserted into all 8 Python tables

#### Scenario: Unit tests pass

- **WHEN** `pytest tests/` runs after consolidation
- **THEN** all tests SHALL pass
- **AND** no test SHALL reference deleted tables
