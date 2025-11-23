# FCE JSON Normalization Design

**Status**: ✅ READY FOR IMPLEMENTATION
**Design Date**: 2025-11-24
**Designer**: Opus (AI Lead Coder)

---

## Context

TheAuditor's FCE (Findings Consolidation Engine) currently stores all finding metadata in JSON TEXT blobs within `findings_consolidated.details_json`. This design reverses the exemption granted in commit d8370a7 based on measured performance impact of 75-700ms overhead per FCE run.

### Constraints
- Must maintain data integrity during migration
- Must follow established junction table patterns from d8370a7
- Must comply with ZERO FALLBACK policy
- Must be backwards incompatible (requires reindex)
- Must complete queries in <10ms total

### Stakeholders
- **Users**: Need fast FCE execution (<1 second)
- **Developers**: Need queryable, joinable data
- **CI/CD**: Needs predictable performance

---

## Goals / Non-Goals

### Goals
1. Eliminate 75-700ms JSON parsing overhead
2. Enable indexed queries on all finding metadata
3. Enforce schema validation at database level
4. Prevent future JSON blob violations
5. Comply with ZERO FALLBACK policy

### Non-Goals
1. Maintain backwards compatibility (clean break)
2. Support gradual migration (all-or-nothing)
3. Preserve JSON format for debugging (use SQL views instead)
4. Optimize write performance (read optimization priority)

---

## Technical Decisions

### Decision 1: Normalize into 5 Junction Tables

**Choice**: Create 5 specialized junction tables instead of 1 generic metadata table

**Rationale**:
- Each data type has different columns and indexes
- Specialized tables allow targeted optimization
- Follows Single Responsibility Principle
- Enables parallel query execution

**Alternatives Considered**:
1. **Single metadata table with type column**: Rejected - Would require type filtering on every query
2. **EAV pattern (entity-attribute-value)**: Rejected - Poor query performance, loses type safety
3. **Keep JSON but add indexes**: Rejected - SQLite cannot index into JSON fields effectively

### Decision 2: Use AUTOINCREMENT for All Junction Tables

**Choice**: Every junction table gets INTEGER PRIMARY KEY AUTOINCREMENT

**Rationale**:
- Proven pattern from commit d8370a7
- Provides stable row identifiers
- Enables efficient DELETE operations
- Simplifies foreign key relationships

**Implementation**:
```sql
CREATE TABLE finding_taint_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Always first
    finding_id TEXT NOT NULL,               -- Foreign key
    path_index INTEGER NOT NULL,            -- Order preservation
    -- data columns follow
);
```

### Decision 3: Composite Indexes for Common Queries

**Choice**: Create composite indexes matching actual query patterns

**Rationale**:
- FCE always queries by finding_id first
- Order matters for composite indexes
- Space tradeoff acceptable for performance

**Index Strategy**:
```sql
-- Primary lookup pattern: WHERE finding_id = ?
CREATE INDEX idx_finding_taint_paths_finding_id
    ON finding_taint_paths(finding_id);

-- Ordered retrieval pattern: WHERE finding_id = ? ORDER BY path_index
CREATE INDEX idx_finding_taint_paths_composite
    ON finding_taint_paths(finding_id, path_index);
```

### Decision 4: Remove ALL Try-Except Blocks

**Choice**: Delete all JSON error handling, let errors crash

**Rationale**:
- ZERO FALLBACK policy is non-negotiable
- Silent failures hide bugs
- Database should never have malformed data
- Crash-first reveals issues immediately

**Before**:
```python
try:
    details = json.loads(details_json)
except (json.JSONDecodeError, TypeError):
    pass  # CANCER - hides corruption
```

**After**:
```python
# No try-except - let it crash if data is bad
details = json.loads(details_json)  # During migration only
# After migration: direct SQL query, no JSON at all
```

### Decision 5: Connection Pool Instead of 8 Connections

**Choice**: Single shared connection for all FCE operations

**Rationale**:
- Current code opens 8 separate connections (400-800ms overhead)
- SQLite handles single connection well
- Reduces resource usage
- Simplifies transaction management

**Implementation**:
```python
class FCE:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    # All methods reuse self.conn
```

---

## Detailed Table Designs

### 1. finding_taint_paths (Critical - 50-500ms bottleneck)

```sql
CREATE TABLE finding_taint_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,
    path_index INTEGER NOT NULL,      -- Preserves order (0, 1, 2...)

    -- Source information
    source_file TEXT,
    source_line INTEGER,
    source_column INTEGER,
    source_name TEXT,                 -- Variable/function name
    source_type TEXT,                 -- 'parameter', 'user_input', etc.
    source_pattern TEXT,               -- Pattern that matched

    -- Sink information
    sink_file TEXT,
    sink_line INTEGER,
    sink_column INTEGER,
    sink_name TEXT,
    sink_type TEXT,                   -- 'sql_query', 'exec', etc.
    sink_pattern TEXT,

    -- Path metadata
    path_length INTEGER,               -- Number of intermediate steps
    path_steps TEXT,                   -- Compressed intermediate steps
    confidence REAL,                   -- 0.0 to 1.0
    vulnerability_type TEXT,           -- 'SQL Injection', 'XSS', etc.

    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);

-- Indexes for O(log n) lookup
CREATE INDEX idx_finding_taint_paths_finding_id
    ON finding_taint_paths(finding_id);
CREATE INDEX idx_finding_taint_paths_composite
    ON finding_taint_paths(finding_id, path_index);
CREATE INDEX idx_finding_taint_paths_vulnerability
    ON finding_taint_paths(vulnerability_type);
```

### 2. finding_graph_hotspots

```sql
CREATE TABLE finding_graph_hotspots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,

    -- Graph metrics
    file_path TEXT NOT NULL,
    in_degree INTEGER,                -- Incoming connections
    out_degree INTEGER,               -- Outgoing connections
    total_connections INTEGER,        -- in + out
    betweenness_centrality REAL,      -- Graph centrality score
    clustering_coefficient REAL,      -- Local clustering
    page_rank REAL,                   -- Importance score

    -- Hotspot classification
    hotspot_type TEXT,                -- 'architectural', 'integration', etc.
    risk_score REAL,                  -- Calculated risk (0-100)

    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);

CREATE INDEX idx_finding_graph_hotspots_finding_id
    ON finding_graph_hotspots(finding_id);
CREATE INDEX idx_finding_graph_hotspots_risk
    ON finding_graph_hotspots(risk_score DESC);
```

### 3. finding_cfg_complexity

```sql
CREATE TABLE finding_cfg_complexity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,

    -- Function identification
    file_path TEXT NOT NULL,
    function_name TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,

    -- Complexity metrics
    cyclomatic_complexity INTEGER,    -- McCabe complexity
    cognitive_complexity INTEGER,     -- Cognitive complexity
    npath_complexity INTEGER,         -- Path complexity

    -- Control flow metrics
    block_count INTEGER,              -- Number of basic blocks
    edge_count INTEGER,               -- Number of edges
    loop_count INTEGER,               -- Number of loops
    branch_count INTEGER,             -- Number of branches

    -- Flags
    has_recursion INTEGER,            -- 0 or 1
    has_goto INTEGER,                 -- 0 or 1
    has_multiple_returns INTEGER,     -- 0 or 1

    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);

CREATE INDEX idx_finding_cfg_complexity_finding_id
    ON finding_cfg_complexity(finding_id);
CREATE INDEX idx_finding_cfg_complexity_cyclomatic
    ON finding_cfg_complexity(cyclomatic_complexity DESC);
```

### 4. finding_metadata

```sql
CREATE TABLE finding_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,
    metadata_type TEXT NOT NULL,      -- 'churn', 'coverage', 'cwe', 'cve'

    -- Churn metrics (when type='churn')
    commits_30d INTEGER,
    commits_90d INTEGER,
    commits_365d INTEGER,
    unique_authors INTEGER,
    lines_added INTEGER,
    lines_deleted INTEGER,
    days_since_modified INTEGER,

    -- Coverage metrics (when type='coverage')
    line_coverage_percent REAL,
    branch_coverage_percent REAL,
    function_coverage_percent REAL,
    uncovered_lines TEXT,              -- Comma-separated line numbers

    -- Vulnerability classification (when type='cwe' or 'cve')
    vuln_id TEXT,                     -- 'CWE-79', 'CVE-2024-1234'
    vuln_name TEXT,                   -- Human-readable name
    vuln_severity TEXT,               -- 'critical', 'high', 'medium', 'low'
    cvss_score REAL,                  -- 0.0 to 10.0

    -- Generic metadata (all types)
    metadata_json TEXT,               -- ONLY for truly dynamic data

    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);

CREATE INDEX idx_finding_metadata_finding_id
    ON finding_metadata(finding_id);
CREATE INDEX idx_finding_metadata_type
    ON finding_metadata(metadata_type);
CREATE INDEX idx_finding_metadata_composite
    ON finding_metadata(finding_id, metadata_type);
```

### 5. symbol_parameters

```sql
CREATE TABLE symbol_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id TEXT NOT NULL,
    param_index INTEGER NOT NULL,      -- Parameter position (0-based)

    -- Parameter details
    param_name TEXT NOT NULL,
    param_type TEXT,                  -- Type annotation if available
    default_value TEXT,                -- Default value if provided

    -- Flags
    is_optional INTEGER DEFAULT 0,    -- Has default value
    is_variadic INTEGER DEFAULT 0,    -- *args or **kwargs
    is_keyword_only INTEGER DEFAULT 0,-- After * in Python

    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE INDEX idx_symbol_parameters_symbol_id
    ON symbol_parameters(symbol_id);
CREATE INDEX idx_symbol_parameters_composite
    ON symbol_parameters(symbol_id, param_index);
```

---

## Query Performance Comparison

### Before (JSON TEXT with parsing)

```python
# Load taint paths - 50-500ms
cursor.execute("SELECT details_json FROM findings_consolidated WHERE id = ?", (finding_id,))
details_json = cursor.fetchone()[0]
details = json.loads(details_json)  # 50-500ms for large paths
taint_paths = details.get('paths', [])
```

### After (Indexed JOIN)

```python
# Load taint paths - <1ms
cursor.execute("""
    SELECT source_file, source_line, source_name,
           sink_file, sink_line, sink_name,
           vulnerability_type, confidence
    FROM finding_taint_paths
    WHERE finding_id = ?
    ORDER BY path_index
""", (finding_id,))
taint_paths = cursor.fetchall()  # <1ms with index
```

**Performance Improvement**: 50-500x faster

---

## Migration Strategy

### Phase 1: Schema Addition (Non-Breaking)
1. Add new tables via schema migration
2. Update schema version number
3. No data migration yet

### Phase 2: Dual Write (Testing)
1. Write to BOTH JSON and normalized tables
2. Verify data integrity
3. Compare query results

### Phase 3: Read Migration (Switch)
1. Update FCE to read from normalized tables
2. Remove json.loads() calls
3. Verify performance improvement

### Phase 4: Cleanup (Breaking)
1. Drop details_json column
2. Drop parameters column
3. Remove JSON write code

---

## Schema Validator Implementation

```python
def validate_no_json_blobs(tables: list[Table]) -> None:
    """Enforce ZERO JSON policy at schema load time."""

    LEGITIMATE_EXCEPTIONS = {
        # graphs.db metadata (different database)
        ('nodes', 'metadata'),
        ('edges', 'metadata'),

        # Planning system (truly dynamic)
        ('plan_documents', 'document_json'),

        # Raw debugging data (not parsed)
        ('react_hooks', 'dependency_array'),
    }

    violations = []
    for table in tables:
        for column in table.columns:
            # Check for JSON-like column names
            suspicious = (
                column.name.endswith('_json') or
                column.name.endswith('_config') or
                column.name == 'dependencies' or
                column.name == 'parameters' or
                column.name == 'metadata'
            )

            if suspicious and column.type == 'TEXT':
                table_col = (table.name, column.name)
                if table_col not in LEGITIMATE_EXCEPTIONS:
                    violations.append(table_col)

    if violations:
        violation_list = ', '.join(f"{t}.{c}" for t, c in violations)
        raise AssertionError(
            f"JSON blob violations detected: {violation_list}. "
            f"Normalize these columns into junction tables."
        )
```

---

## Risks and Mitigations

### Risk 1: Data Loss During Migration
**Mitigation**:
- Test migration on 10+ real projects
- Validate row counts match
- Keep backup of old database

### Risk 2: Query Performance Regression
**Mitigation**:
- Profile with cProfile before/after
- Add EXPLAIN QUERY PLAN tests
- Monitor index usage

### Risk 3: Schema Evolution Complexity
**Mitigation**:
- Document all columns clearly
- Use schema versioning
- Provide migration scripts

### Risk 4: Breaking Downstream Tools
**Mitigation**:
- Search for all details_json consumers
- Update each consumer explicitly
- No backwards compatibility layer

---

## Testing Strategy

### Unit Tests
```python
def test_taint_path_normalization():
    """Verify taint paths preserve all data."""
    original_json = {
        'source': {'file': 'a.py', 'line': 10},
        'sink': {'file': 'b.py', 'line': 20},
        'path': [{'file': 'c.py', 'line': 15}],
        'confidence': 0.9
    }

    # Write to normalized table
    write_taint_path(finding_id, original_json)

    # Read back
    retrieved = read_taint_path(finding_id)

    # Verify all fields preserved
    assert retrieved['source_file'] == 'a.py'
    assert retrieved['source_line'] == 10
    assert retrieved['sink_file'] == 'b.py'
    assert retrieved['sink_line'] == 20
    assert retrieved['confidence'] == 0.9
```

### Performance Tests
```python
def test_fce_performance():
    """Verify <10ms query overhead."""
    import cProfile
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()

    # Run FCE
    results = run_fce(test_project_path)

    profiler.disable()
    stats = pstats.Stats(profiler)

    # Check no json.loads in top functions
    top_functions = stats.get_stats_profile().func_profiles
    assert 'json.loads' not in str(top_functions[:20])

    # Verify total time
    total_time = stats.total_tt
    assert total_time < 1.0  # Under 1 second
```

### Integration Tests
- Run on TheAuditor's own codebase
- Run on 10 open source projects
- Verify finding counts match
- Verify no data loss

---

## Open Questions

1. **Should path_steps be TEXT or normalized?**
   - Current: TEXT with compressed representation
   - Alternative: Separate path_steps table
   - Decision: TEXT for now, normalize if >1KB average

2. **Should we add database triggers for validation?**
   - Pro: Enforce constraints at DB level
   - Con: Harder to debug
   - Decision: No triggers, validate in Python

3. **Should we version the schema in the database?**
   - Current: No version tracking
   - Proposal: Add schema_version table
   - Decision: Yes, add in separate PR

---

## Success Criteria

1. ✅ FCE execution time reduced by >90%
2. ✅ All json.loads() calls eliminated from FCE
3. ✅ Zero data loss during migration
4. ✅ All tests passing
5. ✅ Schema validator prevents future violations
6. ✅ ZERO FALLBACK policy compliance

---

**Next Steps**:
1. Architect approves design
2. Implement schema changes
3. Update FCE to use normalized tables
4. Remove JSON code paths
5. Validate performance improvement