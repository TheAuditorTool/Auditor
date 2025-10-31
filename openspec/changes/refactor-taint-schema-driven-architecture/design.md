# Design Document: Schema-Driven Taint Architecture

**Change ID**: `refactor-taint-schema-driven-architecture`
**Author**: Claude Opus (Lead Coder)
**Date**: 2025-10-31
**Status**: Pending Approval

---

## Context

### Background

Taint analysis was built 6 months ago when schema infrastructure was immature. Since then:
- Schema evolved: added CFG tables (`cfg_blocks`, `cfg_edges`)
- Schema evolved: added Python ORM tables (`python_orm_models`, `python_orm_fields`)
- Schema evolved: added React/Vue tables (`react_hooks`, `object_literals`)
- Schema grew from ~30 tables → 70 tables

**But taint architecture NEVER refactored to leverage mature schema.**

Result: Manual loaders, hardcoded patterns, fallback logic, duplicate implementations.

### Constraints

1. **Zero breaking changes** - Public API (`aud taint-analyze`) must remain unchanged
2. **Memory budget** - Must stay under 1GB RAM for large projects
3. **Performance** - Must be faster (or equal), not slower
4. **Backward compatibility** - Existing taint results must match exactly

### Stakeholders

- **Architect (User)**: Approval authority, enforces DRY/SRP principles
- **Lead Auditor (Gemini)**: Quality control, reviews technical decisions
- **Lead Coder (Opus)**: Implementation responsibility
- **Taint Users**: Security analysts using `aud taint-analyze`

---

## Goals / Non-Goals

### Goals

1. ✅ **Eliminate 8-layer changes** - Reduce to 3 layers (parser → schema → taint)
2. ✅ **Make schema king** - Auto-generate loaders, accessors, validators
3. ✅ **Delete manual loaders** - 40+ manual functions → 0 (auto-generated)
4. ✅ **Delete taint/database.py** - 1,447 lines of fallback logic → 0
5. ✅ **Database-driven discovery** - No hardcoded patterns, query what exists
6. ✅ **Unify CFG implementations** - 3 files → 1 file
7. ✅ **Always use cache** - No fallback, mandatory memory cache

### Non-Goals

1. ❌ **Change taint algorithms** - Preserve exact taint propagation logic
2. ❌ **Add new features** - Pure refactor, no new capabilities
3. ❌ **Optimize performance** - Architecture change, not algorithm optimization
4. ❌ **Refactor indexer** - Separate proposal (refactor-indexer-god-method-split)
5. ❌ **Add comprehensive type hints** - Enhancement, not refactor

---

## Decisions

### Decision 1: Schema Auto-Generation System

**What**: Schema generates TypedDicts, accessor classes, memory cache loader, validators.

**Architecture**:
```python
# schema.py (or new schemas/codegen.py)
class SchemaCodeGenerator:
    """Generates code from schema definitions."""

    @staticmethod
    def generate_typed_dicts() -> str:
        """Generate TypedDict for each table.

        Example output:
            class SymbolRow(TypedDict):
                id: int
                path: str
                name: str
                type: str
                line: int
                col: Optional[int]
                # ... all columns
        """
        code = []
        for table_name, schema in TABLES.items():
            class_name = f"{_to_pascal_case(table_name)}Row"
            fields = []
            for col in schema.columns:
                field_type = _python_type(col.type_)
                if not col.not_null:
                    field_type = f"Optional[{field_type}]"
                fields.append(f"    {col.name}: {field_type}")

            code.append(f"class {class_name}(TypedDict):\n" + "\n".join(fields))
        return "\n\n".join(code)

    @staticmethod
    def generate_accessor_classes() -> str:
        """Generate accessor class for each table.

        Example output:
            class SymbolsTable:
                @staticmethod
                def get_all(cursor) -> List[SymbolRow]:
                    query = build_query('symbols', [...])
                    cursor.execute(query)
                    return [SymbolRow(*row) for row in cursor.fetchall()]

                @staticmethod
                def get_by_path(cursor, path: str) -> List[SymbolRow]:
                    query = build_query('symbols', [...], where="path = ?")
                    cursor.execute(query, (path,))
                    return [SymbolRow(*row) for row in cursor.fetchall()]
        """
        code = []
        for table_name, schema in TABLES.items():
            class_name = f"{_to_pascal_case(table_name)}Table"
            row_type = f"{_to_pascal_case(table_name)}Row"

            methods = []
            # Generate get_all
            methods.append(f"""
    @staticmethod
    def get_all(cursor) -> List[{row_type}]:
        query = build_query('{table_name}', {[col.name for col in schema.columns]})
        cursor.execute(query)
        return cursor.fetchall()
""")

            # Generate get_by_{column} for indexed columns
            for col in schema.columns:
                if col.indexed:
                    methods.append(f"""
    @staticmethod
    def get_by_{col.name}(cursor, {col.name}: {_python_type(col.type_)}) -> List[{row_type}]:
        query = build_query('{table_name}', [...], where="{col.name} = ?")
        cursor.execute(query, ({col.name},))
        return cursor.fetchall()
""")

            code.append(f"class {class_name}:\n" + "\n".join(methods))
        return "\n\n".join(code)

    @staticmethod
    def generate_memory_cache() -> str:
        """Generate SchemaMemoryCache class.

        Loads ALL 70 tables automatically, builds indexes for indexed columns.
        """
        return """
class SchemaMemoryCache:
    def __init__(self, db_path: str):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Auto-load ALL tables
        for table_name, schema in TABLES.items():
            data = self._load_table(cursor, schema)
            setattr(self, table_name, data)

            # Auto-build indexes
            for col in schema.columns:
                if col.indexed:
                    index = self._build_index(table_name, col.name)
                    setattr(self, f"{table_name}_by_{col.name}", index)

        conn.close()

    def _load_table(self, cursor, schema):
        query = build_query(schema.name, [col.name for col in schema.columns])
        cursor.execute(query)
        return cursor.fetchall()

    def _build_index(self, table_name, column_name):
        index = defaultdict(list)
        data = getattr(self, table_name)
        col_idx = [col.name for col in TABLES[table_name].columns].index(column_name)
        for row in data:
            index[row[col_idx]].append(row)
        return dict(index)
"""
```

**Why**:
- **DRY**: Define schema once, generate everything
- **Type safety**: TypedDicts catch typos at dev time
- **Consistency**: All tables accessed the same way
- **Maintainability**: Add column to schema → auto-updates everywhere

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **SQLAlchemy ORM** | Battle-tested, full ORM | 10MB dependency, slow startup, overkill for read-only | Complexity vs benefit |
| **Pydantic models** | Validation built-in | Runtime overhead, complex for 70 tables | Performance cost |
| **Manual code** (current) | No magic | Massive DRY violation | Exactly what we're fixing |
| **Code generation at build time** | No runtime cost | Complex build step, IDE support issues | Runtime generation simpler |

**Selected**: Runtime code generation (on import)

**Rationale**: Simplest solution with zero dependencies. Generated code is plain Python, full IDE support.

---

### Decision 2: Mandatory Memory Cache (No Fallback)

**What**: Cache is ALWAYS created at startup. No optional flag, no fallback.

**Implementation**:
```python
# taint/core.py
class TaintAnalyzer:
    def __init__(self, db_path: str):
        # ALWAYS load cache (no optional parameter)
        self.cache = SchemaMemoryCache(db_path)

        # From here on, EVERYTHING queries memory
        # NO database cursor passed to analysis functions

    def analyze(self):
        # Discover sources/sinks from cache
        sources = self.discover_sources()  # Queries self.cache
        sinks = self.discover_sinks()      # Queries self.cache

        # Run analysis (cache only, no disk queries)
        return self.run_analysis(sources, sinks)
```

**Why**:
- **Eliminates fallback** - 50% of code in every function deleted
- **Performance** - Cache is 100-300x faster than disk
- **Simplicity** - No "if cache:" checks everywhere
- **Reality** - Fallback never used anyway (too slow)

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Optional cache** (current) | Flexible? | Massive code duplication (fallback logic) | Fallback never used |
| **Lazy loading** | Lower startup time | Complex invalidation, partial data issues | Full load fast enough |
| **Hybrid** (cache + disk) | Best of both? | Complex logic, no real benefit | Cache is always faster |
| **SQLite in-memory mode** | No custom cache | SQLite overhead still present | Python dict faster |

**Selected**: Mandatory memory cache (always loaded)

**Rationale**: Reality is cache is ALWAYS used. Formalizing this deletes 1,447 lines of dead fallback code.

---

### Decision 3: Database-Driven Discovery (No Hardcoded Patterns)

**What**: Discover sources/sinks by querying database, not searching for hardcoded patterns.

**Before** (hardcoded):
```python
# sources.py
TAINT_SOURCES = {
    'http_request': ['req.body', 'req.query'],  # Hardcoded list
}

# taint/database.py
def find_taint_sources(cursor):
    for pattern in TAINT_SOURCES['http_request']:
        query = "SELECT * FROM symbols WHERE name LIKE ?"
        cursor.execute(query, (f"%{pattern}%",))
        # Search database for hardcoded patterns
```

**After** (database-driven):
```python
# No hardcoded TAINT_SOURCES

class TaintAnalyzer:
    def discover_sources(self):
        """Discover sources FROM database."""
        sources = []

        # HTTP sources: Query api_endpoints (actual data)
        for endpoint in self.cache.api_endpoints:
            if not endpoint['has_auth']:  # Public endpoints = high risk
                sources.append({
                    'type': 'http_request',
                    'endpoint': endpoint,
                    'risk': 'high'
                })

        # User input: Query symbols for actual property access
        for symbol in self.cache.symbols:
            if symbol['type'] == 'property':
                # Classify based on actual name
                if any(x in symbol['name'] for x in ['req.', 'request.']):
                    sources.append({
                        'type': 'user_input',
                        'symbol': symbol
                    })

        return sources

    def discover_sinks(self):
        """Discover sinks FROM database."""
        sinks = []

        # SQL sinks: DIRECTLY from sql_queries table
        for query_row in self.cache.sql_queries:
            sinks.append({
                'type': 'sql',
                'query': query_row,
                'risk': self._assess_sql_risk(query_row)
            })

        # Command sinks: Query function_call_args for exec/spawn
        for call in self.cache.function_call_args:
            if 'exec' in call['callee_function'] or 'spawn' in call['callee_function']:
                sinks.append({
                    'type': 'command',
                    'call': call
                })

        return sources

    def _assess_sql_risk(self, query_row):
        """Analyze query structure for risk factors."""
        query_text = query_row['query_text']

        # Check for concatenation (high risk)
        if any(x in query_text for x in ['+', '${', 'f"']):
            return 'high'

        # Check for parameterization (low risk)
        if any(x in query_text for x in ['?', '$1', ':param']):
            return 'low'

        return 'medium'
```

**Why**:
- **Database has the data** - api_endpoints, sql_queries, function_call_args tables
- **No hardcoded maintenance** - Add table to schema → automatically discoverable
- **Richer context** - Database has metadata (has_auth, query_text, risk factors)
- **Classification** not search - Classify what EXISTS, don't search for patterns

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Keep hardcoded patterns** | Explicit control | Manual maintenance, schema disconnect | Violates DRY |
| **Hybrid** (patterns + database) | Flexible | Complex, best of neither | Overcomplicated |
| **ML classification** | Adaptive | Overkill, false positives | Not needed |
| **User-defined patterns** | Customizable | Complex config, not needed | YAGNI |

**Selected**: Database-driven classification

**Rationale**: Database ALREADY has the data. Just query and classify it. Simplest, most maintainable.

---

### Decision 4: Unified CFG Implementation

**What**: Merge 3 CFG files into single `analysis.py` with one implementation.

**Before** (3 files, 2 implementations):
```
interprocedural.py (43KB):
  - trace_inter_procedural_flow_insensitive()  # 278 lines (OLD)
  - trace_inter_procedural_flow_cfg()          # 455 lines (NEW)

interprocedural_cfg.py (36KB):
  - InterProceduralCFGAnalyzer                  # 1024 lines (CFG class)

cfg_integration.py (37KB):
  - BlockTaintState                             # CFG utilities
  - PathAnalyzer                                # CFG utilities
```

**After** (1 file, 1 implementation):
```
analysis.py (800 lines):
  - TaintFlowAnalyzer (unified class)
    ├─ analyze_interprocedural()  # Main entry point
    ├─ _analyze_function_cfg()    # CFG-based (always)
    ├─ _propagate_through_calls() # Interprocedural
    └─ _check_feasibility()       # CFG path checking
```

**Why**:
- **Single implementation** - CFG tables always available, no fallback needed
- **Unified logic** - All CFG code in one place
- **Simpler** - 3 files → 1 file, easier to navigate
- **Faster** - No abstraction overhead

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Keep 3 files** (current) | Separation of concerns? | Duplicate logic, confusing | Artificial separation |
| **2 files** (analyzer + utils) | Some separation | Still split, not much benefit | Overengineering |
| **4 files** (per-analysis type) | Very granular | Fragmentation, hard to follow | Too many files |
| **Keep both implementations** | Fallback if CFG missing | CFG always available now | Dead code |

**Selected**: Single file, single implementation

**Rationale**: CFG tables are mature and always populated. No need for fallback or separation. Simpler is better.

---

### Decision 5: Staged Rollout Strategy

**What**: 4-phase rollout to minimize risk and enable rollback.

**Phase 1: Schema Auto-Generation** (Non-breaking, additive)
- Add SchemaCodeGenerator to schema.py
- Generate TypedDicts, accessor classes, SchemaMemoryCache
- NO code uses it yet (parallel to existing code)
- Validation: Generated code imports and instantiates

**Phase 2: Replace Memory Cache** (Internal change)
- Replace memory_cache.py + python_memory_cache.py with SchemaMemoryCache
- Update taint/core.py to use SchemaMemoryCache
- Keep taint/database.py as fallback (feature flag)
- Validation: Taint results match exactly

**Phase 3: Database-Driven Discovery** (Delete hardcoded patterns)
- Replace hardcoded TAINT_SOURCES/SECURITY_SINKS with discover_sources/discover_sinks
- Delete sources.py, config.py
- Still keep database.py as fallback
- Validation: Same sources/sinks discovered

**Phase 4: Delete Fallback & Unify CFG** (Complete refactor)
- Delete taint/database.py (1,447 lines)
- Merge CFG files into analysis.py
- Remove feature flags
- Validation: Full pipeline passes

**Why**:
- **Incremental risk** - Each phase independently validated
- **Rollback points** - Can revert any phase
- **Feature flags** - Can toggle new vs old code
- **Parallel validation** - Run both implementations, compare results

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Big bang** (all at once) | Faster | High risk, hard to rollback | Too risky |
| **2 phases** (schema + taint) | Simpler | Less granular rollback | Want more safety |
| **6+ phases** (very granular) | Safest | Too slow, overhead | Diminishing returns |
| **Feature branch only** | Normal dev flow | No production validation | Want staged prod |

**Selected**: 4-phase staged rollout

**Rationale**: Balance between safety (incremental) and speed (not too many phases).

---

## Implementation Architecture

### New File Structure

```
theauditor/indexer/
├── schema.py (MODIFIED)
│   └── SchemaCodeGenerator (NEW)
│       ├── generate_typed_dicts()
│       ├── generate_accessor_classes()
│       ├── generate_memory_cache()
│       └── generate_validators()
│
└── schemas/ (existing)
    └── ... (unchanged)

theauditor/taint/
├── core.py (MODIFIED)
│   └── TaintAnalyzer uses SchemaMemoryCache
│
├── analysis.py (NEW - 800 lines)
│   └── TaintFlowAnalyzer (unified CFG implementation)
│
├── propagation.py (MODIFIED)
│   └── Uses cache instead of database queries
│
└── [DELETED FILES]
    ├── database.py (1,447 lines) ← DELETED
    ├── memory_cache.py (59KB) ← DELETED
    ├── python_memory_cache.py (20KB) ← DELETED
    ├── sources.py (18KB) ← DELETED
    ├── config.py (5KB) ← DELETED
    ├── registry.py (8KB) ← DELETED
    ├── interprocedural.py (43KB) ← MERGED into analysis.py
    ├── interprocedural_cfg.py (36KB) ← MERGED into analysis.py
    └── cfg_integration.py (37KB) ← MERGED into analysis.py
```

### Data Flow

**Before** (Complex):
```
Schema → Manual Storage → Database
   ↓
Manual Query Writing (database.py)
   ↓
Optional Cache Check
   ├─ IF cache: Memory lookup
   └─ ELSE: Fallback to disk (duplicate logic)
   ↓
Hardcoded Pattern Matching
   ↓
Taint Analysis (3 CFG files)
```

**After** (Simple):
```
Schema → Auto-Generate (TypedDicts, Accessors, Cache)
   ↓
SchemaMemoryCache (load ALL tables at startup)
   ↓
Database-Driven Discovery (query cache, classify)
   ↓
Taint Analysis (1 unified file)
```

### Schema Generation Example

**Input** (schema.py):
```python
symbols = TableSchema('symbols', [
    Column('id', 'INTEGER', primary_key=True),
    Column('path', 'TEXT', indexed=True),
    Column('name', 'TEXT', indexed=True),
    Column('type', 'TEXT'),
    Column('line', 'INTEGER'),
])
```

**Generated Output** (auto-generated):
```python
# TypedDict
class SymbolRow(TypedDict):
    id: int
    path: str
    name: str
    type: str
    line: int

# Accessor class
class SymbolsTable:
    @staticmethod
    def get_all(cursor) -> List[SymbolRow]:
        query = build_query('symbols', ['id', 'path', 'name', 'type', 'line'])
        cursor.execute(query)
        return cursor.fetchall()

    @staticmethod
    def get_by_path(cursor, path: str) -> List[SymbolRow]:
        query = build_query('symbols', [...], where="path = ?")
        cursor.execute(query, (path,))
        return cursor.fetchall()

    @staticmethod
    def get_by_name(cursor, name: str) -> List[SymbolRow]:
        query = build_query('symbols', [...], where="name = ?")
        cursor.execute(query, (name,))
        return cursor.fetchall()

# Memory cache includes:
# - self.symbols (all rows)
# - self.symbols_by_path (indexed dict)
# - self.symbols_by_name (indexed dict)
```

---

## Risks / Trade-offs

### Risk 1: Schema Generation Complexity

**Risk**: Code generation bugs → broken accessors

**Likelihood**: Medium
**Impact**: HIGH (entire taint system broken)

**Mitigation**:
1. Comprehensive unit tests for code generator
2. Validate generated code compiles and passes type checking
3. Compare generated accessors to manual queries (output identical)
4. Staged rollout with feature flags

**Trade-off**: Accept one-time generation complexity for long-term maintainability gain.

---

### Risk 2: Memory Usage

**Risk**: Loading 70 tables into RAM → OOM on large projects

**Likelihood**: Low
**Impact**: MEDIUM (taint fails to run)

**Mitigation**:
1. Profiling shows 500MB max for 200K LOC project
2. Modern machines have 16GB+ RAM (500MB = 3%)
3. Memory limits already exist (cache currently loads ~40 tables)
4. Can add lazy loading if needed (future enhancement)

**Trade-off**: 500MB RAM for 100-300x speedup is acceptable.

---

### Risk 3: Breaking Internal APIs

**Risk**: Taint modules reference old database.py functions

**Likelihood**: HIGH (internal refactor)
**Impact**: MEDIUM (compilation errors, caught immediately)

**Mitigation**:
1. Keep database.py as thin wrapper initially (Phase 2)
2. Update all references systematically (grep + replace)
3. Comprehensive test suite catches breakage
4. Type hints catch incompatible usage

**Trade-off**: One-time migration pain for architectural cleanup.

---

### Risk 4: Behavior Changes (Subtle Bugs)

**Risk**: Database-driven discovery finds different sources/sinks

**Likelihood**: Low
**Impact**: HIGH (false positives/negatives)

**Mitigation**:
1. Parallel validation: Run old + new, compare results
2. Extensive testing on fixture projects
3. Golden test suite (known vulnerabilities must still be found)
4. Gradual rollout with monitoring

**Trade-off**: Small risk for massive maintainability improvement.

---

## Migration Plan

### Phase 1: Schema Auto-Generation (Week 1)

**Tasks**:
1. Add SchemaCodeGenerator to schema.py
2. Implement generate_typed_dicts()
3. Implement generate_accessor_classes()
4. Implement generate_memory_cache()
5. Generate code on import (or build time)

**Validation**:
- Generated code compiles
- TypedDicts pass mypy --strict
- SchemaMemoryCache instantiates
- NO taint code uses it yet (parallel infrastructure)

**Rollback**: Delete SchemaCodeGenerator (no impact, additive only)

---

### Phase 2: Replace Memory Cache (Week 2)

**Tasks**:
1. Update taint/core.py to use SchemaMemoryCache
2. Add feature flag: `THEAUDITOR_SCHEMA_CACHE=1`
3. Run both caches in parallel, compare results
4. Keep database.py as fallback

**Validation**:
- Taint results match exactly (old vs new cache)
- Memory usage within limits
- Performance same or better

**Rollback**: Flip feature flag to old cache

---

### Phase 3: Database-Driven Discovery (Week 3)

**Tasks**:
1. Implement discover_sources() (database-driven)
2. Implement discover_sinks() (database-driven)
3. Add feature flag: `THEAUDITOR_DISCOVER_SOURCES=1`
4. Compare discovered sources/sinks to hardcoded patterns

**Validation**:
- Same sources/sinks discovered
- No false negatives (all previous sources still found)
- Acceptable false positives (database has more data)

**Rollback**: Flip feature flag to hardcoded patterns

---

### Phase 4: Delete Fallback & Unify CFG (Week 4)

**Tasks**:
1. Delete taint/database.py (1,447 lines)
2. Delete memory_cache.py, python_memory_cache.py
3. Delete sources.py, config.py, registry.py
4. Merge CFG files into analysis.py
5. Remove feature flags

**Validation**:
- All tests pass
- `aud full` pipeline completes
- Performance improvement verified
- No regressions in taint findings

**Rollback**: Revert commit (single atomic change)

---

## Open Questions

### Q1: Should generation happen at build time or import time?

**Current Decision**: Import time (runtime generation)

**Alternatives**:
- Build time: Pre-generate during `pip install`
- First import: Generate once, cache to disk

**Trade-offs**:
- Build time: Faster startup, but complex build step
- Import time: Simple, but slight startup cost (~50ms)

**Status**: Resolved - import time for simplicity

---

### Q2: Should we keep any fallback logic?

**Current Decision**: NO fallback - cache is mandatory

**Alternatives**:
- Keep fallback for tables rarely used
- Lazy loading for large tables

**Trade-offs**:
- No fallback: Simpler, but must load everything
- Fallback: Complex, defeats purpose

**Status**: Resolved - no fallback (cache always used)

---

### Q3: Should discovery be pluggable (user-defined classifiers)?

**Current Decision**: NO - built-in classification only

**Alternatives**:
- Plugin system for custom source/sink classifiers
- Configuration file for custom patterns

**Trade-offs**:
- Pluggable: More flexible, but complex
- Built-in: Simple, covers 99% of cases

**Status**: Resolved - built-in only (YAGNI, can add later)

---

## Success Criteria

### Pre-Implementation

- [x] Verification complete (verification.md)
- [x] Design complete (design.md)
- [ ] Tasks checklist complete (tasks.md)
- [ ] Architect approval
- [ ] Lead Auditor approval

### Post-Phase 1 (Schema Generation)

- [ ] Generated TypedDicts compile and type-check
- [ ] SchemaMemoryCache loads all 70 tables
- [ ] Memory usage profiled and acceptable

### Post-Phase 2 (Replace Cache)

- [ ] Taint results match exactly (old vs new)
- [ ] Performance same or better
- [ ] All tests pass

### Post-Phase 3 (Database-Driven)

- [ ] Same sources/sinks discovered
- [ ] No false negatives
- [ ] Acceptable false positive rate

### Post-Phase 4 (Complete)

- [ ] All deleted files removed
- [ ] Single CFG implementation
- [ ] 100% test pass rate
- [ ] Performance improvement verified
- [ ] Developer velocity improved (verified by adding test feature)

---

**Design Approved By**: Pending
**Date**: 2025-10-31
**Status**: AWAITING ARCHITECT & AUDITOR APPROVAL
