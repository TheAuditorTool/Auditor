# Taint Analysis - Cache Integration Requirements

**Capability**: Taint Analysis
**Change Type**: Enhancement
**Related Changes**: verify-cfg-graph-taint-integration

## ADDED Requirements

### Requirement: CFG Query Cache Support

All CFG query functions MUST support optional memory cache parameter for O(1) lookups instead of disk queries.

**Rationale**: CFG queries are hot path operations during taint analysis. Without cache support, loaded CFG data (~100-200MB) sits unused in RAM while queries hit disk repeatedly, degrading performance by 10-100x.

**Affected Functions**:
- `taint/database.py::get_block_for_line()`
- `taint/database.py::get_paths_between_blocks()`
- `taint/database.py::get_block_statements()`
- `taint/database.py::get_cfg_for_function()`

#### Scenario: CFG query with cache uses O(1) RAM lookup

**Given** a MemoryCache instance with loaded CFG data
**And** a CFG query function (e.g., `get_block_for_line`)
**When** the function is called with `cache` parameter
**Then** the function MUST query the cache first using appropriate index
**And** return the result from cache if found
**And** MUST NOT execute a database query if cache hit occurs

#### Scenario: CFG query with cache miss falls back to database

**Given** a MemoryCache instance with loaded CFG data
**And** a CFG query for data not in cache
**When** the function is called with `cache` parameter
**Then** the function MUST detect cache miss
**And** execute database query as fallback
**And** return correct result from database

#### Scenario: CFG query without cache parameter works (backward compat)

**Given** existing code calling CFG query functions without cache parameter
**When** the function is called with NO cache parameter
**Then** the function MUST execute database query
**And** return correct result
**And** MUST NOT raise TypeError or require cache parameter

---

### Requirement: PathAnalyzer Cache Threading

PathAnalyzer MUST accept and use cache for all internal CFG operations.

**Rationale**: PathAnalyzer is the primary consumer of CFG data during flow-sensitive analysis. Every taint path analysis creates a PathAnalyzer instance and queries CFG multiple times. Without cache threading, cache integration is ineffective.

#### Scenario: PathAnalyzer initialization with cache

**Given** a database cursor and MemoryCache instance
**When** PathAnalyzer is initialized with `cache` parameter
**Then** PathAnalyzer MUST store cache reference
**And** MUST pass cache to `get_cfg_for_function()`
**And** MUST use cache for all subsequent CFG queries

#### Scenario: PathAnalyzer CFG block lookups use cache

**Given** a PathAnalyzer initialized with cache
**When** `find_vulnerable_paths()` is called
**Then** all `get_block_for_line()` calls MUST use cache
**And** cache hit rate MUST exceed 90% for typical analysis

#### Scenario: PathAnalyzer without cache works (backward compat)

**Given** existing code creating PathAnalyzer without cache parameter
**When** PathAnalyzer is initialized with NO cache parameter
**Then** PathAnalyzer MUST work correctly using database queries
**And** MUST NOT raise TypeError or require cache parameter

---

### Requirement: InterProceduralCFGAnalyzer Cache Propagation

InterProceduralCFGAnalyzer MUST propagate cache to all PathAnalyzer instances it creates.

**Rationale**: Interprocedural analysis creates multiple PathAnalyzer instances (one per analyzed function). Cache must propagate through all layers to maintain performance.

#### Scenario: InterProceduralCFGAnalyzer creates PathAnalyzer with cache

**Given** an InterProceduralCFGAnalyzer initialized with cache
**When** `analyze_function_call()` creates a PathAnalyzer
**Then** the PathAnalyzer MUST receive the cache parameter
**And** MUST use cache for its CFG operations

#### Scenario: Nested interprocedural analysis maintains cache

**Given** an interprocedural CFG analysis with max_depth=5
**When** analysis recurses through function calls
**Then** ALL PathAnalyzer instances at all depths MUST receive cache
**And** cache hit rate MUST remain >90% across all depths

---

## MODIFIED Requirements

### Requirement: Memory Cache CFG Data Loading

Memory cache MUST load ALL CFG tables that are queried by taint analysis.

**Rationale**: Currently memory_cache.py loads CFG tables but consumers don't use them. This requirement ensures loaded data is actually consumed.

**Change**: Modify requirement to explicitly validate cache usage.

#### Scenario: Memory cache loads cfg_blocks with indexes

**Given** a database with populated cfg_blocks table
**When** MemoryCache.preload() is called
**Then** ALL cfg_blocks MUST be loaded into cache.cfg_blocks
**And** cache.cfg_blocks_by_file index MUST be populated
**And** cache.cfg_blocks_by_function index MUST be populated
**And** cache.cfg_blocks_by_id index MUST be populated

#### Scenario: Memory cache loads cfg_edges with indexes

**Given** a database with populated cfg_edges table
**When** MemoryCache.preload() is called
**Then** ALL cfg_edges MUST be loaded into cache.cfg_edges
**And** cache.cfg_edges_by_file index MUST be populated
**And** cache.cfg_edges_by_function index MUST be populated
**And** cache.cfg_edges_by_source index MUST be populated
**And** cache.cfg_edges_by_target index MUST be populated

#### Scenario: Memory cache CFG data is consumed by queries

**Given** a MemoryCache with loaded CFG data
**When** taint analysis executes with cache enabled
**Then** CFG query functions MUST access cache.cfg_* attributes
**And** cache hit rate MUST exceed 90%
**And** database CFG queries MUST be reduced by >90%

---

### Requirement: Hot Path Table Caching

Memory cache MUST load tables queried in taint analysis hot paths.

**Rationale**: Three tables (`frameworks`, `object_literals`, `framework_safe_sinks`) are queried during taint analysis but NOT currently cached, causing unnecessary disk I/O.

**Change**: Add new tables to cache loading and provide cached query methods.

#### Scenario: Memory cache loads frameworks table

**Given** a database with populated frameworks table
**When** MemoryCache.preload() is called
**Then** ALL frameworks MUST be loaded into cache.frameworks
**And** cache.frameworks_by_name index MUST be populated
**And** `cache.get_frameworks_cached()` method MUST return loaded data

#### Scenario: Memory cache loads object_literals table

**Given** a database with populated object_literals table
**When** MemoryCache.preload() is called
**Then** ALL object_literals MUST be loaded into cache.object_literals
**And** cache.object_literals_by_variable index MUST be populated
**And** cache.object_literals_by_file index MUST be populated

#### Scenario: Taint analysis uses cached frameworks

**Given** a MemoryCache with loaded frameworks
**When** `trace_taint()` queries frameworks table
**Then** query MUST use `cache.get_frameworks_cached()` if cache available
**And** MUST fall back to database query if cache is None
**And** result MUST be identical regardless of cache usage

#### Scenario: Dynamic dispatch uses cached object literals

**Given** a MemoryCache with loaded object_literals
**When** interprocedural_cfg resolves dynamic dispatch
**Then** query MUST use cache.object_literals_by_variable if cache available
**And** MUST fall back to database query if cache is None

---

## Performance Requirements

### Requirement: CFG Query Speedup Target

CFG queries with cache MUST achieve 10-100x speedup compared to database queries.

#### Scenario: Single CFG block lookup speedup

**Given** a benchmark of 1000 `get_block_for_line()` calls
**When** executed with cache vs without cache
**Then** cached version MUST complete in ≤10% of uncached time
**And** speedup MUST be ≥10x

#### Scenario: PathAnalyzer CFG loading speedup

**Given** a benchmark of 100 PathAnalyzer initializations
**When** executed with cache vs without cache
**Then** cached version MUST complete in ≤10% of uncached time
**And** speedup MUST be ≥10x

---

### Requirement: End-to-End Pipeline Speedup

Full taint analysis pipeline with cache MUST show measurable speedup.

#### Scenario: Small project (<5K LOC) speedup

**Given** a small test project (<5K LOC) with CFG data
**When** taint analysis runs with cache vs without cache
**Then** cached version MUST complete in ≤50% of uncached time
**And** speedup MUST be ≥2x

#### Scenario: Medium project (~20K LOC) speedup

**Given** a medium test project (~20K LOC) with CFG data
**When** taint analysis runs with cache vs without cache
**Then** cached version MUST complete in ≤20% of uncached time
**And** speedup MUST be ≥5x

#### Scenario: Large project (>100K LOC) speedup

**Given** a large test project (>100K LOC) with CFG data
**When** taint analysis runs with cache vs without cache
**Then** cached version MUST complete in ≤10% of uncached time
**And** speedup MUST be ≥10x

---

### Requirement: Cache Hit Rate Target

Cache hit rate for CFG queries MUST exceed 90% during typical taint analysis.

#### Scenario: High cache hit rate maintained

**Given** a taint analysis run with cache enabled
**When** analysis completes
**Then** cache.cfg_hit_rate MUST be ≥0.90
**And** >90% of CFG queries MUST have been served from cache
**And** <10% of CFG queries MUST have hit database fallback

---

## Data Integrity Requirements

### Requirement: Cache-Database Equivalence

Query results MUST be identical whether served from cache or database.

#### Scenario: CFG block lookup equivalence

**Given** the same CFG block query parameters
**When** query is executed with cache and without cache
**Then** both results MUST be structurally identical
**And** all block attributes MUST match exactly

#### Scenario: Taint path equivalence

**Given** the same test project and analysis parameters
**When** taint analysis runs with cache vs without cache
**Then** number of detected vulnerabilities MUST be identical
**And** vulnerability types MUST be identical
**And** source/sink line numbers MUST be identical

---

## Backward Compatibility Requirements

### Requirement: Optional Cache Parameter

All cache-enabled functions MUST accept cache as optional parameter with None default.

#### Scenario: Function works without cache parameter

**Given** existing code that calls CFG functions without cache
**When** function is called with NO cache parameter
**Then** function MUST work correctly using database
**And** MUST NOT raise TypeError or parameter errors

#### Scenario: Function works with cache=None

**Given** code that explicitly passes cache=None
**When** function is called with cache=None
**Then** function MUST work correctly using database
**And** behavior MUST match NO cache parameter case

---

## Testing Requirements

### Requirement: Comprehensive Test Coverage

All cache integration MUST have unit and integration test coverage >90%.

#### Scenario: Unit tests for cache parameter

**Given** modified CFG query functions
**Then** unit tests MUST cover:
- Cache hit case
- Cache miss case
- No cache parameter case
- cache=None case

#### Scenario: Integration tests for cache propagation

**Given** modified PathAnalyzer and InterProceduralCFGAnalyzer
**Then** integration tests MUST verify:
- Cache threading through all layers
- Cache hit rate >90%
- Result equivalence with/without cache

#### Scenario: Regression test suite passes

**Given** all existing tests in tests/ directory
**When** cache integration changes are applied
**Then** 100% of existing tests MUST pass
**And** ZERO regressions MUST occur

---

## Documentation Requirements

### Requirement: Cache Parameter Documentation

All modified function signatures MUST include cache parameter documentation.

#### Scenario: Function docstring includes cache

**Given** a modified CFG query function
**Then** docstring MUST include:
- cache parameter description
- cache parameter type (Optional[MemoryCache])
- behavior with cache (O(1) lookup)
- behavior without cache (database fallback)

#### Scenario: Architecture documentation updated

**Given** CLAUDE.md documentation file
**Then** documentation MUST include:
- Memory cache CFG integration explanation
- Cache threading architecture diagram
- Performance expectations with cache
- Example usage with cache parameter

---

## Reference Implementation

### Requirement: Standard Cache Integration Pattern

All cache integration MUST follow standard pattern for consistency.

#### Scenario: Standard cache lookup pattern

**Given** a function that needs cache integration
**Then** implementation MUST follow pattern:

```python
def query_function(cursor, param1, param2, cache=None):
    """Query with optional cache support.

    Args:
        cursor: Database cursor
        param1, param2: Query parameters
        cache: Optional MemoryCache instance for O(1) lookups

    Returns:
        Query result (same format with or without cache)
    """
    # 1. Try cache first if available
    if cache and hasattr(cache, 'appropriate_index'):
        result = cache.appropriate_index.get(key)
        if result is not None:
            return result

    # 2. Fallback to database query
    query = build_query('table_name', ['columns'])
    cursor.execute(query, (param1, param2))
    result = cursor.fetchone()

    return result
```

**Then** all cache-enabled functions MUST follow this pattern:
- Cache check first
- hasattr() guard for cache methods
- Fallback to database on cache miss or no cache
- Identical return format regardless of source

---

## Success Criteria

All scenarios MUST pass for this change to be considered complete.

**Functional**:
- ✅ All CFG query functions accept cache parameter
- ✅ PathAnalyzer threads cache through
- ✅ InterProceduralCFGAnalyzer propagates cache
- ✅ Hot path tables (frameworks, object_literals) cached
- ✅ Backward compatibility maintained

**Performance**:
- ✅ CFG queries: 10-100x speedup with cache
- ✅ Pipeline: 2-20x speedup (varies by project size)
- ✅ Cache hit rate: >90%

**Quality**:
- ✅ Zero regressions
- ✅ Test coverage: >90%
- ✅ Results identical with/without cache
- ✅ Documentation complete
