# Tasks: Python Extractor Consolidation & Data Fidelity Control

## 0. Verification (MUST COMPLETE FIRST)

- [ ] 0.1 Read `scripts/extractor_truth.txt` and confirm 87 extractors with data
- [ ] 0.2 Read current `python_schema.py` and document all invented columns
- [ ] 0.3 Run `aud full --offline` and capture current DB size as baseline
- [ ] 0.4 Verify current schema-extractor mismatches documented in verification.md

---

## CRITICAL IMPLEMENTATION NOTE: Junction Table FK Pattern

**⚠️ READ THIS BEFORE IMPLEMENTING PHASES 4 & 5 ⚠️**

Parent tables that have junction table children (e.g., `python_protocols` → `python_protocol_methods`) require special handling:

### The Problem

The current `base_database.py` generic batch flushing pattern does NOT return row IDs:
```python
# WRONG - batch pattern doesn't return IDs
self.generic_batches['python_protocols'].append(record)  # No ID returned!
```

### The Requirement

Parent `add_*` methods MUST use `cursor.execute` directly and return `cursor.lastrowid`:
```python
# CORRECT - direct execute returns ID for FK reference
def add_python_protocol(self, ...) -> int:
    cursor = self.conn.cursor()
    cursor.execute('INSERT INTO python_protocols (...) VALUES (...)', (...))
    return cursor.lastrowid  # FK for junction table
```

### Affected Tables (5 parent tables need this pattern)

| Parent Table | Junction Table | Phase |
|--------------|----------------|-------|
| python_protocols | python_protocol_methods | 4.2 |
| python_type_definitions | python_typeddict_fields | 4.4 |
| python_test_fixtures | python_fixture_params | 5.3 |
| python_framework_config | python_framework_methods | 5.4 |
| python_validation_schemas | python_schema_validators | 5.5 |

### Implementation Reference

See **appendix-implementation.md Section 5.2** for the complete database mixin pattern with working code.

### Audit Checklist

- [ ] Parent table `add_*` methods use `cursor.execute` directly (NOT batch append)
- [ ] Parent table `add_*` methods return `cursor.lastrowid`
- [ ] Storage handlers call parent `add_*` first, capture ID, then call junction `add_*` with FK
- [ ] Junction tables are in `flush_order` AFTER their parent tables

---

## 1. Data Fidelity Control Infrastructure

### 1.1 Create Fidelity Module

- [ ] 1.1.1 Create `theauditor/indexer/fidelity.py`
- [ ] 1.1.2 Implement `DataFidelityError` exception class
- [ ] 1.1.3 Implement `reconcile_fidelity(manifest, receipt, strict)` function
- [ ] 1.1.4 Add logging for errors and warnings
- [ ] 1.1.5 Unit test: reconciliation detects extracted > 0, stored == 0
- [ ] 1.1.6 Unit test: reconciliation passes when counts match

### 1.2 Generate Extraction Manifest

- [ ] 1.2.1 Modify `python_impl.py` to count records per result key
- [ ] 1.2.2 Add `_extraction_manifest` key to result dict
- [ ] 1.2.3 Include metadata: timestamp, file, extractor_version

### 1.3 Generate Storage Receipt

- [ ] 1.3.1 Modify `python_storage.py` handlers to return row counts
- [ ] 1.3.2 Aggregate counts into storage receipt dict
- [ ] 1.3.3 Return receipt from `store()` method

### 1.4 Wire Reconciliation to Orchestrator

- [ ] 1.4.1 Import fidelity module in `orchestrator.py`
- [ ] 1.4.2 Call `reconcile_fidelity()` after Python storage phase
- [ ] 1.4.3 Pass `strict=True` (crash on zero-store)
- [ ] 1.4.4 Log reconciliation report

### 1.5 Verify Fidelity Control Works

- [ ] 1.5.1 Run `aud full --offline` - expect FAILURE (current schema is wrong)
- [ ] 1.5.2 Document which tables fail fidelity check
- [ ] 1.5.3 Confirm fidelity check catches the known issues

---

## 2. Expression Table Decomposition

### 2.1 Create python_comprehensions Table

- [ ] 2.1.1 Add `python_comprehensions` TableSchema to `python_schema.py`
- [ ] 2.1.2 Columns: id, file, line, comp_kind, comp_type, iteration_var, iteration_source, result_expr, filter_expr, has_filter, nesting_level, in_function
- [ ] 2.1.3 Add indexes: file, comp_kind

### 2.2 Create python_control_statements Table

- [ ] 2.2.1 Add `python_control_statements` TableSchema to `python_schema.py`
- [ ] 2.2.2 Columns: id, file, line, statement_kind, statement_type, loop_type, condition_type, has_message, target_count, target_type, context_count, has_alias, is_async, in_function
- [ ] 2.2.3 Add indexes: file, statement_kind

### 2.3 Add Database Mixin Methods

- [ ] 2.3.1 Add `add_python_comprehension()` to `python_database.py`
- [ ] 2.3.2 Add `add_python_control_statement()` to `python_database.py`
- [ ] 2.3.3 Add both tables to `flush_order` in `base_database.py`

### 2.4 Add Storage Handlers

- [ ] 2.4.1 Add `_store_python_comprehensions()` to `python_storage.py`
- [ ] 2.4.2 Add `_store_python_control_statements()` to `python_storage.py`
- [ ] 2.4.3 Register handlers in `self.handlers` dict

### 2.5 Update Orchestrator Mappings

- [ ] 2.5.1 Map `extract_comprehensions` to `python_comprehensions`
- [ ] 2.5.2 Map `extract_break_continue_pass` to `python_control_statements` with `statement_kind='control'`
- [ ] 2.5.3 Map `extract_assert_statements` to `python_control_statements` with `statement_kind='assert'`
- [ ] 2.5.4 Map `extract_del_statements` to `python_control_statements` with `statement_kind='del'`
- [ ] 2.5.5 Map `extract_with_statements` to `python_control_statements` with `statement_kind='with'`

### 2.6 Re-route Misplaced Extractors

- [ ] 2.6.1 Re-route `extract_copy_protocol` to `python_protocols` with `protocol_kind='copy'`
- [ ] 2.6.2 Re-route `extract_class_decorators` to `python_class_features` with `feature_kind='class_decorator'`
- [ ] 2.6.3 Re-route `extract_recursion_patterns` to `python_functions_advanced` with `function_kind='recursive'`
- [ ] 2.6.4 Re-route `extract_memoization_patterns` to `python_functions_advanced` with `function_kind='memoized'`
- [ ] 2.6.5 Re-route `extract_loop_complexity` to `python_loops` with `loop_kind='complexity_analysis'`
- [ ] 2.6.6 Add required columns to target tables for re-routed data

### 2.7 Verify Phase 2

- [ ] 2.7.1 Run `aud full --offline`
- [ ] 2.7.2 Verify fidelity check passes for new tables
- [ ] 2.7.3 Verify `python_expressions` row count is reduced
- [ ] 2.7.4 Query new tables to confirm data present

---

## 3. Control Flow Tables Alignment (5 Tables)

### 3.1 Align python_loops

- [ ] 3.1.1 Add `loop_kind` column (discriminator)
- [ ] 3.1.2 Remove invented columns: target, iterator, body_line_count
- [ ] 3.1.3 Add missing columns: target_count, in_function, is_infinite
- [ ] 3.1.4 Add complexity columns: estimated_complexity, has_growing_operation
- [ ] 3.1.5 Update `add_python_loop()` signature
- [ ] 3.1.6 Update storage handler .get() calls

### 3.2 Align python_branches

- [ ] 3.2.1 Add `branch_kind` column
- [ ] 3.2.2 Remove invented column: condition
- [ ] 3.2.3 Fix column type: has_elif (was elif_count)
- [ ] 3.2.4 Add missing columns: chain_length, has_complex_condition, nesting_level, handling_strategy, variable_name, is_re_raise, from_exception, message, has_cleanup, cleanup_calls, in_function
- [ ] 3.2.5 Update `add_python_branch()` signature
- [ ] 3.2.6 Update storage handler

### 3.3 Align python_functions_advanced

- [ ] 3.3.1 Add `function_kind` column
- [ ] 3.3.2 Remove invented column: is_method
- [ ] 3.3.3 Add missing columns: function_name, has_async_for, has_async_with, has_yield_from, has_send, is_infinite, generator_type, parameter_count, parameters, body, captures_closure, captured_vars, used_in, as_name, context_expr, context_type, base_case_line, calls_function, recursion_type, cache_size, memoization_type, is_recursive, has_memoization
- [ ] 3.3.4 Update `add_python_function_advanced()` signature
- [ ] 3.3.5 Update storage handler

### 3.4 Align python_io_operations

- [ ] 3.4.1 Add `io_kind` column
- [ ] 3.4.2 Remove invented columns: is_taint_source, is_taint_sink
- [ ] 3.4.3 Add missing columns: flow_type, parameter_name, return_expr, is_async, function_name
- [ ] 3.4.4 Update `add_python_io_operation()` signature
- [ ] 3.4.5 Update storage handler

### 3.5 Align python_state_mutations

- [ ] 3.5.1 Add `mutation_kind` column
- [ ] 3.5.2 Add missing columns: is_init, is_dunder_method, is_property_setter, operator, target_type
- [ ] 3.5.3 Update `add_python_state_mutation()` signature
- [ ] 3.5.4 Update storage handler

### 3.6 Verify Phase 3

- [ ] 3.6.1 Run `aud full --offline`
- [ ] 3.6.2 Verify fidelity check passes for all 5 tables
- [ ] 3.6.3 Verify zero NULL in columns that should have data
- [ ] 3.6.4 Test two-discriminator queries work

---

## 4. OOP/Types Tables Alignment (5 Tables)

### 4.1 Align python_class_features

- [ ] 4.1.1 Add `feature_kind` column
- [ ] 4.1.2 Expand `details` JSON to individual columns: metaclass_name, is_definition, slot_count, abstract_method_count, field_count, frozen, enum_name, enum_type, member_count, method_name, category, visibility, is_name_mangled, method_type_value, decorator, decorator_type, has_arguments
- [ ] 4.1.3 Update `add_python_class_feature()` signature
- [ ] 4.1.4 Update storage handler

### 4.2 Align python_protocols and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [ ] 4.2.1 Add `protocol_kind` column
- [ ] 4.2.2 Add protocol-specific columns: has_iter, has_next, is_generator, raises_stopiteration, has_len, has_getitem, has_setitem, has_delitem, has_contains, is_sequence, is_mapping, param_count, has_args, has_kwargs, has_getstate, has_setstate, has_reduce, has_reduce_ex, has_copy, has_deepcopy
- [ ] 4.2.3 Create `python_protocol_methods` junction table
- [ ] 4.2.4 Add `add_python_protocol()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [ ] 4.2.5 Add `add_python_protocol_method()` to database mixin
- [ ] 4.2.6 Add junction table to flush_order (AFTER python_protocols)
- [ ] 4.2.7 Update storage handler to: (1) call add_python_protocol, (2) capture ID, (3) call add_python_protocol_method with FK

### 4.3 Align python_descriptors

- [ ] 4.3.1 Add `descriptor_kind` column
- [ ] 4.3.2 Add missing columns: name, in_class, is_data_descriptor, property_name, access_type, has_computation, has_validation, is_functools, method_name
- [ ] 4.3.3 Update `add_python_descriptor()` signature
- [ ] 4.3.4 Update storage handler

### 4.4 Align python_type_definitions and Create Junction Tables

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [ ] 4.4.1 Add `type_kind` column
- [ ] 4.4.2 Remove `type_params` JSON, add type_param_1..5 columns
- [ ] 4.4.3 Create `python_typeddict_fields` junction table
- [ ] 4.4.4 Add `add_python_type_definition()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [ ] 4.4.5 Add `add_python_typeddict_field()` to database mixin
- [ ] 4.4.6 Add missing columns: typeddict_name, protocol_name, is_runtime_checkable
- [ ] 4.4.7 Add junction table to flush_order (AFTER python_type_definitions)
- [ ] 4.4.8 Update storage handler to: (1) call add_python_type_definition, (2) capture ID, (3) call add_python_typeddict_field with FK

### 4.5 Align python_literals

- [ ] 4.5.1 Add `literal_kind` column
- [ ] 4.5.2 Expand literal_values JSON to literal_value_1..5 columns
- [ ] 4.5.3 Add missing columns: function_name, overload_count, variants
- [ ] 4.5.4 Update `add_python_literal()` signature
- [ ] 4.5.5 Update storage handler

### 4.6 Verify Phase 4

- [ ] 4.6.1 Run `aud full --offline`
- [ ] 4.6.2 Verify fidelity check passes
- [ ] 4.6.3 Verify junction tables populated
- [ ] 4.6.4 Test SQL JOINs on junction tables

---

## 5. Security/Testing Tables Alignment (5 Tables)

### 5.1 Align python_security_findings

- [ ] 5.1.1 Verify columns match extractor truth (finding_type as kind already exists)
- [ ] 5.1.2 Add missing columns from security extractors: function, is_vulnerable, shell_true, is_constant_input, is_critical, has_concatenation, permissions

### 5.2 Align python_test_cases

- [ ] 5.2.1 Add `test_kind` column
- [ ] 5.2.2 Add missing columns: assertion_type, function_name, test_expr

### 5.3 Align python_test_fixtures and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [ ] 5.3.1 Add `fixture_kind` column
- [ ] 5.3.2 Create `python_fixture_params` junction table
- [ ] 5.3.3 Add `add_python_test_fixture()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [ ] 5.3.4 Add `add_python_fixture_param()` to database mixin
- [ ] 5.3.5 Add junction table to flush_order (AFTER python_test_fixtures)
- [ ] 5.3.6 Add missing columns from testing extractors
- [ ] 5.3.7 Update storage handler to: (1) call add_python_test_fixture, (2) capture ID, (3) call add_python_fixture_param with FK

### 5.4 Align python_framework_config and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [ ] 5.4.1 Verify framework and config_kind columns
- [ ] 5.4.2 Expand `details` JSON to individual columns
- [ ] 5.4.3 Create `python_framework_methods` junction table
- [ ] 5.4.4 Add `add_python_framework_config()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [ ] 5.4.5 Add `add_python_framework_method()` to database mixin
- [ ] 5.4.6 Add junction table to flush_order (AFTER python_framework_config)
- [ ] 5.4.7 Update storage handler to: (1) call add_python_framework_config, (2) capture ID, (3) call add_python_framework_method with FK

### 5.5 Align python_validation_schemas and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [ ] 5.5.1 Add `schema_kind` column
- [ ] 5.5.2 Create `python_schema_validators` junction table
- [ ] 5.5.3 Add `add_python_validation_schema()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [ ] 5.5.4 Add `add_python_schema_validator()` to database mixin
- [ ] 5.5.5 Add junction table to flush_order (AFTER python_validation_schemas)
- [ ] 5.5.6 Update storage handler to: (1) call add_python_validation_schema, (2) capture ID, (3) call add_python_schema_validator with FK

### 5.6 Verify Phase 5

- [ ] 5.6.1 Run `aud full --offline`
- [ ] 5.6.2 Verify fidelity check passes
- [ ] 5.6.3 Verify junction tables populated

---

## 6. Low-Level Tables Alignment (5 Tables)

### 6.1 Align python_operators

- [ ] 6.1.1 Add `operator_kind` column
- [ ] 6.1.2 Verify columns match: operator, operator_type, in_function, chain_length, operators, has_complex_condition, used_in, variable, container_type

### 6.2 Align python_collections

- [ ] 6.2.1 Add `collection_kind` column
- [ ] 6.2.2 Verify columns match: operation, has_default, method, mutates_in_place, builtin, has_key

### 6.3 Align python_stdlib_usage

- [ ] 6.3.1 Add `stdlib_kind` column
- [ ] 6.3.2 Verify columns match: pattern, is_decorator, operation, direction, log_level, path_type, has_flags, threading_type

### 6.4 Align python_imports_advanced

- [ ] 6.4.1 Add `import_kind` column
- [ ] 6.4.2 Wire `extract_python_exports` with `import_kind='export'`
- [ ] 6.4.3 Add missing columns: default, name, type (from exports)

### 6.5 Reduce python_expressions

- [ ] 6.5.1 Remove columns for re-routed extractors
- [ ] 6.5.2 Remove columns for split-off tables
- [ ] 6.5.3 Verify remaining ~25 columns, ~50% sparsity

### 6.6 Verify Phase 6

- [ ] 6.6.1 Run `aud full --offline`
- [ ] 6.6.2 Verify fidelity check passes
- [ ] 6.6.3 Verify exports data stored

---

## 7. Wire Missing Framework Extractors

### 7.1 Wire Flask Extractors

- [ ] 7.1.1 Wire `extract_flask_blueprints` to `python_framework_config` with `framework='flask', config_kind='blueprint'`

### 7.2 Wire Celery Extractors

- [ ] 7.2.1 Wire `extract_celery_tasks` to `python_framework_config` with `framework='celery', config_kind='task'`
- [ ] 7.2.2 Wire `extract_celery_task_calls` to `python_framework_config` with `framework='celery', config_kind='task_call'`
- [ ] 7.2.3 Wire `extract_celery_beat_schedules` to `python_framework_config` with `framework='celery', config_kind='schedule'`

### 7.3 Wire GraphQL Extractors

- [ ] 7.3.1 Wire `extract_graphene_resolvers` to `python_framework_config` with `framework='graphene', config_kind='resolver'`
- [ ] 7.3.2 Wire `extract_ariadne_resolvers` to `python_framework_config` with `framework='ariadne', config_kind='resolver'`
- [ ] 7.3.3 Wire `extract_strawberry_resolvers` to `python_framework_config` with `framework='strawberry', config_kind='resolver'`

### 7.4 Verify Phase 7

- [ ] 7.4.1 Run `aud full --offline` on a Flask/Celery/GraphQL project
- [ ] 7.4.2 Verify framework data stored in `python_framework_config`

---

## 8. Codegen & Final Verification

### 8.1 Regenerate Codegen Files

- [ ] 8.1.1 Regenerate `generated_types.py`
- [ ] 8.1.2 Regenerate `generated_accessors.py`
- [ ] 8.1.3 Regenerate `generated_cache.py`

### 8.2 Update Schema Assertions

- [ ] 8.2.1 Update `theauditor/indexer/schema.py`: `len(TABLES) == 136`
- [ ] 8.2.2 Update `python_schema.py`: `len(PYTHON_TABLES) == 30`
- [ ] 8.2.3 Add junction tables to schema registry

### 8.3 Create Schema Contract Test

- [ ] 8.3.1 Create `tests/test_schema_contract.py`
- [ ] 8.3.2 Test: all extractor outputs have tables
- [ ] 8.3.3 Test: extractor keys match schema columns
- [ ] 8.3.4 Test: no JSON blob columns

### 8.4 Final Verification

- [ ] 8.4.1 Run full test suite: `pytest tests/ -v`
- [ ] 8.4.2 Run `aud full --offline` on TheAuditor codebase
- [ ] 8.4.3 Verify DB size > 150MB (recovered from 127MB)
- [ ] 8.4.4 Verify fidelity check passes with 0 errors
- [ ] 8.4.5 Test taint analysis still works
- [ ] 8.4.6 Test `aud explain` still works
- [ ] 8.4.7 Test pattern rules still work

---

## 9. Documentation & Commit

### 9.1 Update Documentation

- [ ] 9.1.1 Update CLAUDE.md with new table counts
- [ ] 9.1.2 Document fidelity control in Architecture.md
- [ ] 9.1.3 Update project.md schema section

### 9.2 Commit

- [ ] 9.2.1 Stage all changes
- [ ] 9.2.2 Commit with comprehensive message
- [ ] 9.2.3 DO NOT add "Co-authored-by: Claude"

### 9.3 Archive OpenSpec

- [ ] 9.3.1 Run `openspec archive python-extractor-consolidation-fidelity --yes`
- [ ] 9.3.2 Verify archive created
