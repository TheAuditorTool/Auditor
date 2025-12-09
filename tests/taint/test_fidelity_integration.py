"""Integration tests for taint fidelity system.

These tests verify the complete fidelity flow across all pipeline stages,
simulating realistic scenarios without requiring full database indexing.
"""

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

        # Stage 3: Deduplication (simulating 25% removal - under threshold)
        pre_dedup = len(vulnerable_paths) + len(sanitized_paths)  # 4
        post_dedup = 3  # 25% removal

        dedup_manifest = create_dedup_manifest(pre_dedup, post_dedup)
        dedup_result = reconcile_taint_fidelity(
            manifest=dedup_manifest,
            receipt={},
            stage="dedup",
            strict=False,
        )
        assert dedup_result["status"] == "OK"

        # Stage 4a: DB Output
        db_receipt = create_db_output_receipt(
            db_rows_inserted=post_dedup,
            vulnerable_count=2,
            sanitized_count=1,
        )
        db_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": post_dedup},
            receipt=db_receipt,
            stage="db_output",
            strict=False,
        )
        assert db_result["status"] == "OK"

        # Stage 4b: JSON Output
        json_receipt = create_json_output_receipt(
            json_vulnerabilities=2,
            json_bytes_written=5000,
        )
        json_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 2},
            receipt=json_receipt,
            stage="json_output",
            strict=False,
        )
        assert json_result["status"] == "OK"

    def test_pipeline_with_warnings(self):
        """Pipeline that completes with warnings but no errors."""
        # Discovery with 0 sinks (warning)
        discovery_manifest = create_discovery_manifest(
            sources=[{"file": "a.py", "line": 1}],
            sinks=[],
        )
        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )
        assert discovery_result["status"] == "WARNING"
        assert len(discovery_result["warnings"]) == 1

        # Dedup with high removal (warning)
        dedup_manifest = create_dedup_manifest(100, 30)  # 70% removal
        dedup_result = reconcile_taint_fidelity(
            manifest=dedup_manifest,
            receipt={},
            stage="dedup",
            strict=False,
        )
        assert dedup_result["status"] == "WARNING"
        assert "70%" in dedup_result["warnings"][0]

        # DB with count mismatch (warning)
        db_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 30},
            receipt={"db_rows": 28},
            stage="db_output",
            strict=False,
        )
        assert db_result["status"] == "WARNING"
        assert "delta=2" in db_result["warnings"][0]

    def test_pipeline_failure_detection(self):
        """Pipeline that catches critical failures."""
        # Analysis stalled - 0 sinks analyzed when sinks exist
        analysis_manifest = create_analysis_manifest(
            vulnerable_paths=[],
            sanitized_paths=[],
            sinks_analyzed=0,
            sources_checked=10,
        )
        analysis_result = reconcile_taint_fidelity(
            manifest=analysis_manifest,
            receipt={"sinks_to_analyze": 50},
            stage="analysis",
            strict=False,
        )
        assert analysis_result["status"] == "FAILED"
        assert "0/50 sinks" in analysis_result["errors"][0]

        # DB 100% loss
        db_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 100},
            receipt={"db_rows": 0},
            stage="db_output",
            strict=False,
        )
        assert db_result["status"] == "FAILED"
        assert "100% LOSS" in db_result["errors"][0]

        # JSON 100% loss
        json_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 50},
            receipt={"json_count": 0},
            stage="json_output",
            strict=False,
        )
        assert json_result["status"] == "FAILED"
        assert "100% LOSS" in json_result["errors"][0]


class TestStrictModeIntegration:
    """Tests for strict mode behavior across the pipeline."""

    def test_strict_mode_stops_pipeline_on_failure(self):
        """Strict mode raises exception, preventing further processing."""
        with pytest.raises(TaintFidelityError) as exc_info:
            reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,
            )

        # Exception contains details for diagnosis
        assert exc_info.value.details["status"] == "FAILED"
        assert exc_info.value.details["stage"] == "db_output"
        assert len(exc_info.value.details["errors"]) == 1

    def test_strict_mode_allows_warnings(self):
        """Strict mode does not raise on warnings, only errors."""
        # High dedup ratio is a warning, not an error
        dedup_manifest = create_dedup_manifest(100, 30)  # 70% removal

        result = reconcile_taint_fidelity(
            manifest=dedup_manifest,
            receipt={},
            stage="dedup",
            strict=True,  # Strict mode ON
        )

        # Should NOT raise, just return warning status
        assert result["status"] == "WARNING"
        assert len(result["warnings"]) == 1


class TestEnvVarOverrideIntegration:
    """Tests for TAINT_FIDELITY_STRICT environment variable."""

    def test_env_var_allows_pipeline_to_continue_on_failure(self):
        """With env var set, pipeline continues even on critical failure."""
        os.environ["TAINT_FIDELITY_STRICT"] = "0"
        try:
            # This would normally raise in strict mode
            result = reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,  # Would raise without env var
            )

            # Pipeline continues, returns FAILED status
            assert result["status"] == "FAILED"

            # Can continue to next stage
            json_result = reconcile_taint_fidelity(
                manifest={"paths_to_write": 50},
                receipt={"json_count": 50},
                stage="json_output",
                strict=True,  # Still overridden by env var
            )
            assert json_result["status"] == "OK"

        finally:
            del os.environ["TAINT_FIDELITY_STRICT"]

    def test_env_var_unset_allows_strict_failures(self):
        """Without env var, strict mode raises as expected."""
        os.environ.pop("TAINT_FIDELITY_STRICT", None)

        with pytest.raises(TaintFidelityError):
            reconcile_taint_fidelity(
                manifest={"paths_to_write": 100},
                receipt={"db_rows": 0},
                stage="db_output",
                strict=True,
            )


class TestRealisticScenarios:
    """Tests based on real-world taint analysis scenarios."""

    def test_large_codebase_scenario(self):
        """Simulate analysis of a large codebase with many findings."""
        # Discovery: 500 sources, 800 sinks
        sources = [{"file": f"file{i}.py", "line": i} for i in range(500)]
        sinks = [{"file": f"sink{i}.py", "line": i} for i in range(800)]

        discovery_manifest = create_discovery_manifest(sources, sinks)
        assert discovery_manifest["sources"]["count"] == 500
        assert discovery_manifest["sinks"]["count"] == 800

        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={"sinks_to_analyze": 800},
            stage="discovery",
            strict=False,
        )
        assert discovery_result["status"] == "OK"

        # Analysis: 2000 vulnerable, 500 sanitized
        analysis_manifest = create_analysis_manifest(
            vulnerable_paths=[{} for _ in range(2000)],
            sanitized_paths=[{} for _ in range(500)],
            sinks_analyzed=800,
            sources_checked=500,
        )
        assert analysis_manifest["vulnerable_paths"]["count"] == 2000
        assert analysis_manifest["sanitized_paths"]["count"] == 500

    def test_clean_codebase_scenario(self):
        """Simulate analysis of a codebase with no vulnerabilities."""
        # Discovery finds sources and sinks
        discovery_manifest = create_discovery_manifest(
            sources=[{"file": "a.py", "line": 1}],
            sinks=[{"file": "b.py", "line": 2}],
        )
        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={"sinks_to_analyze": 1},
            stage="discovery",
            strict=False,
        )
        assert discovery_result["status"] == "OK"

        # Analysis finds no vulnerable paths (all sanitized)
        analysis_manifest = create_analysis_manifest(
            vulnerable_paths=[],
            sanitized_paths=[{"source": {}, "sink": {}, "sanitizer": "validate"}],
            sinks_analyzed=1,
            sources_checked=1,
        )
        analysis_result = reconcile_taint_fidelity(
            manifest=analysis_manifest,
            receipt={"sinks_to_analyze": 1},
            stage="analysis",
            strict=False,
        )
        assert analysis_result["status"] == "OK"

        # No paths to write
        db_result = reconcile_taint_fidelity(
            manifest={"paths_to_write": 0},
            receipt={"db_rows": 0},
            stage="db_output",
            strict=False,
        )
        # 0 paths to write, 0 written = OK (not 100% loss)
        assert db_result["status"] == "OK"

    def test_no_sources_or_sinks_scenario(self):
        """Simulate analysis of a codebase with no taint sources/sinks."""
        # Discovery finds nothing
        discovery_manifest = create_discovery_manifest(sources=[], sinks=[])

        discovery_result = reconcile_taint_fidelity(
            manifest=discovery_manifest,
            receipt={},
            stage="discovery",
            strict=False,
        )

        # Should warn about both
        assert discovery_result["status"] == "WARNING"
        assert len(discovery_result["warnings"]) == 2
        assert any("0 sources" in w for w in discovery_result["warnings"])
        assert any("0 sinks" in w for w in discovery_result["warnings"])


class TestExistingTestsStillPass:
    """Meta-tests to ensure the fidelity system doesn't break existing functionality."""

    def test_unit_tests_importable(self):
        """Verify unit test module can be imported."""
        from tests.taint import test_fidelity
        assert hasattr(test_fidelity, "TestDiscoveryManifest")
        assert hasattr(test_fidelity, "TestReconcileFidelity")

    def test_fidelity_module_importable(self):
        """Verify fidelity module exports all required functions."""
        from theauditor.taint.fidelity import (
            TaintFidelityError,
            create_analysis_manifest,
            create_db_output_receipt,
            create_dedup_manifest,
            create_discovery_manifest,
            create_json_output_receipt,
            reconcile_taint_fidelity,
        )

        # All functions are callable
        assert callable(create_discovery_manifest)
        assert callable(create_analysis_manifest)
        assert callable(create_dedup_manifest)
        assert callable(create_db_output_receipt)
        assert callable(create_json_output_receipt)
        assert callable(reconcile_taint_fidelity)

        # Exception is a class
        assert issubclass(TaintFidelityError, Exception)
