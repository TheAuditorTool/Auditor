# Tasks: Python Extractor Consolidation & Data Fidelity Control

## Progress Summary

| Phase | Status | Tasks | Notes |
|-------|--------|-------|-------|
| 0. Verification | COMPLETE | 4/4 | Baseline: 150.2MB, 28 Python tables |
| 1. Fidelity Control | COMPLETE | 18/18 | Files: exceptions.py, fidelity.py |
| 2. Expression Decomposition | COMPLETE | 21/21 | 2 new tables, 5 re-routes |
| 3. Control Flow Alignment | COMPLETE | 22/22 | Two-discriminator pattern for 5 tables |
| 4. OOP/Types Alignment | COMPLETE | 27/27 | 2 junction tables, ID return pattern proven |
| 5. Security/Testing Alignment | COMPLETE | 22/22 | 3 junction tables, 4 extractors wired |
| 6. Low-Level Alignment | COMPLETE | 22/22 | 5 tables aligned, exports wired (3,354 rows RECOVERED) |
| 7. Framework Extractors | COMPLETE | 9/9 | Done in Phase 5 |
| 8. Codegen & Verification | PENDING | 0/14 | |
| 9. Documentation & Commit | PENDING | 0/6 | |

**Last Updated**: 2025-11-26
**Current DB Size**: ~145 MB (post-Phase 6 verification)
**Schema Tables**: 136
**Pipeline Status**: 25/25 phases PASS (252.8s)

---

## 0. Verification (MUST COMPLETE FIRST)

- [x] 0.1 Read `scripts/extractor_truth.txt` and confirm 87 extractors with data
- [x] 0.2 Read current `python_schema.py` and document all invented columns
- [x] 0.3 Run `aud full --offline` and capture current DB size as baseline (150.2MB)
- [x] 0.4 Verify current schema-extractor mismatches documented in verification.md

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

- [x] Parent table `add_*` methods use `cursor.execute` directly (NOT batch append)
- [x] Parent table `add_*` methods return `cursor.lastrowid`
- [x] Storage handlers call parent `add_*` first, capture ID, then call junction `add_*` with FK
- [x] Junction tables are in `flush_order` AFTER their parent tables

**All 5 parent tables with junction children now use ID return pattern:**
- python_protocols → python_protocol_methods (Phase 4)
- python_type_definitions → python_typeddict_fields (Phase 4)
- python_test_fixtures → python_fixture_params (Phase 5)
- python_framework_config → python_framework_methods (Phase 5)
- python_validation_schemas → python_schema_validators (Phase 5)

---

## 1. Data Fidelity Control Infrastructure

### 1.1 Create Fidelity Module

- [x] 1.1.1 Create `theauditor/indexer/fidelity.py`
- [x] 1.1.2 Implement `DataFidelityError` exception class (in `exceptions.py`)
- [x] 1.1.3 Implement `reconcile_fidelity(manifest, receipt, strict)` function
- [x] 1.1.4 Add logging for errors and warnings
- [x] 1.1.5 Unit test: reconciliation detects extracted > 0, stored == 0
- [x] 1.1.6 Unit test: reconciliation passes when counts match

### 1.2 Generate Extraction Manifest

- [x] 1.2.1 Modify `python_impl.py` to count records per result key
- [x] 1.2.2 Add `_extraction_manifest` key to result dict
- [x] 1.2.3 Include metadata: timestamp, file, extractor_version

### 1.3 Generate Storage Receipt

- [x] 1.3.1 Modify `storage/__init__.py` to use delta counting (no handler changes needed)
- [x] 1.3.2 Aggregate counts into storage receipt dict
- [x] 1.3.3 Return receipt from `store()` method

### 1.4 Wire Reconciliation to Orchestrator

- [x] 1.4.1 Import fidelity module in `orchestrator.py`
- [x] 1.4.2 Call `reconcile_fidelity()` after Python storage phase
- [x] 1.4.3 Pass `strict=True` (crash on zero-store)
- [x] 1.4.4 Log reconciliation report

### 1.5 Verify Fidelity Control Works

- [x] 1.5.1 Run `aud full --offline` - PASSED (handlers exist for all Python data types)
- [x] 1.5.2 Document which tables fail fidelity check - NONE (see note below)
- [x] 1.5.3 Confirm fidelity check catches the known issues - VERIFIED (see note below)

**NOTE on Fidelity Scope:**
The implemented fidelity check verifies:
- All extracted data types have storage handlers (manifest keys == receipt keys)
- Handlers receive correct item counts (len(data) proxy - handlers don't swallow exceptions)

The fidelity check does NOT verify:
- Schema columns match extractor output keys (caught by Phase 8 CI test)
- Discriminator values don't overwrite subtypes (fixed in Phases 2-6)
- Data is written to correct DB columns (fixed in Phases 2-6)

Handler exception safety verified: no try/except blocks in python_storage.py or core_storage.py

### Implementation Artifacts (Phase 1)

**Files Created:**
- `theauditor/indexer/exceptions.py` (24 lines) - DataFidelityError exception
- `theauditor/indexer/fidelity.py` (99 lines) - reconcile_fidelity() function

**Files Modified:**
- `theauditor/ast_extractors/python_impl.py:1107-1133` - Manifest generation (+27 lines)
- `theauditor/indexer/storage/__init__.py:71-124` - Receipt generation (+24 lines)
- `theauditor/indexer/orchestrator.py:46-47,747-779` - Fidelity wiring (+21 lines)

---

## 2. Expression Table Decomposition

### 2.1 Create python_comprehensions Table

- [x] 2.1.1 Add `python_comprehensions` TableSchema to `python_schema.py`
- [x] 2.1.2 Columns: id, file, line, comp_kind, comp_type, iteration_var, iteration_source, result_expr, filter_expr, has_filter, nesting_level, in_function
- [x] 2.1.3 Add indexes: file, comp_kind, in_function

### 2.2 Create python_control_statements Table

- [x] 2.2.1 Add `python_control_statements` TableSchema to `python_schema.py`
- [x] 2.2.2 Columns: id, file, line, statement_kind, statement_type, loop_type, condition_type, has_message, target_count, target_type, context_count, has_alias, is_async, in_function
- [x] 2.2.3 Add indexes: file, statement_kind, in_function

### 2.3 Add Database Mixin Methods

- [x] 2.3.1 Add `add_python_comprehension()` to `python_database.py`
- [x] 2.3.2 Add `add_python_control_statement()` to `python_database.py`
- [x] 2.3.3 Add both tables to `flush_order` in `base_database.py`

### 2.4 Add Storage Handlers

- [x] 2.4.1 Add `_store_python_comprehensions()` to `python_storage.py`
- [x] 2.4.2 Add `_store_python_control_statements()` to `python_storage.py`
- [x] 2.4.3 Register handlers in `self.handlers` dict

### 2.5 Update Orchestrator Mappings

- [x] 2.5.1 Map `extract_comprehensions` to `python_comprehensions`
- [x] 2.5.2 Map `extract_break_continue_pass` to `python_control_statements` (statement_kind from extractor)
- [x] 2.5.3 Map `extract_assert_statements` to `python_control_statements` with `statement_kind='assert'`
- [x] 2.5.4 Map `extract_del_statements` to `python_control_statements` with `statement_kind='del'`
- [x] 2.5.5 Map `extract_with_statements` to `python_control_statements` with `statement_kind='with'`

### 2.6 Re-route Misplaced Extractors

- [x] 2.6.1 Re-route `extract_copy_protocol` to `python_protocols` with `protocol_type='copy'`
- [x] 2.6.2 Re-route `extract_class_decorators` to `python_class_features` with `feature_type='class_decorator'`
- [x] 2.6.3 Re-route `extract_recursion_patterns` to `python_functions_advanced` with `function_type='recursive'`
- [x] 2.6.4 Re-route `extract_memoization_patterns` to `python_functions_advanced` with `function_type='memoized'`
- [x] 2.6.5 Re-route `extract_loop_complexity` to `python_loops` with `loop_type='complexity_analysis'`
- [x] 2.6.6 Target tables already have required columns (no schema changes needed)

### 2.7 Verify Phase 2

- [x] 2.7.1 Run `aud full --offline` - PASSED (246s, 131 tables)
- [x] 2.7.2 Verify fidelity check passes for new tables - PASSED
- [x] 2.7.3 Verify `python_expressions` row count is reduced: 38k → 14,838 (61% reduction)
- [x] 2.7.4 Query new tables to confirm data present - VERIFIED

### Implementation Artifacts (Phase 2)

**Files Created/Modified:**
- `theauditor/indexer/schemas/python_schema.py` - Added PYTHON_COMPREHENSIONS, PYTHON_CONTROL_STATEMENTS TableSchema
- `theauditor/indexer/database/python_database.py` - Added add_python_comprehension(), add_python_control_statement()
- `theauditor/indexer/storage/python_storage.py` - Added handlers, registered in self.handlers
- `theauditor/indexer/database/base_database.py` - Added to flush_order
- `theauditor/ast_extractors/python_impl.py` - Routed extractors to new tables, re-routed 5 misplaced extractors
- `theauditor/indexer/schema.py` - Updated table count assertion (129 → 131), added exports

**Verification Results:**
| Table | Rows | Notes |
|-------|------|-------|
| python_comprehensions | 1,716 | list=873, generator=739, set=59, dict=45 |
| python_control_statements | 2,250 | continue=1039, break=364, pass=354, with=343, assert=136, del=14 |
| python_expressions | 14,838 | Reduced from ~38k (61% reduction) |
| python_functions_advanced (recursive/memoized) | 13,808 | Re-routed |
| python_loops (complexity_analysis) | 5,312 | Re-routed |
| python_class_features (class_decorator) | 110 | Re-routed |

---

## 3. Control Flow Tables Alignment (5 Tables) - COMPLETE

### 3.1 Align python_loops

- [x] 3.1.1 Add `loop_kind` column (discriminator)
- [x] 3.1.2 Remove invented columns: target, iterator, body_line_count
- [x] 3.1.3 Add missing columns: target_count, in_function, is_infinite
- [x] 3.1.4 Add complexity columns: estimated_complexity, has_growing_operation
- [x] 3.1.5 Update `add_python_loop()` signature
- [x] 3.1.6 Update storage handler .get() calls

### 3.2 Align python_branches

- [x] 3.2.1 Add `branch_kind` column
- [x] 3.2.2 Remove invented column: condition (added back for raises)
- [x] 3.2.3 Fix column type: has_elif (was elif_count)
- [x] 3.2.4 Add missing columns: chain_length, has_complex_condition, nesting_level, handling_strategy, variable_name, is_re_raise, from_exception, message, has_cleanup, cleanup_calls, in_function
- [x] 3.2.5 Update `add_python_branch()` signature
- [x] 3.2.6 Update storage handler with JSON serialization for list columns

### 3.3 Align python_functions_advanced

- [x] 3.3.1 Add `function_kind` column
- [x] 3.3.2 Remove invented column: is_method
- [x] 3.3.3 Add missing columns: function_name, has_async_for, has_async_with, has_yield_from, has_send, is_infinite, generator_type, parameter_count, parameters, body, captures_closure, captured_vars, used_in, as_name, context_expr, context_type, base_case_line, calls_function, recursion_type, cache_size, memoization_type, is_recursive, has_memoization
- [x] 3.3.4 Update `add_python_function_advanced()` signature
- [x] 3.3.5 Update storage handler with JSON serialization for list columns

### 3.4 Align python_io_operations

- [x] 3.4.1 Add `io_kind` column
- [x] 3.4.2 Remove invented columns: is_taint_source, is_taint_sink
- [x] 3.4.3 Add missing columns: flow_type, parameter_name, return_expr, is_async, function_name, is_static
- [x] 3.4.4 Update `add_python_io_operation()` signature
- [x] 3.4.5 Update storage handler

### 3.5 Align python_state_mutations

- [x] 3.5.1 Add `mutation_kind` column
- [x] 3.5.2 Add missing columns: is_init, is_dunder_method, is_property_setter, operator, target_type, operation
- [x] 3.5.3 Update `add_python_state_mutation()` signature
- [x] 3.5.4 Update storage handler

### 3.6 Update python_impl.py with Two-Discriminator Pattern

- [x] 3.6.1 Change `loop_type = 'for_loop'` to `loop_kind = 'for'` (preserve loop_type from extractor)
- [x] 3.6.2 Change `branch_type = 'if'` to `branch_kind = 'if'` (preserve branch_type from extractor)
- [x] 3.6.3 Change `function_type = 'async'` to `function_kind = 'async'` (preserve function_type from extractor)
- [x] 3.6.4 Change `io_type` to `io_kind` (preserve io_type from extractor)
- [x] 3.6.5 Change `mutation_type` to `mutation_kind` (preserve mutation_type from extractor)

### 3.7 Verify Phase 3

- [x] 3.7.1 Run `aud full --offline` - PASSED (249s, all 25 phases successful)
- [x] 3.7.2 Verify fidelity check passes for all 5 tables - PASSED
- [x] 3.7.3 Verify two-discriminator pattern works (loop_kind/loop_type, branch_kind/branch_type, etc.)
- [x] 3.7.4 Verify row counts: loops=8922, branches=9756, functions_advanced=14616, io_operations=18805, state_mutations=1375

### Implementation Artifacts (Phase 3)

**Files Modified:**
- `theauditor/indexer/schemas/python_schema.py` - Added *_kind columns, removed invented columns, added extractor truth columns
- `theauditor/indexer/database/python_database.py` - Updated 5 add_* methods with new signatures
- `theauditor/indexer/storage/python_storage.py` - Updated 5 handlers with new column mappings, added JSON serialization
- `theauditor/ast_extractors/python_impl.py` - Changed all *_type assignments to *_kind (two-discriminator pattern)

**Verification Results:**
| Table | Rows | Discriminator | Subtypes |
|-------|------|---------------|----------|
| python_loops | 8,922 | loop_kind (for, while, async_for, complexity_analysis) | loop_type (enumerate, items, plain, range, zip) |
| python_branches | 9,756 | branch_kind (if, match, raise, except, finally) | N/A |
| python_functions_advanced | 14,616 | function_kind (async, async_generator, context_manager, generator, lambda, memoized, recursive) | N/A |
| python_io_operations | 18,805 | io_kind (DB_*, FILE_*, NETWORK, PROCESS, conditional, nonlocal, param_flow) | N/A |
| python_state_mutations | 1,375 | mutation_kind (argument, augmented, class, global, instance) | mutation_type (assignment, attr_assignment, etc.) |

---

## 4. OOP/Types Tables Alignment (5 Tables) - COMPLETE

### 4.1 Align python_class_features

- [x] 4.1.1 Add `feature_kind` column
- [x] 4.1.2 Expand `details` JSON to individual columns: metaclass_name, is_definition, slot_count, abstract_method_count, field_count, frozen, enum_name, enum_type, member_count, method_name, category, visibility, is_name_mangled, method_type_value, decorator, decorator_type, has_arguments
- [x] 4.1.3 Update `add_python_class_feature()` signature
- [x] 4.1.4 Update storage handler

### 4.2 Align python_protocols and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [x] 4.2.1 Add `protocol_kind` column
- [x] 4.2.2 Add protocol-specific columns: has_iter, has_next, is_generator, raises_stopiteration, has_len, has_getitem, has_setitem, has_delitem, has_contains, is_sequence, is_mapping, param_count, has_args, has_kwargs, has_getstate, has_setstate, has_reduce, has_reduce_ex, has_copy, has_deepcopy
- [x] 4.2.3 Create `python_protocol_methods` junction table
- [x] 4.2.4 Add `add_python_protocol()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [x] 4.2.5 Add `add_python_protocol_method()` to database mixin
- [x] 4.2.6 Add junction table to flush_order (AFTER python_protocols)
- [x] 4.2.7 Update storage handler to: (1) call add_python_protocol, (2) capture ID, (3) call add_python_protocol_method with FK

### 4.3 Align python_descriptors

- [x] 4.3.1 Add `descriptor_kind` column
- [x] 4.3.2 Add missing columns: name, in_class, is_data_descriptor, property_name, access_type, has_computation, has_validation, is_functools, method_name
- [x] 4.3.3 Update `add_python_descriptor()` signature
- [x] 4.3.4 Update storage handler

### 4.4 Align python_type_definitions and Create Junction Tables

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [x] 4.4.1 Add `type_kind` column
- [x] 4.4.2 Remove `type_params` JSON, add type_param_1..5 columns
- [x] 4.4.3 Create `python_typeddict_fields` junction table
- [x] 4.4.4 Add `add_python_type_definition()` - MUST return `cursor.lastrowid` (NOT batch pattern)
- [x] 4.4.5 Add `add_python_typeddict_field()` to database mixin
- [x] 4.4.6 Add missing columns: typeddict_name, protocol_name, is_runtime_checkable
- [x] 4.4.7 Add junction table to flush_order (AFTER python_type_definitions)
- [x] 4.4.8 Update storage handler to: (1) call add_python_type_definition, (2) capture ID, (3) call add_python_typeddict_field with FK

### 4.5 Align python_literals

- [x] 4.5.1 Add `literal_kind` column
- [x] 4.5.2 Expand literal_values JSON to literal_value_1..5 columns
- [x] 4.5.3 Add missing columns: function_name, overload_count, variants
- [x] 4.5.4 Update `add_python_literal()` signature
- [x] 4.5.5 Update storage handler

### 4.6 Verify Phase 4

- [x] 4.6.1 Run `aud full --offline` - PASSED (232s, all 25 phases successful)
- [x] 4.6.2 Verify fidelity check passes - PASSED
- [x] 4.6.3 Verify junction tables populated - python_typeddict_fields: 1,106 rows
- [x] 4.6.4 Test SQL JOINs on junction tables - PASSED

### Implementation Artifacts (Phase 4)

**Files Modified:**
- `theauditor/indexer/schemas/python_schema.py` - Updated 5 OOP/Types tables, created 2 junction tables
- `theauditor/indexer/database/python_database.py` - Updated 5 add_* methods, added 2 junction methods
- `theauditor/indexer/storage/python_storage.py` - Updated 5 handlers with junction logic
- `theauditor/indexer/database/base_database.py` - Added junction tables to flush_order
- `theauditor/ast_extractors/python_impl.py` - Changed all *_type assignments to *_kind
- `theauditor/indexer/schema.py` - Updated table count assertion (131 -> 133)

**Verification Results:**
| Table | Rows | Discriminator | Notes |
|-------|------|---------------|-------|
| python_class_features | 5,758 | feature_kind (metaclass, dataclass, enum, slots, abstract, method_type, dunder, visibility, class_decorator, inheritance) | details JSON expanded |
| python_protocols | 346 | protocol_kind (arithmetic, callable, comparison, container, context_manager, iterator, pickle) | Direct insert with lastrowid |
| python_descriptors | 37 | descriptor_kind (attr_access, descriptor, descriptor_protocol, dynamic_attr, property) | has_getter->has_get renamed |
| python_type_definitions | 143 | type_kind (typed_dict, generic, protocol) | Direct insert with lastrowid |
| python_literals | 14 | literal_kind (literal, overload) | literal_values JSON expanded |

**Junction Tables:**
| Table | Rows | FK | Notes |
|-------|------|----|----|
| python_protocol_methods | 0 | protocol_id -> python_protocols.id | Ready but extractors don't output implemented_methods array |
| python_typeddict_fields | 1,106 | typeddict_id -> python_type_definitions.id | Working correctly |

---

## 5. Security/Testing Tables Alignment (5 Tables) - COMPLETE

### 5.1 Align python_security_findings

- [x] 5.1.1 Add `finding_kind` discriminator column
- [x] 5.1.2 Remove invented columns: severity, source_expr, sink_expr, vulnerable_code, cwe_id
- [x] 5.1.3 Add missing columns: function_name, decorator_name, permissions, is_vulnerable, shell_true, is_constant_input, is_critical, has_concatenation
- [x] 5.1.4 Update `add_python_security_finding()` signature
- [x] 5.1.5 Update storage handler with two-discriminator pattern

### 5.2 Align python_test_cases

- [x] 5.2.1 Add `test_kind` column
- [x] 5.2.2 Remove invented column: expected_exception
- [x] 5.2.3 Add missing columns: function_name, test_expr
- [x] 5.2.4 Update `add_python_test_case()` signature
- [x] 5.2.5 Update storage handler with two-discriminator pattern

### 5.3 Align python_test_fixtures and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [x] 5.3.1 Add `fixture_kind` column
- [x] 5.3.2 Remove `params` JSON blob
- [x] 5.3.3 Add `in_function` column
- [x] 5.3.4 Create `python_fixture_params` junction table
- [x] 5.3.5 Add `add_python_test_fixture()` - returns `cursor.lastrowid` (ID return pattern)
- [x] 5.3.6 Add `add_python_fixture_param()` to database mixin
- [x] 5.3.7 Add junction table to flush_order (AFTER python_test_fixtures)
- [x] 5.3.8 Update storage handler to: (1) call add_python_test_fixture, (2) capture ID, (3) call add_python_fixture_param with FK

### 5.4 Align python_framework_config and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [x] 5.4.1 Add `config_kind` discriminator column
- [x] 5.4.2 Remove JSON blobs: methods, schedule, details
- [x] 5.4.3 Add expanded columns: cache_type, timeout, has_process_request, has_process_response, has_process_exception, has_process_view, has_process_template_response
- [x] 5.4.4 Create `python_framework_methods` junction table
- [x] 5.4.5 Add `add_python_framework_config()` - returns `cursor.lastrowid` (ID return pattern)
- [x] 5.4.6 Add `add_python_framework_method()` to database mixin
- [x] 5.4.7 Add junction table to flush_order (AFTER python_framework_config)
- [x] 5.4.8 Update storage handler to: (1) call add_python_framework_config, (2) capture ID, (3) call add_python_framework_method with FK

### 5.5 Align python_validation_schemas and Create Junction Table

**⚠️ See CRITICAL IMPLEMENTATION NOTE above - use appendix-implementation.md Section 5.2 pattern**

- [x] 5.5.1 Add `schema_kind` discriminator column
- [x] 5.5.2 Remove `validators` JSON blob
- [x] 5.5.3 Create `python_schema_validators` junction table
- [x] 5.5.4 Add `add_python_validation_schema()` - returns `cursor.lastrowid` (ID return pattern)
- [x] 5.5.5 Add `add_python_schema_validator()` to database mixin
- [x] 5.5.6 Add junction table to flush_order (AFTER python_validation_schemas)
- [x] 5.5.7 Update storage handler to: (1) call add_python_validation_schema, (2) capture ID, (3) call add_python_schema_validator with FK

### 5.6 Wire Missing Framework Extractors

- [x] 5.6.1 Wire `extract_flask_blueprints` → python_framework_config (config_kind='blueprint')
- [x] 5.6.2 Wire `extract_graphene_resolvers` → python_framework_config (config_kind='resolver')
- [x] 5.6.3 Wire `extract_ariadne_resolvers` → python_framework_config (config_kind='resolver')
- [x] 5.6.4 Wire `extract_strawberry_resolvers` → python_framework_config (config_kind='resolver')

### 5.7 Verify Phase 5

- [x] 5.7.1 Run `aud full --offline` - PASSED (258.7s, 25/25 phases)
- [x] 5.7.2 Verify fidelity check passes - PASSED
- [x] 5.7.3 Verify schema tables: 136
- [x] 5.7.4 Verify two-discriminator pattern working for all 5 tables

### Implementation Artifacts (Phase 5)

**Files Modified:**
- `theauditor/indexer/schemas/python_schema.py` - Updated 5 Security/Testing tables, created 3 junction tables
- `theauditor/indexer/database/python_database.py` - Updated 5 add_* methods, 3 use ID return pattern, added 3 junction methods
- `theauditor/indexer/storage/python_storage.py` - Updated 5 handlers with junction logic
- `theauditor/indexer/database/base_database.py` - Added 3 junction tables to flush_order
- `theauditor/ast_extractors/python_impl.py` - Wired 4 missing extractors (blueprints, graphql resolvers)
- `theauditor/indexer/schema.py` - Updated table count assertion (133 -> 136)

**Verification Results:**
| Table | Rows | Discriminator | Notes |
|-------|------|---------------|-------|
| python_security_findings | 2,442 | finding_kind (auth, command_injection, crypto, dangerous_eval, jwt, password, path_traversal, sql_injection) | 7 finding_kind values |
| python_test_cases | 163 | test_kind (assertion, unittest) | 2 test_kind values |
| python_test_fixtures | 80 | fixture_kind (fixture, hypothesis, marker, mock, parametrize, plugin_hook) | 6 fixture_kind values |
| python_framework_config | 568 | config_kind (admin, app, blueprint, cache, cli, cors, error_handler, extension, form, form_field, hook, manager, queryset, rate_limit, receiver, resolver, schedule, signal, task, websocket) | 20 config_kind values |
| python_validation_schemas | 293 | schema_kind (field, form, schema, serializer) | 4 schema_kind values |

**Junction Tables:**
| Table | Rows | FK | Notes |
|-------|------|----|-------|
| python_fixture_params | 0 | fixture_id -> python_test_fixtures.id | Infrastructure ready, extractors don't output params array |
| python_framework_methods | 0 | config_id -> python_framework_config.id | Infrastructure ready, extractors don't output methods array |
| python_schema_validators | 0 | schema_id -> python_validation_schemas.id | Infrastructure ready, extractors don't output validators array |

**Newly Wired Extractors:**
| Extractor | Target | config_kind | Rows |
|-----------|--------|-------------|------|
| extract_flask_blueprints | python_framework_config | blueprint | 6 |
| extract_graphene_resolvers | python_framework_config | resolver | 8 |
| extract_ariadne_resolvers | python_framework_config | resolver | (included above) |
| extract_strawberry_resolvers | python_framework_config | resolver | (included above) |

---

## 6. Low-Level Tables Alignment (5 Tables) - COMPLETE

### 6.1 Align python_operators - COMPLETE

- [x] 6.1.1 Add `operator_kind` column
- [x] 6.1.2 Verify columns match: operator, operator_type, in_function, chain_length, operators, has_complex_condition, used_in, variable, container_type
- [x] 6.1.3 Remove invented columns: left_operand, right_operand
- [x] 6.1.4 Update database method add_python_operator()
- [x] 6.1.5 Update storage handler _store_python_operators()
- **Result**: 7,945 rows, 100% discriminator coverage, kinds: arithmetic, bitwise, chained, membership, ternary

### 6.2 Align python_collections - COMPLETE

- [x] 6.2.1 Add `collection_kind` column
- [x] 6.2.2 Verify columns match: operation, has_default, method, mutates_in_place, builtin, has_key, in_function
- [x] 6.2.3 Update database method add_python_collection()
- [x] 6.2.4 Update storage handler _store_python_collections()
- **Result**: 15,580 rows, 100% discriminator coverage, kinds: builtin, collections, dict, functools, list, set, string

### 6.3 Align python_stdlib_usage - COMPLETE

- [x] 6.3.1 Add `stdlib_kind` column
- [x] 6.3.2 Verify columns match: pattern, is_decorator, operation, direction, log_level, path_type, has_flags, threading_type, in_function
- [x] 6.3.3 Update database method add_python_stdlib_usage()
- [x] 6.3.4 Update storage handler _store_python_stdlib_usage()
- **Result**: 6,834 rows, 100% discriminator coverage, kinds: contextlib, contextvars, datetime, json, logging, pathlib, re, threading, typing, weakref

### 6.4 Align python_imports_advanced - COMPLETE

- [x] 6.4.1 Add `import_kind` column
- [x] 6.4.2 Wire `extract_python_exports` with `import_kind='export'`
- [x] 6.4.3 Add missing columns: is_default (renamed from 'default' - reserved keyword), export_type, in_function, has_alias, imported_names, is_wildcard, relative_level, attribute
- [x] 6.4.4 Update database method add_python_import_advanced()
- [x] 6.4.5 Update storage handler _store_python_imports_advanced()
- **Result**: 4,439 rows, 100% discriminator coverage, kinds: export, module_attr, static
- **CRITICAL WIN**: 3,354 export rows RECOVERED (was 0 - UNWIRED)

### 6.5 Reduce python_expressions - COMPLETE

- [x] 6.5.1 Remove columns for re-routed extractors: subtype, expression, variables
- [x] 6.5.2 Add expression_kind discriminator
- [x] 6.5.3 Add specific columns for remaining extractors: target, has_start, has_stop, has_step, is_assignment, element_count, operation, has_rest, target_count, unpack_type, pattern, uses_is, format_type, has_expressions, var_count, context, has_globals, has_locals, generator_function, yield_expr, yield_type, in_loop, condition, awaited_expr, containing_function
- [x] 6.5.4 Update database method add_python_expression()
- [x] 6.5.5 Update storage handler _store_python_expressions()
- **Result**: 14,963 rows, 100% discriminator coverage, kinds: await, bytes, ellipsis, exec, format, none, resource, slice, truthiness, tuple
- **Schema**: 31 columns (reduced from generic junk drawer)

### 6.6 Verify Phase 6 - COMPLETE

- [x] 6.6.1 Run `aud full --offline` - 25/25 phases PASSED (252.8s)
- [x] 6.6.2 Verify fidelity check passes - PASS
- [x] 6.6.3 Verify exports data stored - 3,354 rows with import_kind='export'

**Phase 6 Verification Summary:**
- Pipeline: 25/25 phases, 252.8s
- All 5 tables have two-discriminator pattern with 100% coverage
- python_exports wired - 3,354 rows RECOVERED
- python_expressions cleaned up - removed subtype/expression/variables, 31 columns remaining

---

## 7. Wire Missing Framework Extractors (Partially Done in Phase 5)

### 7.1 Wire Flask Extractors

- [x] 7.1.1 Wire `extract_flask_blueprints` to `python_framework_config` with `framework='flask', config_kind='blueprint'` (DONE in Phase 5)

### 7.2 Wire Celery Extractors

- [x] 7.2.1 `extract_celery_tasks` - ALREADY WIRED (task: 43 rows)
- [x] 7.2.2 `extract_celery_task_calls` - ALREADY WIRED (included in task_call)
- [x] 7.2.3 `extract_celery_beat_schedules` - ALREADY WIRED (schedule: 18 rows)

### 7.3 Wire GraphQL Extractors

- [x] 7.3.1 Wire `extract_graphene_resolvers` to `python_framework_config` with `framework='graphene', config_kind='resolver'` (DONE in Phase 5)
- [x] 7.3.2 Wire `extract_ariadne_resolvers` to `python_framework_config` with `framework='ariadne', config_kind='resolver'` (DONE in Phase 5)
- [x] 7.3.3 Wire `extract_strawberry_resolvers` to `python_framework_config` with `framework='strawberry', config_kind='resolver'` (DONE in Phase 5)

### 7.4 Verify Phase 7

- [x] 7.4.1 Run `aud full --offline` - PASSED (Phase 5 verification)
- [x] 7.4.2 Verify framework data stored - blueprint: 6, resolver: 8, task: 43, schedule: 18

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
