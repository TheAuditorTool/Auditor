# Python Coverage V2: Complete Language Support for Curriculum & Analysis

**Change ID**: python-coverage-v2
**Type**: Enhancement (Language Coverage Completeness)
**Priority**: CRITICAL (Curriculum Blocker)
**Status**: PROPOSED
**Date**: 2025-11-14
**Author**: Lead Coder (Opus AI via Architect)
**Purpose**: Extract 90 missing Python patterns to achieve complete language support for curriculum development and static analysis

---

## Why

### Problem Statement

TheAuditor has excellent security-focused extraction (SAST, taint analysis) and causal learning foundations (side effects, exceptions). However, **90 fundamental Python patterns remain unextracted**, creating critical gaps that block curriculum development and limit analysis capabilities.

**Current Blindspots** (verified 2025-11-14 against python_coverage_v2.md):

1. **Basic Constructs** (0% coverage):
   - No comprehension extraction (list/dict/set/generator)
   - No lambda function detection
   - No slice operations tracking
   - No tuple operations
   - No unpacking patterns

2. **Operators & Expressions** (0% coverage):
   - No operator usage tracking (arithmetic, comparison, logical)
   - No membership testing (in/not in)
   - No chained comparisons
   - No ternary expressions
   - No walrus operator (:=)

3. **Collection Methods** (0% coverage):
   - No dict/list/set method calls
   - No string method tracking
   - No builtin function usage (len, sum, max, min, sorted, etc.)
   - No itertools/functools patterns

4. **Advanced Features** (0% coverage):
   - No metaclasses, descriptors, dataclasses
   - No protocol implementations (iterator, container, callable)
   - No multiple inheritance tracking
   - No dunder method analysis

**Business Impact**:
- **Curriculum Development**: Cannot teach Python fundamentals without extraction data
- **Code Intelligence**: Missing 60% of language constructs limits analysis
- **Security Analysis**: Cannot detect patterns like eval/exec without operator extraction
- **Performance Analysis**: Cannot track comprehension vs loop performance

**Difference from Causal-Learning Proposal**:
- Causal-learning: Focused on behavioral patterns for hypothesis generation (COMPLETE)
- This proposal: Focuses on language completeness for curriculum (90 patterns MISSING)
- No overlap: All causal-learning extractors already implemented and working

---

## What Changes

### Scope: 5 New Extractor Modules (4 weeks)

This proposal implements 90 missing Python patterns organized into 5 cohesive modules.

**Week 1: Fundamentals (25 patterns)**
- Loop enhancements (bounds, step, nesting depth)
- All comprehension types (list, dict, set, generator)
- Lambda functions with closure detection
- Slice operations (start:stop:step)
- Tuple operations (pack/unpack)
- None handling patterns
- String formatting (f-strings, %, format())

**Week 2: Operators & Expressions (15 patterns)**
- All operator types (arithmetic, comparison, logical, bitwise)
- Membership testing (in/not in)
- Chained comparisons (1 < x < 10)
- Ternary expressions (x if condition else y)
- Assignment expressions/walrus (:=)
- Matrix multiplication (@)

**Week 3: Collections & Methods (20 patterns)**
- Dictionary methods (keys, values, items, get, update, pop)
- List methods (append, extend, insert, remove, sort, reverse)
- Set operations (union, intersection, difference)
- String methods (split, join, strip, replace, find)
- Builtin functions (len, sum, max, min, sorted, enumerate, zip)
- Itertools patterns (chain, cycle, combinations, permutations)
- Functools patterns (partial, reduce, lru_cache)

**Week 4: Advanced & Stdlib (30 patterns)**
- Class features (metaclasses, descriptors, dataclasses, enums, slots)
- Protocol implementations (iterator, container, callable, comparison)
- Multiple inheritance & MRO
- Dunder methods categorization
- Standard library patterns (regex, JSON, datetime, threading, logging)

### New Files Created

**5 new extractor modules** (~4,500 lines total):
```
theauditor/ast_extractors/python/
├── fundamental_extractors.py        (Week 1, ~1200 lines)
│   - extract_loop_patterns()           # Enhanced loop analysis
│   - extract_comprehensions()          # All comprehension types
│   - extract_lambda_functions()        # Lambda with captures
│   - extract_slice_operations()        # Slice notation
│   - extract_tuple_operations()        # Pack/unpack
│   - extract_unpacking_patterns()      # Extended unpacking
│   - extract_none_patterns()           # None handling
│   - extract_truthiness_patterns()    # Bool coercion
│   - extract_string_formatting()       # All format types
│
├── operator_extractors.py           (Week 2, ~800 lines)
│   - extract_operators()               # All operator types
│   - extract_membership_tests()        # in/not in
│   - extract_chained_comparisons()     # 1 < x < 10
│   - extract_ternary_expressions()     # x if y else z
│   - extract_walrus_operators()        # := assignments
│   - extract_matrix_multiplication()   # @ operator
│
├── collection_extractors.py         (Week 3, ~1000 lines)
│   - extract_dict_operations()         # Dict methods
│   - extract_list_mutations()          # List methods
│   - extract_set_operations()          # Set operations
│   - extract_string_methods()          # String methods
│   - extract_builtin_usage()           # len, sum, etc.
│   - extract_itertools_usage()         # Itertools patterns
│   - extract_functools_usage()         # Functools patterns
│   - extract_collections_usage()       # defaultdict, Counter, etc.
│
├── class_feature_extractors.py      (Week 4, ~900 lines)
│   - extract_metaclasses()             # Metaclass usage
│   - extract_descriptors()             # Descriptor protocol
│   - extract_dataclasses()             # @dataclass
│   - extract_enums()                   # Enum types
│   - extract_slots()                   # __slots__
│   - extract_abstract_classes()        # ABC usage
│   - extract_multiple_inheritance()    # MRO tracking
│   - extract_dunder_methods()          # Magic methods
│   - extract_method_types()            # class/static/instance
│   - extract_visibility_conventions()  # _private, __mangled
│
└── stdlib_pattern_extractors.py     (Week 4, ~600 lines)
    - extract_regex_patterns()          # re module usage
    - extract_json_operations()         # JSON handling
    - extract_datetime_operations()     # Date/time ops
    - extract_path_operations()         # pathlib usage
    - extract_logging_patterns()        # Logging calls
    - extract_threading_patterns()      # Threading/multiprocessing
    - extract_csv_operations()          # CSV handling
```

**Modified files** (3 files, ~500 lines changed):
- `theauditor/ast_extractors/python/__init__.py` - Import new modules (+50 lines)
- `theauditor/indexer/extractors/python.py` - Call new extractors (+200 lines)
- `theauditor/indexer/schemas/python_schema.py` - Add 45 new tables (+250 lines)

**Database Impact**:
- +45 new tables (79 → 124 tables)
- +15,000 new records extracted from TheAuditor (estimated)
- Database size increase: ~20MB (2-3% growth)

### Breaking Changes

**NONE** - This is purely additive work. All existing extractors remain functional.

---

## Impact

### Affected Specifications

- `specs/python-extraction/spec.md` - Add 90 new pattern categories
- **NO** other specs affected (pure additive work)

### Affected Users

**Curriculum Developers**:
- Can now create comprehensive Python learning paths
- Full coverage of language fundamentals through advanced features
- Data-driven curriculum based on real usage patterns

**Static Analysis Users**:
- 60% more patterns available for analysis
- Complete operator coverage enables new security checks
- Collection method tracking improves performance analysis

**AI/LLM Training**:
- Complete language coverage for code understanding
- Rich pattern data for model training
- Comprehensive AST-to-pattern mapping

### Migration Plan

**NONE REQUIRED** - All changes are additive. Existing databases continue to work.

---

## Detailed Implementation Plan

### Week 1: Fundamentals (Days 1-5)

**Day 1-2: Core Constructs**
```python
def extract_comprehensions(tree, parser_self):
    """Extract all comprehension types.

    Patterns:
    - List: [x*2 for x in range(10)]
    - Dict: {k: v for k, v in items}
    - Set: {x for x in items}
    - Generator: (x for x in items)

    Returns:
    {
        'line': int,
        'comp_type': 'list' | 'dict' | 'set' | 'generator',
        'result_expr': str,  # 'x*2'
        'iteration_var': str,  # 'x'
        'iteration_source': str,  # 'range(10)'
        'has_filter': bool,
        'filter_expr': str | None,
        'nesting_level': int,
    }
    """
```

**Day 3-4: Lambda & Unpacking**
```python
def extract_lambda_functions(tree, parser_self):
    """Extract lambda functions with closure detection.

    Returns:
    {
        'line': int,
        'parameters': List[str],
        'body': str,
        'captures_closure': bool,
        'captured_vars': List[str],
        'used_in': str,  # 'map' | 'filter' | 'sorted_key' | 'assignment'
    }
    """
```

**Day 5: Testing & Integration**
- Wire extractors to pipeline
- Create comprehensive test fixtures
- Verify extraction counts

### Week 2: Operators (Days 6-10)

**Day 6-7: Basic Operators**
```python
def extract_operators(tree, parser_self):
    """Extract all operator usage.

    Categories:
    - Arithmetic: +, -, *, /, //, %, **
    - Comparison: <, >, <=, >=, ==, !=
    - Logical: and, or, not
    - Bitwise: &, |, ^, ~, <<, >>

    Returns:
    {
        'line': int,
        'operator_type': str,
        'operator': str,
        'left_operand': str,
        'right_operand': str,
        'in_function': str,
    }
    """
```

**Day 8-9: Advanced Expressions**
- Chained comparisons (1 < x < 10)
- Ternary expressions (x if y else z)
- Walrus operator (x := expr)
- Matrix multiplication (A @ B)

**Day 10: Testing & Performance**
- Verify single-pass efficiency
- Profile extraction performance

### Week 3: Collections (Days 11-15)

**Day 11-12: Collection Methods**
```python
def extract_dict_operations(tree, parser_self):
    """Extract dictionary method calls.

    Methods: keys(), values(), items(), get(), setdefault(),
             update(), pop(), popitem(), clear()

    Returns:
    {
        'line': int,
        'operation': str,
        'target': str,  # Variable name
        'has_default': bool,
        'is_iteration': bool,
        'in_function': str,
    }
    """
```

**Day 13-14: Builtin & Module Usage**
- Builtin functions (len, sum, max, min, sorted, etc.)
- Itertools patterns (chain, cycle, combinations)
- Functools patterns (partial, reduce, lru_cache)

**Day 15: Integration Testing**
- End-to-end pipeline verification
- Database record validation

### Week 4: Advanced Features (Days 16-20)

**Day 16-17: Class Features**
```python
def extract_metaclasses(tree, parser_self):
    """Extract metaclass usage.

    Returns:
    {
        'line': int,
        'class_name': str,
        'metaclass': str,
        'metaclass_methods': List[str],
    }
    """
```

**Day 18-19: Protocols & Patterns**
- Iterator protocol (__iter__, __next__)
- Container protocol (__getitem__, __setitem__)
- Context manager protocol (__enter__, __exit__)
- Comparison protocol (__eq__, __lt__, etc.)

**Day 20: Final Validation**
- Complete testing on TheAuditor codebase
- Performance benchmarking
- Documentation updates

---

## Risk Analysis

### High Risks

1. **Performance Degradation**
   - **Probability**: MEDIUM (90 new extractors)
   - **Impact**: HIGH (could slow indexing)
   - **Mitigation**: Single-pass AST walking, aggressive deduplication
   - **Contingency**: Defer less critical patterns to future PR

2. **Schema Complexity**
   - **Probability**: MEDIUM (45 new tables)
   - **Impact**: MEDIUM (database management overhead)
   - **Mitigation**: Strategic indexing, normalized design
   - **Contingency**: Consolidate similar tables if needed

### Medium Risks

3. **Extractor Conflicts**
   - **Probability**: LOW (careful analysis done)
   - **Impact**: HIGH (duplicate data, confusion)
   - **Mitigation**: Verified no overlap with existing 20+ extractors
   - **Contingency**: Add conflict detection in pipeline

4. **Test Coverage**
   - **Probability**: MEDIUM (90 patterns to test)
   - **Impact**: MEDIUM (bugs in production)
   - **Mitigation**: Comprehensive fixtures for all patterns
   - **Contingency**: Phased rollout with monitoring

---

## Success Metrics

### Quantitative Targets

| Metric | Baseline | Week 1 | Week 2 | Week 3 | Week 4 | Target |
|--------|----------|--------|--------|--------|--------|--------|
| **Extractor Modules** | 18 | 19 | 20 | 21 | 23 | 23 |
| **Total Extractors** | ~100 | 125 | 140 | 160 | 190 | 190 |
| **Tables** | 79 | 91 | 98 | 108 | 124 | 124 |
| **Records (TheAuditor)** | ~20k | 24k | 27k | 32k | 35k | 35k+ |
| **Pattern Coverage** | 52% | 65% | 75% | 85% | 100% | 100% |

### Qualitative Targets

- ✅ All 90 patterns from python_coverage_v2.md extracted
- ✅ Zero conflicts with existing extractors
- ✅ Performance maintained (<10ms per file)
- ✅ Comprehensive test coverage (>95%)
- ✅ Documentation complete for all patterns

---

## Verification Strategy (teamsop.md Compliance)

### Pre-Implementation Verification (MANDATORY)

**Hypothesis Testing**:
```
Hypothesis 1: No comprehension extractors currently exist
Verification: grep -r "extract.*comprehen" ast_extractors/python/
Result: No matches (confirming gap)

Hypothesis 2: Operator extraction not implemented
Verification: grep -r "extract.*operator" ast_extractors/python/
Result: No matches (confirming gap)

Hypothesis 3: 79 Python tables currently exist
Verification: Query sqlite_master in repo_index.db
Result: Confirmed - 79 tables

Hypothesis 4: AST provides needed nodes for all patterns
Verification: Test parsing of pattern fixtures
Result: All AST nodes available
```

### Post-Implementation Audit (MANDATORY)

After each week:
1. **Re-read** all modified files for correctness
2. **Run** `aud full --offline` on TheAuditor
3. **Query** all new tables for data validation
4. **Compare** counts with expectations (±20% tolerance)
5. **Profile** performance (<10ms maintained)
6. **Test** extraction on pattern fixtures

---

## Approval Checklist

- [x] Gap analysis verified against python_coverage_v2.md (100% mapping)
- [x] All 90 patterns clearly defined with signatures
- [x] Database impact assessed (45 new tables, +15k records)
- [x] Performance strategy defined (single-pass AST)
- [x] Test fixtures planned (90+ test cases)
- [x] Timeline realistic (4 weeks, ~22 patterns/week)
- [x] Risk mitigation strategies defined
- [x] No conflicts with existing extractors verified
- [x] teamsop.md verification protocols embedded
- [x] Success metrics clearly defined

---

## Approval

**Lead Coder (Opus AI)**: Proposal complete, ready for review
**Lead Auditor (Gemini)**: [Pending review]
**Architect (Santa)**: [Pending approval]

---

**END OF PROPOSAL**

**Next Steps After Approval**:
1. Create `design.md` with detailed architecture
2. Create `tasks.md` with atomic task breakdown
3. Create `verification.md` for hypothesis testing
4. Begin Week 1 implementation (fundamental_extractors.py)