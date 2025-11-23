# Implementation Tasks: Sparse Wide Table Normalization

**Prerequisites**:
1. Read `proposal.md` - Understand what and why
2. Read `design.md` - Understand technical decisions
3. Read `verification.md` - Understand verified facts
4. Read `teamsop.md` - Understand Prime Directive
5. Read `CLAUDE.md:194-249` - Understand ZERO FALLBACK policy

---

## 0. Verification (MANDATORY BEFORE ANY CODE)

Execute Prime Directive verification per teamsop.md v4.20.

- [ ] **0.1** Read `theauditor/indexer/schemas/core_schema.py:490-516`
  - **Verify**: FINDINGS_CONSOLIDATED has 14 columns
  - **Verify**: `details_json` is at line 506
  - **Verify**: 6 indexes defined

- [ ] **0.2** Read `theauditor/fce.py:60-70, 125-135, 265-275`
  - **Verify**: json.loads calls exist at lines 63, 81, 130, 171, 210, 268
  - **Verify**: try/except blocks wrap json.loads (ZERO FALLBACK violations)

- [ ] **0.3** Run database query to confirm data distribution
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
  import sqlite3
  conn = sqlite3.connect('.pf/repo_index.db')
  c = conn.cursor()
  c.execute('''
      SELECT tool, COUNT(*) as total,
             SUM(CASE WHEN details_json != \"{}\" THEN 1 ELSE 0 END) as with_details
      FROM findings_consolidated GROUP BY tool
  ''')
  for row in c.fetchall():
      print(f'{row[0]}: {row[2]}/{row[1]}')
  "
  ```
  - **Verify**: ~77% rows have empty details_json

- [ ] **0.4** Confirm taint_flows table exists
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
  import sqlite3
  conn = sqlite3.connect('.pf/repo_index.db')
  c = conn.cursor()
  c.execute('SELECT COUNT(*) FROM taint_flows')
  print(f'taint_flows rows: {c.fetchone()[0]}')
  "
  ```
  - **Verify**: Table exists with >= 1 row

---

## 1. Schema Changes

### Task 1.1: Add Column Support to TableSchema (if needed)

**File**: `theauditor/indexer/schemas/__init__.py` (or where Column is defined)

**Check first**: Does Column class support all needed types?
- INTEGER, TEXT, REAL should already work
- NULL default should already work

**Action**: If Column class needs changes, update here. Otherwise skip.

---

### Task 1.2: Add Partial Index Support

**File**: `theauditor/indexer/database/base_database.py`

**Find**: Index creation loop (search for `CREATE INDEX`)

**BEFORE** (approximate location):
```python
for idx_name, idx_columns in table.indexes:
    cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table.name}({', '.join(idx_columns)})")
```

**AFTER**:
```python
for idx_def in table.indexes:
    idx_name = idx_def[0]
    idx_columns = idx_def[1]
    where_clause = idx_def[2] if len(idx_def) > 2 else None

    sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table.name}({', '.join(idx_columns)})"
    if where_clause:
        sql += f" WHERE {where_clause}"
    cursor.execute(sql)
```

**Test**: Run `aud full` - should not error on new format

---

### Task 1.3: Update FINDINGS_CONSOLIDATED Schema

**File**: `theauditor/indexer/schemas/core_schema.py`
**Location**: Lines 490-516

**BEFORE**:
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
        # === EXISTING COLUMNS (13) ===
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

        # === MYPY COLUMNS (3) ===
        Column("mypy_severity", "TEXT"),
        Column("mypy_code", "TEXT"),
        Column("mypy_hint", "TEXT"),

        # === CFG-ANALYSIS COLUMNS (8) ===
        Column("cfg_complexity", "INTEGER"),
        Column("cfg_block_count", "INTEGER"),
        Column("cfg_edge_count", "INTEGER"),
        Column("cfg_start_line", "INTEGER"),
        Column("cfg_end_line", "INTEGER"),
        Column("cfg_function", "TEXT"),
        Column("cfg_has_loops", "INTEGER"),
        Column("cfg_max_nesting", "INTEGER"),

        # === GRAPH-ANALYSIS COLUMNS (7) ===
        Column("graph_centrality", "REAL"),
        Column("graph_churn", "INTEGER"),
        Column("graph_in_degree", "INTEGER"),
        Column("graph_out_degree", "INTEGER"),
        Column("graph_loc", "INTEGER"),
        Column("graph_score", "REAL"),
        Column("graph_node_id", "TEXT"),

        # === TERRAFORM COLUMNS (4) ===
        Column("tf_finding_id", "TEXT"),
        Column("tf_resource_id", "TEXT"),
        Column("tf_remediation", "TEXT"),
        Column("tf_graph_context", "TEXT"),

        # === FALLBACK FOR COMPLEX DATA ===
        # ONLY use for data that cannot be normalized (e.g., nested taint paths)
        Column("misc_json", "TEXT", default="'{}'"),
    ],
    indexes=[
        # Existing indexes
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # Partial indexes for sparse columns
        ("idx_findings_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
        ("idx_findings_hotspot", ["graph_score"], "graph_score IS NOT NULL"),
        ("idx_findings_centrality", ["graph_centrality"], "graph_centrality IS NOT NULL"),
        ("idx_findings_mypy_code", ["mypy_code"], "mypy_code IS NOT NULL"),
    ]
)
```

**Test**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && aud full
```
- **Verify**: No schema errors
- **Verify**: `SELECT COUNT(*) FROM findings_consolidated` returns rows

---

## 2. Writer Updates

### Task 2.1: Add Column Mapping Function

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Near top of file (after imports)

**ADD** new function:
```python
# Column mappings for each tool type
TOOL_COLUMN_MAPPINGS = {
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
        'centrality': 'graph_centrality',
        'churn': 'graph_churn',
        'in_degree': 'graph_in_degree',
        'out_degree': 'graph_out_degree',
        'loc': 'graph_loc',
        'score': 'graph_score',
        'id': 'graph_node_id',
    },
    'terraform': {
        'finding_id': 'tf_finding_id',
        'resource_id': 'tf_resource_id',
        'remediation': 'tf_remediation',
        'graph_context_json': 'tf_graph_context',
    },
}

def extract_tool_columns(tool: str, additional_info: dict) -> dict:
    """Extract tool-specific columns from additional_info dict.

    Args:
        tool: Tool name (e.g., 'mypy', 'cfg-analysis')
        additional_info: Dict with tool-specific data

    Returns:
        Dict mapping column names to values
    """
    if not additional_info:
        return {}

    mappings = TOOL_COLUMN_MAPPINGS.get(tool, {})
    columns = {}

    for json_key, column_name in mappings.items():
        if json_key in additional_info:
            value = additional_info[json_key]
            # Convert bool to int for SQLite
            if isinstance(value, bool):
                value = 1 if value else 0
            columns[column_name] = value

    return columns
```

---

### Task 2.2: Update write_findings Method

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 680-700 (find `write_findings` or the INSERT INTO findings_consolidated)

**BEFORE**:
```python
cursor.executemany(
    """INSERT INTO findings_consolidated
       (file, line, column, rule, tool, message, severity, category,
        confidence, code_snippet, cwe, timestamp, details_json)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    batch
)
```

**AFTER**:
```python
# Build INSERT with all columns
base_columns = [
    'file', 'line', 'column', 'rule', 'tool', 'message', 'severity',
    'category', 'confidence', 'code_snippet', 'cwe', 'timestamp',
]
tool_columns = [
    'mypy_severity', 'mypy_code', 'mypy_hint',
    'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_start_line',
    'cfg_end_line', 'cfg_function', 'cfg_has_loops', 'cfg_max_nesting',
    'graph_centrality', 'graph_churn', 'graph_in_degree', 'graph_out_degree',
    'graph_loc', 'graph_score', 'graph_node_id',
    'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context',
    'misc_json',
]
all_columns = base_columns + tool_columns
placeholders = ', '.join(['?'] * len(all_columns))

insert_sql = f"""INSERT INTO findings_consolidated
    ({', '.join(all_columns)})
    VALUES ({placeholders})"""

# Build batch with column extraction
normalized_batch = []
for f in batch:
    # Base columns
    row = [
        f[0],   # file
        f[1],   # line
        f[2],   # column
        f[3],   # rule
        f[4],   # tool
        f[5],   # message
        f[6],   # severity
        f[7],   # category
        f[8],   # confidence
        f[9],   # code_snippet
        f[10],  # cwe
        f[11],  # timestamp
    ]

    # Extract tool-specific columns
    tool = f[4]  # tool name
    additional_info = {}
    if len(f) > 12 and f[12]:
        # Parse details_json to get additional_info
        try:
            import json
            additional_info = json.loads(f[12]) if isinstance(f[12], str) else f[12]
        except:
            additional_info = {}

    tool_cols = extract_tool_columns(tool, additional_info)

    # Add tool columns in order (None for columns not in this tool's data)
    for col in tool_columns[:-1]:  # Exclude misc_json
        row.append(tool_cols.get(col))

    # misc_json - only for complex data that couldn't be extracted
    if tool == 'taint' and additional_info:
        import json
        row.append(json.dumps(additional_info))
    else:
        row.append('{}')

    normalized_batch.append(tuple(row))

cursor.executemany(insert_sql, normalized_batch)
```

**Note**: This is a significant change. May need adjustment based on actual batch structure.

---

### Task 2.3: Update rules/base.py StandardFinding.to_dict()

**File**: `theauditor/rules/base.py`
**Location**: Lines 183-186

**BEFORE**:
```python
if self.additional_info:
    # Map additional_info -> details_json for database schema
    import json
    result["details_json"] = json.dumps(self.additional_info)
```

**AFTER**:
```python
if self.additional_info:
    # Pass additional_info as-is; writer will extract to columns
    result["additional_info"] = self.additional_info
    # Keep details_json for backwards compat during transition
    import json
    result["details_json"] = json.dumps(self.additional_info)
```

---

### Task 2.4: Update terraform/analyzer.py

**File**: `theauditor/terraform/analyzer.py`
**Location**: Lines 167-196

**BEFORE**:
```python
details_json = json.dumps({
    'finding_id': finding.finding_id,
    'resource_id': finding.resource_id,
    'remediation': finding.remediation,
    'graph_context_json': finding.graph_context_json,
})

cursor.execute(
    """INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category,
     confidence, code_snippet, cwe, timestamp, details_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (..., details_json,)
)
```

**AFTER**:
```python
cursor.execute(
    """INSERT INTO findings_consolidated
    (file, line, column, rule, tool, message, severity, category,
     confidence, code_snippet, cwe, timestamp,
     tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        finding.finding_id,      # tf_finding_id
        finding.resource_id,     # tf_resource_id
        finding.remediation,     # tf_remediation
        finding.graph_context_json,  # tf_graph_context
    ),
)
```

---

### Task 2.5: Update commands/taint.py

**File**: `theauditor/commands/taint.py`
**Location**: Lines 477-500

**Key change**: Write complex taint data to `misc_json` (exception for complex nested data)

**BEFORE**:
```python
findings_dicts.append({
    ...
    'additional_info': taint_path  # Complete nested structure
})
```

**AFTER**:
```python
import json
findings_dicts.append({
    ...
    'misc_json': json.dumps(taint_path)  # Complex data goes to misc_json
})
```

---

### Task 2.6: Update Other Writers (vulnerability_scanner.py, aws_cdk/analyzer.py)

**Files**: Check each for INSERT INTO findings_consolidated

**Action**: Update INSERT statements to match new schema (add NULL for unused columns)

---

## 3. Reader Updates

### Task 3.1: Update fce.py load_graph_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 52-100

**BEFORE**:
```python
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
            hotspot_files[file_path] = details
    except (json.JSONDecodeError, TypeError):
        pass
```

**AFTER**:
```python
cursor.execute("""
    SELECT file,
           graph_centrality, graph_churn, graph_in_degree,
           graph_out_degree, graph_loc, graph_score, graph_node_id
    FROM findings_consolidated
    WHERE tool='graph-analysis' AND rule='ARCHITECTURAL_HOTSPOT'
""")

for row in cursor.fetchall():
    file_path = row[0]
    hotspot_files[file_path] = {
        'centrality': row[1],
        'churn': row[2],
        'in_degree': row[3],
        'out_degree': row[4],
        'loc': row[5],
        'score': row[6],
        'id': row[7],
    }
```

**REMOVE**: The try/except block (ZERO FALLBACK compliance)

---

### Task 3.2: Update fce.py load_cfg_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 104-143

**BEFORE**:
```python
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
```

**AFTER**:
```python
cursor.execute("""
    SELECT file,
           cfg_complexity, cfg_block_count, cfg_edge_count,
           cfg_start_line, cfg_end_line, cfg_function,
           cfg_has_loops, cfg_max_nesting
    FROM findings_consolidated
    WHERE tool='cfg-analysis' AND rule='HIGH_CYCLOMATIC_COMPLEXITY'
""")

for row in cursor.fetchall():
    file_path = row[0]
    function_name = row[6] or 'unknown'
    key = f"{file_path}:{function_name}"
    complex_functions[key] = {
        'complexity': row[1],
        'block_count': row[2],
        'edge_count': row[3],
        'start_line': row[4],
        'end_line': row[5],
        'function': row[6],
        'has_loops': bool(row[7]),
        'max_nesting': row[8],
    }
```

---

### Task 3.3: Update fce.py load_taint_data_from_db() - USE taint_flows TABLE

**File**: `theauditor/fce.py`
**Location**: Lines 223-280

**BEFORE**:
```python
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
```

**AFTER**:
```python
# Query taint_flows table directly (proper normalized schema)
cursor.execute("""
    SELECT source_file, source_line, source_pattern,
           sink_file, sink_line, sink_pattern,
           vulnerability_type, path_length, hops, path_json
    FROM taint_flows
""")

for row in cursor.fetchall():
    taint_paths.append({
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
    })
```

---

### Task 3.4: Update fce.py Other Load Functions

Apply same pattern to:
- `load_churn_data_from_db()` (line 145-182)
- `load_coverage_data_from_db()` (line 184-221)

**Pattern**: SELECT columns directly, remove json.loads(), remove try/except

---

### Task 3.5: Update context/query.py get_findings()

**File**: `theauditor/context/query.py`
**Location**: Lines 1203-1238

**BEFORE**:
```python
cursor.execute(f"""
    SELECT file, line, column, rule, tool, message, severity,
           category, confidence, cwe, details_json
    FROM findings_consolidated
    ...
""")

for row in cursor.fetchall():
    finding = {...}
    if row['details_json']:
        import json
        try:
            finding['details'] = json.loads(row['details_json'])
        except (json.JSONDecodeError, TypeError):
            pass
```

**AFTER**:
```python
cursor.execute(f"""
    SELECT file, line, column, rule, tool, message, severity,
           category, confidence, cwe,
           mypy_severity, mypy_code, mypy_hint,
           cfg_complexity, cfg_function,
           graph_score, graph_centrality
    FROM findings_consolidated
    ...
""")

for row in cursor.fetchall():
    finding = {
        'file': row['file'],
        'line': row['line'],
        # ... other base fields
    }

    # Build details dict from columns (tool-specific)
    details = {}
    if row['mypy_severity']:
        details['mypy_severity'] = row['mypy_severity']
    if row['mypy_code']:
        details['mypy_code'] = row['mypy_code']
    if row['cfg_complexity']:
        details['complexity'] = row['cfg_complexity']
    if row['cfg_function']:
        details['function'] = row['cfg_function']
    if row['graph_score']:
        details['score'] = row['graph_score']
    if row['graph_centrality']:
        details['centrality'] = row['graph_centrality']

    if details:
        finding['details'] = details

    findings.append(finding)
```

---

### Task 3.6: Remove ZERO FALLBACK Violations

**File**: `theauditor/fce.py`
**Location**: Lines 465-476

**REMOVE** this entire block:
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

**Reason**: ZERO FALLBACK policy - let query crash if table missing.

---

## 4. Testing

### Task 4.1: Run Full Pipeline

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud full
```

**Verify**:
- [ ] No errors during indexing
- [ ] No errors during rule detection
- [ ] findings_consolidated table has expected row count

### Task 4.2: Verify Columns Populated

```bash
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Check mypy columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE mypy_severity IS NOT NULL')
print(f'mypy rows with mypy_severity: {c.fetchone()[0]}')

# Check cfg columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE cfg_complexity IS NOT NULL')
print(f'cfg rows with cfg_complexity: {c.fetchone()[0]}')

# Check graph columns
c.execute('SELECT COUNT(*) FROM findings_consolidated WHERE graph_score IS NOT NULL')
print(f'graph rows with graph_score: {c.fetchone()[0]}')

# Check misc_json usage (should be minimal)
c.execute(\"SELECT COUNT(*) FROM findings_consolidated WHERE misc_json != '{}'\")
print(f'rows using misc_json: {c.fetchone()[0]}')
"
```

**Expected**:
- mypy_severity: ~4,397 rows
- cfg_complexity: ~66 rows
- graph_score: ~50 rows
- misc_json: ~1 row (taint only)

### Task 4.3: Verify FCE Works

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud fce
```

**Verify**:
- [ ] No json.loads errors
- [ ] Output includes hotspots, complexity, taint data
- [ ] Performance improved (should feel faster)

### Task 4.4: Verify aud explain Works

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud explain theauditor/fce.py
```

**Verify**:
- [ ] Findings section shows correct data
- [ ] No JSON parse errors

### Task 4.5: Grep for Remaining json.loads on details_json

```bash
cd C:/Users/santa/Desktop/TheAuditor
grep -rn "json.loads.*details" theauditor/
```

**Expected**: Zero results (or only in misc_json handling)

---

## 5. Cleanup

### Task 5.1: Remove Unused Imports

Check each modified file for unused `import json` statements.

### Task 5.2: Update Type Hints

If any functions changed signatures, update type hints.

### Task 5.3: Run Linter

```bash
cd C:/Users/santa/Desktop/TheAuditor
ruff check theauditor/fce.py theauditor/context/query.py theauditor/indexer/
```

---

## 6. Documentation

### Task 6.1: Update CLAUDE.md

Add note about new schema columns if significant for future developers.

### Task 6.2: Mark OpenSpec Complete

After all tasks done:
1. Mark all checkboxes in this file as `[x]`
2. Update `proposal.md` status to IMPLEMENTED
3. Run `openspec validate normalize-findings-details-json --strict`

---

## Completion Checklist

- [ ] All 0.x verification tasks passed
- [ ] All 1.x schema tasks completed
- [ ] All 2.x writer tasks completed
- [ ] All 3.x reader tasks completed
- [ ] All 4.x testing tasks passed
- [ ] All 5.x cleanup tasks completed
- [ ] All 6.x documentation tasks completed
- [ ] `aud full` runs without errors
- [ ] `aud fce` runs without errors
- [ ] No json.loads on details_json in codebase
- [ ] misc_json used only for taint (1 row)

**Sign-off**: _____________________ Date: _____________________
