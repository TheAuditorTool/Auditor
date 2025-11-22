"""Base database manager with core infrastructure.

This module contains the BaseDatabaseManager class which provides:
- Database connection management
- Transaction control
- Schema creation and validation
- Generic batch flushing system
- Table clearing

All language-specific add_* methods are provided by mixin classes.
"""


import sqlite3
import json
import os
from typing import Any, List, Dict, Optional
from pathlib import Path
from collections import defaultdict

from ..config import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE
from ..schema import TABLES, get_table_schema


def validate_table_name(table: str) -> str:
    """Validate table name against schema to prevent SQL injection.

    Args:
        table: Table name to validate

    Returns:
        The validated table name

    Raises:
        ValueError: If table name is not in TABLES registry
    """
    if table not in TABLES:
        raise ValueError(f"Invalid table name: {table}. Must be one of the schema-defined tables.")
    return table


class BaseDatabaseManager:
    """Base database manager providing core infrastructure.

    This class implements schema-driven database operations and generic batching.
    It should be used as a base class with language-specific mixins.
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
        self.generic_batches: dict[str, list[tuple]] = defaultdict(list)

        # CFG special case: ID mapping for AUTOINCREMENT
        # Maps temporary negative IDs to real database IDs
        self.cfg_id_mapping: dict[int, int] = {}

        # JWT special case: Batch list for dict-based interface
        # Kept for backward compatibility with add_jwt_pattern signature
        self.jwt_patterns_batch: list[dict] = []

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
        from ..schema import validate_all_tables
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
                # Validate table name to prevent SQL injection (should never fail for TABLES)
                validated_table = validate_table_name(table_name)
                cursor.execute(f"DELETE FROM {validated_table}")
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

        # Get ALL columns except AUTOINCREMENT columns
        # DEFAULT values are IRRELEVANT - the add_* method signature determines what's provided
        # Schema column order MUST match add_* method parameter order
        # NOTE: Hybrid approach to support both old and new table patterns:
        #       - Old tables: autoincrement=False but named 'id' (legacy pattern)
        #       - New tables: autoincrement=True with custom names (type_id, field_id, etc.)
        all_cols = [col for col in schema.columns if col.name != 'id' and not col.autoincrement]

        # Determine how many columns the add_* method actually provides
        # by checking the first batch tuple size
        tuple_size = len(batch[0]) if batch else 0

        import os, sys
        if os.environ.get('THEAUDITOR_DEBUG') == '1' and table_name.startswith('graphql_'):
            print(f"[DEBUG] Flush: {table_name}", file=sys.stderr)
            print(f"  all_cols count: {len(all_cols)}", file=sys.stderr)
            print(f"  all_cols names: {[col.name for col in all_cols]}", file=sys.stderr)
            print(f"  tuple_size from batch[0]: {tuple_size}", file=sys.stderr)
            if batch:
                print(f"  batch[0]: {batch[0]}", file=sys.stderr)

        # Take first N columns matching tuple size
        # This handles legacy tables where columns were added but add_* not updated
        columns = [col.name for col in all_cols[:tuple_size]]

        if os.environ.get('THEAUDITOR_DEBUG') == '1' and table_name.startswith('graphql_'):
            print(f"  columns taken (first {tuple_size}): {columns}", file=sys.stderr)

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

        if os.environ.get('THEAUDITOR_DEBUG') == '1' and table_name.startswith('graphql_'):
            print(f"  query: {query}", file=sys.stderr)

        # Execute batch insert
        cursor = self.conn.cursor()
        try:
            cursor.executemany(query, batch)
            if os.environ.get('THEAUDITOR_DEBUG') == '1' and table_name.startswith('graphql_'):
                print(f"[DEBUG] Flush: {table_name} SUCCESS", file=sys.stderr)
        except Exception as e:
            if os.environ.get('THEAUDITOR_DEBUG') == '1' and table_name.startswith('graphql_'):
                print(f"[DEBUG] Flush: {table_name} FAILED - {e}", file=sys.stderr)
            raise

        # Clear batch after flush
        self.generic_batches[table_name] = []

    def flush_batch(self, batch_idx: int | None = None):
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

                # Planning tables (meta-system tables for aud planning commands)
                # FK dependencies: plans → plan_specs → plan_tasks → code_snapshots → code_diffs
                ('plans', 'INSERT'),
                ('plan_specs', 'INSERT'),  # Depends on plans FK
                ('plan_tasks', 'INSERT'),  # Depends on plans and plan_specs FK
                ('code_snapshots', 'INSERT'),  # Depends on plans and plan_tasks FK
                ('code_diffs', 'INSERT'),  # Depends on code_snapshots FK
                ('refactor_candidates', 'INSERT'),  # Independent planning table
                ('refactor_history', 'INSERT'),  # Independent planning table (aud refactor execution log)

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
                ('router_mounts', 'INSERT'),  # PHASE 6.7: Router mount points for full_path resolution
                ('api_endpoint_controls', 'INSERT'),  # Junction table
                ('express_middleware_chains', 'INSERT'),  # PHASE 5: Express middleware execution chains
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

                # Causal Learning Patterns (Week 1 - State Mutations)
                ('python_instance_mutations', 'INSERT'),

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

                # GraphQL tables (Section 7: Taint & FCE Integration)
                # FK dependencies: graphql_schemas → graphql_types → graphql_fields → graphql_field_args
                ('graphql_schemas', 'INSERT'),
                ('graphql_types', 'INSERT'),  # Depends on graphql_schemas FK
                ('graphql_fields', 'INSERT'),  # Depends on graphql_types FK
                ('graphql_field_args', 'INSERT'),  # Depends on graphql_fields FK
                ('graphql_resolver_mappings', 'INSERT'),  # Depends on graphql_fields + symbols FK
                ('graphql_resolver_params', 'INSERT'),  # Depends on graphql_resolver_mappings FK
                ('graphql_execution_edges', 'INSERT'),  # Depends on graphql_fields + symbols FK
                ('graphql_findings_cache', 'INSERT'),  # Independent (findings cache)

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

            # Flush CFG JSX blocks FIRST (must insert before edges/statements)
            # Same special case logic as main CFG tables but for JSX preserved mode
            if 'cfg_blocks_jsx' in self.generic_batches and self.generic_batches['cfg_blocks_jsx']:
                # CFG JSX blocks use temp negative IDs that must be mapped to real IDs
                id_mapping_jsx = {}

                for batch_item in self.generic_batches['cfg_blocks_jsx']:
                    # Extract data (last element is temp_id)
                    file_path, function_name, block_type, start_line, end_line, condition_expr, jsx_mode, extraction_pass, temp_id = batch_item

                    cursor.execute(
                        """INSERT INTO cfg_blocks_jsx (file, function_name, block_type, start_line, end_line, condition_expr, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (file_path, function_name, block_type, start_line, end_line, condition_expr, jsx_mode, extraction_pass)
                    )
                    # Map temporary ID to real AUTOINCREMENT ID
                    real_id = cursor.lastrowid
                    id_mapping_jsx[temp_id] = real_id

                self.generic_batches['cfg_blocks_jsx'] = []

                # Flush CFG JSX edges (map temp IDs to real IDs)
                if 'cfg_edges_jsx' in self.generic_batches and self.generic_batches['cfg_edges_jsx']:
                    updated_edges_jsx = []
                    for file_path, function_name, source_id, target_id, edge_type, jsx_mode, extraction_pass in self.generic_batches['cfg_edges_jsx']:
                        # Map temporary IDs to real IDs
                        real_source = id_mapping_jsx.get(source_id, source_id) if source_id < 0 else source_id
                        real_target = id_mapping_jsx.get(target_id, target_id) if target_id < 0 else target_id
                        updated_edges_jsx.append((file_path, function_name, real_source, real_target, edge_type, jsx_mode, extraction_pass))

                    cursor.executemany(
                        """INSERT INTO cfg_edges_jsx (file, function_name, source_block_id, target_block_id, edge_type, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        updated_edges_jsx
                    )
                    self.generic_batches['cfg_edges_jsx'] = []

                # Flush CFG JSX statements (map temp IDs to real IDs)
                if 'cfg_block_statements_jsx' in self.generic_batches and self.generic_batches['cfg_block_statements_jsx']:
                    updated_statements_jsx = []
                    for block_id, statement_type, line, statement_text, jsx_mode, extraction_pass in self.generic_batches['cfg_block_statements_jsx']:
                        # Map temporary ID to real ID
                        real_block_id = id_mapping_jsx.get(block_id, block_id) if block_id < 0 else block_id
                        updated_statements_jsx.append((real_block_id, statement_type, line, statement_text, jsx_mode, extraction_pass))

                    cursor.executemany(
                        """INSERT INTO cfg_block_statements_jsx (block_id, statement_type, line, statement_text, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        updated_statements_jsx
                    )
                    self.generic_batches['cfg_block_statements_jsx'] = []

            # Flush all generic tables in dependency order
            import os, sys
            for table_name, insert_mode in flush_order:
                if table_name in self.generic_batches and self.generic_batches[table_name]:
                    print(f"[DEBUG] flush_batch: About to flush {table_name} with mode {insert_mode}, batch size {len(self.generic_batches[table_name])}", file=sys.stderr)
                    self.flush_generic_batch(table_name, insert_mode)
                    print(f"[DEBUG] flush_batch: {table_name} flushed successfully", file=sys.stderr)

        except sqlite3.Error as e:
            # DEBUG: Enhanced error reporting for constraint failures
            import os, sys
            if os.environ.get('THEAUDITOR_DEBUG') == '1':
                print(f"\n[DEBUG] SQL Error: {type(e).__name__}: {e}", file=sys.stderr)
                print(f"[DEBUG] Tables with pending batches:", file=sys.stderr)
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        print(f"[DEBUG]   {table_name}: {len(batch)} records", file=sys.stderr)

            if "UNIQUE constraint failed" in str(e):
                print(f"\n[DEBUG] UNIQUE constraint violation: {e}", file=sys.stderr)
                # Report which table had the violation
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        print(f"[DEBUG] Table '{table_name}' has {len(batch)} pending records", file=sys.stderr)

                # If cdk_constructs failure, show actual construct_ids
                if "cdk_constructs.construct_id" in str(e):
                    if 'cdk_constructs' in self.generic_batches:
                        print(f"[DEBUG] CDK construct_ids in batch:", file=sys.stderr)
                        from collections import Counter
                        construct_ids = [record[0] for record in self.generic_batches['cdk_constructs']]
                        duplicates = {k: v for k, v in Counter(construct_ids).items() if v > 1}
                        for construct_id in sorted(set(construct_ids)):
                            count = construct_ids.count(construct_id)
                            if count > 1:
                                print(f"[DEBUG]   DUPLICATE (x{count}): {construct_id}", file=sys.stderr)
                            else:
                                print(f"[DEBUG]   {construct_id}", file=sys.stderr)

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

    def write_findings_batch(self, findings: list[dict], tool_name: str):
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
