# Proposal: Refactor Schema Language Split + Indexer Orchestrator

**Change ID**: `refactor-schema-language-split`
**Type**: Architecture Refactor
**Status**: Pending Approval
**Risk Level**: HIGH (Core Infrastructure)
**Breaking Change**: NO

## Why

**Problem 1 - Schema Monolith**: schema.py has reached 2146 lines and is becoming unmanageable:
- Single monolithic file mixing Python, Node, Rust, Infrastructure, and Planning schemas
- Difficult to navigate (70 table definitions)
- Hard to maintain (language-specific changes touch unrelated code)
- Poor discoverability (developers must scroll through entire file)
- Cannot easily read schema for specific language (all mixed together)

**Problem 2 - Indexer Orchestrator Monolith**: `theauditor/indexer/__init__.py` violates Python conventions:
- `__init__.py` contains 2021 lines of orchestration logic (should be ~10-20 lines of imports)
- Single `IndexerOrchestrator` class doing ALL language orchestration (violates SRP)
- Mixed Python/Node/Rust/Infrastructure orchestration logic in one class
- JSX dual-pass processing (218 lines, React-specific) buried in generic code
- TypeScript batch processing (Node-specific) in generic orchestrator

**Impact**: As codebase grows, both files will continue to expand. Rust maturity, additional frameworks, and new infrastructure providers will add more complexity. Without modularization, maintenance becomes exponentially harder.

**Trigger**: User request for language-specific schema split + discovery that `__init__.py` is a 2021-line code smell requiring immediate fix.

## What Changes

### High-Level Architecture

**BEFORE** (Current):
```
theauditor/indexer/
├── __init__.py (2021 lines) ← WRONG! Should be imports only
│   └── IndexerOrchestrator + all orchestration logic (mixed)
└── schema.py (2146 lines) ← Monolithic
    └── 70 tables + utilities (all mixed)
```

**AFTER** (Proposed):
```
theauditor/indexer/
├── __init__.py (20 lines) ← STUB (proper Python usage: imports only!)
│   └── Exports: IndexerOrchestrator, FileWalker, DatabaseManager
│
├── schema.py (100 lines) ← STUB (maintains backward compatibility)
│   └── Imports and merges from schemas/
│
├── schemas/
│   ├── __init__.py (empty)
│   ├── utils.py (250 lines)           → Column, ForeignKey, TableSchema classes
│   ├── core_schema.py (700 lines)     → 26 tables (used by ALL languages)
│   ├── python_schema.py (150 lines)   → 5 tables (Python-specific)
│   ├── node_schema.py (600 lines)     → 22 tables (Node/JS/React/Vue/TS)
│   ├── infrastructure_schema.py (350) → 12 tables (Docker/Terraform/CDK)
│   └── planning_schema.py (100 lines) → 5 tables (Meta-system)
│
└── orchestration/
    ├── __init__.py (empty)
    ├── core_orchestrator.py (400 lines) → BaseOrchestrator + file walking
    ├── python_orchestrator.py (200 lines) → Python framework detection
    ├── node_orchestrator.py (700 lines) → JSX dual-pass + TypeScript batch
    ├── rust_orchestrator.py (150 lines) → Rust extraction delegation
    └── infrastructure_orchestrator.py (150 lines) → Docker/Terraform/CDK
```

### Detailed Changes

**1. New Directory Structure**:
- Create `theauditor/indexer/schemas/` directory (6 modules)
- Create `theauditor/indexer/orchestration/` directory (5 modules)

**2. Schema - Table Distribution**:
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

**3. Orchestrator - Logic Distribution**:
- **Core Orchestrator (400 lines)**: BaseOrchestrator, file walking, AST caching, database coordination
  - Rationale: Used by ALL languages
- **Python Orchestrator (200 lines)**: Python framework detection (Flask/Django/FastAPI), Python extraction
  - Rationale: Python-specific orchestration
- **Node Orchestrator (700 lines)**: JSX dual-pass (lines 434-652), TypeScript batch processing, React/Vue
  - Rationale: Node-specific (largest due to JSX complexity)
- **Rust Orchestrator (150 lines)**: Rust extraction delegation
  - Rationale: Rust-specific (minimal - early stage)
- **Infrastructure Orchestrator (150 lines)**: Docker/Terraform/CDK delegation
  - Rationale: IaC analysis specific

**4. Stub Pattern** (Both Files):
- Replace schema.py with 100-line stub
- Replace `__init__.py` with 20-line stub (proper Python usage!)
- Stubs import all language-specific modules
- Merge into single registries/exports
- Re-exports ALL utilities
- **ZERO breaking changes** - all imports continue to work

**5. Shared Tables** (Schema Only):
- Tables used by BOTH Python AND Node placed in core_schema.py:
  - `sql_queries` (SQLAlchemy + Sequelize raw queries)
  - `jwt_patterns` (PyJWT + jsonwebtoken)
  - `orm_relationships` (Django + Sequelize associations)
  - `validation_framework_usage` (Pydantic + Zod/Joi/Yup)

**6. Backward Compatibility** (Both Components):
```python
# Schema - BEFORE and AFTER - IDENTICAL
from theauditor.indexer.schema import TABLES, build_query, Column

# Orchestrator - BEFORE and AFTER - IDENTICAL
from theauditor.indexer import IndexerOrchestrator, FileWalker, DatabaseManager

# All 50+ consumer files continue to work with NO changes
```

## Impact

### Affected Files

**Modified (2 files)**:
- `theauditor/indexer/schema.py` (2146→100 lines) - Converted to stub
- `theauditor/indexer/__init__.py` (2021→20 lines) - Converted to stub

**Created (13 files)**:
- `theauditor/indexer/schemas/__init__.py` (empty)
- `theauditor/indexer/schemas/utils.py` (250 lines)
- `theauditor/indexer/schemas/core_schema.py` (700 lines)
- `theauditor/indexer/schemas/python_schema.py` (150 lines)
- `theauditor/indexer/schemas/node_schema.py` (600 lines)
- `theauditor/indexer/schemas/infrastructure_schema.py` (350 lines)
- `theauditor/indexer/schemas/planning_schema.py` (100 lines)
- `theauditor/indexer/orchestration/__init__.py` (empty)
- `theauditor/indexer/orchestration/core_orchestrator.py` (400 lines)
- `theauditor/indexer/orchestration/python_orchestrator.py` (200 lines)
- `theauditor/indexer/orchestration/node_orchestrator.py` (700 lines)
- `theauditor/indexer/orchestration/rust_orchestrator.py` (150 lines)
- `theauditor/indexer/orchestration/infrastructure_orchestrator.py` (150 lines)

**Impacted (50+ files - NO changes required)**:
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

**Schema Split**:
1. **Maintainability**: Developers can focus on language-specific schemas without seeing unrelated tables
2. **Discoverability**: Clear organization (python_schema.py = Python tables, node_schema.py = Node tables)
3. **Separation of Concerns**: Core vs Language-specific vs Infrastructure cleanly separated

**Orchestrator Split**:
4. **Proper Python Usage**: `__init__.py` reduced from 2021 → 20 lines (imports only, as intended)
5. **Language Isolation**: JSX dual-pass (218 lines) clearly identified as Node-specific, not generic
6. **Fixes Code Smell**: Massive `__init__.py` is anti-pattern - now properly structured

**Combined**:
7. **Scalability**: New languages/frameworks easily added (new module + merge in stub)
8. **Readability**: 150-700 line modules vs 2000+ line monoliths
9. **Zero Breakage**: Stub pattern ensures 100% backward compatibility (both schema and orchestrator)
10. **Complete Package Refactor**: Entire indexer package now properly modularized

### Risks

**HIGH RISK FACTORS**:
1. **Manual Copy-Paste**: 4167 lines → 11 files (typo risk)
   - Mitigation: Automated extraction script + diff verification
2. **Logic Split Errors**: Wrong orchestration logic in wrong module
   - Mitigation: Comprehensive line-by-line mapping in verification.md
3. **Import Breakage**: 50+ files depend on both schema and indexer imports
   - Mitigation: Both stubs maintain exact import paths, verified by tests

**MEDIUM RISK FACTORS**:
1. **TABLES Registry Corruption**: Missing tables after merge
   - Mitigation: Automated test: `assert len(TABLES) == 70`
2. **Circular Imports**: utils.py imported by all modules
   - Mitigation: utils.py has NO table definitions (classes only)
3. **Method Resolution Order (MRO)**: Multiple inheritance via mixins in orchestrator
   - Mitigation: Python C3 linearization handles MRO, each mixin has distinct method names

**LOW RISK FACTORS**:
1. **Test Failures**: Schema contract tests may fail
   - Mitigation: Existing test suite (test_schema_contract.py)
2. **JSX Dual-Pass Logic Move**: 218 lines of critical React logic
   - Mitigation: Move as-is (no changes to logic, just location)

### Non-Goals (Explicitly Out of Scope)

1. ❌ **database.py refactor** - Deferred to separate Phase 2 proposal
2. ❌ **Extractor refactors** - Only orchestration split, not extractors themselves
3. ❌ **Type hints** - Enhancement, not refactor
4. ❌ **Schema validation** - Already exists
5. ❌ **Query builder changes** - No functional changes
6. ❌ **Add new tables** - Only reorganize existing
7. ❌ **Change orchestration logic** - Only reorganize, no functional changes

## Validation Criteria

**MUST PASS BEFORE COMMIT**:
1. ✅ All pytest tests pass: `pytest tests/ -v`
2. ✅ TABLES registry has exactly 70 tables
3. ✅ IndexerOrchestrator instantiates correctly
4. ✅ All 50+ consumers import successfully (smoke test)
5. ✅ Query builders work: `build_query('symbols', ['name'])`
6. ✅ `aud index` runs without errors (all languages)
7. ✅ `aud full` runs without errors
8. ✅ Schema contract validation passes
9. ✅ JSX dual-pass still works (critical React feature)
10. ✅ TypeScript batch processing works (function params cache)
11. ✅ Cross-file parameter resolution works (Bug #3 fix)

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

**For Developers Adding New Language Orchestration**:
```python
# BEFORE
# Add logic to IndexerOrchestrator class in __init__.py (2021 lines!)

# AFTER
# 1. Create orchestration/<language>_orchestrator.py
# 2. Add <Language>OrchestrationMixin class
# 3. Import and mix into IndexerOrchestrator in core_orchestrator.py
```

## Success Metrics

**Schema**:
1. ✅ All 70 tables accessible via `TABLES` registry
2. ✅ Query builders work identically

**Orchestrator**:
3. ✅ IndexerOrchestrator instantiates and runs identically
4. ✅ JSX dual-pass works (React-specific logic preserved)
5. ✅ TypeScript batch processing works (Node-specific logic preserved)

**Combined**:
6. ✅ Zero import errors across 50+ consumer files
7. ✅ 100% test pass rate
8. ✅ `aud full` produces identical output before/after
9. ✅ Developers can locate tables/orchestration logic faster
10. ✅ `__init__.py` reduced to proper Python usage (imports only)

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

## Summary Statistics

**Original Scope** (Schema only):
- schema.py: 2146 lines → schemas/ (6 modules, ~2150 lines)

**Extended Scope** (Schema + Orchestrator):
- schema.py: 2146 lines → schemas/ (6 modules, ~2150 lines)
- `__init__.py`: 2021 lines → orchestration/ (5 modules, ~1600 lines)
- **Total**: 4167 lines → 11 modules + 2 stubs (120 stub lines)
- **Net Lines**: ~3870 lines (7% reduction from eliminating duplication)

**Files Modified**: 2 (schema.py, `__init__.py`)
**Files Created**: 13 (7 schema modules + 6 orchestration modules)
**Files Impacted (NO changes)**: 50+

---

**Proposed By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30 (Updated: 2025-10-31 - Extended scope to include indexer orchestrator)
**Status**: AWAITING ARCHITECT & AUDITOR APPROVAL
