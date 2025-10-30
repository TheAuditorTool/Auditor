# Proposal: Python Extraction Phase 2 - Modular Architecture & Comprehensive Coverage

## Why

**Phase 1 Reality Check (2025-10-30):**
Phase 1 (`add-python-extraction-parity`, archived) delivered functional Python extraction:
- 4,593 type annotations extracted
- 14 ORM models, 48 fields, 24 relationships
- 17 FastAPI/Flask routes
- 9 Pydantic validators

**Gap Discovered:**
Code audit revealed Phase 1 only achieved ~15-20% parity with JavaScript extraction (not the claimed 50-60%):

```
JavaScript:  4,649 lines across 5 modular files (28 specialized functions)
Python:      1,584 lines in 1 monolithic file (17 functions)
Test fixtures: 441 lines (tests 3.7% of TheAuditor's own Python complexity)
```

**Missing from TheAuditor's Own Codebase:**
- 72 advanced decorators (@property, @staticmethod, @classmethod, @abstractmethod, context managers) - NOT extracted
- 30 async patterns (async def, await, AsyncIO) - NOT extracted
- 47 advanced type hints (TypedDict, Protocol, Generic, Literal, overload) - NOT extracted
- Django views, forms, admin - NOT extracted
- pytest fixtures, markers, parametrize - NOT extracted
- Celery tasks - NOT extracted

**Architectural Problem:**
`python_impl.py` is a 1,584-line monolith mixing core extraction, framework extraction, async patterns, and CFG logic. JavaScript proved modular architecture scales better (5 files vs 1).

## What

Phase 2 refactors Python extraction to match JavaScript's proven modular architecture and adds comprehensive pattern coverage.

**4 Deliverables:**

1. **Modular Architecture** - Refactor python_impl.py into `/python/` subfolder with 6 specialized modules:
   - `core_extractors.py` - Functions, classes, imports, decorators, context managers
   - `framework_extractors.py` - Django, SQLAlchemy, Flask, FastAPI, Celery
   - `async_extractors.py` - async/await patterns, AsyncIO
   - `testing_extractors.py` - pytest fixtures, parametrize, markers
   - `type_extractors.py` - TypedDict, Protocol, Generic, Literal, overload
   - `cfg_extractor.py` - Enhanced CFG matching JavaScript sophistication

2. **Database Schema Expansion** - Add 10+ new tables matching React/Vue depth:
   - `python_django_views`, `python_django_forms`, `python_django_admin`
   - `python_async_functions`, `python_pytest_fixtures`, `python_celery_tasks`
   - `python_decorators`, `python_context_managers`, `python_generators`
   - `python_protocols`, `python_generics`, `python_type_aliases`

3. **Comprehensive Test Fixtures** - Build 4,300 lines of fixtures matching TheAuditor complexity:
   - Django app (2,000 lines) - All model types, views, forms, admin
   - Async app (800 lines) - AsyncIO patterns, async context managers
   - Testing patterns (600 lines) - pytest fixtures, parametrize, mocking
   - Advanced types (400 lines) - Protocol, Generic, TypedDict
   - Decorators/context (500 lines) - Custom decorators, context managers, generators

4. **Integration Verification** - Verify taint analysis, query system, performance:
   - Async function taint propagation
   - Django view → model taint flows
   - pytest fixture → test taint flows
   - Performance: <10% regression despite 3x more data

**Success Metrics:**
- Python extraction: 1,584 → ~5,000 lines (modular)
- Database tables: 5 → 15+ Python-specific tables
- Test coverage: 441 → 4,741 lines (10.7x increase)
- Actual parity: 15-20% → 40-50% (vs JavaScript)

## Scope

**IN SCOPE:**
- Refactor existing python_impl.py (no logic changes, just modularization)
- Add extractors for TheAuditor's own Python patterns (self-dogfooding)
- Add 10+ database tables for missing patterns
- Build comprehensive test fixtures (4,300 lines)
- Verify taint analysis integration
- Performance benchmarking

**OUT OF SCOPE:**
- Semantic type inference (Mypy/Pyright integration - 6+ months, deferred)
- Control flow constraint analysis (separate proposal)
- Python import style analysis (low priority, deferred)
- 100% parity with JavaScript (architectural gap accepted)

## Downsides

1. **Code churn** - 1,584 lines refactored, ~3,000 new lines written
2. **Migration risk** - Modularization could introduce bugs if not careful
3. **Test maintenance** - 4,300 lines of fixtures require ongoing maintenance
4. **Still not 100%** - Will reach 40-50% parity, not 100% (semantic gap remains)

## Alternatives Considered

**Alternative 1: Incremental addition (keep monolith)**
- Add new extractors to python_impl.py without refactoring
- **Rejected**: File would grow to 5,000+ lines (unmaintainable)

**Alternative 2: Expand Phase 1 proposal**
- Merge Phase 2 into existing proposal
- **Rejected**: Would create unwieldy 200+ task proposal

**Alternative 3: Pause Python work, focus elsewhere**
- Accept 15-20% parity as "good enough"
- **Rejected**: TheAuditor's own Python patterns must be extracted for self-auditing

## Dependencies

**Prerequisites:**
- Phase 1 must be archived (DONE: `2025-10-30-add-python-extraction-parity`)
- `python-extraction` spec must exist (DONE: 10 requirements)

**Parallel Work:**
- Can be done concurrently with other proposals
- No blocking dependencies on other systems

## Sequencing

**Phase 2.1: Modular Architecture (Sessions 9-10)**
1. Create `/python/` subfolder structure
2. Migrate core extractors (imports, functions, classes, assignments)
3. Migrate framework extractors (Django, SQLAlchemy, Flask, FastAPI)
4. Verify database parity (must match Phase 1 counts exactly)

**Phase 2.2: New Extractors (Sessions 11-12)**
1. Add async_extractors.py (async def, await, AsyncIO)
2. Add testing_extractors.py (pytest fixtures, parametrize)
3. Add type_extractors.py (Protocol, Generic, TypedDict)
4. Add new database tables (10+ tables)

**Phase 2.3: Comprehensive Fixtures (Session 13)**
1. Build Django app fixture (2,000 lines)
2. Build async app fixture (800 lines)
3. Build testing patterns fixture (600 lines)
4. Build advanced types fixture (400 lines)
5. Build decorators/context fixture (500 lines)

**Phase 2.4: Integration & Verification (Sessions 14-15)**
1. Verify taint analysis integration
2. Verify query system integration
3. Performance benchmarking
4. Documentation updates

**Estimated Timeline:** 7-10 sessions, ~8,000 lines of code

## Open Questions

1. **Should Django get dedicated subfolder?** (e.g., `/python/django/views.py`, `/python/django/forms.py`)
   - Leans NO - Keep flat structure like JavaScript

2. **Should CFG extractor be separate file?** (JavaScript has dedicated cfg_extractor.js)
   - Leans YES - Python CFG is 289 lines, will grow with enhancements

3. **What performance threshold triggers optimization?** (Phase 1: <35ms overhead acceptable)
   - Recommendation: <50ms per file for Phase 2 (more extraction = more time)

4. **Should pytest fixture extraction include scope analysis?** (function, class, module, session)
   - Leans YES - Scope is critical for taint analysis (session fixtures affect many tests)
