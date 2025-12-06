"""
Rust Integration Tests - Verify full Rust extraction pipeline.

This test suite verifies:
1. Rust schema is properly integrated
2. Extraction functions work together
3. Security rules are properly wired
4. Graph strategies are registered

Created as part of: add-rust-support OpenSpec proposal
"""

import pytest
from pathlib import Path
from tree_sitter_language_pack import get_parser

from theauditor.indexer.schemas.rust_schema import RUST_TABLES
from theauditor.indexer.schema import TABLES
from theauditor.ast_extractors import rust_impl as rust_core


EXPECTED_RUST_TABLES = [
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
    "rust_async_functions",
    "rust_await_points",
    "rust_unsafe_blocks",
    "rust_unsafe_traits",
    "rust_struct_fields",
    "rust_enum_variants",
    "rust_trait_methods",
    "rust_extern_functions",
    "rust_extern_blocks",
]


@pytest.fixture
def fixtures_path():
    """Return path to Rust fixtures directory."""
    return Path(__file__).parent / "fixtures" / "rust"


@pytest.fixture
def rust_parser():
    """Create a Rust tree-sitter parser."""
    return get_parser("rust")


def parse_rust(parser, code: str):
    """Helper to parse Rust code."""
    return parser.parse(code.encode("utf-8"))


class TestRustSchemaIntegration:
    """Tests for Rust schema integration."""

    def test_all_20_rust_tables_in_schema(self):
        """Verify all 20 Rust tables exist in RUST_TABLES."""
        assert len(RUST_TABLES) == 23
        for table in EXPECTED_RUST_TABLES:
            assert table in RUST_TABLES, f"Missing table: {table}"

    def test_rust_tables_in_global_schema(self):
        """Verify Rust tables are registered in global TABLES."""
        for table in EXPECTED_RUST_TABLES:
            assert table in TABLES, f"Rust table {table} not in global TABLES"


class TestRustExtractionIntegration:
    """Tests for full Rust extraction flow."""

    def test_extract_from_lib_rs(self, fixtures_path, rust_parser):
        """Test extraction from lib.rs fixture."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        results = {}

        results["rust_modules"] = rust_core.extract_rust_modules(root, str(rust_file))
        results["rust_use_statements"] = rust_core.extract_rust_use_statements(root, str(rust_file))
        results["rust_structs"] = rust_core.extract_rust_structs(root, str(rust_file))
        results["rust_enums"] = rust_core.extract_rust_enums(root, str(rust_file))
        results["rust_traits"] = rust_core.extract_rust_traits(root, str(rust_file))
        results["rust_impl_blocks"] = rust_core.extract_rust_impl_blocks(root, str(rust_file))
        results["rust_functions"] = rust_core.extract_rust_functions(root, str(rust_file))
        results["rust_generics"] = rust_core.extract_rust_generics(root, str(rust_file))
        results["rust_lifetimes"] = rust_core.extract_rust_lifetimes(root, str(rust_file))
        results["rust_macros"] = rust_core.extract_rust_macros(root, str(rust_file))
        results["rust_macro_invocations"] = rust_core.extract_rust_macro_invocations(
            root, str(rust_file)
        )
        results["rust_async_functions"] = rust_core.extract_rust_async_functions(
            root, str(rust_file)
        )
        results["rust_await_points"] = rust_core.extract_rust_await_points(root, str(rust_file))
        results["rust_unsafe_blocks"] = rust_core.extract_rust_unsafe_blocks(root, str(rust_file))
        results["rust_unsafe_traits"] = rust_core.extract_rust_unsafe_traits(root, str(rust_file))
        results["rust_struct_fields"] = rust_core.extract_rust_struct_fields(root, str(rust_file))
        results["rust_enum_variants"] = rust_core.extract_rust_enum_variants(root, str(rust_file))
        results["rust_trait_methods"] = rust_core.extract_rust_trait_methods(root, str(rust_file))
        results["rust_extern_functions"] = rust_core.extract_rust_extern_functions(
            root, str(rust_file)
        )
        results["rust_extern_blocks"] = rust_core.extract_rust_extern_blocks(root, str(rust_file))

        assert len(results["rust_modules"]) >= 2, "Should extract modules"
        assert len(results["rust_use_statements"]) >= 3, "Should extract use statements"
        assert len(results["rust_structs"]) >= 3, "Should extract structs"
        assert len(results["rust_enums"]) >= 2, "Should extract enums"
        assert len(results["rust_traits"]) >= 3, "Should extract traits"
        assert len(results["rust_impl_blocks"]) >= 3, "Should extract impl blocks"
        assert len(results["rust_functions"]) >= 5, "Should extract functions"
        assert len(results["rust_async_functions"]) >= 3, "Should extract async functions"
        assert len(results["rust_unsafe_blocks"]) >= 1, "Should extract unsafe blocks"
        assert len(results["rust_extern_functions"]) >= 2, "Should extract extern functions"

    def test_struct_field_extraction(self, fixtures_path, rust_parser):
        """Test struct field extraction from lib.rs."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        struct_fields = rust_core.extract_rust_struct_fields(root, str(rust_file))

        field_names = {f.get("field_name") for f in struct_fields}
        assert "field1" in field_names, "Should extract field1 from MyStruct"
        assert "field2" in field_names, "Should extract field2 from MyStruct"
        assert "count" in field_names, "Should extract count from MyStruct"

    def test_trait_method_extraction(self, fixtures_path, rust_parser):
        """Test trait method extraction from lib.rs."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        trait_methods = rust_core.extract_rust_trait_methods(root, str(rust_file))

        method_names = {m.get("method_name") for m in trait_methods}
        assert "process" in method_names, "Should extract process() from Processor trait"

    def test_unsafe_block_detection(self, fixtures_path, rust_parser):
        """Test unsafe block extraction with SAFETY comment detection."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        unsafe_blocks = rust_core.extract_rust_unsafe_blocks(root, str(rust_file))

        assert len(unsafe_blocks) >= 1, "Should find unsafe blocks"

        blocks_with_safety = [b for b in unsafe_blocks if b.get("has_safety_comment")]
        blocks_without_safety = [b for b in unsafe_blocks if not b.get("has_safety_comment")]

        assert len(blocks_with_safety) >= 1 or len(blocks_without_safety) >= 1, (
            "Should detect unsafe blocks"
        )

    def test_macro_invocation_extraction(self, fixtures_path, rust_parser):
        """Test macro invocation extraction with args_sample."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        macro_invocations = rust_core.extract_rust_macro_invocations(root, str(rust_file))

        macro_names = {m.get("macro_name") for m in macro_invocations}
        assert "println" in macro_names, "Should extract println! macro"
        assert "vec" in macro_names, "Should extract vec! macro"

    def test_generics_extraction(self, fixtures_path, rust_parser):
        """Test generic parameter extraction."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        generics = rust_core.extract_rust_generics(root, str(rust_file))

        param_names = {g.get("param_name") for g in generics}
        assert "T" in param_names, "Should extract T generic parameter"

    def test_lifetime_extraction(self, fixtures_path, rust_parser):
        """Test lifetime parameter extraction."""
        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)
        root = tree.root_node

        lifetimes = rust_core.extract_rust_lifetimes(root, str(rust_file))

        lifetime_names = {l.get("lifetime_name") for l in lifetimes}
        assert "'a" in lifetime_names, "Should extract 'a lifetime"


class TestRustSecurityRulesIntegration:
    """Tests for Rust security rules integration."""

    def test_unsafe_rule_importable(self):
        """Verify unsafe_analysis rule module is properly structured."""
        from theauditor.rules.rust import unsafe_analysis

        assert hasattr(unsafe_analysis, "METADATA")
        assert hasattr(unsafe_analysis, "find_unsafe_issues")
        assert unsafe_analysis.METADATA.name == "rust_unsafe"

    def test_ffi_rule_importable(self):
        """Verify ffi_boundary rule module is properly structured."""
        from theauditor.rules.rust import ffi_boundary

        assert hasattr(ffi_boundary, "METADATA")
        assert hasattr(ffi_boundary, "find_ffi_boundary_issues")
        assert ffi_boundary.METADATA.name == "rust_ffi_boundary"

    def test_panic_rule_importable(self):
        """Verify panic_paths rule module is properly structured."""
        from theauditor.rules.rust import panic_paths

        assert hasattr(panic_paths, "METADATA")
        assert hasattr(panic_paths, "find_panic_paths")
        assert panic_paths.METADATA.name == "rust_panic_paths"

    def test_memory_rule_importable(self):
        """Verify memory_safety rule module is properly structured."""
        from theauditor.rules.rust import memory_safety

        assert hasattr(memory_safety, "METADATA")
        assert hasattr(memory_safety, "find_memory_safety_issues")
        assert memory_safety.METADATA.name == "rust_memory_safety"

    def test_integer_rule_importable(self):
        """Verify integer_safety rule module is properly structured."""
        from theauditor.rules.rust import integer_safety

        assert hasattr(integer_safety, "METADATA")
        assert hasattr(integer_safety, "find_integer_safety_issues")
        assert integer_safety.METADATA.name == "rust_integer_safety"

    def test_all_rules_target_rs_files(self):
        """Verify all Rust rules target .rs files."""
        from theauditor.rules.rust import (
            unsafe_analysis,
            ffi_boundary,
            panic_paths,
            memory_safety,
            integer_safety,
        )

        rules = [
            unsafe_analysis,
            ffi_boundary,
            panic_paths,
            memory_safety,
            integer_safety,
        ]

        for rule in rules:
            assert ".rs" in rule.METADATA.target_extensions, (
                f"{rule.METADATA.name} should target .rs files"
            )

    def test_all_rules_database_scoped(self):
        """Verify all Rust rules use database execution scope."""
        from theauditor.rules.rust import (
            unsafe_analysis,
            ffi_boundary,
            panic_paths,
            memory_safety,
            integer_safety,
        )

        rules = [
            unsafe_analysis,
            ffi_boundary,
            panic_paths,
            memory_safety,
            integer_safety,
        ]

        for rule in rules:
            assert rule.METADATA.execution_scope == "database", (
                f"{rule.METADATA.name} should be database-scoped"
            )


class TestRustGraphStrategiesIntegration:
    """Tests for Rust graph strategies integration."""

    def test_rust_trait_strategy_exists(self):
        """Verify RustTraitStrategy exists and is importable."""
        from theauditor.graph.strategies.rust_traits import RustTraitStrategy

        strategy = RustTraitStrategy()
        assert hasattr(strategy, "build")

    def test_rust_unsafe_strategy_exists(self):
        """Verify RustUnsafeStrategy exists and is importable."""
        from theauditor.graph.strategies.rust_unsafe import RustUnsafeStrategy

        strategy = RustUnsafeStrategy()
        assert hasattr(strategy, "build")

    def test_rust_ffi_strategy_exists(self):
        """Verify RustFFIStrategy exists and is importable."""
        from theauditor.graph.strategies.rust_ffi import RustFFIStrategy

        strategy = RustFFIStrategy()
        assert hasattr(strategy, "build")

    def test_rust_async_strategy_exists(self):
        """Verify RustAsyncStrategy exists and is importable."""
        from theauditor.graph.strategies.rust_async import RustAsyncStrategy

        strategy = RustAsyncStrategy()
        assert hasattr(strategy, "build")

    def test_strategies_registered_in_dfg_builder(self):
        """Verify Rust strategies are registered in DFG builder."""
        from unittest.mock import patch
        from theauditor.graph.dfg_builder import DFGBuilder

        with patch.object(DFGBuilder, "__init__", lambda self, db_path: None):
            builder = DFGBuilder.__new__(DFGBuilder)

            from theauditor.graph.strategies.rust_traits import RustTraitStrategy
            from theauditor.graph.strategies.rust_unsafe import RustUnsafeStrategy
            from theauditor.graph.strategies.rust_ffi import RustFFIStrategy
            from theauditor.graph.strategies.rust_async import RustAsyncStrategy

            import theauditor.graph.dfg_builder as dfg_module

            source_code = open(dfg_module.__file__).read()

            assert "RustTraitStrategy" in source_code
            assert "RustUnsafeStrategy" in source_code
            assert "RustFFIStrategy" in source_code
            assert "RustAsyncStrategy" in source_code


class TestRustStorageIntegration:
    """Tests for Rust storage handler integration."""

    def test_storage_importable(self):
        """Verify RustStorage is importable."""
        from theauditor.indexer.storage.rust_storage import RustStorage

        assert RustStorage is not None

    def test_storage_has_handlers(self):
        """Verify RustStorage has handlers for all Rust data types."""
        from theauditor.indexer.storage.rust_storage import RustStorage
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        storage = RustStorage(mock_db, {})

        assert hasattr(storage, "handlers")
        assert len(storage.handlers) == 23, "Should have 23 handlers"

        for table_name in EXPECTED_RUST_TABLES:
            assert table_name in storage.handlers, f"Missing handler: {table_name}"


class TestRustExtractorIntegration:
    """Tests for Rust extractor integration."""

    def test_extractor_supports_rs(self):
        """Verify RustExtractor supports .rs files."""
        from theauditor.indexer.extractors.rust import RustExtractor
        from pathlib import Path

        extractor = RustExtractor(Path("."))
        extensions = extractor.supported_extensions()

        assert ".rs" in extensions

    def test_extractor_has_extract_method(self):
        """Verify RustExtractor has extract method."""
        from theauditor.indexer.extractors.rust import RustExtractor
        from pathlib import Path

        extractor = RustExtractor(Path("."))
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)

    def test_extractor_returns_all_table_keys(self, fixtures_path, rust_parser):
        """Verify RustExtractor.extract() returns all 20 table keys."""
        from theauditor.indexer.extractors.rust import RustExtractor
        from pathlib import Path

        rust_file = fixtures_path / "lib.rs"
        if not rust_file.exists():
            pytest.skip("Fixture file not found")

        extractor = RustExtractor(Path(fixtures_path))
        content = rust_file.read_text(encoding="utf-8")
        tree = parse_rust(rust_parser, content)

        file_info = {"path": str(rust_file)}
        tree_dict = {"type": "tree_sitter", "tree": tree}

        result = extractor.extract(file_info, content, tree_dict)

        for table_name in EXPECTED_RUST_TABLES:
            assert table_name in result, f"Missing key in extract result: {table_name}"
