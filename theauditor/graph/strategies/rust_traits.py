"""Rust Trait Strategy - Builds trait implementation and method resolution edges."""

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class RustTraitStrategy(GraphStrategy):
    """Strategy for building Rust trait implementation edges.

    Enables:
    - Trait impl resolution (which type implements which trait)
    - Method call resolution (which impl block handles a method call)
    - Trait bound tracking for generics
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Rust trait implementations."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "trait_impls": 0,
            "method_impls": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        self._build_implements_trait_edges(cursor, nodes, edges, stats)
        self._build_trait_method_edges(cursor, nodes, edges, stats)

        conn.close()

        stats["unique_nodes"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "rust_traits",
                "stats": stats,
            },
        }
        return FidelityToken.attach_manifest(result)

    def _build_implements_trait_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from impl blocks to trait definitions."""

        cursor.execute("""
            SELECT
                rib.file_path as impl_file,
                rib.line as impl_line,
                rib.end_line as impl_end_line,
                rib.target_type_raw,
                rib.target_type_resolved,
                rib.trait_name,
                rib.trait_resolved,
                rib.is_unsafe
            FROM rust_impl_blocks rib
            WHERE rib.trait_name IS NOT NULL
        """)

        impl_blocks = cursor.fetchall()

        cursor.execute("""
            SELECT file_path, line, name, supertraits, is_unsafe
            FROM rust_traits
        """)
        trait_lookup: dict[str, dict] = {}
        for row in cursor.fetchall():
            trait_lookup[row["name"]] = {
                "file_path": row["file_path"],
                "line": row["line"],
                "name": row["name"],
                "supertraits": row["supertraits"],
                "is_unsafe": row["is_unsafe"],
            }

        for impl_block in impl_blocks:
            stats["trait_impls"] += 1

            impl_file = impl_block["impl_file"]
            impl_line = impl_block["impl_line"]
            target_type = impl_block["target_type_raw"]
            trait_name = impl_block["trait_name"]
            is_unsafe = impl_block["is_unsafe"]

            impl_id = f"{impl_file}:{impl_line}::impl_{target_type}"
            if impl_id not in nodes:
                nodes[impl_id] = DFGNode(
                    id=impl_id,
                    file=impl_file,
                    variable_name=f"impl {trait_name} for {target_type}",
                    scope=f"impl:{impl_line}",
                    type="impl_block",
                    metadata={
                        "target_type": target_type,
                        "trait_name": trait_name,
                        "is_unsafe": bool(is_unsafe),
                    },
                )

            trait_info = trait_lookup.get(trait_name)
            if trait_info:
                trait_file = trait_info["file_path"]
                trait_line = trait_info["line"]
                trait_id = f"{trait_file}:{trait_line}::trait_{trait_name}"

                if trait_id not in nodes:
                    nodes[trait_id] = DFGNode(
                        id=trait_id,
                        file=trait_file,
                        variable_name=trait_name,
                        scope=f"trait:{trait_line}",
                        type="trait",
                        metadata={
                            "supertraits": trait_info["supertraits"],
                            "is_unsafe": bool(trait_info["is_unsafe"]),
                        },
                    )

                new_edges = create_bidirectional_edges(
                    source=impl_id,
                    target=trait_id,
                    edge_type="implements_trait",
                    file=impl_file,
                    line=impl_line,
                    expression=f"impl {trait_name} for {target_type}",
                    function=f"impl:{impl_line}",
                    metadata={
                        "target_type": target_type,
                        "trait_name": trait_name,
                        "is_unsafe": bool(is_unsafe),
                    },
                )
                edges.extend(new_edges)
                stats["edges_created"] += len(new_edges)

    def _build_trait_method_edges(
        self,
        cursor: sqlite3.Cursor,
        nodes: dict[str, DFGNode],
        edges: list[DFGEdge],
        stats: dict[str, int],
    ) -> None:
        """Build edges from impl methods to trait method signatures."""

        cursor.execute("""
            SELECT
                rtm.file_path as trait_file,
                rtm.trait_line,
                rtm.method_line,
                rtm.method_name,
                rtm.return_type,
                rtm.has_default,
                rt.name as trait_name
            FROM rust_trait_methods rtm
            JOIN rust_traits rt ON rtm.file_path = rt.file_path
                AND rtm.trait_line = rt.line
        """)

        trait_methods = cursor.fetchall()

        trait_method_lookup: dict[tuple[str, str], dict] = {}
        for row in trait_methods:
            key = (row["trait_name"], row["method_name"])
            trait_method_lookup[key] = {
                "file_path": row["trait_file"],
                "trait_line": row["trait_line"],
                "method_line": row["method_line"],
                "method_name": row["method_name"],
                "return_type": row["return_type"],
                "has_default": row["has_default"],
            }

        cursor.execute("""
            SELECT
                rf.file_path,
                rf.line as fn_line,
                rf.name as fn_name,
                rf.return_type,
                rib.trait_name,
                rib.target_type_raw,
                rib.line as impl_line,
                rib.end_line as impl_end_line
            FROM rust_functions rf
            JOIN rust_impl_blocks rib ON rf.file_path = rib.file_path
                AND rf.line > rib.line
                AND (rib.end_line IS NULL OR rf.line < rib.end_line)
            WHERE rib.trait_name IS NOT NULL
        """)

        impl_functions = cursor.fetchall()

        for impl_fn in impl_functions:
            trait_name = impl_fn["trait_name"]
            fn_name = impl_fn["fn_name"]
            fn_file = impl_fn["file_path"]
            fn_line = impl_fn["fn_line"]
            target_type = impl_fn["target_type_raw"]

            trait_method = trait_method_lookup.get((trait_name, fn_name))
            if not trait_method:
                continue

            stats["method_impls"] += 1

            impl_method_id = f"{fn_file}:{fn_line}::{fn_name}"
            if impl_method_id not in nodes:
                nodes[impl_method_id] = DFGNode(
                    id=impl_method_id,
                    file=fn_file,
                    variable_name=fn_name,
                    scope=f"impl_{target_type}",
                    type="impl_method",
                    metadata={
                        "trait_name": trait_name,
                        "target_type": target_type,
                    },
                )

            trait_method_id = (
                f"{trait_method['file_path']}:{trait_method['method_line']}::{fn_name}"
            )
            if trait_method_id not in nodes:
                nodes[trait_method_id] = DFGNode(
                    id=trait_method_id,
                    file=trait_method["file_path"],
                    variable_name=fn_name,
                    scope=f"trait_{trait_name}",
                    type="trait_method",
                    metadata={
                        "trait_name": trait_name,
                        "has_default": bool(trait_method["has_default"]),
                        "return_type": trait_method["return_type"],
                    },
                )

            new_edges = create_bidirectional_edges(
                source=impl_method_id,
                target=trait_method_id,
                edge_type="trait_method_impl",
                file=fn_file,
                line=fn_line,
                expression=f"{target_type}::{fn_name} implements {trait_name}::{fn_name}",
                function=fn_name,
                metadata={
                    "trait_name": trait_name,
                    "target_type": target_type,
                    "has_default": bool(trait_method["has_default"]),
                },
            )
            edges.extend(new_edges)
            stats["edges_created"] += len(new_edges)
