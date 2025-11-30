"""
Go Integration Tests - Verify full Go extraction pipeline.

This test suite verifies:
1. Go schema is properly integrated
2. Extraction functions work together
3. Security rules are properly wired
4. Graph strategies are registered

Created as part of: add-go-support OpenSpec proposal
"""

import pytest
from pathlib import Path
from tree_sitter_language_pack import get_parser

from theauditor.indexer.schemas.go_schema import GO_TABLES
from theauditor.indexer.schema import TABLES
from theauditor.ast_extractors import go_impl


# All 22 expected Go tables
EXPECTED_GO_TABLES = [
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
]


@pytest.fixture
def fixtures_path():
    """Return path to Go fixtures directory."""
    return Path(__file__).parent / "fixtures" / "go"


@pytest.fixture
def go_parser():
    """Create a Go tree-sitter parser."""
    return get_parser("go")


def parse_go(parser, code: str):
    """Helper to parse Go code."""
    return parser.parse(code.encode("utf-8"))


class TestGoSchemaIntegration:
    """Tests for Go schema integration."""

    def test_all_22_go_tables_in_schema(self):
        """Verify all 22 Go tables exist in GO_TABLES."""
        assert len(GO_TABLES) == 22
        for table in EXPECTED_GO_TABLES:
            assert table in GO_TABLES, f"Missing table: {table}"

    def test_go_tables_in_global_schema(self):
        """Verify Go tables are registered in global TABLES."""
        for table in EXPECTED_GO_TABLES:
            assert table in TABLES, f"Go table {table} not in global TABLES"


class TestGoExtractionIntegration:
    """Tests for full Go extraction flow."""

    def test_extract_from_comprehensive_sample(self, fixtures_path, go_parser):
        """Test extraction from comprehensive_sample.go."""
        go_file = fixtures_path / "comprehensive_sample.go"
        if not go_file.exists():
            pytest.skip("Fixture file not found")

        content = go_file.read_text(encoding="utf-8")
        tree = parse_go(go_parser, content)

        # Extract all data types
        results = {}

        results["go_packages"] = go_impl.extract_go_package(tree, content, str(go_file))
        results["go_imports"] = go_impl.extract_go_imports(tree, content, str(go_file))
        results["go_structs"] = go_impl.extract_go_structs(tree, content, str(go_file))
        results["go_struct_fields"] = go_impl.extract_go_struct_fields(tree, content, str(go_file))
        results["go_interfaces"] = go_impl.extract_go_interfaces(tree, content, str(go_file))
        results["go_interface_methods"] = go_impl.extract_go_interface_methods(tree, content, str(go_file))
        results["go_functions"] = go_impl.extract_go_functions(tree, content, str(go_file))
        results["go_methods"] = go_impl.extract_go_methods(tree, content, str(go_file))
        results["go_func_params"] = go_impl.extract_go_func_params(tree, content, str(go_file))
        results["go_func_returns"] = go_impl.extract_go_func_returns(tree, content, str(go_file))
        results["go_goroutines"] = go_impl.extract_go_goroutines(tree, content, str(go_file))
        results["go_channels"] = go_impl.extract_go_channels(tree, content, str(go_file))
        results["go_channel_ops"] = go_impl.extract_go_channel_ops(tree, content, str(go_file))
        results["go_defer_statements"] = go_impl.extract_go_defer_statements(tree, content, str(go_file))
        results["go_constants"] = go_impl.extract_go_constants(tree, content, str(go_file))
        results["go_variables"] = go_impl.extract_go_variables(tree, content, str(go_file))
        results["go_type_params"] = go_impl.extract_go_type_params(tree, content, str(go_file))
        results["go_type_assertions"] = go_impl.extract_go_type_assertions(tree, content, str(go_file))
        results["go_error_returns"] = go_impl.extract_go_error_returns(tree, content, str(go_file))
        results["go_captured_vars"] = go_impl.extract_go_captured_vars(
            tree, content, str(go_file), results["go_goroutines"]
        )

        # Verify we got data for key tables
        assert results["go_packages"] is not None, "Should extract package"
        assert len(results["go_imports"]) > 0, "Should extract imports"
        assert len(results["go_structs"]) > 0, "Should extract structs"
        assert len(results["go_functions"]) > 0, "Should extract functions"
        assert len(results["go_goroutines"]) > 0, "Should extract goroutines"
        assert len(results["go_type_params"]) > 0, "Should extract type params (generics)"

    def test_extract_vulnerable_sample(self, fixtures_path, go_parser):
        """Test extraction from vulnerable_sample.go."""
        vuln_file = fixtures_path / "vulnerable_sample.go"
        if not vuln_file.exists():
            pytest.skip("Fixture file not found")

        content = vuln_file.read_text(encoding="utf-8")
        tree = parse_go(go_parser, content)

        # Extract key elements
        constants = go_impl.extract_go_constants(tree, content, str(vuln_file))
        variables = go_impl.extract_go_variables(tree, content, str(vuln_file))
        goroutines = go_impl.extract_go_goroutines(tree, content, str(vuln_file))
        captured = go_impl.extract_go_captured_vars(tree, content, str(vuln_file), goroutines)

        # Verify we found vulnerable patterns
        const_names = {c["name"] for c in constants}
        assert "APIKey" in const_names, "Should find hardcoded secret"
        assert "SecretToken" in const_names, "Should find hardcoded secret"

        # Should find goroutines with captured loop vars
        assert len(goroutines) > 0, "Should find goroutines"
        loop_vars = [c for c in captured if c.get("is_loop_var")]
        assert len(loop_vars) > 0, "Should detect captured loop variables"


class TestGoSecurityRulesIntegration:
    """Tests for Go security rules integration."""

    def test_injection_rule_importable(self):
        """Verify injection rule module is properly structured."""
        from theauditor.rules.go import injection_analyze

        assert hasattr(injection_analyze, "METADATA")
        assert hasattr(injection_analyze, "analyze")
        assert injection_analyze.METADATA.name == "go_injection"

    def test_crypto_rule_importable(self):
        """Verify crypto rule module is properly structured."""
        from theauditor.rules.go import crypto_analyze

        assert hasattr(crypto_analyze, "METADATA")
        assert hasattr(crypto_analyze, "analyze")
        assert crypto_analyze.METADATA.name == "go_crypto"

    def test_concurrency_rule_importable(self):
        """Verify concurrency rule module is properly structured."""
        from theauditor.rules.go import concurrency_analyze

        assert hasattr(concurrency_analyze, "METADATA")
        assert hasattr(concurrency_analyze, "analyze")
        assert concurrency_analyze.METADATA.name == "go_concurrency"

    def test_error_handling_rule_importable(self):
        """Verify error_handling rule module is properly structured."""
        from theauditor.rules.go import error_handling_analyze

        assert hasattr(error_handling_analyze, "METADATA")
        assert hasattr(error_handling_analyze, "analyze")
        assert error_handling_analyze.METADATA.name == "go_error_handling"

    def test_all_rules_target_go_files(self):
        """Verify all Go rules target .go files."""
        from theauditor.rules.go import (
            injection_analyze,
            crypto_analyze,
            concurrency_analyze,
            error_handling_analyze,
        )

        rules = [
            injection_analyze,
            crypto_analyze,
            concurrency_analyze,
            error_handling_analyze,
        ]

        for rule in rules:
            assert ".go" in rule.METADATA.target_extensions, (
                f"{rule.METADATA.name} should target .go files"
            )

    def test_all_rules_database_scoped(self):
        """Verify all Go rules use database execution scope."""
        from theauditor.rules.go import (
            injection_analyze,
            crypto_analyze,
            concurrency_analyze,
            error_handling_analyze,
        )

        rules = [
            injection_analyze,
            crypto_analyze,
            concurrency_analyze,
            error_handling_analyze,
        ]

        for rule in rules:
            assert rule.METADATA.execution_scope == "database", (
                f"{rule.METADATA.name} should be database-scoped"
            )


class TestGoGraphStrategiesIntegration:
    """Tests for Go graph strategies integration."""

    def test_go_http_strategy_exists(self):
        """Verify GoHttpStrategy exists and is importable."""
        from theauditor.graph.strategies.go_http import GoHttpStrategy

        strategy = GoHttpStrategy()
        assert hasattr(strategy, "build")

    def test_go_orm_strategy_exists(self):
        """Verify GoOrmStrategy exists and is importable."""
        from theauditor.graph.strategies.go_orm import GoOrmStrategy

        strategy = GoOrmStrategy()
        assert hasattr(strategy, "build")

    def test_strategies_exported_from_init(self):
        """Verify Go strategies are exported from strategies module."""
        from theauditor.graph.strategies import GoHttpStrategy, GoOrmStrategy

        assert GoHttpStrategy is not None
        assert GoOrmStrategy is not None


class TestGoDatabaseMixinIntegration:
    """Tests for Go database mixin integration."""

    def test_mixin_in_database_manager(self):
        """Verify GoDatabaseMixin is part of DatabaseManager."""
        from theauditor.indexer.database import DatabaseManager
        from theauditor.indexer.database.go_database import GoDatabaseMixin

        # Check that DatabaseManager inherits from GoDatabaseMixin
        assert issubclass(DatabaseManager, GoDatabaseMixin)

    def test_mixin_methods_available(self):
        """Verify Go database methods are available."""
        from theauditor.indexer.database.go_database import GoDatabaseMixin

        # Check a few key methods exist
        assert hasattr(GoDatabaseMixin, "add_go_package")
        assert hasattr(GoDatabaseMixin, "add_go_goroutine")
        assert hasattr(GoDatabaseMixin, "add_go_captured_var")


class TestGoStorageIntegration:
    """Tests for Go storage handler integration."""

    def test_storage_importable(self):
        """Verify GoStorage is importable."""
        from theauditor.indexer.storage.go_storage import GoStorage
        assert GoStorage is not None

    def test_storage_has_handlers(self):
        """Verify GoStorage has handlers for all Go data types."""
        from theauditor.indexer.storage.go_storage import GoStorage
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        storage = GoStorage(mock_db, {})

        assert hasattr(storage, "handlers")
        assert len(storage.handlers) > 0

        # Check for key handlers
        expected_handlers = [
            "go_packages",
            "go_imports",
            "go_structs",
            "go_goroutines",
            "go_captured_vars",
        ]

        for handler_name in expected_handlers:
            assert handler_name in storage.handlers, f"Missing handler: {handler_name}"


class TestGoExtractorIntegration:
    """Tests for Go extractor integration."""

    def test_extractor_supports_go(self):
        """Verify GoExtractor supports .go files."""
        from theauditor.indexer.extractors.go import GoExtractor
        from pathlib import Path

        extractor = GoExtractor(Path("."))
        extensions = extractor.supported_extensions()

        assert ".go" in extensions

    def test_extractor_has_extract_method(self):
        """Verify GoExtractor has extract method."""
        from theauditor.indexer.extractors.go import GoExtractor
        from pathlib import Path

        extractor = GoExtractor(Path("."))
        assert hasattr(extractor, "extract")
        assert callable(extractor.extract)
