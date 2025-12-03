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
| `theauditor/ast_extractors/python_impl.py` | Generate rich manifests |
| `theauditor/indexer/extractors/javascript.py` | Pass through Node manifests |
| `theauditor/ast_extractors/javascript/src/fidelity.ts` | **NEW** - Node-side manifest generation |

### Anchored to Existing Code (VERIFIED 2025-12-03)

**Current manifest generation** (`javascript.py:420-439`):
```python
manifest = {}
total_items = 0
for key, value in result.items():
    if key.startswith("_"):
        continue
    if not isinstance(value, (list, dict)):
        continue
    count = len(value)
    if count > 0:
        manifest[key] = count
        total_items += count

manifest["_total"] = total_items
manifest["_timestamp"] = datetime.utcnow().isoformat()
manifest["_file"] = file_info.get("path", "unknown")
result["_extraction_manifest"] = manifest
```

**Current receipt generation** (`storage/__init__.py:129-132`, inside `process_key()` helper):
```python
if isinstance(data, (list, dict)):
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

**Current orchestrator reconciliation call** (`orchestrator.py:807-811`):
```python
if manifest:
    try:
        reconcile_fidelity(
            manifest=manifest, receipt=receipt, file_path=file_path, strict=True
        )
```

---

## POLYGLOT ASSESSMENT - UNBLOCKED

### Architecture Status (VERIFIED 2025-12-03)

**The `new-architecture-js` ticket is COMPLETE.** The Node extraction pipeline has been fully modernized:

| Feature | Old (Feared) | Current (Reality) |
|---------|--------------|-------------------|
| Code location | Python strings (`js_helper_templates.py`) | TypeScript `src/` directory |
| Build system | Runtime JS concatenation | esbuild bundle (`dist/extractor.cjs`) |
| Validation | None | Zod schemas (`src/schema.ts`) |
| Output | stdout JSON (fragile) | File-based I/O (`outputPath`) |
| Logging | `console.log` pollution | Pino to stderr (`src/utils/logger.ts`) |

### Logging Infrastructure

**Python side** (`theauditor/utils/logging.py`):
- Loguru with Pino-compatible NDJSON output
- Rich integration via `swap_to_rich_sink()` for Live displays
- Request ID correlation via `THEAUDITOR_REQUEST_ID`
- `get_subprocess_env()` for passing correlation to Node

**Node side** (`src/utils/logger.ts`):
- Pino writing to stderr (fd 2), preserving stdout for data
- Same `THEAUDITOR_REQUEST_ID` environment variable
- Matched log format for unified viewing

**This means fidelity error messages will render correctly through the Rich pipeline UI.**

### Current Node Architecture (Clean)

```
src/main.ts (entry point)
    ↓ extracts data via TypeScript extractors
    ↓ sanitizes virtual Vue paths
    ↓ validates via Zod (ExtractionReceiptSchema)
    ↓ writes to outputPath file
javascript.py (Python orchestrator)
    ↓ reads output file
    ↓ currently builds manifest FROM Node output
reconcile_fidelity()
    ↓ compares manifest to receipt
```

### Required Architecture (Phase 5)

```
src/main.ts (entry point)
    ↓ extracts data via TypeScript extractors
    ↓ sanitizes virtual Vue paths
    ↓ attachManifest() ← NEW: generates manifest INSIDE Node
    ↓ validates via Zod
    ↓ writes to outputPath file
javascript.py (Python orchestrator)
    ↓ reads output file
    ↓ detects Node-generated manifest, passes through
reconcile_fidelity()
    ↓ compares Node's manifest to receipt
    ↓ CATCHES Node-side data loss
```

### Value Delivery Timeline

| Phase | Scope | Value |
|-------|-------|-------|
| 1-2 | Infrastructure + reconcile_fidelity | Detection logic ready |
| 3 | Storage rich receipts | Receipt side ready |
| 4 | Python extractor + JS orchestrator | **Python fidelity fully operational** |
| 5 | Node-side manifest (`src/fidelity.ts`) | **Full polyglot parity** |

**ALL PHASES ARE NOW UNBLOCKED.**

---

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Manifest format breaks extractors | LOW | MEDIUM | Backward compat: accept int or dict |
| Receipt format breaks fidelity | LOW | MEDIUM | Same backward compat pattern |
| Performance overhead | LOW | LOW | UUID + column list is ~100 bytes |
| Byte size false positives | MEDIUM | LOW | Use as warning, not hard fail |
| Node TypeScript changes break build | LOW | MEDIUM | `npm run typecheck` before build |

### Rollback Strategy

```bash
git checkout HEAD -- theauditor/indexer/fidelity.py
git checkout HEAD -- theauditor/indexer/storage/__init__.py
git checkout HEAD -- theauditor/ast_extractors/javascript/src/
rm theauditor/indexer/fidelity_utils.py  # New file
cd theauditor/ast_extractors/javascript && npm run build  # Rebuild bundle
```
