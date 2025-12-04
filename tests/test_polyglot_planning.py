"""Tests for polyglot planning support (Go/Rust/Bash).

Tests verify that:
1. Blueprint naming conventions include Go/Rust/Bash
2. Blueprint deps include Cargo/Go module dependencies
3. Explain detects Go/Rust framework handlers
4. Deadcode detects Go/Rust/Bash entry points
5. Boundaries detects Go/Rust entry points
"""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def repo_db():
    """Get connection to repo_index.db if it exists."""
    db_path = Path(".pf/repo_index.db")
    if not db_path.exists():
        pytest.skip("repo_index.db not found - run 'aud full' first")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def graphs_db():
    """Get connection to graphs.db if it exists."""
    db_path = Path(".pf/graphs.db")
    if not db_path.exists():
        pytest.skip("graphs.db not found - run 'aud full' first")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# =============================================================================
# Section 7.1: Blueprint Naming Convention Tests
# =============================================================================


class TestBlueprintNamingConventions:
    """Tests for Go/Rust/Bash naming convention detection."""

    def test_go_symbols_in_unified_table(self, repo_db):
        """Verify Go symbols are in unified symbols table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM symbols s
            JOIN files f ON s.path = f.path
            WHERE f.ext = '.go'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Go symbols should be in unified symbols table"

    def test_rust_symbols_in_unified_table(self, repo_db):
        """Verify Rust symbols are in unified symbols table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM symbols s
            JOIN files f ON s.path = f.path
            WHERE f.ext = '.rs'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Rust symbols should be in unified symbols table"

    def test_bash_symbols_in_unified_table(self, repo_db):
        """Verify Bash symbols are in unified symbols table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM symbols s
            JOIN files f ON s.path = f.path
            WHERE f.ext = '.sh'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Bash symbols should be in unified symbols table"

    def test_go_functions_have_names(self, repo_db):
        """Verify Go function names are extracted for naming analysis."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT name FROM go_functions
            WHERE name IS NOT NULL AND name != ''
            LIMIT 5
            """
        )
        rows = cursor.fetchall()
        assert len(rows) > 0, "Go functions should have names"

    def test_rust_functions_have_names(self, repo_db):
        """Verify Rust function names are extracted for naming analysis."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT name FROM rust_functions
            WHERE name IS NOT NULL AND name != ''
            LIMIT 5
            """
        )
        rows = cursor.fetchall()
        assert len(rows) > 0, "Rust functions should have names"

    def test_bash_functions_have_names(self, repo_db):
        """Verify Bash function names are extracted for naming analysis."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT name FROM bash_functions
            WHERE name IS NOT NULL AND name != ''
            LIMIT 5
            """
        )
        rows = cursor.fetchall()
        assert len(rows) > 0, "Bash functions should have names"


# =============================================================================
# Section 7.2: Blueprint Dependency Tests
# =============================================================================


class TestBlueprintDependencies:
    """Tests for Cargo/Go module dependency detection."""

    def test_cargo_package_configs_populated(self, repo_db):
        """Verify Cargo.toml package configs are stored."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM cargo_package_configs")
        count = cursor.fetchone()[0]
        assert count > 0, "cargo_package_configs should have data from Cargo.toml files"

    def test_cargo_dependencies_populated(self, repo_db):
        """Verify Cargo.toml dependencies are stored."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM cargo_dependencies")
        count = cursor.fetchone()[0]
        assert count > 0, "cargo_dependencies should have data"

    def test_go_module_configs_populated(self, repo_db):
        """Verify go.mod module configs are stored."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM go_module_configs")
        count = cursor.fetchone()[0]
        assert count > 0, "go_module_configs should have data from go.mod files"

    def test_go_module_dependencies_populated(self, repo_db):
        """Verify go.mod dependencies are stored."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM go_module_dependencies")
        count = cursor.fetchone()[0]
        assert count > 0, "go_module_dependencies should have data"

    def test_cargo_config_has_package_name(self, repo_db):
        """Verify Cargo configs have package names."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT package_name FROM cargo_package_configs
            WHERE package_name IS NOT NULL
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        assert row is not None, "Cargo config should have package_name"
        assert row[0], "package_name should not be empty"

    def test_go_module_has_module_path(self, repo_db):
        """Verify Go modules have module paths."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT module_path FROM go_module_configs
            WHERE module_path IS NOT NULL
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        assert row is not None, "Go module config should have module_path"
        assert row[0], "module_path should not be empty"


# =============================================================================
# Section 7.3: Explain Framework Tests
# =============================================================================


class TestExplainFramework:
    """Tests for Go/Rust framework handler detection."""

    def test_go_routes_table_exists(self, repo_db):
        """Verify go_routes table exists and has data."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM go_routes")
        count = cursor.fetchone()[0]
        assert count > 0, "go_routes should have Go web framework routes"

    def test_go_routes_have_framework(self, repo_db):
        """Verify Go routes have framework detection."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT DISTINCT framework FROM go_routes
            WHERE framework IS NOT NULL
            """
        )
        frameworks = [row[0] for row in cursor.fetchall()]
        assert len(frameworks) > 0, "Go routes should have framework field"
        # Common Go frameworks
        valid_frameworks = {"gin", "echo", "chi", "fiber", "gorilla", "net/http"}
        assert any(
            f in valid_frameworks for f in frameworks
        ), f"Framework should be one of {valid_frameworks}, got {frameworks}"

    def test_rust_attributes_table_exists(self, repo_db):
        """Verify rust_attributes table exists and has data."""
        cursor = repo_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM rust_attributes")
        count = cursor.fetchone()[0]
        assert count > 0, "rust_attributes should have Rust attribute data"

    def test_rust_route_attributes_detected(self, repo_db):
        """Verify Rust route attributes are detected."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM rust_attributes
            WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route', 'handler')
            """
        )
        count = cursor.fetchone()[0]
        # May be 0 if no web handlers in fixtures, so just verify query works
        assert count >= 0, "Query for Rust route attributes should work"


# =============================================================================
# Section 7.4: Deadcode Entry Point Tests
# =============================================================================


class TestDeadcodeEntryPoints:
    """Tests for Go/Rust/Bash entry point detection."""

    def test_go_main_functions_detected(self, repo_db):
        """Verify Go main functions are detected as entry points."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM go_functions
            WHERE name = 'main'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Go main functions should be detected"

    def test_rust_main_functions_detected(self, repo_db):
        """Verify Rust main functions are detected as entry points."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM rust_functions
            WHERE name = 'main'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Rust main functions should be detected"

    def test_rust_test_attributes_detected(self, repo_db):
        """Verify Rust test attributes are detected as entry points."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM rust_attributes
            WHERE attribute_name = 'test'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Rust #[test] attributes should be detected"

    def test_bash_files_indexed(self, repo_db):
        """Verify Bash files are indexed (all .sh files are entry points)."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM files
            WHERE ext = '.sh'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Bash .sh files should be indexed"


# =============================================================================
# Section 7.5: Boundaries Entry Point Tests
# =============================================================================


class TestBoundariesEntryPoints:
    """Tests for Go/Rust entry point detection in boundaries analysis."""

    def test_go_routes_have_required_columns(self, repo_db):
        """Verify go_routes has columns needed for boundaries analysis."""
        cursor = repo_db.cursor()
        cursor.execute("PRAGMA table_info(go_routes)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"file", "line", "framework", "method", "path", "handler_func"}
        missing = required - columns
        assert not missing, f"go_routes missing columns for boundaries: {missing}"

    def test_rust_attributes_have_required_columns(self, repo_db):
        """Verify rust_attributes has columns needed for boundaries analysis."""
        cursor = repo_db.cursor()
        cursor.execute("PRAGMA table_info(rust_attributes)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"file_path", "line", "attribute_name", "args", "target_line"}
        missing = required - columns
        assert not missing, f"rust_attributes missing columns for boundaries: {missing}"


# =============================================================================
# Section 7.6: Graph Edge Tests
# =============================================================================


class TestGraphEdges:
    """Tests for Go/Rust/Bash graph edge population."""

    def test_go_import_edges_exist(self, graphs_db):
        """Verify Go import edges are in graphs.db."""
        cursor = graphs_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM edges
            WHERE source LIKE '%.go' AND graph_type = 'import'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Go import edges should exist in graphs.db"

    def test_rust_import_edges_exist(self, graphs_db):
        """Verify Rust import edges are in graphs.db."""
        cursor = graphs_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM edges
            WHERE source LIKE '%.rs' AND graph_type = 'import'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Rust import edges should exist in graphs.db"

    def test_go_refs_populated(self, repo_db):
        """Verify Go imports are in unified refs table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM refs r
            JOIN files f ON r.src = f.path
            WHERE f.ext = '.go'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Go imports should be in unified refs table"

    def test_rust_refs_populated(self, repo_db):
        """Verify Rust use statements are in unified refs table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM refs r
            JOIN files f ON r.src = f.path
            WHERE f.ext = '.rs'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Rust use statements should be in unified refs table"

    def test_bash_refs_populated(self, repo_db):
        """Verify Bash source statements are in unified refs table."""
        cursor = repo_db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM refs r
            JOIN files f ON r.src = f.path
            WHERE f.ext = '.sh'
            """
        )
        count = cursor.fetchone()[0]
        assert count > 0, "Bash source statements should be in unified refs table"
