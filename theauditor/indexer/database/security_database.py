"""Security-focused database operations.

This module contains add_* methods for SECURITY_TABLES defined in schemas/security_schema.py.
Handles 5 security tables including SQL injection detection, JWT patterns, and environment variable usage.
"""

from typing import List, Optional


class SecurityDatabaseMixin:
    """Mixin providing add_* methods for SECURITY_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    # ========================================================
    # SQL SECURITY BATCH METHODS
    # ========================================================

    def add_sql_object(self, file_path: str, kind: str, name: str):
        """Add a SQL object record to the batch."""
        self.generic_batches['sql_objects'].append((file_path, kind, name))

    def add_sql_query(self, file_path: str, line: int, query_text: str, command: str, tables: List[str],
                      extraction_source: str = 'code_execute'):
        """Add a SQL query record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch SQL query record (without tables column)
        - Phase 2: Batch junction records for each table referenced

        Args:
            file_path: Path to the file containing the query
            line: Line number
            query_text: SQL query text
            command: SQL command type (SELECT, INSERT, etc.)
            tables: List of table names referenced
            extraction_source: Source of extraction - one of:
                - 'code_execute': Direct db.execute() calls (HIGH priority for SQL injection)
                - 'orm_query': ORM method calls (MEDIUM priority, usually parameterized)
                - 'migration_file': Database migration files (LOW priority, DDL only)

        NO FALLBACKS. If tables is malformed, hard fail.
        """
        # Phase 1: Add SQL query record (5 params, no tables column)
        self.generic_batches['sql_queries'].append((file_path, line, query_text, command, extraction_source))

        # Phase 2: Add junction records for each table referenced
        if tables:
            for table_name in tables:
                if not table_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['sql_query_tables'].append((file_path, line, table_name))

    # ========================================================
    # ENVIRONMENT VARIABLE SECURITY BATCH METHODS
    # ========================================================

    def add_env_var_usage(self, file: str, line: int, var_name: str, access_type: str,
                         in_function: Optional[str] = None, property_access: Optional[str] = None):
        """Add an environment variable usage record to the batch.

        Args:
            file: File containing the env var access
            line: Line number of the access
            var_name: Name of the environment variable (e.g., "NODE_ENV", "DATABASE_URL")
            access_type: Type of access - "read", "write", or "check"
            in_function: Name of the function containing this access
            property_access: Full property access expression (e.g., "process.env.NODE_ENV")
        """
        self.generic_batches['env_var_usage'].append((
            file, line, var_name, access_type, in_function, property_access
        ))

    # ========================================================
    # JWT SECURITY BATCH METHODS
    # ========================================================

    def add_jwt_pattern(self, file_path, line_number, pattern_type,
                        pattern_text, secret_source, algorithm=None):
        """Add JWT pattern detection.

        KEPT FOR BACKWARD COMPATIBILITY: Uses dict-based interface.
        """
        self.jwt_patterns_batch.append({
            'file_path': file_path,
            'line_number': line_number,
            'pattern_type': pattern_type,
            'pattern_text': pattern_text,
            'secret_source': secret_source,
            'algorithm': algorithm
        })
        if len(self.jwt_patterns_batch) >= self.batch_size:
            self._flush_jwt_patterns()
