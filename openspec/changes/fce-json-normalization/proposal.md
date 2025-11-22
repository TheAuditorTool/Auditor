# FCE JSON Blob Normalization

**Status**: 🔴 PROPOSAL - Awaiting Architect approval

**Parent Proposal**: `performance-revolution-now` (TIER 1.5 Tasks 5, 6, 7)

**Assigned to**: AI #4 (Sonnet recommended - medium complexity)

**Timeline**: 3-4 days (2-3 days implementation + 1 day testing)

**Impact**: 🟡 **MEDIUM** - 75-700ms FCE overhead eliminated + Prevents future JSON violations

**PARALLEL-SAFE**: ✅ Can run concurrently with TIER 1 (different files, 1 coordinated conflict)

---

## Why

### **Problem 1: FCE JSON Blob Overhead (75-700ms)**

The FCE (Findings Consolidation Engine) currently stores all metadata in `findings_consolidated.details_json` as a JSON TEXT blob, requiring 7 `json.loads()` calls that add 75-700ms overhead:

```python
# fce.py - 7 json.loads() calls:
details = json.loads(row['details_json'])
hotspots = details.get('hotspots', [])           # Line 60: 5-10ms
cycles = details.get('cycles', [])               # Line 78: 5-10ms
complexity = details.get('cfg_complexity', [])   # Line 127: 10-20ms
churn = details.get('code_churn', [])           # Line 168: 20-50ms
coverage = details.get('test_coverage', [])      # Line 207: 30-100ms
taint_paths = details.get('paths', [])          # Line 265: 50-500ms ← CRITICAL BOTTLENECK
metadata = details.get('metadata', {})           # Line 401: 5-10ms
```

**Taint paths bottleneck**: 100-10K paths at 1KB+ each = 50-500ms parsing time

### **Problem 2: Violates Commit d8370a7 Normalization Standard**

Commit d8370a7 (Oct 23, 2025) established the "junction table with AUTOINCREMENT" pattern for all relational data but explicitly exempted `findings_consolidated.details_json` as "Intentional findings metadata storage."

**This exemption was wrong.** Measured FCE overhead (75-700ms) justifies normalization.

### **Problem 3: symbols.parameters Still Uses JSON**

Despite d8370a7, `symbols.parameters` column still stores JSON, causing duplicate parsing in `taint/discovery.py:112` and `javascript.py:1288`.

### **Problem 4: No Schema Enforcement**

Future developers might add more JSON blobs, repeating the same mistake. Need automated detection.

---

## What Changes

### **Task 5: FCE findings_consolidated.details_json Normalization**

**Create 4 normalized tables**:

1. **`finding_taint_paths`** (CRITICAL - eliminates 50-500ms bottleneck)
```sql
CREATE TABLE finding_taint_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,
    path_index INTEGER NOT NULL,
    source_file TEXT,
    source_line INTEGER,
    source_expr TEXT,
    sink_file TEXT,
    sink_line INTEGER,
    sink_expr TEXT,
    path_length INTEGER,
    confidence REAL,
    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);
CREATE INDEX idx_finding_taint_paths_finding_id ON finding_taint_paths(finding_id);
```

2. **`finding_graph_hotspots`** (5-10ms overhead)
3. **`finding_cfg_complexity`** (10-20ms overhead)
4. **`finding_metadata`** (churn, coverage, CWE/CVEs - 55-160ms overhead)

**Replace 7 json.loads() with JOINs**:
```python
# BEFORE (fce.py:265):
details = json.loads(details_json)  # 50-500ms
taint_paths = details.get('paths', [])

# AFTER:
cursor.execute("""
    SELECT source_file, source_line, source_expr,
           sink_file, sink_line, sink_expr, confidence
    FROM finding_taint_paths
    WHERE finding_id = ?
    ORDER BY path_index
""", (finding_id,))
taint_paths = cursor.fetchall()  # O(1) indexed lookup, <1ms
```

### **Task 6: symbols.parameters Normalization**

**Create `symbol_parameters` table**:
```sql
CREATE TABLE symbol_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id TEXT NOT NULL,
    param_index INTEGER NOT NULL,
    param_name TEXT,
    param_type TEXT,
    default_value TEXT,
    is_optional INTEGER,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
);
```

**Update consumers** (`taint/discovery.py:112`, `javascript.py:1288`)

### **Task 7: Schema Contract Validation**

**Add JSON blob detector** to `schema.py`:
```python
def _detect_json_blobs(tables):
    violations = []
    LEGITIMATE_EXCEPTIONS = {
        ('nodes', 'metadata'),  # graphs.db intentional
        ('edges', 'metadata'),
        ('plan_documents', 'document_json'),
    }
    for table in tables:
        for col in table.columns:
            if col.type == "TEXT" and col.name.endswith(('_json', 'dependencies', 'parameters')):
                if (table.name, col.name) not in LEGITIMATE_EXCEPTIONS:
                    violations.append((table.name, col.name))
    assert len(violations) == 0, f"JSON violations: {violations}"
```

**Catches future violations at schema load time.**

---

## Impact

### **Affected Code**

**Modified Files** (450-500 lines total):
- `theauditor/fce.py` - Replace 7 json.loads() with JOINs (200 lines modified)
- `theauditor/indexer/schemas/core_schema.py` - Add 5 normalized tables (300 lines added)
- `theauditor/indexer/database/base_database.py` - Update findings writer (50 lines modified)
- `theauditor/taint/discovery.py` - Replace parameters parsing (5 lines modified, line 112)
- `theauditor/indexer/extractors/javascript.py` - Replace parameters parsing (5 lines modified, line 1288)
- `theauditor/indexer/schema.py` - Add JSON blob validator (100 lines added)

**Coordination Point with AI #3**:
⚠️ **CONFLICT**: Both AI #3 and AI #4 touch `javascript.py`
- **AI #3**: Lines 748-768 (module resolution)
- **AI #4**: Line 1288 (parameters normalization)
- **Merge Strategy**: Apply both changes, different line ranges (safe)

### **Breaking Changes**

**Database Schema Changes** (REQUIRE `aud full` reindex):

1. **New Tables**: 5 tables added
   - `finding_taint_paths`
   - `finding_graph_hotspots`
   - `finding_cfg_complexity`
   - `finding_metadata`
   - `symbol_parameters`

2. **Deprecated Columns**:
   - `findings_consolidated.details_json` → Removed (data migrated to tables)
   - `symbols.parameters` → Removed (data migrated to symbol_parameters)

3. **Migration Path**: Standard - Run `aud full` to regenerate database (fresh)

**External API Preserved**: FCE consumers still call `run_fce(root_path)` → no changes needed

### **REVERSES Commit d8370a7 Exemption**

Commit d8370a7 (Oct 23, 2025) explicitly exempted `findings_consolidated.details_json` as "Intentional findings metadata storage."

**This proposal REVERSES that decision** based on measured FCE overhead (75-700ms, with taint paths at 50-500ms).

**Justification**: Performance measurements trump assumptions. JSON blobs are cancer.

---

## Dependencies

**Prerequisites**:
- ✅ Schema contract system exists (`schema.py`)
- ✅ Junction table pattern established (commit d8370a7)

**Required Reading** (BEFORE coding):
1. `performance-revolution-now/INVESTIGATION_REPORT.md` section 5.1 (FCE findings)
2. `performance-revolution-now/design.md` sections 5.1-5.3 (normalization design)
3. This proposal's `tasks.md` sections 5.1-5.5, 6.1-6.5, 7.1-7.4
4. Commit d8370a7 diff (understand junction table pattern)
5. `teamsop.md` v4.20 (Prime Directive)

**Blocking**: None - Can start immediately (PARALLEL-SAFE with TIER 1)

**Blocked by this**: None

---

## Testing Strategy

### **Correctness Testing**

1. **Fixture validation**: Test on 10 projects with known taint findings
2. **FCE output comparison**: Before/after must match (functionally equivalent)
3. **Taint path ordering**: Verify `path_index` preserved correctly
4. **Critical**: Ensure no data loss in normalization

### **Performance Testing**

1. **Measure FCE time before/after**:
   - Before: 75-700ms overhead
   - After: <10ms overhead (90%+ improvement)
2. **Profile with cProfile**: Measure json.loads() elimination

---

## Success Criteria

**MUST MEET ALL**:

1. ✅ FCE overhead: 75-700ms → <10ms (90%+ improvement)
2. ✅ Zero JSON TEXT columns (except documented exemptions)
3. ✅ All tests passing (zero regressions)
4. ✅ Fixtures functionally equivalent (may differ in order, but same data)
5. ✅ Schema validator catches future violations
6. ✅ Coordinated merge with AI #3 on javascript.py

---

## Approval Gates

**Stage 1**: Proposal Review (Current)
- [ ] Architect reviews proposal
- [ ] Architect approves REVERSING commit d8370a7 exemption

**Stage 2**: Verification
- [ ] Coder reads INVESTIGATION_REPORT.md section 5.1
- [ ] Coder completes verification protocol
- [ ] Architect approves verification

**Stage 3**: Implementation
- [ ] FCE normalization (tasks 5.1-5.5)
- [ ] symbols.parameters normalization (tasks 6.1-6.5)
- [ ] Schema validator (tasks 7.1-7.4)
- [ ] Coordinate merge with AI #3

**Stage 4**: Deployment
- [ ] Performance validated
- [ ] Architect approves
- [ ] Merged to main

---

## Related Changes

**Parent**: `performance-revolution-now` (PAUSED AND SPLIT)

**Siblings** (can run in parallel):
- `taint-analysis-spatial-indexes` (AI #1) - Zero file conflicts
- `fix-python-ast-orchestrator` (AI #2) - Zero file conflicts
- `vue-inmemory-module-resolution` (AI #3) - 1 file conflict (coordinate merge)
- `database-indexes-cleanup` (TIER 2) - Zero file conflicts

**Merge Strategy**: Coordinate with AI #3 on `javascript.py`

---

**Next Step**: Architect reviews and approves REVERSING commit d8370a7 exemption
