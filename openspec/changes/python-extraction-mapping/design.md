# Python Extraction Mapping: Design Document

**Version**: 1.0
**Date**: 2025-11-01
**Status**: DRAFT

---

## Context

Phase 3 established a proven 5-layer extraction pipeline with 75 extractors and 59 tables, achieving 70% Python/JavaScript parity. Gap analysis reveals ~100 missing patterns preventing production-grade Python code intelligence.

**Current Architecture** (verified 2025-11-01):
```
Layer 1: AST Extractors → 75 functions across 9 modules
Layer 2: Indexer → extractors/python.py orchestrates extraction
Layer 3: Storage → storage.py handles 59 result types
Layer 4: Database → python_database.py writes to 59 tables
Layer 5: Schema → python_schema.py defines 59 tables
```

**Constraints**:
- Maintain <10ms per file extraction (Phase 3 benchmark: 2-7 files/sec)
- Zero regressions on Phase 3 extractors
- Memory usage <500MB peak
- Database regenerated fresh every `aud index` (no migrations needed)

---

## Goals / Non-Goals

### Goals
1. Reach 95% Python/JavaScript parity through 4 implementation phases (4-6 months)
2. Extract 100+ missing critical patterns (walrus, Django URLs, Pydantic V2, etc.)
3. Add 32 new database tables (59 → 91 tables)
4. Extract 6,000+ new records from TheAuditor (7,761 → 13,761 records)
5. Maintain extraction performance (<10ms per file)

### Non-Goals
1. **NOT** refactoring existing extractors (Phase 3 works, leave it alone)
2. **NOT** adding every possible Python pattern (focus on high-value gaps)
3. **NOT** supporting legacy Python versions (<3.11)
4. **NOT** database migrations (fresh generation model)
5. **NOT** cross-language patterns yet (Python-JS bridge deferred to Phase 8)

---

## Architectural Decisions

### Decision 1: Four-Phase Implementation Strategy

**Context**: ~100 missing patterns across 4 categories (Core, Frameworks, Validation, Polish)

**Options Considered**:
1. **Single Large Phase**: Implement all 100 patterns in one 6-month effort
2. **Category-Based Phases**: Phase by pattern category (Core, Frameworks, Validation, Polish)
3. **Priority-Based Phases**: Phase by impact (TIER 1, TIER 2, TIER 3, TIER 4)
4. **Framework-First Phases**: Phase by framework (Django, Flask, FastAPI, etc.)

**Decision**: Option 2 (Category-Based Phases)

**Rationale**:
- Clear scope boundaries (Core language vs Frameworks vs Validation)
- Incremental value delivery (78% → 85% → 91% → 95% parity)
- Easier to test (category-specific test fixtures)
- Natural checkpoints every 4-6 weeks
- Can pause/pivot between phases without partial work

**Trade-offs**:
- (+) Clear milestones with measurable parity increases
- (+) Can stop at any phase if 85% or 91% is "good enough"
- (+) Easier to onboard new AIs mid-project (phase boundaries)
- (-) Some users may want specific frameworks earlier (FastAPI fans wait until Phase 5)
- (-) Cannot cherry-pick high-value patterns across categories

**Implementation**:
```
Phase 4: Core Language (4-6 weeks) → 78% parity
  - Walrus, augmented, lambdas, comprehensions, exceptions
  - Foundation for all other work

Phase 5: Frameworks (6-8 weeks) → 85% parity
  - Django URLs, FastAPI response models, SQLAlchemy cascade
  - Framework-specific patterns

Phase 6: Validation (4-6 weeks) → 91% parity
  - Pydantic V2, Marshmallow, WTForms, DRF
  - Input validation completeness

Phase 7: Polish (2-4 weeks) → 95% parity
  - Async tasks, type aliases, doctest
  - Final gap closure
```

---

### Decision 2: Module Organization Strategy

**Context**: Adding 100+ extractors requires file organization strategy

**Options Considered**:
1. **Add to Existing Files**: Put all new extractors in current modules
2. **Monolithic Modules**: One huge file per category (expression_extractors.py = 2,000 lines)
3. **Fine-Grained Modules**: One file per framework/pattern (django_urls.py, fastapi_responses.py, etc.)
4. **Hybrid Approach**: Category modules (expression_extractors.py) + framework modules (django_url_extractors.py)

**Decision**: Option 4 (Hybrid Approach)

**Rationale**:
- Balance between cohesion and maintainability
- Core language patterns group naturally (expressions, exceptions, imports)
- Framework patterns vary widely (Django != FastAPI != SQLAlchemy)
- Easier to find extractors (django_url_extractors.py is obvious)
- Consistent with Phase 3 pattern (flask_extractors.py, security_extractors.py)

**Module Structure**:
```
theauditor/ast_extractors/python/
├── core_extractors.py              (Phase 2 - 16 functions)
├── framework_extractors.py         (Phase 2/3 - 25 functions, will grow to 35)
├── flask_extractors.py             (Phase 3 - 9 functions, will grow to 13)
├── security_extractors.py          (Phase 3 - 8 functions)
├── testing_extractors.py           (Phase 2/3 - 12 functions, will grow to 15)
├── django_advanced_extractors.py   (Phase 3 - 4 functions)
├── async_extractors.py             (Phase 2 - 3 functions, will grow to 6)
├── type_extractors.py              (Phase 2 - 5 functions, will grow to 7)
├── expression_extractors.py        (NEW - Phase 4 - 8 functions)
├── exception_extractors.py         (NEW - Phase 4 - 6 functions)
├── import_extractors.py            (NEW - Phase 4 - 5 functions)
├── dataclass_extractors.py         (NEW - Phase 4 - 3 functions)
├── django_url_extractors.py        (NEW - Phase 5 - 8 functions)
├── fastapi_detail_extractors.py    (NEW - Phase 5 - 6 functions)
├── sqlalchemy_detail_extractors.py (NEW - Phase 5 - 10 functions)
├── celery_detail_extractors.py     (NEW - Phase 5 - 7 functions)
├── pydantic_v2_extractors.py       (NEW - Phase 6 - 8 functions)
├── marshmallow_detail_extractors.py (NEW - Phase 6 - 6 functions)
├── wtforms_detail_extractors.py    (NEW - Phase 6 - 3 functions)
├── django_forms_detail_extractors.py (NEW - Phase 6 - 3 functions)
└── async_task_extractors.py        (NEW - Phase 7 - 3 functions)

Total: 25 files, 175 functions
```

**Trade-offs**:
- (+) Easy to navigate (file names match patterns)
- (+) Easier to test in isolation
- (+) Can assign different files to different AIs in parallel
- (-) More files to manage (25 vs 10)
- (-) Import management complexity
- (-) Potential for duplicate helper functions

**Mitigation**: Create shared `extraction_helpers.py` for common utilities

---

### Decision 3: Performance Optimization Strategy

**Context**: Adding 100 extractors (75 → 175) could degrade performance significantly

**Options Considered**:
1. **Naive Approach**: Add extractors without optimization, deal with slowness later
2. **Parallel Extraction**: Run extractors in parallel threads/processes
3. **Single-Pass AST Walking**: Combine extractors to reduce tree traversals
4. **Incremental AST Parsing**: Parse AST once, share across extractors
5. **JIT Compilation**: Use Numba/Cython to speed up hot paths

**Decision**: Option 3 + Option 4 (Single-Pass + Shared AST)

**Rationale**:
- Phase 3 uses multiple ast.walk() calls per file (75 extractors = ~30 tree traversals)
- Single-pass approach: One ast.walk(), dispatch to extractors based on node type
- Shared AST: Parse once, reuse across all extractors
- Proven pattern: JavaScript extractors already use single-pass
- No external dependencies (Numba/Cython add complexity)

**Implementation Pattern**:
```python
# Current (Phase 3) - Multiple Passes
def extract_all_patterns(tree: Dict, parser_self) -> Dict:
    results = {}
    results['walrus'] = extract_walrus(tree)      # ast.walk() #1
    results['augmented'] = extract_augmented(tree) # ast.walk() #2
    results['lambdas'] = extract_lambdas(tree)     # ast.walk() #3
    # ... 172 more tree traversals
    return results

# New (Phase 4+) - Single Pass with Dispatch
def extract_all_patterns(tree: Dict, parser_self) -> Dict:
    results = defaultdict(list)
    actual_tree = tree.get("tree")

    # Single ast.walk()
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.NamedExpr):  # Walrus
            results['walrus'].append(_extract_walrus_from_node(node))
        if isinstance(node, ast.AugAssign):  # Augmented
            results['augmented'].append(_extract_augmented_from_node(node))
        if isinstance(node, ast.Lambda):  # Lambda
            results['lambdas'].append(_extract_lambda_from_node(node))
        # ... dispatch to 172 more extractors

    return dict(results)
```

**Performance Target**:
- Phase 3: 2-7 files/sec (0.14-0.5s per file)
- Phase 4-7 Target: 2-10 files/sec (<0.10s per file goal, <0.5s acceptable)
- Single-pass optimization: ~40% speedup expected
- Worst case: No slower than Phase 3 (<0.5s per file)

**Trade-offs**:
- (+) 40% faster extraction (30 passes → 1 pass)
- (+) Scales to 175+ extractors without slowdown
- (+) Memory efficient (one AST in memory)
- (-) More complex extractor logic (dispatch layer)
- (-) Harder to debug (all extractors run together)
- (-) Refactoring effort (convert 75 existing extractors)

**Rollout**:
1. **Phase 4**: Implement single-pass for NEW extractors only (expression, exception, import)
2. **Phase 5-7**: Continue single-pass pattern for new extractors
3. **Phase 8 (Future)**: Migrate Phase 2/3 extractors to single-pass (optional optimization)

---

### Decision 4: Pydantic V1 vs V2 Handling

**Context**: Pydantic V2 (released 2023) is now standard but V1 still widely used

**Options Considered**:
1. **V2 Only**: Extract only Pydantic V2 patterns, ignore V1
2. **V1 Only**: Continue existing V1 extraction, ignore V2
3. **Dual Extraction**: Separate extractors for V1 and V2
4. **Version Detection + Dual**: Detect version, extract accordingly

**Decision**: Option 4 (Version Detection + Dual Extraction)

**Rationale**:
- Pydantic V2 is 5-10x faster, has better validation, is recommended by maintainers
- But Pydantic V1 still has 40% market share (PyPI stats)
- Breaking changes between V1/V2 (decorators renamed: @validator → @field_validator)
- TheAuditor must support both to avoid blind spots
- Version detection is simple (check for pydantic.v1 import or pydantic.__version__)

**Implementation**:
```python
# Phase 6: pydantic_v2_extractors.py
def extract_pydantic_field_validators(tree: Dict, parser_self) -> List[Dict]:
    """Extract Pydantic V2 @field_validator decorators.

    Detects:
    - @field_validator('field_name')
    - @field_validator('field1', 'field2')
    - mode='before'|'after'|'wrap'
    """
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if _is_pydantic_v2_field_validator(decorator):
                    results.append({
                        'decorator': 'field_validator',
                        'version': 'v2',
                        'fields': _extract_fields(decorator),
                        'mode': _extract_mode(decorator),
                        # ...
                    })
    return results

# Existing Phase 2/3: framework_extractors.py (keep as-is)
def extract_pydantic_validators(tree: Dict, parser_self) -> List[Dict]:
    """Extract Pydantic V1 @validator decorators (LEGACY)."""
    # Continue extracting V1 patterns
    # Mark with 'version': 'v1' for clarity

# New Phase 6: Add version detection
def detect_pydantic_version(tree: Dict) -> str:
    """Detect Pydantic V1 vs V2 from imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == 'pydantic.v1':
                return 'v1'
            if node.module == 'pydantic':
                # V2 if pydantic 2.x
                return 'v2'
    return 'unknown'
```

**Database Schema**:
```python
# Add version column to validators table
PYTHON_VALIDATORS = TableSchema(
    name="python_validators",
    columns=[
        # ...
        Column('pydantic_version', 'TEXT'),  # 'v1', 'v2', 'unknown'
        # ...
    ],
    indexes=['pydantic_version']
)

# Separate table for V2 validators
PYTHON_PYDANTIC_FIELD_VALIDATORS = TableSchema(
    name="python_pydantic_field_validators",
    columns=[
        Column('file', 'TEXT', nullable=False),
        Column('line', 'INTEGER', nullable=False),
        Column('model', 'TEXT', nullable=False),
        Column('fields', 'TEXT', nullable=False),  # JSON array
        Column('validator_func', 'TEXT', nullable=False),
        Column('mode', 'TEXT'),  # 'before', 'after', 'wrap'
        Column('version', 'TEXT DEFAULT "v2"'),
    ],
    primary_key=['file', 'line']
)
```

**Trade-offs**:
- (+) Complete Pydantic coverage (V1 + V2)
- (+) Future-proof (V2 adoption will grow)
- (+) Clear version tracking in database
- (-) More complex extractor logic
- (-) Two sets of validators to maintain
- (-) Potential confusion (which validator decorator is V1 vs V2?)

**Migration Path**:
- Phase 6: Add V2 extractors
- Phase 7: Add version detection
- Phase 8 (Future): Deprecation warnings for V1 (if Pydantic drops V1 support)

---

### Decision 5: Django URL Pattern Extraction Strategy

**Context**: Django URL patterns are defined in urls.py files, not in views

**Options Considered**:
1. **File-Based Extraction**: Only extract from files named urls.py
2. **Pattern-Based Extraction**: Extract from any file with `urlpatterns = [...]`
3. **Import-Following Extraction**: Follow include() references to sub-URLconfs
4. **Hybrid**: File-based + pattern-based

**Decision**: Option 4 (Hybrid: File-based + Pattern-based)

**Rationale**:
- Django convention: urls.py contains URL patterns
- But urlpatterns can be in any file (e.g., myapp/routing.py)
- Some projects use include() to split URLconfs
- Import-following is complex and error-prone (defer to Phase 8)

**Implementation**:
```python
# Phase 5: django_url_extractors.py
def extract_django_url_patterns(tree: Dict, parser_self) -> List[Dict]:
    """Extract Django URL patterns from urlpatterns lists.

    Detects:
    - path('api/users/', views.UserListView.as_view())
    - re_path(r'^users/(?P<pk>[0-9]+)/$', views.UserDetailView)
    - include() references (extract pattern but don't follow)
    """
    results = []
    file_path = tree.get('file', '')

    # Priority 1: urls.py files (Django convention)
    if file_path.endswith('urls.py'):
        results.extend(_extract_urlpatterns_from_file(tree))

    # Priority 2: Any file with urlpatterns = [...]
    else:
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if _is_urlpatterns_assignment(node):
                    results.extend(_extract_urlpatterns_from_assignment(node))

    return results

def _extract_urlpatterns_from_assignment(node: ast.Assign) -> List[Dict]:
    """Extract patterns from urlpatterns = [path(...), re_path(...), ...]."""
    patterns = []
    if isinstance(node.value, ast.List):
        for elt in node.value.elts:
            if isinstance(elt, ast.Call):
                if _is_path_call(elt):
                    patterns.append({
                        'type': 'path',
                        'pattern': _extract_path_pattern(elt),
                        'view': _extract_view_reference(elt),
                        'name': _extract_name_kwarg(elt),
                        # ...
                    })
                elif _is_re_path_call(elt):
                    patterns.append({
                        'type': 're_path',
                        'pattern': _extract_regex_pattern(elt),
                        'view': _extract_view_reference(elt),
                        'name': _extract_name_kwarg(elt),
                        # ...
                    })
                elif _is_include_call(elt):
                    patterns.append({
                        'type': 'include',
                        'pattern': _extract_include_prefix(elt),
                        'module': _extract_include_module(elt),
                        # Don't follow include() - too complex
                    })
    return patterns
```

**Database Schema**:
```python
PYTHON_DJANGO_URL_PATTERNS = TableSchema(
    name="python_django_url_patterns",
    columns=[
        Column('file', 'TEXT', nullable=False),
        Column('line', 'INTEGER', nullable=False),
        Column('type', 'TEXT', nullable=False),  # 'path', 're_path', 'include'
        Column('pattern', 'TEXT', nullable=False),
        Column('view', 'TEXT'),  # View reference (function or class)
        Column('name', 'TEXT'),  # URL name for reverse()
        Column('namespace', 'TEXT'),  # For include() patterns
        Column('method', 'TEXT'),  # HTTP method (if specified)
    ],
    primary_key=['file', 'line'],
    indexes=['pattern', 'view', 'name']
)
```

**Trade-offs**:
- (+) Covers Django convention (urls.py)
- (+) Flexible (works with non-standard files)
- (+) Simple (no import following)
- (-) Misses included URLconfs (deferred to Phase 8)
- (-) Cannot resolve view strings to actual view functions (deferred to Phase 8)

**Expected Results** (TheAuditor):
- ~50 URL patterns extracted (TheAuditor has small Django presence)
- Verification with project_anarchy (larger Django project)

---

### Decision 6: Test Fixture Strategy

**Context**: Need 2,000+ lines of new test fixtures across 4 phases

**Options Considered**:
1. **Hand-Crafted Fixtures**: Write all fixtures manually
2. **Real-World Examples**: Copy from real projects (Django, Flask, FastAPI repos)
3. **Generated Fixtures**: Programmatically generate fixtures
4. **Hybrid**: Real-world + hand-crafted edge cases

**Decision**: Option 4 (Hybrid: Real-world + Edge Cases)

**Rationale**:
- Real-world examples ensure practical patterns covered
- Hand-crafted edge cases ensure completeness (empty cases, malformed code, etc.)
- Generated fixtures are hard to understand/maintain
- Phase 3 approach worked well (569 lines testing_patterns.py)

**Fixture Organization**:
```
tests/fixtures/python/
├── expression_patterns.py        (Phase 4, 300 lines)
│   - Walrus operator in if/while/comprehensions
│   - Augmented assignment (+=, -=, *=, /=, //=, %=, **=, &=, |=, ^=, >>=, <<=)
│   - Lambda functions (simple, nested, in map/filter/sorted)
│   - Comprehensions (list, dict, set, generator, nested, conditional)
│
├── exception_patterns.py         (Phase 4, 300 lines)
│   - raise statements (simple, with from, no args)
│   - try/except/else/finally blocks
│   - Multiple except clauses
│   - Custom exception classes
│   - Context managers (with statement, async with)
│
├── import_patterns.py            (Phase 4, 200 lines)
│   - Relative imports (from . import, from .. import, from ...package import)
│   - Star imports (from x import *)
│   - Conditional imports (if/try-wrapped)
│   - Import chains (import a.b.c.d)
│
├── django_url_patterns.py        (Phase 5, 400 lines)
│   - path() patterns with parameters (<int:pk>, <str:slug>)
│   - re_path() with regex groups
│   - include() with namespaces
│   - View references (function views, CBVs, as_view())
│   - Template tags, filters, management commands
│
├── flask_advanced_patterns.py    (Phase 5, 300 lines)
│   - Route parameter types (<int:id>, <uuid:id>)
│   - render_template() calls
│   - session.get/set usage
│   - Flask-WTF forms
│
├── fastapi_advanced_patterns.py  (Phase 5, 300 lines)
│   - response_model parameter
│   - Body(...) request models
│   - WebSocket routes
│   - BackgroundTasks
│   - Lifespan events
│
├── sqlalchemy_advanced_patterns.py (Phase 5, 400 lines)
│   - Cascade details (all, delete-orphan, save-update, merge, expunge)
│   - Query patterns (.filter, .join, .group_by, .order_by, .limit)
│   - Hybrid properties
│   - Session operations (commit, flush, rollback)
│
├── pydantic_v2_patterns.py       (Phase 6, 400 lines)
│   - @field_validator decorators
│   - @model_validator decorators
│   - Field(...) constraints
│   - model_config settings
│
├── marshmallow_advanced_patterns.py (Phase 6, 200 lines)
│   - @pre_load, @post_load, @pre_dump, @post_dump
│   - Validator details (Length, Range, Email, URL)
│   - Meta.unknown = 'EXCLUDE'|'INCLUDE'|'RAISE'
│
├── async_task_patterns.py        (Phase 7, 200 lines)
│   - asyncio.create_task()
│   - asyncio.gather()
│   - Task result tracking
│
└── type_alias_patterns.py        (Phase 7, 200 lines)
    - Type aliases (TypeAlias = Union[...])
    - Literal values
    - Doctest examples

Total: 2,800 lines of new fixtures
```

**Trade-offs**:
- (+) High-quality fixtures from real code
- (+) Edge cases ensure robustness
- (+) Easy to understand and maintain
- (-) Time-consuming to write (but necessary)
- (-) Fixtures can become stale if patterns change
- (-) Large fixture files can be hard to navigate

**Mitigation**:
- Organize fixtures by phase (easier to maintain)
- Add comments explaining each pattern
- Run fixtures through linters to ensure valid Python

---

### Decision 7: Error Handling Philosophy

**Context**: Extractors encounter malformed AST, need consistent error handling

**Options Considered**:
1. **Fail Fast**: Crash on any error, fix bug immediately
2. **Silent Failure**: Log errors, continue extraction, return empty results
3. **Best Effort**: Log errors, return partial results, continue extraction
4. **Graceful Degradation**: Return approximations when exact extraction fails

**Decision**: Option 3 (Best Effort with Partial Results)

**Rationale**:
- Phase 3 uses best effort successfully
- Don't lose all extraction due to one bad pattern
- Log errors at DEBUG level for investigation
- Return partial results so users get something
- Production databases are regenerated fresh, so errors aren't persistent

**Pattern** (continuing from Phase 3):
```python
def extract_pattern(tree: Dict, parser_self) -> List[Dict]:
    """Extract pattern with best-effort error handling."""
    results = []
    errors = []

    try:
        for node in ast.walk(tree):
            try:
                result = process_node(node)
                if result:  # Only append non-None results
                    results.append(result)
            except Exception as e:
                errors.append(f"Line {getattr(node, 'lineno', '?')}: {e}")
                if parser_self.debug:
                    logger.debug(f"Extraction error at {node.lineno}: {e}")
                # Continue to next node
    except Exception as e:
        logger.error(f"Fatal extraction error in {tree.get('file', 'unknown')}: {e}")
        # Return partial results collected before error

    if errors and parser_self.debug:
        logger.debug(f"Extraction completed with {len(errors)} errors, {len(results)} results")

    return results
```

**Trade-offs**:
- (+) Robust (continues despite errors)
- (+) Partial results better than nothing
- (+) Errors logged for debugging
- (-) Errors might go unnoticed (if not in DEBUG mode)
- (-) Partial results can be misleading (user doesn't know extraction failed)

**Mitigation**:
- Add extraction quality metrics (% of files with errors)
- Surface critical errors in CLI output
- Add `extraction_errors` table to database for tracking

---

## Risks / Trade-offs

### Performance Risks

**Risk**: Adding 100 extractors degrades performance below <10ms target

**Mitigation**:
- Single-pass AST walking (40% speedup expected)
- Profile after each phase, optimize hot paths
- Short-circuit evaluation (check cheap conditions first)
- Memory pool allocation (reuse objects)

**Trade-off**: More complex extractor dispatch logic vs faster extraction

**Contingency**: Defer non-critical extractors (Tier 3/4) if performance degrades >20%

### Pydantic V1/V2 Compatibility Risk

**Risk**: Supporting both V1 and V2 adds complexity and potential for bugs

**Mitigation**:
- Clear version detection logic
- Separate tables for V1 and V2 validators
- Comprehensive test fixtures for both versions

**Trade-off**: Dual maintenance vs complete coverage

**Contingency**: If V1 support becomes too complex, mark as deprecated and focus on V2

### Test Fixture Maintenance Risk

**Risk**: 2,800 lines of new fixtures becomes unmaintainable

**Mitigation**:
- Organize by phase (easier to isolate)
- Add comments explaining patterns
- Use real-world examples (easier to understand)

**Trade-off**: Time spent on fixtures vs extraction quality

**Contingency**: Generate fixtures programmatically if hand-crafting becomes bottleneck

---

## Migration Plan

**NO MIGRATION REQUIRED** - All changes are additive.

**Compatibility**:
- Phase 3 extractors continue working unchanged
- Existing databases compatible (new tables added, old tables untouched)
- No breaking changes to API or CLI

**Rollback**:
- Each phase on separate Git branch
- Database snapshots before each phase
- Can revert to Phase 3 baseline anytime

---

## Open Questions

1. **Should we parallelize extraction across files?**
   - Current: Serial extraction (process files one by one)
   - Alternative: Parallel extraction (process N files concurrently)
   - Trade-off: Complexity vs speed
   - **Decision**: Defer to Phase 8 (not needed for 95% parity goal)

2. **Should we cache AST between aud runs?**
   - Current: Parse AST fresh every `aud index`
   - Alternative: Cache parsed AST on disk
   - Trade-off: Disk space vs speed
   - **Decision**: Defer to Phase 8 (parsing is fast enough)

3. **Should we support Python 2.7?**
   - Current: Python 3.11+ only
   - Alternative: Add Python 2.7 support
   - Trade-off: Maintenance burden vs legacy coverage
   - **Decision**: NO - Python 2.7 reached EOL in 2020

4. **Should we extract from .pyc files?**
   - Current: Only .py source files
   - Alternative: Decompile .pyc to AST
   - Trade-off: Complexity vs closed-source coverage
   - **Decision**: NO - Too complex, unreliable, defer to Phase 8+

---

**END OF DESIGN DOCUMENT**

**Next**: Create tasks.md with atomic task breakdown for each phase
