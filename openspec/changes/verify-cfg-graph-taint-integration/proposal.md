# Proposal: Verify and Enhance CFG/Graph Integration with Taint Analysis

**Change ID**: `verify-cfg-graph-taint-integration`
**Type**: Investigation + Enhancement
**Priority**: P0 (Performance + Correctness)
**Status**: Proposed

## Problem Statement

Following extensive refactors focused on database-first architecture, there is reasonable suspicion that:

1. **CFG integration** may be "light" - incomplete extraction or consumption
2. **Graph integration** may be "low" - insufficient data feeding taint analysis
3. **Memory cache** may not mirror ALL consumed data (critical for 8,461x speedup)
4. **Cross-module contracts** may have drift after independent refactors

**Risk**: Working on the surface, broken underneath.

## Investigation Scope

**Files Analyzed** (Complete Reads - No Partial/Grep):

### Indexer Layer (4 files)
- `indexer/__init__.py` - IndexerOrchestrator
- `indexer/database.py` - Database operations
- `indexer/schema.py` - Schema contract system
- `indexer/extractors/__init__.py` - Extractor registry

### Graph Layer (3 files)
- `graph/builder.py` - Dependency graph building
- `graph/cfg_builder.py` - CFG construction
- `graph/store.py` - Graph persistence (graphs.db)

### Taint Layer (11 files - Complete Coverage)
- `taint/__init__.py` - Module exports
- `taint/core.py` - Main trace_taint()
- `taint/config.py` - TaintConfig
- `taint/sources.py` - Pattern definitions
- `taint/propagation.py` - Worklist algorithm
- `taint/database.py` - Query operations
- **`taint/memory_cache.py`** - 31 indexes, 1086 lines (**CRITICAL**)
- `taint/interprocedural.py` - Cross-function tracking
- `taint/interprocedural_cfg.py` - CFG-based interprocedural
- `taint/cfg_integration.py` - PathAnalyzer, flow-sensitive analysis
- `taint/registry.py` - Pattern registry

## CRITICAL FINDINGS

### Finding 1: CFG Cache Integration Gap (P0 - Performance)

**Location**: `taint/memory_cache.py:376-454`

**What's Loaded**:
```python
# memory_cache.py loads ALL CFG tables with 8 indexes:
self.cfg_blocks = []                        # Primary storage
self.cfg_blocks_by_file = defaultdict(list)         # Index 1
self.cfg_blocks_by_function = defaultdict(list)     # Index 2
self.cfg_blocks_by_id = {}                          # Index 3
self.cfg_edges_by_file = defaultdict(list)          # Index 4
self.cfg_edges_by_function = defaultdict(list)      # Index 5
self.cfg_edges_by_source = defaultdict(list)        # Index 6
self.cfg_edges_by_target = defaultdict(list)        # Index 7
self.cfg_statements_by_block = defaultdict(list)    # Index 8
```

**What's NOT Using It**:
```python
# taint/database.py - NONE of these accept cache parameter:

def get_block_for_line(cursor, file_path, line, function_name=None):
    # Line 841 - ❌ NO cache parameter
    # Queries: cfg_blocks table directly via cursor

def get_paths_between_blocks(cursor, file_path, source_block_id, sink_block_id, max_paths=100):
    # Line 892 - ❌ NO cache parameter
    # Queries: cfg_edges table directly via cursor

def get_block_statements(cursor, block_id):
    # Line 952 - ❌ NO cache parameter
    # Queries: cfg_block_statements table directly via cursor

def get_cfg_for_function(cursor, file_path, function_name):
    # Line 984 - ❌ NO cache parameter
    # Queries: cfg_blocks AND cfg_edges via cursor
```

**Impact Analysis**:
- **Memory Waste**: ~100-200MB CFG data loaded but unused
- **Performance Loss**: Every CFG query hits disk instead of O(1) RAM lookup
- **Pipeline Slowdown**: cfg_integration.py PathAnalyzer calls get_cfg_for_function() on EVERY flow-sensitive analysis
- **Interprocedural Slowdown**: interprocedural_cfg.py InterProceduralCFGAnalyzer uses PathAnalyzer (cascading disk hits)

**Evidence Trail**:
1. `memory_cache.py:376-454` - Loads cfg_blocks, cfg_edges, cfg_block_statements
2. `memory_cache.py:90-98` - Creates 8 CFG-specific indexes
3. `taint/database.py:841-1046` - All 4 CFG query functions lack `cache` parameter
4. `taint/cfg_integration.py:90` - PathAnalyzer calls `get_cfg_for_function(cursor, ...)` - no cache
5. `taint/interprocedural_cfg.py:138` - Creates PathAnalyzer (inherits no-cache behavior)

**Severity**: P0 - This defeats the entire purpose of memory cache for CFG operations.

---

### Finding 2: CFG Extraction Chain - Complete But Cache Disconnected (P0 - Verification)

**CFG Extraction Chain** (COMPLETE):

1. **Extraction**: `ast_extractors/python_impl.py::extract_python_cfg()` and `ast_extractors/typescript_impl.py::extract_typescript_cfg()`
2. **Extractor Integration**: `indexer/extractors/python.py:161` and `indexer/extractors/javascript.py:323` call `extract_cfg()`
3. **Storage**: `indexer/__init__.py:814-839` processes CFG data and calls `db_manager.add_cfg_block/edge/statement()`
4. **Database**: `indexer/database.py` stores in `cfg_blocks`, `cfg_edges`, `cfg_block_statements` tables
5. **Cache Loading**: `memory_cache.py:376-454` loads ALL CFG tables with 8 indexes
6. **Consumption**: ❌ `taint/database.py` CFG query functions DON'T accept cache parameter

**Verification Result**: CFG extraction works for Python AND JavaScript/TypeScript. The problem is cache integration gap (Finding 1), NOT missing extraction.

**Graph Database Separation** (INTENTIONAL):

`.pf/graphs.db` is INTENTIONALLY separate from `.pf/repo_index.db` and serves multiple purposes across the entire pipeline. This separation is by design and will NOT be modified.

- **graphs.db**: Import/call graphs with rich metadata (LOC, churn, visualization)
- **repo_index.db**: Symbols and code structure for taint analysis
- **Status**: Working as designed, no changes needed

---

### Finding 3: Memory Cache Coverage Verification (P1 - Completeness)

**What's Loaded** (memory_cache.py:143-510):

**Core Tables** (11 indexes):
- ✅ `symbols` - 4 indexes (by_line, by_name, by_file, by_type)
- ✅ `assignments` - 3 indexes (by_func, by_target, by_file)
- ✅ `function_call_args` - 3 indexes (by_caller, by_callee, by_file)
- ✅ `function_returns` - 1 index (by_function)

**CFG Tables** (8 indexes):
- ✅ `cfg_blocks` - 3 indexes (by_file, by_function, by_id)
- ✅ `cfg_edges` - 4 indexes (by_file, by_function, by_source, by_target)
- ✅ `cfg_block_statements` - 1 index (by_block)

**Taint-Specialized Tables** (8 indexes):
- ✅ `sql_queries` - 2 indexes (by_type, by_file)
- ✅ `orm_queries` - 2 indexes (by_model, by_file)
- ✅ `react_hooks` - 2 indexes (by_name, by_file)
- ✅ `variable_usage` - 2 indexes (by_name, by_file)

**Security Tables** (4 indexes):
- ✅ `api_endpoints` - 2 indexes (by_file, by_method)
- ✅ `jwt_patterns` - 2 indexes (by_file, by_type)

**Total**: 31 primary indexes + 3 pre-computed (sources, sinks, call_graph)

**Memory Management**: Cache uses dynamic RAM detection via `utils/memory.py`:
- Auto-detects system RAM using platform-specific APIs (Windows ctypes, Linux /proc/meminfo, Mac sysctl)
- Allocates 60% of system RAM by default (MEMORY_ALLOCATION_RATIO)
- Respects `THEAUDITOR_MEMORY_LIMIT_MB` environment variable
- Range: 2GB minimum, 48GB maximum
- See `utils/memory.py::get_recommended_memory_limit()` for implementation

**What's MISSING from Cache**:

Need to verify these tables are either:
1. Not needed by taint analysis, OR
2. Small enough to query directly, OR
3. Should be added to cache

Tables in schema.py NOT in memory_cache.py:
- `files` - Basic file metadata (probably OK to query)
- `imports` - Import statements (used by graph builder?)
- `refs` - References (cross-reference tracking)
- `classes` - Class definitions (OOP analysis?)
- `attributes` - Class attributes
- `decorators` - Python decorators
- `jsx_components` - React components
- `jsx_props` - Component props
- `react_state` - State management
- `env_vars` - Environment variables
- `config_entries` - Configuration values
- `docker_instructions` - Dockerfile commands
- `dependencies` - Package dependencies
- `security_headers` - HTTP security headers
- `frameworks` - Detected frameworks (**THIS ONE IS QUERIED!**)
- `framework_safe_sinks` - Safe sinks list (**THIS ONE IS QUERIED!**)
- `object_literals` - Object properties (**THIS ONE IS QUERIED!**)

**CRITICAL GAPS FOUND**:

```python
# taint/core.py:145-174 - Queries frameworks table
query = build_query('frameworks',
    ['name', 'version', 'language', 'path'],
    order_by="is_primary DESC"
)
cursor.execute(query)  # ❌ NO CACHE - hits disk
```

```python
# taint/database.py:600-668 - Queries framework_safe_sinks table
query = build_query('framework_safe_sinks', ['sink_pattern', 'reason'],
    where="is_safe = 1"
)
cursor.execute(query)  # ❌ NO CACHE - hits disk
```

```python
# interprocedural_cfg.py:224-267 - Queries object_literals table
query = build_query('object_literals',
    ['property_value'],
    where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
)
cursor.execute(query, (base_obj,))  # ❌ NO CACHE - hits disk
```

**Impact**: These are HOT PATH queries executed during taint analysis but NOT cached!

---

## Proposed Changes

### Change 1: Add CFG Cache Integration (P0)

**Affected Files**:
- `taint/database.py` - Add optional cache parameters to 4 CFG functions
- `taint/cfg_integration.py` - Pass cache to CFG query functions
- `taint/interprocedural_cfg.py` - Pass cache through PathAnalyzer

**Backward Compatible Signature Changes** (optional cache parameter with None default):
```python
# BEFORE (still works)
def get_block_for_line(cursor, file_path, line, function_name=None):
def get_paths_between_blocks(cursor, file_path, source_block_id, sink_block_id, max_paths=100):
def get_block_statements(cursor, block_id):
def get_cfg_for_function(cursor, file_path, function_name):

# AFTER (backward compatible - cache optional with None default)
def get_block_for_line(cursor, file_path, line, function_name=None, cache: Optional[Any] = None):
def get_paths_between_blocks(cursor, file_path, source_block_id, sink_block_id, max_paths=100, cache: Optional[Any] = None):
def get_block_statements(cursor, block_id, cache: Optional[Any] = None):
def get_cfg_for_function(cursor, file_path, function_name, cache: Optional[Any] = None):
```

**Backward Compatibility Guarantee**:
- Existing calls without `cache` parameter continue to work
- `cache=None` behaves identically to no cache parameter
- Database fallback ensures identical results
- Zero breaking changes to existing code

**Implementation**:
Add cache lookups before database queries, using existing indexes:
- `cache.cfg_blocks_by_function[(file, func)]`
- `cache.cfg_edges_by_function[(file, func)]`
- `cache.cfg_statements_by_block[block_id]`

**Implementation Pattern** (consistent across all functions):
```python
def get_block_for_line(cursor, file_path, line, function_name=None, cache=None):
    # 1. Try cache first if available
    if cache and hasattr(cache, 'cfg_blocks_by_function'):
        blocks = cache.cfg_blocks_by_function.get((file_path, function_name), [])
        for block in blocks:
            if block["start_line"] <= line <= block["end_line"]:
                return block

    # 2. Fallback to database (original behavior)
    query = build_query('cfg_blocks', ...)
    cursor.execute(query, ...)
    return cursor.fetchone()
```

**Expected Improvement**: 10-100x faster CFG queries (RAM vs disk)

**Note**: `memory_cache.py` is THE ONLY cache. No other cache implementations exist or should be added. Old `cfg_cache` or `graph_cache` references are deprecated.

---

### Change 2: Add Hot Path Tables to Cache (P1)

**Tables to Add**:
1. `frameworks` - Queried in trace_taint() for every analysis
2. `framework_safe_sinks` - Queried in filter_framework_safe_sinks()
3. `object_literals` - Queried in interprocedural dynamic dispatch

**Memory Impact**: ~5-10MB (these are small tables)

**Expected Improvement**: Eliminate disk queries from hot paths

---

## Success Criteria

1. **Performance**: CFG queries use cache (validate with benchmarks)
2. **Correctness**: All taint analysis paths correctly use CFG data
3. **Coverage**: CFG builder verified for Python + JS/TS
4. **Cache Completeness**: All hot path queries use cache
5. **Documentation**: Graph data separation clarified

## Clarifications Confirmed

1. **graphs.db Separation**: ✅ Intentional design, serves many purposes across pipeline. Will NOT be modified or merged.
2. **Memory Management**: ✅ Already dynamic via `utils/memory.py` - detects system RAM and allocates 60% (2-48GB range).
3. **CFG Extraction**: ✅ Complete for Python AND JavaScript/TypeScript. Verified entire chain works.
4. **Backward Compatibility**: ✅ MANDATORY - All changes use optional parameters with None defaults.
5. **Cache Implementation**: ✅ `memory_cache.py` is THE ONLY cache. No other cache implementations allowed.

## References

- Memory cache implementation: `taint/memory_cache.py`
- CFG query functions: `taint/database.py:841-1046`
- CFG integration: `taint/cfg_integration.py`
- Graph storage: `graph/store.py`
- Call graph building: `taint/database.py:671-749`

---

**Next Steps**: Await Architect approval to proceed with implementation or further investigation.
