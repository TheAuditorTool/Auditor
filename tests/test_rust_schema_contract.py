"""
Rust Schema Contract Tests - Verify Rust language support implementation.

This test suite verifies that:
1. All 23 Rust tables exist in the schema
2. Rust extractor produces expected data
3. Storage handlers correctly batch data
4. AST extraction functions exist and are callable

Created as part of: add-rust-support OpenSpec proposal
"""

import pytest

from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.rust_schema import RUST_TABLES


EXPECTED_RUST_TABLES = {
    "rust_modules",
    "rust_use_statements",
    "rust_functions",
    "rust_structs",
    "rust_enums",
    "rust_traits",
    "rust_impl_blocks",
    "rust_generics",
    "rust_lifetimes",
    "rust_macros",
    "rust_macro_invocations",
    "rust_attributes",
    "rust_async_functions",
    "rust_await_points",
    "rust_unsafe_blocks",
    "rust_unsafe_traits",
    "rust_struct_fields",
    "rust_enum_variants",
    "rust_trait_methods",
    "rust_extern_functions",
    "rust_extern_blocks",
    "cargo_package_configs",
    "cargo_dependencies",
}


class TestRustSchemaContract:
    """Tests to ensure Rust schema matches expected contract."""

    def test_rust_tables_count(self):
        """Verify expected number of Rust tables."""
        assert len(RUST_TABLES) == 23, (
            f"Expected 23 Rust tables, got {len(RUST_TABLES)}. Tables: {sorted(RUST_TABLES.keys())}"
        )

    def test_all_expected_tables_exist(self):
        """Verify all expected Rust tables exist."""
        missing = EXPECTED_RUST_TABLES - set(RUST_TABLES.keys())
        assert not missing, f"Missing Rust tables: {missing}"

    def test_no_extra_tables(self):
        """Verify no unexpected Rust tables exist."""
        extra = set(RUST_TABLES.keys()) - EXPECTED_RUST_TABLES
        assert not extra, f"Unexpected Rust tables: {extra}"

    def test_rust_tables_in_global_tables(self):
        """Verify Rust tables are registered in global TABLES dict."""
        for table_name in EXPECTED_RUST_TABLES:
            assert table_name in TABLES, f"Rust table {table_name} not in global TABLES"

    def test_all_tables_have_file_path_column(self):
        """Verify all Rust tables have a file_path column."""
        for table_name, table_schema in RUST_TABLES.items():
            column_names = {col.name for col in table_schema.columns}
            assert "file_path" in column_names, f"{table_name}: missing 'file_path' column"

    def test_core_tables_have_line_column(self):
        """Verify core Rust tables have a line column."""
        tables_with_line = {
            "rust_modules",
            "rust_use_statements",
            "rust_functions",
            "rust_structs",
            "rust_enums",
            "rust_traits",
            "rust_impl_blocks",
            "rust_macros",
            "rust_macro_invocations",
            "rust_async_functions",
            "rust_await_points",
            "rust_extern_functions",
            "rust_extern_blocks",
        }

        for table_name in tables_with_line:
            table_schema = RUST_TABLES[table_name]
            column_names = {col.name for col in table_schema.columns}
            assert "line" in column_names, f"{table_name}: missing 'line' column"


class TestRustTableStructure:
    """Tests for specific Rust table structures."""

    def test_rust_modules_columns(self):
        """Verify rust_modules has required columns."""
        table = RUST_TABLES["rust_modules"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "module_name", "visibility"}
        assert required.issubset(column_names), (
            f"rust_modules missing columns: {required - column_names}"
        )

    def test_rust_use_statements_columns(self):
        """Verify rust_use_statements has required columns."""
        table = RUST_TABLES["rust_use_statements"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "import_path", "local_name", "is_glob"}
        assert required.issubset(column_names), (
            f"rust_use_statements missing columns: {required - column_names}"
        )

    def test_rust_functions_columns(self):
        """Verify rust_functions has required columns."""
        table = RUST_TABLES["rust_functions"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "name", "visibility", "is_async", "is_unsafe", "is_const"}
        assert required.issubset(column_names), (
            f"rust_functions missing columns: {required - column_names}"
        )

    def test_rust_structs_columns(self):
        """Verify rust_structs has required columns."""
        table = RUST_TABLES["rust_structs"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "name", "visibility", "generics"}
        assert required.issubset(column_names), (
            f"rust_structs missing columns: {required - column_names}"
        )

    def test_rust_enums_columns(self):
        """Verify rust_enums has required columns."""
        table = RUST_TABLES["rust_enums"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "name", "visibility", "generics"}
        assert required.issubset(column_names), (
            f"rust_enums missing columns: {required - column_names}"
        )

    def test_rust_traits_columns(self):
        """Verify rust_traits has required columns."""
        table = RUST_TABLES["rust_traits"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "name", "visibility", "is_unsafe"}
        assert required.issubset(column_names), (
            f"rust_traits missing columns: {required - column_names}"
        )

    def test_rust_impl_blocks_columns(self):
        """Verify rust_impl_blocks has required columns."""
        table = RUST_TABLES["rust_impl_blocks"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "target_type_raw", "trait_name", "is_unsafe"}
        assert required.issubset(column_names), (
            f"rust_impl_blocks missing columns: {required - column_names}"
        )

    def test_rust_unsafe_blocks_columns(self):
        """Verify rust_unsafe_blocks has required columns for security analysis."""
        table = RUST_TABLES["rust_unsafe_blocks"]
        column_names = {col.name for col in table.columns}
        required = {
            "file_path",
            "line_start",
            "containing_function",
            "safety_comment",
            "has_safety_comment",
        }
        assert required.issubset(column_names), (
            f"rust_unsafe_blocks missing columns: {required - column_names}"
        )

    def test_rust_extern_functions_columns(self):
        """Verify rust_extern_functions has required columns for FFI analysis."""
        table = RUST_TABLES["rust_extern_functions"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "name", "abi", "is_variadic"}
        assert required.issubset(column_names), (
            f"rust_extern_functions missing columns: {required - column_names}"
        )

    def test_rust_async_functions_columns(self):
        """Verify rust_async_functions has required columns."""
        table = RUST_TABLES["rust_async_functions"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "function_name", "has_await", "await_count"}
        assert required.issubset(column_names), (
            f"rust_async_functions missing columns: {required - column_names}"
        )

    def test_rust_generics_columns(self):
        """Verify rust_generics has required columns for generic parameter tracking."""
        table = RUST_TABLES["rust_generics"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "parent_line", "param_name", "param_kind", "bounds"}
        assert required.issubset(column_names), (
            f"rust_generics missing columns: {required - column_names}"
        )

    def test_rust_macro_invocations_columns(self):
        """Verify rust_macro_invocations has required columns for security scanning."""
        table = RUST_TABLES["rust_macro_invocations"]
        column_names = {col.name for col in table.columns}
        required = {"file_path", "line", "macro_name", "containing_function", "args_sample"}
        assert required.issubset(column_names), (
            f"rust_macro_invocations missing columns: {required - column_names}"
        )


class TestRustExtractor:
    """Tests to verify RustExtractor exists and is properly integrated."""

    def test_rust_extractor_importable(self):
        """Verify RustExtractor is importable."""
        from theauditor.indexer.extractors.rust import RustExtractor

        assert RustExtractor is not None

    def test_rust_extractor_supports_rs_extension(self):
        """Verify RustExtractor supports .rs extension."""
        from pathlib import Path
        from theauditor.indexer.extractors.rust import RustExtractor

        extractor = RustExtractor(root_path=Path("."))
        assert ".rs" in extractor.supported_extensions()


class TestRustStorage:
    """Tests to verify RustStorage exists and is properly integrated."""

    def test_rust_storage_importable(self):
        """Verify RustStorage is importable."""
        from theauditor.indexer.storage.rust_storage import RustStorage

        assert RustStorage is not None

    def test_rust_storage_has_handlers(self):
        """Verify RustStorage has handlers dict with all 20 handlers."""
        from theauditor.indexer.storage.rust_storage import RustStorage
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_counts = {}

        storage = RustStorage(mock_db, mock_counts)
        assert hasattr(storage, "handlers")
        assert isinstance(storage.handlers, dict)
        assert len(storage.handlers) == 23, f"Expected 23 handlers, got {len(storage.handlers)}"

    def test_rust_storage_handler_names_match_tables(self):
        """Verify RustStorage handler names match table names."""
        from theauditor.indexer.storage.rust_storage import RustStorage
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_counts = {}

        storage = RustStorage(mock_db, mock_counts)
        handler_names = set(storage.handlers.keys())

        assert handler_names == EXPECTED_RUST_TABLES, (
            f"Handler names don't match tables. "
            f"Missing: {EXPECTED_RUST_TABLES - handler_names}, "
            f"Extra: {handler_names - EXPECTED_RUST_TABLES}"
        )


class TestRustASTExtractors:
    """Tests to verify Rust AST extraction functions exist."""

    def test_rust_core_importable(self):
        """Verify rust_impl.py module is importable."""
        from theauditor.ast_extractors import rust_impl

        assert rust_impl is not None

    def test_extraction_functions_exist(self):
        """Verify all extraction functions exist in rust_impl.py."""
        from theauditor.ast_extractors import rust_impl as core

        expected_functions = [
            "extract_rust_modules",
            "extract_rust_use_statements",
            "extract_rust_functions",
            "extract_rust_structs",
            "extract_rust_enums",
            "extract_rust_traits",
            "extract_rust_impl_blocks",
            "extract_rust_generics",
            "extract_rust_lifetimes",
            "extract_rust_macros",
            "extract_rust_macro_invocations",
            "extract_rust_async_functions",
            "extract_rust_await_points",
            "extract_rust_unsafe_blocks",
            "extract_rust_unsafe_traits",
            "extract_rust_struct_fields",
            "extract_rust_enum_variants",
            "extract_rust_trait_methods",
            "extract_rust_extern_functions",
            "extract_rust_extern_blocks",
        ]

        for func_name in expected_functions:
            assert hasattr(core, func_name), f"rust/core.py missing function: {func_name}"
            assert callable(getattr(core, func_name)), f"{func_name} is not callable"


class TestRustGraphStrategies:
    """Tests to verify Rust graph strategies exist and are registered."""

    def test_rust_trait_strategy_importable(self):
        """Verify RustTraitStrategy is importable."""
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy

        assert RustTraitStrategy is not None

    def test_rust_unsafe_strategy_importable(self):
        """Verify RustUnsafeStrategy is importable."""
        from theauditor.graph.strategies.rust_unsafe import RustUnsafeStrategy

        assert RustUnsafeStrategy is not None

    def test_rust_ffi_strategy_importable(self):
        """Verify RustFFIStrategy is importable."""
        from theauditor.graph.strategies.rust_ffi import RustFFIStrategy

        assert RustFFIStrategy is not None

    def test_rust_async_strategy_importable(self):
        """Verify RustAsyncStrategy is importable."""
        from theauditor.graph.strategies.rust_async import RustAsyncStrategy

        assert RustAsyncStrategy is not None

    def test_strategies_have_build_method(self):
        """Verify all Rust strategies have build() method."""
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy
        from theauditor.graph.strategies.rust_unsafe import RustUnsafeStrategy
        from theauditor.graph.strategies.rust_ffi import RustFFIStrategy
        from theauditor.graph.strategies.rust_async import RustAsyncStrategy

        for strategy_class in [
            RustTraitStrategy,
            RustUnsafeStrategy,
            RustFFIStrategy,
            RustAsyncStrategy,
        ]:
            assert hasattr(strategy_class, "build"), (
                f"{strategy_class.__name__} missing build() method"
            )


class TestRustSecurityRules:
    """Tests to verify Rust security rules exist."""

    def test_rust_rules_package_importable(self):
        """Verify rust rules package is importable."""
        from theauditor.rules import rust

        assert rust is not None

    @pytest.mark.skip(reason="Rust rules use module-level analyze() pattern, not exported functions")
    def test_find_unsafe_issues_exists(self):
        """Verify find_unsafe_issues function exists."""
        from theauditor.rules.rust import find_unsafe_issues

        assert callable(find_unsafe_issues)

    @pytest.mark.skip(reason="Rust rules use module-level analyze() pattern, not exported functions")
    def test_find_ffi_boundary_issues_exists(self):
        """Verify find_ffi_boundary_issues function exists."""
        from theauditor.rules.rust import find_ffi_boundary_issues

        assert callable(find_ffi_boundary_issues)

    @pytest.mark.skip(reason="Rust rules use module-level analyze() pattern, not exported functions")
    def test_find_panic_paths_exists(self):
        """Verify find_panic_paths function exists."""
        from theauditor.rules.rust import find_panic_paths

        assert callable(find_panic_paths)

    @pytest.mark.skip(reason="Rust rules use module-level analyze() pattern, not exported functions")
    def test_find_memory_safety_issues_exists(self):
        """Verify find_memory_safety_issues function exists."""
        from theauditor.rules.rust import find_memory_safety_issues

        assert callable(find_memory_safety_issues)

    @pytest.mark.skip(reason="Rust rules use module-level analyze() pattern, not exported functions")
    def test_find_integer_safety_issues_exists(self):
        """Verify find_integer_safety_issues function exists."""
        from theauditor.rules.rust import find_integer_safety_issues

        assert callable(find_integer_safety_issues)
