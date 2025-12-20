"""Base database manager with core infrastructure."""

import os
import sqlite3
from collections import defaultdict

from theauditor.utils.logging import logger

from ..config import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE
from ..schema import FLUSH_ORDER, TABLES, get_table_schema


def validate_table_name(table: str) -> str:
    """Validate table name against schema to prevent SQL injection."""
    if table not in TABLES:
        raise ValueError(f"Invalid table name: {table}. Must be one of the schema-defined tables.")
    return table


class BaseDatabaseManager:
    """Base database manager providing core infrastructure."""

    def __init__(self, db_path: str, batch_size: int = DEFAULT_BATCH_SIZE):
        """Initialize the database manager."""
        self.db_path = db_path

        self.conn = sqlite3.connect(db_path, timeout=60)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        self.conn.execute("PRAGMA foreign_keys = ON")

        if batch_size <= 0:
            self.batch_size = DEFAULT_BATCH_SIZE
        elif batch_size > MAX_BATCH_SIZE:
            self.batch_size = MAX_BATCH_SIZE
        else:
            self.batch_size = batch_size

        self.generic_batches: dict[str, list[tuple]] = defaultdict(list)

        self.cfg_id_mapping: dict[int, int] = {}

        self.jwt_patterns_batch: list[dict] = []

    @staticmethod
    def _is_external_path(file_path: str) -> bool:
        """Check if file path is external to the project (typeshed, system Python, etc.).

        External paths are filtered out to prevent FK constraint failures when mypy
        reports errors from typeshed or system Python locations that don't exist in
        the files table.

        Args:
            file_path: Normalized file path to check

        Returns:
            True if path is external (should be filtered), False otherwise
        """
        if not file_path:
            return True

        # Typeshed paths (mypy's standard library stubs)
        if "typeshed" in file_path.lower():
            return True

        # System Python installation paths
        external_indicators = [
            "/lib/python",  # Unix system Python
            "/lib64/python",  # Unix system Python (64-bit)
            "\\lib\\site-packages\\",  # Windows system Python
            "/site-packages/",  # Unix system Python packages
            "<install>",  # Mypy placeholder for installed packages
            "<string>",  # Mypy inline code
        ]

        return any(indicator in file_path for indicator in external_indicators)

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
        """Validate database schema matches expected definitions."""
        from ..schema import validate_all_tables

        cursor = self.conn.cursor()
        mismatches = validate_all_tables(cursor)

        if not mismatches:
            logger.debug("All table schemas validated successfully")
            return True

        logger.debug("Schema validation warnings detected:")
        for table_name, errors in mismatches.items():
            logger.debug(f"Table: {table_name}")
            for error in errors:
                logger.debug(f"- {error}")

        logger.debug("Note: Some mismatches may be due to migration columns (expected)")
        return False

    def create_schema(self) -> None:
        """Create all database tables and indexes using schema.py definitions."""
        cursor = self.conn.cursor()

        for _table_name, table_schema in TABLES.items():
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
        """Clear all existing data from tables using schema.py registry."""
        cursor = self.conn.cursor()

        try:
            for table_name in TABLES:
                validated_table = validate_table_name(table_name)
                cursor.execute(f"DELETE FROM {validated_table}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to clear existing data: {e}") from e

    def flush_generic_batch(self, table_name: str, insert_mode: str = "INSERT") -> None:
        """Flush a single table's batch using schema-driven INSERT."""
        batch = self.generic_batches.get(table_name, [])
        if not batch:
            return

        schema = get_table_schema(table_name)
        if not schema:
            raise RuntimeError(f"No schema found for table '{table_name}' - check TABLES registry")

        all_cols = [col for col in schema.columns if col.name != "id" and not col.autoincrement]

        tuple_size = len(batch[0]) if batch else 0

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
            logger.debug(f"Flush: {table_name}")
            logger.error(f"  all_cols count: {len(all_cols)}")
            logger.error(f"  all_cols names: {[col.name for col in all_cols]}")
            logger.error(f"  tuple_size from batch[0]: {tuple_size}")
            if batch:
                logger.error(f"  batch[0]: {batch[0]}")

        columns = [col.name for col in all_cols[:tuple_size]]

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
            logger.error(f"  columns taken (first {tuple_size}): {columns}")

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
            logger.error(f"  query: {query}")

        cursor = self.conn.cursor()
        try:
            cursor.executemany(query, batch)
            if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
                logger.debug(f"Flush: {table_name} SUCCESS")
        except sqlite3.IntegrityError as e:
            logger.critical(f"\n FK VIOLATION in table '{table_name}'")
            logger.error(f"  Error: {e}")
            logger.error(f"  Query: {query}")
            logger.error(f"  Batch size: {len(batch)}")
            logger.error("  Sample rows (first 5):")
            for i, row in enumerate(batch[:5]):
                logger.error(f"    [{i}] {row}")
            raise
        except Exception as e:
            logger.critical(f"\n BATCH INSERT ERROR in table '{table_name}'")
            logger.error(f"  Error: {e}")
            logger.error(f"  Query: {query}")
            logger.error(f"  Batch size: {len(batch)}")
            logger.error("  Sample rows (first 3):")
            for i, row in enumerate(batch[:3]):
                logger.error(f"    [{i}] {row}")
                for j, val in enumerate(row):
                    if isinstance(val, dict):
                        logger.error(f"        DICT FOUND at position {j}: {val}")
            raise

        self.generic_batches[table_name] = []

    def flush_batch(self, batch_idx: int | None = None) -> None:
        """Execute all pending batch inserts using schema-driven approach."""
        cursor = self.conn.cursor()

        try:
            if "files" in self.generic_batches and self.generic_batches["files"]:
                self.flush_generic_batch("files", "INSERT OR REPLACE")

            if "config_files" in self.generic_batches and self.generic_batches["config_files"]:
                self.flush_generic_batch("config_files", "INSERT OR REPLACE")

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

            if (
                "python_protocols" in self.generic_batches
                and self.generic_batches["python_protocols"]
            ):
                id_map = {}
                for item in self.generic_batches["python_protocols"]:
                    data = item[:-1]
                    temp_id = item[-1]
                    cursor.execute(
                        """INSERT INTO python_protocols (
                            file, line, protocol_kind, protocol_type, class_name, in_function,
                            has_iter, has_next, is_generator, raises_stopiteration,
                            has_contains, has_getitem, has_setitem, has_delitem,
                            has_len, is_mapping, is_sequence,
                            has_args, has_kwargs, param_count,
                            has_getstate, has_setstate, has_reduce, has_reduce_ex,
                            context_expr, resource_type, variable_name,
                            is_async, has_copy, has_deepcopy
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        data,
                    )
                    id_map[temp_id] = cursor.lastrowid
                self.generic_batches["python_protocols"] = []

                if "python_protocol_methods" in self.generic_batches:
                    updated = []
                    for row in self.generic_batches["python_protocol_methods"]:
                        pid = id_map.get(row[1], row[1]) if row[1] < 0 else row[1]
                        updated.append((row[0], pid, row[2], row[3]))
                    cursor.executemany(
                        "INSERT INTO python_protocol_methods (file, protocol_id, method_name, method_order) VALUES (?, ?, ?, ?)",
                        updated,
                    )
                    self.generic_batches["python_protocol_methods"] = []

            if (
                "python_type_definitions" in self.generic_batches
                and self.generic_batches["python_type_definitions"]
            ):
                id_map = {}
                for item in self.generic_batches["python_type_definitions"]:
                    data = item[:-1]
                    temp_id = item[-1]
                    cursor.execute(
                        """INSERT INTO python_type_definitions (
                            file, line, type_kind, name, type_param_count, type_param_1, type_param_2,
                            type_param_3, type_param_4, type_param_5, is_runtime_checkable, methods
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        data,
                    )
                    id_map[temp_id] = cursor.lastrowid
                self.generic_batches["python_type_definitions"] = []

                if "python_typeddict_fields" in self.generic_batches:
                    updated = []
                    for row in self.generic_batches["python_typeddict_fields"]:
                        tid = id_map.get(row[1], row[1]) if row[1] < 0 else row[1]
                        updated.append((row[0], tid, row[2], row[3], row[4], row[5]))
                    cursor.executemany(
                        "INSERT INTO python_typeddict_fields (file, typeddict_id, field_name, field_type, required, field_order) VALUES (?, ?, ?, ?, ?, ?)",
                        updated,
                    )
                    self.generic_batches["python_typeddict_fields"] = []

            if (
                "python_test_fixtures" in self.generic_batches
                and self.generic_batches["python_test_fixtures"]
            ):
                id_map = {}
                for item in self.generic_batches["python_test_fixtures"]:
                    data = item[:-1]
                    temp_id = item[-1]
                    cursor.execute(
                        """INSERT INTO python_test_fixtures (
                            file, line, fixture_kind, fixture_type, name, scope, autouse, in_function
                        ) VALUES (?,?,?,?,?,?,?,?)""",
                        data,
                    )
                    id_map[temp_id] = cursor.lastrowid
                self.generic_batches["python_test_fixtures"] = []

                if "python_fixture_params" in self.generic_batches:
                    updated = []
                    for row in self.generic_batches["python_fixture_params"]:
                        fid = id_map.get(row[1], row[1]) if row[1] < 0 else row[1]
                        updated.append((row[0], fid, row[2], row[3], row[4]))
                    cursor.executemany(
                        "INSERT INTO python_fixture_params (file, fixture_id, param_name, param_value, param_order) VALUES (?, ?, ?, ?, ?)",
                        updated,
                    )
                    self.generic_batches["python_fixture_params"] = []

            if (
                "python_framework_config" in self.generic_batches
                and self.generic_batches["python_framework_config"]
            ):
                id_map = {}
                for item in self.generic_batches["python_framework_config"]:
                    data = item[:-1]
                    temp_id = item[-1]
                    cursor.execute(
                        """INSERT INTO python_framework_config (
                            file, line, config_kind, config_type, framework, name, endpoint,
                            cache_type, timeout, class_name, model_name, function_name,
                            target_name, base_class, has_process_request, has_process_response,
                            has_process_exception, has_process_view, has_process_template_response
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        data,
                    )
                    id_map[temp_id] = cursor.lastrowid
                self.generic_batches["python_framework_config"] = []

                if "python_framework_methods" in self.generic_batches:
                    updated = []
                    for row in self.generic_batches["python_framework_methods"]:
                        cid = id_map.get(row[1], row[1]) if row[1] < 0 else row[1]
                        updated.append((row[0], cid, row[2], row[3]))
                    cursor.executemany(
                        "INSERT INTO python_framework_methods (file, config_id, method_name, method_order) VALUES (?, ?, ?, ?)",
                        updated,
                    )
                    self.generic_batches["python_framework_methods"] = []

            if (
                "python_validation_schemas" in self.generic_batches
                and self.generic_batches["python_validation_schemas"]
            ):
                id_map = {}
                for item in self.generic_batches["python_validation_schemas"]:
                    data = item[:-1]
                    temp_id = item[-1]
                    cursor.execute(
                        """INSERT INTO python_validation_schemas (
                            file, line, schema_kind, schema_type, framework, name, field_type, required
                        ) VALUES (?,?,?,?,?,?,?,?)""",
                        data,
                    )
                    id_map[temp_id] = cursor.lastrowid
                self.generic_batches["python_validation_schemas"] = []

                if "python_schema_validators" in self.generic_batches:
                    updated = []
                    for row in self.generic_batches["python_schema_validators"]:
                        sid = id_map.get(row[1], row[1]) if row[1] < 0 else row[1]
                        updated.append((row[0], sid, row[2], row[3], row[4]))
                    cursor.executemany(
                        "INSERT INTO python_schema_validators (file, schema_id, validator_name, validator_type, validator_order) VALUES (?, ?, ?, ?, ?)",
                        updated,
                    )
                    self.generic_batches["python_schema_validators"] = []

            for table_name, insert_mode in FLUSH_ORDER:
                if table_name in {"files", "config_files"}:
                    continue
                if table_name in self.generic_batches and self.generic_batches[table_name]:
                    self.flush_generic_batch(table_name, insert_mode)

        except sqlite3.IntegrityError as e:
            error_msg = str(e)

            logger.critical(f"\n IntegrityError in flush_batch: {error_msg}")
            logger.critical("Pending batches with data:")
            for tbl, batch in self.generic_batches.items():
                if batch:
                    logger.error(f"  {tbl}: {len(batch)} rows")
                    if len(batch) <= 5:
                        for i, row in enumerate(batch):
                            logger.error(f"    [{i}] {row}")
                    else:
                        for i, row in enumerate(batch[:3]):
                            logger.error(f"    [{i}] {row}")
                        logger.error(f"    ... ({len(batch) - 3} more)")

            if "UNIQUE constraint failed" in error_msg:
                raise ValueError(
                    f"DATABASE INTEGRITY ERROR: Duplicate row insertion attempted.\n"
                    f"  Error: {error_msg}\n"
                    f"  This indicates deduplication was not enforced in storage layer.\n"
                    f"  Check core_storage.py tracking sets."
                ) from e

            if "FOREIGN KEY constraint failed" in error_msg:
                raise ValueError(
                    f"ORPHAN DATA ERROR: Attempted to insert record referencing missing parent.\n"
                    f"  Error: {error_msg}\n"
                    f"  Ensure parent tables (files, symbols) are inserted BEFORE children.\n"
                    f"  Check FLUSH_ORDER in schema.py."
                ) from e

            if batch_idx is not None:
                raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}") from e
            else:
                raise RuntimeError(f"Batch insert failed: {e}") from e

        except sqlite3.Error as e:
            if os.environ.get("THEAUDITOR_DEBUG") == "1":
                logger.debug(f"\n SQL Error: {type(e).__name__}: {e}")
                logger.debug("Tables with pending batches:")
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        logger.debug(f"{table_name}: {len(batch)} records")

            if batch_idx is not None:
                raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}") from e
            else:
                raise RuntimeError(f"Batch insert failed: {e}") from e

    def _flush_jwt_patterns(self):
        """Flush JWT patterns batch (special dict-based interface)."""
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
        """Write findings to database using batch insert with typed columns."""
        if not findings:
            return

        from datetime import UTC, datetime

        cursor = self.conn.cursor()

        normalized = []
        for f in findings:
            details = f.get("additional_info", {})
            if not isinstance(details, dict):
                details = {}

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

            file_path = file_path.replace("\\", "/")

            if file_path.startswith("./"):
                file_path = file_path[2:]

            cfg_function = None
            cfg_complexity = None
            cfg_block_count = None
            cfg_edge_count = None
            cfg_has_loops = None
            cfg_has_recursion = None
            cfg_start_line = None
            cfg_end_line = None
            cfg_threshold = None

            graph_id = None
            graph_in_degree = None
            graph_out_degree = None
            graph_total_connections = None
            graph_centrality = None
            graph_score = None
            graph_cycle_nodes = None

            mypy_error_code = None
            mypy_severity_int = None
            mypy_column = None

            tf_finding_id = None
            tf_resource_id = None
            tf_remediation = None
            tf_graph_context = None

            actual_tool = f.get("tool", tool_name)
            if actual_tool == "cfg-analysis":
                cfg_function = details.get("function")
                cfg_complexity = details.get("complexity")
                cfg_block_count = details.get("block_count")
                cfg_edge_count = details.get("edge_count")
                cfg_has_loops = (
                    1 if details.get("has_loops") else (0 if "has_loops" in details else None)
                )
                cfg_has_recursion = (
                    1
                    if details.get("has_recursion")
                    else (0 if "has_recursion" in details else None)
                )
                cfg_start_line = details.get("start_line")
                cfg_end_line = details.get("end_line")
                cfg_threshold = details.get("threshold")

            elif actual_tool == "graph-analysis":
                graph_id = details.get("id") or details.get("file")
                graph_in_degree = details.get("in_degree")
                graph_out_degree = details.get("out_degree")
                graph_total_connections = details.get("total_connections")
                graph_centrality = details.get("centrality")
                graph_score = details.get("score")
                cycle_nodes = details.get("cycle_nodes", [])
                if cycle_nodes and isinstance(cycle_nodes, list):
                    graph_cycle_nodes = ",".join(str(n) for n in cycle_nodes)

            elif actual_tool == "mypy":
                mypy_error_code = details.get("mypy_code")
                mypy_severity_int = details.get("mypy_severity")
                mypy_column = f.get("column")

            elif actual_tool == "terraform":
                tf_finding_id = details.get("finding_id")
                tf_resource_id = details.get("resource_id")
                tf_remediation = details.get("remediation")
                tf_graph_context = details.get("graph_context_json")

            # Skip external paths (typeshed, system Python) to prevent FK failures
            if self._is_external_path(file_path):
                continue

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
                    cfg_function,
                    cfg_complexity,
                    cfg_block_count,
                    cfg_edge_count,
                    cfg_has_loops,
                    cfg_has_recursion,
                    cfg_start_line,
                    cfg_end_line,
                    cfg_threshold,
                    graph_id,
                    graph_in_degree,
                    graph_out_degree,
                    graph_total_connections,
                    graph_centrality,
                    graph_score,
                    graph_cycle_nodes,
                    mypy_error_code,
                    mypy_severity_int,
                    mypy_column,
                    tf_finding_id,
                    tf_resource_id,
                    tf_remediation,
                    tf_graph_context,
                )
            )

        # Log if findings were filtered
        filtered_count = len(findings) - len(normalized)
        if filtered_count > 0:
            logger.debug(
                f"Filtered {filtered_count} external path findings from {tool_name} "
                "(typeshed/system Python)"
            )

        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i : i + self.batch_size]
            cursor.executemany(
                """INSERT INTO findings_consolidated
                   (file, line, column, rule, tool, message, severity, category,
                    confidence, code_snippet, cwe, timestamp,
                    cfg_function, cfg_complexity, cfg_block_count, cfg_edge_count,
                    cfg_has_loops, cfg_has_recursion, cfg_start_line, cfg_end_line, cfg_threshold,
                    graph_id, graph_in_degree, graph_out_degree, graph_total_connections,
                    graph_centrality, graph_score, graph_cycle_nodes,
                    mypy_error_code, mypy_severity_int, mypy_column,
                    tf_finding_id, tf_resource_id, tf_remediation, tf_graph_context)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?,
                           ?, ?, ?, ?)""",
                batch,
            )

        self.conn.commit()

        if hasattr(self, "_debug") and self._debug:
            logger.info(
                f"Wrote {len(normalized)} findings from {tool_name} to findings_consolidated"
            )
