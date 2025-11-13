# Causal Learning Foundation: Design Document

**Version**: 1.0
**Date**: 2025-11-13
**Status**: DRAFT

---

## Context

python_coverage.md identifies 5 priority levels of behavioral patterns needed for causal learning. Current TheAuditor extraction focuses on security (OWASP Top 10, taint analysis) but lacks patterns for hypothesis generation (side effects, exception flows, behavioral characteristics).

**Current Architecture** (verified 2025-11-13):
```
Layer 1: AST Extractors → 13 modules, 75+ extractors
Layer 2: Indexer → extractors/python.py orchestrates
Layer 3: Storage → storage.py handles result types
Layer 4: Database → python_database.py writes to tables
Layer 5: Schema → python_schema.py defines 59 tables
```

**Constraints**:
- Maintain <10ms per file extraction (current benchmark: 2-7 files/sec)
- Zero regressions on existing extractors
- Memory usage <500MB peak
- Database regenerated fresh every `aud index` (no migrations)
- **NEW CONSTRAINT**: Enable >70% hypothesis validation rate in DIEC tool

---

## Goals / Non-Goals

### Goals
1. Enable causal hypothesis generation for DIEC tool (side effects, exceptions, data flow, behavior, performance)
2. Extract 5 priority levels from python_coverage.md in 4 weeks
3. Add 28 new database tables (59 → 87 tables)
4. Extract 8,500+ new records from TheAuditor
5. Maintain extraction performance (<10ms per file)
6. **PRIMARY GOAL**: Achieve >70% hypothesis validation rate

### Non-Goals
1. **NOT** refactoring existing extractors (leave Phase 3 work alone)
2. **NOT** adding every possible Python pattern (only patterns that enable hypotheses)
3. **NOT** perfect data flow analysis (start with single-file, defer cross-file)
4. **NOT** runtime behavior tracking (static analysis only)
5. **NOT** Python 2.7 support (<3.11 not supported)

---

## Architectural Decisions

### Decision 1: Five-Module Architecture (Priority-Based Organization)

**Context**: python_coverage.md defines 5 priority levels with distinct purposes (side effects, exceptions, data flow, behavior, performance).

**Options Considered**:
1. **Single Monolithic Module**: One causal_extractors.py with all 20 functions
2. **Pattern-Based Modules**: Group by pattern type (mutations, flows, loops)
3. **Priority-Based Modules**: One module per python_coverage.md priority level
4. **Behavior-Based Modules**: Group by what hypothesis they enable

**Decision**: Option 3 (Priority-Based Modules)

**Rationale**:
- Directly maps to python_coverage.md priorities (1:1 traceability)
- Clear implementation order (Week 1 = Priority 1, Week 2 = Priority 3, etc.)
- Each module has cohesive purpose (state mutations vs data flow vs performance)
- Can deploy incrementally (Week 1 extractors work without Week 2)
- Easy to measure success (did Week 1 enable side effect hypotheses?)

**Module Structure**:
```
theauditor/ast_extractors/python/
├── state_mutation_extractors.py     (Priority 1, Week 1, ~800 lines)
│   Purpose: Detect side effects (instance, class, global, argument mutations)
│   Enables: "Function X modifies state Y" hypotheses
│
├── exception_flow_extractors.py     (Priority 1, Week 1, ~600 lines)
│   Purpose: Track error handling (raises, catches, finally, context managers)
│   Enables: "Function X raises Y when Z" hypotheses
│
├── data_flow_extractors.py          (Priority 3, Week 2, ~800 lines)
│   Purpose: Trace data movement (I/O, param→return, closures, nonlocal)
│   Enables: "Function X depends on Y" and "Function X performs I/O" hypotheses
│
├── behavioral_extractors.py         (Priority 4, Week 3, ~700 lines)
│   Purpose: Detect algorithm characteristics (recursion, generators, properties)
│   Enables: "Function X uses recursion" hypotheses
│
└── performance_extractors.py        (Priority 5, Week 4, ~600 lines)
    Purpose: Identify complexity indicators (nested loops, resource usage)
    Enables: "Function X has O(n²) complexity" hypotheses
```

**Trade-offs**:
- (+) Clear priority mapping (easy to understand)
- (+) Incremental deployment (can stop after Week 2 if needed)
- (+) Hypothesis-driven organization (each module serves specific hypothesis types)
- (-) Some overlap (augmented assignments relevant to both state mutations and performance)
- (-) Priority 2 (Control Flow) merged with Priority 1 (exception flow is control flow)

**Implementation**:
- Week 1 implements Priorities 1+2 (side effects + exceptions)
- Week 2 implements Priority 3 (data flow)
- Week 3 implements Priority 4 (behavioral)
- Week 4 implements Priority 5 (performance)
- Priority ordering matches python_coverage.md exactly

---

### Decision 2: Hypothesis-First Design (Extraction Serves Causal Learning)

**Context**: python_coverage.md is explicit: "Extraction layer is not about parsing syntax - it's about recognizing patterns that suggest causal relationships worth testing."

**Options Considered**:
1. **Syntax-First**: Extract all AST patterns, hope they're useful for hypotheses
2. **Security-First**: Extract patterns useful for OWASP Top 10 detection
3. **Hypothesis-First**: Extract ONLY patterns that enable specific hypothesis types
4. **Completeness-First**: Extract everything Python offers (100% coverage)

**Decision**: Option 3 (Hypothesis-First)

**Rationale**:
- python_coverage.md defines 5 hypothesis categories explicitly
- Each extractor MUST enable ≥3 hypothesis types (per success metrics)
- No extraction without clear hypothesis generation path
- Avoids "nice to have" extractions that don't serve causal learning
- Focuses effort on high-value patterns (side effects, not comments)

**Design Pattern**:
Every extractor function follows this contract:
```python
def extract_X(tree, parser_self) -> List[Dict]:
    """Extract pattern X to enable hypothesis Y.

    Detects:
    - [List of specific patterns detected]

    Returns:
    {
        [Fields optimized for hypothesis generation]
    }

    Enables hypothesis: "[Specific hypothesis format]"
    Experiment design: [How to test this hypothesis]
    """
```

**Example**:
```python
def extract_instance_mutations(tree, parser_self) -> List[Dict]:
    """Extract self.x = value patterns (instance attribute mutations).

    Enables hypothesis: "Function X modifies instance attribute Y"
    Experiment design: Call X, check object.Y before/after
    """
```

**Trade-offs**:
- (+) Every extraction has clear value proposition
- (+) Prioritizes high-value patterns (side effects over syntax sugar)
- (+) Avoids scope creep (only extract what enables hypotheses)
- (-) May miss patterns useful for future hypothesis types
- (-) Requires upfront hypothesis design (can't "extract first, figure out use later")

**Mitigation**:
- Document "deferred patterns" that might enable future hypotheses
- Revisit after Week 4 if validation rate < 70%

---

### Decision 3: Context-Aware Extraction (Expected vs Unexpected Mutations)

**Context**: Not all state mutations are equal. `self.count = 0` in `__init__` is expected. `self.count = 0` in `calculate_sum()` is unexpected (side effect).

**Options Considered**:
1. **Naive Extraction**: Extract all `self.x = value` equally
2. **Filter in Extractor**: Skip `__init__` mutations entirely
3. **Context-Aware Extraction**: Extract all, flag context (`is_init`, `is_property_setter`)
4. **Post-Processing**: Extract all, filter during hypothesis generation

**Decision**: Option 3 (Context-Aware Extraction)

**Rationale**:
- DIEC tool needs to know "this mutation is expected" vs "this mutation is surprising"
- Filtering in extractor loses information (can't undo)
- Filtering in hypothesis generation requires re-reading source (slow)
- Context flags enable intelligent hypothesis generation:
  - `is_init=True` → Don't generate "side effect" hypothesis
  - `is_init=False` → Generate "unexpected state mutation" hypothesis
  - `is_property_setter=True` → Expected mutation (property design pattern)

**Implementation Pattern**:
```python
{
    'line': 42,
    'target': 'self.counter',
    'operation': 'assignment',
    'in_function': 'increment',
    'is_init': False,  # NOT in __init__ → unexpected mutation
    'is_property_setter': False,  # NOT a property setter
    'is_dunder_method': False,  # NOT __setitem__, __enter__, etc.
}
```

**Context Flags**:
- `is_init`: True if mutation occurs in `__init__` method
- `is_property_setter`: True if mutation occurs in `@property.setter`
- `is_dunder_method`: True if in `__enter__`, `__exit__`, `__setitem__`, etc.
- `in_function`: Function name where mutation occurs (for hypothesis specificity)

**Trade-offs**:
- (+) Preserves all information (can filter later)
- (+) Enables intelligent hypothesis generation
- (+) Distinguishes expected (design pattern) from unexpected (side effect)
- (-) Slightly larger database (extra boolean columns)
- (-) More complex extractor logic (need to detect method type)

**Validation**:
- Test with `class Counter: __init__` fixture → verify `is_init=True`
- Test with `class Counter: increment` fixture → verify `is_init=False`

---

### Decision 4: Single-Pass AST Walking (Performance Constraint)

**Context**: Adding 20 new extractors (current: 75 extractors) risks performance degradation. Current extraction is multi-pass (each extractor calls `ast.walk()` separately).

**Options Considered**:
1. **Naive Multi-Pass**: Each new extractor calls `ast.walk()` (25 passes → 95 passes)
2. **Single-Pass Dispatch**: One `ast.walk()`, dispatch to extractors by node type
3. **Lazy Extraction**: Extract on-demand when hypothesis generated (slow DIEC tool)
4. **Parallel Extraction**: Multi-threaded extraction (complex)

**Decision**: Option 2 (Single-Pass Dispatch) **for new extractors only**

**Rationale**:
- Old extractors (Phase 2/3) work fine, don't refactor
- New extractors designed for single-pass from Day 1
- JavaScript extractors already use single-pass pattern
- Expected 40% speedup on new extractions

**Implementation Pattern**:
```python
# CORRECT - Single pass with dispatch
def extract_all_state_mutations(tree, parser_self) -> Dict[str, List]:
    """Single-pass extraction of all state mutation types."""
    results = {
        'instance_mutations': [],
        'class_mutations': [],
        'global_mutations': [],
        'argument_mutations': [],
        'augmented_assignments': [],
    }

    actual_tree = tree.get("tree")
    current_function = "global"
    is_in_init = False

    # Single ast.walk()
    for node in ast.walk(actual_tree):
        # Track function context
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            current_function = node.name
            is_in_init = (node.name == "__init__")

        # Dispatch by node type
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            # self.x = value (instance mutation)
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                results['instance_mutations'].append({
                    'line': node.lineno,
                    'target': f"self.{node.attr}",
                    'in_function': current_function,
                    'is_init': is_in_init,
                })

        elif isinstance(node, ast.AugAssign):
            # x += 1 (augmented assignment)
            target_type = _classify_augment_target(node.target)
            results['augmented_assignments'].append({
                'line': node.lineno,
                'target': ast.unparse(node.target),
                'operator': type(node.op).__name__,
                'target_type': target_type,
                'in_function': current_function,
            })

        # ... dispatch to other mutation types

    return results
```

**Trade-offs**:
- (+) 40% speedup on new extractors (1 pass vs 5 passes)
- (+) Scales to 20 new extractors without slowdown
- (+) Memory efficient (one AST in memory)
- (-) More complex extractor code (dispatch layer + context tracking)
- (-) Harder to debug (all extractors run together)

**Rollout**:
- **Week 1-4**: All new extractors use single-pass pattern
- **Week 5+ (Future)**: Optionally migrate Phase 2/3 extractors to single-pass

**Performance Target**:
- Current: 2-7 files/sec (0.14-0.5s per file)
- Target: 2-10 files/sec (0.1s per file best case, 0.5s acceptable)
- Worst case: No slower than current (<0.5s per file)

---

### Decision 5: Static Analysis Limitations (Flag, Don't Guess)

**Context**: Some patterns are impossible to analyze statically (dynamic `getattr`, `eval`, runtime imports).

**Options Considered**:
1. **Optimistic Extraction**: Guess behavior from static patterns
2. **Skip Dynamic Patterns**: Don't extract if can't be certain
3. **Flag as "Requires Runtime Analysis"**: Extract what's visible, flag limitations
4. **Hybrid**: Extract + run limited runtime probing

**Decision**: Option 3 (Flag as "Requires Runtime Analysis")

**Rationale**:
- DIEC tool performs runtime experiments anyway (can validate dynamic behavior)
- Better to extract partial info + flag than skip entirely
- Honest about limitations (don't mislead hypothesis generation)
- Enables hypothesis: "Function uses dynamic attribute access (requires runtime validation)"

**Implementation Pattern**:
```python
{
    'line': 42,
    'io_type': 'FILE_WRITE',
    'operation': 'open',
    'target': None,  # Target is dynamic (variable)
    'is_static': False,  # Flag: target determined at runtime
    'in_function': 'save_data',
}
```

**Flags**:
- `is_static`: False if target/condition/value determined at runtime
- `requires_runtime_analysis`: True if behavior cannot be proven statically
- `dynamic_pattern`: Type of dynamism (getattr, eval, computed string, etc.)

**Example Cases**:
```python
# STATIC - Can extract fully
with open('log.txt', 'w') as f:  # target='log.txt', is_static=True
    f.write(data)

# DYNAMIC - Flag as runtime-dependent
filename = config.get('log_file')
with open(filename, 'w') as f:  # target=None, is_static=False, requires_runtime_analysis=True
    f.write(data)

# CONDITIONAL - Extract condition if static
if DEBUG:
    log_to_file(data)  # condition='DEBUG', is_static=True (can check DEBUG value)
```

**Trade-offs**:
- (+) Honest about static analysis limitations
- (+) Provides partial info even for dynamic patterns
- (+) Enables "requires validation" hypotheses
- (-) Some hypotheses cannot be generated (need runtime info)
- (-) May confuse users ("why is target=None?")

**Mitigation**:
- Clear documentation in hypothesis metadata
- DIEC tool handles runtime validation automatically

---

### Decision 6: No Mutable Default Detection (Deferred)

**Context**: python_coverage.md mentions "mutable default detection" but it's Priority 2 (TIER 2 gaps) and not critical for causal learning.

**Options Considered**:
1. **Include in Week 1**: Extract `def foo(lst=[])`
2. **Include in Week 4**: Add to performance_extractors.py
3. **Defer**: Not in this proposal (add in future PR)
4. **Skip**: Not valuable for hypothesis generation

**Decision**: Option 3 (Defer to Future PR)

**Rationale**:
- python_coverage.md focuses on Priority 1-5 (side effects, exceptions, data flow, behavior, performance)
- Mutable defaults are a code smell but don't enable unique hypothesis types
- Can be detected by static linters (ruff, pylint) - not unique value
- Limited causal learning value (not runtime behavior, just bad practice)

**Trade-off**:
- (+) Keeps Week 1 focused on high-value patterns
- (+) Reduces scope (stay within 4-week timeline)
- (-) Incomplete coverage of python_coverage.md TIER 2 gaps

**Future Work**:
- Add in Week 5+ if validation rate < 70%
- Or add to existing linter integration (not extraction layer)

---

## Risks / Trade-offs

### Performance Risks

**Risk**: Adding 20 extractors (75 → 95) degrades performance below <10ms target

**Mitigation**:
- Single-pass AST walking for all new extractors (40% speedup expected)
- Profile after each week, optimize hot paths
- Context tracking reuses existing function/class traversal

**Trade-off**: More complex extractor code vs faster extraction

**Contingency**: Defer Priority 5 (performance extractors) if Week 1-3 extractors degrade performance >20%

### False Positive Side Effects

**Risk**: Extracting `self.x = value` in `__init__` generates invalid "side effect" hypotheses

**Mitigation**:
- Context flags: `is_init`, `is_property_setter`, `is_dunder_method`
- Hypothesis generation filters expected mutations
- Documentation: "Expected mutations in design patterns"

**Trade-off**: Larger database (extra boolean columns) vs accurate hypothesis generation

**Contingency**: If false positive rate > 30%, add more context flags or filter in extractor

### Hypothesis Validation Rate < 70%

**Risk**: Extracted patterns don't enable testable hypotheses

**Mitigation**:
- Weekly validation rate checks (end of each week)
- Adjust extractors mid-stream if rate low
- Focus on Priorities 1-3 if Priorities 4-5 don't contribute to rate

**Trade-off**: Flexibility to adjust vs fixed scope

**Contingency**: Stop at Week 2 or 3 if >70% rate achieved early

### Cross-File Data Flow Complexity

**Risk**: Closure captures may reference imported functions, parameter flows may cross files

**Mitigation**:
- Start with single-file patterns (Week 2)
- Defer cross-file to Week 5+ (future PR)
- Flag patterns that need cross-file analysis

**Trade-off**: Limited data flow analysis vs manageable scope

**Contingency**: Document limitations, DIEC tool can perform limited cross-file runtime tracing

---

## Migration Plan

**NO MIGRATION REQUIRED** - All changes are additive.

**Compatibility**:
- Existing 75 extractors continue working unchanged
- Existing 59 tables untouched (new tables added)
- No breaking changes to API or CLI
- Database regenerated fresh every run (no schema migrations)

**Rollback**:
- Each week on separate Git branch (`causal-week1`, etc.)
- Database snapshots before each week
- Can revert to current state anytime

---

## Open Questions

1. **Should we extract mutable default parameters?**
   - Current: Deferred to future PR
   - Alternative: Add to Week 4 (performance extractors)
   - Trade-off: Completeness vs scope
   - **Decision**: Defer (not critical for causal learning)

2. **Should we detect tail recursion specifically?**
   - Current: extract_recursion_patterns() detects recursion type
   - Alternative: Just detect any recursion
   - Trade-off: Specificity vs complexity
   - **Decision**: Detect recursion type (enables "tail call optimization" hypothesis)

3. **Should we track exception propagation across functions?**
   - Current: Single-function exception tracking
   - Alternative: Cross-file exception flow
   - Trade-off: Accuracy vs complexity
   - **Decision**: Defer to Week 5+ (start with single-function)

4. **Should we extract docstring-based contracts?**
   - Current: No docstring extraction
   - Alternative: Parse "@raises", "@param", "@return" annotations
   - Trade-off: Contract validation vs scope
   - **Decision**: Defer (python_coverage.md explicitly excludes docstrings)

5. **Should we integrate with existing CFG extraction?**
   - Current: state_mutation_extractors.py standalone
   - Alternative: Extend cfg_extractor.py
   - Trade-off: Integration vs independence
   - **Decision**: Standalone (CFG is for control flow, this is for side effects)

---

**END OF DESIGN DOCUMENT**

**Next**: Create tasks.md with atomic task breakdown for each week
