"""Tests for FCE Semantic Table Registry."""

import pytest

from theauditor.fce.registry import SemanticTableRegistry


class TestRiskSources:
    """Tests for RISK_SOURCES table set."""

    def test_risk_sources_contains_expected_tables(self):
        """RISK_SOURCES contains the 7 expected tables."""
        registry = SemanticTableRegistry()
        expected = {
            "cdk_findings",
            "findings_consolidated",
            "framework_taint_patterns",
            "graphql_findings_cache",
            "python_security_findings",
            "taint_flows",
            "terraform_findings",
        }
        assert registry.RISK_SOURCES == expected

    def test_risk_sources_count(self):
        """RISK_SOURCES has exactly 7 tables."""
        assert len(SemanticTableRegistry.RISK_SOURCES) == 7

    def test_findings_consolidated_is_risk_source(self):
        """findings_consolidated (main findings table) is a risk source."""
        assert "findings_consolidated" in SemanticTableRegistry.RISK_SOURCES

    def test_taint_flows_is_risk_source(self):
        """taint_flows (taint analysis) is a risk source."""
        assert "taint_flows" in SemanticTableRegistry.RISK_SOURCES


class TestContextProcess:
    """Tests for CONTEXT_PROCESS table set."""

    def test_context_process_count(self):
        """CONTEXT_PROCESS has exactly 4 tables."""
        assert len(SemanticTableRegistry.CONTEXT_PROCESS) == 4

    def test_code_diffs_is_process(self):
        """code_diffs is in CONTEXT_PROCESS."""
        assert "code_diffs" in SemanticTableRegistry.CONTEXT_PROCESS

    def test_refactor_tables_are_process(self):
        """refactor_* tables are in CONTEXT_PROCESS."""
        assert "refactor_candidates" in SemanticTableRegistry.CONTEXT_PROCESS
        assert "refactor_history" in SemanticTableRegistry.CONTEXT_PROCESS


class TestContextStructural:
    """Tests for CONTEXT_STRUCTURAL table set."""

    def test_context_structural_count(self):
        """CONTEXT_STRUCTURAL has exactly 6 tables."""
        assert len(SemanticTableRegistry.CONTEXT_STRUCTURAL) == 6

    def test_cfg_tables_are_structural(self):
        """cfg_* tables are in CONTEXT_STRUCTURAL."""
        cfg_tables = [t for t in SemanticTableRegistry.CONTEXT_STRUCTURAL if t.startswith("cfg_")]
        assert len(cfg_tables) == 6


class TestContextFramework:
    """Tests for CONTEXT_FRAMEWORK table set."""

    def test_context_framework_count(self):
        """CONTEXT_FRAMEWORK has 36 tables."""
        assert len(SemanticTableRegistry.CONTEXT_FRAMEWORK) == 36

    def test_react_tables_in_framework(self):
        """React tables are in CONTEXT_FRAMEWORK."""
        react_tables = [
            t for t in SemanticTableRegistry.CONTEXT_FRAMEWORK if t.startswith("react_")
        ]
        assert len(react_tables) == 4  # react_component_hooks, react_components, react_hook_dependencies, react_hooks

    def test_angular_tables_in_framework(self):
        """Angular tables are in CONTEXT_FRAMEWORK."""
        angular_tables = [
            t for t in SemanticTableRegistry.CONTEXT_FRAMEWORK if t.startswith("angular_")
        ]
        assert len(angular_tables) == 9

    def test_vue_tables_in_framework(self):
        """Vue tables are in CONTEXT_FRAMEWORK."""
        vue_tables = [
            t for t in SemanticTableRegistry.CONTEXT_FRAMEWORK if t.startswith("vue_")
        ]
        assert len(vue_tables) == 7

    def test_graphql_tables_in_framework(self):
        """GraphQL tables are in CONTEXT_FRAMEWORK."""
        graphql_tables = [
            t for t in SemanticTableRegistry.CONTEXT_FRAMEWORK if t.startswith("graphql_")
        ]
        assert len(graphql_tables) == 9


class TestContextSecurity:
    """Tests for CONTEXT_SECURITY table set."""

    def test_context_security_count(self):
        """CONTEXT_SECURITY has exactly 6 tables."""
        assert len(SemanticTableRegistry.CONTEXT_SECURITY) == 6

    def test_api_endpoints_is_security(self):
        """api_endpoints is in CONTEXT_SECURITY."""
        assert "api_endpoints" in SemanticTableRegistry.CONTEXT_SECURITY

    def test_jwt_patterns_is_security(self):
        """jwt_patterns is in CONTEXT_SECURITY."""
        assert "jwt_patterns" in SemanticTableRegistry.CONTEXT_SECURITY

    def test_sql_tables_are_security(self):
        """SQL-related tables are in CONTEXT_SECURITY."""
        assert "sql_queries" in SemanticTableRegistry.CONTEXT_SECURITY
        assert "sql_objects" in SemanticTableRegistry.CONTEXT_SECURITY


class TestContextLanguage:
    """Tests for CONTEXT_LANGUAGE table set."""

    def test_context_language_count(self):
        """CONTEXT_LANGUAGE has 88 tables."""
        # 10 bash + 22 go + 36 python + 20 rust = 88
        assert len(SemanticTableRegistry.CONTEXT_LANGUAGE) == 88

    def test_python_tables_in_language(self):
        """Python tables are in CONTEXT_LANGUAGE."""
        python_tables = [
            t for t in SemanticTableRegistry.CONTEXT_LANGUAGE if t.startswith("python_")
        ]
        assert len(python_tables) == 36

    def test_go_tables_in_language(self):
        """Go tables are in CONTEXT_LANGUAGE."""
        go_tables = [
            t for t in SemanticTableRegistry.CONTEXT_LANGUAGE if t.startswith("go_")
        ]
        assert len(go_tables) == 22

    def test_rust_tables_in_language(self):
        """Rust tables are in CONTEXT_LANGUAGE."""
        rust_tables = [
            t for t in SemanticTableRegistry.CONTEXT_LANGUAGE if t.startswith("rust_")
        ]
        assert len(rust_tables) == 20

    def test_bash_tables_in_language(self):
        """Bash tables are in CONTEXT_LANGUAGE."""
        bash_tables = [
            t for t in SemanticTableRegistry.CONTEXT_LANGUAGE if t.startswith("bash_")
        ]
        assert len(bash_tables) == 10


class TestGetContextTablesForFile:
    """Tests for get_context_tables_for_file() method."""

    def test_python_file_returns_python_tables(self):
        """Python file returns python_* tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("src/utils/helpers.py")
        assert all(t.startswith("python_") for t in tables)
        assert len(tables) == 36

    def test_go_file_returns_go_tables(self):
        """Go file returns go_* tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("cmd/server/main.go")
        assert all(t.startswith("go_") for t in tables)
        assert len(tables) == 22

    def test_rust_file_returns_rust_tables(self):
        """Rust file returns rust_* tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("src/lib.rs")
        assert all(t.startswith("rust_") for t in tables)
        assert len(tables) == 20

    def test_bash_file_returns_bash_tables(self):
        """Bash file returns bash_* tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("scripts/deploy.sh")
        assert all(t.startswith("bash_") for t in tables)
        assert len(tables) == 10

    def test_tsx_file_returns_react_and_framework_tables(self):
        """TSX file returns React and other framework tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("src/components/Button.tsx")
        # Should include react_, angular_, vue_, graphql_, sequelize_, prisma_
        prefixes = {"react_", "angular_", "vue_", "graphql_", "sequelize_", "prisma_"}
        assert any(t.startswith(p) for t in tables for p in prefixes)

    def test_jsx_file_returns_react_tables(self):
        """JSX file returns React tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("src/App.jsx")
        assert any(t.startswith("react_") for t in tables)
        assert any(t.startswith("graphql_") for t in tables)

    def test_vue_file_returns_vue_tables(self):
        """Vue file returns Vue tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("src/components/Modal.vue")
        assert all(t.startswith("vue_") for t in tables)

    def test_unknown_extension_returns_empty(self):
        """Unknown extension returns empty list."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("README.md")
        assert tables == []

    def test_results_are_sorted(self):
        """Results are sorted alphabetically."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("main.py")
        assert tables == sorted(tables)

    def test_no_duplicates_in_results(self):
        """Results contain no duplicates."""
        registry = SemanticTableRegistry()
        tables = registry.get_context_tables_for_file("app.tsx")
        assert len(tables) == len(set(tables))


class TestTableSetDisjoint:
    """Tests that table sets don't overlap."""

    def test_risk_and_process_disjoint(self):
        """RISK_SOURCES and CONTEXT_PROCESS are disjoint."""
        overlap = SemanticTableRegistry.RISK_SOURCES & SemanticTableRegistry.CONTEXT_PROCESS
        assert len(overlap) == 0

    def test_risk_and_structural_disjoint(self):
        """RISK_SOURCES and CONTEXT_STRUCTURAL are disjoint."""
        overlap = SemanticTableRegistry.RISK_SOURCES & SemanticTableRegistry.CONTEXT_STRUCTURAL
        assert len(overlap) == 0

    def test_risk_and_framework_disjoint(self):
        """RISK_SOURCES and CONTEXT_FRAMEWORK are disjoint."""
        overlap = SemanticTableRegistry.RISK_SOURCES & SemanticTableRegistry.CONTEXT_FRAMEWORK
        assert len(overlap) == 0

    def test_risk_and_security_disjoint(self):
        """RISK_SOURCES and CONTEXT_SECURITY are disjoint."""
        overlap = SemanticTableRegistry.RISK_SOURCES & SemanticTableRegistry.CONTEXT_SECURITY
        assert len(overlap) == 0

    def test_risk_and_language_disjoint(self):
        """RISK_SOURCES and CONTEXT_LANGUAGE are disjoint."""
        overlap = SemanticTableRegistry.RISK_SOURCES & SemanticTableRegistry.CONTEXT_LANGUAGE
        assert len(overlap) == 0

    def test_all_context_sets_disjoint(self):
        """All CONTEXT_* sets are mutually disjoint."""
        sets = [
            SemanticTableRegistry.CONTEXT_PROCESS,
            SemanticTableRegistry.CONTEXT_STRUCTURAL,
            SemanticTableRegistry.CONTEXT_FRAMEWORK,
            SemanticTableRegistry.CONTEXT_SECURITY,
            SemanticTableRegistry.CONTEXT_LANGUAGE,
        ]
        for i, s1 in enumerate(sets):
            for s2 in sets[i + 1 :]:
                overlap = s1 & s2
                assert len(overlap) == 0, f"Overlap found: {overlap}"


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_all_risk_tables(self):
        """get_all_risk_tables returns sorted list."""
        registry = SemanticTableRegistry()
        tables = registry.get_all_risk_tables()
        assert len(tables) == 7
        assert tables == sorted(tables)

    def test_get_all_context_tables(self):
        """get_all_context_tables returns all context tables."""
        registry = SemanticTableRegistry()
        tables = registry.get_all_context_tables()
        expected_count = (
            len(SemanticTableRegistry.CONTEXT_PROCESS)
            + len(SemanticTableRegistry.CONTEXT_STRUCTURAL)
            + len(SemanticTableRegistry.CONTEXT_FRAMEWORK)
            + len(SemanticTableRegistry.CONTEXT_SECURITY)
            + len(SemanticTableRegistry.CONTEXT_LANGUAGE)
        )
        assert len(tables) == expected_count
        assert tables == sorted(tables)

    def test_get_category_for_table_risk(self):
        """get_category_for_table returns RISK_SOURCES for risk tables."""
        registry = SemanticTableRegistry()
        assert registry.get_category_for_table("findings_consolidated") == "RISK_SOURCES"
        assert registry.get_category_for_table("taint_flows") == "RISK_SOURCES"

    def test_get_category_for_table_context(self):
        """get_category_for_table returns correct category for context tables."""
        registry = SemanticTableRegistry()
        assert registry.get_category_for_table("code_diffs") == "CONTEXT_PROCESS"
        assert registry.get_category_for_table("cfg_blocks") == "CONTEXT_STRUCTURAL"
        assert registry.get_category_for_table("react_components") == "CONTEXT_FRAMEWORK"
        assert registry.get_category_for_table("jwt_patterns") == "CONTEXT_SECURITY"
        assert registry.get_category_for_table("python_decorators") == "CONTEXT_LANGUAGE"

    def test_get_category_for_unknown_table(self):
        """get_category_for_table returns None for unknown tables."""
        registry = SemanticTableRegistry()
        assert registry.get_category_for_table("unknown_table") is None

    def test_total_categorized_tables(self):
        """total_categorized_tables returns correct count."""
        total = SemanticTableRegistry.total_categorized_tables()
        # 7 + 4 + 6 + 36 + 6 + 88 = 147
        assert total == 147
