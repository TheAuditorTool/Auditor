# Python Extraction Mapping: Complete Gap Closure (Phase 4-7)

**Change ID**: python-extraction-mapping
**Type**: Enhancement (Python Extraction Parity)
**Priority**: HIGH
**Status**: PROPOSED
**Date**: 2025-11-01
**Author**: Lead Coder (Sonnet 4.5)
**Supersedes**: python-extraction-phase3-complete (absorbing all remaining work)

---

## Why

### Problem Statement

Phase 3 achieved **70% Python/JavaScript parity** with 75+ extractors and 59 tables. However, comprehensive gap analysis reveals **~100 missing critical patterns** preventing TheAuditor from reaching production-grade Python code intelligence.

**Current Blindspots** (verified 2025-11-01):
- **Core Language**: No walrus operator, augmented assignment, lambdas, comprehensions, exception raising
- **Frameworks**: Django URL patterns missing, FastAPI response models missing, SQLAlchemy cascade details missing
- **Validation**: Pydantic V2 validators not extracted (V2 is now standard), Marshmallow hooks missing
- **Parity**: Python is **20% behind JavaScript** in pattern extraction depth

**Business Impact**:
- Cannot audit modern Python codebases using Python 3.10+ features (walrus, match statements)
- Cannot detect SQL injection in Django URL handlers (routes not extracted)
- Cannot validate Pydantic V2 models (industry standard since 2023)
- Cannot track data flow through comprehensions and lambdas
- Missing 60% of Python patterns means incomplete security analysis

**Why This Matters**:
- Python is 50% of TheAuditor's target projects
- 70% parity = TheAuditor is blind to 30% of critical patterns
- Competitors (Semgrep, CodeQL) have 95%+ Python coverage
- Current gaps create false negatives in security analysis

---

## What Changes

### Scope: 4 Implementation Phases (16-24 weeks)

This proposal maps the path from **70% parity → 95% parity** through systematic gap closure across 4 major phases.

**Phase 4: Core Language Completion** (4-6 weeks)
- Add 22 core Python extractors (walrus, augmented assignment, lambdas, comprehensions, exceptions)
- Create 8 new database tables
- Increase extraction by ~5,000 records on TheAuditor
- **Target**: 78% overall parity

**Phase 5: Framework Deep Dive** (6-8 weeks)
- Add 50+ framework-specific extractors (Django URLs, Flask params, FastAPI response models)
- Create 15+ new database tables
- Increase extraction by ~500 records on TheAuditor
- **Target**: 85% overall parity

**Phase 6: Validation Framework Completion** (4-6 weeks)
- Add 20+ validation extractors (Pydantic V2, Marshmallow, WTForms, DRF)
- Create 6+ new database tables
- Increase extraction by ~270 records on TheAuditor
- **Target**: 91% overall parity

**Phase 7: Parity Polish** (2-4 weeks)
- Add 8 remaining parity extractors (async tasks, type aliases, doctest)
- Create 3+ new database tables
- Increase extraction by ~230 records on TheAuditor
- **Target**: 95% overall parity

### Breaking Changes

**NONE** - This is additive work only. All Phase 2 and Phase 3 extractors remain functional.

---

## Impact

### Affected Specifications
- `specs/python-extraction/spec.md` - Add 100+ new requirements across 7 categories
- **NO** other specs affected (pure additive work)

### Affected Code (Estimated)

**New Files** (7 files, ~3,500 lines):
- `theauditor/ast_extractors/python/expression_extractors.py` - Walrus, augmented, lambdas, comprehensions (600 lines)
- `theauditor/ast_extractors/python/exception_extractors.py` - Raise, try/except, exception hierarchy (400 lines)
- `theauditor/ast_extractors/python/import_extractors.py` - Relative imports, star imports, import chains (300 lines)
- `theauditor/ast_extractors/python/django_url_extractors.py` - Django URL patterns, views (500 lines)
- `theauditor/ast_extractors/python/fastapi_detail_extractors.py` - Response models, WebSockets, background tasks (400 lines)
- `theauditor/ast_extractors/python/pydantic_v2_extractors.py` - Pydantic V2 validators, Field constraints (500 lines)
- `theauditor/ast_extractors/python/marshmallow_detail_extractors.py` - Marshmallow hooks, validators (300 lines)

**Modified Files** (5 files, ~1,200 lines changed):
- `theauditor/ast_extractors/python/framework_extractors.py` - Add SQLAlchemy cascade, Flask params (+400 lines)
- `theauditor/ast_extractors/python/testing_extractors.py` - Add doctest, hypothesis details (+200 lines)
- `theauditor/indexer/extractors/python.py` - Wire all new extractors (+200 lines)
- `theauditor/indexer/schemas/python_schema.py` - Add 32+ new tables (+300 lines)
- `theauditor/indexer/storage.py` - Add storage handlers (+100 lines)

**Database Impact**:
- +32 new tables (59 → 91 tables)
- +6,000 new records extracted from TheAuditor
- Database size increase: ~15% (91MB → 105MB)

### Affected Users
- **Security Analysts**: Can now detect Python-specific vulnerabilities (Django, FastAPI, Pydantic V2)
- **Developers**: Comprehensive code intelligence across all Python patterns
- **DevOps**: Complete infrastructure-as-code analysis (Django settings, FastAPI config)

### Migration Plan
**NONE REQUIRED** - All changes are additive. Existing databases continue to work.

---

## Detailed Gap Analysis

### Tier 1: CRITICAL Gaps (20 patterns) - **Blocks 90% Parity**

#### 1.1 Core Python Language (6 gaps)

| Pattern | Current | Impact | Records Expected |
|---------|---------|--------|------------------|
| Walrus Operator (:=) | NONE | HIGH | ~200 in TheAuditor |
| Augmented Assignment (+=) | NONE | HIGH | ~2,000 in TheAuditor |
| Lambda Functions | NONE | HIGH | ~500 in TheAuditor |
| List/Dict/Set Comprehensions | NONE | HIGH | ~1,500 in TheAuditor |
| Exception Raising (raise) | NONE | CRITICAL | ~800 in TheAuditor |
| Exception Handling (try/except) | Partial | CRITICAL | ~600 in TheAuditor |

**JavaScript Equivalent Coverage**: ✅ Arrow functions, destructuring, spread, throw statements - ALL extracted

#### 1.2 Framework Patterns (9 gaps)

| Framework | Pattern | Current | Records Expected |
|-----------|---------|---------|------------------|
| Django | URL patterns (urls.py) | NONE | ~50 in TheAuditor |
| Django | View methods (get/post/put) | NONE | ~40 in TheAuditor |
| FastAPI | Response models | NONE | ~30 in TheAuditor |
| FastAPI | Request body models | Partial | ~20 in TheAuditor |
| SQLAlchemy | Cascade details | NONE | ~100 in TheAuditor |
| SQLAlchemy | Session operations | NONE | ~50 in TheAuditor |
| Flask | Route parameter types | NONE | ~30 in TheAuditor |
| Celery | Task routing | NONE | ~20 in TheAuditor |
| Celery | Retry policies | NONE | ~15 in TheAuditor |

**JavaScript Equivalent Coverage**: ✅ Express routes with params/middleware - ALL extracted

#### 1.3 Validation Frameworks (5 gaps)

| Framework | Pattern | Current | Records Expected |
|-----------|---------|---------|------------------|
| Pydantic V2 | @field_validator | NONE | ~80 in TheAuditor |
| Pydantic V2 | @model_validator | NONE | ~30 in TheAuditor |
| Pydantic | Field constraints (min_length, ge, le) | NONE | ~40 in TheAuditor |
| Marshmallow | Pre/post load/dump hooks | NONE | ~30 in TheAuditor |
| WTForms | Validator details (DataRequired, Length) | NONE | ~20 in TheAuditor |

**JavaScript Equivalent Coverage**: ✅ Zod `.min()`, `.max()`, `.email()`, `.refine()` - ALL extracted

### Tier 2: HIGH Priority (32 gaps) - **Blocks 95% Parity**

#### 2.1 Core Python Language (8 gaps)

- Default parameter values (NOT extracted) - ~500 expected records
- Relative import levels (from .. import) - ~300 expected records
- Star imports (from x import *) - ~100 expected records
- Mutable default detection - ~50 expected records
- Dataclass field defaults/metadata - ~200 expected records
- Enum member values - ~150 expected records
- Match statement (Python 3.10+) - ~20 expected records
- Context managers (with statement) - ~400 expected records

#### 2.2 Framework Patterns (16 gaps)

**Django** (8 gaps):
- Template tags/filters - ~80 expected
- Management commands - ~20 expected
- Middleware configuration - ~15 expected
- Settings.py extraction - ~100 expected
- Admin configuration - ~30 expected
- Signal sender details - ~20 expected
- Model Manager methods - ~40 expected
- QuerySet method chains - ~60 expected

**Flask** (4 gaps):
- Template rendering (render_template) - ~100 expected
- Session usage (session.get/set) - ~50 expected
- Flask-WTF form usage - ~30 expected
- Flask-RESTful Resource classes - ~20 expected

**FastAPI** (4 gaps):
- WebSocket routes - ~10 expected
- Background tasks - ~15 expected
- Lifespan events - ~5 expected
- APIRouter hierarchy - ~25 expected

#### 2.3 Validation Frameworks (6 gaps)

**Marshmallow**:
- Validator details (Length, Range, Email) - ~20 expected
- Meta.unknown configuration - ~10 expected
- Nested field tracking - ~15 expected

**Django Forms**:
- Meta.fields = '__all__' detection - ~10 expected
- Widget configuration - ~15 expected
- Custom clean methods - ~20 expected

**DRF Serializers**:
- SerializerMethodField tracking - ~25 expected
- Validator details - ~15 expected
- Meta.read_only_fields - ~10 expected

### Tier 3: MEDIUM Priority (30 gaps) - **Polish**

#### 3.1 Async Patterns (3 gaps)
- asyncio.create_task - ~50 expected records
- asyncio.gather - ~30 expected records
- Task result tracking - ~20 expected records

#### 3.2 Type System (2 gaps)
- Type aliases (TypeAlias = Union[...]) - ~50 expected records
- Literal type values - ~30 expected records

#### 3.3 Testing Frameworks (2 gaps)
- Doctest extraction - ~80 expected records
- Hypothesis strategy details - ~20 expected records

### Tier 4: NICE-TO-HAVE (18 gaps) - **Low Priority**

- Multiple assignment unpacking, global/nonlocal, closures, slice operations, delete statements (6 core patterns)
- RQ/APScheduler, Cerberus/Voluptuous, Streamlit/Dash, Peewee/Tortoise, Attrs, Flask-Mail, Django Channels, SQLAlchemy hybrid properties (12 framework patterns)

**Estimated Records**: ~300 across all Tier 4 patterns

---

## Success Metrics

### Quantitative Targets

| Metric | Phase 3 Baseline | Phase 4 | Phase 5 | Phase 6 | Phase 7 | Target |
|--------|------------------|---------|---------|---------|---------|--------|
| **Extractors** | 75 | 97 | 147 | 167 | 175 | 175+ |
| **Tables** | 59 | 67 | 82 | 88 | 91 | 91+ |
| **Records (TheAuditor)** | 7,761 | 12,761 | 13,261 | 13,531 | 13,761 | 13,761+ |
| **Overall Parity** | 70% | 78% | 85% | 91% | 95% | 95% |
| **Core Python Coverage** | 50% | 85% | 85% | 85% | 85% | 85% |
| **Framework Coverage** | 60% | 60% | 90% | 90% | 90% | 90% |
| **Validation Coverage** | 40% | 40% | 40% | 95% | 95% | 95% |
| **Type System Coverage** | 70% | 85% | 85% | 90% | 95% | 95% |
| **Testing Coverage** | 65% | 75% | 75% | 85% | 90% | 90% |

### Qualitative Targets

- **Security Analysis**: Zero false negatives on Pydantic V2 validation, Django URL injection, FastAPI response tampering
- **Code Intelligence**: Complete call graph across lambdas, comprehensions, async flows
- **Performance**: Maintain <10ms per file extraction (no degradation)
- **Reliability**: Zero extraction crashes, 100% test coverage for new extractors
- **Maintainability**: New extractors follow established patterns, <1 hour to add new pattern

---

## Implementation Phases

### Phase 4: Core Language Completion (4-6 weeks)

**Objective**: Close core Python language gaps to reach 85% core coverage

**New Extractors** (22 total):

1. **expression_extractors.py** (8 extractors, 600 lines):
   - `extract_walrus_assignments()` - Walrus operator patterns
   - `extract_augmented_assignments()` - +=, -=, *=, /=, etc.
   - `extract_lambda_functions()` - Lambda expressions
   - `extract_list_comprehensions()` - List comprehensions
   - `extract_dict_comprehensions()` - Dict comprehensions
   - `extract_set_comprehensions()` - Set comprehensions
   - `extract_generator_expressions()` - Generator expressions
   - `extract_ternary_expressions()` - x if y else z

2. **exception_extractors.py** (6 extractors, 400 lines):
   - `extract_exception_raises()` - raise statements
   - `extract_try_except_blocks()` - try/except/finally
   - `extract_exception_handlers()` - except clauses
   - `extract_exception_hierarchy()` - Custom exception classes
   - `extract_context_managers()` - with statements
   - `extract_assert_statements()` - assert with messages

3. **import_extractors.py** (5 extractors, 300 lines):
   - `extract_relative_imports()` - from ..module import (count dots)
   - `extract_star_imports()` - from x import *
   - `extract_conditional_imports()` - if/try-wrapped imports
   - `extract_import_chains()` - x.y.z resolution
   - `extract_aliased_imports()` - import x as y tracking

4. **dataclass_extractors.py** (3 extractors, 200 lines):
   - `extract_dataclass_fields_full()` - Full field details with defaults/metadata
   - `extract_enum_members()` - Enum member names and values
   - `extract_default_parameters()` - Function default values

**New Database Tables** (8 tables):
- `python_walrus_assignments`
- `python_augmented_assignments`
- `python_lambda_functions`
- `python_comprehensions`
- `python_exception_raises`
- `python_try_except_blocks`
- `python_star_imports`
- `python_dataclass_fields_extended`

**Test Fixtures** (800 lines):
- `expression_patterns.py` - Walrus, augmented, lambdas, comprehensions
- `exception_patterns.py` - Raise, try/except, custom exceptions
- `import_patterns.py` - Relative, star, conditional imports

**Estimated Records**: +5,000 records on TheAuditor

**Duration**: 4-6 weeks (1-2 weeks per extractor module)

**Success Criteria**:
- All 22 extractors pass unit tests
- 5,000+ new records extracted from TheAuditor
- Zero performance degradation (<10ms per file maintained)
- Complete exception flow tracking
- Core Python coverage: 50% → 85%

---

### Phase 5: Framework Deep Dive (6-8 weeks)

**Objective**: Close framework-specific gaps to reach 90% framework coverage

**New Extractors** (50+ total):

1. **django_url_extractors.py** (8 extractors, 500 lines):
   - `extract_django_url_patterns()` - path(), re_path() patterns
   - `extract_django_view_methods()` - get/post/put/delete methods
   - `extract_django_template_tags()` - Custom template tags
   - `extract_django_template_filters()` - Custom filters
   - `extract_django_management_commands()` - Management command classes
   - `extract_django_middleware()` - Middleware configuration
   - `extract_django_settings()` - settings.py extraction
   - `extract_django_admin_config()` - Admin.register patterns

2. **flask_detail_extractors.py** (4 extractors, 300 lines):
   - `extract_flask_route_params()` - Route parameter types (<int:id>)
   - `extract_flask_template_rendering()` - render_template calls
   - `extract_flask_session_usage()` - session.get/set patterns
   - `extract_flask_wtf_forms()` - Flask-WTF form usage

3. **fastapi_detail_extractors.py** (6 extractors, 400 lines):
   - `extract_fastapi_response_models()` - response_model parameter
   - `extract_fastapi_request_bodies()` - Body(...) patterns
   - `extract_fastapi_websocket_routes()` - @app.websocket
   - `extract_fastapi_background_tasks()` - BackgroundTasks
   - `extract_fastapi_lifespan()` - Lifespan events
   - `extract_fastapi_router_hierarchy()` - APIRouter nesting

4. **sqlalchemy_detail_extractors.py** (10 extractors, 500 lines):
   - `extract_sqlalchemy_cascade()` - Cascade details (delete, save-update)
   - `extract_sqlalchemy_backref()` - Backref configurations
   - `extract_sqlalchemy_session_ops()` - commit, flush, rollback
   - `extract_sqlalchemy_query_patterns()` - .filter, .join, .group_by
   - `extract_sqlalchemy_hybrid_properties()` - @hybrid_property
   - `extract_sqlalchemy_polymorphic()` - Polymorphic models
   - `extract_sqlalchemy_table_inheritance()` - Inheritance strategies
   - `extract_sqlalchemy_query_loading()` - lazy, eager, joined
   - `extract_sqlalchemy_event_listeners()` - @event.listens_for
   - `extract_sqlalchemy_compiled_caching()` - Compiled cache

5. **celery_detail_extractors.py** (7 extractors, 400 lines):
   - `extract_celery_task_routing()` - queue, exchange routing
   - `extract_celery_retry_policies()` - max_retries, backoff
   - `extract_celery_task_priority()` - priority setting
   - `extract_celery_canvas_patterns()` - chain, group, chord
   - `extract_celery_beat_schedule_details()` - Schedule configuration
   - `extract_celery_result_backends()` - Result backend config
   - `extract_celery_custom_serializers()` - Serializer registration

**New Database Tables** (15 tables):
- `python_django_url_patterns`
- `python_django_view_methods`
- `python_django_template_tags`
- `python_django_management_commands`
- `python_flask_route_params`
- `python_flask_template_rendering`
- `python_fastapi_response_models`
- `python_fastapi_websockets`
- `python_fastapi_background_tasks`
- `python_sqlalchemy_cascades`
- `python_sqlalchemy_session_ops`
- `python_sqlalchemy_query_patterns`
- `python_celery_routing`
- `python_celery_retry_policies`
- `python_celery_canvas`

**Test Fixtures** (1,200 lines):
- `django_urls_patterns.py` - Django URL conf examples
- `flask_advanced_patterns.py` - Flask params, templates, session
- `fastapi_advanced_patterns.py` - Response models, WebSockets, background
- `sqlalchemy_advanced_patterns.py` - Cascade, queries, hybrid properties
- `celery_advanced_patterns.py` - Routing, retry, canvas

**Estimated Records**: +500 records on TheAuditor

**Duration**: 6-8 weeks (1-2 weeks per framework module)

**Success Criteria**:
- All 50+ extractors pass unit tests
- 500+ new records extracted from TheAuditor
- Django URL pattern detection at 100%
- FastAPI response model tracking complete
- SQLAlchemy cascade details captured
- Framework coverage: 60% → 90%

---

### Phase 6: Validation Framework Completion (4-6 weeks)

**Objective**: Close validation framework gaps to reach 95% validation coverage

**New Extractors** (20+ total):

1. **pydantic_v2_extractors.py** (8 extractors, 500 lines):
   - `extract_pydantic_field_validators()` - @field_validator decorators
   - `extract_pydantic_model_validators()` - @model_validator decorators
   - `extract_pydantic_field_constraints()` - Field(min_length, pattern, ge, le)
   - `extract_pydantic_model_config()` - model_config settings
   - `extract_pydantic_computed_fields()` - @computed_field
   - `extract_pydantic_custom_validators()` - Custom validation functions
   - `extract_pydantic_validator_modes()` - 'before', 'after', 'wrap'
   - `extract_pydantic_v1_v2_detection()` - Detect V1 vs V2 usage

2. **marshmallow_detail_extractors.py** (6 extractors, 300 lines):
   - `extract_marshmallow_pre_load()` - @pre_load hooks
   - `extract_marshmallow_post_load()` - @post_load hooks
   - `extract_marshmallow_pre_dump()` - @pre_dump hooks
   - `extract_marshmallow_post_dump()` - @post_dump hooks
   - `extract_marshmallow_validators()` - Length, Range, Email, URL validators
   - `extract_marshmallow_meta()` - Meta.unknown, Meta.partial

3. **wtforms_detail_extractors.py** (3 extractors, 200 lines):
   - `extract_wtforms_validators()` - DataRequired, Length, Email validators
   - `extract_wtforms_field_constraints()` - Field-level constraints
   - `extract_wtforms_widget_config()` - Widget configuration

4. **django_forms_detail_extractors.py** (3 extractors, 200 lines):
   - `extract_django_form_validators()` - Custom validators
   - `extract_django_form_meta()` - Meta.fields = '__all__' detection
   - `extract_django_form_widgets()` - Widget configuration

**New Database Tables** (6 tables):
- `python_pydantic_field_validators` (V2)
- `python_pydantic_model_validators` (V2)
- `python_pydantic_field_constraints`
- `python_marshmallow_hooks`
- `python_marshmallow_validators`
- `python_wtforms_validators`

**Test Fixtures** (600 lines):
- `pydantic_v2_patterns.py` - Pydantic V2 validators, Field constraints
- `marshmallow_advanced_patterns.py` - Hooks, validators, Meta config
- `wtforms_patterns.py` - Validators, constraints, widgets
- `django_forms_patterns.py` - Form validators, Meta config

**Estimated Records**: +270 records on TheAuditor

**Duration**: 4-6 weeks (1 week per framework module)

**Success Criteria**:
- All 20+ extractors pass unit tests
- 270+ new records extracted from TheAuditor
- Pydantic V2 as first-class citizen
- Marshmallow hooks fully tracked
- WTForms validation complete
- Validation coverage: 40% → 95%

---

### Phase 7: Parity Polish (2-4 weeks)

**Objective**: Close remaining parity gaps to reach 95% overall parity

**New Extractors** (8 total):

1. **async_task_extractors.py** (3 extractors, 200 lines):
   - `extract_asyncio_create_task()` - asyncio.create_task patterns
   - `extract_asyncio_gather()` - asyncio.gather patterns
   - `extract_async_task_results()` - Task result tracking

2. **type_alias_extractors.py** (2 extractors, 150 lines):
   - `extract_type_aliases()` - TypeAlias = Union[...] patterns
   - `extract_literal_values()` - Literal['a', 'b'] values

3. **doctest_extractors.py** (1 extractor, 100 lines):
   - `extract_doctest_examples()` - >>> doctest extraction

4. **hypothesis_detail_extractors.py** (1 extractor, 100 lines):
   - `extract_hypothesis_strategy_details()` - Strategy parameters

5. **enum_detail_extractors.py** (1 extractor, 100 lines):
   - `extract_enum_member_values()` - Enum member values and auto()

**New Database Tables** (3 tables):
- `python_async_task_patterns`
- `python_type_aliases`
- `python_doctest_examples`

**Test Fixtures** (400 lines):
- `async_task_patterns.py` - asyncio.create_task, gather
- `type_alias_patterns.py` - Type aliases, Literal values
- `doctest_patterns.py` - Doctest examples

**Estimated Records**: +230 records on TheAuditor

**Duration**: 2-4 weeks

**Success Criteria**:
- All 8 extractors pass unit tests
- 230+ new records extracted from TheAuditor
- Async task orchestration complete
- Type alias tracking complete
- Doctest extraction complete
- Overall parity: 91% → 95%

---

## Timeline

**Total Duration**: 16-24 weeks (4-6 months)

```
Week 1-6:   Phase 4 (Core Language)        → 78% parity
Week 7-14:  Phase 5 (Frameworks)           → 85% parity
Week 15-20: Phase 6 (Validation)           → 91% parity
Week 21-24: Phase 7 (Polish)               → 95% parity
```

**Milestones**:
- Week 6: Core Python extraction complete, 5,000+ new records
- Week 14: Framework extraction complete, 500+ new records
- Week 20: Validation extraction complete, 270+ new records
- Week 24: Parity polish complete, 230+ new records

**Checkpoints** (every 2 weeks):
- Database record count verification
- Performance benchmark (maintain <10ms per file)
- Test coverage check (100% for new extractors)
- OpenSpec documentation sync

---

## Risk Analysis

### High Risks

1. **Performance Degradation**
   - **Probability**: MEDIUM (100+ new extractors could slow extraction)
   - **Impact**: HIGH (users expect <10ms per file)
   - **Mitigation**: Profile after each phase, optimize hot paths, single-pass AST walking
   - **Contingency**: Defer non-critical extractors if performance degrades >20%

2. **Schema Complexity**
   - **Probability**: LOW (32 new tables increases complexity)
   - **Impact**: MEDIUM (harder to maintain)
   - **Mitigation**: Follow Phase 3 schema patterns, comprehensive testing
   - **Contingency**: Consolidate tables if schema becomes unmanageable

3. **Pydantic V1/V2 Compatibility**
   - **Probability**: MEDIUM (must support both versions)
   - **Impact**: HIGH (breaking users on V1)
   - **Mitigation**: Version detection, separate extractors for V1/V2
   - **Contingency**: Focus on V2, add V1 detection warnings

### Medium Risks

4. **Test Fixture Maintenance**
   - **Probability**: MEDIUM (2,000+ lines of new fixtures)
   - **Impact**: MEDIUM (hard to maintain)
   - **Mitigation**: Organize by phase, use real-world examples
   - **Contingency**: Generate fixtures programmatically if needed

5. **Framework API Changes**
   - **Probability**: LOW (Django, Flask, FastAPI APIs change)
   - **Impact**: MEDIUM (extractors break)
   - **Mitigation**: Pin framework versions in tests, version detection
   - **Contingency**: Add compatibility layers for multiple framework versions

### Low Risks

6. **Memory Exhaustion**
   - **Probability**: LOW (91 tables could exceed memory)
   - **Impact**: MEDIUM (crashes on large projects)
   - **Mitigation**: Lazy loading, streaming extraction, memory profiling
   - **Contingency**: Add memory limits, batch processing

---

## Rollback Plan

### Phase Rollback

If any phase fails critically:
1. **Git**: Each phase on separate branch (`pythonmapping-phase4`, `pythonmapping-phase5`, etc.)
2. **Database**: Snapshots in .pf/history/full/ before each phase
3. **Code**: Phase 3 baseline (75 extractors, 59 tables) always available on `pythonparity` branch

### Partial Rollback

If specific extractors fail:
1. Disable extractor in python.py
2. Remove table from schema
3. Continue with remaining extractors

### Data Recovery

- Phase 3 baseline: 7,761 records verified
- Daily snapshots during implementation
- Test projects for verification (TheAuditor, plant, PlantFlow, project_anarchy)

---

## Verification Strategy (teamsop.md Prime Directive)

### Pre-Implementation Verification Phase

Before implementing each phase, the Coder SHALL:

1. **Read Source Files**:
   - Read all relevant extractor modules (`theauditor/ast_extractors/python/`)
   - Read schema file (`theauditor/indexer/schemas/python_schema.py`)
   - Read storage handlers (`theauditor/indexer/storage.py`)
   - Read database writers (`theauditor/indexer/database/python_database.py`)

2. **State Hypotheses**:
   ```
   Hypothesis 1: Current walrus operator extraction = NONE
   Verification: Grep for "walrus" in extractors → ✅ Confirmed, no extraction

   Hypothesis 2: Database has <60 Python tables
   Verification: Count tables in python_schema.py → ✅ Confirmed, 59 tables

   Hypothesis 3: Pydantic V2 validators not extracted
   Verification: Grep for "field_validator" → ✅ Confirmed, only V1 @validator
   ```

3. **Verify Assumptions**:
   - Test fixture coverage: Count lines in `tests/fixtures/python/`
   - Current record count: Query `SELECT COUNT(*) FROM python_*` tables
   - Existing extractor patterns: Read and understand current implementation

4. **Document Discrepancies**:
   - Note any mismatches between proposal and reality
   - Update proposal if needed
   - Flag blockers before implementation

### During Implementation

For each extractor:
1. Write extractor function
2. Test directly with sample code (unit test first)
3. Add schema and database writer
4. Wire into pipeline
5. Create test fixture
6. Verify extraction with database queries

### Post-Implementation Audit

After each phase:
1. Re-read all modified files to confirm correctness
2. Run `aud index` on TheAuditor
3. Query all new tables for data
4. Compare counts with expectations
5. Performance benchmark
6. Memory usage check

**Report Template**: See `verification.md` for detailed teamsop.md C-4.20 format

---

## Absorption of Phase 3 Work

### What This Ticket Absorbs from python-extraction-phase3-complete

**Completed Work** (KEEP AS-IS):
- ✅ 75 extractors implemented (Flask, Security, Django, Testing)
- ✅ 59 database tables created
- ✅ 7,761 records extracted
- ✅ ORM deduplication bug fixed
- ✅ 832 lines of test fixtures

**Incomplete Work** (ABSORB INTO THIS TICKET):
- ⏸️ Performance optimization (Tasks 32-36) → Move to Phase 7
- ⏸️ Integration testing (Tasks 37-40) → Move to Phase 7
- ⚠️ Flask route test failing → Fix in Phase 5

**Documentation** (SUPERSEDE):
- This ticket supersedes all Phase 3 documentation
- Phase 3 can be archived after this ticket is approved
- All Phase 3 achievements documented here as baseline

### Migration Path

1. **Approve this ticket** (`python-extraction-mapping`)
2. **Archive Phase 3 ticket** (`openspec archive python-extraction-phase3-complete --skip-specs --yes`)
3. **Begin Phase 4 implementation** (this ticket)

---

## Dependencies

**Hard Dependencies** (MUST be resolved before starting):
- NONE - All Phase 3 work is complete and functional

**Soft Dependencies** (nice to have):
- Taint analysis fixes (Track A) - Enables validation of security pattern extraction
- GraphQL extraction completion - Enables cross-framework analysis

---

## Approval Checklist

- [ ] Gap analysis verified against source code
- [ ] Phase 4-7 extractors clearly defined
- [ ] Database impact assessed (32 new tables, +6,000 records)
- [ ] Performance impact evaluated (<10ms per file maintained)
- [ ] Test fixtures planned (2,000+ lines)
- [ ] Timeline realistic (16-24 weeks)
- [ ] Risk mitigation strategies defined
- [ ] Rollback plan documented
- [ ] teamsop.md verification protocols integrated
- [ ] Phase 3 work properly absorbed

---

## Approval

**Lead Coder**: Proposal complete, ready for review
**Lead Auditor**: [Pending review]
**Architect**: [Pending approval]

---

**END OF PROPOSAL**

**Next Steps After Approval**:
1. Archive `python-extraction-phase3-complete`
2. Create Phase 4 implementation branch
3. Begin verification phase for core language extractors
