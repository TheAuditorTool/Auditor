"""Rust FFI Strategy - Builds FFI boundary and extern function edges."""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class RustFFIStrategy(GraphStrategy):
    """Strategy for building Rust FFI boundary edges.

    Enables:
    - Tracking extern blocks and their ABI
    - Identifying FFI function declarations
    - Detecting variadic C functions
    - Security analysis of FFI boundaries
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Rust FFI boundaries."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "extern_blocks": 0,
            "extern_functions": 0,
            "variadic_functions": 0,
            "c_abi_blocks": 0,
            "system_abi_blocks": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_extern_blocks'
        """)
        if not cursor.fetchone():
            conn.close()
            return {
                "nodes": [],
                "edges": [],
                "metadata": {"graph_type": "rust_ffi", "stats": stats},
            }

        self._build_extern_block_nodes(cursor, nodes, stats)

        self._build_extern_function_edges(cursor, nodes, edges, stats)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "rust_ffi",
                "stats": stats,
            },
        }

    def _build_extern_block_nodes(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        stats: dict[str, int],
    ) -> None:
        """Build nodes for extern blocks."""
        cursor.execute("""
            SELECT file_path, line, end_line, abi
            FROM rust_extern_blocks
        """)

        extern_blocks = cursor.fetchall()

        for block in extern_blocks:
            stats["extern_blocks"] += 1

            file_path = block["file_path"]
            line = block["line"]
            abi = block["abi"] or "C"

            if abi == "C":
                stats["c_abi_blocks"] += 1
            elif abi == "system":
                stats["system_abi_blocks"] += 1

            block_id = f"{file_path}:{line}::extern_{abi}"
            if block_id not in nodes:
                nodes[block_id] = DFGNode(
                    id=block_id,
                    file=file_path,
                    variable_name=f'extern "{abi}"',
                    scope="module",
                    type="extern_block",
                    metadata={
                        "abi": abi,
                        "line_start": line,
                        "line_end": block["end_line"],
                        "is_ffi_boundary": True,
                    },
                )

    def _build_extern_function_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build nodes and edges for extern functions."""

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_extern_functions'
        """)
        if not cursor.fetchone():
            return

        cursor.execute("""
            SELECT
                ref.file_path,
                ref.line,
                ref.name,
                ref.abi,
                ref.return_type,
                ref.params_json,
                ref.is_variadic
            FROM rust_extern_functions ref
        """)

        extern_functions = cursor.fetchall()

        for fn in extern_functions:
            stats["extern_functions"] += 1

            file_path = fn["file_path"]
            line = fn["line"]
            fn_name = fn["name"]
            abi = fn["abi"] or "C"
            is_variadic = fn["is_variadic"]

            if is_variadic:
                stats["variadic_functions"] += 1

            fn_id = f"{file_path}:{line}::ffi_{fn_name}"
            if fn_id not in nodes:
                nodes[fn_id] = DFGNode(
                    id=fn_id,
                    file=file_path,
                    variable_name=fn_name,
                    scope=f"extern_{abi}",
                    type="extern_function",
                    metadata={
                        "abi": abi,
                        "return_type": fn["return_type"],
                        "params_json": fn["params_json"],
                        "is_variadic": bool(is_variadic),
                        "is_ffi": True,
                    },
                )

            cursor.execute(
                """
                SELECT file_path, line, abi FROM rust_extern_blocks
                WHERE file_path = ?
                  AND line < ?
                  AND (end_line IS NULL OR end_line > ?)
                ORDER BY line DESC
                LIMIT 1
            """,
                (file_path, line, line),
            )
            block_row = cursor.fetchone()

            if block_row:
                block_abi = block_row["abi"] or "C"
                block_id = f"{block_row['file_path']}:{block_row['line']}::extern_{block_abi}"

                if block_id not in nodes:
                    nodes[block_id] = DFGNode(
                        id=block_id,
                        file=block_row["file_path"],
                        variable_name=f'extern "{block_abi}"',
                        scope="module",
                        type="extern_block",
                        metadata={
                            "abi": block_abi,
                            "line_start": block_row["line"],
                            "is_ffi_boundary": True,
                        },
                    )

                new_edges = create_bidirectional_edges(
                    source=block_id,
                    target=fn_id,
                    edge_type="ffi_declaration",
                    file=file_path,
                    line=line,
                    expression=f'extern "{abi}" fn {fn_name}',
                    function=fn_name,
                    metadata={
                        "abi": abi,
                        "is_variadic": bool(is_variadic),
                        "return_type": fn["return_type"],
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)
