"""Impact analysis engine for tracing code dependencies and change blast radius."""


import sqlite3
from pathlib import Path
from typing import Any


def classify_risk(impact_list: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Classify dependencies into actionable risk buckets.

    Organizes impact data into production code, tests, config files,
    and external dependencies for smarter risk assessment.

    Args:
        impact_list: List of dependency dictionaries with 'file' keys

    Returns:
        Dictionary with 'breakdown' (categorized lists) and 'metrics' (counts)
    """
    buckets: dict[str, list[dict[str, Any]]] = {
        "production": [],
        "tests": [],
        "config": [],
        "external": []
    }

    for item in impact_list:
        f_path = item.get("file", "").lower()

        # External/Built-ins
        if f_path == "external":
            buckets["external"].append(item)
            continue

        # Test files
        if any(x in f_path for x in ['test', 'spec', 'mock', 'fixture', '/tests/', '\\tests\\']):
            buckets["tests"].append(item)
            continue

        # Config/Infrastructure files
        if f_path.endswith(('.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env')) or \
           'config' in f_path or 'dockerfile' in f_path:
            buckets["config"].append(item)
            continue

        # Everything else is production code
        buckets["production"].append(item)

    return {
        "breakdown": buckets,
        "metrics": {
            "prod_count": len(buckets["production"]),
            "test_count": len(buckets["tests"]),
            "config_count": len(buckets["config"]),
            "external_count": len(buckets["external"])
        }
    }


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
    # Use context manager for automatic connection cleanup
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

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
                    ORDER BY line DESC, col DESC
                    LIMIT 1
                """, (backend_file, backend_line))

                backend_result = cursor.fetchone()

                if backend_result:
                    backend_name, backend_type, backend_def_line, backend_col = backend_result

                    # Only get downstream dependencies from backend (not upstream)
                    downstream = find_downstream_dependencies(cursor, backend_file, backend_def_line, backend_name)
                    downstream_transitive = calculate_transitive_impact(cursor, downstream, "downstream")

                    # Calculate risk for cross-stack
                    all_impacts = downstream + downstream_transitive
                    risk_data = classify_risk(all_impacts)
                    prod_count = risk_data["metrics"]["prod_count"]
                    risk_level = "HIGH" if prod_count > 10 else ("MEDIUM" if prod_count > 0 else "LOW")

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
                            "total_downstream": len(all_impacts),
                            "total_impact": len(all_impacts),
                            "affected_files": len(set(
                                item["file"] for item in all_impacts if item["file"] != "external"
                            )),
                            "cross_stack": True
                        },
                        "risk_assessment": {
                            "level": risk_level,
                            "summary": f"{prod_count} production, {risk_data['metrics']['test_count']} tests",
                            "details": risk_data["breakdown"]
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
            ORDER BY line DESC, col DESC
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

        # Step 5: Calculate risk classification
        all_impacts = upstream + downstream + upstream_transitive + downstream_transitive
        risk_data = classify_risk(all_impacts)

        # Calculate risk level based on production code impact
        prod_count = risk_data["metrics"]["prod_count"]
        risk_level = "LOW"
        if prod_count > 10:
            risk_level = "HIGH"
        elif prod_count > 0:
            risk_level = "MEDIUM"

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
                "total_impact": len(all_impacts),
                "affected_files": len(set(
                    item["file"] for item in all_impacts if item["file"] != "external"
                ))
            },
            "risk_assessment": {
                "level": risk_level,
                "summary": f"{prod_count} production, {risk_data['metrics']['test_count']} tests, {risk_data['metrics']['config_count']} config",
                "details": risk_data["breakdown"]
            }
        }


def find_upstream_dependencies(
    cursor: sqlite3.Cursor,
    target_file: str,
    target_name: str,
    target_type: str
) -> list[dict[str, Any]]:
    """
    Find all symbols that call the target symbol (upstream dependencies).

    Optimized: Uses a single JOIN query instead of N+1 queries.

    Args:
        cursor: Database cursor
        target_file: File containing the target symbol
        target_name: Name of the target symbol
        target_type: Type of the target symbol (function/class)

    Returns:
        List of upstream dependency dictionaries
    """
    # Single query that finds calls AND their containing functions in one pass.
    # The subquery finds the closest function/class definition that precedes each call.
    # This eliminates the N+1 pattern where we queried for each call's container separately.
    cursor.execute("""
        SELECT
            call.path as file,
            call.line as call_line,
            container.name as symbol,
            container.type as type,
            container.line as line
        FROM symbols call
        JOIN symbols container ON call.path = container.path
        WHERE call.name = ?
          AND call.type = 'call'
          AND container.type IN ('function', 'class')
          AND container.name != ?
          AND container.line = (
              SELECT MAX(s.line)
              FROM symbols s
              WHERE s.path = call.path
              AND s.type IN ('function', 'class')
              AND s.line <= call.line
          )
        ORDER BY call.path, call.line
    """, (target_name, target_name))

    # Deduplicate by file+symbol using dict (preserves insertion order in Python 3.7+)
    unique_deps: dict[tuple[str, str], dict[str, Any]] = {}

    for row in cursor.fetchall():
        f_path, call_line, sym_name, sym_type, sym_line = row
        key = (f_path, sym_name)
        if key not in unique_deps:
            unique_deps[key] = {
                "file": f_path,
                "symbol": sym_name,
                "type": sym_type,
                "line": sym_line,
                "call_line": call_line,
                "calls": target_name
            }

    return list(unique_deps.values())


def find_downstream_dependencies(
    cursor: sqlite3.Cursor,
    target_file: str,
    target_line: int,
    target_name: str
) -> list[dict[str, Any]]:
    """
    Find all symbols called by the target symbol (downstream dependencies).

    Optimized: Uses batch WHERE IN query instead of N+1 queries.

    Args:
        cursor: Database cursor
        target_file: File containing the target symbol
        target_line: Line where target symbol is defined
        target_name: Name of the target symbol

    Returns:
        List of downstream dependency dictionaries
    """
    # Step 1: Find the end line of the target function/class
    cursor.execute("""
        SELECT line
        FROM symbols
        WHERE path = ?
        AND type IN ('function', 'class')
        AND line > ?
        ORDER BY line, col
        LIMIT 1
    """, (target_file, target_line))

    next_symbol = cursor.fetchone()
    end_line = next_symbol[0] if next_symbol else 999999

    # Step 2: Get ALL calls within the function body in one query
    cursor.execute("""
        SELECT DISTINCT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND line > ?
        AND line < ?
        ORDER BY line
    """, (target_file, target_line, end_line))

    raw_calls = cursor.fetchall()
    if not raw_calls:
        return []

    # Step 3: Build a map of {name: call_line}, excluding recursive calls
    call_map: dict[str, int] = {}
    for name, call_line in raw_calls:
        if name != target_name and name not in call_map:
            call_map[name] = call_line

    if not call_map:
        return []

    call_names = list(call_map.keys())

    # Step 4: Batch resolve - find all definitions in ONE query
    placeholders = ','.join('?' * len(call_names))
    cursor.execute(f"""
        SELECT path, name, type, line
        FROM symbols
        WHERE name IN ({placeholders})
        AND type IN ('function', 'class')
    """, call_names)

    # Build lookup of definitions (first definition wins per name)
    definitions: dict[str, tuple[str, str, int]] = {}
    for def_path, def_name, def_type, def_line in cursor.fetchall():
        if def_name not in definitions:
            definitions[def_name] = (def_path, def_type, def_line)

    # Step 5: Assemble results
    downstream = []
    for name in call_names:
        if name in definitions:
            def_path, def_type, def_line = definitions[name]
            downstream.append({
                "file": def_path,
                "symbol": name,
                "type": def_type,
                "line": def_line,
                "called_from_line": call_map[name],
                "called_by": target_name
            })
        else:
            # External or built-in function
            downstream.append({
                "file": "external",
                "symbol": name,
                "type": "unknown",
                "line": 0,
                "called_from_line": call_map[name],
                "called_by": target_name
            })

    return downstream


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
        WHERE endpoint_file = ? AND endpoint_line = ?
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


def calculate_coupling_score(impact_data: dict[str, Any]) -> int:
    """
    Calculate a coupling score (0-100) based on impact metrics.

    Higher score = more tightly coupled = higher risk.

    Args:
        impact_data: Results from analyze_impact

    Returns:
        Integer score 0-100
    """
    if impact_data.get("error"):
        return 0

    summary = impact_data.get("impact_summary", {})
    direct_upstream = summary.get("direct_upstream", 0)
    direct_downstream = summary.get("direct_downstream", 0)
    total_impact = summary.get("total_impact", 0)
    affected_files = summary.get("affected_files", 0)

    # Scoring formula:
    # - Base: direct dependencies (weighted)
    # - Multiplier: affected files spread
    # - Cap at 100
    base_score = (direct_upstream * 3) + (direct_downstream * 2)
    spread_multiplier = min(affected_files / 5, 3)  # Max 3x for 15+ files
    transitive_bonus = min(total_impact / 10, 20)  # Max 20 points for transitive

    score = int(base_score * (1 + spread_multiplier * 0.3) + transitive_bonus)
    return min(score, 100)


def format_planning_context(impact_data: dict[str, Any]) -> str:
    """
    Format impact analysis for planning agent consumption.

    Outputs structured format with:
    - Risk categories (production/tests/config/external)
    - Coupling score
    - Suggested phases for incremental changes

    Args:
        impact_data: Results from analyze_impact

    Returns:
        Planning-friendly formatted string
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append("IMPACT CONTEXT FOR PLANNING")
    lines.append("=" * 60)

    # Error case
    if impact_data.get("error"):
        lines.append(f"\nError: {impact_data['error']}")
        return "\n".join(lines)

    # Target info
    target = impact_data.get("target_symbol") or impact_data.get("backend_symbol")
    if target:
        lines.append(f"\nSymbol: {target['name']} ({target['type']})")
        lines.append(f"Location: {target['file']}:{target['line']}")

    # Coupling score
    coupling = calculate_coupling_score(impact_data)
    if coupling < 30:
        coupling_level = "LOW"
    elif coupling < 70:
        coupling_level = "MEDIUM"
    else:
        coupling_level = "HIGH"
    lines.append(f"Coupling Score: {coupling}/100 ({coupling_level})")

    # Risk classification using classify_risk
    upstream = impact_data.get("upstream", [])
    downstream = impact_data.get("downstream", [])
    all_deps = upstream + downstream

    if all_deps:
        risk_data = classify_risk(all_deps)
        buckets = risk_data["breakdown"]
        metrics = risk_data["metrics"]

        lines.append(f"\n{'-' * 40}")
        lines.append("DEPENDENCIES BY CATEGORY")
        lines.append(f"{'-' * 40}")

        if metrics["prod_count"] > 0:
            lines.append(f"  Production: {metrics['prod_count']} callers")
            for dep in buckets["production"][:5]:
                lines.append(f"    - {dep.get('symbol', 'unknown')} in {dep['file']}")
            if metrics["prod_count"] > 5:
                lines.append(f"    ... and {metrics['prod_count'] - 5} more")

        if metrics["test_count"] > 0:
            lines.append(f"  Tests: {metrics['test_count']} callers")
            for dep in buckets["tests"][:3]:
                lines.append(f"    - {dep.get('symbol', 'unknown')} in {dep['file']}")
            if metrics["test_count"] > 3:
                lines.append(f"    ... and {metrics['test_count'] - 3} more")

        if metrics["config_count"] > 0:
            lines.append(f"  Config: {metrics['config_count']} files")

        if metrics["external_count"] > 0:
            lines.append(f"  External: {metrics['external_count']} calls (no action needed)")

    # Impact summary
    summary = impact_data.get("impact_summary", {})
    lines.append(f"\n{'-' * 40}")
    lines.append("RISK ASSESSMENT")
    lines.append(f"{'-' * 40}")
    lines.append(f"  Direct Impact: {summary.get('direct_upstream', 0) + summary.get('direct_downstream', 0)} dependencies")
    lines.append(f"  Transitive Impact: {summary.get('total_impact', 0)} total")
    lines.append(f"  Affected Files: {summary.get('affected_files', 0)}")

    total = summary.get("total_impact", 0)
    if total > 30:
        risk_level = "HIGH"
    elif total > 10:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    lines.append(f"  Change Risk: {risk_level}")

    # Suggested phases
    if all_deps and len(all_deps) > 3:
        risk_data = classify_risk(all_deps)
        buckets = risk_data["breakdown"]
        metrics = risk_data["metrics"]

        lines.append(f"\n{'-' * 40}")
        lines.append("SUGGESTED PHASES")
        lines.append(f"{'-' * 40}")

        phase_num = 1
        if metrics["test_count"] > 0:
            lines.append(f"  Phase {phase_num}: Update tests ({metrics['test_count']} files) - Update mocks first")
            phase_num += 1

        if metrics["config_count"] > 0:
            lines.append(f"  Phase {phase_num}: Update config ({metrics['config_count']} files) - Low risk")
            phase_num += 1

        # Split production by internal vs external facing
        internal = [d for d in buckets["production"] if "service" in d["file"].lower() or "util" in d["file"].lower()]
        external = [d for d in buckets["production"] if d not in internal]

        if internal:
            lines.append(f"  Phase {phase_num}: Internal callers ({len(internal)} files) - Services/utils")
            phase_num += 1

        if external:
            lines.append(f"  Phase {phase_num}: External interface ({len(external)} files) - API/handlers last")

    # Recommendations based on coupling
    lines.append(f"\n{'-' * 40}")
    lines.append("RECOMMENDATIONS")
    lines.append(f"{'-' * 40}")

    if coupling >= 70:
        lines.append("  [!] HIGH coupling detected:")
        lines.append("      - Consider extracting an interface before refactoring")
        lines.append("      - Break changes into smaller incremental steps")
        lines.append("      - Add comprehensive tests before making changes")
    elif coupling >= 30:
        lines.append("  [*] MEDIUM coupling:")
        lines.append("      - Review all callers for compatibility")
        lines.append("      - Consider phased rollout")
    else:
        lines.append("  [OK] LOW coupling:")
        lines.append("      - Safe to refactor with minimal risk")
        lines.append("      - Standard testing should suffice")

    lines.append("=" * 60)

    return "\n".join(lines)


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

    # Risk assessment - use smart classification if available
    lines.append(f"\n{'─' * 40}")
    lines.append("RISK ASSESSMENT")
    lines.append(f"{'─' * 40}")

    risk_assessment = impact_data.get("risk_assessment")
    if risk_assessment:
        risk_level = risk_assessment["level"]
        lines.append(f"Change Risk Level: {risk_level}")
        lines.append(f"Impact Breakdown: {risk_assessment['summary']}")
    else:
        # Fallback to simple count-based assessment
        risk_level = "LOW"
        if summary["total_impact"] > 20:
            risk_level = "HIGH"
        elif summary["total_impact"] > 10:
            risk_level = "MEDIUM"
        lines.append(f"Change Risk Level: {risk_level}")

    if risk_level == "HIGH":
        lines.append("[!] WARNING: This change has a large blast radius!")
        lines.append("  Consider:")
        lines.append("  - Breaking the change into smaller, incremental steps")
        lines.append("  - Adding comprehensive tests before refactoring")
        lines.append("  - Reviewing all upstream dependencies for compatibility")
    elif risk_level == "MEDIUM":
        lines.append("[!] CAUTION: This change affects multiple components")
        lines.append("  Ensure all callers are updated if the interface changes")

    lines.append("=" * 60)

    return "\n".join(lines)