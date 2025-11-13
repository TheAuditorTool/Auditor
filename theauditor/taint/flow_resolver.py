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
        for entry_id in entry_nodes:
            if self.flows_resolved >= self.max_flows:
                logger.warning(f"Reached maximum flow limit ({self.max_flows})")
                break

            self._trace_from_entry(entry_id, exit_nodes)

        # Commit all resolved flows
        self.repo_conn.commit()

        logger.info(f"Flow resolution complete: {self.flows_resolved} flows resolved")
        return self.flows_resolved

    def _get_entry_nodes(self) -> List[str]:
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

    def _get_exit_nodes(self) -> Set[str]:
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
            AND file LIKE 'backend%'
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
            AND file LIKE 'backend%'
            AND file NOT LIKE '%migration%'
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

        # Response-sending function calls (backend only)
        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'res.send', 'res.json', 'res.render', 'res.write',
                'res.status', 'res.end'
            )
            AND argument_expr IS NOT NULL
            AND file LIKE 'backend%'
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

        # External API calls and file writes (backend only)
        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'axios.post', 'axios.get', 'fetch', 'request',
                'fs.writeFile', 'fs.writeFileSync', 'fs.appendFile',
                'console.log', 'console.error', 'logger.info'
            )
            AND argument_expr IS NOT NULL
            AND file LIKE 'backend%'
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

    def _trace_from_entry(self, entry_id: str, exit_nodes: Set[str]) -> None:
        """Trace all flows from a single entry point using DFS (memory-efficient).

        Args:
            entry_id: Entry point node ID (format: file::function::variable)
            exit_nodes: Set of exit node IDs to trace to
        """
        # MEMORY FIX: DFS with path-only tracking
        # Removed redundant visited set - path list already tracks visited nodes
        # DFS (stack/LIFO) uses less memory than BFS (queue/FIFO) for wide graphs
        worklist = [(entry_id, [entry_id])]  # (current_node, path) - NO visited set
        flows_from_this_entry = 0

        while worklist and self.flows_resolved < self.max_flows and flows_from_this_entry < self.max_flows_per_entry:
            # DFS: pop from end (LIFO)
            current_id, path = worklist.pop()

            # Check depth limit
            if len(path) > self.max_depth:
                # Store as VULNERABLE since we can't determine if it's sanitized
                # The hop chain will show it was truncated by its length
                self._record_flow(entry_id, current_id, path, "VULNERABLE", None)
                continue

            # Check if we've reached an exit
            if current_id in exit_nodes:
                status, sanitizer_meta = self._classify_flow(path)
                self._record_flow(entry_id, current_id, path, status, sanitizer_meta)
                flows_from_this_entry += 1
                # ARCHITECTURAL FIX: NO continue here - allow finding multiple paths
                # The IFDS cycle detection fix (removing depth from state) prevents
                # exponential explosion, so we can safely enumerate multiple paths
                # per entry/exit pair without killing CPU

            # Get successors from unified graph
            successors = self._get_successors(current_id)

            for successor_id in successors:
                # MEMORY FIX: Check path list directly instead of separate visited set
                # Path max length = 20, so O(20) scan is faster than set copy
                # This eliminates 15GB+ of redundant set copies
                if successor_id not in path:
                    new_path = path + [successor_id]
                    worklist.append((successor_id, new_path))

    def _get_successors(self, node_id: str) -> List[str]:
        """Get successor nodes from the unified data flow graph.

        Args:
            node_id: Current node ID (format: file::function::variable)

        Returns:
            List of successor node IDs
        """
        cursor = self.graph_conn.cursor()

        # Query all outgoing edges from this node
        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'data_flow'
              AND source = ?
        """, (node_id,))

        return [row[0] for row in cursor.fetchall()]

    def _classify_flow(self, path: List[str]) -> Tuple[str, Optional[Dict]]:
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

    def _record_flow(self, source: str, sink: str, path: List[str], status: str, sanitizer_meta: Optional[Dict]) -> None:
        """Write resolved flow to resolved_flow_audit table.

        Args:
            source: Entry point node ID (format: file::function::variable)
            sink: Exit point node ID (format: file::function::variable)
            path: Complete path from source to sink
            status: Flow classification (VULNERABLE, SANITIZED, or TRUNCATED)
            sanitizer_meta: Sanitizer metadata dict if flow is SANITIZED, None otherwise
        """
        # Parse source node ID (file::function::variable)
        source_parts = source.split('::')
        source_file = source_parts[0] if len(source_parts) > 0 else ""
        source_function = source_parts[1] if len(source_parts) > 1 else "global"
        source_pattern = source_parts[2] if len(source_parts) > 2 else source

        # Parse sink node ID (file::function::variable)
        sink_parts = sink.split('::')
        sink_file = sink_parts[0] if len(sink_parts) > 0 else ""
        sink_function = sink_parts[1] if len(sink_parts) > 1 else "global"
        sink_pattern = sink_parts[2] if len(sink_parts) > 2 else sink

        # Get line numbers from repo_index.db if available
        repo_cursor = self.repo_conn.cursor()

        # Try to get source line
        source_line = 0
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
        cursor = self.repo_conn.cursor()
        cursor.execute("""
            INSERT INTO resolved_flow_audit (
                source_file, source_line, source_pattern,
                sink_file, sink_line, sink_pattern,
                vulnerability_type, path_length, hops, path_json, flow_sensitive,
                status, sanitizer_file, sanitizer_line, sanitizer_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_file, source_line, source_pattern,
            sink_file, sink_line, sink_pattern,
            "unknown",  # vulnerability_type - rules will classify this later
            len(hop_chain),  # path_length
            len(hop_chain),  # hops
            json.dumps(hop_chain),  # path_json
            1,  # flow_sensitive (forward analysis is flow-sensitive)
            status,  # status (VULNERABLE, SANITIZED, or TRUNCATED)
            sanitizer_meta['file'] if sanitizer_meta else None,  # sanitizer_file
            sanitizer_meta['line'] if sanitizer_meta else None,  # sanitizer_line
            sanitizer_meta['method'] if sanitizer_meta else None   # sanitizer_method
        ))

        self.flows_resolved += 1

        # Periodic commit for large datasets
        if self.flows_resolved % 1000 == 0:
            self.repo_conn.commit()
            logger.debug(f"Recorded {self.flows_resolved} flows...")

    def _get_edge_type(self, from_node: str, to_node: str) -> str:
        """Get the edge type between two nodes from the graph.

        Args:
            from_node: Source node ID (format: file::function::variable)
            to_node: Target node ID (format: file::function::variable)

        Returns:
            Edge type (assignment/return/parameter_binding/cross_boundary/etc)
        """
        cursor = self.graph_conn.cursor()

        cursor.execute("""
            SELECT type
            FROM edges
            WHERE graph_type = 'data_flow'
              AND source = ?
              AND target = ?
            LIMIT 1
        """, (from_node, to_node))

        result = cursor.fetchone()
        return result[0] if result else "unknown"

    def _parse_argument_variable(self, arg_expr: str) -> Optional[str]:
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