# Python Extraction Mapping: Specification Delta

## ADDED Requirements

### Requirement: Walrus Operator Extraction

TheAuditor SHALL extract walrus operator (:=) patterns from Python code to enable data flow analysis through named expressions.

#### Scenario: Walrus in if condition

- **WHEN** code contains `if (n := len(data)) > 10: process(n)`
- **THEN** the system SHALL extract:
  - Target variable: `n`
  - Value expression: `len(data)`
  - Context: `if_condition`
  - File path and line number

#### Scenario: Walrus in while loop

- **WHEN** code contains `while (line := file.readline()): process(line)`
- **THEN** the system SHALL extract walrus assignment with context `while_condition`

#### Scenario: Walrus in comprehension

- **WHEN** code contains `[y for x in range(10) if (y := x*2) > 5]`
- **THEN** the system SHALL extract walrus assignment with context `comprehension`

---

### Requirement: Augmented Assignment Extraction

TheAuditor SHALL extract augmented assignment operators (+=, -=, *=, /=, etc.) to enable data flow tracking.

#### Scenario: Simple augmented assignment

- **WHEN** code contains `count += 1`
- **THEN** the system SHALL extract:
  - Target: `count`
  - Operator: `+=`
  - Value: `1`
  - File path and line number

#### Scenario: All augmented operators

- **WHEN** code uses +=, -=, *=, /=, //=, %=, **=, &=, |=, ^=, >>=, <<=
- **THEN** the system SHALL extract all 12 operator types correctly

---

### Requirement: Lambda Function Extraction

TheAuditor SHALL extract lambda expressions with parameters and body to enable functional pattern analysis.

#### Scenario: Simple lambda

- **WHEN** code contains `sorted(users, key=lambda u: u.name)`
- **THEN** the system SHALL extract:
  - Parameters: `['u']`
  - Body: `u.name`
  - Context: `sorted_key`
  - File path and line number

#### Scenario: Nested lambda

- **WHEN** code contains `lambda x: lambda y: x + y`
- **THEN** the system SHALL extract both outer and inner lambda functions

#### Scenario: Lambda in map/filter

- **WHEN** code contains `map(lambda x: x*2, items)` or `filter(lambda x: x > 0, items)`
- **THEN** the system SHALL extract lambda with context `map` or `filter`

---

### Requirement: Comprehension Extraction

TheAuditor SHALL extract list, dict, set, and generator comprehensions to enable data flow analysis.

#### Scenario: List comprehension

- **WHEN** code contains `[x*2 for x in range(10)]`
- **THEN** the system SHALL extract:
  - Type: `list`
  - Element expression: `x*2`
  - Iterable: `range(10)`
  - Variable: `x`
  - File path and line number

#### Scenario: Dict comprehension

- **WHEN** code contains `{k: v*2 for k, v in items.items()}`
- **THEN** the system SHALL extract dict comprehension with key and value expressions

#### Scenario: Comprehension with condition

- **WHEN** code contains `[x for x in range(10) if x % 2 == 0]`
- **THEN** the system SHALL extract comprehension with filter condition

#### Scenario: Nested comprehension

- **WHEN** code contains `[[y for y in range(x)] for x in range(10)]`
- **THEN** the system SHALL extract both outer and inner comprehensions

---

### Requirement: Exception Raising Extraction

TheAuditor SHALL extract raise statements to enable exception flow analysis.

#### Scenario: Simple raise

- **WHEN** code contains `raise ValueError("Invalid input")`
- **THEN** the system SHALL extract:
  - Exception type: `ValueError`
  - Message: `"Invalid input"`
  - File path and line number

#### Scenario: Raise with from

- **WHEN** code contains `raise RuntimeError("Failed") from original_exc`
- **THEN** the system SHALL extract raise with chained exception reference

#### Scenario: Re-raise

- **WHEN** code contains bare `raise` statement
- **THEN** the system SHALL extract re-raise with no arguments

---

### Requirement: Try/Except Block Extraction

TheAuditor SHALL extract try/except/else/finally blocks to enable exception handling flow analysis.

#### Scenario: Try/except with multiple handlers

- **WHEN** code contains:
  ```python
  try:
      risky_operation()
  except ValueError as e:
      handle_value_error(e)
  except KeyError as e:
      handle_key_error(e)
  finally:
      cleanup()
  ```
- **THEN** the system SHALL extract:
  - Try block location
  - Except handlers with exception types and variables
  - Finally block location
  - File path and line numbers

#### Scenario: Try/except/else

- **WHEN** try block includes else clause
- **THEN** the system SHALL extract else block location

---

### Requirement: Django URL Pattern Extraction

TheAuditor SHALL extract Django URL patterns from urls.py files to enable route discovery.

#### Scenario: path() with parameters

- **WHEN** urls.py contains `path('api/users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail')`
- **THEN** the system SHALL extract:
  - Pattern: `api/users/<int:pk>/`
  - View: `UserDetailView`
  - Name: `user-detail`
  - Parameter type: `int`
  - Parameter name: `pk`
  - File path and line number

#### Scenario: re_path() with regex

- **WHEN** urls.py contains `re_path(r'^users/(?P<pk>[0-9]+)/$', views.UserDetailView)`
- **THEN** the system SHALL extract regex pattern with named group

#### Scenario: include() pattern

- **WHEN** urls.py contains `path('api/', include('api.urls', namespace='api'))`
- **THEN** the system SHALL extract include pattern with namespace

---

### Requirement: Django View Method Extraction

TheAuditor SHALL extract Django CBV methods (get, post, put, delete) to enable HTTP method routing analysis.

#### Scenario: Class-based view methods

- **WHEN** Django view defines `def get(self, request, pk): ...`
- **THEN** the system SHALL extract:
  - View class name
  - Method: `get`
  - Parameters: `self, request, pk`
  - File path and line number

---

### Requirement: FastAPI Response Model Extraction

TheAuditor SHALL extract FastAPI response_model parameters to enable API schema validation.

#### Scenario: Response model in decorator

- **WHEN** route decorator has `@app.get("/users/{user_id}", response_model=UserResponse)`
- **THEN** the system SHALL extract:
  - Route path: `/users/{user_id}`
  - HTTP method: `GET`
  - Response model: `UserResponse`
  - File path and line number

#### Scenario: Request body model

- **WHEN** route function has `user: UserCreate = Body(...)`
- **THEN** the system SHALL extract request body model `UserCreate`

---

### Requirement: SQLAlchemy Cascade Extraction

TheAuditor SHALL extract SQLAlchemy relationship cascade details to enable data integrity analysis.

#### Scenario: Cascade all, delete-orphan

- **WHEN** relationship defines `posts = relationship('Post', cascade='all, delete-orphan')`
- **THEN** the system SHALL extract:
  - Source model: parent model name
  - Target model: `Post`
  - Cascade: `all, delete-orphan`
  - File path and line number

#### Scenario: Multiple cascade types

- **WHEN** cascade uses `cascade='save-update, merge, expunge'`
- **THEN** the system SHALL extract all cascade types

---

### Requirement: SQLAlchemy Session Operation Extraction

TheAuditor SHALL extract session operations (commit, flush, rollback) to enable transaction tracking.

#### Scenario: Session commit

- **WHEN** code contains `session.commit()`
- **THEN** the system SHALL extract:
  - Operation: `commit`
  - Session variable: `session`
  - File path and line number

---

### Requirement: Pydantic V2 Field Validator Extraction

TheAuditor SHALL extract Pydantic V2 @field_validator decorators to enable input validation analysis.

#### Scenario: Single field validator

- **WHEN** model defines `@field_validator('email') def validate_email(cls, v): ...`
- **THEN** the system SHALL extract:
  - Model name
  - Validated fields: `['email']`
  - Validator function: `validate_email`
  - Version: `v2`
  - File path and line number

#### Scenario: Multi-field validator

- **WHEN** validator decorates multiple fields `@field_validator('name', 'email')`
- **THEN** the system SHALL extract all validated field names

#### Scenario: Validator with mode

- **WHEN** validator specifies mode `@field_validator('age', mode='before')`
- **THEN** the system SHALL extract mode: `before`

---

### Requirement: Pydantic V2 Model Validator Extraction

TheAuditor SHALL extract Pydantic V2 @model_validator decorators for model-level validation.

#### Scenario: Model validator

- **WHEN** model defines `@model_validator(mode='after') def validate_model(cls, self): ...`
- **THEN** the system SHALL extract:
  - Model name
  - Validator function: `validate_model`
  - Mode: `after`
  - Version: `v2`
  - File path and line number

---

### Requirement: Pydantic Field Constraint Extraction

TheAuditor SHALL extract Pydantic Field() constraints (min_length, pattern, ge, le) to enable validation rules analysis.

#### Scenario: Field with constraints

- **WHEN** field defines `name: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z]+$')`
- **THEN** the system SHALL extract:
  - Field name: `name`
  - Type: `str`
  - Constraints: `{'min_length': 1, 'max_length': 100, 'pattern': r'^[A-Za-z]+$'}`
  - File path and line number

#### Scenario: Numeric constraints

- **WHEN** field defines `age: int = Field(ge=0, le=150)`
- **THEN** the system SHALL extract ge (greater or equal) and le (less or equal) constraints

---

### Requirement: Marshmallow Hook Extraction

TheAuditor SHALL extract Marshmallow pre_load, post_load, pre_dump, post_dump hooks to enable data transformation tracking.

#### Scenario: Pre-load hook

- **WHEN** schema defines `@pre_load def process_input(self, data, **kwargs): ...`
- **THEN** the system SHALL extract:
  - Schema name
  - Hook type: `pre_load`
  - Hook function: `process_input`
  - File path and line number

#### Scenario: Post-dump hook

- **WHEN** schema defines `@post_dump def remove_nulls(self, data, **kwargs): ...`
- **THEN** the system SHALL extract post_dump hook

---

### Requirement: Marshmallow Validator Extraction

TheAuditor SHALL extract Marshmallow validators (Length, Range, Email, URL) to enable validation rules analysis.

#### Scenario: Field with validators

- **WHEN** field defines `name = fields.String(validate=[Length(min=1, max=100), Regexp(r'^[A-Za-z]+$')])`
- **THEN** the system SHALL extract:
  - Field name: `name`
  - Validators: `[{'type': 'Length', 'min': 1, 'max': 100}, {'type': 'Regexp', 'pattern': r'^[A-Za-z]+$'}]`
  - File path and line number

---

### Requirement: WTForms Validator Extraction

TheAuditor SHALL extract WTForms validators (DataRequired, Length, Email) to enable form validation analysis.

#### Scenario: Form field with validators

- **WHEN** field defines `name = StringField('Name', validators=[DataRequired(), Length(min=1, max=100)])`
- **THEN** the system SHALL extract:
  - Field name: `name`
  - Field type: `StringField`
  - Validators: `[{'type': 'DataRequired'}, {'type': 'Length', 'min': 1, 'max': 100}]`
  - File path and line number

---

### Requirement: Django Form Meta Field Extraction

TheAuditor SHALL extract Django Form Meta.fields configuration to detect auto-generated forms.

#### Scenario: Meta fields = '__all__'

- **WHEN** Django form defines `class Meta: fields = '__all__'`
- **THEN** the system SHALL extract:
  - Form name
  - Meta fields: `'__all__'`
  - Model reference (if ModelForm)
  - File path and line number

---

### Requirement: Async Task Extraction

TheAuditor SHALL extract asyncio.create_task() and asyncio.gather() patterns to enable async orchestration analysis.

#### Scenario: asyncio.create_task

- **WHEN** code contains `task = asyncio.create_task(fetch_data(url))`
- **THEN** the system SHALL extract:
  - Task variable: `task`
  - Coroutine: `fetch_data`
  - Arguments: `url`
  - File path and line number

#### Scenario: asyncio.gather

- **WHEN** code contains `results = await asyncio.gather(task1, task2, task3)`
- **THEN** the system SHALL extract:
  - Result variable: `results`
  - Tasks: `[task1, task2, task3]`
  - File path and line number

---

### Requirement: Type Alias Extraction

TheAuditor SHALL extract type aliases to enable type documentation analysis.

#### Scenario: Simple type alias

- **WHEN** code defines `UserId = int`
- **THEN** the system SHALL extract:
  - Alias name: `UserId`
  - Target type: `int`
  - File path and line number

#### Scenario: Complex type alias

- **WHEN** code defines `JsonDict = Dict[str, Union[str, int, float, bool, None]]`
- **THEN** the system SHALL extract complex type structure

---

### Requirement: Doctest Extraction

TheAuditor SHALL extract doctest examples from docstrings to enable documentation test tracking.

#### Scenario: Doctest in function

- **WHEN** function docstring contains:
  ```python
  \"\"\"
  >>> add(1, 2)
  3
  >>> add(-1, 1)
  0
  \"\"\"
  ```
- **THEN** the system SHALL extract:
  - Function name
  - Doctest examples: `[{'input': 'add(1, 2)', 'output': '3'}, ...]`
  - File path and line number

---

### Requirement: Relative Import Level Extraction

TheAuditor SHALL extract relative import levels (dots) to enable module resolution.

#### Scenario: Parent directory import

- **WHEN** code contains `from ..models import User`
- **THEN** the system SHALL extract:
  - Module: `models`
  - Symbol: `User`
  - Relative level: `2` (two dots)
  - File path and line number

#### Scenario: Current directory import

- **WHEN** code contains `from .utils import helper`
- **THEN** the system SHALL extract relative level: `1`

---

### Requirement: Star Import Detection

TheAuditor SHALL extract star imports (from x import *) to enable namespace pollution detection.

#### Scenario: Star import

- **WHEN** code contains `from django.conf import *`
- **THEN** the system SHALL extract:
  - Module: `django.conf`
  - Type: `star_import`
  - File path and line number

---

### Requirement: Default Parameter Value Extraction

TheAuditor SHALL extract function default parameter values to enable API signature analysis.

#### Scenario: Function with defaults

- **WHEN** function defines `def process(a: int, b: str = 'default', c: List = None):`
- **THEN** the system SHALL extract:
  - Parameter `b` default: `'default'`
  - Parameter `c` default: `None`
  - File path and line number

#### Scenario: Mutable default detection

- **WHEN** function defines `def process(items: List = []):`
- **THEN** the system SHALL flag mutable default (common bug pattern)

---

### Requirement: Enum Member Extraction

TheAuditor SHALL extract Enum member names and values to enable constant tracking.

#### Scenario: String enum

- **WHEN** enum defines:
  ```python
  class Status(str, Enum):
      PENDING = "pending"
      APPROVED = "approved"
      REJECTED = "rejected"
  ```
- **THEN** the system SHALL extract:
  - Enum name: `Status`
  - Members: `[{'name': 'PENDING', 'value': 'pending'}, ...]`
  - Base types: `[str, Enum]`
  - File path and line number

---

### Requirement: Context Manager Extraction

TheAuditor SHALL extract with statements (sync and async) to enable resource management tracking.

#### Scenario: Synchronous context manager

- **WHEN** code contains `with open('file.txt') as f: process(f)`
- **THEN** the system SHALL extract:
  - Context manager: `open('file.txt')`
  - Variable: `f`
  - Type: `sync`
  - File path and line number

#### Scenario: Async context manager

- **WHEN** code contains `async with aiohttp.ClientSession() as session:`
- **THEN** the system SHALL extract async context manager

---

## MODIFIED Requirements

None - All changes are additive. No existing requirements modified.

---

## REMOVED Requirements

None - No requirements removed.

---

## Performance Requirements

### Requirement: Maintain Extraction Performance

All new extractors SHALL maintain extraction performance below 10ms per file.

#### Scenario: Extract large Python file

- **WHEN** processing a Python file with 5,000 lines of code containing 100+ patterns
- **THEN** the system SHALL:
  - Complete extraction in <10ms per file (95th percentile)
  - Use <50MB memory for AST parsing
  - Insert database records in <5ms batch
  - Maintain no memory leaks across multiple files

---

## Integration Requirements

### Requirement: Zero Regression on Existing Extractors

All new extractors SHALL NOT break existing Phase 2/3 extractors.

#### Scenario: Phase 2/3 extractors still work

- **WHEN** Phase 4-7 extractors are added
- **THEN** all Phase 2 (49 extractors) and Phase 3 (26 extractors) SHALL continue producing identical results

---

**END OF SPECIFICATION DELTA**
