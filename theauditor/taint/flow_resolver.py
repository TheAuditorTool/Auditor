"""Complete flow resolution engine for codebase truth generation.

This module implements forward flow analysis to populate the resolved_flow_audit table
with ALL control flows in the codebase, not just vulnerable ones. This transforms
TheAuditor from a security scanner to a complete codebase resolution engine where
the database becomes the queryable truth for AI agents.

Architecture:
    - Forward DFS traversal from ALL entry points to ALL exit points (memory-efficient)
    - Records complete provenance (hop chains) for every flow
    - Classifies flows as SAFE or TRUNCATED only (security rules applied later)
    - Populates resolved_flow_audit table with >100,000 resolved flows
    - Uses graph node IDs: file::function::variable (matches dfg_builder.py)
    - Memory optimized: No redundant visited sets, DFS stack instead of BFS queue
"""

import json
import sqlite3
from collections import defaultdict

from theauditor.utils.logger import setup_logger

from .sanitizer_util import SanitizerRegistry

logger = setup_logger(__name__)


class FlowResolver:
    """Resolves ALL control flows in codebase to populate resolved_flow_audit table.

    This class implements the "Code-to-Truth Compiler" that transforms sprawling
    codebases into structured knowledge that AI can query without reading source code.
    """

    def __init__(self, repo_db: str, graph_db: str):
        """Initialize the flow resolver with database connections.

        Args:
            repo_db: Path to repo_index.db containing extracted facts
            graph_db: Path to graphs.db containing unified data flow graph
        """
        self.repo_db = repo_db
        self.graph_db = graph_db
        self.repo_conn = sqlite3.connect(repo_db)
        self.repo_conn.row_factory = sqlite3.Row
        self.repo_cursor = self.repo_conn.cursor()
        self.graph_conn = sqlite3.connect(graph_db)
        self.flows_resolved = 0
        self.max_depth = 20
        self.max_flows = 100_000
        self.max_flows_per_entry = 1_000

        self.sanitizer_registry = SanitizerRegistry(self.repo_cursor, registry=None)

        self.adjacency_list: dict[str, list[str]] = defaultdict(list)
        self.edge_types: dict[tuple[str, str], str] = {}
        self._preload_graph()

        self.best_paths_cache: dict[tuple, int] = {}

    def _preload_graph(self):
        """Pre-load the entire data flow graph into memory for O(1) traversal.

        This is the critical optimization that transforms FlowResolver from
        "10 million SQL queries" to "1 SQL query + RAM lookups".

        Memory cost: ~50-100MB for large codebases (totally acceptable).
        Speed gain: 1000x faster traversal.
        """
        logger.info("Pre-loading data flow graph into memory...")
        cursor = self.graph_conn.cursor()

        cursor.execute("""
            SELECT source, target, type
            FROM edges
            WHERE graph_type = 'data_flow'
        """)

        edge_count = 0
        for source, target, edge_type in cursor.fetchall():
            self.adjacency_list[source].append(target)
            self.edge_types[(source, target)] = edge_type or "unknown"
            edge_count += 1

        logger.info(
            f"Graph pre-loaded: {edge_count} edges, {len(self.adjacency_list)} nodes in memory"
        )

    def resolve_all_flows(self) -> int:
        """Complete forward flow resolution to generate atomic truth.

        Algorithm:
            1. Get ALL entry points from graph (not pattern-based)
            2. Get ALL exit points from graph (not pattern-based)
            3. Trace EVERY path from entry to exit using BFS
            4. Record ALL paths with complete provenance
            5. Write resolved flows to resolved_flow_audit table

        Returns:
            Number of flows resolved and written to database
        """
        logger.info("Starting complete flow resolution...")

        self.repo_conn.execute("DELETE FROM resolved_flow_audit")
        self.repo_conn.commit()

        entry_nodes = self._get_entry_nodes()
        exit_nodes = self._get_exit_nodes()

        logger.info(f"Found {len(entry_nodes)} entry points and {len(exit_nodes)} exit points")

        for _i, entry_id in enumerate(entry_nodes):
            if self.flows_resolved >= self.max_flows:
                logger.warning(f"Reached maximum flow limit ({self.max_flows})")
                break

            self._trace_from_entry(entry_id, exit_nodes)

        self.repo_conn.commit()

        logger.info(f"Flow resolution complete: {self.flows_resolved} flows resolved")
        return self.flows_resolved

    def _get_entry_nodes(self) -> list[str]:
        """Get all entry points from the unified graph.

        Entry points include:
            - Express middleware chain roots (req.body, req.params, req.query)
            - API endpoints (cross_boundary edge targets)
            - Environment variable accesses
            - Main/index file exports

        Returns:
            List of node IDs (format: file::function::variable)
        """
        cursor = self.graph_conn.cursor()
        entry_nodes = []

        repo_cursor = self.repo_conn.cursor()
        repo_cursor.execute("""
            SELECT DISTINCT file, handler_function
            FROM express_middleware_chains
            WHERE handler_type IN ('middleware', 'controller')
              AND execution_order = 0
        """)

        for file, handler_func in repo_cursor.fetchall():
            for req_field in ["req.body", "req.params", "req.query", "req"]:
                node_id = f"{file}::{handler_func}::{req_field}"

                cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if cursor.fetchone():
                    entry_nodes.append(node_id)

        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'data_flow'
              AND type = 'cross_boundary'
        """)

        for (target,) in cursor.fetchall():
            entry_nodes.append(target)

        repo_cursor = self.repo_conn.cursor()
        repo_cursor.execute("""
            SELECT DISTINCT file, line, var_name, in_function
            FROM env_var_usage
        """)

        for row in repo_cursor.fetchall():
            file = row[0]
            var_name = row[2]
            func = row[3] if row[3] else "global"

            node_id = f"{file}::{func}::{var_name}"

            cursor.execute(
                """
                SELECT 1 FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id = ?
                LIMIT 1
            """,
                (node_id,),
            )

            if cursor.fetchone():
                entry_nodes.append(node_id)

        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'call'
              AND source LIKE '%index%'
              AND target NOT LIKE '%node_modules%'
            LIMIT 100
        """)

        for (target,) in cursor.fetchall():
            cursor.execute(
                """
                SELECT DISTINCT id FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id LIKE ?
                LIMIT 1
            """,
                (f"{target.split('::')[0]}::%",),
            )

            result = cursor.fetchone()
            if result:
                entry_nodes.append(result[0])

        return entry_nodes

    def _get_exit_nodes(self) -> set[str]:
        """Get all exit points from the unified graph.

        Exit points are nodes in the graph that represent sinks:
            - Variables passed to SQL query functions
            - Variables passed to response functions
            - Variables passed to external API calls
            - Variables written to filesystem
            - Variables logged to console

        Returns:
            Set of node IDs representing exit points (format: file::function::variable)
        """
        exit_nodes = set()
        repo_cursor = self.repo_conn.cursor()
        graph_cursor = self.graph_conn.cursor()

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE (
                callee_function LIKE '%.create%'
                OR callee_function LIKE '%.update%'
                OR callee_function LIKE '%.delete%'
                OR callee_function LIKE '%.findOne%'
                OR callee_function LIKE '%.findMany%'
                OR callee_function LIKE '%.save%'
                OR callee_function LIKE '%.destroy%'
                OR callee_function LIKE '%.upsert%'
                OR callee_function LIKE 'prisma.%'
                OR callee_function LIKE 'sequelize.query%'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE (
                callee_function LIKE '%.query'
                OR callee_function LIKE '%.execute'
                OR callee_function LIKE '%.exec'
                OR callee_function LIKE '%.run'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%migration%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'res.send', 'res.json', 'res.render', 'res.write',
                'res.status', 'res.end'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                for req_field in ["req", "req.body", "req.params", "req.query"]:
                    if req_field in arg_expr:
                        alt_node_id = f"{file}::{func}::{req_field}"
                        graph_cursor.execute(
                            """
                            SELECT 1 FROM nodes
                            WHERE graph_type = 'data_flow'
                              AND id = ?
                            LIMIT 1
                        """,
                            (alt_node_id,),
                        )
                        if graph_cursor.fetchone():
                            exit_nodes.add(alt_node_id)

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'axios.post', 'axios.get', 'fetch', 'request',
                'fs.writeFile', 'fs.writeFileSync', 'fs.appendFile',
                'console.log', 'console.error', 'logger.info'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        return exit_nodes

    def _trace_from_entry(self, entry_id: str, exit_nodes: set[str]) -> None:
        """Trace all flows from a single entry point using DFS with Adaptive Throttling.

        Args:
            entry_id: Entry point node ID (format: file::function::variable)
            exit_nodes: Set of exit node IDs to trace to
        """

        parts = entry_id.split("::")
        file_path = parts[0].lower()
        var_name = parts[-1] if len(parts) > 0 else ""

        is_infrastructure = (
            "config" in file_path
            or "env" in file_path
            or (var_name.isupper() and len(var_name) > 1)
            or "process.env" in var_name
        )

        if is_infrastructure:
            CURRENT_MAX_EFFORT = 5_000
            CURRENT_MAX_VISITS = 2
        else:
            CURRENT_MAX_EFFORT = 25_000
            CURRENT_MAX_VISITS = 10

        worklist = [(entry_id, [entry_id])]
        visited_edges: set[tuple[str, str]] = set()
        node_visit_counts: dict[str, int] = defaultdict(int)

        flows_from_this_entry = 0
        effort_counter = 0

        while (
            worklist
            and self.flows_resolved < self.max_flows
            and flows_from_this_entry < self.max_flows_per_entry
        ):
            effort_counter += 1
            if effort_counter > CURRENT_MAX_EFFORT:
                break

            current_id, path = worklist.pop()

            if len(path) > self.max_depth:
                self._record_flow(entry_id, current_id, path, "VULNERABLE", None)
                continue

            if current_id in exit_nodes:
                status, sanitizer_meta = self._classify_flow(path)
                self._record_flow(entry_id, current_id, path, status, sanitizer_meta)
                flows_from_this_entry += 1

            successors = self._get_successors(current_id)

            for successor_id in successors:
                edge = (current_id, successor_id)
                if edge in visited_edges:
                    continue

                if node_visit_counts[successor_id] >= CURRENT_MAX_VISITS:
                    continue

                node_visit_counts[successor_id] += 1
                visited_edges.add(edge)

                new_path = path + [successor_id]
                worklist.append((successor_id, new_path))

    def _get_successors(self, node_id: str) -> list[str]:
        """Get successor nodes from in-memory graph cache (O(1) lookup).

        Args:
            node_id: Current node ID (format: file::function::variable)

        Returns:
            List of successor node IDs
        """

        return self.adjacency_list.get(node_id, [])

    def _classify_flow(self, path: list[str]) -> tuple[str, dict | None]:
        """Classify a flow path based on sanitization.

        Checks if the path goes through any sanitizers (validation frameworks
        or safe sinks). Returns SANITIZED if it does, otherwise VULNERABLE.

        The /rules/ directory will later reclassify VULNERABLE flows based on
        specific security patterns.

        Args:
            path: Complete flow path from entry to exit

        Returns:
            Tuple of (status, sanitizer_metadata)
            - status: "SANITIZED" or "VULNERABLE"
            - sanitizer_metadata: Dict with sanitizer details or None
        """

        sanitizer_meta = self.sanitizer_registry._path_goes_through_sanitizer(path)

        if sanitizer_meta:
            return ("SANITIZED", sanitizer_meta)
        else:
            return ("VULNERABLE", None)

    def _record_flow(
        self, source: str, sink: str, path: list[str], status: str, sanitizer_meta: dict | None
    ) -> None:
        """Write resolved flow to resolved_flow_audit table with SEMANTIC DEDUPLICATION.

        Optimization: "Truth over Noise".
        We store only the SHORTEST path for every unique combination of:
        (Source Node, Sink Node, Status, Sanitizer Method).

        This reduces graph explosion (4k permutations) to distinct semantic outcomes (1-2 paths).

        Args:
            source: Entry point node ID (format: file::function::variable)
            sink: Exit point node ID (format: file::function::variable)
            path: Complete path from source to sink
            status: Flow classification (VULNERABLE, SANITIZED, or TRUNCATED)
            sanitizer_meta: Sanitizer metadata dict if flow is SANITIZED, None otherwise
        """

        source_parts = source.split("::")
        source_file = source_parts[0] if len(source_parts) > 0 else ""
        source_pattern = source_parts[2] if len(source_parts) > 2 else source

        sink_parts = sink.split("::")
        sink_file = sink_parts[0] if len(sink_parts) > 0 else ""
        sink_pattern = sink_parts[2] if len(sink_parts) > 2 else sink

        sanitizer_method = sanitizer_meta["method"] if sanitizer_meta else None

        current_length = len(path)

        cache_key = (source_file, source_pattern, sink_file, sink_pattern, status, sanitizer_method)

        cached_length = self.best_paths_cache.get(cache_key)
        if cached_length is not None:
            if cached_length <= current_length:
                return

        self.best_paths_cache[cache_key] = current_length

        cursor = self.repo_conn.cursor()

        query_sig = """
            SELECT id, path_length FROM resolved_flow_audit
            WHERE source_file = ? AND source_pattern = ?
              AND sink_file = ? AND sink_pattern = ?
              AND status = ?
              -- SQL trick: checks if sanitizer matches OR both are NULL
              AND (sanitizer_method = ? OR (sanitizer_method IS NULL AND ? IS NULL))
              AND engine = 'FlowResolver'
            LIMIT 1
        """

        cursor.execute(
            query_sig,
            (
                source_file,
                source_pattern,
                sink_file,
                sink_pattern,
                status,
                sanitizer_method,
                sanitizer_method,
            ),
        )

        existing = cursor.fetchone()

        if existing:
            existing_id, existing_length = existing

            if existing_length <= current_length:
                return

            cursor.execute("DELETE FROM resolved_flow_audit WHERE id = ?", (existing_id,))

        repo_cursor = self.repo_conn.cursor()

        source_line = 0

        source_function = source_parts[1] if len(source_parts) > 1 else "global"
        repo_cursor.execute(
            """
            SELECT MIN(line) FROM assignments
            WHERE file = ? AND target_var = ?
              AND (in_function = ? OR (in_function IS NULL AND ? = 'global'))
        """,
            (source_file, source_pattern, source_function, source_function),
        )
        result = repo_cursor.fetchone()
        if result and result[0]:
            source_line = result[0]

        sink_line = 0
        sink_function = sink_parts[1] if len(sink_parts) > 1 else "global"
        repo_cursor.execute(
            """
            SELECT MIN(line) FROM function_call_args
            WHERE file = ? AND argument_expr LIKE ?
              AND (caller_function = ? OR (caller_function IS NULL AND ? = 'global'))
        """,
            (sink_file, f"%{sink_pattern}%", sink_function, sink_function),
        )
        result = repo_cursor.fetchone()
        if result and result[0]:
            sink_line = result[0]

        hop_chain = []
        for i in range(len(path) - 1):
            hop = {
                "from": path[i],
                "to": path[i + 1],
                "hop_number": i,
                "type": self._get_edge_type(path[i], path[i + 1]),
            }
            hop_chain.append(hop)

        cursor.execute(
            """
            INSERT INTO resolved_flow_audit (
                source_file, source_line, source_pattern,
                sink_file, sink_line, sink_pattern,
                vulnerability_type, path_length, hops, path_json, flow_sensitive,
                status, sanitizer_file, sanitizer_line, sanitizer_method,
                engine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                source_file,
                source_line,
                source_pattern,
                sink_file,
                sink_line,
                sink_pattern,
                "unknown",
                len(hop_chain),
                len(hop_chain),
                json.dumps(hop_chain),
                1,
                status,
                sanitizer_meta["file"] if sanitizer_meta else None,
                sanitizer_meta["line"] if sanitizer_meta else None,
                sanitizer_method,
                "FlowResolver",
            ),
        )

        self.flows_resolved += 1

        if self.flows_resolved % 1000 == 0:
            self.repo_conn.commit()
            logger.debug(f"Recorded {self.flows_resolved} semantic flows...")

    def _get_edge_type(self, from_node: str, to_node: str) -> str:
        """Get the edge type between two nodes from in-memory cache (O(1) lookup).

        Args:
            from_node: Source node ID (format: file::function::variable)
            to_node: Target node ID (format: file::function::variable)

        Returns:
            Edge type (assignment/return/parameter_binding/cross_boundary/etc)
        """

        return self.edge_types.get((from_node, to_node), "unknown")

    def _parse_argument_variable(self, arg_expr: str) -> str | None:
        """Extract variable name from argument expression.

        Args:
            arg_expr: Argument expression (e.g., "userInput", "req.body", "getUser()")

        Returns:
            Variable name or access path, None if not parseable

        Examples:
            "userInput" -> "userInput"
            "req.body" -> "req.body"
            "user.data.id" -> "user.data.id"
            "getUser()" -> None (function call)
            "'string'" -> None (literal)
            "123" -> None (literal)
        """
        if not arg_expr or not isinstance(arg_expr, str):
            return None

        arg_expr = arg_expr.strip()

        if not arg_expr:
            return None

        if arg_expr.startswith('"') or arg_expr.startswith("'"):
            return None

        if "(" in arg_expr:
            return None

        if any(op in arg_expr for op in ["+", "-", "*", "/", "%", "=", "<", ">", "!"]):
            return None

        if arg_expr.isdigit():
            return None

        if not (arg_expr[0].isalpha() or arg_expr[0] == "_"):
            return None

        return arg_expr

    def close(self):
        """Clean up database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
