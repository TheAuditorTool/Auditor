"""Data Flow Graph Builder - constructs variable data flow graphs."""

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger

from .strategies.bash_pipes import BashPipeStrategy
from .strategies.go_http import GoHttpStrategy
from .strategies.go_orm import GoOrmStrategy
from .strategies.interceptors import InterceptorStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.python_orm import PythonOrmStrategy
from .strategies.rust_async import RustAsyncStrategy
from .strategies.rust_traits import RustTraitStrategy
from .types import DFGEdge, DFGNode, create_bidirectional_edges


class DFGBuilder:
    """Build data flow graphs from normalized database tables."""

    def __init__(self, db_path: str):
        """Initialize DFG builder with database path."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.strategies = [
            PythonOrmStrategy(),
            NodeOrmStrategy(),
            NodeExpressStrategy(),
            InterceptorStrategy(),
            BashPipeStrategy(),
            GoHttpStrategy(),
            GoOrmStrategy(),
            RustTraitStrategy(),
            RustAsyncStrategy(),
        ]

    def build_assignment_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build data flow graph from variable assignments."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_assignments": 0,
            "assignments_with_sources": 0,
            "edges_created": 0,
            "unique_variables": 0,
        }

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
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None,
        ) as assignments:
            for row in assignments:
                stats["total_assignments"] += 1

                file = row["file"]
                line = row["line"]
                target_var = row["target_var"]
                source_expr = row["source_expr"]
                in_function = row["in_function"]
                source_var_name = row["source_var_name"]

                target_scope = in_function if in_function else "global"
                target_id = f"{file}::{target_scope}::{target_var}"

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=file,
                        variable_name=target_var,
                        scope=target_scope,
                        type="variable",
                        metadata={"first_assignment_line": line, "assignment_count": 0},
                    )

                nodes[target_id].metadata["assignment_count"] = (
                    nodes[target_id].metadata.get("assignment_count", 0) + 1
                )

                if source_var_name:
                    stats["assignments_with_sources"] += 1

                    source_scope = in_function if in_function else "global"
                    source_id = f"{file}::{source_scope}::{source_var_name}"

                    if source_id not in nodes:
                        nodes[source_id] = DFGNode(
                            id=source_id,
                            file=file,
                            variable_name=source_var_name,
                            scope=source_scope,
                            type="variable",
                            metadata={"usage_count": 0},
                        )

                    nodes[source_id].metadata["usage_count"] = (
                        nodes[source_id].metadata.get("usage_count", 0) + 1
                    )

                    new_edges = create_bidirectional_edges(
                        source=source_id,
                        target=target_id,
                        edge_type="assignment",
                        file=file,
                        line=line,
                        expression=source_expr[:200] if source_expr else "",
                        function=in_function if in_function else "global",
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)

        conn.close()

        stats["unique_variables"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "data_flow",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def build_return_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build data flow graph from function returns."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_returns": 0,
            "returns_with_vars": 0,
            "edges_created": 0,
            "unique_variables": 0,
        }

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
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None,
        ) as returns:
            for row in returns:
                stats["total_returns"] += 1

                file = row["file"]
                line = row["line"]
                function_name = row["function_name"]
                return_expr = row["return_expr"]
                return_var_name = row["return_var_name"]

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
                            "return_expr": return_expr[:200] if return_expr else "",
                        },
                    )

                if return_var_name:
                    stats["returns_with_vars"] += 1

                    var_id = f"{file}::{function_name}::{return_var_name}"

                    if var_id not in nodes:
                        nodes[var_id] = DFGNode(
                            id=var_id,
                            file=file,
                            variable_name=return_var_name,
                            scope=function_name,
                            type="variable",
                            metadata={"returned": True},
                        )

                    new_edges = create_bidirectional_edges(
                        source=var_id,
                        target=return_id,
                        edge_type="return",
                        file=file,
                        line=line,
                        expression=return_expr[:200] if return_expr else "",
                        function=function_name,
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)

        conn.close()

        stats["unique_variables"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "return_flow",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def build_parameter_binding_edges(self, root: str = ".") -> dict[str, Any]:
        """Build parameter binding edges connecting caller arguments to callee parameters."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_calls": 0,
            "calls_with_metadata": 0,
            "edges_created": 0,
            "skipped_literals": 0,
            "skipped_complex": 0,
        }

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
            item_show_func=lambda x: f"{x['callee_function']}" if x else None,
        ) as calls:
            for row in calls:
                stats["total_calls"] += 1

                caller_file = row["file"]
                caller_function = row["caller_function"]
                callee_function = row["callee_function"]
                callee_file = row["callee_file_path"]
                argument_expr = row["argument_expr"]
                param_name = row["param_name"]
                line = row["line"]

                arg_var = self._parse_argument_variable(argument_expr)
                if not arg_var:
                    stats["skipped_complex"] += 1
                    continue

                if arg_var.isdigit() or arg_var in ("True", "False", "None", "null", "undefined"):
                    stats["skipped_literals"] += 1
                    continue

                stats["calls_with_metadata"] += 1

                resolved_func_name = self._resolve_definition_name(
                    cursor, callee_file, callee_function
                )

                resolved_param_name = self._resolve_parameter_name(
                    cursor, callee_file, resolved_func_name, param_name
                )

                caller_scope = caller_function if caller_function else "global"
                source_id = f"{caller_file}::{caller_scope}::{arg_var}"

                target_id = f"{callee_file}::{resolved_func_name}::{resolved_param_name}"

                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=caller_file,
                        variable_name=arg_var,
                        scope=caller_scope,
                        type="variable",
                        metadata={"used_as_argument": True},
                    )

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=callee_file,
                        variable_name=resolved_param_name,
                        scope=resolved_func_name,
                        type="parameter",
                        metadata={
                            "is_parameter": True,
                            "original_call_site_name": callee_function,
                            "original_param_name": param_name,
                        },
                    )

                new_edges = create_bidirectional_edges(
                    source=source_id,
                    target=target_id,
                    edge_type="parameter_binding",
                    file=caller_file,
                    line=line,
                    expression=f"{callee_function}({argument_expr})",
                    function=caller_function,
                    metadata={
                        "callee": callee_function,
                        "resolved_callee": resolved_func_name,
                        "param_name": param_name,
                        "resolved_param": resolved_param_name,
                        "arg_expr": argument_expr,
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "parameter_binding",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def build_cross_boundary_edges(self, root: str = ".") -> dict[str, Any]:
        """Build edges connecting frontend API calls to backend controllers."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_matches": 0,
            "exact_matches": 0,
            "suffix_matches": 0,
            "edges_created": 0,
            "unique_nodes": 0,
            "skipped_no_body": 0,
            "skipped_no_handler": 0,
            "skipped_no_match": 0,
        }

        logger.info("Loading backend API endpoints...")
        cursor.execute("""
            SELECT file, method, full_path, handler_function
            FROM api_endpoints
            WHERE handler_function IS NOT NULL
              AND full_path IS NOT NULL
              AND method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        """)

        exact_lookup: dict[tuple[str, str], dict] = {}
        suffix_candidates: dict[str, list[dict]] = defaultdict(list)

        for row in cursor.fetchall():
            clean_path = row["full_path"].rstrip("/")
            route = {
                "path": clean_path,
                "file": row["file"],
                "handler_function": row["handler_function"],
                "full_path": row["full_path"],
            }

            exact_lookup[(row["method"], clean_path)] = route

            suffix_candidates[row["method"]].append(route)

        for method in suffix_candidates:
            suffix_candidates[method].sort(key=lambda r: len(r["path"]), reverse=True)

        logger.info("Loading frontend API calls...")
        cursor.execute("""
            SELECT file, line, method, url_literal, body_variable, function_name
            FROM frontend_api_calls
            WHERE body_variable IS NOT NULL
              AND url_literal IS NOT NULL
              AND method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')
        """)

        frontend_calls = cursor.fetchall()

        logger.info(f"Matching {len(frontend_calls)} frontend calls to backend endpoints...")

        with click.progressbar(
            frontend_calls,
            label="Building cross-boundary edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['url_literal']}" if x else None,
        ) as call_results:
            for call in call_results:
                frontend_url = call["url_literal"]
                method = call["method"]
                fe_file = call["file"]
                fe_line = call["line"]
                fe_body = call["body_variable"]
                fe_func = call["function_name"] if call["function_name"] else "global"

                if not fe_body:
                    stats["skipped_no_body"] += 1
                    continue

                clean_frontend_url = frontend_url.rstrip("/")

                backend_match = exact_lookup.get((method, clean_frontend_url))
                match_type = None

                if backend_match:
                    match_type = "exact"
                    stats["exact_matches"] += 1
                else:
                    candidates = suffix_candidates.get(method, [])
                    for route in candidates:
                        if len(route["path"]) > 1 and clean_frontend_url.endswith(route["path"]):
                            backend_match = route
                            match_type = "suffix"
                            stats["suffix_matches"] += 1
                            break

                if not backend_match:
                    stats["skipped_no_match"] += 1
                    continue

                stats["total_matches"] += 1

                be_file = backend_match["file"]
                handler_func = backend_match["handler_function"]
                full_path = backend_match["full_path"]

                if not handler_func:
                    stats["skipped_no_handler"] += 1
                    continue

                if handler_func.startswith("handler(") and handler_func.endswith(")"):
                    handler_func = handler_func[8:-1]

                if "." in handler_func:
                    controller_func = handler_func.split(".")[-1]
                else:
                    controller_func = handler_func

                cursor.execute(
                    """
                    SELECT DISTINCT path
                    FROM symbols
                    WHERE name = ? AND type = 'function'
                    ORDER BY
                        CASE WHEN path LIKE '%controller%' THEN 0 ELSE 1 END,
                        path
                    LIMIT 1
                """,
                    (controller_func,),
                )

                controller_result = cursor.fetchone()
                controller_file = controller_result["path"] if controller_result else be_file

                source_id = f"{fe_file}::{fe_func}::{fe_body}"
                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=fe_file,
                        variable_name=fe_body,
                        scope=fe_func,
                        type="variable",
                        metadata={"is_frontend_input": True},
                    )

                req_field = "req.body" if method in ("POST", "PUT", "PATCH") else "req.params"

                cursor.execute(
                    """
                    SELECT file, handler_function, handler_expr, execution_order,
                           route_method, route_path, route_line
                    FROM express_middleware_chains
                    WHERE file = ?
                      AND route_method = ?
                      AND handler_type IN ('middleware', 'controller')
                    ORDER BY execution_order
                    LIMIT 1
                """,
                    (be_file, method),
                )

                first_middleware = cursor.fetchone()

                if first_middleware:
                    # Use handler_function if available, otherwise construct clean name
                    # from route metadata (avoids using full arrow function body)
                    if first_middleware["handler_function"]:
                        middleware_func = first_middleware["handler_function"]
                    else:
                        route_method = first_middleware["route_method"] or "HANDLER"
                        route_path = first_middleware["route_path"] or ""
                        route_line = first_middleware["route_line"] or 0
                        middleware_func = f"{route_method}:{route_path}@{route_line}"
                    target_file = first_middleware["file"]
                    target_id = f"{target_file}::{middleware_func}::{req_field}"
                else:
                    target_id = f"{controller_file}::{controller_func}::{req_field}"
                    target_file = controller_file
                    middleware_func = controller_func

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=target_file,
                        variable_name=req_field,
                        scope=middleware_func,
                        type="parameter",
                        metadata={"is_api_source": True, "method": method},
                    )

                new_edges = create_bidirectional_edges(
                    source=source_id,
                    target=target_id,
                    edge_type="cross_boundary",
                    file=fe_file,
                    line=fe_line,
                    expression=f"{method} {frontend_url}",
                    function=fe_func,
                    metadata={
                        "frontend_file": fe_file,
                        "backend_file": target_file,
                        "api_method": method,
                        "api_route": full_path,
                        "body_variable": fe_body,
                        "request_field": req_field,
                        "match_type": match_type,
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "cross_boundary",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def build_parameter_mutation_edges(self, root: str = ".") -> dict[str, Any]:
        """Build edges for parameter field mutations (side effects).

        When a callee mutates param.field, create edges back to caller's arg.field.
        Example: infect(B) mutates objRef.data -> creates edge to B.data

        This closes the "Poisoned Reference" gap where object mutations through
        function parameters were not tracked back to the caller's scope.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_mutations": 0,
            "edges_created": 0,
            "skipped_no_callers": 0,
            "skipped_no_field": 0,
            "nodes_created": 0,
        }

        cursor.execute("""
            SELECT
                a.file, a.line, a.in_function, a.target_var, a.source_expr,
                fp.param_name, fp.param_index
            FROM assignments a
            JOIN func_params fp
                ON a.file = fp.file
                AND a.in_function = fp.function_name
            WHERE a.target_var LIKE fp.param_name || '.%'
        """)

        mutations = cursor.fetchall()
        stats["total_mutations"] = len(mutations)

        with click.progressbar(
            mutations,
            label="Building parameter mutation edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['in_function']}::{x['target_var']}" if x else None,
        ) as mutation_rows:
            for row in mutation_rows:
                callee_file = row["file"]
                callee_function = row["in_function"]
                target_var = row["target_var"]
                param_name = row["param_name"]
                param_index = row["param_index"]
                line = row["line"]

                if not target_var.startswith(param_name + "."):
                    stats["skipped_no_field"] += 1
                    continue
                field_path = target_var[len(param_name) :]

                # Query by argument_index (positional) since param_name in
                # function_call_args is often 'arg0', 'arg1' not actual names
                cursor.execute(
                    """
                    SELECT file, line, caller_function, argument_expr
                    FROM function_call_args
                    WHERE callee_file_path = ?
                      AND argument_index = ?
                      AND argument_expr IS NOT NULL
                """,
                    (callee_file, param_index),
                )

                callers = cursor.fetchall()
                if not callers:
                    stats["skipped_no_callers"] += 1
                    continue

                callee_node_id = f"{callee_file}::{callee_function}::{target_var}"
                if callee_node_id not in nodes:
                    nodes[callee_node_id] = DFGNode(
                        id=callee_node_id,
                        file=callee_file,
                        variable_name=target_var,
                        scope=callee_function,
                        type="mutated_param_field",
                        metadata={"is_mutation": True, "param_name": param_name},
                    )
                    stats["nodes_created"] += 1

                for caller in callers:
                    caller_file = caller["file"]
                    caller_function = caller["caller_function"] or "global"
                    arg_expr = caller["argument_expr"]

                    arg_var = self._parse_argument_variable(arg_expr)
                    if not arg_var:
                        continue

                    caller_field_var = f"{arg_var}{field_path}"
                    caller_node_id = f"{caller_file}::{caller_function}::{caller_field_var}"

                    if caller_node_id not in nodes:
                        nodes[caller_node_id] = DFGNode(
                            id=caller_node_id,
                            file=caller_file,
                            variable_name=caller_field_var,
                            scope=caller_function,
                            type="argument_field",
                            metadata={
                                "created_by": "parameter_mutation",
                                "base_var": arg_var,
                                "field_path": field_path,
                            },
                        )
                        stats["nodes_created"] += 1

                    new_edges = create_bidirectional_edges(
                        source=callee_node_id,
                        target=caller_node_id,
                        edge_type="parameter_mutation",
                        file=callee_file,
                        line=line,
                        expression=f"{param_name}{field_path} mutation -> {arg_var}{field_path}",
                        function=callee_function,
                        metadata={
                            "callee_function": callee_function,
                            "caller_function": caller_function,
                            "param_name": param_name,
                            "arg_expr": arg_expr,
                            "field_path": field_path,
                        },
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)

        conn.close()

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "data_flow",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def build_field_alias_edges(self, all_nodes: dict[str, dict]) -> dict[str, Any]:
        """Build field-level alias edges for simple variable copies.

        When B = A, and B.data exists, create edge B.data <-> A.data.
        Must run AFTER other builders to see created field nodes.

        Uses FIXPOINT ITERATION to handle transitive alias chains:
        - If a=b; b=c; c=d, we need multiple passes to connect a.field to d.field
        - Each pass creates new nodes that subsequent passes can discover
        - Converges when no new edges are created in a pass

        Uses INCREMENTAL INDEX UPDATES for O(1) performance:
        - Build nodes_by_prefix once from all_nodes
        - When creating new nodes, immediately append to index
        - Avoids O(N) full rebuild on each iteration
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "aliases_found": 0,
            "field_edges_created": 0,
            "nodes_created": 0,
            "iterations": 0,
            "converged": False,
        }

        # Build initial index from all_nodes (O(N) - done once)
        nodes_by_prefix: dict[str, list[str]] = defaultdict(list)
        for node_id in all_nodes:
            parts = node_id.split("::")
            if len(parts) >= 3:
                var_part = parts[2]
                if "." in var_part:
                    base_var = var_part.split(".")[0]
                    prefix_key = f"{parts[0]}::{parts[1]}::{base_var}"
                    nodes_by_prefix[prefix_key].append(node_id)

        cursor.execute("""
            SELECT file, line, in_function, target_var, source_expr
            FROM assignments
            WHERE source_expr GLOB '[A-Za-z_]*'
              AND target_var GLOB '[A-Za-z_]*'
              AND source_expr NOT LIKE '%.%'
              AND target_var NOT LIKE '%.%'
              AND source_expr NOT LIKE '{%'
              AND source_expr NOT LIKE '[%'
              AND source_expr NOT LIKE '"%'
              AND source_expr NOT LIKE '''%'
        """)

        aliases = cursor.fetchall()
        stats["aliases_found"] = len(aliases)

        # Track created edges to prevent duplicates across iterations
        edge_hashes: set[str] = set()

        # Fixpoint iteration: keep running until no new edges created
        max_iterations = 10  # Safety valve for circular aliases (a=b; b=a)

        for iteration in range(max_iterations):
            stats["iterations"] = iteration + 1
            edges_created_in_pass = 0

            for row in aliases:
                file = row["file"]
                func = row["in_function"] or "global"
                target = row["target_var"]
                source = row["source_expr"]
                line = row["line"]

                target_prefix = f"{file}::{func}::{target}"
                target_field_nodes = nodes_by_prefix.get(target_prefix, [])

                for target_node_id in target_field_nodes:
                    field_suffix = target_node_id[len(target_prefix) :]

                    source_field_var = f"{source}{field_suffix}"
                    source_node_id = f"{file}::{func}::{source_field_var}"

                    # Check edge hash to prevent duplicates
                    edge_hash = f"{target_node_id}->{source_node_id}"
                    if edge_hash in edge_hashes:
                        continue

                    # Create node if it doesn't exist
                    if source_node_id not in all_nodes and source_node_id not in nodes:
                        new_node = DFGNode(
                            id=source_node_id,
                            file=file,
                            variable_name=source_field_var,
                            scope=func,
                            type="aliased_field",
                            metadata={
                                "created_by": "field_alias",
                                "alias_of": target_node_id,
                                "iteration": iteration,
                            },
                        )
                        nodes[source_node_id] = new_node
                        stats["nodes_created"] += 1

                        # INCREMENTAL INDEX UPDATE: append new node immediately
                        # This allows subsequent aliases in THIS pass to find it
                        parts = source_node_id.split("::")
                        if len(parts) >= 3:
                            var_part = parts[2]
                            if "." in var_part:
                                base_var = var_part.split(".")[0]
                                prefix_key = f"{parts[0]}::{parts[1]}::{base_var}"
                                nodes_by_prefix[prefix_key].append(source_node_id)

                    # Create bidirectional edges
                    new_edges = create_bidirectional_edges(
                        source=target_node_id,
                        target=source_node_id,
                        edge_type="field_alias",
                        file=file,
                        line=line,
                        expression=f"{target} = {source} -> field alias",
                        function=func,
                        metadata={
                            "alias_target": target,
                            "alias_source": source,
                            "field_suffix": field_suffix,
                            "iteration": iteration,
                        },
                    )
                    edges.extend(new_edges)
                    edge_hashes.add(edge_hash)
                    edge_hashes.add(f"{source_node_id}->{target_node_id}")  # Reverse
                    edges_created_in_pass += len(new_edges)
                    stats["field_edges_created"] += len(new_edges)

            # Convergence check: if no new edges, we're done
            if edges_created_in_pass == 0:
                stats["converged"] = True
                logger.info(f"Alias resolution converged after {iteration + 1} iteration(s)")
                break

        if not stats["converged"]:
            logger.warning(
                f"Alias resolution hit max iterations ({max_iterations}). "
                f"Possible circular aliases or very deep chain."
            )

        conn.close()

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "graph_type": "data_flow",
                "stats": stats,
            },
        }

    def build_unified_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build unified data flow graph combining all edge types."""

        logger.info("Building assignment flow graph...")
        assignment_graph = self.build_assignment_flow_graph(root)

        logger.info("Building return flow graph...")
        return_graph = self.build_return_flow_graph(root)

        logger.info("Building parameter binding edges...")
        parameter_graph = self.build_parameter_binding_edges(root)

        logger.info("Building cross-boundary API edges...")
        cross_boundary_graph = self.build_cross_boundary_edges(root)

        logger.info("Building parameter mutation edges...")
        mutation_graph = self.build_parameter_mutation_edges(root)

        core_graphs = [
            assignment_graph,
            return_graph,
            parameter_graph,
            cross_boundary_graph,
            mutation_graph,
        ]

        strategy_graphs = []
        strategy_stats = {}

        for strategy in self.strategies:
            logger.info(f"Running strategy: {strategy.name}...")

            result = strategy.build(str(self.db_path), root)
            strategy_graphs.append(result)
            strategy_stats[strategy.name] = result.get("metadata", {}).get("stats", {})

        nodes = {}
        for graph in core_graphs + strategy_graphs:
            for node in graph.get("nodes", []):
                nodes[node["id"]] = node

        edges = []
        for graph in core_graphs + strategy_graphs:
            edges.extend(graph.get("edges", []))

        logger.info("Building field alias edges...")
        alias_graph = self.build_field_alias_edges(nodes)

        for node in alias_graph.get("nodes", []):
            nodes[node["id"]] = node
        edges.extend(alias_graph.get("edges", []))

        stats = {
            "assignment_stats": assignment_graph["metadata"]["stats"],
            "return_stats": return_graph["metadata"]["stats"],
            "parameter_stats": parameter_graph["metadata"]["stats"],
            "cross_boundary_stats": cross_boundary_graph["metadata"]["stats"],
            "mutation_stats": mutation_graph["metadata"]["stats"],
            "alias_stats": alias_graph["metadata"]["stats"],
            "strategy_stats": strategy_stats,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

        logger.info(f"\nUnified graph complete: {len(nodes)} nodes, {len(edges)} edges")

        result = {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "unified_data_flow",
                "stats": stats,
            },
        }

        return FidelityToken.attach_manifest(result)

    def get_data_dependencies(
        self, file: str, variable: str, function: str = None
    ) -> dict[str, Any]:
        """Get all variables that flow into the given variable."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        scope = function if function else "global"
        target_id = f"{file}::{scope}::{variable}"

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
            f = row["file"]
            sc = row["in_function"] if row["in_function"] else "global"
            target = f"{f}::{sc}::{row['target_var']}"
            source = f"{f}::{sc}::{row['source_var_name']}"

            graph[target].add(source)

        conn.close()

        dependencies = set()
        visited = set()
        queue = [target_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            sources = graph.get(current, set())
            for source in sources:
                if source not in visited:
                    dependencies.add(source)
                    queue.append(source)

        return {
            "target": target_id,
            "dependencies": list(dependencies),
            "dependency_count": len(dependencies),
        }

    def _resolve_definition_name(
        self, cursor: sqlite3.Cursor, file_path: str, call_site_name: str
    ) -> str:
        """Resolve call-site function name to definition name.

        GRAPH FIX G3: The call site might say 'service.doThing' (instance), but
        the definition is 'Service.doThing' (class). We strip the instance name
        and look for ANY function in the target file that ends with '.doThing'.

        This bridges the "Two Universes" problem where call-site and definition-site
        use different namespaces (camelCase instance vs PascalCase class).
        """

        if "." not in call_site_name:
            return call_site_name

        short_name = call_site_name.split(".")[-1]

        cursor.execute(
            """
            SELECT name FROM symbols
            WHERE path = ?
              AND type IN ('function', 'method')
              AND (name = ? OR name LIKE ?)
            LIMIT 1
        """,
            (file_path, short_name, f"%.{short_name}"),
        )

        result = cursor.fetchone()
        if result:
            return result["name"]

        return call_site_name

    def _resolve_parameter_name(
        self, cursor: sqlite3.Cursor, file_path: str, func_name: str, param_name: str
    ) -> str:
        """Resolve positional argument name (arg0) to actual parameter name.

        GRAPH FIX G4: Taint flows into 'arg0', but the function body uses 'userData'.
        We need to map position (0) to name ('userData') using the func_params table.

        This ensures the target node of call edges matches the source node of
        internal assignment edges, stitching the graph together.
        """

        if not param_name.startswith("arg") or not param_name[3:].isdigit():
            return param_name

        try:
            arg_index = int(param_name[3:])
        except ValueError:
            return param_name

        cursor.execute(
            """
            SELECT param_name FROM func_params
            WHERE file = ? AND function_name = ? AND param_index = ?
        """,
            (file_path, func_name, arg_index),
        )
        result = cursor.fetchone()

        if result:
            return result["param_name"]

        if "." in func_name:
            short_name = func_name.split(".")[-1]
            cursor.execute(
                """
                SELECT param_name FROM func_params
                WHERE file = ? AND function_name LIKE ? AND param_index = ?
            """,
                (file_path, f"%{short_name}", arg_index),
            )
            result = cursor.fetchone()
            if result:
                return result["param_name"]

        return param_name

    def _parse_argument_variable(self, arg_expr: str) -> str | None:
        """Parse an argument expression to extract the variable name.

        GRAPH FIX G1: Removed naive split(" ")[0] which lost data for expressions
        like `await getID()` (returned "await") or `new User()` (returned "new").
        Now handles keyword prefixes properly before falling back to complex_expression.
        """
        if not arg_expr:
            return None

        expr = arg_expr.strip()

        if expr.startswith("async") or "=>" in expr:
            return "function_expression"

        if expr.startswith("{") and expr.endswith("}"):
            return "object_literal"

        if expr.startswith("[") and expr.endswith("]"):
            return "array_literal"

        keyword_prefixes = ("await ", "new ", "typeof ", "void ", "delete ", "yield ", "yield* ")
        for prefix in keyword_prefixes:
            if expr.startswith(prefix):
                remainder = expr[len(prefix) :].strip()
                if remainder:
                    result = self._parse_argument_variable(remainder)
                    if result:
                        return result

                return None

        if "(" in expr and expr.endswith(")"):
            start = expr.find("(") + 1
            end = expr.rfind(")")
            inner = expr[start:end].strip()

            if inner and all(c.isalnum() or c in "._$?" for c in inner):
                return inner

            return None

        if expr and expr[0] in "\"'`":
            return "string_literal"

        if expr.endswith("!"):
            return expr[:-1]

        if " " in expr:
            return None

        return expr
