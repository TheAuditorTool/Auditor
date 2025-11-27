# Tasks: Add Transactional Fidelity Handshake

**Execution Strategy**: Sequential implementation with backward compatibility at each step.

---

## 0. Verification (Prime Directive)

### 0.1 Verify Current Fidelity Implementation
- [ ] **0.1.1** Read `theauditor/indexer/fidelity.py` completely
  - **HOW**: Read file, confirm `reconcile_fidelity()` signature and logic
  - **EXPECTED**: Function accepts `manifest: dict[str, int], receipt: dict[str, int]`
  - **CURRENT LOCATION**: `fidelity.py:23-90`

- [ ] **0.1.2** Verify manifest generation in JavaScript extractor
  - **HOW**: Read `theauditor/indexer/extractors/javascript.py:758-770`
  - **EXPECTED**: Manifest is `{table_name: count}` with `_total`, `_timestamp`, `_file` metadata

- [ ] **0.1.3** Verify manifest generation in Python extractor
  - **HOW**: Read `theauditor/ast_extractors/python_impl.py:1049-1056`
  - **EXPECTED**: Same pattern as JavaScript extractor

- [ ] **0.1.4** Verify receipt generation in DataStorer
  - **HOW**: Read `theauditor/indexer/storage/__init__.py:100-121`
  - **EXPECTED**: `receipt[data_type] = len(data)` pattern

- [ ] **0.1.5** Verify orchestrator reconciliation call
  - **HOW**: Read `theauditor/indexer/orchestrator.py:819-830`
  - **EXPECTED**: `reconcile_fidelity(manifest=manifest, receipt=receipt, file_path=file_path)`

---

## 1. Phase 1: Create FidelityToken Helper

### 1.1 Create `fidelity_utils.py`
- [ ] **1.1.1** Create new file `theauditor/indexer/fidelity_utils.py`
  - **HOW**: Create file with FidelityToken class
  - **CONTENT**:
    ```python
    """Fidelity utilities for creating transaction tokens.

    Shared between Extractors (Manifests) and Storage (Receipts).
    Enables transactional integrity verification beyond simple counts.
    """
    import uuid
    from typing import Any


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
                # NOTE: O(N) string allocation - acceptable for typical files (<1000 rows)
                # If indexing slows on large files (10k+ LOC), consider threshold guard
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
                manifest[table_name] = FidelityToken.create_manifest(rows)

            extracted_data["_extraction_manifest"] = manifest
            return extracted_data
    ```
  - **WHY**: Centralizes token creation logic for both sides

### 1.2 Add Unit Tests
- [ ] **1.2.1** Create test file `tests/test_fidelity_utils.py`
  - **HOW**: Write tests for FidelityToken methods
  - **TESTS**:
    - `test_create_manifest_empty_list`
    - `test_create_manifest_with_data`
    - `test_create_receipt`
    - `test_attach_manifest_ignores_private_keys`

---

## 2. Phase 2: Upgrade reconcile_fidelity

### 2.1 Modify `fidelity.py`
- [ ] **2.1.0** Add typing import
  - **HOW**: Add `from typing import Any` to imports at top of file
  - **LOCATION**: `fidelity.py:1-5` (import section)
  - **CURRENT IMPORTS**:
    ```python
    import logging
    from .exceptions import DataFidelityError
    ```
  - **AFTER**:
    ```python
    import logging
    from typing import Any
    from .exceptions import DataFidelityError
    ```
  - **WHY**: Required for `dict[str, Any]` type hint

- [ ] **2.1.1** Update type hints to accept rich tokens
  - **HOW**: Change signature from `dict[str, int]` to `dict[str, Any]`
  - **LOCATION**: `fidelity.py:23-25`
  - **NOTE**: Current code has lowercase `any` on line 25 which is a latent bug (should be `Any`). This change fixes both the parameter types AND the return type bug.
  - **BEFORE**:
    ```python
    def reconcile_fidelity(
        manifest: dict[str, int], receipt: dict[str, int], file_path: str, strict: bool = True
    ) -> dict[str, any]:  # BUG: lowercase 'any' is invalid
    ```
  - **AFTER**:
    ```python
    def reconcile_fidelity(
        manifest: dict[str, Any], receipt: dict[str, Any], file_path: str, strict: bool = True
    ) -> dict[str, Any]:
    ```

- [ ] **2.1.2** Add backward compatibility normalization
  - **HOW**: Insert after line 54 (before the for loop)
  - **CODE**:
    ```python
    for table in sorted(tables):
        # Backward compatibility: auto-upgrade legacy int counts to dict format
        m_data = manifest.get(table, {})
        r_data = receipt.get(table, {})

        if isinstance(m_data, int):
            m_data = {"count": m_data, "columns": [], "tx_id": None}
        if isinstance(r_data, int):
            r_data = {"count": r_data, "columns": [], "tx_id": None}

        m_count = m_data.get("count", 0)
        r_count = r_data.get("count", 0)
    ```

- [ ] **2.1.3** Add transaction ID check
  - **HOW**: Insert after existence check
  - **CODE**:
    ```python
        # IDENTITY CHECK: Did Storage process THIS batch?
        m_tx = m_data.get("tx_id")
        r_tx = r_data.get("tx_id")

        if m_tx and r_tx and m_tx != r_tx:
            errors.append(
                f"{table}: TRANSACTION MISMATCH. "
                f"Extractor sent batch '{m_tx[:8]}...', Storage confirmed '{r_tx[:8]}...'. "
                "Possible pipeline cross-talk or stale buffer."
            )
    ```

- [ ] **2.1.4** Add schema/topology check
  - **HOW**: Insert after transaction ID check
  - **CODE**:
    ```python
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
    ```

- [ ] **2.1.5** Add byte size warning (optional)
  - **HOW**: Insert after count check
  - **CODE**:
    ```python
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

### 2.2 Update Tests
- [ ] **2.2.1** Add tests to `tests/test_schema_contract.py`
  - **HOW**: Add to existing `TestDataFidelityInfrastructure` class
  - **LOCATION**: `tests/test_schema_contract.py:219-246`
  - **EXISTING TESTS IN THIS CLASS**:
    - `test_fidelity_module_exists` (line 222)
    - `test_data_fidelity_error_exists` (line 227)
    - `test_reconcile_fidelity_callable` (line 232)
  - **NEW TESTS TO ADD**:
    ```python
    def test_reconcile_legacy_format_still_works(self):
        """Verify backward compat with int-only manifest/receipt."""
        from theauditor.indexer.fidelity import reconcile_fidelity
        result = reconcile_fidelity(
            manifest={'symbols': 10},  # Legacy int format
            receipt={'symbols': 10},
            file_path='test.py',
            strict=False
        )
        assert result['status'] == 'OK'

    def test_reconcile_rich_format_transaction_id_mismatch(self):
        """Verify tx_id mismatch raises error."""
        from theauditor.indexer.fidelity import reconcile_fidelity
        from theauditor.indexer.exceptions import DataFidelityError
        import pytest
        with pytest.raises(DataFidelityError, match="TRANSACTION MISMATCH"):
            reconcile_fidelity(
                manifest={'symbols': {'count': 10, 'tx_id': 'abc', 'columns': ['name']}},
                receipt={'symbols': {'count': 10, 'tx_id': 'xyz', 'columns': ['name']}},
                file_path='test.py',
                strict=True
            )

    def test_reconcile_rich_format_schema_violation(self):
        """Verify dropped columns raises error."""
        from theauditor.indexer.fidelity import reconcile_fidelity
        from theauditor.indexer.exceptions import DataFidelityError
        import pytest
        with pytest.raises(DataFidelityError, match="SCHEMA VIOLATION"):
            reconcile_fidelity(
                manifest={'symbols': {'count': 10, 'tx_id': 'abc', 'columns': ['name', 'type']}},
                receipt={'symbols': {'count': 10, 'tx_id': 'abc', 'columns': ['name']}},
                file_path='test.py',
                strict=True
            )
    ```

---

## 3. Phase 3: Upgrade DataStorer Receipt Generation

### 3.1 Modify `storage/__init__.py`
- [ ] **3.1.1** Import FidelityToken
  - **HOW**: Add import at top of file
  - **CODE**: `from ..fidelity_utils import FidelityToken`
  - **NOTE**: Storage is in subpackage (indexer/storage/), so use `..` to reach parent (indexer/)

- [ ] **3.1.2** Update store() to generate rich receipts with Receipt Integrity
  - **HOW**: Modify receipt generation to reflect *actual storage behavior*, not just input echoing
  - **LOCATION**: `theauditor/indexer/storage/__init__.py:102-121`
  - **CRITICAL**: Receipt must use columns from *what Storage actually wrote*, not `data[0].keys()`.
    See design.md Decision 5 for the "Receipt Integrity Trap" explanation.
  - **CURRENT**:
    ```python
    if isinstance(data, list):
        receipt[data_type] = len(data)
    else:
        receipt[data_type] = 1 if data else 0
    ```
  - **IMPLEMENTATION STRATEGY**:
    1. Ensure internal storage methods (`_insert_batch`, `_upsert`) return the list of columns they used
    2. Pass those *confirmed* columns to `FidelityToken.create_receipt`
    3. **Fallback**: If storage method returns `None` (legacy handler), fall back to `data[0].keys()`
       but log a warning that receipt integrity is "optimistic"
  - **AFTER**:
    ```python
    # Extract tx_id from manifest for receipt echo
    manifest = extracted.get("_extraction_manifest", {})
    table_manifest = manifest.get(data_type, {})
    tx_id = table_manifest.get("tx_id") if isinstance(table_manifest, dict) else None

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        # Dispatch to storage and get confirmed columns
        confirmed_cols = self._dispatch_storage(data_type, data)

        # Receipt Integrity: Use confirmed columns if available, else optimistic fallback
        if confirmed_cols is not None:
            columns = sorted(confirmed_cols)
        else:
            # Legacy handler - log warning and use input columns
            logger.warning(f"Receipt integrity: {data_type} using optimistic columns (handler returned None)")
            columns = sorted(list(data[0].keys()))

        data_bytes = sum(len(str(v)) for row in data for v in row.values())
        receipt[data_type] = FidelityToken.create_receipt(
            count=len(data),
            columns=columns,
            tx_id=tx_id,
            data_bytes=data_bytes
        )
    elif isinstance(data, list):
        # List of non-dict items - use legacy format
        receipt[data_type] = len(data)
    else:
        receipt[data_type] = 1 if data else 0
    ```
  - **PREREQUISITE**: Task 3.1.3 (new) must be completed first to add column returns to storage methods

- [ ] **3.1.3** Update internal storage methods to return confirmed columns
  - **HOW**: Modify `_insert_batch`, `_upsert`, and dispatch methods to return column list
  - **LOCATION**: `theauditor/indexer/storage/__init__.py` (internal methods)
  - **PATTERN**:
    ```python
    def _insert_batch(self, table: str, data: list[dict]) -> list[str] | None:
        """Insert batch and return columns actually used.

        Returns:
            List of column names passed to SQL, or None if legacy handler.
        """
        if not data:
            return None
        columns = list(data[0].keys())  # These are the columns we'll use
        # ... existing insert logic ...
        return columns  # Return what we actually passed to SQL
    ```
  - **WHY**: Enables Receipt Integrity - receipt reflects actual SQL behavior, not input echo
  - **SCOPE**: Only update methods that handle dict data; legacy int-based paths return None

---

## 4. Phase 4: Upgrade Extractors (REQUIRED for Value Delivery)

**CRITICAL**: Without this phase, manifests remain int-only. The infrastructure (Phases 1-3) provides backward compatibility but NO NEW DETECTION CAPABILITY until extractors generate rich manifests.

This phase CAN be implemented as a separate OpenSpec change if desired for smaller PRs, but **value is not delivered until Phase 4 completes**.

### 4.1 JavaScript Extractor
- [ ] **4.1.1** Import FidelityToken
  - **HOW**: Add import at top of file
  - **LOCATION**: `theauditor/indexer/extractors/javascript.py:1-20`
  - **CODE**: `from theauditor.indexer.fidelity_utils import FidelityToken`

- [ ] **4.1.2** Update manifest generation in `javascript.py`
  - **HOW**: Replace count-based manifest with FidelityToken
  - **LOCATION**: `theauditor/indexer/extractors/javascript.py:758-770`
  - **CURRENT**:
    ```python
    for key, value in result.items():
        if key.startswith("_") or not isinstance(value, list):
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
    # Generate rich manifest with transaction tokens
    manifest = {}
    for key, value in result.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        if len(value) > 0:
            manifest[key] = FidelityToken.create_manifest(value)
            total_items += len(value)

    manifest["_total"] = total_items
    manifest["_timestamp"] = datetime.utcnow().isoformat()
    manifest["_file"] = file_info.get("path", "unknown")
    result["_extraction_manifest"] = manifest
    ```

### 4.2 Python Extractor
- [ ] **4.2.1** Import FidelityToken
  - **HOW**: Add import at top of file
  - **LOCATION**: `theauditor/ast_extractors/python_impl.py:1-30`
  - **CODE**: `from theauditor.indexer.fidelity_utils import FidelityToken`

- [ ] **4.2.2** Update manifest generation in `python_impl.py`
  - **HOW**: Replace count-based manifest with FidelityToken
  - **LOCATION**: `theauditor/ast_extractors/python_impl.py:1049-1056`
  - **PATTERN**: Same as JavaScript extractor - replace `manifest[table] = count` with `manifest[table] = FidelityToken.create_manifest(rows)`

---

## 5. Validation

### 5.1 Run Tests
- [ ] **5.1.1** Run unit tests
  - **HOW**: `.venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
  - **EXPECTED**: All tests pass

- [ ] **5.1.2** Run full pipeline
  - **HOW**: `aud full --offline`
  - **EXPECTED**: Completes without fidelity errors

### 5.2 Manual Verification
- [ ] **5.2.1** Verify backward compatibility
  - **HOW**: Ensure old-format manifests still work
  - **TEST**: Create test with `manifest = {"symbols": 50}` (int format)

- [ ] **5.2.2** Verify rich format works
  - **HOW**: Ensure new-format manifests/receipts are generated and checked
  - **TEST**: Add debug logging to verify tokens flow through

---

## 6. Cleanup

### 6.1 Documentation
- [ ] **6.1.1** Update docstring in `fidelity.py`
  - **HOW**: Add description of new verification modes

### 6.2 Archive
- [ ] **6.2.1** Archive change when complete
  - **HOW**: `openspec archive add-fidelity-transaction-handshake --yes`

---

## Appendix: Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `theauditor/indexer/fidelity_utils.py` | 1 | **NEW** - FidelityToken class |
| `theauditor/indexer/fidelity.py` | 2 | Upgrade reconcile_fidelity |
| `theauditor/indexer/storage/__init__.py` | 3 | Rich receipt generation |
| `tests/test_fidelity_utils.py` | 1 | **NEW** - Unit tests |

## Appendix: Test Commands

```bash
# Unit tests
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Full pipeline
aud full --offline

# Validate OpenSpec
openspec validate add-fidelity-transaction-handshake --strict
```
