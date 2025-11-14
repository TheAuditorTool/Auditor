# Python Coverage V2: Design Document

**Version**: 1.0
**Date**: 2025-11-14
**Status**: DRAFT

---

## Context

python_coverage_v2.md identifies 90 missing Python patterns across fundamentals, operators, collections, and advanced features. The causal-learning extractors (already implemented) cover behavioral patterns but leave language fundamentals unextracted.

**Current Architecture** (verified 2025-11-14):
```
Layer 1: AST Extractors → 18 modules, ~100 extractors
Layer 2: Orchestrator → python.py calls extractors
Layer 3: Schema → python_schema.py defines 79 tables
Layer 4: Storage → python_database.py + python_storage.py write to SQLite
```

**Key Constraints**:
- Maintain <10ms per file extraction
- Zero conflicts with existing extractors
- Single-pass AST walking for performance
- Database regenerated fresh every `aud full`
- Follow existing 4-layer wiring pattern

---

## Goals / Non-Goals

### Goals
1. Extract all 90 patterns from python_coverage_v2.md
2. Create 5 new extractor modules with clear separation
3. Add 45 new database tables
4. Maintain extraction performance
5. Enable comprehensive Python curriculum development
6. Achieve 100% language coverage for static analysis

### Non-Goals
1. **NOT** refactoring existing extractors
2. **NOT** modifying causal-learning extractors
3. **NOT** adding Python 2.x support
4. **NOT** implementing runtime analysis
5. **NOT** creating duplicate extractors

---

## Architectural Decisions

### Decision 1: Five-Module Architecture (Domain-Based Organization)

**Context**: 90 patterns need logical grouping without creating monolithic files or too many small modules.

**Options Considered**:
1. **Single Module**: One python_complete_extractors.py with all 90 patterns
2. **Pattern-Per-Module**: 90 separate modules (one per pattern)
3. **Week-Based Modules**: 4 modules matching implementation weeks
4. **Domain-Based Modules**: 5 modules by conceptual domain
5. **Size-Based Modules**: Split when reaching 1000 lines

**Decision**: Option 4 (Domain-Based Modules)

**Rationale**:
- Logical cohesion (comprehensions with lambdas, operators together)
- Balanced file sizes (600-1200 lines each)
- Clear naming prevents conflicts with existing modules
- Easy to find specific extractors
- Maintainable long-term

**Module Design**:
```
fundamental_extractors.py   - Core language constructs
operator_extractors.py      - All operator types
collection_extractors.py    - Collection methods and operations
class_feature_extractors.py - Advanced class features
stdlib_pattern_extractors.py - Standard library usage patterns
```

**Trade-offs**:
- (+) Clear organization and findability
- (+) No naming conflicts with existing modules
- (+) Balanced file sizes
- (-) Some patterns could fit multiple modules
- (-) Need clear documentation of what's where

---

### Decision 2: Single-Pass AST Walking (Performance Critical)

**Context**: Adding 90 extractors risks 90x AST walks, destroying performance.

**Options Considered**:
1. **Naive Multi-Pass**: Each extractor walks AST independently
2. **Single-Pass Dispatch**: One walk, dispatch to all extractors
3. **Cached AST**: Walk once, cache results, extractors query cache
4. **Lazy Extraction**: Only extract when queried
5. **Parallel Walking**: Multi-threaded extraction

**Decision**: Option 2 (Single-Pass Dispatch)

**Rationale**:
- Proven pattern (JavaScript extractors use this)
- 40-60% performance improvement expected
- Simpler than caching or parallelization
- Maintains extraction atomicity

**Implementation Pattern**:
```python
def extract_all_patterns(tree: Dict, parser_self) -> Dict[str, List]:
    """Single-pass extraction dispatching to multiple extractors."""
    results = {
        'comprehensions': [],
        'lambda_functions': [],
        'operators': [],
        # ... all pattern types
    }

    actual_tree = tree.get("tree")
    context = ExtractionContext()  # Shared context

    for node in ast.walk(actual_tree):
        # Dispatch by node type
        if isinstance(node, ast.ListComp):
            _extract_list_comp(node, context, results['comprehensions'])
        elif isinstance(node, ast.Lambda):
            _extract_lambda(node, context, results['lambda_functions'])
        elif isinstance(node, ast.BinOp):
            _extract_operator(node, context, results['operators'])
        # ... dispatch to all patterns

    return results
```

**Trade-offs**:
- (+) Massive performance improvement
- (+) Single source of truth for context
- (+) Easier debugging (one traversal)
- (-) More complex extractor code
- (-) Harder to test individual patterns

---

### Decision 3: Pattern Completeness Over Perfection

**Context**: Some patterns have edge cases that require runtime analysis (dynamic attributes, eval, computed values).

**Options Considered**:
1. **Skip Dynamic Patterns**: Only extract statically analyzable patterns
2. **Best Effort Extraction**: Extract what's visible, flag limitations
3. **Hybrid Analysis**: Limited runtime probing for dynamic patterns
4. **Require Type Hints**: Only extract typed code accurately
5. **Conservative Extraction**: Only extract with 100% confidence

**Decision**: Option 2 (Best Effort Extraction)

**Rationale**:
- Better to have partial data than no data
- Flags allow consumers to handle uncertainty
- Aligns with existing extractor patterns
- Enables future enhancement

**Implementation Pattern**:
```python
{
    'line': 42,
    'pattern': 'dict_method',
    'method': 'get',
    'target': 'config',  # Variable name if static
    'key': None,  # Key if dynamic
    'is_static': False,  # Flag dynamic patterns
    'confidence': 0.7,  # Confidence score
}
```

**Trade-offs**:
- (+) Maximum pattern coverage
- (+) Transparent about limitations
- (+) Enables incremental improvement
- (-) Some false positives possible
- (-) Requires careful documentation

---

### Decision 4: Granular Table Design (Normalized Schema)

**Context**: 45 new tables vs fewer consolidated tables.

**Options Considered**:
1. **One Table Per Pattern**: 90 separate tables
2. **Module-Based Tables**: 5 tables (one per module)
3. **Granular Normalized**: 45 tables with specific schemas
4. **Single Patterns Table**: One table with JSON data
5. **Hybrid**: Mix of granular and consolidated

**Decision**: Option 3 (Granular Normalized)

**Rationale**:
- Efficient querying of specific patterns
- Type-safe schemas
- Consistent with existing architecture
- Enables pattern-specific indexes

**Example Tables**:
```sql
-- Specific schema for each pattern type
CREATE TABLE python_comprehensions (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    comp_type TEXT NOT NULL,
    result_expr TEXT,
    iteration_var TEXT,
    has_filter BOOLEAN,
    PRIMARY KEY (file, line)
);

CREATE TABLE python_operators (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    operator_type TEXT NOT NULL,
    operator TEXT NOT NULL,
    in_function TEXT,
    PRIMARY KEY (file, line, operator)
);
```

**Trade-offs**:
- (+) Optimal query performance
- (+) Clear schemas
- (+) Type safety
- (-) More tables to manage
- (-) Potential redundancy

---

### Decision 5: Incremental Integration (Weekly Milestones)

**Context**: 4-week implementation needs clear checkpoints.

**Options Considered**:
1. **Big Bang**: Implement all, integrate at end
2. **Weekly Integration**: Wire each week's work immediately
3. **Module Integration**: Wire when module complete
4. **Pattern Integration**: Wire each pattern as completed
5. **Two-Phase**: All extraction first, then integration

**Decision**: Option 2 (Weekly Integration)

**Rationale**:
- Early validation of approach
- Incremental risk reduction
- Allows course correction
- Maintains momentum

**Integration Points**:
- Week 1 End: fundamental_extractors wired and tested
- Week 2 End: operator_extractors integrated
- Week 3 End: collection_extractors operational
- Week 4 End: All modules complete and tested

**Trade-offs**:
- (+) Early feedback
- (+) Reduced integration risk
- (+) Demonstrable progress
- (-) More integration overhead
- (-) Potential rework if design changes

---

## Implementation Patterns

### Pattern 1: Extractor Module Structure

```python
"""Module docstring following ARCHITECTURAL CONTRACT pattern.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts
"""

import ast
from typing import Dict, List, Any, Optional
from ..base import get_node_name

# ============================================================================
# Helper Functions
# ============================================================================

def _get_context(node: ast.AST) -> Dict:
    """Get extraction context for node."""
    # ... implementation

# ============================================================================
# Main Extractors
# ============================================================================

def extract_pattern_name(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract pattern_name from AST.

    Patterns detected:
    - Pattern 1 description
    - Pattern 2 description

    Args:
        tree: AST tree dictionary with 'tree' key
        parser_self: Parser instance (unused but required)

    Returns:
        List of pattern dictionaries
    """
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return []

    results = []
    # ... extraction logic
    return results
```

### Pattern 2: Wiring to Pipeline

```python
# Step 1: python.py imports
from theauditor.ast_extractors.python import (
    # ... existing imports
    fundamental_extractors,  # NEW
    operator_extractors,     # NEW
)

# Step 2: python.py result dictionary
result = {
    # ... existing keys
    'python_comprehensions': [],     # NEW
    'python_lambda_functions': [],   # NEW
    'python_operators': [],          # NEW
}

# Step 3: python.py extractor calls
if tree and isinstance(tree, dict):
    # ... existing calls

    # Fundamental patterns
    comprehensions = fundamental_extractors.extract_comprehensions(tree, self.ast_parser)
    if comprehensions:
        result['python_comprehensions'].extend(comprehensions)

# Step 4: Schema definition
PYTHON_COMPREHENSIONS = TableSchema(
    name="python_comprehensions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("comp_type", "TEXT", nullable=False),
        # ... other columns
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_python_comp_file", ["file"]),
        ("idx_python_comp_type", ["comp_type"]),
    ]
)
```

### Pattern 3: Testing Strategy

```python
# tests/fixtures/python/fundamentals.py
"""Test fixture for fundamental patterns."""

# Comprehensions
list_comp = [x * 2 for x in range(10)]
dict_comp = {k: v for k, v in items.items()}
set_comp = {x for x in numbers if x > 0}
gen_comp = (x for x in data)

# Nested comprehension
matrix = [[i * j for j in range(3)] for i in range(3)]

# Lambda functions
simple_lambda = lambda x: x + 1
multi_param = lambda x, y: x * y
with_closure = lambda x: x + outer_var

# Verification test
def test_comprehensions():
    tree = parse_fixture('fundamentals.py')
    results = extract_comprehensions(tree, None)
    assert len(results) == 5  # Including nested
    assert results[0]['comp_type'] == 'list'
```

---

## Performance Considerations

### Benchmarks

Current baseline (existing extractors):
- Small file (<100 lines): 2-5ms
- Medium file (100-500 lines): 5-10ms
- Large file (>500 lines): 10-50ms

Target with 90 new extractors:
- Small file: 3-6ms (20% increase acceptable)
- Medium file: 7-12ms (20% increase acceptable)
- Large file: 12-60ms (20% increase acceptable)

### Optimization Strategies

1. **Single-pass AST walking** (40% improvement)
2. **Node type dispatch dictionary** (10% improvement)
3. **Early filtering by node type** (15% improvement)
4. **Lazy string formatting** (5% improvement)
5. **Result deduplication** (10% improvement)

### Memory Management

- Maximum memory per file: 10MB
- Result size limits: 1000 items per pattern type
- String truncation: 500 chars for expressions
- Circular reference detection

---

## Risk Mitigation

### Performance Risks
- **Mitigation**: Continuous profiling after each module
- **Trigger**: >20% slowdown triggers optimization sprint
- **Fallback**: Defer less critical patterns

### Integration Risks
- **Mitigation**: Integration tests after each extractor
- **Trigger**: Failed integration triggers immediate fix
- **Fallback**: Isolated module development

### Data Quality Risks
- **Mitigation**: Comprehensive test fixtures
- **Trigger**: <90% accuracy triggers pattern review
- **Fallback**: Conservative extraction mode

---

## Open Questions

1. **Should we combine similar tables?**
   - Current: Separate tables for each pattern
   - Alternative: Combine operators into one table
   - **Decision**: Keep separate for query optimization

2. **How to handle Python 3.10+ patterns?**
   - Current: Extract if AST supports
   - Alternative: Version-specific extractors
   - **Decision**: Extract all, flag version requirements

3. **Should we extract docstring patterns?**
   - Current: No docstring extraction
   - Alternative: Extract parameter/return hints from docstrings
   - **Decision**: Defer to future PR

---

**END OF DESIGN DOCUMENT**

**Next**: Create tasks.md with detailed task breakdown