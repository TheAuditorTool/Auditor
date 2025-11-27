# Implementation Tasks

**Last Updated**: 2025-11-27 (Re-verified after codebase refactors)

---

## Overview

| Phase | Tasks | Est. Changes | Status |
|-------|-------|--------------|--------|
| 1. Schema | 1 task | 30 lines | Not Started |
| 2. Writers | 3 tasks | 150 lines | Not Started |
| 3. Readers | 4 tasks | 200 lines | Not Started |
| 4. Validation | 2 tasks | 50 lines | Not Started |

---

## Phase 1: Schema Changes

### Task 1.1: Add 23 nullable columns to FINDINGS_CONSOLIDATED

**File**: `theauditor/indexer/schemas/core_schema.py`
**Location**: Lines 488-514

**BEFORE** (core_schema.py:488-514):
```python
FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("column", "INTEGER"),
        Column("rule", "TEXT", nullable=False),
        Column("tool", "TEXT", nullable=False),
        Column("message", "TEXT"),
        Column("severity", "TEXT", nullable=False),
        Column("category", "TEXT"),
        Column("confidence", "REAL"),
        Column("code_snippet", "TEXT"),
        Column("cwe", "TEXT"),
        Column("timestamp", "TEXT", nullable=False),
        Column("details_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
    ]
)
```

**AFTER**:
```python
FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
        # Core columns (unchanged)
        Column("id", "INTEGER", nullable=False, primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("column", "INTEGER"),
        Column("rule", "TEXT", nullable=False),
        Column("tool", "TEXT", nullable=False),
        Column("message", "TEXT"),
        Column("severity", "TEXT", nullable=False),
        Column("category", "TEXT"),
        Column("confidence", "REAL"),
        Column("code_snippet", "TEXT"),
        Column("cwe", "TEXT"),
        Column("timestamp", "TEXT", nullable=False),

        # CFG Analysis columns (9 keys from cfg-analysis tool)
        Column("cfg_function", "TEXT"),           # function name
        Column("cfg_complexity", "INTEGER"),      # cyclomatic complexity
        Column("cfg_block_count", "INTEGER"),     # number of blocks
        Column("cfg_edge_count", "INTEGER"),      # number of edges
        Column("cfg_has_loops", "INTEGER"),       # 0/1 boolean
        Column("cfg_has_recursion", "INTEGER"),   # 0/1 boolean
        Column("cfg_start_line", "INTEGER"),      # function start
        Column("cfg_end_line", "INTEGER"),        # function end
        Column("cfg_threshold", "INTEGER"),       # complexity threshold used

        # Graph Analysis columns (7 keys from graph-analysis tool)
        Column("graph_id", "TEXT"),               # node identifier
        Column("graph_in_degree", "INTEGER"),     # incoming connections
        Column("graph_out_degree", "INTEGER"),    # outgoing connections
        Column("graph_total_connections", "INTEGER"),
        Column("graph_centrality", "REAL"),       # betweenness centrality
        Column("graph_score", "REAL"),            # composite hotspot score
        Column("graph_cycle_nodes", "TEXT"),      # comma-separated node list for cycles

        # Mypy columns (3 keys from mypy tool)
        Column("mypy_error_code", "TEXT"),        # mypy error code (e.g., "arg-type")
        Column("mypy_severity_int", "INTEGER"),   # mypy severity as integer
        Column("mypy_column", "INTEGER"),         # column number from mypy

        # Terraform columns (4 keys from terraform tool)
        Column("tf_finding_id", "TEXT"),          # Terraform finding ID
        Column("tf_resource_id", "TEXT"),         # Resource identifier
        Column("tf_remediation", "TEXT"),         # Remediation suggestion
        Column("tf_graph_context", "TEXT"),       # Graph context JSON (kept as JSON - complex)

        # Fallback for complex/unknown data
        Column("misc_json", "TEXT"),              # Catch-all for data that doesn't fit above

        # DEPRECATED - Keep for backward compat, will be NULL going forward
        Column("details_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        # Existing indexes (unchanged)
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # New indexes for normalized columns
        ("idx_findings_cfg_complexity", ["cfg_complexity"]),
        ("idx_findings_graph_score", ["graph_score"]),
    ]
)
```

**Acceptance Criteria**:
- [ ] Schema file updated with 23 new columns + misc_json
- [ ] details_json kept for backward compatibility (will be NULL)
- [ ] `aud full --offline` creates table with new schema
- [ ] No migration needed (tables regenerated each run)

---

## Phase 2: Writer Changes

### Task 2.1: Update base_database.py write_findings_batch()

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 647-735

**Current Method Signature** (line 647):
```python
def write_findings_batch(self, findings: list[dict], tool_name: str) -> None:
```

**Current INSERT Statement** (lines 722-728):
```python
cursor.executemany(
    """INSERT INTO findings_consolidated
       (file, line, column, rule, tool, message, severity, category,
        confidence, code_snippet, cwe, timestamp, details_json)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    batch
)
```

**AFTER** - Replace JSON serialization logic (lines 670-717) with tool-specific column mapping:
```python
def write_findings_batch(self, findings: list[dict], tool_name: str) -> None:
    """Write findings to database with normalized columns by tool type."""
    if not findings:
        return

    from datetime import datetime, UTC

    cursor = self.conn.cursor()
    normalized = []

    for f in findings:
        # Get details dict (was additional_info or details_json)
        details = f.get('additional_info', f.get('details_json', {}))
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, TypeError):
                details = {}
        if not isinstance(details, dict):
            details = {}

        # Core fields (unchanged)
        file_path = f.get('file', '')
        if not isinstance(file_path, str):
            file_path = str(file_path or '')

        rule_value = f.get('rule')
        if not rule_value:
            rule_value = f.get('pattern', f.get('pattern_name', f.get('code', 'unknown-rule')))
        if isinstance(rule_value, str):
            rule_value = rule_value.strip() or 'unknown-rule'
        else:
            rule_value = str(rule_value) if rule_value is not None else 'unknown-rule'

        # Tool-specific column mapping
        cfg_function = cfg_complexity = cfg_block_count = cfg_edge_count = None
        cfg_has_loops = cfg_has_recursion = cfg_start_line = cfg_end_line = cfg_threshold = None
        graph_id = graph_in_degree = graph_out_degree = graph_total_connections = None
        graph_centrality = graph_score = graph_cycle_nodes = None
        mypy_error_code = mypy_severity_int = mypy_column = None
        tf_finding_id = tf_resource_id = tf_remediation = tf_graph_context = None
        misc_json = None

        if tool_name == 'cfg-analysis':
            cfg_function = details.get('function')
            cfg_complexity = details.get('complexity')
            cfg_block_count = details.get('block_count')
            cfg_edge_count = details.get('edge_count')
            cfg_has_loops = 1 if details.get('has_loops') else 0
            cfg_has_recursion = 1 if details.get('has_recursion') else 0
            cfg_start_line = details.get('start_line')
            cfg_end_line = details.get('end_line')
            cfg_threshold = details.get('threshold')

        elif tool_name == 'graph-analysis':
            graph_id = details.get('id') or details.get('file')
            graph_in_degree = details.get('in_degree')
            graph_out_degree = details.get('out_degree')
            graph_total_connections = details.get('total_connections')
            graph_centrality = details.get('centrality')
            graph_score = details.get('score')
            cycle_nodes = details.get('cycle_nodes', [])
            if cycle_nodes:
                graph_cycle_nodes = ','.join(str(n) for n in cycle_nodes)

        elif tool_name == 'mypy':
            mypy_error_code = details.get('error_code')
            mypy_severity_int = details.get('severity')
            mypy_column = details.get('column')

        elif tool_name == 'terraform':
            tf_finding_id = details.get('finding_id')
            tf_resource_id = details.get('resource_id')
            tf_remediation = details.get('remediation')
            tf_graph_context = details.get('graph_context_json')

        elif tool_name == 'taint' and details:
            # Taint has complex nested structure - store in misc_json
            # FCE should read from taint_flows table directly
            misc_json = json.dumps(details)

        elif details:
            # Unknown tool with details - store in misc_json
            misc_json = json.dumps(details)

        normalized.append((
            file_path,
            int(f.get('line', 0)),
            f.get('column'),
            rule_value,
            f.get('tool', tool_name),
            f.get('message', ''),
            f.get('severity', 'medium'),
            f.get('category'),
            f.get('confidence'),
            f.get('code_snippet'),
            f.get('cwe'),
            f.get('timestamp', datetime.now(UTC).isoformat()),
            # CFG columns
            cfg_function, cfg_complexity, cfg_block_count, cfg_edge_count,
            cfg_has_loops, cfg_has_recursion, cfg_start_line, cfg_end_line, cfg_threshold,
            # Graph columns
            graph_id, graph_in_degree, graph_out_degree, graph_total_connections,
            graph_centrality, graph_score, graph_cycle_nodes,
            # Mypy columns
            mypy_error_code, mypy_severity_int, mypy_column,
            # Terraform columns
            tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context,
            # Fallback
            misc_json,
            # Deprecated (NULL)
            None,
        ))

    # Batch insert with expanded columns
    for i in range(0, len(normalized), self.batch_size):
        batch = normalized[i:i+self.batch_size]
        cursor.executemany(
            """INSERT INTO findings_consolidated
               (file, line, column, rule, tool, message, severity, category,
                confidence, code_snippet, cwe, timestamp,
                cfg_function, cfg_complexity, cfg_block_count, cfg_edge_count,
                cfg_has_loops, cfg_has_recursion, cfg_start_line, cfg_end_line, cfg_threshold,
                graph_id, graph_in_degree, graph_out_degree, graph_total_connections,
                graph_centrality, graph_score, graph_cycle_nodes,
                mypy_error_code, mypy_severity_int, mypy_column,
                tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context,
                misc_json, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?,
                       ?, ?, ?, ?,
                       ?, ?)""",
            batch
        )

    self.conn.commit()
```

**Acceptance Criteria**:
- [ ] Tool-specific column mapping implemented
- [ ] All 23 new columns populated based on tool_name
- [ ] misc_json used for unknown/complex data
- [ ] details_json always NULL (deprecated)

---

### Task 2.2: Update terraform/analyzer.py direct INSERT

**File**: `theauditor/terraform/analyzer.py`
**Location**: Lines 166-195

**BEFORE** (lines 166-195):
```python
details_json = json.dumps({
    'finding_id': finding.finding_id,
    'resource_id': finding.resource_id,
    'remediation': finding.remediation,
    'graph_context_json': finding.graph_context_json,
})

cursor.execute(
    """
    INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category,
     confidence, code_snippet, cwe, timestamp, details_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        finding.file_path,
        finding.line_number,
        None,  # column
        finding.rule_id,
        'terraform',
        finding.description,
        finding.severity.lower(),
        finding.category,
        finding.confidence if hasattr(finding, 'confidence') else None,
        finding.resource_id or '',
        '',
        timestamp,
        details_json,
    ),
)
```

**AFTER**:
```python
cursor.execute(
    """
    INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category,
     confidence, code_snippet, cwe, timestamp,
     tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        finding.file_path,
        finding.line_number,
        None,  # column
        finding.rule_id,
        'terraform',
        finding.description,
        finding.severity.lower(),
        finding.category,
        finding.confidence if hasattr(finding, 'confidence') else None,
        finding.resource_id or '',  # code_snippet
        '',  # cwe
        timestamp,
        # Terraform-specific columns
        finding.finding_id,
        finding.resource_id,
        finding.remediation,
        finding.graph_context_json,
    ),
)
```

**Acceptance Criteria**:
- [ ] No json.dumps() call
- [ ] Terraform columns populated directly
- [ ] details_json not in INSERT (uses default NULL)

---

### Task 2.3: Verify taint writer (no changes needed)

**File**: `theauditor/commands/taint.py`
**Location**: Lines 476-516

**Current behavior**: Passes `additional_info: taint_path` to `write_findings_batch()`

**No changes needed**: The updated `write_findings_batch()` in Task 2.1 handles taint by storing complex data in `misc_json`. FCE should read from `taint_flows` table directly (see Task 3.4).

**Acceptance Criteria**:
- [ ] Verify taint findings use misc_json (via Task 2.1 changes)
- [ ] No changes to taint.py itself

---

## Phase 3: Reader Changes

### Task 3.1: Update fce.py load_graph_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 29-90

**BEFORE** (lines 29-90):
```python
def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load graph analysis data (hotspots and cycles) from database."""
    hotspot_files = {}
    cycles = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load hotspots with structured data from details_json
    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            hotspot_files[file_path] = details

    # Load cycles - deduplicate by cycle nodes
    cursor.execute("""
        SELECT DISTINCT details_json
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='CIRCULAR_DEPENDENCY'
    """)

    seen_cycles = set()
    for row in cursor.fetchall():
        details_json = row[0]
        if details_json:
            details = json.loads(details_json)
            cycle_nodes = details.get('cycle_nodes', [])
            cycle_size = details.get('cycle_size', len(cycle_nodes))
            ...

    conn.close()
    return hotspot_files, cycles
```

**AFTER**:
```python
def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load graph analysis data (hotspots and cycles) from database."""
    hotspot_files = {}
    cycles = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load hotspots from normalized columns (no JSON parsing)
    cursor.execute("""
        SELECT file, graph_id, graph_in_degree, graph_out_degree,
               graph_total_connections, graph_centrality, graph_score
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'
    """)

    for row in cursor.fetchall():
        file_path, graph_id, in_deg, out_deg, total_conn, centrality, score = row
        hotspot_files[file_path] = {
            'id': graph_id or file_path,
            'file': file_path,
            'in_degree': in_deg or 0,
            'out_degree': out_deg or 0,
            'total_connections': total_conn or 0,
            'centrality': centrality or 0.0,
            'score': score or 0.0,
        }

    # Load cycles from normalized columns
    cursor.execute("""
        SELECT DISTINCT graph_cycle_nodes
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='CIRCULAR_DEPENDENCY'
          AND graph_cycle_nodes IS NOT NULL
    """)

    seen_cycles = set()
    for row in cursor.fetchall():
        cycle_nodes_str = row[0]
        if cycle_nodes_str:
            cycle_nodes = cycle_nodes_str.split(',')
            cycle_size = len(cycle_nodes)

            # Deduplicate cycles by sorted node list
            cycle_key = tuple(sorted(cycle_nodes))
            if cycle_key and cycle_key not in seen_cycles:
                cycles.append({
                    'nodes': list(cycle_key),
                    'size': cycle_size
                })
                seen_cycles.add(cycle_key)

    conn.close()
    return hotspot_files, cycles
```

**Acceptance Criteria**:
- [ ] No json.loads() calls
- [ ] SELECT uses normalized columns
- [ ] Output format unchanged (backward compatible)

---

### Task 3.2: Update fce.py load_cfg_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 93-124

**BEFORE** (lines 93-124):
```python
def load_cfg_data_from_db(db_path: str) -> dict[str, Any]:
    """Load CFG complexity data from database."""
    complex_functions = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, details_json
        FROM findings_consolidated
        WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
    """)

    for row in cursor.fetchall():
        file_path, details_json = row
        if details_json:
            details = json.loads(details_json)
            function_name = details.get('function', 'unknown')
            key = f"{file_path}:{function_name}"
            complex_functions[key] = details

    conn.close()
    return complex_functions
```

**AFTER**:
```python
def load_cfg_data_from_db(db_path: str) -> dict[str, Any]:
    """Load CFG complexity data from database."""
    complex_functions = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, cfg_function, cfg_complexity, cfg_block_count, cfg_edge_count,
               cfg_has_loops, cfg_has_recursion, cfg_start_line, cfg_end_line, cfg_threshold
        FROM findings_consolidated
        WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
    """)

    for row in cursor.fetchall():
        (file_path, function, complexity, block_count, edge_count,
         has_loops, has_recursion, start_line, end_line, threshold) = row
        function_name = function or 'unknown'
        key = f"{file_path}:{function_name}"
        complex_functions[key] = {
            'file': file_path,
            'function': function_name,
            'complexity': complexity or 0,
            'block_count': block_count or 0,
            'edge_count': edge_count or 0,
            'has_loops': bool(has_loops),
            'has_recursion': bool(has_recursion),
            'start_line': start_line or 0,
            'end_line': end_line or 0,
            'threshold': threshold,
        }

    conn.close()
    return complex_functions
```

**Acceptance Criteria**:
- [ ] No json.loads() calls
- [ ] SELECT uses cfg_* columns
- [ ] Output format unchanged

---

### Task 3.3: Update fce.py load_graphql_findings_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 313-393

**Change Required**: This function reads from `graphql_findings_cache` table, not `findings_consolidated`. The details_json in that table is different.

For now, keep the json.loads since it's a different table. Add a TODO comment.

**AFTER** (add comment at line 370):
```python
# Parse details JSON for additional metadata
# TODO: Consider normalizing graphql_findings_cache table separately
details = {}
if details_json:
    details = json.loads(details_json)
```

**Acceptance Criteria**:
- [ ] TODO comment added
- [ ] No functional changes (different table)

---

### Task 3.4: Update fce.py load_taint_data_from_db() to use taint_flows

**File**: `theauditor/fce.py`
**Location**: Lines 191-241

**BEFORE** (lines 191-241):
```python
def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """Load complete taint paths from database."""
    taint_paths = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all taint findings with non-empty details_json
    cursor.execute("""
        SELECT details_json
        FROM findings_consolidated
        WHERE tool='taint'
          AND details_json IS NOT NULL
          AND details_json != '{}'
    """)

    for row in cursor.fetchall():
        details_json = row[0]
        if details_json:
            path_data = json.loads(details_json)
            # Validate it has taint path structure (source and sink required)
            if 'source' in path_data and 'sink' in path_data:
                taint_paths.append(path_data)

    conn.close()
    return taint_paths
```

**AFTER** (use taint_flows table directly):
```python
def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """Load complete taint paths from taint_flows table.

    Uses the normalized taint_flows table instead of parsing JSON from
    findings_consolidated. This is faster and provides structured access
    to source, sink, and path information.
    """
    taint_paths = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query taint_flows table directly (normalized structure)
    cursor.execute("""
        SELECT source_file, source_line, source_pattern,
               sink_file, sink_line, sink_pattern,
               vulnerability_type, path_length, hops, path_json
        FROM taint_flows
    """)

    for row in cursor.fetchall():
        (source_file, source_line, source_pattern,
         sink_file, sink_line, sink_pattern,
         vuln_type, path_length, hops, path_json) = row

        # Parse path_json for intermediate steps (only complex data left)
        path_steps = []
        if path_json:
            import json
            path_steps = json.loads(path_json)

        taint_paths.append({
            'source': {
                'file': source_file,
                'line': source_line,
                'pattern': source_pattern,
            },
            'sink': {
                'file': sink_file,
                'line': sink_line,
                'pattern': sink_pattern,
            },
            'vulnerability_type': vuln_type,
            'path_length': path_length,
            'hops': hops,
            'path': path_steps,
            'severity': 'high',  # All taint paths are high severity
        })

    conn.close()
    return taint_paths
```

**Acceptance Criteria**:
- [ ] Uses taint_flows table (already exists)
- [ ] Only path_json needs parsing (intermediate steps)
- [ ] Output format compatible with existing FCE consumers

---

### Task 3.5: Remove dead code functions

**File**: `theauditor/fce.py`
**Location**: Lines 127-188

The following functions query tools that DON'T EXIST in the database:
- `load_churn_data_from_db()` - queries `tool='churn-analysis'` (doesn't exist)
- `load_coverage_data_from_db()` - queries `tool='coverage-analysis'` (doesn't exist)

**Action**: Delete these functions OR update to query correct data source.

**Option A (Recommended)**: Delete dead code
```python
# DELETE lines 127-188 (load_churn_data_from_db and load_coverage_data_from_db)
```

**Option B**: Update to use graph-analysis tool with churn data
```python
def load_churn_data_from_db(db_path: str) -> dict[str, Any]:
    """Load code churn data from graph-analysis findings."""
    churn_files = {}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Churn data is stored in graph-analysis, not a separate tool
    cursor.execute("""
        SELECT file, misc_json
        FROM findings_consolidated
        WHERE tool='graph-analysis'
          AND misc_json LIKE '%commits_90d%'
    """)
    # ... parse churn from misc_json
```

**Acceptance Criteria**:
- [ ] Dead code removed OR updated to use correct data source
- [ ] No queries for non-existent tools

---

### Task 3.6: Update context/query.py get_findings()

**File**: `theauditor/context/query.py`
**Location**: Lines 1087-1189

**BEFORE** (lines 1154-1185):
```python
cursor.execute(f"""
    SELECT file, line, column, rule, tool, message, severity,
           category, confidence, cwe, details_json
    FROM findings_consolidated
    WHERE {where_sql}
    ORDER BY severity DESC, file, line
    LIMIT 1000
""", params)

findings = []
for row in cursor.fetchall():
    finding = {
        'file': row['file'],
        'line': row['line'],
        ...
        'cwe': row['cwe']
    }

    # Parse details_json if present
    if row['details_json']:
        import json
        try:
            finding['details'] = json.loads(row['details_json'])
        except (json.JSONDecodeError, TypeError):
            # Malformed JSON - skip details field
            pass

    findings.append(finding)
```

**AFTER**:
```python
cursor.execute(f"""
    SELECT file, line, column, rule, tool, message, severity,
           category, confidence, cwe,
           cfg_function, cfg_complexity, cfg_block_count,
           graph_id, graph_score, graph_centrality,
           mypy_error_code, tf_finding_id, tf_resource_id, tf_remediation,
           misc_json
    FROM findings_consolidated
    WHERE {where_sql}
    ORDER BY severity DESC, file, line
    LIMIT 1000
""", params)

findings = []
for row in cursor.fetchall():
    finding = {
        'file': row['file'],
        'line': row['line'],
        'column': row['column'],
        'rule': row['rule'],
        'tool': row['tool'],
        'message': row['message'],
        'severity': row['severity'],
        'category': row['category'],
        'confidence': row['confidence'],
        'cwe': row['cwe']
    }

    # Build details dict from normalized columns (no JSON parsing)
    details = {}
    tool = row['tool']

    if tool == 'cfg-analysis':
        if row['cfg_function']:
            details['function'] = row['cfg_function']
        if row['cfg_complexity']:
            details['complexity'] = row['cfg_complexity']
        if row['cfg_block_count']:
            details['block_count'] = row['cfg_block_count']

    elif tool == 'graph-analysis':
        if row['graph_id']:
            details['id'] = row['graph_id']
        if row['graph_score']:
            details['score'] = row['graph_score']
        if row['graph_centrality']:
            details['centrality'] = row['graph_centrality']

    elif tool == 'mypy':
        if row['mypy_error_code']:
            details['error_code'] = row['mypy_error_code']

    elif tool == 'terraform':
        if row['tf_finding_id']:
            details['finding_id'] = row['tf_finding_id']
        if row['tf_resource_id']:
            details['resource_id'] = row['tf_resource_id']
        if row['tf_remediation']:
            details['remediation'] = row['tf_remediation']

    elif row['misc_json']:
        # Fallback: parse misc_json for unknown tools
        import json
        try:
            details = json.loads(row['misc_json'])
        except (json.JSONDecodeError, TypeError):
            pass

    if details:
        finding['details'] = details

    findings.append(finding)
```

**Acceptance Criteria**:
- [ ] No json.loads for known tools
- [ ] Only misc_json fallback for unknown tools
- [ ] ZERO FALLBACK violation removed (try/except only for misc_json)

---

### Task 3.7: Update aws_cdk/analyzer.py from_standard_findings()

**File**: `theauditor/aws_cdk/analyzer.py`
**Location**: Lines 135-145

**BEFORE** (lines 135-145):
```python
for finding in standard_findings:
    # Parse additional_info from details_json if present
    import json
    details_json = finding.get('details_json')
    if details_json and isinstance(details_json, str):
        try:
            additional = json.loads(details_json)
        except json.JSONDecodeError:
            additional = {}
    else:
        additional = finding.get('details_json', {})
```

**AFTER**:
```python
for finding in standard_findings:
    # Get additional info from normalized columns or fallback
    additional = {}

    # CDK findings don't use details columns (they write NULL)
    # Check for misc_json fallback
    misc = finding.get('misc_json')
    if misc and isinstance(misc, str):
        import json
        try:
            additional = json.loads(misc)
        except json.JSONDecodeError:
            additional = {}
    elif isinstance(misc, dict):
        additional = misc
```

**Acceptance Criteria**:
- [ ] Uses misc_json instead of details_json
- [ ] ZERO FALLBACK violation fixed (only misc_json needs try/except)

---

### Task 3.8: Update commands/workflows.py get_workflow_findings()

**File**: `theauditor/commands/workflows.py`
**Location**: Lines 351-379

**BEFORE** (lines 352-378):
```python
cursor.execute(f"""
    SELECT file, line, rule, tool, message, severity, category, confidence,
           code_snippet, cwe, timestamp, details_json
    FROM findings_consolidated
    WHERE tool = 'github-actions-rules'
    AND {severity_condition}
    ...
""")

for row in cursor.fetchall():
    ...
    findings.append({
        ...
        "details": json.loads(details) if details else {}
    })
```

**AFTER**:
```python
cursor.execute(f"""
    SELECT file, line, rule, tool, message, severity, category, confidence,
           code_snippet, cwe, timestamp, misc_json
    FROM findings_consolidated
    WHERE tool = 'github-actions-rules'
    AND {severity_condition}
    ...
""")

for row in cursor.fetchall():
    ...
    # Workflow findings don't typically have structured details
    # Use misc_json as fallback if needed
    details = {}
    if misc_json:
        import json
        try:
            details = json.loads(misc_json)
        except (json.JSONDecodeError, TypeError):
            pass

    findings.append({
        ...
        "details": details
    })
```

**Acceptance Criteria**:
- [ ] Uses misc_json instead of details_json
- [ ] Empty dict default instead of conditional json.loads

---

## Phase 4: Validation

### Task 4.1: Create test script

**File**: `tests/test_findings_normalization.py` (new file)

```python
"""Tests for findings_consolidated normalization."""
import sqlite3
import json
import pytest
from pathlib import Path


def test_schema_has_new_columns(tmp_db):
    """Verify all 23 new columns exist."""
    cursor = tmp_db.cursor()
    cursor.execute("PRAGMA table_info(findings_consolidated)")
    columns = {row[1] for row in cursor.fetchall()}

    expected_new = {
        'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count',
        'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold',
        'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections',
        'graph_centrality', 'graph_score', 'graph_cycle_nodes',
        'mypy_error_code', 'mypy_severity_int', 'mypy_column',
        'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context',
        'misc_json',
    }

    assert expected_new.issubset(columns), f"Missing columns: {expected_new - columns}"


def test_details_json_is_null(tmp_db):
    """Verify details_json is always NULL for new writes."""
    cursor = tmp_db.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM findings_consolidated
        WHERE details_json IS NOT NULL AND details_json != '{}'
    """)
    non_null_count = cursor.fetchone()[0]
    assert non_null_count == 0, f"Found {non_null_count} rows with non-NULL details_json"


def test_cfg_columns_populated(tmp_db):
    """Verify cfg-analysis findings use cfg_* columns."""
    cursor = tmp_db.cursor()
    cursor.execute("""
        SELECT cfg_function, cfg_complexity
        FROM findings_consolidated
        WHERE tool = 'cfg-analysis'
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        assert row[0] is not None, "cfg_function should be populated"
        assert row[1] is not None, "cfg_complexity should be populated"


def test_no_json_loads_in_fce():
    """Verify fce.py has no json.loads on details_json."""
    fce_path = Path(__file__).parent.parent / "theauditor" / "fce.py"
    content = fce_path.read_text()

    # Should not find pattern: json.loads(details_json) or json.loads(row['details_json'])
    import re
    matches = re.findall(r'json\.loads\([^)]*details_json[^)]*\)', content)
    assert len(matches) == 0, f"Found json.loads on details_json: {matches}"
```

**Acceptance Criteria**:
- [ ] Tests pass after implementation
- [ ] No json.loads on details_json in fce.py
- [ ] Schema has all new columns

---

### Task 4.2: Integration test with aud full

**Steps**:
1. Run `aud full --offline` on test repo
2. Verify findings written with normalized columns
3. Verify FCE runs without json.loads errors
4. Verify report generation works

```bash
# Test commands
aud full --offline
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT cfg_complexity FROM findings_consolidated WHERE tool=\"cfg-analysis\" LIMIT 5')
for row in c.fetchall():
    print(f'cfg_complexity: {row[0]}')
conn.close()
"
```

**Acceptance Criteria**:
- [ ] `aud full --offline` completes without errors
- [ ] Normalized columns contain data
- [ ] FCE correlation runs successfully
- [ ] `aud report` generates valid output

---

## Summary

| File | Changes | json.loads Removed |
|------|---------|-------------------|
| core_schema.py | +23 columns | N/A |
| base_database.py | Rewrite write_findings_batch | 0 (was writer) |
| terraform/analyzer.py | Direct column INSERT | 0 (was writer) |
| fce.py | 4 function rewrites | 7 calls |
| context/query.py | Build dict from columns | 1 call |
| aws_cdk/analyzer.py | Use misc_json | 1 call |
| commands/workflows.py | Use misc_json | 1 call |

**Total json.loads removed**: 10 calls
**ZERO FALLBACK violations fixed**: 3 (context/query.py, aws_cdk/analyzer.py, commands/workflows.py)
