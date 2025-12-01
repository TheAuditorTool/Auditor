"""Base database manager with core infrastructure."""

import os
import sqlite3
import sys
from collections import defaultdict

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
        except sqlite3.IntegrityError as e:
            # FK VIOLATION DIAGNOSTIC: Print offending data before crash
            print(f"\n[CRITICAL] FK VIOLATION in table '{table_name}'", file=sys.stderr)
            print(f"  Error: {e}", file=sys.stderr)
            print(f"  Query: {query}", file=sys.stderr)
            print(f"  Batch size: {len(batch)}", file=sys.stderr)
            print(f"  Sample rows (first 5):", file=sys.stderr)
            for i, row in enumerate(batch[:5]):
                print(f"    [{i}] {row}", file=sys.stderr)
            raise  # Re-raise: crash loud with forensics
        except Exception as e:
            if os.environ.get("THEAUDITOR_DEBUG") == "1" and table_name.startswith("graphql_"):
                print(f"[DEBUG] Flush: {table_name} FAILED - {e}", file=sys.stderr)
            raise

        self.generic_batches[table_name] = []

    def flush_batch(self, batch_idx: int | None = None) -> None:
        """Execute all pending batch inserts using schema-driven approach."""
        cursor = self.conn.cursor()

        try:
            # FLUSH_ORDER is defined in schema.py - single source of truth
            # validated at import time to ensure all tables have schemas
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

            for table_name, insert_mode in FLUSH_ORDER:
                if table_name in self.generic_batches and self.generic_batches[table_name]:
                    self.flush_generic_batch(table_name, insert_mode)

        except sqlite3.IntegrityError as e:
            error_msg = str(e)

            # DIAGNOSTIC: Dump all pending batches to help identify the culprit
            print(f"\n[CRITICAL] IntegrityError in flush_batch: {error_msg}", file=sys.stderr)
            print(f"[CRITICAL] Pending batches with data:", file=sys.stderr)
            for tbl, batch in self.generic_batches.items():
                if batch:
                    print(f"  {tbl}: {len(batch)} rows", file=sys.stderr)
                    if len(batch) <= 5:
                        for i, row in enumerate(batch):
                            print(f"    [{i}] {row}", file=sys.stderr)
                    else:
                        for i, row in enumerate(batch[:3]):
                            print(f"    [{i}] {row}", file=sys.stderr)
                        print(f"    ... ({len(batch) - 3} more)", file=sys.stderr)

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
                print(f"\n[DEBUG] SQL Error: {type(e).__name__}: {e}", file=sys.stderr)
                print("[DEBUG] Tables with pending batches:", file=sys.stderr)
                for table_name, batch in self.generic_batches.items():
                    if batch:
                        print(f"[DEBUG]   {table_name}: {len(batch)} records", file=sys.stderr)

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
            print(f"[DB] Wrote {len(findings)} findings from {tool_name} to findings_consolidated")
