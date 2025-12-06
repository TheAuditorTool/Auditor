# Normalize findings_consolidated.details_json to Sparse Wide Table

**Status**: PROPOSAL - Awaiting Architect Approval
**Change ID**: `normalize-findings-details-json`
**Complexity**: MEDIUM (10 json.loads calls, 3 writer files, 4 reader files)
**Estimated Time**: 16 hours
**Breaking**: YES - Requires `aud full` reindex after deployment
**Risk Level**: LOW-MEDIUM (79% of rows unaffected, main paths unchanged)
**Last Updated**: 2025-11-27 (Re-verified after codebase refactors)

---

## Why

### Problem Statement

The `findings_consolidated.details_json` column stores tool-specific metadata as a JSON TEXT blob. This causes:

1. **Performance overhead**: 8 `json.loads()` calls in FCE add 125-700ms per run
2. **No SQL filtering**: Cannot query `WHERE complexity > 10` - must load all rows and filter in Python
3. **Silent failures**: try/except blocks around JSON parsing hide data corruption
4. **Violation of d8370a7 pattern**: The schema normalization commit established junction tables as the standard

### Measured Impact (Verified 2025-11-24)

| Tool | Rows | details_json Used | Keys |
|------|------|-------------------|------|
| ruff | 11,604 | 0% (empty) | 0 |
| patterns | 5,298 | 0% (empty) | 0 |
| mypy | 4,397 | 100% | 3 scalar |
| eslint | 463 | 0% (empty) | 0 |
| cfg-analysis | 66 | 100% | 9 scalar |
| graph-analysis | 50 | 100% | 7 scalar |
| cdk | 14 | 0% (empty) | 0 |
| terraform | 7 | 100% | 4 scalar |
| taint | 1 | 100% | 7 LIST/DICT |
| **TOTAL** | **21,900** | **21%** | **23 scalar + 7 complex** |

**Key Finding**: 79% of rows (17,379/21,900) have `details_json = '{}'` (verified 2025-11-24)

### Solution: Sparse Wide Table (Gemini 2025 Pattern)

Instead of junction tables (complex) or generated columns (slow), flatten the 23 scalar keys directly into the table as nullable columns. SQLite stores NULLs in the record header with zero payload bytes.

**Benefits**:
- Zero storage overhead for 79% of rows (NULLs are free)
- O(log n) indexed queries vs O(n) json.loads() + Python filter
- Enables SQL-level correlation: `WHERE complexity > 10 AND hotspot_score > 0.8`
- Respects ZERO FALLBACK policy (no try/except for JSON parsing)

---

## What Changes

### Summary

| Change Type | Count | Files |
|-------------|-------|-------|
| Schema columns added | 24 (23 + misc_json) | 1 |
| Schema indexes added | 2 | 1 |
| Writers updated | 2 | 2 |
| json.loads removed | 10 | 4 |
| **Total lines changed** | ~400 | ~7 |

### Schema Changes (BREAKING)

**File**: `theauditor/indexer/schemas/core_schema.py:488-514`

**BEFORE** (14 columns):
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
        Column("details_json", "TEXT", default="'{}'"),  # <-- REMOVE
    ],
    ...
)
```

**AFTER** (36 columns):
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

        # === MYPY COLUMNS (3) - 4,397 rows ===
        Column("mypy_severity", "TEXT"),      # "error", "warning", "note"
        Column("mypy_code", "TEXT"),          # "no-untyped-def", "var-annotated"
        Column("mypy_hint", "TEXT"),          # Additional hint text

        # === CFG-ANALYSIS COLUMNS (9) - 66 rows ===
        Column("cfg_complexity", "INTEGER"),  # Cyclomatic complexity
        Column("cfg_block_count", "INTEGER"), # Basic blocks
        Column("cfg_edge_count", "INTEGER"),  # Control flow edges
        Column("cfg_start_line", "INTEGER"),  # Function start
        Column("cfg_end_line", "INTEGER"),    # Function end
        Column("cfg_function", "TEXT"),       # Function name
        Column("cfg_has_loops", "INTEGER"),   # Boolean as INT (0/1)
        Column("cfg_max_nesting", "INTEGER"), # Max nesting depth

        # === GRAPH-ANALYSIS COLUMNS (7) - 50 rows ===
        Column("graph_centrality", "REAL"),   # Betweenness centrality
        Column("graph_churn", "INTEGER"),     # Git churn count
        Column("graph_in_degree", "INTEGER"), # Incoming edges
        Column("graph_out_degree", "INTEGER"),# Outgoing edges
        Column("graph_loc", "INTEGER"),       # Lines of code
        Column("graph_score", "REAL"),        # Hotspot score
        Column("graph_node_id", "TEXT"),      # Node identifier

        # === TERRAFORM COLUMNS (4) - 7 rows ===
        Column("tf_finding_id", "TEXT"),      # Terraform finding ID
        Column("tf_resource_id", "TEXT"),     # Resource identifier
        Column("tf_remediation", "TEXT"),     # Remediation guidance
        Column("tf_graph_context", "TEXT"),   # Graph context (TEXT, not JSON)

        # === FALLBACK FOR COMPLEX DATA ===
        Column("misc_json", "TEXT", default="'{}'"),  # ONLY for taint paths (1 row)
    ],
    indexes=[
        # Existing indexes
        ("idx_findings_file_line", ["file", "line"]),
        ("idx_findings_tool", ["tool"]),
        ("idx_findings_severity", ["severity"]),
        ("idx_findings_rule", ["rule"]),
        ("idx_findings_category", ["category"]),
        ("idx_findings_tool_rule", ["tool", "rule"]),
        # NEW: Partial indexes for sparse columns
        ("idx_findings_complexity", ["cfg_complexity"], "cfg_complexity IS NOT NULL"),
        ("idx_findings_hotspot", ["graph_score"], "graph_score IS NOT NULL"),
        ("idx_findings_centrality", ["graph_centrality"], "graph_centrality IS NOT NULL"),
        ("idx_findings_mypy_code", ["mypy_code"], "mypy_code IS NOT NULL"),
    ]
)
```

### Writer Changes (2 files)

| File | Lines | Method | Change |
|------|-------|--------|--------|
| `base_database.py` | 647-735 | `write_findings_batch()` | Tool-specific column mapping |
| `terraform/analyzer.py` | 166-195 | Direct INSERT | Write to `tf_*` columns |

Note: `commands/taint.py` uses `write_findings_batch()` which handles taint via `misc_json`.

### Reader Changes (10 json.loads calls in 4 files)

| File | Line | Function | Change |
|------|------|----------|--------|
| `fce.py` | 61 | `load_graph_data_from_db()` | SELECT `graph_*` columns directly |
| `fce.py` | 75 | `load_graph_data_from_db()` | SELECT `graph_*` columns directly |
| `fce.py` | 117 | `load_cfg_data_from_db()` | SELECT `cfg_*` columns directly |
| `fce.py` | 151 | `load_churn_data_from_db()` | DEAD CODE - tool doesn't exist |
| `fce.py` | 183 | `load_coverage_data_from_db()` | DEAD CODE - tool doesn't exist |
| `fce.py` | 234 | `load_taint_data_from_db()` | **USE taint_flows TABLE** |
| `fce.py` | 372 | `load_graphql_findings_from_db()` | Different table, add TODO |
| `context/query.py` | 1182 | `get_findings()` | Build dict from columns |
| `aws_cdk/analyzer.py` | 141 | `from_standard_findings()` | Use misc_json fallback |
| `commands/workflows.py` | 378 | `get_workflow_findings()` | Use misc_json fallback |

---

## Impact

### Files Modified

| File | LOC Changed | Risk |
|------|-------------|------|
| `theauditor/indexer/schemas/core_schema.py` | ~50 | LOW |
| `theauditor/indexer/database/base_database.py` | ~100 | MEDIUM |
| `theauditor/fce.py` | ~150 | HIGH |
| `theauditor/context/query.py` | ~50 | MEDIUM |
| `theauditor/terraform/analyzer.py` | ~20 | LOW |
| `theauditor/aws_cdk/analyzer.py` | ~10 | LOW |
| `theauditor/commands/workflows.py` | ~10 | LOW |
| **TOTAL** | **~390** | |

### Breaking Changes

1. **Database schema change**: New columns added, `details_json` renamed to `misc_json`
2. **Requires reindex**: Users MUST run `aud full` after update
3. **No backwards compatibility**: Old databases will not work (by design - regenerated fresh)

### What Does NOT Break

| Component | Status | Reason |
|-----------|--------|--------|
| `aud full` | UNAFFECTED | Write-only path |
| `aud report` | UNAFFECTED | Does not use details_json |
| `aud detect-patterns` | UNAFFECTED | Write-only path |
| Main findings flow | UNAFFECTED | `load_findings_from_db()` at fce.py:483 does not SELECT details_json |

---

## Risk Assessment

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FCE breaks silently | LOW | HIGH | Remove all try/except, let errors crash |
| Data loss | LOW | HIGH | Verify row counts before/after |
| Performance regression | LOW | MEDIUM | Benchmark with cProfile |
| New column naming conflict | LOW | LOW | Prefix all new columns (mypy_, cfg_, graph_, tf_) |

### Rollback Plan

1. `git revert <commit>` - Revert all changes
2. Run `aud full` - Regenerate database with old schema
3. **Time to rollback**: ~15 minutes

---

## Success Criteria

All criteria MUST be met before marking complete:

- [ ] Schema updated with 24 new columns (23 + misc_json) in core_schema.py:488-514
- [ ] 2 writers updated: base_database.py, terraform/analyzer.py
- [ ] All 10 json.loads() calls removed/updated (7 in fce.py, 3 in other files)
- [ ] FCE `load_taint_data_from_db()` uses `taint_flows` table (not details_json)
- [ ] Zero `json.loads` calls on `details_json` in codebase
- [ ] ZERO FALLBACK violations fixed in context/query.py, aws_cdk/analyzer.py, commands/workflows.py
- [ ] Dead code removed: fce.py load_churn_data_from_db(), load_coverage_data_from_db()
- [ ] All tests passing
- [ ] Performance: FCE correlation <10ms (down from 125-700ms)
- [ ] `misc_json` only used for taint complex data

---

## Testing Strategy

### Unit Tests

1. **Schema test**: Verify all 36 columns exist after `aud full`
2. **Writer tests**: Verify each tool writes to correct columns
3. **Reader tests**: Verify FCE functions return correct data without JSON parsing

### Integration Tests

1. Run `aud full` on TheAuditor codebase itself
2. Verify `aud fce` completes without errors
3. Verify `aud explain` shows findings correctly

### Performance Tests

```bash
# Before: Measure current FCE time
python -m cProfile -s cumtime -c "from theauditor.fce import run_fce; run_fce('.')" 2>&1 | grep json.loads

# After: Verify no json.loads in profile
# Should show 0 calls to json.loads for details_json
```

---

## Dependencies

### Prerequisites

- [x] Schema system supports nullable columns (VERIFIED)
- [x] Schema system supports partial indexes (VERIFIED - existing pattern)
- [x] `taint_flows` table exists (VERIFIED - 1 row currently)
- [x] Database regenerates fresh on `aud full` (VERIFIED - no migration needed)

### Required Reading

1. `teamsop.md` - Prime Directive, verification requirements
2. `CLAUDE.md:194-249` - ZERO FALLBACK policy
3. Commit d8370a7 - Junction table pattern (for context)
4. This proposal's `verification.md` - All hypothesis verifications
5. This proposal's `tasks.md` - Atomic implementation steps

---

## Approval Required

### Architect Decision Points

1. **Approve sparse wide table pattern** (vs junction tables from d8370a7)
   - Rationale: Simpler, same performance, 77% NULL storage is free

2. **Approve keeping misc_json for taint** (1 row only)
   - Rationale: Taint has 7 LIST/DICT keys, too complex to flatten
   - Alternative: FCE should read from `taint_flows` table directly

3. **Approve breaking change** (requires reindex)
   - Rationale: Database regenerates fresh, no migration complexity

---

## Related

- **Supersedes**: `archive/fce-json-normalization` (never implemented)
- **Supersedes**: `archive/fce-column-flattening` (never implemented)
- **References**: Commit d8370a7 (schema normalization pattern)
- **Conflicts with**: None identified

---

**Next Step**: Architect reviews and approves/denies this proposal
