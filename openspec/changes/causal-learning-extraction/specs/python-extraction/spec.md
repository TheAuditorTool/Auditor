# Python Extraction Spec Deltas: Causal Learning Foundation

This delta adds behavioral pattern extraction requirements to enable hypothesis generation and experimental validation for the DIEC causal learning tool.

---

## ADDED Requirements

### Requirement: State Mutation Detection

The system SHALL extract all state mutation patterns including instance attributes, class attributes, global variables, and mutable argument modifications.

**Rationale**: Side effects are the primary patterns that static analysis cannot prove but experimentation can validate. Detecting state mutations enables the generation of testable hypotheses about function behavior (e.g., "This function modifies instance attribute X").

**Extraction Target**: ≥3,000 state mutation records from TheAuditor codebase.

#### Scenario: Instance attribute mutation detected

- **GIVEN** a Python file containing `class Counter` with method `increment(self): self.count += 1`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an instance mutation record with:
  - `target`: "self.count"
  - `operation`: "augmented_assignment"
  - `in_function`: "increment"
  - `is_init`: False (not in `__init__`)

#### Scenario: Constructor initialization distinguished from side effects

- **GIVEN** a Python file with `__init__(self): self.count = 0`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an instance mutation with `is_init`: True to distinguish expected initialization from unexpected side effects

#### Scenario: Class attribute mutation detected

- **GIVEN** a Python file with `Counter.instances += 1`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a class mutation record with `class_name`: "Counter" and `attribute`: "instances"

#### Scenario: Global variable mutation detected

- **GIVEN** a Python file with `global _cache; _cache[key] = value`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a global mutation record with `global_name`: "_cache"

#### Scenario: Mutable argument modification detected

- **GIVEN** a Python file with `def modify(lst): lst.append(x)`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an argument mutation record with `parameter_name`: "lst" and `mutation_type`: "append"

---

### Requirement: Exception Flow Tracking

The system SHALL extract exception control flow patterns including raise statements, exception handlers, finally blocks, and context managers.

**Rationale**: Error handling is fundamental to robustness. Understanding exception flows enables hypothesis generation about function reliability and error propagation (e.g., "Function X raises ValueError when input is negative").

**Extraction Target**: ≥2,000 exception flow records from TheAuditor codebase.

#### Scenario: Exception raise with message extracted

- **GIVEN** a Python file with `raise ValueError("Invalid input")`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an exception raise record with:
  - `exception_type`: "ValueError"
  - `message`: "Invalid input"
  - `is_re_raise`: False

#### Scenario: Conditional exception raise detected

- **GIVEN** a Python file with `if x < 0: raise ValueError("Negative")`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an exception raise with `condition`: "if x < 0"

#### Scenario: Exception handler strategy classified

- **GIVEN** a Python file with `except ValueError: return None`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an exception catch with `handling_strategy`: "return_none"

#### Scenario: Finally block cleanup tracked

- **GIVEN** a Python file with `finally: lock.release()`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a finally block record with `cleanup_calls`: "lock.release"

#### Scenario: Context manager resource cleanup detected

- **GIVEN** a Python file with `with open(file) as f: f.write(data)`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a context manager record with `context_expr`: "open(file)"

---

### Requirement: I/O Operation Detection

The system SHALL extract all I/O operations that interact with external systems including file operations, database transactions, network calls, process spawning, and environment variable modifications.

**Rationale**: External interactions are invisible to static analysis. Detecting I/O operations enables hypothesis generation about function side effects on external systems (e.g., "Function X writes to filesystem").

**Extraction Target**: ≥2,000 I/O operation records from TheAuditor codebase.

#### Scenario: File write operation detected

- **GIVEN** a Python file with `with open('log.txt', 'w') as f: f.write(data)`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with:
  - `io_type`: "FILE_WRITE"
  - `operation`: "open"
  - `target`: "log.txt"
  - `is_static`: True

#### Scenario: Database commit operation detected

- **GIVEN** a Python file with `db.session.commit()`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with `io_type`: "DB_COMMIT"

#### Scenario: Network request detected

- **GIVEN** a Python file with `requests.post(url, data=payload)`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with `io_type`: "NETWORK"

#### Scenario: Process spawning detected

- **GIVEN** a Python file with `subprocess.run(['ls', '-la'])`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with `io_type`: "PROCESS"

#### Scenario: Environment variable modification detected

- **GIVEN** a Python file with `os.environ['KEY'] = 'value'`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with `io_type`: "ENV_MODIFY"

#### Scenario: Dynamic I/O target flagged

- **GIVEN** a Python file with `filename = get_config(); open(filename, 'w')`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract an I/O operation with `is_static`: False and `target`: None

---

### Requirement: Data Flow Analysis

The system SHALL extract data flow patterns including parameter-to-return flows, closure captures, and nonlocal variable access.

**Rationale**: Understanding how data moves through code enables taint analysis and security hypothesis generation (e.g., "Function X returns transformed parameter Y").

**Extraction Target**: ≥1,850 data flow records from TheAuditor codebase.

#### Scenario: Direct parameter return flow

- **GIVEN** a Python file with `def identity(x): return x`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a parameter flow with:
  - `function_name`: "identity"
  - `parameter_name`: "x"
  - `flow_type`: "direct"

#### Scenario: Transformed parameter return flow

- **GIVEN** a Python file with `def double(x): return x * 2`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a parameter flow with `flow_type`: "transformed"

#### Scenario: Closure variable capture

- **GIVEN** a Python file with nested functions where `inner()` references `x` from `outer()`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a closure capture with:
  - `inner_function`: "inner"
  - `captured_variable`: "x"
  - `outer_function`: "outer"

#### Scenario: Nonlocal variable modification

- **GIVEN** a Python file with `nonlocal counter; counter += 1`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a nonlocal access with `access_type`: "write"

---

### Requirement: Recursion Pattern Detection

The system SHALL detect recursion patterns including direct recursion, mutual recursion, tail recursion, and base case identification.

**Rationale**: Recursive patterns indicate specific algorithm characteristics that can only be verified through testing (e.g., "Function X uses recursion with base case Y").

**Extraction Target**: ≥80 recursion patterns from TheAuditor codebase.

#### Scenario: Direct recursion detected

- **GIVEN** a Python file with `def factorial(n): return n * factorial(n-1) if n > 0 else 1`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a recursion pattern with:
  - `function_name`: "factorial"
  - `recursion_type`: "direct"
  - `base_case_line`: [line number of `if n > 0`]

#### Scenario: Tail recursion identified

- **GIVEN** a Python file with `def tail_factorial(n, acc=1): return tail_factorial(n-1, n*acc) if n > 0 else acc`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a recursion pattern with `recursion_type`: "tail"

#### Scenario: Mutual recursion detected

- **GIVEN** a Python file with `def is_even(n)` calling `is_odd(n-1)` and vice versa
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract recursion patterns for both functions with `recursion_type`: "mutual"

---

### Requirement: Generator Pattern Extraction

The system SHALL extract generator patterns including yield statements, yield conditions, and yield-from expressions.

**Rationale**: Generator behavior can only be validated through runtime execution. Extracting yield patterns enables hypothesis generation about lazy evaluation and iteration behavior (e.g., "Generator X yields when condition Y").

**Extraction Target**: ≥200 generator yield records from TheAuditor codebase.

#### Scenario: Simple yield statement

- **GIVEN** a Python file with `def gen(): yield value`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a generator yield with:
  - `generator_function`: "gen"
  - `yield_type`: "yield"
  - `yield_expr`: "value"

#### Scenario: Conditional yield

- **GIVEN** a Python file with `if condition: yield value`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a generator yield with `condition`: "if condition"

#### Scenario: Yield from delegation

- **GIVEN** a Python file with `yield from other_generator()`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a generator yield with `yield_type`: "yield_from"

---

### Requirement: Property Access Pattern Detection

The system SHALL extract property patterns including computed property getters, validated property setters, and dynamic attribute access via `__getattr__` and `__setattr__`.

**Rationale**: Properties may perform computation or validation that is invisible in static code. Detecting property patterns enables hypothesis generation about hidden behavior (e.g., "Property X computes value rather than returning stored attribute").

**Extraction Target**: ≥150 property patterns from TheAuditor codebase.

#### Scenario: Computed property getter

- **GIVEN** a Python file with `@property def area(self): return self.width * self.height`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a property pattern with:
  - `property_name`: "area"
  - `access_type`: "getter"
  - `has_computation`: True

#### Scenario: Validated property setter

- **GIVEN** a Python file with `@age.setter def age(self, value): if value < 0: raise ValueError; self._age = value`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a property pattern with:
  - `property_name`: "age"
  - `access_type`: "setter"
  - `has_validation`: True

#### Scenario: Dynamic attribute interception

- **GIVEN** a Python file with `def __getattr__(self, name): return self._data.get(name)`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a dynamic attribute pattern with `method_name`: "__getattr__"

---

### Requirement: Loop Complexity Detection

The system SHALL extract loop complexity patterns including nested loops, growing operations within loops, and nesting levels.

**Rationale**: Loop complexity indicates performance characteristics that must be measured, not guessed. Detecting nested loops enables hypothesis generation about algorithmic complexity (e.g., "Function X has O(n²) complexity due to nested loops").

**Extraction Target**: ≥250 loop complexity records from TheAuditor codebase.

#### Scenario: Nested loop detected

- **GIVEN** a Python file with nested `for` loops
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a loop complexity record with `nesting_level`: 2

#### Scenario: Growing operation in loop

- **GIVEN** a Python file with `for item in items: result.append(transform(item))`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a loop complexity record with `has_growing_operation`: True

#### Scenario: While loop complexity

- **GIVEN** a Python file with `while condition: ...`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a loop complexity record with `loop_type`: "while"

---

### Requirement: Resource Usage Pattern Detection

The system SHALL extract resource usage patterns including large data structure allocation, file handle accumulation, and database connection patterns.

**Rationale**: Resource usage must be measured to validate performance claims. Detecting resource patterns enables hypothesis generation about memory and resource consumption (e.g., "Function X allocates large memory structures").

**Extraction Target**: ≥100 resource usage records from TheAuditor codebase.

#### Scenario: Large list comprehension

- **GIVEN** a Python file with `result = [x for x in range(1000000)]`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a resource usage pattern with:
  - `resource_type`: "large_list"
  - `allocation_expr`: "[x for x in range(1000000)]"

#### Scenario: File handle without context manager

- **GIVEN** a Python file with `f = open(file)` without corresponding `f.close()` or `with` statement
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a resource usage pattern with `resource_type`: "file_handle"

#### Scenario: Database connection pattern

- **GIVEN** a Python file with `conn = db.connect()`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a resource usage pattern with `resource_type`: "db_connection"

---

### Requirement: Memoization Pattern Detection

The system SHALL detect memoization and caching patterns including `@lru_cache` decorators, manual cache dictionaries, and missing memoization opportunities in recursive functions.

**Rationale**: Memoization presence or absence affects performance characteristics. Detecting memoization patterns enables hypothesis generation about optimization opportunities (e.g., "Function X would benefit from memoization").

**Extraction Target**: ≥50 memoization patterns from TheAuditor codebase.

#### Scenario: LRU cache decorator detected

- **GIVEN** a Python file with `@functools.lru_cache(maxsize=128) def expensive_func():`
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a memoization pattern with:
  - `function_name`: "expensive_func"
  - `has_memoization`: True
  - `memoization_type`: "lru_cache"

#### Scenario: Manual cache dictionary

- **GIVEN** a Python file using a module-level `_cache = {}` dictionary for memoization
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a memoization pattern with `memoization_type`: "manual"

#### Scenario: Unmemoized recursion

- **GIVEN** a Python file with recursive function without memoization
- **WHEN** the extraction pipeline processes the file
- **THEN** the system SHALL extract a memoization pattern with:
  - `has_memoization`: False
  - `memoization_type`: "none"

---

### Requirement: Hypothesis Generation Enablement

The system SHALL ensure that extracted patterns enable hypothesis generation with ≥3 hypothesis types per extraction pattern category and achieve a validation rate of >70% when hypotheses are tested experimentally.

**Rationale**: The extraction layer exists to serve causal learning. If extracted patterns do not enable testable hypotheses, the extraction is not valuable.

**Success Metric**: >70% of generated hypotheses must be testable and validatable through experiments.

#### Scenario: Side effect hypothesis generated

- **GIVEN** an extracted instance mutation: `self.counter += 1` in function `increment`
- **WHEN** hypothesis generation processes the extraction
- **THEN** the system SHALL generate hypothesis: "Function increment modifies instance attribute counter"
- **AND** the system SHALL design experiment: "Call increment(), check object.counter before/after"

#### Scenario: Exception handling hypothesis generated

- **GIVEN** an extracted exception raise: `raise ValueError("Invalid")` with condition `if x < 0`
- **WHEN** hypothesis generation processes the extraction
- **THEN** the system SHALL generate hypothesis: "Function raises ValueError when x < 0"
- **AND** the system SHALL design experiment: "Call function with negative x, assert ValueError raised"

#### Scenario: I/O hypothesis generated

- **GIVEN** an extracted I/O operation: `open(file, 'w')`
- **WHEN** hypothesis generation processes the extraction
- **THEN** the system SHALL generate hypothesis: "Function writes to filesystem"
- **AND** the system SHALL design experiment: "Mock filesystem, call function, verify write occurred"

#### Scenario: Data flow hypothesis generated

- **GIVEN** an extracted parameter flow: `return param * 2`
- **WHEN** hypothesis generation processes the extraction
- **THEN** the system SHALL generate hypothesis: "Function returns transformed parameter"
- **AND** the system SHALL design experiment: "Call with parameter=5, assert return value=10"

#### Scenario: Performance hypothesis generated

- **GIVEN** an extracted nested loop with `nesting_level`: 2
- **WHEN** hypothesis generation processes the extraction
- **THEN** the system SHALL generate hypothesis: "Function has O(n²) complexity"
- **AND** the system SHALL design experiment: "Test with varying input sizes, measure execution time"

---

### Requirement: Performance Maintenance

The system SHALL maintain extraction performance of <10 milliseconds per file despite adding 20 new extraction functions.

**Rationale**: Extraction must remain fast to support rapid iteration. Performance degradation blocks developer productivity.

**Success Metric**: Extraction time ≤0.5 seconds per file (no degradation from baseline).

#### Scenario: Single-pass extraction optimization

- **GIVEN** 5 new state mutation extractors
- **WHEN** implemented with single-pass AST walking instead of multi-pass
- **THEN** extraction time SHALL not increase by more than 10% compared to baseline

#### Scenario: Large file extraction performance

- **GIVEN** a Python file with >1000 lines of code
- **WHEN** the extraction pipeline processes the file
- **THEN** extraction time SHALL be <0.5 seconds

#### Scenario: Entire codebase extraction performance

- **GIVEN** TheAuditor codebase with ~200 Python files
- **WHEN** running `aud index`
- **THEN** total extraction time SHALL be <2 minutes (maintaining 2-10 files/sec throughput)

---

## END OF DELTAS
