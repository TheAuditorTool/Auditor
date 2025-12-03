# Tasks: Add Transactional Fidelity Handshake

**Last Verified**: 2025-12-03
**Execution Strategy**: Sequential implementation with backward compatibility at each step.
**All Phases UNBLOCKED**: The `new-architecture-js` ticket is complete.

---

## Infrastructure Context

### Logging
- **Python**: `from theauditor.utils.logging import logger` (Loguru, Pino-compatible NDJSON)
- **Node**: `import { logger } from './utils/logger'` (Pino to stderr)
- **Correlation**: `THEAUDITOR_REQUEST_ID` environment variable
- **Display**: Rich integration via `theauditor/pipeline/ui.py`

### Key File Locations (VERIFIED 2025-12-03)
| Component | File | Lines |
|-----------|------|-------|
| `reconcile_fidelity()` | `theauditor/indexer/fidelity.py` | 10-57 |
| JS manifest generation | `theauditor/indexer/extractors/javascript.py` | 420-439 |
| Python manifest generation | `theauditor/ast_extractors/python_impl.py` | 1004-1024 |
| Receipt generation | `theauditor/indexer/storage/__init__.py` | 117-136 (`process_key`) |
| Orchestrator fidelity call | `theauditor/indexer/orchestrator.py` | 807-811 |
| Node entry point | `theauditor/ast_extractors/javascript/src/main.ts` | 915-921 |
| Node Zod validation | `theauditor/ast_extractors/javascript/src/schema.ts` | 668-674 |

---

## Phase 1: Create FidelityToken Helper

### 1.1 Create `fidelity_utils.py`
- [ ] **1.1.1** Create new file `theauditor/indexer/fidelity_utils.py`
  - **CONTENT**:
    ```python
    """Fidelity utilities for creating transaction tokens.

    Shared between Extractors (Manifests) and Storage (Receipts).
    Enables transactional integrity verification beyond simple counts.
    """
    import uuid
    from typing import Any

    from theauditor.utils.logging import logger


    class FidelityToken:
        """Standardizes fidelity manifest and receipt creation."""

        @staticmethod
        def create_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
            """Generate manifest token from extractor data.

            Args:
                rows: List of dictionaries (the data being extracted).

            Returns:
                Dict with tx_id, columns, count, bytes for fidelity checking.
            """
            if not rows:
                return {
                    "count": 0,
                    "columns": [],
                    "tx_id": None,
                    "bytes": 0
                }

            return {
                "count": len(rows),
                "tx_id": str(uuid.uuid4()),
                "columns": sorted(list(rows[0].keys())) if rows else [],
                "bytes": sum(len(str(v)) for row in rows for v in row.values())
            }

        @staticmethod
        def create_receipt(
            count: int, columns: list[str], tx_id: str | None, data_bytes: int = 0
        ) -> dict[str, Any]:
            """Generate receipt token from storage operation.

            Args:
                count: Number of rows inserted
                columns: Column names actually written
                tx_id: Transaction ID from manifest (echoed back)
                data_bytes: Approximate byte size of data written

            Returns:
                Dict matching manifest structure for comparison.
            """
            return {
                "count": count,
                "columns": sorted(columns),
                "tx_id": tx_id,
                "bytes": data_bytes
            }

        @staticmethod
        def attach_manifest(extracted_data: dict[str, Any]) -> dict[str, Any]:
            """Attach manifest to extraction result (one-liner for extractors).

            Usage: return FidelityToken.attach_manifest(result)
            """
            manifest = {}

            for table_name, rows in extracted_data.items():
                if table_name.startswith("_") or not isinstance(rows, list):
                    continue
                if rows and isinstance(rows[0], dict):
                    manifest[table_name] = FidelityToken.create_manifest(rows)

            extracted_data["_extraction_manifest"] = manifest
            return extracted_data
    ```
  - **WHY**: Centralizes token creation logic for both sides

---

## Phase 2: Upgrade reconcile_fidelity

### 2.1 Modify `fidelity.py`
- [ ] **2.1.1** Update imports
  - **FILE**: `theauditor/indexer/fidelity.py`
  - **LOCATION**: Lines 1-5
  - **BEFORE**:
    ```python
    """Data Fidelity Control System."""

    import logging

    from .exceptions import DataFidelityError

    logger = logging.getLogger(__name__)
    ```
  - **AFTER**:
    ```python
    """Data Fidelity Control System."""

    from typing import Any

    from theauditor.utils.logging import logger

    from .exceptions import DataFidelityError
    ```
  - **WHY**: Use Loguru for unified logging, add `Any` for type hints

- [ ] **2.1.2** Update function signature
  - **LOCATION**: Lines 10-12
  - **BEFORE**:
    ```python
    def reconcile_fidelity(
        manifest: dict[str, int], receipt: dict[str, int], file_path: str, strict: bool = True
    ) -> dict[str, any]:
    ```
  - **AFTER**:
    ```python
    def reconcile_fidelity(
        manifest: dict[str, Any], receipt: dict[str, Any], file_path: str, strict: bool = True
    ) -> dict[str, Any]:
    ```
  - **WHY**: Accept both int (legacy) and dict (rich token) formats

- [ ] **2.1.3** Add backward compatibility and rich token checks
  - **LOCATION**: Replace lines 21-30 (the for loop)
  - **BEFORE**:
    ```python
    for table in sorted(tables):
        extracted = manifest.get(table, 0)
        stored = receipt.get(table, 0)

        if extracted > 0 and stored == 0:
            errors.append(f"{table}: extracted {extracted} -> stored 0 (100% LOSS)")

        elif extracted != stored:
            delta = extracted - stored
            warnings.append(f"{table}: extracted {extracted} -> stored {stored} (delta: {delta})")
    ```
  - **AFTER**:
    ```python
    for table in sorted(tables):
        # Backward compatibility: auto-upgrade legacy int counts to dict format
        m_data = manifest.get(table, {})
        r_data = receipt.get(table, {})

        if isinstance(m_data, int):
            m_data = {"count": m_data, "columns": [], "tx_id": None, "bytes": 0}
        if isinstance(r_data, int):
            r_data = {"count": r_data, "columns": [], "tx_id": None, "bytes": 0}

        m_count = m_data.get("count", 0)
        r_count = r_data.get("count", 0)

        # IDENTITY CHECK: Did Storage process THIS batch?
        m_tx = m_data.get("tx_id")
        r_tx = r_data.get("tx_id")

        if m_tx and r_tx and m_tx != r_tx:
            errors.append(
                f"{table}: TRANSACTION MISMATCH. "
                f"Extractor sent batch '{m_tx[:8]}...', Storage confirmed '{r_tx[:8]}...'. "
                "Possible pipeline cross-talk or stale buffer."
            )

        # TOPOLOGY CHECK: Did Storage preserve all columns?
        m_cols = set(m_data.get("columns", []))
        r_cols = set(r_data.get("columns", []))

        dropped_cols = m_cols - r_cols
        if dropped_cols:
            errors.append(
                f"{table}: SCHEMA VIOLATION. "
                f"Extractor found {sorted(m_cols)}, Storage only saved {sorted(r_cols)}. "
                f"Dropped columns: {dropped_cols}"
            )

        # COUNT CHECK: Row-level data loss (existing logic)
        if m_count > 0 and r_count == 0:
            errors.append(f"{table}: extracted {m_count} -> stored 0 (100% LOSS)")
        elif m_count != r_count:
            delta = m_count - r_count
            warnings.append(f"{table}: extracted {m_count} -> stored {r_count} (delta: {delta})")

        # VOLUME CHECK: Rough data integrity (warning only)
        m_bytes = m_data.get("bytes", 0)
        r_bytes = r_data.get("bytes", 0)

        if m_count == r_count and m_bytes > 1000 and r_bytes > 0 and r_bytes < m_bytes * 0.1:
            warnings.append(
                f"{table}: Data volume collapsed. "
                f"Extractor: {m_bytes} bytes, Storage: {r_bytes} bytes. "
                "Possible NULL data issue."
            )
    ```

---

## Phase 3: Upgrade Storage Receipt Generation

### 3.1 Modify `storage/__init__.py`
- [ ] **3.1.1** Add FidelityToken import
  - **FILE**: `theauditor/indexer/storage/__init__.py`
  - **LOCATION**: After line 13 (after existing imports)
  - **ADD**:
    ```python
    from ..fidelity_utils import FidelityToken
    ```

- [ ] **3.1.2** Update receipt generation in `process_key()`
  - **LOCATION**: Inside `store()` method, the `process_key()` helper function at lines 117-136
  - **BEFORE** (lines 129-132):
    ```python
    if isinstance(data, (list, dict)):
        receipt[data_type] = len(data)
    else:
        receipt[data_type] = 1 if data else 0
    ```
  - **AFTER**:
    ```python
    # Get manifest tx_id for receipt echo
    manifest = extracted.get("_extraction_manifest", {})
    table_manifest = manifest.get(data_type, {})
    tx_id = table_manifest.get("tx_id") if isinstance(table_manifest, dict) else None

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        # Rich receipt for dict-based data
        columns = sorted(data[0].keys())
        data_bytes = sum(len(str(v)) for row in data for v in row.values())
        receipt[data_type] = FidelityToken.create_receipt(
            count=len(data),
            columns=columns,
            tx_id=tx_id,
            data_bytes=data_bytes
        )
    elif isinstance(data, (list, dict)):
        # Legacy format for non-dict lists
        receipt[data_type] = len(data)
    else:
        receipt[data_type] = 1 if data else 0
    ```

---

## Phase 4: Upgrade Extractors

### 4.1 Python Extractor
- [ ] **4.1.1** Import FidelityToken
  - **FILE**: `theauditor/ast_extractors/python_impl.py`
  - **LOCATION**: Add to imports at top of file
  - **ADD**:
    ```python
    from theauditor.indexer.fidelity_utils import FidelityToken
    ```

- [ ] **4.1.2** Update manifest generation
  - **LOCATION**: Lines 1004-1024 (end of `extract_all_python_data()`)
  - **BEFORE** (lines 1004-1024):
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

    from datetime import datetime

    manifest["_total"] = total_items
    manifest["_timestamp"] = datetime.utcnow().isoformat()
    manifest["_file"] = context.file_path if hasattr(context, "file_path") else "unknown"

    result["_extraction_manifest"] = manifest
    ```
  - **AFTER**:
    ```python
    manifest = {}
    total_items = 0

    for key, value in result.items():
        if key.startswith("_"):
            continue
        if not isinstance(value, (list, dict)):
            continue

        if isinstance(value, list) and len(value) > 0:
            if isinstance(value[0], dict):
                manifest[key] = FidelityToken.create_manifest(value)
            else:
                manifest[key] = len(value)  # Legacy for non-dict lists
            total_items += len(value)
        elif isinstance(value, dict):
            manifest[key] = len(value)
            total_items += len(value)

    from datetime import datetime

    manifest["_total"] = total_items
    manifest["_timestamp"] = datetime.utcnow().isoformat()
    manifest["_file"] = context.file_path if hasattr(context, "file_path") else "unknown"

    result["_extraction_manifest"] = manifest
    ```

### 4.2 JavaScript Orchestrator (Interim)
- [ ] **4.2.1** Import FidelityToken
  - **FILE**: `theauditor/indexer/extractors/javascript.py`
  - **LOCATION**: Add to imports at top of file
  - **ADD**:
    ```python
    from theauditor.indexer.fidelity_utils import FidelityToken
    ```

- [ ] **4.2.2** Update manifest generation to detect Node-generated manifests
  - **LOCATION**: Lines 420-439 (inside `_process_extraction_result()`)
  - **BEFORE**:
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
  - **AFTER**:
    ```python
    # Check if Node already generated manifest (new architecture)
    if "_extraction_manifest" in result:
        node_manifest = result["_extraction_manifest"]
        # Validate it's the new rich format (dict of dicts with tx_id)
        first_value = next(iter(node_manifest.values()), None) if node_manifest else None
        if isinstance(first_value, dict) and "tx_id" in first_value:
            # Node generated rich manifest - pass through
            logger.debug("Using Node-generated manifest (new architecture)")
            # Add metadata
            node_manifest["_total"] = sum(
                v.get("count", 0) for v in node_manifest.values()
                if isinstance(v, dict) and not str(v).startswith("_")
            )
            node_manifest["_timestamp"] = datetime.utcnow().isoformat()
            node_manifest["_file"] = file_info.get("path", "unknown")
            return result

    # Build manifest from Node output (legacy or interim)
    logger.debug("Building manifest from Node output (Python-side)")
    manifest = {}
    total_items = 0

    for key, value in result.items():
        if key.startswith("_"):
            continue
        if not isinstance(value, list):
            continue

        if len(value) > 0:
            if isinstance(value[0], dict):
                manifest[key] = FidelityToken.create_manifest(value)
            else:
                manifest[key] = len(value)
            total_items += len(value)

    manifest["_total"] = total_items
    manifest["_timestamp"] = datetime.utcnow().isoformat()
    manifest["_file"] = file_info.get("path", "unknown")

    result["_extraction_manifest"] = manifest
    ```

---

## Phase 5: Node-Side Manifest Generation

**STATUS**: UNBLOCKED. The TypeScript bundle architecture is in place.

### 5.1 Create `src/fidelity.ts`
- [ ] **5.1.1** Create new file `theauditor/ast_extractors/javascript/src/fidelity.ts`
  - **CONTENT**:
    ```typescript
    /**
     * Fidelity utilities for creating transaction tokens.
     *
     * Mirrors Python's FidelityToken class for polyglot parity.
     * Generates manifest INSIDE Node before JSON output.
     */
    import { randomUUID } from 'crypto';
    import { logger } from './utils/logger';

    export interface FidelityManifest {
      tx_id: string;
      columns: string[];
      count: number;
      bytes: number;
    }

    /**
     * Creates a manifest token for a specific table/list of rows.
     */
    export function createManifest(rows: unknown[]): FidelityManifest {
      if (!Array.isArray(rows) || rows.length === 0) {
        return {
          tx_id: '',
          columns: [],
          count: 0,
          bytes: 0
        };
      }

      const firstRow = rows[0] as Record<string, unknown>;
      const columns = typeof firstRow === 'object' && firstRow !== null
        ? Object.keys(firstRow).sort()
        : [];

      return {
        tx_id: randomUUID(),
        columns: columns,
        count: rows.length,
        bytes: JSON.stringify(rows).length
      };
    }

    /**
     * Attaches manifest to extraction results for all files.
     * Call this right before Zod validation.
     */
    export function attachManifest(
      results: Record<string, any>
    ): Record<string, any> {
      for (const [filePath, fileResult] of Object.entries(results)) {
        if (!fileResult.success || !fileResult.extracted_data) {
          continue;
        }

        const manifest: Record<string, FidelityManifest> = {};

        for (const [tableName, rows] of Object.entries(fileResult.extracted_data)) {
          if (tableName.startsWith('_') || !Array.isArray(rows)) {
            continue;
          }

          if (rows.length > 0 && typeof rows[0] === 'object' && rows[0] !== null) {
            manifest[tableName] = createManifest(rows as Record<string, unknown>[]);
          }
        }

        fileResult.extracted_data._extraction_manifest = manifest;
        logger.debug({ file: filePath, tables: Object.keys(manifest).length }, 'Attached fidelity manifest');
      }

      return results;
    }
    ```

### 5.2 Update `src/main.ts`
- [ ] **5.2.1** Add import
  - **FILE**: `theauditor/ast_extractors/javascript/src/main.ts`
  - **LOCATION**: After line 17 (with other imports)
  - **ADD**:
    ```typescript
    import { attachManifest } from './fidelity';
    ```

- [ ] **5.2.2** Call attachManifest before Zod validation
  - **LOCATION**: Lines 915-919 (before `ExtractionReceiptSchema.parse`)
  - **BEFORE**:
    ```typescript
    // Sanitize virtual Vue paths before validation
    const sanitizedResults = sanitizeVirtualPaths(results, virtualToOriginalMap);

    try {
      const validated = ExtractionReceiptSchema.parse(sanitizedResults);
    ```
  - **AFTER**:
    ```typescript
    // Sanitize virtual Vue paths before validation
    const sanitizedResults = sanitizeVirtualPaths(results, virtualToOriginalMap);

    // Attach fidelity manifests (generated INSIDE Node)
    const withManifest = attachManifest(sanitizedResults);

    try {
      const validated = ExtractionReceiptSchema.parse(withManifest);
    ```

### 5.3 Update Zod Schema (REQUIRED)
**WHY REQUIRED**: Zod's default `.object()` uses `.strip()` mode which silently drops unknown keys. Without adding `_extraction_manifest` to `ExtractedDataSchema`, the manifest will be stripped during validation and never reach Python - defeating Phase 5 entirely.

- [ ] **5.3.1** Add manifest schema to `src/schema.ts`
  - **FILE**: `theauditor/ast_extractors/javascript/src/schema.ts`
  - **LOCATION**: After line 665 (before `ExtractedDataSchema`)
  - **ADD**:
    ```typescript
    export const FidelityManifestSchema = z.object({
      tx_id: z.string(),
      columns: z.array(z.string()),
      count: z.number(),
      bytes: z.number(),
    });

    export const ExtractionManifestSchema = z.record(
      z.string(),
      FidelityManifestSchema
    ).optional();
    ```

- [ ] **5.3.2** Add to ExtractedDataSchema
  - **LOCATION**: Inside `ExtractedDataSchema` definition (around line 590-666)
  - **ADD** at the end before closing `})`:
    ```typescript
    _extraction_manifest: ExtractionManifestSchema,
    ```

### 5.4 Build Bundle
- [ ] **5.4.1** Type check
  - **HOW**: `cd theauditor/ast_extractors/javascript && npm run typecheck`
  - **EXPECTED**: No errors

- [ ] **5.4.2** Build bundle
  - **HOW**: `npm run build`
  - **EXPECTED**: `dist/extractor.cjs` updated

---

## Phase 6: Validation

### 6.1 Unit Tests
- [ ] **6.1.1** Run existing tests
  - **HOW**: `.venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
  - **EXPECTED**: All tests pass

### 6.2 Integration Tests
- [ ] **6.2.1** Run full pipeline
  - **HOW**: `aud full --offline`
  - **EXPECTED**: Completes without fidelity errors

- [ ] **6.2.2** Verify Node manifest in logs
  - **HOW**: `THEAUDITOR_LOG_LEVEL=DEBUG aud full --offline 2>&1 | grep -i manifest`
  - **EXPECTED**: "Using Node-generated manifest" or "Attached fidelity manifest"

### 6.3 Manual Verification
- [ ] **6.3.1** Test backward compatibility
  - **HOW**: Temporarily revert Python extractor to int format
  - **EXPECTED**: Fidelity still passes (auto-upgrade works)

- [ ] **6.3.2** Test schema violation detection
  - **HOW**: Temporarily modify storage to drop a column
  - **EXPECTED**: `DataFidelityError` with "SCHEMA VIOLATION"

---

## Appendix: Files Modified

| Phase | File | Change Type |
|-------|------|-------------|
| 1 | `theauditor/indexer/fidelity_utils.py` | NEW |
| 2 | `theauditor/indexer/fidelity.py` | MODIFY |
| 3 | `theauditor/indexer/storage/__init__.py` | MODIFY |
| 4 | `theauditor/ast_extractors/python_impl.py` | MODIFY |
| 4 | `theauditor/indexer/extractors/javascript.py` | MODIFY |
| 5 | `theauditor/ast_extractors/javascript/src/fidelity.ts` | NEW |
| 5 | `theauditor/ast_extractors/javascript/src/main.ts` | MODIFY |
| 5 | `theauditor/ast_extractors/javascript/src/schema.ts` | MODIFY (REQUIRED) |

## Appendix: Test Commands

```bash
# Unit tests
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Type check Node
cd theauditor/ast_extractors/javascript && npm run typecheck

# Build Node bundle
npm run build

# Full pipeline
aud full --offline

# Debug logging
THEAUDITOR_LOG_LEVEL=DEBUG aud full --offline

# Validate OpenSpec
openspec validate add-fidelity-transaction-handshake --strict
```
