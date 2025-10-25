"""Data Flow Graph Builder - constructs variable data flow graphs.

This module builds data flow graphs from normalized assignment and return data
stored in the database. It tracks how data flows between variables through
assignments and function returns.

Architecture:
- Database-first: NO fallbacks, NO JSON parsing
- Reads from normalized junction tables (assignment_sources, function_return_sources)
- Returns same format as builder.py (dataclass -> asdict)
- Zero tolerance for missing data - hard fail exposes bugs
"""

import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set
from collections import defaultdict

import click


@dataclass
class DFGNode:
    """Represents a variable in the data flow graph."""

    id: str  # Format: "file::variable" or "file::function::variable"
    file: str
    variable_name: str
    scope: str  # function name or "global"
    type: str = "variable"  # variable, parameter, return_value
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DFGEdge:
    """Represents a data flow edge in the graph."""

    source: str  # Source variable ID
    target: str  # Target variable ID
    file: str  # File containing this edge (moved before defaults)
    line: int  # Line number (moved before defaults)
    type: str = "assignment"  # assignment, return, parameter
    expression: str = ""  # The assignment expression
    function: str = ""  # Function context
    metadata: Dict[str, Any] = field(default_factory=dict)


class DFGBuilder:
    """Build data flow graphs from normalized database tables.

    This builder operates in database-first mode, reading all assignment and
    return data from the normalized junction tables. NO JSON parsing exists.
    If data is missing, the query returns empty - exposing indexer bugs.
    """

    def __init__(self, db_path: str):
        """Initialize DFG builder with database path.

        Args:
            db_path: Path to repo_index.db database
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def build_assignment_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build data flow graph from variable assignments.

        Queries the normalized assignments + assignment_sources tables to construct
        a graph showing how data flows through variable assignments.

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata (same format as builder.py)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_assignments': 0,
            'assignments_with_sources': 0,
            'edges_created': 0,
            'unique_variables': 0
        }

        # Query normalized assignments with their source variables
        # NO JSON PARSING - uses JOIN on normalized junction table
        cursor.execute("""
            SELECT
                a.file,
                a.line,
                a.target_var,
                a.source_expr,
                a.in_function,
                asrc.source_var_name
            FROM assignments a
            LEFT JOIN assignment_sources asrc
                ON a.file = asrc.assignment_file
                AND a.line = asrc.assignment_line
                AND a.target_var = asrc.assignment_target
            ORDER BY a.file, a.line
        """)

        with click.progressbar(
            cursor.fetchall(),
            label="Building data flow graph",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None
        ) as assignments:
            for row in assignments:
                stats['total_assignments'] += 1

                file = row['file']
                line = row['line']
                target_var = row['target_var']
                source_expr = row['source_expr']
                in_function = row['in_function']
                source_var_name = row['source_var_name']

                # Create target node (variable being assigned to)
                target_scope = in_function if in_function else "global"
                target_id = f"{file}::{target_scope}::{target_var}"

                if target_id not in nodes:
                    nodes[target_id] = DFGNode(
                        id=target_id,
                        file=file,
                        variable_name=target_var,
                        scope=target_scope,
                        type="variable",
                        metadata={
                            "first_assignment_line": line,
                            "assignment_count": 0
                        }
                    )

                # Use .get() with default - node may have been created as source first
                nodes[target_id].metadata["assignment_count"] = nodes[target_id].metadata.get("assignment_count", 0) + 1

                # If there's a source variable, create edge
                if source_var_name:
                    stats['assignments_with_sources'] += 1

                    # Create source node
                    source_scope = in_function if in_function else "global"
                    source_id = f"{file}::{source_scope}::{source_var_name}"

                    if source_id not in nodes:
                        nodes[source_id] = DFGNode(
                            id=source_id,
                            file=file,
                            variable_name=source_var_name,
                            scope=source_scope,
                            type="variable",
                            metadata={"usage_count": 0}
                        )

                    nodes[source_id].metadata["usage_count"] = nodes[source_id].metadata.get("usage_count", 0) + 1

                    # Create edge: source_var -> target_var
                    edge = DFGEdge(
                        source=source_id,
                        target=target_id,
                        type="assignment",
                        file=file,
                        line=line,
                        expression=source_expr[:200] if source_expr else "",  # Truncate long expressions
                        function=in_function if in_function else "global",
                        metadata={}
                    )
                    edges.append(edge)
                    stats['edges_created'] += 1

        conn.close()

        stats['unique_variables'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "data_flow",
                "stats": stats
            }
        }

    def build_return_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build data flow graph from function returns.

        Queries the normalized function_returns + function_return_sources tables
        to construct a graph showing how data flows through return statements.

        Args:
            root: Project root directory (for metadata only)

        Returns:
            Dict with nodes, edges, and metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: Dict[str, DFGNode] = {}
        edges: List[DFGEdge] = []

        stats = {
            'total_returns': 0,
            'returns_with_vars': 0,
            'edges_created': 0,
            'unique_variables': 0
        }

        # Query normalized function returns with their return variables
        # NO JSON PARSING - uses JOIN on normalized junction table
        cursor.execute("""
            SELECT
                fr.file,
                fr.line,
                fr.function_name,
                fr.return_expr,
                frsrc.return_var_name
            FROM function_returns fr
            LEFT JOIN function_return_sources frsrc
                ON fr.file = frsrc.return_file
                AND fr.line = frsrc.return_line
                AND fr.function_name = frsrc.return_function
            ORDER BY fr.file, fr.line
        """)

        with click.progressbar(
            cursor.fetchall(),
            label="Building return flow graph",
            show_pos=True,
            show_percent=True,
            item_show_func=lambda x: f"{x['file']}:{x['line']}" if x else None
        ) as returns:
            for row in returns:
                stats['total_returns'] += 1

                file = row['file']
                line = row['line']
                function_name = row['function_name']
                return_expr = row['return_expr']
                return_var_name = row['return_var_name']

                # Create return value node
                return_id = f"{file}::{function_name}::return"

                if return_id not in nodes:
                    nodes[return_id] = DFGNode(
                        id=return_id,
                        file=file,
                        variable_name=f"{function_name}_return",
                        scope=function_name,
                        type="return_value",
                        metadata={
                            "return_line": line,
                            "return_expr": return_expr[:200] if return_expr else ""
                        }
                    )

                # If there's a return variable, create edge
                if return_var_name:
                    stats['returns_with_vars'] += 1

                    # Create source variable node (variable being returned)
                    var_id = f"{file}::{function_name}::{return_var_name}"

                    if var_id not in nodes:
                        nodes[var_id] = DFGNode(
                            id=var_id,
                            file=file,
                            variable_name=return_var_name,
                            scope=function_name,
                            type="variable",
                            metadata={"returned": True}
                        )

                    # Create edge: variable -> return_value
                    edge = DFGEdge(
                        source=var_id,
                        target=return_id,
                        type="return",
                        file=file,
                        line=line,
                        expression=return_expr[:200] if return_expr else "",
                        function=function_name,
                        metadata={}
                    )
                    edges.append(edge)
                    stats['edges_created'] += 1

        conn.close()

        stats['unique_variables'] = len(nodes)

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "return_flow",
                "stats": stats
            }
        }

    def build_unified_flow_graph(self, root: str = ".") -> Dict[str, Any]:
        """Build unified data flow graph combining assignments and returns.

        Args:
            root: Project root directory

        Returns:
            Combined graph with all data flow edges
        """
        # Build both graphs
        assignment_graph = self.build_assignment_flow_graph(root)
        return_graph = self.build_return_flow_graph(root)

        # Merge nodes (dedup by id)
        nodes = {}
        for node in assignment_graph["nodes"]:
            nodes[node["id"]] = node
        for node in return_graph["nodes"]:
            nodes[node["id"]] = node

        # Combine edges
        edges = assignment_graph["edges"] + return_graph["edges"]

        # Merge stats
        stats = {
            "assignment_stats": assignment_graph["metadata"]["stats"],
            "return_stats": return_graph["metadata"]["stats"],
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "metadata": {
                "root": str(Path(root).resolve()),
                "graph_type": "unified_data_flow",
                "stats": stats
            }
        }

    def get_data_dependencies(self, file: str, variable: str,
                              function: str = None) -> Dict[str, Any]:
        """Get all variables that flow into the given variable.

        Performs a backwards traversal from the target variable to find all
        source variables in its data dependency chain.

        Args:
            file: File path
            variable: Variable name
            function: Function scope (None for global)

        Returns:
            Dict with dependencies and flow paths
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        scope = function if function else "global"
        target_id = f"{file}::{scope}::{variable}"

        # Build adjacency list from assignments
        graph: Dict[str, Set[str]] = defaultdict(set)

        cursor.execute("""
            SELECT
                a.file,
                a.target_var,
                a.in_function,
                asrc.source_var_name
            FROM assignments a
            LEFT JOIN assignment_sources asrc
                ON a.file = asrc.assignment_file
                AND a.line = asrc.assignment_line
                AND a.target_var = asrc.assignment_target
            WHERE asrc.source_var_name IS NOT NULL
        """)

        for row in cursor.fetchall():
            f = row['file']
            sc = row['in_function'] if row['in_function'] else "global"
            target = f"{f}::{sc}::{row['target_var']}"
            source = f"{f}::{sc}::{row['source_var_name']}"

            # Edge: source -> target (for backwards traversal, we reverse this)
            graph[target].add(source)

        conn.close()

        # BFS backwards from target to find all dependencies
        dependencies = set()
        visited = set()
        queue = [target_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            # Get all variables that flow into current
            sources = graph.get(current, set())
            for source in sources:
                if source not in visited:
                    dependencies.add(source)
                    queue.append(source)

        return {
            "target": target_id,
            "dependencies": list(dependencies),
            "dependency_count": len(dependencies)
        }
