"""Shared data structures for the graph module.

This module contains the core data types used by:
- DFGBuilder (the orchestrator)
- All GraphStrategy implementations (Python ORM, Node Express, etc.)

Extracted to prevent circular imports when strategies need to create nodes/edges.

Architecture:
- DFGNode: Represents a variable in the data flow graph
- DFGEdge: Represents a data flow edge between variables
- create_bidirectional_edges: Helper to create forward + reverse edges
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DFGNode:
    """Represents a variable in the data flow graph."""

    id: str
    file: str
    variable_name: str
    scope: str
    type: str = "variable"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DFGEdge:
    """Represents a data flow edge in the graph."""

    source: str
    target: str
    file: str
    line: int
    type: str = "assignment"
    expression: str = ""
    function: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def create_bidirectional_edges(
    source: str,
    target: str,
    edge_type: str,
    file: str,
    line: int,
    expression: str,
    function: str,
    metadata: dict[str, Any] = None,
) -> list[DFGEdge]:
    """
    Helper to create both a FORWARD edge and a REVERSE edge.

    Forward: Source -> Target (type)
    Reverse: Target -> Source (type_reverse)

    This enables backward traversal algorithms (IFDS) to navigate the graph
    by querying outgoing edges from a sink.

    Args:
        source: Source node ID
        target: Target node ID
        edge_type: Type of edge (assignment, return, etc.)
        file: File containing this edge
        line: Line number
        expression: Expression for this edge
        function: Function context
        metadata: Additional metadata dict

    Returns:
        List containing both forward and reverse edges
    """
    if metadata is None:
        metadata = {}

    edges = []

    forward = DFGEdge(
        source=source,
        target=target,
        type=edge_type,
        file=file,
        line=line,
        expression=expression,
        function=function,
        metadata=metadata,
    )
    edges.append(forward)

    reverse_meta = metadata.copy()
    reverse_meta["is_reverse"] = True
    reverse_meta["original_type"] = edge_type

    reverse = DFGEdge(
        source=target,
        target=source,
        type=f"{edge_type}_reverse",
        file=file,
        line=line,
        expression=f"REV: {expression[:190]}" if expression else "REVERSE",
        function=function,
        metadata=reverse_meta,
    )
    edges.append(reverse)

    return edges
