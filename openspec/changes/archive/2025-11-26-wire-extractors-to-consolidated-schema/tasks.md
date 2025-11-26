# Tasks: Wire Extractors to Consolidated Schema

## Pre-Flight Checklist

**STOP. Before ANY code changes, verify these:**

- [ ] Read `design.md` completely (all 20 table definitions)
- [ ] Read `proposal.md` completely (consolidation strategy)
- [ ] Verify current state matches expected baseline

**Baseline Verification:**
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
print(f'TABLES: {len(TABLES)} (expect 109)')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 8)')
"
```

---

## VERIFICATION FINDINGS (2025-11-25)

**Auditor:** Opus Lead Coder
**Status:** PHASE 1 COMPLETE

### Initial State Verified (Pre-Implementation):
- TABLES: 109 - MATCH
- PYTHON_TABLES: 8 - MATCH
- python_storage.py handlers: 7 - MATCH (python_package_configs via generic_batches)
- python_database.py: 149 methods (141 zombie) - CRITICAL FINDING

### Post-Phase 1 State (2025-11-25):
- TABLES: 129 - VERIFIED
- PYTHON_TABLES: 28 - VERIFIED
- schema.py assertion: Updated 109 → 129
- python_database.py: 28 methods (8 original + 20 new) - CLEANED
- base_database.py flush_order: Updated with 28 Python tables

### Critical Finding: Zombie Database Mixin Methods - RESOLVED

**File:** `theauditor/indexer/database/python_database.py`

The file contained **149 `add_python_*` methods** (1,816 lines) writing to tables that no longer exist.

**Resolution:**
- Purged 141 zombie methods (1,655 lines deleted)
- Removed dead `add_python_blueprint` method (table doesn't exist in schema)
- Added 20 new consolidated methods
- Final state: 28 methods for 28 tables

### Completed Task Sequence:

1. **Phase 1.1-1.4:** Add 20 tables to python_schema.py - DONE
2. **Phase 1.5a (PURGE):** Delete 141 zombie methods - DONE (1,655 lines deleted)
3. **Phase 1.5b:** Add 20 new `add_python_*` methods - DONE
4. **Phase 1.6:** Update `flush_order` in base_database.py - DONE
5. **Phase 1.7:** Update schema.py assertion (109 → 129) - DONE
6. **Phase 1.8:** Verify schema changes - DONE (129 tables, 28 Python)
7. **Phase 2:** Add 20 handlers to python_storage.py - DONE (27 handlers total)
8. **Phase 3:** Rewire python_impl.py - PENDING
9. **Phase 4:** Regenerate codegen - PENDING
10. **Phase 5:** Full verification - PENDING

---

## Phase 1: Schema - Add 20 Consolidated Tables

**File:** `theauditor/indexer/schemas/python_schema.py`

### Task 1.1: Add Group 1 - Control & Data Flow (5 tables) - DONE

- [x] Add `PYTHON_LOOPS` TableSchema
- [x] Add `PYTHON_BRANCHES` TableSchema
- [x] Add `PYTHON_FUNCTIONS_ADVANCED` TableSchema
- [x] Add `PYTHON_IO_OPERATIONS` TableSchema
- [x] Add `PYTHON_STATE_MUTATIONS` TableSchema
- [x] Add all 5 to `PYTHON_TABLES` dict

### Task 1.2: Add Group 2 - Object-Oriented & Types (5 tables) - DONE

- [x] Add `PYTHON_CLASS_FEATURES` TableSchema
- [x] Add `PYTHON_PROTOCOLS` TableSchema
- [x] Add `PYTHON_DESCRIPTORS` TableSchema
- [x] Add `PYTHON_TYPE_DEFINITIONS` TableSchema
- [x] Add `PYTHON_LITERALS` TableSchema
- [x] Add all 5 to `PYTHON_TABLES` dict

### Task 1.3: Add Group 3 - Security & Testing (5 tables) - DONE

- [x] Add `PYTHON_SECURITY_FINDINGS` TableSchema
- [x] Add `PYTHON_TEST_CASES` TableSchema
- [x] Add `PYTHON_TEST_FIXTURES` TableSchema
- [x] Add `PYTHON_FRAMEWORK_CONFIG` TableSchema
- [x] Add `PYTHON_VALIDATION_SCHEMAS` TableSchema
- [x] Add all 5 to `PYTHON_TABLES` dict

### Task 1.4: Add Group 4 - Low-Level & Misc (5 tables) - DONE

- [x] Add `PYTHON_OPERATORS` TableSchema
- [x] Add `PYTHON_COLLECTIONS` TableSchema
- [x] Add `PYTHON_STDLIB_USAGE` TableSchema
- [x] Add `PYTHON_IMPORTS_ADVANCED` TableSchema
- [x] Add `PYTHON_EXPRESSIONS` TableSchema
- [x] Add all 5 to `PYTHON_TABLES` dict

### Task 1.5a: PURGE Zombie Database Methods (PREREQUISITE) - DONE

**File:** `theauditor/indexer/database/python_database.py`

**CRITICAL:** Clean first, build second. Delete ~100 zombie methods BEFORE adding new ones.

**Methods KEPT (8 for kept tables):**
- `add_python_orm_model` → `python_orm_models`
- `add_python_orm_field` → `python_orm_fields`
- `add_python_route` → `python_routes`
- `add_python_validator` → `python_validators`
- `add_python_package_config` → `python_package_configs`
- `add_python_decorator` → `python_decorators`
- `add_python_django_view` → `python_django_views`
- `add_python_django_middleware` → `python_django_middleware`

**Note:** `add_python_blueprint` was initially kept but later removed (table doesn't exist in PYTHON_TABLES).

**PURGE RESULTS (2025-11-25):**
```
Old file size: 1,816 lines
New file size: 161 lines (after initial purge)
Final file size: 553 lines (after adding 20 new methods)
Lines deleted: 1,655 lines
Zombie methods deleted: 141
Original methods remaining: 8
```

**Final Verification (post-Phase 1.5b):**
```
Tables in PYTHON_TABLES: 28
Methods in PythonDatabaseMixin: 28
(8 original + 20 new consolidated)
```

- [x] Deleted 141 zombie methods
- [x] Verified 8 original methods remain
- [x] Added 20 new consolidated methods
- [x] All 28 methods import and parse correctly

### Task 1.5b: Add 20 New Database Mixin Methods - DONE

**File:** `theauditor/indexer/database/python_database.py`

All 20 methods added with correct column order matching schema.

**Additional fix:** Removed dead `add_python_blueprint` method (table doesn't exist in schema).

**Verification output:**
```
Tables in PYTHON_TABLES: 28
Methods in PythonDatabaseMixin: 28
```

- [x] `add_python_loop` → `python_loops`
- [x] `add_python_branch` → `python_branches`
- [x] `add_python_function_advanced` → `python_functions_advanced`
- [x] `add_python_io_operation` → `python_io_operations`
- [x] `add_python_state_mutation` → `python_state_mutations`
- [x] `add_python_class_feature` → `python_class_features`
- [x] `add_python_protocol` → `python_protocols`
- [x] `add_python_descriptor` → `python_descriptors`
- [x] `add_python_type_definition` → `python_type_definitions`
- [x] `add_python_literal` → `python_literals`
- [x] `add_python_security_finding` → `python_security_findings`
- [x] `add_python_test_case` → `python_test_cases`
- [x] `add_python_test_fixture` → `python_test_fixtures`
- [x] `add_python_framework_config` → `python_framework_config`
- [x] `add_python_validation_schema` → `python_validation_schemas`
- [x] `add_python_operator` → `python_operators`
- [x] `add_python_collection` → `python_collections`
- [x] `add_python_stdlib_usage` → `python_stdlib_usage`
- [x] `add_python_import_advanced` → `python_imports_advanced`
- [x] `add_python_expression` → `python_expressions`

### Task 1.6: Update Flush Order - DONE

**File:** `theauditor/indexer/database/base_database.py`

Updated flush_order (lines 328-362):
- Replaced old orphan Python tables with 8 correct original tables
- Added all 20 new consolidated tables in groups
- Removed `python_blueprints` (table doesn't exist)
- Added `python_package_configs` (was missing)

- [x] All 8 original tables in flush_order
- [x] All 20 new consolidated tables in flush_order
- [x] Removed orphan table references

### Task 1.7: Update schema.py Assertion - DONE

**File:** `theauditor/indexer/schema.py`

```python
# Changed from:
assert len(TABLES) == 109
# To:
assert len(TABLES) == 129  # 109 + 20 new consolidated tables
```

- [x] Assertion updated
- [x] Docstring updated (python_schema.py: 8 → 28 tables)
- [x] PYTHON_TABLES comment updated
- [x] Re-exports added for 20 new tables

### Task 1.8: Verify Schema Changes - DONE

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
print(f'TABLES: {len(TABLES)} (expect 129)')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 28)')
for name in sorted(PYTHON_TABLES.keys()):
    print(f'  - {name}')
"
```

**Output (2025-11-25):**
```
[SCHEMA] Loaded 129 tables
TABLES: 129 (expected 129)
PYTHON_TABLES: 28 (expected 28)
```

- [x] TABLES == 129
- [x] PYTHON_TABLES == 28

---

## Phase 2: Storage - Add 20 Consolidated Handlers - DONE

**File:** `theauditor/indexer/storage/python_storage.py`

### Task 2.1: Add Group 1 Handlers - DONE

- [x] Add `_store_python_loops` handler
- [x] Add `_store_python_branches` handler
- [x] Add `_store_python_functions_advanced` handler
- [x] Add `_store_python_io_operations` handler
- [x] Add `_store_python_state_mutations` handler
- [x] Register all 5 in `self.handlers` dict

### Task 2.2: Add Group 2 Handlers - DONE

- [x] Add `_store_python_class_features` handler
- [x] Add `_store_python_protocols` handler
- [x] Add `_store_python_descriptors` handler
- [x] Add `_store_python_type_definitions` handler
- [x] Add `_store_python_literals` handler
- [x] Register all 5 in `self.handlers` dict

### Task 2.3: Add Group 3 Handlers - DONE

- [x] Add `_store_python_security_findings` handler
- [x] Add `_store_python_test_cases` handler
- [x] Add `_store_python_test_fixtures` handler
- [x] Add `_store_python_framework_config` handler
- [x] Add `_store_python_validation_schemas` handler
- [x] Register all 5 in `self.handlers` dict

### Task 2.4: Add Group 4 Handlers - DONE

- [x] Add `_store_python_operators` handler
- [x] Add `_store_python_collections` handler
- [x] Add `_store_python_stdlib_usage` handler
- [x] Add `_store_python_imports_advanced` handler
- [x] Add `_store_python_expressions` handler
- [x] Register all 5 in `self.handlers` dict

### Task 2.5: Verify Storage Handlers - DONE

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.storage.python_storage import PythonStorage
class FakeDB:
    def get_cursor(self): return None
ps = PythonStorage(FakeDB(), {})
print(f'Python handlers: {len(ps.handlers)} (expect 27)')
# 7 original + 20 new = 27
"
```

**Output (2025-11-25):**
```
[SCHEMA] Loaded 129 tables
Python handlers: 27 (expect 27)
```

- [x] Handlers == 27

---

## Phase 3: python_impl.py - Wire Extractors to Consolidated Tables

**File:** `theauditor/ast_extractors/python_impl.py`

### Task 3.1: Update Result Dictionary

Replace ~150 granular keys with 28 consolidated keys:

```python
result = {
    # Core (unchanged)
    'imports': [],
    'symbols': [],
    'assignments': [],
    'function_calls': [],
    'returns': [],
    'variable_usage': [],
    'cfg': [],
    'object_literals': [],
    'type_annotations': [],
    'resolved_imports': {},
    'orm_relationships': [],
    'cdk_constructs': [],
    'cdk_construct_properties': [],
    'sql_queries': [],
    'routes': [],  # Legacy

    # KEPT Python tables (8)
    'python_decorators': [],
    'python_django_middleware': [],
    'python_django_views': [],
    'python_orm_fields': [],
    'python_orm_models': [],
    'python_package_configs': [],
    'python_routes': [],
    'python_validators': [],

    # NEW consolidated tables (20)
    'python_loops': [],
    'python_branches': [],
    'python_functions_advanced': [],
    'python_io_operations': [],
    'python_state_mutations': [],
    'python_class_features': [],
    'python_protocols': [],
    'python_descriptors': [],
    'python_type_definitions': [],
    'python_literals': [],
    'python_security_findings': [],
    'python_test_cases': [],
    'python_test_fixtures': [],
    'python_framework_config': [],
    'python_validation_schemas': [],
    'python_operators': [],
    'python_collections': [],
    'python_stdlib_usage': [],
    'python_imports_advanced': [],
    'python_expressions': [],
}
```

- [ ] Result dict updated with 28 Python keys

### Task 3.2: Wire control_flow_extractors.py

**Source:** `theauditor/ast_extractors/python/control_flow_extractors.py`

| Extractor Function | Line | → Table | Discriminator |
|-------------------|------|---------|---------------|
| `extract_for_loops` | 93 | python_loops | `loop_type='for_loop'` |
| `extract_while_loops` | 167 | python_loops | `loop_type='while_loop'` |
| `extract_async_for_loops` | 219 | python_loops | `loop_type='async_for_loop'` |
| `extract_if_statements` | 263 | python_branches | `branch_type='if'` |
| `extract_match_statements` | 343 | python_branches | `branch_type='match'` |
| `extract_break_continue_pass` | 416 | python_expressions | `expression_type='break'/'continue'/'pass'` |
| `extract_assert_statements` | 477 | python_expressions | `expression_type='assert'` |
| `extract_del_statements` | 530 | python_expressions | `expression_type='del'` |
| `extract_import_statements` | 580 | python_imports_advanced | `import_type='static'` |
| `extract_with_statements` | 631 | python_expressions | `expression_type='with'` |

- [ ] for_loops → python_loops
- [ ] while_loops → python_loops
- [ ] async_for_loops → python_loops
- [ ] if_statements → python_branches
- [ ] match_statements → python_branches
- [ ] break_continue_pass → python_expressions
- [ ] assert_statements → python_expressions
- [ ] del_statements → python_expressions
- [ ] import_statements → python_imports_advanced
- [ ] with_statements → python_expressions

### Task 3.3: Wire security_extractors.py

**Source:** `theauditor/ast_extractors/python/security_extractors.py`

| Extractor Function | Line | → Table | Discriminator |
|-------------------|------|---------|---------------|
| `extract_auth_decorators` | 75 | python_security_findings | `finding_type='auth'` |
| `extract_password_hashing` | 128 | python_security_findings | `finding_type='password'` |
| `extract_sql_injection_patterns` | 191 | python_security_findings | `finding_type='sql_injection'` |
| `extract_command_injection_patterns` | 255 | python_security_findings | `finding_type='command_injection'` |
| `extract_path_traversal_patterns` | 309 | python_security_findings | `finding_type='path_traversal'` |
| `extract_dangerous_eval_exec` | 361 | python_security_findings | `finding_type='dangerous_eval'` |
| `extract_crypto_operations` | 410 | python_security_findings | `finding_type='crypto'` |
| `extract_jwt_operations` | 561 | python_security_findings | `finding_type='jwt'` |

- [ ] auth_decorators → python_security_findings
- [ ] password_hashing → python_security_findings
- [ ] sql_injection_patterns → python_security_findings
- [ ] command_injection_patterns → python_security_findings
- [ ] path_traversal_patterns → python_security_findings
- [ ] dangerous_eval_exec → python_security_findings
- [ ] crypto_operations → python_security_findings
- [ ] jwt_operations → python_security_findings

### Task 3.4: Wire testing_extractors.py

**Source:** `theauditor/ast_extractors/python/testing_extractors.py`

| Extractor Function | Line | → Table | Discriminator |
|-------------------|------|---------|---------------|
| `extract_pytest_fixtures` | 30 | python_test_fixtures | `fixture_type='fixture'` |
| `extract_pytest_parametrize` | 75 | python_test_fixtures | `fixture_type='parametrize'` |
| `extract_pytest_markers` | 113 | python_test_fixtures | `fixture_type='marker'` |
| `extract_mock_patterns` | 145 | python_test_fixtures | `fixture_type='mock'` |
| `extract_unittest_test_cases` | 196 | python_test_cases | `test_type='unittest'` |
| `extract_assertion_patterns` | 256 | python_test_cases | `test_type='assertion'` |
| `extract_pytest_plugin_hooks` | 310 | python_test_fixtures | `fixture_type='plugin_hook'` |
| `extract_hypothesis_strategies` | 357 | python_test_fixtures | `fixture_type='hypothesis'` |

- [ ] pytest_fixtures → python_test_fixtures
- [ ] pytest_parametrize → python_test_fixtures
- [ ] pytest_markers → python_test_fixtures
- [ ] mock_patterns → python_test_fixtures
- [ ] unittest_test_cases → python_test_cases
- [ ] assertion_patterns → python_test_cases
- [ ] pytest_plugin_hooks → python_test_fixtures
- [ ] hypothesis_strategies → python_test_fixtures

### Task 3.5: Wire async_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_async_functions` | python_functions_advanced | `function_type='async'` |
| `extract_await_expressions` | python_expressions | `expression_type='await'` |
| `extract_async_generators` | python_functions_advanced | `function_type='async_generator'` |

- [ ] async_functions → python_functions_advanced
- [ ] await_expressions → python_expressions
- [ ] async_generators → python_functions_advanced

### Task 3.6: Wire state_mutation_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_instance_mutations` | python_state_mutations | `mutation_type='instance'` |
| `extract_class_mutations` | python_state_mutations | `mutation_type='class'` |
| `extract_global_mutations` | python_state_mutations | `mutation_type='global'` |
| `extract_argument_mutations` | python_state_mutations | `mutation_type='argument'` |
| `extract_augmented_assignments` | python_state_mutations | `mutation_type='augmented'` |

- [ ] instance_mutations → python_state_mutations
- [ ] class_mutations → python_state_mutations
- [ ] global_mutations → python_state_mutations
- [ ] argument_mutations → python_state_mutations
- [ ] augmented_assignments → python_state_mutations

### Task 3.7: Wire exception_flow_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_exception_raises` | python_branches | `branch_type='raise'` |
| `extract_exception_catches` | python_branches | `branch_type='except'` |
| `extract_finally_blocks` | python_branches | `branch_type='finally'` |
| `extract_context_managers_enhanced` | python_protocols | `protocol_type='context_manager'` |

- [ ] exception_raises → python_branches
- [ ] exception_catches → python_branches
- [ ] finally_blocks → python_branches
- [ ] context_managers_enhanced → python_protocols

### Task 3.8: Wire data_flow_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_io_operations` | python_io_operations | `io_type='file'/'network'/'database'/'process'` |
| `extract_parameter_return_flow` | python_io_operations | `io_type='param_flow'` |
| `extract_closure_captures` | python_io_operations | `io_type='closure'` |
| `extract_nonlocal_access` | python_io_operations | `io_type='nonlocal'` |
| `extract_conditional_calls` | python_io_operations | `io_type='conditional'` |

- [ ] io_operations → python_io_operations
- [ ] parameter_return_flow → python_io_operations
- [ ] closure_captures → python_io_operations
- [ ] nonlocal_access → python_io_operations
- [ ] conditional_calls → python_io_operations

### Task 3.9: Wire behavioral_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_recursion_patterns` | python_expressions | `expression_type='recursion'` |
| `extract_generator_yields` | python_expressions | `expression_type='yield'` |
| `extract_property_patterns` | python_descriptors | `descriptor_type='property'` |
| `extract_dynamic_attributes` | python_descriptors | `descriptor_type='dynamic_attr'` |

- [ ] recursion_patterns → python_expressions
- [ ] generator_yields → python_expressions
- [ ] property_patterns → python_descriptors
- [ ] dynamic_attributes → python_descriptors

### Task 3.10: Wire performance_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_loop_complexity` | python_expressions | `expression_type='complexity'` |
| `extract_resource_usage` | python_expressions | `expression_type='resource'` |
| `extract_memoization_patterns` | python_expressions | `expression_type='memoize'` |

- [ ] loop_complexity → python_expressions
- [ ] resource_usage → python_expressions
- [ ] memoization_patterns → python_expressions

### Task 3.11: Wire fundamental_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_comprehensions` | python_expressions | `expression_type='comprehension'` |
| `extract_lambda_functions` | python_functions_advanced | `function_type='lambda'` |
| `extract_slice_operations` | python_expressions | `expression_type='slice'` |
| `extract_tuple_operations` | python_expressions | `expression_type='tuple'` |
| `extract_unpacking_patterns` | python_expressions | `expression_type='unpack'` |
| `extract_none_patterns` | python_expressions | `expression_type='none'` |
| `extract_truthiness_patterns` | python_expressions | `expression_type='truthiness'` |
| `extract_string_formatting` | python_expressions | `expression_type='format'` |

- [ ] comprehensions → python_expressions
- [ ] lambda_functions → python_functions_advanced
- [ ] slice_operations → python_expressions
- [ ] tuple_operations → python_expressions
- [ ] unpacking_patterns → python_expressions
- [ ] none_patterns → python_expressions
- [ ] truthiness_patterns → python_expressions
- [ ] string_formatting → python_expressions

### Task 3.12: Wire operator_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_operators` | python_operators | `operator_type='binary'/'unary'` |
| `extract_membership_tests` | python_operators | `operator_type='membership'` |
| `extract_chained_comparisons` | python_operators | `operator_type='chained'` |
| `extract_ternary_expressions` | python_operators | `operator_type='ternary'` |
| `extract_walrus_operators` | python_operators | `operator_type='walrus'` |
| `extract_matrix_multiplication` | python_operators | `operator_type='matmul'` |

- [ ] operators → python_operators
- [ ] membership_tests → python_operators
- [ ] chained_comparisons → python_operators
- [ ] ternary_expressions → python_operators
- [ ] walrus_operators → python_operators
- [ ] matrix_multiplication → python_operators

### Task 3.13: Wire collection_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_dict_operations` | python_collections | `collection_type='dict'` |
| `extract_list_mutations` | python_collections | `collection_type='list'` |
| `extract_set_operations` | python_collections | `collection_type='set'` |
| `extract_string_methods` | python_collections | `collection_type='string'` |
| `extract_builtin_usage` | python_collections | `collection_type='builtin'` |
| `extract_itertools_usage` | python_collections | `collection_type='itertools'` |
| `extract_functools_usage` | python_collections | `collection_type='functools'` |
| `extract_collections_usage` | python_collections | `collection_type='collections'` |

- [ ] dict_operations → python_collections
- [ ] list_mutations → python_collections
- [ ] set_operations → python_collections
- [ ] string_methods → python_collections
- [ ] builtin_usage → python_collections
- [ ] itertools_usage → python_collections
- [ ] functools_usage → python_collections
- [ ] collections_usage → python_collections

### Task 3.14: Wire class_feature_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_metaclasses` | python_class_features | `feature_type='metaclass'` |
| `extract_descriptors` | python_descriptors | `descriptor_type='descriptor'` |
| `extract_dataclasses` | python_class_features | `feature_type='dataclass'` |
| `extract_enums` | python_class_features | `feature_type='enum'` |
| `extract_slots` | python_class_features | `feature_type='slots'` |
| `extract_abstract_classes` | python_class_features | `feature_type='abstract'` |
| `extract_method_types` | python_class_features | `feature_type='method_type'` |
| `extract_multiple_inheritance` | python_class_features | `feature_type='inheritance'` |
| `extract_dunder_methods` | python_class_features | `feature_type='dunder'` |
| `extract_visibility_conventions` | python_class_features | `feature_type='visibility'` |

- [ ] metaclasses → python_class_features
- [ ] descriptors → python_descriptors
- [ ] dataclasses → python_class_features
- [ ] enums → python_class_features
- [ ] slots → python_class_features
- [ ] abstract_classes → python_class_features
- [ ] method_types → python_class_features
- [ ] multiple_inheritance → python_class_features
- [ ] dunder_methods → python_class_features
- [ ] visibility_conventions → python_class_features

### Task 3.15: Wire type_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_protocols` | python_type_definitions | `type_kind='protocol'` |
| `extract_generics` | python_type_definitions | `type_kind='generic'` |
| `extract_typed_dicts` | python_type_definitions | `type_kind='typed_dict'` |
| `extract_literals` | python_literals | `literal_type='literal'` |
| `extract_overloads` | python_literals | `literal_type='overload'` |

- [ ] protocols → python_type_definitions
- [ ] generics → python_type_definitions
- [ ] typed_dicts → python_type_definitions
- [ ] literals → python_literals
- [ ] overloads → python_literals

### Task 3.16: Wire protocol_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_iterator_protocol` | python_protocols | `protocol_type='iterator'` |
| `extract_container_protocol` | python_protocols | `protocol_type='container'` |
| `extract_callable_protocol` | python_protocols | `protocol_type='callable'` |
| `extract_comparison_protocol` | python_protocols | `protocol_type='comparison'` |
| `extract_arithmetic_protocol` | python_protocols | `protocol_type='arithmetic'` |
| `extract_pickle_protocol` | python_protocols | `protocol_type='pickle'` |
| `extract_weakref_usage` | python_stdlib_usage | `module='weakref'` |
| `extract_contextvar_usage` | python_stdlib_usage | `module='contextvars'` |
| `extract_module_attributes` | python_imports_advanced | `import_type='module_attr'` |
| `extract_class_decorators` | python_expressions | `expression_type='class_decorator'` |

- [ ] iterator_protocol → python_protocols
- [ ] container_protocol → python_protocols
- [ ] callable_protocol → python_protocols
- [ ] comparison_protocol → python_protocols
- [ ] arithmetic_protocol → python_protocols
- [ ] pickle_protocol → python_protocols
- [ ] weakref_usage → python_stdlib_usage
- [ ] contextvar_usage → python_stdlib_usage
- [ ] module_attributes → python_imports_advanced
- [ ] class_decorators → python_expressions

### Task 3.17: Wire stdlib_pattern_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_regex_patterns` | python_stdlib_usage | `module='re'` |
| `extract_json_operations` | python_stdlib_usage | `module='json'` |
| `extract_datetime_operations` | python_stdlib_usage | `module='datetime'` |
| `extract_path_operations` | python_stdlib_usage | `module='pathlib'` |
| `extract_logging_patterns` | python_stdlib_usage | `module='logging'` |
| `extract_threading_patterns` | python_stdlib_usage | `module='threading'` |
| `extract_contextlib_patterns` | python_stdlib_usage | `module='contextlib'` |
| `extract_type_checking` | python_stdlib_usage | `module='typing'` |

- [ ] regex_patterns → python_stdlib_usage
- [ ] json_operations → python_stdlib_usage
- [ ] datetime_operations → python_stdlib_usage
- [ ] path_operations → python_stdlib_usage
- [ ] logging_patterns → python_stdlib_usage
- [ ] threading_patterns → python_stdlib_usage
- [ ] contextlib_patterns → python_stdlib_usage
- [ ] type_checking → python_stdlib_usage

### Task 3.18: Wire advanced_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_namespace_packages` | python_imports_advanced | `import_type='namespace'` |
| `extract_cached_property` | python_descriptors | `descriptor_type='cached_property'` |
| `extract_descriptor_protocol` | python_descriptors | `descriptor_type='descriptor'` |
| `extract_attribute_access_protocol` | python_descriptors | `descriptor_type='attr_access'` |
| `extract_copy_protocol` | python_expressions | `expression_type='copy'` |
| `extract_ellipsis_usage` | python_expressions | `expression_type='ellipsis'` |
| `extract_bytes_operations` | python_expressions | `expression_type='bytes'` |
| `extract_exec_eval_compile` | python_expressions | `expression_type='exec'` |

- [ ] namespace_packages → python_imports_advanced
- [ ] cached_property → python_descriptors
- [ ] descriptor_protocol → python_descriptors
- [ ] attribute_access_protocol → python_descriptors
- [ ] copy_protocol → python_expressions
- [ ] ellipsis_usage → python_expressions
- [ ] bytes_operations → python_expressions
- [ ] exec_eval_compile → python_expressions

### Task 3.19: Wire flask_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_flask_app_factories` | python_framework_config | `framework='flask', config_type='app'` |
| `extract_flask_extensions` | python_framework_config | `framework='flask', config_type='extension'` |
| `extract_flask_request_hooks` | python_framework_config | `framework='flask', config_type='hook'` |
| `extract_flask_error_handlers` | python_framework_config | `framework='flask', config_type='error_handler'` |
| `extract_flask_websocket_handlers` | python_framework_config | `framework='flask', config_type='websocket'` |
| `extract_flask_cli_commands` | python_framework_config | `framework='flask', config_type='cli'` |
| `extract_flask_cors_configs` | python_framework_config | `framework='flask', config_type='cors'` |
| `extract_flask_rate_limits` | python_framework_config | `framework='flask', config_type='rate_limit'` |
| `extract_flask_cache_decorators` | python_framework_config | `framework='flask', config_type='cache'` |

- [ ] flask_app_factories → python_framework_config
- [ ] flask_extensions → python_framework_config
- [ ] flask_request_hooks → python_framework_config
- [ ] flask_error_handlers → python_framework_config
- [ ] flask_websocket_handlers → python_framework_config
- [ ] flask_cli_commands → python_framework_config
- [ ] flask_cors_configs → python_framework_config
- [ ] flask_rate_limits → python_framework_config
- [ ] flask_cache_decorators → python_framework_config

### Task 3.20: Wire framework_extractors.py (Celery)

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_celery_tasks` | python_framework_config | `framework='celery', config_type='task'` |
| `extract_celery_task_calls` | python_framework_config | `framework='celery', config_type='task_call'` |
| `extract_celery_beat_schedules` | python_framework_config | `framework='celery', config_type='schedule'` |

- [ ] celery_tasks → python_framework_config
- [ ] celery_task_calls → python_framework_config
- [ ] celery_beat_schedules → python_framework_config

### Task 3.21: Wire django_web_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_django_forms` | python_framework_config | `framework='django', config_type='form'` |
| `extract_django_form_fields` | python_framework_config | `framework='django', config_type='form_field'` |
| `extract_django_admin` | python_framework_config | `framework='django', config_type='admin'` |

- [ ] django_forms → python_framework_config
- [ ] django_form_fields → python_framework_config
- [ ] django_admin → python_framework_config

### Task 3.22: Wire django_advanced_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_django_signals` | python_framework_config | `framework='django', config_type='signal'` |
| `extract_django_receivers` | python_framework_config | `framework='django', config_type='receiver'` |
| `extract_django_managers` | python_framework_config | `framework='django', config_type='manager'` |
| `extract_django_querysets` | python_framework_config | `framework='django', config_type='queryset'` |

- [ ] django_signals → python_framework_config
- [ ] django_receivers → python_framework_config
- [ ] django_managers → python_framework_config
- [ ] django_querysets → python_framework_config

### Task 3.23: Wire validation_extractors.py

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_marshmallow_schemas` | python_validation_schemas | `framework='marshmallow', schema_type='schema'` |
| `extract_marshmallow_fields` | python_validation_schemas | `framework='marshmallow', schema_type='field'` |
| `extract_drf_serializers` | python_validation_schemas | `framework='drf', schema_type='serializer'` |
| `extract_drf_serializer_fields` | python_validation_schemas | `framework='drf', schema_type='field'` |
| `extract_wtforms_forms` | python_validation_schemas | `framework='wtforms', schema_type='form'` |
| `extract_wtforms_fields` | python_validation_schemas | `framework='wtforms', schema_type='field'` |

- [ ] marshmallow_schemas → python_validation_schemas
- [ ] marshmallow_fields → python_validation_schemas
- [ ] drf_serializers → python_validation_schemas
- [ ] drf_serializer_fields → python_validation_schemas
- [ ] wtforms_forms → python_validation_schemas
- [ ] wtforms_fields → python_validation_schemas

### Task 3.24: Wire core_extractors.py (generators, context_managers)

| Extractor Function | → Table | Discriminator |
|-------------------|---------|---------------|
| `extract_generators` | python_functions_advanced | `function_type='generator'` |
| `extract_context_managers` | python_functions_advanced | `function_type='context_manager'` |

- [ ] generators → python_functions_advanced
- [ ] context_managers → python_functions_advanced

### Task 3.25: Verify python_impl.py Compiles

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.ast_extractors import python_impl
print('python_impl.py import successful')
"
```

- [ ] No import errors

---

## Phase 4: Regenerate Generated Code

### Task 4.1: Run Codegen

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m theauditor.indexer.schemas.codegen
```

- [ ] Codegen completed without errors

### Task 4.2: Verify Generated Code

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schemas.generated_types import *
from theauditor.indexer.schemas.generated_accessors import *
print('Generated code import successful')
"
```

- [ ] No import errors

---

## Phase 5: Full Verification

### Task 5.1: Run Full Pipeline on TheAuditor

```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
```

- [ ] Pipeline completes without errors
- [ ] All phases successful

### Task 5.2: Verify Consolidated Tables Have Data

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

tables = [
    'python_loops', 'python_branches', 'python_functions_advanced',
    'python_io_operations', 'python_state_mutations',
    'python_class_features', 'python_protocols', 'python_descriptors',
    'python_type_definitions', 'python_literals',
    'python_security_findings', 'python_test_cases', 'python_test_fixtures',
    'python_framework_config', 'python_validation_schemas',
    'python_operators', 'python_collections', 'python_stdlib_usage',
    'python_imports_advanced', 'python_expressions',
]

print('=== CONSOLIDATED TABLE ROW COUNTS ===')
total = 0
for t in tables:
    c.execute(f'SELECT COUNT(*) FROM {t}')
    count = c.fetchone()[0]
    total += count
    print(f'{t}: {count} rows')

print(f'\\nTOTAL: {total} rows')
conn.close()
"
```

- [ ] All 20 consolidated tables exist
- [ ] Total rows > 50,000

### Task 5.3: Verify Existing Consumers Still Work

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.graph.strategies.interceptors import InterceptorStrategy
from theauditor.taint.discovery import TaintDiscovery
from theauditor.boundaries.boundary_analyzer import BoundaryAnalyzer
print('All consumers import successfully')
"
```

- [ ] InterceptorStrategy imports
- [ ] TaintDiscovery imports
- [ ] BoundaryAnalyzer imports

### Task 5.4: Run Unit Tests

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/test_code_snippets.py tests/test_explain_command.py -v --tb=short
```

- [ ] All tests pass

### Task 5.5: Run Full Pipeline on PlantFlow

```bash
cd C:/Users/santa/Desktop/PlantFlow && aud full --offline
```

- [ ] Pipeline completes without errors
- [ ] All phases successful

---

## Phase 6: Documentation & Commit

### Task 6.1: Update CLAUDE.md

- [ ] Update table counts: 109 → 129, 8 → 28 Python tables
- [ ] Document consolidated table structure

### Task 6.2: Prepare Commit Message

(Do NOT commit - present for review)

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| 1.1-1.4 | Add 20 tables to python_schema.py | DONE |
| 1.7-1.8 | Update schema.py assertion + verify | DONE |
| 1.5a | PURGE ~140 zombie database methods | DONE (1,655 lines deleted) |
| 1.5b | Add 20 new database mixin methods | DONE (28 methods total) |
| 1.6 | Update flush_order in base_database.py | DONE |
| 2 | Add 20 handlers to python_storage.py | DONE (27 handlers total) |
| 3 | Wire ~150 outputs in python_impl.py | DONE |
| 4 | Regenerate codegen | DONE |
| 5 | Full pipeline verification | DONE |
| 6 | Documentation + commit | PENDING |

**Progress**: Phase 5 COMPLETE. Full pipeline (aud full --offline) passed all 25 phases.

**Bugs Fixed During Phase 5**:
- `python_literals.values` column renamed to `literal_values` (SQL reserved keyword)
- Updated schema, database mixin, and storage handler
- **CRITICAL FIX**: Storage handler now reads both `lit.get('literal_values') or lit.get('values')`
  to handle extractor output (which uses `values`) vs DB column (which uses `literal_values`)

**Estimated work remaining**:
- Phase 6: Documentation + commit (optional)
