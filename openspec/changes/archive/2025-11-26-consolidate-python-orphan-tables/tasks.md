# Tasks: Python Orphan Table Consolidation

## Pre-Flight Checklist

**STOP. Before ANY code changes, verify these:**

- [x] **PRIME DIRECTIVE ACKNOWLEDGED**: Read-first, act-second. No assumptions.
- [x] Read `design.md` completely (all sections)
- [x] Read `proposal.md` completely (all sections)
- [x] Run baseline verification command below

**Baseline Verification Command:**
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
print('=== BASELINE (must match before starting) ===')
print(f'TABLES: {len(TABLES)} (expect 250)')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 149)')
"
```

**RECORD BASELINE STATE:**
```
Date: 2025-11-25
TABLES: 250 (expect 250) - VERIFIED
PYTHON_TABLES: 149 (expect 149) - VERIFIED
aud full --offline: (not run - schema changes needed first)
pytest: (not run - schema changes needed first)
```

---

## Phase 0: Verification (Pre-Implementation)

### Task 0.1: Verify No Hidden Consumers

**Objective**: Confirm orphan tables have NO hidden consumers

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import os
import re

# VERIFIED LIST: 141 orphan tables (from PYTHON_TABLES - used_tables)
orphan_tables = [
    'python_abstract_classes', 'python_argument_mutations', 'python_arithmetic_protocol',
    'python_assert_statements', 'python_assertion_patterns', 'python_async_for_loops',
    'python_async_functions', 'python_async_generators', 'python_attribute_access_protocol',
    'python_augmented_assignments', 'python_auth_decorators', 'python_await_expressions',
    'python_blueprints', 'python_break_continue_pass', 'python_builtin_usage',
    'python_bytes_operations', 'python_cached_property', 'python_callable_protocol',
    'python_celery_beat_schedules', 'python_celery_task_calls', 'python_celery_tasks',
    'python_chained_comparisons', 'python_class_decorators', 'python_class_mutations',
    'python_closure_captures', 'python_collections_usage', 'python_command_injection',
    'python_comparison_protocol', 'python_comprehensions', 'python_conditional_calls',
    'python_container_protocol', 'python_context_managers', 'python_context_managers_enhanced',
    'python_contextlib_patterns', 'python_contextvar_usage', 'python_copy_protocol',
    'python_crypto_operations', 'python_dangerous_eval', 'python_dataclasses',
    'python_datetime_operations', 'python_del_statements', 'python_descriptor_protocol',
    'python_descriptors', 'python_dict_operations', 'python_django_admin',
    'python_django_form_fields', 'python_django_forms', 'python_django_managers',
    'python_django_querysets', 'python_django_receivers', 'python_django_signals',
    'python_drf_serializer_fields', 'python_drf_serializers', 'python_dunder_methods',
    'python_dynamic_attributes', 'python_ellipsis_usage', 'python_enums',
    'python_exception_catches', 'python_exception_raises', 'python_exec_eval_compile',
    'python_finally_blocks', 'python_flask_apps', 'python_flask_cache',
    'python_flask_cli_commands', 'python_flask_cors', 'python_flask_error_handlers',
    'python_flask_extensions', 'python_flask_hooks', 'python_flask_rate_limits',
    'python_flask_websockets', 'python_for_loops', 'python_functools_usage',
    'python_generator_yields', 'python_generators', 'python_generics',
    'python_global_mutations', 'python_hypothesis_strategies', 'python_if_statements',
    'python_import_statements', 'python_instance_mutations', 'python_io_operations',
    'python_iterator_protocol', 'python_itertools_usage', 'python_json_operations',
    'python_jwt_operations', 'python_lambda_functions', 'python_list_mutations',
    'python_literals', 'python_logging_patterns', 'python_loop_complexity',
    'python_marshmallow_fields', 'python_marshmallow_schemas', 'python_match_statements',
    'python_matrix_multiplication', 'python_membership_tests', 'python_memoization_patterns',
    'python_metaclasses', 'python_method_types', 'python_mock_patterns',
    'python_module_attributes', 'python_multiple_inheritance', 'python_namespace_packages',
    'python_none_patterns', 'python_nonlocal_access', 'python_operators',
    'python_overloads', 'python_parameter_return_flow', 'python_password_hashing',
    'python_path_operations', 'python_path_traversal', 'python_pickle_protocol',
    'python_property_patterns', 'python_protocols', 'python_pytest_fixtures',
    'python_pytest_markers', 'python_pytest_parametrize', 'python_pytest_plugin_hooks',
    'python_recursion_patterns', 'python_regex_patterns', 'python_resource_usage',
    'python_set_operations', 'python_slice_operations', 'python_slots',
    'python_sql_injection', 'python_string_formatting', 'python_string_methods',
    'python_ternary_expressions', 'python_threading_patterns', 'python_truthiness_patterns',
    'python_tuple_operations', 'python_type_checking', 'python_typed_dicts',
    'python_unittest_test_cases', 'python_unpacking_patterns', 'python_visibility_conventions',
    'python_walrus_operators', 'python_weakref_usage', 'python_while_loops',
    'python_with_statements', 'python_wtforms_fields', 'python_wtforms_forms'
]

print(f'Checking {len(orphan_tables)} orphan tables for hidden consumers...')

# Search for SELECT queries in analysis code
found = {}
for root, dirs, files in os.walk('theauditor'):
    skip = ['storage', 'schemas', 'database', '__pycache__']
    if any(s in root for s in skip):
        continue
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                    for table in orphan_tables:
                        if f'FROM {table}' in content or f'from {table}' in content:
                            if table not in found:
                                found[table] = []
                            found[table].append(path)
            except: pass

if found:
    print('WARNING: Found SELECT queries for orphan tables!')
    for table, files in found.items():
        print(f'  {table}: {files}')
else:
    print('CONFIRMED: No SELECT queries for orphan tables')
    print(f'Safe to delete all {len(orphan_tables)} orphan tables')
"
```

- [x] Output shows "CONFIRMED: No SELECT queries for orphan tables"
- [x] Count shows exactly 141 orphan tables
- [x] If any found, investigate before proceeding

### Task 0.2: Backup Current State

```bash
cd C:/Users/santa/Desktop/TheAuditor
git checkout -b backup/pre-orphan-consolidation
git checkout dev
```

- [x] Backup branch created (SKIPPED - on isolated dev branch, all committed)

---

## Phase 1: Schema Cleanup (141 tables)

### Task 1.1: Tables to KEEP (8 tables)

**These are the ONLY tables to keep in python_schema.py:**

```python
PYTHON_TABLES = {
    'python_decorators': PYTHON_DECORATORS,
    'python_django_middleware': PYTHON_DJANGO_MIDDLEWARE,
    'python_django_views': PYTHON_DJANGO_VIEWS,
    'python_orm_fields': PYTHON_ORM_FIELDS,
    'python_orm_models': PYTHON_ORM_MODELS,
    'python_package_configs': PYTHON_PACKAGE_CONFIGS,
    'python_routes': PYTHON_ROUTES,
    'python_validators': PYTHON_VALIDATORS,
}
```

**Verified consumers for each table:**
| Table | Consumer Files |
|-------|---------------|
| `python_decorators` | `graph/strategies/interceptors.py`, `context/deadcode_graph.py`, `context/query.py` |
| `python_django_middleware` | `graph/strategies/interceptors.py` |
| `python_django_views` | `graph/strategies/interceptors.py` |
| `python_orm_fields` | `rules/graphql/overfetch.py` |
| `python_orm_models` | `rules/graphql/overfetch.py`, `taint/discovery.py` |
| `python_package_configs` | `deps.py`, `commands/blueprint.py` |
| `python_routes` | `boundaries/boundary_analyzer.py`, `context/deadcode_graph.py`, `context/query.py` |
| `python_validators` | `taint/discovery.py` (via SchemaMemoryCache) |

- [x] List verified against actual code

### Task 1.2: Edit python_schema.py

**File**: `theauditor/indexer/schemas/python_schema.py`

**Action**: Delete ALL TableSchema definitions EXCEPT:
- `PYTHON_DECORATORS`
- `PYTHON_DJANGO_MIDDLEWARE`
- `PYTHON_DJANGO_VIEWS`
- `PYTHON_ORM_FIELDS`
- `PYTHON_ORM_MODELS`
- `PYTHON_PACKAGE_CONFIGS`
- `PYTHON_ROUTES`
- `PYTHON_VALIDATORS`

**After edit:**
- File should have ~8 TableSchema definitions
- `PYTHON_TABLES` dict should have exactly 8 entries
- File should be ~200-300 lines (was ~2800 lines)

- [x] All 141 orphan TableSchema definitions deleted
- [x] PYTHON_TABLES dict updated to exactly 8 entries
- [x] File compiles: `python -c "from theauditor.indexer.schemas.python_schema import PYTHON_TABLES; print(len(PYTHON_TABLES))"`

**COMPLETED**: 2025-11-25 - File reduced from ~2795 lines to 209 lines

### Task 1.3: Update schema.py Assertion

**File**: `theauditor/indexer/schema.py`

**Find**:
```python
assert len(TABLES) == 250, f"Schema contract violation: Expected 250 tables, got {len(TABLES)}"
```

**Replace with**:
```python
assert len(TABLES) == 109, f"Schema contract violation: Expected 109 tables, got {len(TABLES)}"
```

- [x] Assertion updated from 250 to 109
- [x] Also removed deleted table aliases (PYTHON_BLUEPRINTS, PYTHON_CELERY_*, etc.)
- [x] Updated comment block about table counts

**COMPLETED**: 2025-11-25

### Task 1.4: Verify Schema Changes

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
print(f'TABLES: {len(TABLES)} (expect 109)')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 8)')
assert len(TABLES) == 109, f'Expected 109, got {len(TABLES)}'
assert len(PYTHON_TABLES) == 8, f'Expected 8, got {len(PYTHON_TABLES)}'
print('Schema verification PASSED')
"
```

- [x] TABLES == 109
- [x] PYTHON_TABLES == 8

**COMPLETED**: 2025-11-25 - All assertions pass

---

## Phase 2: Storage Cleanup (141 handlers)

### Task 2.1: Handlers to KEEP (7 handlers)

**File**: `theauditor/indexer/storage/python_storage.py`

**Keep ONLY these handler dict entries:**
```python
self.handlers = {
    'python_decorators': self._store_python_decorators,
    'python_django_middleware': self._store_python_django_middleware,
    'python_django_views': self._store_python_django_views,
    'python_orm_fields': self._store_python_orm_fields,
    'python_orm_models': self._store_python_orm_models,
    'python_routes': self._store_python_routes,
    'python_validators': self._store_python_validators,
}
```

**NOTE:** `python_package_configs` is stored via `generic_batches` in `python_database.py`, not here.

**Delete ALL 141 other `_store_python_*` methods.**

- [x] Handler dict reduced to exactly 7 entries
- [x] All 141 orphan `_store_python_*` methods deleted
- [x] File compiles without errors

**COMPLETED**: 2025-11-25 - File reduced from ~2800 lines to 169 lines

### Task 2.2: Verify Storage Changes

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.storage.python_storage import PythonStorage
class FakeDB:
    def get_cursor(self): return None
ps = PythonStorage(FakeDB(), {})
print(f'Python handlers: {len(ps.handlers)} (expect 7)')
print('Handlers:', sorted(ps.handlers.keys()))
assert len(ps.handlers) == 7, f'Expected 7, got {len(ps.handlers)}'
print('Storage verification PASSED')
"
```

- [x] Handlers == 7

**COMPLETED**: 2025-11-25 - All assertions pass

---

## Phase 3: Extractor Cleanup (19 files to delete, 5 files to modify)

### Task 3.1: DELETE Extractor Files (19 files)

**Directory**: `theauditor/ast_extractors/python/`

**Files to DELETE (all their python_* outputs are orphans):**
```bash
cd C:/Users/santa/Desktop/TheAuditor/theauditor/ast_extractors/python

rm advanced_extractors.py      # python_namespace_packages, python_cached_property, etc.
rm async_extractors.py         # python_async_functions, python_await_expressions, etc.
rm behavioral_extractors.py    # python_recursion_patterns, python_generator_yields, etc.
rm class_feature_extractors.py # python_metaclasses, python_descriptors, etc.
rm collection_extractors.py    # python_dict_operations, python_list_mutations, etc.
rm control_flow_extractors.py  # python_for_loops, python_while_loops, etc.
rm data_flow_extractors.py     # python_io_operations, python_closure_captures, etc.
rm django_advanced_extractors.py # python_django_signals, python_django_receivers, etc.
rm exception_flow_extractors.py  # python_exception_raises, python_exception_catches, etc.
rm framework_extractors.py     # python_celery_tasks, python_celery_task_calls, etc.
rm fundamental_extractors.py   # python_comprehensions, python_lambda_functions, etc.
rm operator_extractors.py      # python_operators, python_membership_tests, etc.
rm performance_extractors.py   # python_loop_complexity, python_resource_usage, etc.
rm protocol_extractors.py      # python_iterator_protocol, python_container_protocol, etc.
rm security_extractors.py      # python_auth_decorators, python_sql_injection, etc.
rm state_mutation_extractors.py # python_instance_mutations, python_class_mutations, etc.
rm stdlib_pattern_extractors.py # python_regex_patterns, python_json_operations, etc.
rm testing_extractors.py       # python_pytest_fixtures, python_mock_patterns, etc.
rm type_extractors.py          # python_protocols, python_generics, etc.
```

- [x] All 19 files deleted (2025-11-25)

### Task 3.2: KEEP Extractor Files (8 files)

**Files to KEEP unchanged (no python_* tables):**
- `__init__.py` (will update imports in Task 3.4)
- `cdk_extractor.py` (outputs cdk_constructs, not python_*)
- `cfg_extractor.py` (outputs cfg, not python_*)
- `task_graphql_extractors.py` (outputs graphql_*, not python_*)

**Files to KEEP with PARTIAL CLEANUP (remove orphan extractions):**
- `core_extractors.py`
- `django_web_extractors.py`
- `flask_extractors.py`
- `orm_extractors.py`
- `validation_extractors.py`

### Task 3.3: Modify Kept Extractor Files

**core_extractors.py:**
- KEEP: `extract_python_decorators()`
- REMOVE: `extract_python_context_managers()`, `extract_generators()`
- Note: Other core functions (symbols, imports, etc.) output to core tables, not python_*

**django_web_extractors.py:**
- KEEP: `extract_django_cbvs()`, `extract_django_middleware()`
- REMOVE: `extract_django_forms()`, `extract_django_form_fields()`, `extract_django_admin()`

**flask_extractors.py:**
- KEEP: `extract_flask_routes()`
- REMOVE: `extract_flask_app_factories()`, `extract_flask_extensions()`, `extract_flask_request_hooks()`,
          `extract_flask_error_handlers()`, `extract_flask_websocket_handlers()`, `extract_flask_cli_commands()`,
          `extract_flask_cors_configs()`, `extract_flask_rate_limits()`, `extract_flask_cache_decorators()`

**orm_extractors.py:**
- KEEP: `extract_sqlalchemy_definitions()`, `extract_django_definitions()`
- REMOVE: `extract_flask_blueprints()`

**validation_extractors.py:**
- KEEP: `extract_pydantic_validators()`
- REMOVE: `extract_marshmallow_schemas()`, `extract_marshmallow_fields()`,
          `extract_drf_serializers()`, `extract_drf_serializer_fields()`,
          `extract_wtforms_forms()`, `extract_wtforms_fields()`

- [x] Each file modified per above spec (2025-11-25)
- [x] Each file compiles without errors

### Task 3.4: Update python_impl.py

**File**: `theauditor/ast_extractors/python_impl.py`

**DELETE these imports (lines 25-62):**
```python
# DELETE these imports
from theauditor.ast_extractors.python import (
    framework_extractors,      # DELETE
    django_advanced_extractors, # DELETE
    async_extractors,          # DELETE
    behavioral_extractors,     # DELETE
    collection_extractors,     # DELETE
    control_flow_extractors,   # DELETE
    data_flow_extractors,      # DELETE
    exception_flow_extractors, # DELETE
    operator_extractors,       # DELETE
    performance_extractors,    # DELETE
    protocol_extractors,       # DELETE
    state_mutation_extractors, # DELETE
    advanced_extractors,       # DELETE
    class_feature_extractors,  # DELETE
    security_extractors,       # DELETE
    stdlib_pattern_extractors, # DELETE
    testing_extractors,        # DELETE
    type_extractors,           # DELETE
    fundamental_extractors,    # DELETE
)
```

**KEEP these imports:**
```python
from theauditor.ast_extractors.python import (
    core_extractors,
    flask_extractors,
    django_web_extractors,
    validation_extractors,
    orm_extractors,
    cfg_extractor,
    cdk_extractor,
    task_graphql_extractors,
)
```

**DELETE result dict keys for orphan tables (lines 84-297):**
Remove all `'python_*': []` entries except:
- `python_decorators`
- `python_django_middleware`
- `python_django_views`
- `python_orm_fields`
- `python_orm_models`
- `python_package_configs`
- `python_routes`
- `python_validators`

**DELETE all extraction calls that populate orphan tables (lines 447-1002):**
Remove ALL calls to:
- `framework_extractors.*`
- `django_advanced_extractors.*`
- `async_extractors.*`
- `behavioral_extractors.*`
- `collection_extractors.*`
- `control_flow_extractors.*`
- `data_flow_extractors.*`
- `exception_flow_extractors.*`
- `operator_extractors.*`
- `performance_extractors.*`
- `protocol_extractors.*`
- `state_mutation_extractors.*`
- `advanced_extractors.*`
- `class_feature_extractors.*`
- `security_extractors.*`
- `stdlib_pattern_extractors.*`
- `testing_extractors.*`
- `type_extractors.*`
- `fundamental_extractors.*`

Also remove orphan extraction calls from KEPT modules:
- `core_extractors.extract_python_context_managers()`
- `core_extractors.extract_generators()`
- `django_web_extractors.extract_django_forms()`
- `django_web_extractors.extract_django_form_fields()`
- `django_web_extractors.extract_django_admin()`
- `flask_extractors.extract_flask_app_factories()`
- `flask_extractors.extract_flask_extensions()`
- `flask_extractors.extract_flask_request_hooks()`
- `flask_extractors.extract_flask_error_handlers()`
- `flask_extractors.extract_flask_websocket_handlers()`
- `flask_extractors.extract_flask_cli_commands()`
- `flask_extractors.extract_flask_cors_configs()`
- `flask_extractors.extract_flask_rate_limits()`
- `flask_extractors.extract_flask_cache_decorators()`
- `orm_extractors.extract_flask_blueprints()`
- `validation_extractors.extract_marshmallow_schemas()`
- `validation_extractors.extract_marshmallow_fields()`
- `validation_extractors.extract_drf_serializers()`
- `validation_extractors.extract_drf_serializer_fields()`
- `validation_extractors.extract_wtforms_forms()`
- `validation_extractors.extract_wtforms_fields()`

- [x] All deleted extractor imports removed (2025-11-25)
- [x] All orphan result dict keys removed
- [x] All orphan extraction calls removed
- [x] File compiles without errors

**COMPLETED**: 2025-11-25 - File reduced from ~1034 lines to 231 lines

### Task 3.5: Update __init__.py

**File**: `theauditor/ast_extractors/python/__init__.py`

**Remove exports for deleted extractors.**

- [x] Exports updated (2025-11-25)
- [x] No import errors

**COMPLETED**: 2025-11-25 - File reduced from ~468 lines to 125 lines

### Task 3.6: Verify Extractor Changes

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.ast_extractors import python_impl
print('Extractor import verification PASSED')
"
```

- [x] No import errors (2025-11-25)

**PHASE 3 COMPLETED**: 2025-11-25
- 19 extractor files deleted
- 5 extractor files partially cleaned
- python_impl.py updated
- __init__.py exports updated
- All imports verified working

---

## Phase 4: Regenerate Generated Code

### Task 4.1: Run Schema Codegen

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m theauditor.indexer.schemas.codegen
```

- [x] Codegen completed without errors (2025-11-25)

### Task 4.2: Verify Generated Code

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schemas.generated_cache import SchemaMemoryCache
print('Generated code import verification PASSED')
"
```

- [x] No import errors (2025-11-25)
- [x] 109 TypedDicts generated
- [x] 109 Accessors generated
- [x] 8 Python TypedDicts (matches 8 kept tables)

**PHASE 4 COMPLETED**: 2025-11-25

---

## Phase 5: Full Verification

### Task 5.1: Archive Old Database (via aud full)

Note: `aud full --offline` automatically archives old databases to `.pf/history/full/{date}` for regression comparison.

- [x] Old database archived to .pf/history/full/20251125_192703 (2025-11-25)

### Task 5.2: Run Full Pipeline

```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full --offline
```

- [x] Pipeline completes without errors (2025-11-25)
- [x] All 25 phases successful
- [x] 788 files indexed, 51543 symbols
- [x] Total time: 4.1 minutes

### Task 5.3: Verify Database Tables

- [x] Exactly 8 python_* tables exist (2025-11-25)
- [x] All 8 expected tables present with data:
  - python_decorators: 1264 rows
  - python_django_middleware: 7 rows
  - python_django_views: 12 rows
  - python_orm_fields: 191 rows
  - python_orm_models: 53 rows
  - python_package_configs: 4 rows
  - python_routes: 41 rows
  - python_validators: 9 rows

### Task 5.4: Run Unit Tests

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -m pytest tests/test_code_snippets.py tests/test_explain_command.py -v --tb=short
```

- [x] All 22 tests pass (2025-11-25)

### Task 5.5: Verify Consumers Still Work

- [x] InterceptorStrategy imports (2025-11-25)
- [x] TaintDiscovery imports
- [x] boundary_analyzer imports
- [x] GraphDeadCodeDetector imports
- [x] CodeQueryEngine imports
- [x] check_graphql_overfetch imports
- [x] Blueprint command imports

**PHASE 5 COMPLETED**: 2025-11-25

---

## Side Quest: Critical Hotfixes (Blocking Issues)

**Status:** COMPLETE
**Triggered By:** Schema consolidation changed pipeline timing, exposing latent race conditions.

### Bug 1: Database Lock (Concurrency) - ATTEMPT 1 (FAILED)

Initial fix applied WAL mode to Track C files only (deps.py, vulnerability_scanner.py).
**Result:** FAILED - Track B held lock without WAL mode, Track C still blocked.

### Bug 1: Database Lock (Concurrency) - ATTEMPT 2 (SUCCESS)

**Root Cause:** WAL mode must be set by the FIRST connection to take effect. Track B opened connections before Track C, without WAL mode.

**Solution:** Option A - Fix at Source (Database Creation)

**Files Modified:**
- `theauditor/indexer/runner.py:101-104` (initial schema creation)
- `theauditor/indexer/database/base_database.py:58-61` (DatabaseManager)

**Fix Applied (at source):**
```python
conn = sqlite3.connect(db_path, timeout=60)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

- [x] runner.py:101-104 - WAL at database creation (2025-11-25)
- [x] base_database.py:58-61 - WAL in DatabaseManager (2025-11-25)
- [x] deps.py (4 locations) - timeout + WAL for redundancy
- [x] vulnerability_scanner.py:69 - timeout + WAL for redundancy
- [x] Verified: `aud full` with Track C completed successfully (19.1s)

### Bug 2: OSError in Print (Windows Console)

**Root Cause:** Windows console buffer becomes unstable with `flush=True` under heavy parallel load.

**Files Modified:**
- `theauditor/events.py` (2 locations)

**Fix Applied:**
```python
try:
    print(f"[COMPLETED] {track_name} ({elapsed:.1f}s)", flush=True)
except OSError:
    pass  # Windows console buffer issue - ignore
```

- [x] events.py:83-88 - on_parallel_track_start wrapped (2025-11-25)
- [x] events.py:90-95 - on_parallel_track_complete wrapped (2025-11-25)

### Verification

- [x] Syntax check passed for all modified files
- [x] TheAuditor: `aud full` with Track C completed (202.5s, all 25 phases)
- [x] PlantFlow: `aud full` completed (191.0s, all 25 phases) - **CONFIRMED FIX WORKS**

**SIDE QUEST COMPLETED**: 2025-11-25

---

## Phase 6: Cleanup

### Task 6.1: Update Documentation

**Update CLAUDE.md:**
- Change "250 tables" to "109 tables"
- Change "149 Python tables" to "8 Python tables"

- [ ] Documentation updated

### Task 6.2: Final Commit

```bash
cd C:/Users/santa/Desktop/TheAuditor
git add -A
git commit -m "feat(schema): delete 141 orphan Python tables

Consolidate Python schema from 149 tables to 8 tables.
All deleted tables had zero consumers (no SELECT queries).

Tables KEPT (8):
- python_decorators (interceptors, deadcode, query)
- python_django_middleware (interceptors)
- python_django_views (interceptors)
- python_orm_fields (graphql overfetch)
- python_orm_models (overfetch, taint discovery)
- python_package_configs (deps, blueprint)
- python_routes (boundary, deadcode, query)
- python_validators (taint discovery)

Extractor files DELETED (19):
- advanced_extractors.py, async_extractors.py, behavioral_extractors.py
- class_feature_extractors.py, collection_extractors.py, control_flow_extractors.py
- data_flow_extractors.py, django_advanced_extractors.py, exception_flow_extractors.py
- framework_extractors.py, fundamental_extractors.py, operator_extractors.py
- performance_extractors.py, protocol_extractors.py, security_extractors.py
- state_mutation_extractors.py, stdlib_pattern_extractors.py, testing_extractors.py
- type_extractors.py

Impact:
- TABLES: 250 -> 109 (-141)
- Memory: ~56% fewer tables loaded
- Schema complexity: 95% reduction in Python tables

Breaking changes: NONE (deleted tables had no consumers)"
```

- [ ] Changes committed

---

## Post-Implementation Audit Checklist

- [ ] `len(TABLES) == 109`
- [ ] `len(PYTHON_TABLES) == 8`
- [ ] `len(ps.handlers) == 8` (PythonStorage)
- [ ] 19 extractor files deleted
- [ ] 5 extractor files partially cleaned
- [ ] `aud full --offline` passes
- [ ] `pytest` passes
- [ ] All consumers work (interceptors, taint, boundary)
- [ ] Generated code regenerated
- [ ] Documentation updated

### Rollback Command (if needed)

```bash
git revert HEAD
rm -f .pf/repo_index.db
aud full --offline
```

---

## Summary

| Phase | Tasks | Risk |
|-------|-------|------|
| 0. Verification | Confirm no hidden consumers | LOW |
| 1. Schema | Delete 141 table definitions | MEDIUM |
| 2. Storage | Delete 141 handlers | LOW |
| 3. Extractors | Delete 19 files, modify 5 files | MEDIUM |
| 4. Codegen | Regenerate generated code | LOW |
| 5. Verification | Full pipeline test | LOW |
| 6. Cleanup | Documentation, commit | LOW |

**Total estimated deletions**: ~8000 lines of code
