"""Rust Unsafe Strategy - Builds unsafe block containment and propagation edges."""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class RustUnsafeStrategy(GraphStrategy):
    """Strategy for building Rust unsafe block analysis edges.

    Enables:
    - Tracking which functions contain unsafe blocks
    - Identifying unsafe blocks without SAFETY comments
    - Tracking unsafe trait implementations
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Rust unsafe blocks and propagation."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "unsafe_blocks": 0,
            "unsafe_functions": 0,
            "unsafe_traits": 0,
            "blocks_with_safety_comment": 0,
            "blocks_without_safety_comment": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_unsafe_blocks'
        """)
        if not cursor.fetchone():
            conn.close()
            return {
                "nodes": [],
                "edges": [],
                "metadata": {"graph_type": "rust_unsafe", "stats": stats},
            }

        self._build_containment_edges(cursor, nodes, edges, stats)

        self._build_unsafe_function_nodes(cursor, nodes, edges, stats)

        self._build_unsafe_trait_edges(cursor, nodes, edges, stats)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "rust_unsafe",
                "stats": stats,
            },
        }

    def _build_containment_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from functions to their contained unsafe blocks."""

        cursor.execute("""
            SELECT
                ub.file_path,
                ub.line_start,
                ub.line_end,
                ub.containing_function,
                ub.reason,
                ub.safety_comment,
                ub.has_safety_comment,
                ub.operations_json
            FROM rust_unsafe_blocks ub
            WHERE ub.containing_function IS NOT NULL
        """)

        unsafe_blocks = cursor.fetchall()

        for block in unsafe_blocks:
            stats["unsafe_blocks"] += 1

            file_path = block["file_path"]
            line_start = block["line_start"]
            line_end = block["line_end"]
            containing_fn = block["containing_function"]
            has_safety = block["has_safety_comment"]

            if has_safety:
                stats["blocks_with_safety_comment"] += 1
            else:
                stats["blocks_without_safety_comment"] += 1

            block_id = f"{file_path}:{line_start}::unsafe_block"
            if block_id not in nodes:
                nodes[block_id] = DFGNode(
                    id=block_id,
                    file=file_path,
                    variable_name="unsafe",
                    scope=containing_fn,
                    type="unsafe_block",
                    metadata={
                        "line_start": line_start,
                        "line_end": line_end,
                        "reason": block["reason"],
                        "has_safety_comment": bool(has_safety),
                        "safety_comment": block["safety_comment"],
                    },
                )

            cursor.execute(
                """
                SELECT line, end_line FROM rust_functions
                WHERE file_path = ? AND name = ?
                LIMIT 1
            """,
                (file_path, containing_fn),
            )
            fn_row = cursor.fetchone()

            if fn_row:
                fn_line = fn_row["line"]

                fn_id = f"{file_path}:{fn_line}::{containing_fn}"
                if fn_id not in nodes:
                    nodes[fn_id] = DFGNode(
                        id=fn_id,
                        file=file_path,
                        variable_name=containing_fn,
                        scope="module",
                        type="function",
                        metadata={"contains_unsafe": True},
                    )

                new_edges = create_bidirectional_edges(
                    source=fn_id,
                    target=block_id,
                    edge_type="unsafe_contains",
                    file=file_path,
                    line=line_start,
                    expression=f"{containing_fn} contains unsafe block",
                    function=containing_fn,
                    metadata={
                        "has_safety_comment": bool(has_safety),
                        "reason": block["reason"],
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)

    def _build_unsafe_function_nodes(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build nodes for functions declared as unsafe."""
        cursor.execute("""
            SELECT file_path, line, end_line, name, visibility, return_type
            FROM rust_functions
            WHERE is_unsafe = 1
        """)

        unsafe_functions = cursor.fetchall()

        for fn in unsafe_functions:
            stats["unsafe_functions"] += 1

            file_path = fn["file_path"]
            line = fn["line"]
            fn_name = fn["name"]

            fn_id = f"{file_path}:{line}::{fn_name}"
            if fn_id not in nodes:
                nodes[fn_id] = DFGNode(
                    id=fn_id,
                    file=file_path,
                    variable_name=fn_name,
                    scope="module",
                    type="unsafe_function",
                    metadata={
                        "visibility": fn["visibility"],
                        "return_type": fn["return_type"],
                        "is_declared_unsafe": True,
                    },
                )

    def _build_unsafe_trait_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges for unsafe trait implementations."""

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_unsafe_traits'
        """)
        if not cursor.fetchone():
            return

        cursor.execute("""
            SELECT file_path, line, trait_name, impl_type
            FROM rust_unsafe_traits
        """)

        unsafe_trait_impls = cursor.fetchall()

        for impl in unsafe_trait_impls:
            stats["unsafe_traits"] += 1

            file_path = impl["file_path"]
            line = impl["line"]
            trait_name = impl["trait_name"]
            impl_type = impl["impl_type"]

            impl_id = f"{file_path}:{line}::unsafe_impl_{trait_name}"
            if impl_id not in nodes:
                nodes[impl_id] = DFGNode(
                    id=impl_id,
                    file=file_path,
                    variable_name=f"unsafe impl {trait_name}",
                    scope=f"impl:{line}",
                    type="unsafe_trait_impl",
                    metadata={
                        "trait_name": trait_name,
                        "impl_type": impl_type,
                    },
                )

            cursor.execute(
                """
                SELECT file_path, line, name FROM rust_traits
                WHERE name = ? AND is_unsafe = 1
                LIMIT 1
            """,
                (trait_name,),
            )
            trait_row = cursor.fetchone()

            if trait_row:
                trait_id = f"{trait_row['file_path']}:{trait_row['line']}::trait_{trait_name}"
                if trait_id not in nodes:
                    nodes[trait_id] = DFGNode(
                        id=trait_id,
                        file=trait_row["file_path"],
                        variable_name=trait_name,
                        scope="module",
                        type="unsafe_trait",
                        metadata={"is_unsafe": True},
                    )

                new_edges = create_bidirectional_edges(
                    source=impl_id,
                    target=trait_id,
                    edge_type="unsafe_trait_impl",
                    file=file_path,
                    line=line,
                    expression=f"unsafe impl {trait_name} for {impl_type}",
                    function=f"impl:{line}",
                    metadata={
                        "trait_name": trait_name,
                        "impl_type": impl_type,
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)
