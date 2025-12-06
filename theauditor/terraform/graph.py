"""Terraform Provisioning Flow Graph Builder."""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger

from ..graph.store import XGraphStore


@dataclass
class ProvisioningNode:
    """Represents a node in the Terraform provisioning graph."""

    id: str
    file: str
    node_type: str
    terraform_type: str
    name: str
    is_sensitive: bool = False
    has_public_exposure: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvisioningEdge:
    """Represents a data flow edge in the provisioning graph."""

    source: str
    target: str
    file: str
    edge_type: str
    expression: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TerraformGraphBuilder:
    """Build Terraform provisioning flow graphs from repo_index.db."""

    def __init__(self, db_path: str):
        """Initialize builder with database path."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        graphs_db_path = self.db_path.parent / "graphs.db"
        self.store = XGraphStore(db_path=str(graphs_db_path))

    def _bulk_load_all_data(self, cursor) -> dict[str, Any]:
        """Bulk load ALL Terraform data in 5 queries instead of N*M queries."""

        cursor.execute("""
            SELECT resource_id, property_name, property_value
            FROM terraform_resource_properties
        """)
        props_map: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            rid = row["resource_id"]
            if rid not in props_map:
                props_map[rid] = {}
            value = row["property_value"]
            if value:
                try:
                    props_map[rid][row["property_name"]] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    props_map[rid][row["property_name"]] = value
            else:
                props_map[rid][row["property_name"]] = value

        cursor.execute("""
            SELECT resource_id, property_name
            FROM terraform_resource_properties
            WHERE is_sensitive = 1
        """)
        sensitive_map: dict[str, set[str]] = {}
        for row in cursor.fetchall():
            rid = row["resource_id"]
            if rid not in sensitive_map:
                sensitive_map[rid] = set()
            sensitive_map[rid].add(row["property_name"])

        cursor.execute("""
            SELECT resource_id, depends_on_ref
            FROM terraform_resource_deps
        """)
        deps_map: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            rid = row["resource_id"]
            if rid not in deps_map:
                deps_map[rid] = []
            deps_map[rid].append(row["depends_on_ref"])

        cursor.execute("""
            SELECT variable_id, variable_name
            FROM terraform_variables
        """)
        var_lookup: dict[str, str] = {}
        for row in cursor.fetchall():
            var_name = row["variable_name"]
            if var_name not in var_lookup:
                var_lookup[var_name] = row["variable_id"]

        cursor.execute("""
            SELECT resource_id, resource_type, resource_name
            FROM terraform_resources
        """)
        resource_lookup: dict[str, str] = {}
        for row in cursor.fetchall():
            key = f"{row['resource_type']}.{row['resource_name']}"
            resource_lookup[key] = row["resource_id"]

        return {
            "props": props_map,
            "sensitive": sensitive_map,
            "deps": deps_map,
            "vars": var_lookup,
            "resources": resource_lookup,
        }

    def build_provisioning_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build provisioning flow graph from Terraform data."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        bulk_data = self._bulk_load_all_data(cursor)

        nodes: dict[str, ProvisioningNode] = {}
        edges: list[ProvisioningEdge] = []

        stats = {
            "total_resources": 0,
            "total_variables": 0,
            "total_outputs": 0,
            "edges_created": 0,
            "files_processed": 0,
        }

        cursor.execute("""
            SELECT variable_id, file_path, variable_name, variable_type, is_sensitive
            FROM terraform_variables
        """)

        for row in cursor.fetchall():
            stats["total_variables"] += 1
            nodes[row["variable_id"]] = ProvisioningNode(
                id=row["variable_id"],
                file=row["file_path"],
                node_type="variable",
                terraform_type=row["variable_type"] or "unknown",
                name=row["variable_name"],
                is_sensitive=bool(row["is_sensitive"]),
                metadata={"source": "terraform_variables"},
            )

        cursor.execute("""
            SELECT resource_id, file_path, resource_type, resource_name,
                   has_public_exposure
            FROM terraform_resources
        """)

        for row in cursor.fetchall():
            stats["total_resources"] += 1

            resource_id = row["resource_id"]

            properties = bulk_data["props"].get(resource_id, {})
            sensitive_props = list(bulk_data["sensitive"].get(resource_id, set()))

            nodes[resource_id] = ProvisioningNode(
                id=resource_id,
                file=row["file_path"],
                node_type="resource",
                terraform_type=row["resource_type"],
                name=row["resource_name"],
                has_public_exposure=bool(row["has_public_exposure"]),
                metadata={
                    "properties": properties,
                    "sensitive_properties": sensitive_props,
                },
            )

            var_refs = self._extract_variable_references(properties)

            for var_name in var_refs:
                var_id = bulk_data["vars"].get(var_name)
                if var_id and var_id in nodes:
                    edges.append(
                        ProvisioningEdge(
                            source=var_id,
                            target=resource_id,
                            file=row["file_path"],
                            edge_type="variable_reference",
                            expression=f"var.{var_name}",
                            metadata={
                                "property_path": self._find_property_path(properties, var_name)
                            },
                        )
                    )
                    stats["edges_created"] += 1

            depends_on = bulk_data["deps"].get(resource_id, [])
            for dep_ref in depends_on:
                dep_id = bulk_data["resources"].get(dep_ref)
                if dep_id and dep_id in nodes:
                    edges.append(
                        ProvisioningEdge(
                            source=dep_id,
                            target=resource_id,
                            file=row["file_path"],
                            edge_type="resource_dependency",
                            expression=dep_ref,
                            metadata={"explicit_depends_on": True},
                        )
                    )
                    stats["edges_created"] += 1

        cursor.execute("""
            SELECT output_id, file_path, output_name, value_json, is_sensitive
            FROM terraform_outputs
        """)

        for row in cursor.fetchall():
            stats["total_outputs"] += 1
            output_id = row["output_id"]

            nodes[output_id] = ProvisioningNode(
                id=output_id,
                file=row["file_path"],
                node_type="output",
                terraform_type="output",
                name=row["output_name"],
                is_sensitive=bool(row["is_sensitive"]),
                metadata={"value_expr": row["value_json"]},
            )

            value_json = row["value_json"]
            if value_json:
                refs = self._extract_references_from_expression(value_json)
                for ref in refs:
                    source_id = self._resolve_reference_from_bulk(ref, bulk_data)
                    if source_id and source_id in nodes:
                        edges.append(
                            ProvisioningEdge(
                                source=source_id,
                                target=output_id,
                                file=row["file_path"],
                                edge_type="output_reference",
                                expression=ref,
                            )
                        )
                        stats["edges_created"] += 1

        conn.close()

        files = {node.file for node in nodes.values()}
        stats["files_processed"] = len(files)

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "terraform_provisioning",
                "stats": stats,
            },
        }

        self._write_to_graphs_db(result)

        logger.info(
            f"Built Terraform provisioning graph: {stats['total_resources']} resources, "
            f"{stats['total_variables']} variables, {stats['total_outputs']} outputs, "
            f"{stats['edges_created']} edges"
        )

        return result

    def _extract_variable_references(self, properties: dict) -> set[str]:
        """Extract variable names from property values."""
        var_names = set()

        def scan_value(val):
            if isinstance(val, str):
                matches = re.findall(r"\$\{var\.(\w+)\}|var\.(\w+)", val)
                for match in matches:
                    var_names.add(match[0] or match[1])
            elif isinstance(val, dict):
                for v in val.values():
                    scan_value(v)
            elif isinstance(val, list):
                for item in val:
                    scan_value(item)

        scan_value(properties)
        return var_names

    def _resolve_reference_from_bulk(self, ref: str, bulk_data: dict) -> str | None:
        """Resolve any Terraform reference using preloaded bulk data. O(1)."""
        if ref.startswith("var."):
            var_name = ref.split(".", 1)[1]
            return bulk_data["vars"].get(var_name)
        else:
            return bulk_data["resources"].get(ref)

    def _find_variable_id(self, cursor, var_name: str, current_file: str) -> str | None:
        """Find variable ID by name (may be in different file)."""

        cursor.execute(
            """
            SELECT variable_id FROM terraform_variables
            WHERE variable_name = ? AND file_path = ?
        """,
            (var_name, current_file),
        )
        row = cursor.fetchone()
        if row:
            return row["variable_id"]

        cursor.execute(
            """
            SELECT variable_id FROM terraform_variables
            WHERE variable_name = ?
            LIMIT 1
        """,
            (var_name,),
        )
        row = cursor.fetchone()
        return row["variable_id"] if row else None

    def _resolve_resource_reference(self, cursor, ref: str, current_file: str) -> str | None:
        """Resolve resource reference like 'aws_security_group.web' to resource_id."""

        parts = ref.split(".", 1)
        if len(parts) != 2:
            return None

        resource_type, resource_name = parts

        cursor.execute(
            """
            SELECT resource_id FROM terraform_resources
            WHERE resource_type = ? AND resource_name = ?
        """,
            (resource_type, resource_name),
        )
        row = cursor.fetchone()
        return row["resource_id"] if row else None

    def _extract_references_from_expression(self, expr_json: str) -> set[str]:
        """Extract all Terraform references from an expression."""
        refs = set()
        if not expr_json:
            return refs

        try:
            expr = json.loads(expr_json) if isinstance(expr_json, str) else expr_json
        except Exception:
            expr = str(expr_json)

        matches = re.findall(
            r"((?:aws_|azurerm_|google_)\w+\.\w+|var\.\w+|data\.\w+\.\w+)", str(expr)
        )
        refs.update(matches)
        return refs

    def _resolve_reference(self, cursor, ref: str, current_file: str) -> str | None:
        """Resolve any Terraform reference to node ID."""
        if ref.startswith("var."):
            var_name = ref.split(".", 1)[1]
            return self._find_variable_id(cursor, var_name, current_file)
        else:
            return self._resolve_resource_reference(cursor, ref, current_file)

    def _find_property_path(self, properties: dict, var_name: str) -> str | None:
        """Find which property path contains the variable reference."""

        for key, val in properties.items():
            if isinstance(val, str) and var_name in val:
                return key
        return None

    def _get_resource_properties(self, cursor, resource_id: str) -> dict[str, Any]:
        """Get resource properties from junction table."""
        cursor.execute(
            """
            SELECT property_name, property_value
            FROM terraform_resource_properties
            WHERE resource_id = ?
            """,
            (resource_id,),
        )
        properties = {}
        for row in cursor.fetchall():
            value = row["property_value"]

            if value:
                try:
                    properties[row["property_name"]] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    properties[row["property_name"]] = value
            else:
                properties[row["property_name"]] = value
        return properties

    def _is_property_sensitive(self, cursor, resource_id: str, property_name: str) -> bool:
        """Check if a property is marked as sensitive."""
        cursor.execute(
            """
            SELECT is_sensitive FROM terraform_resource_properties
            WHERE resource_id = ? AND property_name = ?
            """,
            (resource_id, property_name),
        )
        row = cursor.fetchone()
        return bool(row and row["is_sensitive"]) if row else False

    def _get_resource_deps(self, cursor, resource_id: str) -> list[str]:
        """Get resource dependencies from junction table."""
        cursor.execute(
            """
            SELECT depends_on_ref FROM terraform_resource_deps
            WHERE resource_id = ?
            """,
            (resource_id,),
        )
        return [row["depends_on_ref"] for row in cursor.fetchall()]

    def _write_to_graphs_db(self, graph: dict[str, Any]):
        """Write graph to graphs.db using XGraphStore.save_custom_graph()."""

        store_nodes = []
        for node in graph["nodes"]:
            store_nodes.append(
                {
                    "id": node["id"],
                    "file": node["file"],
                    "type": node["node_type"],
                    "lang": "terraform",
                    "metadata": {
                        "terraform_type": node["terraform_type"],
                        "name": node["name"],
                        "is_sensitive": node["is_sensitive"],
                        "has_public_exposure": node["has_public_exposure"],
                        **node["metadata"],
                    },
                }
            )

        store_edges = []
        for edge in graph["edges"]:
            store_edges.append(
                {
                    "source": edge["source"],
                    "target": edge["target"],
                    "type": edge["edge_type"],
                    "file": edge["file"],
                    "line": 0,
                    "expression": edge["expression"],
                    "metadata": edge["metadata"],
                }
            )

        store_graph = FidelityToken.attach_manifest(
            {"nodes": store_nodes, "edges": store_edges, "metadata": graph["metadata"]}
        )
        self.store.save_custom_graph(store_graph, graph_type="terraform_provisioning")

        logger.debug("Wrote Terraform provisioning graph to graphs.db")
