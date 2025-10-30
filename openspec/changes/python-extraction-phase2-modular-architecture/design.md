# Design: Python Extraction Phase 2 - Modular Architecture & Comprehensive Coverage

## Context

Phase 1 (`add-python-extraction-parity`) delivered functional Python extraction but code audit revealed architectural limitations:

**Current State (Phase 1):**
- Single monolithic file: `python_impl.py` (1,584 lines)
- 17 extraction functions mixed together (core + framework + CFG)
- 5 database tables (python_orm_models, python_orm_fields, python_routes, python_blueprints, python_validators)
- 441 lines of test fixtures
- ~15-20% parity with JavaScript extraction

**JavaScript Architecture (Proven Pattern):**
- Modular structure: 5 files, 4,649 lines total
- 28 specialized extraction functions
- 8 database tables (react_components, react_hooks, vue_components, etc.)
- Clear separation: core → framework → security → CFG

**Gap Discovered:**
TheAuditor's own Python codebase uses patterns NOT extracted by Phase 1:
- 72 advanced decorators (@property, @staticmethod, context managers)
- 30 async patterns (async def, await, AsyncIO)
- 47 advanced type hints (TypedDict, Protocol, Generic)
- Django views, forms, admin
- pytest fixtures, parametrize, markers
- Celery tasks

**Problem:** Monolithic architecture cannot scale to handle comprehensive Python pattern coverage.

## Decision 1: Adopt JavaScript's Modular Architecture

**Chosen:** Refactor python_impl.py into `/python/` subfolder with 6 specialized modules

**Rationale:**
- **Proven pattern**: JavaScript extraction uses modular architecture successfully
- **Maintainability**: 6 files of ~500-800 lines each > 1 file of 5,000 lines
- **Separation of concerns**: Core extraction, framework patterns, async, testing, types all have distinct concerns
- **Parallel development**: Multiple developers can work on different modules without conflicts
- **Testing**: Easier to test individual modules in isolation

**Alternatives Considered:**

**Alternative 1: Keep monolithic file, add more functions**
- **Rejected**: Would grow to 5,000+ lines, unmaintainable
- File would mix 40+ extraction functions with no clear boundaries
- Merge conflicts guaranteed if multiple people work on it

**Alternative 2: Split by language feature (variables.py, functions.py, classes.py)**
- **Rejected**: Doesn't match problem space
- Framework extraction crosses multiple language features (classes, decorators, calls)
- JavaScript doesn't use this pattern

**Alternative 3: Split by framework (django.py, flask.py, fastapi.py)**
- **Rejected**: Too granular
- Frameworks share common patterns (all need ORM extraction, all need route extraction)
- Would create duplication and maintenance burden

**Chosen Module Structure:**
```
theauditor/ast_extractors/python/
├── __init__.py              - Public API re-exports
├── core_extractors.py       - Language fundamentals (functions, classes, imports, decorators)
├── framework_extractors.py  - Web frameworks & ORMs (Django, Flask, FastAPI, SQLAlchemy, Celery)
├── async_extractors.py      - Async patterns (async def, await, async with, AsyncIO)
├── testing_extractors.py    - Testing frameworks (pytest fixtures, parametrize, markers, mocking)
├── type_extractors.py       - Advanced type system (Protocol, Generic, TypedDict, overload)
└── cfg_extractor.py         - Control Flow Graph (matches JavaScript's cfg_extractor.js)
```

**Trade-offs:**
- **Pro**: Clear boundaries, easy to navigate, matches JavaScript pattern
- **Con**: More files to import, slightly more boilerplate
- **Con**: Migration risk (all imports must be updated)

## Decision 2: Backward Compatibility via __init__.py Re-exports

**Chosen:** Maintain backward compatibility by re-exporting all functions from `__init__.py`

**Rationale:**
- **Zero breakage**: Existing code using `from python_impl import extract_*` continues working
- **Gradual migration**: Can update imports incrementally
- **Rollback safety**: Can revert to python_impl.py if Phase 2 fails

**Implementation:**
```python
# theauditor/ast_extractors/python/__init__.py
from .core_extractors import (
    extract_python_imports,
    extract_python_functions,
    extract_python_classes,
    # ... all core functions
)
from .framework_extractors import (
    extract_sqlalchemy_definitions,
    extract_django_definitions,
    # ... all framework functions
)
# ... etc for all modules
```

**Trade-offs:**
- **Pro**: Zero breaking changes, easy migration
- **Con**: Hides module structure from users (they still see flat namespace)
- **Con**: IDE autocomplete doesn't show module organization

**Alternative Considered:**
**Force immediate migration**: Remove python_impl.py, force imports like `from python.core_extractors import extract_*`
- **Rejected**: Too risky, would break existing code immediately

## Decision 3: Database Schema Expansion (5 → 15+ Tables)

**Chosen:** Add 10+ new Python-specific tables to match React/Vue depth

**Rationale:**
- **Parity requirement**: JavaScript has 8 React/Vue tables, Python has 5 ORM/route tables
- **Pattern coverage**: Each pattern type needs dedicated table (decorators, async, pytest, etc.)
- **Query performance**: Dedicated tables faster than JSON blobs in generic table
- **Schema clarity**: `python_decorators` table is self-documenting vs `python_patterns` with type column

**New Tables:**
```sql
-- Django Framework
python_django_views (file, line, view_class, view_type, model, template)
python_django_forms (file, line, form_class, model, fields)
python_django_admin (file, line, admin_class, model, list_display, list_filter)

-- Async Patterns
python_async_functions (file, line, function_name, has_await, has_async_with, has_async_for)

-- Testing
python_pytest_fixtures (file, line, fixture_name, scope, params, dependencies)

-- Advanced Types
python_protocols (file, line, protocol_name, methods, runtime_checkable)
python_generics (file, line, class_name, type_params)
python_type_aliases (file, line, alias_name, target_type)

-- Core Patterns
python_decorators (file, line, decorator_name, decorator_type, target_name, target_type)
python_context_managers (file, line, class_name, has_enter, has_exit, is_async)
python_generators (file, line, function_name, has_yield, has_send, is_async)

-- Background Tasks
python_celery_tasks (file, line, task_name, queue, retry, rate_limit)
```

**Trade-offs:**
- **Pro**: Fast queries, clear schema, extensible
- **Con**: More tables = more database overhead
- **Con**: Memory cache must load 15+ tables (memory increase)

**Alternative Considered:**
**Generic python_patterns table with type column**
- Example: `(file, line, pattern_type='decorator', data=JSON)`
- **Rejected**: Slow queries (must filter by JSON), unclear schema, hard to validate

## Decision 4: Comprehensive Test Fixtures (441 → 4,741 lines, 10.7x)

**Chosen:** Build 4,300 lines of new fixtures covering Django, async, pytest, advanced types

**Rationale:**
- **Self-dogfooding**: TheAuditor has 3,537 Python constructs, fixtures had only 130 (3.7% coverage)
- **Real-world validation**: Can't claim "production ready" testing against toy examples
- **Pattern verification**: Each new extractor needs comprehensive fixture to verify correctness
- **Regression prevention**: Large fixtures catch edge cases that small fixtures miss

**Fixture Breakdown:**
```
tests/fixtures/python/comprehensive/
├── django_app/          2,000 lines - All Django patterns
├── async_app/             800 lines - All async patterns
├── testing_patterns/      600 lines - All pytest patterns
├── advanced_types/        400 lines - All type system patterns
└── decorators_context/    500 lines - All decorator/context patterns
                          ───────
                          4,300 lines total
```

**Trade-offs:**
- **Pro**: Comprehensive validation, catches edge cases, production confidence
- **Con**: 4,300 lines to maintain, slower test runs
- **Con**: Must keep fixtures in sync with TheAuditor's actual patterns

**Alternative Considered:**
**Minimal fixtures (add 100-200 lines to existing 441)**
- **Rejected**: Insufficient coverage, false confidence

## Decision 5: Extraction Function Naming - Explicit vs Generic

**Chosen:** Explicit function names that describe exact pattern extracted

**Rationale:**
- **Clarity**: `extract_django_views()` > `extract_views()` (which framework?)
- **Consistency**: Matches JavaScript pattern (`extractReactComponents()` vs `extractComponents()`)
- **Namespace**: Multiple frameworks can have similar patterns, explicit names avoid conflicts

**Examples:**
```python
# CHOSEN - Explicit
extract_django_views()           # Clear: Django class-based views
extract_django_forms()           # Clear: Django ModelForm/FormSets
extract_pytest_fixtures()        # Clear: pytest @pytest.fixture decorators
extract_celery_tasks()           # Clear: Celery @task decorators

# REJECTED - Generic
extract_views()                  # Ambiguous: Django? Flask? FastAPI?
extract_forms()                  # Ambiguous: Django? WTForms?
extract_fixtures()               # Ambiguous: pytest? unittest?
extract_tasks()                  # Ambiguous: Celery? asyncio?
```

**Trade-offs:**
- **Pro**: Self-documenting, no ambiguity, easy to search
- **Con**: Longer function names, more typing

## Decision 6: CFG Extraction - Separate File (Match JavaScript)

**Chosen:** Extract `extract_python_cfg()` to dedicated `cfg_extractor.py`

**Rationale:**
- **JavaScript precedent**: JavaScript has dedicated `cfg_extractor.js` (554 lines)
- **Growth potential**: Python CFG is currently 289 lines, will grow with enhancements
- **Distinct concern**: CFG extraction is fundamentally different from symbol/framework extraction
- **Performance**: CFG is expensive, may want to make it optional in future

**Trade-offs:**
- **Pro**: Clean separation, matches JavaScript, room to grow
- **Con**: One more file to maintain

**Alternative Considered:**
**Keep CFG in core_extractors.py**
- **Rejected**: Mixes concerns, core_extractors.py would grow too large

## Decision 7: Hardcoded Constants - Extract to Framework Module

**Chosen:** Move framework detection constants (SQLALCHEMY_BASE_IDENTIFIERS, DJANGO_MODEL_BASES, FASTAPI_HTTP_METHODS) from top-level to framework_extractors.py

**Rationale:**
- **Locality**: Constants only used by framework extractors, should live with them
- **Extensibility**: Easy to add new framework constants without polluting namespace
- **Encapsulation**: Framework module owns its detection logic

**Implementation:**
```python
# framework_extractors.py
SQLALCHEMY_BASE_IDENTIFIERS = {"Base", "DeclarativeBase", "db.Model"}
DJANGO_MODEL_BASES = {"models.Model", "django.db.models.Model"}
FASTAPI_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
```

**Trade-offs:**
- **Pro**: Better organization, clear ownership
- **Con**: Slight import overhead (must import from framework module)

## Decision 8: Performance Targets - Accept <10% Regression

**Chosen:** Accept up to 10% performance regression for 3x more extraction

**Rationale:**
- **Value trade-off**: 10% slower indexing for 40-50% parity is worth it
- **Phase 1 baseline**: 830.2s taint analysis (13.8 minutes)
- **Phase 2 target**: <913s taint analysis (15.2 minutes, +10%)
- **Extraction overhead**: <50ms per file (was <35ms in Phase 1)

**Reasoning:**
- **3x more data**: Extracting 15+ tables vs 5 tables
- **3x more extractors**: 40 functions vs 17 functions
- **Acceptable cost**: 10% = 2 more minutes on 15-minute analysis

**Trade-offs:**
- **Pro**: Avoids premature optimization, delivers functionality first
- **Con**: May need optimization later if regression exceeds 10%

**Mitigation:**
- If regression >10%, profile and optimize hot paths
- Consider making some extractors optional (e.g., CFG, testing patterns)
- Consider parallel extraction (currently sequential)

## Decision 9: Memory Cache - Eager vs Lazy Loading

**Chosen:** Eager loading (load all 15+ tables at startup)

**Rationale:**
- **Consistency**: Phase 1 uses eager loading for 5 tables
- **Simplicity**: No complex lazy loading logic needed
- **Performance**: Taint analysis queries all tables anyway, lazy loading provides no benefit
- **Memory acceptable**: 77MB (Phase 1) → <150MB (Phase 2) is acceptable

**Trade-offs:**
- **Pro**: Simple, consistent, no lazy loading bugs
- **Con**: Higher initial memory cost, slower startup

**Alternative Considered:**
**Lazy loading (load tables on first access)**
- **Rejected**: Adds complexity, no performance benefit for TheAuditor's usage pattern

## Decision 10: Async Taint Propagation - Treat await as Call Site

**Chosen:** Model `await expression` as function call site for taint propagation

**Rationale:**
- **Semantic match**: `await async_func()` behaves like `sync_func()` for taint purposes
- **Existing infrastructure**: Can reuse call site taint logic
- **Correctness**: Taint flows through await boundaries (async source → await → async sink)

**Implementation:**
```python
# async_extractors.py
def extract_await_expressions(tree):
    """Extract await expressions as call sites for taint analysis."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            yield {
                'line': node.lineno,
                'expression': ast.unparse(node.value),
                'is_async': True
            }
```

**Trade-offs:**
- **Pro**: Reuses existing taint logic, correct semantics
- **Con**: Async-specific optimizations (e.g., asyncio.gather) require custom logic

## Decision 11: pytest Fixture Scope - Store and Use for Taint

**Chosen:** Extract and store pytest fixture scope (function/class/module/session)

**Rationale:**
- **Taint reach**: Session fixtures affect all tests, function fixtures affect one test
- **Correctness**: Taint from session fixture propagates farther than function fixture
- **Real-world importance**: Session DB fixtures are common taint sources

**Schema:**
```sql
python_pytest_fixtures (
    file TEXT,
    line INTEGER,
    fixture_name TEXT,
    scope TEXT,  -- 'function', 'class', 'module', 'session'
    params TEXT, -- JSON array of parameter values
    dependencies TEXT -- JSON array of dependent fixture names
)
```

**Trade-offs:**
- **Pro**: Accurate taint analysis for pytest codebases
- **Con**: Adds complexity to fixture extraction

## Decision 12: Django Template Extraction - OUT OF SCOPE

**Chosen:** Do NOT extract Django templates (HTML files)

**Rationale:**
- **Phase 2 scope**: Python code extraction only
- **Template parsing**: Requires different parser (not Python AST)
- **Complexity**: Django template language has its own syntax
- **Diminishing returns**: Most security issues are in Python views, not templates

**Future work:** If needed, create separate proposal for Django template extraction

**Trade-offs:**
- **Pro**: Keeps Phase 2 scope manageable, ships faster
- **Con**: Incomplete Django coverage (views yes, templates no)

## Decision 13: Celery Chain Detection - Store as JSON

**Chosen:** Store Celery task chains as JSON array in database

**Rationale:**
- **Flexibility**: Chain structure varies (chain, group, chord, etc.)
- **Simplicity**: Don't need dedicated `celery_chains` table, just JSON column
- **Query pattern**: Rarely query chain structure, mostly query task definitions

**Schema:**
```sql
python_celery_tasks (
    file TEXT,
    line INTEGER,
    task_name TEXT,
    queue TEXT,
    retry_count INTEGER,
    chain_structure TEXT -- JSON: {"type": "chain", "tasks": ["task1", "task2"]}
)
```

**Trade-offs:**
- **Pro**: Flexible, simple, no schema changes for new chain types
- **Con**: Can't efficiently query chain structure (e.g., "find all chains containing task X")

## Open Questions

### Question 1: Should decorators be stored per-decorator or per-target?

**Context:** A function can have multiple decorators. Store one row per decorator or one row per function with JSON array of decorators?

**Options:**
- **Option A (Per-decorator)**: One row per decorator
  ```sql
  ('file.py', 10, '@property', 'property', 'getter', 'function')
  ('file.py', 11, '@setter', 'property', 'setter', 'function')
  ```
- **Option B (Per-target)**: One row per function with decorator list
  ```sql
  ('file.py', 10, 'getter', 'function', JSON(['@property', '@setter']))
  ```

**Recommendation:** Option A (per-decorator) - Easier to query "find all @property uses"

### Question 2: Should Protocol extraction include method signatures?

**Context:** Protocols define interfaces. Should we store just protocol name or full method signatures?

**Options:**
- **Option A (Name only)**: Store protocol name only
- **Option B (Full signature)**: Store protocol name + method names + signatures as JSON

**Recommendation:** Option B (full signature) - Needed for taint analysis to understand what methods are expected

### Question 3: Should async context managers have dedicated table?

**Context:** Async context managers (`async with`) are similar to sync context managers but async.

**Options:**
- **Option A (Shared table)**: Store in `python_context_managers` with `is_async` flag
- **Option B (Dedicated table)**: Create `python_async_context_managers` table

**Recommendation:** Option A (shared table) - Reduces table count, `is_async` flag is sufficient

### Question 4: Should Django form validation be extracted?

**Context:** Django forms have `clean()` and `clean_<field>()` methods for validation.

**Options:**
- **Option A (Extract validators)**: Store form validators like Pydantic validators
- **Option B (Skip validators)**: Only extract form structure, not validation logic

**Recommendation:** Option A (extract validators) - Important for taint analysis (validators are sanitizers)

## Success Metrics

**Architecture:**
- Python extraction: 1,584 lines (1 file) → ~5,000 lines (6 files) ✓
- Module boundaries: Core, Framework, Async, Testing, Types, CFG ✓
- Backward compatibility: 100% (all existing imports work) ✓

**Database:**
- Python tables: 5 → 15+ ✓
- Match React/Vue depth (8 tables) ✓

**Coverage:**
- Test fixtures: 441 → 4,741 lines (10.7x) ✓
- TheAuditor self-coverage: 3.7% → 100% (all patterns) ✓

**Performance:**
- Extraction overhead: <50ms per file ✓
- Taint analysis: <913s (< +10% regression) ✓
- Memory cache: <150MB (<2x increase) ✓

**Parity:**
- Actual parity: 15-20% → 40-50% (vs JavaScript) ✓
- Extraction functions: 17 → ~40 ✓
- Table count: 5 → 15+ ✓
