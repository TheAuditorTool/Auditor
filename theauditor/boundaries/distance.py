"""Boundary Distance Calculator."""

import sqlite3
from collections import deque
from pathlib import Path

from theauditor.graph.analyzer import XGraphAnalyzer
from theauditor.graph.store import XGraphStore


def _normalize_path(path: str) -> str:
    """Normalize path to forward slashes for consistent comparison."""
    return path.replace("\\", "/") if path else ""


def _build_graph_index(graph: dict) -> None:
    """Build O(1) lookup indexes for graph nodes. Caches in graph dict."""
    if "_node_by_id" in graph:
        return

    node_by_id: dict[str, dict] = {}
    nodes_by_file: dict[str, list[dict]] = {}

    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        node_file = _normalize_path(node.get("file", ""))

        node_by_id[node_id] = node

        if node_file:
            if node_file not in nodes_by_file:
                nodes_by_file[node_file] = []
            nodes_by_file[node_file].append(node)

    graph["_node_by_id"] = node_by_id
    graph["_nodes_by_file"] = nodes_by_file


def calculate_distance(
    db_path: str, entry_file: str, entry_line: int, control_file: str, control_line: int
) -> int | None:
    """Calculate call-chain distance between entry point and control point."""

    graph_db_path = str(Path(db_path).parent / "graphs.db")

    store = XGraphStore(graph_db_path)
    call_graph = store.load_call_graph()

    if not call_graph.get("nodes") or not call_graph.get("edges"):
        raise RuntimeError(
            f"Graph DB empty or missing at {graph_db_path}. "
            "Run 'aud graph build' to generate the call graph."
        )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        entry_func = _find_containing_function(cursor, entry_file, entry_line)
        control_func = _find_containing_function(cursor, control_file, control_line)

        if not entry_func or not control_func:
            return None

        if entry_func == control_func:
            return 0

        entry_node = _find_graph_node(call_graph, entry_file, entry_func.split(":")[-1])
        control_node = _find_graph_node(call_graph, control_file, control_func.split(":")[-1])

        if not entry_node or not control_node:
            return None

        analyzer = XGraphAnalyzer(call_graph)
        path = analyzer.find_shortest_path(entry_node, control_node, call_graph)

        if path:
            return len(path) - 1

        return None

    finally:
        conn.close()


def _find_graph_node(graph: dict, file_path: str, func_name: str) -> str | None:
    """Find a node ID in the graph matching file and function name.

    Uses indexed lookup (O(1) file lookup + O(k) where k = nodes in that file).
    """
    _build_graph_index(graph)

    file_path_normalized = _normalize_path(file_path)
    nodes_by_file = graph.get("_nodes_by_file", {})

    file_nodes = nodes_by_file.get(file_path_normalized, [])

    for node in file_nodes:
        node_id = node.get("id", "")

        if func_name in node_id:
            return node_id

        if node_id.endswith(func_name):
            return node_id

    node_by_id = graph.get("_node_by_id", {})
    target_id = f"{file_path_normalized}:{func_name}"
    if target_id in node_by_id:
        return target_id

    return None


def _find_containing_function(cursor, file_path: str, line: int) -> str | None:
    """Find function containing the given file:line location."""
    cursor.execute(
        """
        SELECT name, type, line, end_line
        FROM symbols
        WHERE path = ?
          AND type IN ('function', 'method', 'arrow_function')
          AND line <= ?
          AND (end_line >= ? OR end_line IS NULL)
        ORDER BY line DESC
        LIMIT 1
    """,
        (file_path, line, line),
    )

    result = cursor.fetchone()
    if result:
        func_name = result[0]
        return f"{file_path}:{func_name}"

    return None


def find_all_paths_to_controls(
    db_path: str,
    entry_file: str,
    entry_line: int,
    control_patterns: list[str],
    max_depth: int = 5,
    call_graph: dict | None = None,
) -> list[dict]:
    """Find all control points reachable from entry point and their distances.

    Args:
        db_path: Path to repo_index.db
        entry_file: Entry point file path
        entry_line: Entry point line number
        control_patterns: Patterns to match control functions
        max_depth: Maximum traversal depth
        call_graph: Pre-loaded call graph (pass to avoid repeated disk I/O)

    Raises RuntimeError if graph is missing - run 'aud graph build' first.
    """
    if call_graph is None:
        graph_db_path = str(Path(db_path).parent / "graphs.db")
        store = XGraphStore(graph_db_path)
        call_graph = store.load_call_graph()

        if not call_graph.get("nodes") or not call_graph.get("edges"):
            raise RuntimeError(
                f"Graph DB empty or missing at {graph_db_path}. "
                "Run 'aud graph build' to generate the call graph."
            )

    return _find_controls_via_graph(
        db_path, call_graph, entry_file, entry_line, control_patterns, max_depth
    )


def _find_controls_via_graph(
    db_path: str,
    call_graph: dict,
    entry_file: str,
    entry_line: int,
    control_patterns: list[str],
    max_depth: int,
) -> list[dict]:
    """Find control points using graph traversal (includes interceptor edges)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        entry_func = _find_containing_function(cursor, entry_file, entry_line)
        if not entry_func:
            return results

        entry_name = entry_func.split(":")[-1]
        entry_node = _find_graph_node(call_graph, entry_file, entry_name)

        if not entry_node:
            return results

        adj = {}
        for edge in call_graph.get("edges", []):
            source = edge["source"]
            target = edge["target"]
            if source not in adj:
                adj[source] = []
            adj[source].append(target)

        queue = deque([(entry_node, 0, [entry_name])])
        visited = {entry_node}

        while queue:
            current_node, distance, path = queue.popleft()

            if distance >= max_depth:
                continue

            for neighbor in adj.get(current_node, []):
                if neighbor in visited:
                    continue

                visited.add(neighbor)

                neighbor_name = _extract_func_name(neighbor)
                neighbor_file = _extract_file_from_node(call_graph, neighbor)
                new_path = path + [neighbor_name]

                is_control = any(
                    pattern.lower() in neighbor_name.lower() for pattern in control_patterns
                )

                if is_control:
                    control_line = _get_function_line(cursor, neighbor_file, neighbor_name)

                    results.append(
                        {
                            "control_function": neighbor_name,
                            "control_file": neighbor_file or "unknown",
                            "control_line": control_line or 0,
                            "distance": distance + 1,
                            "path": new_path,
                        }
                    )

                queue.append((neighbor, distance + 1, new_path))

    finally:
        conn.close()

    return results


def _extract_func_name(node_id: str) -> str:
    """Extract function name from node ID."""
    # Node IDs can be: "file:func", "file::type::name::param", etc.
    if "::" in node_id:
        parts = node_id.split("::")

        for part in reversed(parts):
            if part and not part.startswith("/") and not part.endswith((".js", ".ts", ".py")):
                return part
    if ":" in node_id:
        return node_id.split(":")[-1]
    return node_id


def _extract_file_from_node(graph: dict, node_id: str) -> str | None:
    """Get file path from node metadata. O(1) indexed lookup."""
    _build_graph_index(graph)
    node = graph.get("_node_by_id", {}).get(node_id)
    return node.get("file") if node else None


def _get_function_line(cursor, file_path: str | None, func_name: str) -> int | None:
    """Get function definition line from symbols table."""
    if not file_path:
        return None

    cursor.execute(
        """
        SELECT line FROM symbols
        WHERE path = ? AND name = ?
          AND type IN ('function', 'method', 'arrow_function')
        LIMIT 1
    """,
        (file_path, func_name),
    )

    result = cursor.fetchone()
    return result[0] if result else None


def measure_boundary_quality(controls: list[dict], accepts_input: bool = True) -> dict:
    """Assess boundary quality. Binary: validated or unvalidated.

    Args:
        controls: List of validation control points found
        accepts_input: Whether the route accepts user input (req.body, req.query, etc.)

    Returns:
        Quality assessment with severity level.
    """
    if not accepts_input:
        return {
            "quality": "no_input",
            "severity": "INFO",
            "reason": "Route does not accept user input",
            "facts": ["No user input detected in handler"],
        }

    if not controls:
        return {
            "quality": "unvalidated",
            "severity": "MEDIUM",
            "reason": "Route accepts input but has no validation middleware",
            "facts": [
                "User input detected",
                "No validation control found",
            ],
        }

    validators = [c["control_function"] for c in controls]
    min_distance = min(c["distance"] for c in controls)

    return {
        "quality": "validated",
        "severity": "PASS",
        "reason": f"Protected by: {', '.join(validators)}",
        "facts": [f"Found {len(controls)} validation control(s)"],
        "metrics": {
            "validator_count": len(controls),
            "min_distance": min_distance,
        },
    }
