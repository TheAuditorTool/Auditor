"""Base database manager with core infrastructure.

This module contains the BaseDatabaseManager class which provides:
- Database connection management
- Transaction control
- Schema creation and validation
- Generic batch flushing system
- Table clearing

All language-specific add_* methods are provided by mixin classes.
"""

import json
import os
import sqlite3
import sys
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

        self.conn = sqlite3.connect(db_path, timeout=60)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        if batch_size <= 0:
            self.batch_size = DEFAULT_BATCH_SIZE
        elif batch_size > MAX_BATCH_SIZE:
            self.batch_size = MAX_BATCH_SIZE
        else:
            self.batch_size = batch_size

        self.generic_batches: dict[str, list[tuple]] = defaultdict(list)

        self.cfg_id_mapping: dict[int, int] = {}

        self.jwt_patterns_batch: list[dict] = []

    def begin_transaction(self) -> None:
        """Start a new transaction."""
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        """Commit the current transaction."""
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to commit database changes: {e}") from e

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.conn.rollback()

    def close(self) -> None:
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
        import sys

        from ..schema import validate_all_tables

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

        print(
            "[SCHEMA] Note: Some mismatches may be due to migration columns (expected)",
            file=sys.stderr,
        )
        return False

    def create_schema(self) -> None:
        """Create all database tables and indexes using schema.py definitions.

        ARCHITECTURE: Schema-driven table creation.
        - Loops over TABLES registry from schema.py
        - Calls TableSchema.create_table_sql() for CREATE TABLE
        - Calls TableSchema.create_indexes_sql() for CREATE INDEX
        - NO hardcoded SQL (909 lines → 20 lines)
        """
        cursor = self.conn.cursor()

        for table_name, table_schema in TABLES.items():
            create_table_sql = table_schema.create_table_sql()
            cursor.execute(create_table_sql)

            for create_index_sql in table_schema.create_indexes_sql():
                cursor.execute(create_index_sql)

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

    def clear_tables(self) -> None:
        """Clear all existing data from tables using schema.py registry.

        ARCHITECTURE: Schema-driven table clearing.
        - Loops over TABLES registry from schema.py
        - Executes DELETE FROM for each table
        - NO hardcoded table list (48 lines → 10 lines)
        """
        cursor = self.conn.cursor()

        try:
            for table_name in TABLES:
                validated_table = validate_table_name(table_name)
                cursor.execute(f"DELETE FROM {validated_table}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to clear existing data: {e}") from e

    def flush_generic_batch(self, table_name: str, insert_mode: str = "INSERT") -> None:
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
            return

        schema = get_table_schema(table_name)
        if not schema:
            raise RuntimeError(f"No schema found for table '{table_name}' - check TABLES registry")

        all_cols = [col for col in schema.columns if col.name != "id" and not col.autoincrement]

        tuple_size = len(batch[0]) if batch else 0

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
            print(f"[DEBUG] Flush: {table_name}", file=sys.stderr)
            print(f"  all_cols count: {len(all_cols)}", file=sys.stderr)
            print(f"  all_cols names: {[col.name for col in all_cols]}", file=sys.stderr)
            print(f"  tuple_size from batch[0]: {tuple_size}", file=sys.stderr)
            if batch:
                print(f"  batch[0]: {batch[0]}", file=sys.stderr)

        columns = [col.name for col in all_cols[:tuple_size]]

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
            print(f"  columns taken (first {tuple_size}): {columns}", file=sys.stderr)

        if len(columns) != tuple_size:
            raise RuntimeError(
                f"Column mismatch for table '{table_name}': "
                f"add_* method provides {tuple_size} values but schema has {len(all_cols)} columns. "
                f"Taking first {tuple_size}: {columns}. "
                f"Verify schema column order matches add_* parameter order."
            )

        placeholders = ", ".join(["?" for _ in columns])
        column_list = ", ".join(columns)
        query = f"{insert_mode} INTO {table_name} ({column_list}) VALUES ({placeholders})"

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
            print(f"  query: {query}", file=sys.stderr)

        cursor = self.conn.cursor()
        try:
            cursor.executemany(query, batch)
            if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
                print(f"[DEBUG] Flush: {table_name} SUCCESS", file=sys.stderr)
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
                print(f"[DEBUG] Flush: {table_name} FAILED - {e}", file=sys.stderr)
            raise

        self.generic_batches[table_name] = []

    def flush_batch(self, batch_idx: int | None = None) -> None:
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
            flush_order = [
                ("files", "INSERT OR REPLACE"),
                ("config_files", "INSERT OR REPLACE"),
                ("plans", "INSERT"),
                ("plan_specs", "INSERT"),
                ("plan_tasks", "INSERT"),
                ("code_snapshots", "INSERT"),
                ("code_diffs", "INSERT"),
                ("refactor_candidates", "INSERT"),
                ("refactor_history", "INSERT"),
                ("refs", "INSERT"),
                ("symbols", "INSERT"),
                ("class_properties", "INSERT"),
                ("env_var_usage", "INSERT"),
                ("orm_relationships", "INSERT"),
                ("sql_objects", "INSERT"),
                ("sql_queries", "INSERT"),
                ("orm_queries", "INSERT"),
                ("prisma_models", "INSERT"),
                ("api_endpoints", "INSERT"),
                ("router_mounts", "INSERT"),
                ("api_endpoint_controls", "INSERT"),
                ("express_middleware_chains", "INSERT"),
                ("python_orm_models", "INSERT"),
                ("python_orm_fields", "INSERT"),
                ("python_routes", "INSERT"),
                ("python_validators", "INSERT"),
                ("python_package_configs", "INSERT"),
                ("python_decorators", "INSERT"),
                ("python_django_views", "INSERT"),
                ("python_django_middleware", "INSERT"),
                ("python_loops", "INSERT"),
                ("python_branches", "INSERT"),
                ("python_functions_advanced", "INSERT"),
                ("python_io_operations", "INSERT"),
                ("python_state_mutations", "INSERT"),
                ("python_class_features", "INSERT"),
                ("python_protocols", "INSERT"),
                ("python_descriptors", "INSERT"),
                ("python_type_definitions", "INSERT"),
                ("python_literals", "INSERT"),
                ("python_protocol_methods", "INSERT"),
                ("python_typeddict_fields", "INSERT"),
                ("python_security_findings", "INSERT"),
                ("python_test_cases", "INSERT"),
                ("python_test_fixtures", "INSERT"),
                ("python_framework_config", "INSERT"),
                ("python_validation_schemas", "INSERT"),
                ("python_fixture_params", "INSERT"),
                ("python_framework_methods", "INSERT"),
                ("python_schema_validators", "INSERT"),
                ("python_operators", "INSERT"),
                ("python_collections", "INSERT"),
                ("python_stdlib_usage", "INSERT"),
                ("python_imports_advanced", "INSERT"),
                ("python_expressions", "INSERT"),
                ("python_comprehensions", "INSERT"),
                ("python_control_statements", "INSERT"),
                ("sql_query_tables", "INSERT"),
                ("docker_images", "INSERT"),
                ("compose_services", "INSERT"),
                ("nginx_configs", "INSERT"),
                ("terraform_files", "INSERT"),
                ("terraform_resources", "INSERT"),
                ("terraform_variables", "INSERT"),
                ("terraform_variable_values", "INSERT"),
                ("terraform_outputs", "INSERT"),
                ("terraform_findings", "INSERT"),
                ("cdk_constructs", "INSERT"),
                ("cdk_construct_properties", "INSERT"),
                ("cdk_findings", "INSERT"),
                ("graphql_schemas", "INSERT"),
                ("graphql_types", "INSERT"),
                ("graphql_fields", "INSERT"),
                ("graphql_field_args", "INSERT"),
                ("graphql_resolver_mappings", "INSERT"),
                ("graphql_resolver_params", "INSERT"),
                ("graphql_execution_edges", "INSERT"),
                ("graphql_findings_cache", "INSERT"),
                ("github_workflows", "INSERT"),
                ("github_jobs", "INSERT"),
                ("github_job_dependencies", "INSERT"),
                ("github_steps", "INSERT"),
                ("github_step_outputs", "INSERT"),
                ("github_step_references", "INSERT"),
                ("assignments", "INSERT"),
                ("assignment_sources", "INSERT"),
                ("function_call_args", "INSERT"),
                ("function_returns", "INSERT"),
                ("function_return_sources", "INSERT"),
                ("react_components", "INSERT"),
                ("react_component_hooks", "INSERT"),
                ("react_hooks", "INSERT"),
                ("react_hook_dependencies", "INSERT"),
                ("variable_usage", "INSERT"),
                ("object_literals", "INSERT"),
                ("function_returns_jsx", "INSERT OR REPLACE"),
                ("function_return_sources_jsx", "INSERT"),
                ("symbols_jsx", "INSERT OR REPLACE"),
                ("assignments_jsx", "INSERT OR REPLACE"),
                ("assignment_sources_jsx", "INSERT"),
                ("function_call_args_jsx", "INSERT OR REPLACE"),
                ("vue_components", "INSERT"),
                ("vue_hooks", "INSERT"),
                ("vue_directives", "INSERT"),
                ("vue_provide_inject", "INSERT"),
                ("type_annotations", "INSERT OR REPLACE"),
                ("package_configs", "INSERT OR REPLACE"),
                ("lock_analysis", "INSERT OR REPLACE"),
                ("import_styles", "INSERT"),
                ("import_style_names", "INSERT"),
                ("frameworks", "INSERT OR IGNORE"),
                ("framework_safe_sinks", "INSERT OR IGNORE"),
            ]

            self._flush_jwt_patterns()

            if "cfg_blocks" in self.generic_batches and self.generic_batches["cfg_blocks"]:
                id_mapping = {}

                for batch_item in self.generic_batches["cfg_blocks"]:
                    (
                        file_path,
                        function_name,
                        block_type,
                        start_line,
                        end_line,
                        condition_expr,
                        temp_id,
                    ) = batch_item

                    cursor.execute(
                        """INSERT INTO cfg_blocks (file, function_name, block_type, start_line, end_line, condition_expr)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            file_path,
                            function_name,
                            block_type,
                            start_line,
                            end_line,
                            condition_expr,
                        ),
                    )

                    real_id = cursor.lastrowid
                    id_mapping[temp_id] = real_id

                self.generic_batches["cfg_blocks"] = []
                self.cfg_id_mapping.update(id_mapping)

                if "cfg_edges" in self.generic_batches and self.generic_batches["cfg_edges"]:
                    updated_edges = []
                    for (
                        file_path,
                        function_name,
                        source_id,
                        target_id,
                        edge_type,
                    ) in self.generic_batches["cfg_edges"]:
                        real_source = (
                            id_mapping.get(source_id, source_id) if source_id < 0 else source_id
                        )
                        real_target = (
                            id_mapping.get(target_id, target_id) if target_id < 0 else target_id
                        )
                        updated_edges.append(
                            (file_path, function_name, real_source, real_target, edge_type)
                        )

                    cursor.executemany(
                        """INSERT INTO cfg_edges (file, function_name, source_block_id, target_block_id, edge_type)
                           VALUES (?, ?, ?, ?, ?)""",
                        updated_edges,
                    )
                    self.generic_batches["cfg_edges"] = []

                if (
                    "cfg_block_statements" in self.generic_batches
                    and self.generic_batches["cfg_block_statements"]
                ):
                    updated_statements = []
                    for block_id, statement_type, line, statement_text in self.generic_batches[
                        "cfg_block_statements"
                    ]:
                        real_block_id = (
                            id_mapping.get(block_id, block_id) if block_id < 0 else block_id
                        )
                        updated_statements.append(
                            (real_block_id, statement_type, line, statement_text)
                        )

                    cursor.executemany(
                        """INSERT INTO cfg_block_statements (block_id, statement_type, line, statement_text)
                           VALUES (?, ?, ?, ?)""",
                        updated_statements,
                    )
                    self.generic_batches["cfg_block_statements"] = []

            if "cfg_blocks_jsx" in self.generic_batches and self.generic_batches["cfg_blocks_jsx"]:
                id_mapping_jsx = {}

                for batch_item in self.generic_batches["cfg_blocks_jsx"]:
                    (
                        file_path,
                        function_name,
                        block_type,
                        start_line,
                        end_line,
                        condition_expr,
                        jsx_mode,
                        extraction_pass,
                        temp_id,
                    ) = batch_item

                    cursor.execute(
                        """INSERT INTO cfg_blocks_jsx (file, function_name, block_type, start_line, end_line, condition_expr, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            file_path,
                            function_name,
                            block_type,
                            start_line,
                            end_line,
                            condition_expr,
                            jsx_mode,
                            extraction_pass,
                        ),
                    )

                    real_id = cursor.lastrowid
                    id_mapping_jsx[temp_id] = real_id

                self.generic_batches["cfg_blocks_jsx"] = []

                if (
                    "cfg_edges_jsx" in self.generic_batches
                    and self.generic_batches["cfg_edges_jsx"]
                ):
                    updated_edges_jsx = []
                    for (
                        file_path,
                        function_name,
                        source_id,
                        target_id,
                        edge_type,
                        jsx_mode,
                        extraction_pass,
                    ) in self.generic_batches["cfg_edges_jsx"]:
                        real_source = (
                            id_mapping_jsx.get(source_id, source_id) if source_id < 0 else source_id
                        )
                        real_target = (
                            id_mapping_jsx.get(target_id, target_id) if target_id < 0 else target_id
                        )
                        updated_edges_jsx.append(
                            (
                                file_path,
                                function_name,
                                real_source,
                                real_target,
                                edge_type,
                                jsx_mode,
                                extraction_pass,
                            )
                        )

                    cursor.executemany(
                        """INSERT INTO cfg_edges_jsx (file, function_name, source_block_id, target_block_id, edge_type, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        updated_edges_jsx,
                    )
                    self.generic_batches["cfg_edges_jsx"] = []

                if (
                    "cfg_block_statements_jsx" in self.generic_batches
                    and self.generic_batches["cfg_block_statements_jsx"]
                ):
                    updated_statements_jsx = []
                    for (
                        block_id,
                        statement_type,
                        line,
                        statement_text,
                        jsx_mode,
                        extraction_pass,
                    ) in self.generic_batches["cfg_block_statements_jsx"]:
                        real_block_id = (
                            id_mapping_jsx.get(block_id, block_id) if block_id < 0 else block_id
                        )
                        updated_statements_jsx.append(
                            (
                                real_block_id,
                                statement_type,
                                line,
                                statement_text,
                                jsx_mode,
                                extraction_pass,
                            )
                        )

                    cursor.executemany(
                        """INSERT INTO cfg_block_statements_jsx (block_id, statement_type, line, statement_text, jsx_mode, extraction_pass)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        updated_statements_jsx,
                    )
                    self.generic_batches["cfg_block_statements_jsx"] = []

            import os
            import sys

            for table_name, insert_mode in flush_order:
                if table_name in self.generic_batches and self.generic_batches[table_name]:
                    self.flush_generic_batch(table_name, insert_mode)

        except sqlite3.Error as e:
            import os
            import sys

            if os.environ.get("THEAUDITOR_DEBUG") == "1":
                print(f"\n[DEBUG] SQL Error: {type(e).__name__}: {e}", file=sys.stderr)
                print("[DEBUG] Tables with pending batches:", file=sys.stderr)
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        print(f"[DEBUG]   {table_name}: {len(batch)} records", file=sys.stderr)

            if "UNIQUE constraint failed" in str(e):
                pass

            if batch_idx is not None:
                raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}") from e
            else:
                raise RuntimeError(f"Batch insert failed: {e}") from e

    def _flush_jwt_patterns(self):
        """Flush JWT patterns batch (special dict-based interface).

        KEPT FOR BACKWARD COMPATIBILITY: add_jwt_pattern uses dict format.
        """
        if not self.jwt_patterns_batch:
            return
        cursor = self.conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO jwt_patterns
            (file_path, line_number, pattern_type, pattern_text, secret_source, algorithm)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            [
                (
                    p["file_path"],
                    p["line_number"],
                    p["pattern_type"],
                    p["pattern_text"],
                    p["secret_source"],
                    p["algorithm"],
                )
                for p in self.jwt_patterns_batch
            ],
        )
        self.jwt_patterns_batch.clear()

    def write_findings_batch(self, findings: list[dict], tool_name: str) -> None:
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

        from datetime import UTC, datetime

        cursor = self.conn.cursor()

        normalized = []
        for f in findings:
            details = f.get("additional_info", f.get("details_json", {}))

            if isinstance(details, dict):
                details_str = json.dumps(details)
            elif isinstance(details, str):
                try:
                    json.loads(details)
                    details_str = details
                except (json.JSONDecodeError, TypeError):
                    details_str = "{}"
            else:
                details_str = "{}"

            rule_value = f.get("rule")
            if not rule_value:
                rule_value = f.get("pattern", f.get("pattern_name", f.get("code", "unknown-rule")))
            if isinstance(rule_value, str):
                rule_value = rule_value.strip() or "unknown-rule"
            else:
                rule_value = str(rule_value) if rule_value is not None else "unknown-rule"

            file_path = f.get("file", "")
            if not isinstance(file_path, str):
                file_path = str(file_path or "")

            normalized.append(
                (
                    file_path,
                    int(f.get("line", 0)),
                    f.get("column"),
                    rule_value,
                    f.get("tool", tool_name),
                    f.get("message", ""),
                    f.get("severity", "medium"),
                    f.get("category"),
                    f.get("confidence"),
                    f.get("code_snippet"),
                    f.get("cwe"),
                    f.get("timestamp", datetime.now(UTC).isoformat()),
                    details_str,
                )
            )

        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i : i + self.batch_size]
            cursor.executemany(
                """INSERT INTO findings_consolidated
                   (file, line, column, rule, tool, message, severity, category,
                    confidence, code_snippet, cwe, timestamp, details_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )

        self.conn.commit()

        if hasattr(self, "_debug") and self._debug:
            print(f"[DB] Wrote {len(findings)} findings from {tool_name} to findings_consolidated")
