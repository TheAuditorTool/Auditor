# Python Coverage Fix - Missing Extractors for Complete Language Support

## Executive Summary

After reviewing the new retrofit layer implementation, we have ~85% coverage of Python patterns. This document defines the **exact extractors needed** to reach 100% coverage for DIEC's causal learning capabilities.

## Critical Missing Extractors (Must Implement)

### 1. Loop Patterns Extractor (HIGHEST PRIORITY - Curriculum Blocker)

**File:** `diec/engines/librarian/ast/python/loop_extractors.py` (NEW)

```python
def extract_loop_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """
    Extract all loop structures for causal hypothesis generation.

    Returns:
    [
        {
            'line': int,
            'loop_type': 'for' | 'while',
            'iteration_var': 'i' | None,  # None for while loops
            'iteration_source': 'range(10)' | 'items' | 'condition',
            'has_break': bool,
            'has_continue': bool,
            'has_else': bool,  # for/while...else clause
            'nesting_level': int,  # 1 = top-level, 2+ = nested
            'in_function': str | None,
            'is_async': bool,  # async for
            'is_infinite': bool,  # while True pattern detection
        }
    ]
    """
```

**Test Cases to Handle:**
```python
# Basic for loop
for i in range(10):
    print(i)

# For with enumerate
for idx, val in enumerate(items):
    process(idx, val)

# While loop with break
while condition:
    if done:
        break
    process()

# Nested loops (O(n²) pattern)
for i in range(n):
    for j in range(m):
        matrix[i][j] = compute()

# For...else pattern
for item in items:
    if target == item:
        break
else:
    raise NotFound()

# List comprehension (also a loop!)
[x*2 for x in range(10)]

# Async for
async for msg in stream:
    await process(msg)
```

### 2. Conditional Execution Extractor

**File:** `diec/engines/librarian/ast/python/control_flow_extractors.py` (NEW)

```python
def extract_conditional_execution(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """
    Extract if/elif/else patterns and conditional execution context.

    Returns:
    [
        {
            'line': int,
            'condition_type': 'if' | 'elif' | 'else',
            'condition': 'x > 0' | None,  # None for else
            'is_guard_clause': bool,  # Early return pattern
            'has_elif': bool,
            'has_else': bool,
            'nesting_level': int,
            'in_function': str | None,
            'in_loop': bool,
            'contains_return': bool,
            'contains_raise': bool,
            'is_ternary': bool,  # x if cond else y
        }
    ]
```

**Test Cases:**
```python
# Guard clause
def process(x):
    if x is None:
        return  # Guard clause
    do_work(x)

# Complex if/elif/else
if x > 0:
    positive()
elif x < 0:
    negative()
else:
    zero()

# Ternary
result = "pos" if x > 0 else "neg"

# Nested conditionals
if outer:
    if inner:
        deep_work()
```

### 3. Import Patterns Extractor (Enhanced)

**File:** Update existing `core_extractors.py` OR create `import_pattern_extractors.py`

```python
def extract_import_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """
    Extract advanced import patterns beyond basic imports.

    Returns:
    [
        {
            'line': int,
            'import_type': 'absolute' | 'relative',
            'module': 'os.path' | '.utils' | '..parent',
            'names': ['func1', 'func2'] | ['*'],  # Star import
            'is_star_import': bool,
            'is_lazy_import': bool,  # Import inside function
            'is_conditional': bool,  # Import in if/try block
            'is_circular_risk': bool,  # Import at bottom of file
            'relative_level': 0 | 1 | 2,  # Number of dots
            'in_function': str | None,
            'in_try_block': bool,
        }
    ]
```

**Test Cases:**
```python
# Star import (dangerous)
from module import *

# Relative imports
from . import sibling
from ..parent import something
from ...grandparent import other

# Lazy import (performance pattern)
def process():
    import heavy_module  # Only imported when needed
    return heavy_module.compute()

# Conditional import (compatibility pattern)
try:
    import numpy as np
except ImportError:
    np = None

# Circular import prevention
def get_model():
    from .models import User  # Import at use point
    return User
```

### 4. String Formatting Extractor (Already exists but not wired!)

**Action Required:** The extractor exists in `fundamental_extractors.py` but is NOT imported in `__init__.py`

**Add to** `diec/engines/librarian/ast/python/__init__.py`:
```python
from .fundamental_extractors import (
    # ... existing imports ...
    extract_string_formatting,  # ADD THIS!
)

# Also add to __all__ list:
__all__ = [
    # ... existing ...
    'extract_string_formatting',  # ADD THIS!
]
```

### 5. Match Statement Extractor (Python 3.10+)

**File:** `diec/engines/librarian/ast/python/match_extractors.py` (NEW)

```python
def extract_match_statements(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """
    Extract Python 3.10+ match/case pattern matching.

    Returns:
    [
        {
            'line': int,
            'match_subject': 'value',
            'num_cases': int,
            'has_wildcard': bool,  # Has case _:
            'pattern_types': ['literal', 'class', 'sequence', 'mapping'],
            'has_guards': bool,  # case x if condition:
            'in_function': str | None,
        }
    ]
    """
```

**Test Cases:**
```python
match command:
    case ["quit"]:
        exit()
    case ["load", filename]:
        load_file(filename)
    case ["save", filename] if filename.endswith(".json"):
        save_json(filename)
    case _:
        print("Unknown command")
```

## Integration Fixes Required

### 1. Wire New Extractors into `__init__.py`

**File:** `diec/engines/librarian/ast/python/__init__.py`

Add these imports:
```python
# Add to imports section
from .state_mutation_extractors import (
    extract_instance_mutations,
    extract_class_mutations,
    extract_global_mutations,
    extract_argument_mutations,
    extract_augmented_assignments,
)

from .exception_flow_extractors import (
    extract_exception_raises,
    extract_exception_handlers,
    extract_finally_blocks,
    extract_context_managers,
)

from .behavioral_extractors import (
    extract_recursion_patterns,
    extract_generator_yields,
    extract_property_patterns,
    extract_dynamic_attributes,
)

from .performance_extractors import (
    extract_loop_complexity,
    extract_recursive_patterns,
    extract_algorithm_patterns,
)

from .fundamental_extractors import (
    extract_comprehensions,
    extract_lambda_functions,
    extract_slice_operations,
    extract_tuple_operations,
    extract_unpacking_patterns,
    extract_none_patterns,
    extract_truthiness_patterns,
    extract_string_formatting,  # This one exists but not imported!
)

from .operator_extractors import (
    extract_operators,
    extract_membership_tests,
    extract_chained_comparisons,
    extract_ternary_expressions,
    extract_walrus_operators,
    extract_matrix_multiplication,
)

# NEW extractors once created:
from .loop_extractors import (
    extract_loop_patterns,
)

from .control_flow_extractors import (
    extract_conditional_execution,
)

from .import_pattern_extractors import (
    extract_import_patterns,
)

from .match_extractors import (
    extract_match_statements,
)
```

Add to `__all__` export list:
```python
__all__ = [
    # ... existing exports ...

    # State mutations
    'extract_instance_mutations',
    'extract_class_mutations',
    'extract_global_mutations',
    'extract_argument_mutations',
    'extract_augmented_assignments',

    # Exception flow
    'extract_exception_raises',
    'extract_exception_handlers',
    'extract_finally_blocks',

    # Behavioral
    'extract_recursion_patterns',
    'extract_generator_yields',
    'extract_property_patterns',
    'extract_dynamic_attributes',

    # Performance
    'extract_loop_complexity',
    'extract_algorithm_patterns',

    # Fundamental (add missing ones)
    'extract_comprehensions',
    'extract_lambda_functions',
    'extract_slice_operations',
    'extract_tuple_operations',
    'extract_unpacking_patterns',
    'extract_none_patterns',
    'extract_truthiness_patterns',
    'extract_string_formatting',

    # Operators
    'extract_operators',
    'extract_membership_tests',
    'extract_chained_comparisons',
    'extract_ternary_expressions',
    'extract_walrus_operators',
    'extract_matrix_multiplication',

    # NEW
    'extract_loop_patterns',
    'extract_conditional_execution',
    'extract_import_patterns',
    'extract_match_statements',
]
```

### 2. Create Missing Retrofit Handlers

For each new extractor, create a corresponding retrofit handler:

**File:** `diec/engines/librarian/ast/retrofits/loops.py` (NEW)
```python
@register_retrofit('loops')
class LoopRetrofit(BaseRetrofit):
    def process(self, filepath: str, extracted_data: Dict[str, Any]) -> Tuple[List[CKGNode], List[CKGEdge]]:
        # Convert loop patterns to CONCEPT nodes
        # Link to containing FUNCTION nodes
        # Create CONTAINS edges
```

**File:** `diec/engines/librarian/ast/retrofits/control_flow.py` (NEW)
```python
@register_retrofit('control_flow')
class ControlFlowRetrofit(BaseRetrofit):
    def process(self, filepath: str, extracted_data: Dict[str, Any]) -> Tuple[List[CKGNode], List[CKGEdge]]:
        # Convert conditionals to CONTROL_FLOW nodes
        # Track guard clauses as EARLY_RETURN edges
```

## Testing Requirements

For each new extractor, create tests:

**File:** `tests/EXTRACTION/test_loops.py`
```python
def test_for_loops():
    code = """
    for i in range(10):
        print(i)
    """
    data = extract_loop_patterns({"tree": ast.parse(code)}, None)
    assert len(data) == 1
    assert data[0]['loop_type'] == 'for'
    assert data[0]['iteration_var'] == 'i'
```

**File:** `tests/EXTRACTION/test_control_flow.py`
```python
def test_guard_clause():
    code = """
    def process(x):
        if x is None:
            return
        work(x)
    """
    data = extract_conditional_execution({"tree": ast.parse(code)}, None)
    assert any(d['is_guard_clause'] for d in data)
```

## Hypothesis Generation Impact

With these extractors, DIEC can generate new hypothesis types:

### From Loop Patterns:
- "This loop is infinite" → Test with timeout
- "This loop has O(n²) complexity" → Test with varying sizes
- "This loop modifies its iteration source" → Test for bugs

### From Conditionals:
- "This function has guard clauses" → Test with None/invalid inputs
- "This branch is never taken" → Coverage testing
- "These conditions are mutually exclusive" → Logic validation

### From Import Patterns:
- "This has circular import risk" → Test import order
- "This uses star imports" → Namespace pollution testing
- "This has lazy imports" → Performance testing

### From String Formatting:
- "This f-string has expressions" → Security testing
- "This uses % formatting" → Python 2 compatibility

## Implementation Priority

1. **Week 1 - Critical for Curriculum:**
   - `extract_loop_patterns` (curriculum chapters 5-6)
   - `extract_conditional_execution` (basic control flow)
   - Fix `extract_string_formatting` import

2. **Week 2 - Enhanced Patterns:**
   - `extract_import_patterns` (security/performance)
   - `extract_match_statements` (modern Python)
   - Integration fixes in `__init__.py`

3. **Week 3 - Testing:**
   - Test all extractors
   - Verify retrofit handlers
   - Run on curriculum code

## Success Metrics

- [ ] All 5 missing extractors implemented
- [ ] All extractors imported in `__init__.py`
- [ ] All extractors in `__all__` export list
- [ ] Retrofit handlers for new extractors
- [ ] Tests achieving >90% coverage
- [ ] Successfully extract from Python curriculum
- [ ] Generate 200+ new hypotheses from patterns

## File Checklist

**New Files to Create:**
- [ ] `loop_extractors.py`
- [ ] `control_flow_extractors.py`
- [ ] `import_pattern_extractors.py` (or update core_extractors.py)
- [ ] `match_extractors.py`
- [ ] `retrofits/loops.py`
- [ ] `retrofits/control_flow.py`
- [ ] `tests/EXTRACTION/test_loops.py`
- [ ] `tests/EXTRACTION/test_control_flow.py`

**Files to Update:**
- [ ] `python/__init__.py` - Add all imports and exports
- [ ] `retrofits/__init__.py` - Register new retrofits

## Notes

- The `extract_loop_complexity` in `performance_extractors.py` focuses on complexity analysis, not basic loop structure. We need both.
- Many extractors exist but aren't wired into `__init__.py` - this is preventing them from being used!
- The retrofit layer architecture is excellent - maintain the same pattern for new extractors
- Keep validation logic inline per DIEC architecture requirements

With these additions, DIEC will have 100% Python language coverage for causal hypothesis generation and experimental validation.