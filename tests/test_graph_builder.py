"""Unit tests for graph builder import resolution.

This test suite focuses on the fragile resolve_import_path method,
which is the most critical part of dependency graph construction.

Tests cover:
- TypeScript path aliases (@/components/Foo)
- Deep relative paths (../../../utils/helper)
- Python module imports
- Node modules (external packages)
- Edge cases with missing files
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from theauditor.graph.builder import XGraphBuilder


@pytest.fixture
def mock_project():
    """Create a mock project structure with database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create .pf directory with database
        pf_dir = project_root / ".pf"
        pf_dir.mkdir()
        db_path = pf_dir / "repo_index.db"

        # Initialize database with files table
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create files table (minimal schema for testing)
        cursor.execute("""
            CREATE TABLE files (
                path TEXT PRIMARY KEY,
                language TEXT,
                loc INTEGER
            )
        """)

        # Create tsconfig_paths table for alias resolution
        cursor.execute("""
            CREATE TABLE tsconfig_paths (
                id INTEGER PRIMARY KEY,
                alias TEXT NOT NULL,
                path TEXT NOT NULL,
                context TEXT DEFAULT 'root'
            )
        """)

        # Add mock files to database
        test_files = [
            # Frontend files
            ("frontend/src/components/Button.tsx", "typescript", 100),
            ("frontend/src/utils/helpers.ts", "typescript", 50),
            ("frontend/src/pages/Home.tsx", "typescript", 200),
            ("frontend/src/services/api.ts", "typescript", 150),

            # Backend files
            ("backend/src/routes/users.ts", "typescript", 120),
            ("backend/src/models/user.ts", "typescript", 80),
            ("backend/src/utils/db.ts", "typescript", 60),

            # Python files
            ("backend/app/services/user_service.py", "python", 90),
            ("backend/app/models/user.py", "python", 70),
        ]

        cursor.executemany(
            "INSERT INTO files (path, language, loc) VALUES (?, ?, ?)",
            test_files
        )

        # Add TypeScript path aliases
        aliases = [
            ("@/components", "frontend/src/components", "frontend"),
            ("@/utils", "frontend/src/utils", "frontend"),
            ("@/services", "frontend/src/services", "frontend"),
            ("@/routes", "backend/src/routes", "backend"),
            ("@/models", "backend/src/models", "backend"),
        ]

        cursor.executemany(
            "INSERT INTO tsconfig_paths (alias, path, context) VALUES (?, ?, ?)",
            aliases
        )

        conn.commit()
        conn.close()

        yield project_root, db_path


@pytest.fixture
def builder(mock_project):
    """Create XGraphBuilder instance with mock project."""
    project_root, db_path = mock_project
    return XGraphBuilder(project_root=str(project_root))


class TestResolveImportPath:
    """Test suite for resolve_import_path method."""

    def test_python_simple_module(self, builder):
        """Test Python module path resolution."""
        source = Path("backend/app/services/user_service.py")
        result = builder.resolve_import_path("app.models.user", source, "python")
        assert result == "app/models/user"

    def test_python_nested_module(self, builder):
        """Test deeply nested Python module."""
        source = Path("backend/app/services/user_service.py")
        result = builder.resolve_import_path("app.services.auth.jwt", source, "python")
        assert result == "app/services/auth/jwt"

    def test_typescript_alias_frontend(self, builder):
        """Test TypeScript path alias resolution in frontend context."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("@/components/Button", source, "typescript")

        # Should resolve to actual file with extension
        assert result in [
            "frontend/src/components/Button.tsx",
            "frontend/src/components/Button.ts",
            "frontend/src/components/Button"
        ]

    def test_typescript_alias_backend(self, builder):
        """Test TypeScript path alias resolution in backend context."""
        source = builder.project_root / "backend/src/routes/users.ts"
        result = builder.resolve_import_path("@/models/user", source, "typescript")

        # Should resolve to backend model
        assert result in [
            "backend/src/models/user.ts",
            "backend/src/models/user"
        ]

    def test_relative_import_sibling(self, builder):
        """Test relative import from sibling file (./foo)."""
        source = builder.project_root / "frontend/src/components/Button.tsx"
        result = builder.resolve_import_path("./helpers", source, "typescript")

        # Should resolve relative to source directory
        # Note: The method tries multiple extensions
        assert "frontend/src/components/helpers" in result

    def test_relative_import_parent(self, builder):
        """Test relative import from parent directory (../foo)."""
        source = builder.project_root / "frontend/src/components/Button.tsx"
        result = builder.resolve_import_path("../utils/helpers", source, "typescript")

        # Should resolve to utils directory
        assert result in [
            "frontend/src/utils/helpers.ts",
            "frontend/src/utils/helpers"
        ]

    def test_relative_import_deep(self, builder):
        """Test deeply nested relative import (../../../foo)."""
        source = builder.project_root / "frontend/src/components/Button.tsx"
        result = builder.resolve_import_path("../../../backend/src/utils/db", source, "typescript")

        # Should traverse up and back down
        assert "backend/src/utils/db" in result

    def test_node_modules_import(self, builder):
        """Test external node_modules import."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("react", source, "typescript")

        # Should return as-is for external packages
        assert result == "react"

    def test_scoped_node_modules(self, builder):
        """Test scoped npm package import (@apollo/client)."""
        source = builder.project_root / "frontend/src/services/api.ts"
        result = builder.resolve_import_path("@apollo/client", source, "typescript")

        # Should return as-is (external package, not path alias)
        # Note: This is a critical edge case - @apollo vs @/ aliases
        assert result == "@apollo/client"

    def test_missing_file_with_extensions(self, builder):
        """Test resolution for missing file tries multiple extensions."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("./NonExistent", source, "typescript")

        # Should still return a path even if file doesn't exist in DB
        assert "frontend/src/pages/NonExistent" in result

    def test_index_file_resolution(self, builder):
        """Test that index files are checked during resolution."""
        # Add an index file to the mock database
        conn = sqlite3.connect(builder.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (path, language, loc) VALUES (?, ?, ?)",
            ("frontend/src/hooks/index.ts", "typescript", 30)
        )
        conn.commit()
        conn.close()

        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("../hooks", source, "typescript")

        # Should resolve to index file
        assert result == "frontend/src/hooks/index.ts"

    def test_windows_path_normalization(self, builder):
        """Test that backslashes are normalized to forward slashes."""
        # Simulate Windows path with backslashes
        source = Path("frontend\\src\\pages\\Home.tsx")
        result = builder.resolve_import_path("@/utils/helpers", source, "typescript")

        # Result should use forward slashes
        assert "\\" not in result
        assert "/" in result or result.startswith("@")

    def test_edge_case_empty_import(self, builder):
        """Test handling of empty import string."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("", source, "typescript")

        # Should return empty or original
        assert result == ""

    def test_edge_case_quoted_import(self, builder):
        """Test that quotes and semicolons are stripped."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("'@/components/Button';", source, "typescript")

        # Should strip quotes and semicolons
        assert "'" not in result
        assert ";" not in result

    def test_unknown_language_passthrough(self, builder):
        """Test that unknown languages return import as-is."""
        source = Path("some/file.unknown")
        result = builder.resolve_import_path("some/weird/import", source, "rust")

        # Should return as-is for unsupported languages
        assert result == "some/weird/import"


class TestEdgeCasesAndRegressions:
    """Test edge cases and potential regression scenarios."""

    def test_circular_relative_imports(self, builder):
        """Test that circular relative imports don't cause infinite loops."""
        source = builder.project_root / "frontend/src/components/Button.tsx"

        # This is a nonsensical import but should not crash
        result = builder.resolve_import_path("./../../src/components/Button", source, "typescript")
        assert isinstance(result, str)

    def test_alias_without_slash(self, builder):
        """Test TypeScript alias that doesn't match any configured alias."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("@unknown/path", source, "typescript")

        # Should return as-is if alias not found
        assert "@unknown" in result

    def test_very_long_import_path(self, builder):
        """Test handling of extremely long import paths."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        long_import = "../" * 50 + "utils/helper"
        result = builder.resolve_import_path(long_import, source, "typescript")

        # Should handle without crashing
        assert isinstance(result, str)

    def test_special_characters_in_import(self, builder):
        """Test import paths with special characters."""
        source = builder.project_root / "frontend/src/pages/Home.tsx"
        result = builder.resolve_import_path("./file-with-dashes", source, "typescript")

        # Should preserve special characters
        assert "file-with-dashes" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
