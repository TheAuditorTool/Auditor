# python-extraction-architecture Specification Delta

## ADDED Requirements

### Requirement: Modular Python Extraction Architecture

The system SHALL organize Python extraction code into modular structure under `theauditor/ast_extractors/python/` directory.

The system SHALL provide six specialized extraction modules: `core_extractors.py`, `framework_extractors.py`, `async_extractors.py`, `testing_extractors.py`, `type_extractors.py`, `cfg_extractor.py`.

The system SHALL maintain backward compatibility by re-exporting all extraction functions from `theauditor/ast_extractors/python/__init__.py`.

The system SHALL NOT break existing imports from `python_impl.py` during migration period.

#### Scenario: Modular architecture created
- **GIVEN** Python extraction codebase exists in single `python_impl.py` file
- **WHEN** Phase 2 modular refactor is applied
- **THEN** `/python/` directory exists with 6 module files
- **AND** `__init__.py` re-exports all functions for backward compatibility
- **AND** existing code using `from python_impl import extract_*` continues working

#### Scenario: Core extractors module separation
- **GIVEN** core extraction functions (imports, functions, classes, assignments)
- **WHEN** refactored into `core_extractors.py`
- **THEN** all core functions exist in `core_extractors.py`
- **AND** all core functions maintain exact same signatures
- **AND** `aud index` produces identical database counts

#### Scenario: Framework extractors module separation
- **GIVEN** framework extraction functions (SQLAlchemy, Django, Flask, FastAPI, Pydantic)
- **WHEN** refactored into `framework_extractors.py`
- **THEN** all framework functions exist in `framework_extractors.py`
- **AND** framework detection constants (SQLALCHEMY_BASE_IDENTIFIERS, etc.) moved to module
- **AND** `aud full --offline` produces identical ORM/route counts

---

### Requirement: Python Decorator Extraction

The system SHALL extract all decorator patterns from Python code including built-in decorators (@property, @staticmethod, @classmethod, @abstractmethod) and custom decorators.

The system SHALL store decorator name, decorator type, target name, target type (function/class), file, and line number.

The system SHALL create `python_decorators` table with columns: file, line, decorator_name, decorator_type, target_name, target_type.

The system SHALL extract decorators from TheAuditor's own codebase (72+ instances verified).

#### Scenario: Property decorator extraction
- **GIVEN** Python class with @property decorated method
  ```python
  class Foo:
      @property
      def bar(self):
          return self._bar
  ```
- **WHEN** file is indexed
- **THEN** `python_decorators` table contains row with decorator_name='property', decorator_type='property', target_name='bar', target_type='function'

#### Scenario: Staticmethod decorator extraction
- **GIVEN** Python class with @staticmethod decorated method
- **WHEN** file is indexed
- **THEN** `python_decorators` table contains row with decorator_type='staticmethod'

#### Scenario: Custom decorator extraction
- **GIVEN** Python function with custom decorator `@my_decorator`
- **WHEN** file is indexed
- **THEN** `python_decorators` table contains row with decorator_name='my_decorator', decorator_type='custom'

---

### Requirement: Python Context Manager Extraction

The system SHALL extract context manager classes by detecting `__enter__` and `__exit__` methods.

The system SHALL extract `with` statement usage and identify context manager expressions.

The system SHALL detect async context managers (`async with`, `__aenter__`, `__aexit__`).

The system SHALL create `python_context_managers` table with columns: file, line, class_name, has_enter, has_exit, is_async.

#### Scenario: Basic context manager extraction
- **GIVEN** Python class with `__enter__` and `__exit__` methods
  ```python
  class MyContext:
      def __enter__(self):
          return self
      def __exit__(self, *args):
          pass
  ```
- **WHEN** file is indexed
- **THEN** `python_context_managers` table contains row with class_name='MyContext', has_enter=True, has_exit=True, is_async=False

#### Scenario: Async context manager extraction
- **GIVEN** Python class with `__aenter__` and `__aexit__` methods
- **WHEN** file is indexed
- **THEN** `python_context_managers` table contains row with is_async=True

---

### Requirement: Python Async Pattern Extraction

The system SHALL extract async function definitions (`async def`) with function name, has_await flag, file, and line number.

The system SHALL extract `await` expressions within async functions.

The system SHALL extract async context managers (`async with` statements).

The system SHALL extract async generators (`async for` loops).

The system SHALL create `python_async_functions` table with columns: file, line, function_name, has_await, has_async_with, has_async_for.

#### Scenario: Async function extraction
- **GIVEN** Python file with async function
  ```python
  async def fetch_data():
      data = await api_call()
      return data
  ```
- **WHEN** file is indexed
- **THEN** `python_async_functions` table contains row with function_name='fetch_data', has_await=True

#### Scenario: Async context manager usage
- **GIVEN** async function using `async with`
  ```python
  async def process():
      async with aiohttp.ClientSession() as session:
          pass
  ```
- **WHEN** file is indexed
- **THEN** `python_async_functions` table contains row with has_async_with=True

---

### Requirement: pytest Fixture Extraction

The system SHALL extract pytest fixtures by detecting `@pytest.fixture` decorators.

The system SHALL extract fixture name, scope (function/class/module/session), parameters, and dependencies.

The system SHALL extract pytest parametrize decorators (`@pytest.mark.parametrize`).

The system SHALL extract custom pytest markers.

The system SHALL create `python_pytest_fixtures` table with columns: file, line, fixture_name, scope, params, dependencies.

#### Scenario: Basic pytest fixture extraction
- **GIVEN** Python test file with pytest fixture
  ```python
  @pytest.fixture
  def user():
      return User(name='test')
  ```
- **WHEN** file is indexed
- **THEN** `python_pytest_fixtures` table contains row with fixture_name='user', scope='function'

#### Scenario: Session-scoped fixture extraction
- **GIVEN** pytest fixture with session scope
  ```python
  @pytest.fixture(scope='session')
  def db():
      return Database()
  ```
- **WHEN** file is indexed
- **THEN** `python_pytest_fixtures` table contains row with scope='session'

---

### Requirement: Django Class-Based View Extraction

The system SHALL extract Django class-based views (CreateView, UpdateView, ListView, DetailView, FormView).

The system SHALL extract view class name, view type, associated model, template name, file, and line number.

The system SHALL create `python_django_views` table with columns: file, line, view_class, view_type, model, template.

#### Scenario: CreateView extraction
- **GIVEN** Django view inheriting from CreateView
  ```python
  class UserCreateView(CreateView):
      model = User
      template_name = 'user_form.html'
  ```
- **WHEN** file is indexed
- **THEN** `python_django_views` table contains row with view_class='UserCreateView', view_type='CreateView', model='User'

---

### Requirement: Django Form Extraction

The system SHALL extract Django form classes (ModelForm, Form, FormSets).

The system SHALL extract form class name, associated model, fields, widgets, file, and line number.

The system SHALL create `python_django_forms` table with columns: file, line, form_class, model, fields, widgets.

#### Scenario: ModelForm extraction
- **GIVEN** Django ModelForm
  ```python
  class UserForm(ModelForm):
      class Meta:
          model = User
          fields = ['name', 'email']
  ```
- **WHEN** file is indexed
- **THEN** `python_django_forms` table contains row with form_class='UserForm', model='User', fields='["name", "email"]'

---

### Requirement: Celery Task Extraction

The system SHALL extract Celery task definitions by detecting `@task` and `@shared_task` decorators.

The system SHALL extract task name, queue, retry settings, rate limits, file, and line number.

The system SHALL detect Celery task chains, groups, and chords.

The system SHALL create `python_celery_tasks` table with columns: file, line, task_name, queue, retry_count, chain_structure.

#### Scenario: Basic Celery task extraction
- **GIVEN** Python file with Celery task
  ```python
  @task(queue='default', max_retries=3)
  def process_order(order_id):
      pass
  ```
- **WHEN** file is indexed
- **THEN** `python_celery_tasks` table contains row with task_name='process_order', queue='default', retry_count=3

---

### Requirement: Advanced Type System Extraction

The system SHALL extract Protocol definitions from typing module.

The system SHALL extract Generic class definitions with type parameters.

The system SHALL extract TypedDict definitions with required/optional fields.

The system SHALL extract Literal type usage.

The system SHALL extract @overload decorator usage for function overloading.

The system SHALL create `python_protocols`, `python_generics`, `python_type_aliases` tables.

#### Scenario: Protocol extraction
- **GIVEN** Python file with Protocol definition
  ```python
  from typing import Protocol
  class Drawable(Protocol):
      def draw(self) -> None: ...
  ```
- **WHEN** file is indexed
- **THEN** `python_protocols` table contains row with protocol_name='Drawable', methods='["draw"]'

#### Scenario: Generic class extraction
- **GIVEN** Python file with Generic class
  ```python
  from typing import Generic, TypeVar
  T = TypeVar('T')
  class Container(Generic[T]):
      pass
  ```
- **WHEN** file is indexed
- **THEN** `python_generics` table contains row with class_name='Container', type_params='["T"]'

---

### Requirement: Generator Extraction

The system SHALL extract generator functions by detecting `yield` statements.

The system SHALL extract generator expressions.

The system SHALL differentiate sync generators from async generators.

The system SHALL create `python_generators` table with columns: file, line, function_name, has_yield, has_send, is_async.

#### Scenario: Generator function extraction
- **GIVEN** Python function with yield
  ```python
  def count_up(n):
      for i in range(n):
          yield i
  ```
- **WHEN** file is indexed
- **THEN** `python_generators` table contains row with function_name='count_up', has_yield=True, is_async=False

---

### Requirement: Comprehensive Test Fixture Coverage

The system SHALL provide test fixtures covering Django app patterns (~2,000 lines).

The system SHALL provide test fixtures covering async patterns (~800 lines).

The system SHALL provide test fixtures covering pytest patterns (~600 lines).

The system SHALL provide test fixtures covering advanced type system (~400 lines).

The system SHALL provide test fixtures covering decorators/context managers (~500 lines).

The system SHALL achieve total fixture line count >= 4,300 lines (10.7x Phase 1's 441 lines).

#### Scenario: Django app fixture extraction
- **GIVEN** Django app fixture with models, views, forms, admin
- **WHEN** fixture is indexed
- **THEN** all Django tables populated (python_django_views, python_django_forms, python_django_admin)
- **AND** fixture line count >= 2,000 lines

#### Scenario: Async app fixture extraction
- **GIVEN** Async app fixture with async functions, async context managers, AsyncIO patterns
- **WHEN** fixture is indexed
- **THEN** python_async_functions table populated
- **AND** fixture line count >= 800 lines

---

### Requirement: Performance Within Acceptable Limits

The system SHALL complete Phase 2 extraction with <50ms overhead per Python file.

The system SHALL complete taint analysis within <10% regression (830.2s → <913s).

The system SHALL maintain memory cache size <150MB (Phase 1: 77MB, allow <2x increase).

The system SHALL maintain database size <150MB (Phase 1: 71MB, allow <2x increase).

#### Scenario: Extraction performance benchmark
- **GIVEN** 100 Python files from TheAuditor codebase
- **WHEN** indexed with Phase 2 extractors
- **THEN** average extraction time per file <50ms
- **AND** total indexing time increase <5 seconds vs Phase 1

#### Scenario: Taint analysis performance regression
- **GIVEN** TheAuditor codebase
- **WHEN** `aud full --offline` run with Phase 2 extractors
- **THEN** taint analysis completes in <913 seconds (<10% regression from 830.2s baseline)

#### Scenario: Memory cache size acceptable
- **GIVEN** TheAuditor codebase indexed with Phase 2 extractors
- **WHEN** memory cache loads all 15+ Python tables
- **THEN** memory cache size <150MB (<2x Phase 1's 77MB baseline)

---
