# Design Document: Sparse Wide Table for findings_consolidated

## Context

### Background

The `findings_consolidated` table is the central fact table for all security findings. It receives data from:
- Linters (ruff, eslint, mypy)
- Security rules (patterns)
- Terraform/CDK analyzers
- Taint analysis
- Graph analysis (hotspots, complexity)

Currently, tool-specific metadata is stored in `details_json` as a JSON TEXT blob. This creates:
1. Parse overhead (json.loads)
2. No SQL filtering capability
3. ZERO FALLBACK violations (try/except around parsing)

### Stakeholders

- **FCE (Findings Correlation Engine)**: Primary consumer of details_json
- **Context Query (`aud explain`)**: Secondary consumer for display
- **Rules Engine**: Primary writer via StandardFinding.additional_info
- **Tool Analyzers**: Direct writers (terraform, taint, graph)

### Constraints

1. **ZERO FALLBACK Policy**: No try/except, no fallbacks, crash on bad data
2. **Database Regeneration**: Schema regenerates fresh on every `aud full`
3. **Backwards Compatibility**: NOT required (by design)
4. **Performance**: FCE correlation must complete in <10ms (currently 125-700ms)

---

## Goals / Non-Goals

### Goals

1. Eliminate json.loads() overhead in FCE (125-700ms -> <10ms)
2. Enable SQL-level filtering (`WHERE complexity > 10`)
3. Achieve ZERO FALLBACK compliance (remove all try/except for JSON)
4. Maintain data integrity (zero data loss)
5. Keep schema simple and maintainable

### Non-Goals

1. Backwards compatibility with old databases
2. Support for arbitrary dynamic keys
3. Normalization of taint complex data (keep in misc_json)
4. Migration tooling (database regenerates fresh)

---

## Decision 1: Sparse Wide Table vs Junction Tables

### Options Considered

**Option A: Junction Tables (d8370a7 Pattern)**
```sql
CREATE TABLE finding_cfg_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER REFERENCES findings_consolidated(id),
    complexity INTEGER,
    block_count INTEGER,
    ...
);
```
- Pros: Follows existing pattern, normalized
- Cons: Requires JOINs, more complex queries, 5 new tables

**Option B: Sparse Wide Table (Selected)**
```sql
ALTER TABLE findings_consolidated
ADD COLUMN cfg_complexity INTEGER;  -- NULL for 99.7% of rows
```
- Pros: No JOINs, simple queries, NULLs are free in SQLite
- Cons: Wide table (36 columns), doesn't follow d8370a7 pattern

**Option C: Generated Columns**
```sql
ALTER TABLE findings_consolidated
ADD COLUMN cfg_complexity INTEGER
GENERATED ALWAYS AS (json_extract(details_json, '$.complexity'));
```
- Pros: No write path changes
- Cons: Still parses JSON at query time, performance gain minimal

### Decision

**Selected: Option B (Sparse Wide Table)**

**Rationale**:
1. SQLite NULL storage: Zero bytes in payload (stored in header only)
2. Query simplicity: `SELECT complexity FROM ...` vs complex JOIN
3. 79% of rows have empty details_json - NULLs are the common case
4. Only 23 keys to flatten (not 100s)
5. Partial indexes keep sparse column indexes tiny

**Trade-off accepted**: 36 columns is wider than ideal, but SQLite handles 2000 columns. The query simplicity and performance gain outweigh the schema width.

---

## Decision 2: Column Naming Convention

### Options Considered

1. **Raw names**: `complexity`, `block_count`, `centrality`
2. **Prefixed names**: `cfg_complexity`, `cfg_block_count`, `graph_centrality`

### Decision

**Selected: Prefixed names**

**Rationale**:
1. Prevents naming collisions (e.g., both cfg and graph have `complexity`)
2. Self-documenting which tool each column belongs to
3. Easy to add new tools without collision risk
4. Grep-friendly: `grep cfg_ core_schema.py` shows all CFG columns

**Prefixes defined**:
| Tool | Prefix | Example |
|------|--------|---------|
| mypy | `mypy_` | `mypy_severity`, `mypy_code` |
| cfg-analysis | `cfg_` | `cfg_complexity`, `cfg_block_count` |
| graph-analysis | `graph_` | `graph_centrality`, `graph_score` |
| terraform | `tf_` | `tf_finding_id`, `tf_resource_id` |

---

## Decision 3: Handling Taint Complex Data

### Problem

Taint findings have 7 LIST/DICT keys that cannot flatten to single columns:
- `source`: DICT with file, line, name, pattern, type
- `sink`: DICT with file, line, name, pattern, type
- `path`: LIST of intermediate steps
- `conditions`: LIST of conditions
- `tainted_vars`: LIST
- `sanitized_vars`: LIST
- `related_sources`: LIST

### Options Considered

1. **Normalize fully**: Create finding_taint_paths, finding_taint_conditions, etc.
2. **Keep in JSON**: Store in misc_json column
3. **Use existing table**: FCE reads from taint_flows instead

### Decision

**Selected: Option 3 (Use existing taint_flows table)**

**Rationale**:
1. `taint_flows` table already exists with proper schema
2. Only 1 row in findings_consolidated has taint data
3. FCE `load_taint_data_from_db()` should query `taint_flows` directly
4. Keep `misc_json` as fallback for any future complex data

**Implementation**:
```python
# fce.py - BEFORE
def load_taint_data_from_db(db_path):
    cursor.execute("SELECT details_json FROM findings_consolidated WHERE tool='taint'")
    for row in cursor:
        path_data = json.loads(row['details_json'])  # <-- REMOVE

# fce.py - AFTER
def load_taint_data_from_db(db_path):
    cursor.execute("""
        SELECT source_file, source_line, source_pattern,
               sink_file, sink_line, sink_pattern,
               vulnerability_type, path_length, path_json
        FROM taint_flows
    """)
    # Direct column access, path_json still needs json.loads but that's OK
    # (it's the actual path array, not metadata)
```

---

## Decision 4: Partial Index Support

### Problem

Current schema system doesn't support WHERE clause in index definitions:
```python
# Current format
indexes=[("idx_name", ["col1", "col2"])]

# Needed format
indexes=[("idx_name", ["col1"], "col1 IS NOT NULL")]
```

### Options Considered

1. **Extend TableSchema**: Add optional where_clause to index tuple
2. **Separate partial_indexes field**: New field for partial indexes
3. **Raw SQL in indexes**: Allow SQL string for complex indexes

### Decision

**Selected: Option 1 (Extend tuple format)**

**Rationale**:
1. Minimal change to existing code
2. Backwards compatible (2-tuple works, 3-tuple adds WHERE)
3. Follows existing pattern

**Implementation**:
```python
# core_schema.py - Index definition
indexes=[
    # Existing format (no WHERE)
    ("idx_findings_file_line", ["file", "line"]),
    # New format (with WHERE for partial index)
    ("idx_findings_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
]

# database.py - Index creation
for idx in table.indexes:
    name, columns = idx[0], idx[1]
    where_clause = idx[2] if len(idx) > 2 else None

    sql = f"CREATE INDEX {name} ON {table.name}({', '.join(columns)})"
    if where_clause:
        sql += f" WHERE {where_clause}"
    cursor.execute(sql)
```

---

## Decision 5: Writer Abstraction

### Problem

6 different files write to findings_consolidated. Each needs to map tool-specific data to columns.

### Options Considered

1. **Inline mapping**: Each writer handles its own column mapping
2. **Central mapper**: Single function maps tool -> columns
3. **Tool-specific methods**: DatabaseManager.add_mypy_finding(), add_cfg_finding(), etc.

### Decision

**Selected: Option 2 (Central mapper)**

**Rationale**:
1. Single source of truth for column mappings
2. Easy to add new tools
3. Writers stay simple (pass dict, mapper handles columns)

**Implementation**:
```python
# base_database.py

TOOL_COLUMN_MAPPINGS = {
    'mypy': {
        'mypy_severity': lambda f: f.get('additional_info', {}).get('mypy_severity'),
        'mypy_code': lambda f: f.get('additional_info', {}).get('mypy_code'),
        'mypy_hint': lambda f: f.get('additional_info', {}).get('hint'),
    },
    'cfg-analysis': {
        'cfg_complexity': lambda f: f.get('additional_info', {}).get('complexity'),
        'cfg_block_count': lambda f: f.get('additional_info', {}).get('block_count'),
        # ... etc
    },
    'graph-analysis': {
        'graph_centrality': lambda f: f.get('additional_info', {}).get('centrality'),
        # ... etc
    },
    'terraform': {
        'tf_finding_id': lambda f: f.get('additional_info', {}).get('finding_id'),
        # ... etc
    },
}

def map_finding_to_columns(finding: dict) -> dict:
    """Map a finding dict to column values."""
    tool = finding.get('tool', '')
    mappings = TOOL_COLUMN_MAPPINGS.get(tool, {})

    columns = {}
    for col_name, extractor in mappings.items():
        value = extractor(finding)
        if value is not None:
            columns[col_name] = value

    return columns
```

---

## Decision 6: misc_json Fallback Column

### Problem

Some future tool might have complex data that doesn't fit columns.

### Options Considered

1. **No fallback**: Require all tools to use columns
2. **misc_json column**: Keep JSON column for exceptions
3. **Separate overflow table**: finding_overflow_json

### Decision

**Selected: Option 2 (misc_json column)**

**Rationale**:
1. Provides escape hatch for edge cases
2. Current taint complex data can use it (1 row)
3. Easy to audit usage (`SELECT COUNT(*) FROM findings_consolidated WHERE misc_json != '{}'`)
4. Name clearly indicates "miscellaneous" - not for regular use

**Guardrails**:
- Add comment in schema: "ONLY for complex nested data that cannot be normalized"
- Log warning when misc_json is written to
- Audit query in CI: fail if misc_json usage exceeds threshold

---

## Risks / Trade-offs

### Risk 1: Schema Width

**Risk**: 36 columns might cause maintenance burden
**Mitigation**:
- Columns are grouped by tool prefix
- Each group is independent
- Adding new tool = adding new prefix group

### Risk 2: Column Mapping Errors

**Risk**: Writers might map to wrong columns
**Mitigation**:
- Central mapper with explicit tool -> column mapping
- Unit tests for each tool's mapping
- CI validation that all tools map correctly

### Risk 3: Future Dynamic Data

**Risk**: New tool might need truly dynamic keys
**Mitigation**:
- misc_json column exists as fallback
- If pattern emerges, add new columns in future PR
- Database regenerates, so schema changes are cheap

---

## Migration Plan

### Phase 0: Add columns (Non-breaking)

1. Update core_schema.py with new columns
2. Update index creation with partial index support
3. Test: `aud full` creates table with new columns

### Phase 1: Update writers (Dual-write optional)

1. Update rules/base.py to map additional_info to columns
2. Update base_database.py INSERT to include new columns
3. Update terraform/analyzer.py to write columns
4. Update commands/taint.py to write misc_json
5. Test: Verify columns populated after `aud full`

### Phase 2: Update readers

1. Update fce.py to SELECT columns instead of details_json
2. Update fce.py load_taint_data_from_db to use taint_flows
3. Update context/query.py to build details dict from columns
4. Update aws_cdk/analyzer.py to read columns
5. Test: `aud fce` works without json.loads

### Phase 3: Cleanup

1. Remove `details_json` column from schema (rename to misc_json done in Phase 0)
2. Remove any remaining json.loads for details_json
3. Verify: `grep -r "json.loads.*details" theauditor/` returns nothing

---

## Open Questions (Resolved)

1. **Should we support backwards-compatible reads?**
   - Answer: NO - Database regenerates fresh, no old data to read

2. **Should we add schema versioning?**
   - Answer: DEFERRED - Not required for this change, consider separately

3. **Should we add database triggers for validation?**
   - Answer: NO - Validate in Python for debuggability (per CLAUDE.md)

4. **What if a tool needs >10 columns?**
   - Answer: Add them. SQLite handles 2000 columns.

---

## References

- `teamsop.md` v4.20 - Prime Directive requirements
- `CLAUDE.md:194-249` - ZERO FALLBACK policy
- Commit d8370a7 - Junction table pattern (context, not followed here)
- SQLite documentation - NULL storage optimization
- Gemini proposal (2025-11-24) - Sparse wide table recommendation
