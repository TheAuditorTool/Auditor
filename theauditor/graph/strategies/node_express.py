"""Node Express Strategy - Handles Express middleware chains and controller resolution.

This strategy builds edges for:
1. Express middleware chains (validateBody -> authenticate -> controller)
2. Controller implementation resolution (route handler -> actual controller method)

Extracted from dfg_builder.py as part of Phase 3: Strategy Pattern refactoring.
"""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any
from collections import defaultdict

import click

from .base import GraphStrategy
from ..types import DFGNode, DFGEdge, create_bidirectional_edges


class NodeExpressStrategy(GraphStrategy):
    """Strategy for building Node.js Express middleware and controller edges.

    Handles:
    - Middleware chain edges (req flows through middleware sequence)
    - Controller implementation edges (route handler -> controller method)

    Creates edges showing data flow through Express request handling pipeline.
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Express middleware and controllers.

        Combines results from:
        - _build_middleware_edges()
        - _build_controller_edges()

        Args:
            db_path: Path to repo_index.db
            project_root: Project root for metadata

        Returns:
            Dict with merged nodes, edges, metadata
        """

        middleware_result = self._build_middleware_edges(db_path, project_root)
        controller_result = self._build_controller_edges(db_path, project_root)

        merged_nodes = {}
        for node in middleware_result["nodes"]:
            merged_nodes[node["id"]] = node
        for node in controller_result["nodes"]:
            merged_nodes[node["id"]] = node

        merged_edges = middleware_result["edges"] + controller_result["edges"]

        merged_stats = {
            "middleware": middleware_result["metadata"].get("stats", {}),
            "controller": controller_result["metadata"].get("stats", {}),
            "total_nodes": len(merged_nodes),
            "total_edges": len(merged_edges),
        }

        return {
            "nodes": list(merged_nodes.values()),
            "edges": merged_edges,
            "metadata": {"graph_type": "node_express", "stats": merged_stats},
        }

    def _build_middleware_edges(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges connecting Express middleware chains.

        Creates edges showing data flow through middleware execution order.
        For a route with validateBody -> authenticate -> controller,
        creates edges showing req.body flows through the chain.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_routes": 0,
            "total_middleware": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT file, route_path, route_method, execution_order,
                   handler_expr, handler_type, handler_function
            FROM express_middleware_chains
            WHERE handler_type IN ('middleware', 'controller')
            ORDER BY file, route_path, route_method, execution_order
        """)

        routes: dict[str, list] = defaultdict(list)
        for row in cursor.fetchall():
            key = f"{row['route_method']} {row['route_path']}"
            routes[key].append(row)
            stats["total_middleware"] += 1

        stats["total_routes"] = len(routes)

        with click.progressbar(
            routes.items(),
            label="Building middleware chain edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: x[0] if x else None,
        ) as route_items:
            for route_key, handlers in route_items:
                if len(handlers) < 2:
                    continue

                for i in range(len(handlers) - 1):
                    curr_handler = handlers[i]
                    next_handler = handlers[i + 1]

                    if curr_handler["handler_type"] == "controller":
                        continue

                    curr_func = curr_handler["handler_function"] or curr_handler["handler_expr"]
                    next_func = next_handler["handler_function"] or next_handler["handler_expr"]

                    if not curr_func or not next_func:
                        continue

                    for req_field in ["req", "req.body", "req.params", "req.query"]:
                        source_id = f"{curr_handler['file']}::{curr_func}::{req_field}"
                        if source_id not in nodes:
                            nodes[source_id] = DFGNode(
                                id=source_id,
                                file=curr_handler["file"],
                                variable_name=req_field,
                                scope=curr_func,
                                type="variable",
                                metadata={"is_middleware": True},
                            )

                        target_id = f"{next_handler['file']}::{next_func}::{req_field}"
                        if target_id not in nodes:
                            nodes[target_id] = DFGNode(
                                id=target_id,
                                file=next_handler["file"],
                                variable_name=req_field,
                                scope=next_func,
                                type="parameter",
                                metadata={"is_middleware": True},
                            )

                        new_edges = create_bidirectional_edges(
                            source=source_id,
                            target=target_id,
                            edge_type="express_middleware_chain",
                            file=curr_handler["file"],
                            line=0,
                            expression=f"{curr_func} -> {next_func}",
                            function=curr_func,
                            metadata={
                                "route": route_key,
                                "execution_order": curr_handler["execution_order"],
                                "next_order": next_handler["execution_order"],
                            },
                        )
                        edges.extend(new_edges)
                        stats["edges_created"] += len(new_edges)

        conn.close()
        stats["unique_nodes"] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "express_middleware",
                "stats": stats,
            },
        }

    def _build_controller_edges(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges connecting route handlers to controller implementations.

        Bridges the gap between Express route handlers and their actual
        controller method implementations.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "handlers_processed": 0,
            "controllers_resolved": 0,
            "edges_created": 0,
            "failed_resolutions": 0,
        }

        print("[NodeExpressStrategy] Pre-loading import_styles and symbols...")

        import_styles_map: dict[str, dict[str, str]] = defaultdict(dict)
        cursor.execute("SELECT file, package, alias_name FROM import_styles")
        for row in cursor.fetchall():
            import_styles_map[row["file"]][row["alias_name"]] = row["package"]

        symbols_by_name: dict[str, list[dict]] = defaultdict(list)
        cursor.execute("""
            SELECT path, name, type
            FROM symbols
            WHERE type IN ('function', 'class')
        """)
        for row in cursor.fetchall():
            symbols_by_name[row["name"]].append(
                {
                    "path": row["path"],
                    "name": row["name"],
                    "type": row["type"],
                }
            )

        cursor.execute("""
            SELECT DISTINCT file, route_path, route_method, handler_expr
            FROM express_middleware_chains
            WHERE handler_type = 'controller' AND handler_expr IS NOT NULL
        """)

        handlers = cursor.fetchall()
        stats["handlers_processed"] = len(handlers)

        for handler in handlers:
            route_file = handler["file"]
            handler_expr = handler["handler_expr"]

            object_name = None
            method_name = None

            if "(" in handler_expr and ")" in handler_expr:
                start = handler_expr.index("(") + 1
                end = handler_expr.rindex(")")
                inner = handler_expr[start:end]
                if "." in inner:
                    object_name, method_name = inner.split(".", 1)
            elif "." in handler_expr:
                object_name, method_name = handler_expr.split(".", 1)
            else:
                continue

            if not object_name or not method_name:
                continue

            import_package = import_styles_map.get(route_file, {}).get(object_name)
            if not import_package:
                stats["failed_resolutions"] += 1
                continue

            symbol_result = None
            if method_name in symbols_by_name:
                candidates = symbols_by_name[method_name]
                for sym in candidates:
                    if "controller" in sym["path"].lower():
                        symbol_result = sym
                        break
                if not symbol_result and candidates:
                    symbol_result = candidates[0]

            if not symbol_result:
                full_name = f"{object_name}.{method_name}"
                if full_name in symbols_by_name:
                    candidates = symbols_by_name[full_name]
                    if candidates:
                        symbol_result = candidates[0]

            if not symbol_result:
                stats["failed_resolutions"] += 1
                continue

            resolved_path = symbol_result["path"]
            symbol_name = symbol_result["name"]

            if symbol_name == method_name:
                full_method_name = method_name
            elif "." in symbol_name:
                full_method_name = f"{symbol_name}.{method_name}"
            else:
                full_method_name = f"{symbol_name}.{method_name}"

            method_exists = False
            if full_method_name in symbols_by_name:
                for sym in symbols_by_name[full_method_name]:
                    if sym["path"] == resolved_path and sym["type"] == "function":
                        method_exists = True
                        break

            if not method_exists:
                if symbol_name == method_name:
                    method_exists = True
                else:
                    stats["failed_resolutions"] += 1
                    continue

            stats["controllers_resolved"] += 1

            for suffix in ["req", "req.body", "req.params", "req.query", "res"]:
                source_id = f"{route_file}::{handler_expr}::{suffix}"
                if source_id not in nodes:
                    nodes[source_id] = DFGNode(
                        id=source_id,
                        file=route_file,
                        variable_name=suffix,
                        scope=handler_expr,
                        type="parameter",
                        metadata={"handler": True},
                    )

                target_id = f"{resolved_path}::{full_method_name}::{suffix}"
                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=resolved_path,
                        variable_name=suffix,
                        scope=full_method_name,
                        type="parameter",
                        metadata={"controller": True},
                    )

                new_edges = create_bidirectional_edges(
                    source=source_id,
                    target=target_id,
                    edge_type="controller_implementation",
                    file=route_file,
                    line=0,
                    expression=f"{handler_expr} -> {full_method_name}",
                    function=handler_expr,
                    metadata={
                        "route_path": handler["route_path"],
                        "route_method": handler["route_method"],
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)

        conn.close()

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "type": "controller_implementation_flow",
                "root": project_root,
                "stats": stats,
            },
        }
