"""Node.js ORM Strategy - Handles Sequelize/TypeORM/Prisma relationship expansion.

This strategy builds edges for Node.js ORM relationships, enabling taint tracking
through model relationships (e.g., User.posts -> Post instances).

Created as part of refactor-polyglot-taint-engine (2025-11-27).
"""

import sqlite3
from dataclasses import asdict
from typing import Any

import click

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class NodeOrmStrategy(GraphStrategy):
    """Strategy for building Node.js ORM relationship edges.

    Handles:
    - Sequelize associations (hasMany, belongsTo, hasOne, belongsToMany)
    - TypeORM relationships (future: when typeorm_entities table exists)
    - Prisma relations (future: when prisma_models table exists)

    Creates edges from ORM model variables to their relationship attributes,
    enabling taint tracking through model relationships.
    """

    @property
    def name(self) -> str:
        return "node_orm"

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Node.js ORM relationships.

        Args:
            db_path: Path to repo_index.db
            project_root: Project root for metadata

        Returns:
            Dict with nodes, edges, metadata for ORM expansions
        """
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

        # =================================================================
        # SEQUELIZE ASSOCIATIONS
        # =================================================================
        try:
            # Check if table exists (strategy should not crash if missing)
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

                            # Infer alias from association type if not provided
                            alias = self._infer_alias(assoc_type, target)

                            # Source node: Model.alias (e.g., User.posts)
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

                            # Target node: Target model instance
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

                            # Create bidirectional edges for IFDS backward traversal
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

        except sqlite3.OperationalError:
            # Table might not exist - that's fine, not all projects use Sequelize
            pass

        # =================================================================
        # TYPEORM ENTITIES (Future)
        # =================================================================
        # TODO: Add support for typeorm_entities table when it exists
        # Schema would be similar: entity_name, relation_type, target_entity, etc.

        # =================================================================
        # PRISMA MODELS (Future)
        # =================================================================
        # TODO: Add support for prisma_models table when it exists
        # Schema would include relation fields from Prisma schema

        conn.close()

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {"graph_type": "node_orm", "stats": stats},
        }

    def _infer_alias(self, assoc_type: str, target_model: str) -> str:
        """Infer field name from association type.

        hasMany(Post) -> 'posts' (pluralized)
        belongsTo(User) -> 'user' (singular lowercase)
        hasOne(Profile) -> 'profile' (singular lowercase)

        Args:
            assoc_type: Association type (hasMany, belongsTo, hasOne, belongsToMany)
            target_model: Target model name

        Returns:
            Inferred alias for the relationship field
        """
        lower = target_model.lower()

        if "Many" in assoc_type:
            # Pluralize: Post -> posts, Category -> categories
            if lower.endswith("y"):
                return lower[:-1] + "ies"
            elif lower.endswith("s"):
                return lower + "es"
            else:
                return lower + "s"
        else:
            # Singular: User -> user
            return lower
