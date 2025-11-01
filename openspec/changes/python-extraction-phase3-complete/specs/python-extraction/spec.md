# Python Extraction Capability Specification

## ADDED Requirements

### Requirement: Flask Deep Dive Extraction

TheAuditor SHALL extract Flask application factories, extensions, request hooks, websocket handlers, and security configurations to enable taint analysis of Flask applications.

#### Scenario: Flask application factory pattern

- **WHEN** a Python file defines `def create_app(config_name): app = Flask(__name__); app.config.from_object(config[config_name]); return app`
- **THEN** the system SHALL extract:
  - Factory function name: `create_app`
  - Factory parameters: `config_name`
  - Application variable: `app`
  - Configuration source: `config[config_name]`
  - File path and line number

#### Scenario: Flask extension registration

- **WHEN** code instantiates `db = SQLAlchemy(app)`
- **THEN** the system SHALL extract:
  - Extension type: `SQLAlchemy`
  - Extension variable: `db`
  - Registered with application: `app`
  - File path and line number

#### Scenario: Flask request hook

- **WHEN** code defines `@app.before_request` decorator on a function
- **THEN** the system SHALL extract:
  - Hook type: `before_request`
  - Hook function name
  - Application instance: `app`
  - File path and line number

### Requirement: Testing Framework Extraction

TheAuditor SHALL extract pytest fixtures, unittest test cases, hypothesis strategies, and test coverage markers to enable test-aware analysis.

#### Scenario: Pytest fixture with yield

- **WHEN** a test file defines `@pytest.fixture` with `yield` statement
- **THEN** the system SHALL extract:
  - Fixture name
  - Scope (function/module/session)
  - Has yield: `True`
  - Teardown code after yield
  - File path and line number

#### Scenario: Unittest test case

- **WHEN** a class inherits from `unittest.TestCase` with test methods
- **THEN** the system SHALL extract:
  - Test class name
  - Test method names (starting with `test_`)
  - Assertion methods used (`assertEqual`, `assertTrue`, etc.)
  - File path and line number

#### Scenario: Hypothesis property-based test

- **WHEN** a test function uses `@given(st.integers())` decorator
- **THEN** the system SHALL extract:
  - Test function name
  - Hypothesis strategies used
  - Property being tested
  - File path and line number

### Requirement: Async/Await Pattern Extraction

TheAuditor SHALL extract async functions, await expressions, async context managers, and asyncio patterns to enable taint flow analysis through asynchronous code.

#### Scenario: Async function definition

- **WHEN** code defines `async def fetch_data(url): async with aiohttp.ClientSession() as session: return await session.get(url)`
- **THEN** the system SHALL extract:
  - Function name: `fetch_data`
  - Is async: `True`
  - Parameters: `url`
  - Async context managers: `aiohttp.ClientSession`, `session.get`
  - Await calls: `session.get`
  - File path and line number

#### Scenario: Async context manager

- **WHEN** code uses `async with` statement
- **THEN** the system SHALL extract:
  - Context manager expression
  - Variable binding (if present)
  - File path and line number

### Requirement: Type Annotation Enhancement

TheAuditor SHALL extract generic types, type aliases, Protocol definitions, TypeVar usage, and NewType definitions to enable type-aware analysis.

#### Scenario: Generic type annotation

- **WHEN** a function signature includes `def process_items(items: List[Dict[str, int]]) -> Optional[int]:`
- **THEN** the system SHALL extract:
  - Parameter `items` type: `List[Dict[str, int]]`
  - Return type: `Optional[int]`
  - Generic types used: `List`, `Dict`, `Optional`
  - Nested type structure preserved
  - File path and line number

#### Scenario: TypeVar definition

- **WHEN** code defines `T = TypeVar('T', bound=BaseModel)`
- **THEN** the system SHALL extract:
  - TypeVar name: `T`
  - Bound type: `BaseModel`
  - Constraints (if any)
  - File path and line number

#### Scenario: Protocol definition

- **WHEN** a class inherits from `Protocol` with typed methods
- **THEN** the system SHALL extract:
  - Protocol name
  - Required methods with signatures
  - File path and line number

### Requirement: Django ORM Deep Extraction

TheAuditor SHALL extract Django custom managers, querysets, model methods, signals, and Meta options to enable Django-specific taint analysis.

#### Scenario: Django custom manager

- **WHEN** a model defines `published = PublishedManager()` where `PublishedManager` extends `models.Manager`
- **THEN** the system SHALL extract:
  - Manager class name: `PublishedManager`
  - Model name: `Article`
  - Manager instance name: `published`
  - Custom queryset methods (if overridden)
  - File path and line number

#### Scenario: Django signal connection

- **WHEN** code uses `@receiver(post_save, sender=User)` decorator
- **THEN** the system SHALL extract:
  - Signal type: `post_save`
  - Sender model: `User`
  - Receiver function name
  - File path and line number

#### Scenario: Django model Meta options

- **WHEN** a Django model has `class Meta: db_table = 'custom_users'; ordering = ['-created_at']`
- **THEN** the system SHALL extract:
  - Model name
  - Custom table name: `custom_users`
  - Ordering: `['-created_at']`
  - Other Meta options
  - File path and line number

### Requirement: Security Pattern Extraction

TheAuditor SHALL extract authentication decorators, password hashing, JWT operations, CSRF protection, SQL queries, file operations, subprocess calls, and dangerous eval/exec usage for security analysis.

#### Scenario: Authentication decorator

- **WHEN** a view function has `@login_required` decorator
- **THEN** the system SHALL extract:
  - Decorator type: `login_required`
  - Function name
  - Required permissions (if specified)
  - File path and line number

#### Scenario: Password hashing detection

- **WHEN** code calls `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`
- **THEN** the system SHALL extract:
  - Hashing library: `bcrypt`
  - Method: `hashpw`
  - Input variable: `password`
  - File path and line number

#### Scenario: Raw SQL query

- **WHEN** code executes `cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")`
- **THEN** the system SHALL extract:
  - Query text (with interpolation markers)
  - Execution method: `cursor.execute`
  - Is parameterized: `False` (string interpolation used)
  - Input variables: `user_id`
  - File path and line number

#### Scenario: Dangerous eval usage

- **WHEN** code calls `eval(user_input)`
- **THEN** the system SHALL extract:
  - Dangerous function: `eval`
  - Input expression: `user_input`
  - File path and line number
  - Mark as high-risk pattern

## MODIFIED Requirements

### Requirement: Parameter Resolution Enhancement

TheAuditor SHALL enhance existing parameter resolution to support *args, **kwargs, default values, and complex parameter patterns.

#### Scenario: Function with variadic arguments

- **WHEN** a function signature is `def process(a: int, b: str = 'default', *args, **kwargs) -> None:`
- **THEN** the system SHALL extract:
  - Regular parameters: `a`, `b`
  - Default values: `b='default'`
  - Variadic positional: `*args`
  - Variadic keyword: `**kwargs`
  - Type annotations for all typed parameters
  - Return type annotation
  - File path and line number

## Performance Requirements

### Requirement: Extraction Performance Targets

All Python extractors SHALL meet performance targets to enable real-time analysis on large codebases.

#### Scenario: Extract large Python file efficiently

- **WHEN** processing a Python file with 5,000 lines of code
- **THEN** the system SHALL:
  - Complete extraction in <10ms per file
  - Use <50MB memory for AST parsing
  - Insert database records in <5ms batch
  - Maintain no memory leaks across multiple files

## Integration Requirements

### Requirement: Taint Analysis Integration

Python extractors SHALL populate database tables required by taint analysis for vulnerability detection in Python code.

#### Scenario: Flask route taint flow detection

- **WHEN** a Flask route has `@app.route('/user/<user_id>')` with `db.execute(f"SELECT * FROM users WHERE id = {user_id}")`
- **THEN** taint analysis SHALL:
  - Identify source: `user_id` (route parameter)
  - Identify sink: `db.execute` (SQL query)
  - Detect vulnerability: SQL injection (f-string interpolation)
  - Report file, line, and vulnerability type
  - Include full taint flow path from source to sink
