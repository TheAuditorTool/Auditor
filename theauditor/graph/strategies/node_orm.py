"""Node.js ORM Strategy - Handles Sequelize/TypeORM/Prisma relationship expansion."""

import sqlite3
from dataclasses import asdict
from typing import Any

import click

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class NodeOrmStrategy(GraphStrategy):
    """Strategy for building Node.js ORM relationship edges."""

    @property
    def name(self) -> str:
        return "node_orm"

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Node.js ORM relationships."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "sequelize_associations": 0,
            "typeorm_relations": 0,
            "prisma_relations": 0,
            "edges_created": 0,
        }

        # GRAPH FIX G4: Removed try/except - violates Zero Fallback (Fail Loud)
        # Table check is valid feature detection, but real errors must crash
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sequelize_associations'"
        )
        if cursor.fetchone():
            cursor.execute("""
                SELECT file, line, model_name, association_type, target_model, foreign_key
                FROM sequelize_associations
            """)

            associations = cursor.fetchall()
            if associations:
                with click.progressbar(
                    associations,
                    label="Building Sequelize ORM edges",
                    show_pos=True,
                ) as items:
                    for row in items:
                        stats["sequelize_associations"] += 1

                        file = row["file"]
                        line = row["line"]
                        model = row["model_name"]
                        assoc_type = row["association_type"]
                        target = row["target_model"]
                        foreign_key = row["foreign_key"]

                        alias = self._infer_alias(assoc_type, target)

                        source_id = f"{file}::{model}::{alias}"
                        if source_id not in nodes:
                            nodes[source_id] = DFGNode(
                                id=source_id,
                                file=file,
                                variable_name=alias,
                                scope=model,
                                type="orm_relationship",
                                metadata={
                                    "model": model,
                                    "target": target,
                                    "association_type": assoc_type,
                                },
                            )

                        target_id = f"{file}::{target}::instance"
                        if target_id not in nodes:
                            nodes[target_id] = DFGNode(
                                id=target_id,
                                file=file,
                                variable_name="instance",
                                scope=target,
                                type="orm_model",
                                metadata={"model": target},
                            )

                        new_edges = create_bidirectional_edges(
                            source=source_id,
                            target=target_id,
                            edge_type="orm_expansion",
                            file=file,
                            line=line,
                            expression=f"{model}.{assoc_type}({target})",
                            function=model,
                            metadata={
                                "association_type": assoc_type,
                                "foreign_key": foreign_key or "",
                            },
                        )
                        edges.extend(new_edges)
                        stats["edges_created"] += len(new_edges)

        conn.close()

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {"graph_type": "node_orm", "stats": stats},
        }

    def _infer_alias(self, assoc_type: str, target_model: str) -> str:
        """Infer field name from association type."""
        lower = target_model.lower()

        if "Many" in assoc_type:
            if lower.endswith("y"):
                return lower[:-1] + "ies"
            elif lower.endswith("s"):
                return lower + "es"
            else:
                return lower + "s"
        else:
            return lower
