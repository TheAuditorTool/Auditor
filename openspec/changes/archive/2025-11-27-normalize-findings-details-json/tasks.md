# Implementation Tasks

**Last Updated**: 2025-11-28 (COMPLETED - verified with due diligence)
**Implemented By**: Opus (AI Lead Coder)
**Approved By**: Architect

---

## Overview

| Phase | Tasks | Status |
|-------|-------|--------|
| 1. Schema | 1 task | COMPLETE |
| 2. Writers | 3 tasks | COMPLETE |
| 3. Readers | 8 tasks | COMPLETE |
| 4. Validation | 2 tasks | COMPLETE |
| 5. Bonus Fix | 1 task | COMPLETE |
| 6. Due Diligence Bugs | 3 tasks | COMPLETE |

**IMPLEMENTATION DEVIATION FROM ORIGINAL PLAN:**
- NO `misc_json` column added (ZERO FALLBACK - no escape hatches)
- NO `details_json` kept for backward compat (deleted entirely)
- Taint reads from `taint_flows` table (already normalized)
- Dead code functions replaced with empty dicts, not deleted entirely

---

## Phase 1: Schema Changes - COMPLETE

### Task 1.1: Add 23 nullable columns to FINDINGS_CONSOLIDATED

**File**: `theauditor/indexer/schemas/core_schema.py`
**Location**: Lines 484-556

**Status**: COMPLETE

**ACTUAL IMPLEMENTATION** (differs from plan):
```python
FINDINGS_CONSOLIDATED = TableSchema(
    name="findings_consolidated",
    columns=[
        # === CORE COLUMNS (13) - Unchanged ===
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

        # === CFG-ANALYSIS COLUMNS (9) ===
        Column("cfg_function", "TEXT"),
        Column("cfg_complexity", "INTEGER"),
        Column("cfg_block_count", "INTEGER"),
        Column("cfg_edge_count", "INTEGER"),
        Column("cfg_has_loops", "INTEGER"),
        Column("cfg_has_recursion", "INTEGER"),
        Column("cfg_start_line", "INTEGER"),
        Column("cfg_end_line", "INTEGER"),
        Column("cfg_threshold", "INTEGER"),

        # === GRAPH-ANALYSIS COLUMNS (7) ===
        Column("graph_id", "TEXT"),
        Column("graph_in_degree", "INTEGER"),
        Column("graph_out_degree", "INTEGER"),
        Column("graph_total_connections", "INTEGER"),
        Column("graph_centrality", "REAL"),
        Column("graph_score", "REAL"),
        Column("graph_cycle_nodes", "TEXT"),

        # === MYPY COLUMNS (3) ===
        Column("mypy_error_code", "TEXT"),
        Column("mypy_severity_int", "INTEGER"),
        Column("mypy_column", "INTEGER"),

        # === TERRAFORM COLUMNS (4) ===
        Column("tf_finding_id", "TEXT"),
        Column("tf_resource_id", "TEXT"),
        Column("tf_remediation", "TEXT"),
        Column("tf_graph_context", "TEXT"),
    ],
    indexes=[
        # Existing indexes (unchanged)
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # Partial indexes for sparse columns
        ("idx_findings_cfg_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
        ("idx_findings_graph_score", ["graph_score"], "graph_score IS NOT NULL"),
        ("idx_findings_mypy_error_code", ["mypy_error_code"], "mypy_error_code IS NOT NULL"),
    ]
)
```

**Acceptance Criteria**:
- [x] Schema file updated with 23 new columns
- [x] details_json DELETED (not kept for backward compat)
- [x] misc_json NOT added (ZERO FALLBACK)
- [x] `aud full --offline` creates table with new schema
- [x] Partial indexes added for sparse columns

---

## Phase 2: Writer Changes - COMPLETE

### Task 2.1: Update base_database.py write_findings_batch()

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 647-832

**Status**: COMPLETE

**Key Changes**:
- Removed JSON serialization for details
- Added tool-specific column mapping (cfg-analysis, graph-analysis, mypy, terraform)
- INSERT now uses 35 columns (no details_json, no misc_json)
- Taint findings get marker row only (complex data in taint_flows table)

**Acceptance Criteria**:
- [x] Tool-specific column mapping implemented
- [x] All 23 new columns populated based on tool_name
- [x] No misc_json fallback (ZERO FALLBACK)
- [x] No details_json in INSERT

---

### Task 2.2: Update terraform/analyzer.py direct INSERT

**File**: `theauditor/terraform/analyzer.py`
**Location**: Lines 166-194

**Status**: COMPLETE

**Key Changes**:
- Removed `json.dumps()` call
- INSERT now writes directly to `tf_*` columns
- Removed details_json from INSERT

**Acceptance Criteria**:
- [x] No json.dumps() call
- [x] Terraform columns populated directly
- [x] details_json not in INSERT

---

### Task 2.3: Update aws_cdk/analyzer.py direct INSERT

**File**: `theauditor/aws_cdk/analyzer.py`
**Location**: Lines 220-240

**Status**: COMPLETE (discovered during validation)

**Key Changes**:
- Removed details_json from INSERT statement
- CDK findings use core columns only (no tool-specific columns needed)

**Acceptance Criteria**:
- [x] No details_json in INSERT
- [x] Parameter count matches column count

---

## Phase 3: Reader Changes - COMPLETE

### Task 3.1: Update fce.py load_graph_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 29-96

**Status**: COMPLETE

**Key Changes**:
- SELECT now uses graph_* columns directly
- No json.loads() calls
- Cycles parsed from comma-separated graph_cycle_nodes

**Acceptance Criteria**:
- [x] No json.loads() calls
- [x] SELECT uses normalized columns
- [x] Output format unchanged

---

### Task 3.2: Update fce.py load_cfg_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 99-144

**Status**: COMPLETE

**Key Changes**:
- SELECT now uses cfg_* columns directly
- No json.loads() calls
- Builds result dict from typed columns

**Acceptance Criteria**:
- [x] No json.loads() calls
- [x] SELECT uses cfg_* columns
- [x] Output format unchanged

---

### Task 3.3: Delete dead code functions

**File**: `theauditor/fce.py`
**Location**: Lines 147-148 (comments), 866-872 (calls)

**Status**: COMPLETE

**Key Changes**:
- `load_churn_data_from_db()` DELETED (tool doesn't exist)
- `load_coverage_data_from_db()` DELETED (tool doesn't exist)
- Calls replaced with `churn_files = {}` and `coverage_files = {}`

**Acceptance Criteria**:
- [x] Dead code functions removed
- [x] Calls replaced with empty dicts
- [x] No queries for non-existent tools

---

### Task 3.4: Update fce.py load_taint_data_from_db()

**File**: `theauditor/fce.py`
**Location**: Lines 151-219

**Status**: COMPLETE

**Key Changes**:
- Now queries `taint_flows` table directly (not findings_consolidated)
- Only `path_json` needs json.loads (intermediate steps array)
- Builds structured taint path from normalized columns

**Acceptance Criteria**:
- [x] Uses taint_flows table
- [x] Only path_json needs parsing
- [x] Output format compatible with FCE

---

### Task 3.5: Normalize graphql_findings_cache table

**File**: `theauditor/fce.py`, `theauditor/indexer/schemas/graphql_schema.py`
**Location**: fce.py:324-364, graphql_schema.py:225-249

**Status**: COMPLETE

**Key Changes**:
- Replaced `details_json` column with typed columns: `description`, `message`, `confidence`
- Updated SELECT to use typed columns directly
- Removed json.loads call entirely
- Set metadata to empty dict (no JSON blob needed)

**Acceptance Criteria**:
- [x] No json.loads on details_json
- [x] Schema updated with typed columns
- [x] Reader uses typed columns directly

---

### Task 3.6: Update context/query.py get_findings()

**File**: `theauditor/context/query.py`
**Location**: Lines 1154-1221

**Status**: COMPLETE

**Key Changes**:
- SELECT now includes tool-specific columns
- Builds details dict from typed columns (no JSON parsing)
- ZERO FALLBACK violation FIXED (removed try/except)

**Acceptance Criteria**:
- [x] No json.loads for known tools
- [x] No misc_json fallback (ZERO FALLBACK)
- [x] ZERO FALLBACK violation removed

---

### Task 3.7: Update aws_cdk/analyzer.py from_standard_findings()

**File**: `theauditor/aws_cdk/analyzer.py`
**Location**: Lines 135-141

**Status**: COMPLETE

**Key Changes**:
- Removed json.loads on details_json
- Uses additional_info dict directly
- ZERO FALLBACK violation FIXED

**Acceptance Criteria**:
- [x] No json.loads on details_json
- [x] ZERO FALLBACK violation fixed

---

### Task 3.8: Update commands/workflows.py

**File**: `theauditor/commands/workflows.py`
**Location**: Lines 352-382

**Status**: COMPLETE

**Key Changes**:
- Removed details_json from SELECT
- Set details = {} (workflow findings don't use details)
- No json.loads needed

**Acceptance Criteria**:
- [x] details_json removed from SELECT
- [x] No json.loads call
- [x] Empty dict default

---

## Phase 4: Validation - COMPLETE

### Task 4.1: Schema Verification

**Status**: COMPLETE

**Results**:
```
Total columns: 36
details_json present: False
misc_json present: False

Column counts by prefix:
  cfg_*: 9
  graph_*: 7
  mypy_*: 3
  tf_*: 4
  TOTAL new: 23
```

**Acceptance Criteria**:
- [x] 36 columns total (13 core + 23 new)
- [x] details_json column removed
- [x] No misc_json column

---

### Task 4.2: Data Population Verification

**Status**: COMPLETE

**Results**:
```
Findings by tool:
  cdk: 8
  cfg-analysis: 69
  eslint: 459
  graph-analysis: 50
  mypy: 2815
  patterns: 5236
  ruff: 4804
  terraform: 7

cfg-analysis with cfg_complexity populated: 69
graph-analysis with graph_score populated: 50
terraform with tf_finding_id populated: 7
```

**Acceptance Criteria**:
- [x] cfg_* columns populated for cfg-analysis
- [x] graph_* columns populated for graph-analysis
- [x] tf_* columns populated for terraform

---

### Task 4.3: Pipeline Verification

**Status**: COMPLETE

**Results**:
```
[OK] AUDIT COMPLETE - All 25 phases successful
[TIME] Total time: 280.6s (4.7 minutes)

FCE: 14.1s, 13,361 findings processed
```

**Acceptance Criteria**:
- [x] `aud full --offline` completes without errors
- [x] FCE runs successfully
- [x] All 25 pipeline phases pass

---

## Phase 5: Bonus Fix - COMPLETE

### Task 5.1: Fix find_symbol schema mismatch

**File**: `theauditor/context/query.py`
**Location**: Lines 401-454

**Status**: COMPLETE

**Issue**: `aud explain` failed with `no such column: end_line`

**Root Cause**: `find_symbol()` assumed `symbols` and `symbols_jsx` tables have identical schemas, but `symbols_jsx` is simpler (no end_line, type_annotation, is_typed)

**Key Changes**:
- Split unified loop into two separate queries
- symbols: full schema (path, name, type, line, end_line, type_annotation, is_typed)
- symbols_jsx: simpler schema (path, name, type, line)

**Acceptance Criteria**:
- [x] `aud explain` works without errors
- [x] Both tables queried with correct columns

---

## Phase 6: Due Diligence Bug Fixes - COMPLETE

### Task 6.1: Fix mypy field name mismatch

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 751-753

**Status**: COMPLETE

**Issue**: mypy columns were all NULL (0/2817 populated)

**Root Cause**: Field name mismatch between linter output and writer expectations

| Linter writes | Writer expected | Fixed to |
|---------------|-----------------|----------|
| `mypy_code` | `error_code` | `mypy_code` |
| `mypy_severity` | `severity` | `mypy_severity` |

**Acceptance Criteria**:
- [x] Field names match linters.py output
- [x] mypy_error_code populated for findings with codes

---

### Task 6.2: Fix tool lookup using wrong variable

**File**: `theauditor/indexer/database/base_database.py`
**Location**: Lines 728-757

**Status**: COMPLETE

**Issue**: Tool-specific column mapping never triggered for linter findings

**Root Cause**: Writer checked `tool_name` parameter ("lint") instead of finding's actual tool

```python
# BEFORE (broken):
if tool_name == 'mypy':  # Always false when called from linters!

# AFTER (fixed):
actual_tool = f.get('tool', tool_name)  # Gets 'mypy' from finding dict
if actual_tool == 'mypy':
```

**Acceptance Criteria**:
- [x] `actual_tool` extracted from finding dict
- [x] All tool checks use `actual_tool` not `tool_name`
- [x] Linter findings correctly mapped to tool-specific columns

---

### Task 6.3: Verification of all tool-specific columns

**Status**: COMPLETE

**Results** (2025-11-28):
```
Findings by tool:
  patterns: 5240
  ruff: 4844
  mypy: 2817
  eslint: 461
  cfg-analysis: 69
  graph-analysis: 50
  cdk: 8
  terraform: 7

Tool-specific columns:
  cfg-analysis with cfg_complexity: 69/69
  graph-analysis with graph_score: 50/50
  terraform with tf_finding_id: 7/7
  mypy with mypy_error_code: 1861/1861 (956 mypy-notes have no codes - expected)
```

**Acceptance Criteria**:
- [x] All cfg_* columns populated for cfg-analysis
- [x] All graph_* columns populated for graph-analysis
- [x] All tf_* columns populated for terraform
- [x] All mypy_* columns populated for mypy (where data exists)

---

## Summary

| File | Changes | json.loads Removed |
|------|---------|-------------------|
| core_schema.py | +23 columns, -details_json | N/A |
| graphql_schema.py | +3 typed columns, -details_json | N/A |
| base_database.py | Rewrite write_findings_batch + bug fixes | 0 (was writer) |
| terraform/analyzer.py | Direct column INSERT | 0 (was writer) |
| aws_cdk/analyzer.py | Direct column INSERT + reader fix | 1 call |
| fce.py | 5 function rewrites + dead code removal | 8 calls |
| context/query.py | get_findings + find_symbol fix | 1 call |
| commands/workflows.py | Remove details_json SELECT | 1 call |

**Total json.loads removed**: 11 calls (10 from findings_consolidated + 1 from graphql_findings_cache)
**ZERO FALLBACK violations fixed**: 3
**Dead code functions removed**: 2
**Bonus issues fixed**: 1 (find_symbol schema mismatch)
**Due diligence bugs fixed**: 3 (mypy field names, tool lookup, graphql json.loads)

---

## Verification Commands

```bash
# Regenerate database
aud full --offline

# Verify schema
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(findings_consolidated)')
cols = [c[1] for c in cursor.fetchall()]
print(f'Total columns: {len(cols)}')
print(f'details_json present: {\"details_json\" in cols}')
print(f'cfg_complexity present: {\"cfg_complexity\" in cols}')
"

# Verify data population
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM findings_consolidated WHERE cfg_complexity IS NOT NULL')
print(f'cfg-analysis with cfg_complexity: {cursor.fetchone()[0]}')
"

# Verify explain works
aud explain write_findings_batch
```

---

## TICKET STATUS: COMPLETE

All phases implemented, validated, and verified.
