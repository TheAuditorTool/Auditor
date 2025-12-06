"""Rust Async Strategy - Builds async/await flow edges."""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class RustAsyncStrategy(GraphStrategy):
    """Strategy for building Rust async/await flow edges.

    Enables:
    - Tracking async function definitions
    - Mapping await points within async functions
    - Identifying async functions with multiple await points
    - Detecting potential blocking issues in async context
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Rust async/await flow."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "async_functions": 0,
            "await_points": 0,
            "functions_with_awaits": 0,
            "functions_without_awaits": 0,
            "max_await_count": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        self._build_async_function_nodes(cursor, nodes, stats)

        self._build_await_point_edges(cursor, nodes, edges, stats)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "rust_async",
                "stats": stats,
            },
        }
        return FidelityToken.attach_manifest(result)

    def _build_async_function_nodes(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        stats: dict[str, int],
    ) -> None:
        """Build nodes for async functions."""
        cursor.execute("""
            SELECT
                file_path,
                line,
                function_name,
                return_type,
                has_await,
                await_count
            FROM rust_async_functions
        """)

        async_functions = cursor.fetchall()

        for fn in async_functions:
            stats["async_functions"] += 1

            file_path = fn["file_path"]
            line = fn["line"]
            fn_name = fn["function_name"]
            has_await = fn["has_await"]
            await_count = fn["await_count"] or 0

            if has_await:
                stats["functions_with_awaits"] += 1
            else:
                stats["functions_without_awaits"] += 1

            if await_count > stats["max_await_count"]:
                stats["max_await_count"] = await_count

            fn_id = f"{file_path}:{line}::async_{fn_name}"
            if fn_id not in nodes:
                nodes[fn_id] = DFGNode(
                    id=fn_id,
                    file=file_path,
                    variable_name=fn_name,
                    scope="module",
                    type="async_function",
                    metadata={
                        "return_type": fn["return_type"],
                        "has_await": bool(has_await),
                        "await_count": await_count,
                        "is_async": True,
                    },
                )

    def _build_await_point_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from async functions to their await points."""

        cursor.execute("""
            SELECT
                file_path,
                line,
                containing_function,
                awaited_expression
            FROM rust_await_points
        """)

        await_points = cursor.fetchall()

        for await_pt in await_points:
            stats["await_points"] += 1

            file_path = await_pt["file_path"]
            line = await_pt["line"]
            containing_fn = await_pt["containing_function"]
            awaited_expr = await_pt["awaited_expression"] or "unknown"

            await_id = f"{file_path}:{line}::await"
            if await_id not in nodes:
                nodes[await_id] = DFGNode(
                    id=await_id,
                    file=file_path,
                    variable_name=".await",
                    scope=containing_fn or "unknown",
                    type="await_point",
                    metadata={
                        "awaited_expression": awaited_expr,
                        "containing_function": containing_fn,
                    },
                )

            if containing_fn:
                cursor.execute(
                    """
                    SELECT file_path, line, function_name
                    FROM rust_async_functions
                    WHERE file_path = ? AND function_name = ?
                    LIMIT 1
                """,
                    (file_path, containing_fn),
                )
                fn_row = cursor.fetchone()

                if fn_row:
                    fn_id = f"{fn_row['file_path']}:{fn_row['line']}::async_{containing_fn}"

                    if fn_id not in nodes:
                        nodes[fn_id] = DFGNode(
                            id=fn_id,
                            file=fn_row["file_path"],
                            variable_name=containing_fn,
                            scope="module",
                            type="async_function",
                            metadata={"is_async": True},
                        )

                    new_edges = create_bidirectional_edges(
                        source=fn_id,
                        target=await_id,
                        edge_type="await_point",
                        file=file_path,
                        line=line,
                        expression=f"{containing_fn} awaits {awaited_expr}",
                        function=containing_fn,
                        metadata={
                            "awaited_expression": awaited_expr,
                        },
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)
