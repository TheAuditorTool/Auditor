"""Complete flow resolution engine for codebase truth generation.

This module implements forward flow analysis to populate the resolved_flow_audit table
with ALL control flows in the codebase, not just vulnerable ones. This transforms
TheAuditor from a security scanner to a complete codebase resolution engine where
the database becomes the queryable truth for AI agents.

Architecture:
    - Forward BFS traversal from ALL entry points to ALL exit points
    - Records complete provenance (hop chains) for every flow
    - Classifies flows as SAFE or TRUNCATED only (security rules applied later)
    - Populates resolved_flow_audit table with >100,000 resolved flows
    - Uses graph node IDs: file::function::variable (matches dfg_builder.py)
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from collections import deque

from theauditor.utils.logger import setup_logger

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
        self.max_flows = 1_000_000  # Safety limit for total flows

        # Load sanitizers from database (same as IFDS analyzer)
        self._load_safe_sinks()
        self._load_validation_sanitizers()

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
            - API endpoints (cross_boundary edge targets)
            - Express middleware chain roots
            - Environment variable accesses
            - Main/index file exports

        Returns:
            List of node IDs (format: file::function::variable)
        """
        cursor = self.graph_conn.cursor()
        entry_nodes = []

        # API endpoints - these are TARGETS of cross_boundary edges ONLY
        # Don't include express_middleware_chain targets as those are intermediate nodes
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

        # SQL query executions - find the argument variables
        repo_cursor.execute("""
            SELECT DISTINCT fca.file, fca.line, fca.caller_function, fca.argument_expr
            FROM function_call_args fca
            JOIN sql_queries sq ON
                fca.file = sq.file_path
                AND fca.line = sq.line_number
            WHERE fca.argument_expr IS NOT NULL
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
        """Trace all flows from a single entry point using BFS.

        Args:
            entry_id: Entry point node ID (format: file::function::variable)
            exit_nodes: Set of exit node IDs to trace to
        """
        # BFS with path tracking
        worklist = deque([(entry_id, [entry_id])])
        visited_edges = set()

        while worklist and self.flows_resolved < self.max_flows:
            current_id, path = worklist.popleft()

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
                continue

            # Get successors from unified graph
            successors = self._get_successors(current_id)

            for successor_id in successors:
                edge = (current_id, successor_id)
                if edge not in visited_edges:
                    visited_edges.add(edge)
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
        sanitizer_meta = self._path_goes_through_sanitizer(path)

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

    def _load_safe_sinks(self):
        """Load sanitizers from framework_safe_sinks table."""
        self.safe_sinks: Set[str] = set()
        try:
            self.repo_cursor.execute("SELECT sink_pattern FROM framework_safe_sinks")
            rows = self.repo_cursor.fetchall()

            for row in rows:
                pattern = row['sink_pattern']
                self.safe_sinks.add(pattern)
        except sqlite3.OperationalError:
            # Table doesn't exist - no sanitizers loaded
            pass

    def _load_validation_sanitizers(self):
        """Load validation framework sanitizers from validation_framework_usage table.

        This captures location-based sanitizers like Zod middleware that must be
        matched by file:line, not just function name pattern.
        """
        self.validation_sanitizers: List[Dict] = []
        try:
            self.repo_cursor.execute("""
                SELECT file_path, line, framework, method, argument_expr, is_validator
                FROM validation_framework_usage
                WHERE is_validator = 1
            """)
            rows = self.repo_cursor.fetchall()

            for row in rows:
                sanitizer = {
                    'file': row['file_path'],
                    'line': row['line'],
                    'framework': row['framework'],
                    'method': row['method'],
                    'argument': row['argument_expr']
                }
                self.validation_sanitizers.append(sanitizer)
        except sqlite3.OperationalError:
            # Table doesn't exist - no validation sanitizers loaded
            pass

    def _path_goes_through_sanitizer(self, path: List[str]) -> Optional[Dict]:
        """Check if a flow path goes through a sanitizer.

        Checks THREE types of sanitizers:
        1. Validation middleware calls (validateBody, validateParams, validateQuery)
        2. Validation framework sanitizers (location-based: file:line match)
        3. Safe sink patterns (name-based: function name pattern match)

        Args:
            path: List of node IDs in the flow path

        Returns:
            Dict with sanitizer metadata if path is sanitized, None otherwise
        """
        # The path is just a list of node IDs, not hops
        # Each node ID is in format: file::function::variable
        for i, node_id in enumerate(path):
            # Parse node ID: file::function::variable
            parts = node_id.split('::')
            if len(parts) < 2:
                continue

            file = parts[0]
            func = parts[1] if len(parts) > 1 else None

            # CHECK 0: Validation middleware functions (validateBody, validateParams, validateQuery)
            # These appear in route files as function names in the middleware chain
            if func and any(validator in func for validator in ['validateBody', 'validateParams', 'validateQuery', 'validateRequest']):
                # This is a validation middleware call - it's a sanitizer!
                return {
                    'file': file,
                    'line': 0,  # We don't have exact line in node ID
                    'method': func
                }

            # Get line number for this node if available
            # Query assignments table to find line number
            if func:
                self.repo_cursor.execute("""
                    SELECT MIN(line) as line FROM assignments
                    WHERE file = ? AND in_function = ?
                    LIMIT 1
                """, (file, func))
            else:
                self.repo_cursor.execute("""
                    SELECT MIN(line) as line FROM assignments
                    WHERE file = ?
                    LIMIT 1
                """, (file,))

            result = self.repo_cursor.fetchone()
            line = result['line'] if result and result['line'] else 0

            if not line:
                continue

            # CHECK 1: Validation Framework Sanitizers (Location-Based)
            for san in self.validation_sanitizers:
                # Match by file path (handle both absolute and relative paths)
                file_match = (
                    file == san['file'] or
                    file.endswith(san['file']) or
                    san['file'].endswith(file)
                )

                if file_match and line == san['line']:
                    # Found validation sanitizer match
                    return {
                        'file': san['file'],
                        'line': san['line'],
                        'method': f"{san['framework']}.{san['method']}"
                    }

            # CHECK 2: Safe Sink Patterns (Function Name-Based)
            # Query function calls at this location
            self.repo_cursor.execute("""
                SELECT callee_function FROM function_call_args
                WHERE file = ? AND line = ?
                LIMIT 10
            """, (file, line))

            callees = [row['callee_function'] for row in self.repo_cursor.fetchall()]

            for callee in callees:
                if self._is_sanitizer(callee):
                    return {
                        'file': file,
                        'line': line,
                        'method': callee
                    }

        return None  # No sanitizer found

    def _is_sanitizer(self, function_name: str) -> bool:
        """Check if a function is a sanitizer.

        Checks database safe_sinks for pattern matches.
        """
        # Check database safe sinks (exact match)
        if function_name in self.safe_sinks:
            return True

        # Check any pattern that partially matches
        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True

        return False

    def close(self):
        """Clean up database connections."""
        self.repo_conn.close()
        self.graph_conn.close()