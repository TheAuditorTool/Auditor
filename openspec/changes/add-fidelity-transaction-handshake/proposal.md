# Proposal: Add Transactional Handshake to Data Fidelity Control

## Why

The current fidelity system (`theauditor/indexer/fidelity.py`) is a **Counter**, not a **Verifier**. It only compares row counts between extraction manifests and storage receipts:

```python
# Current: reconcile_fidelity(manifest, receipt, file_path) at fidelity.py:23-90
# manifest = {"symbols": 50, "assignments": 120}  # counts only
# receipt  = {"symbols": 50, "assignments": 120}  # counts only
```

This passes fidelity checks even when:
1. **"Empty Envelope"** - Storage received 100 rows but they're all NULLs
2. **"White Note"** - Extractor sent `['id', 'email', 'role']` columns, Storage only saved `['id']`
3. **"Cross-talk"** - Storage processed a stale batch from a previous run

The ~22MB silent data loss incident (documented in `fidelity.py:13`) was caught by count mismatch, but schema/topology mismatches remain undetected.

## What Changes

### Upgrade Manifest/Receipt to Rich Transaction Tokens

Replace simple `{table: count}` with `{table: {tx_id, columns, count, bytes}}`:

```python
# NEW: Rich manifest from extractor
{
    "symbols": {
        "tx_id": "uuid-abc123",      # Unique batch identity
        "columns": ["name", "type", "line", "col"],  # Schema fingerprint
        "count": 50,                  # Row count (existing)
        "bytes": 12500                # Rough volume check
    }
}
```

### Three New Crash Conditions in `reconcile_fidelity`

1. **Transaction ID Mismatch** - Extractor sent batch `A`, Storage confirmed batch `B`
2. **Schema Violation** - Extractor found columns `[A,B,C]`, Storage only wrote `[A,B]`
3. **Data Collapse** - Row counts match but byte size collapsed (100 rows, 5MB -> 1KB)

### NOT Changing

- Database schema (no migrations)
- Extractor interfaces (contract preserved)
- Storage handler signatures
- Existing count-based verification (enhanced, not replaced)

## Impact

### Affected Specs
- `indexer` capability (fidelity requirements)

### Affected Code

| File | Changes |
|------|---------|
| `theauditor/indexer/fidelity.py` | Upgrade `reconcile_fidelity()` for rich tokens |
| `theauditor/indexer/fidelity_utils.py` | **NEW** - `FidelityToken` helper class |
| `theauditor/indexer/storage/__init__.py` | DataStorer.store() returns rich receipts |
| `theauditor/ast_extractors/python_impl.py` | Generate rich manifests (currently at line 1054) |
| `theauditor/indexer/extractors/javascript.py` | Generate rich manifests (currently at line 768) |

### Anchored to Existing Code

**Current manifest generation** (`javascript.py:758-770`):
```python
manifest["_total"] = total_items
manifest["_timestamp"] = datetime.utcnow().isoformat()
manifest["_file"] = file_info.get("path", "unknown")
result["_extraction_manifest"] = manifest
```

**Current receipt generation** (`storage/__init__.py:113-116`, within `store()` method at lines 68-121):
```python
if isinstance(data, list):
    receipt[data_type] = len(data)
else:
    receipt[data_type] = 1 if data else 0
```

**Current reconciliation** (`fidelity.py:54-63`):
```python
for table in sorted(tables):
    extracted = manifest.get(table, 0)
    stored = receipt.get(table, 0)
    if extracted > 0 and stored == 0:
        errors.append(f"{table}: extracted {extracted} -> stored 0 (100% LOSS)")
```

### Relationship to Active Changes

- **`refactor-extraction-zero-fallback`**: Complementary - removes deduplication fallbacks
- This proposal: Extends fidelity from counts to full transaction handshake

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Manifest format breaks extractors | LOW | MEDIUM | Backward compat: accept int or dict |
| Receipt format breaks fidelity | LOW | MEDIUM | Same backward compat pattern |
| Performance overhead | LOW | LOW | UUID + column list is ~100 bytes |
| Byte size false positives | MEDIUM | LOW | Use as warning, not hard fail |

### Rollback Strategy

```bash
git checkout HEAD -- theauditor/indexer/fidelity.py
git checkout HEAD -- theauditor/indexer/storage/__init__.py
rm theauditor/indexer/fidelity_utils.py  # New file
```
