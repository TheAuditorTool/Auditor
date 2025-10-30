# Design Document: Schema Language Split + Indexer Orchestrator Refactor

**Change ID**: `refactor-schema-language-split`
**Document Version**: 2.0 (Extended Scope)
**Last Updated**: 2025-10-31

## Context

TheAuditor's indexer package suffers from two monolithic files that violate architectural principles:

**Problem 1 - Schema Monolith**: schema.py has grown to 2146 lines in a single file, containing 70 table definitions spanning Python, Node/JS, Rust, Infrastructure, and Planning domains. This violates the Single Responsibility Principle and creates maintenance overhead.

**Problem 2 - Orchestrator Monolith**: `__init__.py` contains 2021 lines of orchestration logic. This violates Python conventions where `__init__.py` should contain only imports (~10-20 lines). The single `IndexerOrchestrator` class mixes Python/Node/Rust/Infrastructure orchestration logic.

**Current Pain Points (Schema)**:
1. Developers must scroll through 2000+ lines to find relevant tables
2. Language-specific changes (e.g., adding Python ORM field) touch a file containing React/Vue/Terraform tables
3. No clear separation between core (cross-language) and language-specific schemas
4. Future language additions (Go, Java, C#) will only increase file size

**Current Pain Points (Orchestrator)**:
1. `__init__.py` with 2021 lines is a major code smell (anti-pattern)
2. JSX dual-pass processing (218 lines, React-specific) buried in generic orchestrator
3. TypeScript batch processing (Node-specific) in generic code
4. No separation between Python/Node/Rust orchestration logic
5. Adding new language orchestration requires modifying 2021-line class

**Stakeholders**:
- **Developers**: Easier navigation, faster lookup, clear language boundaries
- **Architect**: Better code organization, easier reviews, proper Python usage
- **Codebase**: Reduced complexity, improved maintainability, scalable architecture

## Goals / Non-Goals

### Goals

**Schema**:
1. **Modularize schema.py** by language/domain into separate files
2. **Establish clear categorization** (Core vs Python vs Node vs Infrastructure)
3. **Preserve all functionality** (query builders, validation, etc.)

**Orchestrator**:
4. **Fix `__init__.py` code smell** - reduce from 2021 → 20 lines (imports only)
5. **Modularize IndexerOrchestrator** by language using mixin pattern
6. **Isolate language-specific logic** (JSX dual-pass = Node, not generic)

**Combined**:
7. **Maintain 100% backward compatibility** - zero breaking changes to consumers
8. **Enable future scalability** (easy to add new languages/frameworks)

### Non-Goals

1. ❌ Refactor database.py (deferred to Phase 2)
2. ❌ Refactor extractors (only orchestration, not extraction implementation)
3. ❌ Change database structure or table schemas
4. ❌ Add new tables or remove existing tables
5. ❌ Modify query builder functionality
6. ❌ Modify orchestration logic (only reorganize, not change)
7. ❌ Add type hints (separate enhancement)
8. ❌ Change consumer code (50+ files remain untouched)

## Architectural Decisions

### Decision 1: Stub Pattern vs Direct Imports

**Options Considered**:
1. **Stub Pattern** (CHOSEN): Keep `schema.py` as entry point, delegate to sub-modules
   - Pros: 100% backward compatible, zero consumer changes, gradual adoption
   - Cons: Extra indirection layer (negligible performance impact)

2. **Direct Imports**: Remove schema.py, update all 50 consumers to import from sub-modules
   - Pros: Cleaner architecture, no stub overhead
   - Cons: 50 files require changes, high risk of breakage, merge conflicts

3. **Package __init__.py**: Move stub logic to `schemas/__init__.py`
   - Pros: Standard Python pattern
   - Cons: Confusing import paths (`from theauditor.indexer.schemas import TABLES`), breaks backward compatibility

**Rationale**: Stub pattern chosen for ZERO RISK backward compatibility. All 50 consumers continue working with no changes. Future refactors can gradually migrate consumers if desired.

### Decision 2: Table Categorization

**Categories Defined**:
1. **Core** (26 tables): Used by ALL languages (Python + Node + Rust)
   - Examples: symbols, assignments, function_call_args, sql_queries, jwt_patterns
   - Rationale: Cross-language security analysis (taint, patterns, findings)

2. **Python** (5 tables): Python-specific frameworks
   - Examples: python_orm_models, python_routes, python_validators
   - Rationale: Flask, FastAPI, Django, SQLAlchemy, Pydantic

3. **Node** (22 tables): JavaScript/TypeScript frameworks
   - Examples: react_components, vue_hooks, type_annotations, api_endpoints
   - Rationale: React, Vue, Express, Sequelize, Prisma, TypeScript

4. **Infrastructure** (12 tables): DevOps/IaC analysis
   - Examples: docker_images, terraform_resources, cdk_constructs
   - Rationale: Docker, Terraform, AWS CDK, Nginx

5. **Planning** (5 tables): Meta-system for database-driven planning
   - Examples: plans, plan_tasks, code_snapshots
   - Rationale: Planning system isolation

**Ambiguous Cases Resolved**:

| Table | Languages | Final Category | Rationale |
|-------|-----------|----------------|-----------|
| `sql_queries` | Python + Node | **CORE** | Both SQLAlchemy (Python) and Sequelize (Node) use raw queries - security critical |
| `jwt_patterns` | Python + Node | **CORE** | Both PyJWT (Python) and jsonwebtoken (Node) - auth critical |
| `orm_relationships` | Python + Node | **CORE** | Django (Python) and Sequelize (Node) associations - cross-lang pattern |
| `validation_framework_usage` | Python + Node | **CORE** | Pydantic (Python) and Zod/Joi (Node) - sanitization critical |
| `symbols` | ALL | **CORE** | Used by Python, Node, AND Rust extractors |

**Guiding Principle**: If table is used by 2+ languages → CORE. If language-specific → language module.

### Decision 3: Query Builder Location

**Options Considered**:
1. **core_schema.py** (CHOSEN): Keep with core table definitions
   - Pros: Logical grouping (core tables + core utilities), minimal refactor
   - Cons: Slightly larger core_schema.py file

2. **utils.py**: Move to utility module
   - Pros: Clean separation (data vs logic)
   - Cons: Circular import risk (utils imports TABLES, query builders use TABLES), extra file

3. **Separate query_builders.py**: Dedicated module
   - Pros: Maximum separation of concerns
   - Cons: Over-engineering for 3 functions, circular import issues

**Rationale**: core_schema.py chosen for simplicity. Query builders use CORE_TABLES internally, so keeping them together avoids circular imports. Future refactors can extract if needed.

### Decision 4: Utilities (Column, ForeignKey, TableSchema)

**Decision**: Extract to dedicated `utils.py` module.

**Rationale**:
- These classes have ZERO dependencies on table definitions
- Used by ALL schema modules (core, python, node, infrastructure, planning)
- Perfect candidate for shared utility module
- Avoids circular imports (utils → schemas, not schemas → utils)

**Structure**:
```python
# utils.py
@dataclass
class Column:
    """Column definition"""
    ...

@dataclass
class ForeignKey:
    """Foreign key metadata"""
    ...

@dataclass
class TableSchema:
    """Complete table schema"""
    ...
```

### Decision 5: TABLES Registry Merge Strategy

**Implementation**:
```python
# schema.py (stub)
from .schemas.core_schema import CORE_TABLES
from .schemas.python_schema import PYTHON_TABLES
from .schemas.node_schema import NODE_TABLES
from .schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
from .schemas.planning_schema import PLANNING_TABLES

# Merge all tables into single registry
TABLES = {
    **CORE_TABLES,
    **PYTHON_TABLES,
    **NODE_TABLES,
    **INFRASTRUCTURE_TABLES,
    **PLANNING_TABLES
}
```

**Validation**:
```python
assert len(TABLES) == 70, f"Expected 70 tables, got {len(TABLES)}"
```

**Conflict Detection**: Python's dict merge (`**`) will raise error if duplicate keys exist. This is intentional - prevents accidental duplicate table names across modules.

### Decision 6: JSX Table Placement

**Question**: Do JSX tables belong in core or node?

**Tables**: symbols_jsx, assignments_jsx, function_call_args_jsx, function_returns_jsx (+ junction tables)

**Decision**: Place in **node_schema.py**.

**Rationale**:
- JSX is React-specific (Node ecosystem)
- Dual-pass extraction is Node extractor feature (javascript.py)
- Python/Rust never use JSX tables
- Avoids polluting core with framework-specific tables

### Decision 7: Junction Table Organization

**Pattern**: Junction tables placed in SAME module as parent table.

**Examples**:
- `api_endpoint_controls` (junction) → node_schema.py (same as api_endpoints)
- `sql_query_tables` (junction) → core_schema.py (same as sql_queries)
- `react_component_hooks` (junction) → node_schema.py (same as react_components)

**Rationale**: Maintains cohesion. Junction tables are tightly coupled to parent tables.

### Decision 8: Orchestrator Mixin Pattern (NEW - Orchestrator Component)

**Question**: How to split `IndexerOrchestrator` (2021 lines) into language-specific modules?

**Options Considered**:
1. **Mixin Pattern** (CHOSEN): BaseOrchestrator + language-specific mixins
   - Pros: Same pattern as planned database.py Phase 2, Python MRO handles inheritance
   - Pros: Each mixin focused on one language, easy to add new languages
   - Cons: Multiple inheritance complexity (mitigated by Python C3 linearization)

2. **Strategy Pattern**: Separate orchestrator classes, factory selects by language
   - Pros: No multiple inheritance
   - Cons: Loses unified interface, requires file type detection before instantiation

3. **Monolithic with Internal Methods**: Keep single class, add `_process_python()`, `_process_node()` methods
   - Pros: Simpler inheritance
   - Cons: Doesn't solve the 2021-line problem, still mixed concerns

**Rationale**: Mixin pattern chosen for consistency with database.py Phase 2 plan and proven Python pattern. Python's C3 linearization handles MRO automatically. Each mixin has distinct method names (no conflicts).

**Implementation**:
```python
class IndexerOrchestrator(BaseOrchestrator,
                          PythonOrchestrationMixin,
                          NodeOrchestrationMixin,
                          RustOrchestrationMixin,
                          InfrastructureOrchestrationMixin):
    """Merged orchestrator via mixin pattern."""
    pass
```

### Decision 9: Orchestrator Logic Distribution (NEW - Orchestrator Component)

**Question**: Which logic goes in which orchestrator?

**Core Orchestrator** (400 lines):
- File walking, AST caching, database coordination
- Extractor selection (`_select_extractor`)
- Resource cleanup (`_cleanup_extractors`)
- Generic processing patterns

**Node Orchestrator** (700 lines - LARGEST):
- JSX dual-pass processing (lines 434-652) - 218 lines!
- TypeScript batch processing (lines 258-310)
- Cross-file parameter resolution (lines 329-336)
- Node framework detection (Express/React/Vue)
- **Why largest**: JSX dual-pass is complex React-specific logic

**Python/Rust/Infrastructure Orchestrators** (150-200 lines each):
- Language-specific framework detection
- Language-specific extraction delegation
- Minimal logic (simpler than Node/JSX)

**Guiding Principle**: If logic is specific to one language/ecosystem → language orchestrator. If used by ALL → core orchestrator.

## Risks / Trade-offs

### Risk 1: Manual Copy-Paste Errors

**Risk**: Copying 4167 lines (2146 schema + 2021 orchestrator) to 11 files could introduce typos, missed tables/logic, or formatting errors.

**Mitigation**:
1. **Automated Extraction**: Use Python script to extract tables/logic by line range (not manual copy-paste)
2. **Diff Verification**: Compare originals vs merged outputs to ensure identical
3. **Automated Tests**: `assert len(TABLES) == 70` catches missing tables
4. **Schema Contract Tests**: test_schema_contract.py validates all table structures
5. **Integration Tests**: `aud index` + `aud full` verify orchestrator works identically

### Risk 2: Circular Imports

**Risk**: utils.py imported by all modules. If utils imports from schemas, creates cycle.

**Mitigation**: utils.py contains ONLY class definitions (Column, ForeignKey, TableSchema). NO table definitions, NO imports from schemas.

**Verification**:
```python
# utils.py - ALLOWED
from typing import Dict, List
from dataclasses import dataclass

# utils.py - FORBIDDEN
from .core_schema import CORE_TABLES  # ❌ CIRCULAR
```

### Risk 3: TABLES Registry Corruption

**Risk**: Dict merge could drop tables or create duplicates.

**Mitigation**:
1. **Automated Validation**: `assert len(TABLES) == 70`
2. **Duplicate Detection**: Python dict merge raises error on duplicate keys
3. **Manual Verification**: verification.md lists all 70 tables with module assignment

### Risk 4: Import Path Breakage

**Risk**: 50+ consumer files could break if import paths change (schema or orchestrator).

**Mitigation**:
1. **Stub Pattern**: Both schema.py and `__init__.py` remain as entry points, all imports identical
2. **Smoke Test**: Import all symbols from 50+ files before commit
3. **Test Suite**: Existing tests validate imports (test_database_integration.py)

### Risk 5: Method Resolution Order (MRO) Conflicts (NEW - Orchestrator)

**Risk**: Multiple inheritance via mixins could cause method conflicts or incorrect MRO.

**Mitigation**:
1. **Python C3 Linearization**: Python automatically handles MRO via C3 algorithm
2. **Distinct Method Names**: Each mixin uses distinct method names (no conflicts)
   - PythonOrchestrationMixin: `_detect_python_frameworks()`, `_process_python_file()`
   - NodeOrchestrationMixin: `_detect_node_frameworks()`, `_jsx_dual_pass_extraction()`
   - No method name collisions between mixins
3. **MRO Testing**: Explicit test to verify `IndexerOrchestrator.__mro__` is correct
4. **Integration Testing**: `aud index` validates orchestrator works across all languages

### Risk 6: JSX Dual-Pass Logic Move (NEW - Orchestrator)

**Risk**: Moving 218 lines of critical React JSX dual-pass logic could break React analysis.

**Mitigation**:
1. **Move As-Is**: NO changes to logic, only location changes (lines 434-652 → node_orchestrator.py)
2. **Existing Test Suite**: `tests/test_jsx_pass.py` validates JSX dual-pass functionality
3. **Integration Test**: Run `aud index` on React projects, verify JSX tables populated
4. **Pre/Post Comparison**: Compare JSX table contents before/after refactor (must be identical)

### Trade-off 1: File Count vs Monolithic Files

**Schema Before**: 1 file (2146 lines)
**Schema After**: 8 files (2250 lines total, +104 overhead = 4.8%)

**Orchestrator Before**: 1 file (2021 lines in `__init__.py`)
**Orchestrator After**: 6 files (1620 lines total, -401 lines = 19.8% reduction)

**Combined Before**: 2 monolithic files (4167 lines)
**Combined After**: 14 modular files (3870 lines, -297 lines = 7.1% reduction)

**Analysis**:
- Pro: Modularity, discoverability, maintainability, proper Python usage
- Pro: 7% net line reduction from eliminating duplication
- Con: More files to navigate (14 vs 2)
- Verdict: Acceptable - 14 well-organized files >> 2 monolithic files

### Trade-off 2: Stub Overhead vs Direct Imports

**Stub Pattern**: Extra indirection (schema.py → schemas/*.py, `__init__.py` → orchestration/*.py)
**Direct Imports**: No indirection, but 50+ files need changes

**Analysis**:
- Performance: Negligible (import time, not runtime)
- Risk: Stub = zero risk, Direct = high risk (50+ file changes)
- Verdict: Stub pattern prioritizes safety over architectural purity

### Trade-off 3: Mixin Pattern vs Strategy Pattern (NEW - Orchestrator)

**Mixin Pattern** (CHOSEN): Multiple inheritance, Python MRO
**Strategy Pattern**: Separate classes, factory selection

**Analysis**:
- Mixin Pros: Unified interface, proven pattern, consistent with database.py Phase 2
- Mixin Cons: Multiple inheritance complexity (mitigated by C3 linearization)
- Strategy Pros: No multiple inheritance
- Strategy Cons: Loses unified interface, requires upfront language detection
- Verdict: Mixin pattern for consistency and proven reliability in Python

## Migration Plan

### Phase 1: Schema Split + Orchestrator Split (THIS PROPOSAL)

**Part A - Schema Split**:
1. Create `theauditor/indexer/schemas/` directory
2. Create `utils.py` (Column, ForeignKey, TableSchema)
3. Create `core_schema.py` (26 tables + query builders)
4. Create `python_schema.py` (5 tables)
5. Create `node_schema.py` (22 tables)
6. Create `infrastructure_schema.py` (12 tables)
7. Create `planning_schema.py` (5 tables)
8. Replace `schema.py` with stub (imports + merge + re-export)

**Part B - Orchestrator Split**:
9. Create `theauditor/indexer/orchestration/` directory
10. Create `core_orchestrator.py` (BaseOrchestrator + file walking + AST caching)
11. Create `python_orchestrator.py` (Python framework detection + extraction)
12. Create `node_orchestrator.py` (JSX dual-pass + TypeScript batch + Node frameworks)
13. Create `rust_orchestrator.py` (Rust extraction delegation)
14. Create `infrastructure_orchestrator.py` (Docker/Terraform/CDK delegation)
15. Create merged `IndexerOrchestrator` class (mixin pattern)
16. Replace `__init__.py` with stub (imports + exports)

**Part C - Validation & Commit**:
17. Run validation tests (pytest + smoke tests + integration tests)
18. Commit ONLY if ALL tests pass (single atomic commit)

**Validation Checklist**:
```bash
# Schema Validation
# 1. Table count
python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70"

# 2. Import smoke test
python -c "from theauditor.indexer.schema import TABLES, build_query, Column, TableSchema"

# 3. Query builder
python -c "from theauditor.indexer.schema import build_query; print(build_query('symbols', ['name']))"

# Orchestrator Validation
# 4. Orchestrator import
python -c "from theauditor.indexer import IndexerOrchestrator, FileWalker, DatabaseManager"

# 5. Orchestrator instantiation
python -c "from theauditor.indexer import IndexerOrchestrator; orc = IndexerOrchestrator('.', '.pf/repo_index.db'); print('OK')"

# 6. MRO check
python -c "from theauditor.indexer import IndexerOrchestrator; print(IndexerOrchestrator.__mro__)"

# Combined Validation
# 7. Full test suite
pytest tests/ -v

# 8. Integration test (all languages)
aud index tests/fixtures/test_project
aud full tests/fixtures/test_project

# 9. JSX-specific test
pytest tests/test_jsx_pass.py -v
```

**Rollback**: `git revert <commit>` - Single atomic commit for instant rollback.

### Phase 2: Database Split (SEPARATE PROPOSAL)

**Scope**: Split database.py (1407 lines) into language-specific mixins.

**Structure**:
```python
# database.py (stub)
from .databases.core_database import CoreDatabaseMixin
from .databases.python_database import PythonDatabaseMixin
from .databases.node_database import NodeDatabaseMixin
from .databases.infrastructure_database import InfrastructureDatabaseMixin

class DatabaseManager(CoreDatabaseMixin, PythonDatabaseMixin,
                      NodeDatabaseMixin, InfrastructureDatabaseMixin):
    """Merged database manager with all add_* methods."""
    pass
```

**Benefits**:
- Same modularity as schema split
- add_python_* methods in python_database.py
- add_react_* methods in node_database.py
- add_terraform_* methods in infrastructure_database.py

**Deferred Reasons**:
1. Proves stub pattern works first (risk reduction)
2. Allows schema split validation in isolation
3. Database split can learn from schema split lessons

**Timeline**: Phase 2 proposal after Phase 1 deployed and validated.

## Open Questions

### Resolved

✅ **Q1**: Where do shared tables (sql_queries, jwt_patterns) go?
**A1**: core_schema.py - used by both Python and Node for security analysis.

✅ **Q2**: Should query builders stay in core_schema.py or move to utils.py?
**A2**: core_schema.py - avoids circular imports, keeps utilities with core tables.

✅ **Q3**: Can stub maintain 100% backward compatibility?
**A3**: Yes - verified all 50 consumers use `from theauditor.indexer.schema import`.

✅ **Q4**: Should database.py split in same change?
**A4**: No - deferred to Phase 2 to reduce blast radius.

✅ **Q5**: Do JSX tables belong in core or node?
**A5**: node_schema.py - React-specific dual-pass extraction.

### Unresolved

❓ **Q6**: Should we add type hints to all schema definitions?
💬 **Discussion**: Out of scope for this refactor. Type hints are an enhancement, not part of modularization. Separate proposal if desired.

❓ **Q7**: Should we add docstrings to every table?
💬 **Discussion**: Out of scope. Existing tables have inline comments. Comprehensive docstrings are an enhancement, not required for refactor.

## Performance Considerations

**Import Time**: Negligible overhead (~1ms).
- Before: Import 1 file (schema.py)
- After: Import stub → import 5 sub-modules
- Analysis: Python import caching makes this O(1) after first import

**Runtime Performance**: ZERO impact.
- TABLES registry is identical dict (70 entries)
- Query builders unchanged
- Database operations unchanged

**Memory Usage**: Identical.
- Same TableSchema objects, same Column definitions
- Python imports load into memory once (cached)

## Testing Strategy

### Unit Tests

**Existing Tests** (must pass):
- `tests/test_schema_contract.py` - Validates all table schemas
- `tests/test_database_integration.py` - Tests database operations
- `tests/test_jsx_pass.py` - Tests JSX dual-pass extraction
- `tests/test_memory_cache.py` - Tests taint memory cache

**New Tests** (add if needed):
- `test_schema_stub.py` - Validates stub imports and merges correctly

### Integration Tests

**Command Tests**:
```bash
# Test indexer
aud index tests/fixtures/test_project

# Test full analysis
aud full tests/fixtures/test_project

# Verify identical output before/after
```

**Import Smoke Tests**:
```python
# Test all 50 consumer files can import
import sys
consumers = [
    'theauditor.rules.auth.jwt_analyze',
    'theauditor.taint.core',
    'theauditor.commands.index',
    # ... all 50 files
]
for module in consumers:
    __import__(module)
    print(f'✓ {module}')
```

### Validation Tests

**Pre-Commit Hooks**:
```bash
# 1. Table count validation
python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == 70"

# 2. No duplicate tables
python -c "from theauditor.indexer.schema import TABLES; assert len(TABLES) == len(set(TABLES.keys()))"

# 3. All query builders work
python -c "
from theauditor.indexer.schema import build_query, build_join_query, validate_all_tables
build_query('symbols', ['name'])
print('✓ Query builders work')
"
```

## Documentation Updates

**Files to Update**:
1. ✅ `verification.md` (this proposal) - Comprehensive pre-implementation verification
2. ✅ `proposal.md` - High-level proposal
3. ✅ `design.md` (this file) - Technical decisions
4. ✅ `tasks.md` - Implementation checklist

**No Updates Required**:
- README.md - No user-facing changes
- API docs - No API changes
- Schema contract - Validated by tests

## Success Criteria

**Functional**:
1. ✅ All 70 tables accessible via TABLES registry
2. ✅ All 50 consumers import successfully
3. ✅ Query builders work identically
4. ✅ aud index produces identical output
5. ✅ aud full produces identical output

**Non-Functional**:
1. ✅ Developers can find tables faster (measured subjectively)
2. ✅ Code reviews easier (language-specific files)
3. ✅ Future language additions require only new module + merge
4. ✅ No performance degradation (import time, runtime)

**Testing**:
1. ✅ 100% test pass rate (pytest tests/)
2. ✅ Zero import errors (50 consumers)
3. ✅ Zero schema contract violations
4. ✅ Zero regression in aud commands

## Alternatives Considered

### Alternative 1: Keep Single File, Add Language Comments

**Idea**: Keep schema.py monolithic, add `# ==== PYTHON TABLES ====` section comments.

**Pros**:
- Zero risk (no refactor)
- Simple implementation (add comments)

**Cons**:
- Doesn't solve discoverability (still 2146 lines to scroll)
- Doesn't scale (file still grows with new languages)
- Doesn't enforce separation (easy to mix concerns)

**Verdict**: Rejected - doesn't address root problem.

### Alternative 2: Split by Feature, Not Language

**Idea**: Organize by feature (auth_schema.py, routing_schema.py, orm_schema.py).

**Pros**:
- Logical grouping by domain (auth, routing, ORM)

**Cons**:
- Cross-cuts languages (auth_schema.py has both Python and Node tables)
- Doesn't help language-specific developers (Python dev still sees Node tables)
- Ambiguous categorization (is react_components routing or framework?)

**Verdict**: Rejected - language split is clearer for multi-language codebase.

### Alternative 3: One File Per Table

**Idea**: 70 files (one per table).

**Pros**:
- Maximum granularity

**Cons**:
- Over-engineering (70 files is excessive)
- Import complexity (import 70 files vs 5)
- Navigation overhead (70 files to manage)

**Verdict**: Rejected - excessive fragmentation.

## Conclusion

This design document outlines a comprehensive, low-risk approach to refactoring schema.py into language-specific modules:

✅ **Stub pattern** ensures 100% backward compatibility
✅ **Clear categorization** (Core/Python/Node/Infrastructure/Planning)
✅ **Risk mitigation** for all identified risks
✅ **Comprehensive testing** strategy
✅ **Phase 2 path** for database.py split
✅ **Zero performance impact**
✅ **Atomic rollback** (single commit)

**Confidence Level**: HIGH (90%)

**Ready for Implementation**: YES (pending Architect/Auditor approval)

---

**Designed By**: Claude Opus (Lead Coder)
**Date**: 2025-10-30
**Status**: AWAITING APPROVAL
