"""Impact analysis engine for tracing code dependencies and change blast radius."""


import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple


def analyze_impact(
    db_path: str,
    target_file: str,
    target_line: int,
    trace_to_backend: bool = False
) -> dict[str, Any]:
    """
    Analyze the impact of changing code at a specific file and line.
    
    Traces both upstream dependencies (who calls this) and downstream 
    dependencies (what this calls) to understand the blast radius of changes.
    
    Args:
        db_path: Path to the SQLite database
        target_file: Path to the file containing the target code
        target_line: Line number of the target code
        
    Returns:
        Dictionary containing:
        - target_symbol: Name and type of the symbol at target location
        - upstream: List of symbols that call the target (callers)
        - downstream: List of symbols called by the target (callees)
        - impact_summary: Statistics about the blast radius
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Normalize the target file path to match database format
        target_file = Path(target_file).as_posix()
        if target_file.startswith("./"):
            target_file = target_file[2:]
        
        # Check if cross-stack analysis is requested
        if trace_to_backend and target_file.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs')):
            # Attempt cross-stack tracing
            cross_stack_trace = trace_frontend_to_backend(cursor, target_file, target_line)
            
            if cross_stack_trace:
                # Found a backend endpoint - analyze its downstream impact
                backend_file = cross_stack_trace["backend"]["file"]
                backend_line = cross_stack_trace["backend"]["line"]
                
                # Find the backend function/class at the traced location
                cursor.execute("""
                    SELECT name, type, line, col
                    FROM symbols
                    WHERE path = ? 
                    AND type IN ('function', 'class')
                    AND line <= ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (backend_file, backend_line))
                
                backend_result = cursor.fetchone()
                
                if backend_result:
                    backend_name, backend_type, backend_def_line, backend_col = backend_result
                    
                    # Only get downstream dependencies from backend (not upstream)
                    downstream = find_downstream_dependencies(cursor, backend_file, backend_def_line, backend_name)
                    downstream_transitive = calculate_transitive_impact(cursor, downstream, "downstream")
                    
                    # Build cross-stack response
                    return {
                        "cross_stack_trace": cross_stack_trace,
                        "target_symbol": {
                            "name": f"API Call to {cross_stack_trace['frontend']['url']}",
                            "type": "api_call",
                            "file": target_file,
                            "line": target_line,
                            "column": 0
                        },
                        "backend_symbol": {
                            "name": backend_name,
                            "type": backend_type,
                            "file": backend_file,
                            "line": backend_def_line,
                            "column": backend_col
                        },
                        "upstream": [],  # Frontend has no upstream in this context
                        "upstream_transitive": [],
                        "downstream": downstream,
                        "downstream_transitive": downstream_transitive,
                        "impact_summary": {
                            "direct_upstream": 0,
                            "direct_downstream": len(downstream),
                            "total_upstream": 0,
                            "total_downstream": len(downstream) + len(downstream_transitive),
                            "total_impact": len(downstream) + len(downstream_transitive),
                            "affected_files": len(set(
                                [d["file"] for d in downstream] +
                                [d["file"] for d in downstream_transitive]
                            )),
                            "cross_stack": True
                        }
                    }
        
        # Step 1: Find the target symbol at the specified location
        # Look for function or class definition at or near the target line
        cursor.execute("""
            SELECT name, type, line, col
            FROM symbols
            WHERE path = ? 
            AND type IN ('function', 'class')
            AND line <= ?
            ORDER BY line DESC
            LIMIT 1
        """, (target_file, target_line))
        
        target_result = cursor.fetchone()
        
        if not target_result:
            # No function/class found, return empty analysis
            return {
                "target_symbol": None,
                "error": f"No function or class found at {target_file}:{target_line}",
                "upstream": [],
                "downstream": [],
                "impact_summary": {
                    "total_upstream": 0,
                    "total_downstream": 0,
                    "total_impact": 0
                }
            }
        
        target_name, target_type, target_def_line, target_col = target_result
        
        # Step 2: Find upstream dependencies (who calls this symbol)
        upstream = find_upstream_dependencies(cursor, target_file, target_name, target_type)
        
        # Step 3: Find downstream dependencies (what this symbol calls)
        downstream = find_downstream_dependencies(cursor, target_file, target_def_line, target_name)
        
        # Step 4: Calculate transitive impact (recursive dependencies)
        upstream_transitive = calculate_transitive_impact(cursor, upstream, "upstream")
        downstream_transitive = calculate_transitive_impact(cursor, downstream, "downstream")
        
        # Build response
        return {
            "target_symbol": {
                "name": target_name,
                "type": target_type,
                "file": target_file,
                "line": target_def_line,
                "column": target_col
            },
            "upstream": upstream,
            "upstream_transitive": upstream_transitive,
            "downstream": downstream,
            "downstream_transitive": downstream_transitive,
            "impact_summary": {
                "direct_upstream": len(upstream),
                "direct_downstream": len(downstream),
                "total_upstream": len(upstream) + len(upstream_transitive),
                "total_downstream": len(downstream) + len(downstream_transitive),
                "total_impact": len(upstream) + len(downstream) + len(upstream_transitive) + len(downstream_transitive),
                "affected_files": len(set(
                    [u["file"] for u in upstream] + 
                    [d["file"] for d in downstream] +
                    [u["file"] for u in upstream_transitive] +
                    [d["file"] for d in downstream_transitive]
                ))
            }
        }
        
    finally:
        conn.close()


def find_upstream_dependencies(
    cursor: sqlite3.Cursor,
    target_file: str,
    target_name: str,
    target_type: str
) -> list[dict[str, Any]]:
    """
    Find all symbols that call the target symbol (upstream dependencies).
    
    Args:
        cursor: Database cursor
        target_file: File containing the target symbol
        target_name: Name of the target symbol
        target_type: Type of the target symbol (function/class)
        
    Returns:
        List of upstream dependency dictionaries
    """
    upstream = []
    
    # Find all calls to this symbol
    # Match by name (simple matching, could be enhanced with qualified names)
    cursor.execute("""
        SELECT DISTINCT s1.path, s1.name, s1.type, s1.line, s1.col
        FROM symbols s1
        WHERE s1.type = 'call'
        AND s1.name = ?
        AND EXISTS (
            SELECT 1 FROM symbols s2
            WHERE s2.path = s1.path
            AND s2.type IN ('function', 'class')
            AND s2.line <= s1.line
            AND s2.name != ?
        )
        ORDER BY s1.path, s1.line
    """, (target_name, target_name))
    
    for row in cursor.fetchall():
        call_file, call_name, call_type, call_line, call_col = row
        
        # Find the containing function/class for this call
        cursor.execute("""
            SELECT name, type, line
            FROM symbols
            WHERE path = ?
            AND type IN ('function', 'class')
            AND line <= ?
            ORDER BY line DESC
            LIMIT 1
        """, (call_file, call_line))
        
        container = cursor.fetchone()
        if container:
            container_name, container_type, container_line = container
            upstream.append({
                "file": call_file,
                "symbol": container_name,
                "type": container_type,
                "line": container_line,
                "call_line": call_line,
                "calls": target_name
            })
    
    # Deduplicate by file+symbol combination
    seen = set()
    unique_upstream = []
    for dep in upstream:
        key = (dep["file"], dep["symbol"])
        if key not in seen:
            seen.add(key)
            unique_upstream.append(dep)
    
    return unique_upstream


def find_downstream_dependencies(
    cursor: sqlite3.Cursor,
    target_file: str,
    target_line: int,
    target_name: str
) -> list[dict[str, Any]]:
    """
    Find all symbols called by the target symbol (downstream dependencies).
    
    Args:
        cursor: Database cursor
        target_file: File containing the target symbol
        target_line: Line where target symbol is defined
        target_name: Name of the target symbol
        
    Returns:
        List of downstream dependency dictionaries
    """
    downstream = []
    
    # Find the end line of the target function/class
    # Look for the next function/class definition in the same file
    cursor.execute("""
        SELECT line
        FROM symbols
        WHERE path = ?
        AND type IN ('function', 'class')
        AND line > ?
        ORDER BY line
        LIMIT 1
    """, (target_file, target_line))
    
    next_symbol = cursor.fetchone()
    end_line = next_symbol[0] if next_symbol else 999999
    
    # Find all calls within the target function/class body
    cursor.execute("""
        SELECT DISTINCT name, line, col
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND line > ?
        AND line < ?
        ORDER BY line
    """, (target_file, target_line, end_line))
    
    for row in cursor.fetchall():
        called_name, call_line, call_col = row
        
        # Skip recursive calls
        if called_name == target_name:
            continue
            
        # Try to find the definition of the called symbol
        cursor.execute("""
            SELECT path, type, line
            FROM symbols
            WHERE name = ?
            AND type IN ('function', 'class')
            LIMIT 1
        """, (called_name,))
        
        definition = cursor.fetchone()
        if definition:
            def_file, def_type, def_line = definition
            downstream.append({
                "file": def_file,
                "symbol": called_name,
                "type": def_type,
                "line": def_line,
                "called_from_line": call_line,
                "called_by": target_name
            })
        else:
            # External or built-in function
            downstream.append({
                "file": "external",
                "symbol": called_name,
                "type": "unknown",
                "line": 0,
                "called_from_line": call_line,
                "called_by": target_name
            })
    
    # Deduplicate by symbol name
    seen = set()
    unique_downstream = []
    for dep in downstream:
        if dep["symbol"] not in seen:
            seen.add(dep["symbol"])
            unique_downstream.append(dep)
    
    return unique_downstream


def calculate_transitive_impact(
    cursor: sqlite3.Cursor,
    direct_deps: list[dict[str, Any]],
    direction: str,
    max_depth: int = 2,
    visited: set[tuple[str, str]] | None = None
) -> list[dict[str, Any]]:
    """
    Calculate transitive dependencies up to max_depth.
    
    Args:
        cursor: Database cursor
        direct_deps: Direct dependencies to expand
        direction: "upstream" or "downstream"
        max_depth: Maximum recursion depth
        visited: Set of already visited (file, symbol) pairs
        
    Returns:
        List of transitive dependencies
    """
    if max_depth <= 0 or not direct_deps:
        return []
    
    if visited is None:
        visited = set()
    
    transitive = []
    
    for dep in direct_deps:
        # Skip external dependencies
        if dep["file"] == "external":
            continue
            
        dep_key = (dep["file"], dep["symbol"])
        if dep_key in visited:
            continue
        visited.add(dep_key)
        
        if direction == "upstream":
            # Find who calls this dependency
            next_level = find_upstream_dependencies(
                cursor, dep["file"], dep["symbol"], dep["type"]
            )
        else:
            # Find what this dependency calls
            next_level = find_downstream_dependencies(
                cursor, dep["file"], dep["line"], dep["symbol"]
            )
        
        # Add current level
        for next_dep in next_level:
            next_dep["depth"] = max_depth
            transitive.append(next_dep)
        
        # Recurse
        recursive_deps = calculate_transitive_impact(
            cursor, next_level, direction, max_depth - 1, visited
        )
        transitive.extend(recursive_deps)
    
    return transitive


def trace_frontend_to_backend(
    cursor: sqlite3.Cursor,
    target_file: str,
    target_line: int
) -> dict[str, Any] | None:
    """
    Trace a frontend API call to its corresponding backend endpoint.

    Uses function_call_args table to find axios/fetch calls instead of
    parsing source code with regex. This follows the database-first
    architecture principle.

    Args:
        cursor: Database cursor
        target_file: Frontend file containing API call
        target_line: Line number of the API call

    Returns:
        Dictionary with cross-stack trace information or None if not found
    """
    import re

    # Query database for API calls at target location
    # Look for common HTTP client function calls
    cursor.execute("""
        SELECT callee_function, argument_expr
        FROM function_call_args
        WHERE file = ?
        AND line = ?
        AND (
            callee_function LIKE 'axios.%'
            OR callee_function = 'fetch'
            OR callee_function LIKE 'http.%'
            OR callee_function LIKE '$.%'
            OR callee_function LIKE 'request.%'
        )
        LIMIT 1
    """, (target_file, target_line))

    call_match = cursor.fetchone()
    if not call_match:
        return None  # No API call at this location

    callee_function, argument_expr = call_match

    # Extract method from callee_function
    # axios.get → GET, fetch → GET (default), axios.post → POST
    method = None
    if callee_function.startswith('axios.'):
        method = callee_function.split('.')[1].upper()
    elif callee_function == 'fetch':
        # Check if method is specified in argument_expr
        # Example: "'/api/users', { method: 'POST' }"
        method_match = re.search(r'method:\s*[\'"`](GET|POST|PUT|PATCH|DELETE)[\'"`]', argument_expr, re.IGNORECASE)
        method = method_match.group(1).upper() if method_match else 'GET'
    elif callee_function.startswith('http.') or callee_function.startswith('request.'):
        method = callee_function.split('.')[1].upper()
    elif callee_function.startswith('$.'):
        # jQuery: $.get, $.post, $.ajax
        func_name = callee_function.split('.')[1]
        if func_name == 'ajax':
            # Look for type in arguments
            type_match = re.search(r'type:\s*[\'"`](GET|POST|PUT|PATCH|DELETE)[\'"`]', argument_expr, re.IGNORECASE)
            method = type_match.group(1).upper() if type_match else 'GET'
        elif func_name == 'get':
            method = 'GET'
        elif func_name == 'post':
            method = 'POST'
        else:
            method = 'GET'
    else:
        method = 'GET'  # Default fallback

    # Extract URL from argument_expr (first positional argument)
    # argument_expr format examples:
    #   "'/api/users', { headers: ... }"
    #   "'/api/users'"
    #   "`/api/users/${id}`"
    # Extract first quoted string
    url_match = re.search(r'[\'"`]([^\'"`]+)[\'"`]', argument_expr)
    if not url_match:
        return None

    url_path = url_match.group(1)

    if not url_path or not method:
        return None

    # Clean up the URL path
    # Remove query parameters and fragments
    url_path = url_path.split('?')[0].split('#')[0]
    # Remove any template literals (${...})
    url_path = re.sub(r'\$\{[^}]+\}', '*', url_path)

    # Query the api_endpoints table to find matching backend endpoint
    # Try exact match first
    cursor.execute("""
        SELECT file, line, method, pattern
        FROM api_endpoints
        WHERE pattern = ? AND method = ?
        LIMIT 1
    """, (url_path, method))

    backend_match = cursor.fetchone()

    if not backend_match:
        # Try pattern matching (e.g., /api/users/* matches /api/users/:id)
        # Convert URL to SQL LIKE pattern
        like_pattern = url_path.replace('*', '%')

        cursor.execute("""
            SELECT file, line, method, pattern
            FROM api_endpoints
            WHERE ? LIKE REPLACE(REPLACE(pattern, ':id', '%'), ':{param}', '%')
            AND method = ?
            LIMIT 1
        """, (url_path, method))

        backend_match = cursor.fetchone()

    if not backend_match:
        # No matching backend endpoint found
        return None

    backend_file, backend_line, backend_method, backend_pattern = backend_match

    # Query junction table for controls
    cursor.execute("""
        SELECT control_name
        FROM api_endpoint_controls
        WHERE file = ? AND line = ?
    """, (backend_file, backend_line))

    backend_controls = [row[0] for row in cursor.fetchall()]

    return {
        "frontend": {
            "file": target_file,
            "line": target_line,
            "method": method,
            "url": url_path
        },
        "backend": {
            "file": backend_file,
            "line": backend_line,
            "method": backend_method,
            "pattern": backend_pattern,
            "controls": backend_controls
        }
    }


def format_impact_report(impact_data: dict[str, Any]) -> str:
    """
    Format impact analysis results into a human-readable report.
    
    Args:
        impact_data: Results from analyze_impact
        
    Returns:
        Formatted string report
    """
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("IMPACT ANALYSIS REPORT")
    lines.append("=" * 60)
    
    # Target symbol
    if impact_data.get("error"):
        lines.append(f"\nError: {impact_data['error']}")
        return "\n".join(lines)
    
    # Check for cross-stack trace
    if impact_data.get("cross_stack_trace"):
        trace = impact_data["cross_stack_trace"]
        lines.append(f"\n{'─' * 40}")
        lines.append("FRONTEND TO BACKEND TRACE")
        lines.append(f"{'─' * 40}")
        lines.append(f"Frontend API Call:")
        lines.append(f"  File: {trace['frontend']['file']}:{trace['frontend']['line']}")
        lines.append(f"  Method: {trace['frontend']['method']}")
        lines.append(f"  URL: {trace['frontend']['url']}")
        lines.append(f"\nBackend Endpoint:")
        lines.append(f"  File: {trace['backend']['file']}:{trace['backend']['line']}")
        lines.append(f"  Method: {trace['backend']['method']}")
        lines.append(f"  Pattern: {trace['backend']['pattern']}")
        if trace['backend'].get('controls') and trace['backend']['controls'] != '[]':
            lines.append(f"  Security Controls: {trace['backend']['controls']}")
        
        # Show backend symbol as the primary target
        if impact_data.get("backend_symbol"):
            backend = impact_data["backend_symbol"]
            lines.append(f"\nBackend Function: {backend['name']} ({backend['type']})")
            lines.append(f"Location: {backend['file']}:{backend['line']}")
    else:
        target = impact_data["target_symbol"]
        lines.append(f"\nTarget Symbol: {target['name']} ({target['type']})")
        lines.append(f"Location: {target['file']}:{target['line']}")
    
    # Impact summary
    summary = impact_data["impact_summary"]
    lines.append(f"\n{'─' * 40}")
    lines.append("IMPACT SUMMARY")
    lines.append(f"{'─' * 40}")
    lines.append(f"Direct Upstream Dependencies: {summary['direct_upstream']}")
    lines.append(f"Direct Downstream Dependencies: {summary['direct_downstream']}")
    lines.append(f"Total Upstream (including transitive): {summary['total_upstream']}")
    lines.append(f"Total Downstream (including transitive): {summary['total_downstream']}")
    lines.append(f"Total Impact Radius: {summary['total_impact']} symbols")
    lines.append(f"Affected Files: {summary['affected_files']}")
    
    # Upstream dependencies
    if impact_data["upstream"]:
        lines.append(f"\n{'─' * 40}")
        lines.append("UPSTREAM DEPENDENCIES (Who calls this)")
        lines.append(f"{'─' * 40}")
        for dep in impact_data["upstream"][:10]:  # Limit to first 10
            lines.append(f"  • {dep['symbol']} ({dep['type']}) in {dep['file']}:{dep['line']}")
        if len(impact_data["upstream"]) > 10:
            lines.append(f"  ... and {len(impact_data['upstream']) - 10} more")
    
    # Downstream dependencies
    if impact_data["downstream"]:
        lines.append(f"\n{'─' * 40}")
        lines.append("DOWNSTREAM DEPENDENCIES (What this calls)")
        lines.append(f"{'─' * 40}")
        for dep in impact_data["downstream"][:10]:  # Limit to first 10
            if dep["file"] != "external":
                lines.append(f"  • {dep['symbol']} ({dep['type']}) in {dep['file']}:{dep['line']}")
            else:
                lines.append(f"  • {dep['symbol']} (external/built-in)")
        if len(impact_data["downstream"]) > 10:
            lines.append(f"  ... and {len(impact_data['downstream']) - 10} more")
    
    # Risk assessment
    lines.append(f"\n{'─' * 40}")
    lines.append("RISK ASSESSMENT")
    lines.append(f"{'─' * 40}")
    
    risk_level = "LOW"
    if summary["total_impact"] > 20:
        risk_level = "HIGH"
    elif summary["total_impact"] > 10:
        risk_level = "MEDIUM"
    
    lines.append(f"Change Risk Level: {risk_level}")
    
    if risk_level == "HIGH":
        lines.append("⚠ WARNING: This change has a large blast radius!")
        lines.append("  Consider:")
        lines.append("  - Breaking the change into smaller, incremental steps")
        lines.append("  - Adding comprehensive tests before refactoring")
        lines.append("  - Reviewing all upstream dependencies for compatibility")
    elif risk_level == "MEDIUM":
        lines.append("⚠ CAUTION: This change affects multiple components")
        lines.append("  Ensure all callers are updated if the interface changes")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)