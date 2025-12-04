"""Comprehensive test suite for the Fidelity Transaction Handshake system.

Tests cover:
1. FidelityToken creation (manifests and receipts)
2. reconcile_fidelity() detection capabilities
3. ZERO FALLBACK enforcement (legacy int rejection)
4. Edge cases and boundary conditions

Each test is designed to PROVE the system protects against specific failure modes.
"""

import pytest
import uuid

from theauditor.indexer.fidelity import reconcile_fidelity
from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.indexer.exceptions import DataFidelityError


# =============================================================================
# SECTION 1: FidelityToken.create_manifest() Tests
# =============================================================================


class TestCreateManifestList:
    """Tests for manifest creation from list data (standard rows)."""

    def test_manifest_from_list_of_dicts_has_all_fields(self):
        """VERIFY: Manifest contains tx_id, columns, count, bytes."""
        rows = [
            {"name": "foo", "type": "function", "line": 10},
            {"name": "bar", "type": "class", "line": 20},
        ]
        manifest = FidelityToken.create_manifest(rows)

        assert manifest is not None
        assert "tx_id" in manifest
        assert "columns" in manifest
        assert "count" in manifest
        assert "bytes" in manifest

    def test_manifest_tx_id_is_valid_uuid(self):
        """VERIFY: tx_id is a valid UUID string (batch identity)."""
        rows = [{"name": "test", "value": 123}]
        manifest = FidelityToken.create_manifest(rows)

        # Should be parseable as UUID
        parsed = uuid.UUID(manifest["tx_id"])
        assert str(parsed) == manifest["tx_id"]

    def test_manifest_columns_are_sorted(self):
        """VERIFY: Columns are sorted for deterministic comparison."""
        rows = [{"zebra": 1, "alpha": 2, "mike": 3}]
        manifest = FidelityToken.create_manifest(rows)

        assert manifest["columns"] == ["alpha", "mike", "zebra"]

    def test_manifest_count_matches_row_count(self):
        """VERIFY: Count reflects actual number of rows."""
        rows = [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}, {"a": 5}]
        manifest = FidelityToken.create_manifest(rows)

        assert manifest["count"] == 5

    def test_manifest_bytes_calculated_from_values(self):
        """VERIFY: Bytes calculated from stringified values."""
        rows = [
            {"name": "hello", "count": 100},  # "hello" = 5, "100" = 3
        ]
        manifest = FidelityToken.create_manifest(rows)

        # sum(len(str(v)) for v in row.values()) = len("hello") + len("100") = 8
        assert manifest["bytes"] == 8

    def test_manifest_empty_list_returns_zero_token(self):
        """VERIFY: Empty list produces count=0, tx_id=None."""
        manifest = FidelityToken.create_manifest([])

        assert manifest["count"] == 0
        assert manifest["columns"] == []
        assert manifest["tx_id"] is None
        assert manifest["bytes"] == 0

    def test_manifest_list_of_non_dicts_returns_count_only(self):
        """VERIFY: List of tuples/primitives gets count but no columns."""
        rows = [(1, 2), (3, 4), (5, 6)]
        manifest = FidelityToken.create_manifest(rows)

        assert manifest["count"] == 3
        assert manifest["columns"] == []
        assert manifest["tx_id"] is None


class TestCreateManifestDict:
    """Tests for manifest creation from dict data (key-value pairs like refs)."""

    def test_manifest_from_dict_has_all_fields(self):
        """VERIFY: Dict data produces valid manifest."""
        data = {"foo": "/path/to/foo", "bar": "/path/to/bar"}
        manifest = FidelityToken.create_manifest(data)

        assert manifest is not None
        assert "tx_id" in manifest
        assert "columns" in manifest
        assert "count" in manifest
        assert "bytes" in manifest

    def test_manifest_dict_count_is_key_count(self):
        """VERIFY: Count reflects number of key-value pairs."""
        data = {"a": "1", "b": "2", "c": "3"}
        manifest = FidelityToken.create_manifest(data)

        assert manifest["count"] == 3

    def test_manifest_dict_columns_empty(self):
        """VERIFY: K/V pairs don't have schema columns."""
        data = {"ref1": "path1", "ref2": "path2"}
        manifest = FidelityToken.create_manifest(data)

        assert manifest["columns"] == []

    def test_manifest_dict_bytes_includes_keys_and_values(self):
        """VERIFY: Bytes = sum(len(k) + len(v))."""
        data = {"ab": "cd"}  # len("ab") + len("cd") = 4
        manifest = FidelityToken.create_manifest(data)

        assert manifest["bytes"] == 4


class TestCreateManifestUnsupported:
    """Tests for unsupported data types."""

    def test_manifest_string_returns_none(self):
        """VERIFY: String input returns None (unsupported)."""
        manifest = FidelityToken.create_manifest("not a list or dict")
        assert manifest is None

    def test_manifest_int_returns_none(self):
        """VERIFY: Integer input returns None (unsupported)."""
        manifest = FidelityToken.create_manifest(42)
        assert manifest is None

    def test_manifest_none_returns_none(self):
        """VERIFY: None input returns None."""
        manifest = FidelityToken.create_manifest(None)
        assert manifest is None


# =============================================================================
# SECTION 2: FidelityToken.create_receipt() Tests
# =============================================================================


class TestCreateReceipt:
    """Tests for receipt creation (Storage side)."""

    def test_receipt_echoes_tx_id(self):
        """VERIFY: Receipt echoes back the manifest's tx_id."""
        tx_id = "abc-123-def-456"
        receipt = FidelityToken.create_receipt(
            count=10, columns=["a", "b"], tx_id=tx_id, data_bytes=500
        )

        assert receipt["tx_id"] == tx_id

    def test_receipt_columns_are_sorted(self):
        """VERIFY: Receipt columns are sorted for comparison."""
        receipt = FidelityToken.create_receipt(
            count=5, columns=["zebra", "alpha", "mike"], tx_id="x", data_bytes=100
        )

        assert receipt["columns"] == ["alpha", "mike", "zebra"]

    def test_receipt_count_preserved(self):
        """VERIFY: Receipt count matches input."""
        receipt = FidelityToken.create_receipt(
            count=42, columns=[], tx_id="x", data_bytes=0
        )

        assert receipt["count"] == 42

    def test_receipt_bytes_preserved(self):
        """VERIFY: Receipt bytes matches input."""
        receipt = FidelityToken.create_receipt(
            count=1, columns=[], tx_id="x", data_bytes=9999
        )

        assert receipt["bytes"] == 9999


# =============================================================================
# SECTION 3: FidelityToken.attach_manifest() Tests
# =============================================================================


class TestAttachManifest:
    """Tests for the attach_manifest helper (extractor integration)."""

    def test_attach_adds_manifest_key(self):
        """VERIFY: attach_manifest adds _extraction_manifest key."""
        data = {
            "symbols": [{"name": "foo", "type": "func"}],
            "imports": [{"module": "os", "alias": None}],
        }
        result = FidelityToken.attach_manifest(data)

        assert "_extraction_manifest" in result
        assert "symbols" in result["_extraction_manifest"]
        assert "imports" in result["_extraction_manifest"]

    def test_attach_skips_private_keys(self):
        """VERIFY: Keys starting with _ are skipped."""
        data = {
            "symbols": [{"name": "foo"}],
            "_internal": [{"secret": "data"}],
        }
        result = FidelityToken.attach_manifest(data)

        assert "symbols" in result["_extraction_manifest"]
        assert "_internal" not in result["_extraction_manifest"]

    def test_attach_handles_dict_values(self):
        """VERIFY: Dict values (like refs) are included."""
        data = {
            "refs": {"foo": "/path/foo", "bar": "/path/bar"},
        }
        result = FidelityToken.attach_manifest(data)

        assert "refs" in result["_extraction_manifest"]
        assert result["_extraction_manifest"]["refs"]["count"] == 2

    def test_attach_includes_total(self):
        """VERIFY: _total is sum of all counts."""
        data = {
            "symbols": [{"a": 1}, {"a": 2}],  # count=2
            "imports": [{"b": 1}],  # count=1
        }
        result = FidelityToken.attach_manifest(data)

        assert result["_extraction_manifest"]["_total"] == 3

    def test_attach_includes_timestamp(self):
        """VERIFY: _timestamp is added."""
        data = {"symbols": [{"a": 1}]}
        result = FidelityToken.attach_manifest(data)

        assert "_timestamp" in result["_extraction_manifest"]


# =============================================================================
# SECTION 4: reconcile_fidelity() - Happy Path Tests
# =============================================================================


class TestReconcileFidelityHappyPath:
    """Tests for successful reconciliation (no errors)."""

    def test_matching_manifest_and_receipt_passes(self):
        """VERIFY: Identical manifest/receipt returns OK."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name", "type"],
                "count": 10,
                "bytes": 500,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name", "type"],
                "count": 10,
                "bytes": 500,
            }
        }

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "OK"
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_extra_columns_in_receipt_allowed(self):
        """VERIFY: Storage adding columns (like id, created_at) is OK."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name", "type"],
                "count": 5,
                "bytes": 100,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["id", "name", "type", "created_at"],  # Extra columns OK
                "count": 5,
                "bytes": 150,
            }
        }

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "OK"
        assert result["errors"] == []

    def test_multiple_tables_all_pass(self):
        """VERIFY: Multiple tables all matching returns OK."""
        tx1 = str(uuid.uuid4())
        tx2 = str(uuid.uuid4())

        manifest = {
            "symbols": {"tx_id": tx1, "columns": ["a"], "count": 5, "bytes": 50},
            "imports": {"tx_id": tx2, "columns": ["b"], "count": 3, "bytes": 30},
        }
        receipt = {
            "symbols": {"tx_id": tx1, "columns": ["a"], "count": 5, "bytes": 50},
            "imports": {"tx_id": tx2, "columns": ["b"], "count": 3, "bytes": 30},
        }

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "OK"


# =============================================================================
# SECTION 5: reconcile_fidelity() - TRANSACTION MISMATCH Detection
# =============================================================================


class TestReconcileTransactionMismatch:
    """Tests for tx_id mismatch detection (cross-talk/stale buffer)."""

    def test_transaction_mismatch_raises_error(self):
        """VERIFY: Different tx_ids raises DataFidelityError."""
        manifest = {
            "symbols": {
                "tx_id": "manifest-batch-aaa",
                "columns": ["name"],
                "count": 10,
                "bytes": 100,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": "receipt-batch-bbb",  # DIFFERENT!
                "columns": ["name"],
                "count": 10,
                "bytes": 100,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "TRANSACTION MISMATCH" in error_msg
        assert "manifest" in error_msg  # truncated tx_id shown
        assert "receipt" in error_msg
        assert "cross-talk" in error_msg.lower() or "stale buffer" in error_msg.lower()

    def test_transaction_mismatch_details_in_exception(self):
        """VERIFY: Exception details contain structured info."""
        manifest = {"tbl": {"tx_id": "aaa", "columns": [], "count": 1, "bytes": 1}}
        receipt = {"tbl": {"tx_id": "bbb", "columns": [], "count": 1, "bytes": 1}}

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert exc_info.value.details["status"] == "FAILED"
        assert len(exc_info.value.details["errors"]) > 0

    def test_missing_tx_id_skips_check(self):
        """VERIFY: If tx_id is None on either side, check is skipped."""
        manifest = {
            "symbols": {
                "tx_id": None,  # Missing tx_id
                "columns": ["name"],
                "count": 5,
                "bytes": 50,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": "some-id",
                "columns": ["name"],
                "count": 5,
                "bytes": 50,
            }
        }

        # Should NOT raise - tx_id check skipped when one side is None
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")
        assert result["status"] == "OK"


# =============================================================================
# SECTION 6: reconcile_fidelity() - SCHEMA VIOLATION Detection
# =============================================================================


class TestReconcileSchemaViolation:
    """Tests for column drop detection (White Note bug)."""

    def test_dropped_column_raises_error(self):
        """VERIFY: Missing column in receipt raises DataFidelityError."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["id", "name", "type", "line"],  # 4 columns
                "count": 10,
                "bytes": 500,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["id", "name"],  # Only 2! Missing 'type' and 'line'
                "count": 10,
                "bytes": 500,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "SCHEMA VIOLATION" in error_msg
        assert "type" in error_msg or "line" in error_msg
        assert "Dropped columns" in error_msg

    def test_single_dropped_column_caught(self):
        """VERIFY: Even one dropped column is caught."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "data": {
                "tx_id": tx_id,
                "columns": ["a", "b", "c"],
                "count": 5,
                "bytes": 100,
            }
        }
        receipt = {
            "data": {
                "tx_id": tx_id,
                "columns": ["a", "b"],  # Missing 'c'
                "count": 5,
                "bytes": 100,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "SCHEMA VIOLATION" in str(exc_info.value)
        assert "'c'" in str(exc_info.value) or "c" in str(exc_info.value)


# =============================================================================
# SECTION 7: reconcile_fidelity() - COUNT LOSS Detection
# =============================================================================


class TestReconcileCountLoss:
    """Tests for row count loss detection."""

    def test_100_percent_loss_raises_error(self):
        """VERIFY: extracted N -> stored 0 raises DataFidelityError."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 156,  # Extracted 156 rows
                "bytes": 1000,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 0,  # Stored 0! Total loss!
                "bytes": 0,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "100% LOSS" in error_msg
        assert "156" in error_msg
        assert "0" in error_msg

    def test_partial_loss_is_warning_not_error(self):
        """VERIFY: Partial loss (N -> M where M < N) is warning only."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 100,
                "bytes": 500,
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 95,  # Lost 5 rows
                "bytes": 475,
            }
        }

        # Should NOT raise - partial loss is warning only
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) > 0
        assert "delta" in result["warnings"][0].lower()


# =============================================================================
# SECTION 8: reconcile_fidelity() - VOLUME COLLAPSE Detection
# =============================================================================


class TestReconcileVolumeCollapse:
    """Tests for byte collapse detection (Empty Envelope bug)."""

    def test_volume_collapse_triggers_warning(self):
        """VERIFY: >90% byte collapse with same count triggers warning."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 100,
                "bytes": 50000,  # 50KB of data
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 100,  # Same count
                "bytes": 500,  # Only 500 bytes! 99% collapse!
            }
        }

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "WARNING"
        assert any("collapsed" in w.lower() for w in result["warnings"])

    def test_small_data_skips_volume_check(self):
        """VERIFY: Data < 1000 bytes skips volume check."""
        tx_id = str(uuid.uuid4())
        manifest = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 5,
                "bytes": 500,  # Small data
            }
        }
        receipt = {
            "symbols": {
                "tx_id": tx_id,
                "columns": ["name"],
                "count": 5,
                "bytes": 10,  # Huge collapse but data too small
            }
        }

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        # Should NOT warn - data too small for volume check
        assert result["status"] == "OK"


# =============================================================================
# SECTION 9: ZERO FALLBACK Enforcement (Legacy Int Rejection)
# =============================================================================


class TestZeroFallbackEnforcement:
    """Tests for ZERO FALLBACK policy - legacy int format rejection."""

    def test_legacy_int_manifest_raises_error(self):
        """VERIFY: Manifest with int value (legacy format) raises error."""
        manifest = {
            "symbols": 150,  # LEGACY INT FORMAT - FORBIDDEN
        }
        receipt = {
            "symbols": {"tx_id": "x", "columns": [], "count": 150, "bytes": 0}
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "LEGACY FORMAT VIOLATION" in error_msg
        assert "manifest" in error_msg.lower()

    def test_legacy_int_receipt_raises_error(self):
        """VERIFY: Receipt with int value (legacy format) raises error."""
        manifest = {
            "symbols": {"tx_id": "x", "columns": [], "count": 150, "bytes": 0}
        }
        receipt = {
            "symbols": 150,  # LEGACY INT FORMAT - FORBIDDEN
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "LEGACY FORMAT VIOLATION" in error_msg
        assert "receipt" in error_msg.lower()

    def test_zero_fallback_details_include_table_and_value(self):
        """VERIFY: Exception details include diagnostic info."""
        manifest = {"bad_table": 42}
        receipt = {"bad_table": {"tx_id": "x", "columns": [], "count": 42, "bytes": 0}}

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert exc_info.value.details["table"] == "bad_table"
        assert exc_info.value.details["value"] == 42
        assert exc_info.value.details["source"] == "manifest"


# =============================================================================
# SECTION 10: Strict vs Non-Strict Mode
# =============================================================================


class TestStrictMode:
    """Tests for strict=True vs strict=False behavior."""

    def test_strict_mode_raises_on_error(self):
        """VERIFY: strict=True raises exception on errors."""
        manifest = {"tbl": {"tx_id": "a", "columns": [], "count": 10, "bytes": 0}}
        receipt = {"tbl": {"tx_id": "b", "columns": [], "count": 10, "bytes": 0}}

        with pytest.raises(DataFidelityError):
            reconcile_fidelity(manifest, receipt, "/test/file.py", strict=True)

    def test_non_strict_mode_returns_result(self):
        """VERIFY: strict=False returns result instead of raising."""
        manifest = {"tbl": {"tx_id": "a", "columns": [], "count": 10, "bytes": 0}}
        receipt = {"tbl": {"tx_id": "b", "columns": [], "count": 10, "bytes": 0}}

        # Should NOT raise
        result = reconcile_fidelity(manifest, receipt, "/test/file.py", strict=False)

        assert result["status"] == "FAILED"
        assert len(result["errors"]) > 0


# =============================================================================
# SECTION 11: Edge Cases and Boundary Conditions
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_manifest_and_receipt(self):
        """VERIFY: Both empty passes OK."""
        result = reconcile_fidelity({}, {}, "/test/file.py")
        assert result["status"] == "OK"

    def test_manifest_only_metadata_keys(self):
        """VERIFY: Only _prefixed keys are ignored."""
        manifest = {"_total": 100, "_timestamp": "2024-01-01"}
        receipt = {"_something": "else"}

        result = reconcile_fidelity(manifest, receipt, "/test/file.py")
        assert result["status"] == "OK"

    def test_table_in_manifest_not_in_receipt(self):
        """VERIFY: Table in manifest but missing from receipt = 100% loss."""
        manifest = {
            "symbols": {"tx_id": "x", "columns": [], "count": 50, "bytes": 100}
        }
        receipt = {}  # No symbols table!

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "100% LOSS" in str(exc_info.value)

    def test_table_in_receipt_not_in_manifest(self):
        """VERIFY: Extra table in receipt triggers warning (negative delta)."""
        manifest = {}
        receipt = {
            "extra": {"tx_id": "x", "columns": [], "count": 10, "bytes": 50}
        }

        # Extra tables in receipt trigger warning (stored more than extracted = negative delta)
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")
        assert result["status"] == "WARNING"
        assert any("delta" in w.lower() for w in result["warnings"])

    def test_unicode_in_data(self):
        """VERIFY: Unicode characters don't break byte calculation."""
        rows = [{"name": "hello world", "value": 42}]
        manifest = FidelityToken.create_manifest(rows)

        assert manifest["bytes"] > 0
        assert isinstance(manifest["bytes"], int)


# =============================================================================
# SECTION 12: Integration - End-to-End Token Flow
# =============================================================================


class TestEndToEndTokenFlow:
    """Tests simulating the full extractor -> storage -> reconcile flow."""

    def test_full_flow_happy_path(self):
        """VERIFY: Complete flow from extraction to reconciliation."""
        # 1. Extractor generates data with manifest
        extracted = {
            "symbols": [
                {"name": "foo", "type": "function", "line": 10},
                {"name": "bar", "type": "class", "line": 20},
            ],
            "imports": [
                {"module": "os", "alias": None},
            ],
        }
        FidelityToken.attach_manifest(extracted)

        manifest = extracted["_extraction_manifest"]

        # 2. Storage processes and generates receipt
        receipt = {}
        for table in ["symbols", "imports"]:
            data = extracted[table]
            table_manifest = manifest.get(table, {})
            receipt[table] = FidelityToken.create_receipt(
                count=len(data),
                columns=sorted(data[0].keys()) if data else [],
                tx_id=table_manifest.get("tx_id"),
                data_bytes=table_manifest.get("bytes", 0),
            )

        # 3. Reconcile
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "OK"

    def test_full_flow_with_data_loss(self):
        """VERIFY: Flow catches simulated data loss."""
        # 1. Extractor generates data
        extracted = {
            "symbols": [
                {"name": "foo", "type": "function"},
                {"name": "bar", "type": "class"},
            ],
        }
        FidelityToken.attach_manifest(extracted)
        manifest = extracted["_extraction_manifest"]

        # 2. Storage "loses" data (simulated bug)
        receipt = {
            "symbols": FidelityToken.create_receipt(
                count=0,  # BUG: Lost all data!
                columns=[],
                tx_id=manifest["symbols"]["tx_id"],
                data_bytes=0,
            )
        }

        # 3. Reconcile catches the loss
        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "100% LOSS" in str(exc_info.value)

    def test_full_flow_with_schema_drift(self):
        """VERIFY: Flow catches simulated schema drift."""
        # 1. Extractor generates data with 3 columns
        extracted = {
            "data": [
                {"id": 1, "name": "foo", "secret": "password123"},
            ],
        }
        FidelityToken.attach_manifest(extracted)
        manifest = extracted["_extraction_manifest"]

        # 2. Storage drops 'secret' column (simulated bug)
        receipt = {
            "data": FidelityToken.create_receipt(
                count=1,
                columns=["id", "name"],  # Missing 'secret'!
                tx_id=manifest["data"]["tx_id"],
                data_bytes=100,
            )
        }

        # 3. Reconcile catches the schema violation
        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "SCHEMA VIOLATION" in str(exc_info.value)
        assert "secret" in str(exc_info.value)
