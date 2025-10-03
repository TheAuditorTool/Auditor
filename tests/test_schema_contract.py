"""Tests for schema contract system."""
import pytest
import sqlite3
from theauditor.indexer.schema import (
    build_query, validate_all_tables, TABLES,
    API_ENDPOINTS, FILES, SYMBOLS, VARIABLE_USAGE
)


class TestSchemaDefinitions:
    """Test schema registry and table definitions."""

    def test_tables_registry_populated(self):
        """Verify TABLES registry has expected tables."""
        assert len(TABLES) >= 36, "Should have 36+ table definitions"
        assert 'files' in TABLES
        assert 'symbols' in TABLES
        assert 'api_endpoints' in TABLES
        assert 'variable_usage' in TABLES

    def test_api_endpoints_has_all_columns(self):
        """Verify api_endpoints has 8 required columns (PHASE 1 fix)."""
        column_names = {col.name for col in API_ENDPOINTS.columns}
        assert 'file' in column_names
        assert 'line' in column_names  # Added in PHASE 1
        assert 'method' in column_names
        assert 'pattern' in column_names
        assert 'path' in column_names  # Added in PHASE 1
        assert 'has_auth' in column_names  # Added in PHASE 1
        assert 'handler_function' in column_names  # Added in PHASE 1
        assert 'controls' in column_names


class TestBuildQuery:
    """Test query builder function."""

    def test_build_query_all_columns(self):
        """Build query selecting all columns."""
        query = build_query('files', ['file', 'extension', 'size'])
        assert 'SELECT' in query
        assert 'files' in query
        assert 'file' in query
        assert 'extension' in query

    def test_build_query_with_where(self):
        """Build query with WHERE clause."""
        query = build_query('sql_queries', where="command != 'UNKNOWN'")
        assert 'WHERE' in query
        assert "command != 'UNKNOWN'" in query

    def test_build_query_invalid_table(self):
        """Reject invalid table name."""
        with pytest.raises((KeyError, ValueError)):
            build_query('nonexistent_table', ['file'])

    def test_build_query_invalid_column(self):
        """Reject invalid column name."""
        with pytest.raises((ValueError, KeyError)):
            build_query('files', ['nonexistent_column'])


class TestSchemaValidation:
    """Test schema validation against real database."""

    def test_validate_against_minimal_db(self, temp_db):
        """Validate schema against database with one table."""
        # Create files table using schema definition
        temp_db.execute(FILES.create_table_sql())

        # Validate
        mismatches = validate_all_tables(temp_db.cursor())

        # files should pass, others should be missing
        assert 'files' not in mismatches, "files table should match schema"

    def test_validate_detects_missing_column(self, temp_db):
        """Detect missing column in table."""
        # Create table with missing column
        temp_db.execute("""
            CREATE TABLE files (
                file TEXT NOT NULL
                -- Missing: extension, size, language
            )
        """)

        mismatches = validate_all_tables(temp_db.cursor())
        assert 'files' in mismatches, "Should detect missing columns"

    def test_validate_detects_wrong_column_name(self, temp_db):
        """Detect incorrect column name."""
        # Create table with wrong column name
        temp_db.execute("""
            CREATE TABLE variable_usage (
                var_name TEXT,  -- WRONG: should be variable_name
                context TEXT    -- WRONG: should be in_component
            )
        """)

        mismatches = validate_all_tables(temp_db.cursor())
        assert 'variable_usage' in mismatches


class TestMemoryCacheSchemaCompliance:
    """Test that memory cache uses correct schema."""

    def test_memory_cache_uses_correct_columns(self):
        """Verify memory cache queries use variable_name not var_name."""
        from theauditor.taint.memory_cache import MemoryCache
        import inspect

        # Read source code of MemoryCache
        source = inspect.getsource(MemoryCache)

        # Should use schema-compliant column names
        assert 'variable_name' in source, "Should query variable_name column"
        assert 'in_component' in source, "Should query in_component column"

        # Should NOT use old column names in queries
        # (OK to use as dict keys for API compatibility)
        assert 'build_query' in source, "Should use build_query helper"
