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

### Decision 5: Receipt Columns Reflect Actual Storage Behavior (Receipt Integrity)

**What**: Receipt `columns` are derived from the **columns actually passed to SQL builders**, not from raw input `data[0].keys()`.

**Why (The Receipt Integrity Trap)**:
If Storage has a hardcoded SQL bug that drops columns, looking at the *input data* for the receipt will hide the bug:

```
Scenario: Extractor sends {'id': 1, 'email': 'x'}
Buggy Storage: Hardcoded SQL is `INSERT INTO users (id) ...` (drops email)
WRONG Receipt: columns = data[0].keys() -> ['id', 'email']
Result: Manifest says ['id', 'email']. Receipt says ['id', 'email'].
        Fidelity check PASSES, but data was lost!
```

**The Fix**: Receipt must reflect what Storage *executed*, not what it *received*.

**Implementation Pattern**:
```python
# In storage/__init__.py

# WRONG (Optimistic Receipt - hides bugs):
columns = sorted(list(data[0].keys()))  # Just echoing input

# CORRECT (Verified Receipt - catches SQL bugs):
inserted_cols = self._dispatch_storage(table, data)  # Returns actual columns
receipt[table] = FidelityToken.create_receipt(..., columns=inserted_cols, ...)
```

**Two Receipt Modes**:
| Mode | Source | What It Checks |
|------|--------|----------------|
| Optimistic | `data[0].keys()` | Handoff only - did Storage receive the data? |
| Verified | SQL builder output | Persistence - did Storage actually write the data? |

**Example Flow (Verified)**:
```
Extractor produces: [{name: "foo", type: "function", line: 10}]
Manifest columns:   ["line", "name", "type"]  (from extractor output)
Storage receives:   [{name: "foo", type: "function", line: 10}]
SQL builder uses:   ["name", "type", "line"]  (confirmed from _insert_batch)
Receipt columns:    ["line", "name", "type"]  (from SQL builder, sorted)
DB actually writes: [id, file, name, type, line, created_at]  (schema has more)

Comparison: manifest columns == receipt columns (both verified at write)
```

**Fallback for Legacy Handlers**: If internal storage method returns `None` (legacy handler not yet updated), fall back to `data[0].keys()` but log a warning that receipt integrity is "optimistic".

**Implication**: Fidelity now verifies extractor->storage->SQL handoff, catching bugs in all three layers.

---

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

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| UUID generation overhead | Lazy generation - only create if manifest requested |
| Column list memory | Sorted list, typically <20 columns, ~200 bytes |
| False positives on byte collapse | Use as warning only, threshold at 90% collapse |
| Extractor adoption friction | Provide `FidelityToken.attach_manifest()` one-liner |
| Python version compat | Uses `list[str]` (3.9+), `str \| None` (3.10+); project requires 3.9+ |
| Byte calculation perf | O(N) string alloc acceptable for <1000 rows; add threshold guard if needed |

## Migration Plan

**Phase 1: Infrastructure** (this proposal)
1. Add `fidelity_utils.py` with `FidelityToken` class
2. Upgrade `reconcile_fidelity()` for rich tokens
3. Upgrade `DataStorer.store()` to return rich receipts

**Phase 2: Extractor Adoption** (follow-up changes)
1. Update JavaScript extractor manifest generation
2. Update Python extractor manifest generation
3. Update other extractors as needed

**Rollback**: Each phase independently revertable via git checkout.

## Resolved Questions

### Question 1: Should tx_id persist across JSX second pass?

**Decision**: NO - Each pass generates its own tx_id.

**Rationale**:
- JSX pass is a separate extraction cycle with different data (symbols, assignments, etc.)
- Cross-referencing tx_ids between passes adds complexity without value
- Fidelity check runs after EACH pass independently
- Orchestrator flow (`orchestrator.py:819-830`) calls `reconcile_fidelity()` per pass

### Question 2: Should bytes include nested object serialization?

**Decision**: YES - Use `str(v)` which captures nested structure.

**Rationale**:
- `sum(len(str(v)) for row in rows for v in row.values())` serializes all values
- Nested dicts/lists become string representations, contributing to byte count
- Approximation is acceptable - the 90% collapse threshold provides margin for serialization variance
- False positives are warnings, not hard fails (Decision 6)

### Question 3: What is the default strictness mode?

**Decision**: `strict=True` by default in orchestrator.

**Rationale**:
- A fidelity check that only logs warnings to a log file is functionally useless
- The existing `reconcile_fidelity(strict=True)` call in `orchestrator.py:819-830` already uses strict mode
- In strict mode, fidelity violations raise `DataFidelityError`, halting the pipeline
- Non-strict mode (for debugging/migration) only logs warnings without halting
