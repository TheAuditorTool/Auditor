"""Node Express Strategy - Handles Express middleware chains and controller resolution."""

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class NodeExpressStrategy(GraphStrategy):
    """Strategy for building Node.js Express middleware and controller edges."""

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Express middleware and controllers."""

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
        """Build edges connecting Express middleware chains."""
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
        """Build edges connecting route handlers to controller implementations."""
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

            # GRAPH FIX G5: Handle method chaining (e.g., services.users.update)
            # For chained methods, try multiple resolution strategies:
            # 1. Full method name (users.update)
            # 2. Last segment only (update) filtered by import path
            # 3. Full chain as symbol name (services.users.update)
            symbol_result = None

            # Strategy 1: Try method_name as-is (handles Class.method patterns)
            if method_name in symbols_by_name:
                candidates = symbols_by_name[method_name]
                # Prefer candidates matching the import path
                for sym in candidates:
                    if import_package and import_package in sym["path"]:
                        symbol_result = sym
                        break
                if not symbol_result:
                    for sym in candidates:
                        if "controller" in sym["path"].lower():
                            symbol_result = sym
                            break
                if not symbol_result and candidates:
                    symbol_result = candidates[0]

            # Strategy 2: For chained methods (users.update), try just the last segment
            if not symbol_result and "." in method_name:
                final_method = method_name.rsplit(".", 1)[-1]
                if final_method in symbols_by_name:
                    candidates = symbols_by_name[final_method]
                    # MUST filter by import path to avoid false matches
                    for sym in candidates:
                        if import_package and import_package in sym["path"]:
                            symbol_result = sym
                            break
                    # Also try partial path matches (services/users -> update)
                    if not symbol_result:
                        chain_parts = method_name.split(".")
                        for sym in candidates:
                            # Check if path contains the chain segments
                            path_lower = sym["path"].lower()
                            if all(part.lower() in path_lower for part in chain_parts[:-1]):
                                symbol_result = sym
                                break

            # Strategy 3: Try full qualified name
            if not symbol_result:
                full_name = f"{object_name}.{method_name}"
                if full_name in symbols_by_name:
                    candidates = symbols_by_name[full_name]
                    if candidates:
                        symbol_result = candidates[0]

            if not symbol_result:
                # PHASE 1 FIX: Create ghost node instead of silently dropping.
                # Graph should show unresolved references so analysis can flag them.
                stats["failed_resolutions"] += 1

                # Create ghost node for unresolved controller
                ghost_id = f"UNRESOLVED::{object_name}.{method_name}"
                if ghost_id not in nodes:
                    nodes[ghost_id] = DFGNode(
                        id=ghost_id,
                        file="UNRESOLVED",
                        variable_name=f"{object_name}.{method_name}",
                        scope="UNRESOLVED",
                        type="ghost",
                        metadata={
                            "reason": "symbol_resolution_failed",
                            "import_package": import_package,
                            "route_file": route_file,
                        },
                    )

                # Still create edges to the ghost node
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

                    target_id = f"{ghost_id}::{suffix}"
                    if target_id not in nodes:
                        nodes[target_id] = DFGNode(
                            id=target_id,
                            file="UNRESOLVED",
                            variable_name=suffix,
                            scope=f"{object_name}.{method_name}",
                            type="ghost_parameter",
                            metadata={"ghost": True},
                        )

                    new_edges = create_bidirectional_edges(
                        source=source_id,
                        target=target_id,
                        edge_type="controller_unresolved",
                        file=route_file,
                        line=0,
                        expression=f"{handler_expr} -> UNRESOLVED:{object_name}.{method_name}",
                        function=handler_expr,
                        metadata={
                            "route_path": handler["route_path"],
                            "route_method": handler["route_method"],
                            "ghost": True,
                        },
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)

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
