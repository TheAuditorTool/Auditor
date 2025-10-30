# python-extraction Specification

## Purpose
TBD - created by archiving change add-python-extraction-parity. Update Purpose after archive.
## Requirements
### Requirement: Python Type Annotation Extraction

The system SHALL extract Python type annotations from function definitions, class definitions, and variable annotations.

The system SHALL extract parameter type annotations from function arguments using `ast.arg.annotation`.

The system SHALL extract return type annotations from function definitions using `ast.FunctionDef.returns`.

The system SHALL extract class attribute type annotations from `ast.AnnAssign` nodes.

The system SHALL serialize type annotations to strings using `ast.unparse()` for Python 3.9+.

The system SHALL store extracted type annotations in the `type_annotations` table with columns: file, line, column, symbol_name, symbol_kind, type_annotation, return_type.

The system SHALL handle generic types (List, Dict, Optional, Union, Tuple) by preserving their full type signature including type parameters.

#### Scenario: Basic function type annotation extraction
- **GIVEN** a Python file with function `def add(x: int, y: int) -> int: return x + y`
- **WHEN** the file is indexed
- **THEN** the `type_annotations` table contains a row with symbol_name='add', return_type='int'
- **AND** the `type_annotations` table contains rows for parameters 'x' and 'y' with type_annotation='int'

#### Scenario: Generic type annotation extraction
- **GIVEN** a Python file with function `def process(items: List[str]) -> Dict[str, int]:`
- **WHEN** the file is indexed
- **THEN** the `type_annotations` table contains a row with symbol_name='process', return_type='Dict[str, int]'
- **AND** parameter 'items' has type_annotation='List[str]' with full generic signature preserved

#### Scenario: Optional type annotation extraction
- **GIVEN** a Python file with function `def lookup(key: str) -> Optional[int]:`
- **WHEN** the file is indexed
- **THEN** return_type='Optional[int]' is stored correctly

#### Scenario: Union type annotation extraction
- **GIVEN** a Python file with function `def parse(value: Union[int, str]) -> str:`
- **WHEN** the file is indexed
- **THEN** parameter 'value' has type_annotation='Union[int, str]'

#### Scenario: Class attribute type annotation extraction
- **GIVEN** a Python class with `class Person: name: str; age: int`
- **WHEN** the file is indexed
- **THEN** the `type_annotations` table contains rows for 'Person.name' with type='str' and 'Person.age' with type='int'

#### Scenario: Function without type annotations (legacy code)
- **GIVEN** a Python file with function `def legacy(x, y): return x + y` (no annotations)
- **WHEN** the file is indexed
- **THEN** the function is extracted to the `symbols` table
- **AND** the `type_annotations` table contains NO rows for this function (or rows with NULL type_annotation)
- **AND** no errors are raised

#### Scenario: Partial type annotations (mixed)
- **GIVEN** a Python file with function `def mixed(x: int, y): return x + y` (partial annotations)
- **WHEN** the file is indexed
- **THEN** parameter 'x' has type_annotation='int'
- **AND** parameter 'y' has type_annotation=NULL or no row

#### Scenario: Complex nested generic types
- **GIVEN** a Python file with function `def complex(data: Dict[str, List[Union[int, str]]]) -> Tuple[str, int]:`
- **WHEN** the file is indexed
- **THEN** parameter 'data' has type_annotation='Dict[str, List[Union[int, str]]]' with full nesting preserved
- **AND** return_type='Tuple[str, int]'

---

### Requirement: SQLAlchemy Model Extraction

The system SHALL detect SQLAlchemy model classes by checking for inheritance from `Base`, `db.Model`, or `Model`.

The system SHALL extract Column() definitions from SQLAlchemy models including field name, field type, and line number.

The system SHALL extract `relationship()` definitions including relationship attribute name and target model when the target string or symbol is provided as the first positional argument.

The system SHALL extract ForeignKey() definitions from Column() declarations.

The system SHALL store SQLAlchemy models in the `python_orm_models` table with columns: file, line, model_name, table_name, orm_type='sqlalchemy'.

The system SHALL store model fields in the `python_orm_fields` table with columns: file, line, model_name, field_name, field_type, is_primary_key, is_foreign_key, foreign_key_target.

The system SHALL store relationships in the existing `orm_relationships` table with source_model, target_model, relationship_type, foreign_key, as_name.

#### Scenario: Basic SQLAlchemy model extraction
- **GIVEN** a Python file with SQLAlchemy model:
  ```python
  class User(Base):
      id = Column(Integer, primary_key=True)
      name = Column(String)
      email = Column(String)
  ```
- **WHEN** the file is indexed
- **THEN** the `python_orm_models` table contains row with model_name='User', orm_type='sqlalchemy'
- **AND** the `python_orm_fields` table contains 3 rows for 'id', 'name', 'email'
- **AND** field 'id' has is_primary_key=True

#### Scenario: SQLAlchemy relationship extraction
- **GIVEN** a Python file with SQLAlchemy models defining a relationship:
  ```python
  class User(Base):
      items = relationship('Item')
  ```
- **WHEN** the file is indexed
- **THEN** the `orm_relationships` table contains row with source_model='User', target_model='Item', as_name='items'

#### Scenario: SQLAlchemy model without explicit __tablename__
- **GIVEN** a SQLAlchemy model without `__tablename__` attribute
- **WHEN** the file is indexed
- **THEN** table_name is NULL (SQLAlchemy infers from class name)

#### Scenario: Non-SQLAlchemy class named Base
- **GIVEN** a Python file with class named `Base` that is NOT a SQLAlchemy model
- **WHEN** the file is indexed
- **THEN** false positive may occur (class detected as SQLAlchemy model)
- **AND** this is acceptable trade-off (prefer false positives over false negatives)

---

### Requirement: Pydantic Model Extraction

The system SHALL detect Pydantic model classes by checking for inheritance from `BaseModel`.

The system SHALL extract field annotations from Pydantic models (already handled by type annotation extraction).

The system SHALL extract `@validator` decorated methods from Pydantic models including validator name, target field(s), and validator type.

The system SHALL extract `@root_validator` decorated methods from Pydantic models.

The system SHALL store Pydantic validators in the `python_validators` table with columns: file, line, model_name, field_name, validator_method, validator_type.

The system SHALL detect FastAPI dependency injection by finding `Depends()` calls in function parameters.

#### Scenario: Pydantic model with field validator
- **GIVEN** a Python file with Pydantic model:
  ```python
  class User(BaseModel):
      email: str
      age: int

      @validator('email')
      def check_email(cls, v):
          assert '@' in v
          return v
  ```
- **WHEN** the file is indexed
- **THEN** the `python_validators` table contains row with model_name='User', field_name='email', validator_method='check_email', validator_type='field'

#### Scenario: Pydantic root validator
- **GIVEN** a Pydantic model with `@root_validator` decorator
- **WHEN** the file is indexed
- **THEN** the `python_validators` table contains row with validator_type='root'

#### Scenario: FastAPI dependency injection detection
- **GIVEN** a FastAPI endpoint with dependency:
  ```python
  @app.get('/users')
  def get_users(db: Session = Depends(get_db)):
      pass
  ```
- **WHEN** the file is indexed
- **THEN** the endpoint is recorded with dependency 'get_db' tracked

---

### Requirement: Flask Route Extraction

The system SHALL detect Flask routes by finding decorators matching `@app.route()`, `@blueprint.route()`, `@api.route()`.

The system SHALL extract route pattern, HTTP methods, and handler function name from Flask route decorators.

The system SHALL detect authentication decorators (`@login_required`, `@auth_required`, `@permission_required`) above route decorators and set `has_auth=True` flag.

The system SHALL extract Flask Blueprint definitions from `Blueprint()` constructor calls.

The system SHALL store Flask routes in the `python_routes` table with columns: file, line, framework='flask', method, pattern, handler_function, has_auth.

The system SHALL store Flask Blueprints in the `python_blueprints` table with columns: file, line, blueprint_name, url_prefix, subdomain.

#### Scenario: Basic Flask route extraction
- **GIVEN** a Python file with Flask route:
  ```python
  @app.route('/users', methods=['GET', 'POST'])
  def users():
      pass
  ```
- **WHEN** the file is indexed
- **THEN** the `python_routes` table contains 2 rows: one with method='GET', one with method='POST'
- **AND** both rows have pattern='/users', handler_function='users', framework='flask'

#### Scenario: Flask route with authentication
- **GIVEN** a Flask route with authentication decorator:
  ```python
  @login_required
  @app.route('/admin')
  def admin():
      pass
  ```
- **WHEN** the file is indexed
- **THEN** the route row has has_auth=True

#### Scenario: Flask Blueprint extraction
- **GIVEN** a Flask Blueprint definition:
  ```python
  api = Blueprint('api', __name__, url_prefix='/api/v1')
  ```
- **WHEN** the file is indexed
- **THEN** the `python_blueprints` table contains row with blueprint_name='api', url_prefix='/api/v1'

#### Scenario: Flask route on Blueprint
- **GIVEN** a Flask route on Blueprint:
  ```python
  @api.route('/users')
  def api_users():
      pass
  ```
- **WHEN** the file is indexed
- **THEN** the route is extracted with pattern='/users'
- **AND** handler_function='api_users'

---

### Requirement: FastAPI Route Extraction

The system SHALL detect FastAPI routes by finding decorators matching `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()`, `@router.get()`, etc.

The system SHALL extract route pattern from decorator's first argument.

The system SHALL infer HTTP method from decorator name (`get` → `GET`, `post` → `POST`).

The system SHALL extract FastAPI dependencies from function parameters with `Depends()` default values.

The system SHALL store FastAPI dependencies as JSON array in the `dependencies` column of `python_routes` table.

The system SHALL store FastAPI routes in the `python_routes` table with columns: file, line, framework='fastapi', method, pattern, handler_function, dependencies.

#### Scenario: Basic FastAPI route extraction
- **GIVEN** a Python file with FastAPI route:
  ```python
  @app.get('/users')
  def get_users():
      return []
  ```
- **WHEN** the file is indexed
- **THEN** the `python_routes` table contains row with method='GET', pattern='/users', handler_function='get_users', framework='fastapi'

#### Scenario: FastAPI route with dependencies
- **GIVEN** a FastAPI route with dependencies:
  ```python
  @app.get('/users')
  def get_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
      pass
  ```
- **WHEN** the file is indexed
- **THEN** the route row has dependencies='["get_db", "get_current_user"]' (JSON array)

#### Scenario: FastAPI path parameters
- **GIVEN** a FastAPI route with path parameters:
  ```python
  @app.get('/users/{user_id}')
  def get_user(user_id: int):
      pass
  ```
- **WHEN** the file is indexed
- **THEN** pattern='/users/{user_id}' is stored
- **AND** parameter 'user_id' type annotation 'int' is stored in type_annotations table

---

### Requirement: Python Import Resolution

The system SHALL resolve relative Python imports to absolute module paths.

The system SHALL use file path + import statement to calculate absolute module name.

The system SHALL handle `from ..module import Name` by navigating up directory levels based on dot count.

The system SHALL handle `from .module import Name` by resolving relative to current directory.

The system SHALL handle `import module` absolute imports by storing module name as-is.

The system SHALL build a `resolved_imports` dictionary mapping imported names to resolved module paths.

The system SHALL NOT resolve virtual environment packages to full site-packages paths (store package name only).

The system SHALL NOT resolve dynamic imports (`importlib.import_module(variable)`).

#### Scenario: Relative import resolution (parent directory)
- **GIVEN** file at `myapp/views/user.py` with import `from ..models import User`
- **WHEN** the file is indexed
- **THEN** import resolves to `myapp.models.User`
- **AND** `resolved_imports['User']` = `'myapp/models.py'`

#### Scenario: Relative import resolution (current directory)
- **GIVEN** file at `myapp/views/user.py` with import `from .forms import UserForm`
- **WHEN** the file is indexed
- **THEN** import resolves to `myapp.views.forms.UserForm`
- **AND** `resolved_imports['UserForm']` = `'myapp/views/forms.py'`

#### Scenario: Absolute import (standard library)
- **GIVEN** file with import `import json`
- **WHEN** the file is indexed
- **THEN** `resolved_imports['json']` = `'json'` (no path resolution)

#### Scenario: Absolute import (third-party package)
- **GIVEN** file with import `import requests`
- **WHEN** the file is indexed
- **THEN** `resolved_imports['requests']` = `'requests'` (package name only, no site-packages path)

#### Scenario: Dynamic import (cannot resolve)
- **GIVEN** file with `importlib.import_module(module_name)` where `module_name` is variable
- **WHEN** the file is indexed
- **THEN** import is NOT resolved (skipped)
- **AND** no error is raised

---

### Requirement: ORM Relationship Graph

The system SHALL extract SQLAlchemy relationships recorded via `relationship()` calls and store their source attribute name and target model when available.

The system SHALL extract Django ORM relationships from `ForeignKey`, `ManyToManyField`, `OneToOneField` field definitions.

The system SHALL store relationships in the existing `orm_relationships` table with columns: file, line, source_model, target_model, relationship_type, foreign_key, cascade_delete, as_name.

The system SHALL detect relationship type (one-to-many, many-to-one, many-to-many, one-to-one) using heuristics based on the relationship construct (e.g., `ForeignKey` → belongsTo, `ManyToManyField` → manyToMany, plural attribute names → hasMany).

#### Scenario: SQLAlchemy one-to-many relationship
- **GIVEN** SQLAlchemy models with one-to-many relationship:
  ```python
  class Author(Base):
      books = relationship('Book')

  class Book(Base):
      author_id = Column(Integer, ForeignKey('authors.id'))
      author = relationship('Author')
  ```
- **WHEN** the file is indexed
- **THEN** the `orm_relationships` table contains row with source_model='Author', target_model='Book', relationship_type='hasMany', as_name='books'
- **AND** the `orm_relationships` table contains row with source_model='Book', target_model='Author', relationship_type='belongsTo', as_name='author'
- **AND** field `author_id` has is_foreign_key=True, foreign_key_target='authors.id'

#### Scenario: Django ForeignKey relationship
- **GIVEN** Django models with ForeignKey:
  ```python
  class Author(models.Model):
      pass

  class Book(models.Model):
      author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
  ```
- **WHEN** the file is indexed
- **THEN** the `orm_relationships` table contains row with source_model='Book', target_model='Author', foreign_key='author', cascade_delete=True

#### Scenario: Django ManyToMany relationship
- **GIVEN** Django model with ManyToManyField:
  ```python
  class Author(models.Model):
      books = models.ManyToManyField('Book', related_name='authors')
  ```
- **WHEN** the file is indexed
- **THEN** the `orm_relationships` table contains row with relationship_type='manyToMany'

---

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility with existing Python extraction.

The system SHALL NOT break existing function extraction, class extraction, import extraction, or call extraction.

The system SHALL preserve existing `args` list in function extraction results (parameter names only).

The system SHALL handle Python files without type annotations gracefully (no errors, NULL type annotations).

The system SHALL NOT modify database schema for existing tables (only add new tables).

#### Scenario: Legacy Python file without type annotations still works
- **GIVEN** a Python file from 2015 with no type annotations
- **WHEN** the file is indexed
- **THEN** functions, classes, imports, calls are still extracted
- **AND** no errors are raised
- **AND** type_annotations table has no rows (or rows with NULL) for this file

#### Scenario: Existing tests still pass after Python extraction enhancements
- **GIVEN** existing test suite for Python extraction
- **WHEN** new type annotation extraction code is deployed
- **THEN** all existing tests pass with 100% pass rate
- **AND** no regression in existing functionality

---

### Requirement: Performance

The system SHALL complete type annotation extraction with <10ms overhead per Python file (Phase 1).

The system SHALL complete framework extraction with <15ms overhead per Python file (Phase 2).

The system SHALL complete import resolution with <10ms overhead per Python file (Phase 3).

The system SHALL maintain total indexing overhead <35ms per Python file across all 3 phases.

The system SHALL NOT introduce memory leaks or excessive memory usage (increase <10MB for 1000 files).

#### Scenario: Performance benchmark - type annotation extraction
- **GIVEN** 100 Python files with type annotations
- **WHEN** files are indexed with type extraction enabled
- **AND** compared to baseline indexing without type extraction
- **THEN** average overhead is <10ms per file
- **AND** total indexing time increase is <1 second for 100 files

#### Scenario: Performance benchmark - framework extraction
- **GIVEN** 100 Python files with Flask/FastAPI routes and SQLAlchemy models
- **WHEN** files are indexed with framework extraction enabled
- **THEN** average overhead is <15ms per file

#### Scenario: Performance benchmark - import resolution
- **GIVEN** 100 Python files with relative and absolute imports
- **WHEN** files are indexed with import resolution enabled
- **THEN** average overhead is <10ms per file

#### Scenario: No performance regression for TypeScript extraction
- **GIVEN** TypeScript files in the same project
- **WHEN** Python extraction enhancements are deployed
- **THEN** TypeScript indexing time is unchanged (no cross-language performance impact)

---

### Requirement: Error Handling

The system SHALL NOT crash if type annotation extraction fails for a specific node (log warning, continue).

The system SHALL NOT crash if framework detection false-positives on non-framework code (extract anyway, acceptable).

The system SHALL NOT crash if import resolution cannot resolve a specific import (skip that import, continue).

The system SHALL log warnings for extraction failures with line number and error message.

The system SHALL NOT use fallback logic (per CLAUDE.md ZERO FALLBACK POLICY) - if extraction fails, return empty list or NULL.

#### Scenario: Malformed type annotation (syntax error in annotation)
- **GIVEN** a Python file with malformed type annotation that causes `ast.unparse()` to fail
- **WHEN** the file is indexed
- **THEN** a warning is logged with the annotation line number
- **AND** that specific type annotation is stored as NULL
- **AND** other valid type annotations in the file are still extracted
- **AND** indexing continues without crashing

#### Scenario: Non-existent module in import resolution
- **GIVEN** a file with import `from nonexistent_module import Foo`
- **WHEN** the file is indexed
- **THEN** import resolution cannot find module
- **AND** that import is skipped (not added to resolved_imports)
- **AND** a debug log message is emitted
- **AND** indexing continues without error

#### Scenario: Framework false positive (class named Base that's not SQLAlchemy)
- **GIVEN** a file with `class Base: pass` that is NOT a SQLAlchemy model
- **WHEN** the file is indexed
- **THEN** class may be detected as SQLAlchemy model (false positive)
- **AND** extraction proceeds (extracts as model even though it's not)
- **AND** this is acceptable trade-off (prefer false positives)

---

