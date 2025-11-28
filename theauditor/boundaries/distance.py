"""Boundary Distance Calculator."""

import sqlite3
from collections import deque
from pathlib import Path

from theauditor.graph.analyzer import XGraphAnalyzer
from theauditor.graph.store import XGraphStore


def calculate_distance(
    db_path: str, entry_file: str, entry_line: int, control_file: str, control_line: int
) -> int | None:
    """Calculate call-chain distance between entry point and control point."""

    graph_db_path = str(Path(db_path).parent / "graphs.db")

    store = XGraphStore(graph_db_path)
    call_graph = store.load_call_graph()

    if not call_graph.get("nodes") or not call_graph.get("edges"):
        return _calculate_distance_fallback(
            db_path, entry_file, entry_line, control_file, control_line
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
            return _calculate_distance_fallback(
                db_path, entry_file, entry_line, control_file, control_line
            )

        analyzer = XGraphAnalyzer(call_graph)
        path = analyzer.find_shortest_path(entry_node, control_node, call_graph)

        if path:
            return len(path) - 1

        return None

    finally:
        conn.close()


def _find_graph_node(graph: dict, file_path: str, func_name: str) -> str | None:
    """Find a node ID in the graph matching file and function name."""

    file_path_normalized = file_path.replace("\\", "/")

    for node in graph.get("nodes", []):
        node_id = node.get("id", "")
        node_file = node.get("file", "").replace("\\", "/")

        if node_file == file_path_normalized and func_name in node_id:
            return node_id

        if file_path_normalized in node_id and func_name in node_id:
            return node_id

        if node_id == f"{file_path_normalized}:{func_name}":
            return node_id

        if node_file == file_path_normalized and node_id.endswith(func_name):
            return node_id

    return None


def _calculate_distance_fallback(
    db_path: str, entry_file: str, entry_line: int, control_file: str, control_line: int
) -> int | None:
    """Fallback distance calculation using repo_index.db when graphs.db unavailable."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        entry_func = _find_containing_function(cursor, entry_file, entry_line)
        control_func = _find_containing_function(cursor, control_file, control_line)

        if not entry_func or not control_func:
            return None

        if entry_func == control_func:
            return 0

        return _bfs_distance_sql(cursor, entry_func, control_func)

    finally:
        conn.close()


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


def _bfs_distance_sql(cursor, start_func: str, target_func: str, max_depth: int = 10) -> int | None:
    """BFS through function_call_args (fallback when graphs.db unavailable)."""
    start_file, start_name = start_func.split(":", 1)
    target_file, target_name = target_func.split(":", 1)

    queue = deque([(start_func, 0)])
    visited = {start_func}

    while queue:
        current_func, distance = queue.popleft()

        if distance >= max_depth:
            continue

        current_file, current_name = current_func.split(":", 1)

        cursor.execute(
            """
            SELECT callee_function, callee_file_path
            FROM function_call_args
            WHERE caller_function = ?
              AND file = ?
              AND callee_function IS NOT NULL
              AND callee_file_path IS NOT NULL
        """,
            (current_name, current_file),
        )

        for callee, callee_file in cursor.fetchall():
            callee_qualified = f"{callee_file}:{callee}"

            if callee_qualified == target_func:
                return distance + 1

            if callee_qualified not in visited:
                visited.add(callee_qualified)
                queue.append((callee_qualified, distance + 1))

    return None


def find_all_paths_to_controls(
    db_path: str, entry_file: str, entry_line: int, control_patterns: list[str], max_depth: int = 5
) -> list[dict]:
    """Find all control points reachable from entry point and their distances."""
    graph_db_path = str(Path(db_path).parent / "graphs.db")

    store = XGraphStore(graph_db_path)
    call_graph = store.load_call_graph()

    if call_graph.get("nodes") and call_graph.get("edges"):
        return _find_controls_via_graph(
            db_path, call_graph, entry_file, entry_line, control_patterns, max_depth
        )

    return _find_controls_via_sql(db_path, entry_file, entry_line, control_patterns, max_depth)


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
            return _find_controls_via_sql(
                db_path, entry_file, entry_line, control_patterns, max_depth
            )

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
    """Get file path from node metadata."""
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node.get("file")
    return None


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


def _find_controls_via_sql(
    db_path: str, entry_file: str, entry_line: int, control_patterns: list[str], max_depth: int
) -> list[dict]:
    """Fallback: Find control points using SQL BFS (no interceptor edges)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        entry_func = _find_containing_function(cursor, entry_file, entry_line)
        if not entry_func:
            return results

        entry_file_part, entry_name = entry_func.split(":", 1)

        queue = deque([(entry_func, 0, [entry_name])])
        visited = {entry_func}

        while queue:
            current_func, distance, path = queue.popleft()

            if distance >= max_depth:
                continue

            current_file, current_name = current_func.split(":", 1)

            cursor.execute(
                """
                SELECT callee_function, callee_file_path, line
                FROM function_call_args
                WHERE caller_function = ?
                  AND file = ?
                  AND callee_function IS NOT NULL
            """,
                (current_name, current_file),
            )

            for callee, callee_file, call_line in cursor.fetchall():
                is_control = any(pattern.lower() in callee.lower() for pattern in control_patterns)

                if is_control:
                    cursor.execute(
                        """
                        SELECT line FROM symbols
                        WHERE path = ? AND name = ?
                          AND type IN ('function', 'method', 'arrow_function')
                        LIMIT 1
                    """,
                        (callee_file, callee),
                    )

                    def_result = cursor.fetchone()
                    callee_line = def_result[0] if def_result else call_line

                    results.append(
                        {
                            "control_function": callee,
                            "control_file": callee_file,
                            "control_line": callee_line,
                            "distance": distance + 1,
                            "path": path + [callee],
                        }
                    )

                callee_qualified = f"{callee_file}:{callee}"
                if callee_qualified not in visited:
                    visited.add(callee_qualified)
                    queue.append((callee_qualified, distance + 1, path + [callee]))

    finally:
        conn.close()

    return results


def measure_boundary_quality(controls: list[dict]) -> dict:
    """Assess boundary quality based on control distances."""
    if not controls:
        return {
            "quality": "missing",
            "reason": "No validation, sanitization, or checks found in call chain",
            "facts": [
                "Entry point accepts external data",
                "No validation control detected within search depth",
                "Data flows to downstream functions without validation gate",
            ],
        }

    if len(controls) == 1:
        distance = controls[0]["distance"]
        control_func = controls[0]["control_function"]

        if distance == 0:
            return {
                "quality": "clear",
                "reason": f"Single control point '{control_func}' at distance 0 (same function as entry)",
                "facts": [
                    "Validation occurs in entry function",
                    "External data validated before use",
                    "No intermediate functions between entry and validation",
                ],
            }
        elif distance <= 2:
            return {
                "quality": "acceptable",
                "reason": f"Single control point '{control_func}' at distance {distance}",
                "facts": [
                    f"Validation occurs {distance} function call(s) after entry",
                    f"Data flows through {distance} intermediate function(s) before validation",
                    "Single validation control point detected",
                ],
            }
        else:
            return {
                "quality": "fuzzy",
                "reason": f"Single control point '{control_func}' at distance {distance}",
                "facts": [
                    f"Validation occurs {distance} function calls after entry",
                    f"Data flows through {distance} intermediate functions before validation control",
                    f"Distance {distance} creates {distance} potential code paths without validation",
                ],
            }
    else:
        distances = [c["distance"] for c in controls]
        min_dist = min(distances)
        max_dist = max(distances)
        control_names = [c["control_function"] for c in controls]

        return {
            "quality": "fuzzy",
            "reason": f"Multiple control points detected: {', '.join(control_names)}",
            "facts": [
                f"{len(controls)} different validation controls found",
                f"Control distances range from {min_dist} to {max_dist}",
                "Multiple validation points indicate distributed boundary enforcement",
                "Different code paths may encounter different validation controls",
            ],
        }
