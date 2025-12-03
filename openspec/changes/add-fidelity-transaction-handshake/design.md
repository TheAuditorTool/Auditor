# Design: Transactional Fidelity Handshake

## Context

The Data Fidelity Control system was introduced after discovering ~22MB of silent data loss when schema columns were invented without verifying extractor outputs. The current system compares counts but cannot detect:

- Schema topology mismatches (columns dropped silently)
- Empty data (rows with NULL values)
- Batch cross-talk (wrong data processed)

**Stakeholders**:
- Extractors (generate manifests)
- DataStorer (generates receipts)
- Orchestrator (calls reconciliation)

**Constraints**:
- Must maintain backward compatibility with existing extractors
- No database schema changes
- Zero performance regression on main path

## Infrastructure Context (VERIFIED 2025-12-03)

### Logging Architecture

**Python** (`theauditor/utils/logging.py`):
- Loguru with Pino-compatible NDJSON output
- `THEAUDITOR_LOG_LEVEL` environment variable (DEBUG|INFO|WARNING|ERROR)
- `THEAUDITOR_REQUEST_ID` for cross-language correlation
- Rich integration via `swap_to_rich_sink()` for Live displays

**Node** (`src/utils/logger.ts`):
- Pino writing to stderr (fd 2)
- stdout reserved for JSON data output
- Same `THEAUDITOR_REQUEST_ID` for correlation

**Pipeline UI** (`theauditor/pipeline/`):
- Rich-based rendering with `RichRenderer`
- Phase/task status tracking
- Console utilities (`print_error`, `print_warning`, `print_success`)

**Implication**: Fidelity errors will render correctly through the Rich pipeline UI, and logs can be correlated across Python/Node boundaries.

### Storage Architecture

**Handler-based design** (`storage/__init__.py`):
```python
class DataStorer:
    def __init__(self, db_manager, counts):
        self.core = CoreStorage(db_manager, counts)
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        # ... more domain handlers

        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            # ...
        }

    def store(self, file_path, extracted, jsx_pass=False):
        # PRIORITY_ORDER ensures parents before children
        for priority_key in PRIORITY_ORDER:
            if priority_key in extracted:
                process_key(priority_key, extracted[priority_key])
        # Then remaining keys
        for data_type, data in extracted.items():
            if data_type not in priority_set:
                process_key(data_type, data)
        return receipt
```

**Implication**: Receipt generation happens in `process_key()` helper at line 117-136, not directly in `store()`.

### Node Extraction Architecture

**TypeScript bundle** (`ast_extractors/javascript/`):
- Source in `src/` directory (TypeScript)
- Built via esbuild to `dist/extractor.cjs`
- Zod validation in `src/schema.ts` before output
- File-based I/O (not fragile stdout)

**Entry point** (`src/main.ts:918-929`):
```typescript
const sanitizedResults = sanitizeVirtualPaths(results, virtualToOriginalMap);
try {
  const validated = ExtractionReceiptSchema.parse(sanitizedResults);
  fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");
} catch (e) {
  if (e instanceof z.ZodError) {
    console.error("[BATCH ERROR] Zod validation failed");
    process.exit(1);
  }
}
```

**Implication**: Adding fidelity is inserting `attachManifest()` call before Zod validation.

---

## Goals / Non-Goals

**Goals:**
- Detect schema violations ("White Note" bug) where columns are silently dropped
- Detect transaction cross-talk where wrong batch is processed
- Provide rough integrity checks via byte size comparison
- Maintain backward compatibility with simple `{table: count}` manifests

**Non-Goals:**
- Cryptographic integrity (no checksums/hashes of actual data)
- Full data content verification (too expensive)
- Real-time streaming verification (batch-oriented design)

## Decisions

### Decision 1: Transaction Token Structure

**What**: Rich token containing identity, topology, and volume:

```python
{
    "tx_id": str,        # UUID for batch identity
    "columns": List[str], # Sorted column names (schema fingerprint)
    "count": int,         # Row count (existing)
    "bytes": int          # Approximate data volume
}
```

**Why**:
- `tx_id`: Proves Storage processed THIS specific batch, not a stale one
- `columns`: Detects schema drift without full data comparison
- `bytes`: Rough sanity check for data collapse (NULLs)

**Alternatives Considered**:
- **Hash of first row**: Rejected - too expensive, adds ~50ms per file
- **Full data checksum**: Rejected - O(n) memory, defeats batch streaming
- **Column count only**: Rejected - doesn't catch column name changes

### Decision 2: Backward Compatibility via Type Detection

**What**: `reconcile_fidelity` accepts both legacy `int` and new `dict` formats:

```python
# fidelity.py - inside reconcile_fidelity()
m_data = manifest.get(table, {})
r_data = receipt.get(table, {})

# Auto-upgrade legacy format
if isinstance(m_data, int):
    m_data = {"count": m_data, "columns": [], "tx_id": None}
if isinstance(r_data, int):
    r_data = {"count": r_data, "columns": [], "tx_id": None}
```

**Why**: Allows incremental rollout - extractors can be upgraded one at a time.

**Alternatives Considered**:
- **Version flag in manifest**: Rejected - adds complexity, auto-detect simpler
- **Require all extractors upgraded first**: Rejected - too risky for big-bang release

### Decision 3: Column Comparison Uses Set Subtraction

**What**: Only flag columns that Extractor found but Storage dropped:

```python
dropped_cols = set(manifest_cols) - set(receipt_cols)
if dropped_cols:
    errors.append(f"Schema Violation: Dropped columns {dropped_cols}")
```

**Why**: Storage may add columns (like `id`, `created_at`). We only care about data loss, not data augmentation.

**Alternatives Considered**:
- **Exact column match**: Rejected - would false-positive on auto-generated columns
- **Bidirectional diff**: Rejected - extra columns in Storage are not a bug

### Decision 4: FidelityToken Helper Class Location

**What**: New file `theauditor/indexer/fidelity_utils.py`

**Why**:
- Shared by Extractors (manifest) and Storage (receipt)
- Keeps `fidelity.py` focused on reconciliation logic
- Follows existing pattern: `exceptions.py` is separate from `fidelity.py`

**Alternatives Considered**:
- **Inside fidelity.py**: Rejected - creates circular import risk with extractors
- **Inside extractors base**: Rejected - Storage also needs it

### Decision 5: Receipt Columns Reflect Actual Storage Behavior

**What**: Receipt `columns` are derived from the **columns actually passed to handlers**, which forward dict keys to `db_manager.add_*` methods.

**Why (The Receipt Integrity Trap)**:
If Storage has a hardcoded SQL bug that drops columns, looking at the *input data* for the receipt will hide the bug.

**Implementation** (`storage/__init__.py:117-136`, `process_key()` helper):
```python
def process_key(data_type: str, data: Any) -> None:
    if data_type.startswith("_"):
        return
    if jsx_pass and data_type not in jsx_only_types:
        return

    handler = self.handlers.get(data_type)
    if handler:
        handler(file_path, data, jsx_pass)
        # Current: count only
        if isinstance(data, (list, dict)):
            receipt[data_type] = len(data)
        else:
            receipt[data_type] = 1 if data else 0
```

**Note**: The current handler architecture forwards dict keys directly to `db_manager`. Therefore `data[0].keys()` reflects what gets written.

### Decision 6: Byte Size as Warning, Not Hard Fail

**What**: Significant byte size collapse triggers WARNING, not ERROR:

```python
if m_count == r_count and m_bytes > 1000 and r_bytes < m_bytes * 0.1:
    warnings.append(f"{table}: Data collapse - {m_bytes} bytes -> {r_bytes} bytes")
```

**Why**:
- Byte calculation is approximate (string representation)
- False positives possible with different serialization
- Still valuable as diagnostic signal

**Alternatives Considered**:
- **Hard fail on collapse**: Rejected - too many false positives initially
- **Skip byte check entirely**: Rejected - loses "Empty Envelope" detection

### Decision 7: Node-Side Manifest Generation (UNBLOCKED)

**What**: Node extractors generate `_extraction_manifest` inside the TypeScript bundle.

**Status**: UNBLOCKED. The `new-architecture-js` ticket is COMPLETE.

**Evidence**:
- `dist/extractor.cjs` exists (built bundle)
- `src/main.ts` has clean entry point with Zod validation
- `src/utils/logger.ts` uses Pino for proper log separation
- File-based I/O (not fragile stdout parsing)

**Implementation Location** (`src/main.ts:916-929`):
```typescript
// Current flow:
const sanitizedResults = sanitizeVirtualPaths(results, virtualToOriginalMap);
const validated = ExtractionReceiptSchema.parse(sanitizedResults);
fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");

// New flow (Phase 5):
const sanitizedResults = sanitizeVirtualPaths(results, virtualToOriginalMap);
const withManifest = attachManifest(sanitizedResults);  // NEW
const validated = ExtractionReceiptSchema.parse(withManifest);
fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");
```

**Format Requirement**: Node's manifest MUST match Python's format exactly:
```typescript
interface FidelityManifest {
  tx_id: string;
  columns: string[];
  count: number;
  bytes: number;
}
```

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| UUID generation overhead | Lazy generation - only create if manifest requested |
| Column list memory | Sorted list, typically <20 columns, ~200 bytes |
| False positives on byte collapse | Use as warning only, threshold at 90% collapse |
| Extractor adoption friction | Provide `FidelityToken.attach_manifest()` one-liner |
| Node TypeScript changes break build | Run `npm run typecheck` before `npm run build` |
| Byte calculation perf | O(N) string alloc acceptable for <1000 rows |

## Migration Plan

**Phase 1: Infrastructure**
1. Add `fidelity_utils.py` with `FidelityToken` class

**Phase 2: Reconciliation Logic**
1. Upgrade `reconcile_fidelity()` for rich tokens
2. Add tx_id, columns, bytes verification

**Phase 3: Storage Receipts**
1. Upgrade `DataStorer.store()` to return rich receipts
2. Modify `process_key()` helper

**Phase 4: Python Extractor**
1. Update `python_impl.py` manifest generation
2. Update `javascript.py` orchestrator (interim Python-side manifest)

**Phase 5: Node-Side Manifest** (UNBLOCKED)
1. Create `src/fidelity.ts` with TypeScript `attachManifest()`
2. Update `src/main.ts` to call `attachManifest()` before Zod validation
3. Update `javascript.py` to detect and pass through Node manifest
4. Run `npm run build`

**Rollback**: Each phase independently revertable via git checkout.

## Resolved Questions

### Question 1: Should tx_id persist across JSX second pass?

**Decision**: NO - Each pass generates its own tx_id.

**Rationale**:
- JSX pass is a separate extraction cycle with different data
- Cross-referencing tx_ids between passes adds complexity without value
- Fidelity check runs after EACH pass independently
- Orchestrator flow (`orchestrator.py:807-811`) calls `reconcile_fidelity()` per pass

### Question 2: Should bytes include nested object serialization?

**Decision**: YES - Use `str(v)` which captures nested structure.

**Rationale**:
- `sum(len(str(v)) for row in rows for v in row.values())` serializes all values
- Nested dicts/lists become string representations
- Approximation is acceptable - 90% collapse threshold provides margin
- False positives are warnings, not hard fails (Decision 6)

### Question 3: What is the default strictness mode?

**Decision**: `strict=True` by default in orchestrator.

**Rationale**:
- Fidelity check that only logs warnings is functionally useless
- Existing `reconcile_fidelity(strict=True)` at `orchestrator.py:809` uses strict mode
- In strict mode, violations raise `DataFidelityError`, halting pipeline
- Non-strict mode (for debugging) only logs warnings

### Question 4: How do fidelity errors render in CLI?

**Decision**: Use existing `DataFidelityError` exception with Rich formatting.

**Rationale**:
- `theauditor/pipeline/ui.py` provides `print_error()` for styled errors
- Loguru logs will appear correctly via `swap_to_rich_sink()` integration
- Exception message includes full reconciliation report via `details` attribute
