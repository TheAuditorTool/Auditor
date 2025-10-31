"""Tests for GraphQL database operations.

Tests cover:
1. Schema creation (all 8 GraphQL tables)
2. Batch operations (add_graphql_* methods)
3. Foreign key constraints
4. Data retrieval and queries
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from theauditor.indexer.database import DatabaseManager


class TestGraphQLDatabaseSchema:
    """Test GraphQL table schema creation."""

    @pytest.fixture
    def db_manager(self):
        """Create temporary database with GraphQL tables."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_schema()
        yield manager
        manager.close()

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_graphql_tables_created(self, db_manager):
        """Verify all 8 GraphQL tables are created."""
        cursor = db_manager.conn.cursor()

        # Check table existence
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'graphql_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        assert 'graphql_schemas' in tables
        assert 'graphql_types' in tables
        assert 'graphql_fields' in tables
        assert 'graphql_field_args' in tables
        assert 'graphql_resolver_mappings' in tables
        assert 'graphql_resolver_params' in tables
        assert 'graphql_execution_edges' in tables
        assert 'graphql_findings_cache' in tables

        assert len([t for t in tables if t.startswith('graphql_')]) == 8

    def test_graphql_schemas_columns(self, db_manager):
        """Verify graphql_schemas table has correct columns."""
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA table_info(graphql_schemas)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'schema_id' in columns
        assert 'file_path' in columns
        assert 'schema_hash' in columns
        assert 'language' in columns
        assert 'last_modified' in columns

    def test_graphql_types_columns(self, db_manager):
        """Verify graphql_types table has correct columns."""
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA table_info(graphql_types)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'type_id' in columns
        assert 'schema_path' in columns
        assert 'type_name' in columns
        assert 'kind' in columns
        assert 'implements' in columns
        assert 'description' in columns
        assert 'line' in columns

    def test_graphql_fields_columns(self, db_manager):
        """Verify graphql_fields table has correct columns."""
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA table_info(graphql_fields)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'field_id' in columns
        assert 'type_id' in columns
        assert 'field_name' in columns
        assert 'return_type' in columns
        assert 'is_list' in columns
        assert 'is_nullable' in columns
        assert 'directives_json' in columns
        assert 'line' in columns

    def test_graphql_field_args_columns(self, db_manager):
        """Verify graphql_field_args table has correct columns."""
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA table_info(graphql_field_args)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'field_id' in columns
        assert 'arg_name' in columns
        assert 'arg_type' in columns
        assert 'is_nullable' in columns
        assert 'default_value' in columns
        assert 'directives_json' in columns

    def test_graphql_resolver_mappings_columns(self, db_manager):
        """Verify graphql_resolver_mappings table has correct columns."""
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA table_info(graphql_resolver_mappings)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'field_id' in columns
        assert 'resolver_symbol_id' in columns
        assert 'resolver_path' in columns
        assert 'resolver_line' in columns
        assert 'confidence' in columns


class TestGraphQLDatabaseOperations:
    """Test GraphQL database write operations."""

    @pytest.fixture
    def db_manager(self):
        """Create temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        manager = DatabaseManager(db_path)
        manager.create_schema()
        yield manager
        manager.close()

        Path(db_path).unlink(missing_ok=True)

    def test_add_graphql_schema(self, db_manager):
        """Test adding GraphQL schema entry."""
        schema_id = db_manager.add_graphql_schema(
            file_path='schema.graphql',
            schema_hash='abc123',
            language='graphql',
            last_modified=1234567890
        )

        assert schema_id is not None

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_schemas WHERE schema_id = ?", (schema_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == 'schema.graphql'  # file_path
        assert row[2] == 'abc123'  # schema_hash

    def test_add_graphql_type(self, db_manager):
        """Test adding GraphQL type."""
        type_id = db_manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='User',
            kind='object',
            implements=None,
            description='User type',
            line=10
        )

        assert type_id is not None

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_types WHERE type_id = ?", (type_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[2] == 'User'  # type_name
        assert row[3] == 'object'  # kind

    def test_add_graphql_field(self, db_manager):
        """Test adding GraphQL field."""
        # First add type
        type_id = db_manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Query',
            kind='object',
            implements=None,
            description=None,
            line=1
        )

        # Add field
        field_id = db_manager.add_graphql_field(
            type_id=type_id,
            field_name='user',
            return_type='User',
            is_list=False,
            is_nullable=True,
            directives_json=None,
            description=None,
            line=2
        )

        assert field_id is not None

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_fields WHERE field_id = ?", (field_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[2] == 'user'  # field_name
        assert row[3] == 'User'  # return_type

    def test_add_graphql_field_arg(self, db_manager):
        """Test adding field argument."""
        # Setup: type + field
        type_id = db_manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Query',
            kind='object',
            implements=None,
            description=None,
            line=1
        )

        field_id = db_manager.add_graphql_field(
            type_id=type_id,
            field_name='user',
            return_type='User',
            is_list=False,
            is_nullable=True,
            directives_json=None,
            description=None,
            line=2
        )

        # Add argument
        db_manager.add_graphql_field_arg(
            field_id=field_id,
            arg_name='id',
            arg_type='ID!',
            is_nullable=False,
            default_value=None,
            directives_json=None
        )

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_field_args WHERE field_id = ?", (field_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == 'id'  # arg_name
        assert row[2] == 'ID!'  # arg_type

    def test_add_graphql_resolver_mapping(self, db_manager):
        """Test adding resolver mapping."""
        # Setup: type + field + symbol
        type_id = db_manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Query',
            kind='object',
            implements=None,
            description=None,
            line=1
        )

        field_id = db_manager.add_graphql_field(
            type_id=type_id,
            field_name='user',
            return_type='User',
            is_list=False,
            is_nullable=True,
            directives_json=None,
            description=None,
            line=2
        )

        # Add fake symbol
        symbol_id = db_manager.add_symbol(
            name='resolve_user',
            type='function',
            file='resolvers.py',
            line=10,
            end_line=20,
            scope='module',
            raw_data='{}'
        )

        # Add resolver mapping
        db_manager.add_graphql_resolver_mapping(
            field_id=field_id,
            resolver_symbol_id=symbol_id,
            resolver_path='resolvers.py',
            resolver_line=10,
            confidence='high'
        )

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_resolver_mappings WHERE field_id = ?", (field_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == field_id  # field_id
        assert row[1] == symbol_id  # resolver_symbol_id

    def test_add_graphql_execution_edge(self, db_manager):
        """Test adding execution edge."""
        # Setup: type + field
        type_id = db_manager.add_graphql_type(
            schema_path='schema.graphql',
            type_name='Query',
            kind='object',
            implements=None,
            description=None,
            line=1
        )

        field_id = db_manager.add_graphql_field(
            type_id=type_id,
            field_name='user',
            return_type='User',
            is_list=False,
            is_nullable=True,
            directives_json=None,
            description=None,
            line=2
        )

        # Add fake target symbol
        target_symbol_id = db_manager.add_symbol(
            name='getUserById',
            type='function',
            file='services.py',
            line=50,
            end_line=60,
            scope='module',
            raw_data='{}'
        )

        # Add execution edge
        edge_id = db_manager.add_graphql_execution_edge(
            from_field_id=field_id,
            to_symbol_id=target_symbol_id,
            edge_kind='resolver_call'
        )

        assert edge_id is not None

        # Verify inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT * FROM graphql_execution_edges WHERE edge_id = ?", (edge_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == field_id  # from_field_id
        assert row[2] == target_symbol_id  # to_symbol_id

    def test_batch_operations(self, db_manager):
        """Test batch insert performance."""
        # Add 100 types
        type_ids = []
        for i in range(100):
            type_id = db_manager.add_graphql_type(
                schema_path='schema.graphql',
                type_name=f'Type{i}',
                kind='object',
                implements=None,
                description=None,
                line=i
            )
            type_ids.append(type_id)

        # Commit batch
        db_manager.commit()

        # Verify all inserted
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graphql_types")
        count = cursor.fetchone()[0]

        assert count == 100

    def test_foreign_key_constraints(self, db_manager):
        """Test that foreign key constraints are enforced."""
        # Try to add field with invalid type_id
        # Should fail or be handled gracefully depending on FK constraints

        # Note: SQLite FK constraints must be enabled explicitly
        # This test verifies the schema has FK definitions
        cursor = db_manager.conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(graphql_fields)")
        fks = cursor.fetchall()

        # Should have FK to graphql_types
        assert len(fks) > 0
        assert any('graphql_types' in str(fk) or 'type_id' in str(fk) for fk in fks)
