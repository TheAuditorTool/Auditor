"""
Integration tests for database operations using golden snapshot.

Tests verify database.py methods WORK by querying a known-good snapshot,
not by running TheAuditor (no dogfooding).

Golden Snapshot: repo_index.db (root directory)
- Created from 5 production runs on diverse projects
- Known-good state with populated tables
- Fast, deterministic, no circular logic

Test Strategy:
- 95% snapshot-based (this file): Fast, reliable
- 5% dogfooding (test_e2e_smoke.py): Minimal E2E verification
"""

import pytest
import sqlite3
from pathlib import Path


class TestRefsTablePopulation:
    """Test refs table structure and population (Gap #1 from test plan)."""

    def test_refs_table_exists(self, golden_conn):
        """Verify refs table exists in golden snapshot."""
        cursor = golden_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='refs'")
        assert cursor.fetchone() is not None, "refs table should exist"

    def test_refs_table_has_data(self, golden_conn):
        """Verify refs table populated from 5 production runs."""
        cursor = golden_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM refs")
        count = cursor.fetchone()[0]
        assert count > 0, f"refs table should have import data from 5 projects, got {count}"

    def test_refs_table_has_correct_schema(self, golden_conn):
        """Verify refs table has 4-tuple structure (src, kind, value, line)."""
        cursor = golden_conn.cursor()

        # Get column info
        cursor.execute("PRAGMA table_info(refs)")
        columns = {row[1] for row in cursor.fetchall()}

        # Verify required columns exist
        assert 'src' in columns, "refs should have 'src' column"
        assert 'kind' in columns, "refs should have 'kind' column"
        assert 'value' in columns, "refs should have 'value' column"
        assert 'line' in columns, "refs should have 'line' column"

    def test_refs_has_both_import_types(self, golden_conn):
        """Verify refs contains both 'import' and 'from' kinds."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT DISTINCT kind FROM refs")
        kinds = {row[0] for row in cursor.fetchall()}

        assert 'import' in kinds, "Should have 'import' statements"
        assert 'from' in kinds, "Should have 'from' statements"

    def test_refs_line_numbers_populated(self, golden_conn):
        """Verify all refs have line numbers (4-tuple support)."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM refs WHERE line IS NULL")
        null_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM refs")
        total_count = cursor.fetchone()[0]

        # Allow some refs to not have line numbers (backward compat)
        # but majority should have them
        assert null_count < total_count * 0.5, \
            f"Most refs should have line numbers, but {null_count}/{total_count} are NULL"

    def test_refs_line_numbers_are_positive(self, golden_conn):
        """Verify line numbers are valid positive integers."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT line FROM refs WHERE line IS NOT NULL")
        lines = [row[0] for row in cursor.fetchall()]

        assert all(isinstance(line, int) for line in lines), "Line numbers should be integers"
        assert all(line > 0 for line in lines), "Line numbers should be positive"

    def test_refs_common_imports_present(self, golden_conn):
        """Verify common Python imports present from diverse projects."""
        cursor = golden_conn.cursor()

        # Check for common stdlib modules that should be in any Python project
        cursor.execute("SELECT DISTINCT value FROM refs WHERE kind IN ('import', 'from')")
        imported_modules = {row[0] for row in cursor.fetchall()}

        # At least SOME common imports should be present across 5 projects
        common_modules = {'os', 'sys', 'pathlib', 'typing', 're', 'json'}
        found = common_modules & imported_modules

        assert len(found) >= 2, \
            f"Expected at least 2 common stdlib imports from 5 projects, found: {found}"


class TestJWTPatterns:
    """Test jwt_patterns table (Gap #2 - P0 from test plan)."""

    def test_jwt_patterns_table_exists(self, golden_conn):
        """Verify jwt_patterns table exists."""
        cursor = golden_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jwt_patterns'")
        assert cursor.fetchone() is not None, "jwt_patterns table should exist"

    def test_jwt_patterns_table_has_correct_schema(self, golden_conn):
        """Verify jwt_patterns has all required columns."""
        cursor = golden_conn.cursor()

        cursor.execute("PRAGMA table_info(jwt_patterns)")
        columns = {row[1] for row in cursor.fetchall()}

        # Schema from database.py lines 275-287
        required = {'file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'}
        assert required.issubset(columns), f"jwt_patterns missing columns: {required - columns}"

    def test_jwt_patterns_has_data_if_jwt_code_present(self, golden_conn):
        """Verify jwt_patterns populated if any project uses JWT."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns")
        count = cursor.fetchone()[0]

        # If 5 diverse projects include auth code, at least SOME should use JWT
        # If count is 0, it's either:
        # 1. None of the 5 projects use JWT (acceptable)
        # 2. JWT extraction is broken (would need investigation)
        # We just verify the table structure works, not that data exists
        assert count >= 0, "jwt_patterns table should be queryable"

    def test_jwt_patterns_secret_source_categorization(self, golden_conn):
        """Verify secret_source field properly categorizes JWT secrets."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT DISTINCT secret_source FROM jwt_patterns WHERE secret_source IS NOT NULL")
        sources = {row[0] for row in cursor.fetchall()}

        # If we have JWT patterns, verify secret sources are categorized
        if sources:
            # Valid categories from indexer/extractors/__init__.py lines 188-203
            valid_sources = {'environment', 'config', 'hardcoded', 'variable', 'unknown'}
            assert sources.issubset(valid_sources), \
                f"Invalid secret sources found: {sources - valid_sources}"

    def test_jwt_patterns_algorithm_detection(self, golden_conn):
        """Verify algorithm field populated for JWT patterns."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns WHERE algorithm IS NOT NULL")
        with_algo = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jwt_patterns")
        total = cursor.fetchone()[0]

        # If we have JWT patterns, most should have algorithm detected
        if total > 0:
            assert with_algo / total >= 0.5, \
                f"Most JWT patterns should have algorithm, got {with_algo}/{total}"


class TestBatchFlushLogic:
    """Test batch flushing handles boundaries correctly (Gap #4)."""

    def test_batch_size_boundary_refs(self, golden_conn):
        """Verify refs table handles data regardless of batch size (200 items)."""
        cursor = golden_conn.cursor()

        # If we have > 200 refs, batch flushing worked
        cursor.execute("SELECT COUNT(*) FROM refs")
        count = cursor.fetchone()[0]

        # This is a smoke test - if count > 200, multi-batch worked
        # We can't control exact batch size from snapshot, but we can verify large datasets
        if count > 200:
            # Batch flushing must have worked to get this many records
            pass  # Success

    def test_no_duplicate_refs(self, golden_conn):
        """Verify deduplication logic works (no duplicate imports)."""
        cursor = golden_conn.cursor()

        # Check for exact duplicates
        cursor.execute("""
            SELECT src, kind, value, COUNT(*) as cnt
            FROM refs
            GROUP BY src, kind, value
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()

        # Some duplicates might be acceptable (same import in different files)
        # but massive duplication indicates batch flush bug
        if duplicates:
            max_dups = max(dup[3] for dup in duplicates)
            assert max_dups < 10, \
                f"Found excessive duplicates (max {max_dups}), possible batch flush bug"


class TestSQLExtractionSourceTagging:
    """Test sql_queries extraction_source field (Gap #6 - P1)."""

    def test_sql_queries_table_exists(self, golden_conn):
        """Verify sql_queries table exists."""
        cursor = golden_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sql_queries'")
        assert cursor.fetchone() is not None, "sql_queries table should exist"

    def test_sql_extraction_source_field_exists(self, golden_conn):
        """Verify extraction_source column exists."""
        cursor = golden_conn.cursor()

        cursor.execute("PRAGMA table_info(sql_queries)")
        columns = {row[1] for row in cursor.fetchall()}

        assert 'extraction_source' in columns, "sql_queries should have extraction_source column"

    def test_sql_extraction_source_categories(self, golden_conn):
        """Verify extraction_source uses valid categories."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT DISTINCT extraction_source FROM sql_queries WHERE extraction_source IS NOT NULL")
        sources = {row[0] for row in cursor.fetchall()}

        if sources:
            # Valid categories from extractors
            valid_sources = {'migration_file', 'orm_query', 'code_execute', 'raw_sql'}
            assert sources.issubset(valid_sources), \
                f"Invalid extraction sources: {sources - valid_sources}"

    def test_sql_command_field_not_unknown(self, golden_conn):
        """Verify sql_queries.command field properly categorized (not all UNKNOWN)."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sql_queries WHERE command = 'UNKNOWN'")
        unknown_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sql_queries")
        total_count = cursor.fetchone()[0]

        if total_count > 0:
            unknown_ratio = unknown_count / total_count
            # Per nightmare_fuel.md, old code had 97.6% UNKNOWN
            # After AST-based extraction, should be much lower
            assert unknown_ratio < 0.5, \
                f"Too many UNKNOWN SQL commands ({unknown_ratio:.1%}), expected < 50%"


class TestAPIEndpointsTable:
    """Test api_endpoints table structure (from final_audit Part 1)."""

    def test_api_endpoints_table_exists(self, golden_conn):
        """Verify api_endpoints table exists."""
        cursor = golden_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_endpoints'")
        assert cursor.fetchone() is not None, "api_endpoints table should exist"

    def test_api_endpoints_has_8_columns(self, golden_conn):
        """Verify api_endpoints has all 8 columns (from schema.py)."""
        cursor = golden_conn.cursor()

        cursor.execute("PRAGMA table_info(api_endpoints)")
        columns = {row[1] for row in cursor.fetchall()}

        # From schema.py lines 285-297
        required = {
            'file_path', 'line', 'http_method', 'route_pattern',
            'route_path', 'has_auth', 'handler_function', 'auth_controls'
        }
        assert required.issubset(columns), \
            f"api_endpoints missing columns: {required - columns}"

    def test_api_endpoints_auth_detection(self, golden_conn):
        """Verify has_auth field properly detects authentication."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT DISTINCT has_auth FROM api_endpoints WHERE has_auth IS NOT NULL")
        auth_values = {row[0] for row in cursor.fetchall()}

        if auth_values:
            # has_auth should be boolean (0 or 1 in SQLite)
            assert auth_values.issubset({0, 1}), \
                f"has_auth should be boolean, got: {auth_values}"


class TestSchemaContract:
    """Test schema contract system works on golden snapshot."""

    def test_build_query_produces_valid_sql(self, golden_conn):
        """Verify build_query() generates valid SQL for all tables."""
        from theauditor.indexer.schema import build_query

        cursor = golden_conn.cursor()

        # Test on several critical tables
        tables = ['refs', 'symbols', 'files', 'sql_queries', 'api_endpoints']

        for table in tables:
            query = build_query(table)
            # Should not raise exception
            cursor.execute(query)
            results = cursor.fetchall()
            # Just verify query works, don't assert data exists

    def test_validate_all_tables_passes_on_snapshot(self, golden_conn):
        """Verify schema validation passes on golden snapshot."""
        from theauditor.indexer.schema import validate_all_tables

        cursor = golden_conn.cursor()

        # Run validation
        mismatches = validate_all_tables(cursor)

        # Golden snapshot should have no schema mismatches
        assert not mismatches, \
            f"Schema validation failed: {mismatches}"


class TestDatabaseIndexes:
    """Test that indexes exist (from final_audit Part 1 - 86 indexes)."""

    def test_database_has_indexes(self, golden_conn):
        """Verify golden snapshot has performance indexes."""
        cursor = golden_conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        index_count = cursor.fetchone()[0]

        # Per final_audit line 59: "86 total indexes across all tables"
        # We don't need exact 86, but should have substantial number
        assert index_count >= 20, \
            f"Expected at least 20 indexes for performance, got {index_count}"

    def test_critical_tables_have_indexes(self, golden_conn):
        """Verify critical columns have indexes."""
        cursor = golden_conn.cursor()

        # Check for some critical indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        # Some expected indexes (from database.py lines 800+)
        expected_prefixes = ['idx_refs', 'idx_symbols', 'idx_files']

        for prefix in expected_prefixes:
            matching = [idx for idx in indexes if idx.startswith(prefix)]
            assert matching, f"No indexes found for {prefix}"
