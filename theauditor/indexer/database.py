"""Database operations for the indexer.

This module contains the DatabaseManager class which handles all database
operations including schema creation, batch inserts, and transaction management.

ARCHITECTURE: Schema-Driven Database Layer
- schema.py is the Single Source of Truth for all table definitions
- This module consumes schema.py TABLES registry to generate SQL dynamically
- NO hardcoded CREATE TABLE or INSERT statements (except CFG special case)
- Generic batching system replaces 58 individual batch lists

CRITICAL ARCHITECTURE RULE: NO FALLBACKS ALLOWED.
The database is generated fresh every run. It MUST exist and MUST be correct.
NO graceful degradation, NO try/except around schema operations, NO migrations.
Hard failure is the only acceptable behavior for missing data or schema errors.
"""

import sqlite3
import json
import os
from typing import Any, List, Dict, Optional
from pathlib import Path
from collections import defaultdict

from .config import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE
from .schema import TABLES, get_table_schema


class DatabaseManager:
    """Manages database operations with schema-driven batching and transactions.

    This class implements a generic batching system that consumes schema.py
    as the single source of truth for all table definitions and operations.
    """

    def __init__(self, db_path: str, batch_size: int = DEFAULT_BATCH_SIZE):
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file
            batch_size: Size of batches for insert operations
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

        # Validate and set batch size
        if batch_size <= 0:
            self.batch_size = DEFAULT_BATCH_SIZE
        elif batch_size > MAX_BATCH_SIZE:
            self.batch_size = MAX_BATCH_SIZE
        else:
            self.batch_size = batch_size

        # Generic batch system: {table_name: [tuple, tuple, ...]}
        # Replaces 58 individual batch lists with single dictionary
        self.generic_batches: Dict[str, List[tuple]] = defaultdict(list)

        # CFG special case: ID mapping for AUTOINCREMENT
        # Maps temporary negative IDs to real database IDs
        self.cfg_id_mapping: Dict[int, int] = {}

        # JWT special case: Batch list for dict-based interface
        # Kept for backward compatibility with add_jwt_pattern signature
        self.jwt_patterns_batch: List[Dict] = []

    def begin_transaction(self):
        """Start a new transaction."""
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        """Commit the current transaction."""
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to commit database changes: {e}")

    def rollback(self):
        """Rollback the current transaction."""
        self.conn.rollback()

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def validate_schema(self) -> bool:
        """
        Validate database schema matches expected definitions.

        Runs after indexing to ensure all tables were created correctly.
        Logs warnings for any mismatches.

        Returns:
            True if all schemas valid, False if mismatches found
        """
        from .schema import validate_all_tables
        import sys

        cursor = self.conn.cursor()
        mismatches = validate_all_tables(cursor)

        if not mismatches:
            print("[SCHEMA] All table schemas validated successfully", file=sys.stderr)
            return True

        print("[SCHEMA] Schema validation warnings detected:", file=sys.stderr)
        for table_name, errors in mismatches.items():
            print(f"[SCHEMA]   Table: {table_name}", file=sys.stderr)
            for error in errors:
                print(f"[SCHEMA]     - {error}", file=sys.stderr)

        print("[SCHEMA] Note: Some mismatches may be due to migration columns (expected)", file=sys.stderr)
        return False

    def create_schema(self):
        """Create all database tables and indexes using schema.py definitions.

        ARCHITECTURE: Schema-driven table creation.
        - Loops over TABLES registry from schema.py
        - Calls TableSchema.create_table_sql() for CREATE TABLE
        - Calls TableSchema.create_indexes_sql() for CREATE INDEX
        - NO hardcoded SQL (909 lines → 20 lines)
        """
        cursor = self.conn.cursor()

        # Create all tables from schema registry
        for table_name, table_schema in TABLES.items():
            # Generate and execute CREATE TABLE statement
            create_table_sql = table_schema.create_table_sql()
            cursor.execute(create_table_sql)

            # Generate and execute CREATE INDEX statements
            for create_index_sql in table_schema.create_indexes_sql():
                cursor.execute(create_index_sql)

        # Create unified views for JSX backward compatibility
        # These views combine transformed + preserved JSX data
        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS function_returns_unified AS
            SELECT *, 'transformed' as view_jsx_mode, 0 as view_extraction_pass
            FROM function_returns
            UNION ALL
            SELECT * FROM function_returns_jsx
        """
        )

        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS symbols_unified AS
            SELECT *, 'transformed' as view_jsx_mode FROM symbols
            UNION ALL
            SELECT * FROM symbols_jsx
        """
        )

        self.conn.commit()

    def clear_tables(self):
        """Clear all existing data from tables using schema.py registry.

        ARCHITECTURE: Schema-driven table clearing.
        - Loops over TABLES registry from schema.py
        - Executes DELETE FROM for each table
        - NO hardcoded table list (48 lines → 10 lines)
        """
        cursor = self.conn.cursor()

        try:
            # Clear all tables defined in schema
            for table_name in TABLES.keys():
                cursor.execute(f"DELETE FROM {table_name}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to clear existing data: {e}")

    def flush_generic_batch(self, table_name: str, insert_mode: str = 'INSERT'):
        """Flush a single table's batch using schema-driven INSERT.

        ARCHITECTURE: Schema-driven batch flushing.
        - Looks up table schema from TABLES registry
        - Gets column list from TableSchema.column_names()
        - Builds INSERT statement dynamically
        - Handles INSERT, INSERT OR REPLACE, INSERT OR IGNORE modes

        Args:
            table_name: Name of table to flush
            insert_mode: SQL insert verb - one of:
                - 'INSERT': Standard insert (fails on constraint violation)
                - 'INSERT OR REPLACE': Update existing rows (for files, jsx tables)
                - 'INSERT OR IGNORE': Skip duplicates (for frameworks)
        """
        batch = self.generic_batches.get(table_name, [])
        if not batch:
            return  # Nothing to flush

        # Get schema for this table
        schema = get_table_schema(table_name)
        if not schema:
            raise RuntimeError(f"No schema found for table '{table_name}' - check TABLES registry")

        # Get ALL columns except AUTOINCREMENT id
        # DEFAULT values are IRRELEVANT - the add_* method signature determines what's provided
        # Schema column order MUST match add_* method parameter order
        all_cols = [col for col in schema.columns if col.name != 'id']

        # Determine how many columns the add_* method actually provides
        # by checking the first batch tuple size
        tuple_size = len(batch[0]) if batch else 0

        # Take first N columns matching tuple size
        # This handles legacy tables where columns were added but add_* not updated
        columns = [col.name for col in all_cols[:tuple_size]]

        if len(columns) != tuple_size:
            # This should never happen if schema column order matches add_* parameter order
            raise RuntimeError(
                f"Column mismatch for table '{table_name}': "
                f"add_* method provides {tuple_size} values but schema has {len(all_cols)} columns. "
                f"Taking first {tuple_size}: {columns}. "
                f"Verify schema column order matches add_* parameter order."
            )

        # Build dynamic INSERT statement
        placeholders = ', '.join(['?' for _ in columns])
        column_list = ', '.join(columns)
        query = f"{insert_mode} INTO {table_name} ({column_list}) VALUES ({placeholders})"

        # Execute batch insert
        cursor = self.conn.cursor()
        cursor.executemany(query, batch)

        # Clear batch after flush
        self.generic_batches[table_name] = []

    def flush_batch(self, batch_idx: Optional[int] = None):
        """Execute all pending batch inserts using schema-driven approach.

        ARCHITECTURE: Hybrid flushing strategy.
        - Generic tables: Use flush_generic_batch() (475 lines → 50 lines)
        - CFG tables: Keep special case logic for ID mapping (required)
        - JWT patterns: Keep special flush method (dict-based interface)

        Special Cases:
        1. CFG blocks: MUST be inserted before edges/statements (ID dependencies)
        2. Junction tables: MUST be inserted after parent records
        3. INSERT modes: Respect OR REPLACE/OR IGNORE for specific tables
        """
        cursor = self.conn.cursor()

        try:
            # Define table flush order and INSERT modes
            # This ensures FK constraints are satisfied (parent → child)
            flush_order = [
                # Core tables (no FK dependencies)
                ('files', 'INSERT OR REPLACE'),  # Deduplication for symlinks
                ('config_files', 'INSERT OR REPLACE'),  # Multiple passes may reprocess

                # Code structure tables (depend on files)
                ('refs', 'INSERT'),
                ('symbols', 'INSERT'),
                ('class_properties', 'INSERT'),  # TypeScript/JavaScript class property declarations
                ('env_var_usage', 'INSERT'),  # Environment variable usage (process.env.X)
                ('orm_relationships', 'INSERT'),  # ORM relationship declarations (hasMany, belongsTo, etc.)
                ('sql_objects', 'INSERT'),
                ('sql_queries', 'INSERT'),
                ('orm_queries', 'INSERT'),
                ('prisma_models', 'INSERT'),

                # API endpoints (before junction table)
                ('api_endpoints', 'INSERT'),
                ('api_endpoint_controls', 'INSERT'),  # Junction table
                ('python_orm_models', 'INSERT'),
                ('python_orm_fields', 'INSERT'),
                ('python_routes', 'INSERT'),
                ('python_blueprints', 'INSERT'),
                ('python_validators', 'INSERT'),

                # Python Phase 2.2: Advanced patterns
                ('python_decorators', 'INSERT'),
                ('python_context_managers', 'INSERT'),
                ('python_async_functions', 'INSERT'),
                ('python_await_expressions', 'INSERT'),
                ('python_async_generators', 'INSERT'),
                ('python_pytest_fixtures', 'INSERT'),
                ('python_pytest_parametrize', 'INSERT'),
                ('python_pytest_markers', 'INSERT'),
                ('python_mock_patterns', 'INSERT'),
                ('python_protocols', 'INSERT'),
                ('python_generics', 'INSERT'),
                ('python_typed_dicts', 'INSERT'),
                ('python_literals', 'INSERT'),
                ('python_overloads', 'INSERT'),

                # SQL query tables (before junction table)
                ('sql_query_tables', 'INSERT'),  # Junction table

                # JWT patterns (special flush method handles this)
                # Skipped here - handled by _flush_jwt_patterns()

                # Docker tables
                ('docker_images', 'INSERT'),
                ('compose_services', 'INSERT'),
                ('nginx_configs', 'INSERT'),

                # Terraform tables (Infrastructure as Code)
                ('terraform_files', 'INSERT'),
                ('terraform_resources', 'INSERT'),
                ('terraform_variables', 'INSERT'),
                ('terraform_variable_values', 'INSERT'),
                ('terraform_outputs', 'INSERT'),
                ('terraform_findings', 'INSERT'),

                # AWS CDK tables (Infrastructure as Code)
                ('cdk_constructs', 'INSERT'),
                ('cdk_construct_properties', 'INSERT'),  # Depends on cdk_constructs FK
                ('cdk_findings', 'INSERT'),

                # GitHub Actions tables (CI/CD Security)
                ('github_workflows', 'INSERT'),
                ('github_jobs', 'INSERT'),  # Depends on github_workflows FK
                ('github_job_dependencies', 'INSERT'),  # Junction table - depends on github_jobs FK
                ('github_steps', 'INSERT'),  # Depends on github_jobs FK
                ('github_step_outputs', 'INSERT'),  # Depends on github_steps FK
                ('github_step_references', 'INSERT'),  # Depends on github_steps FK

                # Data flow tables (before junction tables)
                ('assignments', 'INSERT'),
                ('assignment_sources', 'INSERT'),  # Junction table
                ('function_call_args', 'INSERT'),
                ('function_returns', 'INSERT'),
                ('function_return_sources', 'INSERT'),  # Junction table

                # CFG tables (special case - handled separately below)
                # Skipped here - handled by CFG special case logic

                # React tables (before junction tables)
                ('react_components', 'INSERT'),
                ('react_component_hooks', 'INSERT'),  # Junction table
                ('react_hooks', 'INSERT'),
                ('react_hook_dependencies', 'INSERT'),  # Junction table
                ('variable_usage', 'INSERT'),
                ('object_literals', 'INSERT'),

                # JSX tables (dual-pass extraction uses OR REPLACE)
                ('function_returns_jsx', 'INSERT OR REPLACE'),
                ('function_return_sources_jsx', 'INSERT'),  # Junction table
                ('symbols_jsx', 'INSERT OR REPLACE'),
                ('assignments_jsx', 'INSERT OR REPLACE'),
                ('assignment_sources_jsx', 'INSERT'),  # Junction table
                ('function_call_args_jsx', 'INSERT OR REPLACE'),

                # Vue tables
                ('vue_components', 'INSERT'),
                ('vue_hooks', 'INSERT'),
                ('vue_directives', 'INSERT'),
                ('vue_provide_inject', 'INSERT'),

                # TypeScript tables
                ('type_annotations', 'INSERT OR REPLACE'),

                # Build analysis tables
                ('package_configs', 'INSERT OR REPLACE'),
                ('lock_analysis', 'INSERT OR REPLACE'),
                ('import_styles', 'INSERT'),
                ('import_style_names', 'INSERT'),  # Junction table

                # Framework detection tables
                ('frameworks', 'INSERT OR IGNORE'),  # Avoid duplicates from multiple scans
                ('framework_safe_sinks', 'INSERT OR IGNORE'),
            ]

            # Flush JWT patterns first (special dict-based batch)
            self._flush_jwt_patterns()

            # Flush CFG blocks FIRST (must insert before edges/statements)
            # This is the ONLY special case logic preserved from old system
            if 'cfg_blocks' in self.generic_batches and self.generic_batches['cfg_blocks']:
                # CFG blocks use temp negative IDs that must be mapped to real IDs
                # This is necessary because AUTOINCREMENT assigns IDs after INSERT
                id_mapping = {}

                for batch_item in self.generic_batches['cfg_blocks']:
                    # Extract data (last element is temp_id)
                    file_path, function_name, block_type, start_line, end_line, condition_expr, temp_id = batch_item

                    cursor.execute(
                        """INSERT INTO cfg_blocks (file, function_name, block_type, start_line, end_line, condition_expr)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (file_path, function_name, block_type, start_line, end_line, condition_expr)
                    )
                    # Map temporary ID to real AUTOINCREMENT ID
                    real_id = cursor.lastrowid
                    id_mapping[temp_id] = real_id

                self.generic_batches['cfg_blocks'] = []
                self.cfg_id_mapping.update(id_mapping)

                # Flush CFG edges (map temp IDs to real IDs)
                if 'cfg_edges' in self.generic_batches and self.generic_batches['cfg_edges']:
                    updated_edges = []
                    for file_path, function_name, source_id, target_id, edge_type in self.generic_batches['cfg_edges']:
                        # Map temporary IDs to real IDs
                        real_source = id_mapping.get(source_id, source_id) if source_id < 0 else source_id
                        real_target = id_mapping.get(target_id, target_id) if target_id < 0 else target_id
                        updated_edges.append((file_path, function_name, real_source, real_target, edge_type))

                    cursor.executemany(
                        """INSERT INTO cfg_edges (file, function_name, source_block_id, target_block_id, edge_type)
                           VALUES (?, ?, ?, ?, ?)""",
                        updated_edges
                    )
                    self.generic_batches['cfg_edges'] = []

                # Flush CFG statements (map temp IDs to real IDs)
                if 'cfg_block_statements' in self.generic_batches and self.generic_batches['cfg_block_statements']:
                    updated_statements = []
                    for block_id, statement_type, line, statement_text in self.generic_batches['cfg_block_statements']:
                        # Map temporary ID to real ID
                        real_block_id = id_mapping.get(block_id, block_id) if block_id < 0 else block_id
                        updated_statements.append((real_block_id, statement_type, line, statement_text))

                    cursor.executemany(
                        """INSERT INTO cfg_block_statements (block_id, statement_type, line, statement_text)
                           VALUES (?, ?, ?, ?)""",
                        updated_statements
                    )
                    self.generic_batches['cfg_block_statements'] = []

            # Flush all generic tables in dependency order
            for table_name, insert_mode in flush_order:
                if table_name in self.generic_batches and self.generic_batches[table_name]:
                    self.flush_generic_batch(table_name, insert_mode)

        except sqlite3.Error as e:
            # DEBUG: Enhanced error reporting for UNIQUE constraint failures
            if "UNIQUE constraint failed" in str(e):
                import sys
                print(f"\n[DEBUG] UNIQUE constraint violation: {e}", file=sys.stderr)
                # Report which table had the violation
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        print(f"[DEBUG] Table '{table_name}' has {len(batch)} pending records", file=sys.stderr)

            if batch_idx is not None:
                raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}")
            else:
                raise RuntimeError(f"Batch insert failed: {e}")

    def _flush_jwt_patterns(self):
        """Flush JWT patterns batch (special dict-based interface).

        KEPT FOR BACKWARD COMPATIBILITY: add_jwt_pattern uses dict format.
        """
        if not self.jwt_patterns_batch:
            return
        cursor = self.conn.cursor()
        cursor.executemany("""
            INSERT OR REPLACE INTO jwt_patterns
            (file_path, line_number, pattern_type, pattern_text, secret_source, algorithm)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (p['file_path'], p['line_number'], p['pattern_type'],
             p['pattern_text'], p['secret_source'], p['algorithm'])
            for p in self.jwt_patterns_batch
        ])
        self.jwt_patterns_batch.clear()

    # ========================================================================
    # ADD_* METHODS - BACKWARD COMPATIBLE INTERFACE
    # ========================================================================
    # These methods preserve the existing API used by extractors
    # Now use generic_batches dict instead of 58 individual batch lists

    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch.

        Deduplicates paths to prevent UNIQUE constraint violations.
        This can happen with symlinks, junction points, or case sensitivity issues.
        """
        # Check if path already in current batch (O(n) but batches are small)
        batch = self.generic_batches['files']
        if not any(item[0] == path for item in batch):
            batch.append((path, sha256, ext, bytes_size, loc))

    def add_ref(self, src: str, kind: str, value: str, line: Optional[int] = None):
        """Add a reference record to the batch."""
        self.generic_batches['refs'].append((src, kind, value, line))

    def add_endpoint(self, file_path: str, method: str, pattern: str, controls: List[str],
                     line: Optional[int] = None, path: Optional[str] = None,
                     has_auth: bool = False, handler_function: Optional[str] = None):
        """Add an API endpoint record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch endpoint record (without controls column)
        - Phase 2: Batch junction records for each control/middleware

        NO FALLBACKS. If controls is malformed, hard fail.
        """
        # Phase 1: Add endpoint record (6 params, no controls column)
        self.generic_batches['api_endpoints'].append((file_path, line, method, pattern, path,
                                                      has_auth, handler_function))

        # Phase 2: Add junction records for each control/middleware
        if controls:
            for control_name in controls:
                if not control_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['api_endpoint_controls'].append((file_path, line, control_name))

    def add_python_orm_model(self, file_path: str, line: int, model_name: str,
                             table_name: Optional[str], orm_type: str = 'sqlalchemy'):
        """Add a Python ORM model definition to the batch."""
        self.generic_batches['python_orm_models'].append((file_path, line, model_name, table_name, orm_type))

    def add_python_orm_field(self, file_path: str, line: int, model_name: str,
                             field_name: str, field_type: Optional[str],
                             is_primary_key: bool = False, is_foreign_key: bool = False,
                             foreign_key_target: Optional[str] = None):
        """Add a Python ORM field definition to the batch."""
        self.generic_batches['python_orm_fields'].append((
            file_path,
            line,
            model_name,
            field_name,
            field_type,
            1 if is_primary_key else 0,
            1 if is_foreign_key else 0,
            foreign_key_target
        ))

    def add_python_route(self, file_path: str, line: int, framework: str, method: str,
                         pattern: str, handler_function: str, has_auth: bool = False,
                         dependencies: Optional[List[str]] = None, blueprint: Optional[str] = None):
        """Add a Python framework route (Flask/FastAPI) to the batch."""
        dependencies_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches['python_routes'].append((
            file_path,
            line,
            framework,
            method,
            pattern,
            handler_function,
            1 if has_auth else 0,
            dependencies_json,
            blueprint
        ))

    def add_python_blueprint(self, file_path: str, line: int, blueprint_name: str,
                             url_prefix: Optional[str], subdomain: Optional[str]):
        """Add a Flask blueprint definition to the batch."""
        self.generic_batches['python_blueprints'].append((
            file_path,
            line,
            blueprint_name,
            url_prefix,
            subdomain
        ))

    def add_python_validator(self, file_path: str, line: int, model_name: str,
                             field_name: Optional[str], validator_method: str,
                             validator_type: str):
        """Add a Pydantic validator definition to the batch."""
        self.generic_batches['python_validators'].append((
            file_path,
            line,
            model_name,
            field_name,
            validator_method,
            validator_type
        ))

    # Phase 2.2: Advanced Python pattern add_* methods

    def add_python_decorator(self, file_path: str, line: int, decorator_name: str,
                            decorator_type: str, target_type: str, target_name: str,
                            is_async: bool):
        """Add a Python decorator usage to the batch."""
        self.generic_batches['python_decorators'].append((
            file_path,
            line,
            decorator_name,
            decorator_type,
            target_type,
            target_name,
            1 if is_async else 0
        ))

    def add_python_context_manager(self, file_path: str, line: int, context_type: str,
                                   context_expr: Optional[str], as_name: Optional[str],
                                   is_async: bool, is_custom: bool):
        """Add a Python context manager usage to the batch."""
        self.generic_batches['python_context_managers'].append((
            file_path,
            line,
            context_type,
            context_expr,
            as_name,
            1 if is_async else 0,
            1 if is_custom else 0
        ))

    def add_python_async_function(self, file_path: str, line: int, function_name: str,
                                  has_await: bool, await_count: int,
                                  has_async_with: bool, has_async_for: bool):
        """Add a Python async function to the batch."""
        self.generic_batches['python_async_functions'].append((
            file_path,
            line,
            function_name,
            1 if has_await else 0,
            await_count,
            1 if has_async_with else 0,
            1 if has_async_for else 0
        ))

    def add_python_await_expression(self, file_path: str, line: int, await_expr: str,
                                    containing_function: Optional[str]):
        """Add a Python await expression to the batch."""
        self.generic_batches['python_await_expressions'].append((
            file_path,
            line,
            await_expr,
            containing_function
        ))

    def add_python_async_generator(self, file_path: str, line: int, generator_type: str,
                                   target_vars: Optional[str], iterable_expr: Optional[str],
                                   function_name: Optional[str]):
        """Add a Python async generator pattern to the batch."""
        self.generic_batches['python_async_generators'].append((
            file_path,
            line,
            generator_type,
            target_vars,
            iterable_expr,
            function_name
        ))

    def add_python_pytest_fixture(self, file_path: str, line: int, fixture_name: str,
                                  scope: str, has_autouse: bool, has_params: bool):
        """Add a pytest fixture to the batch."""
        self.generic_batches['python_pytest_fixtures'].append((
            file_path,
            line,
            fixture_name,
            scope,
            1 if has_autouse else 0,
            1 if has_params else 0
        ))

    def add_python_pytest_parametrize(self, file_path: str, line: int, test_function: str,
                                      parameter_names: str, argvalues_count: int):
        """Add a pytest parametrize decorator to the batch."""
        self.generic_batches['python_pytest_parametrize'].append((
            file_path,
            line,
            test_function,
            parameter_names,
            argvalues_count
        ))

    def add_python_pytest_marker(self, file_path: str, line: int, test_function: str,
                                 marker_name: str, marker_args: Optional[str]):
        """Add a pytest marker to the batch."""
        self.generic_batches['python_pytest_markers'].append((
            file_path,
            line,
            test_function,
            marker_name,
            marker_args
        ))

    def add_python_mock_pattern(self, file_path: str, line: int, mock_type: str,
                                target: Optional[str], in_function: Optional[str],
                                is_decorator: bool):
        """Add a Python mock pattern to the batch."""
        self.generic_batches['python_mock_patterns'].append((
            file_path,
            line,
            mock_type,
            target,
            in_function,
            1 if is_decorator else 0
        ))

    def add_python_protocol(self, file_path: str, line: int, protocol_name: str,
                           methods: str, is_runtime_checkable: bool):
        """Add a Python Protocol class to the batch."""
        self.generic_batches['python_protocols'].append((
            file_path,
            line,
            protocol_name,
            methods,
            1 if is_runtime_checkable else 0
        ))

    def add_python_generic(self, file_path: str, line: int, class_name: str,
                          type_params: Optional[str]):
        """Add a Python Generic class to the batch."""
        self.generic_batches['python_generics'].append((
            file_path,
            line,
            class_name,
            type_params
        ))

    def add_python_typed_dict(self, file_path: str, line: int, typeddict_name: str,
                             fields: str):
        """Add a Python TypedDict to the batch."""
        self.generic_batches['python_typed_dicts'].append((
            file_path,
            line,
            typeddict_name,
            fields
        ))

    def add_python_literal(self, file_path: str, line: int, usage_context: str,
                          name: Optional[str], literal_type: str):
        """Add a Python Literal type usage to the batch."""
        self.generic_batches['python_literals'].append((
            file_path,
            line,
            usage_context,
            name,
            literal_type
        ))

    def add_python_overload(self, file_path: str, function_name: str, overload_count: int,
                           variants: str):
        """Add a Python @overload function to the batch."""
        self.generic_batches['python_overloads'].append((
            file_path,
            function_name,
            overload_count,
            variants
        ))

    def add_python_django_view(self, file_path: str, line: int, view_class_name: str,
                              view_type: str, base_view_class: Optional[str],
                              model_name: Optional[str], template_name: Optional[str],
                              has_permission_check: bool, http_method_names: Optional[str],
                              has_get_queryset_override: bool):
        """Add a Django Class-Based View to the batch."""
        self.generic_batches['python_django_views'].append((
            file_path,
            line,
            view_class_name,
            view_type,
            base_view_class,
            model_name,
            template_name,
            1 if has_permission_check else 0,
            http_method_names,
            1 if has_get_queryset_override else 0
        ))

    def add_python_django_form(self, file_path: str, line: int, form_class_name: str,
                               is_model_form: bool, model_name: Optional[str],
                               field_count: int, has_custom_clean: bool):
        """Add a Django Form or ModelForm to the batch."""
        self.generic_batches['python_django_forms'].append((
            file_path,
            line,
            form_class_name,
            1 if is_model_form else 0,
            model_name,
            field_count,
            1 if has_custom_clean else 0
        ))

    def add_python_django_form_field(self, file_path: str, line: int, form_class_name: str,
                                     field_name: str, field_type: str,
                                     required: bool, max_length: Optional[int],
                                     has_custom_validator: bool):
        """Add a Django form field to the batch."""
        self.generic_batches['python_django_form_fields'].append((
            file_path,
            line,
            form_class_name,
            field_name,
            field_type,
            1 if required else 0,
            max_length,
            1 if has_custom_validator else 0
        ))

    def add_python_django_admin(self, file_path: str, line: int, admin_class_name: str,
                                model_name: Optional[str], list_display: Optional[str],
                                list_filter: Optional[str], search_fields: Optional[str],
                                readonly_fields: Optional[str], has_custom_actions: bool):
        """Add a Django ModelAdmin configuration to the batch."""
        self.generic_batches['python_django_admin'].append((
            file_path,
            line,
            admin_class_name,
            model_name,
            list_display,
            list_filter,
            search_fields,
            readonly_fields,
            1 if has_custom_actions else 0
        ))

    def add_python_django_middleware(self, file_path: str, line: int, middleware_class_name: str,
                                     has_process_request: bool, has_process_response: bool,
                                     has_process_exception: bool, has_process_view: bool,
                                     has_process_template_response: bool):
        """Add a Django middleware configuration to the batch."""
        self.generic_batches['python_django_middleware'].append((
            file_path,
            line,
            middleware_class_name,
            1 if has_process_request else 0,
            1 if has_process_response else 0,
            1 if has_process_exception else 0,
            1 if has_process_view else 0,
            1 if has_process_template_response else 0
        ))

    def add_python_marshmallow_schema(self, file_path: str, line: int, schema_class_name: str,
                                      field_count: int, has_nested_schemas: bool,
                                      has_custom_validators: bool):
        """Add a Marshmallow schema definition to the batch."""
        self.generic_batches['python_marshmallow_schemas'].append((
            file_path,
            line,
            schema_class_name,
            field_count,
            1 if has_nested_schemas else 0,
            1 if has_custom_validators else 0
        ))

    def add_python_marshmallow_field(self, file_path: str, line: int, schema_class_name: str,
                                     field_name: str, field_type: str, required: bool,
                                     allow_none: bool, has_validate: bool, has_custom_validator: bool):
        """Add a Marshmallow field definition to the batch."""
        self.generic_batches['python_marshmallow_fields'].append((
            file_path,
            line,
            schema_class_name,
            field_name,
            field_type,
            1 if required else 0,
            1 if allow_none else 0,
            1 if has_validate else 0,
            1 if has_custom_validator else 0
        ))

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

    def add_symbol(self, path: str, name: str, symbol_type: str, line: int, col: int, end_line: Optional[int] = None,
                   type_annotation: Optional[str] = None, parameters: Optional[str] = None):
        """Add a symbol record to the batch.

        Args:
            path: File path containing the symbol
            name: Symbol name
            symbol_type: Type of symbol ('function', 'class', 'variable', etc.)
            line: Line number where symbol is defined
            col: Column number where symbol is defined
            end_line: Last line of symbol definition (optional)
            type_annotation: TypeScript/type annotation (optional)
            parameters: JSON array of parameter names for functions (optional, e.g., '["data", "_createdBy"]')
        """
        import os
        if os.getenv("THEAUDITOR_DEBUG"):
            # Check if this exact symbol already exists in batch
            symbol_key = (path, name, symbol_type, line, col)
            existing = [s for s in self.generic_batches['symbols'] if (s[0], s[1], s[2], s[3], s[4]) == symbol_key]
            if existing:
                print(f"[DEBUG] add_symbol: DUPLICATE detected! {name} ({symbol_type}) at {path}:{line}:{col}")
            if parameters and os.getenv("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] add_symbol: {name} ({symbol_type}) has parameters: {parameters}")
        self.generic_batches['symbols'].append((path, name, symbol_type, line, col, end_line, type_annotation, parameters))

    def add_class_property(self, file: str, line: int, class_name: str, property_name: str,
                          property_type: Optional[str] = None, is_optional: bool = False,
                          is_readonly: bool = False, access_modifier: Optional[str] = None,
                          has_declare: bool = False, initializer: Optional[str] = None):
        """Add a class property declaration record to the batch.

        Args:
            file: File containing the class
            line: Line number of property declaration
            class_name: Name of the containing class
            property_name: Name of the property
            property_type: TypeScript type annotation (e.g., "string", "number | null")
            is_optional: Whether property has ? modifier
            is_readonly: Whether property has readonly keyword
            access_modifier: "private", "protected", or "public" (None = public by default)
            has_declare: Whether property has declare keyword (TypeScript ambient declaration)
            initializer: Default value expression if present
        """
        self.generic_batches['class_properties'].append((
            file, line, class_name, property_name, property_type,
            1 if is_optional else 0,
            1 if is_readonly else 0,
            access_modifier,
            1 if has_declare else 0,
            initializer
        ))

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

    def add_orm_relationship(self, file: str, line: int, source_model: str, target_model: str,
                            relationship_type: str, foreign_key: Optional[str] = None,
                            cascade_delete: bool = False, as_name: Optional[str] = None):
        """Add an ORM relationship record to the batch.

        Args:
            file: File containing the relationship definition
            line: Line number of the relationship
            source_model: Source model name (e.g., "User")
            target_model: Target model name (e.g., "Account")
            relationship_type: Type of relationship - "hasMany", "belongsTo", "hasOne", etc.
            foreign_key: Foreign key column name (e.g., "account_id")
            cascade_delete: Whether CASCADE delete is enabled
            as_name: Association alias (e.g., "owner")
        """
        self.generic_batches['orm_relationships'].append((
            file, line, source_model, target_model, relationship_type,
            foreign_key, 1 if cascade_delete else 0, as_name
        ))

    def add_orm_query(self, file_path: str, line: int, query_type: str, includes: Optional[str],
                      has_limit: bool, has_transaction: bool):
        """Add an ORM query record to the batch."""
        self.generic_batches['orm_queries'].append((file_path, line, query_type, includes, has_limit, has_transaction))

    def add_docker_image(self, file_path: str, base_image: Optional[str], exposed_ports: List[str],
                        env_vars: Dict, build_args: Dict, user: Optional[str], has_healthcheck: bool):
        """Add a Docker image record to the batch."""
        ports_json = json.dumps(exposed_ports)
        env_json = json.dumps(env_vars)
        args_json = json.dumps(build_args)
        self.generic_batches['docker_images'].append((file_path, base_image, ports_json, env_json,
                                                      args_json, user, has_healthcheck))

    def add_assignment(self, file_path: str, line: int, target_var: str, source_expr: str,
                      source_vars: List[str], in_function: str, property_path: Optional[str] = None):
        """Add a variable assignment record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch assignment record (without source_vars column)
        - Phase 2: Batch junction records for each source variable

        Args:
            property_path: Full property path for destructured assignments (e.g., 'req.params.id')
                          NULL for non-destructured assignments (e.g., 'const x = y')

        NO FALLBACKS. If source_vars is malformed, hard fail.
        """
        # DEBUG: Track batch index for duplicate investigation
        import os
        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            batch_idx = len(self.generic_batches['assignments'])
            import sys
            print(f"[TRACE] add_assignment() call #{batch_idx}: {file_path}:{line} {target_var} in {in_function}", file=sys.stderr)

        # Phase 1: Add assignment record (6 params including property_path)
        self.generic_batches['assignments'].append((file_path, line, target_var, source_expr, in_function, property_path))

        # Phase 2: Add junction records for each source variable
        if source_vars:
            for source_var in source_vars:
                if not source_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['assignment_sources'].append((file_path, line, target_var, source_var))

    def add_function_call_arg(self, file_path: str, line: int, caller_function: str,
                              callee_function: str, arg_index: int, arg_expr: str, param_name: str,
                              callee_file_path: Optional[str] = None):
        """Add a function call argument record to the batch.

        Args:
            file_path: File containing the function call
            line: Line number of the call
            caller_function: Name of the calling function
            callee_function: Name of the called function
            arg_index: Index of the argument (0-based)
            arg_expr: Expression passed as argument
            param_name: Parameter name in callee signature
            callee_file_path: Resolved file path where callee is defined (for cross-file tracking)
        """
        self.generic_batches['function_call_args'].append((file_path, line, caller_function, callee_function,
                                                           arg_index, arg_expr, param_name, callee_file_path))

    def add_function_return(self, file_path: str, line: int, function_name: str,
                           return_expr: str, return_vars: List[str]):
        """Add a function return statement record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch function return record (without return_vars column)
        - Phase 2: Batch junction records for each return variable

        NO FALLBACKS. If return_vars is malformed, hard fail.
        """
        # Phase 1: Add function return record (4 params, no return_vars column)
        self.generic_batches['function_returns'].append((file_path, line, function_name, return_expr))

        # Phase 2: Add junction records for each return variable
        if return_vars:
            for return_var in return_vars:
                if not return_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['function_return_sources'].append((file_path, line, function_name, return_var))

    def add_config_file(self, path: str, content: str, file_type: str, context: Optional[str] = None):
        """Add a configuration file content to the batch."""
        self.generic_batches['config_files'].append((path, content, file_type, context))

    def add_prisma_model(self, model_name: str, field_name: str, field_type: str,
                        is_indexed: bool, is_unique: bool, is_relation: bool):
        """Add a Prisma model field record to the batch."""
        self.generic_batches['prisma_models'].append((model_name, field_name, field_type,
                                                      is_indexed, is_unique, is_relation))

    def add_compose_service(self, file_path: str, service_name: str, image: Optional[str],
                           ports: List[str], volumes: List[str], environment: Dict,
                           is_privileged: bool, network_mode: str,
                           # 9 new security fields (Phase 3C)
                           user: Optional[str] = None,
                           cap_add: Optional[List[str]] = None,
                           cap_drop: Optional[List[str]] = None,
                           security_opt: Optional[List[str]] = None,
                           restart: Optional[str] = None,
                           command: Optional[List[str]] = None,
                           entrypoint: Optional[List[str]] = None,
                           depends_on: Optional[List[str]] = None,
                           healthcheck: Optional[Dict] = None):
        """Add a Docker Compose service record to the batch.

        Args:
            file_path: Path to docker-compose.yml
            service_name: Name of the service
            image: Docker image name
            ports: List of port mappings
            volumes: List of volume mounts
            environment: Dictionary of environment variables
            is_privileged: Whether service runs in privileged mode
            network_mode: Network mode (bridge, host, etc.)
            user: User/UID to run as (security: detect root)
            cap_add: Linux capabilities to add (security: detect dangerous caps)
            cap_drop: Linux capabilities to drop (security: enforce hardening)
            security_opt: Security options (security: detect disabled AppArmor/SELinux)
            restart: Restart policy (operational: availability)
            command: Override CMD instruction (security: command injection risk)
            entrypoint: Override ENTRYPOINT instruction (security: tampering)
            depends_on: Service dependencies (operational: dependency graph)
            healthcheck: Health check configuration (operational: availability)
        """
        ports_json = json.dumps(ports)
        volumes_json = json.dumps(volumes)
        env_json = json.dumps(environment)

        # Encode new fields as JSON (or None if not provided)
        cap_add_json = json.dumps(cap_add) if cap_add else None
        cap_drop_json = json.dumps(cap_drop) if cap_drop else None
        security_opt_json = json.dumps(security_opt) if security_opt else None
        command_json = json.dumps(command) if command else None
        entrypoint_json = json.dumps(entrypoint) if entrypoint else None
        depends_on_json = json.dumps(depends_on) if depends_on else None
        healthcheck_json = json.dumps(healthcheck) if healthcheck else None

        self.generic_batches['compose_services'].append((
            file_path, service_name, image, ports_json, volumes_json, env_json,
            is_privileged, network_mode,
            # 9 new fields
            user, cap_add_json, cap_drop_json, security_opt_json,
            restart, command_json, entrypoint_json, depends_on_json, healthcheck_json
        ))

    def add_nginx_config(self, file_path: str, block_type: str, block_context: str,
                        directives: Dict, level: int):
        """Add an Nginx configuration block to the batch."""
        directives_json = json.dumps(directives)
        # Use a default context if empty to avoid primary key issues
        block_context = block_context or 'default'

        # Check for duplicates before adding
        batch = self.generic_batches['nginx_configs']
        batch_key = (file_path, block_type, block_context)
        if not any(b[:3] == batch_key for b in batch):
            batch.append((file_path, block_type, block_context, directives_json, level))

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

    def add_cfg_block(self, file_path: str, function_name: str, block_type: str,
                     start_line: int, end_line: int, condition_expr: Optional[str] = None) -> int:
        """Add a CFG block to the batch and return its temporary ID.

        SPECIAL CASE: CFG blocks use AUTOINCREMENT, so real IDs are unknown until INSERT.
        This method returns a temporary negative ID that will be mapped to real ID during flush.

        Note: Since we use AUTOINCREMENT, we need to handle IDs carefully.
        This returns a temporary ID that will be replaced during flush.
        """
        # Generate temporary ID (negative to distinguish from real IDs)
        batch = self.generic_batches['cfg_blocks']
        temp_id = -(len(batch) + 1)
        batch.append((file_path, function_name, block_type,
                     start_line, end_line, condition_expr, temp_id))
        return temp_id

    def add_cfg_edge(self, file_path: str, function_name: str, source_block_id: int,
                    target_block_id: int, edge_type: str):
        """Add a CFG edge to the batch."""
        self.generic_batches['cfg_edges'].append((file_path, function_name, source_block_id,
                                                  target_block_id, edge_type))

    def add_cfg_statement(self, block_id: int, statement_type: str, line: int,
                         statement_text: Optional[str] = None):
        """Add a CFG block statement to the batch."""
        self.generic_batches['cfg_block_statements'].append((block_id, statement_type, line, statement_text))

    def add_react_component(self, file_path: str, name: str, component_type: str,
                           start_line: int, end_line: int, has_jsx: bool,
                           hooks_used: Optional[List[str]] = None,
                           props_type: Optional[str] = None):
        """Add a React component to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch component record (without hooks_used column)
        - Phase 2: Batch junction records for each hook used

        NO FALLBACKS. If hooks_used is malformed, hard fail.
        """
        # Phase 1: Add component record (6 params, no hooks_used column)
        self.generic_batches['react_components'].append((file_path, name, component_type,
                                                         start_line, end_line, has_jsx, props_type))

        # Phase 2: Add junction records for each hook used
        if hooks_used:
            for hook_name in hooks_used:
                if not hook_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['react_component_hooks'].append((file_path, name, hook_name))

    def add_react_hook(self, file_path: str, line: int, component_name: str,
                      hook_name: str, dependency_array: Optional[List[str]] = None,
                      dependency_vars: Optional[List[str]] = None,
                      callback_body: Optional[str] = None, has_cleanup: bool = False,
                      cleanup_type: Optional[str] = None):
        """Add a React hook usage to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch hook record (without dependency_vars column)
        - Phase 2: Batch junction records for each dependency variable

        NO FALLBACKS. If dependency_vars is malformed, hard fail.
        """
        # Phase 1: Add hook record (7 params, no dependency_vars column)
        deps_array_json = json.dumps(dependency_array) if dependency_array is not None else None
        # Limit callback body to 500 chars
        if callback_body and len(callback_body) > 500:
            callback_body = callback_body[:497] + '...'
        self.generic_batches['react_hooks'].append((file_path, line, component_name, hook_name,
                                                    deps_array_json, callback_body,
                                                    has_cleanup, cleanup_type))

        # Phase 2: Add junction records for each dependency variable
        if dependency_vars:
            for dep_var in dependency_vars:
                if not dep_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['react_hook_dependencies'].append((file_path, line, component_name, dep_var))

    def add_variable_usage(self, file_path: str, line: int, variable_name: str,
                          usage_type: str, in_component: Optional[str] = None,
                          in_hook: Optional[str] = None, scope_level: int = 0):
        """Add a variable usage record to the batch."""
        self.generic_batches['variable_usage'].append((file_path, line, variable_name, usage_type,
                                                       in_component or '', in_hook or '', scope_level))

    def add_object_literal(self, file_path: str, line: int, variable_name: str,
                          property_name: str, property_value: str,
                          property_type: str, nested_level: int = 0,
                          in_function: str = ''):
        """Add object literal property-function mapping to batch.

        Args:
            file_path: Path to the file containing the object literal
            line: Line number where the object literal appears
            variable_name: Name of the variable holding the object (e.g., 'handlers')
            property_name: Key in the object literal (e.g., 'create')
            property_value: Value expression (e.g., 'handleCreate' or '{nested}')
            property_type: Type of value - one of:
                - 'function_ref': Reference to a function (e.g., handleCreate)
                - 'literal': Primitive literal value (string, number, boolean)
                - 'expression': Complex expression
                - 'object': Nested object literal
                - 'method_definition': ES6 method syntax (method() {})
                - 'shorthand': Shorthand property ({ handleClick })
                - 'arrow_function': Inline arrow function
                - 'function_expression': Inline function expression
            nested_level: Depth of nesting (0 = top level, 1 = first nested, etc.)
            in_function: Name of containing function ('' for module scope)
        """
        self.generic_batches['object_literals'].append((
            file_path, line, variable_name, property_name,
            property_value, property_type, nested_level, in_function
        ))

    # ========================================================
    # JSX-SPECIFIC BATCH METHODS FOR DUAL-PASS EXTRACTION
    # ========================================================

    def add_function_return_jsx(self, file_path: str, line: int, function_name: str,
                                return_expr: str, return_vars: List[str], has_jsx: bool = False,
                                returns_component: bool = False, cleanup_operations: Optional[str] = None,
                                jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function return record for preserved JSX extraction.

        ARCHITECTURE: Normalized many-to-many relationship (JSX variant).
        - Phase 1: Batch JSX function return record (without return_vars column)
        - Phase 2: Batch JSX junction records for each return variable

        NO FALLBACKS. If return_vars is malformed, hard fail.
        """
        # Phase 1: Add JSX function return record (8 params, no return_vars column)
        self.generic_batches['function_returns_jsx'].append((file_path, line, function_name, return_expr,
                                                             has_jsx, returns_component,
                                                             cleanup_operations, jsx_mode, extraction_pass))

        # Phase 2: Add JSX junction records for each return variable
        if return_vars:
            for return_var in return_vars:
                if not return_var:  # Skip empty strings (data validation, not fallback)
                    continue
                # Schema: (return_file, return_line, return_function, jsx_mode, return_var_name)
                self.generic_batches['function_return_sources_jsx'].append((file_path, line, function_name, jsx_mode, return_var))

    def add_symbol_jsx(self, path: str, name: str, symbol_type: str, line: int, col: int,
                      jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX symbol record for preserved JSX extraction."""
        self.generic_batches['symbols_jsx'].append((path, name, symbol_type, line, col, jsx_mode, extraction_pass))

    def add_assignment_jsx(self, file_path: str, line: int, target_var: str, source_expr: str,
                          source_vars: List[str], in_function: str, property_path: Optional[str] = None,
                          jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX assignment record for preserved JSX extraction.

        ARCHITECTURE: Normalized many-to-many relationship (JSX variant).
        - Phase 1: Batch JSX assignment record (without source_vars column)
        - Phase 2: Batch JSX junction records for each source variable

        Args:
            property_path: Full property path for destructured assignments (e.g., 'req.params.id')
                          NULL for non-destructured assignments (e.g., 'const x = y')

        NO FALLBACKS. If source_vars is malformed, hard fail.
        """
        # Phase 1: Add JSX assignment record (8 params including property_path)
        self.generic_batches['assignments_jsx'].append((file_path, line, target_var, source_expr,
                                                        in_function, property_path, jsx_mode, extraction_pass))

        # Phase 2: Add JSX junction records for each source variable
        if source_vars:
            for source_var in source_vars:
                if not source_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['assignment_sources_jsx'].append((file_path, line, target_var, jsx_mode, source_var))

    def add_function_call_arg_jsx(self, file_path: str, line: int, caller_function: str,
                                  callee_function: str, arg_index: int, arg_expr: str, param_name: str,
                                  jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function call argument record for preserved JSX extraction."""
        self.generic_batches['function_call_args_jsx'].append((file_path, line, caller_function, callee_function,
                                                               arg_index, arg_expr, param_name, jsx_mode, extraction_pass))

    # ========================================================
    # VUE-SPECIFIC BATCH METHODS FOR FRAMEWORK ANALYSIS
    # ========================================================

    def add_vue_component(self, file_path: str, name: str, component_type: str,
                         start_line: int, end_line: int, has_template: bool = False,
                         has_style: bool = False, composition_api_used: bool = False,
                         props_definition: Optional[Dict] = None,
                         emits_definition: Optional[Dict] = None,
                         setup_return: Optional[str] = None):
        """Add a Vue component to the batch."""
        props_json = json.dumps(props_definition) if props_definition else None
        emits_json = json.dumps(emits_definition) if emits_definition else None
        self.generic_batches['vue_components'].append((file_path, name, component_type,
                                                       start_line, end_line, has_template, has_style,
                                                       composition_api_used, props_json, emits_json,
                                                       setup_return))

    def add_vue_hook(self, file_path: str, line: int, component_name: str,
                    hook_name: str, hook_type: str, dependencies: Optional[List[str]] = None,
                    return_value: Optional[str] = None, is_async: bool = False):
        """Add a Vue hook/reactivity usage to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches['vue_hooks'].append((file_path, line, component_name, hook_name,
                                                  hook_type, deps_json, return_value, is_async))

    def add_vue_directive(self, file_path: str, line: int, directive_name: str,
                         expression: str, in_component: str, has_key: bool = False,
                         modifiers: Optional[List[str]] = None):
        """Add a Vue directive usage to the batch."""
        modifiers_json = json.dumps(modifiers) if modifiers else None
        self.generic_batches['vue_directives'].append((file_path, line, directive_name, expression,
                                                       in_component, has_key, modifiers_json))

    def add_vue_provide_inject(self, file_path: str, line: int, component_name: str,
                              operation_type: str, key_name: str, value_expr: Optional[str] = None,
                              is_reactive: bool = False):
        """Add a Vue provide/inject operation to the batch."""
        self.generic_batches['vue_provide_inject'].append((file_path, line, component_name,
                                                           operation_type, key_name, value_expr, is_reactive))

    def add_type_annotation(self, file_path: str, line: int, column: int, symbol_name: str,
                           symbol_kind: str, type_annotation: str = None, is_any: bool = False,
                           is_unknown: bool = False, is_generic: bool = False,
                           has_type_params: bool = False, type_params: str = None,
                           return_type: str = None, extends_type: str = None):
        """Add a TypeScript type annotation record to the batch."""
        self.generic_batches['type_annotations'].append((file_path, line, column, symbol_name, symbol_kind,
                                                         type_annotation, is_any, is_unknown, is_generic,
                                                         has_type_params, type_params, return_type, extends_type))

    def add_package_config(self, file_path: str, package_name: str, version: str,
                          dependencies: Optional[Dict], dev_dependencies: Optional[Dict],
                          peer_dependencies: Optional[Dict], scripts: Optional[Dict],
                          engines: Optional[Dict], workspaces: Optional[List],
                          is_private: bool = False):
        """Add a package.json configuration to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        dev_deps_json = json.dumps(dev_dependencies) if dev_dependencies else None
        peer_deps_json = json.dumps(peer_dependencies) if peer_dependencies else None
        scripts_json = json.dumps(scripts) if scripts else None
        engines_json = json.dumps(engines) if engines else None
        workspaces_json = json.dumps(workspaces) if workspaces else None

        self.generic_batches['package_configs'].append((file_path, package_name, version,
                                                        deps_json, dev_deps_json, peer_deps_json,
                                                        scripts_json, engines_json, workspaces_json,
                                                        is_private))

    def add_lock_analysis(self, file_path: str, lock_type: str,
                         package_manager_version: Optional[str],
                         total_packages: int, duplicate_packages: Optional[Dict],
                         lock_file_version: Optional[str]):
        """Add a lock file analysis result to the batch."""
        duplicates_json = json.dumps(duplicate_packages) if duplicate_packages else None

        self.generic_batches['lock_analysis'].append((file_path, lock_type, package_manager_version,
                                                      total_packages, duplicates_json, lock_file_version))

    def add_import_style(self, file_path: str, line: int, package: str,
                        import_style: str, imported_names: Optional[List[str]] = None,
                        alias_name: Optional[str] = None, full_statement: Optional[str] = None):
        """Add an import style record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch import style record (without imported_names column)
        - Phase 2: Batch junction records for each imported name

        NO FALLBACKS. If imported_names is malformed, hard fail.
        """
        # Phase 1: Add import style record (5 params, no imported_names column)
        self.generic_batches['import_styles'].append((file_path, line, package, import_style,
                                                      alias_name, full_statement))

        # Phase 2: Add junction records for each imported name
        if imported_names:
            for imported_name in imported_names:
                if not imported_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['import_style_names'].append((file_path, line, imported_name))

    def add_framework(self, name, version, language, path, source, is_primary=False):
        """Add framework to batch."""
        # Skip if no name provided
        if not name:
            return
        self.generic_batches['frameworks'].append((name, version, language, path, source, is_primary))
        if len(self.generic_batches['frameworks']) >= self.batch_size:
            self.flush_batch()

    def add_framework_safe_sink(self, framework_id, pattern, sink_type, is_safe, reason):
        """Add framework safe sink to batch."""
        self.generic_batches['framework_safe_sinks'].append((framework_id, pattern, sink_type, is_safe, reason))
        if len(self.generic_batches['framework_safe_sinks']) >= self.batch_size:
            self.flush_batch()

    def write_findings_batch(self, findings: List[dict], tool_name: str):
        """Write findings to database using batch insert for dual-write pattern.

        This method implements the dual-write architecture where findings are written
        to BOTH the database (for FCE performance) AND JSON files (for AI consumption).

        Args:
            findings: List of finding dicts from any tool (patterns, taint, lint, etc.)
            tool_name: Name of the tool that generated findings (e.g., 'patterns', 'taint')

        Notes:
            - Normalizes findings to standard format (handles different field names)
            - Uses batch inserts for performance (batch_size from config)
            - Automatically commits after all batches complete
            - Optional fields (column, cwe, confidence) are gracefully handled
        """
        if not findings:
            return

        from datetime import datetime, UTC

        cursor = self.conn.cursor()

        # Normalize findings to standard format
        normalized = []
        for f in findings:
            # Extract structured data from additional_info or details_json
            details = f.get('additional_info', f.get('details_json', {}))

            # JSON serialize if it's a dict, otherwise use empty object
            if isinstance(details, dict):
                details_str = json.dumps(details)
            elif isinstance(details, str):
                # Already JSON string, validate it
                try:
                    json.loads(details)
                    details_str = details
                except (json.JSONDecodeError, TypeError):
                    details_str = '{}'
            else:
                details_str = '{}'

            # Handle different finding formats from various tools
            # Try multiple field names for compatibility
            rule_value = f.get('rule')
            if not rule_value:
                rule_value = f.get('pattern', f.get('pattern_name', f.get('code', 'unknown-rule')))
            if isinstance(rule_value, str):
                rule_value = rule_value.strip() or 'unknown-rule'
            else:
                rule_value = str(rule_value) if rule_value is not None else 'unknown-rule'

            file_path = f.get('file', '')
            if not isinstance(file_path, str):
                file_path = str(file_path or '')

            normalized.append((
                file_path,
                int(f.get('line', 0)),
                f.get('column'),  # Optional
                rule_value,
                f.get('tool', tool_name),
                f.get('message', ''),
                f.get('severity', 'medium'),  # Default to medium if not specified
                f.get('category'),  # Optional
                f.get('confidence'),  # Optional
                f.get('code_snippet'),  # Optional
                f.get('cwe'),  # Optional
                f.get('timestamp', datetime.now(UTC).isoformat()),
                details_str  # Structured data
            ))

        # Batch insert using configured batch size for performance
        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i:i+self.batch_size]
            cursor.executemany(
                """INSERT INTO findings_consolidated
                   (file, line, column, rule, tool, message, severity, category,
                    confidence, code_snippet, cwe, timestamp, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )

        # Commit immediately for findings (not part of normal batch cycle)
        self.conn.commit()

        # Debug logging if enabled
        if hasattr(self, '_debug') and self._debug:
            print(f"[DB] Wrote {len(findings)} findings from {tool_name} to findings_consolidated")

    # ========================================================
    # TERRAFORM BATCH METHODS
    # ========================================================

    def add_terraform_file(self, file_path: str, module_name: Optional[str] = None,
                          stack_name: Optional[str] = None, backend_type: Optional[str] = None,
                          providers_json: Optional[str] = None, is_module: bool = False,
                          module_source: Optional[str] = None):
        """Add a Terraform file record to the batch."""
        self.generic_batches['terraform_files'].append((
            file_path, module_name, stack_name, backend_type,
            providers_json, is_module, module_source
        ))

    def add_terraform_resource(self, resource_id: str, file_path: str, resource_type: str,
                               resource_name: str, module_path: Optional[str] = None,
                               properties_json: Optional[str] = None,
                               depends_on_json: Optional[str] = None,
                               sensitive_flags_json: Optional[str] = None,
                               has_public_exposure: bool = False,
                               line: Optional[int] = None):
        """Add a Terraform resource record to the batch."""
        self.generic_batches['terraform_resources'].append((
            resource_id, file_path, resource_type, resource_name,
            module_path, properties_json, depends_on_json,
            sensitive_flags_json, has_public_exposure, line
        ))

    def add_terraform_variable(self, variable_id: str, file_path: str, variable_name: str,
                               variable_type: Optional[str] = None,
                               default_json: Optional[str] = None,
                               is_sensitive: bool = False,
                               description: str = '',
                               source_file: Optional[str] = None,
                               line: Optional[int] = None):
        """Add a Terraform variable record to the batch."""
        self.generic_batches['terraform_variables'].append((
            variable_id, file_path, variable_name, variable_type,
            default_json, is_sensitive, description, source_file, line
        ))

    def add_terraform_variable_value(self, file_path: str, variable_name: str,
                                     variable_value_json: Optional[str] = None,
                                     line: Optional[int] = None,
                                     is_sensitive_context: bool = False):
        """Add a .tfvars variable value record to the batch."""
        self.generic_batches['terraform_variable_values'].append((
            file_path,
            variable_name,
            variable_value_json,
            line,
            is_sensitive_context,
        ))

    def add_terraform_output(self, output_id: str, file_path: str, output_name: str,
                            value_json: Optional[str] = None,
                            is_sensitive: bool = False,
                            description: str = '',
                            line: Optional[int] = None):
        """Add a Terraform output record to the batch."""
        self.generic_batches['terraform_outputs'].append((
            output_id, file_path, output_name, value_json,
            is_sensitive, description, line
        ))

    def add_terraform_finding(self, finding_id: str, file_path: str,
                             resource_id: Optional[str] = None,
                             category: str = '',
                             severity: str = 'medium',
                             title: str = '',
                             description: str = '',
                             graph_context_json: Optional[str] = None,
                             remediation: str = '',
                             line: Optional[int] = None):
        """Add a Terraform finding record to the batch."""
        self.generic_batches['terraform_findings'].append((
            finding_id, file_path, resource_id, category,
            severity, title, description, graph_context_json,
            remediation, line
        ))

    # ========================================================================
    # AWS CDK (Cloud Development Kit) Infrastructure-as-Code Methods
    # ========================================================================

    def add_cdk_construct(self, file_path: str, line: int, cdk_class: str,
                         construct_name: Optional[str], construct_id: str):
        """Add a CDK construct record to the batch.

        Args:
            file_path: Path to Python file containing construct
            line: Line number of construct instantiation
            cdk_class: CDK class name (e.g., 's3.Bucket', 'aws_cdk.aws_s3.Bucket')
            construct_name: CDK logical ID (nullable - 2nd positional arg)
            construct_id: Composite key: {file}::L{line}::{class}::{name}
        """
        # DEBUG: Log all construct_ids being added to batch
        if os.environ.get('THEAUDITOR_CDK_DEBUG') == '1':
            print(f"[CDK-DB] Adding to batch: {construct_id}")

        self.generic_batches['cdk_constructs'].append((
            construct_id, file_path, line, cdk_class, construct_name
        ))

    def add_cdk_construct_property(self, construct_id: str, property_name: str,
                                   property_value_expr: str, line: int):
        """Add a CDK construct property record to the batch.

        Args:
            construct_id: FK to cdk_constructs.construct_id
            property_name: Property keyword argument name (e.g., 'public_read_access')
            property_value_expr: Serialized property value via ast.unparse()
            line: Line number of property definition
        """
        self.generic_batches['cdk_construct_properties'].append((
            construct_id, property_name, property_value_expr, line
        ))

    def add_cdk_finding(self, finding_id: str, file_path: str,
                       construct_id: Optional[str] = None,
                       category: str = '',
                       severity: str = 'medium',
                       title: str = '',
                       description: str = '',
                       remediation: str = '',
                       line: Optional[int] = None):
        """Add a CDK security finding record to the batch.

        Args:
            finding_id: Unique finding identifier
            file_path: Path to CDK file with issue
            construct_id: Optional FK to cdk_constructs (nullable for file-level findings)
            category: Finding category (e.g., 'public_exposure', 'missing_encryption')
            severity: Severity level ('critical', 'high', 'medium', 'low')
            title: Short finding title
            description: Detailed finding description
            remediation: Suggested fix
            line: Line number of issue
        """
        self.generic_batches['cdk_findings'].append((
            finding_id, file_path, construct_id, category,
            severity, title, description, remediation, line
        ))

    # ========================================================================
    # GitHub Actions CI/CD Workflow Security Methods
    # ========================================================================

    def add_github_workflow(self, workflow_path: str, workflow_name: Optional[str],
                           on_triggers: str, permissions: Optional[str] = None,
                           concurrency: Optional[str] = None, env: Optional[str] = None):
        """Add a GitHub Actions workflow record to the batch.

        Args:
            workflow_path: Path to workflow file (.github/workflows/ci.yml)
            workflow_name: Workflow name from 'name:' field or filename
            on_triggers: JSON array of trigger events
            permissions: JSON object of workflow-level permissions
            concurrency: JSON object of concurrency settings
            env: JSON object of workflow-level environment variables
        """
        self.generic_batches['github_workflows'].append((
            workflow_path, workflow_name, on_triggers, permissions, concurrency, env
        ))

    def add_github_job(self, job_id: str, workflow_path: str, job_key: str,
                      job_name: Optional[str], runs_on: Optional[str],
                      strategy: Optional[str] = None, permissions: Optional[str] = None,
                      env: Optional[str] = None, if_condition: Optional[str] = None,
                      timeout_minutes: Optional[int] = None,
                      uses_reusable_workflow: bool = False,
                      reusable_workflow_path: Optional[str] = None):
        """Add a GitHub Actions job record to the batch.

        Args:
            job_id: Composite PK (workflow_path||':'||job_key)
            workflow_path: FK to github_workflows
            job_key: Job key from YAML (e.g., 'build', 'test')
            job_name: Optional name: field
            runs_on: JSON array of runner labels (supports matrix)
            strategy: JSON object of matrix strategy
            permissions: JSON object of job-level permissions
            env: JSON object of job-level env vars
            if_condition: Conditional expression for job execution
            timeout_minutes: Job timeout
            uses_reusable_workflow: True if uses: workflow.yml
            reusable_workflow_path: Path to reusable workflow if used
        """
        self.generic_batches['github_jobs'].append((
            job_id, workflow_path, job_key, job_name, runs_on, strategy,
            permissions, env, if_condition, timeout_minutes,
            uses_reusable_workflow, reusable_workflow_path
        ))

    def add_github_job_dependency(self, job_id: str, needs_job_id: str):
        """Add a GitHub Actions job dependency edge (needs: relationship).

        Args:
            job_id: FK to github_jobs (dependent job)
            needs_job_id: FK to github_jobs (dependency job)
        """
        self.generic_batches['github_job_dependencies'].append((
            job_id, needs_job_id
        ))

    def add_github_step(self, step_id: str, job_id: str, sequence_order: int,
                       step_name: Optional[str], uses_action: Optional[str],
                       uses_version: Optional[str], run_script: Optional[str],
                       shell: Optional[str], env: Optional[str],
                       with_args: Optional[str], if_condition: Optional[str],
                       timeout_minutes: Optional[int], continue_on_error: bool = False):
        """Add a GitHub Actions step record to the batch.

        Args:
            step_id: Composite PK (job_id||':'||sequence_order)
            job_id: FK to github_jobs
            sequence_order: Step order within job (0-indexed)
            step_name: Optional name: field
            uses_action: Action reference (e.g., 'actions/checkout@v4')
            uses_version: Version/ref extracted from uses
            run_script: Shell script content from run: field
            shell: Shell type (bash, pwsh, python)
            env: JSON object of step-level env vars
            with_args: JSON object of action inputs (with: field)
            if_condition: Conditional expression for step execution
            timeout_minutes: Step timeout
            continue_on_error: Continue on failure flag
        """
        self.generic_batches['github_steps'].append((
            step_id, job_id, sequence_order, step_name, uses_action, uses_version,
            run_script, shell, env, with_args, if_condition, timeout_minutes,
            continue_on_error
        ))

    def add_github_step_output(self, step_id: str, output_name: str, output_expression: str):
        """Add a GitHub Actions step output declaration.

        Args:
            step_id: FK to github_steps
            output_name: Output key
            output_expression: Value expression
        """
        self.generic_batches['github_step_outputs'].append((
            step_id, output_name, output_expression
        ))

    def add_github_step_reference(self, step_id: str, reference_location: str,
                                  reference_type: str, reference_path: str):
        """Add a GitHub Actions step reference (${{ }} expression).

        Args:
            step_id: FK to github_steps
            reference_location: Where reference appears ('run', 'env', 'with', 'if')
            reference_type: Type of reference ('github', 'secrets', 'env', 'needs', 'steps')
            reference_path: Full path (e.g., 'github.event.pull_request.head.sha')
        """
        self.generic_batches['github_step_references'].append((
            step_id, reference_location, reference_type, reference_path
        ))

    def get_framework_id(self, name, language):
        """Get framework ID from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM frameworks WHERE name = ? AND language = ?", (name, language))
        result = cursor.fetchone()
        return result[0] if result else None


# Standalone function for backward compatibility
def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite database schema - backward compatibility wrapper.

    Args:
        conn: SQLite connection (remains open after schema creation)
    """
    # Use the existing connection to create schema
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = conn
    manager.cursor = conn.cursor()
    manager.batch_size = 200

    # Initialize generic batch system
    manager.generic_batches = defaultdict(list)
    manager.cfg_id_mapping = {}
    manager.jwt_patterns_batch = []

    # Create the schema using the existing connection
    manager.create_schema()
    # Don't close - let caller handle connection lifecycle
