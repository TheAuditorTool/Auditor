# Python Coverage Needs for Causal Learning

## Executive Summary

The extraction layer is the foundation of all causal learning. Without proper extraction, hypotheses cannot be generated, experiments cannot be designed, and learning cannot occur. This document identifies the critical Python patterns that need extraction to enable meaningful causal discovery.

## Current State Assessment

### What We Have (Adequately Covered)
- Basic functions and classes
- Import statements
- Simple assignments
- Return statements
- Basic decorators
- Framework routes (Flask/Django)
- Type annotations

### Critical Gaps Preventing Learning

The following patterns are essential for generating testable hypotheses about code behavior. Without these, the system is blind to crucial causal relationships.

---

## Priority 1: Side Effect Detection (HIGHEST VALUE)

**Why Critical**: Side effects are the #1 thing that static analysis cannot prove but experimentation can. This is where causal learning shines.

### 1.1 State Mutation Patterns

We need to detect when functions modify:
- Instance attributes: `self.x = value`
- Class attributes: `cls.x = value` or `ClassName.x = value`
- Module globals: `global x; x = value`
- Mutable argument modification: `def foo(lst): lst.append(x)`
- Dictionary/list mutations: `dict['key'] = value`, `list[0] = value`
- In-place operations: `+=`, `-=`, `*=`, `/=` on mutable objects

**Extraction Needed**:
```python
def extract_state_mutations(node):
    """
    Returns:
    {
        'type': 'MODIFIES_INSTANCE' | 'MODIFIES_CLASS' | 'MODIFIES_GLOBAL' | 'MODIFIES_ARGUMENT',
        'target': 'self.counter' | 'MyClass.instances' | 'GLOBAL_STATE',
        'operation': 'assignment' | 'augmented_assignment' | 'method_call',
        'location': {...}
    }
    """
```

### 1.2 I/O Operations

Critical for detecting functions that interact with external systems:
- File operations beyond simple reads
- Database transaction patterns
- Network calls
- Process spawning
- Environment variable modifications

**Extraction Needed**:
```python
def extract_io_operations(node):
    """
    Detect patterns like:
    - with open(file, 'w') as f: f.write(...)
    - db.session.commit()
    - requests.post(...)
    - subprocess.run(...)
    - os.environ['KEY'] = value
    """
```

---

## Priority 2: Control Flow Dependencies

**Why Critical**: Understanding when code executes is essential for designing valid experiments.

### 2.1 Conditional Execution Patterns

- Functions only called within specific conditions
- Early returns based on validation
- Exception-dependent paths
- Guard clauses

**Extraction Needed**:
```python
def extract_conditional_calls(node):
    """
    Track which functions are called under what conditions:
    if condition:
        dangerous_operation()  # Only called when condition is True
    """
```

### 2.2 Exception Flow

- What exceptions can be raised
- What exceptions are caught and how
- Finally blocks that always execute
- Context managers that ensure cleanup

**Extraction Needed**:
```python
def extract_exception_patterns(node):
    """
    Returns exception flows:
    - raises: [ValueError, TypeError, CustomError]
    - catches: {ValueError: 'converted_to_none', TypeError: 're_raised'}
    - finally_blocks: ['cleanup_resources()']
    """
```

---

## Priority 3: Data Flow Analysis

**Why Critical**: Understanding how data moves through code enables taint analysis and security hypothesis generation.

### 3.1 Parameter to Return Flow

Track how function parameters influence return values:
- Direct returns: `return param`
- Transformed returns: `return param * 2`
- Conditional returns: `return a if condition else b`
- No data flow: `return constant`

### 3.2 Closure and Nonlocal Access

Functions that capture external state:
- Closures accessing outer variables
- Nonlocal modifications
- Lambda captures

**Extraction Needed**:
```python
def extract_closure_captures(node):
    """
    Identify variables from outer scope:
    def outer():
        x = 10
        def inner():
            return x * 2  # Captures 'x'
    """
```

---

## Priority 4: Behavioral Patterns

**Why Critical**: These patterns indicate specific behaviors that can only be verified through testing.

### 4.1 Recursion Detection

- Direct recursion: Function calls itself
- Mutual recursion: A calls B, B calls A
- Tail recursion patterns
- Base case detection

### 4.2 Generator and Iterator Patterns

- Yield statements and their conditions
- Generator expressions
- Async generators
- Iterator protocol implementation

### 4.3 Property Access Patterns

- Property getters that compute values
- Property setters with validation
- Descriptors with side effects
- Dynamic attribute access (`__getattr__`, `__setattr__`)

---

## Priority 5: Performance Indicators

**Why Critical**: Performance characteristics must be measured, not guessed.

### 5.1 Loop Complexity Patterns

- Nested loops (potential O(n²) or worse)
- Loops with growing operations (append in loop)
- Recursive patterns without memoization
- Comprehensions vs explicit loops

### 5.2 Resource Usage Patterns

- Large data structure creation
- File handle management
- Database connection patterns
- Memory allocation patterns

---

## Implementation Priority Order

1. **State Mutation Detection** (Week 1)
   - Enables: Side effect hypotheses
   - Value: Highest - proves what static analysis cannot

2. **Exception Flow** (Week 1)
   - Enables: Error handling hypotheses
   - Value: High - critical for robustness testing

3. **I/O Operations** (Week 2)
   - Enables: External interaction hypotheses
   - Value: High - security and reliability

4. **Data Flow Analysis** (Week 2)
   - Enables: Taint analysis, security hypotheses
   - Value: High - security critical

5. **Control Flow Dependencies** (Week 3)
   - Enables: Conditional behavior hypotheses
   - Value: Medium - improves experiment accuracy

6. **Behavioral Patterns** (Week 3)
   - Enables: Algorithm characteristic hypotheses
   - Value: Medium - interesting but not critical

7. **Performance Indicators** (Week 4)
   - Enables: Complexity hypotheses
   - Value: Low - nice to have

---

## Success Metrics

Each extraction pattern should enable:
1. **Hypothesis Generation**: At least 3 hypothesis types per pattern
2. **Experiment Design**: Clear test cases for each hypothesis
3. **Validation Rate**: >70% of generated hypotheses should be testable

## Testing Requirements

For each new extraction pattern:
1. Create a test file with 10+ examples of the pattern
2. Verify extraction captures all instances
3. Generate hypotheses from extracted patterns
4. Design and run experiments to validate hypotheses
5. Achieve >70% validation rate

---

## What NOT to Focus On

These are already adequate or low value:
- Simple function definitions
- Basic imports
- Type annotations (unless runtime behavior)
- Comments and docstrings
- Formatting and style
- Simple variable assignments

---

## The End Goal

With these extractions, DIEC can generate hypotheses like:
- "This function modifies instance state" → Test by checking object before/after
- "This function has side effects on files" → Test by monitoring filesystem
- "This function only executes in production mode" → Test with different configs
- "This function has O(n²) complexity" → Test with varying input sizes
- "This function can raise ValueError" → Test with invalid inputs

Each hypothesis becomes an experiment, each experiment produces knowledge, and knowledge drives understanding.

The extraction layer is not about parsing syntax - it's about recognizing patterns that suggest causal relationships worth testing.