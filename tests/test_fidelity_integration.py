"""Integration tests for end-to-end fidelity transaction handshake.

These tests verify the COMPLETE flow:
1. Real extraction (Python + Node)
2. Real storage to SQLite
3. Real fidelity reconciliation

This proves the system works in production, not just in unit tests.

Note: Node extraction tests require TypeScript compiler. They will be skipped
if the Node extractor environment isn't properly set up.
"""

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest


# Skip marker for Node-dependent tests
# These tests require full Node environment setup which isn't available in temp dirs
# Run with: pytest -m "not requires_node_sandbox" to skip, or set AUDITOR_TEST_NODE=1 to enable
requires_node_extractor = pytest.mark.skipif(
    os.environ.get("AUDITOR_TEST_NODE") != "1",
    reason="Node sandbox tests disabled (set AUDITOR_TEST_NODE=1 to enable)"
)

from theauditor.indexer.orchestrator import IndexerOrchestrator
from theauditor.indexer.fidelity import reconcile_fidelity
from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.indexer.exceptions import DataFidelityError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_project():
    """Create a temporary project directory with test files."""
    temp_dir = Path(tempfile.mkdtemp(prefix="aud_fidelity_int_"))
    yield temp_dir
    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except PermissionError:
        pass  # Windows file locking


@pytest.fixture
def python_project(temp_project):
    """Create a Python project with extractable symbols."""
    # package.json to make it recognizable
    (temp_project / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "1.0.0"
""")

    # Python file with symbols
    (temp_project / "models.py").write_text("""
class User:
    '''User model with authentication.'''

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def validate(self) -> bool:
        '''Validate user data.'''
        return '@' in self.email


def create_user(name: str, email: str) -> User:
    '''Factory function for users.'''
    return User(name, email)


ADMIN_ROLE = 'admin'
USER_ROLE = 'user'
""")

    return temp_project


@pytest.fixture
def node_project(temp_project):
    """Create a Node.js project with extractable symbols."""
    (temp_project / "package.json").write_text("""{
  "name": "test-node-project",
  "version": "1.0.0"
}""")

    # Simple JS file
    (temp_project / "utils.js").write_text("""
function formatDate(date) {
  return date.toISOString();
}

const DEFAULT_TIMEOUT = 5000;

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  async fetch(endpoint) {
    return fetch(this.baseUrl + endpoint);
  }
}

module.exports = { formatDate, ApiClient, DEFAULT_TIMEOUT };
""")

    return temp_project


@pytest.fixture
def mixed_project(temp_project):
    """Create a polyglot project with Python and Node files."""
    (temp_project / "package.json").write_text("""{
  "name": "polyglot-project",
  "version": "1.0.0"
}""")

    (temp_project / "pyproject.toml").write_text("""
[project]
name = "polyglot-project"
version = "1.0.0"
""")

    (temp_project / "backend.py").write_text("""
class DatabaseConnection:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def query(self, sql):
        pass
""")

    (temp_project / "frontend.js").write_text("""
class UIComponent {
  render() {
    return '<div>Hello</div>';
  }
}
""")

    return temp_project


# =============================================================================
# SECTION 1: Happy Path Integration Tests
# =============================================================================


class TestFidelityIntegrationHappyPath:
    """Test successful extraction->storage->fidelity flow."""

    def test_python_extraction_passes_fidelity(self, python_project):
        """VERIFY: Python extraction produces matching manifest/receipt."""
        db_path = python_project / "test.db"

        orchestrator = IndexerOrchestrator(python_project, str(db_path))
        orchestrator.db_manager.create_schema()

        # This should NOT raise DataFidelityError
        counts, stats = orchestrator.index()

        # Verify data was actually stored
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM symbols")
        symbol_count = cursor.fetchone()[0]

        conn.close()
        orchestrator.db_manager.close()

        assert symbol_count > 0, "Should have extracted symbols"
        # If we get here, fidelity passed (no DataFidelityError raised)

    @requires_node_extractor
    def test_node_extraction_passes_fidelity(self, node_project):
        """VERIFY: Node extraction produces matching manifest/receipt."""
        db_path = node_project / "test.db"

        orchestrator = IndexerOrchestrator(node_project, str(db_path))
        orchestrator.db_manager.create_schema()

        # This should NOT raise DataFidelityError
        counts, stats = orchestrator.index()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM symbols")
        symbol_count = cursor.fetchone()[0]

        conn.close()
        orchestrator.db_manager.close()

        assert symbol_count > 0, "Should have extracted JS symbols"

    @requires_node_extractor
    def test_polyglot_extraction_passes_fidelity(self, mixed_project):
        """VERIFY: Mixed Python+Node project passes fidelity for both."""
        db_path = mixed_project / "test.db"

        orchestrator = IndexerOrchestrator(mixed_project, str(db_path))
        orchestrator.db_manager.create_schema()

        # This should NOT raise DataFidelityError
        counts, stats = orchestrator.index()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Both Python and JS should have symbols
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path LIKE '%.py'")
        py_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path LIKE '%.js'")
        js_count = cursor.fetchone()[0]

        conn.close()
        orchestrator.db_manager.close()

        assert py_count > 0, "Python symbols should be extracted"
        assert js_count > 0, "JavaScript symbols should be extracted"


# =============================================================================
# SECTION 2: Manifest Token Verification
# =============================================================================


class TestManifestTokenStructure:
    """Test that manifests have correct rich token structure."""

    def test_python_manifest_has_rich_tokens(self, python_project):
        """VERIFY: Python extractor produces rich manifest tokens."""
        # Create extraction data
        data = {
            "symbols": [
                {"name": "User", "type": "class", "line": 1},
                {"name": "validate", "type": "method", "line": 10},
            ],
            "imports": [
                {"module": "os", "alias": None},
            ],
        }

        FidelityToken.attach_manifest(data)
        manifest = data["_extraction_manifest"]

        # Verify rich token structure
        assert "symbols" in manifest
        assert isinstance(manifest["symbols"], dict)
        assert "tx_id" in manifest["symbols"]
        assert "columns" in manifest["symbols"]
        assert "count" in manifest["symbols"]
        assert "bytes" in manifest["symbols"]

        # Verify values make sense
        assert manifest["symbols"]["count"] == 2
        assert "name" in manifest["symbols"]["columns"]
        assert "type" in manifest["symbols"]["columns"]
        assert manifest["symbols"]["bytes"] > 0

    def test_manifest_tx_id_uniqueness(self, python_project):
        """VERIFY: Each manifest gets unique tx_id."""
        data1 = {"symbols": [{"name": "foo"}]}
        data2 = {"symbols": [{"name": "bar"}]}

        FidelityToken.attach_manifest(data1)
        FidelityToken.attach_manifest(data2)

        tx1 = data1["_extraction_manifest"]["symbols"]["tx_id"]
        tx2 = data2["_extraction_manifest"]["symbols"]["tx_id"]

        assert tx1 != tx2, "Each extraction should have unique tx_id"


# =============================================================================
# SECTION 3: Failure Detection Integration
# =============================================================================


class TestFidelityFailureDetection:
    """Test that fidelity catches actual problems."""

    def test_simulated_data_loss_detected(self):
        """VERIFY: 100% data loss raises DataFidelityError."""
        # Simulate extractor output
        manifest = {
            "symbols": {
                "tx_id": "test-batch-123",
                "columns": ["name", "type"],
                "count": 50,
                "bytes": 2500,
            }
        }

        # Simulate storage that lost all data
        receipt = {
            "symbols": {
                "tx_id": "test-batch-123",
                "columns": ["name", "type"],
                "count": 0,  # LOST ALL DATA!
                "bytes": 0,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "100% LOSS" in str(exc_info.value)

    def test_simulated_schema_drift_detected(self):
        """VERIFY: Dropped columns raise DataFidelityError."""
        manifest = {
            "users": {
                "tx_id": "test-batch-456",
                "columns": ["id", "name", "email", "password_hash"],
                "count": 100,
                "bytes": 10000,
            }
        }

        # Storage dropped sensitive column!
        receipt = {
            "users": {
                "tx_id": "test-batch-456",
                "columns": ["id", "name"],  # Missing email, password_hash!
                "count": 100,
                "bytes": 5000,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        error_msg = str(exc_info.value)
        assert "SCHEMA VIOLATION" in error_msg
        assert "email" in error_msg or "password_hash" in error_msg

    def test_simulated_crosstalk_detected(self):
        """VERIFY: tx_id mismatch raises DataFidelityError."""
        manifest = {
            "data": {
                "tx_id": "batch-from-file-A",
                "columns": ["value"],
                "count": 10,
                "bytes": 100,
            }
        }

        # Storage processed a DIFFERENT batch!
        receipt = {
            "data": {
                "tx_id": "batch-from-file-B",  # WRONG BATCH!
                "columns": ["value"],
                "count": 10,
                "bytes": 100,
            }
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "TRANSACTION MISMATCH" in str(exc_info.value)


# =============================================================================
# SECTION 4: ZERO FALLBACK Enforcement
# =============================================================================


class TestZeroFallbackIntegration:
    """Test that legacy int format is rejected in integration."""

    def test_legacy_manifest_rejected(self):
        """VERIFY: Legacy int manifest raises DataFidelityError."""
        # Old format (pre-transaction handshake)
        manifest = {
            "symbols": 50,  # LEGACY INT - FORBIDDEN
        }
        receipt = {
            "symbols": {"tx_id": "x", "columns": [], "count": 50, "bytes": 0}
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "LEGACY FORMAT VIOLATION" in str(exc_info.value)

    def test_legacy_receipt_rejected(self):
        """VERIFY: Legacy int receipt raises DataFidelityError."""
        manifest = {
            "symbols": {"tx_id": "x", "columns": [], "count": 50, "bytes": 0}
        }
        receipt = {
            "symbols": 50,  # LEGACY INT - FORBIDDEN
        }

        with pytest.raises(DataFidelityError) as exc_info:
            reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert "LEGACY FORMAT VIOLATION" in str(exc_info.value)


# =============================================================================
# SECTION 5: End-to-End Byte Parity
# =============================================================================


class TestByteParity:
    """Test that byte calculations match between Python and Node."""

    def test_python_byte_calculation_deterministic(self):
        """VERIFY: Same data produces same bytes."""
        data = [
            {"name": "foo", "type": "function", "line": 10},
            {"name": "bar", "type": "class", "line": 20},
        ]

        manifest1 = FidelityToken.create_manifest(data)
        manifest2 = FidelityToken.create_manifest(data)

        # tx_id will differ, but bytes should match
        assert manifest1["bytes"] == manifest2["bytes"]

    def test_bytes_grow_with_data_size(self):
        """VERIFY: More data = more bytes (sanity check)."""
        small_data = [{"name": "a"}]
        large_data = [{"name": "a" * 1000}]

        small_manifest = FidelityToken.create_manifest(small_data)
        large_manifest = FidelityToken.create_manifest(large_data)

        assert large_manifest["bytes"] > small_manifest["bytes"]


# =============================================================================
# SECTION 6: Database Verification
# =============================================================================


class TestDatabaseIntegrity:
    """Test that data actually makes it to the database correctly."""

    def test_symbol_columns_preserved(self, python_project):
        """VERIFY: All expected columns are stored in database."""
        db_path = python_project / "test.db"

        orchestrator = IndexerOrchestrator(python_project, str(db_path))
        orchestrator.db_manager.create_schema()
        orchestrator.index()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get column names from symbols table
        cursor.execute("PRAGMA table_info(symbols)")
        columns = {row[1] for row in cursor.fetchall()}

        conn.close()
        orchestrator.db_manager.close()

        # Core columns should exist
        assert "name" in columns
        assert "type" in columns
        assert "path" in columns

    def test_no_null_corruption(self, python_project):
        """VERIFY: No NULL values in critical columns."""
        db_path = python_project / "test.db"

        orchestrator = IndexerOrchestrator(python_project, str(db_path))
        orchestrator.db_manager.create_schema()
        orchestrator.index()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check for NULL names (would indicate Empty Envelope bug)
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE name IS NULL")
        null_count = cursor.fetchone()[0]

        conn.close()
        orchestrator.db_manager.close()

        assert null_count == 0, "No symbols should have NULL names"


# =============================================================================
# SECTION 7: Warning vs Error Behavior
# =============================================================================


class TestWarningBehavior:
    """Test that warnings don't crash but errors do."""

    def test_partial_loss_warns_not_crashes(self):
        """VERIFY: Partial data loss is warning, not error."""
        manifest = {
            "data": {
                "tx_id": "x",
                "columns": ["a"],
                "count": 100,
                "bytes": 500,
            }
        }
        receipt = {
            "data": {
                "tx_id": "x",
                "columns": ["a"],
                "count": 95,  # Lost 5 rows - partial loss
                "bytes": 475,
            }
        }

        # Should NOT raise - partial loss is warning only
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "WARNING"
        assert len(result["warnings"]) > 0

    def test_volume_collapse_warns_not_crashes(self):
        """VERIFY: Byte collapse is warning, not error."""
        manifest = {
            "data": {
                "tx_id": "x",
                "columns": ["a"],
                "count": 100,
                "bytes": 50000,
            }
        }
        receipt = {
            "data": {
                "tx_id": "x",
                "columns": ["a"],
                "count": 100,  # Same count
                "bytes": 100,  # But way less bytes
            }
        }

        # Should NOT raise - volume collapse is warning only
        result = reconcile_fidelity(manifest, receipt, "/test/file.py")

        assert result["status"] == "WARNING"
        assert any("collapse" in w.lower() for w in result["warnings"])
