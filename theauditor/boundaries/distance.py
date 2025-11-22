"""Boundary Distance Calculator.

Calculates call-chain distance between entry points and control points
using the call_graph table. This is the core metric for boundary analysis.

Distance Semantics:
    0 = Control at entry point (PERFECT - validation in function signature)
    1 = Control in first call (GOOD - validation as first line)
    2 = Control two calls deep (ACCEPTABLE - validation in service layer)
    3+ = Control too far (BAD - validation after data has spread)
    None = No control found (CRITICAL - missing validation entirely)

Example:
    @app.post('/user')
    def create_user(request):           # ← Entry point
        data = validate(request.json)    # ← Distance 0 (same function)
        user_service.create(data)
            def create(data):
                db.insert('users', data)

Truth Courier Design: Reports factual distance measurements, not recommendations.
"""


import sqlite3
from typing import Optional, List, Tuple, Dict
from collections import deque


def calculate_distance(
    db_path: str,
    entry_file: str,
    entry_line: int,
    control_file: str,
    control_line: int
) -> int | None:
    """
    Calculate call-chain distance between entry point and control point.

    Uses BFS (Breadth-First Search) on call_graph to find shortest path.

    Args:
        db_path: Path to repo_index.db
        entry_file: File containing entry point (e.g., 'src/routes/users.js')
        entry_line: Line number of entry point
        control_file: File containing control point (e.g., 'src/validators/user.js')
        control_line: Line number of control point

    Returns:
        Distance as integer, or None if no path exists

    Example:
        >>> calculate_distance(
        ...     db_path='/project/.pf/repo_index.db',
        ...     entry_file='src/routes/users.js',
        ...     entry_line=34,
        ...     control_file='src/routes/users.js',
        ...     control_line=35
        ... )
        0  # Control point is in same function (distance 0)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Find function containing entry point
        entry_function = _find_containing_function(cursor, entry_file, entry_line)
        if not entry_function:
            return None

        # Find function containing control point
        control_function = _find_containing_function(cursor, control_file, control_line)
        if not control_function:
            return None

        # Same function? Distance is 0
        if entry_function == control_function:
            return 0

        # BFS through call graph
        return _bfs_distance(cursor, entry_function, control_function)

    finally:
        conn.close()


def _find_containing_function(cursor, file_path: str, line: int) -> str | None:
    """
    Find function containing the given file:line location.

    Uses symbols table to find function definitions that span the line.
    """
    cursor.execute("""
        SELECT name, type, line, end_line
        FROM symbols
        WHERE path = ?
          AND type IN ('function', 'method', 'arrow_function')
          AND line <= ?
          AND (end_line >= ? OR end_line IS NULL)
        ORDER BY line DESC
        LIMIT 1
    """, (file_path, line, line))

    result = cursor.fetchone()
    if result:
        func_name, func_type, start, end = result
        # Return qualified name (path:function for uniqueness)
        return f"{file_path}:{func_name}"

    return None


def _bfs_distance(cursor, start_func: str, target_func: str, max_depth: int = 10) -> int | None:
    """
    BFS through call graph to find distance from start to target.

    Args:
        cursor: Database cursor
        start_func: Starting function (qualified name)
        target_func: Target function (qualified name)
        max_depth: Maximum search depth (prevents infinite loops)

    Returns:
        Distance as integer, or None if unreachable within max_depth
    """
    # Extract file:function components
    start_file, start_name = start_func.split(':', 1)
    target_file, target_name = target_func.split(':', 1)

    # BFS queue: (current_function, distance)
    queue = deque([(start_func, 0)])
    visited = {start_func}

    while queue:
        current_func, distance = queue.popleft()

        # Max depth check
        if distance >= max_depth:
            continue

        # Extract current components
        current_file, current_name = current_func.split(':', 1)

        # Query function_call_args for functions called FROM current function
        cursor.execute("""
            SELECT callee_function, callee_file_path
            FROM function_call_args
            WHERE caller_function = ?
              AND file = ?
              AND callee_function IS NOT NULL
              AND callee_file_path IS NOT NULL
        """, (current_name, current_file))

        for callee, callee_file in cursor.fetchall():
            callee_qualified = f"{callee_file}:{callee}"

            # Found target?
            if callee_qualified == target_func:
                return distance + 1

            # Add to queue if not visited
            if callee_qualified not in visited:
                visited.add(callee_qualified)
                queue.append((callee_qualified, distance + 1))

    # No path found
    return None


def find_all_paths_to_controls(
    db_path: str,
    entry_file: str,
    entry_line: int,
    control_patterns: list[str],
    max_depth: int = 5
) -> list[dict]:
    """
    Find all control points reachable from entry point and their distances.

    This is used to detect:
    - Missing controls (no paths found)
    - Multiple controls (scattered validation)
    - Late controls (distance too high)

    Args:
        db_path: Path to repo_index.db
        entry_file: Entry point file
        entry_line: Entry point line
        control_patterns: List of control function patterns to find
                         (e.g., ['validate', 'sanitize', 'check'])
        max_depth: Maximum call chain depth to search

    Returns:
        List of dicts with:
            - control_function: Function name
            - control_file: File path
            - control_line: Line number
            - distance: Call chain distance from entry
            - path: List of functions in call chain

    Example:
        >>> find_all_paths_to_controls(
        ...     db_path='/project/.pf/repo_index.db',
        ...     entry_file='src/routes/users.js',
        ...     entry_line=34,
        ...     control_patterns=['validate', 'sanitize'],
        ...     max_depth=3
        ... )
        [
            {
                'control_function': 'validateUser',
                'control_file': 'src/validators/user.js',
                'control_line': 12,
                'distance': 2,
                'path': ['create_user', 'processUser', 'validateUser']
            }
        ]
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        entry_function = _find_containing_function(cursor, entry_file, entry_line)
        if not entry_function:
            return results

        entry_file_part, entry_name = entry_function.split(':', 1)

        # BFS with path tracking
        queue = deque([(entry_function, 0, [entry_name])])
        visited = {entry_function}

        while queue:
            current_func, distance, path = queue.popleft()

            if distance >= max_depth:
                continue

            current_file, current_name = current_func.split(':', 1)

            # Query callees
            cursor.execute("""
                SELECT callee_function, callee_file_path, line
                FROM function_call_args
                WHERE caller_function = ?
                  AND file = ?
                  AND callee_function IS NOT NULL
            """, (current_name, current_file))

            for callee, callee_file, call_line in cursor.fetchall():
                # Check if callee matches control pattern
                is_control = any(pattern.lower() in callee.lower()
                               for pattern in control_patterns)

                if is_control:
                    # Find definition line
                    cursor.execute("""
                        SELECT line
                        FROM symbols
                        WHERE path = ?
                          AND name = ?
                          AND type IN ('function', 'method', 'arrow_function')
                        LIMIT 1
                    """, (callee_file, callee))

                    def_result = cursor.fetchone()
                    callee_line = def_result[0] if def_result else call_line

                    results.append({
                        'control_function': callee,
                        'control_file': callee_file,
                        'control_line': callee_line,
                        'distance': distance + 1,
                        'path': path + [callee]
                    })

                # Continue BFS
                callee_qualified = f"{callee_file}:{callee}"
                if callee_qualified not in visited:
                    visited.add(callee_qualified)
                    queue.append((callee_qualified, distance + 1, path + [callee]))

    finally:
        conn.close()

    return results


def measure_boundary_quality(controls: list[dict]) -> dict:
    """
    Assess boundary quality based on control distances.

    Args:
        controls: List of control points with distances (from find_all_paths_to_controls)

    Returns:
        Dict with quality metrics:
            - quality: 'clear', 'acceptable', 'fuzzy', 'missing'
            - reason: Factual description of boundary state
            - facts: List of factual observations (NOT recommendations)

    Quality Levels:
        - clear: Single control at distance 0
        - acceptable: Single control at distance 1-2
        - fuzzy: Multiple controls OR distance 3+
        - missing: No controls found
    """
    if not controls:
        return {
            'quality': 'missing',
            'reason': 'No validation, sanitization, or checks found in call chain',
            'facts': [
                'Entry point accepts external data',
                'No validation control detected within search depth',
                'Data flows to downstream functions without validation gate'
            ]
        }

    if len(controls) == 1:
        distance = controls[0]['distance']
        control_func = controls[0]['control_function']

        if distance == 0:
            return {
                'quality': 'clear',
                'reason': f"Single control point '{control_func}' at distance 0 (same function as entry)",
                'facts': [
                    'Validation occurs in entry function',
                    'External data validated before use',
                    'No intermediate functions between entry and validation'
                ]
            }
        elif distance <= 2:
            return {
                'quality': 'acceptable',
                'reason': f"Single control point '{control_func}' at distance {distance}",
                'facts': [
                    f"Validation occurs {distance} function call(s) after entry",
                    f"Data flows through {distance} intermediate function(s) before validation",
                    'Single validation control point detected'
                ]
            }
        else:
            return {
                'quality': 'fuzzy',
                'reason': f"Single control point '{control_func}' at distance {distance}",
                'facts': [
                    f"Validation occurs {distance} function calls after entry",
                    f"Data flows through {distance} intermediate functions before validation control",
                    f"Distance {distance} creates {distance} potential code paths without validation"
                ]
            }
    else:
        # Multiple controls
        distances = [c['distance'] for c in controls]
        min_dist = min(distances)
        max_dist = max(distances)
        control_names = [c['control_function'] for c in controls]

        return {
            'quality': 'fuzzy',
            'reason': f"Multiple control points detected: {', '.join(control_names)}",
            'facts': [
                f"{len(controls)} different validation controls found",
                f"Control distances range from {min_dist} to {max_dist}",
                'Multiple validation points indicate distributed boundary enforcement',
                'Different code paths may encounter different validation controls'
            ]
        }
