"""Go HTTP Strategy - Handles Go HTTP framework middleware chains and route resolution."""

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from theauditor.indexer.fidelity_utils import FidelityToken

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class GoHttpStrategy(GraphStrategy):
    """Strategy for building Go HTTP middleware and route handler edges.

    Supports: Gin, Echo, Fiber, Chi, net/http
    """

    name = "go_http"
    priority = 50

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go HTTP routes and middleware."""

        middleware_result = self._build_middleware_edges(db_path, project_root)
        route_result = self._build_route_handler_edges(db_path, project_root)

        merged_nodes = {}
        for node in middleware_result["nodes"]:
            merged_nodes[node["id"]] = node
        for node in route_result["nodes"]:
            merged_nodes[node["id"]] = node

        merged_edges = middleware_result["edges"] + route_result["edges"]

        merged_stats = {
            "middleware": middleware_result["metadata"].get("stats", {}),
            "routes": route_result["metadata"].get("stats", {}),
            "total_nodes": len(merged_nodes),
            "total_edges": len(merged_edges),
        }

        result = {
            "nodes": list(merged_nodes.values()),
            "edges": merged_edges,
            "metadata": {"graph_type": "go_http", "stats": merged_stats},
        }
        return FidelityToken.attach_manifest(result)

    def _build_middleware_edges(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges connecting Go middleware chains."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_middleware": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT file AS file_path, line, framework, router_var, middleware_func, is_global
            FROM go_middleware
            ORDER BY file, line
        """)

        router_middleware: dict[str, list] = defaultdict(list)
        for row in cursor.fetchall():
            key = f"{row['file_path']}::{row['router_var']}"
            router_middleware[key].append(row)
            stats["total_middleware"] += 1

        for _router_key, middlewares in router_middleware.items():
            if len(middlewares) < 2:
                continue

            sorted_mw = sorted(middlewares, key=lambda m: m["line"])

            for i in range(len(sorted_mw) - 1):
                curr_mw = sorted_mw[i]
                next_mw = sorted_mw[i + 1]

                curr_func = curr_mw["middleware_func"]
                next_func = next_mw["middleware_func"]
                file_path = curr_mw["file_path"]

                for ctx_field in ["ctx", "c", "c.Request", "c.Writer"]:
                    source_id = f"{file_path}::{curr_func}::{ctx_field}"
                    if source_id not in nodes:
                        nodes[source_id] = DFGNode(
                            id=source_id,
                            file=file_path,
                            variable_name=ctx_field,
                            scope=curr_func,
                            type="variable",
                            metadata={
                                "is_middleware": True,
                                "framework": curr_mw["framework"],
                            },
                        )

                    target_id = f"{file_path}::{next_func}::{ctx_field}"
                    if target_id not in nodes:
                        nodes[target_id] = DFGNode(
                            id=target_id,
                            file=file_path,
                            variable_name=ctx_field,
                            scope=next_func,
                            type="parameter",
                            metadata={
                                "is_middleware": True,
                                "framework": next_mw["framework"],
                            },
                        )

                    new_edges = create_bidirectional_edges(
                        source=source_id,
                        target=target_id,
                        edge_type="go_middleware_chain",
                        file=file_path,
                        line=curr_mw["line"],
                        expression=f"{curr_func} -> {next_func}",
                        function=curr_func,
                        metadata={
                            "framework": curr_mw["framework"],
                            "router_var": curr_mw["router_var"],
                            "is_global": curr_mw["is_global"],
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
                "graph_type": "go_middleware",
                "stats": stats,
            },
        }

    def _build_route_handler_edges(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges connecting routes to handler functions."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_routes": 0,
            "handlers_resolved": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT file AS file_path, line, framework, method, path, handler_func
            FROM go_routes
            WHERE handler_func IS NOT NULL
            ORDER BY file, line
        """)

        routes = cursor.fetchall()
        stats["total_routes"] = len(routes)

        if not routes:
            conn.close()
            return {
                "nodes": [],
                "edges": [],
                "metadata": {"graph_type": "go_routes", "stats": stats},
            }

        cursor.execute("""
            SELECT file AS file_path, line, name, signature
            FROM go_functions
        """)

        func_lookup: dict[str, dict] = {}
        for row in cursor.fetchall():
            func_lookup[row["name"]] = {
                "file_path": row["file_path"],
                "line": row["line"],
                "name": row["name"],
                "signature": row["signature"],
            }

        with click.progressbar(
            routes,
            label="Building Go route handler edges",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['method']} {x['path']}" if x else None,
        ) as route_items:
            for route in route_items:
                handler_func = route["handler_func"]
                route_file = route["file_path"]
                method = route["method"]
                path = route["path"]
                framework = route["framework"]

                resolved = func_lookup.get(handler_func)
                handler_file = resolved["file_path"] if resolved else route_file

                stats["handlers_resolved"] += 1

                ctx_params = self._get_framework_context_params(framework)

                for ctx_param in ctx_params:
                    source_id = f"{route_file}::route::{method}_{path}::{ctx_param}"
                    if source_id not in nodes:
                        nodes[source_id] = DFGNode(
                            id=source_id,
                            file=route_file,
                            variable_name=ctx_param,
                            scope=f"route:{method}_{path}",
                            type="parameter",
                            metadata={
                                "is_route_entry": True,
                                "method": method,
                                "path": path,
                                "framework": framework,
                            },
                        )

                    target_id = f"{handler_file}::{handler_func}::{ctx_param}"
                    if target_id not in nodes:
                        nodes[target_id] = DFGNode(
                            id=target_id,
                            file=handler_file,
                            variable_name=ctx_param,
                            scope=handler_func,
                            type="parameter",
                            metadata={
                                "is_handler_param": True,
                                "framework": framework,
                            },
                        )

                    new_edges = create_bidirectional_edges(
                        source=source_id,
                        target=target_id,
                        edge_type="go_route_handler",
                        file=route_file,
                        line=route["line"],
                        expression=f"{method} {path} -> {handler_func}",
                        function=f"route:{method}_{path}",
                        metadata={
                            "http_method": method,
                            "route_path": path,
                            "handler": handler_func,
                            "framework": framework,
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
                "graph_type": "go_routes",
                "stats": stats,
            },
        }

    def _get_framework_context_params(self, framework: str) -> list[str]:
        """Get context parameter names for each Go HTTP framework."""
        params = {
            "gin": ["c", "c.Request", "c.Params", "c.Query", "c.PostForm"],
            "echo": ["c", "c.Request()", "c.Param", "c.QueryParam", "c.FormValue"],
            "fiber": ["c", "c.Params", "c.Query", "c.Body"],
            "chi": ["r", "r.URL", "r.Body", "w"],
            "net_http": ["r", "r.URL", "r.Body", "r.Form", "w"],
        }
        return params.get(framework, ["r", "w"])
