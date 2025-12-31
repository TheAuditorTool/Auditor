"""Unit tests for taint fidelity module.

Tests the proper manifest/receipt pattern with tx_id tracking,
mirroring indexer/fidelity.py and graph/fidelity.py patterns.
"""

import os

import pytest

from theauditor.taint.fidelity import (
    TaintFidelityError,
    create_analysis_manifest,
    create_db_manifest,
    create_db_receipt,
    create_discovery_manifest,
    reconcile_taint_fidelity,
)


class TestDiscoveryManifest:
    """Tests for create_discovery_manifest()."""

    def test_structure_with_data(self):
        """Manifest includes source/sink counts and stage identifier."""
        sources = [{"file": "a.py", "line": 1, "pattern": "request.args"}]
        sinks = [{"file": "b.py", "line": 2, "pattern": "cursor.execute"}]

        manifest = create_discovery_manifest(sources, sinks)

        assert manifest["_stage"] == "discovery"
        assert manifest["sources_count"] == 1
        assert manifest["sinks_count"] == 1

    def test_empty_lists(self):
        """Manifest handles empty source/sink lists."""
        manifest = create_discovery_manifest([], [])

        assert manifest["_stage"] == "discovery"
        assert manifest["sources_count"] == 0
        assert manifest["sinks_count"] == 0

    def test_multiple_items(self):
        """Manifest counts multiple sources and sinks correctly."""
        sources = [
            {"file": "a.py", "line": 1},
            {"file": "a.py", "line": 5},
            {"file": "b.py", "line": 10},
        ]
        sinks = [{"file": "c.py", "line": 20}]

        manifest = create_discovery_manifest(sources, sinks)

        assert manifest["sources_count"] == 3
        assert manifest["sinks_count"] == 1


class TestAnalysisManifest:
    """Tests for create_analysis_manifest()."""

    def test_structure(self):
        """Manifest includes path counts and analysis stats."""
        vulnerable = [{"source": "a", "sink": "b"}]
        sanitized = [{"source": "c", "sink": "d"}, {"source": "e", "sink": "f"}]

        manifest = create_analysis_manifest(
            vulnerable_paths=vulnerable,
            sanitized_paths=sanitized,
            sinks_analyzed=10,
            sources_checked=5,
        )

        assert manifest["_stage"] == "analysis"
        assert manifest["vulnerable_count"] == 1
        assert manifest["sanitized_count"] == 2
        assert manifest["total_paths"] == 3
        assert manifest["sinks_analyzed"] == 10
        assert manifest["sources_checked"] == 5

    def test_zero_paths(self):
        """Manifest handles zero paths case."""
        manifest = create_analysis_manifest(
            vulnerable_paths=[],
            sanitized_paths=[],
            sinks_analyzed=100,
            sources_checked=50,
        )

        assert manifest["vulnerable_count"] == 0
        assert manifest["sanitized_count"] == 0
        assert manifest["total_paths"] == 0
        assert manifest["sinks_analyzed"] == 100


class TestDbManifest:
    """Tests for create_db_manifest()."""

    def test_structure(self):
        """Manifest includes tx_id, count, and tables."""
        manifest = create_db_manifest(paths_to_write=150)

        assert manifest["_stage"] == "db_output"
        assert manifest["count"] == 150
        assert "tx_id" in manifest
        assert len(manifest["tx_id"]) == 36  # UUID format
        assert "resolved_flow_audit" in manifest["tables"]
        assert "taint_flows" in manifest["tables"]

    def test_tx_id_unique(self):
        """Each manifest gets a unique tx_id."""
        manifest1 = create_db_manifest(paths_to_write=10)
        manifest2 = create_db_manifest(paths_to_write=10)

        assert manifest1["tx_id"] != manifest2["tx_id"]

    def test_zero_paths(self):
        """Manifest handles zero paths."""
        manifest = create_db_manifest(paths_to_write=0)

        assert manifest["count"] == 0
        assert "tx_id" in manifest


class TestDbReceipt:
    """Tests for create_db_receipt()."""

    def test_structure(self):
        """Receipt includes row count and echoed tx_id."""
        tx_id = "test-uuid-1234"
        receipt = create_db_receipt(rows_inserted=150, tx_id=tx_id)

        assert receipt["_stage"] == "db_output"
        assert receipt["count"] == 150
        assert receipt["tx_id"] == tx_id

    def test_zero_rows(self):
        """Receipt handles zero rows."""
        receipt = create_db_receipt(rows_inserted=0, tx_id="abc")

        assert receipt["count"] == 0


class TestReconcileFidelity:
    """Tests for reconcile_taint_fidelity()."""

    def test_ok_result_discovery(self):
        """Returns OK when discovery finds sources and sinks."""
        manifest = create_discovery_manifest(
            sources=[{"file": "a.py", "line": 1}],
            sinks=[{"file": "b.py", "line": 2}],
        )

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={"sinks_to_analyze": 1},
            stage="discovery",
            strict=False,
        )

        assert result["status"] == "OK"
        assert result["stage"] == "discovery"
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0

    def test_warning_zero_sources(self):
        """Warns when discovery finds zero sources."""
        manifest = create_discovery_manifest(sources=[], sinks=[{"file": "b.py"}])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1
        assert "0 sources" in result["warnings"][0]

    def test_error_zero_sinks(self):
        """Errors when discovery finds zero sinks (analysis cannot proceed)."""
        manifest = create_discovery_manifest(sources=[{"file": "a.py"}], sinks=[])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert len(result["errors"]) == 1
        assert "0 sinks" in result["errors"][0]

    def test_error_db_100_percent_loss(self):
        """Error when DB has paths to write but 0 rows inserted."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt=receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert len(result["errors"]) == 1
        assert "100% LOSS" in result["errors"][0]

    def test_warning_db_count_mismatch(self):
        """Warning when DB row count doesn't match manifest."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=95, tx_id=manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt=receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1
        assert "delta=5" in result["warnings"][0]

    def test_error_tx_id_mismatch(self):
        """Error when tx_id doesn't match (cross-talk detection)."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=100, tx_id="different-tx-id-12345678")

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt=receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert len(result["errors"]) == 1
        assert "TRANSACTION MISMATCH" in result["errors"][0]

    def test_ok_db_with_matching_tx_id(self):
        """OK when tx_id and count both match."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=100, tx_id=manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt=receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "OK"
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0

    def test_strict_mode_raises_on_error(self):
        """Raises TaintFidelityError in strict mode on error."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

        with pytest.raises(TaintFidelityError) as exc_info:
            reconcile_taint_fidelity(
                manifest=manifest,
                receipt=receipt,
                stage="db_output",
                strict=True,
            )

        assert "100% LOSS" in str(exc_info.value)
        assert exc_info.value.details["status"] == "FAILED"

    def test_strict_false_no_raise(self):
        """Does not raise in non-strict mode even on error."""
        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt=receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        # No exception raised

    def test_analysis_stalled_pipeline(self):
        """Error when analysis processes 0 sinks but sinks exist."""
        manifest = create_analysis_manifest(
            vulnerable_paths=[],
            sanitized_paths=[],
            sinks_analyzed=0,
            sources_checked=10,
        )

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={"sinks_to_analyze": 50},
            stage="analysis",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert "0/50 sinks" in result["errors"][0]


class TestEnvVarOverride:
    """Tests for TAINT_FIDELITY_STRICT environment variable."""

    def test_env_var_disables_strict(self):
        """TAINT_FIDELITY_STRICT=0 prevents exception even with strict=True."""
        os.environ["TAINT_FIDELITY_STRICT"] = "0"
        try:
            manifest = create_db_manifest(paths_to_write=100)
            receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

            result = reconcile_taint_fidelity(
                manifest=manifest,
                receipt=receipt,
                stage="db_output",
                strict=True,  # Overridden by env var
            )

            assert result["status"] == "FAILED"
            # No exception raised due to env var override
        finally:
            del os.environ["TAINT_FIDELITY_STRICT"]

    def test_env_var_not_set_allows_strict(self):
        """Without env var, strict=True raises on error."""
        os.environ.pop("TAINT_FIDELITY_STRICT", None)

        manifest = create_db_manifest(paths_to_write=100)
        receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

        with pytest.raises(TaintFidelityError):
            reconcile_taint_fidelity(
                manifest=manifest,
                receipt=receipt,
                stage="db_output",
                strict=True,
            )

    def test_env_var_value_1_allows_strict(self):
        """TAINT_FIDELITY_STRICT=1 does not override strict mode."""
        os.environ["TAINT_FIDELITY_STRICT"] = "1"
        try:
            manifest = create_db_manifest(paths_to_write=100)
            receipt = create_db_receipt(rows_inserted=0, tx_id=manifest["tx_id"])

            with pytest.raises(TaintFidelityError):
                reconcile_taint_fidelity(
                    manifest=manifest,
                    receipt=receipt,
                    stage="db_output",
                    strict=True,
                )
        finally:
            del os.environ["TAINT_FIDELITY_STRICT"]


class TestTaintFidelityError:
    """Tests for TaintFidelityError exception class."""

    def test_basic_creation(self):
        """Error can be created with message."""
        error = TaintFidelityError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}

    def test_with_details(self):
        """Error stores details dict."""
        details = {"stage": "db_output", "errors": ["100% LOSS"]}
        error = TaintFidelityError("Test error", details=details)

        assert str(error) == "Test error"
        assert error.details == details
        assert error.details["stage"] == "db_output"

    def test_is_exception(self):
        """TaintFidelityError is a proper exception."""
        assert issubclass(TaintFidelityError, Exception)

        with pytest.raises(TaintFidelityError):
            raise TaintFidelityError("Test")
