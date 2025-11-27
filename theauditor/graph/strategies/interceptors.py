"""Interceptor Graph Strategy.

Wires "Pre-Flight" logic (Middleware, Decorators) into the Data Flow Graph.
This creates structural edges between Route Entries and Handlers, passing through
validation/auth layers that were previously invisible to the graph walker.

Architecture:
- Express Middleware Chains: Route -> Middleware 1 -> Middleware 2 -> Controller
- Python Decorators: Decorator -> Function (decorator wraps the function)

This eliminates the need for Taint Analysis to 'guess' if validation happened.
It makes validation structurally present in the Data Flow Graph.

NO FALLBACKS. Database-first. If tables don't exist, we skip gracefully
(strategies are pluggable, not every project has Express or Python).
"""

import sqlite3
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from theauditor.graph.types import DFGEdge, DFGNode, create_bidirectional_edges


class InterceptorStrategy:
    """Graph strategy to wire up interceptors (Middleware, Decorators).

    Connects:
    1. Express Middleware Chains (Route -> Middleware -> Controller)
    2. Python Decorators (Decorator -> Function)

    This enables Taint Analysis to naturally walk through validation layers
    and mark flows as SANITIZED when they pass through validators.
    """

    name = "interceptors"

    def build(self, db_path: str, root: str) -> dict[str, Any]:
        """Build interceptor edges from middleware chains and decorators.

        Args:
            db_path: Path to repo_index.db
            root: Project root directory

        Returns:
            Dict with nodes, edges, and metadata (same format as other strategies)
        """
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

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "graph_type": "interceptors",
                "stats": stats,
            },
        }

    def _build_express_middleware_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from Express middleware chains.

        Logic:
        1. Group middleware by route (method + path)
        2. Sort by execution_order
        3. Create chain: Route Entry -> MW1 -> MW2 -> Controller

        Node IDs follow dfg_builder pattern: file::scope::variable
        """

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='express_middleware_chains'"
        )
        if not cursor.fetchone():
            return

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
                if "." in clean_func:
                    clean_func = clean_func.split(".")[-1]

                controller_file = None
                if item["handler_type"] == "controller":
                    full_func_name, controller_file = self._resolve_controller_info(
                        cursor, clean_func
                    )
                else:
                    full_func_name = clean_func

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
        """Build edges from Python decorators.

        Logic:
        - Decorators wrap functions, so data flows THROUGH the decorator first
        - Create edge: Decorator -> Function
        - This allows taint analysis to "see" validation decorators

        Example: @validate_json wraps create_user
        - Data enters validate_json first
        - Then flows to create_user
        - If validate_json is a sanitizer, path is marked safe
        """

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

        Logic:
        - Django middleware runs BEFORE every view (configured in settings.MIDDLEWARE)
        - Create edges: Middleware -> All Views
        - This allows taint analysis to "see" global auth/security middleware

        Example: BasicAuthMiddleware protects all views
        - Request enters middleware first
        - Then flows to view
        - If middleware is a sanitizer (auth check), path is marked safe
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
        """)
        middlewares = cursor.fetchall()

        if not middlewares:
            return

        cursor.execute("""
            SELECT file, view_name
            FROM python_django_views
        """)
        views = cursor.fetchall()

        if not views:
            return

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

            for view in views:
                view_file = view["file"]
                view_name = view["view_name"]
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
                    source=mw_node_id,
                    target=view_node_id,
                    edge_type="django_middleware_flow",
                    file=mw_file,
                    line=0,
                    expression=f"settings.MIDDLEWARE: {mw_class}",
                    function=view_name,
                    metadata={"middleware": mw_class, "view": view_name},
                )
                edges.extend(new_edges)
                stats["django_middleware_edges_created"] += len(new_edges)

    def _resolve_controller_info(
        self,
        cursor: sqlite3.Cursor,
        method_name: str,
    ) -> tuple[str, str]:
        """Look up full ClassName.methodName and controller file path from symbols.

        This bridges the naming gap between InterceptorStrategy and DFGBuilder.

        CRITICAL: The handler is REFERENCED in routes file but DEFINED in controller file.
        e.g., routes/user.routes.ts references userController.create
              but UserController.create is defined in controllers/user.controller.ts

        Args:
            cursor: Database cursor
            method_name: Short method name (e.g., 'create', 'exportData')

        Returns:
            Tuple of (full_function_name, controller_file_path)
            Falls back to (method_name, None) if not found
        """
        try:
            cursor.execute(
                """
                SELECT name, path FROM symbols
                WHERE type = 'function'
                  AND name LIKE ?
                ORDER BY
                    CASE WHEN name LIKE '%Controller.%' THEN 0 ELSE 1 END,
                    LENGTH(name)
                LIMIT 1
            """,
                (f"%.{method_name}",),
            )

            row = cursor.fetchone()
            if row:
                return (row["name"], row["path"])
            return (method_name, None)
        except Exception:
            return (method_name, None)
