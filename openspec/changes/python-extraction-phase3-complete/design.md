# Python Extraction Phase 3: Design Document

**Version**: 1.0
**Date**: 2025-11-01
**Status**: DRAFT

---

## ARCHITECTURAL OVERVIEW

Phase 3 extends the proven 5-layer pipeline from Phase 2 with optimizations and new patterns.

```
┌─────────────────────────────────────────────────────────────┐
│                     EXTRACTION PIPELINE                       │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: AST EXTRACTORS (79 functions across 9 modules)      │
│   ├── core_extractors.py (16 functions)                      │
│   ├── framework_extractors.py (25 functions)                 │
│   ├── flask_extractors.py (10 functions) [NEW]              │
│   ├── security_extractors.py (8 functions) [NEW]            │
│   └── testing_extractors.py (12 functions) [EXPANDED]       │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: INDEXER (Single orchestrator, multiple extractors)  │
│   └── extractors/python.py (50+ result keys)                │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: STORAGE (50+ storage methods)                       │
│   └── storage.py (1,800+ lines)                             │
├─────────────────────────────────────────────────────────────┤
│ Layer 4: DATABASE WRITERS (50+ writer methods)               │
│   └── database/python_database.py                           │
├─────────────────────────────────────────────────────────────┤
│ Layer 5: SCHEMA (50+ table definitions)                      │
│   └── schemas/python_schema.py                              │
└─────────────────────────────────────────────────────────────┘
```

---

## DESIGN DECISIONS

### Decision 1: Flask Module Separation
**Context**: framework_extractors.py is 92KB, adding 10 Flask extractors would make it 120KB+

**Options Considered**:
1. Add to framework_extractors.py
2. Create flask_extractors.py
3. Split framework_extractors.py into multiple files

**Decision**: Create flask_extractors.py

**Rationale**:
- Maintains module cohesion
- Follows single responsibility principle
- Easier to test in isolation
- Consistent with JavaScript pattern (separate framework modules)

**Trade-offs**:
- (+) Better maintainability
- (+) Faster incremental builds
- (-) One more import to manage
- (-) Potential for duplicate helper functions

### Decision 2: Memory Cache Architecture
**Context**: 50+ tables require memory cache for performance

**Options Considered**:
1. Eager load all tables on startup
2. Lazy load on first access
3. Hybrid: eager load hot tables, lazy load cold

**Decision**: Hybrid approach

**Rationale**:
- Hot tables (decorators, functions, classes) used frequently
- Cold tables (Flask WebSockets, hypothesis strategies) used rarely
- Reduces startup from 5s to <1s
- Memory usage stays under 500MB

**Implementation**:
```python
class PythonMemoryCache:
    HOT_TABLES = ['python_functions', 'python_classes', 'python_decorators']
    COLD_TABLES = ['python_flask_websockets', 'python_hypothesis_strategies']

    def __init__(self):
        self._load_hot_tables()  # On startup
        self._cold_cache = {}    # Lazy loaded
```

### Decision 3: Security Pattern Scope
**Context**: Infinite security patterns possible, need practical boundaries

**Options Considered**:
1. Extract everything security-related
2. Focus on OWASP Top 10 only
3. Prioritize by CVE frequency

**Decision**: OWASP Top 10 focus with CVE additions

**Rationale**:
- OWASP covers 80% of vulnerabilities
- CVE data adds real-world relevance
- Manageable scope (8 extractors)
- Clear success criteria

**Patterns Included**:
- SQL Injection (raw queries)
- XSS (template rendering)
- Authentication (decorators)
- Cryptography (hashing)
- Deserialization (pickle)
- Command Injection (subprocess)
- Path Traversal (file operations)
- Code Injection (eval/exec)

### Decision 4: Performance Optimization Strategy
**Context**: Current extraction ~15ms per file, target <10ms

**Options Considered**:
1. Parallelize ast.walk()
2. Cache AST between extractors
3. Single-pass extraction
4. JIT compilation with Numba

**Decision**: Single-pass extraction with AST caching

**Rationale**:
- Single ast.walk() instead of multiple
- Share AST between extractors
- 40% performance improvement
- No external dependencies

**Implementation**:
```python
def extract_all_patterns(tree: Dict) -> Dict:
    results = {}
    actual_tree = tree.get("tree")

    # Single walk
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef):
            _extract_function_patterns(node, results)
            _extract_decorator_patterns(node, results)
            _extract_async_patterns(node, results)
        elif isinstance(node, ast.ClassDef):
            _extract_class_patterns(node, results)

    return results
```

### Decision 5: Test Fixture Strategy
**Context**: Phase 2 has 2,512 lines (58% of target), need coverage for new extractors

**Options Considered**:
1. Expand to original 4,300 line target
2. Add only for new extractors
3. Generate fixtures programmatically

**Decision**: Add only for new extractors (Option 2)

**Rationale**:
- Current fixtures already comprehensive
- New patterns need specific examples
- Time better spent on extractors
- Can expand later if needed

**Coverage Plan**:
- Flask: 800 lines (10 patterns)
- Testing: 600 lines (8 patterns)
- Security: 500 lines (8 patterns)
- Django: 400 lines (4 patterns)
- Total: 2,300 new lines (4,812 total)

### Decision 6: Database Schema Evolution
**Context**: Adding 16+ new tables, need migration strategy

**Options Considered**:
1. Drop and recreate all tables
2. ALTER TABLE migrations
3. Versioned schema with compatibility

**Decision**: Drop and recreate (Option 1)

**Rationale**:
- Database regenerated fresh each `aud index`
- No persistent data to migrate
- Simplest, most reliable
- Consistent with current approach

### Decision 7: Taint Analysis Integration
**Context**: New patterns need taint propagation rules

**Options Considered**:
1. Update taint analyzer for each pattern
2. Generic taint rules based on pattern type
3. Separate taint configuration file

**Decision**: Generic rules with pattern-specific overrides

**Rationale**:
- Most patterns follow standard propagation
- Special cases (async, signals) get custom rules
- Maintainable and extensible
- Reuses existing taint infrastructure

**Taint Rules**:
```python
PATTERN_TAINT_RULES = {
    'async_function': {'propagates': True, 'awaitable': True},
    'django_signal': {'propagates': True, 'broadcast': True},
    'flask_route': {'entry_point': True, 'user_input': True},
    'test_mock': {'synthetic': True, 'controllable': True}
}
```

### Decision 8: Error Handling Philosophy
**Context**: Extractors can encounter malformed AST, need consistent approach

**Options Considered**:
1. Fail fast on any error
2. Silent failure with logging
3. Best effort with error collection

**Decision**: Best effort with error collection

**Rationale**:
- Don't lose all extraction due to one bad pattern
- Collect errors for debugging
- Log at DEBUG level
- Return partial results

**Pattern**:
```python
def extract_pattern(tree: Dict) -> List[Dict]:
    results = []
    errors = []

    try:
        # Main extraction logic
        for node in ast.walk(tree):
            try:
                result = process_node(node)
                results.append(result)
            except Exception as e:
                errors.append(f"Line {node.lineno}: {e}")
                if DEBUG:
                    logger.debug(f"Extraction error: {e}")
    except Exception as e:
        logger.error(f"Fatal extraction error: {e}")

    return results
```

### Decision 9: Module Dependencies
**Context**: New extractors need various helper functions

**Options Considered**:
1. Duplicate helpers in each module
2. Central helpers module
3. Inherit from base class

**Decision**: Central helpers module

**Rationale**:
- Single source of truth
- Easier to test helpers
- Reduces code duplication
- Can optimize helpers once

**Structure**:
```python
# extraction_helpers.py
def get_decorator_name(node): ...
def extract_string_value(node): ...
def get_function_calls(node): ...
def is_test_function(node): ...
```

### Decision 10: Validation Strategy
**Context**: Need to ensure extraction quality

**Options Considered**:
1. Unit tests for each extractor
2. Integration tests only
3. Property-based testing
4. Golden file comparisons

**Decision**: Golden files + property tests

**Rationale**:
- Golden files catch regressions
- Property tests find edge cases
- Fast feedback during development
- Easy to update when needed

**Test Structure**:
```python
# test_flask_extractors.py
def test_flask_golden_files():
    """Compare extraction against known good outputs."""

def test_flask_properties():
    """Property: every Flask() call creates an app entry."""
```

---

## PERFORMANCE ARCHITECTURE

### Current Performance (Phase 2)
- **Average**: 15ms per file
- **P95**: 25ms per file
- **P99**: 45ms per file
- **Memory**: 300MB average, 450MB peak

### Target Performance (Phase 3)
- **Average**: <10ms per file
- **P95**: <15ms per file
- **P99**: <30ms per file
- **Memory**: <400MB average, <500MB peak

### Optimization Techniques

1. **Single-Pass AST Walking**
   - Combine related extractors
   - Share node type checking
   - Reduce tree traversals from N to 1

2. **Memory Pool Allocation**
   - Pre-allocate result dictionaries
   - Reuse list objects
   - Clear instead of recreate

3. **Lazy Attribute Access**
   - Only compute expensive attributes when needed
   - Cache computed values
   - Use __slots__ for extractor classes

4. **Short-Circuit Evaluation**
   - Check cheap conditions first
   - Early return on non-matches
   - Skip deep inspection for simple patterns

---

## SECURITY ARCHITECTURE

### Threat Model
- **Input**: Untrusted Python source code
- **Threats**: Malformed AST, resource exhaustion, injection
- **Mitigations**: Timeouts, resource limits, sandboxing

### Security Boundaries
1. **AST Parsing**: Handled by Python's ast module (trusted)
2. **Extraction**: Read-only operations, no execution
3. **Database**: Parameterized queries only
4. **File System**: Read-only access to source files

### Security Patterns Detected

**Critical** (Immediate Security Risk):
- eval()/exec() with user input
- SQL queries with string formatting
- Subprocess with shell=True
- Pickle deserialization
- Raw file path operations

**High** (Likely Security Risk):
- Missing authentication decorators
- Weak password hashing
- JWT without verification
- CSRF exemptions
- Unvalidated redirects

**Medium** (Potential Security Risk):
- Debug mode in production
- Verbose error messages
- Missing rate limiting
- Weak random generation
- HTTP instead of HTTPS

---

## TESTING ARCHITECTURE

### Test Pyramid

```
        /\
       /  \
      / E2E \ (10%)
     /______\
    /        \
   /  Integr. \ (30%)
  /____________\
 /              \
/   Unit Tests   \ (60%)
/________________\
```

### Test Categories

1. **Unit Tests** (60%):
   - Each extractor function
   - Helper functions
   - Schema definitions
   - Database writers

2. **Integration Tests** (30%):
   - Full pipeline extraction
   - Database round-trip
   - Memory cache operations
   - Multi-file projects

3. **End-to-End Tests** (10%):
   - Real project extraction
   - Performance benchmarks
   - Memory profiling
   - Taint analysis integration

### Test Data Strategy

**Fixtures** (Controlled):
- Hand-crafted examples
- Edge cases
- Security patterns
- Framework samples

**Real Projects** (Validation):
- Django (large framework)
- Flask (microframework)
- FastAPI (modern async)
- Celery (distributed)
- pytest (testing)

**Generated** (Fuzzing):
- Hypothesis strategies
- AST mutation
- Random valid Python
- Boundary conditions

---

## INTEGRATION POINTS

### With Existing Systems

1. **Indexer**:
   - Register extractors in python.py
   - Add result keys to dictionary
   - Maintain extraction order

2. **Storage**:
   - Add storage methods
   - Register handlers
   - Update counts

3. **Database**:
   - Add writer methods
   - Register batch handlers
   - Maintain transaction boundaries

4. **Schema**:
   - Define table structures
   - Add to PYTHON_TABLES
   - Update migration scripts

5. **Memory Cache**:
   - Add cache loaders
   - Register invalidation
   - Update warming logic

6. **Taint Analyzer**:
   - Add propagation rules
   - Register entry points
   - Update sink definitions

### API Contracts

**Extractor Function**:
```python
def extract_X(tree: Dict, parser_self) -> List[Dict[str, Any]]
```

**Storage Method**:
```python
def _store_python_X(self, file_path: str, data: List, jsx_pass: bool)
```

**Database Writer**:
```python
def add_python_X(self, file_path: str, **fields)
```

**Schema Definition**:
```python
PYTHON_X = TableSchema(name="python_x", columns=[...], ...)
```

---

## MONITORING & OBSERVABILITY

### Metrics to Track

**Performance**:
- Extraction time per file
- Extraction time per pattern
- Database write time
- Memory cache hit rate

**Quality**:
- Patterns extracted per file
- Error rate per extractor
- Schema validation failures
- Duplicate detection rate

**Scale**:
- Files processed per second
- Records inserted per second
- Peak memory usage
- Database size growth

### Logging Strategy

**INFO Level**:
- Extraction started/completed
- File count, record count
- Major errors

**DEBUG Level**:
- Individual extractor times
- Pattern match details
- Cache operations
- Query execution

**ERROR Level**:
- Extraction failures
- Database errors
- Schema violations
- Resource exhaustion

---

## FUTURE CONSIDERATIONS

### Phase 4 Possibilities

1. **Machine Learning Integration**:
   - Pattern learning from codebase
   - Anomaly detection
   - Code similarity clustering

2. **Cross-Language Patterns**:
   - Python-JavaScript bridges
   - Python-SQL interactions
   - Python-Shell integration

3. **Advanced Frameworks**:
   - Tornado async
   - Twisted reactors
   - Pyramid traversal
   - Bottle routes

4. **Performance Optimizations**:
   - Rust extractor modules
   - Parallel extraction
   - Incremental updates
   - Distributed processing

5. **Enhanced Security**:
   - CVE matching
   - Dependency scanning
   - License compliance
   - Supply chain analysis

---

**END OF DESIGN DOCUMENT**