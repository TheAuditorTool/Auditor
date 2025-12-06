"""Node.js ORM Strategy - Handles Sequelize/TypeORM/Prisma relationship expansion."""

import sqlite3
from dataclasses import asdict
from typing import Any

import click

from theauditor.indexer.fidelity_utils import FidelityToken

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy

IRREGULAR_PLURALS: dict[str, str] = {
    "child": "children",
    "person": "people",
    "man": "men",
    "woman": "women",
    "foot": "feet",
    "tooth": "teeth",
    "goose": "geese",
    "mouse": "mice",
    "louse": "lice",
    "ox": "oxen",
    "datum": "data",
    "medium": "media",
    "criterion": "criteria",
    "phenomenon": "phenomena",
    "analysis": "analyses",
    "basis": "bases",
    "crisis": "crises",
    "diagnosis": "diagnoses",
    "hypothesis": "hypotheses",
    "thesis": "theses",
    "axis": "axes",
    "index": "indices",
    "matrix": "matrices",
    "vertex": "vertices",
    "appendix": "appendices",
    "leaf": "leaves",
    "life": "lives",
    "wife": "wives",
    "knife": "knives",
    "wolf": "wolves",
    "calf": "calves",
    "half": "halves",
    "self": "selves",
    "shelf": "shelves",
    "elf": "elves",
    "loaf": "loaves",
    "thief": "thieves",
    "status": "statuses",
    "address": "addresses",
    "process": "processes",
    "class": "classes",
    "alias": "aliases",
    "sheep": "sheep",
    "fish": "fish",
    "deer": "deer",
    "species": "species",
    "series": "series",
    "news": "news",
    "equipment": "equipment",
    "information": "information",
    "rice": "rice",
    "money": "money",
    "aircraft": "aircraft",
}


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

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {"graph_type": "node_orm", "stats": stats},
        }
        return FidelityToken.attach_manifest(result)

    def _infer_alias(self, assoc_type: str, target_model: str) -> str:
        """Infer field name from association type.

        GRAPH FIX G14: Use irregular plural lookup before naive rules.
        Prevents child->childs, person->persons, etc.
        """
        lower = target_model.lower()

        if "Many" in assoc_type:
            if lower in IRREGULAR_PLURALS:
                return IRREGULAR_PLURALS[lower]

            if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
                return lower[:-1] + "ies"
            elif lower.endswith(("s", "x", "z", "ch", "sh")):
                return lower + "es"
            elif lower.endswith("f"):
                return lower[:-1] + "ves"
            elif lower.endswith("fe"):
                return lower[:-2] + "ves"
            else:
                return lower + "s"
        else:
            return lower
