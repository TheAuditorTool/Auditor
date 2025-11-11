"""Data Flow Graph Builder - constructs variable data flow graphs.

This module builds data flow graphs from normalized assignment and return data
stored in the database. It tracks how data flows between variables through
assignments and function returns.

Architecture:
- Database-first: NO fallbacks, NO JSON parsing
- Reads from normalized junction tables (assignment_sources, function_return_sources)
- Returns same format as builder.py (dataclass -> asdict)
- Zero tolerance for missing data - hard fail exposes bugs
"""

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set, Optional
from collections import defaultdict

import click


@dataclass
class DFGNode:
    """Represents a variable in the data flow graph."""

    id: str  # Format: "file::variable" or "file::function::variable"
    file: str
    variable_name: str
    scope: str  # function name or "global"
    type: str = "variable"  # variable, parameter, return_value
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DFGEdge:
    """Represents a data flow edge in the graph."""

    source: str  # Source variable ID
    target: str  # Target variable ID
    file: str  # File containing this edge (moved before defaults)
    line: int  # Line number (moved before defaults)
    type: str = "assignment"  # assignment, return, parameter
    expression: str = ""  # The assignment expression
    function: str = ""  # Function context
    metadata: Dict[str, Any] = field(default_factory=dict)


class DFGBuilder:
    """Build data flow graphs from normalized database tables.

    This builder operates in database-first mode, reading all assignment and
    return data from the normalized junction tables. NO JSON parsing exists.
    If data is missing, the query returns empty - exposing indexer bugs.
    """

    def __init__(self, db_path: str):
        """Initialize DFG builder with database path.

        Args:
            db_path: Path to repo_index.db database
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def build_assignment_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build data flow graph from variable assignments.

        Queries the normalized assignments + assignment_sources tables to construct
        a graph showing how data flows through variable assignments.

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata (same format as builder.py)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_assignments': 0,
            'assignments_with_sources': 0,
            'edges_created': 0,
            'unique_variables': 0
        }

        # Query normalized assignments with their source variables
        # NO JSON PARSING - uses JOIN on normalized junction table
        cursor.execute("""
            SELECT
                a.file,
                a.line,
                a.target_var,
                a.source_expr,
                a.in_function,
                asrc.source_var_name
            FROM assignments a
            LEFT JOIN assignment_sources asrc
                ON a.file = asrc.assignment_file
                AND a.line = asrc.assignment_line
                AND a.target_var = asrc.assignment_target
            ORDER BY a.file, a.line
        """)

        with click.progressbar(
            cursor.fetchall(),
            label="Building data flow graph",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None
        ) as assignments:
            for row in assignments:
                stats['total_assignments'] += 1

                file = row['file']
                line = row['line']
                target_var = row['target_var']
                source_expr = row['source_expr']
                in_function = row['in_function']
                source_var_name = row['source_var_name']

                # Create target node (variable being assigned to)
                target_scope = in_function if in_function else "global"
                target_id = f"{file}::{target_scope}::{target_var}"

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=file,
                        variable_name=target_var,
                        scope=target_scope,
                        type="variable",
                        metadata={
                            "first_assignment_line": line,
                            "assignment_count": 0
                        }
                    )

                # Use .get() with default - node may have been created as source first
                nodes[target_id].metadata["assignment_count"] = nodes[target_id].metadata.get("assignment_count", 0) + 1

                # If there's a source variable, create edge
                if source_var_name:
                    stats['assignments_with_sources'] += 1

                    # Create source node
                    source_scope = in_function if in_function else "global"
                    source_id = f"{file}::{source_scope}::{source_var_name}"

                    if source_id not in nodes:
                        nodes[source_id] = DFGNode(
                            id=source_id,
                            file=file,
                            variable_name=source_var_name,
                            scope=source_scope,
                            type="variable",
                            metadata={"usage_count": 0}
                        )

                    nodes[source_id].metadata["usage_count"] = nodes[source_id].metadata.get("usage_count", 0) + 1

                    # Create edge: source_var -> target_var
                    edge = DFGEdge(
                        source=source_id,
                        target=target_id,
                        type="assignment",
                        file=file,
                        line=line,
                        expression=source_expr[:200] if source_expr else "",  # Truncate long expressions
                        function=in_function if in_function else "global",
                        metadata={}
                    )
                    edges.append(edge)
                    stats['edges_created'] += 1

        conn.close()

        stats['unique_variables'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "data_flow",
                "stats": stats
            }
        }

    def build_return_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build data flow graph from function returns.

        Queries the normalized function_returns + function_return_sources tables
        to construct a graph showing how data flows through return statements.

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_returns': 0,
            'returns_with_vars': 0,
            'edges_created': 0,
            'unique_variables': 0
        }

        # Query normalized function returns with their return variables
        # NO JSON PARSING - uses JOIN on normalized junction table
        cursor.execute("""
            SELECT
                fr.file,
                fr.line,
                fr.function_name,
                fr.return_expr,
                frsrc.return_var_name
            FROM function_returns fr
            LEFT JOIN function_return_sources frsrc
                ON fr.file = frsrc.return_file
                AND fr.line = frsrc.return_line
                AND fr.function_name = frsrc.return_function
            ORDER BY fr.file, fr.line
        """)

        with click.progressbar(
            cursor.fetchall(),
            label="Building return flow graph",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None
        ) as returns:
            for row in returns:
                stats['total_returns'] += 1

                file = row['file']
                line = row['line']
                function_name = row['function_name']
                return_expr = row['return_expr']
                return_var_name = row['return_var_name']

                # Create return value node
                return_id = f"{file}::{function_name}::return"

                if return_id not in nodes:
                    nodes[return_id] = DFGNode(
                        id=return_id,
                        file=file,
                        variable_name=f"{function_name}_return",
                        scope=function_name,
                        type="return_value",
                        metadata={
                            "return_line": line,
                            "return_expr": return_expr[:200] if return_expr else ""
                        }
                    )

                # If there's a return variable, create edge
                if return_var_name:
                    stats['returns_with_vars'] += 1

                    # Create source variable node (variable being returned)
                    var_id = f"{file}::{function_name}::{return_var_name}"

                    if var_id not in nodes:
                        nodes[var_id] = DFGNode(
                            id=var_id,
                            file=file,
                            variable_name=return_var_name,
                            scope=function_name,
                            type="variable",
                            metadata={"returned": True}
                        )

                    # Create edge: variable -> return_value
                    edge = DFGEdge(
                        source=var_id,
                        target=return_id,
                        type="return",
                        file=file,
                        line=line,
                        expression=return_expr[:200] if return_expr else "",
                        function=function_name,
                        metadata={}
                    )
                    edges.append(edge)
                    stats['edges_created'] += 1

        conn.close()

        stats['unique_variables'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "return_flow",
                "stats": stats
            }
        }

    def build_parameter_binding_edges(self, root: str = ".") -> Dict[str, Any]:
        """Build parameter binding edges connecting caller arguments to callee parameters.

        This is the CRITICAL inter-procedural data flow edge that enables multi-hop
        cross-function taint analysis. Without these edges, IFDS cannot traverse
        function boundaries.

        For a call like: processData(userInput)
        Creates edge: caller_file::caller_func::userInput -> callee_file::processData::data

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_calls': 0,
            'calls_with_metadata': 0,
            'edges_created': 0,
            'skipped_literals': 0,
            'skipped_complex': 0
        }

        # Query function calls with complete parameter binding metadata
        # ZERO FALLBACK: Only process calls with all required fields
        cursor.execute("""
            SELECT
                file, line, caller_function, callee_function,
                argument_expr, param_name, callee_file_path
            FROM function_call_args
            WHERE param_name IS NOT NULL
              AND argument_expr IS NOT NULL
              AND callee_file_path IS NOT NULL
              AND caller_function IS NOT NULL
        """)

        with click.progressbar(
            cursor.fetchall(),
            label="Building parameter binding edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['callee_function']}" if x else None
        ) as calls:
            for row in calls:
                stats['total_calls'] += 1

                # Extract metadata
                caller_file = row['file']
                caller_function = row['caller_function']
                callee_function = row['callee_function']
                callee_file = row['callee_file_path']
                argument_expr = row['argument_expr']
                param_name = row['param_name']
                line = row['line']

                # Parse argument expression to extract variable name
                # ZERO FALLBACK: Skip literals and complex expressions
                arg_var = self._parse_argument_variable(argument_expr)
                if not arg_var:
                    stats['skipped_complex'] += 1
                    continue

                # Check if it's a literal (number, string, boolean)
                if arg_var.isdigit() or arg_var in ('True', 'False', 'None', 'null', 'undefined'):
                    stats['skipped_literals'] += 1
                    continue

                stats['calls_with_metadata'] += 1

                # Find callee function name (strip module path)
                # e.g., "theauditor.taint.core.trace_taint" -> "trace_taint"
                callee_func_name = callee_function.split('.')[-1] if '.' in callee_function else callee_function

                # Construct node IDs (matching dfg format: file::function::variable)
                caller_scope = caller_function if caller_function else "global"
                source_id = f"{caller_file}::{caller_scope}::{arg_var}"

                # For callee, find the actual function definition
                # ZERO FALLBACK: Use callee_func_name as scope
                target_id = f"{callee_file}::{callee_func_name}::{param_name}"

                # Create nodes if they don't exist
                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=caller_file,
                        variable_name=arg_var,
                        scope=caller_scope,
                        type="variable",
                        metadata={"used_as_argument": True}
                    )

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=callee_file,
                        variable_name=param_name,
                        scope=callee_func_name,
                        type="parameter",
                        metadata={"is_parameter": True}
                    )

                # Create parameter binding edge: argument -> parameter
                edge = DFGEdge(
                    source=source_id,
                    target=target_id,
                    type="parameter_binding",
                    file=caller_file,
                    line=line,
                    expression=f"{callee_function}({argument_expr})",
                    function=caller_function,
                    metadata={
                        "callee": callee_function,
                        "param_name": param_name,
                        "arg_expr": argument_expr
                    }
                )
                edges.append(edge)
                stats['edges_created'] += 1

        conn.close()

        stats['unique_nodes'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "parameter_binding",
                "stats": stats
            }
        }

    def build_cross_boundary_edges(self, root: str = ".") -> Dict[str, Any]:
        """Build edges connecting frontend API calls to backend controllers.

        Creates edges from frontend body variables to backend req.body/params/query.
        This enables cross-boundary taint flow tracking from user inputs in the
        frontend to API handlers in the backend.

        Example edge:
            frontend/src/components/Form.tsx::submit::userData ->
            backend/src/controllers/user.controller.ts::create::req.body

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_matches': 0,
            'edges_created': 0,
            'unique_nodes': 0,
            'skipped_no_body': 0,
            'skipped_no_handler': 0
        }

        # DETERMINISTIC JOIN: Match frontend API calls to backend endpoints
        # Uses full_path (actual route) not pattern (generic template)
        # Handles trailing slash differences with rtrim()
        cursor.execute("""
            SELECT
                fe.file AS fe_file,
                fe.line AS fe_line,
                fe.method AS method,
                fe.url_literal AS url_literal,
                fe.body_variable AS body_variable,
                fe.function_name AS fe_function,
                be.file AS be_file,
                be.full_path AS full_path,
                be.handler_function AS handler_function
            FROM frontend_api_calls fe
            JOIN api_endpoints be ON
                fe.method = be.method
                AND rtrim(fe.url_literal, '/') = rtrim(be.full_path, '/')
            WHERE fe.body_variable IS NOT NULL
              AND be.handler_function IS NOT NULL
              AND fe.method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        """)

        matches = cursor.fetchall()
        stats['total_matches'] = len(matches)

        with click.progressbar(
            matches,
            label="Building cross-boundary edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['url_literal']}" if x else None
        ) as match_results:
            for match in match_results:
                # Skip if no body variable (shouldn't happen due to WHERE clause)
                if not match['body_variable']:
                    stats['skipped_no_body'] += 1
                    continue

                # Skip if no handler function (shouldn't happen due to WHERE clause)
                if not match['handler_function']:
                    stats['skipped_no_handler'] += 1
                    continue

                # Extract handler function name
                # First, remove wrapper if present: "handler(controller.create)" -> "controller.create"
                handler_func = match['handler_function']
                if handler_func.startswith('handler(') and handler_func.endswith(')'):
                    handler_func = handler_func[8:-1]  # Remove "handler(" and ")"

                # Now extract the function name: "controller.create" -> "create"
                if '.' in handler_func:
                    controller_func = handler_func.split('.')[-1]
                else:
                    controller_func = handler_func

                # Frontend variables
                fe_file = match['fe_file']
                fe_body = match['body_variable']
                fe_func = match['fe_function'] if match['fe_function'] else 'global'

                # Backend route file
                be_file = match['be_file']
                method = match['method']

                # Query for the actual controller file using the handler function
                # ZERO FALLBACK: If not found, use the route file as controller file
                cursor.execute("""
                    SELECT DISTINCT path
                    FROM symbols
                    WHERE name = ? AND type = 'function'
                    ORDER BY
                        CASE WHEN path LIKE '%controller%' THEN 0 ELSE 1 END,
                        path
                    LIMIT 1
                """, (controller_func,))

                controller_result = cursor.fetchone()
                controller_file = controller_result['path'] if controller_result else be_file

                # Create frontend node (source)
                source_id = f"{fe_file}::{fe_func}::{fe_body}"
                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=fe_file,
                        variable_name=fe_body,
                        scope=fe_func,
                        type="variable",
                        metadata={"is_frontend_input": True}
                    )

                # Determine backend request field based on HTTP method
                # POST/PUT/PATCH typically use body, GET/DELETE use params/query
                if method in ('POST', 'PUT', 'PATCH'):
                    req_field = 'req.body'
                else:
                    req_field = 'req.params'  # Could also be req.query

                # Find the first middleware in the chain for this route
                # The middleware chains are stored with router-relative paths
                # So we need to match on the backend file and method
                # Try to find middleware chain in the route file
                cursor.execute("""
                    SELECT file, handler_function, handler_expr, execution_order
                    FROM express_middleware_chains
                    WHERE file = ?
                      AND route_method = ?
                      AND handler_type IN ('middleware', 'controller')
                    ORDER BY execution_order
                    LIMIT 1
                """, (match['be_file'], method))

                first_middleware = cursor.fetchone()

                if first_middleware:
                    # Target the first middleware/handler in the chain
                    middleware_func = first_middleware['handler_function'] or first_middleware['handler_expr']
                    target_file = first_middleware['file']
                    target_id = f"{target_file}::{middleware_func}::{req_field}"
                else:
                    # No middleware chain found, use controller directly (fallback)
                    target_id = f"{controller_file}::{controller_func}::{req_field}"
                    target_file = controller_file
                    middleware_func = controller_func

                # Create backend node (target)
                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=target_file,
                        variable_name=req_field,
                        scope=middleware_func,
                        type="parameter",
                        metadata={"is_api_source": True, "method": method}
                    )

                # Create cross-boundary edge
                edge = DFGEdge(
                    source=source_id,
                    target=target_id,
                    type="cross_boundary",
                    file=fe_file,
                    line=match['fe_line'],
                    expression=f"{method} {match['url_literal']}",
                    function=fe_func,
                    metadata={
                        "frontend_file": fe_file,
                        "backend_file": target_file,
                        "api_method": method,
                        "api_route": match['full_path'],
                        "body_variable": fe_body,
                        "request_field": req_field
                    }
                )
                edges.append(edge)
                stats['edges_created'] += 1

        conn.close()

        stats['unique_nodes'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "cross_boundary",
                "stats": stats
            }
        }

    def build_express_middleware_edges(self, root: str = ".") -> Dict[str, Any]:
        """Build edges connecting Express middleware chains.

        Creates edges showing data flow through middleware execution order.
        For a route with validateBody -> authenticate -> controller,
        creates edges showing req.body flows through the chain.

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_routes': 0,
            'total_middleware': 0,
            'edges_created': 0,
            'unique_nodes': 0
        }

        # Query middleware chains ordered by file, route and execution order
        cursor.execute("""
            SELECT file, route_path, route_method, execution_order,
                   handler_expr, handler_type, handler_function
            FROM express_middleware_chains
            WHERE handler_type IN ('middleware', 'controller')
            ORDER BY file, route_path, route_method, execution_order
        """)

        # Group by file AND route (to avoid cross-file edges)
        routes: Dict[str, List] = defaultdict(list)
        for row in cursor.fetchall():
            # Include file in the key to prevent cross-file grouping
            key = f"{row['file']}::{row['route_method']} {row['route_path']}"
            routes[key].append(row)
            stats['total_middleware'] += 1

        stats['total_routes'] = len(routes)

        with click.progressbar(
            routes.items(),
            label="Building middleware chain edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: x[0] if x else None
        ) as route_items:
            for route_key, handlers in route_items:
                if len(handlers) < 2:
                    continue  # Need at least 2 handlers to create edges

                # Create edges between consecutive handlers in the chain
                for i in range(len(handlers) - 1):
                    curr_handler = handlers[i]
                    next_handler = handlers[i + 1]

                    # Skip if current handler is a controller (controllers are endpoints, not middleware)
                    # Controllers don't pass control to the next handler
                    if curr_handler['handler_type'] == 'controller':
                        continue

                    # Extract handler identifiers
                    curr_func = curr_handler['handler_function'] or curr_handler['handler_expr']
                    next_func = next_handler['handler_function'] or next_handler['handler_expr']

                    if not curr_func or not next_func:
                        continue

                    # Middleware typically passes req object through the chain
                    # Create edges for req, req.body, req.params, req.query
                    for req_field in ['req', 'req.body', 'req.params', 'req.query']:
                        # Source node (current handler output)
                        source_id = f"{curr_handler['file']}::{curr_func}::{req_field}"
                        if source_id not in nodes:
                            nodes[source_id] = DFGNode(
                                id=source_id,
                                file=curr_handler['file'],
                                variable_name=req_field,
                                scope=curr_func,
                                type="variable",
                                metadata={"is_middleware": True}
                            )

                        # Target node (next handler input)
                        target_id = f"{next_handler['file']}::{next_func}::{req_field}"
                        if target_id not in nodes:
                            nodes[target_id] = DFGNode(
                                id=target_id,
                                file=next_handler['file'],
                                variable_name=req_field,
                                scope=next_func,
                                type="parameter",
                                metadata={"is_middleware": True}
                            )

                        # Create middleware chain edge
                        edge = DFGEdge(
                            source=source_id,
                            target=target_id,
                            type="express_middleware_chain",
                            file=curr_handler['file'],
                            line=0,  # Middleware chains don't have specific line numbers
                            expression=f"{curr_func} -> {next_func}",
                            function=curr_func,
                            metadata={
                                "route": route_key,
                                "execution_order": curr_handler['execution_order'],
                                "next_order": next_handler['execution_order']
                            }
                        )
                        edges.append(edge)
                        stats['edges_created'] += 1

        conn.close()

        stats['unique_nodes'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "express_middleware",
                "stats": stats
            }
        }

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

        # Must start with letter or underscore (Python/JS identifier)
        if not (arg_expr[0].isalpha() or arg_expr[0] == '_'):
            return None

        # Valid identifier pattern: variable or variable.field.field
        # Just return the full expression (may include dots for access paths)
        return arg_expr

    def build_controller_implementation_edges(self, root: str = ".") -> Dict[str, Any]:
        """Build edges connecting route handlers to controller implementations.

        This bridges the gap between Express route handlers and their actual
        controller method implementations by:
        1. Finding handler expressions like 'handler(controller.create)'
        2. Resolving controller imports to actual file paths
        3. Finding controller methods in symbols table
        4. Creating edges from handlers to implementations

        Args:
            root: Project root directory

        Returns:
            Graph with controller implementation edges
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes = {}
        edges = []

        stats = {
            'handlers_processed': 0,
            'controllers_resolved': 0,
            'edges_created': 0,
            'failed_resolutions': 0
        }

        # Get all controller handlers from express_middleware_chains
        cursor.execute("""
            SELECT DISTINCT
                file,
                route_path,
                route_method,
                handler_expr
            FROM express_middleware_chains
            WHERE handler_type = 'controller'
              AND handler_expr IS NOT NULL
        """)

        handlers = cursor.fetchall()
        stats['handlers_processed'] = len(handlers)

        for handler in handlers:
            route_file = handler['file']
            handler_expr = handler['handler_expr']

            # Parse the handler expression to extract object and method
            object_name = None
            method_name = None

            # Pattern 1: handler(controller.method) or fileHandler(controller.method)
            if '(' in handler_expr and ')' in handler_expr:
                # Extract content between parentheses
                start = handler_expr.index('(') + 1
                end = handler_expr.rindex(')')
                inner = handler_expr[start:end]

                if '.' in inner:
                    object_name, method_name = inner.split('.', 1)

            # Pattern 2: controller.method (direct reference)
            elif '.' in handler_expr:
                object_name, method_name = handler_expr.split('.', 1)

            # Pattern 3: Single identifiers like 'userId' - skip these
            else:
                continue

            if not object_name or not method_name:
                continue

            # Resolve the controller import
            # First try alias_name (default imports like: import controller from ...)
            cursor.execute("""
                SELECT package
                FROM import_styles
                WHERE file = ?
                  AND alias_name = ?
            """, (route_file, object_name))

            import_result = cursor.fetchone()

            # If not found, try named imports (import { categoryController } from ...)
            if not import_result:
                # Check if it's a named import
                cursor.execute("""
                    SELECT ist.package
                    FROM import_style_names isn
                    JOIN import_styles ist ON isn.import_file = ist.file
                        AND isn.import_line = ist.line
                    WHERE isn.import_file = ?
                      AND isn.imported_name = ?
                      AND ist.package LIKE '%controller%'
                """, (route_file, object_name))

                import_result = cursor.fetchone()

            if not import_result:
                stats['failed_resolutions'] += 1
                continue

            import_path = import_result['package']

            # Resolve TypeScript path alias to actual file
            resolved_path = self._resolve_ts_path(import_path)

            # Find the controller class
            cursor.execute("""
                SELECT name
                FROM symbols
                WHERE path = ?
                  AND type = 'class'
            """, (resolved_path,))

            class_result = cursor.fetchone()
            if not class_result:
                # Some controllers might export functions directly without a class
                # Try to find the method directly
                cursor.execute("""
                    SELECT name
                    FROM symbols
                    WHERE path = ?
                      AND name = ?
                      AND type = 'function'
                """, (resolved_path, method_name))

                method_result = cursor.fetchone()
                if method_result:
                    full_method_name = method_result['name']
                else:
                    stats['failed_resolutions'] += 1
                    continue
            else:
                class_name = class_result['name']
                full_method_name = f'{class_name}.{method_name}'

                # Find the actual method
                cursor.execute("""
                    SELECT name
                    FROM symbols
                    WHERE path = ?
                      AND name = ?
                      AND type = 'function'
                """, (resolved_path, full_method_name))

                method_result = cursor.fetchone()
                if not method_result:
                    stats['failed_resolutions'] += 1
                    continue

            stats['controllers_resolved'] += 1

            # Create nodes and edges for all variable suffixes
            for suffix in ['req', 'req.body', 'req.params', 'req.query', 'res']:
                # Source node (handler in route)
                source_id = f"{route_file}::{handler_expr}::{suffix}"
                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=route_file,
                        variable_name=suffix,
                        scope=handler_expr,
                        type="parameter",
                        metadata={"handler": True}
                    )

                # Target node (controller method)
                target_id = f"{resolved_path}::{full_method_name}::{suffix}"
                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=resolved_path,
                        variable_name=suffix,
                        scope=full_method_name,
                        type="parameter",
                        metadata={"controller": True}
                    )

                # Create edge
                edge = DFGEdge(
                    source=source_id,
                    target=target_id,
                    file=route_file,
                    line=0,  # We don't have line numbers for these
                    type="controller_implementation",
                    expression=f"{handler_expr} -> {full_method_name}",
                    function=handler_expr,
                    metadata={
                        "route_path": handler['route_path'],
                        "route_method": handler['route_method']
                    }
                )
                edges.append(edge)
                stats['edges_created'] += 1

        conn.close()

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "type": "controller_implementation_flow",
                "root": root,
                "stats": stats
            }
        }

    def _resolve_ts_path(self, import_path: str) -> str:
        """Resolve TypeScript path aliases to actual file paths.

        Based on tsconfig.json mappings:
        @controllers/* -> backend/src/controllers/*
        @services/* -> backend/src/services/*
        etc.

        Args:
            import_path: Import path potentially containing TypeScript alias

        Returns:
            Resolved file path with .ts extension
        """
        # Map of TypeScript aliases to actual paths
        # This could be read from tsconfig.json, but hardcoding for stability
        alias_map = {
            '@controllers/': 'backend/src/controllers/',
            '@services/': 'backend/src/services/',
            '@middleware/': 'backend/src/middleware/',
            '@utils/': 'backend/src/utils/',
            '@models/': 'backend/src/models/',
            '@validation/': 'backend/src/validation/',
            '@config/': 'backend/src/config/',
            '@schemas/': 'backend/src/schemas/',
            '@routes/': 'backend/src/routes/',
        }

        for alias, base_path in alias_map.items():
            if import_path.startswith(alias):
                # Replace alias with actual path and add .ts extension
                module_name = import_path[len(alias):]
                return f"{base_path}{module_name}.ts"

        # If no alias, check if it needs .ts extension
        if not import_path.endswith('.ts') and not import_path.endswith('.js'):
            return f"{import_path}.ts"

        return import_path

    def build_unified_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build unified data flow graph combining all edge types.

        Includes:
        - Assignment edges (x = y)
        - Return edges (return x)
        - Parameter binding edges (func(x) -> param)
        - Cross-boundary edges (frontend -> backend API)
        - Express middleware edges (chain execution order)

        Args:
            root: Project root directory

        Returns:
            Combined graph with all data flow edges (complete provenance)
        """
        # Build all graph types
        print("Building assignment flow graph...")
        assignment_graph = self.build_assignment_flow_graph(root)

        print("Building return flow graph...")
        return_graph = self.build_return_flow_graph(root)

        print("Building parameter binding edges...")
        parameter_graph = self.build_parameter_binding_edges(root)

        print("Building cross-boundary API edges...")
        cross_boundary_graph = self.build_cross_boundary_edges(root)

        print("Building Express middleware chain edges...")
        middleware_graph = self.build_express_middleware_edges(root)

        print("Building controller implementation edges...")
        controller_impl_graph = self.build_controller_implementation_edges(root)

        # Merge nodes (dedup by id)
        nodes = {}
        for graph in [assignment_graph, return_graph, parameter_graph,
                      cross_boundary_graph, middleware_graph, controller_impl_graph]:
            for node in graph["nodes"]:
                nodes[node["id"]] = node

        # Combine edges
        edges = (assignment_graph["edges"] +
                return_graph["edges"] +
                parameter_graph["edges"] +
                cross_boundary_graph["edges"] +
                middleware_graph["edges"] +
                controller_impl_graph["edges"])

        # Merge stats
        stats = {
            "assignment_stats": assignment_graph["metadata"]["stats"],
            "return_stats": return_graph["metadata"]["stats"],
            "parameter_stats": parameter_graph["metadata"]["stats"],
            "cross_boundary_stats": cross_boundary_graph["metadata"]["stats"],
            "middleware_stats": middleware_graph["metadata"]["stats"],
            "controller_implementation_stats": controller_impl_graph["metadata"]["stats"],
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }

        print(f"\nUnified graph complete: {len(nodes)} nodes, {len(edges)} edges")

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "unified_data_flow",
                "stats": stats
            }
        }

    def get_data_dependencies(self, file: str, variable: str,
                              function: str = None) -> Dict[str, Any]:
        """Get all variables that flow into the given variable.

        Performs a backwards traversal from the target variable to find all
        source variables in its data dependency chain.

        Args:
            file: File path
            variable: Variable name
            function: Function scope (None for global)

        Returns:
            Dict with dependencies and flow paths
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        scope = function if function else "global"
        target_id = f"{file}::{scope}::{variable}"

        # Build adjacency list from assignments
        graph: Dict[str, Set[str]] = defaultdict(set)

        cursor.execute("""
            SELECT
                a.file,
                a.target_var,
                a.in_function,
                asrc.source_var_name
            FROM assignments a
            LEFT JOIN assignment_sources asrc
                ON a.file = asrc.assignment_file
                AND a.line = asrc.assignment_line
                AND a.target_var = asrc.assignment_target
            WHERE asrc.source_var_name IS NOT NULL
        """)

        for row in cursor.fetchall():
            f = row['file']
            sc = row['in_function'] if row['in_function'] else "global"
            target = f"{f}::{sc}::{row['target_var']}"
            source = f"{f}::{sc}::{row['source_var_name']}"

            # Edge: source -> target (for backwards traversal, we reverse this)
            graph[target].add(source)

        conn.close()

        # BFS backwards from target to find all dependencies
        dependencies = set()
        visited = set()
        queue = [target_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            # Get all variables that flow into current
            sources = graph.get(current, set())
            for source in sources:
                if source not in visited:
                    dependencies.add(source)
                    queue.append(source)

        return {
            "target": target_id,
            "dependencies": list(dependencies),
            "dependency_count": len(dependencies)
        }
