"""Interceptor Graph Strategy."""

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from theauditor.graph.types import DFGEdge, DFGNode, create_bidirectional_edges
from theauditor.indexer.fidelity_utils import FidelityToken

from .resolution import path_matches


class InterceptorStrategy:
    """Graph strategy to wire up interceptors (Middleware, Decorators)."""

    name = "interceptors"

    def build(self, db_path: str, root: str) -> dict[str, Any]:
        """Build interceptor edges from middleware chains and decorators."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "express_chains_processed": 0,
            "express_edges_created": 0,
            "controller_bridges_created": 0,
            "python_decorators_processed": 0,
            "python_decorator_edges_created": 0,
            "django_middleware_edges_created": 0,
        }

        self._build_express_middleware_edges(cursor, nodes, edges, stats)

        self._build_python_decorator_edges(cursor, nodes, edges, stats)

        self._build_django_middleware_edges(cursor, nodes, edges, stats)

        conn.close()

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "graph_type": "interceptors",
                "stats": stats,
            },
        }
        return FidelityToken.attach_manifest(result)

    def _build_express_middleware_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from Express middleware chains."""

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='express_middleware_chains'"
        )
        if not cursor.fetchone():
            return

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
            SELECT
                file,
                route_path,
                route_method,
                handler_expr,
                handler_type,
                execution_order
            FROM express_middleware_chains
            ORDER BY route_path, route_method, execution_order
        """)

        routes: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in cursor.fetchall():
            key = f"{row['route_method']} {row['route_path']}"
            routes[key].append(row)

        for route_key, chain in routes.items():
            if not chain:
                continue

            stats["express_chains_processed"] += 1

            first_item = chain[0]
            route_file = first_item["file"]

            route_scope = f"route:{route_key.replace(' ', '_').replace('/', '_')}"
            entry_node_id = f"{route_file}::{route_scope}::request"

            if entry_node_id not in nodes:
                nodes[entry_node_id] = DFGNode(
                    id=entry_node_id,
                    file=route_file,
                    variable_name="request",
                    scope=route_scope,
                    type="route_entry",
                    metadata={"route": route_key, "is_entry": True},
                )

            prev_node_id = entry_node_id

            for item in chain:
                raw_expr = item["handler_expr"] or "unknown"
                clean_func = raw_expr.split("(")[0].strip()

                object_name = None
                method_name = clean_func
                if "." in clean_func:
                    parts = clean_func.split(".", 1)
                    object_name = parts[0]
                    method_name = parts[1] if len(parts) > 1 else clean_func

                controller_file = None
                if item["handler_type"] == "controller":
                    full_func_name, controller_file = self._resolve_controller_info(
                        route_file=item["file"],
                        object_name=object_name,
                        method_name=method_name,
                        import_styles_map=import_styles_map,
                        symbols_by_name=symbols_by_name,
                    )
                else:
                    full_func_name = method_name

                current_node_id = f"{item['file']}::{full_func_name}::input"

                if current_node_id not in nodes:
                    nodes[current_node_id] = DFGNode(
                        id=current_node_id,
                        file=item["file"],
                        variable_name="input",
                        scope=full_func_name,
                        type="interceptor",
                        metadata={
                            "raw_expr": raw_expr,
                            "handler_type": item["handler_type"],
                            "execution_order": item["execution_order"],
                        },
                    )

                new_edges = create_bidirectional_edges(
                    source=prev_node_id,
                    target=current_node_id,
                    edge_type="interceptor_flow",
                    file=item["file"],
                    line=0,
                    expression=f"Chain: {route_key}",
                    function="middleware_chain",
                    metadata={"order": item["execution_order"]},
                )
                edges.extend(new_edges)
                stats["express_edges_created"] += len(new_edges)

                if item["handler_type"] == "controller" and controller_file:
                    request_aliases = ["req", "request", "ctx", "context"]

                    properties = ["", ".body", ".query", ".params", ".headers"]

                    for alias in request_aliases:
                        for prop in properties:
                            full_alias = f"{alias}{prop}"

                            alias_node_id = f"{controller_file}::{full_func_name}::{full_alias}"

                            if alias_node_id not in nodes:
                                nodes[alias_node_id] = DFGNode(
                                    id=alias_node_id,
                                    file=controller_file,
                                    variable_name=full_alias,
                                    scope=full_func_name,
                                    type="request_alias",
                                    metadata={
                                        "alias": full_alias,
                                        "source_handler": current_node_id,
                                    },
                                )

                            bridge_edges = create_bidirectional_edges(
                                source=current_node_id,
                                target=alias_node_id,
                                edge_type="parameter_alias",
                                file=controller_file,
                                line=0,
                                expression=f"Controller Binding: {full_alias} = input",
                                function=full_func_name,
                                metadata={
                                    "alias": full_alias,
                                    "handler_type": "controller",
                                    "routes_file": item["file"],
                                    "controller_file": controller_file,
                                },
                            )
                            edges.extend(bridge_edges)
                            stats["controller_bridges_created"] += len(bridge_edges)

                prev_node_id = current_node_id

    def _build_python_decorator_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from Python decorators."""

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='python_decorators'"
        )
        if not cursor.fetchone():
            return

        cursor.execute("""
            SELECT
                file,
                line,
                decorator_name,
                target_name,
                target_type
            FROM python_decorators
            WHERE target_name IS NOT NULL
              AND decorator_name IS NOT NULL
        """)

        for row in cursor.fetchall():
            file = row["file"]
            dec_name = row["decorator_name"]
            func_name = row["target_name"]
            line = row["line"]

            stats["python_decorators_processed"] += 1

            dec_node_id = f"{file}::{dec_name}::wrapper"

            if dec_node_id not in nodes:
                nodes[dec_node_id] = DFGNode(
                    id=dec_node_id,
                    file=file,
                    variable_name="wrapper",
                    scope=dec_name,
                    type="decorator",
                    metadata={"decorator_name": dec_name},
                )

            func_node_id = f"{file}::{func_name}::args"

            if func_node_id not in nodes:
                nodes[func_node_id] = DFGNode(
                    id=func_node_id,
                    file=file,
                    variable_name="args",
                    scope=func_name,
                    type="function_entry",
                    metadata={"decorated_by": dec_name},
                )

            new_edges = create_bidirectional_edges(
                source=dec_node_id,
                target=func_node_id,
                edge_type="decorator_wrap",
                file=file,
                line=line,
                expression=f"@{dec_name}",
                function=func_name,
                metadata={"decorator": dec_name},
            )
            edges.extend(new_edges)
            stats["python_decorator_edges_created"] += len(new_edges)

    def _build_django_middleware_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from Django global middleware to views.

        GRAPH FIX G12: Replaced Hub pattern with Sequential Chaining.
        The Hub pattern (G8) caused taint explosion - if ONE middleware was tainted,
        ALL views became tainted via the hub. Sequential chaining preserves:
        - Correct taint flow: MW1 -> MW2 -> MW3 -> Views
        - Edge efficiency: M + V edges (same as hub)
        - Precision: Only downstream components are tainted
        """

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='python_django_middleware'"
        )
        has_middleware = cursor.fetchone()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='python_django_views'"
        )
        has_views = cursor.fetchone()

        if not (has_middleware and has_views):
            return

        cursor.execute("""
            SELECT file, middleware_class_name
            FROM python_django_middleware
            WHERE has_process_request = 1
            ORDER BY file, middleware_class_name
        """)
        middlewares = cursor.fetchall()

        if not middlewares:
            return

        cursor.execute("""
            SELECT file, view_class_name
            FROM python_django_views
        """)
        views = cursor.fetchall()

        if not views:
            return

        entry_node_id = "Django::Request::Entry"
        if entry_node_id not in nodes:
            nodes[entry_node_id] = DFGNode(
                id=entry_node_id,
                file="django.http",
                variable_name="request",
                scope="HttpRequest",
                type="request_entry",
                metadata={"is_entry": True, "framework": "django"},
            )

        previous_node_id = entry_node_id

        for mw in middlewares:
            mw_file = mw["file"]
            mw_class = mw["middleware_class_name"]
            mw_node_id = f"{mw_file}::{mw_class}::request"

            if mw_node_id not in nodes:
                nodes[mw_node_id] = DFGNode(
                    id=mw_node_id,
                    file=mw_file,
                    variable_name="request",
                    scope=mw_class,
                    type="middleware",
                    metadata={"middleware_class": mw_class},
                )

            new_edges = create_bidirectional_edges(
                source=previous_node_id,
                target=mw_node_id,
                edge_type="django_middleware_chain",
                file=mw_file,
                line=0,
                expression=f"settings.MIDDLEWARE: {mw_class}",
                function="process_request",
                metadata={"middleware": mw_class},
            )
            edges.extend(new_edges)
            stats["django_middleware_edges_created"] += len(new_edges)

            previous_node_id = mw_node_id

        last_middleware_node = previous_node_id

        for view in views:
            view_file = view["file"]
            view_name = view["view_class_name"]
            view_node_id = f"{view_file}::{view_name}::request"

            if view_node_id not in nodes:
                nodes[view_node_id] = DFGNode(
                    id=view_node_id,
                    file=view_file,
                    variable_name="request",
                    scope=view_name,
                    type="view_entry",
                    metadata={"view_name": view_name},
                )

            new_edges = create_bidirectional_edges(
                source=last_middleware_node,
                target=view_node_id,
                edge_type="django_router_to_view",
                file=view_file,
                line=0,
                expression=f"urlpatterns -> {view_name}",
                function=view_name,
                metadata={"view": view_name},
            )
            edges.extend(new_edges)
            stats["django_middleware_edges_created"] += len(new_edges)

    def _path_matches(self, import_package: str, symbol_path: str) -> bool:
        """Check if import package matches symbol path.

        GRAPH FIX G13: Delegated to shared resolution module to eliminate duplication.
        See resolution.py for full implementation and GRAPH FIX G11 details.
        """
        return path_matches(import_package, symbol_path)

    def _resolve_controller_info(
        self,
        route_file: str,
        object_name: str | None,
        method_name: str,
        import_styles_map: dict[str, dict[str, str]],
        symbols_by_name: dict[str, list[dict]],
    ) -> tuple[str, str | None]:
        """Look up full ClassName.methodName and controller file path from symbols.

        GRAPH FIX G2: Replaced fuzzy LIKE %.methodName with exact import-based resolution.
        The old approach matched BOTH UserController.updateUser AND AdminController.updateUser
        creating false edges. Now we:
        1. Look up where the object was imported from
        2. Find the method in THAT specific file only
        """

        if not object_name:
            if method_name in symbols_by_name:
                candidates = symbols_by_name[method_name]

                for sym in candidates:
                    if "controller" in sym["path"].lower():
                        return (sym["name"], sym["path"])
                if candidates:
                    return (candidates[0]["name"], candidates[0]["path"])
            return (method_name, None)

        file_imports = import_styles_map.get(route_file, {})
        import_package = file_imports.get(object_name)

        if not import_package:
            if method_name in symbols_by_name:
                candidates = symbols_by_name[method_name]
                for sym in candidates:
                    if "controller" in sym["path"].lower():
                        return (sym["name"], sym["path"])

            return (method_name, None)

        full_method_name = f"{object_name}.{method_name}"

        if full_method_name in symbols_by_name:
            candidates = symbols_by_name[full_method_name]

            for sym in candidates:
                if self._path_matches(import_package, sym["path"]):
                    return (sym["name"], sym["path"])

        if method_name in symbols_by_name:
            candidates = symbols_by_name[method_name]

            for sym in candidates:
                if self._path_matches(import_package, sym["path"]):
                    return (f"{object_name}.{method_name}", sym["path"])

            for sym in candidates:
                if "controller" in sym["path"].lower():
                    return (sym["name"], sym["path"])

        method_suffix = f".{method_name}"
        for sym_name, syms in symbols_by_name.items():
            if sym_name.endswith(method_suffix):
                for sym in syms:
                    if self._path_matches(import_package, sym["path"]):
                        return (sym["name"], sym["path"])

        return (method_name, None)
