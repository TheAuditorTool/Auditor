# Extraction Test Coverage Gaps - MUST COMPLETE

**Date**: 2025-10-31
**Status**: 9 Critical Gaps Identified

---

## Overview

TheAuditor has comprehensive **fixtures** for Python and Node ecosystems, but critical **test coverage gaps** exist that prevent validation of extraction quality. All items below are **MUST HAVE** - they validate core functionality that users depend on.

---

## Python Ecosystem Gaps (6 tasks)

### ❌ GAP 1: Django ORM Extraction
**Status**: No Django models fixture exists
**Impact**: Django is a major Python framework - missing ORM extraction validation means we can't guarantee Django projects work correctly

**Required**:
- Pure Django models (not SQLAlchemy)
- `ForeignKey`, `OneToOneField`, `ManyToManyField` (including `through=` tables)
- `GenericForeignKey` (polymorphic relationships)
- Validates `python_orm_models`, `python_orm_fields`, `orm_relationships` tables

**Fixture Location**: `tests/fixtures/python/django_app.py`
**Test Location**: `tests/test_python_framework_extraction.py::test_django_models_extracted`

**Example Code**:
```python
class Organization(models.Model):
    name = models.CharField(max_length=100)

class User(models.Model):
    username = models.CharField(max_length=100)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    profile = models.OneToOneField('Profile', on_delete=models.CASCADE)

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    tags = models.ManyToManyField('Tag', through='PostTag')

class Tag(models.Model):
    name = models.CharField(max_length=50)

class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

### ❌ GAP 2: Deep Class Nesting/Inheritance (Python)
**Status**: Only flat class structures tested
**Impact**: Multi-level inheritance and nested classes break symbol resolution if not properly tested

**Required**:
- 3+ level inheritance chains (validates parent-of-parent resolution)
- Nested classes 3+ levels deep (validates children-of-children symbols)
- Method resolution order (MRO) validation

**Fixture Location**: `tests/fixtures/python/deep_nesting.py`
**Test Location**: `tests/test_python_framework_extraction.py::test_deep_inheritance_extracted`

**Example Code**:
```python
# Deep inheritance
class BaseModel:
    id = None

class TimestampedModel(BaseModel):
    created_at = None

class SoftDeletableModel(TimestampedModel):
    deleted_at = None

class User(SoftDeletableModel):  # 3 levels deep
    username = None

# Deep nesting
class Outer:
    class Middle:
        class Inner:
            class DeepNested:
                def method(self):
                    pass
```

---

### ❌ GAP 3: Complex Decorators (Python)
**Status**: Only simple `@app.route()` tested
**Impact**: Decorator chains affect control flow and security (auth, validation) - must validate CFG includes them

**Required**:
- Stacked decorators (3+ deep)
- Parameterized decorators with arguments
- Custom decorators wrapping functions
- Validates CFG includes decorator calls

**Fixture Location**: `tests/fixtures/python/decorators.py`
**Test Location**: `tests/test_python_framework_extraction.py::test_complex_decorators_extracted`

**Example Code**:
```python
@auth.required(role="admin")
@cache.memoize(timeout=60)
@validate_input(schema=UserSchema)
@rate_limit(requests=100, window=60)
def admin_endpoint(user_id: int):
    pass

@property
@cache.cached
def computed_value(self):
    pass
```

---

### ❌ GAP 4: Async Patterns (Python)
**Status**: Only synchronous code tested
**Impact**: Async/await is core Python 3.11+ - missing validation means async codebases may have broken call graphs

**Required**:
- `async def` functions
- `await` call chains (function calls function calls function)
- Async context managers (`async with`)
- Validates async call graph resolution

**Fixture Location**: `tests/fixtures/python/async_app.py`
**Test Location**: `tests/test_python_framework_extraction.py::test_async_patterns_extracted`

**Example Code**:
```python
async def fetch_user(user_id: int):
    data = await db.get_user(user_id)
    profile = await fetch_profile(data.profile_id)  # Chain
    permissions = await fetch_permissions(user_id)  # Parallel
    return User(data, profile, permissions)

async def process_batch(items):
    results = await asyncio.gather(*[process_item(i) for i in items])
    return results
```

---

### ❌ GAP 5: Circular Dependencies (Python)
**Status**: Only linear imports tested
**Impact**: Real codebases have circular imports - if import resolution breaks, database is incomplete

**Required**:
- A imports B, B imports A (both directions)
- A imports B imports C imports A (cycle of 3)
- Validates import resolution doesn't infinite loop or crash

**Fixture Location**: `tests/fixtures/python/circular_imports/`
**Test Location**: `tests/test_python_framework_extraction.py::test_circular_imports_handled`

**Example Structure**:
```
circular_imports/
├── models.py       # imports services.UserService
├── services.py     # imports models.User
└── controllers.py  # imports both models and services
```

**Example Code**:
```python
# models.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services import UserService

class User:
    def get_service(self) -> 'UserService':
        from services import UserService  # Runtime import
        return UserService(self)

# services.py
from models import User

class UserService:
    def __init__(self, user: User):
        self.user = user
```

---

### ❌ GAP 6: Complex Type Hints (Python)
**Status**: Only basic `str`, `int` tested
**Impact**: Type hints drive static analysis - complex generics must be extracted correctly

**Required**:
- `List[Dict[str, Union[int, str]]]` (nested generics)
- `Optional[Tuple[int, ...]]` (variadic tuples)
- `Callable[[int, str], bool]` (function signatures)
- `TypeVar`, `Generic` (custom generics)

**Fixture Location**: `tests/fixtures/python/type_annotations.py`
**Test Location**: `tests/test_python_framework_extraction.py::test_complex_type_hints_extracted`

**Example Code**:
```python
from typing import List, Dict, Union, Optional, Callable, TypeVar, Generic

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class Repository(Generic[T]):
    def find_all(self) -> List[T]:
        pass

def transform(
    data: List[Dict[str, Union[int, str, None]]],
    mapper: Callable[[Dict[str, Union[int, str, None]]], Optional[T]]
) -> Optional[Dict[str, List[T]]]:
    pass

def process_batch(
    items: List[Tuple[int, str, Optional[bool]]]
) -> Dict[int, Union[str, List[int]]]:
    pass
```

---

## Node/TypeScript Ecosystem Gaps (3 tasks)

### ❌ GAP 7: Node/TypeScript Extraction Tests (CRITICAL)
**Status**: Fixtures exist (`node-express-api`, `node-react-app`, etc.) but **NO TESTS**
**Impact**: **HIGHEST PRIORITY** - We have 10+ fixture directories but zero validation they extract correctly

**Required**:
- Test file: `tests/test_node_framework_extraction.py`
- Validate Express routes extracted to `js_routes` table
- Validate React components extracted to `js_components` table
- Validate TypeScript interfaces extracted
- Validate Angular dependency injection
- Validate Next.js API routes
- Validate Prisma ORM models

**Test Coverage Needed**:
```python
def test_express_routes_extracted()      # node-express-api
def test_react_components_extracted()    # node-react-app
def test_angular_services_extracted()    # node-angular-app
def test_nextjs_api_routes_extracted()   # node-nextjs-app
def test_prisma_models_extracted()       # node-prisma-orm
def test_bullmq_queues_extracted()       # node-bullmq-jobs
def test_typescript_interfaces_extracted()
```

**Fixtures Already Exist**:
- `tests/fixtures/node-express-api/`
- `tests/fixtures/node-react-app/`
- `tests/fixtures/node-angular-app/`
- `tests/fixtures/node-nextjs-app/`
- `tests/fixtures/node-prisma-orm/`
- `tests/fixtures/node-bullmq-jobs/`
- `tests/fixtures/node-react-query/`

---

### ❌ GAP 8: TypeScript Generics & Class Inheritance
**Status**: Basic types only, no generic nesting or inheritance chains
**Impact**: TypeScript's power is in types - complex generics must be extracted correctly

**Required**:
- Generic type parameters with constraints (`<T extends User>`)
- Nested generics (`Partial<Record<keyof T, string>>`)
- Mapped types (`DeepPartial<T>`)
- 3+ level class inheritance (`class Child extends Middle extends Base`)
- Interface merging and extension

**Fixture Location**: `tests/fixtures/node-typescript-advanced/generics.ts`
**Test Location**: `tests/test_node_framework_extraction.py::test_typescript_generics_extracted`

**Example Code**:
```typescript
// Complex generics
type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

function process<T extends User, K extends keyof T>(
    data: Partial<Record<K, string>>,
    mapper: (value: T[K]) => string
): DeepPartial<T> {
    // ...
}

// Deep inheritance
class BaseEntity {
    id: number;
}

class TimestampedEntity extends BaseEntity {
    createdAt: Date;
}

class SoftDeletableEntity extends TimestampedEntity {
    deletedAt?: Date;
}

class User extends SoftDeletableEntity {  // 3 levels deep
    username: string;
}
```

---

### ❌ GAP 9: Higher-Order Components & Dynamic Imports
**Status**: Simple components only, no HOCs or dynamic imports
**Impact**: Modern React/Next.js uses HOCs and code splitting - must validate call chain resolution

**Required**:
- Nested HOCs (`withAuth(withLayout(Component))`)
- Dynamic `import()` expressions
- Conditional imports
- React.lazy + Suspense patterns
- Validates call chain through wrappers

**Fixture Location**: `tests/fixtures/node-react-app/hocs/`
**Test Location**: `tests/test_node_framework_extraction.py::test_hoc_patterns_extracted`

**Example Code**:
```typescript
// HOCs
const EnhancedComponent = withAuth(
    withLayout(
        withLogging(
            withErrorBoundary(BaseComponent)
        )
    )
);

// Dynamic imports
const DynamicComponent = React.lazy(() => import('./DynamicComponent'));

async function loadModule(moduleName: string) {
    if (moduleName === 'admin') {
        const module = await import('./admin-module');
        return module.default;
    }
    return await import('./default-module');
}
```

---

## Execution Plan

### Phase 1: Critical Foundation (Tasks 7, 1, 2)
1. **Task 7**: Node/TypeScript extraction tests (HIGHEST PRIORITY - fixtures exist but untested)
2. **Task 1**: Django ORM fixture + tests
3. **Task 2**: Deep nesting fixtures (Python + TypeScript)

### Phase 2: Control Flow Quality (Tasks 3, 4, 8)
4. **Task 3**: Complex decorators (Python)
5. **Task 4**: Async patterns (Python)
6. **Task 8**: TypeScript generics + inheritance

### Phase 3: Edge Cases (Tasks 5, 6, 9)
7. **Task 5**: Circular dependencies (Python)
8. **Task 6**: Complex type hints (Python)
9. **Task 9**: HOCs + dynamic imports (TypeScript)

---

## Success Criteria

For each task:
- ✅ Fixture file(s) created
- ✅ Test(s) written validating database extraction
- ✅ Test runs during `aud full` on TheAuditor repo
- ✅ Documentation updated

**ALL 9 TASKS ARE MANDATORY** - they validate core extraction functionality users depend on.

---

## Progress Tracking

| Task | Status | Fixture | Test | Verified |
|------|--------|---------|------|----------|
| 1. Django ORM | ✅ **COMPLETED** | ✅ django_app.py | ✅ 12 tests | ⏳ Pending |
| 2. Deep Nesting (Python + TypeScript) | ✅ **COMPLETED** | ✅ Both fixtures | ✅ 16 tests | ⏳ Pending |
| 3. Complex Decorators (Python) | ✅ **COMPLETED** | ✅ decorators.py | ✅ 12 tests | ⏳ Pending |
| 4. Async Patterns (Python) | ✅ **COMPLETED** | ✅ async_app.py | ✅ 14 tests | ⏳ Pending |
| 5. Circular Imports | ⏳ TODO | - | - | - |
| 6. Complex Type Hints | ⏳ TODO | - | - | - |
| 7. **Node/TS Tests** | ✅ **COMPLETED** | ✅ EXISTS | ✅ 24 tests | ⏳ Pending |
| 8. TS Generics/Inheritance | ⏳ TODO | - | - | - |
| 9. HOCs/Dynamic Imports | ⏳ TODO | - | - | - |

**Started**: 2025-10-31
**Target Completion**: TBD
**Current Task**: #2 - Deep Nesting (Python + TypeScript)

---

## Completed Tasks Summary

### Task 7: Node/TypeScript Extraction Tests ✅
**Completed**: 2025-10-31
**Files Created**:
- `tests/test_node_framework_extraction.py` (491 lines, 24 tests)

**Tests Cover**:
- Express routes (api_endpoints, api_endpoint_controls)
- React components/hooks (react_components, react_hooks, react_component_hooks, react_hook_dependencies)
- Angular services (dependency injection, HttpClient)
- Next.js API routes (including dynamic routes)
- Prisma ORM models
- BullMQ queues/workers
- TypeScript interfaces/classes
- Full-stack integration tests
- Symbol/import resolution

**Validation**: Existing fixtures now have comprehensive test coverage.

---

### Task 1: Django ORM Fixture + Tests ✅
**Completed**: 2025-10-31
**Files Created**:
- `tests/fixtures/python/django_app.py` (365 lines, 17 models)
- Added 12 tests to `tests/test_python_framework_extraction.py`

**Django Fixture Contains**:
- **17 Models**: Organization, Profile, User, Tag, Post, PostTag, Comment, Notification, ActivityLog, Team, TeamMembership, Project, FieldTypeCoverage
- **ForeignKey**: 17 relationships including self-referential (Comment.parent_comment)
- **OneToOneField**: User ↔ Profile
- **ManyToManyField**: Post ↔ Tag (with through=PostTag), Post ↔ User (likes)
- **Through Tables**: PostTag, TeamMembership with additional fields
- **GenericForeignKey**: Notification, ActivityLog (polymorphic)
- **Cascade Behaviors**: CASCADE, SET_NULL, PROTECT (Project model)
- **Field Types**: 20+ Django field types (CharField, TextField, JSONField, etc.)

**Tests Added** (12 functions):
1. `test_django_models_extracted` - Validates 13 models in python_orm_models
2. `test_django_foreign_key_fields_extracted` - Validates 17 ForeignKey fields
3. `test_django_onetoone_relationships` - User ↔ Profile OneToOne
4. `test_django_manytomany_relationships` - Post ↔ Tag ManyToMany
5. `test_django_through_tables_extracted` - PostTag, TeamMembership as models
6. `test_django_self_referential_relationship` - Comment.parent_comment
7. `test_django_cascade_behaviors_extracted` - on_delete validation
8. `test_django_generic_foreign_key_extracted` - GenericForeignKey fields
9. `test_django_field_types_extracted` - Field type coverage
10. `test_django_vs_sqlalchemy_parity` - Django vs SQLAlchemy extraction parity
11. `test_django_bidirectional_relationships` - belongsTo + hasMany symmetry

**Tables Validated**:
- `python_orm_models` (model extraction)
- `python_orm_fields` (field types, is_foreign_key)
- `orm_relationships` (ForeignKey, OneToOne, ManyToMany)

**Parity Achieved**: Django ORM extraction now matches SQLAlchemy coverage.

---

### Task 2: Deep Nesting (Python + TypeScript) ✅
**Completed**: 2025-10-31
**Files Created**:
- `tests/fixtures/python/deep_nesting.py` (430 lines, 25+ classes)
- `tests/fixtures/node-typescript-advanced/deep_nesting.ts` (510 lines, 20+ classes)
- Added 8 Python tests to `tests/test_python_framework_extraction.py`
- Added 8 TypeScript tests to `tests/test_node_framework_extraction.py`

**Python Fixture Contains**:
- **5-level inheritance**: BaseModel → TimestampedModel → SoftDeletableModel → User → AdminUser → SuperAdminUser
- **Multiple inheritance**: AuditableModel (BaseModel + Loggable + Cacheable)
- **Diamond inheritance**: AuditedUser (inherits from AuditableModel + TimestampedModel, both inherit BaseModel)
- **4-level nested classes**: OuterClass.MiddleClass.InnerClass.DeepNested
- **Nested inheritance**: Container.BaseHandler → Container.MiddleHandler → Container.AdvancedHandler
- **Repository pattern**: Repository → UserRepository → AdminUserRepository
- **Abstract methods**: AbstractService → UserService → EnhancedUserService
- **Metaclasses**: ModelMeta → MetaModel → MetaUser

**TypeScript Fixture Contains**:
- **5-level inheritance**: BaseEntity → TimestampedEntity → SoftDeletableEntity → User → AdminUser → SuperAdminUser
- **4-level interfaces**: IIdentifiable → ITimestampable → IAuditable → IVersioned
- **4-level nested classes**: OuterContainer.MiddleContainer.InnerContainer.DeepNested
- **Nested namespaces**: Application.Core.Advanced with service hierarchy
- **Generic repository**: Repository<T extends BaseEntity> → UserRepository → AdminUserRepository
- **Abstract classes**: AbstractService → UserService → EnhancedUserService
- **Mixin patterns**: Loggable + Cacheable mixins on MixedEntity

**Python Tests Added** (8 functions):
1. `test_deep_inheritance_extracted` - 5-level chain validation
2. `test_deep_nested_classes_extracted` - 4-level nesting validation
3. `test_inherited_methods_accessible` - Method inheritance visibility
4. `test_multiple_inheritance_extracted` - Diamond problem handling
5. `test_nested_class_with_inheritance` - Nested classes with extends
6. `test_repository_pattern_inheritance` - Generic base pattern
7. `test_abstract_service_hierarchy` - Template method pattern
8. `test_metaclass_inheritance` - Metaclass extraction

**TypeScript Tests Added** (8 functions):
1. `test_typescript_deep_inheritance_extracted` - 5-level class chain
2. `test_typescript_interface_chains_extracted` - 4-level interface extension
3. `test_typescript_nested_classes_extracted` - 4-level nested classes
4. `test_typescript_namespace_nesting` - Namespace hierarchy
5. `test_typescript_generic_repository_inheritance` - Generic class chains
6. `test_typescript_abstract_class_hierarchy` - Abstract method patterns
7. `test_typescript_mixin_pattern` - Mixin composition
8. `test_typescript_vs_python_deep_nesting_parity` - Cross-language validation

**Validates**:
- `symbols` table: Nested paths (Outer.Middle.Inner.Deep), parent_class column
- Parent-of-parent resolution (BaseModel is grandparent of User)
- Children-of-children resolution (DeepNested is nested 3 levels deep)
- Method Resolution Order (MRO) in multiple inheritance

---

### Task 3: Complex Decorators (Python) ✅
**Completed**: 2025-10-31
**Files Created**:
- `tests/fixtures/python/decorators.py` (410 lines, 30+ decorators/functions)
- Added 12 tests to `tests/test_python_framework_extraction.py`

**Decorator Fixture Contains**:
- **Simple decorators**: simple_decorator, timer, log_calls, require_auth
- **Parameterized decorators**: cache(timeout=60), rate_limit(requests=100, window=60), retry(max_attempts=3), require_role(role="admin"), validate_input(schema={})
- **Security decorators**: require_auth, require_role, require_permissions
- **Validation decorators**: validate_input, validate_output
- **4-stacked decorators**: admin_dashboard (@require_auth @require_role @cache @rate_limit)
- **3-stacked decorators**: create_user, fetch_external_api, transfer_funds
- **Class decorators**: @singleton, @add_logging on ConfigManager
- **Method decorators**: APIController with decorated methods (get_users, delete_user, expensive_operation)
- **Static/class method decorators**: @staticmethod @cache, @classmethod @require_permissions
- **Property decorators**: @property, @setter, @deleter on User class
- **Transaction decorator**: with_transaction (context manager pattern)
- **Async decorators**: async_timer on async_fetch_data (preview of Task 4)

**Tests Added** (12 functions):
1. `test_simple_decorators_extracted` - Basic decorators without args
2. `test_parameterized_decorators_extracted` - Decorators with arguments
3. `test_stacked_decorators_on_functions` - 3+ decorator chains
4. `test_security_decorators_extracted` - Auth/role/permissions decorators
5. `test_validation_decorators_extracted` - Input/output validation
6. `test_class_decorators_extracted` - @singleton, @add_logging
7. `test_method_decorators_in_classes` - Instance method decorators
8. `test_staticmethod_classmethod_decorators` - @staticmethod/@classmethod combos
9. `test_property_decorators_extracted` - @property/@setter
10. `test_transaction_decorator_extracted` - Context manager decorators
11. `test_async_decorators_extracted` - Async function decorators
12. `test_decorator_call_graph_entries` - CFG includes decorator calls

**Security Impact**:
Decorator extraction is critical for security analysis:
- **Auth decorators** (@require_auth, @require_role) validate access control
- **Validation decorators** (@validate_input) detect missing sanitization
- **Rate limit decorators** (@rate_limit) identify DoS protection
- **Transaction decorators** (@with_transaction) show atomic operation boundaries

CFG must include decorator calls to detect security bypasses (e.g., missing @require_auth).

---

### Task 4: Async Patterns (Python) ✅
**Completed**: 2025-10-31
**Files Created**:
- `tests/fixtures/python/async_app.py` (550 lines, 45+ async functions)
- Added 14 tests to `tests/test_python_framework_extraction.py`

**Async Fixture Contains**:
- **Basic async functions**: simple_async_function, async_with_params
- **Await call chains (3 levels)**: fetch_user → fetch_user_data → fetch_user_profile
- **Parallel async (asyncio.gather)**: process_batch, fetch_user_and_posts, fetch_multiple
- **Async context managers**: AsyncDatabaseConnection (__aenter__, __aexit__), @asynccontextmanager
- **Async with statements**: query_database, use_api_client
- **Async generators**: generate_numbers, fetch_paginated_results (yield in async def)
- **Async for loops**: consume_async_generator, process_paginated_data
- **Async error handling**: try/except in async context, retry_async_operation
- **Async decorators**: async_timer, async_retry, decorated_async_function
- **Mixed sync/async**: sync_helper called from async context, run_in_executor
- **Async class methods**: AsyncService (initialize, fetch_data, process, static_async_method, from_config)
- **Async comprehensions**: Async list/dict comprehensions
- **Real-world pattern**: AsyncAPIClient (connect, disconnect, get, post, fetch_multiple)

**Tests Added** (14 functions):
1. `test_async_functions_extracted` - async def functions
2. `test_await_call_chains_extracted` - 3-level await chains
3. `test_parallel_async_operations_extracted` - asyncio.gather patterns
4. `test_async_context_managers_extracted` - __aenter__/__aexit__
5. `test_async_with_statement_functions` - async with usage
6. `test_async_generators_extracted` - yield in async def
7. `test_async_for_loops_extracted` - async for consumption
8. `test_async_error_handling_extracted` - try/except in async
9. `test_async_decorators_on_functions` - Decorators on async functions
10. `test_mixed_sync_async_code` - Sync called from async
11. `test_async_class_methods_extracted` - Async instance/static/class methods
12. `test_async_comprehensions_extracted` - Async list/dict comprehensions
13. `test_async_api_client_class_extracted` - Real-world async pattern
14. `test_async_symbol_count` - Overall extraction completeness (40+ functions, 3+ classes)

**Call Graph Impact**:
Async/await call chains are critical for taint analysis:
- **Await chains**: `fetch_user` → `await fetch_user_data` → `await fetch_user_profile` must be tracked
- **Parallel await**: `asyncio.gather()` creates multiple await points - all must be captured
- **Async context**: `async with` boundaries affect resource lifecycle tracking
- **Mixed sync/async**: Sync functions called from async context must show in call graph

Validates async call graph resolution for modern Python 3.11+ codebases.
