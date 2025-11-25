# Design: Python Orphan Table Consolidation Architecture

## Context

### Current State (Verified 2025-11-25)

```
theauditor/indexer/
    schema.py                     # Aggregates all *_TABLES dicts -> TABLES
    schemas/
        python_schema.py          # 149 tables (141 orphans, 8 used)
    storage/
        python_storage.py         # 59 handlers (51 for orphan tables)

theauditor/ast_extractors/python/
    behavioral_extractors.py      # Populates orphan tables
    class_feature_extractors.py   # Populates orphan tables
    collection_extractors.py      # Populates orphan tables
    control_flow_extractors.py    # Populates orphan tables
    data_flow_extractors.py       # Populates orphan tables
    exception_flow_extractors.py  # Populates orphan tables
    fundamental_extractors.py     # Populates orphan tables
    operator_extractors.py        # Populates orphan tables
    performance_extractors.py     # Populates orphan tables
    protocol_extractors.py        # Populates orphan tables
    security_extractors.py        # Populates orphan tables
    state_mutation_extractors.py  # Populates orphan tables
    stdlib_pattern_extractors.py  # Populates orphan tables
    type_extractors.py            # Populates orphan tables
    orm_extractors.py             # Populates USED tables
    flask_extractors.py           # Populates USED tables (partially)
    django_web_extractors.py      # Populates USED tables
    validation_extractors.py      # Populates USED tables
    core_extractors.py            # Populates USED tables (decorators)
```

### The Data Flow Problem

```
AST Parsing -> Extractors -> Storage Handlers -> Database Tables -> ???

The "???" is the problem:
- 141 tables are written to during indexing
- 0 consumers (rules, commands, taint) query these tables
- Data goes in, never comes out
```

### Polyglot Consideration

**This is Python-only**. Node/JS has 5 tables with 100% utilization - no orphans there.

No orchestrator changes needed - this only affects:
1. Python schema definitions
2. Python storage handlers
3. Python AST extractors

---

## Goals / Non-Goals

### Goals

1. **Delete orphan tables**: Remove 141 tables that are never queried
2. **Delete orphan extractors**: Remove extraction code that only populates orphan tables
3. **Delete orphan handlers**: Remove storage handlers for orphan tables
4. **Maintain functionality**: Keep the 8 tables that ARE used
5. **Reduce cognitive load**: Make Python schema navigable

### Non-Goals

1. NOT reorganizing remaining tables (separate proposal if needed)
2. NOT adding new analysis that uses orphan tables
3. NOT modifying Node/JS schema (no orphans there)
4. NOT changing core infrastructure (orchestrator, pipelines)

---

## Decisions

### Decision 1: Delete vs Archive

**Options:**
- A) DELETE tables entirely from schema
- B) ARCHIVE tables (comment out, keep code)
- C) MOVE tables to "dormant_schema.py"

**Decision: A) DELETE**

**Rationale:**
- No consumers = no value
- Archived code rots and misleads
- If needed later, re-add with actual consumer
- Git history preserves everything anyway

### Decision 2: Extractor Handling

**Options:**
- A) DELETE extractor files that only populate orphan tables
- B) KEEP extractors but skip calling them
- C) MODIFY extractors to not extract orphan patterns

**Decision: A) DELETE + C) MODIFY for mixed files**

**Rationale:**
- Dead code is technical debt
- Skipping calls still has maintenance burden
- If pattern needed later, re-implement with consumer

**Extractor Files to DELETE (19 files - verified from python_impl.py analysis):**
```
theauditor/ast_extractors/python/
    advanced_extractors.py       # 8 orphan tables (namespace_packages, cached_property, etc.)
    async_extractors.py          # 3 orphan tables (async_functions, await_expressions, etc.)
    behavioral_extractors.py     # 4 orphan tables (recursion_patterns, generator_yields, etc.)
    class_feature_extractors.py  # 10 orphan tables (metaclasses, descriptors, etc.)
    collection_extractors.py     # 8 orphan tables (dict_operations, list_mutations, etc.)
    control_flow_extractors.py   # 10 orphan tables (for_loops, while_loops, etc.)
    data_flow_extractors.py      # 5 orphan tables (io_operations, closure_captures, etc.)
    django_advanced_extractors.py # 4 orphan tables (django_signals, django_receivers, etc.)
    exception_flow_extractors.py # 4 orphan tables (exception_raises, exception_catches, etc.)
    framework_extractors.py      # 3 orphan tables (celery_tasks, celery_task_calls, etc.)
    fundamental_extractors.py    # 8 orphan tables (comprehensions, lambda_functions, etc.)
    operator_extractors.py       # 6 orphan tables (operators, membership_tests, etc.)
    performance_extractors.py    # 3 orphan tables (loop_complexity, resource_usage, etc.)
    protocol_extractors.py       # 10 orphan tables (iterator_protocol, container_protocol, etc.)
    security_extractors.py       # 8 orphan tables (auth_decorators, sql_injection, etc.)
    state_mutation_extractors.py # 5 orphan tables (instance_mutations, class_mutations, etc.)
    stdlib_pattern_extractors.py # 8 orphan tables (regex_patterns, json_operations, etc.)
    testing_extractors.py        # 8 orphan tables (pytest_fixtures, mock_patterns, etc.)
    type_extractors.py           # 5 orphan tables (protocols, generics, etc.)
```

**Extractor Files to KEEP unchanged (3 files - no python_* tables):**
```
theauditor/ast_extractors/python/
    cdk_extractor.py             # outputs cdk_constructs (infrastructure table)
    cfg_extractor.py             # outputs cfg (core table)
    task_graphql_extractors.py   # outputs graphql_* tables
```

**Extractor Files to KEEP with PARTIAL CLEANUP (5 files - mixed used/orphan):**
```
theauditor/ast_extractors/python/
    core_extractors.py           # KEEP: python_decorators
                                 # REMOVE: python_context_managers, python_generators

    django_web_extractors.py     # KEEP: python_django_middleware, python_django_views
                                 # REMOVE: python_django_forms, python_django_form_fields, python_django_admin

    flask_extractors.py          # KEEP: python_routes
                                 # REMOVE: python_flask_apps, python_flask_extensions, python_flask_hooks,
                                 #         python_flask_error_handlers, python_flask_websockets,
                                 #         python_flask_cli_commands, python_flask_cors,
                                 #         python_flask_rate_limits, python_flask_cache

    orm_extractors.py            # KEEP: python_orm_models, python_orm_fields
                                 # REMOVE: python_blueprints

    validation_extractors.py     # KEEP: python_validators
                                 # REMOVE: python_marshmallow_schemas, python_marshmallow_fields,
                                 #         python_drf_serializers, python_drf_serializer_fields,
                                 #         python_wtforms_forms, python_wtforms_fields
```

### Decision 3: Storage Handler Consolidation

**Current**: `python_storage.py` has 59 handlers

**After**: Reduce to ~8 handlers for used tables

**Handlers to KEEP:**
```python
self.handlers = {
    'python_decorators': self._store_python_decorators,
    'python_django_middleware': self._store_python_django_middleware,
    'python_django_views': self._store_python_django_views,
    'python_orm_fields': self._store_python_orm_fields,
    'python_orm_models': self._store_python_orm_models,
    'python_package_configs': self._store_python_package_configs,
    'python_routes': self._store_python_routes,
    'python_validators': self._store_python_validators,
}
```

### Decision 4: Schema Assertion Update

**Current**: `assert len(TABLES) == 250`

**After**: `assert len(TABLES) == 109` (250 - 141 = 109)

**Breakdown of 109:**
```
CORE_TABLES:           24  (unchanged)
SECURITY_TABLES:        7  (unchanged)
FRAMEWORKS_TABLES:      6  (unchanged)
PYTHON_TABLES:          8  (was 149, now 8)
NODE_TABLES:           29  (unchanged)
INFRASTRUCTURE_TABLES: 18  (unchanged)
PLANNING_TABLES:        9  (unchanged)
GRAPHQL_TABLES:         8  (unchanged)
--------------------------
TOTAL:                109
```

### Decision 5: Generated Code Handling

**Files to regenerate:**
- `theauditor/indexer/schemas/generated_types.py`
- `theauditor/indexer/schemas/generated_accessors.py`
- `theauditor/indexer/schemas/generated_cache.py`

**Method**: Run `python -m theauditor.indexer.schemas.codegen` after schema changes

---

## Architecture After Change

### Schema Layer

```
theauditor/indexer/schemas/
    python_schema.py          # 8 tables (was 149)

    # PYTHON_TABLES dict:
    {
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

### Extractor Layer

```
theauditor/ast_extractors/python/
    __init__.py               # Update imports
    utils/                    # KEEP (shared utilities)
    orm_extractors.py         # KEEP
    flask_extractors.py       # KEEP (or merge into routes_extractors.py)
    django_web_extractors.py  # KEEP
    validation_extractors.py  # KEEP
    core_extractors.py        # KEEP (decorators, package_configs)
    # DELETE everything else
```

### Storage Layer

```
theauditor/indexer/storage/python_storage.py
    # Handler count: 8 (was 59)
    # File size: ~200 lines (was 2,486 lines)
```

---

## Risks / Trade-offs

### Risk 1: Hidden Consumer Discovery

**Risk**: A consumer exists that we didn't find
**Likelihood**: LOW (comprehensive grep performed)
**Impact**: HIGH (queries would fail)
**Mitigation**:
1. Run full test suite before merge
2. Run `aud full --offline` on real project
3. Search for dynamic table references

### Risk 2: Future Feature Loss

**Risk**: Deleted tables needed for future feature
**Likelihood**: MEDIUM (some patterns are useful)
**Impact**: LOW (can re-add later)
**Mitigation**:
1. Git history preserves all code
2. Document deletion rationale
3. Re-add when consumer exists

### Risk 3: Extractor Chain Breakage

**Risk**: Deleting extractor breaks other extractors
**Likelihood**: LOW (extractors are independent)
**Impact**: MEDIUM (indexing fails)
**Mitigation**:
1. Check `python_impl.py` for extractor orchestration
2. Test extraction after each file deletion
3. Update `__init__.py` imports

### Risk 4: Cache Invalidation

**Risk**: Old cache has deleted tables, new code doesn't
**Likelihood**: HIGH (certain to happen)
**Impact**: LOW (just re-index)
**Mitigation**:
1. Delete `.pf/repo_index.db` after schema change
2. Document in release notes

---

## Migration Strategy

### Phase 1: Schema Cleanup (Non-Breaking)

1. Delete 141 table definitions from `python_schema.py`
2. Update `PYTHON_TABLES` dict to only include 8 tables
3. Regenerate `generated_*.py` files
4. Update `schema.py` assertion: `assert len(TABLES) == 109`

**Verification**: `python -c "from theauditor.indexer.schema import TABLES; print(len(TABLES))"`

### Phase 2: Storage Cleanup (Non-Breaking)

1. Delete 51 storage handler methods from `python_storage.py`
2. Update `self.handlers` dict to only include 8 handlers

**Verification**: `python -c "from theauditor.indexer.storage import UnifiedStorage; s = UnifiedStorage(None, {}); print(len(s.python.handlers))"`

### Phase 3: Extractor Cleanup (Potentially Breaking)

1. Delete 14 extractor files from `theauditor/ast_extractors/python/`
2. Update `python_impl.py` to not call deleted extractors
3. Update `__init__.py` to not import deleted extractors

**Verification**: `aud full --offline` on test project

### Phase 4: Final Verification

1. Run full test suite
2. Run `aud full --offline` on TheAuditor itself
3. Verify 8 Python tables exist in `repo_index.db`
4. Verify 0 orphan tables exist

---

## Dependency Analysis

### What Depends on Deleted Tables

**NOTHING** - that's why they're orphans.

### What Depends on Kept Tables

| Table | Consumer | File |
|-------|----------|------|
| `python_decorators` | InterceptorStrategy | `graph/strategies/interceptors.py:281-348` |
| `python_decorators` | DeadcodeGraph | `context/deadcode_graph.py` |
| `python_decorators` | CodeQueryEngine | `context/query.py` |
| `python_django_middleware` | InterceptorStrategy | `graph/strategies/interceptors.py:350-449` |
| `python_django_views` | InterceptorStrategy | `graph/strategies/interceptors.py:350-449` |
| `python_orm_fields` | GraphQL Overfetch | `rules/graphql/overfetch.py` |
| `python_orm_models` | GraphQL Overfetch | `rules/graphql/overfetch.py` |
| `python_orm_models` | TaintDiscovery | `taint/discovery.py` |
| `python_package_configs` | DepsCommand | `deps.py` |
| `python_package_configs` | BlueprintCommand | `commands/blueprint.py` |
| `python_routes` | BoundaryAnalyzer | `boundaries/boundary_analyzer.py` |
| `python_routes` | DeadcodeGraph | `context/deadcode_graph.py` |
| `python_routes` | CodeQueryEngine | `context/query.py` |
| `python_validators` | TaintDiscovery | `taint/discovery.py` (via cache) |

---

## Open Questions (Resolved)

### Q1: Keep security tables for future rules?

**Answer**: NO. Delete them. If rules are needed:
1. Re-add table with consumer
2. Follow "no consumer = no table" principle
3. Prevents dead code accumulation

### Q2: Keep testing tables for pytest analysis?

**Answer**: NO. Delete them. No pytest analysis exists today.

### Q3: What about causal learning tables?

**Answer**: DELETE. The ML pipeline doesn't exist. Re-add when it does.

### Q4: Should we keep python_blueprints?

**Answer**: Investigate. It's in `flask_extractors.py` alongside `python_routes`.
- `python_routes`: USED by boundary analyzer
- `python_blueprints`: NOT USED

**Decision**: Delete `python_blueprints` too. Update flask_extractors.py to only extract routes.

---

## Verification Commands

```bash
# Check table count
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
print(f'TABLES: {len(TABLES)} (expect 109)')
print(f'PYTHON_TABLES: {len(PYTHON_TABLES)} (expect 8)')
"

# Check storage handlers
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
from theauditor.indexer.storage.python_storage import PythonStorage
ps = PythonStorage(None, {})
print(f'Python handlers: {len(ps.handlers)} (expect 8)')
"

# Full pipeline test
aud full --offline

# Unit tests
pytest tests/test_code_snippets.py tests/test_explain_command.py -v --tb=short
```
