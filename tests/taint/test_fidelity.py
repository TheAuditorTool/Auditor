"""Unit tests for taint fidelity module."""

import os

import pytest

from theauditor.taint.fidelity import (
    TaintFidelityError,
    create_analysis_manifest,
    create_db_output_receipt,
    create_dedup_manifest,
    create_discovery_manifest,
    create_json_output_receipt,
    reconcile_taint_fidelity,
)


class TestDiscoveryManifest:
    """Tests for create_discovery_manifest()."""

    def test_structure_with_data(self):
        """Manifest includes source/sink tokens and stage identifier."""
        sources = [{"file": "a.py", "line": 1, "pattern": "request.args"}]
        sinks = [{"file": "b.py", "line": 2, "pattern": "cursor.execute"}]

        manifest = create_discovery_manifest(sources, sinks)

        assert manifest["_stage"] == "discovery"
        assert "sources" in manifest
        assert "sinks" in manifest
        assert manifest["sources"]["count"] == 1
        assert manifest["sinks"]["count"] == 1

    def test_empty_lists(self):
        """Manifest handles empty source/sink lists."""
        manifest = create_discovery_manifest([], [])

        assert manifest["_stage"] == "discovery"
        assert manifest["sources"]["count"] == 0
        assert manifest["sinks"]["count"] == 0

    def test_multiple_items(self):
        """Manifest counts multiple sources and sinks correctly."""
        sources = [
            {"file": "a.py", "line": 1},
            {"file": "a.py", "line": 5},
            {"file": "b.py", "line": 10},
        ]
        sinks = [{"file": "c.py", "line": 20}]

        manifest = create_discovery_manifest(sources, sinks)

        assert manifest["sources"]["count"] == 3
        assert manifest["sinks"]["count"] == 1


class TestAnalysisManifest:
    """Tests for create_analysis_manifest()."""

    def test_structure(self):
        """Manifest includes path tokens and analysis stats."""
        vulnerable = [{"source": "a", "sink": "b"}]
        sanitized = [{"source": "c", "sink": "d"}, {"source": "e", "sink": "f"}]

        manifest = create_analysis_manifest(
            vulnerable_paths=vulnerable,
            sanitized_paths=sanitized,
            sinks_analyzed=10,
            sources_checked=5,
        )

        assert manifest["_stage"] == "analysis"
        assert manifest["vulnerable_paths"]["count"] == 1
        assert manifest["sanitized_paths"]["count"] == 2
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

        assert manifest["vulnerable_paths"]["count"] == 0
        assert manifest["sanitized_paths"]["count"] == 0
        assert manifest["sinks_analyzed"] == 100


class TestDedupManifest:
    """Tests for create_dedup_manifest()."""

    def test_ratio_calculation(self):
        """Removal ratio is calculated correctly."""
        manifest = create_dedup_manifest(pre_dedup_count=100, post_dedup_count=40)

        assert manifest["_stage"] == "dedup"
        assert manifest["pre_dedup_count"] == 100
        assert manifest["post_dedup_count"] == 40
        assert manifest["removed_count"] == 60
        assert manifest["removal_ratio"] == 0.6

    def test_no_removal(self):
        """Zero removal ratio when no duplicates."""
        manifest = create_dedup_manifest(pre_dedup_count=50, post_dedup_count=50)

        assert manifest["removed_count"] == 0
        assert manifest["removal_ratio"] == 0.0

    def test_zero_input(self):
        """Handles zero pre-dedup count without division error."""
        manifest = create_dedup_manifest(pre_dedup_count=0, post_dedup_count=0)

        assert manifest["removed_count"] == 0
        assert manifest["removal_ratio"] == 0.0  # max(0, 1) = 1, so 0/1 = 0

    def test_complete_dedup(self):
        """100% removal ratio when all paths are duplicates."""
        manifest = create_dedup_manifest(pre_dedup_count=100, post_dedup_count=0)

        assert manifest["removed_count"] == 100
        assert manifest["removal_ratio"] == 1.0


class TestDbOutputReceipt:
    """Tests for create_db_output_receipt()."""

    def test_structure(self):
        """Receipt includes row count and path breakdowns."""
        receipt = create_db_output_receipt(
            db_rows_inserted=150,
            vulnerable_count=100,
            sanitized_count=50,
        )

        assert receipt["_stage"] == "db_output"
        assert receipt["db_rows"] == 150
        assert receipt["vulnerable_count"] == 100
        assert receipt["sanitized_count"] == 50

    def test_zero_rows(self):
        """Receipt handles zero rows."""
        receipt = create_db_output_receipt(
            db_rows_inserted=0,
            vulnerable_count=0,
            sanitized_count=0,
        )

        assert receipt["db_rows"] == 0


class TestJsonOutputReceipt:
    """Tests for create_json_output_receipt()."""

    def test_structure(self):
        """Receipt includes vulnerability count and byte size."""
        receipt = create_json_output_receipt(
            json_vulnerabilities=25,
            json_bytes_written=12500,
        )

        assert receipt["_stage"] == "json_output"
        assert receipt["json_count"] == 25
        assert receipt["json_bytes"] == 12500

    def test_zero_output(self):
        """Receipt handles zero vulnerabilities."""
        receipt = create_json_output_receipt(
            json_vulnerabilities=0,
            json_bytes_written=50,  # Empty JSON still has some bytes
        )

        assert receipt["json_count"] == 0
        assert receipt["json_bytes"] == 50


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

    def test_warning_zero_sinks(self):
        """Warns when discovery finds zero sinks."""
        manifest = create_discovery_manifest(sources=[{"file": "a.py"}], sinks=[])

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1
        assert "0 sinks" in result["warnings"][0]

    def test_warning_high_dedup_ratio(self):
        """Warns when dedup removes more than 50% of paths."""
        manifest = create_dedup_manifest(pre_dedup_count=100, post_dedup_count=40)

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={},
            stage="dedup",
            strict=False,
        )

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1
        assert "60%" in result["warnings"][0]

    def test_ok_dedup_under_threshold(self):
        """No warning when dedup removes less than 50%."""
        manifest = create_dedup_manifest(pre_dedup_count=100, post_dedup_count=60)

        result = reconcile_taint_fidelity(
            manifest=manifest,
            receipt={},
            stage="dedup",
            strict=False,
        )

        assert result["status"] == "OK"
        assert len(result["warnings"]) == 0

    def test_error_db_100_percent_loss(self):
        """Error when DB has paths to write but 0 rows inserted."""
        result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 100},
            receipt={"db_rows": 0},
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert len(result["errors"]) == 1
        assert "100% LOSS" in result["errors"][0]

    def test_warning_db_count_mismatch(self):
        """Warning when DB row count doesn't match manifest."""
        result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 100},
            receipt={"db_rows": 95},
            stage="db_output",
            strict=False,
        )

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1
        assert "delta=5" in result["warnings"][0]

    def test_error_json_100_percent_loss(self):
        """Error when JSON has paths to write but 0 in output."""
        result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 50},
            receipt={"json_count": 0},
            stage="json_output",
            strict=False,
        )

        assert result["status"] == "FAILED"
        assert len(result["errors"]) == 1
        assert "100% LOSS" in result["errors"][0]

    def test_strict_mode_raises_on_error(self):
        """Raises TaintFidelityError in strict mode on error."""
        with pytest.raises(TaintFidelityError) as exc_info:
            reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,
            )

        assert "100% LOSS" in str(exc_info.value)
        assert exc_info.value.details["status"] == "FAILED"

    def test_strict_false_no_raise(self):
        """Does not raise in non-strict mode even on error."""
        result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 100},
            receipt={"db_rows": 0},
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
            # This would normally raise with strict=True
            result = reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,  # Overridden by env var
            )

            assert result["status"] == "FAILED"
            # No exception raised due to env var override
        finally:
            del os.environ["TAINT_FIDELITY_STRICT"]

    def test_env_var_not_set_allows_strict(self):
        """Without env var, strict=True raises on error."""
        # Ensure env var is not set
        os.environ.pop("TAINT_FIDELITY_STRICT", None)

        with pytest.raises(TaintFidelityError):
            reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,
            )

    def test_env_var_value_1_allows_strict(self):
        """TAINT_FIDELITY_STRICT=1 does not override strict mode."""
        os.environ["TAINT_FIDELITY_STRICT"] = "1"
        try:
            with pytest.raises(TaintFidelityError):
                reconcile_taint_fidelity(
                    manifest={"paths_to_write": 100},
                    receipt={"db_rows": 0},
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
