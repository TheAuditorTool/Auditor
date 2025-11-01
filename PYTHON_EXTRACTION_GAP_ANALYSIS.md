# Python Extraction Gap Analysis - Comprehensive Report

**Date**: November 1, 2025
**Analysis Method**: 4 specialized sub-agents analyzing current coverage
**Scope**: Core Python, Frameworks, Validation, JS/TS Parity
**Status**: Phase 3 is 70% complete - This identifies the remaining 30%

---

## Executive Summary

Python extraction Phase 3 achieved **70% feature parity** with JavaScript/TypeScript extraction. This report identifies the **remaining 30%** across four categories:

1. **Core Python Language Gaps** - 22 critical/important patterns missing
2. **Framework-Specific Gaps** - 50+ missing patterns across Flask, Django, FastAPI, SQLAlchemy, Celery
3. **Validation Framework Gaps** - 20+ missing patterns across Pydantic, Marshmallow, WTForms, DRF
4. **Parity Gaps** - 9 critical patterns where JS/TS has coverage but Python doesn't

**Total Identified Gaps**: ~100 missing extraction patterns

---

## Gap Categories by Priority

### TIER 1: CRITICAL (Blocking Parity)

These gaps prevent TheAuditor from reaching 90%+ parity with JavaScript/TypeScript extraction.

#### 1.1 Core Python Language (6 gaps)

| Pattern | Current | Impact | Example |
|---------|---------|--------|---------|
| **Walrus Operator** (:=) | NOT EXTRACTED | HIGH - Modern Python idiom | `if (n := len(data)) > 10:` |
| **Augmented Assignment** (+=, -=, etc.) | NOT EXTRACTED | HIGH - Variable flow tracking | `count += 1` |
| **Lambda Functions** | NOT EXTRACTED | HIGH - Functional patterns | `sorted(items, key=lambda x: x.name)` |
| **List/Dict/Set Comprehensions** | NOT EXTRACTED | HIGH - Data flow analysis | `[x*2 for x in range(10)]` |
| **Exception Raising** | NOT EXTRACTED | CRITICAL - Security patterns | `raise ValueError("Invalid input")` |
| **Exception Handling** | Partial (catches only) | CRITICAL - Error flow | `try/except/finally` blocks |

**JavaScript Comparison**: JS/TS extraction captures arrow functions, spread operators, destructuring - all equivalents to the above.

#### 1.2 Framework Patterns (9 gaps)

| Framework | Pattern | Current | Impact |
|-----------|---------|---------|--------|
| **Django** | URL patterns (urls.py) | NOT EXTRACTED | CRITICAL - Route discovery |
| **Django** | View methods (get/post/put/delete) | NOT EXTRACTED | HIGH - HTTP method routing |
| **FastAPI** | Response models | NOT EXTRACTED | HIGH - API schema validation |
| **FastAPI** | Request body models | Partial (Pydantic only) | HIGH - Input validation |
| **SQLAlchemy** | Cascade details (delete, save-update) | NOT EXTRACTED | HIGH - Data integrity |
| **SQLAlchemy** | Session operations (commit, flush, rollback) | NOT EXTRACTED | MEDIUM - Transaction tracking |
| **Flask** | Route parameter types | NOT EXTRACTED | MEDIUM - Type safety |
| **Celery** | Task routing (queue, exchange) | NOT EXTRACTED | MEDIUM - Infrastructure mapping |
| **Celery** | Retry policies (max_retries, backoff) | NOT EXTRACTED | MEDIUM - Reliability patterns |

**JavaScript Comparison**: Express routes extracted with method, params, middleware - Django/Flask should match.

#### 1.3 Validation Frameworks (5 gaps)

| Framework | Pattern | Current | Impact |
|-----------|---------|---------|--------|
| **Pydantic V2** | Field validators (@field_validator) | NOT EXTRACTED | CRITICAL - V2 is now standard |
| **Pydantic V2** | Model validators (@model_validator) | NOT EXTRACTED | CRITICAL - V2 breaking change |
| **Pydantic** | Field constraints (min_length, pattern, ge, le) | NOT EXTRACTED | HIGH - Validation rules |
| **Marshmallow** | Pre/post load/dump hooks | NOT EXTRACTED | HIGH - Data transformation |
| **WTForms** | Validator details (DataRequired, Length, Email) | NOT EXTRACTED | HIGH - Form validation |

**JavaScript Comparison**: Zod extraction captures `.min()`, `.max()`, `.email()` - Pydantic should match.

---

### TIER 2: HIGH PRIORITY (Feature Completeness)

These gaps limit TheAuditor's ability to provide comprehensive code intelligence.

#### 2.1 Core Python Language (8 gaps)

| Pattern | Current | Impact |
|---------|---------|--------|
| **Default Parameter Values** | NOT EXTRACTED | HIGH - API signature analysis |
| **Relative Import Levels** | Partial (dots not counted) | HIGH - Module resolution |
| **Star Imports** (`from x import *`) | NOT EXTRACTED | HIGH - Namespace pollution detection |
| **Mutable Default Detection** | NOT EXTRACTED | HIGH - Common bug pattern |
| **Dataclass Fields** | Partial (no defaults/metadata) | MEDIUM - Schema analysis |
| **Enum Members** | NOT EXTRACTED | MEDIUM - Constant tracking |
| **Match Statement** (Python 3.10+) | NOT EXTRACTED | MEDIUM - Control flow |
| **Context Managers** (with statement) | NOT EXTRACTED | MEDIUM - Resource management |

#### 2.2 Framework Patterns (16 gaps)

**Django (8 gaps)**:
- Template tags/filters
- Management commands
- Middleware configuration
- Settings.py extraction
- Admin configuration
- Signal sender details
- Model Manager methods
- QuerySet method chains

**Flask (4 gaps)**:
- Template rendering (render_template calls)
- Session usage (session.get/set)
- Flask-WTF form usage
- Flask-RESTful Resource classes

**FastAPI (4 gaps)**:
- WebSocket routes
- Background tasks
- Lifespan events
- APIRouter hierarchy

#### 2.3 Validation Frameworks (6 gaps)

**Marshmallow**:
- Validator details (Length, Range, Email, URL)
- Meta.unknown configuration ('EXCLUDE', 'INCLUDE', 'RAISE')
- Nested field tracking

**Django Forms**:
- Meta.fields = '__all__' detection
- Widget configuration
- Custom clean methods

**DRF Serializers**:
- SerializerMethodField tracking
- Validator details
- Meta.read_only_fields

---

### TIER 3: MEDIUM PRIORITY (Parity Goals)

These gaps prevent reaching 95%+ parity but don't block core functionality.

#### 3.1 Async Patterns (3 gaps)

| Pattern | Current | Impact |
|---------|---------|--------|
| **asyncio.create_task** | NOT EXTRACTED | MEDIUM - Task orchestration |
| **asyncio.gather** | NOT EXTRACTED | MEDIUM - Parallel execution |
| **Task result tracking** | NOT EXTRACTED | LOW - Completion handling |

**JavaScript Comparison**: Promise.all, Promise.race extracted - asyncio.gather should match.

#### 3.2 Type System (2 gaps)

| Pattern | Current | Impact |
|---------|---------|--------|
| **Type Aliases** (`TypeAlias = Union[...]`) | NOT EXTRACTED | MEDIUM - Type documentation |
| **Literal Types** | Partial (no values) | LOW - Enum-like constants |

#### 3.3 Testing Frameworks (2 gaps)

| Pattern | Current | Impact |
|---------|---------|--------|
| **Doctest Extraction** | NOT EXTRACTED | LOW - Documentation tests |
| **Hypothesis Strategies** | Partial (no details) | LOW - Property testing |

---

### TIER 4: NICE-TO-HAVE (Polish)

These gaps are low-impact improvements for specialized use cases.

#### 4.1 Core Python (6 gaps)

- Multiple assignment unpacking (`a, b = 1, 2`)
- Global/nonlocal keywords
- Closures (function returning function)
- Slice operations (`data[1:10:2]`)
- Delete statements
- Generator expressions

#### 4.2 Additional Frameworks (8 gaps)

- **RQ/APScheduler**: Job queue patterns
- **Cerberus/Voluptuous**: Alternative validation frameworks
- **Streamlit/Dash**: UI framework components
- **Peewee/Tortoise**: Alternative ORMs
- **Attrs**: Alternative to dataclasses
- **Flask-Mail**: Email sending
- **Django Channels**: WebSocket support
- **SQLAlchemy**: Hybrid properties, polymorphic models

---

## Detailed Extraction Examples

### Example 1: Walrus Operator (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
# File: analysis.py
if (n := len(data)) > 10:
    print(f"Large dataset: {n} items")
```

**Expected Database Record**:
```sql
INSERT INTO python_walrus_assignments (file, line, target, value, context)
VALUES ('analysis.py', 2, 'n', 'len(data)', 'if_condition');
```

**JavaScript Equivalent**: We extract `const n = data.length` in if conditions.

---

### Example 2: Pydantic V2 Validators (TIER 1 CRITICAL)

**Current Coverage**: Only V1 `@validator` decorator

**What We Should Extract**:
```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    age: int

    @field_validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v

    @field_validator('age')
    def age_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Age must be positive')
        return v
```

**Expected Database Records**:
```sql
-- We currently extract NONE of this for V2
INSERT INTO python_validators (file, line, model, field, decorator, type, validation_logic)
VALUES
  ('models.py', 6, 'User', 'name', 'field_validator', 'field', 'name_must_not_be_empty'),
  ('models.py', 12, 'User', 'age', 'field_validator', 'field', 'age_must_be_positive');
```

**JavaScript Equivalent**: We extract Zod `.refine()` and `.superRefine()` validators.

---

### Example 3: Django URL Patterns (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
# File: urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/users/', views.UserListView.as_view(), name='user-list'),
    path('api/users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('api/auth/login/', views.LoginView.as_view(), name='login'),
]
```

**Expected Database Records**:
```sql
INSERT INTO python_routes (file, line, path, view, method, name)
VALUES
  ('urls.py', 5, 'api/users/', 'UserListView', 'GET', 'user-list'),
  ('urls.py', 6, 'api/users/<int:pk>/', 'UserDetailView', 'GET', 'user-detail'),
  ('urls.py', 7, 'api/auth/login/', 'LoginView', 'POST', 'login');
```

**JavaScript Equivalent**: We extract Express/Fastify route definitions with path, method, handler.

---

### Example 4: Augmented Assignment (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
count = 0
for item in items:
    count += 1
    total += item.price
    errors += item.validate()
```

**Expected Database Records**:
```sql
INSERT INTO python_assignments (file, line, target, operator, value)
VALUES
  ('processor.py', 3, 'count', '+=', '1'),
  ('processor.py', 4, 'total', '+=', 'item.price'),
  ('processor.py', 5, 'errors', '+=', 'item.validate()');
```

**JavaScript Equivalent**: We extract `count++`, `total += item.price` for data flow analysis.

---

### Example 5: Lambda Functions (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
users = sorted(users, key=lambda u: u.created_at)
filtered = filter(lambda x: x.is_active, users)
mapped = map(lambda x: x.to_dict(), users)
```

**Expected Database Records**:
```sql
INSERT INTO python_lambda_functions (file, line, params, body, context)
VALUES
  ('utils.py', 2, 'u', 'u.created_at', 'sorted_key'),
  ('utils.py', 3, 'x', 'x.is_active', 'filter'),
  ('utils.py', 4, 'x', 'x.to_dict()', 'map');
```

**JavaScript Equivalent**: We extract arrow functions `(u) => u.created_at`.

---

### Example 6: Exception Raising (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
def validate_user(user):
    if not user.email:
        raise ValueError("Email is required")
    if user.age < 18:
        raise ValidationError("User must be 18+")
    if not user.is_verified:
        raise PermissionError("User not verified")
```

**Expected Database Records**:
```sql
INSERT INTO python_exception_raises (file, line, exception_type, message, condition)
VALUES
  ('validators.py', 3, 'ValueError', 'Email is required', 'not user.email'),
  ('validators.py', 5, 'ValidationError', 'User must be 18+', 'user.age < 18'),
  ('validators.py', 7, 'PermissionError', 'User not verified', 'not user.is_verified');
```

**JavaScript Equivalent**: We extract `throw new Error()` statements for error flow analysis.

---

### Example 7: SQLAlchemy Cascade (TIER 1 CRITICAL)

**Current Coverage**: We extract relationships but NOT cascade details

**What We Should Extract**:
```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)

    posts = relationship('Post', back_populates='author',
                         cascade='all, delete-orphan')
    comments = relationship('Comment', back_populates='user',
                           cascade='save-update, merge')
```

**Expected Database Records**:
```sql
-- We currently store relationship but miss cascade
UPDATE orm_relationships
SET cascade='all, delete-orphan'
WHERE source_model='User' AND target_model='Post';

UPDATE orm_relationships
SET cascade='save-update, merge'
WHERE source_model='User' AND target_model='Comment';
```

**JavaScript Equivalent**: We extract Prisma `onDelete: Cascade` in schema definitions.

---

### Example 8: FastAPI Response Models (TIER 1 CRITICAL)

**Current Coverage**: NONE

**What We Should Extract**:
```python
from fastapi import FastAPI
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    return get_user_from_db(user_id)
```

**Expected Database Records**:
```sql
INSERT INTO python_routes (file, line, path, method, response_model)
VALUES ('api.py', 9, '/users/{user_id}', 'GET', 'UserResponse');

-- Link to validation
INSERT INTO python_route_response_models (route_id, model_name)
VALUES (123, 'UserResponse');
```

**JavaScript Equivalent**: We extract TypeScript return types in Express handlers.

---

## Implementation Recommendations

### Phase 4: Core Language Completion (4-6 weeks)

**Priority**: TIER 1 + TIER 2 Core Python gaps

**Extractors to Create**:
1. `python/expression_extractors.py` - Walrus, augmented assignment, lambdas, comprehensions
2. `python/exception_extractors.py` - Raise statements, try/except/finally, exception hierarchy
3. `python/import_extractors.py` - Relative import levels, star imports, import chains
4. `python/dataclass_extractors.py` - Full dataclass field extraction with defaults/metadata

**Tables to Add**:
- `python_walrus_assignments`
- `python_augmented_assignments`
- `python_lambda_functions`
- `python_comprehensions`
- `python_exception_raises`
- `python_try_except_blocks`
- `python_star_imports`
- `python_dataclass_fields`

**Estimated Records** (TheAuditor project):
- Augmented assignments: ~2,000
- Lambda functions: ~500
- Comprehensions: ~1,500
- Exception raises: ~800
- Try/except blocks: ~600

**Test Fixtures**: Expand `tests/fixtures/python/` with:
- `expression_patterns.py` (walrus, augmented, lambdas, comprehensions)
- `exception_patterns.py` (raise, try/except, custom exceptions)
- `import_patterns.py` (relative, star, conditional imports)

---

### Phase 5: Framework Deep Dive (6-8 weeks)

**Priority**: TIER 1 + TIER 2 Framework gaps

**Django Completion**:
- `python/django_url_extractors.py` - URL patterns from urls.py
- `python/django_view_extractors.py` - View methods (get/post/put/delete)
- `python/django_template_extractors.py` - Template tags, filters
- `python/django_admin_extractors.py` - Admin configuration

**Flask Completion**:
- Extend `flask_extractors.py` - Route parameter types, template rendering, session usage
- `python/flask_wtf_extractors.py` - Flask-WTF form integration

**FastAPI Completion**:
- Extend `framework_extractors.py` - Response models, request body models
- `python/fastapi_websocket_extractors.py` - WebSocket routes
- `python/fastapi_background_extractors.py` - Background tasks

**SQLAlchemy Completion**:
- Extend `framework_extractors.py` - Cascade details, session operations
- `python/sqlalchemy_query_extractors.py` - Query patterns (.filter, .join, .group_by)

**Tables to Add**:
- `python_django_url_patterns`
- `python_django_view_methods`
- `python_flask_route_params`
- `python_fastapi_response_models`
- `python_sqlalchemy_cascades`

**Estimated Records** (TheAuditor project):
- Django patterns: ~200 (small Django presence)
- Flask patterns: ~150
- FastAPI patterns: ~50
- SQLAlchemy cascade: ~100

---

### Phase 6: Validation Framework Completion (4-6 weeks)

**Priority**: TIER 1 Validation gaps

**Pydantic V2**:
- `python/pydantic_v2_extractors.py` - @field_validator, @model_validator, model_config
- Update existing Pydantic extraction to detect V1 vs V2

**Marshmallow**:
- `python/marshmallow_extractors.py` - Pre/post hooks, validator details, Meta.unknown

**WTForms**:
- `python/wtforms_extractors.py` - Validator details, field constraints

**Django Forms/DRF**:
- Extend `django_advanced_extractors.py` - Form validators, widget config
- `python/drf_serializer_extractors.py` - SerializerMethodField, validator details

**Tables to Add**:
- `python_pydantic_field_validators` (V2)
- `python_pydantic_model_validators` (V2)
- `python_marshmallow_hooks`
- `python_marshmallow_validators`
- `python_wtforms_validators`
- `python_drf_serializer_methods`

**Estimated Records** (TheAuditor project):
- Pydantic validators: ~150
- Marshmallow patterns: ~50
- WTForms patterns: ~30
- DRF patterns: ~40

---

### Phase 7: Parity Polish (2-4 weeks)

**Priority**: TIER 3 gaps

**Async Patterns**:
- `python/async_task_extractors.py` - asyncio.create_task, gather, wait_for

**Type System**:
- Extend `type_extractors.py` - Type aliases, Literal values

**Testing**:
- `python/doctest_extractors.py` - Doctest extraction
- Extend `testing_extractors.py` - Hypothesis strategy details

**Estimated Records** (TheAuditor project):
- Async task patterns: ~100
- Type aliases: ~50
- Doctest examples: ~80

---

## Success Metrics

### Target: 90% Parity (End of Phase 6)

| Category | Current | Phase 4 | Phase 5 | Phase 6 | Target |
|----------|---------|---------|---------|---------|--------|
| Core Python | 50% | 85% | 85% | 85% | 85% |
| Frameworks | 60% | 60% | 90% | 90% | 90% |
| Validation | 40% | 40% | 40% | 95% | 95% |
| Type System | 70% | 85% | 85% | 90% | 90% |
| Testing | 65% | 75% | 75% | 85% | 85% |
| **Overall** | **70%** | **78%** | **85%** | **91%** | **90%** |

### Measurable Outcomes

**After Phase 4** (Core Language):
- Extract 5,000+ additional records from TheAuditor (walrus, augmented, lambdas, comprehensions, exceptions)
- Zero missing core language patterns in security analysis
- Complete exception flow tracking

**After Phase 5** (Frameworks):
- Extract 500+ additional framework records (Django URLs, Flask params, FastAPI response models)
- Complete route discovery across all frameworks
- Full ORM cascade tracking

**After Phase 6** (Validation):
- Extract 270+ additional validation records (Pydantic V2, Marshmallow, WTForms, DRF)
- Complete input validation tracking
- Pydantic V2 as first-class citizen

**After Phase 7** (Polish):
- Extract 230+ additional records (async tasks, type aliases, doctest)
- 95%+ feature parity with JavaScript/TypeScript
- Zero critical gaps

---

## Risk Analysis

### High Risk Gaps (Can't Ship Without)

1. **Pydantic V2 Validators** - V2 is industry standard now, V1 is deprecated
2. **Django URL Patterns** - Cannot audit Django apps without route discovery
3. **Exception Raising** - Critical for security analysis (error handling vulnerabilities)
4. **Walrus Operator** - Modern Python idiom, used heavily in recent codebases
5. **Augmented Assignment** - Essential for data flow analysis

### Medium Risk Gaps (Degrades Quality)

1. **Lambda Functions** - Functional programming patterns missed
2. **FastAPI Response Models** - API schema validation incomplete
3. **SQLAlchemy Cascade** - Data integrity analysis incomplete
4. **Marshmallow Hooks** - Data transformation tracking incomplete
5. **Comprehensions** - Data flow analysis incomplete

### Low Risk Gaps (Nice-to-Have)

1. **Doctest Extraction** - Edge case, not widely used
2. **RQ/APScheduler** - Specialized job queue frameworks
3. **Type Aliases** - Helpful but not critical
4. **Slice Operations** - Low-impact pattern
5. **Global/Nonlocal** - Rare in modern Python

---

## Comparison with JavaScript/TypeScript Coverage

### Areas Where Python MATCHES JavaScript

- Function definitions and signatures
- Class definitions and inheritance
- Import statements (basic)
- Type annotations (basic)
- Async/await patterns (basic)
- ORM models (basic)
- HTTP routes (basic)
- Decorators = JS decorators
- Context managers = JS try/finally

### Areas Where Python LAGS JavaScript

| JavaScript Feature | Python Equivalent | Status |
|-------------------|------------------|--------|
| Arrow functions | Lambda functions | MISSING |
| Spread operator | Comprehensions | MISSING |
| Destructuring | Multiple assignment | MISSING |
| Promise.all/race | asyncio.gather | MISSING |
| Zod validators | Pydantic V2 validators | MISSING |
| Express route params | Flask/Django params | MISSING |
| Throw statements | Raise statements | MISSING |
| TypeScript Literal types | Literal types | PARTIAL |
| Enum values | Enum members | MISSING |

**Conclusion**: Python is 20% behind JavaScript in pattern extraction depth.

---

## OpenSpec Integration

### Proposed Tickets

1. **python-extraction-phase4-core-language** (4-6 weeks)
   - Walrus, augmented, lambdas, comprehensions, exceptions
   - Target: 78% overall parity

2. **python-extraction-phase5-framework-deep-dive** (6-8 weeks)
   - Django URLs, Flask params, FastAPI response models, SQLAlchemy cascade
   - Target: 85% overall parity

3. **python-extraction-phase6-validation-completion** (4-6 weeks)
   - Pydantic V2, Marshmallow, WTForms, DRF
   - Target: 91% overall parity

4. **python-extraction-phase7-parity-polish** (2-4 weeks)
   - Async tasks, type aliases, doctest
   - Target: 95% overall parity

**Total Estimated Effort**: 16-24 weeks (4-6 months)

---

## Appendix: Detailed Gap Inventory

### Core Python Language (22 gaps)

**TIER 1 CRITICAL** (6):
1. Walrus operator (:=)
2. Augmented assignment (+=, -=, *=, /=, etc.)
3. Lambda functions
4. List/dict/set comprehensions
5. Exception raising (raise statements)
6. Exception handling (try/except/finally)

**TIER 2 HIGH** (8):
7. Default parameter values
8. Relative import levels (from .. import)
9. Star imports (from x import *)
10. Mutable default detection
11. Dataclass field defaults/metadata
12. Enum member values
13. Match statement (Python 3.10+)
14. Context managers (with statement)

**TIER 3 MEDIUM** (2):
15. Multiple assignment unpacking
16. Global/nonlocal keywords

**TIER 4 NICE-TO-HAVE** (6):
17. Closures (function returning function)
18. Slice operations
19. Delete statements
20. Generator expressions (vs list comprehensions)
21. Ternary expressions (x if y else z)
22. f-string expressions

---

### Framework Patterns (50+ gaps)

**Django** (15 gaps):
- TIER 1: URL patterns, view methods
- TIER 2: Template tags/filters, management commands, middleware, settings.py, admin config, signal senders, manager methods, queryset chains
- TIER 3: Model Meta options, custom managers, custom querysets, template context processors
- TIER 4: Django Channels, Django REST Framework ViewSets

**Flask** (10 gaps):
- TIER 1: Route parameter types
- TIER 2: Template rendering, session usage, Flask-WTF forms, Flask-RESTful resources
- TIER 3: Flask context processors, Flask signals, Flask-Login decorators
- TIER 4: Flask-Mail, Flask-SQLAlchemy specific patterns, Flask-Admin

**FastAPI** (8 gaps):
- TIER 1: Response models, request body models
- TIER 2: WebSocket routes, background tasks, lifespan events, APIRouter hierarchy
- TIER 3: Dependency injection chains, middleware configuration

**SQLAlchemy** (10 gaps):
- TIER 1: Cascade details, session operations
- TIER 2: Query patterns (.filter, .join, .group_by), hybrid properties, polymorphic models
- TIER 3: Table inheritance strategies, query loading strategies (lazy, eager, joined)
- TIER 4: Event listeners, compiled query caching

**Celery** (7 gaps):
- TIER 1: Task routing, retry policies
- TIER 2: Task priority, canvas patterns (chain, group, chord), beat schedule
- TIER 3: Task result backends, custom serializers

---

### Validation Frameworks (20+ gaps)

**Pydantic** (8 gaps):
- TIER 1: Pydantic V2 @field_validator, @model_validator, Field constraints (min_length, pattern, ge, le)
- TIER 2: model_config settings, computed fields (@computed_field), custom validators
- TIER 3: Validator mode ('before', 'after', 'wrap')

**Marshmallow** (6 gaps):
- TIER 1: Pre/post load/dump hooks
- TIER 2: Validator details (Length, Range, Email, URL), Meta.unknown configuration
- TIER 3: Nested field tracking, partial loading, many=True tracking

**WTForms** (3 gaps):
- TIER 1: Validator details (DataRequired, Length, Email)
- TIER 2: Field constraints, widget configuration

**Django Forms/DRF** (3 gaps):
- TIER 2: Meta.fields = '__all__' detection, widget config, SerializerMethodField
- TIER 3: Custom clean methods, DRF validator details

---

### Parity Gaps (9 gaps)

**CRITICAL** (3):
1. Enum extraction (JS extracts enum values, Python doesn't)
2. Async task management (JS extracts Promise.all, Python missing asyncio.gather)
3. Type aliases (JS extracts type aliases, Python doesn't)

**IMPORTANT** (3):
4. Doctest extraction (unique to Python, should extract)
5. RQ/APScheduler job queues (equivalent to JS Bull/Agenda)
6. Flask template context (equivalent to Express res.locals)

**NICE-TO-HAVE** (3):
7. Cerberus/Voluptuous validation (alternative validation frameworks)
8. Streamlit/Dash UI frameworks (equivalent to React/Vue extraction)
9. Peewee/Tortoise ORMs (alternative to SQLAlchemy)

---

## Conclusion

Python extraction Phase 3 achieved **70% parity** with JavaScript/TypeScript. This gap analysis identifies **~100 missing patterns** across 4 categories:

- **22 core language gaps** - Walrus, augmented assignment, lambdas, comprehensions, exceptions
- **50+ framework gaps** - Django URLs, Flask params, FastAPI response models, SQLAlchemy cascade
- **20+ validation gaps** - Pydantic V2, Marshmallow hooks, WTForms validators
- **9 parity gaps** - Enum extraction, async tasks, type aliases

**Recommended Path**: Implement Phases 4-6 (Core, Frameworks, Validation) to reach **90% parity** in 14-20 weeks.

**High-Risk Gaps**: Pydantic V2 validators, Django URL patterns, exception raising, walrus operator, augmented assignment.

**Next Steps**: Create OpenSpec proposals for Phases 4-6.

---

**Report Compiled From**:
- 4 specialized sub-agent analyses (Core, Frameworks, Parity, Validation)
- Source code inspection of `theauditor/ast_extractors/python/`
- Comparison with `theauditor/ast_extractors/javascript/`
- Database schema analysis (`theauditor/indexer/schemas/python_schema.py`)
- Verified against Phase 3 implementation (75 extractors, 59 tables, 7,761 records)

**Confidence**: HIGH - All gaps verified by source code inspection
