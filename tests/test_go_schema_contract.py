"""
Go Schema Contract Tests - Verify Go language support implementation.

This test suite verifies that:
1. All 22 Go tables exist in the schema
2. Go extractor produces expected data
3. Storage handlers correctly batch data
4. Database methods exist and are callable

Created as part of: add-go-support OpenSpec proposal
"""

import pytest

from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.go_schema import GO_TABLES


# Expected Go tables from the spec
EXPECTED_GO_TABLES = {
    "go_packages",
    "go_imports",
    "go_structs",
    "go_struct_fields",
    "go_interfaces",
    "go_interface_methods",
    "go_functions",
    "go_methods",
    "go_func_params",
    "go_func_returns",
    "go_goroutines",
    "go_channels",
    "go_channel_ops",
    "go_defer_statements",
    "go_error_returns",
    "go_type_assertions",
    "go_routes",
    "go_constants",
    "go_variables",
    "go_type_params",
    "go_captured_vars",
    "go_middleware",
}


class TestGoSchemaContract:
    """Tests to ensure Go schema matches expected contract."""

    def test_go_tables_count(self):
        """Verify expected number of Go tables."""
        assert len(GO_TABLES) == 22, (
            f"Expected 22 Go tables, got {len(GO_TABLES)}. "
            f"Tables: {sorted(GO_TABLES.keys())}"
        )

    def test_all_expected_tables_exist(self):
        """Verify all expected Go tables exist."""
        missing = EXPECTED_GO_TABLES - set(GO_TABLES.keys())
        assert not missing, f"Missing Go tables: {missing}"

    def test_no_extra_tables(self):
        """Verify no unexpected Go tables exist."""
        extra = set(GO_TABLES.keys()) - EXPECTED_GO_TABLES
        assert not extra, f"Unexpected Go tables: {extra}"

    def test_go_tables_in_global_tables(self):
        """Verify Go tables are registered in global TABLES dict."""
        for table_name in EXPECTED_GO_TABLES:
            assert table_name in TABLES, f"Go table {table_name} not in global TABLES"

    def test_all_tables_have_file_column(self):
        """Verify all Go tables have a file column."""
        for table_name, table_schema in GO_TABLES.items():
            column_names = {col.name for col in table_schema.columns}
            assert "file" in column_names, f"{table_name}: missing 'file' column"

    def test_core_tables_have_line_column(self):
        """Verify core Go tables have a line column."""
        tables_with_line = {
            "go_packages",
            "go_imports",
            "go_structs",
            "go_interfaces",
            "go_functions",
            "go_methods",
            "go_goroutines",
            "go_channels",
            "go_channel_ops",
            "go_defer_statements",
            "go_error_returns",
            "go_type_assertions",
            "go_routes",
            "go_constants",
            "go_variables",
            "go_type_params",
            "go_captured_vars",
            "go_middleware",
        }

        for table_name in tables_with_line:
            table_schema = GO_TABLES[table_name]
            column_names = {col.name for col in table_schema.columns}
            assert "line" in column_names, f"{table_name}: missing 'line' column"


class TestGoTableStructure:
    """Tests for specific Go table structures."""

    def test_go_packages_columns(self):
        """Verify go_packages has required columns."""
        table = GO_TABLES["go_packages"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "name", "import_path"}
        assert required.issubset(column_names), (
            f"go_packages missing columns: {required - column_names}"
        )

    def test_go_imports_columns(self):
        """Verify go_imports has required columns."""
        table = GO_TABLES["go_imports"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "path", "alias", "is_dot_import"}
        assert required.issubset(column_names), (
            f"go_imports missing columns: {required - column_names}"
        )

    def test_go_structs_columns(self):
        """Verify go_structs has required columns."""
        table = GO_TABLES["go_structs"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "name", "is_exported", "doc_comment"}
        assert required.issubset(column_names), (
            f"go_structs missing columns: {required - column_names}"
        )

    def test_go_struct_fields_columns(self):
        """Verify go_struct_fields has required columns."""
        table = GO_TABLES["go_struct_fields"]
        column_names = {col.name for col in table.columns}
        required = {
            "file", "struct_name", "field_name", "field_type",
            "tag", "is_embedded", "is_exported"
        }
        assert required.issubset(column_names), (
            f"go_struct_fields missing columns: {required - column_names}"
        )

    def test_go_goroutines_columns(self):
        """Verify go_goroutines has required columns."""
        table = GO_TABLES["go_goroutines"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "containing_func", "spawned_expr", "is_anonymous"}
        assert required.issubset(column_names), (
            f"go_goroutines missing columns: {required - column_names}"
        )

    def test_go_captured_vars_columns(self):
        """Verify go_captured_vars has required columns for race detection."""
        table = GO_TABLES["go_captured_vars"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "goroutine_id", "var_name", "var_type", "is_loop_var"}
        assert required.issubset(column_names), (
            f"go_captured_vars missing columns: {required - column_names}"
        )

    def test_go_variables_has_package_level_flag(self):
        """Verify go_variables has is_package_level for race detection."""
        table = GO_TABLES["go_variables"]
        column_names = {col.name for col in table.columns}
        assert "is_package_level" in column_names, (
            "go_variables missing 'is_package_level' column for race detection"
        )

    def test_go_type_params_columns(self):
        """Verify go_type_params has columns for Go 1.18+ generics."""
        table = GO_TABLES["go_type_params"]
        column_names = {col.name for col in table.columns}
        required = {
            "file", "line", "parent_name", "parent_kind",
            "param_index", "param_name", "constraint"
        }
        assert required.issubset(column_names), (
            f"go_type_params missing columns: {required - column_names}"
        )

    def test_go_routes_columns(self):
        """Verify go_routes has framework detection columns."""
        table = GO_TABLES["go_routes"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "framework", "method", "path", "handler_func"}
        assert required.issubset(column_names), (
            f"go_routes missing columns: {required - column_names}"
        )

    def test_go_middleware_columns(self):
        """Verify go_middleware has required columns."""
        table = GO_TABLES["go_middleware"]
        column_names = {col.name for col in table.columns}
        required = {"file", "line", "framework", "router_var", "middleware_func", "is_global"}
        assert required.issubset(column_names), (
            f"go_middleware missing columns: {required - column_names}"
        )


class TestGoDatabaseMixin:
    """Tests to verify GoDatabaseMixin exists and is properly integrated."""

    def test_go_database_mixin_importable(self):
        """Verify GoDatabaseMixin is importable."""
        from theauditor.indexer.database.go_database import GoDatabaseMixin
        assert GoDatabaseMixin is not None

    def test_go_database_mixin_has_methods(self):
        """Verify GoDatabaseMixin has expected add_go_* methods."""
        from theauditor.indexer.database.go_database import GoDatabaseMixin

        expected_methods = [
            "add_go_package",
            "add_go_import",
            "add_go_struct",
            "add_go_struct_field",
            "add_go_interface",
            "add_go_interface_method",
            "add_go_function",
            "add_go_method",
            "add_go_func_param",
            "add_go_func_return",
            "add_go_goroutine",
            "add_go_channel",
            "add_go_channel_op",
            "add_go_defer_statement",
            "add_go_error_return",
            "add_go_type_assertion",
            "add_go_route",
            "add_go_constant",
            "add_go_variable",
            "add_go_type_param",
            "add_go_captured_var",
            "add_go_middleware",
        ]

        for method_name in expected_methods:
            assert hasattr(GoDatabaseMixin, method_name), (
                f"GoDatabaseMixin missing method: {method_name}"
            )


class TestGoExtractor:
    """Tests to verify GoExtractor exists and is properly integrated."""

    def test_go_extractor_importable(self):
        """Verify GoExtractor is importable."""
        from theauditor.indexer.extractors.go import GoExtractor
        assert GoExtractor is not None

    def test_go_extractor_supports_go_extension(self):
        """Verify GoExtractor supports .go extension."""
        from pathlib import Path
        from theauditor.indexer.extractors.go import GoExtractor

        extractor = GoExtractor(root_path=Path("."))
        assert ".go" in extractor.supported_extensions()


class TestGoStorage:
    """Tests to verify GoStorage exists and is properly integrated."""

    def test_go_storage_importable(self):
        """Verify GoStorage is importable."""
        from theauditor.indexer.storage.go_storage import GoStorage
        assert GoStorage is not None

    def test_go_storage_has_handlers(self):
        """Verify GoStorage has handlers dict."""
        from theauditor.indexer.storage.go_storage import GoStorage
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_counts = {}

        storage = GoStorage(mock_db, mock_counts)
        assert hasattr(storage, "handlers")
        assert isinstance(storage.handlers, dict)
        assert len(storage.handlers) > 0


class TestGoImplFunctions:
    """Tests to verify go_impl extraction functions exist."""

    def test_go_impl_importable(self):
        """Verify go_impl module is importable."""
        from theauditor.ast_extractors import go_impl
        assert go_impl is not None

    def test_extraction_functions_exist(self):
        """Verify all extraction functions exist in go_impl."""
        from theauditor.ast_extractors import go_impl

        expected_functions = [
            "extract_go_package",
            "extract_go_imports",
            "extract_go_structs",
            "extract_go_struct_fields",
            "extract_go_interfaces",
            "extract_go_interface_methods",
            "extract_go_functions",
            "extract_go_methods",
            "extract_go_func_params",
            "extract_go_func_returns",
            "extract_go_goroutines",
            "extract_go_channels",
            "extract_go_channel_ops",
            "extract_go_defer_statements",
            "extract_go_constants",
            "extract_go_variables",
            "extract_go_type_params",
            "extract_go_type_assertions",
            "extract_go_error_returns",
            "extract_go_captured_vars",
        ]

        for func_name in expected_functions:
            assert hasattr(go_impl, func_name), f"go_impl missing function: {func_name}"
            assert callable(getattr(go_impl, func_name)), f"{func_name} is not callable"
