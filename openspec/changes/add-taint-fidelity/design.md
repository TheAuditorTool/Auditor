# Design: Taint Fidelity System

## Architecture Overview

The taint fidelity system mirrors the existing fidelity patterns in `indexer/fidelity.py` and `graph/fidelity.py`. It adds manifest/receipt checkpoints at 4 critical locations in the taint pipeline.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TAINT PIPELINE WITH FIDELITY                          │
└─────────────────────────────────────────────────────────────────────────────┘

     DISCOVERY              ANALYSIS              DEDUP                OUTPUT
         │                      │                   │                     │
         ▼                      ▼                   ▼                     ▼
    ┌─────────┐            ┌─────────┐        ┌─────────┐           ┌─────────┐
    │ sources │            │  IFDS   │        │ dedup   │           │ DB +    │
    │  sinks  │───────────►│ Trace   │───────►│ paths   │──────────►│  JSON   │
    └─────────┘            └─────────┘        └─────────┘           └─────────┘
         │                      │                   │                     │
         ▼                      ▼                   ▼                     ▼
    ┌─────────┐            ┌─────────┐        ┌─────────┐           ┌─────────┐
    │Manifest │            │Manifest │        │Manifest │           │Receipt  │
    │   #1    │            │   #2    │        │   #3    │           │ #4a,#4b │
    └─────────┘            └─────────┘        └─────────┘           └─────────┘
         │                      │                   │                     │
         └──────────────────────┴───────────────────┴─────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  reconcile_taint_   │
                              │     fidelity()      │
                              └─────────────────────┘
```

## Checkpoint Details

### Checkpoint 1: Discovery Manifest

**Location**: `core.py:567` (insert after line 566 `sinks = discovery.filter_framework_safe_sinks(sinks)`)

**What it captures**:
```python
{
    "sources": {
        "count": 140,
        "tx_id": "uuid-...",
        "columns": ["file", "line", "pattern", "category", ...],
        "bytes": 45000
    },
    "sinks": {
        "count": 200,
        "tx_id": "uuid-...",
        "columns": ["file", "line", "pattern", "category", ...],
        "bytes": 62000
    },
    "_stage": "discovery"
}
```

**What it catches**:
- Query returning 0 sources when repo has HTTP endpoints
- Query returning 0 sinks when repo has SQL/exec calls
- Pattern matching regex failing silently

### Checkpoint 2: Analysis Manifest

**Location**: `core.py:686` (insert after line 685 `all_sanitized_paths.extend(sanitized)`, before line 686 `ifds_analyzer.close()`)

**What it captures**:
```python
{
    "vulnerable_paths": {
        "count": 325,
        "tx_id": "uuid-...",
        "bytes": 180000
    },
    "sanitized_paths": {
        "count": 45,
        "tx_id": "uuid-...",
        "bytes": 25000
    },
    "sinks_analyzed": 200,
    "sources_checked": 140,
    "_stage": "analysis"
}
```

**What it catches**:
- IFDS loop terminating early due to exception
- max_depth truncating all paths prematurely
- Algorithm bug causing 0 paths found

### Checkpoint 3: Deduplication Manifest

**Location**: `core.py:697` (insert after line 696 `unique_sanitized_paths = deduplicate_paths(all_sanitized_paths)`)

**What it captures**:
```python
{
    "pre_dedup_count": 370,
    "post_dedup_count": 185,
    "removed_count": 185,
    "removal_ratio": 0.5,
    "_stage": "dedup"
}
```

**What it catches**:
- Hash collisions causing excessive deduplication
- Dedup algorithm bug removing valid unique paths
- >50% removal triggers warning for investigation

### Checkpoint 4a: DB Output Receipt

**Location**: `core.py:797` (insert after line 796 `conn.commit()` in `trace_taint()`)

**What it captures**:
```python
{
    "db_rows": 185,
    "vulnerable_count": 140,
    "sanitized_count": 45,
    "_stage": "db_output"
}
```

**What it catches**:
- DB insert failing silently (constraint violation)
- Transaction rollback without raising
- Row count mismatch

### Checkpoint 4b: JSON Output Receipt

**Location**: `core.py:955-973` (replace entire `save_taint_analysis()` function to add byte tracking)

**Note**: This is a **separate function** from `trace_taint()`. The JSON write happens in `save_taint_analysis()` which is called by the CLI after `trace_taint()` returns. The current implementation uses `json.dump()` directly to file handle, which doesn't allow capturing byte count. Must refactor to use `json.dumps()` + `f.write()` pattern.

**What it captures**:
```python
{
    "json_count": 140,
    "json_bytes": 245000,
    "_stage": "json_output"
}
```

**What it catches**:
- JSON serialization dropping paths (non-serializable objects)
- File write interrupted
- Encoding errors

## File Structure

```
theauditor/taint/
├── __init__.py
├── access_path.py
├── core.py              # MODIFY: Add 3 checkpoints in trace_taint() + refactor save_taint_analysis()
├── discovery.py
├── fidelity.py          # NEW: Fidelity module
├── flow_resolver.py     # UNCHANGED (independent engine)
├── ifds_analyzer.py     # UNCHANGED
├── taint_path.py
└── type_resolver.py
```

## Error Handling

### Strict Mode (Default)

```python
reconcile_taint_fidelity(manifest, receipt, stage="db_output", strict=True)
# Raises TaintFidelityError if counts mismatch
```

### Non-Strict Mode (Debugging)

```python
reconcile_taint_fidelity(manifest, receipt, stage="db_output", strict=False)
# Logs error but continues execution
```

### Environment Variable Override

```bash
TAINT_FIDELITY_STRICT=0 aud taint  # Disable strict mode globally
```

## Integration with Pipeline Logging

The fidelity results will be logged using the existing `logger` infrastructure:

```
[INFO] Taint Discovery: 140 sources, 200 sinks [Fidelity: OK]
[INFO] IFDS Analysis: 325 vulnerable, 45 sanitized [Fidelity: OK]
[WARNING] Taint Fidelity Warnings at dedup: removed 50% of paths
[INFO] Taint DB Output: 185 rows [Fidelity: OK]
[INFO] Taint JSON Output: 140 vulns, 245000 bytes [Fidelity: OK]
```

## Dependencies

### Uses Existing Infrastructure

- `theauditor.indexer.fidelity_utils.FidelityToken` - manifest/receipt creation
- `theauditor.utils.logging.logger` - logging infrastructure

### FidelityToken API Reference

```python
# FidelityToken.create_manifest(data: list[dict]) returns:
{
    "count": int,      # len(data)
    "tx_id": str,      # UUID for transaction tracing
    "columns": list,   # sorted(first_row.keys())
    "bytes": int       # sum of string lengths of all values
}

# FidelityToken.create_receipt(count, columns, tx_id, data_bytes) returns:
{
    "count": int,
    "columns": list,
    "tx_id": str | None,
    "bytes": int
}
```

### No New Dependencies

- No new packages required
- No new database tables
- No new CLI commands

## Testing Strategy

### Unit Tests

```python
# tests/taint/test_fidelity.py

def test_discovery_manifest_structure():
    sources = [{"file": "a.py", "line": 1}]
    sinks = [{"file": "b.py", "line": 2}]
    manifest = create_discovery_manifest(sources, sinks)
    assert manifest["sources"]["count"] == 1
    assert manifest["sinks"]["count"] == 1
    assert "_stage" in manifest

def test_dedup_manifest_ratio():
    manifest = create_dedup_manifest(100, 40)
    assert manifest["removal_ratio"] == 0.6
    assert manifest["removed_count"] == 60

def test_reconcile_catches_100_percent_loss():
    manifest = {"paths_to_write": 100}
    receipt = {"db_rows": 0}
    with pytest.raises(TaintFidelityError):
        reconcile_taint_fidelity(manifest, receipt, "db_output", strict=True)

def test_reconcile_warns_on_high_dedup():
    manifest = create_dedup_manifest(100, 40)
    result = reconcile_taint_fidelity(manifest, {}, "dedup", strict=False)
    assert result["status"] == "WARNING"

def test_env_var_disables_strict():
    import os
    os.environ["TAINT_FIDELITY_STRICT"] = "0"
    manifest = {"paths_to_write": 100}
    receipt = {"db_rows": 0}
    # Should NOT raise despite 100% loss
    result = reconcile_taint_fidelity(manifest, receipt, "db_output", strict=True)
    assert result["status"] == "FAILED"
    del os.environ["TAINT_FIDELITY_STRICT"]
```

### Integration Tests

```python
# tests/taint/test_fidelity_integration.py

def test_full_pipeline_fidelity(test_project_with_vulns):
    """Run aud taint and verify fidelity passes at all stages."""
    result = run_taint_analysis(test_project_with_vulns)

    assert result["discovery_fidelity"]["status"] == "OK"
    assert result["analysis_fidelity"]["status"] == "OK"
    assert result["dedup_fidelity"]["status"] in ("OK", "WARNING")
    assert result["db_output_fidelity"]["status"] == "OK"
```

## Rollback Plan

If fidelity checks cause issues in production:

1. **Quick disable**: `TAINT_FIDELITY_STRICT=0`
2. **Code rollback**: Revert checkpoints in `core.py` (4 locations)
3. **Full rollback**: Delete `taint/fidelity.py`

The fidelity system is purely additive - it doesn't change any existing logic, only observes and reports.

## Architecture Note: IFDS vs FlowResolver

IFDS (`ifds_analyzer.py`) and FlowResolver (`flow_resolver.py`) are **independent, alternative engines**:

- `mode="backward"` (default): Only IFDS runs
- `mode="forward"`: Only FlowResolver runs
- `mode="complete"`: FlowResolver runs first, then IFDS

They do NOT hand data to each other. Both write to `resolved_flow_audit` table independently. This fidelity system instruments the **common path** (discovery → analysis → dedup → output) that both modes share, NOT cross-engine communication.
