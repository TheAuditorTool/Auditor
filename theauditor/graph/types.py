"""Shared data structures for the graph module."""

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
    """Helper to create both a FORWARD edge and a REVERSE edge."""
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
