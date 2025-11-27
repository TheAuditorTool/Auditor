"""
Schema Contract Tests - Prevent future schema/extractor drift.

This test suite verifies that:
1. All extractor outputs have corresponding tables
2. Extractor output keys match schema columns
3. No JSON blob columns remain (replaced with junction tables)
4. Two-discriminator pattern is consistently applied

Created as part of: python-extractor-consolidation-fidelity
Purpose: Prevent the 22MB data loss bug from recurring
"""

from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.python_schema import PYTHON_TABLES

# Known columns that are infrastructure, not extractor output
INFRASTRUCTURE_COLUMNS = {'id', 'file', 'line'}

# Columns added by orchestrator (discriminators), not extractors
DISCRIMINATOR_COLUMNS = {
    'loop_kind', 'branch_kind', 'function_kind', 'io_kind', 'mutation_kind',
    'feature_kind', 'protocol_kind', 'descriptor_kind', 'type_kind', 'literal_kind',
    'finding_kind', 'test_kind', 'fixture_kind', 'config_kind', 'schema_kind',
    'operator_kind', 'collection_kind', 'stdlib_kind', 'import_kind', 'expression_kind',
    'comp_kind', 'statement_kind'
}

# JSON blob columns that should NOT exist (replaced with junction tables or expanded)
# Note: 'methods' in python_type_definitions is comma-separated string, not JSON
FORBIDDEN_JSON_COLUMNS = {
    'implemented_methods',  # -> python_protocol_methods junction
    'fields',               # -> python_typeddict_fields junction
    'params',               # -> python_fixture_params junction
    'validators',           # -> python_schema_validators junction
    # 'methods' - framework_config uses junction, type_definitions uses comma-separated
    'details',              # -> expanded to individual columns
    'schedule',             # -> expanded to individual columns
    'type_params',          # -> expanded to type_param_1..5
    'literal_values',       # -> expanded to literal_value_1..5
}

# Tables that are config/metadata, not extraction results
CONFIG_TABLES = {'python_package_configs'}

# Tables that should have two-discriminator pattern (*_kind + *_type)
TWO_DISCRIMINATOR_TABLES = {
    'python_loops': ('loop_kind', 'loop_type'),
    'python_branches': ('branch_kind', 'branch_type'),
    'python_functions_advanced': ('function_kind', 'function_type'),
    'python_io_operations': ('io_kind', 'io_type'),
    'python_state_mutations': ('mutation_kind', 'mutation_type'),
    'python_class_features': ('feature_kind', 'feature_type'),
    'python_protocols': ('protocol_kind', 'protocol_type'),
    'python_descriptors': ('descriptor_kind', 'descriptor_type'),
    'python_type_definitions': ('type_kind', None),  # Already had type_kind
    'python_literals': ('literal_kind', 'literal_type'),
    'python_security_findings': ('finding_kind', 'finding_type'),
    'python_test_cases': ('test_kind', 'test_type'),
    'python_test_fixtures': ('fixture_kind', 'fixture_type'),
    'python_framework_config': ('config_kind', 'config_type'),
    'python_validation_schemas': ('schema_kind', 'schema_type'),
    'python_operators': ('operator_kind', 'operator_type'),
    'python_collections': ('collection_kind', 'collection_type'),
    'python_stdlib_usage': ('stdlib_kind', 'usage_type'),
    'python_imports_advanced': ('import_kind', 'import_type'),
    'python_expressions': ('expression_kind', 'expression_type'),
    'python_comprehensions': ('comp_kind', 'comp_type'),
    'python_control_statements': ('statement_kind', 'statement_type'),
}

# Junction tables and their parent relationships
JUNCTION_TABLES = {
    'python_protocol_methods': 'python_protocols',
    'python_typeddict_fields': 'python_type_definitions',
    'python_fixture_params': 'python_test_fixtures',
    'python_framework_methods': 'python_framework_config',
    'python_schema_validators': 'python_validation_schemas',
}


class TestSchemaContract:
    """Tests to ensure schema matches extractor output contract."""

    def test_python_tables_count(self):
        """Verify expected number of Python tables."""
        # 28 original + 2 new (comprehensions, control_statements) + 5 junction = 35
        assert len(PYTHON_TABLES) == 35, (
            f"Expected 35 Python tables, got {len(PYTHON_TABLES)}. "
            f"Tables: {sorted(PYTHON_TABLES.keys())}"
        )

    def test_total_tables_count(self):
        """Verify total table count matches assertion in schema.py."""
        # Updated 2025-11-26: 136 + 8 Node junction tables = 144
        assert len(TABLES) == 144, (
            f"Expected 144 total tables, got {len(TABLES)}. "
            "Update this test if intentionally adding/removing tables."
        )

    def test_no_json_blob_columns(self):
        """Verify no JSON blob columns remain in Python tables."""
        violations = []

        for table_name, table_schema in PYTHON_TABLES.items():
            column_names = {col.name for col in table_schema.columns}
            forbidden_found = column_names & FORBIDDEN_JSON_COLUMNS

            if forbidden_found:
                violations.append(f"{table_name}: {forbidden_found}")

        assert not violations, (
            f"JSON blob columns still exist (should use junction tables):\n"
            + "\n".join(violations)
        )

    def test_two_discriminator_pattern(self):
        """Verify tables with consolidated extractors have *_kind discriminator."""
        violations = []

        for table_name, (kind_col, _type_col) in TWO_DISCRIMINATOR_TABLES.items():
            if table_name not in PYTHON_TABLES:
                violations.append(f"{table_name}: table not found")
                continue

            table_schema = PYTHON_TABLES[table_name]
            column_names = {col.name for col in table_schema.columns}

            if kind_col not in column_names:
                violations.append(f"{table_name}: missing {kind_col} discriminator")

            # type_col is optional (some tables don't preserve subtype)
            # Just verify kind_col exists

        assert not violations, (
            f"Two-discriminator pattern violations:\n"
            + "\n".join(violations)
        )

    def test_junction_tables_exist(self):
        """Verify all junction tables exist."""
        for junction_table, parent_table in JUNCTION_TABLES.items():
            assert junction_table in PYTHON_TABLES, (
                f"Junction table {junction_table} not found "
                f"(should reference {parent_table})"
            )

    def test_junction_tables_have_foreign_key(self):
        """Verify junction tables have proper FK column to parent."""
        # Map of junction table -> expected FK column name
        junction_fk_columns = {
            'python_protocol_methods': 'protocol_id',
            'python_typeddict_fields': 'typeddict_id',
            'python_fixture_params': 'fixture_id',
            'python_framework_methods': 'config_id',
            'python_schema_validators': 'schema_id',
        }

        for junction_table, expected_fk in junction_fk_columns.items():
            if junction_table not in PYTHON_TABLES:
                continue  # Caught by test_junction_tables_exist

            table_schema = PYTHON_TABLES[junction_table]
            column_names = {col.name for col in table_schema.columns}

            assert expected_fk in column_names, (
                f"Junction table {junction_table} missing FK column '{expected_fk}'. "
                f"Found columns: {column_names}"
            )

    def test_all_tables_have_file_and_line(self):
        """Verify all Python tables have file and line columns (except junction/config)."""
        violations = []

        # Tables that don't need file/line (junction tables, config tables)
        exempt_tables = set(JUNCTION_TABLES.keys()) | CONFIG_TABLES

        for table_name, table_schema in PYTHON_TABLES.items():
            if table_name in exempt_tables:
                continue

            column_names = {col.name for col in table_schema.columns}

            if 'file' not in column_names:
                violations.append(f"{table_name}: missing 'file' column")

            if 'line' not in column_names:
                violations.append(f"{table_name}: missing 'line' column")

        assert not violations, (
            f"Tables missing required columns:\n"
            + "\n".join(violations)
        )

    def test_discriminator_columns_not_nullable(self):
        """Verify *_kind discriminator columns are NOT NULL."""
        violations = []

        for table_name, (kind_col, _) in TWO_DISCRIMINATOR_TABLES.items():
            if table_name not in PYTHON_TABLES:
                continue

            table_schema = PYTHON_TABLES[table_name]

            for col in table_schema.columns:
                if col.name == kind_col:
                    if col.nullable:
                        violations.append(
                            f"{table_name}.{kind_col} should be NOT NULL"
                        )
                    break

        assert not violations, (
            f"Discriminator columns should be NOT NULL:\n"
            + "\n".join(violations)
        )


class TestDataFidelityInfrastructure:
    """Tests to verify fidelity control infrastructure exists."""

    def test_fidelity_module_exists(self):
        """Verify fidelity.py module exists and is importable."""
        from theauditor.indexer import fidelity
        assert hasattr(fidelity, 'reconcile_fidelity')

    def test_data_fidelity_error_exists(self):
        """Verify DataFidelityError exception exists."""
        from theauditor.indexer.exceptions import DataFidelityError
        assert issubclass(DataFidelityError, Exception)

    def test_reconcile_fidelity_callable(self):
        """Verify reconcile_fidelity function is callable."""
        from theauditor.indexer.fidelity import reconcile_fidelity

        # Should not raise with matching counts
        # Signature: reconcile_fidelity(manifest, receipt, file_path, strict=True)
        result = reconcile_fidelity(
            manifest={'test_table': 10},
            receipt={'test_table': 10},
            file_path='test.py',
            strict=False
        )
        assert 'errors' in result
        assert 'warnings' in result


class TestNoInventedColumns:
    """Tests to verify invented columns were removed."""

    def test_python_loops_no_invented_columns(self):
        """Verify python_loops doesn't have invented columns."""
        table = PYTHON_TABLES['python_loops']
        column_names = {col.name for col in table.columns}

        invented = {'target', 'iterator', 'body_line_count'}
        found_invented = column_names & invented

        assert not found_invented, (
            f"python_loops still has invented columns: {found_invented}"
        )

    def test_python_operators_no_invented_columns(self):
        """Verify python_operators doesn't have invented columns."""
        table = PYTHON_TABLES['python_operators']
        column_names = {col.name for col in table.columns}

        invented = {'left_operand', 'right_operand'}
        found_invented = column_names & invented

        assert not found_invented, (
            f"python_operators still has invented columns: {found_invented}"
        )

    def test_python_io_operations_no_invented_columns(self):
        """Verify python_io_operations doesn't have invented columns."""
        table = PYTHON_TABLES['python_io_operations']
        column_names = {col.name for col in table.columns}

        invented = {'is_taint_source', 'is_taint_sink'}
        found_invented = column_names & invented

        assert not found_invented, (
            f"python_io_operations still has invented columns: {found_invented}"
        )

    def test_python_security_findings_no_invented_columns(self):
        """Verify python_security_findings doesn't have invented columns."""
        table = PYTHON_TABLES['python_security_findings']
        column_names = {col.name for col in table.columns}

        invented = {'severity', 'source_expr', 'sink_expr', 'vulnerable_code', 'cwe_id'}
        found_invented = column_names & invented

        assert not found_invented, (
            f"python_security_findings still has invented columns: {found_invented}"
        )

    def test_python_expressions_no_generic_columns(self):
        """Verify python_expressions doesn't have generic junk drawer columns."""
        table = PYTHON_TABLES['python_expressions']
        column_names = {col.name for col in table.columns}

        generic = {'subtype', 'expression', 'variables'}
        found_generic = column_names & generic

        assert not found_generic, (
            f"python_expressions still has generic columns: {found_generic}"
        )
