# Proposal: Add Transactional Handshake to Data Fidelity Control

## Why

The current fidelity system (`theauditor/indexer/fidelity.py`) is a **Counter**, not a **Verifier**. It only compares row counts between extraction manifests and storage receipts:

```python
# Current: reconcile_fidelity(manifest, receipt, file_path) at fidelity.py:10-57
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
| `theauditor/ast_extractors/python_impl.py` | Generate rich manifests (currently at line 1023) |
| `theauditor/indexer/extractors/javascript.py` | Generate rich manifests (currently at line 728) |

### Anchored to Existing Code

**Current manifest generation** (`javascript.py:711-728`):
```python
manifest["_total"] = total_items
manifest["_timestamp"] = datetime.utcnow().isoformat()
manifest["_file"] = file_info.get("path", "unknown")
result["_extraction_manifest"] = manifest
```

**Current receipt generation** (`storage/__init__.py:67-70`, within `store()` method at lines 32-75):
```python
if isinstance(data, list):
    receipt[data_type] = len(data)
else:
    receipt[data_type] = 1 if data else 0
```

**Current reconciliation** (`fidelity.py:21-26`):
```python
for table in sorted(tables):
    extracted = manifest.get(table, 0)
    stored = receipt.get(table, 0)
    if extracted > 0 and stored == 0:
        errors.append(f"{table}: extracted {extracted} -> stored 0 (100% LOSS)")
```

### Relationship to Active Changes

- **`refactor-extraction-zero-fallback`**: Complementary - removes deduplication fallbacks
- **`new-architecture-js`**: REQUIRED DEPENDENCY - Node extractors must generate manifests at source
- This proposal: Extends fidelity from counts to full transaction handshake

---

## POLYGLOT ASSESSMENT - CRITICAL

### The Parity Problem

**Python**: Ironclad. Python extractor (`python_impl.py`) generates manifests directly from extraction output. Fidelity catches any Python-side data loss.

**Node**: WEAK. Node extractors (`ast_extractors/javascript/*.js`) output raw JSON. The Python orchestrator (`javascript.py`) builds manifests AFTER receiving Node output. This means:

```
Node extractor silently drops data → Python sees truncated JSON →
Python builds manifest from truncated data → Fidelity passes →
DATA LOSS UNDETECTED
```

### Current Architecture (Fragile)

```
Node Extractor (10 JS files)
    ↓ raw JSON (no manifest)
Python Orchestrator (javascript.py)
    ↓ builds manifest from whatever arrived
reconcile_fidelity()
    ↓ compares manifest to receipt
    ✓ PASSES (but Node lost data silently)
```

### Required Architecture (Ironclad)

```
Node Extractor (bundled TypeScript)
    ↓ JSON + _extraction_manifest (generated inside Node)
Python Orchestrator (javascript.py)
    ↓ passes through Node's manifest
reconcile_fidelity()
    ↓ compares Node's manifest to receipt
    ✗ FAILS if Node's output doesn't match what Storage received
```

### What This Means for This Ticket

**Phase 1-4**: Python-side only. Infrastructure + Python extractor upgrade.

**Phase 5 (NEW)**: Node-side manifest generation. BLOCKED by `new-architecture-js` ticket which:
1. Converts fragile JS concatenation to TypeScript bundle
2. Adds Zod schema validation inside Node
3. Generates `_extraction_manifest` BEFORE JSON output

**Value Delivery Timeline**:
| Phase | Scope | Value |
|-------|-------|-------|
| 1-3 | Infrastructure | Enables rich tokens (no detection yet) |
| 4 | Python extractor | Python fidelity fully operational |
| 5 | Node extractor | Node fidelity fully operational (REQUIRES new-architecture-js) |

### Blocking Relationship

```
add-fidelity-transaction-handshake (Phase 1-4)
    ↓ can run independently
new-architecture-js
    ↓ must complete first
add-fidelity-transaction-handshake (Phase 5)
    ↓ Node-side manifest generation
FULL PARITY ACHIEVED
```

---

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Manifest format breaks extractors | LOW | MEDIUM | Backward compat: accept int or dict |
| Receipt format breaks fidelity | LOW | MEDIUM | Same backward compat pattern |
| Performance overhead | LOW | LOW | UUID + column list is ~100 bytes |
| Byte size false positives | MEDIUM | LOW | Use as warning, not hard fail |
| **Node fidelity incomplete** | **HIGH** | **HIGH** | **Phase 5 blocked until new-architecture-js completes** |

### Rollback Strategy

```bash
git checkout HEAD -- theauditor/indexer/fidelity.py
git checkout HEAD -- theauditor/indexer/storage/__init__.py
rm theauditor/indexer/fidelity_utils.py  # New file
```
