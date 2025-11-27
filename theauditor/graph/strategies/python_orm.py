"""Python ORM Strategy - Handles SQLAlchemy/Django ORM relationship expansion.

This strategy builds edges for ORM relationships, enabling taint tracking
through model relationships (e.g., User -> user.posts).

Extracted from dfg_builder.py as part of Phase 3: Strategy Pattern refactoring.
"""

import sqlite3
from dataclasses import asdict
from typing import Any

import click

from .base import GraphStrategy
from ..types import DFGNode, DFGEdge, create_bidirectional_edges


from theauditor.taint.orm_utils import PythonOrmContext


class PythonOrmStrategy(GraphStrategy):
    """Strategy for building Python ORM relationship edges.

    Handles:
    - SQLAlchemy relationships (relationship(), ForeignKey)
    - Django ORM relationships (ForeignKey, ManyToManyField)

    Creates edges from ORM model variables to their relationship attributes,
    enabling taint tracking through model relationships.
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Python ORM relationships.

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

        stats = {"orm_expansions": 0, "edges_created": 0}

        try:
            orm_context = PythonOrmContext.from_database(cursor)
            if not orm_context.enabled:
                conn.close()
                return {"nodes": [], "edges": [], "metadata": {"stats": stats}}
        except Exception as e:
            print(f"[PythonOrmStrategy] ORM Context init failed: {e}")
            conn.close()
            return {"nodes": [], "edges": [], "metadata": {"stats": stats}}

        known_models = (
            orm_context.get_all_model_names() if hasattr(orm_context, "get_all_model_names") else []
        )
        if not known_models:
            known_models = list(getattr(orm_context, "models", {}).keys())

        if not known_models:
            print("[PythonOrmStrategy] No ORM models found, skipping")
            conn.close()
            return {"nodes": [], "edges": [], "metadata": {"stats": stats}}

        print(f"[PythonOrmStrategy] Found {len(known_models)} ORM models: {known_models[:5]}...")

        model_patterns = set()
        for model in known_models:
            model_lower = model.lower()
            model_patterns.add(model_lower)
            model_patterns.add(f"{model_lower}s")
            model_patterns.add(f"current_{model_lower}")
            model_patterns.add(f"new_{model_lower}")

        placeholders = ",".join("?" * len(model_patterns))
        cursor.execute(
            f"""
            SELECT file, target_var, in_function
            FROM assignments
            WHERE target_var IN ({placeholders})
        """,
            list(model_patterns),
        )

        potential_models = cursor.fetchall()
        print(
            f"[PythonOrmStrategy] Found {len(potential_models)} potential ORM variable assignments"
        )

        with click.progressbar(
            potential_models, label="Building Python ORM edges", show_pos=True
        ) as items:
            for row in items:
                file = row["file"]
                var_name = row["target_var"]
                func = row["in_function"] or "global"

                model_name = orm_context.get_model_for_variable(file, [func], var_name)

                if not model_name:
                    continue

                rels = orm_context.get_relationships(model_name)
                fk_fields = orm_context.get_fk_fields(model_name)

                if not rels and not fk_fields:
                    continue

                stats["orm_expansions"] += 1

                source_id = f"{file}::{func}::{var_name}"

                for rel in rels:
                    alias = rel["alias"]
                    target_var = f"{var_name}.{alias}"
                    target_id = f"{file}::{func}::{target_var}"

                    if target_id not in nodes:
                        nodes[target_id] = DFGNode(
                            id=target_id,
                            file=file,
                            variable_name=target_var,
                            scope=func,
                            type="orm_expansion",
                            metadata={"model": model_name, "relation": alias},
                        )

                    new_edges = create_bidirectional_edges(
                        source=source_id,
                        target=target_id,
                        edge_type="orm_expansion",
                        file=file,
                        line=0,
                        expression=f"ORM: {model_name}.{alias}",
                        function=func,
                    )
                    edges.extend(new_edges)
                    stats["edges_created"] += len(new_edges)

        conn.close()
        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {"graph_type": "python_orm", "stats": stats},
        }
