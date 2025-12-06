"""Bash Pipe Strategy - Handles Bash data flow through pipes, sources, and subshells."""

import sqlite3
from dataclasses import asdict
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken

from ..types import DFGEdge, DFGNode, create_bidirectional_edges
from .base import GraphStrategy


class BashPipeStrategy(GraphStrategy):
    """Strategy for building Bash-specific data flow edges.

    Creates three edge types:
    1. pipe_flow: stdout of command N -> stdin of command N+1
    2. source_include: source statement -> sourced file
    3. subshell_capture: subshell output -> capture variable
    """

    def build(self, db_path: str, project_root: str) -> dict[str, Any]:
        """Build pipe flow, source include, and subshell capture edges."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nodes: dict[str, DFGNode] = {}
        edges: list[DFGEdge] = []

        stats = {
            "pipe_edges": 0,
            "source_edges": 0,
            "capture_edges": 0,
            "pipelines_processed": 0,
        }

        cursor.execute("""
            SELECT file, line, pipeline_id, position, command_text, containing_function
            FROM bash_pipes
            ORDER BY file, pipeline_id, position
        """)

        current_pipeline: tuple[str, int] | None = None
        prev_node_id: str | None = None

        for row in cursor.fetchall():
            file = row["file"]
            line = row["line"]
            pipeline_id = row["pipeline_id"]
            position = row["position"]
            command_text = row["command_text"]
            containing_function = row["containing_function"]

            if (file, pipeline_id) != current_pipeline:
                current_pipeline = (file, pipeline_id)
                prev_node_id = None
                stats["pipelines_processed"] += 1

            node_id = f"bash:pipe:{file}:{line}:{position}"

            if node_id not in nodes:
                label = command_text[:50] + "..." if len(command_text) > 50 else command_text
                nodes[node_id] = DFGNode(
                    id=node_id,
                    file=file,
                    variable_name=f"pipe_{pipeline_id}_{position}",
                    scope=containing_function or "global",
                    type="bash_pipe_command",
                    metadata={
                        "line": line,
                        "pipeline_id": pipeline_id,
                        "position": position,
                        "command_text": command_text,
                        "label": label,
                    },
                )

            if prev_node_id:
                new_edges = create_bidirectional_edges(
                    source=prev_node_id,
                    target=node_id,
                    edge_type="pipe_flow",
                    file=file,
                    line=line,
                    expression="|",
                    function=containing_function or "global",
                    metadata={"pipeline_id": pipeline_id},
                )
                edges.extend(new_edges)
                stats["pipe_edges"] += len(new_edges)

            prev_node_id = node_id

        cursor.execute("""
            SELECT file, line, sourced_path, syntax, has_variable_expansion, containing_function
            FROM bash_sources
        """)

        for row in cursor.fetchall():
            file = row["file"]
            line = row["line"]
            sourced_path = row["sourced_path"]
            syntax = row["syntax"]
            has_variable_expansion = row["has_variable_expansion"]
            containing_function = row["containing_function"]

            source_node_id = f"bash:source:{file}:{line}"
            target_node_id = f"bash:file:{sourced_path}"

            if source_node_id not in nodes:
                label = f"{syntax} {sourced_path}"
                nodes[source_node_id] = DFGNode(
                    id=source_node_id,
                    file=file,
                    variable_name=f"source_{line}",
                    scope=containing_function or "global",
                    type="bash_source_statement",
                    metadata={
                        "line": line,
                        "sourced_path": sourced_path,
                        "syntax": syntax,
                        "has_variable_expansion": bool(has_variable_expansion),
                        "label": label,
                    },
                )

            if target_node_id not in nodes:
                nodes[target_node_id] = DFGNode(
                    id=target_node_id,
                    file=sourced_path,
                    variable_name="sourced_file",
                    scope="global",
                    type="bash_sourced_file",
                    metadata={
                        "sourced_path": sourced_path,
                        "label": sourced_path,
                    },
                )

            new_edges = create_bidirectional_edges(
                source=source_node_id,
                target=target_node_id,
                edge_type="source_include",
                file=file,
                line=line,
                expression=f"{syntax} {sourced_path}",
                function=containing_function or "global",
                metadata={
                    "syntax": syntax,
                    "has_variable_expansion": bool(has_variable_expansion),
                },
            )
            edges.extend(new_edges)
            stats["source_edges"] += len(new_edges)

        cursor.execute("""
            SELECT file, line, syntax, command_text, capture_target, containing_function
            FROM bash_subshells
            WHERE capture_target IS NOT NULL
        """)

        for row in cursor.fetchall():
            file = row["file"]
            line = row["line"]
            syntax = row["syntax"]
            command_text = row["command_text"]
            capture_target = row["capture_target"]
            containing_function = row["containing_function"]

            subshell_node_id = f"bash:subshell:{file}:{line}"
            variable_node_id = f"bash:var:{file}:{containing_function or 'global'}:{capture_target}"

            if subshell_node_id not in nodes:
                if syntax == "backtick":
                    label = (
                        f"`{command_text[:30]}...`"
                        if len(command_text) > 30
                        else f"`{command_text}`"
                    )
                else:
                    label = (
                        f"$({command_text[:30]}...)"
                        if len(command_text) > 30
                        else f"$({command_text})"
                    )

                nodes[subshell_node_id] = DFGNode(
                    id=subshell_node_id,
                    file=file,
                    variable_name=f"subshell_{line}",
                    scope=containing_function or "global",
                    type="bash_subshell",
                    metadata={
                        "line": line,
                        "syntax": syntax,
                        "command_text": command_text,
                        "label": label,
                    },
                )

            if variable_node_id not in nodes:
                nodes[variable_node_id] = DFGNode(
                    id=variable_node_id,
                    file=file,
                    variable_name=capture_target,
                    scope=containing_function or "global",
                    type="bash_variable",
                    metadata={
                        "capture_target": capture_target,
                        "label": f"${capture_target}",
                    },
                )

            new_edges = create_bidirectional_edges(
                source=subshell_node_id,
                target=variable_node_id,
                edge_type="subshell_capture",
                file=file,
                line=line,
                expression=f"{capture_target}=$({command_text[:50]})",
                function=containing_function or "global",
                metadata={
                    "syntax": syntax,
                    "capture_target": capture_target,
                },
            )
            edges.extend(new_edges)
            stats["capture_edges"] += len(new_edges)

        conn.close()

        result = {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
            "metadata": {
                "graph_type": "bash_pipes",
                "stats": stats,
            },
        }
        return FidelityToken.attach_manifest(result)
