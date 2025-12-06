# Proposal: Refactor python_schema.py - Split into Domain-Specific Schemas

## Why

The `python_schema.py` file has grown to **2,795 lines** containing **149 table definitions** that violate single-responsibility principle. An earlier instance of AI rushed implementation and placed everything in one file instead of distributing tables to their correct domain-specific schema files.

**Current problems:**
1. **Cognitive Overload**: File is too large to read in one pass (requires chunked reads)
2. **Mixed Concerns**: Security tables, framework tables, causal learning tables, and language coverage tables all in one file
3. **Maintainability**: Finding/editing a specific table requires scanning 2800 lines
4. **Inconsistency**: Node.js security tables (env_var_usage) already live in security_schema.py, but Python equivalents don't
5. **Missing Modularity**: No separation between "Python language patterns" vs "Django framework patterns" vs "Security vulnerability patterns"

**Risk Level: HIGH** - This touches 250 database tables. Schema changes affect:
- `theauditor/indexer/schema.py` (THE aggregation file - imports and merges all schema dicts into `TABLES`)
- `theauditor/indexer/orchestrator.py` (table creation)
- `theauditor/indexer/storage.py` (insert operations)
- `theauditor/fce.py` (cross-table queries)
- All extractors that write to these tables
- All rules that read from these tables

## Current State (Verified 2025-11-25)

```
ACTUAL TABLE COUNTS (from Python import):
  CORE_TABLES:           24
  SECURITY_TABLES:        7
  FRAMEWORKS_TABLES:      6
  PYTHON_TABLES:        149  <-- THE PROBLEM
  NODE_TABLES:           29
  INFRASTRUCTURE_TABLES: 18
  PLANNING_TABLES:        9
  GRAPHQL_TABLES:         8
  --------------------------
  TOTAL (TABLES):       250
```

## What Changes

### File Changes Summary

| Action | File | Current | After | Tables Moved |
|--------|------|---------|-------|--------------|
| MODIFY | `python_schema.py` | 149 tables | 28 tables | -121 |
| MODIFY | `security_schema.py` | 7 tables | 15 tables | +8 |
| MODIFY | `frameworks_schema.py` | 6 tables | 33 tables | +27 |
| CREATE | `causal_schema.py` | 0 tables | 18 tables | +18 |
| CREATE | `python_coverage_schema.py` | 0 tables | 68 tables | +68 |
| MODIFY | `theauditor/indexer/schema.py` | N/A | N/A | Update imports |

**Verification**: 149 - 8 - 27 - 18 - 68 = 28 (remaining in python_schema.py)

### Tables Moving to security_schema.py (8 tables)

| # | Table Name | Why Security |
|---|------------|--------------|
| 1 | `python_auth_decorators` | Authentication bypass patterns |
| 2 | `python_password_hashing` | Weak credential storage |
| 3 | `python_jwt_operations` | JWT token misuse |
| 4 | `python_sql_injection` | OWASP A03:2021 Injection |
| 5 | `python_command_injection` | OWASP A03:2021 Injection |
| 6 | `python_path_traversal` | OWASP A01:2021 Broken Access |
| 7 | `python_dangerous_eval` | Code injection (eval/exec) |
| 8 | `python_crypto_operations` | Cryptographic failures |

### Tables Moving to frameworks_schema.py (27 tables)

**Django Framework (9 tables):**
| # | Table Name |
|---|------------|
| 1 | `python_django_admin` |
| 2 | `python_django_form_fields` |
| 3 | `python_django_forms` |
| 4 | `python_django_managers` |
| 5 | `python_django_middleware` |
| 6 | `python_django_querysets` |
| 7 | `python_django_receivers` |
| 8 | `python_django_signals` |
| 9 | `python_django_views` |

**Flask Framework (9 tables):**
| # | Table Name |
|---|------------|
| 1 | `python_flask_apps` |
| 2 | `python_flask_cache` |
| 3 | `python_flask_cli_commands` |
| 4 | `python_flask_cors` |
| 5 | `python_flask_error_handlers` |
| 6 | `python_flask_extensions` |
| 7 | `python_flask_hooks` |
| 8 | `python_flask_rate_limits` |
| 9 | `python_flask_websockets` |

**Validation/Serialization (6 tables):**
| # | Table Name |
|---|------------|
| 1 | `python_drf_serializer_fields` |
| 2 | `python_drf_serializers` |
| 3 | `python_marshmallow_fields` |
| 4 | `python_marshmallow_schemas` |
| 5 | `python_wtforms_fields` |
| 6 | `python_wtforms_forms` |

**Task Queues (3 tables):**
| # | Table Name |
|---|------------|
| 1 | `python_celery_beat_schedules` |
| 2 | `python_celery_task_calls` |
| 3 | `python_celery_tasks` |

### Tables Moving to NEW causal_schema.py (18 tables)

**Side Effect Detection (5 tables):**
| # | Table Name | What It Tracks |
|---|------------|----------------|
| 1 | `python_argument_mutations` | param.append() mutations |
| 2 | `python_augmented_assignments` | += -= *= etc |
| 3 | `python_class_mutations` | Class.x = y mutations |
| 4 | `python_global_mutations` | global var mutations |
| 5 | `python_instance_mutations` | self.x = y mutations |

**Exception Flow (4 tables):**
| # | Table Name | What It Tracks |
|---|------------|----------------|
| 1 | `python_context_managers_enhanced` | with statement analysis |
| 2 | `python_exception_catches` | except handlers |
| 3 | `python_exception_raises` | raise statements |
| 4 | `python_finally_blocks` | finally cleanup |

**Data Flow (5 tables):**
| # | Table Name | What It Tracks |
|---|------------|----------------|
| 1 | `python_closure_captures` | nonlocal/closure variables |
| 2 | `python_conditional_calls` | calls inside if/else |
| 3 | `python_io_operations` | File, network, DB, process |
| 4 | `python_nonlocal_access` | nonlocal keyword usage |
| 5 | `python_parameter_return_flow` | param -> return tracking |

**Behavioral Patterns (4 tables):**
| # | Table Name | What It Tracks |
|---|------------|----------------|
| 1 | `python_dynamic_attributes` | __getattr__/__setattr__ |
| 2 | `python_generator_yields` | yield/yield from |
| 3 | `python_property_patterns` | @property getters/setters |
| 4 | `python_recursion_patterns` | direct/tail/mutual recursion |

### Tables Moving to NEW python_coverage_schema.py (68 tables)

**Fundamentals (8 tables):**
`python_comprehensions`, `python_lambda_functions`, `python_slice_operations`, `python_tuple_operations`, `python_unpacking_patterns`, `python_none_patterns`, `python_truthiness_patterns`, `python_string_formatting`

**Operators (6 tables):**
`python_operators`, `python_membership_tests`, `python_chained_comparisons`, `python_ternary_expressions`, `python_walrus_operators`, `python_matrix_multiplication`

**Collections (8 tables):**
`python_dict_operations`, `python_list_mutations`, `python_set_operations`, `python_string_methods`, `python_builtin_usage`, `python_itertools_usage`, `python_functools_usage`, `python_collections_usage`

**Advanced Class Features (10 tables):**
`python_metaclasses`, `python_descriptors`, `python_dataclasses`, `python_enums`, `python_slots`, `python_abstract_classes`, `python_method_types`, `python_multiple_inheritance`, `python_dunder_methods`, `python_visibility_conventions`

**Stdlib Patterns (8 tables):**
`python_regex_patterns`, `python_json_operations`, `python_datetime_operations`, `python_path_operations`, `python_logging_patterns`, `python_threading_patterns`, `python_contextlib_patterns`, `python_type_checking`

**Control Flow (10 tables):**
`python_for_loops`, `python_while_loops`, `python_async_for_loops`, `python_if_statements`, `python_match_statements`, `python_break_continue_pass`, `python_assert_statements`, `python_del_statements`, `python_import_statements`, `python_with_statements`

**Protocols (10 tables):**
`python_iterator_protocol`, `python_container_protocol`, `python_callable_protocol`, `python_comparison_protocol`, `python_arithmetic_protocol`, `python_pickle_protocol`, `python_weakref_usage`, `python_contextvar_usage`, `python_module_attributes`, `python_class_decorators`

**Advanced (8 tables):**
`python_namespace_packages`, `python_cached_property`, `python_descriptor_protocol`, `python_attribute_access_protocol`, `python_copy_protocol`, `python_ellipsis_usage`, `python_bytes_operations`, `python_exec_eval_compile`

### Tables STAYING in python_schema.py (28 tables)

**Core ORM/Routes (6 tables):**
`python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`, `python_package_configs`

**Async Patterns (5 tables):**
`python_decorators`, `python_context_managers`, `python_async_functions`, `python_await_expressions`, `python_async_generators`

**Testing (8 tables):**
`python_pytest_fixtures`, `python_pytest_parametrize`, `python_pytest_markers`, `python_mock_patterns`, `python_unittest_test_cases`, `python_assertion_patterns`, `python_pytest_plugin_hooks`, `python_hypothesis_strategies`

**Typing (5 tables):**
`python_protocols`, `python_generics`, `python_typed_dicts`, `python_literals`, `python_overloads`

**Generators/Performance (4 tables):**
`python_generators`, `python_loop_complexity`, `python_resource_usage`, `python_memoization_patterns`

## Impact

### Breaking Changes
- **NONE** at runtime - tables remain identical, just moved between files
- **Import paths** change for consumers who import schema constants directly (rare - use `TABLES['name']`)

### Affected Code Paths
| Component | File | Impact |
|-----------|------|--------|
| Schema Aggregation | `indexer/schema.py` | Add 2 new imports, update `TABLES` dict |
| Orchestrator | `orchestrator.py` | No change (uses `TABLES` dict) |
| Storage | `storage.py` | No change (uses table names as strings) |
| Extractors | `extractors/*.py` | No change |
| Rules | `rules/*.py` | No change (queries by table name) |
| FCE | `fce.py` | No change (queries by table name) |

### Post-Refactor Table Counts
```
CORE_TABLES:           24  (unchanged)
SECURITY_TABLES:       15  (was 7, +8)
FRAMEWORKS_TABLES:     33  (was 6, +27)
PYTHON_TABLES:         28  (was 149, -121)
NODE_TABLES:           29  (unchanged)
INFRASTRUCTURE_TABLES: 18  (unchanged)
PLANNING_TABLES:        9  (unchanged)
GRAPHQL_TABLES:         8  (unchanged)
CAUSAL_TABLES:         18  (NEW)
PYTHON_COVERAGE_TABLES: 68  (NEW)
--------------------------
TOTAL (TABLES):       250  (unchanged)
```

### Verification Criteria
- [ ] `len(TABLES) == 250` (unchanged)
- [ ] `len(PYTHON_TABLES) == 28`
- [ ] `len(SECURITY_TABLES) == 15`
- [ ] `len(FRAMEWORKS_TABLES) == 33`
- [ ] `len(CAUSAL_TABLES) == 18`
- [ ] `len(PYTHON_COVERAGE_TABLES) == 68`
- [ ] `aud full --index` succeeds without errors
- [ ] All 250 tables created in repo_index.db
- [ ] `pytest tests/` passes
- [ ] No import errors in any module

## Approval Gate

**DO NOT PROCEED** until:
1. Architect reviews table categorization
2. Lead Auditor validates design decisions
3. Both approve migration strategy

This is a **high-risk refactor** affecting the entire schema layer.
