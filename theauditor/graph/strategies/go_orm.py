"""Go ORM Strategy - Handles GORM/SQLx struct relationships and database model edges."""

import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class GoOrmStrategy(GraphStrategy):
    """Strategy for building Go ORM relationship edges.

    Supports: GORM, SQLx, Ent
    Parses struct tags to detect:
    - Foreign keys (foreignKey tag)
    - Relationships (belongs_to, has_many, has_one, many_to_many)
    - Table mappings (gorm:"column:..." tags)
    """

    name = "go_orm"
    priority = 51

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build edges for Go ORM relationships."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "total_structs": 0,
            "orm_models": 0,
            "relationships_found": 0,
            "edges_created": 0,
            "unique_nodes": 0,
        }

        cursor.execute("""
            SELECT file AS file_path, struct_name, field_name, field_type, tag
            FROM go_struct_fields
            WHERE tag IS NOT NULL AND tag != ''
        """)

        struct_fields = cursor.fetchall()

        structs: dict[str, list] = defaultdict(list)
        for field in struct_fields:
            key = f"{field['file_path']}::{field['struct_name']}"
            structs[key].append(field)

        stats["total_structs"] = len(structs)

        orm_models: dict[str, list] = {}
        for struct_key, fields in structs.items():
            has_orm_tag = any(self._is_orm_tag(f["tag"]) for f in fields)
            if has_orm_tag:
                orm_models[struct_key] = fields
                stats["orm_models"] += 1

        if not orm_models:
            conn.close()
            return {
                "nodes": [],
                "edges": [],
                "metadata": {"graph_type": "go_orm", "stats": stats},
            }

        logger.info(f"Found {len(orm_models)} ORM models")

        with click.progressbar(
            orm_models.items(),
            label="Building Go ORM edges",
            show_pos=True,
        ) as model_items:
            for struct_key, fields in model_items:
                file_path, struct_name = struct_key.split("::", 1)

                model_id = f"{file_path}::{struct_name}"
                if model_id not in nodes:
                    nodes[model_id] = DFGNode(
                        id=model_id,
                        file=file_path,
                        variable_name=struct_name,
                        scope="global",
                        type="orm_model",
                        metadata={"is_orm_model": True},
                    )

                for field in fields:
                    tag = field["tag"]
                    field_name = field["field_name"]
                    field_type = field["field_type"]

                    relationships = self._parse_gorm_relationships(tag, field_type)

                    for rel in relationships:
                        stats["relationships_found"] += 1

                        target_model = rel["target_model"]
                        rel_type = rel["relationship_type"]

                        target_key = None
                        for key in orm_models:
                            if key.endswith(f"::{target_model}"):
                                target_key = key
                                break

                        if target_key:
                            target_file, _ = target_key.split("::", 1)
                            target_id = f"{target_file}::{target_model}"
                        else:
                            target_id = f"unknown::{target_model}"

                        if target_id not in nodes:
                            nodes[target_id] = DFGNode(
                                id=target_id,
                                file=target_key.split("::")[0] if target_key else "unknown",
                                variable_name=target_model,
                                scope="global",
                                type="orm_model",
                                metadata={"is_orm_model": True},
                            )

                        new_edges = create_bidirectional_edges(
                            source=model_id,
                            target=target_id,
                            edge_type=f"go_orm_{rel_type}",
                            file=file_path,
                            line=0,
                            expression=f"{struct_name}.{field_name} -> {target_model}",
                            function="global",
                            metadata={
                                "relationship_type": rel_type,
                                "field_name": field_name,
                                "field_type": field_type,
                                "foreign_key": rel.get("foreign_key"),
                                "references": rel.get("references"),
                            },
                        )
                        edges.extend(new_edges)
                        stats["edges_created"] += len(new_edges)

        conn.close()
        stats["unique_nodes"] = len(nodes)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(project_root).resolve()),
                "graph_type": "go_orm",
                "stats": stats,
            },
        }
        return FidelityToken.attach_manifest(result)

    def _is_orm_tag(self, tag: str) -> bool:
        """Check if a struct tag contains ORM-related tags."""
        if not tag:
            return False
        orm_prefixes = ["gorm:", "db:", "sql:", "json:"]
        return any(prefix in tag.lower() for prefix in orm_prefixes)

    def _parse_gorm_relationships(self, tag: str, field_type: str) -> list[dict]:
        """Parse GORM relationship information from struct tags.

        GORM relationship patterns:
        - `gorm:"foreignKey:UserID"` - Foreign key reference
        - `gorm:"references:ID"` - Reference to target model's field
        - Type patterns:
          - `*User` or `User` - belongs_to (singular)
          - `[]User` or `[]*User` - has_many (slice)
          - `gorm.Model` embedded - base model
        """
        relationships = []

        if not tag:
            return relationships

        target_model = self._extract_model_from_type(field_type)
        if not target_model:
            return relationships

        is_slice = field_type.startswith("[]") or field_type.startswith("[]*")
        is_pointer = "*" in field_type

        gorm_match = re.search(r'gorm:"([^"]*)"', tag)
        gorm_tag = gorm_match.group(1) if gorm_match else ""

        foreign_key = None
        references = None

        if gorm_tag:
            fk_match = re.search(r"foreignKey:(\w+)", gorm_tag, re.IGNORECASE)
            if fk_match:
                foreign_key = fk_match.group(1)

            ref_match = re.search(r"references:(\w+)", gorm_tag, re.IGNORECASE)
            if ref_match:
                references = ref_match.group(1)

        if is_slice:
            rel_type = "has_many"
        elif "many2many" in gorm_tag.lower():
            rel_type = "many_to_many"
        elif foreign_key:
            rel_type = "belongs_to"
        else:
            rel_type = "has_one" if is_pointer else "belongs_to"

        relationships.append(
            {
                "target_model": target_model,
                "relationship_type": rel_type,
                "foreign_key": foreign_key,
                "references": references,
            }
        )

        return relationships

    def _extract_model_from_type(self, field_type: str) -> str | None:
        """Extract model name from Go type.

        Examples:
        - `*User` -> `User`
        - `[]User` -> `User`
        - `[]*User` -> `User`
        - `User` -> `User`
        - `string` -> None (primitive)
        - `time.Time` -> None (stdlib)
        """
        if not field_type:
            return None

        clean_type = field_type.lstrip("*").lstrip("[]").lstrip("*")

        primitives = {
            "string",
            "int",
            "int8",
            "int16",
            "int32",
            "int64",
            "uint",
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "float32",
            "float64",
            "bool",
            "byte",
            "rune",
            "error",
            "interface{}",
            "any",
        }

        if clean_type.lower() in primitives:
            return None

        if "." in clean_type:
            pkg = clean_type.split(".")[0]
            stdlib_pkgs = {"time", "context", "sql", "gorm", "json", "fmt"}
            if pkg.lower() in stdlib_pkgs:
                return None

        if len(clean_type) == 1 and clean_type.isupper():
            return None

        return clean_type
