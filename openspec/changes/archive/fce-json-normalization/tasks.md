# FCE JSON Normalization Tasks

**CRITICAL**: This implementation REVERSES commit d8370a7 exemption for `findings_consolidated.details_json`
**Status**: ✅ READY FOR IMPLEMENTATION
**Estimated Time**: 3-4 days
**Implementer**: Any AI or Human following these atomic steps

---

## 0. Verification Phase (MANDATORY - Per Prime Directive)

### 0.1 Read Required Documentation
- [ ] 0.1.1 Read entire `teamsop.md` v4.20 (Prime Directive)
- [ ] 0.1.2 Read `CLAUDE.md` ZERO FALLBACK policy section (lines 194-249)
- [ ] 0.1.3 Read this proposal's `verification.md` (all verification results)
- [ ] 0.1.4 Read this proposal's `design.md` (all technical decisions)
- [ ] 0.1.5 Read commit d8370a7 full diff: `git show d8370a7`

### 0.2 Verify Current State
- [ ] 0.2.1 Read `theauditor/fce.py` lines 60-410 to confirm 7 json.loads() calls
- [ ] 0.2.2 Read `theauditor/indexer/schemas/core_schema.py` line 80 to confirm parameters column
- [ ] 0.2.3 Run `aud full` on a test project and measure FCE time with cProfile
- [ ] 0.2.4 Document baseline performance: ___ ms JSON parsing overhead

### 0.3 Get Architect Approval
- [ ] 0.3.1 Confirm Architect approves REVERSING commit d8370a7 exemption
- [ ] 0.3.2 Confirm Architect approves breaking backwards compatibility
- [ ] 0.3.3 Record approval in `verification.md` approval section
- [ ] 0.3.4 **STOP HERE IF NOT APPROVED**

---

## Task 5: FCE findings_consolidated.details_json Normalization

### 5.1 Create Schema for finding_taint_paths Table

**Location**: `theauditor/indexer/schemas/core_schema.py`

- [ ] 5.1.1 Open `core_schema.py` and locate the findings_consolidated table definition
- [ ] 5.1.2 After findings_consolidated table, add finding_taint_paths table:
```python
finding_taint_paths = Table(
    "finding_taint_paths",
    [
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("finding_id", "TEXT", nullable=False),
        Column("path_index", "INTEGER", nullable=False),
        # Source columns
        Column("source_file", "TEXT"),
        Column("source_line", "INTEGER"),
        Column("source_column", "INTEGER"),
        Column("source_name", "TEXT"),
        Column("source_type", "TEXT"),
        Column("source_pattern", "TEXT"),
        # Sink columns
        Column("sink_file", "TEXT"),
        Column("sink_line", "INTEGER"),
        Column("sink_column", "INTEGER"),
        Column("sink_name", "TEXT"),
        Column("sink_type", "TEXT"),
        Column("sink_pattern", "TEXT"),
        # Path metadata
        Column("path_length", "INTEGER"),
        Column("path_steps", "TEXT"),  # Compressed representation
        Column("confidence", "REAL"),
        Column("vulnerability_type", "TEXT"),
    ],
    indexes=[
        Index("idx_finding_taint_paths_finding_id", ["finding_id"]),
        Index("idx_finding_taint_paths_composite", ["finding_id", "path_index"]),
        Index("idx_finding_taint_paths_vulnerability", ["vulnerability_type"]),
    ],
    foreign_keys=[
        ForeignKey("finding_id", "findings_consolidated", "id", on_delete="CASCADE")
    ]
)
```
- [ ] 5.1.3 Add table to schema registry at bottom of file

### 5.2 Create Schema for finding_graph_hotspots Table

**Location**: `theauditor/indexer/schemas/core_schema.py`

- [ ] 5.2.1 After finding_taint_paths, add finding_graph_hotspots table:
```python
finding_graph_hotspots = Table(
    "finding_graph_hotspots",
    [
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("finding_id", "TEXT", nullable=False),
        Column("file_path", "TEXT", nullable=False),
        Column("in_degree", "INTEGER"),
        Column("out_degree", "INTEGER"),
        Column("total_connections", "INTEGER"),
        Column("betweenness_centrality", "REAL"),
        Column("clustering_coefficient", "REAL"),
        Column("page_rank", "REAL"),
        Column("hotspot_type", "TEXT"),
        Column("risk_score", "REAL"),
    ],
    indexes=[
        Index("idx_finding_graph_hotspots_finding_id", ["finding_id"]),
        Index("idx_finding_graph_hotspots_risk", ["risk_score"], order="DESC"),
    ],
    foreign_keys=[
        ForeignKey("finding_id", "findings_consolidated", "id", on_delete="CASCADE")
    ]
)
```
- [ ] 5.2.2 Add to schema registry

### 5.3 Create Schema for finding_cfg_complexity Table

**Location**: `theauditor/indexer/schemas/core_schema.py`

- [ ] 5.3.1 After finding_graph_hotspots, add finding_cfg_complexity table:
```python
finding_cfg_complexity = Table(
    "finding_cfg_complexity",
    [
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("finding_id", "TEXT", nullable=False),
        Column("file_path", "TEXT", nullable=False),
        Column("function_name", "TEXT", nullable=False),
        Column("start_line", "INTEGER"),
        Column("end_line", "INTEGER"),
        Column("cyclomatic_complexity", "INTEGER"),
        Column("cognitive_complexity", "INTEGER"),
        Column("npath_complexity", "INTEGER"),
        Column("block_count", "INTEGER"),
        Column("edge_count", "INTEGER"),
        Column("loop_count", "INTEGER"),
        Column("branch_count", "INTEGER"),
        Column("has_recursion", "INTEGER", default=0),
        Column("has_goto", "INTEGER", default=0),
        Column("has_multiple_returns", "INTEGER", default=0),
    ],
    indexes=[
        Index("idx_finding_cfg_complexity_finding_id", ["finding_id"]),
        Index("idx_finding_cfg_complexity_cyclomatic", ["cyclomatic_complexity"], order="DESC"),
    ],
    foreign_keys=[
        ForeignKey("finding_id", "findings_consolidated", "id", on_delete="CASCADE")
    ]
)
```
- [ ] 5.3.2 Add to schema registry

### 5.4 Create Schema for finding_metadata Table

**Location**: `theauditor/indexer/schemas/core_schema.py`

- [ ] 5.4.1 After finding_cfg_complexity, add finding_metadata table:
```python
finding_metadata = Table(
    "finding_metadata",
    [
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("finding_id", "TEXT", nullable=False),
        Column("metadata_type", "TEXT", nullable=False),
        # Churn metrics
        Column("commits_30d", "INTEGER"),
        Column("commits_90d", "INTEGER"),
        Column("commits_365d", "INTEGER"),
        Column("unique_authors", "INTEGER"),
        Column("lines_added", "INTEGER"),
        Column("lines_deleted", "INTEGER"),
        Column("days_since_modified", "INTEGER"),
        # Coverage metrics
        Column("line_coverage_percent", "REAL"),
        Column("branch_coverage_percent", "REAL"),
        Column("function_coverage_percent", "REAL"),
        Column("uncovered_lines", "TEXT"),
        # Vulnerability classification
        Column("vuln_id", "TEXT"),
        Column("vuln_name", "TEXT"),
        Column("vuln_severity", "TEXT"),
        Column("cvss_score", "REAL"),
        # Fallback for truly dynamic data
        Column("metadata_json", "TEXT"),
    ],
    indexes=[
        Index("idx_finding_metadata_finding_id", ["finding_id"]),
        Index("idx_finding_metadata_type", ["metadata_type"]),
        Index("idx_finding_metadata_composite", ["finding_id", "metadata_type"]),
    ],
    foreign_keys=[
        ForeignKey("finding_id", "findings_consolidated", "id", on_delete="CASCADE")
    ]
)
```
- [ ] 5.4.2 Add to schema registry

### 5.5 Update FCE to Read from Normalized Tables

**Location**: `theauditor/fce.py`

#### 5.5.1 Replace load_taint_data_from_db (lines 223-280)

- [ ] 5.5.1.1 Locate function at line 223
- [ ] 5.5.1.2 **REMOVE** entire function including try/except blocks
- [ ] 5.5.1.3 Replace with:
```python
def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """Load taint paths from normalized finding_taint_paths table.

    NO FALLBACKS. NO JSON PARSING. HARD FAIL ON ERROR.
    """
    taint_paths = []

    # Single connection, no fallback
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Direct query, no JSON
    cursor.execute("""
        SELECT finding_id, path_index,
               source_file, source_line, source_column, source_name, source_type, source_pattern,
               sink_file, sink_line, sink_column, sink_name, sink_type, sink_pattern,
               path_length, path_steps, confidence, vulnerability_type
        FROM finding_taint_paths
        ORDER BY finding_id, path_index
    """)

    # Group by finding_id
    current_finding = None
    current_path = None

    for row in cursor.fetchall():
        if current_finding != row['finding_id']:
            if current_path:
                taint_paths.append(current_path)
            current_finding = row['finding_id']
            current_path = {
                'finding_id': row['finding_id'],
                'source': {
                    'file': row['source_file'],
                    'line': row['source_line'],
                    'column': row['source_column'],
                    'name': row['source_name'],
                    'type': row['source_type'],
                    'pattern': row['source_pattern'],
                },
                'sink': {
                    'file': row['sink_file'],
                    'line': row['sink_line'],
                    'column': row['sink_column'],
                    'name': row['sink_name'],
                    'type': row['sink_type'],
                    'pattern': row['sink_pattern'],
                },
                'path': [],  # Will be populated from path_steps if needed
                'confidence': row['confidence'],
                'vulnerability_type': row['vulnerability_type'],
            }

    if current_path:
        taint_paths.append(current_path)

    conn.close()
    return taint_paths
```

#### 5.5.2 Replace load_graph_data_from_db (lines 29-101)

- [ ] 5.5.2.1 Locate function at line 29
- [ ] 5.5.2.2 **REMOVE** entire function including ALL try/except blocks
- [ ] 5.5.2.3 Replace with normalized table query (NO JSON):
```python
def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load graph data from normalized finding_graph_hotspots table.

    NO FALLBACKS. NO JSON PARSING. HARD FAIL ON ERROR.
    """
    hotspot_files = {}
    cycles = []  # Would need separate table for cycles

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Direct query, no JSON
    cursor.execute("""
        SELECT file_path, in_degree, out_degree, total_connections,
               betweenness_centrality, clustering_coefficient, page_rank,
               hotspot_type, risk_score
        FROM finding_graph_hotspots
        ORDER BY risk_score DESC
    """)

    for row in cursor.fetchall():
        hotspot_files[row['file_path']] = dict(row)

    conn.close()
    return hotspot_files, cycles
```

#### 5.5.3 Remove ALL Try-Except JSON Handlers

- [ ] 5.5.3.1 Search fce.py for "json.JSONDecodeError"
- [ ] 5.5.3.2 **DELETE** all try/except blocks at lines: 61-67, 79-94, 128-135, 169-174, 208-213, 266-273, 402-406
- [ ] 5.5.3.3 Replace each with direct processing (no error handling)

#### 5.5.4 Remove Table Existence Check (lines 465-476)

- [ ] 5.5.4.1 Locate lines 465-476 checking for findings_consolidated table
- [ ] 5.5.4.2 **DELETE** entire check and fallback
- [ ] 5.5.4.3 Replace with direct query (assume table exists)

### 5.6 Update Database Writers

**Location**: `theauditor/indexer/database/base_database.py` and related

#### 5.6.1 Update Taint Analysis Writer

- [ ] 5.6.1.1 Locate taint finding writer in `theauditor/taint/analysis.py`
- [ ] 5.6.1.2 Find where it writes to findings_consolidated
- [ ] 5.6.1.3 Add code to ALSO write to finding_taint_paths:
```python
# After writing to findings_consolidated
for i, path in enumerate(taint_paths):
    cursor.execute("""
        INSERT INTO finding_taint_paths (
            finding_id, path_index,
            source_file, source_line, source_column, source_name, source_type, source_pattern,
            sink_file, sink_line, sink_column, sink_name, sink_type, sink_pattern,
            path_length, confidence, vulnerability_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        finding_id, i,
        path['source']['file'], path['source']['line'], path['source'].get('column'),
        path['source'].get('name'), path['source'].get('type'), path['source'].get('pattern'),
        path['sink']['file'], path['sink']['line'], path['sink'].get('column'),
        path['sink'].get('name'), path['sink'].get('type'), path['sink'].get('pattern'),
        len(path.get('path', [])), path.get('confidence', 0.5), path.get('vulnerability_type')
    ))
```

#### 5.6.2 Update Graph Analysis Writer

- [ ] 5.6.2.1 Locate graph finding writer in `theauditor/graph/store.py` or similar
- [ ] 5.6.2.2 Add code to write to finding_graph_hotspots table
- [ ] 5.6.2.3 Remove JSON serialization, write columns directly

#### 5.6.3 Update CFG Complexity Writer

- [ ] 5.6.3.1 Locate CFG analysis writer
- [ ] 5.6.3.2 Add code to write to finding_cfg_complexity table
- [ ] 5.6.3.3 Remove JSON serialization

#### 5.6.4 Update Metadata Writers

- [ ] 5.6.4.1 Locate churn/coverage writers
- [ ] 5.6.4.2 Add code to write to finding_metadata table
- [ ] 5.6.4.3 Use metadata_type column to differentiate

### 5.7 Testing Phase 1 - Schema Validation

- [ ] 5.7.1 Run `python -c "from theauditor.indexer.schemas import core_schema"`
- [ ] 5.7.2 Verify no import errors
- [ ] 5.7.3 Run `aud full` on small test project
- [ ] 5.7.4 Check `.pf/repo_index.db` has new tables:
```bash
sqlite3 .pf/repo_index.db ".tables" | grep finding_
```
- [ ] 5.7.5 Verify all 5 new tables exist

---

## Task 6: symbols.parameters Normalization

### 6.1 Create Schema for symbol_parameters Table

**Location**: `theauditor/indexer/schemas/core_schema.py`

- [ ] 6.1.1 After symbols table definition, add:
```python
symbol_parameters = Table(
    "symbol_parameters",
    [
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("symbol_id", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_type", "TEXT"),
        Column("default_value", "TEXT"),
        Column("is_optional", "INTEGER", default=0),
        Column("is_variadic", "INTEGER", default=0),
        Column("is_keyword_only", "INTEGER", default=0),
    ],
    indexes=[
        Index("idx_symbol_parameters_symbol_id", ["symbol_id"]),
        Index("idx_symbol_parameters_composite", ["symbol_id", "param_index"]),
    ],
    foreign_keys=[
        ForeignKey("symbol_id", "symbols", "id", on_delete="CASCADE")
    ]
)
```
- [ ] 6.1.2 Add to schema registry

### 6.2 Remove parameters Column from symbols Table

- [ ] 6.2.1 Locate symbols table definition in core_schema.py (around line 75)
- [ ] 6.2.2 Find line 80: `Column("parameters", "TEXT")`
- [ ] 6.2.3 **DELETE** this line entirely
- [ ] 6.2.4 Verify no other references to symbols.parameters

### 6.3 Update Python Extractor

**Location**: `theauditor/indexer/extractors/python.py`

- [ ] 6.3.1 Search for where parameters are written to symbols table
- [ ] 6.3.2 Find JSON serialization of parameters
- [ ] 6.3.3 Replace with writes to symbol_parameters table:
```python
# Instead of: parameters = json.dumps(param_list)
# Write each parameter separately:
for i, param in enumerate(param_list):
    cursor.execute("""
        INSERT INTO symbol_parameters (
            symbol_id, param_index, param_name, param_type, default_value, is_optional
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        symbol_id, i, param['name'], param.get('type'),
        param.get('default'), 1 if param.get('default') else 0
    ))
```

### 6.4 Update JavaScript Extractor

**Location**: `theauditor/indexer/extractors/javascript.py`

- [ ] 6.4.1 Search for parameters handling
- [ ] 6.4.2 Find JSON serialization
- [ ] 6.4.3 Replace with symbol_parameters writes
- [ ] 6.4.4 **COORDINATE WITH AI #3** if they modify lines 748-768

### 6.5 Update Consumers

- [ ] 6.5.1 Search entire codebase for "symbols.parameters"
- [ ] 6.5.2 Update each consumer to JOIN symbol_parameters table
- [ ] 6.5.3 Verify taint/discovery.py no longer needs parameters parsing

### 6.6 Testing Phase 2 - Parameters Validation

- [ ] 6.6.1 Create test Python file with functions having parameters
- [ ] 6.6.2 Run indexer on test file
- [ ] 6.6.3 Query symbol_parameters table:
```sql
SELECT * FROM symbol_parameters WHERE symbol_id IN (
    SELECT id FROM symbols WHERE type = 'function' LIMIT 5
);
```
- [ ] 6.6.4 Verify parameters are correctly stored with indexes

---

## Task 7: Schema Contract Validation

### 7.1 Create JSON Blob Detector

**Location**: `theauditor/indexer/schema.py` (or create if doesn't exist)

- [ ] 7.1.1 Add validation function:
```python
def validate_no_json_blobs(tables: list) -> None:
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

### 7.2 Hook Validator into Schema Load

**Location**: `theauditor/indexer/database/__init__.py` or similar

- [ ] 7.2.1 Find where schemas are loaded/initialized
- [ ] 7.2.2 Add call to validate_no_json_blobs(all_tables)
- [ ] 7.2.3 Ensure it runs BEFORE database creation

### 7.3 Test Validator

- [ ] 7.3.1 Temporarily add a test column ending in "_json"
- [ ] 7.3.2 Run schema load
- [ ] 7.3.3 Verify AssertionError is raised
- [ ] 7.3.4 Remove test column
- [ ] 7.3.5 Verify schema loads successfully

---

## Task 8: Performance Validation

### 8.1 Baseline Measurement

- [ ] 8.1.1 Run FCE on large project WITH JSON parsing:
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
run_fce(project_path)
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats('json.loads', 10)
```
- [ ] 8.1.2 Record total time spent in json.loads: ___ ms

### 8.2 Post-Implementation Measurement

- [ ] 8.2.1 Run same test AFTER normalization
- [ ] 8.2.2 Verify json.loads no longer appears in top functions
- [ ] 8.2.3 Record new FCE total time: ___ ms
- [ ] 8.2.4 Calculate improvement: ___% reduction

### 8.3 Query Performance Test

- [ ] 8.3.1 Test indexed query performance:
```sql
EXPLAIN QUERY PLAN
SELECT * FROM finding_taint_paths WHERE finding_id = 'test-id';
```
- [ ] 8.3.2 Verify "USING INDEX" in plan
- [ ] 8.3.3 Measure actual query time: should be <1ms

---

## Task 9: Integration Testing

### 9.1 Full Pipeline Test

- [ ] 9.1.1 Delete `.pf/` directory entirely
- [ ] 9.1.2 Run `aud full` on TheAuditor itself
- [ ] 9.1.3 Verify no errors during indexing
- [ ] 9.1.4 Verify new tables populated
- [ ] 9.1.5 Run FCE and verify output

### 9.2 Data Integrity Test

- [ ] 9.2.1 Compare finding counts before/after
- [ ] 9.2.2 Verify no findings lost
- [ ] 9.2.3 Spot check 10 random taint paths
- [ ] 9.2.4 Verify path order preserved (path_index)

### 9.3 ZERO FALLBACK Compliance Test

- [ ] 9.3.1 Grep for "try.*json" in fce.py
- [ ] 9.3.2 Verify NO try/except blocks remain
- [ ] 9.3.3 Grep for "if.*exists" (table checks)
- [ ] 9.3.4 Verify NO existence checks remain

---

## Task 10: Cleanup

### 10.1 Remove Old Code

- [ ] 10.1.1 Remove old JSON writing code from all writers
- [ ] 10.1.2 Remove details_json column references
- [ ] 10.1.3 Remove parameters column references
- [ ] 10.1.4 Delete any migration/compatibility code

### 10.2 Documentation

- [ ] 10.2.1 Update this proposal status to COMPLETED
- [ ] 10.2.2 Document final performance numbers in verification.md
- [ ] 10.2.3 Update Architecture.md with new schema
- [ ] 10.2.4 Add migration guide for users

### 10.3 Final Validation

- [ ] 10.3.1 Run `openspec validate fce-json-normalization --strict`
- [ ] 10.3.2 Fix any validation errors
- [ ] 10.3.3 Commit all changes
- [ ] 10.3.4 Create PR for review

---

## Completion Checklist

**Must complete ALL items before marking proposal complete:**

- [ ] All 7 json.loads() removed from FCE
- [ ] All try/except blocks removed (ZERO FALLBACK)
- [ ] All table existence checks removed
- [ ] 5 normalized tables created and populated
- [ ] symbols.parameters column removed
- [ ] Schema validator preventing new violations
- [ ] FCE overhead reduced from 75-700ms to <10ms
- [ ] All tests passing
- [ ] No data loss confirmed
- [ ] Performance improvement measured and documented

---

## Rollback Plan

If critical issues discovered:

1. **Revert schema changes**: Remove new tables
2. **Restore JSON columns**: Re-add details_json and parameters
3. **Revert FCE code**: Git revert the FCE changes
4. **Re-index**: Run `aud full` to regenerate database

**Time to rollback**: ~30 minutes

---

**Final Note**: This implementation is BREAKING. Users MUST run `aud full` after updating to regenerate their database with the new schema. There is NO backwards compatibility.