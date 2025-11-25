"""Terraform Provisioning Flow Graph Builder.

Constructs data flow graphs from Terraform resources, showing how variables,
resources, and outputs connect through dependencies and interpolations.

Architecture:
- Database-first: Reads from repo_index.db terraform_* tables
- Outputs to graphs.db via XGraphStore.save_custom_graph()
- Zero fallbacks: Missing data = empty graph (exposes indexer bugs)
- Same format as DFGBuilder (dataclass → asdict)

Usage:
    builder = TerraformGraphBuilder(db_path=".pf/repo_index.db")
    graph = builder.build_provisioning_flow_graph(root=".")
    # Returns: {'nodes': [...], 'edges': [...], 'metadata': {...}}
"""


import sqlite3
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..graph.store import XGraphStore
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ProvisioningNode:
    """Represents a node in the Terraform provisioning graph."""

    id: str  # Format: "resource_id", "variable_id", or "output_id"
    file: str
    node_type: str  # "resource", "variable", "output", "data"
    terraform_type: str  # e.g., "aws_db_instance", "string", etc.
    name: str
    is_sensitive: bool = False
    has_public_exposure: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvisioningEdge:
    """Represents a data flow edge in the provisioning graph."""

    source: str  # Source node ID
    target: str  # Target node ID
    file: str
    edge_type: str  # "variable_reference", "resource_dependency", "output_reference"
    expression: str = ""  # The interpolation expression
    metadata: dict[str, Any] = field(default_factory=dict)


class TerraformGraphBuilder:
    """Build Terraform provisioning flow graphs from repo_index.db.

    Follows DFGBuilder pattern exactly - database-first, zero fallbacks.
    """

    def __init__(self, db_path: str):
        """Initialize builder with database path.

        Args:
            db_path: Path to repo_index.db
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Initialize XGraphStore for writing to graphs.db
        graphs_db_path = self.db_path.parent / "graphs.db"
        self.store = XGraphStore(db_path=str(graphs_db_path))

    def build_provisioning_flow_graph(self, root: str = ".") -> dict[str, Any]:
        """Build provisioning flow graph from Terraform data.

        Queries terraform_* tables to construct a graph showing how
        variables flow through resources to outputs.

        Args:
            root: Project root (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata (same format as DFGBuilder)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, "ProvisioningNode"] = {}
        edges: list["ProvisioningEdge"] = []

        stats = {
            'total_resources': 0,
            'total_variables': 0,
            'total_outputs': 0,
            'edges_created': 0,
            'files_processed': 0,
        }

        # Step 1: Load all variables as source nodes
        cursor.execute("""
            SELECT variable_id, file_path, variable_name, variable_type, is_sensitive
            FROM terraform_variables
        """)

        for row in cursor.fetchall():
            stats['total_variables'] += 1
            nodes[row['variable_id']] = ProvisioningNode(
                id=row['variable_id'],
                file=row['file_path'],
                node_type='variable',
                terraform_type=row['variable_type'] or 'unknown',
                name=row['variable_name'],
                is_sensitive=bool(row['is_sensitive']),
                metadata={'source': 'terraform_variables'}
            )

        # Step 2: Load all resources as processing nodes
        cursor.execute("""
            SELECT resource_id, file_path, resource_type, resource_name,
                   properties_json, depends_on_json, sensitive_flags_json,
                   has_public_exposure
            FROM terraform_resources
        """)

        for row in cursor.fetchall():
            stats['total_resources'] += 1

            # Create resource node
            resource_id = row['resource_id']
            nodes[resource_id] = ProvisioningNode(
                id=resource_id,
                file=row['file_path'],
                node_type='resource',
                terraform_type=row['resource_type'],
                name=row['resource_name'],
                has_public_exposure=bool(row['has_public_exposure']),
                metadata={
                    'properties': json.loads(row['properties_json']) if row['properties_json'] else {},
                    'sensitive_properties': json.loads(row['sensitive_flags_json']) if row['sensitive_flags_json'] else [],
                }
            )

            # Parse properties to find variable references
            properties = json.loads(row['properties_json']) if row['properties_json'] else {}
            var_refs = self._extract_variable_references(properties)

            for var_name in var_refs:
                # Find variable node by name (may be in different file)
                var_id = self._find_variable_id(cursor, var_name, row['file_path'])
                if var_id and var_id in nodes:
                    edges.append(ProvisioningEdge(
                        source=var_id,
                        target=resource_id,
                        file=row['file_path'],
                        edge_type='variable_reference',
                        expression=f"var.{var_name}",
                        metadata={'property_path': self._find_property_path(properties, var_name)}
                    ))
                    stats['edges_created'] += 1

            # Parse depends_on to create explicit dependency edges
            depends_on = json.loads(row['depends_on_json']) if row['depends_on_json'] else []
            for dep_ref in depends_on:
                # dep_ref format: "aws_security_group.web" or full reference
                dep_id = self._resolve_resource_reference(cursor, dep_ref, row['file_path'])
                if dep_id and dep_id in nodes:
                    edges.append(ProvisioningEdge(
                        source=dep_id,
                        target=resource_id,
                        file=row['file_path'],
                        edge_type='resource_dependency',
                        expression=dep_ref,
                        metadata={'explicit_depends_on': True}
                    ))
                    stats['edges_created'] += 1

        # Step 3: Load outputs as sink nodes
        cursor.execute("""
            SELECT output_id, file_path, output_name, value_json, is_sensitive
            FROM terraform_outputs
        """)

        for row in cursor.fetchall():
            stats['total_outputs'] += 1
            output_id = row['output_id']

            nodes[output_id] = ProvisioningNode(
                id=output_id,
                file=row['file_path'],
                node_type='output',
                terraform_type='output',
                name=row['output_name'],
                is_sensitive=bool(row['is_sensitive']),
                metadata={'value_expr': row['value_json']}
            )

            # Parse output value to find resource/variable references
            value_json = row['value_json']
            if value_json:
                refs = self._extract_references_from_expression(value_json)
                for ref in refs:
                    source_id = self._resolve_reference(cursor, ref, row['file_path'])
                    if source_id and source_id in nodes:
                        edges.append(ProvisioningEdge(
                            source=source_id,
                            target=output_id,
                            file=row['file_path'],
                            edge_type='output_reference',
                            expression=ref,
                        ))
                        stats['edges_created'] += 1

        conn.close()

        # Count unique files
        files = {node.file for node in nodes.values()}
        stats['files_processed'] = len(files)

        # Convert to dict format (same as DFGBuilder)
        result = {
            'nodes': [asdict(node) for node in nodes.values()],
            'edges': [asdict(edge) for edge in edges],
            'metadata': {
                'root': str(Path(root).resolve()),
                'graph_type': 'terraform_provisioning',
                'stats': stats,
            }
        }

        # Write to graphs.db
        self._write_to_graphs_db(result)

        logger.info(
            f"Built Terraform provisioning graph: {stats['total_resources']} resources, "
            f"{stats['total_variables']} variables, {stats['total_outputs']} outputs, "
            f"{stats['edges_created']} edges"
        )

        return result

    def _extract_variable_references(self, properties: dict) -> set[str]:
        """Extract variable names from property values.

        Searches for Terraform variable interpolations:
        - Modern: var.NAME
        - Legacy: ${var.NAME}
        """
        var_names = set()

        def scan_value(val):
            if isinstance(val, str):
                # Look for ${var.NAME} or var.NAME patterns
                matches = re.findall(r'\$\{var\.(\w+)\}|var\.(\w+)', val)
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

    def _find_variable_id(self, cursor, var_name: str, current_file: str) -> str | None:
        """Find variable ID by name (may be in different file).

        Tries same file first, then any file (for module variables).
        """
        # Try same file first
        cursor.execute("""
            SELECT variable_id FROM terraform_variables
            WHERE variable_name = ? AND file_path = ?
        """, (var_name, current_file))
        row = cursor.fetchone()
        if row:
            return row['variable_id']

        # Try any file (module variables)
        cursor.execute("""
            SELECT variable_id FROM terraform_variables
            WHERE variable_name = ?
            LIMIT 1
        """, (var_name,))
        row = cursor.fetchone()
        return row['variable_id'] if row else None

    def _resolve_resource_reference(self, cursor, ref: str, current_file: str) -> str | None:
        """Resolve resource reference like 'aws_security_group.web' to resource_id.

        Args:
            cursor: Database cursor
            ref: Resource reference (e.g., "aws_security_group.web")
            current_file: Current file path

        Returns:
            resource_id or None if not found
        """
        # ref format: "resource_type.resource_name"
        parts = ref.split('.', 1)
        if len(parts) != 2:
            return None

        resource_type, resource_name = parts

        cursor.execute("""
            SELECT resource_id FROM terraform_resources
            WHERE resource_type = ? AND resource_name = ?
        """, (resource_type, resource_name))
        row = cursor.fetchone()
        return row['resource_id'] if row else None

    def _extract_references_from_expression(self, expr_json: str) -> set[str]:
        """Extract all Terraform references from an expression.

        Matches patterns:
        - aws_*.name (resource references)
        - var.name (variable references)
        - data.*.name (data source references)
        """
        refs = set()
        if not expr_json:
            return refs

        try:
            expr = json.loads(expr_json) if isinstance(expr_json, str) else expr_json
        except:
            expr = str(expr_json)

        # Match patterns: aws_*.name, var.name, data.*.name
        matches = re.findall(r'((?:aws_|azurerm_|google_)\w+\.\w+|var\.\w+|data\.\w+\.\w+)', str(expr))
        refs.update(matches)
        return refs

    def _resolve_reference(self, cursor, ref: str, current_file: str) -> str | None:
        """Resolve any Terraform reference to node ID.

        Args:
            cursor: Database cursor
            ref: Terraform reference (var.X, aws_Y.Z, etc.)
            current_file: Current file path

        Returns:
            Node ID or None if not found
        """
        if ref.startswith('var.'):
            var_name = ref.split('.', 1)[1]
            return self._find_variable_id(cursor, var_name, current_file)
        else:
            return self._resolve_resource_reference(cursor, ref, current_file)

    def _find_property_path(self, properties: dict, var_name: str) -> str | None:
        """Find which property path contains the variable reference.

        Args:
            properties: Resource properties dict
            var_name: Variable name to search for

        Returns:
            Property key or None if not found
        """
        # Simplified - just return first match
        for key, val in properties.items():
            if isinstance(val, str) and var_name in val:
                return key
        return None

    def _write_to_graphs_db(self, graph: dict[str, Any]):
        """Write graph to graphs.db using XGraphStore.save_custom_graph().

        Converts ProvisioningNode/Edge format to XGraphStore format.
        """
        # XGraphStore expects nodes/edges with specific fields
        store_nodes = []
        for node in graph['nodes']:
            store_nodes.append({
                'id': node['id'],
                'file': node['file'],
                'type': node['node_type'],
                'lang': 'terraform',
                'metadata': {
                    'terraform_type': node['terraform_type'],
                    'name': node['name'],
                    'is_sensitive': node['is_sensitive'],
                    'has_public_exposure': node['has_public_exposure'],
                    **node['metadata']
                }
            })

        store_edges = []
        for edge in graph['edges']:
            store_edges.append({
                'source': edge['source'],
                'target': edge['target'],
                'type': edge['edge_type'],
                'file': edge['file'],
                'metadata': {
                    'expression': edge['expression'],
                    **edge['metadata']
                }
            })

        # Write via XGraphStore.save_custom_graph()
        self.store.save_custom_graph({
            'nodes': store_nodes,
            'edges': store_edges,
            'metadata': graph['metadata']
        }, graph_type='terraform_provisioning')

        logger.debug(f"Wrote Terraform provisioning graph to graphs.db")
