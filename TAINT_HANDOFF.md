# Taint Analysis System - Due Diligence Handoff

## Executive Summary

**System Status**: FUNCTIONAL but with data quality issues
**Last Run**: PlantFlow - 99,116 flows resolved in ~72 minutes
**Primary Concern**: 99.6% of flows hit max_depth=20, vulnerability_type always "unknown"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     aud taint-analyze                               │
│                         (taint.py)                                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  FlowResolver   │     │  IFDSAnalyzer   │
│  (forward mode) │     │ (backward mode) │
│  flow_resolver  │     │ ifds_analyzer   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  repo_index.db  │     │   graphs.db     │
│  (raw facts)    │     │  (data flow)    │
└─────────────────┘     └─────────────────┘
```

### Three Analysis Modes

| Mode | Engine | Direction | Use Case |
|------|--------|-----------|----------|
| `backward` | IFDSTaintAnalyzer | Sink → Source | Security findings (IFDS demand-driven) |
| `forward` | FlowResolver | Entry → Exit | Complete codebase flow map |
| `complete` | Both | Both | Full analysis |

---

## Current Issues (Priority Order)

### CRITICAL: All Flows Have `vulnerability_type = "unknown"`

**Evidence**:
```sql
SELECT vulnerability_type, COUNT(*) FROM resolved_flow_audit GROUP BY vulnerability_type;
-- Result: unknown: 99,116
```

**Root Cause**: `flow_resolver.py:597` hardcodes `"unknown"`:
```python
cursor.execute("""
    INSERT INTO resolved_flow_audit (..., vulnerability_type, ...)
    VALUES (..., ?, ...)
""", (..., "unknown", ...))  # Line 597
```

**Impact**: Cannot filter/report by vulnerability type (SQLi, XSS, RCE, etc.)

**Fix Required**: Classify flows based on sink patterns:
- `res.send/res.render` → XSS
- `db.query/sequelize.*` → SQLi
- `exec/spawn/system` → RCE
- `fs.*/path.*` → Path Traversal

---

### HIGH: 99.6% of Flows Hit max_depth=20 (Truncated)

**Evidence**:
```
Path length distribution:
  20 hops: 98,702 (99.6%)
  <20 hops: 414 (0.4%)
```

**Analysis**: These aren't "20-hop flows" - they're truncated at the limit.

**Options**:
1. Increase `max_depth` (slower, more memory)
2. Add smarter pruning (stop at validation/sanitizer)
3. Accept truncation (current behavior)

**Current Code** (`flow_resolver.py:33`):
```python
self.max_depth = 20  # Hardcoded limit
```

---

### HIGH: sink_line Only 67.6% Populated

**Evidence**:
```
source_line populated: 99,116/99,116 (100.0%)  ✓ FIXED
sink_line populated: 67,027/99,116 (67.6%)     ✗ NEEDS FIX
```

**Root Cause**: Sink lookup only queries `function_call_args`, but:
- React hooks (`useState`, `useQuery`) are in `callee_function`, not `argument_expr`
- JSX mode data is in `function_call_args_jsx` table
- JSX elements (`<input>`, `<button>`) not captured anywhere

**Uncommitted Fix** (`flow_resolver.py:546-569`):
```python
# UNION with function_call_args_jsx
# Search both argument_expr AND callee_function
```

**Estimated Improvement**: ~32% of missing lines would be found

**Remaining Gap**: JSX element tags not in any table (extractor limitation)

---

### MEDIUM: IFDS Never Ran (0 Results)

**Evidence**:
```sql
SELECT engine, COUNT(*) FROM resolved_flow_audit GROUP BY engine;
-- FlowResolver: 99,116
-- IFDS: 0
```

**Analysis**: PlantFlow ran with `--mode forward` (FlowResolver only).

**Impact**: No backward security analysis (demand-driven from sinks).

**To Test IFDS**: Run `aud taint-analyze --mode backward` or `--mode complete`

---

### MEDIUM: No Sanitizer Detection in FlowResolver

**Evidence**:
```sql
SELECT status, COUNT(*) FROM resolved_flow_audit GROUP BY status;
-- VULNERABLE: 99,116
-- SANITIZED: 0
```

**Analysis**: All 99,116 flows marked VULNERABLE, but:
- 233 Joi validations exist in codebase
- 3 safe sinks registered (res.json, res.jsonp, res.status().json)

**Root Cause Check**: `SanitizerRegistry` is loaded but may not match patterns.

**Code Path**: `flow_resolver.py:427-428`:
```python
status, sanitizer_meta = self._classify_flow(path)  # Calls sanitizer_registry
```

---

### LOW: cross_boundary Edges = 0 in graphs.db

**Evidence**:
```sql
SELECT COUNT(*) FROM edges WHERE type = 'cross_boundary';
-- Result: 0
```

**Impact**: FlowResolver uses cross_boundary for entry points (`_get_entry_nodes`).
Currently relies on pattern matching as fallback.

**Graph Builder Issue**: `aud graph build` not creating cross_boundary edges?

---

## Data Quality Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total flows | 99,116 | OK |
| source_line populated | 100% | FIXED |
| sink_line populated | 67.6% | NEEDS FIX |
| vulnerability_type classified | 0% | CRITICAL |
| Sanitizer detection | 0% | MEDIUM |
| Flows at max_depth | 99.6% | INVESTIGATE |
| IFDS backward analysis | 0 | NOT RUN |

---

## Files Modified (Uncommitted)

### `theauditor/taint/flow_resolver.py`

```diff
-SELECT MIN(line) FROM function_call_args
-WHERE file = ? AND argument_expr LIKE ?
+SELECT MIN(line) FROM (
+    SELECT line FROM function_call_args
+    WHERE file = ? AND (argument_expr LIKE ? OR callee_function LIKE ?)
+    UNION ALL
+    SELECT line FROM function_call_args_jsx
+    WHERE file = ? AND (argument_expr LIKE ? OR callee_function LIKE ?)
+)
```

**Decision Needed**: Commit this partial fix or expand further?

---

## Recommended Next Steps

### Immediate (Before Commit)

1. **Classify vulnerability_type** - Map sink patterns to vuln categories
2. **Commit sink_line fix** - Partial improvement is better than none

### Short Term

3. **Debug sanitizer detection** - Why 0 SANITIZED flows?
4. **Run IFDS mode** - Test backward analysis for comparison
5. **Investigate max_depth=20** - Are these real long flows or infinite loops?

### Medium Term

6. **Add cross_boundary edges** - Fix graph builder
7. **Capture JSX elements** - Modify TypeScript extractor

---

## Verification Commands

```bash
# Check flow audit status
cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('C:/Users/santa/Desktop/plantflow/.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT vulnerability_type, COUNT(*) FROM resolved_flow_audit GROUP BY vulnerability_type')
for row in c.fetchall(): print(f'{row[0]}: {row[1]}')
"

# Test IFDS mode
aud taint-analyze --mode backward --max-depth 5

# Check sanitizer loading
THEAUDITOR_DEBUG=1 aud taint-analyze --mode forward 2>&1 | grep -i sanitizer
```

---

## Key Files Reference

| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `taint/flow_resolver.py` | Forward flow resolution | 33 (max_depth), 546-569 (sink_line), 597 (vuln_type) |
| `taint/ifds_analyzer.py` | Backward IFDS analysis | 38-39 (limits), 55-82 (main entry) |
| `taint/core.py` | Mode dispatch, registry | 301-342 (forward), 344-376 (complete) |
| `taint/discovery.py` | Source/sink discovery | 29-117 (sources), 119-457 (sinks) |
| `taint/sanitizer_util.py` | Sanitizer detection | 144-237 (_path_goes_through_sanitizer) |
| `commands/taint.py` | CLI command | 48-50 (options), 370-377 (trace_taint call) |

---

## Session Context

- **Project**: PlantFlow (cannabis dispensary)
- **Indexing Time**: ~40 minutes
- **Taint Analysis Time**: ~72 minutes (FlowResolver forward mode)
- **Previous Fix**: source_line lookup (commit `6ea3af4`)
- **Current**: sink_line fix uncommitted, vulnerability_type unaddressed
