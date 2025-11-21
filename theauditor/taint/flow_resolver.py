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
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

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
        self.max_depth = 20  # Maximum hop chain length
        self.max_flows = 100_000  # REDUCED: Safety limit (prevents CPU kill on large graphs)
        self.max_flows_per_entry = 1_000  # NEW: Per-entry limit to prevent single entry explosion

        # Initialize shared sanitizer registry
        self.sanitizer_registry = SanitizerRegistry(self.repo_cursor, registry=None)

        # TURBO MODE: In-memory graph cache for O(1) traversal
        # Eliminates millions of SQLite round-trips during graph walking
        self.adjacency_list: Dict[str, List[str]] = defaultdict(list)
        self.edge_types: Dict[Tuple[str, str], str] = {}
        self._preload_graph()

        # In-Memory Deduplication Cache (King of the Hill)
        # Eliminates millions of DB reads for path comparison
        # Key: (source_file, source_pattern, sink_file, sink_pattern, status, sanitizer) -> path_length
        self.best_paths_cache: Dict[Tuple, int] = {}

    def _preload_graph(self):
        """Pre-load the entire data flow graph into memory for O(1) traversal.

        This is the critical optimization that transforms FlowResolver from
        "10 million SQL queries" to "1 SQL query + RAM lookups".

        Memory cost: ~50-100MB for large codebases (totally acceptable).
        Speed gain: 1000x faster traversal.
        """
        logger.info("Pre-loading data flow graph into memory...")
        cursor = self.graph_conn.cursor()

        # Fetch ALL data flow edges in ONE query
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

        logger.info(f"Graph pre-loaded: {edge_count} edges, {len(self.adjacency_list)} nodes in memory")

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

        # Clear existing flows for fresh resolution
        self.repo_conn.execute("DELETE FROM resolved_flow_audit")
        self.repo_conn.commit()

        # Get entry and exit points from graph
        entry_nodes = self._get_entry_nodes()
        exit_nodes = self._get_exit_nodes()

        logger.info(f"Found {len(entry_nodes)} entry points and {len(exit_nodes)} exit points")

        # Forward BFS from each entry point
        import sys
        for i, entry_id in enumerate(entry_nodes):
            print(f"[FLOW] >> Entry {i+1}/{len(entry_nodes)}: {entry_id[:80]}...", file=sys.stderr, flush=True)

            if self.flows_resolved >= self.max_flows:
                logger.warning(f"Reached maximum flow limit ({self.max_flows})")
                break

            self._trace_from_entry(entry_id, exit_nodes)
            print(f" Done ({self.flows_resolved} flows)", file=sys.stderr, flush=True)

        # Commit all resolved flows
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

        # Express middleware chains - the REAL entry points for backend taint analysis
        # These are where user input enters the backend (req.body, req.params, req.query)
        repo_cursor = self.repo_conn.cursor()
        repo_cursor.execute("""
            SELECT DISTINCT file, handler_function
            FROM express_middleware_chains
            WHERE handler_type IN ('middleware', 'controller')
              AND execution_order = 0
        """)

        for file, handler_func in repo_cursor.fetchall():
            # Create entry nodes for common request fields
            for req_field in ['req.body', 'req.params', 'req.query', 'req']:
                node_id = f"{file}::{handler_func}::{req_field}"

                # Verify this node exists in the graph
                cursor.execute("""
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """, (node_id,))

                if cursor.fetchone():
                    entry_nodes.append(node_id)

        # API endpoints - these are TARGETS of cross_boundary edges
        # Keep for completeness but middleware chains are primary
        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'data_flow'
              AND type = 'cross_boundary'
        """)

        for (target,) in cursor.fetchall():
            # The target IS the node ID, already in correct format
            entry_nodes.append(target)

        # Environment variable accesses - need to find actual graph nodes
        repo_cursor = self.repo_conn.cursor()
        repo_cursor.execute("""
            SELECT DISTINCT file, line, var_name, in_function
            FROM env_var_usage
        """)

        for row in repo_cursor.fetchall():
            file = row[0]
            var_name = row[2]  # e.g., "process.env.MY_VAR"
            func = row[3] if row[3] else "global"

            # Construct the node ID matching dfg_builder format
            node_id = f"{file}::{func}::{var_name}"

            # Verify this node exists in the graph
            cursor.execute("""
                SELECT 1 FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id = ?
                LIMIT 1
            """, (node_id,))

            if cursor.fetchone():
                entry_nodes.append(node_id)

        # Main entry points from call graph
        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'call'
              AND source LIKE '%index%'
              AND target NOT LIKE '%node_modules%'
            LIMIT 100
        """)

        for (target,) in cursor.fetchall():
            # Call graph nodes might have different format, verify in data_flow
            cursor.execute("""
                SELECT DISTINCT id FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id LIKE ?
                LIMIT 1
            """, (f"{target.split('::')[0]}::%",))

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

        # Database operations through service methods (Prisma, Sequelize, etc.)
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

        for file, line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            # Parse the argument to get variable name
            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                # Construct the node ID for this SQL argument
                node_id = f"{file}::{func}::{var_name}"

                # Verify it exists in the graph
                graph_cursor.execute("""
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """, (node_id,))

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        # SQL query executions (raw queries, not in migrations)
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

        for file, line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute("""
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """, (node_id,))

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        # Response-sending function calls (Express/Node.js specific)
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

        for file, line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                # Also include req.body/params/query being sent in response
                for req_field in ['req', 'req.body', 'req.params', 'req.query']:
                    if req_field in arg_expr:
                        alt_node_id = f"{file}::{func}::{req_field}"
                        graph_cursor.execute("""
                            SELECT 1 FROM nodes
                            WHERE graph_type = 'data_flow'
                              AND id = ?
                            LIMIT 1
                        """, (alt_node_id,))
                        if graph_cursor.fetchone():
                            exit_nodes.add(alt_node_id)

                # Check if the main variable exists
                graph_cursor.execute("""
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """, (node_id,))

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        # External API calls and file writes
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

        for file, line, func, arg_expr in repo_cursor.fetchall():
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute("""
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """, (node_id,))

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        return exit_nodes

    def _trace_from_entry(self, entry_id: str, exit_nodes: set[str]) -> None:
        """Trace all flows from a single entry point using DFS with Adaptive Throttling.

        Args:
            entry_id: Entry point node ID (format: file::function::variable)
            exit_nodes: Set of exit node IDs to trace to
        """
        # --- ADAPTIVE THROTTLING (The Infrastructure Fix) ---
        # Detect if this is a "Super Node" (Config/Env vars) that connects to everything.
        # Heuristics:
        # 1. File path contains 'config' or 'env'
        # 2. Variable name is uppercase (constant/env var convention)
        # 3. Contains process.env

        parts = entry_id.split('::')
        file_path = parts[0].lower()
        var_name = parts[-1] if len(parts) > 0 else ""

        is_infrastructure = (
            "config" in file_path or
            "env" in file_path or
            (var_name.isupper() and len(var_name) > 1) or  # DB_HOST, SMTP_PORT
            "process.env" in var_name
        )

        # Set limits based on importance
        if is_infrastructure:
            # Low limits for config (stops the 30-second chug)
            CURRENT_MAX_EFFORT = 5_000   # Stop after 5k checks
            CURRENT_MAX_VISITS = 2       # Don't revisit nodes more than twice
        else:
            # High limits for User Input (finds the deep bugs)
            CURRENT_MAX_EFFORT = 25_000  # Full exploration
            CURRENT_MAX_VISITS = 10      # Reasonable revisits
        # ----------------------------------------------------

        worklist = [(entry_id, [entry_id])]
        visited_edges: set[tuple[str, str]] = set()
        node_visit_counts: dict[str, int] = defaultdict(int)

        flows_from_this_entry = 0
        effort_counter = 0

        while worklist and self.flows_resolved < self.max_flows and flows_from_this_entry < self.max_flows_per_entry:
            # CIRCUIT BREAKER CHECK (Adaptive)
            effort_counter += 1
            if effort_counter > CURRENT_MAX_EFFORT:
                break

            # DFS: pop from end (LIFO)
            current_id, path = worklist.pop()

            # Check depth limit
            if len(path) > self.max_depth:
                self._record_flow(entry_id, current_id, path, "VULNERABLE", None)
                continue

            # Check if we've reached an exit
            if current_id in exit_nodes:
                status, sanitizer_meta = self._classify_flow(path)
                self._record_flow(entry_id, current_id, path, status, sanitizer_meta)
                flows_from_this_entry += 1

            # Get successors from unified graph
            successors = self._get_successors(current_id)

            for successor_id in successors:
                # 1. Edge Cycle Check (Standard)
                edge = (current_id, successor_id)
                if edge in visited_edges:
                    continue

                # 2. NODE VISIT PRUNING (Adaptive)
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
        # TURBO MODE: Dictionary lookup instead of SQL query
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
        # Check if path goes through any sanitizer
        sanitizer_meta = self.sanitizer_registry._path_goes_through_sanitizer(path)

        if sanitizer_meta:
            return ("SANITIZED", sanitizer_meta)
        else:
            # Default to VULNERABLE - rules will determine if actually vulnerable
            return ("VULNERABLE", None)

    def _record_flow(self, source: str, sink: str, path: list[str], status: str, sanitizer_meta: dict | None) -> None:
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
        # ------------------------------------------------------------------
        # STEP 1: EXTRACT IDENTITY (THE FINGERPRINT)
        # We parse the strings to get the clean file/variable names.
        # This is the "Fingerprint" of the flow.
        # ------------------------------------------------------------------

        # Parse Source (file::function::variable)
        source_parts = source.split('::')
        source_file = source_parts[0] if len(source_parts) > 0 else ""
        source_pattern = source_parts[2] if len(source_parts) > 2 else source

        # Parse Sink (file::function::variable)
        sink_parts = sink.split('::')
        sink_file = sink_parts[0] if len(sink_parts) > 0 else ""
        sink_pattern = sink_parts[2] if len(sink_parts) > 2 else sink

        # Handle the Sanitizer (This distinguishes "Safe" paths from "Unsafe" ones)
        sanitizer_method = sanitizer_meta['method'] if sanitizer_meta else None

        # How long is this new path?
        current_length = len(path)

        # ------------------------------------------------------------------
        # STEP 1.5: RAM CHECK (The Shield) - Avoid DB reads entirely
        # Check in-memory cache before touching database
        # ------------------------------------------------------------------
        cache_key = (source_file, source_pattern, sink_file, sink_pattern, status, sanitizer_method)

        cached_length = self.best_paths_cache.get(cache_key)
        if cached_length is not None:
            if cached_length <= current_length:
                # RAM says we already have a better/equal path. Stop here.
                # Zero disk I/O. Zero latency.
                return

        # Update RAM cache immediately so future checks hit it
        self.best_paths_cache[cache_key] = current_length

        # ------------------------------------------------------------------
        # STEP 2: CHECK FOR EXISTING CHAMPION (DB Backup)
        # We ask the DB: "Do you already have a path for this exact scenario?"
        # This is now rarely hit because RAM cache handles most cases.
        # ------------------------------------------------------------------
        cursor = self.repo_conn.cursor()

        # The Query: Look for a match on Source + Sink + Status + Sanitizer
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

        cursor.execute(query_sig, (
            source_file, source_pattern,
            sink_file, sink_pattern,
            status,
            sanitizer_method, sanitizer_method
        ))

        existing = cursor.fetchone()

        # ------------------------------------------------------------------
        # STEP 3: THE DECISION MATRIX
        # ------------------------------------------------------------------
        if existing:
            existing_id, existing_length = existing

            # SCENARIO 1: The existing path is SHORTER or EQUAL.
            # The new path is worse. Discard it.
            if existing_length <= current_length:
                return

            # SCENARIO 2: The new path is BETTER (Shorter).
            # The old path is obsolete. Delete it so we can replace it.
            cursor.execute("DELETE FROM resolved_flow_audit WHERE id = ?", (existing_id,))

        # ------------------------------------------------------------------
        # STEP 4: STANDARD INSERT (Line Numbers + Hop Chain + DB Write)
        # ------------------------------------------------------------------

        # Get line numbers from repo_index.db if available
        repo_cursor = self.repo_conn.cursor()

        # Try to get source line
        source_line = 0
        # Use function context for more accurate line lookup
        source_function = source_parts[1] if len(source_parts) > 1 else "global"
        repo_cursor.execute("""
            SELECT MIN(line) FROM assignments
            WHERE file = ? AND target_var = ?
              AND (in_function = ? OR (in_function IS NULL AND ? = 'global'))
        """, (source_file, source_pattern, source_function, source_function))
        result = repo_cursor.fetchone()
        if result and result[0]:
            source_line = result[0]

        # Try to get sink line
        sink_line = 0
        sink_function = sink_parts[1] if len(sink_parts) > 1 else "global"
        repo_cursor.execute("""
            SELECT MIN(line) FROM function_call_args
            WHERE file = ? AND argument_expr LIKE ?
              AND (caller_function = ? OR (caller_function IS NULL AND ? = 'global'))
        """, (sink_file, f"%{sink_pattern}%", sink_function, sink_function))
        result = repo_cursor.fetchone()
        if result and result[0]:
            sink_line = result[0]

        # Build hop chain with complete provenance
        hop_chain = []
        for i in range(len(path) - 1):
            hop = {
                'from': path[i],
                'to': path[i + 1],
                'hop_number': i,
                'type': self._get_edge_type(path[i], path[i + 1])
            }
            hop_chain.append(hop)

        # Insert into resolved_flow_audit table (matching core.py schema)
        cursor.execute("""
            INSERT INTO resolved_flow_audit (
                source_file, source_line, source_pattern,
                sink_file, sink_line, sink_pattern,
                vulnerability_type, path_length, hops, path_json, flow_sensitive,
                status, sanitizer_file, sanitizer_line, sanitizer_method,
                engine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_file, source_line, source_pattern,
            sink_file, sink_line, sink_pattern,
            "unknown",  # vulnerability_type - /rules/ will classify this later
            len(hop_chain),  # path_length
            len(hop_chain),  # hops
            json.dumps(hop_chain),  # path_json
            1,  # flow_sensitive (forward analysis is flow-sensitive)
            status,  # status (VULNERABLE, SANITIZED, or TRUNCATED)
            sanitizer_meta['file'] if sanitizer_meta else None,  # sanitizer_file
            sanitizer_meta['line'] if sanitizer_meta else None,  # sanitizer_line
            sanitizer_method,  # sanitizer_method (already extracted above)
            "FlowResolver"  # engine column
        ))

        self.flows_resolved += 1

        # Periodic commit for large datasets
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
        # TURBO MODE: Dictionary lookup instead of SQL query
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

        # Remove whitespace
        arg_expr = arg_expr.strip()

        # Skip empty
        if not arg_expr:
            return None

        # Skip literals
        if arg_expr.startswith('"') or arg_expr.startswith("'"):
            return None

        # Skip function calls (contains parentheses)
        if '(' in arg_expr:
            return None

        # Skip operators
        if any(op in arg_expr for op in ['+', '-', '*', '/', '%', '=', '<', '>', '!']):
            return None

        # Skip numeric literals
        if arg_expr.isdigit():
            return None

        # Must start with letter or underscore (Python/JS identifier)
        if not (arg_expr[0].isalpha() or arg_expr[0] == '_'):
            return None

        # Valid identifier pattern: variable or variable.field.field
        # Just return the full expression (may include dots for access paths)
        return arg_expr





    def close(self):
        """Clean up database connections."""
        self.repo_conn.close()
        self.graph_conn.close()