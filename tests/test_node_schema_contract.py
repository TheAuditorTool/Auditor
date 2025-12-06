"""
Node Schema Contract Tests - Prevent schema drift for Node/JS/TS tables.

This test suite verifies that:
1. All 8 junction tables exist and are registered
2. JSON blob columns have been removed (regression guard)
3. Junction table structures match specification
4. Database dispatcher methods exist
5. Generic batches accept new table keys

Created as part of: node-schema-normalization
Purpose: Lock in the JSON blob -> junction table migration
"""

import pytest

from theauditor.indexer.database.node_database import NodeDatabaseMixin
from theauditor.indexer.schemas.node_schema import (
    ANGULAR_COMPONENT_STYLES,
    ANGULAR_COMPONENTS,
    ANGULAR_MODULE_DECLARATIONS,
    ANGULAR_MODULE_EXPORTS,
    ANGULAR_MODULE_IMPORTS,
    ANGULAR_MODULE_PROVIDERS,
    ANGULAR_MODULES,
    NODE_TABLES,
    VUE_COMPONENT_EMITS,
    VUE_COMPONENT_PROPS,
    VUE_COMPONENT_SETUP_RETURNS,
    VUE_COMPONENTS,
)


NODE_JUNCTION_TABLES = {
    "vue_component_props",
    "vue_component_emits",
    "vue_component_setup_returns",
    "angular_component_styles",
    "angular_module_declarations",
    "angular_module_imports",
    "angular_module_providers",
    "angular_module_exports",
}


FORBIDDEN_NODE_JSON_COLUMNS = {
    "props_definition",
    "emits_definition",
    "setup_return",
    "style_paths",
    "declarations",
    "imports",
    "providers",
    "exports",
}


JUNCTION_TABLE_COLUMNS = {
    "vue_component_props": [
        "file",
        "component_name",
        "prop_name",
        "prop_type",
        "is_required",
        "default_value",
    ],
    "vue_component_emits": ["file", "component_name", "emit_name", "payload_type"],
    "vue_component_setup_returns": ["file", "component_name", "return_name", "return_type"],
    "angular_component_styles": ["file", "component_name", "style_path"],
    "angular_module_declarations": ["file", "module_name", "declaration_name", "declaration_type"],
    "angular_module_imports": ["file", "module_name", "imported_module"],
    "angular_module_providers": ["file", "module_name", "provider_name", "provider_type"],
    "angular_module_exports": ["file", "module_name", "exported_name"],
}


JUNCTION_DISPATCHER_METHODS = [
    "add_vue_component_prop",
    "add_vue_component_emit",
    "add_vue_component_setup_return",
    "add_angular_component_style",
    "add_angular_module_declaration",
    "add_angular_module_import",
    "add_angular_module_provider",
    "add_angular_module_export",
]


class TestNodeTableRegistry:
    """Tests to verify Node tables are properly registered."""

    def test_node_tables_count(self):
        """Verify expected number of Node tables (39 original + 8 junction + 4 package junction = 51)."""
        assert len(NODE_TABLES) == 51, (
            f"Expected 51 Node tables, got {len(NODE_TABLES)}. Tables: {sorted(NODE_TABLES.keys())}"
        )

    def test_junction_tables_registered(self):
        """Verify all 8 junction tables are in NODE_TABLES registry."""
        missing = NODE_JUNCTION_TABLES - set(NODE_TABLES.keys())
        assert not missing, f"Junction tables missing from NODE_TABLES registry: {missing}"

    def test_junction_tables_not_duplicated(self):
        """Verify junction tables are registered exactly once."""

        table_names = list(NODE_TABLES.keys())
        for junction_table in NODE_JUNCTION_TABLES:
            count = table_names.count(junction_table)
            assert count == 1, f"Junction table {junction_table} appears {count} times in registry"


class TestNoJsonBlobColumns:
    """Regression guard - ensure JSON blob columns stay removed."""

    def test_vue_components_no_json_blobs(self):
        """Verify vue_components has no JSON blob columns."""
        column_names = {col.name for col in VUE_COMPONENTS.columns}
        forbidden_found = column_names & {"props_definition", "emits_definition", "setup_return"}

        assert not forbidden_found, (
            f"vue_components still has JSON blob columns: {forbidden_found}. "
            "These should be in junction tables."
        )

    def test_angular_components_no_json_blobs(self):
        """Verify angular_components has no JSON blob columns."""
        column_names = {col.name for col in ANGULAR_COMPONENTS.columns}
        forbidden_found = column_names & {"style_paths"}

        assert not forbidden_found, (
            f"angular_components still has JSON blob columns: {forbidden_found}. "
            "These should be in angular_component_styles junction table."
        )

    def test_angular_modules_no_json_blobs(self):
        """Verify angular_modules has no JSON blob columns."""
        column_names = {col.name for col in ANGULAR_MODULES.columns}
        forbidden_found = column_names & {"declarations", "imports", "providers", "exports"}

        assert not forbidden_found, (
            f"angular_modules still has JSON blob columns: {forbidden_found}. "
            "These should be in angular_module_* junction tables."
        )

    def test_no_json_blobs_in_all_node_tables(self):
        """Comprehensive check - no forbidden JSON columns in any Node table."""
        violations = []

        for table_name, table_schema in NODE_TABLES.items():
            column_names = {col.name for col in table_schema.columns}
            forbidden_found = column_names & FORBIDDEN_NODE_JSON_COLUMNS

            if forbidden_found:
                violations.append(f"{table_name}: {forbidden_found}")

        assert not violations, (
            "JSON blob columns found in Node tables (should use junction tables):\n"
            + "\n".join(violations)
        )


class TestJunctionTableStructures:
    """Tests to verify junction table column structures."""

    def test_vue_component_props_columns(self):
        """Verify vue_component_props has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["vue_component_props"]
        actual = [col.name for col in VUE_COMPONENT_PROPS.columns]

        assert actual == expected, (
            f"vue_component_props columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_vue_component_emits_columns(self):
        """Verify vue_component_emits has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["vue_component_emits"]
        actual = [col.name for col in VUE_COMPONENT_EMITS.columns]

        assert actual == expected, (
            f"vue_component_emits columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_vue_component_setup_returns_columns(self):
        """Verify vue_component_setup_returns has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["vue_component_setup_returns"]
        actual = [col.name for col in VUE_COMPONENT_SETUP_RETURNS.columns]

        assert actual == expected, (
            f"vue_component_setup_returns columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_angular_component_styles_columns(self):
        """Verify angular_component_styles has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["angular_component_styles"]
        actual = [col.name for col in ANGULAR_COMPONENT_STYLES.columns]

        assert actual == expected, (
            f"angular_component_styles columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_angular_module_declarations_columns(self):
        """Verify angular_module_declarations has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["angular_module_declarations"]
        actual = [col.name for col in ANGULAR_MODULE_DECLARATIONS.columns]

        assert actual == expected, (
            f"angular_module_declarations columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_angular_module_imports_columns(self):
        """Verify angular_module_imports has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["angular_module_imports"]
        actual = [col.name for col in ANGULAR_MODULE_IMPORTS.columns]

        assert actual == expected, (
            f"angular_module_imports columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_angular_module_providers_columns(self):
        """Verify angular_module_providers has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["angular_module_providers"]
        actual = [col.name for col in ANGULAR_MODULE_PROVIDERS.columns]

        assert actual == expected, (
            f"angular_module_providers columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_angular_module_exports_columns(self):
        """Verify angular_module_exports has correct columns."""
        expected = JUNCTION_TABLE_COLUMNS["angular_module_exports"]
        actual = [col.name for col in ANGULAR_MODULE_EXPORTS.columns]

        assert actual == expected, (
            f"angular_module_exports columns mismatch.\nExpected: {expected}\nActual: {actual}"
        )

    def test_all_junction_tables_have_file_column(self):
        """Verify all junction tables have 'file' as first column."""
        violations = []

        for table_name in NODE_JUNCTION_TABLES:
            table_schema = NODE_TABLES[table_name]
            columns = [col.name for col in table_schema.columns]

            if not columns or columns[0] != "file":
                violations.append(
                    f"{table_name}: first column is '{columns[0] if columns else 'EMPTY'}', expected 'file'"
                )

        assert not violations, "Junction tables missing 'file' as first column:\n" + "\n".join(
            violations
        )


class TestDatabaseDispatcherMethods:
    """Tests to verify database mixin has the dispatcher methods."""

    def test_junction_dispatcher_methods_exist(self):
        """Verify all 8 junction add_* methods exist in NodeDatabaseMixin."""
        missing = []

        for method_name in JUNCTION_DISPATCHER_METHODS:
            if not hasattr(NodeDatabaseMixin, method_name):
                missing.append(method_name)

        assert not missing, f"NodeDatabaseMixin missing dispatcher methods: {missing}"

    def test_dispatcher_methods_are_callable(self):
        """Verify dispatcher methods are callable (not properties)."""
        for method_name in JUNCTION_DISPATCHER_METHODS:
            method = getattr(NodeDatabaseMixin, method_name, None)
            assert callable(method), f"NodeDatabaseMixin.{method_name} is not callable"

    def test_parent_methods_still_exist(self):
        """Verify parent add_* methods still exist after refactoring."""
        parent_methods = [
            "add_vue_component",
            "add_angular_component",
            "add_angular_module",
        ]

        for method_name in parent_methods:
            assert hasattr(NodeDatabaseMixin, method_name), (
                f"NodeDatabaseMixin missing parent method: {method_name}"
            )


class TestGenericBatchesConfiguration:
    """Tests to verify generic_batches accepts new table keys."""

    def test_generic_batches_accepts_junction_keys(self):
        """Verify DatabaseManager's generic_batches accepts junction table keys."""
        from theauditor.indexer.database import DatabaseManager

        manager = DatabaseManager(":memory:")

        assert hasattr(manager, "generic_batches"), (
            "DatabaseManager missing generic_batches attribute"
        )

        for table_name in NODE_JUNCTION_TABLES:
            try:
                manager.generic_batches[table_name].append(("test",))
            except KeyError as e:
                pytest.fail(f"generic_batches rejected key '{table_name}': {e}")

        for table_name in NODE_JUNCTION_TABLES:
            assert len(manager.generic_batches[table_name]) == 1, (
                f"Data not appended to generic_batches['{table_name}']"
            )

        manager.close()

    def test_parent_table_columns_reduced(self):
        """Verify parent tables have fewer columns after JSON removal."""

        vue_cols = len(VUE_COMPONENTS.columns)
        assert vue_cols == 8, f"vue_components should have 8 columns (JSON removed), got {vue_cols}"

        angular_comp_cols = len(ANGULAR_COMPONENTS.columns)
        assert angular_comp_cols == 6, (
            f"angular_components should have 6 columns (style_paths removed), got {angular_comp_cols}"
        )

        angular_mod_cols = len(ANGULAR_MODULES.columns)
        assert angular_mod_cols == 3, (
            f"angular_modules should have 3 columns (JSON arrays removed), got {angular_mod_cols}"
        )


class TestSchemaContractIntegrity:
    """Cross-cutting tests to verify overall schema integrity."""

    def test_total_table_count_updated(self):
        """Verify global TABLES count was updated for new junction tables."""
        from theauditor.indexer.schema import TABLES

        assert len(TABLES) == 170, (
            f"Expected 170 total tables (155 + 15 JSON normalization junction), got {len(TABLES)}. "
            "Update schema.py assertion if intentionally changing table count."
        )

    def test_junction_tables_have_indexes(self):
        """Verify junction tables have at least one index."""
        violations = []

        for table_name in NODE_JUNCTION_TABLES:
            table_schema = NODE_TABLES[table_name]
            if not table_schema.indexes:
                violations.append(f"{table_name}: no indexes defined")

        assert not violations, "Junction tables missing indexes:\n" + "\n".join(violations)

    def test_junction_tables_have_file_index(self):
        """Verify junction tables have index on file column."""
        violations = []

        for table_name in NODE_JUNCTION_TABLES:
            table_schema = NODE_TABLES[table_name]
            index_columns = {col for idx_name, cols in table_schema.indexes for col in cols}

            if "file" not in index_columns:
                violations.append(f"{table_name}: no index on 'file' column")

        assert not violations, "Junction tables missing file index:\n" + "\n".join(violations)
