# Real World Project Fixture

## Purpose
The **most comprehensive Python test fixture** in TheAuditor, simulating a production-grade multi-framework application with 2293 lines of code across 38 files.

Tests advanced Python framework extraction capabilities across:
- **SQLAlchemy ORM** (models, relationships, cascade deletes)
- **FastAPI** (routes, dependency injection, Pydantic validators)
- **Celery** (background tasks, security configurations, serializers)
- **Django** (forms, admin, middleware, DRF serializers)
- **WTForms** (form validation)
- **Async patterns** (generators, async functions, context managers)

This fixture validates that TheAuditor can extract **deep framework semantics** from real-world Python codebases.

## Project Structure

```
realworld_project/
├── spec.yaml                      # Comprehensive verification rules
├── README.md                      # This file
│
├── models/                        # SQLAlchemy ORM
│   ├── base.py                    # Declarative base
│   ├── accounts.py                # Organization, User, Profile models
│   └── audit.py                   # AuditLog model
│
├── api/                           # FastAPI routes
│   ├── users_fastapi.py           # FastAPI router with dependency injection
│   ├── admin_flask.py             # Flask Blueprint for admin
│   └── deps.py                    # FastAPI dependencies
│
├── services/                      # Business logic
│   ├── accounts.py                # Account service layer
│   ├── emails.py                  # Email service
│   ├── async_tasks.py             # Async task orchestration
│   └── task_orchestration.py     # Celery task coordination
│
├── tasks/                         # Celery background tasks
│   └── celery_tasks.py            # 17 task definitions with varying security configs
│
├── validators/                    # Pydantic validators
│   └── accounts.py                # AccountPayload with @validator and @root_validator
│
├── schemas/                       # Serializers
│   ├── user_schemas.py            # Marshmallow schemas
│   └── drf_serializers.py         # Django REST Framework serializers
│
├── forms/                         # Form frameworks
│   ├── article_forms.py           # Django forms
│   └── wtforms_auth_forms.py      # WTForms for authentication
│
├── middleware/                    # Django middleware
│   └── auth_middleware.py         # 6 middleware classes
│
├── views/                         # Django views
│   └── article_views.py           # Class-based and function-based views
│
├── utils/                         # Utility modules
│   └── generators.py              # 27+ generator patterns
│
├── repositories/                  # Data access layer
│   └── accounts.py                # Repository pattern
│
├── admin.py                       # Django admin configuration
├── celeryconfig.py                # Celery configuration
└── tests/
    └── test_accounts.py           # Pytest fixtures and tests
```

## Framework Coverage Statistics

### Extracted Data (After `aud index`)

| Table | Count | Description |
|---|---|---|
| **python_orm_models** | 4 | Organization, User, Profile, AuditLog |
| **python_orm_fields** | 20 | All model fields with PK/FK flags |
| **orm_relationships** | 8 | Bidirectional relationships with cascade |
| **python_routes** | 4 | FastAPI routes with dependency injection |
| **python_celery_tasks** | 17 | Celery tasks with security configs |
| **python_validators** | 2 | Pydantic field + root validators |
| **python_django_forms** | 17 | Django form definitions |
| **python_wtforms_forms** | 10 | WTForms for auth |
| **python_drf_serializers** | 11 | DRF serializer classes |
| **python_django_middleware** | 6 | Django middleware classes |
| **python_generators** | 27 | Generator functions and expressions |

**Total**: 126+ framework-specific entities extracted

## Advanced Patterns Demonstrated

### 1. SQLAlchemy ORM Relationships (models/accounts.py)

**4 Models with Complex Relationships**:

```python
Organization
  └─[1:N cascade]→ User
      ├─[1:1 cascade]→ Profile
      └─[1:N cascade]→ AuditLog
```

**Security Risk**: Deleting an Organization cascades to all Users, Profiles, and AuditLogs (data loss)

**Junction Table Verification**:
```sql
SELECT source_model, target_model, cascade_delete
FROM orm_relationships
WHERE file LIKE '%realworld_project%'
```

Expected: 8 relationships (4 bidirectional pairs)

### 2. FastAPI Dependency Injection (api/users_fastapi.py)

**Patterns Tested**:
- Path parameters: `@router.get("/users/{account_id}")`
- Depends() injections: `repository=Depends(get_repository)`
- Response models: `response_model=list[AccountResponse]`
- Status codes: `status_code=201`

**Taint Flow**:
```
/users/{account_id} → get_user(account_id) → service.fetch_account(account_id) → repository.get_by_id(account_id) → SQL
```

### 3. Celery Security Configurations (tasks/celery_tasks.py)

**17 Tasks Demonstrating**:

| Task | Serializer | Rate Limit | Time Limit | Security Status |
|---|---|---|---|---|
| `dangerous_task` | **pickle** | ❌ | ❌ | **CRITICAL RCE** |
| `send_email` | None (pickle) | ❌ | ❌ | **HIGH DoS risk** |
| `process_payment` | **json** | ❌ | ❌ | **Safe serializer, no limits** |
| `comprehensive_task` | **json** | 100/m | 60s | **BEST PRACTICE** |
| `long_running_export` | **json** | 50/h | 120s | **BEST PRACTICE** |
| `send_sms` | None | **10/m** | ❌ | **Rate limited** |
| `generate_report` | None | ❌ | **30s** | **Time limited** |

**Critical Finding**:
```sql
SELECT task_name, serializer
FROM python_celery_tasks
WHERE serializer = 'pickle'
```

Result: `dangerous_task` - **Remote Code Execution vulnerability**

### 4. Pydantic Validators (validators/accounts.py)

**2 Validator Types**:

```python
@validator("timezone")  # Field validator
def timezone_supported(cls, value: str) -> str:
    if value not in {"UTC", "US/Pacific", "US/Eastern"}:
        raise ValueError("unsupported timezone")
    return value

@root_validator  # Root validator (cross-field)
def title_matches_role(cls, values: dict) -> dict:
    title = values.get("title")
    if title and len(title) < 3:
        raise ValueError("title too short")
    return values
```

**Extraction Test**:
```sql
SELECT validator_name, validator_type, field_name
FROM python_validators
WHERE file LIKE '%realworld_project%'
```

Expected: `timezone_supported` (field), `title_matches_role` (root)

### 5. Django Forms (forms/article_forms.py)

**17 Form Definitions** including:
- ModelForms with Meta classes
- Form field validators
- Custom clean_* methods
- Required/optional fields

**WTForms** (forms/wtforms_auth_forms.py):
- 10 WTForms classes
- Field-level validators
- Custom validation logic

### 6. Django REST Framework Serializers (schemas/drf_serializers.py)

**11 Serializers** with:
- ModelSerializer inheritance
- Nested serializers
- read_only_fields
- Custom validation methods

### 7. Django Middleware (middleware/auth_middleware.py)

**6 Middleware Classes**:
- `AuthenticationMiddleware`
- `RateLimitMiddleware`
- `AuditLoggingMiddleware`
- `CORSMiddleware`
- `SecurityHeadersMiddleware`
- `RequestIDMiddleware`

### 8. Python Generators (utils/generators.py)

**27 Generator Patterns**:
- Generator functions (`yield`)
- Generator expressions
- Async generators (`async def` + `yield`)
- Generator delegation (`yield from`)

## Sample Verification Queries

### Query 1: Find All Cascade Delete Risks

```sql
SELECT
    r.source_model,
    r.target_model,
    r.cascade_delete,
    pom.table_name
FROM orm_relationships r
JOIN python_orm_models pom
    ON r.source_model = pom.model_name
WHERE r.cascade_delete = 1
  AND r.file LIKE '%realworld_project%'
ORDER BY r.source_model;
```

**Expected Results**:
- Organization → User (cascade=1)
- User → Profile (cascade=1)
- User → AuditLog (cascade=1)

**Security Implication**: Deleting 1 Organization can delete hundreds of Users and thousands of dependent records.

### Query 2: Find Celery Tasks Without Security Limits

```sql
SELECT
    task_name,
    serializer,
    rate_limit,
    time_limit
FROM python_celery_tasks
WHERE (rate_limit IS NULL OR rate_limit = '')
  AND (time_limit IS NULL OR time_limit = 0)
  AND file LIKE '%realworld_project%'
ORDER BY task_name;
```

**Expected Results**: ~10 tasks with no rate/time limits (DoS risk)

### Query 3: Find API Routes and Their Dependency Chains

```sql
SELECT
    pr.method,
    pr.pattern,
    pr.handler_function,
    pr.has_deps
FROM python_routes pr
WHERE pr.file LIKE '%realworld_project%'
ORDER BY pr.pattern;
```

**Expected Results**: 4 FastAPI routes, all with `has_deps=1` (dependency injection)

### Query 4: Find All Validators (Pydantic + Django + WTForms)

```sql
-- Pydantic validators
SELECT 'pydantic' AS framework, validator_name, validator_type
FROM python_validators
WHERE file LIKE '%realworld_project%'

UNION ALL

-- Django form validators (from clean_* methods)
SELECT 'django', form_name, 'clean_method'
FROM python_django_forms
WHERE file LIKE '%realworld_project%'

UNION ALL

-- WTForms validators
SELECT 'wtforms', form_name, 'wtforms'
FROM python_wtforms_forms
WHERE file LIKE '%realworld_project%'

ORDER BY framework;
```

**Expected Results**: Mix of all 3 validation frameworks

### Query 5: Track Taint Flow from FastAPI Route to SQL

```sql
-- Find route handlers
SELECT DISTINCT fc.callee_function
FROM function_calls fc
JOIN python_routes pr
    ON fc.file = pr.file AND fc.line >= pr.line
WHERE pr.file LIKE '%realworld_project%/api/users_fastapi.py'
ORDER BY fc.callee_function;
```

**Taint Chain**:
1. `/users/{account_id}` (route parameter - TAINT SOURCE)
2. `get_user(account_id)` (handler)
3. `service.fetch_account(account_id)` (service layer)
4. `repository.get_by_id(account_id)` (data layer)
5. SQL query with account_id (SINK)

## Security Vulnerabilities Demonstrated

### CRITICAL

1. **Celery Pickle Serializer RCE**
   - File: `tasks/celery_tasks.py:93`
   - Task: `dangerous_task`
   - Vulnerability: `serializer='pickle'` allows remote code execution
   - Fix: Use `serializer='json'`

### HIGH

2. **Cascade Delete Data Loss**
   - File: `models/accounts.py:22-26`
   - Risk: Deleting Organization cascades to all Users/Profiles/AuditLogs
   - Fix: Add soft delete or require explicit confirmation

3. **No Rate Limiting on Tasks**
   - File: `tasks/celery_tasks.py:14-16`
   - Tasks: `send_email`, `complex_data_processing`, etc.
   - Risk: Can be abused for DoS attacks
   - Fix: Add `rate_limit='N/m'`

### MEDIUM

4. **No Time Limits on Long-Running Tasks**
   - File: `tasks/celery_tasks.py:37-40`
   - Task: `fetch_external_api`
   - Risk: Infinite execution consuming resources
   - Fix: Add `time_limit=N`

## Testing Use Cases

This fixture enables testing:

1. **Multi-Framework Extraction**: Verify indexer handles SQLAlchemy, FastAPI, Celery, Django, WTForms simultaneously
2. **Junction Table Queries**: Test complex SQL JOINs across orm_relationships, python_routes, python_celery_tasks
3. **Security Pattern Detection**: Find pickle serializers, cascade deletes, missing rate limits
4. **Taint Flow Analysis**: Track request parameters → service layer → SQL queries
5. **Cross-File Dependency Tracking**: Validate import resolution across 38 files
6. **Async Pattern Extraction**: Test generator, async function, context manager extraction

## How to Use This Fixture

1. **Index the project** (from TheAuditor root):
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Verify all patterns extracted**:
   ```bash
   # Run spec.yaml verification rules
   # (spec.yaml has 13 verification queries + 3 security patterns)
   ```

3. **Query specific patterns**:
   ```bash
   # Find dangerous Celery tasks
   aud context query --symbol dangerous_task

   # Find ORM models
   aud context query --symbol User --show-relationships

   # Find API routes
   # Query python_routes table
   ```

4. **Test security rules**:
   ```sql
   -- Find all CRITICAL findings
   SELECT * FROM python_celery_tasks
   WHERE serializer = 'pickle'

   -- Find all MEDIUM findings
   SELECT * FROM orm_relationships
   WHERE cascade_delete = 1
   ```

## Expected Schema Population

When this fixture is indexed, expect:

- ✅ **4 ORM models** (Organization, User, Profile, AuditLog)
- ✅ **8 bidirectional relationships** with cascade flags
- ✅ **4 FastAPI routes** with dependency injection metadata
- ✅ **17 Celery tasks** with serializer, rate_limit, time_limit extraction
- ✅ **1 CRITICAL security finding** (pickle serializer)
- ✅ **3 CASCADE DELETE risks** (data loss potential)
- ✅ **2 Pydantic validators** (field + root)
- ✅ **17 Django forms + 10 WTForms**
- ✅ **11 DRF serializers**
- ✅ **6 Django middleware**
- ✅ **27+ generators** (sync + async)

## File Breakdown

| Directory | Files | Lines | Primary Purpose |
|---|---|---|---|
| models/ | 3 | 150 | SQLAlchemy ORM definitions |
| api/ | 3 | 200 | FastAPI + Flask routes |
| services/ | 4 | 400 | Business logic layer |
| tasks/ | 2 | 350 | Celery background tasks |
| validators/ | 1 | 40 | Pydantic validators |
| schemas/ | 2 | 250 | Marshmallow + DRF serializers |
| forms/ | 2 | 300 | Django + WTForms |
| middleware/ | 1 | 150 | Django middleware |
| views/ | 1 | 100 | Django views |
| utils/ | 1 | 200 | Generator patterns |
| repositories/ | 1 | 100 | Data access layer |
| **Total** | **38** | **2293** | **Full-stack Python app** |

## Why This Fixture Matters

Real-world Python projects use **multiple frameworks simultaneously**:
- FastAPI for REST APIs
- Celery for background jobs
- SQLAlchemy for database ORM
- Pydantic for request validation
- Django forms/admin for internal tools

This fixture proves TheAuditor can handle **polyglot Python codebases** and extract security-relevant patterns from all major frameworks. If extraction works here, it works on production code.

## Coverage Checklist

- ✅ SQLAlchemy ORM (models, fields, relationships, cascade)
- ✅ FastAPI (routes, dependencies, response models)
- ✅ Celery (tasks, decorators, security configs, serializers)
- ✅ Pydantic (field validators, root validators)
- ✅ Django (forms, admin, middleware, views)
- ✅ Django REST Framework (serializers, ModelSerializer)
- ✅ WTForms (forms, field validators)
- ✅ Marshmallow (schemas)
- ✅ Generators (sync, async, expressions)
- ✅ Async patterns (async def, await, async generators)
- ✅ Context managers
- ✅ Pytest fixtures
- ✅ Repository pattern
- ✅ Service layer pattern
- ✅ Dependency injection

**This is the gold standard fixture for Python framework extraction testing.**
