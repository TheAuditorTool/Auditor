# Design: python_schema.py Decomposition Architecture

## Context

### Current Schema Architecture (Verified 2025-11-25)

```
theauditor/indexer/
    schema.py                 # THE AGGREGATION FILE - imports all *_TABLES dicts
                              # and merges into single TABLES dict
                              # ALSO re-exports individual table constants
    schemas/
        utils.py              # Column, TableSchema, ForeignKey classes
        core_schema.py        # 24 tables - language-agnostic core patterns
        security_schema.py    # 7 tables - cross-language security patterns
        frameworks_schema.py  # 6 tables - cross-language framework patterns
        python_schema.py      # 149 tables - BLOATED - needs split
        node_schema.py        # 29 tables - React/Vue/TypeScript
        infrastructure_schema.py # 18 tables - Docker/Terraform/CDK/GitHub Actions
        planning_schema.py    # 9 tables - Planning/meta-system
        graphql_schema.py     # 8 tables - GraphQL types/resolvers
        graphs_schema.py      # Graph database schema (separate DB)
        codegen.py            # Schema code generation
        generated_*.py        # Auto-generated accessor/validator code
```

**CRITICAL**: The aggregation happens in `theauditor/indexer/schema.py`, NOT in `schemas/__init__.py` (which doesn't exist). The variable is named `TABLES`, NOT `ALL_TABLES`.

### Current Aggregation Code (schema.py lines 56-79)

```python
# Import all table registries
from .schemas.core_schema import CORE_TABLES
from .schemas.security_schema import SECURITY_TABLES
from .schemas.frameworks_schema import FRAMEWORKS_TABLES
from .schemas.python_schema import PYTHON_TABLES
from .schemas.node_schema import NODE_TABLES
from .schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
from .schemas.planning_schema import PLANNING_TABLES
from .schemas.graphql_schema import GRAPHQL_TABLES

TABLES: dict[str, TableSchema] = {
    **CORE_TABLES,           # 24 tables
    **SECURITY_TABLES,       # 7 tables
    **FRAMEWORKS_TABLES,     # 6 tables (was 5)
    **PYTHON_TABLES,         # 149 tables (was 59)
    **NODE_TABLES,           # 29 tables (was 26)
    **INFRASTRUCTURE_TABLES, # 18 tables
    **PLANNING_TABLES,       # 9 tables
    **GRAPHQL_TABLES,        # 8 tables
}

assert len(TABLES) == 250, f"Schema contract violation: Expected 250 tables, got {len(TABLES)}"
```

### Design Philosophy (from existing docstrings)
Each schema file has a clear domain:
- **core_schema.py**: "Used by ALL languages" - symbols, calls, CFG
- **node_schema.py**: "Node/JavaScript/TypeScript-specific"
- **security_schema.py**: "Cross-language security patterns"
- **frameworks_schema.py**: "Cross-language framework patterns"
- **infrastructure_schema.py**: "Infrastructure-as-Code"
- **planning_schema.py**: "Meta-system tables (not code analysis)"
- **graphql_schema.py**: "GraphQL schema layer"
- **python_schema.py**: SHOULD BE "Python-specific language patterns"

### The Problem
python_schema.py violated its design philosophy by accumulating:
1. **Python security patterns** (should be in security_schema.py)
2. **Django/Flask framework patterns** (should be in frameworks_schema.py)
3. **Causal learning patterns** (new domain - needs own file)
4. **Python language coverage** (new domain - needs own file)

## Goals / Non-Goals

### Goals
1. **Single Responsibility**: Each file owns ONE domain
2. **Reasonable File Size**: Target <800 lines per schema file
3. **Consistent Organization**: Follow existing patterns from other schema files
4. **Zero Runtime Changes**: Table names, columns, indexes unchanged
5. **Reversibility**: Can be reverted with `git revert`

### Non-Goals
1. NOT changing table schemas (column names, types, indexes)
2. NOT renaming tables (would break existing databases)
3. NOT modifying extractor code (imports stay the same)
4. NOT changing storage.py or fce.py
5. NOT adding new tables in this change

## Decisions

### Decision 1: Security Tables -> security_schema.py

**Rationale**: security_schema.py already contains:
- `sql_objects`, `sql_queries`, `sql_query_tables` (SQL analysis)
- `jwt_patterns` (auth token patterns)
- `env_var_usage` (environment variable exposure)
- `taint_flows` (data flow tracking)
- `resolved_flow_audit` (taint provenance)

Python security tables follow same pattern - vulnerability detection, not language patterns.

**Tables to move (8)**:
| Table Name | Current Registry Key |
|------------|---------------------|
| `PYTHON_AUTH_DECORATORS` | `python_auth_decorators` |
| `PYTHON_PASSWORD_HASHING` | `python_password_hashing` |
| `PYTHON_JWT_OPERATIONS` | `python_jwt_operations` |
| `PYTHON_SQL_INJECTION` | `python_sql_injection` |
| `PYTHON_COMMAND_INJECTION` | `python_command_injection` |
| `PYTHON_PATH_TRAVERSAL` | `python_path_traversal` |
| `PYTHON_DANGEROUS_EVAL` | `python_dangerous_eval` |
| `PYTHON_CRYPTO_OPERATIONS` | `python_crypto_operations` |

### Decision 2: Framework Tables -> frameworks_schema.py

**Rationale**: frameworks_schema.py already contains:
- `orm_queries` (cross-language ORM)
- `orm_relationships` (cross-language ORM)
- `prisma_models` (Node ORM)
- `api_endpoints` (cross-language API)
- `api_endpoint_controls` (cross-language auth)
- (6 tables currently)

Django/Flask tables are framework-specific patterns, not Python language patterns.

**Tables to move (27)**:
| Category | Count | Tables |
|----------|-------|--------|
| Django | 9 | `python_django_admin`, `python_django_form_fields`, `python_django_forms`, `python_django_managers`, `python_django_middleware`, `python_django_querysets`, `python_django_receivers`, `python_django_signals`, `python_django_views` |
| Flask | 9 | `python_flask_apps`, `python_flask_cache`, `python_flask_cli_commands`, `python_flask_cors`, `python_flask_error_handlers`, `python_flask_extensions`, `python_flask_hooks`, `python_flask_rate_limits`, `python_flask_websockets` |
| Validation | 6 | `python_drf_serializer_fields`, `python_drf_serializers`, `python_marshmallow_fields`, `python_marshmallow_schemas`, `python_wtforms_fields`, `python_wtforms_forms` |
| Task Queues | 3 | `python_celery_beat_schedules`, `python_celery_task_calls`, `python_celery_tasks` |

### Decision 3: NEW causal_schema.py for Causal Learning

**Rationale**: "Causal Learning Patterns" is a distinct analytical domain:
- Side effect detection (mutations)
- Exception flow (try/except/finally)
- Data flow (closures, IO, returns)
- Behavioral patterns (recursion, generators)

These are NOT Python language coverage - they're semantic analysis patterns for understanding causality.

**Tables to create file with (18)**:
| Category | Tables |
|----------|--------|
| Side Effect Detection (5) | `python_argument_mutations`, `python_augmented_assignments`, `python_class_mutations`, `python_global_mutations`, `python_instance_mutations` |
| Exception Flow (4) | `python_context_managers_enhanced`, `python_exception_catches`, `python_exception_raises`, `python_finally_blocks` |
| Data Flow (5) | `python_closure_captures`, `python_conditional_calls`, `python_io_operations`, `python_nonlocal_access`, `python_parameter_return_flow` |
| Behavioral Patterns (4) | `python_dynamic_attributes`, `python_generator_yields`, `python_property_patterns`, `python_recursion_patterns` |

### Decision 4: NEW python_coverage_schema.py for Language Coverage

**Rationale**: "Python Coverage V2" tables track Python LANGUAGE constructs, not frameworks or security:
- Comprehensions, lambdas, slices
- Operators, membership tests
- Dict/list/set operations
- Class features (metaclass, descriptor, dataclass)
- Control flow (for, while, if, match)
- Protocols (iterator, callable, comparison)

This is AST-level language coverage - fundamentally different from framework patterns.

**Tables to create file with (68)**:
| Category | Count | Tables |
|----------|-------|--------|
| Fundamentals | 8 | `python_comprehensions`, `python_lambda_functions`, `python_slice_operations`, `python_tuple_operations`, `python_unpacking_patterns`, `python_none_patterns`, `python_truthiness_patterns`, `python_string_formatting` |
| Operators | 6 | `python_operators`, `python_membership_tests`, `python_chained_comparisons`, `python_ternary_expressions`, `python_walrus_operators`, `python_matrix_multiplication` |
| Collections | 8 | `python_dict_operations`, `python_list_mutations`, `python_set_operations`, `python_string_methods`, `python_builtin_usage`, `python_itertools_usage`, `python_functools_usage`, `python_collections_usage` |
| Advanced Class | 10 | `python_metaclasses`, `python_descriptors`, `python_dataclasses`, `python_enums`, `python_slots`, `python_abstract_classes`, `python_method_types`, `python_multiple_inheritance`, `python_dunder_methods`, `python_visibility_conventions` |
| Stdlib | 8 | `python_regex_patterns`, `python_json_operations`, `python_datetime_operations`, `python_path_operations`, `python_logging_patterns`, `python_threading_patterns`, `python_contextlib_patterns`, `python_type_checking` |
| Control Flow | 10 | `python_for_loops`, `python_while_loops`, `python_async_for_loops`, `python_if_statements`, `python_match_statements`, `python_break_continue_pass`, `python_assert_statements`, `python_del_statements`, `python_import_statements`, `python_with_statements` |
| Protocols | 10 | `python_iterator_protocol`, `python_container_protocol`, `python_callable_protocol`, `python_comparison_protocol`, `python_arithmetic_protocol`, `python_pickle_protocol`, `python_weakref_usage`, `python_contextvar_usage`, `python_module_attributes`, `python_class_decorators` |
| Advanced | 8 | `python_namespace_packages`, `python_cached_property`, `python_descriptor_protocol`, `python_attribute_access_protocol`, `python_copy_protocol`, `python_ellipsis_usage`, `python_bytes_operations`, `python_exec_eval_compile` |

### Decision 5: KEEP in python_schema.py (28 tables)

**Rationale**: These are foundational Python patterns that belong together:

| Category | Tables |
|----------|--------|
| Core ORM/Routes (6) | `python_orm_models`, `python_orm_fields`, `python_routes`, `python_blueprints`, `python_validators`, `python_package_configs` |
| Async Patterns (5) | `python_decorators`, `python_context_managers`, `python_async_functions`, `python_await_expressions`, `python_async_generators` |
| Testing (8) | `python_pytest_fixtures`, `python_pytest_parametrize`, `python_pytest_markers`, `python_mock_patterns`, `python_unittest_test_cases`, `python_assertion_patterns`, `python_pytest_plugin_hooks`, `python_hypothesis_strategies` |
| Typing (5) | `python_protocols`, `python_generics`, `python_typed_dicts`, `python_literals`, `python_overloads` |
| Generators/Performance (4) | `python_generators`, `python_loop_complexity`, `python_resource_usage`, `python_memoization_patterns` |

**Why keep async/testing/typing together**:
- Async is a Python 3.5+ language feature (not framework)
- Testing is pytest/unittest (Python ecosystem, not Django Test)
- Typing is PEP 484 type hints (language feature)
- These are commonly used together in any Python codebase

## Risks / Trade-offs

### Risk 1: Import Path Changes
**Impact**: LOW - Schema imports are internal
**Mitigation**: Only `indexer/schema.py` imports schema modules. Consumers use `TABLES['name']` dict.

### Risk 2: Missing Table During Move
**Impact**: HIGH - Would cause 500 error on INSERT
**Mitigation**:
1. Count tables before and after (must equal 250)
2. Run `aud full --index` as smoke test
3. Automated verification in tasks.md

### Risk 3: Circular Import
**Impact**: MEDIUM - Could break module loading
**Mitigation**:
1. Each schema file is self-contained
2. No schema imports from another schema
3. Only `schema.py` aggregates

### Risk 4: Registry Mismatch
**Impact**: HIGH - Would silently miss tables
**Mitigation**:
1. Each file has `DOMAIN_TABLES: dict[str, TableSchema]` at bottom
2. `schema.py` does: `TABLES = {**CORE_TABLES, **SECURITY_TABLES, ...}`
3. `assert len(TABLES) == 250` at module load time

### Risk 5: Backward Compatibility Re-exports
**Impact**: MEDIUM - Code importing individual constants would break
**Mitigation**:
1. `schema.py` already re-exports individual table constants (lines 99-272)
2. Must add re-exports for NEW schema files (CAUSAL_TABLES, PYTHON_COVERAGE_TABLES)
3. Alternative: Consumers should use `TABLES['name']` pattern

## Migration Plan

### Phase 1: Create New Files (Non-Breaking)
1. Create `causal_schema.py` with copied tables (18 tables)
2. Create `python_coverage_schema.py` with copied tables (68 tables)
3. Verify both files import cleanly
4. DO NOT update `schema.py` yet - tables exist in BOTH places

### Phase 2: Modify Existing Files (Non-Breaking)
1. Add 8 tables to `security_schema.py`
2. Add 27 tables to `frameworks_schema.py`
3. Update `SECURITY_TABLES` and `FRAMEWORKS_TABLES` dicts
4. DO NOT remove from `python_schema.py` yet - duplicates OK temporarily

### Phase 3: Update schema.py (Critical)
1. Add imports for new schema files
2. Update `TABLES` dict aggregation
3. Verify `len(TABLES) == 250` (assertion will catch duplicates)

### Phase 4: Clean python_schema.py (Breaking until complete)
1. Delete moved table definitions
2. Update `PYTHON_TABLES` dict to only include remaining 28 tables
3. Verify file size ~750 lines

### Phase 5: Update Re-exports in schema.py
1. Add re-exports for causal tables
2. Add re-exports for coverage tables
3. Verify backward compat imports work

### Phase 6: Verification
1. `assert len(TABLES) == 250` passes
2. `aud full --index` succeeds
3. `pytest tests/` passes
4. Check repo_index.db has all 250 tables

## Rollback Plan

If issues detected:
```bash
git revert <commit_hash>
rm -f .pf/repo_index.db
aud full --index
```

## Open Questions

1. **Q**: Should testing tables (pytest, unittest) move to a testing_schema.py?
   **A**: NO - Keep simple. Testing is Python ecosystem, not separate domain.

2. **Q**: Should we rename tables to remove `PYTHON_` prefix for moved tables?
   **A**: NO - Table names are API. Renaming would break existing databases.

3. **Q**: Should frameworks_schema.py be split into django_schema.py, flask_schema.py?
   **A**: NO - Too granular. Framework patterns belong together for cross-framework analysis.

## File Size Targets (Post-Refactor)

| File | Current Lines | Current Tables | Target Lines | Target Tables |
|------|---------------|----------------|--------------|---------------|
| python_schema.py | 2795 | 149 | ~750 | 28 |
| security_schema.py | 242 | 7 | ~370 | 15 |
| frameworks_schema.py | 160 | 6 | ~860 | 33 |
| causal_schema.py | 0 | 0 | ~280 | 18 |
| python_coverage_schema.py | 0 | 0 | ~1100 | 68 |

**Overhead**: ~5% increase from file headers/imports
**Benefit**: No file >1100 lines (vs 2795 currently)
