"""Data Flow Graph Builder - constructs variable data flow graphs.

This module builds data flow graphs from normalized assignment and return data
stored in the database. It tracks how data flows between variables through
assignments and function returns.

Architecture:
- Database-first: NO fallbacks, NO JSON parsing
- Reads from normalized junction tables (assignment_sources, function_return_sources)
- Returns same format as builder.py (dataclass -> asdict)
- Zero tolerance for missing data - hard fail exposes bugs
- Strategy Pattern: Language-specific logic delegated to strategies/
"""


import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any
from collections import defaultdict

import click

# Shared types (extracted to prevent circular imports with strategies)
from .types import DFGNode, DFGEdge, create_bidirectional_edges

# Strategy Pattern: Language-specific logic delegated to strategies
from .strategies.python_orm import PythonOrmStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.interceptors import InterceptorStrategy


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

        # Strategy Pattern: Language-specific builders
        # Add new strategies here when supporting new languages (Rust, Go, etc.)
        # Order: ORM strategies first (build model edges), then middleware/interceptors
        self.strategies = [
            PythonOrmStrategy(),
            NodeOrmStrategy(),
            NodeExpressStrategy(),
            InterceptorStrategy(),
        ]

    def build_assignment_flow_graph(self, root: str = ".") -> dict[str, Any]:
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

        nodes: dict[str, "DFGNode"] = {}
        edges: list["DFGEdge"] = []

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
                    new_edges = create_bidirectional_edges(
                        source=source_id, target=target_id, edge_type="assignment",
                        file=file, line=line,
                        expression=source_expr[:200] if source_expr else "",
                        function=in_function if in_function else "global"
                    )
                    edges.extend(new_edges)
                    stats['edges_created'] += len(new_edges)

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

    def build_return_flow_graph(self, root: str = ".") -> dict[str, Any]:
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

        nodes: dict[str, "DFGNode"] = {}
        edges: list["DFGEdge"] = []

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
                    new_edges = create_bidirectional_edges(
                        source=var_id, target=return_id, edge_type="return",
                        file=file, line=line,
                        expression=return_expr[:200] if return_expr else "",
                        function=function_name
                    )
                    edges.extend(new_edges)
                    stats['edges_created'] += len(new_edges)

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

    def build_parameter_binding_edges(self, root: str = ".") -> dict[str, Any]:
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

        nodes: dict[str, "DFGNode"] = {}
        edges: list["DFGEdge"] = []

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

                # FIX: Preserve class names for JavaScript/TypeScript (e.g. ZoneService.createArea)
                # Only strip Python module paths (e.g., "theauditor.taint.core.trace_taint" -> "trace_taint")
                if callee_file.endswith('.py') and '.' in callee_function:
                    # Python: strip module path but be careful with class methods
                    parts = callee_function.split('.')
                    # If it looks like module.module.function, take last part
                    # If it looks like Class.method (2 parts), preserve it
                    if len(parts) > 2:
                        callee_func_name = parts[-1]  # Strip module path
                    else:
                        callee_func_name = callee_function  # Preserve Class.method
                else:
                    # JavaScript/TypeScript: ALWAYS preserve full name (Class.method)
                    callee_func_name = callee_function

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
                new_edges = create_bidirectional_edges(
                    source=source_id, target=target_id, edge_type="parameter_binding",
                    file=caller_file, line=line,
                    expression=f"{callee_function}({argument_expr})",
                    function=caller_function,
                    metadata={"callee": callee_function,
                            "param_name": param_name,
                            "arg_expr": argument_expr}
                )
                edges.extend(new_edges)
                stats['edges_created'] += len(new_edges)

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

    def build_cross_boundary_edges(self, root: str = ".") -> dict[str, Any]:
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

        nodes: dict[str, "DFGNode"] = {}
        edges: list["DFGEdge"] = []

        stats = {
            'total_matches': 0,
            'exact_matches': 0,
            'suffix_matches': 0,
            'edges_created': 0,
            'unique_nodes': 0,
            'skipped_no_body': 0,
            'skipped_no_handler': 0,
            'skipped_no_match': 0
        }

        # [FIX 2024-11] VECTORIZED MATCHING: O(1) exact + O(M) suffix with early break
        # Previous: O(N*M) nested loops for exact AND suffix matching
        # Now: Dict lookup for exact, pre-sorted list for suffix (longest paths first)

        # Step 1: Build backend endpoint indexes
        print("[DFG Builder] Loading backend API endpoints...")
        cursor.execute("""
            SELECT file, method, full_path, handler_function
            FROM api_endpoints
            WHERE handler_function IS NOT NULL
              AND full_path IS NOT NULL
              AND method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        """)

        # Two indexes for O(1) exact match + efficient suffix match
        exact_lookup: dict[tuple[str, str], dict] = {}  # (method, path) -> route
        suffix_candidates: dict[str, list[dict]] = defaultdict(list)  # method -> [routes sorted by len DESC]

        for row in cursor.fetchall():
            clean_path = row['full_path'].rstrip('/')
            route = {
                'path': clean_path,
                'file': row['file'],
                'handler_function': row['handler_function'],
                'full_path': row['full_path']
            }
            # Exact lookup index
            exact_lookup[(row['method'], clean_path)] = route
            # Suffix candidates (will sort after)
            suffix_candidates[row['method']].append(route)

        # Pre-sort suffix candidates by path length DESC (longest/most specific first)
        # This ensures we match /api/users/profile before /api/users
        for method in suffix_candidates:
            suffix_candidates[method].sort(key=lambda r: len(r['path']), reverse=True)

        # Step 2: Fetch frontend API calls (no JOIN constraint)
        print("[DFG Builder] Loading frontend API calls...")
        cursor.execute("""
            SELECT file, line, method, url_literal, body_variable, function_name
            FROM frontend_api_calls
            WHERE body_variable IS NOT NULL
              AND url_literal IS NOT NULL
              AND method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        """)

        frontend_calls = cursor.fetchall()

        # Step 3: Soft match frontend calls to backend routes
        print(f"[DFG Builder] Matching {len(frontend_calls)} frontend calls to backend endpoints...")

        with click.progressbar(
            frontend_calls,
            label="Building cross-boundary edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['url_literal']}" if x else None
        ) as call_results:
            for call in call_results:
                # Extract call metadata
                frontend_url = call['url_literal']
                method = call['method']
                fe_file = call['file']
                fe_line = call['line']
                fe_body = call['body_variable']
                fe_func = call['function_name'] if call['function_name'] else 'global'

                # Skip if no body variable
                if not fe_body:
                    stats['skipped_no_body'] += 1
                    continue

                # Clean frontend URL (strip trailing slash)
                clean_frontend_url = frontend_url.rstrip('/')

                # [FIX 2024-11] VECTORIZED LOOKUP
                # Attempt 1: O(1) Exact Match via dict lookup
                backend_match = exact_lookup.get((method, clean_frontend_url))
                match_type = None

                if backend_match:
                    match_type = "exact"
                    stats['exact_matches'] += 1
                else:
                    # Attempt 2: Suffix Match (pre-sorted by length DESC for most specific first)
                    # Example: frontend="https://api.example.com/api/users" matches backend="/api/users"
                    candidates = suffix_candidates.get(method, [])
                    for route in candidates:
                        # SAFETY CHECK: Don't match root "/" against everything
                        if len(route['path']) > 1 and clean_frontend_url.endswith(route['path']):
                            backend_match = route
                            match_type = "suffix"
                            stats['suffix_matches'] += 1
                            break  # First match is most specific due to pre-sorting

                # Skip if no match found
                if not backend_match:
                    stats['skipped_no_match'] += 1
                    continue

                stats['total_matches'] += 1

                # Extract backend metadata
                be_file = backend_match['file']
                handler_func = backend_match['handler_function']
                full_path = backend_match['full_path']

                # Skip if no handler function
                if not handler_func:
                    stats['skipped_no_handler'] += 1
                    continue

                # Extract handler function name
                # First, remove wrapper if present: "handler(controller.create)" -> "controller.create"
                if handler_func.startswith('handler(') and handler_func.endswith(')'):
                    handler_func = handler_func[8:-1]  # Remove "handler(" and ")"

                # Now extract the function name: "controller.create" -> "create"
                if '.' in handler_func:
                    controller_func = handler_func.split('.')[-1]
                else:
                    controller_func = handler_func

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
                """, (be_file, method))

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
                new_edges = create_bidirectional_edges(
                    source=source_id, target=target_id, edge_type="cross_boundary",
                    file=fe_file, line=fe_line,
                    expression=f"{method} {frontend_url}",
                    function=fe_func,
                    metadata={
                        "frontend_file": fe_file,
                        "backend_file": target_file,
                        "api_method": method,
                        "api_route": full_path,
                        "body_variable": fe_body,
                        "request_field": req_field,
                        "match_type": match_type  # "exact" or "suffix" - for debugging soft match effectiveness
                    }
                )
                edges.extend(new_edges)
                stats['edges_created'] += len(new_edges)

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

    # ==========================================================================
    # NOTE: Language-specific methods moved to strategies/ (Phase 3 refactoring):
    # - build_express_middleware_edges -> strategies/node_express.py
    # - build_controller_implementation_edges -> strategies/node_express.py
    # - build_python_orm_edges -> strategies/python_orm.py
    # ==========================================================================

    def build_unified_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build unified data flow graph combining all edge types.

        Architecture (Strategy Pattern):
        - Core builders: Assignment, Return, Parameter, Cross-boundary (always run)
        - Strategies: Language-specific logic (Express, ORM, etc.) - pluggable

        Includes:
        - Assignment edges (x = y)
        - Return edges (return x)
        - Parameter binding edges (func(x) -> param)
        - Cross-boundary edges (frontend -> backend API)
        - Strategy edges (Express middleware, Python ORM, etc.)

        Args:
            root: Project root directory

        Returns:
            Combined graph with all data flow edges (complete provenance)
        """
        # =================================================================
        # CORE BUILDERS (Always run - language agnostic)
        # =================================================================
        print("Building assignment flow graph...")
        assignment_graph = self.build_assignment_flow_graph(root)

        print("Building return flow graph...")
        return_graph = self.build_return_flow_graph(root)

        print("Building parameter binding edges...")
        parameter_graph = self.build_parameter_binding_edges(root)

        print("Building cross-boundary API edges...")
        cross_boundary_graph = self.build_cross_boundary_edges(root)

        # Collect core graphs
        core_graphs = [assignment_graph, return_graph, parameter_graph, cross_boundary_graph]

        # =================================================================
        # STRATEGY PATTERN: Language-specific builders (pluggable)
        # =================================================================
        strategy_graphs = []
        strategy_stats = {}

        for strategy in self.strategies:
            print(f"Running strategy: {strategy.name}...")
            try:
                result = strategy.build(str(self.db_path), root)
                strategy_graphs.append(result)
                strategy_stats[strategy.name] = result.get("metadata", {}).get("stats", {})
            except Exception as e:
                # Don't crash entire build if one strategy fails
                print(f"  WARNING: Strategy {strategy.name} failed: {e}")
                strategy_stats[strategy.name] = {"error": str(e)}

        # =================================================================
        # MERGE ALL RESULTS
        # =================================================================
        # Merge nodes (dedup by id)
        nodes = {}
        for graph in core_graphs + strategy_graphs:
            for node in graph.get("nodes", []):
                nodes[node["id"]] = node

        # Combine edges
        edges = []
        for graph in core_graphs + strategy_graphs:
            edges.extend(graph.get("edges", []))

        # Merge stats
        stats = {
            "assignment_stats": assignment_graph["metadata"]["stats"],
            "return_stats": return_graph["metadata"]["stats"],
            "parameter_stats": parameter_graph["metadata"]["stats"],
            "cross_boundary_stats": cross_boundary_graph["metadata"]["stats"],
            "strategy_stats": strategy_stats,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

        print(f"\nUnified graph complete: {len(nodes)} nodes, {len(edges)} edges")

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "unified_data_flow",
                "stats": stats,
            },
        }

    def get_data_dependencies(self, file: str, variable: str,
                              function: str = None) -> dict[str, Any]:
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
        graph: dict[str, set[str]] = defaultdict(set)

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

    def _parse_argument_variable(self, arg_expr: str) -> str | None:
        """Parse an argument expression to extract the variable name.

        Handles various expression types:
        - Simple variables: "data" -> "data"
        - Property access: "obj.prop" -> "obj.prop"
        - Function calls: "validate(data)" -> "data" (unwrap)
        - Async/Arrow functions: "async () => {}" -> "function_expression"
        - Object literals: "{a: 1}" -> "object_literal"
        - Array literals: "[1, 2]" -> "array_literal"
        - String literals: "'hello'" -> "string_literal"

        Args:
            arg_expr: The argument expression string

        Returns:
            Variable name or placeholder, None if unparseable
        """
        if not arg_expr:
            return None

        # 1. Async/Arrow Functions (Fixes 102 missing asyncHandler edges)
        # We return a placeholder so the edge is CREATED.
        if arg_expr.startswith('async') or '=>' in arg_expr:
            return "function_expression"

        # 2. Object Literals (Fixes 1,921 missing config/options edges)
        if arg_expr.startswith('{') and arg_expr.endswith('}'):
            return "object_literal"

        # 3. Array Literals (Fixes 273 missing edges)
        if arg_expr.startswith('[') and arg_expr.endswith(']'):
            return "array_literal"

        # 4. Wrapped Calls (Fixes 220 missing validation edges)
        # Try to unwrap simple wrappers like validate(data) -> data
        if '(' in arg_expr and arg_expr.endswith(')'):
            start = arg_expr.find('(') + 1
            end = arg_expr.rfind(')')
            inner = arg_expr[start:end].strip()

            # If inner looks like a clean variable/property, use it
            # Allow dots, underscores, $, question marks (optional chaining)
            if inner and all(c.isalnum() or c in '._$?' for c in inner):
                return inner

            # If complex inside (e.g. nested calls), fall back to placeholder
            # BUT KEEP THE EDGE.
            return "complex_expression"

        # 5. String Literals (Fixes 2,457 missing edges)
        # Usually not taint sources, but required for graph continuity
        if arg_expr[0] in '"\'`':
            return "string_literal"

        # 6. Non-null assertions (Fixes 52 missing edges)
        # "userId!" -> "userId"
        if arg_expr.endswith('!'):
            return arg_expr[:-1]

        # 7. Fallback: Return the expression itself (cleaned)
        # This catches "prefix + path", "data[index]", etc.
        # We split by space/operators to get the primary token
        clean_expr = arg_expr.split(' ')[0]

        # Final safety check: if it creates a valid SQL/Graph ID, return it
        return clean_expr
