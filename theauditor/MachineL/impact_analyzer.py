"""Impact analysis engine for tracing code dependencies and change blast radius."""

import sqlite3
from pathlib import Path
from typing import Any


def classify_risk(impact_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify dependencies into actionable risk buckets."""
    buckets: dict[str, list[dict[str, Any]]] = {
        "production": [],
        "tests": [],
        "config": [],
        "external": [],
    }

    for item in impact_list:
        f_path = item.get("file", "").lower()

        if f_path == "external":
            buckets["external"].append(item)
            continue

        if any(x in f_path for x in ["test", "spec", "mock", "fixture", "/tests/", "\\tests\\"]):
            buckets["tests"].append(item)
            continue

        if (
            f_path.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"))
            or "config" in f_path
            or "dockerfile" in f_path
        ):
            buckets["config"].append(item)
            continue

        buckets["production"].append(item)

    return {
        "breakdown": buckets,
        "metrics": {
            "prod_count": len(buckets["production"]),
            "test_count": len(buckets["tests"]),
            "config_count": len(buckets["config"]),
            "external_count": len(buckets["external"]),
        },
    }


def analyze_impact(
    db_path: str, target_file: str, target_line: int, trace_to_backend: bool = False
) -> dict[str, Any]:
    """Analyze the impact of changing code at a specific file and line."""

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        target_file = Path(target_file).as_posix()
        if target_file.startswith("./"):
            target_file = target_file[2:]

        if trace_to_backend and target_file.endswith(
            (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
        ):
            cross_stack_trace = trace_frontend_to_backend(cursor, target_file, target_line)

            if cross_stack_trace:
                backend_file = cross_stack_trace["backend"]["file"]
                backend_line = cross_stack_trace["backend"]["line"]

                cursor.execute(
                    """
                    SELECT name, type, line, col
                    FROM symbols
                    WHERE path = ?
                    AND type IN ('function', 'class')
                    AND line <= ?
                    ORDER BY line DESC, col DESC
                    LIMIT 1
                """,
                    (backend_file, backend_line),
                )

                backend_result = cursor.fetchone()

                if backend_result:
                    backend_name, backend_type, backend_def_line, backend_col = backend_result

                    downstream = find_downstream_dependencies(
                        cursor, backend_file, backend_def_line, backend_name
                    )
                    downstream_transitive = calculate_transitive_impact(
                        cursor, downstream, "downstream"
                    )

                    all_impacts = downstream + downstream_transitive
                    risk_data = classify_risk(all_impacts)
                    prod_count = risk_data["metrics"]["prod_count"]
                    risk_level = (
                        "HIGH" if prod_count > 10 else ("MEDIUM" if prod_count > 0 else "LOW")
                    )

                    return {
                        "cross_stack_trace": cross_stack_trace,
                        "target_symbol": {
                            "name": f"API Call to {cross_stack_trace['frontend']['url']}",
                            "type": "api_call",
                            "file": target_file,
                            "line": target_line,
                            "column": 0,
                        },
                        "backend_symbol": {
                            "name": backend_name,
                            "type": backend_type,
                            "file": backend_file,
                            "line": backend_def_line,
                            "column": backend_col,
                        },
                        "upstream": [],
                        "upstream_transitive": [],
                        "downstream": downstream,
                        "downstream_transitive": downstream_transitive,
                        "impact_summary": {
                            "direct_upstream": 0,
                            "direct_downstream": len(downstream),
                            "total_upstream": 0,
                            "total_downstream": len(all_impacts),
                            "total_impact": len(all_impacts),
                            "affected_files": len(
                                {item["file"] for item in all_impacts if item["file"] != "external"}
                            ),
                            "cross_stack": True,
                        },
                        "risk_assessment": {
                            "level": risk_level,
                            "summary": f"{prod_count} production, {risk_data['metrics']['test_count']} tests",
                            "details": risk_data["breakdown"],
                        },
                    }

        cursor.execute(
            """
            SELECT name, type, line, col
            FROM symbols
            WHERE path = ?
            AND type IN ('function', 'class')
            AND line <= ?
            ORDER BY line DESC, col DESC
            LIMIT 1
        """,
            (target_file, target_line),
        )

        target_result = cursor.fetchone()

        if not target_result:
            return {
                "target_symbol": None,
                "error": f"No function or class found at {target_file}:{target_line}",
                "upstream": [],
                "downstream": [],
                "impact_summary": {"total_upstream": 0, "total_downstream": 0, "total_impact": 0},
            }

        target_name, target_type, target_def_line, target_col = target_result

        upstream = find_upstream_dependencies(cursor, target_file, target_name, target_type)

        downstream = find_downstream_dependencies(cursor, target_file, target_def_line, target_name)

        upstream_transitive = calculate_transitive_impact(cursor, upstream, "upstream")
        downstream_transitive = calculate_transitive_impact(cursor, downstream, "downstream")

        all_impacts = upstream + downstream + upstream_transitive + downstream_transitive
        risk_data = classify_risk(all_impacts)

        prod_count = risk_data["metrics"]["prod_count"]
        risk_level = "LOW"
        if prod_count > 10:
            risk_level = "HIGH"
        elif prod_count > 0:
            risk_level = "MEDIUM"

        return {
            "target_symbol": {
                "name": target_name,
                "type": target_type,
                "file": target_file,
                "line": target_def_line,
                "column": target_col,
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
                "affected_files": len(
                    {item["file"] for item in all_impacts if item["file"] != "external"}
                ),
            },
            "risk_assessment": {
                "level": risk_level,
                "summary": f"{prod_count} production, {risk_data['metrics']['test_count']} tests, {risk_data['metrics']['config_count']} config",
                "details": risk_data["breakdown"],
            },
        }


def find_upstream_dependencies(
    cursor: sqlite3.Cursor, target_file: str, target_name: str, target_type: str
) -> list[dict[str, Any]]:
    """Find all symbols that call the target symbol (upstream dependencies)."""

    cursor.execute(
        """
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
    """,
        (target_name, target_name),
    )

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
                "calls": target_name,
            }

    return list(unique_deps.values())


def find_downstream_dependencies(
    cursor: sqlite3.Cursor, target_file: str, target_line: int, target_name: str
) -> list[dict[str, Any]]:
    """Find all symbols called by the target symbol (downstream dependencies)."""

    cursor.execute(
        """
        SELECT line
        FROM symbols
        WHERE path = ?
        AND type IN ('function', 'class')
        AND line > ?
        ORDER BY line, col
        LIMIT 1
    """,
        (target_file, target_line),
    )

    next_symbol = cursor.fetchone()
    end_line = next_symbol[0] if next_symbol else 999999

    cursor.execute(
        """
        SELECT DISTINCT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND line > ?
        AND line < ?
        ORDER BY line
    """,
        (target_file, target_line, end_line),
    )

    raw_calls = cursor.fetchall()
    if not raw_calls:
        return []

    call_map: dict[str, int] = {}
    for name, call_line in raw_calls:
        if name != target_name and name not in call_map:
            call_map[name] = call_line

    if not call_map:
        return []

    call_names = list(call_map.keys())

    placeholders = ",".join("?" * len(call_names))
    cursor.execute(
        f"""
        SELECT path, name, type, line
        FROM symbols
        WHERE name IN ({placeholders})
        AND type IN ('function', 'class')
    """,
        call_names,
    )

    definitions: dict[str, tuple[str, str, int]] = {}
    for def_path, def_name, def_type, def_line in cursor.fetchall():
        if def_name not in definitions:
            definitions[def_name] = (def_path, def_type, def_line)

    downstream = []
    for name in call_names:
        if name in definitions:
            def_path, def_type, def_line = definitions[name]
            downstream.append(
                {
                    "file": def_path,
                    "symbol": name,
                    "type": def_type,
                    "line": def_line,
                    "called_from_line": call_map[name],
                    "called_by": target_name,
                }
            )
        else:
            downstream.append(
                {
                    "file": "external",
                    "symbol": name,
                    "type": "unknown",
                    "line": 0,
                    "called_from_line": call_map[name],
                    "called_by": target_name,
                }
            )

    return downstream


def find_upstream_dependencies_batch(
    cursor: sqlite3.Cursor, symbols: list[tuple[str, str, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Batch version: Find all callers for multiple symbols in ONE query.

    Args:
        cursor: Database cursor
        symbols: List of (file_path, symbol_name, symbol_type) tuples

    Returns:
        Dict mapping symbol_name -> list of upstream dependencies
    """
    if not symbols:
        return {}

    symbol_names = list({s[1] for s in symbols})
    if not symbol_names:
        return {}

    placeholders = ",".join("?" * len(symbol_names))

    cursor.execute(
        f"""
        SELECT
            call.name as target_name,
            call.path as file,
            call.line as call_line,
            container.name as symbol,
            container.type as type,
            container.line as line
        FROM symbols call
        JOIN symbols container ON call.path = container.path
        WHERE call.name IN ({placeholders})
          AND call.type = 'call'
          AND container.type IN ('function', 'class')
          AND container.name NOT IN ({placeholders})
          AND container.line = (
              SELECT MAX(s.line)
              FROM symbols s
              WHERE s.path = call.path
              AND s.type IN ('function', 'class')
              AND s.line <= call.line
          )
        ORDER BY call.name, call.path, call.line
    """,
        symbol_names + symbol_names,
    )

    results: dict[str, dict[tuple[str, str], dict[str, Any]]] = {name: {} for name in symbol_names}

    for row in cursor.fetchall():
        target_name, f_path, call_line, sym_name, sym_type, sym_line = row
        if target_name not in results:
            continue

        key = (f_path, sym_name)
        if key not in results[target_name]:
            results[target_name][key] = {
                "file": f_path,
                "symbol": sym_name,
                "type": sym_type,
                "line": sym_line,
                "call_line": call_line,
                "calls": target_name,
            }

    return {name: list(deps.values()) for name, deps in results.items()}


def find_downstream_dependencies_batch(
    cursor: sqlite3.Cursor, symbols: list[tuple[str, int, str]]
) -> dict[str, list[dict[str, Any]]]:
    """Batch version: Find all calls made by multiple symbols in bulk queries.

    Args:
        cursor: Database cursor
        symbols: List of (file_path, start_line, symbol_name) tuples

    Returns:
        Dict mapping "file_path:symbol_name" -> list of downstream dependencies
    """
    if not symbols:
        return {}

    file_paths = list({s[0] for s in symbols})
    placeholders = ",".join("?" * len(file_paths))

    cursor.execute(
        f"""
        SELECT path, name, type, line
        FROM symbols
        WHERE path IN ({placeholders})
        AND type IN ('function', 'class')
        ORDER BY path, line
    """,
        file_paths,
    )

    file_symbols: dict[str, list[tuple[int, str, str]]] = {}
    for path, name, sym_type, line in cursor.fetchall():
        if path not in file_symbols:
            file_symbols[path] = []
        file_symbols[path].append((line, name, sym_type))

    symbol_ranges: list[tuple[str, int, int, str]] = []
    for file_path, start_line, symbol_name in symbols:
        if file_path not in file_symbols:
            continue

        end_line = 999999
        found_start = False
        for line, _name, _ in file_symbols[file_path]:
            if line == start_line:
                found_start = True
                continue
            if found_start and line > start_line:
                end_line = line
                break

        symbol_ranges.append((file_path, start_line, end_line, symbol_name))

    if not symbol_ranges:
        return {}

    where_clauses = []
    params = []
    for file_path, start_line, end_line, _ in symbol_ranges:
        where_clauses.append("(path = ? AND type = 'call' AND line > ? AND line < ?)")
        params.extend([file_path, start_line, end_line])

    if not where_clauses:
        return {}

    cursor.execute(
        f"""
        SELECT path, name, line
        FROM symbols
        WHERE {" OR ".join(where_clauses)}
        ORDER BY path, line
    """,
        params,
    )

    file_calls: dict[str, dict[str, int]] = {}
    for path, call_name, call_line in cursor.fetchall():
        if path not in file_calls:
            file_calls[path] = {}
        if call_name not in file_calls[path]:
            file_calls[path][call_name] = call_line

    all_call_names = set()
    for calls in file_calls.values():
        all_call_names.update(calls.keys())

    symbol_names_set = {s[2] for s in symbols}
    all_call_names -= symbol_names_set

    if not all_call_names:
        return {f"{fp}:{name}": [] for fp, _, name in symbols}

    call_name_list = list(all_call_names)
    placeholders = ",".join("?" * len(call_name_list))

    cursor.execute(
        f"""
        SELECT path, name, type, line
        FROM symbols
        WHERE name IN ({placeholders})
        AND type IN ('function', 'class')
    """,
        call_name_list,
    )

    definitions: dict[str, tuple[str, str, int]] = {}
    for def_path, def_name, def_type, def_line in cursor.fetchall():
        if def_name not in definitions:
            definitions[def_name] = (def_path, def_type, def_line)

    results: dict[str, list[dict[str, Any]]] = {}

    for file_path, start_line, end_line, symbol_name in symbol_ranges:
        key = f"{file_path}:{symbol_name}"
        downstream = []

        if file_path in file_calls:
            for call_name, call_line in file_calls[file_path].items():
                if call_line <= start_line or call_line >= end_line:
                    continue

                if call_name == symbol_name:
                    continue

                if call_name in definitions:
                    def_path, def_type, def_line = definitions[call_name]
                    downstream.append(
                        {
                            "file": def_path,
                            "symbol": call_name,
                            "type": def_type,
                            "line": def_line,
                            "called_from_line": call_line,
                            "called_by": symbol_name,
                        }
                    )
                else:
                    downstream.append(
                        {
                            "file": "external",
                            "symbol": call_name,
                            "type": "unknown",
                            "line": 0,
                            "called_from_line": call_line,
                            "called_by": symbol_name,
                        }
                    )

        results[key] = downstream

    return results


def calculate_transitive_impact(
    cursor: sqlite3.Cursor,
    direct_deps: list[dict[str, Any]],
    direction: str,
    max_depth: int = 2,
    visited: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Calculate transitive dependencies up to max_depth."""
    if max_depth <= 0 or not direct_deps:
        return []

    if visited is None:
        visited = set()

    transitive = []

    for dep in direct_deps:
        if dep["file"] == "external":
            continue

        dep_key = (dep["file"], dep["symbol"])
        if dep_key in visited:
            continue
        visited.add(dep_key)

        if direction == "upstream":
            next_level = find_upstream_dependencies(cursor, dep["file"], dep["symbol"], dep["type"])
        else:
            next_level = find_downstream_dependencies(
                cursor, dep["file"], dep["line"], dep["symbol"]
            )

        for next_dep in next_level:
            next_dep["depth"] = max_depth
            transitive.append(next_dep)

        recursive_deps = calculate_transitive_impact(
            cursor, next_level, direction, max_depth - 1, visited
        )
        transitive.extend(recursive_deps)

    return transitive


def trace_frontend_to_backend(
    cursor: sqlite3.Cursor, target_file: str, target_line: int
) -> dict[str, Any] | None:
    """Trace a frontend API call to its corresponding backend endpoint."""
    import re

    cursor.execute(
        """
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
    """,
        (target_file, target_line),
    )

    call_match = cursor.fetchone()
    if not call_match:
        return None

    callee_function, argument_expr = call_match

    method = None
    if callee_function.startswith("axios."):
        method = callee_function.split(".")[1].upper()
    elif callee_function == "fetch":
        method_match = re.search(
            r'method:\s*[\'"`](GET|POST|PUT|PATCH|DELETE)[\'"`]', argument_expr, re.IGNORECASE
        )
        method = method_match.group(1).upper() if method_match else "GET"
    elif callee_function.startswith("http.") or callee_function.startswith("request."):
        method = callee_function.split(".")[1].upper()
    elif callee_function.startswith("$."):
        func_name = callee_function.split(".")[1]
        if func_name == "ajax":
            type_match = re.search(
                r'type:\s*[\'"`](GET|POST|PUT|PATCH|DELETE)[\'"`]', argument_expr, re.IGNORECASE
            )
            method = type_match.group(1).upper() if type_match else "GET"
        elif func_name == "get":
            method = "GET"
        elif func_name == "post":
            method = "POST"
        else:
            method = "GET"
    else:
        method = "GET"

    url_match = re.search(r'[\'"`]([^\'"`]+)[\'"`]', argument_expr)
    if not url_match:
        return None

    url_path = url_match.group(1)

    if not url_path or not method:
        return None

    url_path = url_path.split("?")[0].split("#")[0]

    url_path = re.sub(r"\$\{[^}]+\}", "*", url_path)

    cursor.execute(
        """
        SELECT file, line, method, pattern
        FROM api_endpoints
        WHERE pattern = ? AND method = ?
        LIMIT 1
    """,
        (url_path, method),
    )

    backend_match = cursor.fetchone()

    if not backend_match:
        return None

    backend_file, backend_line, backend_method, backend_pattern = backend_match

    cursor.execute(
        """
        SELECT control_name
        FROM api_endpoint_controls
        WHERE endpoint_file = ? AND endpoint_line = ?
    """,
        (backend_file, backend_line),
    )

    backend_controls = [row[0] for row in cursor.fetchall()]

    return {
        "frontend": {"file": target_file, "line": target_line, "method": method, "url": url_path},
        "backend": {
            "file": backend_file,
            "line": backend_line,
            "method": backend_method,
            "pattern": backend_pattern,
            "controls": backend_controls,
        },
    }


def calculate_coupling_score(impact_data: dict[str, Any]) -> int:
    """Calculate a coupling score (0-100) based on impact metrics."""
    if impact_data.get("error"):
        return 0

    summary = impact_data.get("impact_summary", {})
    direct_upstream = summary.get("direct_upstream", 0)
    direct_downstream = summary.get("direct_downstream", 0)
    total_impact = summary.get("total_impact", 0)
    affected_files = summary.get("affected_files", 0)

    base_score = (direct_upstream * 3) + (direct_downstream * 2)
    spread_multiplier = min(affected_files / 5, 3)
    transitive_bonus = min(total_impact / 10, 20)

    score = int(base_score * (1 + spread_multiplier * 0.3) + transitive_bonus)
    return min(score, 100)


def format_planning_context(impact_data: dict[str, Any]) -> str:
    """Format impact analysis for planning agent consumption."""
    lines = []

    lines.append("=" * 60)
    lines.append("IMPACT CONTEXT FOR PLANNING")
    lines.append("=" * 60)

    if impact_data.get("error"):
        lines.append(f"\nError: {impact_data['error']}")
        return "\n".join(lines)

    target = impact_data.get("target_symbol") or impact_data.get("backend_symbol")
    if target:
        lines.append(f"\nSymbol: {target['name']} ({target['type']})")
        lines.append(f"Location: {target['file']}:{target['line']}")

    coupling = calculate_coupling_score(impact_data)
    if coupling < 30:
        coupling_level = "LOW"
    elif coupling < 70:
        coupling_level = "MEDIUM"
    else:
        coupling_level = "HIGH"
    lines.append(f"Coupling Score: {coupling}/100 ({coupling_level})")

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

    summary = impact_data.get("impact_summary", {})
    lines.append(f"\n{'-' * 40}")
    lines.append("RISK ASSESSMENT")
    lines.append(f"{'-' * 40}")
    lines.append(
        f"  Direct Impact: {summary.get('direct_upstream', 0) + summary.get('direct_downstream', 0)} dependencies"
    )
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

    if all_deps and len(all_deps) > 3:
        risk_data = classify_risk(all_deps)
        buckets = risk_data["breakdown"]
        metrics = risk_data["metrics"]

        lines.append(f"\n{'-' * 40}")
        lines.append("SUGGESTED PHASES")
        lines.append(f"{'-' * 40}")

        phase_num = 1
        if metrics["test_count"] > 0:
            lines.append(
                f"  Phase {phase_num}: Update tests ({metrics['test_count']} files) - Update mocks first"
            )
            phase_num += 1

        if metrics["config_count"] > 0:
            lines.append(
                f"  Phase {phase_num}: Update config ({metrics['config_count']} files) - Low risk"
            )
            phase_num += 1

        internal = [
            d
            for d in buckets["production"]
            if "service" in d["file"].lower() or "util" in d["file"].lower()
        ]
        external = [d for d in buckets["production"] if d not in internal]

        if internal:
            lines.append(
                f"  Phase {phase_num}: Internal callers ({len(internal)} files) - Services/utils"
            )
            phase_num += 1

        if external:
            lines.append(
                f"  Phase {phase_num}: External interface ({len(external)} files) - API/handlers last"
            )

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
    """Format impact analysis results into a human-readable report."""
    lines = []

    lines.append("=" * 60)
    lines.append("IMPACT ANALYSIS REPORT")
    lines.append("=" * 60)

    if impact_data.get("error"):
        lines.append(f"\nError: {impact_data['error']}")
        return "\n".join(lines)

    if impact_data.get("cross_stack_trace"):
        trace = impact_data["cross_stack_trace"]
        lines.append(f"\n{'─' * 40}")
        lines.append("FRONTEND TO BACKEND TRACE")
        lines.append(f"{'─' * 40}")
        lines.append("Frontend API Call:")
        lines.append(f"  File: {trace['frontend']['file']}:{trace['frontend']['line']}")
        lines.append(f"  Method: {trace['frontend']['method']}")
        lines.append(f"  URL: {trace['frontend']['url']}")
        lines.append("\nBackend Endpoint:")
        lines.append(f"  File: {trace['backend']['file']}:{trace['backend']['line']}")
        lines.append(f"  Method: {trace['backend']['method']}")
        lines.append(f"  Pattern: {trace['backend']['pattern']}")
        if trace["backend"].get("controls") and trace["backend"]["controls"] != "[]":
            lines.append(f"  Security Controls: {trace['backend']['controls']}")

        if impact_data.get("backend_symbol"):
            backend = impact_data["backend_symbol"]
            lines.append(f"\nBackend Function: {backend['name']} ({backend['type']})")
            lines.append(f"Location: {backend['file']}:{backend['line']}")
    else:
        target = impact_data["target_symbol"]
        lines.append(f"\nTarget Symbol: {target['name']} ({target['type']})")
        lines.append(f"Location: {target['file']}:{target['line']}")

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

    if impact_data["upstream"]:
        lines.append(f"\n{'─' * 40}")
        lines.append("UPSTREAM DEPENDENCIES (Who calls this)")
        lines.append(f"{'─' * 40}")
        for dep in impact_data["upstream"][:10]:
            lines.append(f"  • {dep['symbol']} ({dep['type']}) in {dep['file']}:{dep['line']}")
        if len(impact_data["upstream"]) > 10:
            lines.append(f"  ... and {len(impact_data['upstream']) - 10} more")

    if impact_data["downstream"]:
        lines.append(f"\n{'─' * 40}")
        lines.append("DOWNSTREAM DEPENDENCIES (What this calls)")
        lines.append(f"{'─' * 40}")
        for dep in impact_data["downstream"][:10]:
            if dep["file"] != "external":
                lines.append(f"  • {dep['symbol']} ({dep['type']}) in {dep['file']}:{dep['line']}")
            else:
                lines.append(f"  • {dep['symbol']} (external/built-in)")
        if len(impact_data["downstream"]) > 10:
            lines.append(f"  ... and {len(impact_data['downstream']) - 10} more")

    lines.append(f"\n{'─' * 40}")
    lines.append("RISK ASSESSMENT")
    lines.append(f"{'─' * 40}")

    risk_assessment = impact_data.get("risk_assessment")
    if risk_assessment:
        risk_level = risk_assessment["level"]
        lines.append(f"Change Risk Level: {risk_level}")
        lines.append(f"Impact Breakdown: {risk_assessment['summary']}")
    else:
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
