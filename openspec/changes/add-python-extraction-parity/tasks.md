# Implementation Tasks: Python Extraction Parity

## 0. Verification (PRE-IMPLEMENTATION)

**Purpose**: Complete verification before writing any code, per teamsop.md SOP v4.20

- [x] 0.1 Create `verification.md` documenting all verification findings
- [x] 0.2 Verify Python AST API for type annotation access
  - Verify `ast.FunctionDef` has `args` attribute with `ast.arguments` type
  - Verify `ast.arguments` has `args` list containing `ast.arg` objects
  - Verify `ast.arg` has `annotation` attribute (can be None)
  - Verify `ast.FunctionDef` has `returns` attribute (can be None)
  - Verify `ast.AnnAssign` for variable type annotations
  - Test with fixture: `def foo(x: int, y: str) -> bool: pass`
- [x] 0.3 Verify database schema for type_annotations table
  - Read `theauditor/indexer/schema.py:1025-1049`
  - Confirm TYPE_ANNOTATIONS table exists with columns: file, line, column, symbol_name, type_annotation, return_type
  - Verify no schema changes needed (table already exists)
  - Confirm column types match what Python extraction will provide
- [x] 0.4 Verify current Python extractor behavior
  - Read `theauditor/ast_extractors/python_impl.py:29-57` (extract_python_functions)
  - Document line 54: `"args": [arg.arg for arg in node.args.args]` - only extracts arg NAMES
  - Verify annotations are accessible but not extracted
  - Test with grep: `grep "annotation" theauditor/ast_extractors/python_impl.py` (expect 0 hits)
- [x] 0.5 Verify TypeScript type annotation format for consistency
  - Read `theauditor/ast_extractors/typescript_impl.py:704-716`
  - Document TypeScript type annotation serialization format
  - Verify Python can match this format for consistency
  - Test TypeScript sample: `function foo(x: number): string` → verify storage format
- [x] 0.6 Verify indexer storage path for type annotations
  - Read `theauditor/indexer/extractors/javascript.py:136-151`
  - Document how JavaScript stores type annotations
  - Verify Python extractor can follow same pattern
  - Check indexer/__init__.py for type_annotations storage logic
- [ ] 0.7 Test Python type hint extraction with minimal fixture
  - Create `tests/fixtures/python/type_test.py` with 5 functions using type hints
  - Run manual AST walk to verify annotation nodes are accessible
  - Document findings in verification.md
- [ ] 0.8 Verify no blocking dependencies or conflicts
  - Check for any code that assumes Python has no type annotations
  - Check taint analyzer for Python type assumptions
  - Verify adding type annotations won't break existing code
- [x] 0.9 Document all discrepancies between proposal assumptions and code reality
  - List any proposal claims that don't match actual code
  - Document workarounds or plan adjustments needed
- [ ] 0.10 Get verification.md approved before proceeding to Phase 1

---

## PHASE 1: TYPE SYSTEM PARITY

### 1. Python Type Annotation Extraction - Functions

**File**: `theauditor/ast_extractors/python_impl.py:29-57`

- [x] 1.1 Add `_get_type_annotation()` helper function
  - **Location**: After line 27, before `extract_python_functions()`
  - **Implementation**:
    ```python
    def _get_type_annotation(node: Optional[ast.expr]) -> Optional[str]:
        """Convert AST type annotation node to string.

        Args:
            node: AST node representing type annotation (can be None)

        Returns:
            String representation of type, or None if no annotation
        """
        if node is None:
            return None

        return ast.unparse(node) if hasattr(ast, 'unparse') else None
    ```
  - **Why**: Centralize type serialization logic. `ast.unparse()` added in Python 3.9 converts AST back to code string.
  - **Alternative**: If Python <3.9, use `astor.to_source()` or manual serialization
  - **Test**: Verify `_get_type_annotation(ast.parse("int").body[0].value)` returns `"int"`

- [x] 1.2 Modify `extract_python_functions()` to extract parameter type annotations
  - **Location**: Line 54 - replace `"args": [arg.arg for arg in node.args.args]`
  - **Before**:
    ```python
    "args": [arg.arg for arg in node.args.args],
    ```
  - **After**:
    ```python
    # Preserve legacy args list plus rich metadata for all param kinds
    function_entry["args"] = [arg.arg for arg in node.args.args]
    parameter_entries.append({
        "name": arg.arg,
        "kind": kind,
        "type_annotation": annotation_text,
        "is_generic": is_generic,
        "has_type_params": has_type_params,
        "type_params": type_params,
    })
    ```
  - **Why**: Capture annotations for positional-only, standard, vararg, kw-only, and kwarg parameters with generic flags.
  - **Test**: Function `def foo(x: int, *, y: str) -> None` stores entries for both parameters with annotations.

- [x] 1.3 Add return type annotation extraction
  - **Location**: After "args" extraction in extract_python_functions()
  - **Implementation**:
    ```python
    "return_type": _get_type_annotation(node.returns),
    ```
  - **Why**: Capture function return type for type-aware analysis
  - **Test**: Function `def foo() -> bool: pass` should produce `"return_type": "bool"`

- [x] 1.4 Add decorator extraction for type-relevant decorators
  - **Location**: After "return_type" in extract_python_functions()
  - **Implementation**:
    ```python
    "decorators": [get_node_name(dec) for dec in node.decorator_list],
    ```
  - **Why**: Decorators like `@overload`, `@abstractmethod` affect type semantics
  - **Test**: Function with `@property` decorator should capture it

- [x] 1.5 Handle generic types (List, Dict, Optional, Union, Tuple)
  - **Location**: In `_get_type_annotation()` function
  - **Verification**: Ensure `ast.unparse()` correctly serializes subscripted types
  - **Test Cases**:
    - `List[str]` → `"List[str]"`
    - `Dict[str, int]` → `"Dict[str, int]"`
    - `Optional[str]` → `"Optional[str]"` or `"str | None"`
    - `Union[int, str]` → `"Union[int, str]"` or `"int | str"`
  - **Note**: Python 3.10+ uses `|` syntax, 3.9- uses `Union`. Both should work.

- [x] 1.6 Handle type comments (PEP 484) for Python 3.5-3.7 compatibility
  - **Location**: In extract_python_functions() after "return_type"
  - **Implementation**:
    ```python
    "type_comment": node.type_comment if hasattr(node, 'type_comment') else None,
    ```
  - **Why**: Older Python code uses `# type: (int, str) -> bool` comments instead of annotations
  - **Test**: Function with `# type: (int) -> str` comment should capture it

### 2. Python Type Annotation Extraction - Classes

**File**: `theauditor/ast_extractors/python_impl.py:60-77`

- [x] 2.1 Add class attribute type annotation extraction
  - **Location**: In extract_python_classes(), after "bases" extraction
  - **Implementation**:
    ```python
    # Extract class-level annotated assignments (class attributes with types)
    attributes = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign):
            attr_name = get_node_name(item.target)
            attr_type = _get_type_annotation(item.annotation)
            if attr_name and attr_type:
                attributes.append({
                    "name": attr_name,
                    "type": attr_type,
                    "line": item.lineno
                })

    annotations = extract_python_attribute_annotations(...)
```
  - **Why**: Class attributes with type annotations are important for ORM models, dataclasses, Pydantic models
  - **Test**: Class with `class Foo: x: int; y: str` should extract attributes

- [ ] 2.2 Extract base class type parameters (generics)
  - **Location**: In extract_python_classes(), modify "bases" extraction
  - **Before**: `"bases": [get_node_name(base) for base in node.bases]`
  - **After**:
    ```python
    "bases": [get_node_name(base) for base in node.bases],
    "base_types": [_get_type_annotation(base) for base in node.bases],
    ```
  - **Why**: Generic base classes like `class Foo(Generic[T]):` or `class Bar(List[int]):` carry type information
  - **Test**: `class Foo(Generic[T]):` should extract `"base_types": ["Generic[T]"]`

- [ ] 2.3 Detect and flag dataclass/Pydantic models
  - **Location**: In extract_python_classes(), after "bases"
  - **Implementation**:
    ```python
    "decorators": [get_node_name(dec) for dec in node.decorator_list],
    "is_dataclass": any(get_node_name(dec) in ('dataclass', 'dataclasses.dataclass') for dec in node.decorator_list),
    "is_pydantic": any('BaseModel' in base for base in [get_node_name(b) for b in node.bases]),
    ```
  - **Why**: Dataclasses and Pydantic models have special type semantics (auto-generated __init__, validation)
  - **Test**: `@dataclass class Foo:` should set `"is_dataclass": True`

### 3. Database Storage - Type Annotations

**File**: `theauditor/indexer/extractors/python.py:47-75`

- [x] 3.1 Add type annotation storage in Python extractor result dict
  - **Location**: In Python extractor's extract() method, where result dict is built
  - **Implementation**:
    ```python
    result = {
        'imports': [],
        'routes': [],
        'symbols': [],
        'assignments': [],
        'function_calls': [],
        'returns': [],
        'type_annotations': [],  # ADD THIS
        # ... existing keys ...
    }
    ```
  - **Why**: Initialize type_annotations list to receive extracted data

- [x] 3.2 Populate type_annotations from extracted function data
  - **Location**: After functions are extracted, before returning result
  - **Implementation**:
    ```python
    for annotation in func.get('type_annotations', []):
        result['type_annotations'].append(annotation)
    ```
  - **Why**: Transform extracted type data into database-ready format matching schema
  - **Compatibility**: Match JavaScript format from `extractors/javascript.py:136-151`

- [x] 3.3 Handle class attribute type annotations
  - **Location**: After classes are extracted
  - **Implementation**:
    ```python
    # Convert class attribute type data to type_annotations format
    for cls in classes:
    for attr in python_impl.extract_python_attribute_annotations(tree, self.ast_parser):
        result['type_annotations'].append(attr)
    ```

- [x] 3.4 Verify database schema compatibility
  - **Pre-implementation**: Check `theauditor/indexer/schema.py:1025-1049` for TYPE_ANNOTATIONS columns
  - **Columns to populate**: file, line, column, symbol_name, symbol_kind, type_annotation, return_type
  - **Columns to leave NULL**: is_any, is_unknown, is_generic, has_type_params, type_params, extends_type
  - **Why**: Python ast module doesn't provide TypeScript-level type analysis (any/unknown detection). Leave advanced columns NULL for now.

- [x] 3.5 Update indexer to store Python type annotations
  - **File**: `theauditor/indexer/__init__.py`
  - **Location**: Search for JavaScript type_annotations storage (likely around where symbols are stored)
  - **Action**: Verify Python extractor result['type_annotations'] is processed same as JavaScript
  - **Test**: After indexing Python file with type hints, query database: `SELECT * FROM type_annotations WHERE symbol_name LIKE '%.py%'`

### 4. Testing - Type Annotation Extraction

**Fixtures**: Create in `tests/fixtures/python/`

- [ ] 4.1 Create `type_hints_basic.py` - Basic type annotations
  - **Content**:
    ```python
    def add(x: int, y: int) -> int:
        return x + y

    def greet(name: str) -> str:
        return f"Hello, {name}"

    def process(data: dict, flag: bool = False) -> None:
        pass

    class Person:
        name: str
        age: int

        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age
    ```
  - **Purpose**: Test basic int, str, bool, dict, None types

- [ ] 4.2 Create `type_hints_generics.py` - Generic type annotations
  - **Content**:
    ```python
    from typing import List, Dict, Optional, Union, Tuple, Set

    def process_list(items: List[str]) -> List[int]:
        return [len(item) for item in items]

    def lookup(data: Dict[str, int], key: str) -> Optional[int]:
        return data.get(key)

    def parse(value: Union[int, str]) -> str:
        return str(value)

    def coords() -> Tuple[float, float]:
        return (0.0, 0.0)
    ```
  - **Purpose**: Test generic types (List, Dict, Optional, Union, Tuple)

- [ ] 4.3 Create `type_hints_classes.py` - Class type annotations
  - **Content**:
    ```python
    from dataclasses import dataclass
    from typing import Generic, TypeVar

    @dataclass
    class Config:
        host: str
        port: int
        debug: bool = False

    T = TypeVar('T')

    class Container(Generic[T]):
        value: T

        def get(self) -> T:
            return self.value
    ```
  - **Purpose**: Test dataclasses, generic classes, class attributes

- [ ] 4.4 Create `type_hints_edge_cases.py` - Edge cases
  - **Content**:
    ```python
    from typing import Any, Callable

    # No annotations
    def legacy(x, y):
        return x + y

    # Partial annotations
    def mixed(x: int, y):
        return x + y

    # Complex types
    def callback(func: Callable[[int, str], bool]) -> None:
        pass

    # Type comments (pre-3.6)
    def old_style(x, y):
        # type: (int, str) -> bool
        return True

    # Any type
    def dynamic(value: Any) -> Any:
        return value
    ```
  - **Purpose**: Test edge cases, mixed annotations, legacy code

**Test Cases**: Create in `tests/test_python_type_extraction.py`

- [ ] 4.5 Test basic type annotation extraction
  - **Test**: Index `type_hints_basic.py`, query `type_annotations` table
  - **Assertions**:
    - `add` function has `return_type = "int"`
    - `add` parameters `x` and `y` have `type_annotation = "int"`
    - `greet` function has `return_type = "str"`
    - `process` function has `return_type = "None"` or NULL
    - `Person` class attributes `name` and `age` have type annotations

- [ ] 4.6 Test generic type annotation extraction
  - **Test**: Index `type_hints_generics.py`, query `type_annotations` table
  - **Assertions**:
    - `process_list` has `return_type = "List[int]"`
    - `lookup` has `return_type = "Optional[int]"`
    - `parse` parameter has `type_annotation = "Union[int, str]"`
    - `coords` has `return_type = "Tuple[float, float]"`

- [ ] 4.7 Test class type annotation extraction
  - **Test**: Index `type_hints_classes.py`, query `type_annotations` table
  - **Assertions**:
    - `Config` attributes have type annotations (host: str, port: int, debug: bool)
    - `Container` is detected as generic class
    - `Container.get` has return type `T`

- [ ] 4.8 Test edge cases
  - **Test**: Index `type_hints_edge_cases.py`, query `type_annotations` table
  - **Assertions**:
    - `legacy` function has NO type annotations (NULL return_type)
    - `mixed` function has partial annotations (x has type, y doesn't)
    - `callback` has complex `Callable[[int, str], bool]` type
    - `old_style` type comment is captured (if Python <3.6 support needed)
    - `dynamic` has `Any` type annotations

- [ ] 4.9 Test database consistency with TypeScript
  - **Test**: Index both Python and TypeScript files, compare `type_annotations` rows
  - **Assertions**:
    - Column formats match (symbol_name, type_annotation, return_type)
    - Python types don't pollute TypeScript analysis
    - No NULL constraint violations

- [ ] 4.10 Test performance impact
  - **Test**: Benchmark indexing before and after type annotation extraction
  - **Baseline**: Index 100 Python files without type extraction
  - **With Types**: Index same 100 files with type extraction
  - **Assertion**: Overhead <10ms per file (acceptable)

### 5. Regression Testing - Phase 1

- [ ] 5.1 Run full existing test suite: `pytest tests/ -v`
  - **Purpose**: Ensure no existing tests broken by type annotation changes
  - **Expected**: 100% pass rate, same as before
  - **If failures**: Identify and fix root cause before proceeding

- [ ] 5.2 Verify Python extraction without type hints still works
  - **Test**: Index Python file with NO type hints (legacy code)
  - **Assertion**: No errors, no NULL violations, symbols still extracted

- [ ] 5.3 Verify TypeScript extraction unaffected
  - **Test**: Index TypeScript file, check `type_annotations` table
  - **Assertion**: TypeScript rows unchanged, no format changes

- [ ] 5.4 Verify taint analysis still runs
  - **Test**: Run taint analysis on Python project
  - **Assertion**: No crashes, results still produced (may be same or improved)

### 6. Documentation - Phase 1

- [ ] 6.1 Update CLAUDE.md with Python type extraction capabilities
  - **Location**: Search for "type annotation" or "Python extraction" section
  - **Add**: Document that Python type hints are now extracted
  - **Add**: List supported type constructs (int, str, List[T], Optional[T], etc.)
  - **Add**: Note limitations (no inference, no Any/Unknown detection like TypeScript)

- [ ] 6.2 Add inline documentation to python_impl.py
  - **Location**: Add docstring to `_get_type_annotation()`
  - **Location**: Update docstring for `extract_python_functions()` mentioning type extraction
  - **Location**: Update docstring for `extract_python_classes()` mentioning attribute types

- [ ] 6.3 Update PARITY_AUDIT_VERIFIED.md with Phase 1 results
  - **Location**: After implementation complete
  - **Add**: Section documenting Phase 1 completion
  - **Add**: Updated metrics: Python type annotations extracted (was 0, now >0)
  - **Add**: Updated parity score (was 15-25%, now ~30-35%)

### 7. Code Quality - Phase 1

- [ ] 7.1 Run linting: `ruff check theauditor/ast_extractors --fix`
- [ ] 7.2 Run formatting: `ruff format theauditor/ast_extractors`
- [ ] 7.3 Run type checking: `mypy theauditor/ast_extractors --strict`
- [ ] 7.4 Verify all new code has docstrings and inline comments
- [ ] 7.5 Verify no dead code or unused imports

### 8. OpenSpec Validation - Phase 1

- [ ] 8.1 Run `openspec validate add-python-extraction-parity --strict`
- [ ] 8.2 Resolve any validation errors
- [ ] 8.3 Verify all Phase 1 scenarios in spec.md are testable
- [ ] 8.4 Update tasks.md to mark Phase 1 tasks complete

### 9. Approval & Deployment - Phase 1

- [ ] 9.1 Post-implementation audit: Re-read all modified files
- [ ] 9.2 Confirm no syntax errors introduced
- [ ] 9.3 Confirm no logical flaws
- [ ] 9.4 Run full test suite one final time
- [ ] 9.5 Request Architect approval for Phase 1
- [ ] 9.6 Deploy Phase 1 to production
- [ ] 9.7 Monitor for issues post-deployment
- [ ] 9.8 Proceed to Phase 2 only after Phase 1 approval

---

## PHASE 2: FRAMEWORK SUPPORT PARITY

### 10. SQLAlchemy Model Extraction

**File**: `theauditor/ast_extractors/python_impl.py` (new function)

- [x] 10.1 Add `extract_sqlalchemy_models()` function
  - **Location**: After extract_python_classes(), before extract_python_calls()
  - **Implementation Outline**:
    ```python
    def extract_sqlalchemy_models(tree: Dict, parser_self) -> List[Dict]:
        """Extract SQLAlchemy model definitions.

        Detects classes inheriting from Base, db.Model, or declarative_base().
        Extracts fields, relationships, foreign keys.
        """
        models = []
        actual_tree = tree.get("tree")

        if not actual_tree:
            return models

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.ClassDef):
                # Check if inherits from SQLAlchemy base
                bases = [get_node_name(base) for base in node.bases]
                if any(base in ('Base', 'db.Model', 'Model') for base in bases):
                    # This is a SQLAlchemy model
                    fields = []
                    relationships = []

                    # Extract Column() definitions
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            # Check if assignment is Column(...)
                            if isinstance(item.value, ast.Call):
                                func_name = get_node_name(item.value.func)
                                if func_name == 'Column':
                                    # Extract field info
                                    field_name = get_node_name(item.targets[0])
                                    field_type = None
                                    if item.value.args:
                                        field_type = get_node_name(item.value.args[0])

                                    fields.append({
                                        'name': field_name,
                                        'type': field_type,
                                        'line': item.lineno
                                    })

                                # Check for relationship() definitions
                                elif func_name == 'relationship':
                                    # Extract relationship info
                                    rel_name = get_node_name(item.targets[0])
                                    target_model = None
                                    if item.value.args:
                                        # First arg is usually target model as string
                                        target_model = get_node_name(item.value.args[0])

                                    relationships.append({
                                        'name': rel_name,
                                        'target_model': target_model,
                                        'line': item.lineno
                                    })

                    models.append({
                        'name': node.name,
                        'line': node.lineno,
                        'fields': fields,
                        'relationships': relationships
                    })

        return models
    ```
  - **Why**: SQLAlchemy models are critical for backend Python apps. Need to extract schema and relationships.
  - **Test**: Model with `class User(Base): id = Column(Integer)` should extract field

- [x] 10.2 Extract ForeignKey definitions
  - **Location**: In extract_sqlalchemy_models(), within Column() extraction
  - **Logic**: Check Column() call for ForeignKey in arguments
  - **Example**: `user_id = Column(Integer, ForeignKey('users.id'))` → extract FK relationship

- [x] 10.3 Extract relationship back_populates and backref
  - **Location**: In extract_sqlalchemy_models(), within relationship() extraction
  - **Logic**: Parse relationship() keyword arguments for `back_populates`, `backref`
  - **Example**: `items = relationship('Item', back_populates='owner')` → extract bidirectional relationship

- [x] 10.4 Store SQLAlchemy models in orm_relationships table
  - **Location**: In Python extractor's extract() method, after model extraction
  - **Implementation**:
    ```python
    # Convert SQLAlchemy relationships to orm_relationships format
    for model in sqlalchemy_models:
        for rel in model['relationships']:
            result['orm_relationships'].append({
                'line': rel['line'],
                'source_model': model['name'],
                'target_model': rel['target_model'],
                'relationship_type': 'hasMany',  # TODO: detect actual type
                'foreign_key': None,  # TODO: extract FK
                'cascade_delete': False,  # TODO: detect CASCADE
                'as_name': rel['name']
            })
    ```
  - **Why**: Populate existing orm_relationships table (already in schema)

### 11. Pydantic Validator Extraction

**File**: `theauditor/ast_extractors/python_impl.py` (new helper)

- [x] 11.1 Add `extract_pydantic_validators()` function
  - **Location**: After SQLAlchemy helpers
  - **Purpose**: Detect `BaseModel` subclasses and record validator methods
  - **Detection**: Check class bases for `BaseModel` suffix
  - **Extraction**:
    - `@validator` decorated methods (field-level)
    - `@root_validator` decorated methods (model-level)
  - **Test**: `class User(BaseModel): @validator('email')` should register validator entry

- [x] 11.2 Extract Pydantic field validators
  - **Location**: In `extract_pydantic_validators()`, check for `@validator` decorators
  - **Implementation**: Store validator method names and target fields
  - **Example**: `@validator('email')` → extract that `email` field has validation

- [x] 11.3 Extract FastAPI dependency injection
  - **Location**: `_extract_fastapi_dependencies()` helper invoked by `extract_fastapi_routes()`
  - **Detection**: Parameters with `Depends()` default value
  - **Example**: `def endpoint(db: Session = Depends(get_db)):` → extract dependency

- [x] 11.4 Store Pydantic data in new python_validators table
  - **Note**: Table doesn't exist yet, create in schema changes (task 15.1)

### 12. Flask Route Extraction

**File**: `theauditor/ast_extractors/python_impl.py` (new function)

- [x] 12.1 Add `extract_flask_routes()` function
  - **Location**: After extract_pydantic_models()
  - **Purpose**: Extract Flask route decorators
  - **Detection**: Check for `@app.route()`, `@blueprint.route()`, `@api.route()` decorators
  - **Extraction**:
    - Route pattern (e.g., `/users/<int:id>`)
    - HTTP methods (GET, POST, PUT, DELETE)
    - Middleware/auth decorators above route decorator
    - Function name (handler)
  - **Test**: `@app.route('/users', methods=['GET'])` should extract route

- [x] 12.2 Detect Flask authentication/middleware decorators
  - **Location**: In extract_flask_routes(), check decorators above route decorator
  - **Common patterns**: `@login_required`, `@auth_required`, `@permission_required`
  - **Store**: Flag `has_auth` if auth decorator present
  - **Example**: `@login_required` above `@app.route()` → set `has_auth=True`

- [x] 12.3 Extract Flask Blueprint hierarchy
  - **Location**: Separate function or within extract_flask_routes()
  - **Detection**: `Blueprint()` constructor calls
  - **Example**: `api = Blueprint('api', __name__)` → extract blueprint definition
  - **Store**: Blueprint name, URL prefix (if available)

- [x] 12.4 Store Flask routes in new python_routes table
  - **Note**: Table doesn't exist yet, create in schema changes (task 15.2)

### 13. FastAPI Route Extraction

**File**: `theauditor/ast_extractors/python_impl.py` (new function)

- [x] 13.1 Add `extract_fastapi_routes()` function
  - **Location**: After extract_flask_routes()
  - **Purpose**: Extract FastAPI route decorators
  - **Detection**: Check for `@app.get()`, `@app.post()`, `@router.get()` decorators
  - **Extraction**:
    - Route pattern
    - HTTP method (derived from decorator name)
    - Dependencies (via Depends())
    - Response model (via response_model parameter)
    - Tags, summary, description (via decorator parameters)
  - **Test**: `@app.get('/users', response_model=User)` should extract route

- [x] 13.2 Extract FastAPI dependency injection
  - **Location**: In extract_fastapi_routes(), analyze function parameters
  - **Detection**: Parameters with `Depends()` default value
  - **Example**: `db: Session = Depends(get_db)` → extract dependency injection
  - **Store**: Parameter name, dependency function

- [ ] 13.3 Extract FastAPI path/query parameters
  - **Location**: In extract_fastapi_routes(), analyze function parameters
  - **Detection**: Parameters with Path(), Query(), Body() annotations
  - **Example**: `user_id: int = Path(...)` → extract path parameter
  - **Store**: Parameter name, type, validation constraints

- [x] 13.4 Store FastAPI routes in python_routes table (same as Flask)

### 14. Django Model Extraction (Optional - Can Defer)

**Note**: Django support is lower priority than Flask/FastAPI. Can be deferred to Phase 3 or future proposal.

- [x] 14.1 Add Django model extraction helper
  - **Detection**: Check for `models.Model` inheritance
  - **Extraction**: Capture fields, `ForeignKey`, `ManyToManyField`, `OneToOneField` relationships
  - **Store**: Populate `python_orm_models` and shared `orm_relationships`

### 15. Database Schema Changes - Phase 2

**File**: `theauditor/indexer/schema.py`

- [x] 15.1 Add PYTHON_VALIDATORS table schema
  - **Location**: After ORM_RELATIONSHIPS table definition (line ~384)
  - **Implementation**:
    ```python
    PYTHON_VALIDATORS = TableSchema(
        name="python_validators",
        columns=[
            Column("file", "TEXT", nullable=False),
            Column("line", "INTEGER", nullable=False),
            Column("model_name", "TEXT", nullable=False),
            Column("field_name", "TEXT", nullable=False),
            Column("validator_method", "TEXT", nullable=False),
            Column("validator_type", "TEXT", nullable=False),  # "field", "root", "pre", "post"
        ],
        primary_key=["file", "line", "model_name", "field_name"],
        indexes=[
            ("idx_python_validators_file", ["file"]),
            ("idx_python_validators_model", ["model_name"]),
        ]
    )
    ```
  - **Why**: Store Pydantic field validators for framework-aware analysis

- [x] 15.2 Add PYTHON_ROUTES table schema
  - **Location**: After PYTHON_VALIDATORS table definition
  - **Implementation**:
    ```python
    PYTHON_ROUTES = TableSchema(
        name="python_routes",
        columns=[
            Column("file", "TEXT", nullable=False),
            Column("line", "INTEGER", nullable=False),
            Column("framework", "TEXT", nullable=False),  # "flask", "fastapi", "django"
            Column("method", "TEXT", nullable=False),  # "GET", "POST", etc.
            Column("pattern", "TEXT", nullable=False),  # "/users/<int:id>"
            Column("handler_function", "TEXT", nullable=False),
            Column("has_auth", "BOOLEAN", default="0"),
            Column("dependencies", "TEXT"),  # JSON array of dependency names (FastAPI)
        ],
        primary_key=["file", "line", "pattern"],
        indexes=[
            ("idx_python_routes_file", ["file"]),
            ("idx_python_routes_framework", ["framework"]),
            ("idx_python_routes_method", ["method"]),
        ]
    )
    ```
  - **Why**: Store Flask/FastAPI routes for API endpoint analysis

- [x] 15.3 Add PYTHON_ORM_MODELS table schema
  - **Location**: After PYTHON_ROUTES table definition
  - **Implementation**:
    ```python
    PYTHON_ORM_MODELS = TableSchema(
        name="python_orm_models",
        columns=[
            Column("file", "TEXT", nullable=False),
            Column("line", "INTEGER", nullable=False),
            Column("model_name", "TEXT", nullable=False),
            Column("table_name", "TEXT"),  # Explicit __tablename__ if present
            Column("orm_type", "TEXT", nullable=False),  # "sqlalchemy", "django", "pydantic"
        ],
        primary_key=["file", "model_name"],
        indexes=[
            ("idx_python_orm_models_file", ["file"]),
            ("idx_python_orm_models_type", ["orm_type"]),
        ]
    )
    ```

- [x] 15.4 Add PYTHON_ORM_FIELDS table schema
  - **Location**: After PYTHON_ORM_MODELS table definition
  - **Implementation**:
    ```python
    PYTHON_ORM_FIELDS = TableSchema(
        name="python_orm_fields",
        columns=[
            Column("file", "TEXT", nullable=False),
            Column("line", "INTEGER", nullable=False),
            Column("model_name", "TEXT", nullable=False),
            Column("field_name", "TEXT", nullable=False),
            Column("field_type", "TEXT"),  # Integer, String, etc.
            Column("is_primary_key", "BOOLEAN", default="0"),
            Column("is_foreign_key", "BOOLEAN", default="0"),
            Column("foreign_key_target", "TEXT"),  # "users.id"
            Column("is_nullable", "BOOLEAN", default="1"),
        ],
        primary_key=["file", "model_name", "field_name"],
        indexes=[
            ("idx_python_orm_fields_model", ["model_name"]),
            ("idx_python_orm_fields_fk", ["is_foreign_key"]),
        ]
    )
    ```

- [x] 15.5 Add PYTHON_BLUEPRINTS table schema (Flask)
  - **Location**: After PYTHON_ORM_FIELDS table definition
  - **Implementation**:
    ```python
    PYTHON_BLUEPRINTS = TableSchema(
        name="python_blueprints",
        columns=[
            Column("file", "TEXT", nullable=False),
            Column("line", "INTEGER", nullable=False),
            Column("blueprint_name", "TEXT", nullable=False),
            Column("url_prefix", "TEXT"),
            Column("subdomain", "TEXT"),
        ],
        primary_key=["file", "blueprint_name"],
        indexes=[
            ("idx_python_blueprints_file", ["file"]),
        ]
    )
    ```

- [x] 15.6 Register all new tables in TABLES dict
  - **Location**: Bottom of schema.py, in TABLES dict
  - **Add**:
    ```python
    # Python framework tables
    "python_validators": PYTHON_VALIDATORS,
    "python_routes": PYTHON_ROUTES,
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,
    "python_blueprints": PYTHON_BLUEPRINTS,
    ```

### 16. Database Storage - Framework Data

**File**: `theauditor/indexer/extractors/python.py`

- [ ] 16.1 Initialize new result dict keys for framework data
  - **Location**: In extract() method, add to result dict
  - **Add**:
    ```python
    result = {
        # ... existing keys ...
        'sqlalchemy_models': [],
        'pydantic_models': [],
        'flask_routes': [],
        'fastapi_routes': [],
        'python_validators': [],
        'python_orm_models': [],
        'python_orm_fields': [],
        'python_blueprints': [],
    }
    ```

- [x] 16.2 Call new extraction helpers
  - **Location**: Within `PythonExtractor.extract()` after function/class extraction
  - **Implementation**: Invoke `python_impl.extract_sqlalchemy_definitions`, `extract_django_definitions`, `extract_pydantic_validators`, and map results into `result[...]` keys.

- [x] 16.3 Transform and store framework data
  - **Location**: Same block – extend `result['python_orm_models']`, `result['python_orm_fields']`, `result['orm_relationships']`, `result['python_routes']`, `result['python_blueprints']`, `result['python_validators']`.
  - **Outcome**: Indexer writes populated payloads via `DatabaseManager`.

### 17. Testing - Framework Extraction

**Fixtures**: Create in `tests/fixtures/python/`

- [ ] 17.1 Create `sqlalchemy_app.py` - SQLAlchemy models
  - **Content**: Define 3+ models with relationships, ForeignKeys, different column types
  - **Purpose**: Test SQLAlchemy model extraction

- [ ] 17.2 Create `pydantic_app.py` - Pydantic models
  - **Content**: Define 3+ BaseModel classes with validators, Field definitions
  - **Purpose**: Test Pydantic model extraction

- [ ] 17.3 Create `flask_app.py` - Flask routes
  - **Content**: Define 5+ routes with different methods, auth decorators, blueprints
  - **Purpose**: Test Flask route extraction

- [ ] 17.4 Create `fastapi_app.py` - FastAPI routes
  - **Content**: Define 5+ routes with dependencies, path parameters, response models
  - **Purpose**: Test FastAPI route extraction

**Test Cases**: Create in `tests/test_python_framework_extraction.py`

- [ ] 17.5 Test SQLAlchemy model extraction
  - **Test**: Index sqlalchemy_app.py, query python_orm_models and python_orm_fields tables
  - **Assertions**: Models extracted, fields extracted, relationships in orm_relationships table

- [ ] 17.6 Test Pydantic model extraction
  - **Test**: Index pydantic_app.py, query python_validators table
  - **Assertions**: BaseModel classes detected, validators extracted

- [ ] 17.7 Test Flask route extraction
  - **Test**: Index flask_app.py, query python_routes table
  - **Assertions**: Routes extracted, methods correct, auth flags set, blueprints tracked

- [ ] 17.8 Test FastAPI route extraction
  - **Test**: Index fastapi_app.py, query python_routes table
  - **Assertions**: Routes extracted, dependencies tracked, response models recorded

- [ ] 17.9 Test cross-framework compatibility
  - **Test**: Index file with Flask + SQLAlchemy together
  - **Assertion**: Both extracted without conflicts

### 18. Regression Testing - Phase 2

- [ ] 18.1 Run full test suite: `pytest tests/ -v`
- [ ] 18.2 Verify Phase 1 (type annotations) still works
- [ ] 18.3 Verify no database schema conflicts
- [ ] 18.4 Performance benchmark: <15ms per file overhead

### 19. Documentation - Phase 2

- [ ] 19.1 Update CLAUDE.md with framework extraction capabilities
- [ ] 19.2 Document supported frameworks: Flask, FastAPI, SQLAlchemy, Pydantic
- [ ] 19.3 Update PARITY_AUDIT_VERIFIED.md with Phase 2 results

### 20. Code Quality - Phase 2

- [ ] 20.1 Run linting: `ruff check theauditor --fix`
- [ ] 20.2 Run formatting: `ruff format theauditor`
- [ ] 20.3 Run type checking: `mypy theauditor --strict`

### 21. OpenSpec Validation - Phase 2

- [ ] 21.1 Run `openspec validate add-python-extraction-parity --strict`
- [ ] 21.2 Verify all Phase 2 scenarios testable
- [ ] 21.3 Update tasks.md to mark Phase 2 complete

### 22. Approval & Deployment - Phase 2

- [ ] 22.1 Post-implementation audit
- [ ] 22.2 Request Architect approval for Phase 2
- [ ] 22.3 Deploy Phase 2 to production
- [ ] 22.4 Monitor post-deployment
- [ ] 22.5 Proceed to Phase 3 after approval

---

## PHASE 3: ADVANCED FEATURE PARITY

### 23. Python Import Path Resolution

**File**: `theauditor/ast_extractors/python_impl.py` (new function)

- [x] 23.1 Add `resolve_python_imports()` function
  - **Purpose**: Convert relative imports to absolute paths
  - **Example**: `from ..models import User` → resolve to `myapp.models.User`
  - **Implementation**: Use file path + import statement to calculate absolute module

- [x] 23.2 Track virtual environment packages
  - **Purpose**: Distinguish local modules from third-party packages without resolving into site-packages
  - **Detection**: Fallback to module name when filesystem lookup fails

- [x] 23.3 Build resolved_imports dict matching JavaScript format
  - **Format**: `{'User': 'myapp/models.py', 'requests': 'requests'}`
  - **Store**: In Python extractor result dict

### 24. ORM Relationship Graph Enhancement

- [x] 24.1 Enhance SQLAlchemy relationship extraction with bidirectional tracking
- [x] 24.2 Extract Django ForeignKey, ManyToMany, OneToOne relationships
- [ ] 24.3 Build relationship graph for taint analysis FK traversal
- [x] 24.4 Store in existing orm_relationships table

### 25. Testing - Phase 3

- [ ] 25.1 Create fixtures for import resolution
- [ ] 25.2 Create fixtures for ORM relationships
- [ ] 25.3 Write test cases
- [ ] 25.4 Regression testing

### 26. Documentation - Phase 3

- [ ] 26.1 Update CLAUDE.md
- [ ] 26.2 Update PARITY_AUDIT_VERIFIED.md with final results
- [ ] 26.3 Document known limitations

### 27. Final Validation

- [ ] 27.1 Run full test suite
- [ ] 27.2 OpenSpec validation
- [ ] 27.3 Request final approval
- [ ] 27.4 Deploy Phase 3

---

## COMPLETION CHECKLIST

- [ ] All 3 phases implemented
- [ ] All tests passing
- [ ] Documentation complete
- [ ] PARITY_AUDIT_VERIFIED.md updated with final metrics
- [ ] Python parity increased from 15-25% to 50-60%
- [ ] Python extraction gap reduced from 4.7x to ~2.4x
- [ ] Archive OpenSpec change after deployment
- [ ] Celebrate success

---

**Total Tasks**: 100+ discrete implementation steps
**Estimated Lines of Code**: ~1,500 lines across 3 phases
**Risk Level**: Medium (significant changes, but phased rollout mitigates risk)
**Dependencies**: None (no new external libraries)
