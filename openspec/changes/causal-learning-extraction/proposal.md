# Causal Learning Foundation: Python Behavioral Pattern Extraction

**Change ID**: causal-learning-extraction
**Type**: Enhancement (Causal Learning Infrastructure)
**Priority**: CRITICAL
**Status**: PROPOSED
**Date**: 2025-11-13
**Author**: Lead Coder (Opus AI via Architect)
**Purpose**: Enable hypothesis generation and experimental validation through behavioral pattern extraction

---

## Why

### Problem Statement

The extraction layer is the foundation of all causal learning. Without proper extraction of behavioral patterns, the DIEC tool (Dynamic Inference and Experimentation for Code) **cannot generate testable hypotheses, cannot design valid experiments, and cannot perform meaningful causal discovery**.

**Current Blindspots** (verified 2025-11-13 against python_coverage.md):

1. **Side Effects**: Cannot detect state mutations (self.x = value), I/O operations, global modifications
2. **Exception Flow**: Cannot track raises/catches/finally blocks for error handling hypothesis generation
3. **Data Flow**: Cannot trace parameter → return flow, closure captures, nonlocal access
4. **Behavioral Patterns**: Cannot detect recursion, generators, property access with side effects
5. **Performance Indicators**: Cannot extract loop complexity, resource usage patterns

**Business Impact**:
- DIEC tool is **blind to 80% of causal relationships** in Python code
- Cannot generate hypotheses like "This function modifies instance state" or "This function has side effects on files"
- Cannot design experiments to validate behavior claims
- Static analysis tells us syntax, but **not what code actually does at runtime**

**Why This Matters**:
- TheAuditor focuses on security vulnerabilities (what's wrong)
- DIEC focuses on behavioral understanding (what happens and why)
- Same extraction layer serves both tools → **double win**
- Side effects are the #1 thing static analysis cannot prove but experimentation can
- Causal learning is where TheAuditor + DIEC create unique value proposition

**Difference from python-extraction-mapping Proposal**:
- Old proposal: "JavaScript parity" (feature completeness for SAST)
- This proposal: "Causal learning foundation" (behavioral patterns for experimentation)
- Old focus: Django URL patterns, Pydantic V2 validators (framework completeness)
- This focus: State mutations, exception flows, side effects (behavior understanding)
- Old goal: 95% Python/JavaScript parity
- This goal: >70% hypothesis validation rate in DIEC tool

---

## What Changes

### Scope: 5 New Extractor Modules (4 weeks)

This proposal implements behavioral pattern extraction in priority order from python_coverage.md.

**Week 1: Priority 1 + 2 (Side Effects & Exceptions)**
- Add state mutation detection (instance, class, global, argument modifications)
- Add exception flow tracking (raises, catches, finally blocks)
- Create 2 new extractor modules
- Create 10+ new database tables
- **Target**: Enable side effect and error handling hypotheses

**Week 2: Priority 3 (Data Flow)**
- Add I/O operation detection (file, database, network, process, env vars)
- Add parameter → return flow tracking
- Add closure capture and nonlocal access detection
- Create 1 new extractor module
- Create 8+ new database tables
- **Target**: Enable taint analysis and security hypotheses

**Week 3: Priority 4 (Behavioral Patterns)**
- Add recursion detection (direct, mutual, tail recursion)
- Add generator/iterator pattern extraction
- Add property access pattern extraction (getters with computation, setters with validation)
- Create 1 new extractor module
- Create 6+ new database tables
- **Target**: Enable algorithm characteristic hypotheses

**Week 4: Priority 5 (Performance Indicators)**
- Add loop complexity detection (nested loops, growing operations)
- Add resource usage pattern extraction
- Create 1 new extractor module
- Create 4+ new database tables
- **Target**: Enable performance hypotheses

### New Files Created

**5 new extractor modules** (~3,500 lines total):
```
theauditor/ast_extractors/python/
├── state_mutation_extractors.py      (Week 1, ~800 lines)
│   - extract_instance_mutations()
│   - extract_class_mutations()
│   - extract_global_mutations()
│   - extract_argument_mutations()
│   - extract_augmented_assignments()
│
├── exception_flow_extractors.py      (Week 1, ~600 lines)
│   - extract_exception_raises()
│   - extract_exception_catches()
│   - extract_finally_blocks()
│   - extract_context_manager_cleanup()
│
├── data_flow_extractors.py           (Week 2, ~800 lines)
│   - extract_io_operations()
│   - extract_parameter_return_flow()
│   - extract_closure_captures()
│   - extract_nonlocal_access()
│
├── behavioral_extractors.py          (Week 3, ~700 lines)
│   - extract_recursion_patterns()
│   - extract_generator_patterns()
│   - extract_property_access_patterns()
│   - extract_dynamic_attribute_access()
│
└── performance_extractors.py         (Week 4, ~600 lines)
    - extract_loop_complexity()
    - extract_resource_usage()
    - extract_memoization_patterns()
```

**Modified files** (3 files, ~400 lines changed):
- `theauditor/ast_extractors/python/__init__.py` - Wire all new extractors (+100 lines)
- `theauditor/indexer/extractors/python.py` - Call new extractors (+150 lines)
- `theauditor/indexer/schemas/python_schema.py` - Add 28+ new tables (+150 lines)

**Database Impact**:
- +28 new tables (59 → 87 tables)
- +10,000 new records extracted from TheAuditor (estimated)
- Database size increase: ~25% (91MB → 114MB)

### Breaking Changes

**NONE** - This is additive work only. All existing extractors remain functional.

---

## Impact

### Affected Specifications

- `specs/python-extraction/spec.md` - Add 5 new behavioral pattern categories
- **NO** other specs affected (pure additive work)

### Affected Users

**TheAuditor Users**:
- Security analysts get enhanced taint analysis (side effect tracking)
- Developers get better dead code detection (side effect vs pure function distinction)
- DevOps get performance risk indicators (loop complexity, resource usage)

**DIEC Tool Users**:
- Can generate hypotheses about side effects: "This function modifies instance state"
- Can design experiments: "Call function, check object state before/after"
- Can validate claims: "This function has O(n²) complexity" → test with varying inputs
- **>70% hypothesis validation rate target** (per python_coverage.md)

### Migration Plan

**NONE REQUIRED** - All changes are additive. Existing databases continue to work.

---

## Detailed Gap Analysis (Mapped to python_coverage.md)

### Priority 1: Side Effect Detection (Week 1 - HIGHEST VALUE)

**Why Critical**: Side effects are the #1 thing that static analysis cannot prove but experimentation can. This is where causal learning shines.

#### Current State: BLIND
- ❌ Cannot detect `self.x = value` (instance mutation)
- ❌ Cannot detect `ClassName.x = value` (class mutation)
- ❌ Cannot detect `global x; x = value` (global mutation)
- ❌ Cannot detect `def foo(lst): lst.append(x)` (argument mutation)
- ❌ Cannot detect `dict['key'] = value` (dictionary mutation)
- ❌ Cannot detect `list[0] = value` (list mutation)
- ❌ Cannot distinguish pure functions from impure functions

**We HAVE**:
- ✅ Simple assignments: `x = value` (core_extractors.py:extract_python_assignments)
- ⚠️ Augmented assignments tracked but not categorized by mutation type

**Gap**: No way to generate hypothesis "This function has side effects on instance state"

**Records Expected**: ~3,000 state mutations in TheAuditor codebase

#### Implementation Plan (Week 1, Part 1):

**state_mutation_extractors.py** (800 lines, 5 extractors):

```python
def extract_instance_mutations(tree, parser_self) -> List[Dict]:
    """Extract self.x = value patterns (instance attribute mutations).

    Detects:
    - Direct assignment: self.counter = 0
    - Augmented assignment: self.counter += 1
    - Nested attributes: self.config.debug = True
    - Method calls with side effects: self.items.append(x)

    Returns:
    {
        'line': int,
        'target': str,  # 'self.counter'
        'operation': 'assignment' | 'augmented_assignment' | 'method_call',
        'in_function': str,  # Function name where mutation occurs
        'is_init': bool,  # True if in __init__ (expected mutation)
    }

    Enables hypothesis: "Function X modifies instance attribute Y"
    Experiment design: Call X, check object.Y before/after
    """
```

```python
def extract_class_mutations(tree, parser_self) -> List[Dict]:
    """Extract ClassName.x = value patterns (class attribute mutations).

    Detects:
    - Class variable assignment: MyClass.instances = []
    - cls.x = value in @classmethod

    Enables hypothesis: "Function X modifies class state"
    """
```

```python
def extract_global_mutations(tree, parser_self) -> List[Dict]:
    """Extract global x; x = value patterns.

    Detects:
    - global statement followed by assignment
    - Module-level variable reassignment

    Enables hypothesis: "Function X has global side effects"
    """
```

```python
def extract_argument_mutations(tree, parser_self) -> List[Dict]:
    """Extract mutable argument modifications.

    Detects:
    - def foo(lst): lst.append(x)
    - def foo(d): d['key'] = value
    - Any method call on parameter that mutates it

    Enables hypothesis: "Function X mutates its arguments"
    """
```

```python
def extract_augmented_assignments(tree, parser_self) -> List[Dict]:
    """Extract +=, -=, *=, /=, //=, %=, **=, &=, |=, ^=, >>=, <<= on ANY target.

    Categorizes by target type:
    - Instance: self.x += 1
    - Class: cls.x += 1
    - Global: global_var += 1
    - Local: local_var += 1
    - Argument: param += 1

    Enables hypothesis: "Function X performs in-place operations on Y"
    """
```

**Database Tables** (5 tables):
```sql
CREATE TABLE python_instance_mutations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    target TEXT NOT NULL,  -- 'self.counter'
    operation TEXT NOT NULL,  -- 'assignment' | 'augmented_assignment' | 'method_call'
    in_function TEXT NOT NULL,
    is_init BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file, line, target)
);

CREATE TABLE python_class_mutations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    attribute TEXT NOT NULL,
    operation TEXT NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, class_name, attribute)
);

CREATE TABLE python_global_mutations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    global_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, global_name)
);

CREATE TABLE python_argument_mutations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    parameter_name TEXT NOT NULL,
    mutation_type TEXT NOT NULL,  -- 'append' | 'setitem' | 'update' | 'other'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, parameter_name)
);

CREATE TABLE python_augmented_assignments (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    target TEXT NOT NULL,  -- Full target expression
    operator TEXT NOT NULL,  -- '+=', '-=', etc.
    target_type TEXT NOT NULL,  -- 'instance' | 'class' | 'global' | 'local' | 'argument'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, target)
);
```

**Test Fixtures** (200 lines):
```python
# tests/fixtures/python/state_mutation_patterns.py
class Counter:
    instances = 0  # Class attribute

    def __init__(self):
        self.count = 0  # Instance attribute (expected in __init__)
        Counter.instances += 1  # Class mutation

    def increment(self):
        self.count += 1  # Instance mutation (augmented assignment)

    def reset(self):
        self.count = 0  # Instance mutation (direct assignment)

def modify_list(items):
    items.append('new')  # Argument mutation

_global_cache = {}

def update_cache(key, value):
    global _global_cache
    _global_cache[key] = value  # Global mutation
```

**Success Criteria**:
- ✅ Extract 3,000+ state mutations from TheAuditor
- ✅ Distinguish expected mutations (__init__) from unexpected mutations
- ✅ Enable hypothesis generation: "Function has side effects on instance/class/global state"
- ✅ Achieve >70% validation rate when testing generated hypotheses

---

### Priority 1: Exception Flow (Week 1, Part 2)

**Why Critical**: Error handling is fundamental to robustness. Cannot design experiments without knowing what exceptions can occur.

#### Current State: PARTIAL
- ⚠️ `exception_extractors.py` exists in proposal but NOT implemented in codebase
- ❌ Cannot track which exceptions are raised where
- ❌ Cannot track which exceptions are caught and how they're handled
- ❌ Cannot detect finally block cleanup logic
- ❌ Cannot trace exception propagation paths

**We HAVE**:
- ✅ Try/except detection exists but minimal (no extraction)

**Gap**: No way to generate hypothesis "Function X raises ValueError when input is negative"

**Records Expected**: ~800 exception raises, ~600 exception handlers in TheAuditor

#### Implementation Plan (Week 1, Part 2):

**exception_flow_extractors.py** (600 lines, 4 extractors):

```python
def extract_exception_raises(tree, parser_self) -> List[Dict]:
    """Extract raise statements with exception type and context.

    Detects:
    - raise ValueError("message")
    - raise CustomError() from original_error
    - raise  # Re-raise in except block
    - Conditional raises: if condition: raise Error()

    Returns:
    {
        'line': int,
        'exception_type': str,  # 'ValueError'
        'message': str | None,  # Static message if available
        'from_exception': str | None,  # For exception chaining
        'in_function': str,
        'condition': str | None,  # 'if x < 0' if conditional
        'is_re_raise': bool,  # True for bare 'raise'
    }

    Enables hypothesis: "Function X raises ValueError when condition Y"
    Experiment design: Call X with invalid input, assert ValueError raised
    """
```

```python
def extract_exception_catches(tree, parser_self) -> List[Dict]:
    """Extract except clauses and their handling strategies.

    Detects:
    - except ValueError as e: ...
    - except (TypeError, ValueError): ...
    - except Exception: ...
    - Multiple except clauses for same try block

    Returns:
    {
        'line': int,
        'exception_types': List[str],  # ['ValueError', 'TypeError']
        'variable_name': str | None,  # 'e' in 'as e'
        'handling_strategy': str,  # 'return_none' | 're_raise' | 'log_and_continue' | 'convert_to_other'
        'in_function': str,
    }

    Enables hypothesis: "Function X converts ValueError to None"
    """
```

```python
def extract_finally_blocks(tree, parser_self) -> List[Dict]:
    """Extract finally blocks that always execute.

    Detects:
    - finally: cleanup()
    - Resource cleanup patterns
    - File handle closing
    - Lock releasing

    Enables hypothesis: "Function X always releases lock even on error"
    """
```

```python
def extract_context_manager_cleanup(tree, parser_self) -> List[Dict]:
    """Extract context managers (with statements) that ensure cleanup.

    Detects:
    - with open(file) as f: ...
    - with lock: ...
    - @contextmanager decorated functions

    Enables hypothesis: "Function X guarantees resource cleanup"
    """
```

**Database Tables** (4 tables):
```sql
CREATE TABLE python_exception_raises (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    exception_type TEXT NOT NULL,
    message TEXT,
    from_exception TEXT,
    in_function TEXT NOT NULL,
    condition TEXT,
    is_re_raise BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file, line, exception_type)
);

CREATE TABLE python_exception_catches (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    exception_types TEXT NOT NULL,  -- Comma-separated for multiple types
    variable_name TEXT,
    handling_strategy TEXT NOT NULL,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

CREATE TABLE python_finally_blocks (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    cleanup_calls TEXT,  -- Comma-separated function names called in finally
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

CREATE TABLE python_context_managers (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    context_expr TEXT NOT NULL,  -- 'open(file)' or 'lock'
    variable_name TEXT,  -- 'f' in 'as f'
    in_function TEXT NOT NULL,
    is_async BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (file, line, context_expr)
);
```

**Success Criteria**:
- ✅ Extract 800+ exception raises from TheAuditor
- ✅ Extract 600+ exception handlers
- ✅ Enable hypothesis generation: "Function raises X when Y" and "Function converts X to Z"
- ✅ Achieve >70% validation rate

---

### Priority 2: I/O Operations (Week 2, Part 1)

**Why Critical**: External interactions are invisible to static analysis. Must detect to design experiments that mock/monitor I/O.

#### Current State: BLIND
- ❌ Cannot detect file writes (only reads tracked minimally)
- ❌ Cannot detect database commits/rollbacks
- ❌ Cannot detect network calls
- ❌ Cannot detect subprocess spawning
- ❌ Cannot detect environment variable modifications

**Gap**: No way to generate hypothesis "Function X writes to filesystem"

**Records Expected**: ~2,000 I/O operations in TheAuditor

#### Implementation Plan (Week 2, Part 1):

**data_flow_extractors.py** (800 lines, 4 extractors):

```python
def extract_io_operations(tree, parser_self) -> List[Dict]:
    """Extract all I/O operations that interact with external systems.

    Detects:
    - File operations: open(file, 'w'), Path.write_text()
    - Database operations: db.session.commit(), cursor.execute()
    - Network calls: requests.post(), urllib.request.urlopen()
    - Process spawning: subprocess.run(), os.system()
    - Environment modifications: os.environ['KEY'] = value

    Returns:
    {
        'line': int,
        'io_type': 'FILE_WRITE' | 'FILE_READ' | 'DB_COMMIT' | 'DB_QUERY' | 'NETWORK' | 'PROCESS' | 'ENV_MODIFY',
        'operation': str,  # 'open', 'requests.post', 'subprocess.run', etc.
        'target': str | None,  # Filename, URL, command, etc. (if static)
        'in_function': str,
    }

    Enables hypothesis: "Function X writes to filesystem"
    Experiment design: Mock filesystem, call X, verify write occurred
    """
```

**Database Table** (1 table):
```sql
CREATE TABLE python_io_operations (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    io_type TEXT NOT NULL,
    operation TEXT NOT NULL,
    target TEXT,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, operation)
);
```

---

### Priority 3: Data Flow Analysis (Week 2, Part 2)

**Why Critical**: Understanding how data flows enables taint analysis and security hypothesis generation.

#### Current State: PARTIAL
- ✅ Function calls with arguments tracked (core_extractors.py)
- ✅ Assignments tracked (core_extractors.py)
- ⚠️ Return statements tracked but not linked to parameters
- ❌ Closure captures not tracked
- ❌ Nonlocal modifications not tracked

**Gap**: Cannot trace parameter → return flow to validate "Function X returns transformed parameter Y"

**Records Expected**: ~1,500 parameter flows, ~300 closure captures in TheAuditor

#### Implementation Plan (Week 2, Part 2):

```python
def extract_parameter_return_flow(tree, parser_self) -> List[Dict]:
    """Track how function parameters influence return values.

    Detects:
    - Direct returns: return param
    - Transformed returns: return param * 2
    - Conditional returns: return a if condition else b
    - No data flow: return constant

    Enables hypothesis: "Function X returns transformed parameter Y"
    """
```

```python
def extract_closure_captures(tree, parser_self) -> List[Dict]:
    """Identify variables captured from outer scope.

    Detects:
    - def outer(): x = 10; def inner(): return x * 2
    - Lambda captures

    Enables hypothesis: "Function X depends on outer variable Y"
    """
```

```python
def extract_nonlocal_access(tree, parser_self) -> List[Dict]:
    """Extract nonlocal variable modifications.

    Detects:
    - nonlocal x; x = value

    Enables hypothesis: "Nested function X modifies outer variable Y"
    """
```

**Database Tables** (3 tables):
```sql
CREATE TABLE python_parameter_return_flow (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    return_expr TEXT NOT NULL,
    flow_type TEXT NOT NULL,  -- 'direct' | 'transformed' | 'conditional' | 'none'
    PRIMARY KEY (file, line, parameter_name)
);

CREATE TABLE python_closure_captures (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    inner_function TEXT NOT NULL,
    captured_variable TEXT NOT NULL,
    outer_function TEXT NOT NULL,
    PRIMARY KEY (file, line, inner_function, captured_variable)
);

CREATE TABLE python_nonlocal_access (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    variable_name TEXT NOT NULL,
    access_type TEXT NOT NULL,  -- 'read' | 'write'
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, variable_name)
);
```

---

### Priority 4: Behavioral Patterns (Week 3)

**Why Critical**: Algorithm characteristics can only be verified through testing.

#### Current State: PARTIAL
- ⚠️ Generators detected but not yield conditions tracked
- ❌ Recursion not detected
- ❌ Property access patterns not tracked

**Records Expected**: ~500 behavioral patterns in TheAuditor

#### Implementation Plan (Week 3):

**behavioral_extractors.py** (700 lines, 4 extractors):

```python
def extract_recursion_patterns(tree, parser_self) -> List[Dict]:
    """Detect recursion patterns.

    Detects:
    - Direct recursion: Function calls itself
    - Mutual recursion: A calls B, B calls A (requires cross-file analysis)
    - Tail recursion patterns
    - Base case detection

    Enables hypothesis: "Function X uses recursion with base case Y"
    """
```

```python
def extract_generator_patterns(tree, parser_self) -> List[Dict]:
    """Extract yield statements and their conditions.

    Detects:
    - yield value
    - yield from generator
    - Conditional yields: if condition: yield value

    Enables hypothesis: "Generator X yields when condition Y"
    """
```

```python
def extract_property_access_patterns(tree, parser_self) -> List[Dict]:
    """Extract property getters/setters with computation or validation.

    Detects:
    - @property with computation
    - @property.setter with validation
    - Descriptors with side effects

    Enables hypothesis: "Property X computes value rather than returning stored attribute"
    """
```

```python
def extract_dynamic_attribute_access(tree, parser_self) -> List[Dict]:
    """Extract __getattr__ and __setattr__ patterns.

    Detects:
    - Dynamic attribute access
    - Attribute proxying

    Enables hypothesis: "Class X intercepts attribute access"
    """
```

**Database Tables** (6 tables):
```sql
CREATE TABLE python_recursion_patterns (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    recursion_type TEXT NOT NULL,  -- 'direct' | 'mutual' | 'tail'
    base_case_line INTEGER,
    PRIMARY KEY (file, line, function_name)
);

CREATE TABLE python_generator_yields (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    generator_function TEXT NOT NULL,
    yield_type TEXT NOT NULL,  -- 'yield' | 'yield_from'
    yield_expr TEXT,
    condition TEXT,
    PRIMARY KEY (file, line)
);

CREATE TABLE python_property_patterns (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    property_name TEXT NOT NULL,
    access_type TEXT NOT NULL,  -- 'getter' | 'setter' | 'deleter'
    has_computation BOOLEAN,
    has_validation BOOLEAN,
    PRIMARY KEY (file, line, property_name, access_type)
);

CREATE TABLE python_dynamic_attributes (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    method_name TEXT NOT NULL,  -- '__getattr__' | '__setattr__' | '__getattribute__'
    PRIMARY KEY (file, line, class_name, method_name)
);
```

---

### Priority 5: Performance Indicators (Week 4)

**Why Critical**: Performance characteristics must be measured, not guessed.

#### Current State: BLIND
- ❌ Cannot detect nested loops
- ❌ Cannot detect growing operations in loops
- ❌ Cannot detect resource allocation patterns

**Records Expected**: ~400 performance patterns in TheAuditor

#### Implementation Plan (Week 4):

**performance_extractors.py** (600 lines, 3 extractors):

```python
def extract_loop_complexity(tree, parser_self) -> List[Dict]:
    """Detect nested loops and growing operations.

    Detects:
    - Nested loops (potential O(n²) or worse)
    - Loops with append/extend/update (potential list growth)
    - Loops over loops without break (guaranteed O(n*m))

    Enables hypothesis: "Function X has O(n²) complexity due to nested loops"
    Experiment design: Test with varying input sizes, measure execution time
    """
```

```python
def extract_resource_usage(tree, parser_self) -> List[Dict]:
    """Extract resource allocation patterns.

    Detects:
    - Large data structure creation: [x for x in range(1000000)]
    - File handle accumulation: open() without close or context manager
    - Database connection patterns

    Enables hypothesis: "Function X allocates large memory structures"
    """
```

```python
def extract_memoization_patterns(tree, parser_self) -> List[Dict]:
    """Detect memoization and caching patterns.

    Detects:
    - @functools.lru_cache decorator
    - Manual cache dictionary usage
    - Recursive functions without memoization (potential optimization)

    Enables hypothesis: "Function X would benefit from memoization"
    """
```

**Database Tables** (4 tables):
```sql
CREATE TABLE python_loop_complexity (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    nesting_level INTEGER NOT NULL,
    loop_type TEXT NOT NULL,  -- 'for' | 'while'
    has_growing_operation BOOLEAN,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line)
);

CREATE TABLE python_resource_usage (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    resource_type TEXT NOT NULL,  -- 'large_list' | 'file_handle' | 'db_connection'
    allocation_expr TEXT,
    in_function TEXT NOT NULL,
    PRIMARY KEY (file, line, resource_type)
);

CREATE TABLE python_memoization_patterns (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    has_memoization BOOLEAN,
    memoization_type TEXT,  -- 'lru_cache' | 'manual' | 'none'
    PRIMARY KEY (file, line, function_name)
);
```

---

## Timeline

**Total Duration**: 4 weeks

```
Week 1: Priority 1 (Side Effects + Exceptions) → Enable side effect hypotheses
  - Days 1-3: state_mutation_extractors.py (5 extractors, 5 tables)
  - Days 4-5: exception_flow_extractors.py (4 extractors, 4 tables)
  - Database: +9 tables, +3,800 records

Week 2: Priority 3 (Data Flow) → Enable taint analysis hypotheses
  - Days 1-2: I/O operations (1 extractor, 1 table)
  - Days 3-5: Parameter flows, closures, nonlocal (3 extractors, 3 tables)
  - Database: +4 tables, +3,800 records

Week 3: Priority 4 (Behavioral) → Enable algorithm hypotheses
  - Days 1-5: behavioral_extractors.py (4 extractors, 4 tables)
  - Database: +4 tables, +500 records

Week 4: Priority 5 (Performance) → Enable complexity hypotheses
  - Days 1-5: performance_extractors.py (3 extractors, 4 tables)
  - Database: +4 tables, +400 records
  - Final testing and validation
```

**Milestones**:
- Week 1: State mutations and exception flow enable first hypothesis generation
- Week 2: Data flow enables security taint analysis hypotheses
- Week 3: Behavioral patterns enable algorithm characteristic hypotheses
- Week 4: Performance indicators enable complexity hypotheses
- **End of Week 4**: >70% hypothesis validation rate achieved (per python_coverage.md)

**Checkpoints** (end of each week):
- Hypothesis generation test: Generate 10 hypotheses from extracted patterns
- Experiment design test: Design valid experiments for each hypothesis
- Validation rate check: Measure % of hypotheses that can be tested and validated
- Performance check: Maintain <10ms per file extraction

---

## Success Metrics (from python_coverage.md)

### Quantitative Targets

| Metric | Baseline | Week 1 | Week 2 | Week 3 | Week 4 | Target |
|--------|----------|--------|--------|--------|--------|--------|
| **Extractor Modules** | 13 | 15 | 16 | 17 | 18 | 18 |
| **Tables** | 59 | 68 | 72 | 76 | 80 | 87 |
| **Records (TheAuditor)** | 7,761 | 11,561 | 15,361 | 15,861 | 16,261 | 16,261+ |
| **Hypothesis Types** | 0 | 2 | 4 | 6 | 7 | 7+ |
| **Validation Rate** | 0% | 60% | 70% | 75% | 75% | >70% |

### Qualitative Targets

**Each extraction pattern MUST enable**:
1. **Hypothesis Generation**: ≥3 hypothesis types per pattern
2. **Experiment Design**: Clear test cases for each hypothesis
3. **Validation Rate**: >70% of generated hypotheses should be testable

**Example Success Path**:
```
Extract: state_mutation_extractors.py finds self.counter += 1 in increment()
  ↓
Generate Hypothesis: "increment() modifies instance attribute counter"
  ↓
Design Experiment: Call increment(), check object.counter before/after
  ↓
Validate: Run experiment, confirm counter increased by 1
  ↓
Result: Hypothesis validated ✅ (contributes to >70% validation rate)
```

**Failure Modes to Avoid**:
- Extraction finds pattern but hypothesis cannot be generated → Fix extractor
- Hypothesis generated but cannot be tested → Fix experiment design
- Experiment runs but validation fails → Legitimate discovery (not a failure!)

---

## Risk Analysis

### High Risks

1. **False Positive Side Effect Detection**
   - **Probability**: MEDIUM (self.x = value in __init__ is expected, not a side effect)
   - **Impact**: HIGH (generates invalid hypotheses, wastes experiment time)
   - **Mitigation**: Flag __init__ mutations separately, distinguish expected vs unexpected
   - **Contingency**: Add confidence scores to extracted patterns

2. **Cross-File Data Flow Complexity**
   - **Probability**: HIGH (closure captures may reference imported functions)
   - **Impact**: MEDIUM (limits hypothesis accuracy)
   - **Mitigation**: Start with single-file patterns, defer cross-file to Week 5+
   - **Contingency**: Document limitations in hypothesis metadata

3. **Performance Degradation**
   - **Probability**: LOW (5 new modules, single-pass extraction planned)
   - **Impact**: MEDIUM (slows indexing)
   - **Mitigation**: Single-pass AST walking, profile after each week
   - **Contingency**: Defer performance extractors (Priority 5) if needed

### Medium Risks

4. **Hypothesis Validation Rate < 70%**
   - **Probability**: MEDIUM (new patterns, unknown quality)
   - **Impact**: HIGH (blocks DIEC tool value proposition)
   - **Mitigation**: Weekly validation rate checks, adjust extractors mid-stream
   - **Contingency**: Focus on high-value patterns (Priorities 1-3 only)

5. **Dynamic Code Patterns**
   - **Probability**: MEDIUM (getattr, setattr, eval)
   - **Impact**: LOW (edge cases)
   - **Mitigation**: Extract what's statically visible, flag dynamic patterns
   - **Contingency**: Document as "requires runtime analysis"

### Low Risks

6. **Schema Complexity**
   - **Probability**: LOW (28 new tables is manageable)
   - **Impact**: MEDIUM (harder to maintain)
   - **Mitigation**: Follow existing schema patterns, comprehensive docs
   - **Contingency**: Consolidate tables if needed

---

## Rollback Plan

### Week-by-Week Rollback

Each week is independently mergeable:
1. **Git**: Each week on separate branch (`causal-week1`, `causal-week2`, etc.)
2. **Database**: Snapshots in .pf/history/full/ before each week
3. **Code**: Can disable any week's extractors by commenting out in __init__.py

### Partial Rollback

If specific extractors fail:
1. Comment out failing extractor in `__init__.py`
2. Remove table from schema (database regenerated fresh anyway)
3. Continue with remaining extractors

### Data Recovery

- Week 0 baseline: 7,761 records verified (current state)
- Daily snapshots during implementation
- Test projects for verification: TheAuditor, plant, PlantFlow

---

## Verification Strategy (teamsop.md Prime Directive - EMBEDDED)

### Pre-Implementation Verification Phase (MANDATORY)

Before implementing EACH WEEK, the Coder SHALL follow teamsop.md v4.20 protocols:

#### 1. Read Source Files (Verification Phase)

**Week 1 Pre-Implementation**:
- ✅ Read `theauditor/ast_extractors/python/core_extractors.py` (full file)
- ✅ Read `theauditor/ast_extractors/python/__init__.py` (full file)
- ✅ Read `theauditor/indexer/extractors/python.py` (full file, lines 1-1410)
- ✅ Read `theauditor/indexer/schemas/python_schema.py` (partial read)
- ✅ Read `python_coverage.md` (full file) ← DONE
- ✅ Read `openspec/changes/python-extraction-mapping/proposal.md` (full file) ← DONE for reference only

**Hypothesis Testing**:
```
Hypothesis 1: No state mutation extractors currently exist
Verification Method: Grep for "extract.*mutation" in ast_extractors/python/
Expected Result: No matches (confirming gap)

Hypothesis 2: Augmented assignments are tracked but not categorized
Verification Method: Check extract_python_assignments in core_extractors.py
Expected Result: ✅ Confirmed - assignments tracked but no mutation type categorization

Hypothesis 3: Exception extractors do NOT exist in production code
Verification Method: Check if exception_extractors.py file exists
Expected Result: ✅ Confirmed - No such file (not imported in __init__.py)

Hypothesis 4: Database has 59 Python tables currently
Verification Method: Count tables in python_schema.py
Expected Result: Will verify before Week 1 starts
```

#### 2. State Assumptions (Test Case Format)

**Week 1 Assumptions**:
- Assumption 1: AST provides `ast.Attribute` nodes for `self.x` access → VERIFY: Test AST parsing
- Assumption 2: AST provides `ast.Global` nodes for global statements → VERIFY: Test AST parsing
- Assumption 3: Single-pass extraction is possible for all state mutations → VERIFY: Profile prototype
- Assumption 4: ~3,000 state mutations exist in TheAuditor → VERIFY: Manual grep estimate

#### 3. Document Discrepancies (Before Implementation)

**Discrepancy Tracking**:
- If actual AST structure differs from assumed → Update extractor logic
- If record count estimates off by >30% → Investigate why
- If performance degrades >20% → Optimize or defer extractors
- If validation rate < 70% → Adjust hypothesis generation logic

#### 4. Post-Implementation Audit (MANDATORY AFTER EACH WEEK)

After each week, the Coder SHALL:
1. **Re-read** all modified files to confirm correctness (no syntax errors, no logic flaws)
2. **Run** `aud index` on TheAuditor
3. **Query** all new tables for data: `SELECT COUNT(*) FROM python_*_mutations`
4. **Compare** counts with expectations (±30% tolerance)
5. **Generate** 10 sample hypotheses from extracted patterns
6. **Design** experiments for each hypothesis
7. **Measure** validation rate (target: >70%)

**Report Template** (teamsop.md C-4.20 format):

```
Completion Report: Week 1 (State Mutations + Exception Flow)

Phase: Week 1
Objective: Enable side effect and error handling hypotheses
Status: [COMPLETE | PARTIAL | BLOCKED]

1. Verification Phase Report (Pre-Implementation)
   Hypotheses & Verification:
   - Hypothesis 1: No state mutation extractors exist
     Verification: ✅ Confirmed via grep
   - Hypothesis 2: AST provides Attribute nodes for self.x
     Verification: ✅ Confirmed via test parsing

   Discrepancies Found: [List any mismatches]

2. Deep Root Cause Analysis
   Surface Symptom: "DIEC tool cannot generate side effect hypotheses"
   Problem Chain:
   1. No extraction of self.x = value patterns
   2. No way to distinguish pure vs impure functions
   3. No data for hypothesis generation
   Actual Root Cause: Missing state mutation extractors

3. Implementation Details & Rationale
   Files Modified:
   - state_mutation_extractors.py (NEW, 800 lines)
   - exception_flow_extractors.py (NEW, 600 lines)
   - __init__.py (+50 lines)
   - python.py (+80 lines)
   - python_schema.py (+100 lines)

   Change Rationale:
   Decision: Create separate extractors for each mutation type
   Reasoning: Enables targeted hypothesis generation per mutation category
   Alternative Considered: Single extract_mutations() function
   Rejected Because: Too coarse-grained, loses mutation type distinction

4. Edge Case & Failure Mode Analysis
   Edge Cases Considered:
   - __init__ mutations (expected, flagged separately)
   - Property setters (tracked in behavioral_extractors.py Week 3)
   - Descriptors (deferred to Week 3)

   Performance Impact: <10ms per file maintained ✅

5. Post-Implementation Integrity Audit
   Audit Method: Re-read all modified files
   Files Audited: [List all]
   Result: ✅ SUCCESS - No syntax errors, logic correct

6. Impact, Reversion, & Testing
   Immediate: 9 new tables, 3,800 new records
   Downstream: DIEC can generate side effect hypotheses

   Testing Performed:
   $ aud index
   $ python -c "
   import sqlite3
   conn = sqlite3.connect('.pf/repo_index.db')
   print(conn.execute('SELECT COUNT(*) FROM python_instance_mutations').fetchone())
   "
   Result: [Record count]

   Hypothesis Generation Test:
   Generated 10 hypotheses: [List]
   Validation Rate: [X%] (Target: >70%)

7. Confirmation of Understanding
   Verification Finding: Gaps confirmed via grep and file reads
   Root Cause: Missing extraction modules
   Implementation Logic: 5 new extractors, 9 new tables
   Confidence Level: HIGH
```

---

## Approval Checklist

- [ ] Gap analysis verified against python_coverage.md (100% mapping)
- [ ] All 5 weeks/priorities clearly defined (state mutations → performance)
- [ ] Database impact assessed (28 new tables, +8,500 records)
- [ ] Performance impact evaluated (<10ms per file maintained)
- [ ] Test fixtures planned (800+ lines across 5 modules)
- [ ] Timeline realistic (4 weeks, 1 priority per week)
- [ ] Risk mitigation strategies defined (validation rate checks, performance profiling)
- [ ] Rollback plan documented (week-by-week branches)
- [ ] teamsop.md verification protocols EMBEDDED (Pre-Implementation + Post-Implementation Audit)
- [ ] Success metrics from python_coverage.md adopted (>70% validation rate)
- [ ] Double-win value proposition clear (TheAuditor + DIEC tool)

---

## Approval

**Lead Coder (Opus AI)**: Proposal complete, awaiting Architect approval
**Lead Auditor (Gemini)**: [Pending review]
**Architect (Santa)**: [Pending approval]

---

**END OF PROPOSAL**

**Next Steps After Approval**:
1. Create `openspec/changes/causal-learning-extraction/design.md`
2. Create `openspec/changes/causal-learning-extraction/tasks.md`
3. Create `openspec/changes/causal-learning-extraction/verification.md`
4. Begin Week 1 verification phase (read source files, state hypotheses)
5. Implement state_mutation_extractors.py
