# Implementation Tasks: Sparse Wide Table Normalization

**VERIFIED**: 2025-11-24 against live database and codebase
**Verifier**: Opus (AI Lead Coder)
**Protocol**: teamsop.md v4.20 Prime Directive

---

## Prerequisites (READ FIRST)

1. Read `proposal.md` - Understand what and why
2. Read `design.md` - Understand technical decisions
3. Read `verification.md` - Understand verified facts
4. Read `teamsop.md` - Understand Prime Directive
5. Read `CLAUDE.md:194-249` - Understand ZERO FALLBACK policy

---

## VERIFIED DATA DISTRIBUTION (2025-11-24)

**Tools with non-empty details_json** (21% of rows = 4,521/21,900):

| Tool | Rows | Keys |
|------|------|------|
| mypy | 4,397 | mypy_severity, mypy_code, hint |
| cfg-analysis | 66 | complexity, block_count, edge_count, start_line, end_line, function, has_loops, max_nesting, file |
| graph-analysis | 50 | id, in_degree, out_degree, centrality, churn, loc, score |
| terraform | 7 | finding_id, resource_id, remediation, graph_context_json (NULL) |
| taint | 1 | source (DICT), sink (DICT), path (LIST), + 11 more |

**Tools with EMPTY details_json** (79% of rows = 17,379/21,900):
- ruff: 11,604 rows
- patterns: 5,298 rows
- eslint: 463 rows
- cdk: 14 rows

**CRITICAL FINDING**: `churn-analysis` and `coverage-analysis` tools DO NOT EXIST.
- `load_churn_data_from_db()` at fce.py:145-181 queries non-existent tool (dead code)
- `load_coverage_data_from_db()` at fce.py:184-220 queries non-existent tool (dead code)
- Churn data is stored in `graph-analysis` tool (key: `churn`)

---

## 0. Verification (MANDATORY BEFORE ANY CODE)

### Task 0.1: Verify Schema Location

**Command**:
```bash
grep -n "FINDINGS_CONSOLIDATED = TableSchema" theauditor/indexer/schemas/core_schema.py
```

**Expected**: Line 490

**Verify**: Read lines 490-516 to confirm 14 columns including `details_json`

---

### Task 0.2: Verify Write Path Location

**Command**:
```bash
grep -n "INSERT INTO findings_consolidated" theauditor/indexer/database/base_database.py
```

**Expected**: Line 688

**Verify**: Read lines 630-700 to confirm write logic structure

---

### Task 0.3: Verify FCE Read Locations

**Command**:
```bash
grep -n "json.loads.*details" theauditor/fce.py
```

**Expected**: Lines 63, 81, 130, 171, 210, 268

**Verify**: 6 json.loads calls exist

---

### Task 0.4: Verify Database State

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('''SELECT tool, COUNT(*), SUM(CASE WHEN details_json != \"{}\" THEN 1 ELSE 0 END)
             FROM findings_consolidated GROUP BY tool ORDER BY COUNT(*) DESC''')
for row in c.fetchall():
    print(f'{row[0]}: {row[2]}/{row[1]} with data')
"
```

**Expected output matches verified data distribution above**

---

## 1. Schema Changes

### Task 1.1: Update FINDINGS_CONSOLIDATED Schema

**File**: `theauditor/indexer/schemas/core_schema.py`
**Location**: Lines 490-516

**COMPLETE BEFORE** (copy of current code):
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

**COMPLETE AFTER** (replace entire block):
```python
FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
        # === BASE COLUMNS (13) - unchanged ===
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

        # === MYPY COLUMNS (3) - 4,397 rows use these ===
        Column("mypy_severity", "TEXT"),       # "error", "warning", "note"
        Column("mypy_code", "TEXT"),           # "no-untyped-def", "var-annotated", etc.
        Column("mypy_hint", "TEXT"),           # Additional hint text (261 rows)

        # === CFG-ANALYSIS COLUMNS (8) - 66 rows use these ===
        # Note: 'file' key in details_json is redundant with base 'file' column, skip it
        Column("cfg_complexity", "INTEGER"),   # Cyclomatic complexity value
        Column("cfg_block_count", "INTEGER"),  # Number of basic blocks
        Column("cfg_edge_count", "INTEGER"),   # Number of control flow edges
        Column("cfg_start_line", "INTEGER"),   # Function start line
        Column("cfg_end_line", "INTEGER"),     # Function end line
        Column("cfg_function", "TEXT"),        # Function name
        Column("cfg_has_loops", "INTEGER"),    # Boolean as 0/1
        Column("cfg_max_nesting", "INTEGER"),  # Maximum nesting depth

        # === GRAPH-ANALYSIS COLUMNS (7) - 50 rows use these ===
        # Note: 'churn' is stored here (no separate churn-analysis tool)
        Column("graph_node_id", "TEXT"),       # Node identifier (was 'id')
        Column("graph_in_degree", "INTEGER"),  # Incoming dependency count
        Column("graph_out_degree", "INTEGER"), # Outgoing dependency count
        Column("graph_centrality", "REAL"),    # Betweenness centrality (0.0-1.0)
        Column("graph_churn", "INTEGER"),      # Git commit count (code churn)
        Column("graph_loc", "INTEGER"),        # Lines of code
        Column("graph_score", "REAL"),         # Composite hotspot score

        # === TERRAFORM COLUMNS (4) - 7 rows use these ===
        Column("tf_finding_id", "TEXT"),       # Terraform finding identifier
        Column("tf_resource_id", "TEXT"),      # Resource identifier
        Column("tf_remediation", "TEXT"),      # Remediation guidance
        Column("tf_graph_context", "TEXT"),    # Graph context (always NULL currently)

        # === FALLBACK COLUMN (1) - only for taint (1 row) ===
        # ONLY use for complex nested data that cannot be flattened
        Column("misc_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        # Existing indexes - unchanged
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # NOTE: Partial indexes require schema system enhancement (Task 1.2)
        # Add after Task 1.2 is complete:
        # ("idx_findings_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
        # ("idx_findings_hotspot", ["graph_score"], "graph_score IS NOT NULL"),
    ]
)
```

**Verification after edit**:
```bash
grep -c "Column(" theauditor/indexer/schemas/core_schema.py | head -1
# Should show increased column count
```

---

### Task 1.2: Add Partial Index Support (OPTIONAL - skip if time constrained)

**File**: `theauditor/indexer/database/base_database.py`

**Why**: Partial indexes only index non-NULL rows, keeping index size small for sparse columns.

**Find**: Search for index creation loop (approximately lines 300-400)
```bash
grep -n "CREATE INDEX" theauditor/indexer/database/base_database.py
```

**Change**: Update loop to handle 3-tuple format (name, columns, where_clause)

**If not implemented**: Standard indexes still work, just slightly larger. Not a blocker.

---

## 2. Writer Updates

### Task 2.1: Update base_database.py write_findings()

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 630-700 (find method `write_findings`)

**COMPLETE BEFORE** (lines 668-693):
```python
            normalized.append((
                file_path,
                int(f.get('line', 0)),
                f.get('column'),  # Optional
                rule_value,
                f.get('tool', tool_name),
                f.get('message', ''),
                f.get('severity', 'medium'),  # Default to medium if not specified
                f.get('category'),  # Optional
                f.get('confidence'),  # Optional
                f.get('code_snippet'),  # Optional
                f.get('cwe'),  # Optional
                f.get('timestamp', datetime.now(UTC).isoformat()),
                details_str  # Structured data
            ))

        # Batch insert using configured batch size for performance
        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i:i+self.batch_size]
            cursor.executemany(
                """INSERT INTO findings_consolidated
                   (file, line, column, rule, tool, message, severity, category,
                    confidence, code_snippet, cwe, timestamp, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )
```

**COMPLETE AFTER** (replace the entire section from line ~636 to ~693):
```python
        # Column mappings for tool-specific data extraction
        TOOL_COLUMN_EXTRACTORS = {
            'mypy': {
                'mypy_severity': 'mypy_severity',
                'mypy_code': 'mypy_code',
                'hint': 'mypy_hint',
            },
            'cfg-analysis': {
                'complexity': 'cfg_complexity',
                'block_count': 'cfg_block_count',
                'edge_count': 'cfg_edge_count',
                'start_line': 'cfg_start_line',
                'end_line': 'cfg_end_line',
                'function': 'cfg_function',
                'has_loops': 'cfg_has_loops',
                'max_nesting': 'cfg_max_nesting',
            },
            'graph-analysis': {
                'id': 'graph_node_id',
                'in_degree': 'graph_in_degree',
                'out_degree': 'graph_out_degree',
                'centrality': 'graph_centrality',
                'churn': 'graph_churn',
                'loc': 'graph_loc',
                'score': 'graph_score',
            },
            'terraform': {
                'finding_id': 'tf_finding_id',
                'resource_id': 'tf_resource_id',
                'remediation': 'tf_remediation',
                'graph_context_json': 'tf_graph_context',
            },
        }

        # All tool-specific columns in schema order
        TOOL_COLUMNS = [
            'mypy_severity', 'mypy_code', 'mypy_hint',
            'cfg_complexity', 'cfg_block_count', 'cfg_edge_count',
            'cfg_start_line', 'cfg_end_line', 'cfg_function',
            'cfg_has_loops', 'cfg_max_nesting',
            'graph_node_id', 'graph_in_degree', 'graph_out_degree',
            'graph_centrality', 'graph_churn', 'graph_loc', 'graph_score',
            'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context',
            'misc_json',
        ]

        normalized = []
        for f in findings:
            # Extract tool-specific data
            details = f.get('additional_info', f.get('details_json', {}))
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except (json.JSONDecodeError, TypeError):
                    details = {}
            if not isinstance(details, dict):
                details = {}

            # Get tool name
            tool = f.get('tool', tool_name)

            # Extract tool-specific column values
            extractor = TOOL_COLUMN_EXTRACTORS.get(tool, {})
            tool_values = {}
            for json_key, column_name in extractor.items():
                if json_key in details:
                    value = details[json_key]
                    # Convert bool to int for SQLite
                    if isinstance(value, bool):
                        value = 1 if value else 0
                    tool_values[column_name] = value

            # Handle different finding formats from various tools
            rule_value = f.get('rule')
            if not rule_value:
                rule_value = f.get('pattern', f.get('pattern_name', f.get('code', 'unknown-rule')))
            if isinstance(rule_value, str):
                rule_value = rule_value.strip() or 'unknown-rule'
            else:
                rule_value = str(rule_value) if rule_value is not None else 'unknown-rule'

            file_path = f.get('file', '')
            if not isinstance(file_path, str):
                file_path = str(file_path or '')

            # Build base tuple
            row = [
                file_path,
                int(f.get('line', 0)),
                f.get('column'),
                rule_value,
                tool,
                f.get('message', ''),
                f.get('severity', 'medium'),
                f.get('category'),
                f.get('confidence'),
                f.get('code_snippet'),
                f.get('cwe'),
                f.get('timestamp', datetime.now(UTC).isoformat()),
            ]

            # Add tool-specific columns (None for columns not in this tool's data)
            for col in TOOL_COLUMNS[:-1]:  # All except misc_json
                row.append(tool_values.get(col))

            # misc_json: Only for taint (complex nested data)
            if tool == 'taint' and details:
                row.append(json.dumps(details))
            else:
                row.append('{}')

            normalized.append(tuple(row))

        # Build INSERT statement with all columns
        base_cols = 'file, line, column, rule, tool, message, severity, category, confidence, code_snippet, cwe, timestamp'
        tool_cols = ', '.join(TOOL_COLUMNS)
        all_cols = f'{base_cols}, {tool_cols}'
        placeholders = ', '.join(['?'] * (12 + len(TOOL_COLUMNS)))

        insert_sql = f"""INSERT INTO findings_consolidated ({all_cols}) VALUES ({placeholders})"""

        # Batch insert
        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i:i+self.batch_size]
            cursor.executemany(insert_sql, batch)
```

**Verification after edit**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full
# Should complete without SQL errors
```

---

### Task 2.2: Update terraform/analyzer.py

**File**: `theauditor/terraform/analyzer.py`
**Location**: Lines 167-196

**COMPLETE BEFORE**:
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
                    finding.line or 0,
                    None,
                    finding.finding_id,
                    'terraform',
                    finding.title,
                    finding.severity,
                    finding.category,
                    1.0,
                    finding.resource_id or '',
                    '',
                    timestamp,
                    details_json,
                ),
            )
```

**COMPLETE AFTER**:
```python
            # Write directly to columns (no JSON serialization)
            cursor.execute(
                """
                INSERT INTO findings_consolidated
                (file, line, column, rule, tool, message, severity, category,
                 confidence, code_snippet, cwe, timestamp,
                 tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context,
                 misc_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding.file_path,
                    finding.line or 0,
                    None,
                    finding.finding_id,
                    'terraform',
                    finding.title,
                    finding.severity,
                    finding.category,
                    1.0,
                    finding.resource_id or '',
                    '',
                    timestamp,
                    # Tool-specific columns
                    finding.finding_id,        # tf_finding_id
                    finding.resource_id,       # tf_resource_id
                    finding.remediation,       # tf_remediation
                    finding.graph_context_json,  # tf_graph_context
                    '{}',                      # misc_json (not used for terraform)
                ),
            )
```

**Also remove**: The `json.dumps()` import if no longer used in file.

---

### Task 2.3: Update commands/taint.py

**File**: `theauditor/commands/taint.py`
**Location**: Lines 490-501 (inside the findings_dicts.append block)

**COMPLETE BEFORE** (verified 2025-11-24):
```python
                findings_dicts.append({
                    'file': sink.get('file', ''),                        # Sink location (where vulnerability manifests)
                    'line': int(sink.get('line', 0)),                    # Sink line number
                    'column': sink.get('column'),                        # Sink column
                    'rule': f"taint-{sink.get('category', 'unknown')}", # Sink category (xss, sql, etc.)
                    'tool': 'taint',
                    'message': message,                                  # Constructed: "XSS: req.body → res.send"
                    'severity': 'high',                                  # Default high (all taint flows are critical)
                    'category': 'injection',
                    'code_snippet': None,                                # Not available in taint path structure
                    'additional_info': taint_path                        # Store complete path (source, intermediate steps, sink)
                })
```

**COMPLETE AFTER**:
```python
                # Taint has complex nested data - store in misc_json
                # FCE will read from taint_flows table instead
                findings_dicts.append({
                    'file': sink.get('file', ''),
                    'line': int(sink.get('line', 0)),
                    'column': sink.get('column'),
                    'rule': f"taint-{sink.get('category', 'unknown')}",
                    'tool': 'taint',
                    'message': message,
                    'severity': 'high',
                    'category': 'injection',
                    'code_snippet': None,
                    'additional_info': taint_path,  # Goes to misc_json via write_findings
                })
```

**Note**: No actual change needed here - write_findings handles taint specially.

---

## 3. Reader Updates

### Task 3.1: Update fce.py load_graph_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 29-101 (entire function)

**COMPLETE BEFORE**:
```python
def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Load graph analysis data (hotspots and cycles) from database.
    ...
    """
    hotspot_files = {}
    cycles = []

    try:
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
            try:
                if details_json:
                    details = json.loads(details_json)
                    # Use file path as key, store full hotspot data
                    hotspot_files[file_path] = details
            except (json.JSONDecodeError, TypeError):
                pass

        # Load cycles - deduplicate by cycle nodes
        cursor.execute("""
            SELECT DISTINCT details_json
            FROM findings_consolidated
            WHERE tool='graph-analysis' AND rule='CIRCULAR_DEPENDENCY'
        """)

        seen_cycles = set()
        for row in cursor.fetchall():
            details_json = row[0]
            try:
                if details_json:
                    details = json.loads(details_json)
                    cycle_nodes = details.get('cycle_nodes', [])
                    cycle_size = details.get('cycle_size', len(cycle_nodes))

                    # Deduplicate cycles by sorted node list
                    cycle_key = tuple(sorted(cycle_nodes))
                    if cycle_key and cycle_key not in seen_cycles:
                        cycles.append({
                            'nodes': list(cycle_key),
                            'size': cycle_size
                        })
                        seen_cycles.add(cycle_key)
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()

    except sqlite3.Error as e:
        print(f"[FCE] Database error loading graph data: {e}")

    return hotspot_files, cycles
```

**COMPLETE AFTER**:
```python
def load_graph_data_from_db(db_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Load graph analysis data (hotspots and cycles) from database.

    Queries findings_consolidated using direct column access (no JSON parsing).
    """
    hotspot_files = {}
    cycles = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load hotspots using direct column access
    cursor.execute("""
        SELECT file, graph_node_id, graph_in_degree, graph_out_degree,
               graph_centrality, graph_churn, graph_loc, graph_score
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'
    """)

    for row in cursor.fetchall():
        file_path = row[0]
        hotspot_files[file_path] = {
            'id': row[1],
            'in_degree': row[2],
            'out_degree': row[3],
            'centrality': row[4],
            'churn': row[5],
            'loc': row[6],
            'score': row[7],
        }

    # Load cycles (cycle_nodes stored in misc_json for complex array data)
    cursor.execute("""
        SELECT DISTINCT misc_json
        FROM findings_consolidated
        WHERE tool='graph-analysis' AND rule='CIRCULAR_DEPENDENCY'
          AND misc_json != '{}'
    """)

    seen_cycles = set()
    for row in cursor.fetchall():
        # cycles have complex array data, still need JSON parse for misc_json
        if row[0]:
            details = json.loads(row[0])
            cycle_nodes = details.get('cycle_nodes', [])
            cycle_size = details.get('cycle_size', len(cycle_nodes))

            cycle_key = tuple(sorted(cycle_nodes))
            if cycle_key and cycle_key not in seen_cycles:
                cycles.append({'nodes': list(cycle_key), 'size': cycle_size})
                seen_cycles.add(cycle_key)

    conn.close()
    return hotspot_files, cycles
```

**CRITICAL**: Removed try/except (ZERO FALLBACK compliance). Errors will crash.

---

### Task 3.2: Update fce.py load_cfg_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 104-143

**COMPLETE BEFORE**:
```python
def load_cfg_data_from_db(db_path: str) -> dict[str, Any]:
    """Load CFG complexity data from database."""
    complex_functions = {}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT file, details_json
            FROM findings_consolidated
            WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
        """)

        for row in cursor.fetchall():
            file_path, details_json = row
            try:
                if details_json:
                    details = json.loads(details_json)
                    function_name = details.get('function', 'unknown')
                    key = f"{file_path}:{function_name}"
                    complex_functions[key] = details
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()

    except sqlite3.Error as e:
        print(f"[FCE] Database error loading CFG data: {e}")

    return complex_functions
```

**COMPLETE AFTER**:
```python
def load_cfg_data_from_db(db_path: str) -> dict[str, Any]:
    """Load CFG complexity data from database using direct column access."""
    complex_functions = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, cfg_function, cfg_complexity, cfg_block_count,
               cfg_edge_count, cfg_start_line, cfg_end_line,
               cfg_has_loops, cfg_max_nesting
        FROM findings_consolidated
        WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
    """)

    for row in cursor.fetchall():
        file_path = row[0]
        function_name = row[1] or 'unknown'
        key = f"{file_path}:{function_name}"
        complex_functions[key] = {
            'function': row[1],
            'complexity': row[2],
            'block_count': row[3],
            'edge_count': row[4],
            'start_line': row[5],
            'end_line': row[6],
            'has_loops': bool(row[7]) if row[7] is not None else False,
            'max_nesting': row[8],
        }

    conn.close()
    return complex_functions
```

---

### Task 3.3: Update fce.py load_churn_data_from_db() - DEAD CODE

**File**: `theauditor/fce.py`
**Location**: Lines 145-181

**VERIFIED FACT**: Tool `churn-analysis` does NOT exist in database. This function ALWAYS returns empty dict.

**DECISION**: Two options:

**Option A (Conservative)**: Keep function but add comment
```python
def load_churn_data_from_db(db_path: str) -> dict[str, Any]:
    """
    Load code churn data from database.

    NOTE: As of 2025-11-24, no 'churn-analysis' tool exists.
    Churn data is stored in 'graph-analysis' tool as graph_churn column.
    This function is preserved for potential future use but currently returns empty.
    """
    # Churn data is now in graph-analysis tool (graph_churn column)
    # which is loaded by load_graph_data_from_db()
    return {}
```

**Option B (Aggressive)**: Delete function entirely and update callers.

**RECOMMENDATION**: Option A for safety. Document the finding.

---

### Task 3.4: Update fce.py load_coverage_data_from_db() - DEAD CODE

**File**: `theauditor/fce.py`
**Location**: Lines 184-220

**VERIFIED FACT**: Tool `coverage-analysis` does NOT exist in database. This function ALWAYS returns empty dict.

**APPLY SAME CHANGE AS TASK 3.3**: Keep function, add comment, return empty dict.

---

### Task 3.5: Update fce.py load_taint_data_from_db() - USE taint_flows TABLE

**File**: `theauditor/fce.py`
**Location**: Lines 223-280

**COMPLETE BEFORE**:
```python
def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """Load complete taint paths from database."""
    taint_paths = []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT details_json
            FROM findings_consolidated
            WHERE tool='taint'
              AND details_json IS NOT NULL
              AND details_json != '{}'
        """)

        for row in cursor.fetchall():
            details_json = row[0]
            try:
                if details_json:
                    path_data = json.loads(details_json)
                    if 'source' in path_data and 'sink' in path_data:
                        taint_paths.append(path_data)
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()

    except sqlite3.Error as e:
        print(f"[FCE] Database error loading taint data: {e}")

    return taint_paths
```

**COMPLETE AFTER**:
```python
def load_taint_data_from_db(db_path: str) -> list[dict[str, Any]]:
    """
    Load complete taint paths from taint_flows table.

    Uses taint_flows table directly (proper normalized schema) instead of
    parsing findings_consolidated.misc_json.
    """
    taint_paths = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query taint_flows table (already normalized with proper columns)
    cursor.execute("""
        SELECT source_file, source_line, source_pattern,
               sink_file, sink_line, sink_pattern,
               vulnerability_type, path_length, hops, path_json,
               flow_sensitive
        FROM taint_flows
    """)

    for row in cursor.fetchall():
        path_data = {
            'source': {
                'file': row[0],
                'line': row[1],
                'pattern': row[2],
            },
            'sink': {
                'file': row[3],
                'line': row[4],
                'pattern': row[5],
            },
            'vulnerability_type': row[6],
            'path_length': row[7],
            'hops': row[8],
            'path': json.loads(row[9]) if row[9] else [],  # path_json is the actual path array
            'flow_sensitive': bool(row[10]),
        }
        taint_paths.append(path_data)

    conn.close()
    return taint_paths
```

---

### Task 3.6: Remove ZERO FALLBACK Violation at fce.py:465-476

**File**: `theauditor/fce.py`
**Location**: Lines 465-476

**DELETE THIS ENTIRE BLOCK**:
```python
        # Check if table exists (graceful fallback for old databases)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='findings_consolidated'
        """)

        if not cursor.fetchone():
            print("[FCE] Warning: findings_consolidated table not found")
            print("[FCE] Database may need re-indexing with new schema")
            print("[FCE] Run: aud index")
            conn.close()
            return []
```

**REASON**: ZERO FALLBACK policy. If table doesn't exist, let query crash.

---

### Task 3.7: Update context/query.py get_findings()

**File**: `theauditor/context/query.py`
**Location**: Lines 1203-1238

**COMPLETE BEFORE** (key section):
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
                    'column': row['column'],
                    'rule': row['rule'],
                    'tool': row['tool'],
                    'message': row['message'],
                    'severity': row['severity'],
                    'category': row['category'],
                    'confidence': row['confidence'],
                    'cwe': row['cwe']
                }

                # Parse details_json if present
                if row['details_json']:
                    import json
                    try:
                        finding['details'] = json.loads(row['details_json'])
                    except (json.JSONDecodeError, TypeError):
                        pass

                findings.append(finding)
```

**COMPLETE AFTER**:
```python
            cursor.execute(f"""
                SELECT file, line, column, rule, tool, message, severity,
                       category, confidence, cwe,
                       mypy_severity, mypy_code, mypy_hint,
                       cfg_complexity, cfg_function, cfg_block_count,
                       graph_score, graph_centrality, graph_churn,
                       tf_finding_id, tf_resource_id
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

                # Build details dict from columns (no JSON parsing)
                details = {}
                tool = row['tool']

                if tool == 'mypy':
                    if row['mypy_severity']:
                        details['mypy_severity'] = row['mypy_severity']
                    if row['mypy_code']:
                        details['mypy_code'] = row['mypy_code']
                    if row['mypy_hint']:
                        details['hint'] = row['mypy_hint']

                elif tool == 'cfg-analysis':
                    if row['cfg_complexity']:
                        details['complexity'] = row['cfg_complexity']
                    if row['cfg_function']:
                        details['function'] = row['cfg_function']
                    if row['cfg_block_count']:
                        details['block_count'] = row['cfg_block_count']

                elif tool == 'graph-analysis':
                    if row['graph_score']:
                        details['score'] = row['graph_score']
                    if row['graph_centrality']:
                        details['centrality'] = row['graph_centrality']
                    if row['graph_churn']:
                        details['churn'] = row['graph_churn']

                elif tool == 'terraform':
                    if row['tf_finding_id']:
                        details['finding_id'] = row['tf_finding_id']
                    if row['tf_resource_id']:
                        details['resource_id'] = row['tf_resource_id']

                if details:
                    finding['details'] = details

                findings.append(finding)
```

---

## 4. Testing

### Task 4.1: Run Full Pipeline

```bash
cd C:/Users/santa/Desktop/TheAuditor
rm -rf .pf/  # Clean slate
aud full
```

**Expected**: Completes without errors

---

### Task 4.2: Verify Columns Populated

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Verify mypy columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE mypy_severity IS NOT NULL')
mypy_count = c.fetchone()[0]
print(f'mypy_severity populated: {mypy_count} rows (expected: ~4397)')

# Verify cfg columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE cfg_complexity IS NOT NULL')
cfg_count = c.fetchone()[0]
print(f'cfg_complexity populated: {cfg_count} rows (expected: ~66)')

# Verify graph columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE graph_score IS NOT NULL')
graph_count = c.fetchone()[0]
print(f'graph_score populated: {graph_count} rows (expected: ~50)')

# Verify misc_json is minimal (only taint)
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE misc_json != '{}'\")
misc_count = c.fetchone()[0]
print(f'misc_json used: {misc_count} rows (expected: ~1, taint only)')

# Verify total row count unchanged
c.execute('SELECT COUNT(*) FROM findings_consolidated')
total = c.fetchone()[0]
print(f'Total rows: {total} (expected: ~21900)')
"
```

---

### Task 4.3: Verify FCE Works

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud fce
```

**Expected**: Completes without errors, shows hotspots and correlations

---

### Task 4.4: Verify No json.loads on details_json

```bash
cd C:/Users/santa/Desktop/TheAuditor
grep -rn "json.loads.*details_json" theauditor/
```

**Expected**: Zero results (or only in misc_json handling for cycles)

---

### Task 4.5: Verify aud explain Works

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud explain theauditor/fce.py
```

**Expected**: Shows findings with details populated from columns

---

## 5. Cleanup

### Task 5.1: Remove Unused json Import

Check each modified file - if `import json` is no longer used, remove it.

Files to check:
- `theauditor/fce.py` - Keep for misc_json/path_json parsing
- `theauditor/terraform/analyzer.py` - Remove if no longer used
- `theauditor/context/query.py` - Remove if no longer used

---

### Task 5.2: Run Linter

```bash
cd C:/Users/santa/Desktop/TheAuditor
ruff check theauditor/fce.py theauditor/context/query.py theauditor/indexer/
```

Fix any issues found.

---

## 6. Documentation

### Task 6.1: Update This File

Mark all tasks as `[x]` complete.

### Task 6.2: Update proposal.md Status

Change status from `PROPOSAL` to `IMPLEMENTED`.

### Task 6.3: Validate with OpenSpec

```bash
cd C:/Users/santa/Desktop/TheAuditor
openspec validate normalize-findings-details-json --strict
```

---

## Completion Checklist

### Phase 0: Verification
- [ ] 0.1 Schema location verified
- [ ] 0.2 Write path location verified
- [ ] 0.3 FCE read locations verified
- [ ] 0.4 Database state verified

### Phase 1: Schema
- [ ] 1.1 FINDINGS_CONSOLIDATED schema updated (23 new columns)
- [ ] 1.2 Partial indexes added (optional)

### Phase 2: Writers
- [ ] 2.1 base_database.py write_findings() updated
- [ ] 2.2 terraform/analyzer.py updated
- [ ] 2.3 commands/taint.py verified (no change needed)

### Phase 3: Readers
- [ ] 3.1 fce.py load_graph_data_from_db() updated
- [ ] 3.2 fce.py load_cfg_data_from_db() updated
- [ ] 3.3 fce.py load_churn_data_from_db() documented as dead code
- [ ] 3.4 fce.py load_coverage_data_from_db() documented as dead code
- [ ] 3.5 fce.py load_taint_data_from_db() uses taint_flows table
- [ ] 3.6 ZERO FALLBACK violation removed (fce.py:465-476)
- [ ] 3.7 context/query.py get_findings() updated

### Phase 4: Testing
- [ ] 4.1 aud full completes without errors
- [ ] 4.2 Columns populated correctly
- [ ] 4.3 aud fce completes without errors
- [ ] 4.4 No json.loads on details_json
- [ ] 4.5 aud explain works

### Phase 5: Cleanup
- [ ] 5.1 Unused imports removed
- [ ] 5.2 Linter passes

### Phase 6: Documentation
- [ ] 6.1 tasks.md checkboxes complete
- [ ] 6.2 proposal.md status updated
- [ ] 6.3 OpenSpec validation passes

---

**Sign-off**: _____________________ Date: _____________________
