"""Integration tests for taint fidelity system.

These tests verify the complete fidelity flow across all pipeline stages,
simulating realistic scenarios without requiring full database indexing.
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


class TestFullPipelineFidelity:
    """Tests simulating the complete taint pipeline with fidelity checks."""

    def test_successful_pipeline_all_stages(self):
        """Simulate a successful taint analysis with all fidelity checks passing."""
        # Stage 1: Discovery
        sources = [
            {"file": "api.py", "line": 10, "pattern": "request.args"},
            {"file": "api.py", "line": 25, "pattern": "request.json"},
            {"file": "handlers.py", "line": 5, "pattern": "request.form"},
        ]
        sinks = [
            {"file": "db.py", "line": 50, "pattern": "cursor.execute"},
            {"file": "db.py", "line": 75, "pattern": "db.query"},
        ]

        discovery_manifest = create_discovery_manifest(sources, sinks)
        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={"sinks_to_analyze": len(sinks)},
            stage="discovery",
            strict=False,
        )
        assert discovery_result["status"] == "OK"

        # Stage 2: Analysis
        vulnerable_paths = [
            {"source": sources[0], "sink": sinks[0], "path": []},
            {"source": sources[1], "sink": sinks[0], "path": []},
            {"source": sources[2], "sink": sinks[1], "path": []},
        ]
        sanitized_paths = [
            {"source": sources[0], "sink": sinks[1], "path": [], "sanitizer": "escape"},
        ]

        analysis_manifest = create_analysis_manifest(
            vulnerable_paths=vulnerable_paths,
            sanitized_paths=sanitized_paths,
            sinks_analyzed=len(sinks),
            sources_checked=len(sources),
        )
        analysis_result = reconcile_taint_fidelity(
            manifest=analysis_manifest,
            receipt={"sinks_to_analyze": len(sinks)},
            stage="analysis",
            strict=False,
        )
        assert analysis_result["status"] == "OK"

        # Stage 3: DB Output (with tx_id tracking)
        paths_to_write = len(vulnerable_paths) + len(sanitized_paths)  # 4
        db_manifest = create_db_manifest(paths_to_write=paths_to_write)
        db_receipt = create_db_receipt(
            rows_inserted=paths_to_write,
            tx_id=db_manifest["tx_id"],
        )
        db_result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )
        assert db_result["status"] == "OK"

    def test_pipeline_with_warnings(self):
        """Simulate a pipeline that completes with warnings but no errors."""
        # Discovery with 0 sources (warning)
        discovery_manifest = create_discovery_manifest(
            sources=[],
            sinks=[{"file": "db.py", "line": 50}],
        )
        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )
        assert discovery_result["status"] == "WARNING"
        assert len(discovery_result["warnings"]) == 1

        # DB with count mismatch (warning)
        db_manifest = create_db_manifest(paths_to_write=100)
        db_receipt = create_db_receipt(rows_inserted=95, tx_id=db_manifest["tx_id"])
        db_result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )
        assert db_result["status"] == "WARNING"
        assert "delta=5" in db_result["warnings"][0]

    def test_pipeline_failure_zero_sinks(self):
        """Pipeline should fail hard when no sinks are found."""
        discovery_manifest = create_discovery_manifest(
            sources=[{"file": "a.py", "line": 1}],
            sinks=[],
        )

        result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert "0 sinks" in result["errors"][0]

    def test_pipeline_failure_db_loss(self):
        """Pipeline should fail hard when DB write loses all data."""
        db_manifest = create_db_manifest(paths_to_write=100)
        db_receipt = create_db_receipt(rows_inserted=0, tx_id=db_manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert "100% LOSS" in result["errors"][0]

    def test_pipeline_failure_tx_mismatch(self):
        """Pipeline should fail hard when transaction ID mismatches."""
        db_manifest = create_db_manifest(paths_to_write=100)
        db_receipt = create_db_receipt(
            rows_inserted=100,
            tx_id="wrong-transaction-id-123456",
        )

        result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert "TRANSACTION MISMATCH" in result["errors"][0]


class TestStrictModeIntegration:
    """Tests for strict mode behavior across pipeline."""

    def test_strict_mode_raises_on_first_error(self):
        """In strict mode, first error raises exception immediately."""
        with pytest.raises(TaintFidelityError) as exc_info:
            discovery_manifest = create_discovery_manifest(
                sources=[{"file": "a.py"}],
                sinks=[],
            )
            reconcile_taint_fidelity(
                manifest=discovery_manifest,
                receipt={},
                stage="discovery",
                strict=True,
            )

        assert "0 sinks" in str(exc_info.value)
        assert exc_info.value.details["stage"] == "discovery"

    def test_strict_mode_allows_warnings(self):
        """Strict mode does not raise on warnings, only errors."""
        # 0 sources is a warning, not an error
        discovery_manifest = create_discovery_manifest(
            sources=[],
            sinks=[{"file": "b.py"}],
        )

        result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={},
            stage="discovery",
            strict=True,  # Strict mode ON
        )

        # Should return WARNING, not raise
        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1

    def test_strict_mode_on_db_tx_mismatch(self):
        """Strict mode raises on transaction mismatch."""
        db_manifest = create_db_manifest(paths_to_write=50)
        db_receipt = create_db_receipt(
            rows_inserted=50,
            tx_id="different-tx-12345678",
        )

        with pytest.raises(TaintFidelityError) as exc_info:
            reconcile_taint_fidelity(
                manifest=db_manifest,
                receipt=db_receipt,
                stage="db_output",
                strict=True,
            )

        assert "TRANSACTION MISMATCH" in str(exc_info.value)


class TestEnvVarIntegration:
    """Tests for environment variable override in realistic scenarios."""

    def test_env_var_prevents_pipeline_failure(self):
        """TAINT_FIDELITY_STRICT=0 allows pipeline to continue despite errors."""
        os.environ["TAINT_FIDELITY_STRICT"] = "0"
        try:
            db_manifest = create_db_manifest(paths_to_write=100)
            db_receipt = create_db_receipt(rows_inserted=0, tx_id=db_manifest["tx_id"])

            result = reconcile_taint_fidelity(
                manifest=db_manifest,
                receipt=db_receipt,
                stage="db_output",
                strict=True,  # Would raise, but env var overrides
            )

            # Pipeline continues, error logged but not raised
            assert result["status"] == "FAILED"
        finally:
            del os.environ["TAINT_FIDELITY_STRICT"]


class TestEdgeCases:
    """Edge case tests for fidelity system."""

    def test_zero_paths_is_valid(self):
        """Zero vulnerable/sanitized paths is valid if sinks were analyzed."""
        analysis_manifest = create_analysis_manifest(
            vulnerable_paths=[],
            sanitized_paths=[],
            sinks_analyzed=10,
            sources_checked=5,
        )

        result = reconcile_taint_fidelity(
            manifest=analysis_manifest,
            receipt={"sinks_to_analyze": 10},
            stage="analysis",
            strict=False,
        )

        # This is OK - we analyzed sinks, just found no vulnerabilities
        assert result["status"] == "OK"

    def test_zero_paths_db_write_is_ok(self):
        """Writing zero paths to DB is valid if that's what was expected."""
        db_manifest = create_db_manifest(paths_to_write=0)
        db_receipt = create_db_receipt(rows_inserted=0, tx_id=db_manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "OK"

    def test_large_scale_db_write(self):
        """Verify fidelity works with large path counts."""
        db_manifest = create_db_manifest(paths_to_write=10000)
        db_receipt = create_db_receipt(rows_inserted=10000, tx_id=db_manifest["tx_id"])

        result = reconcile_taint_fidelity(
            manifest=db_manifest,
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "OK"


class TestPublicAPI:
    """Tests to verify public API is correctly exposed."""

    def test_all_functions_importable(self):
        """All public functions can be imported from taint.fidelity."""
        from theauditor.taint.fidelity import (
            TaintFidelityError,
            create_analysis_manifest,
            create_db_manifest,
            create_db_receipt,
            create_discovery_manifest,
            reconcile_taint_fidelity,
        )

        # All functions are callable
        assert callable(create_discovery_manifest)
        assert callable(create_analysis_manifest)
        assert callable(create_db_manifest)
        assert callable(create_db_receipt)
        assert callable(reconcile_taint_fidelity)

        # TaintFidelityError is an exception
        assert issubclass(TaintFidelityError, Exception)
