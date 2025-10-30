# Proposal: Refactor Schema Language Split

**Change ID**: `refactor-schema-language-split`
**Type**: Architecture Refactor
**Status**: Pending Approval
**Risk Level**: HIGH (Core Infrastructure)
**Breaking Change**: NO

## Why

**Problem**: schema.py has reached 2146 lines and is becoming unmanageable:
- Single monolithic file mixing Python, Node, Rust, Infrastructure, and Planning schemas
- Difficult to navigate (70 table definitions)
- Hard to maintain (language-specific changes touch unrelated code)
- Poor discoverability (developers must scroll through entire file)
- Cannot easily read schema for specific language (all mixed together)

**Impact**: As codebase grows, schema.py will continue to expand. Rust maturity, additional frameworks, and new infrastructure providers will add more tables. Without modularization, maintenance becomes exponentially harder.

**Trigger**: User request for language-specific schema split to improve maintainability.

## What Changes

### High-Level Architecture

**BEFORE** (Current):
```
theauditor/indexer/
└── schema.py (2146 lines)
    └── 70 tables + utilities (all mixed)
```

**AFTER** (Proposed):
```
theauditor/indexer/
├── schema.py (100 lines) → STUB (maintains backward compatibility)
└── schemas/
    ├── __init__.py (empty)
    ├── utils.py (250 lines)           → Column, ForeignKey, TableSchema classes
    ├── core_schema.py (700 lines)     → 26 tables (used by ALL languages)
    ├── python_schema.py (150 lines)   → 5 tables (Python-specific)
    ├── node_schema.py (600 lines)     → 22 tables (Node/JS/React/Vue/TS)
    ├── infrastructure_schema.py (350) → 12 tables (Docker/Terraform/CDK)
    └── planning_schema.py (100 lines) → 5 tables (Meta-system)
```

### Detailed Changes

**1. New Directory Structure**:
- Create `theauditor/indexer/schemas/` directory
- Create 6 new Python modules (utils, core, python, node, infrastructure, planning)

**2. Table Distribution**:
- **Core (26 tables)**: symbols, assignments, function_call_args, function_returns, sql_queries, jwt_patterns, cfg_blocks, findings_consolidated, etc.
  - Rationale: Used by ALL languages (Python + Node + Rust)
- **Python (5 tables)**: python_orm_models, python_orm_fields, python_routes, python_blueprints, python_validators
  - Rationale: Flask/FastAPI/Django/SQLAlchemy/Pydantic specific
- **Node (22 tables)**: react_components, vue_components, type_annotations, api_endpoints, class_properties, etc.
  - Rationale: React/Vue/TypeScript/Express/Sequelize/Prisma specific
- **Infrastructure (12 tables)**: docker_images, compose_services, terraform_resources, cdk_constructs, etc.
  - Rationale: DevOps/IaC analysis (Docker/Terraform/CDK/Nginx)
- **Planning (5 tables)**: plans, plan_tasks, plan_specs, code_snapshots, code_diffs
  - Rationale: Meta-system for planning database

**3. Stub Pattern**:
- Replace schema.py with 100-line stub
- Stub imports all language-specific TABLES dicts
- Merges into single `TABLES` registry
- Re-exports ALL utilities (build_query, Column, TableSchema, etc.)
- **ZERO breaking changes** - all imports continue to work

**4. Shared Tables**:
- Tables used by BOTH Python AND Node placed in core_schema.py:
  - `sql_queries` (SQLAlchemy + Sequelize raw queries)
  - `jwt_patterns` (PyJWT + jsonwebtoken)
  - `orm_relationships` (Django + Sequelize associations)
  - `validation_framework_usage` (Pydantic + Zod/Joi/Yup)

**5. Backward Compatibility**:
```python
# BEFORE and AFTER - IDENTICAL
from theauditor.indexer.schema import TABLES, build_query, Column

# All 50 consumer files continue to work with NO changes
```

## Impact

### Affected Files

**Modified (1 file)**:
- `theauditor/indexer/schema.py` (2146→100 lines) - Converted to stub

**Created (7 files)**:
- `theauditor/indexer/schemas/__init__.py` (empty)
- `theauditor/indexer/schemas/utils.py` (250 lines)
- `theauditor/indexer/schemas/core_schema.py` (700 lines)
- `theauditor/indexer/schemas/python_schema.py` (150 lines)
- `theauditor/indexer/schemas/node_schema.py` (600 lines)
- `theauditor/indexer/schemas/infrastructure_schema.py` (350 lines)
- `theauditor/indexer/schemas/planning_schema.py` (100 lines)

**Impacted (50 files - NO changes required)**:
- Rules: 27 files (auth, orm, deployment, frameworks, dependency, python, node)
- Taint: 8 files (core, interprocedural, memory_cache, propagation, etc.)
- Tests: 6 files (schema_contract, database_integration, jsx_pass, etc.)
- Commands: 3 files (index, taint)
- Planning: 1 file (manager)
- Insights: 1 file (ml)
- Extractors: 4 files (python, javascript, docker, generic)

**NOT Modified (database.py deferred to Phase 2)**:
- `theauditor/indexer/database.py` (1407 lines) - NO changes in this proposal

### Benefits

1. **Maintainability**: Developers can focus on language-specific schemas without seeing unrelated tables
2. **Discoverability**: Clear organization (python_schema.py = Python tables, node_schema.py = Node tables)
3. **Separation of Concerns**: Core vs Language-specific vs Infrastructure cleanly separated
4. **Scalability**: New languages/frameworks easily added (new module + merge in stub)
5. **Readability**: 150-700 line modules vs single 2146-line file
6. **Zero Breakage**: Stub pattern ensures 100% backward compatibility

### Risks

**HIGH RISK FACTORS**:
1. **Manual Copy-Paste**: 2146 lines → 6 files (typo risk)
   - Mitigation: Automated extraction script + diff verification
2. **Table Split Errors**: Wrong table in wrong module
   - Mitigation: Comprehensive verification.md mapping (see verification.md)
3. **Import Breakage**: 50 files depend on schema imports
   - Mitigation: Stub maintains exact import paths, verified by tests

**MEDIUM RISK FACTORS**:
1. **TABLES Registry Corruption**: Missing tables after merge
   - Mitigation: Automated test: `assert len(TABLES) == 70`
2. **Circular Imports**: utils.py imported by all modules
   - Mitigation: utils.py has NO table definitions (classes only)

**LOW RISK FACTORS**:
1. **Test Failures**: Schema contract tests may fail
   - Mitigation: Existing test suite (test_schema_contract.py)

### Non-Goals (Explicitly Out of Scope)

1. ❌ **database.py refactor** - Deferred to separate Phase 2 proposal
2. ❌ **Type hints** - Enhancement, not refactor
3. ❌ **Schema validation** - Already exists
4. ❌ **Query builder changes** - No functional changes
5. ❌ **Add new tables** - Only reorganize existing

## Validation Criteria

**MUST PASS BEFORE COMMIT**:
1. ✅ All pytest tests pass: `pytest tests/ -v`
2. ✅ TABLES registry has exactly 70 tables
3. ✅ All 50 consumers import successfully (smoke test)
4. ✅ Query builders work: `build_query('symbols', ['name'])`
5. ✅ `aud index` runs without errors
6. ✅ `aud full` runs without errors
7. ✅ Schema contract validation passes

## Rollback Plan

**Single Atomic Commit**: All changes in one commit.

**Rollback**: `git revert <commit_hash>` - Instant restore to original schema.py.

**Zero Data Loss**: Database not touched (schema refactor only).

## Dependencies

**None** - This is a pure internal refactor with no external dependencies.

## Migration Path

**For Users**: ZERO migration required. All imports work identically.

**For Developers Adding New Tables**:
```python
# BEFORE
# Add table to schema.py at bottom

# AFTER
# 1. Determine language: Python, Node, Core, or Infrastructure
# 2. Add table to appropriate schemas/*.py module
# 3. Stub automatically merges into TABLES registry
```

## Success Metrics

1. ✅ All 70 tables accessible via `TABLES` registry
2. ✅ Zero import errors across 50 consumer files
3. ✅ 100% test pass rate
4. ✅ `aud full` produces identical output before/after
5. ✅ Developers can locate tables faster (measured by "time to find table definition")

## Approval Checklist

- [ ] Architect approval (User)
- [ ] Lead Auditor approval (Gemini)
- [ ] Lead Coder verification complete (Opus)
- [ ] Risk analysis reviewed
- [ ] Test plan approved
- [ ] Rollback plan documented

## Phase 2 Preview (Separate Proposal)

**Future Work**: Split database.py using same pattern.

**Proposed Structure**:
```
database.py (STUB)
databases/
├── core_database.py (CoreDatabaseMixin)
├── python_database.py (PythonDatabaseMixin)
├── node_database.py (NodeDatabaseMixin)
└── infrastructure_database.py (InfrastructureDatabaseMixin)

class DatabaseManager(CoreDatabaseMixin, PythonDatabaseMixin, ...):
    pass
```

**Benefits**: Same as schema split (modularity, maintainability, discoverability).

**Deferred Reasons**:
1. Proves stub pattern works first (lower risk)
2. Reduces blast radius (one refactor at a time)
3. Allows lessons learned from Phase 1 to inform Phase 2

---

**Proposed By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: AWAITING ARCHITECT & AUDITOR APPROVAL
