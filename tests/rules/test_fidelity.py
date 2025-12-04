"""Tests for the fidelity tracking infrastructure.

Tests cover:
- 5.5 RuleDB helper
- 5.6 Fidelity verification
"""

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch

from theauditor.rules.fidelity import (
    RuleDB,
    RuleManifest,
    RuleResult,
    FidelityError,
    verify_fidelity,
    STRICT_FIDELITY,
)
from theauditor.rules.query import Q


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database with test tables."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create a minimal symbols table matching the schema
    cursor.execute("""
        CREATE TABLE symbols (
            id INTEGER PRIMARY KEY,
            name TEXT,
            path TEXT,
            line INTEGER,
            column INTEGER,
            type TEXT,
            language TEXT,
            qualified_name TEXT,
            docstring TEXT,
            signature TEXT,
            decorators TEXT,
            parent_symbol TEXT,
            scope TEXT,
            is_async INTEGER,
            is_generator INTEGER,
            is_exported INTEGER,
            is_abstract INTEGER,
            complexity INTEGER,
            parameters TEXT,
            return_type TEXT,
            file_hash TEXT
        )
    """)

    # Insert test data
    cursor.executemany(
        "INSERT INTO symbols (name, path, line, type) VALUES (?, ?, ?, ?)",
        [
            ("foo", "/test/file.py", 10, "function"),
            ("bar", "/test/file.py", 20, "function"),
            ("Baz", "/test/file.py", 30, "class"),
            ("qux", "/test/other.py", 5, "function"),
            ("helper", "/test/utils.py", 1, "function"),
        ],
    )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)


class TestRuleManifest:
    """Test RuleManifest tracking class."""

    def test_initial_state(self):
        """Manifest starts with zeroed counters."""
        manifest = RuleManifest("test_rule")

        assert manifest.rule_name == "test_rule"
        assert manifest.items_scanned == 0
        assert manifest.tables_queried == set()
        assert manifest.queries_executed == 0

    def test_track_query_updates_all_fields(self):
        """track_query updates all tracking fields."""
        manifest = RuleManifest("test_rule")

        manifest.track_query("symbols", 50)

        assert manifest.items_scanned == 50
        assert "symbols" in manifest.tables_queried
        assert manifest.queries_executed == 1

    def test_track_query_accumulates(self):
        """Multiple track_query calls accumulate."""
        manifest = RuleManifest("test_rule")

        manifest.track_query("symbols", 50)
        manifest.track_query("assignments", 30)
        manifest.track_query("symbols", 20)

        assert manifest.items_scanned == 100
        assert manifest.tables_queried == {"symbols", "assignments"}
        assert manifest.queries_executed == 3

    def test_to_dict_returns_standardized_keys(self):
        """to_dict returns dict with standardized keys."""
        manifest = RuleManifest("test_rule")
        manifest.track_query("symbols", 50)

        result = manifest.to_dict()

        assert result["rule_name"] == "test_rule"
        assert result["items_scanned"] == 50
        assert result["tables_queried"] == ["symbols"]  # Sorted list
        assert result["queries_executed"] == 1
        assert "execution_time_ms" in result
        assert isinstance(result["execution_time_ms"], int)


class TestRuleDB:
    """5.5 Test RuleDB helper class."""

    def test_query_execution_returns_list_tuple(self, temp_db):
        """Query execution returns list[tuple]."""
        with RuleDB(temp_db, "test_rule") as db:
            rows = db.query(Q("symbols").select("name", "line").where("type = ?", "function"))

        assert isinstance(rows, list)
        assert len(rows) == 4  # 4 functions in test data
        assert all(isinstance(row, tuple) for row in rows)

    def test_manifest_tracks_queries_executed(self, temp_db):
        """Manifest tracks queries_executed count."""
        with RuleDB(temp_db, "test_rule") as db:
            db.query(Q("symbols").select("name"))
            db.query(Q("symbols").select("line"))
            db.query(Q("symbols").select("type"))

            manifest = db.get_manifest()

        assert manifest["queries_executed"] == 3

    def test_manifest_tracks_tables_queried(self, temp_db):
        """Manifest tracks tables_queried set."""
        with RuleDB(temp_db, "test_rule") as db:
            db.query(Q("symbols").select("name"))
            db.query(Q("symbols").select("line"))

            manifest = db.get_manifest()

        assert "symbols" in manifest["tables_queried"]

    def test_manifest_tracks_items_scanned(self, temp_db):
        """Manifest tracks items_scanned (row count)."""
        with RuleDB(temp_db, "test_rule") as db:
            # Query returns 4 functions
            db.query(Q("symbols").select("name").where("type = ?", "function"))
            # Query returns 1 class
            db.query(Q("symbols").select("name").where("type = ?", "class"))

            manifest = db.get_manifest()

        assert manifest["items_scanned"] == 5  # 4 + 1

    def test_context_manager_closes_connection(self, temp_db):
        """Context manager closes connection on exit."""
        db = RuleDB(temp_db, "test_rule")
        conn = db.conn

        with db:
            pass  # Exit context

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_context_manager_closes_on_exception(self, temp_db):
        """Context manager closes connection even on exception."""
        db = RuleDB(temp_db, "test_rule")
        conn = db.conn

        with pytest.raises(ValueError):
            with db:
                raise ValueError("Test exception")

        # Connection should still be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_execute_raw_sql(self, temp_db):
        """execute() method runs raw SQL with tracking."""
        with RuleDB(temp_db, "test_rule") as db:
            rows = db.execute("SELECT name FROM symbols WHERE type = ?", ["function"])
            manifest = db.get_manifest()

        assert len(rows) == 4
        assert manifest["queries_executed"] == 1
        assert manifest["items_scanned"] == 4

    def test_rule_name_in_manifest(self, temp_db):
        """Rule name appears in manifest."""
        with RuleDB(temp_db, "my_security_rule") as db:
            db.query(Q("symbols").select("name"))
            manifest = db.get_manifest()

        assert manifest["rule_name"] == "my_security_rule"


class TestRuleResult:
    """Test RuleResult dataclass."""

    def test_ruleresult_holds_findings_and_manifest(self):
        """RuleResult holds findings list and manifest dict."""
        result = RuleResult(findings=[], manifest={"items_scanned": 100})

        assert result.findings == []
        assert result.manifest == {"items_scanned": 100}

    def test_ruleresult_default_manifest(self):
        """RuleResult has empty dict as default manifest."""
        result = RuleResult(findings=[])

        assert result.manifest == {}


class TestFidelityVerification:
    """5.6 Test fidelity verification."""

    def test_pass_case_items_scanned_positive(self):
        """Verification passes when items_scanned > 0."""
        manifest = {"items_scanned": 100, "rule_name": "test"}
        expected = {"table_row_count": 500}

        passed, errors = verify_fidelity(manifest, expected)

        assert passed is True
        assert errors == []

    def test_fail_case_zero_items_scanned(self):
        """Verification fails when items_scanned = 0 but table has rows."""
        manifest = {"items_scanned": 0, "rule_name": "test"}
        expected = {"table_row_count": 500}

        passed, errors = verify_fidelity(manifest, expected)

        assert passed is False
        assert len(errors) == 1
        assert "scanned 0 items" in errors[0]
        assert "500 rows" in errors[0]

    def test_pass_case_empty_table(self):
        """Verification passes when both items_scanned and table_row_count are 0."""
        manifest = {"items_scanned": 0, "rule_name": "test"}
        expected = {"table_row_count": 0}

        passed, errors = verify_fidelity(manifest, expected)

        assert passed is True
        assert errors == []

    def test_strict_mode_raises_fidelity_error(self):
        """Strict mode raises FidelityError on failure."""
        manifest = {"items_scanned": 0, "rule_name": "test"}
        expected = {"table_row_count": 500}

        # Directly patch the module-level constant
        with patch("theauditor.rules.fidelity.STRICT_FIDELITY", True):
            with pytest.raises(FidelityError) as exc_info:
                verify_fidelity(manifest, expected)

            assert "scanned 0 items" in str(exc_info.value.errors)

    def test_warn_mode_logs_and_returns_errors(self):
        """Warn mode (default) logs warning and returns errors."""
        manifest = {"items_scanned": 0, "rule_name": "test"}
        expected = {"table_row_count": 500}

        # Ensure strict mode is off
        with patch("theauditor.rules.fidelity.STRICT_FIDELITY", False):
            with patch("theauditor.rules.fidelity.logger") as mock_logger:
                passed, errors = verify_fidelity(manifest, expected)

        assert passed is False
        assert len(errors) == 1
        mock_logger.warning.assert_called_once()

    def test_missing_manifest_keys_use_defaults(self):
        """Missing manifest keys default to 0."""
        manifest = {}  # No items_scanned key
        expected = {"table_row_count": 100}

        # Ensure strict mode is off for this test
        with patch("theauditor.rules.fidelity.STRICT_FIDELITY", False):
            passed, errors = verify_fidelity(manifest, expected)

        assert passed is False  # 0 items but 100 rows = fail

    def test_missing_expected_keys_use_defaults(self):
        """Missing expected keys default to 0."""
        manifest = {"items_scanned": 0, "rule_name": "test"}
        expected = {}  # No table_row_count key

        passed, errors = verify_fidelity(manifest, expected)

        assert passed is True  # 0 items, 0 expected = pass


class TestFidelityError:
    """Test FidelityError exception class."""

    def test_fidelity_error_holds_errors_list(self):
        """FidelityError holds list of error messages."""
        error = FidelityError(["Error 1", "Error 2"])

        assert error.errors == ["Error 1", "Error 2"]
        assert "Error 1" in str(error)
        assert "Error 2" in str(error)
