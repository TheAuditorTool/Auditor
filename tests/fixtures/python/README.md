# Python Fixtures Collection

Focused test fixtures for Python framework extraction, each targeting specific patterns.

## Fixture Files

### flask_app.py (60 lines)
**Purpose**: Flask blueprint, routes, and auth decorator extraction

**Patterns**:
- Flask Blueprint with URL prefix (`/api`)
- 6 routes (GET, POST, PUT, DELETE)
- 2 custom decorators (`@login_required`, `@audit_event`)
- Decorator stacking (`@login_required @audit_event`)
- Path parameters (`<int:user_id>`)
- Missing auth on one endpoint (security risk)

**Populated Tables**:
- `python_routes` (6 routes)
- `python_blueprints` (1 blueprint: "api")
- `api_endpoint_controls` (6+ decorator applications)

**Sample Query**:
```sql
SELECT pr.pattern, aec.control_name
FROM python_routes pr
LEFT JOIN api_endpoint_controls aec
  ON pr.file = aec.endpoint_file AND pr.line = aec.endpoint_line
WHERE pr.file LIKE '%flask_app.py'
ORDER BY pr.pattern;
```

**Expected**: `/ping` has no controls (public), all others have `@login_required`

---

### fastapi_app.py (65 lines)
**Purpose**: FastAPI route extraction with dependency injection

**Patterns**:
- APIRouter with prefix (`/v1`) and tags
- 5 routes with varying HTTP methods
- Dependency injection (`Depends(get_db)`, `Depends(get_current_user)`)
- Response models (`List[UserResponse]`, `UserResponse`)
- Status codes (`status_code=201`, `status_code=204`)
- Pydantic models (`UserResponse`, `UserCreate`)

**Populated Tables**:
- `python_routes` (5 routes with `has_deps=1`)
- `function_calls` (Depends() calls)

**Sample Query**:
```sql
SELECT method, pattern, handler_function
FROM python_routes
WHERE file LIKE '%fastapi_app.py'
  AND has_deps = 1
ORDER BY pattern;
```

**Expected**: All 5 routes have dependency injection

---

### pydantic_app.py (63 lines)
**Purpose**: Pydantic validator extraction (field + root)

**Patterns**:
- 4 Pydantic models (`Address`, `UserSettings`, `UserPayload`, `BulkInvite`)
- Field validators (`@validator`)
- Root validators (`@root_validator`)
- Nested models (`UserPayload` contains `UserSettings` and `Address`)
- Field constraints (`Field(min_length=3)`)

**Populated Tables**:
- `python_validators` (4+ validators)

**Sample Query**:
```sql
SELECT validator_name, validator_type, field_name
FROM python_validators
WHERE file LIKE '%pydantic_app.py'
ORDER BY validator_type, validator_name;
```

**Expected**:
- Field validators: `postal_code_length`, `timezone_not_empty`, `email_must_have_at`, `emails_not_empty`
- Root validators: `passwords_match`

---

### parity_sample.py (103 lines)
**Purpose**: Multi-framework parity - all patterns in one file

**Patterns**:
- **SQLAlchemy ORM**: 4 models (User, Post, Comment, Profile)
- **ORM Relationships**: Bidirectional with cascade flags
- **Pydantic**: Account model with field + root validators
- **FastAPI**: Router with routes and dependencies
- **Flask**: Blueprint with routes

**Populated Tables**:
- `python_orm_models` (4 models)
- `orm_relationships` (6+ relationships)
- `python_routes` (FastAPI + Flask routes)
- `python_validators` (2 validators)

**Sample Query**:
```sql
-- Verify all frameworks extracted from single file
SELECT 'ORM Models' AS category, COUNT(*) AS count
FROM python_orm_models WHERE file LIKE '%parity_sample.py'
UNION ALL
SELECT 'Routes', COUNT(*)
FROM python_routes WHERE file LIKE '%parity_sample.py'
UNION ALL
SELECT 'Validators', COUNT(*)
FROM python_validators WHERE file LIKE '%parity_sample.py';
```

**Expected**: Non-zero counts for all frameworks

---

### sqlalchemy_app.py (~100 lines)
**Purpose**: SQLAlchemy ORM models and relationships

**Patterns**:
- Declarative Base
- Foreign keys with ondelete behaviors
- Bidirectional relationships
- `back_populates` vs `backref`
- Cascade delete flags

**Populated Tables**:
- `python_orm_models` (3+ models)
- `python_orm_fields` (15+ fields with PK/FK flags)
- `orm_relationships` (4+ relationships)

**Sample Query**:
```sql
SELECT source_model, target_model, cascade_delete
FROM orm_relationships
WHERE file LIKE '%sqlalchemy_app.py'
ORDER BY source_model;
```

---

### cross_file_taint/ Directory
**Purpose**: Cross-file taint flow tracking

**Files**:
- `controller.py` - HTTP request handlers (taint source)
- `service.py` - Business logic layer
- `database.py` - Raw SQL queries (taint sink)

**Taint Flow**:
```
controller.py: get_user(user_id)  [HTTP param - TAINT SOURCE]
  → service.py: fetch_user(user_id)
    → database.py: execute("SELECT ... WHERE id = ?", (user_id,))  [SQL - SINK]
```

**Populated Tables**:
- `symbols` (functions across files)
- `function_calls` (cross-file calls)
- `refs` (cross-file references)

**Sample Query**:
```sql
-- Find cross-file call chains
SELECT fc.function_name, fc.callee_function, fc.file
FROM function_calls fc
WHERE fc.file LIKE '%cross_file_taint%'
ORDER BY fc.file, fc.line;
```

---

### import_resolution/ Directory
**Purpose**: Import chain resolution across packages

**Structure**:
```
import_resolution/
├── __init__.py
├── app.py (imports from api/, services/, util/)
├── api/
│   └── endpoints.py
├── services/
│   └── user_service.py
└── util/
    └── helpers.py
```

**Patterns**:
- Package imports (`from api import endpoints`)
- Relative imports (`from ..services import user_service`)
- Module-level imports
- Cross-package dependencies

**Populated Tables**:
- `imports` (import statements with module paths)
- `refs` (resolved import targets)

**Sample Query**:
```sql
SELECT module_path, imported_names, file
FROM imports
WHERE file LIKE '%import_resolution%'
ORDER BY file, line;
```

---

### type_test.py (~30 lines)
**Purpose**: Python type annotation extraction

**Patterns**:
- Type hints (`def foo(x: int) -> str`)
- Generic types (`List[str]`, `Dict[str, int]`)
- Optional types (`Optional[User]`)
- Union types (`Union[str, int]`)

**Populated Tables**:
- `symbols` (with type annotation metadata)
- `type_annotations` (if exists)

---

## How to Use These Fixtures

1. **Index from TheAuditor root**:
   ```bash
   cd C:/Users/santa/Desktop/TheAuditor
   aud index
   ```

2. **Run spec.yaml verification**:
   ```bash
   # From python/ fixture directory
   cd tests/fixtures/python
   # Run verification queries from spec.yaml
   ```

3. **Query specific patterns**:
   ```bash
   aud context query --symbol list_users  # Flask route
   aud context query --symbol UserPayload  # Pydantic model
   ```

## Coverage Summary

| Fixture | Lines | Flask | FastAPI | Pydantic | SQLAlchemy | Taint | Imports |
|---|---|---|---|---|---|---|---|
| flask_app.py | 60 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| fastapi_app.py | 65 | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| pydantic_app.py | 63 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| parity_sample.py | 103 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| sqlalchemy_app.py | ~100 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| cross_file_taint/ | ~200 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| import_resolution/ | ~150 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**Total Coverage**: All major Python framework patterns

## Relation to realworld_project

The `realworld_project/` directory is a **comprehensive integration** of all these patterns in a single realistic codebase (2293 lines across 38 files). Individual fixtures here test **isolated patterns** for focused unit testing.

Use individual fixtures when:
- Testing specific extractor functions
- Debugging extraction failures
- Writing unit tests for indexer changes
- Verifying single-framework support

Use `realworld_project/` when:
- Testing end-to-end extraction
- Verifying framework interactions
- Testing junction table queries
- Simulating real-world codebases
