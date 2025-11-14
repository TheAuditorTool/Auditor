# Python Extraction Spec Deltas: Complete Language Coverage V2

This delta adds 90 missing Python pattern extraction requirements to enable comprehensive curriculum development and static analysis capabilities.

---

## MODIFIED Requirements

### Requirement: Enhanced Loop Pattern Extraction

The existing loop extraction in performance_extractors.py SHALL be enhanced with bounds detection, step tracking, and nesting depth analysis.

**Rationale**: Current loop extraction misses critical metadata needed for performance analysis and curriculum examples.

**Extraction Target**: ≥500 enhanced loop records from TheAuditor codebase.

#### Scenario: Static bounds detection

- **GIVEN** a for loop with `range(0, 10, 2)`
- **WHEN** the loop extractor runs
- **THEN** it SHALL extract bounds_min=0, bounds_max=10, bounds_step=2

#### Scenario: Nested loop depth tracking

- **GIVEN** nested loops at depth 3
- **WHEN** the loop extractor runs
- **THEN** it SHALL record nesting_level=3

#### Scenario: Loop variable tracking

- **GIVEN** a loop `for i, j in enumerate(items):`
- **WHEN** the loop extractor runs
- **THEN** it SHALL record iteration_vars=['i', 'j']

---

## ADDED Requirements

### Requirement: Comprehension Extraction

The system SHALL extract all four Python comprehension types with full metadata.

**Rationale**: Comprehensions are fundamental Python constructs missing from extraction, blocking curriculum development.

**Extraction Target**: ≥300 comprehension records from TheAuditor codebase.

#### Scenario: List comprehension with filter

- **GIVEN** a list comprehension `[x*2 for x in range(10) if x % 2 == 0]`
- **WHEN** extract_comprehensions runs
- **THEN** it SHALL create python_comprehensions record with comp_type='list', has_filter=true, filter_expr='x % 2 == 0'

#### Scenario: Dictionary comprehension

- **GIVEN** a dict comprehension `{k: v*2 for k, v in items.items()}`
- **WHEN** extract_comprehensions runs
- **THEN** it SHALL record comp_type='dict', result_expr='{k: v*2}'

#### Scenario: Set comprehension

- **GIVEN** a set comprehension `{x for x in numbers if x > 0}`
- **WHEN** extract_comprehensions runs
- **THEN** it SHALL record comp_type='set'

#### Scenario: Generator expression

- **GIVEN** a generator expression `(x for x in data)`
- **WHEN** extract_comprehensions runs
- **THEN** it SHALL record comp_type='generator'

#### Scenario: Nested comprehension tracking

- **GIVEN** `[[x*y for y in row] for row in matrix]`
- **WHEN** extract_comprehensions runs
- **THEN** it SHALL record nesting_level=2 for outer, nesting_level=1 for inner

---

### Requirement: Lambda Function Extraction

The system SHALL extract lambda functions with parameter analysis and closure detection.

**Rationale**: Lambda functions are widely used but untracked, limiting functional programming curriculum.

**Extraction Target**: ≥200 lambda function records from TheAuditor codebase.

#### Scenario: Simple lambda

- **GIVEN** `lambda x: x + 1`
- **WHEN** extract_lambda_functions runs
- **THEN** it SHALL record parameters=['x'], body='x + 1'

#### Scenario: Lambda with closure

- **GIVEN** `multiplier = 5; func = lambda x: x * multiplier`
- **WHEN** extract_lambda_functions runs
- **THEN** it SHALL record captures_closure=true, captured_vars=['multiplier']

#### Scenario: Lambda in map context

- **GIVEN** `map(lambda x: x*2, items)`
- **WHEN** extract_lambda_functions runs
- **THEN** it SHALL record used_in='map'

#### Scenario: Lambda as key function

- **GIVEN** `sorted(items, key=lambda x: x[1])`
- **WHEN** extract_lambda_functions runs
- **THEN** it SHALL record used_in='sorted_key'

---

### Requirement: Slice Operation Extraction

The system SHALL extract slice operations with complete parameter tracking.

**Rationale**: Slice operations are fundamental to sequence manipulation but completely untracked.

**Extraction Target**: ≥150 slice operation records from TheAuditor codebase.

#### Scenario: Full slice parameters

- **GIVEN** `list[1:10:2]`
- **WHEN** extract_slice_operations runs
- **THEN** it SHALL record start=1, stop=10, step=2

#### Scenario: Partial slice

- **GIVEN** `list[:5]`
- **WHEN** extract_slice_operations runs
- **THEN** it SHALL record start=None, stop=5, step=None

#### Scenario: Negative indexing

- **GIVEN** `list[-3:-1]`
- **WHEN** extract_slice_operations runs
- **THEN** it SHALL record start=-3, stop=-1

#### Scenario: Slice assignment

- **GIVEN** `list[0:5] = [1, 2, 3]`
- **WHEN** extract_slice_operations runs
- **THEN** it SHALL record is_assignment=true

---

### Requirement: Tuple Operations Extraction

The system SHALL extract tuple packing, unpacking, and literal operations.

**Rationale**: Tuple operations including unpacking patterns are untracked, limiting sequence manipulation curriculum.

**Extraction Target**: ≥200 tuple operation records from TheAuditor codebase.

#### Scenario: Tuple packing

- **GIVEN** `coords = (x, y, z)`
- **WHEN** extract_tuple_operations runs
- **THEN** it SHALL record operation='pack', elements=['x', 'y', 'z']

#### Scenario: Tuple unpacking

- **GIVEN** `a, b, c = (1, 2, 3)`
- **WHEN** extract_tuple_operations runs
- **THEN** it SHALL record operation='unpack', target_vars=['a', 'b', 'c']

#### Scenario: Extended unpacking

- **GIVEN** `a, *rest, b = [1, 2, 3, 4, 5]`
- **WHEN** extract_unpacking_patterns runs
- **THEN** it SHALL record has_rest=true, rest_var='rest'

#### Scenario: Nested unpacking

- **GIVEN** `(a, (b, c)) = (1, (2, 3))`
- **WHEN** extract_unpacking_patterns runs
- **THEN** it SHALL record unpack_type='nested'

#### Scenario: Argument unpacking

- **GIVEN** `func(*args, **kwargs)`
- **WHEN** extract_unpacking_patterns runs
- **THEN** it SHALL record unpack_type='both', args_var='args', kwargs_var='kwargs'

---

### Requirement: None Pattern Extraction

The system SHALL extract None handling patterns with correctness checking.

**Rationale**: None handling is a common source of bugs; tracking patterns enables quality analysis.

**Extraction Target**: ≥300 None pattern records from TheAuditor codebase.

#### Scenario: Correct None check

- **GIVEN** `if x is None:`
- **WHEN** extract_none_patterns runs
- **THEN** it SHALL record pattern='is_none_check', uses_is=true

#### Scenario: Incorrect None comparison

- **GIVEN** `if x == None:`
- **WHEN** extract_none_patterns runs
- **THEN** it SHALL record pattern='is_none_check', uses_is=false

#### Scenario: None as default

- **GIVEN** `def foo(x=None):`
- **WHEN** extract_none_patterns runs
- **THEN** it SHALL record pattern='none_default'

#### Scenario: None return

- **GIVEN** `return None`
- **WHEN** extract_none_patterns runs
- **THEN** it SHALL record pattern='none_return'

---

### Requirement: Truthiness Pattern Extraction

The system SHALL extract implicit and explicit boolean coercion patterns.

**Rationale**: Understanding truthiness patterns is critical for Python idiom curriculum.

**Extraction Target**: ≥250 truthiness pattern records from TheAuditor codebase.

#### Scenario: Implicit bool check

- **GIVEN** `if my_list:`
- **WHEN** extract_truthiness_patterns runs
- **THEN** it SHALL record pattern='implicit_bool', expression='my_list'

#### Scenario: Explicit bool conversion

- **GIVEN** `bool(x)`
- **WHEN** extract_truthiness_patterns runs
- **THEN** it SHALL record pattern='explicit_bool'

#### Scenario: Short-circuit evaluation

- **GIVEN** `result = x and y`
- **WHEN** extract_truthiness_patterns runs
- **THEN** it SHALL record pattern='short_circuit', expression='x and y'

#### Scenario: Falsy value detection

- **GIVEN** `if not []:`
- **WHEN** extract_truthiness_patterns runs
- **THEN** it SHALL record falsy_values=['[]']

---

### Requirement: String Formatting Extraction

The system SHALL extract all string formatting methods with expression analysis.

**Rationale**: String formatting is evolving; tracking all methods enables modern Python curriculum.

**Extraction Target**: ≥400 string formatting records from TheAuditor codebase.

#### Scenario: F-string with expression

- **GIVEN** `f"{name.upper():^20}"`
- **WHEN** extract_string_formatting runs
- **THEN** it SHALL record format_type='f_string', has_expressions=true, format_specs=['^20']

#### Scenario: Percent formatting

- **GIVEN** `"Hello %s, you are %d" % (name, age)`
- **WHEN** extract_string_formatting runs
- **THEN** it SHALL record format_type='percent'

#### Scenario: Format method

- **GIVEN** `"Hello {}, you are {}".format(name, age)`
- **WHEN** extract_string_formatting runs
- **THEN** it SHALL record format_type='format_method'

#### Scenario: Template strings

- **GIVEN** `Template("Hello $name").substitute(name=user)`
- **WHEN** extract_string_formatting runs
- **THEN** it SHALL record format_type='template'

---

### Requirement: Operator Extraction

The system SHALL extract all operator types with operand analysis.

**Rationale**: Operator usage is completely untracked, blocking expression analysis curriculum.

**Extraction Target**: ≥1,000 operator records from TheAuditor codebase.

#### Scenario: Arithmetic operators

- **GIVEN** `a + b * c ** 2`
- **WHEN** extract_operators runs
- **THEN** it SHALL create records for Add, Mult, Pow with operator_type='arithmetic'

#### Scenario: Comparison operators

- **GIVEN** `x > 5 and y <= 10`
- **WHEN** extract_operators runs
- **THEN** it SHALL record operator_type='comparison' for >, <=

#### Scenario: Logical operators

- **GIVEN** `a and b or not c`
- **WHEN** extract_operators runs
- **THEN** it SHALL record operator_type='logical' for and, or, not

#### Scenario: Bitwise operators

- **GIVEN** `flags & mask | other`
- **WHEN** extract_operators runs
- **THEN** it SHALL record operator_type='bitwise' for &, |

#### Scenario: Identity operators

- **GIVEN** `x is not None`
- **WHEN** extract_operators runs
- **THEN** it SHALL record operator_type='identity' for 'is not'

---

### Requirement: Membership Testing Extraction

The system SHALL extract membership tests with container type detection.

**Rationale**: Membership testing is fundamental but untracked.

**Extraction Target**: ≥200 membership test records from TheAuditor codebase.

#### Scenario: List membership

- **GIVEN** `if item in my_list:`
- **WHEN** extract_membership_tests runs
- **THEN** it SHALL record operator='in', container_type='list'

#### Scenario: Dict membership

- **GIVEN** `if key not in my_dict:`
- **WHEN** extract_membership_tests runs
- **THEN** it SHALL record operator='not in', container_type='dict'

#### Scenario: String membership

- **GIVEN** `if "sub" in string:`
- **WHEN** extract_membership_tests runs
- **THEN** it SHALL record operator='in', container_type='str'

---

### Requirement: Chained Comparison Extraction

The system SHALL extract chained comparisons with full operator chain.

**Rationale**: Chained comparisons are Python-specific and untracked.

**Extraction Target**: ≥50 chained comparison records from TheAuditor codebase.

#### Scenario: Simple chain

- **GIVEN** `1 < x < 10`
- **WHEN** extract_chained_comparisons runs
- **THEN** it SHALL record operators=['<', '<'], operands=['1', 'x', '10']

#### Scenario: Complex chain

- **GIVEN** `a <= b < c != d`
- **WHEN** extract_chained_comparisons runs
- **THEN** it SHALL record chain_length=4

---

### Requirement: Ternary Expression Extraction

The system SHALL extract ternary conditional expressions.

**Rationale**: Ternary expressions are common but untracked.

**Extraction Target**: ≥100 ternary expression records from TheAuditor codebase.

#### Scenario: Simple ternary

- **GIVEN** `result = x if condition else y`
- **WHEN** extract_ternary_expressions runs
- **THEN** it SHALL record true_value='x', condition='condition', false_value='y'

#### Scenario: Nested ternary

- **GIVEN** `a if b else c if d else e`
- **WHEN** extract_ternary_expressions runs
- **THEN** it SHALL record nested=true

---

### Requirement: Walrus Operator Extraction

The system SHALL extract assignment expressions (walrus operator).

**Rationale**: Python 3.8+ walrus operator needs tracking for modern Python curriculum.

**Extraction Target**: ≥30 walrus operator records from TheAuditor codebase.

#### Scenario: Walrus in if condition

- **GIVEN** `if (n := len(items)) > 0:`
- **WHEN** extract_walrus_operators runs
- **THEN** it SHALL record variable='n', expression='len(items)', used_in='if'

#### Scenario: Walrus in while

- **GIVEN** `while (line := file.readline()):`
- **WHEN** extract_walrus_operators runs
- **THEN** it SHALL record used_in='while', avoids_double_computation=true

#### Scenario: Walrus in comprehension

- **GIVEN** `[y for x in data if (y := f(x)) > 0]`
- **WHEN** extract_walrus_operators runs
- **THEN** it SHALL record used_in='comprehension'

---

### Requirement: Matrix Multiplication Extraction

The system SHALL extract @ matrix multiplication operator.

**Rationale**: Matrix multiplication operator needs tracking for numerical computing curriculum.

**Extraction Target**: ≥10 matrix multiplication records from TheAuditor codebase.

#### Scenario: Matrix multiply

- **GIVEN** `C = A @ B`
- **WHEN** extract_matrix_multiplication runs
- **THEN** it SHALL record left='A', right='B', operator='@'

---

### Requirement: Dictionary Operation Extraction

The system SHALL extract dictionary method calls and operations.

**Rationale**: Dictionary operations are fundamental but only mutations are tracked.

**Extraction Target**: ≥500 dictionary operation records from TheAuditor codebase.

#### Scenario: Dict iteration methods

- **GIVEN** `for k, v in my_dict.items():`
- **WHEN** extract_dict_operations runs
- **THEN** it SHALL record operation='items', is_iteration=true

#### Scenario: Dict get with default

- **GIVEN** `value = config.get('key', 'default')`
- **WHEN** extract_dict_operations runs
- **THEN** it SHALL record operation='get', has_default=true

#### Scenario: Dict update

- **GIVEN** `dict1.update(dict2)`
- **WHEN** extract_dict_operations runs
- **THEN** it SHALL record operation='update'

#### Scenario: Dict unpacking

- **GIVEN** `{**dict1, **dict2, 'key': 'value'}`
- **WHEN** extract_dict_operations runs
- **THEN** it SHALL record unpacked_dicts=['dict1', 'dict2']

---

### Requirement: List Method Extraction

The system SHALL extract list methods distinguishing mutations.

**Rationale**: List methods need comprehensive tracking beyond current mutation-only extraction.

**Extraction Target**: ≥600 list method records from TheAuditor codebase.

#### Scenario: In-place mutation

- **GIVEN** `my_list.sort(reverse=True)`
- **WHEN** extract_list_mutations runs
- **THEN** it SHALL record method='sort', mutates_in_place=true

#### Scenario: Non-mutating operation

- **GIVEN** `new_list = sorted(old_list)`
- **WHEN** extract_list_mutations runs
- **THEN** it SHALL record mutates_in_place=false

#### Scenario: List append

- **GIVEN** `items.append(x)`
- **WHEN** extract_list_mutations runs
- **THEN** it SHALL record method='append', returns=None

#### Scenario: List pop

- **GIVEN** `last = items.pop()`
- **WHEN** extract_list_mutations runs
- **THEN** it SHALL record method='pop', returns='element'

---

### Requirement: Set Operation Extraction

The system SHALL extract set operations and methods.

**Rationale**: Set operations are mathematical fundamentals but completely untracked.

**Extraction Target**: ≥100 set operation records from TheAuditor codebase.

#### Scenario: Set operators

- **GIVEN** `result = set1 | set2 & set3`
- **WHEN** extract_set_operations runs
- **THEN** it SHALL record operations for union (|) and intersection (&)

#### Scenario: Set methods

- **GIVEN** `set1.intersection(set2)`
- **WHEN** extract_set_operations runs
- **THEN** it SHALL record operation='intersection', method_used=true

#### Scenario: Set difference

- **GIVEN** `diff = set1 - set2`
- **WHEN** extract_set_operations runs
- **THEN** it SHALL record operation='difference', operator='-'

---

### Requirement: String Method Extraction

The system SHALL extract string method calls with semantic analysis.

**Rationale**: String methods are fundamental but completely untracked.

**Extraction Target**: ≥800 string method records from TheAuditor codebase.

#### Scenario: String split

- **GIVEN** `parts = text.split(',')`
- **WHEN** extract_string_methods runs
- **THEN** it SHALL record method='split', returns='list'

#### Scenario: String join

- **GIVEN** `result = ', '.join(items)`
- **WHEN** extract_string_methods runs
- **THEN** it SHALL record method='join', returns='str'

#### Scenario: Method chaining

- **GIVEN** `clean = text.strip().lower().replace(' ', '_')`
- **WHEN** extract_string_methods runs
- **THEN** it SHALL record method_chain=['strip', 'lower', 'replace']

---

### Requirement: Builtin Function Extraction

The system SHALL extract usage of Python builtin functions.

**Rationale**: Builtin function usage is completely untracked, blocking idiom curriculum.

**Extraction Target**: ≥1,000 builtin function records from TheAuditor codebase.

#### Scenario: Sorted with key

- **GIVEN** `sorted(students, key=lambda s: s.grade, reverse=True)`
- **WHEN** extract_builtin_usage runs
- **THEN** it SHALL record builtin='sorted', has_key=true, has_reverse=true

#### Scenario: Enumerate usage

- **GIVEN** `for i, item in enumerate(items, start=1):`
- **WHEN** extract_builtin_usage runs
- **THEN** it SHALL record builtin='enumerate', has_start=true

#### Scenario: Zip usage

- **GIVEN** `for x, y in zip(list1, list2):`
- **WHEN** extract_builtin_usage runs
- **THEN** it SHALL record builtin='zip', num_iterables=2

#### Scenario: Map/Filter

- **GIVEN** `result = map(str.upper, filter(None, items))`
- **WHEN** extract_builtin_usage runs
- **THEN** it SHALL record builtins=['map', 'filter']

---

### Requirement: Itertools Pattern Extraction

The system SHALL extract itertools module usage patterns.

**Rationale**: Itertools patterns are advanced Python but untracked.

**Extraction Target**: ≥50 itertools pattern records from TheAuditor codebase.

#### Scenario: Infinite iterators

- **GIVEN** `itertools.cycle([1, 2, 3])`
- **WHEN** extract_itertools_usage runs
- **THEN** it SHALL record function='cycle', is_infinite=true

#### Scenario: Combinations

- **GIVEN** `itertools.combinations(items, 2)`
- **WHEN** extract_itertools_usage runs
- **THEN** it SHALL record function='combinations', r=2

#### Scenario: Chain usage

- **GIVEN** `itertools.chain(list1, list2, list3)`
- **WHEN** extract_itertools_usage runs
- **THEN** it SHALL record function='chain', num_iterables=3

---

### Requirement: Functools Pattern Extraction

The system SHALL extract functools module usage patterns.

**Rationale**: Functools patterns enable functional programming curriculum.

**Extraction Target**: ≥30 functools pattern records from TheAuditor codebase.

#### Scenario: Partial application

- **GIVEN** `add5 = functools.partial(add, 5)`
- **WHEN** extract_functools_usage runs
- **THEN** it SHALL record function='partial', partial_args=['5']

#### Scenario: LRU cache

- **GIVEN** `@functools.lru_cache(maxsize=128)`
- **WHEN** extract_functools_usage runs
- **THEN** it SHALL record function='lru_cache', is_decorator=true, maxsize=128

#### Scenario: Reduce usage

- **GIVEN** `functools.reduce(operator.add, numbers)`
- **WHEN** extract_functools_usage runs
- **THEN** it SHALL record function='reduce', func='operator.add'

---

### Requirement: Collections Module Extraction

The system SHALL extract collections module usage.

**Rationale**: Collections module provides essential data structures but is untracked.

**Extraction Target**: ≥100 collections module records from TheAuditor codebase.

#### Scenario: defaultdict usage

- **GIVEN** `counts = defaultdict(int)`
- **WHEN** extract_collections_usage runs
- **THEN** it SHALL record collection_type='defaultdict', default_factory='int'

#### Scenario: Counter usage

- **GIVEN** `freq = Counter(words)`
- **WHEN** extract_collections_usage runs
- **THEN** it SHALL record collection_type='Counter'

#### Scenario: namedtuple

- **GIVEN** `Point = namedtuple('Point', ['x', 'y'])`
- **WHEN** extract_collections_usage runs
- **THEN** it SHALL record collection_type='namedtuple', fields=['x', 'y']

---

### Requirement: Metaclass Extraction

The system SHALL extract metaclass usage and methods.

**Rationale**: Metaclasses are advanced Python features needing tracking.

**Extraction Target**: ≥10 metaclass records from TheAuditor codebase.

#### Scenario: Basic metaclass

- **GIVEN** `class MyClass(metaclass=MyMeta):`
- **WHEN** extract_metaclasses runs
- **THEN** it SHALL record class_name='MyClass', metaclass='MyMeta'

#### Scenario: ABCMeta usage

- **GIVEN** `class Interface(metaclass=ABCMeta):`
- **WHEN** extract_metaclasses runs
- **THEN** it SHALL record metaclass='ABCMeta', is_abstract=true

---

### Requirement: Descriptor Protocol Extraction

The system SHALL extract descriptor implementations.

**Rationale**: Descriptors are Python internals needing documentation.

**Extraction Target**: ≥5 descriptor records from TheAuditor codebase.

#### Scenario: Data descriptor

- **GIVEN** a class with `__get__`, `__set__`, `__delete__`
- **WHEN** extract_descriptors runs
- **THEN** it SHALL record is_data_descriptor=true

#### Scenario: Non-data descriptor

- **GIVEN** a class with only `__get__`
- **WHEN** extract_descriptors runs
- **THEN** it SHALL record is_data_descriptor=false

---

### Requirement: Dataclass Extraction

The system SHALL extract dataclass definitions and configuration.

**Rationale**: Dataclasses are modern Python requiring tracking.

**Extraction Target**: ≥20 dataclass records from TheAuditor codebase.

#### Scenario: Frozen dataclass

- **GIVEN** `@dataclass(frozen=True, order=True)`
- **WHEN** extract_dataclasses runs
- **THEN** it SHALL record frozen=true, order=true

#### Scenario: Dataclass fields

- **GIVEN** fields with type hints and defaults
- **WHEN** extract_dataclasses runs
- **THEN** it SHALL extract field metadata including types and defaults

#### Scenario: Auto-generated methods

- **GIVEN** a standard dataclass
- **WHEN** extract_dataclasses runs
- **THEN** it SHALL record auto_generated=['__init__', '__repr__', '__eq__']

---

### Requirement: Enum Extraction

The system SHALL extract enum definitions and members.

**Rationale**: Enums provide type safety but are untracked.

**Extraction Target**: ≥30 enum records from TheAuditor codebase.

#### Scenario: Basic enum

- **GIVEN** `class Color(Enum): RED = 1`
- **WHEN** extract_enums runs
- **THEN** it SHALL record enum_type='Enum', members=[{'name': 'RED', 'value': 1}]

#### Scenario: IntEnum

- **GIVEN** `class Status(IntEnum):`
- **WHEN** extract_enums runs
- **THEN** it SHALL record enum_type='IntEnum'

#### Scenario: Flag enum

- **GIVEN** `class Permission(Flag):`
- **WHEN** extract_enums runs
- **THEN** it SHALL record enum_type='Flag', supports_bitwise=true

---

### Requirement: Slots Extraction

The system SHALL extract __slots__ usage.

**Rationale**: Slots optimize memory but need tracking for patterns.

**Extraction Target**: ≥10 slots records from TheAuditor codebase.

#### Scenario: Slots definition

- **GIVEN** `__slots__ = ['x', 'y', 'z']`
- **WHEN** extract_slots runs
- **THEN** it SHALL record slots=['x', 'y', 'z'], restricts_attrs=true

---

### Requirement: Abstract Base Class Extraction

The system SHALL extract ABC usage and abstract methods.

**Rationale**: ABCs define interfaces but are untracked.

**Extraction Target**: ≥15 ABC records from TheAuditor codebase.

#### Scenario: Abstract method

- **GIVEN** `@abstractmethod def process(self):`
- **WHEN** extract_abstract_classes runs
- **THEN** it SHALL record abstract_methods=['process']

#### Scenario: ABC inheritance

- **GIVEN** `class Base(ABC):`
- **WHEN** extract_abstract_classes runs
- **THEN** it SHALL record inherits_from='ABC'

---

### Requirement: Multiple Inheritance Extraction

The system SHALL extract multiple inheritance patterns and MRO.

**Rationale**: Multiple inheritance complexity needs documentation.

**Extraction Target**: ≥20 multiple inheritance records from TheAuditor codebase.

#### Scenario: Diamond inheritance

- **GIVEN** classes forming diamond pattern
- **WHEN** extract_multiple_inheritance runs
- **THEN** it SHALL record diamond_problem=true

#### Scenario: MRO calculation

- **GIVEN** `class D(B, C):`
- **WHEN** extract_multiple_inheritance runs
- **THEN** it SHALL calculate and record method resolution order

---

### Requirement: Dunder Method Extraction

The system SHALL categorize dunder methods by protocol.

**Rationale**: Dunder methods define object behavior but lack categorization.

**Extraction Target**: ≥200 dunder method records from TheAuditor codebase.

#### Scenario: Context manager protocol

- **GIVEN** `__enter__` and `__exit__` methods
- **WHEN** extract_dunder_methods runs
- **THEN** it SHALL record category='context_manager'

#### Scenario: Iterator protocol

- **GIVEN** `__iter__` and `__next__` methods
- **WHEN** extract_dunder_methods runs
- **THEN** it SHALL record category='iteration'

#### Scenario: Comparison protocol

- **GIVEN** `__eq__`, `__lt__`, etc.
- **WHEN** extract_dunder_methods runs
- **THEN** it SHALL record category='comparison'

---

### Requirement: Method Type Extraction

The system SHALL distinguish method types.

**Rationale**: Method types affect calling patterns but are untracked.

**Extraction Target**: ≥500 method type records from TheAuditor codebase.

#### Scenario: Class method

- **GIVEN** `@classmethod def from_string(cls, s):`
- **WHEN** extract_method_types runs
- **THEN** it SHALL record method_type='class', first_param='cls'

#### Scenario: Static method

- **GIVEN** `@staticmethod def validate(value):`
- **WHEN** extract_method_types runs
- **THEN** it SHALL record method_type='static'

#### Scenario: Instance method

- **GIVEN** `def process(self, data):`
- **WHEN** extract_method_types runs
- **THEN** it SHALL record method_type='instance', first_param='self'

---

### Requirement: Visibility Convention Extraction

The system SHALL extract Python naming conventions.

**Rationale**: Naming conventions indicate privacy but are untracked.

**Extraction Target**: ≥300 visibility convention records from TheAuditor codebase.

#### Scenario: Single underscore

- **GIVEN** `_internal_method`
- **WHEN** extract_visibility_conventions runs
- **THEN** it SHALL record visibility='protected', pattern='_single'

#### Scenario: Name mangling

- **GIVEN** `__private_attr`
- **WHEN** extract_visibility_conventions runs
- **THEN** it SHALL record visibility='name_mangled', pattern='__double'

#### Scenario: Magic methods

- **GIVEN** `__init__`
- **WHEN** extract_visibility_conventions runs
- **THEN** it SHALL record visibility='public', pattern='__double_trailing__'

---

### Requirement: Regex Pattern Extraction

The system SHALL extract regular expression usage.

**Rationale**: Regex patterns need tracking for security and complexity analysis.

**Extraction Target**: ≥100 regex pattern records from TheAuditor codebase.

#### Scenario: Compiled regex

- **GIVEN** `pattern = re.compile(r'\d+', re.IGNORECASE)`
- **WHEN** extract_regex_patterns runs
- **THEN** it SHALL record operation='compile', flags=['IGNORECASE']

#### Scenario: Regex groups

- **GIVEN** `re.search(r'(\w+):(\d+)', text)`
- **WHEN** extract_regex_patterns runs
- **THEN** it SHALL record has_groups=true, group_count=2

#### Scenario: Substitution

- **GIVEN** `re.sub(r'\s+', ' ', text)`
- **WHEN** extract_regex_patterns runs
- **THEN** it SHALL record operation='sub', pattern=r'\s+', replacement=' '

---

### Requirement: JSON Operation Extraction

The system SHALL extract JSON handling patterns.

**Rationale**: JSON operations need tracking for API analysis.

**Extraction Target**: ≥150 JSON operation records from TheAuditor codebase.

#### Scenario: Custom encoder

- **GIVEN** `json.dumps(obj, cls=CustomEncoder)`
- **WHEN** extract_json_operations runs
- **THEN** it SHALL record has_custom_encoder=true, encoder_class='CustomEncoder'

#### Scenario: Indentation

- **GIVEN** `json.dumps(data, indent=2)`
- **WHEN** extract_json_operations runs
- **THEN** it SHALL record indent=2, pretty_print=true

---

### Requirement: Datetime Operation Extraction

The system SHALL extract datetime operations.

**Rationale**: Datetime handling patterns need documentation.

**Extraction Target**: ≥100 datetime operation records from TheAuditor codebase.

#### Scenario: Formatting

- **GIVEN** `date.strftime('%Y-%m-%d %H:%M:%S')`
- **WHEN** extract_datetime_operations runs
- **THEN** it SHALL record operation='strftime', format_string='%Y-%m-%d %H:%M:%S'

#### Scenario: Parsing

- **GIVEN** `datetime.strptime(date_str, '%Y-%m-%d')`
- **WHEN** extract_datetime_operations runs
- **THEN** it SHALL record operation='strptime', format_string='%Y-%m-%d'

#### Scenario: Timedelta

- **GIVEN** `datetime.now() + timedelta(days=7)`
- **WHEN** extract_datetime_operations runs
- **THEN** it SHALL record operation='timedelta', days=7

---

### Requirement: Path Operation Extraction

The system SHALL extract pathlib usage patterns.

**Rationale**: Modern path handling needs tracking vs os.path.

**Extraction Target**: ≥200 path operation records from TheAuditor codebase.

#### Scenario: Pathlib usage

- **GIVEN** `Path('file.txt').read_text()`
- **WHEN** extract_path_operations runs
- **THEN** it SHALL record uses_pathlib=true, operation='read_text'

#### Scenario: Path components

- **GIVEN** `path.parent.stem`
- **WHEN** extract_path_operations runs
- **THEN** it SHALL record path_components=['parent', 'stem']

---

### Requirement: Logging Pattern Extraction

The system SHALL extract logging patterns.

**Rationale**: Logging patterns indicate debugging and monitoring strategies.

**Extraction Target**: ≥300 logging pattern records from TheAuditor codebase.

#### Scenario: Log level

- **GIVEN** `logger.error('Failed: %s', error)`
- **WHEN** extract_logging_patterns runs
- **THEN** it SHALL record log_level='ERROR', uses_lazy_formatting=true

#### Scenario: F-string anti-pattern

- **GIVEN** `logger.info(f'User {user} logged in')`
- **WHEN** extract_logging_patterns runs
- **THEN** it SHALL record uses_lazy_formatting=false, anti_pattern=true

---

### Requirement: Threading Pattern Extraction

The system SHALL extract threading and multiprocessing patterns.

**Rationale**: Concurrency patterns need tracking for correctness analysis.

**Extraction Target**: ≥50 threading pattern records from TheAuditor codebase.

#### Scenario: Thread creation

- **GIVEN** `Thread(target=worker, daemon=True)`
- **WHEN** extract_threading_patterns runs
- **THEN** it SHALL record pattern='Thread', is_daemon=true

#### Scenario: Thread pool

- **GIVEN** `ThreadPoolExecutor(max_workers=5)`
- **WHEN** extract_threading_patterns runs
- **THEN** it SHALL record pattern='ThreadPoolExecutor', pool_size=5

#### Scenario: Lock usage

- **GIVEN** `with lock:`
- **WHEN** extract_threading_patterns runs
- **THEN** it SHALL record pattern='Lock', context_manager=true

---

### Requirement: CSV Operation Extraction

The system SHALL extract CSV operations.

**Rationale**: CSV handling patterns need documentation.

**Extraction Target**: ≥30 CSV operation records from TheAuditor codebase.

#### Scenario: DictReader

- **GIVEN** `csv.DictReader(file, delimiter=';')`
- **WHEN** extract_csv_operations runs
- **THEN** it SHALL record operation='DictReader', delimiter=';'

#### Scenario: CSV writer

- **GIVEN** `csv.writer(file).writerow(data)`
- **WHEN** extract_csv_operations runs
- **THEN** it SHALL record operation='writer', method='writerow'

---

### Requirement: Performance Requirements

The system SHALL maintain extraction performance within acceptable bounds.

**Rationale**: Adding 90 extractors must not degrade performance beyond acceptable limits.

**Extraction Target**: Performance metrics maintained.

#### Scenario: Small file performance

- **GIVEN** a Python file with <100 lines of code
- **WHEN** all 90 extractors run
- **THEN** extraction SHALL complete in <6ms

#### Scenario: Medium file performance

- **GIVEN** a Python file with 100-500 lines
- **WHEN** all 90 extractors run
- **THEN** extraction SHALL complete in <12ms

#### Scenario: Large file performance

- **GIVEN** a Python file with >500 lines
- **WHEN** all 90 extractors run
- **THEN** extraction SHALL complete in <60ms

---

### Requirement: Memory Constraints

The system SHALL operate within memory limits.

**Rationale**: Memory efficiency is critical for large codebases.

**Extraction Target**: Memory limits enforced.

#### Scenario: Per-file memory limit

- **GIVEN** any Python file
- **WHEN** extraction runs
- **THEN** memory usage SHALL not exceed 10MB

#### Scenario: Result truncation

- **GIVEN** extraction results exceeding 1000 items per pattern
- **WHEN** storing results
- **THEN** the system SHALL truncate to 1000 items

---

### Requirement: Single-Pass AST Walking

The system SHALL use efficient AST traversal.

**Rationale**: Single-pass walking is critical for performance.

**Extraction Target**: Single traversal verified.

#### Scenario: Single traversal

- **GIVEN** multiple extractors for a file
- **WHEN** processing the file
- **THEN** the AST SHALL be walked exactly once

#### Scenario: Dispatch efficiency

- **GIVEN** node type dispatch
- **WHEN** processing nodes
- **THEN** dispatch SHALL use O(1) dictionary lookup

---

## REMOVED Requirements

None - This is purely additive work.

---

## RENAMED Requirements

None - No existing requirements are being renamed.