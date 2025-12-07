"""Input Validation Boundary Analyzer."""

import sqlite3
from pathlib import Path

from theauditor.boundaries.distance import (
    _build_graph_index,
    find_all_paths_to_controls,
    measure_boundary_quality,
)
from theauditor.graph.store import XGraphStore

VALIDATION_PATTERNS = ["validate", "parse", "check", "sanitize", "clean", "schema", "validator"]

# Framework-specific validation middleware patterns
EXPRESS_VALIDATION_PATTERNS = ["validate", "validateBody", "validateParams", "validateQuery", "parse", "schema"]


def _table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _detect_frameworks(cursor) -> dict[str, list[dict]]:
    """Detect frameworks from the frameworks table.

    Returns dict grouped by framework name with path info.
    """
    frameworks: dict[str, list[dict]] = {}

    if not _table_exists(cursor, "frameworks"):
        return frameworks

    cursor.execute("""
        SELECT name, language, path, version FROM frameworks
        WHERE name IS NOT NULL
    """)

    for name, language, path, version in cursor.fetchall():
        name_lower = name.lower()
        if name_lower not in frameworks:
            frameworks[name_lower] = []
        frameworks[name_lower].append({
            "name": name,
            "language": language,
            "path": path or ".",
            "version": version,
        })

    return frameworks


def _analyze_express_boundaries(cursor, framework_info: list[dict], max_entries: int) -> list[dict]:
    """Analyze boundaries for Express.js projects using middleware chains.

    Express middleware runs BEFORE the handler, so we check express_middleware_chains
    for validation middleware rather than doing call graph traversal.

    Key insight (from GPT/Gemini): We derive entry points directly from
    express_middleware_chains instead of joining with api_endpoints.
    Distance = execution_order of validation middleware (0 = first, 1 = second, etc.)
    """
    results = []

    if not _table_exists(cursor, "express_middleware_chains"):
        return results

    # Check if this project uses Zod/Joi for validation (from validation_framework_usage)
    has_validation_framework = False
    if _table_exists(cursor, "validation_framework_usage"):
        cursor.execute("""
            SELECT COUNT(*) FROM validation_framework_usage
            WHERE framework IN ('zod', 'joi', 'yup', 'superstruct') AND is_validator = 1
        """)
        has_validation_framework = cursor.fetchone()[0] > 0

    # Derive entry points directly from express_middleware_chains (GROUP BY unique routes)
    # No LIMIT here - SQL queries are O(1), no performance reason to cap
    cursor.execute("""
        SELECT DISTINCT file, route_line, route_path, route_method
        FROM express_middleware_chains
    """)

    routes = cursor.fetchall()

    for file, route_line, route_path, route_method in routes:
        # Get full path from api_endpoints if available
        full_path = route_path
        if _table_exists(cursor, "api_endpoints"):
            cursor.execute("""
                SELECT full_path FROM api_endpoints
                WHERE file = ? AND line = ?
                LIMIT 1
            """, (file, route_line))
            row = cursor.fetchone()
            if row and row[0]:
                full_path = row[0]

        entry_name = f"{route_method or 'GET'} {full_path}"

        # Get the full middleware chain for this route, ordered by execution
        cursor.execute("""
            SELECT execution_order, handler_expr, handler_type
            FROM express_middleware_chains
            WHERE file = ? AND route_line = ?
            ORDER BY execution_order ASC
        """, (file, route_line))

        chain = cursor.fetchall()

        # Find validation middleware and controller in the chain
        validation_controls = []
        controller_order = None

        for exec_order, handler_expr, handler_type in chain:
            if handler_type == "controller":
                controller_order = exec_order
                continue

            if handler_type != "middleware":
                continue

            # Check if this middleware is a validation middleware
            handler_lower = handler_expr.lower() if handler_expr else ""
            is_validation = any(
                pat.lower() in handler_lower
                for pat in EXPRESS_VALIDATION_PATTERNS
            )

            if is_validation:
                # Distance = execution_order (0 = first middleware = immediate validation)
                # If validation is at order 0, it's the first thing that runs = distance 0
                # If validation is at order 2, two other middlewares ran first = distance 2
                validation_controls.append({
                    "control_function": handler_expr,
                    "control_file": file,
                    "control_line": route_line,
                    "distance": exec_order,
                    "path": [f"middleware[{i}]:{h}" for i, h, _ in chain[:exec_order + 1]],
                })

        # Use measure_boundary_quality for consistent scoring
        quality = measure_boundary_quality(validation_controls)

        # Build violations based on quality
        violations = []
        if quality["quality"] == "missing":
            violations.append({
                "type": "NO_VALIDATION",
                "severity": "CRITICAL",
                "message": "Express route has no validation middleware in chain",
                "facts": quality["facts"],
            })
        elif quality["quality"] == "fuzzy":
            # Check for distance issues
            for control in validation_controls:
                if control["distance"] >= 3:
                    violations.append({
                        "type": "VALIDATION_DISTANCE",
                        "severity": "HIGH",
                        "message": f"Validation '{control['control_function']}' at position {control['distance']} in middleware chain",
                        "facts": [
                            f"Data passes through {control['distance']} middleware(s) before validation",
                            "Earlier middleware may process unvalidated data",
                        ],
                    })

        results.append({
            "entry_point": entry_name,
            "entry_file": file,
            "entry_line": route_line,
            "controls": validation_controls,
            "quality": quality,
            "violations": violations,
            "framework": "express",
        })

    return results


def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """Analyze input validation boundaries across all entry points.

    Uses framework-aware analysis when possible:
    - Express: Checks express_middleware_chains for validation middleware
    - FastAPI/Django: (TODO) Check python decorators and validators
    - Go/Rust: (TODO) Check framework-specific patterns

    Falls back to generic call graph BFS for unknown frameworks.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []
    analyzed_files: set[tuple[str, int]] = set()  # Track (file, line) already analyzed

    try:
        # Step 1: Detect frameworks
        frameworks = _detect_frameworks(cursor)

        # Step 2: Route to framework-specific analyzers
        if "express" in frameworks:
            express_results = _analyze_express_boundaries(
                cursor, frameworks["express"], max_entries
            )
            results.extend(express_results)
            # Track which entry points we've analyzed
            for r in express_results:
                analyzed_files.add((r["entry_file"], r["entry_line"]))

        # TODO: Add FastAPI analyzer
        # if "fastapi" in frameworks:
        #     results.extend(_analyze_fastapi_boundaries(cursor, frameworks["fastapi"], max_entries))

        # TODO: Add Django analyzer
        # if "django" in frameworks:
        #     results.extend(_analyze_django_boundaries(cursor, frameworks["django"], max_entries))

        # Step 3: Fall back to generic BFS for remaining entry points
        remaining_entries = max_entries - len(results)
        if remaining_entries <= 0:
            return results

        entry_points = []

        if _table_exists(cursor, "python_routes"):
            cursor.execute(
                """
                SELECT file, line, pattern, method FROM python_routes
                WHERE pattern IS NOT NULL
                LIMIT ?
            """,
                (max_entries // 3,),
            )
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append(
                    {
                        "type": "http",
                        "name": f"{method or 'GET'} {pattern}",
                        "file": file,
                        "line": line,
                    }
                )

        if _table_exists(cursor, "js_routes"):
            cursor.execute(
                """
                SELECT file, line, pattern, method FROM js_routes
                WHERE pattern IS NOT NULL
                LIMIT ?
            """,
                (max_entries // 3,),
            )
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append(
                    {
                        "type": "http",
                        "name": f"{method or 'GET'} {pattern}",
                        "file": file,
                        "line": line,
                    }
                )

        if _table_exists(cursor, "api_endpoints"):
            cursor.execute(
                """
                SELECT file, line, pattern, method FROM api_endpoints
                WHERE pattern IS NOT NULL
                LIMIT ?
            """,
                (max_entries // 3,),
            )
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append(
                    {
                        "type": "http",
                        "name": f"{method or 'GET'} {pattern}",
                        "file": file,
                        "line": line,
                    }
                )

        if _table_exists(cursor, "go_routes"):
            cursor.execute(
                """
                SELECT file, line, path, method FROM go_routes
                WHERE path IS NOT NULL
                LIMIT ?
            """,
                (max_entries // 4,),
            )
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append(
                    {
                        "type": "http",
                        "name": f"{method or 'GET'} {pattern}",
                        "file": file,
                        "line": line,
                    }
                )

        if _table_exists(cursor, "rust_attributes"):
            cursor.execute(
                """
                SELECT file_path, target_line, args, attribute_name FROM rust_attributes
                WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route')
                AND args IS NOT NULL
                LIMIT ?
            """,
                (max_entries // 4,),
            )
            for file, line, pattern, method in cursor.fetchall():
                entry_points.append(
                    {
                        "type": "http",
                        "name": f"{method.upper()} {pattern}",
                        "file": file,
                        "line": line or 0,
                    }
                )

        # Filter out entry points already analyzed by framework-specific analyzers
        entry_points = [
            ep for ep in entry_points
            if (ep["file"], ep["line"]) not in analyzed_files
        ]

        # If no remaining entry points, return framework-specific results
        if not entry_points:
            return results

        # Load call graph for generic BFS analysis
        graph_db_path = str(Path(db_path).parent / "graphs.db")
        store = XGraphStore(graph_db_path)
        call_graph = store.load_call_graph()

        # If graph is empty but we have framework results, just return those
        if not call_graph.get("nodes") or not call_graph.get("edges"):
            if results:
                # We have framework-specific results, graph not needed
                return results
            raise RuntimeError(
                f"Graph DB empty or missing at {graph_db_path}. "
                "Run 'aud graph build' to generate the call graph."
            )

        _build_graph_index(call_graph)

        for entry in entry_points[:remaining_entries]:
            controls = find_all_paths_to_controls(
                db_path=db_path,
                entry_file=entry["file"],
                entry_line=entry["line"],
                control_patterns=VALIDATION_PATTERNS,
                max_depth=5,
                call_graph=call_graph,
            )

            quality = measure_boundary_quality(controls)

            violations = []

            if quality["quality"] == "missing":
                violations.append(
                    {
                        "type": "NO_VALIDATION",
                        "severity": "CRITICAL",
                        "message": "Entry point accepts external data without validation control in call chain",
                        "facts": quality["facts"],
                    }
                )

            elif quality["quality"] == "fuzzy":
                if len(controls) > 1:
                    control_names = [c["control_function"] for c in controls]
                    violations.append(
                        {
                            "type": "SCATTERED_VALIDATION",
                            "severity": "MEDIUM",
                            "message": f"Multiple validation controls: {', '.join(control_names)}",
                            "facts": quality["facts"],
                        }
                    )

                for control in controls:
                    if control["distance"] >= 3:
                        violations.append(
                            {
                                "type": "VALIDATION_DISTANCE",
                                "severity": "HIGH",
                                "message": f"Validation '{control['control_function']}' occurs at distance {control['distance']}",
                                "control": control,
                                "facts": [
                                    f"Data flows through {control['distance']} functions before validation",
                                    f"Call path: {' -> '.join(control['path'])}",
                                    f"Distance {control['distance']} creates {control['distance']} potential unvalidated code paths",
                                ],
                            }
                        )

            results.append(
                {
                    "entry_point": entry["name"],
                    "entry_file": entry["file"],
                    "entry_line": entry["line"],
                    "controls": controls,
                    "quality": quality,
                    "violations": violations,
                }
            )

    finally:
        conn.close()

    return results


def generate_report(analysis_results: list[dict]) -> str:
    """Generate human-readable boundary analysis report."""
    total = len(analysis_results)
    clear = sum(1 for r in analysis_results if r["quality"]["quality"] == "clear")
    acceptable = sum(1 for r in analysis_results if r["quality"]["quality"] == "acceptable")
    fuzzy = sum(1 for r in analysis_results if r["quality"]["quality"] == "fuzzy")
    missing = sum(1 for r in analysis_results if r["quality"]["quality"] == "missing")

    critical_violations = []
    high_violations = []
    medium_violations = []

    for result in analysis_results:
        for violation in result["violations"]:
            violation["entry"] = result["entry_point"]
            violation["file"] = result["entry_file"]
            violation["line"] = result["entry_line"]

            if violation["severity"] == "CRITICAL":
                critical_violations.append(violation)
            elif violation["severity"] == "HIGH":
                high_violations.append(violation)
            else:
                medium_violations.append(violation)

    report = []
    report.append("=== INPUT VALIDATION BOUNDARY ANALYSIS ===\n")
    report.append(f"Entry Points Analyzed: {total}")
    report.append(f"  Clear Boundaries:      {clear} ({clear * 100 // total if total else 0}%)")
    report.append(
        f"  Acceptable Boundaries: {acceptable} ({acceptable * 100 // total if total else 0}%)"
    )
    report.append(f"  Fuzzy Boundaries:      {fuzzy} ({fuzzy * 100 // total if total else 0}%)")
    report.append(f"  Missing Boundaries:    {missing} ({missing * 100 // total if total else 0}%)")
    report.append(f"\nBoundary Score: {(clear + acceptable) * 100 // total if total else 0}%\n")

    # Show 5 from each category for balanced visibility
    display_limit = 5

    if critical_violations:
        report.append(f"\n[CRITICAL] FINDINGS ({len(critical_violations)}):\n")
        for i, v in enumerate(critical_violations[:display_limit], 1):
            report.append(f"{i}. {v['entry']}")
            report.append(f"   File: {v['file']}:{v['line']}")
            report.append(f"   Observation: {v['message']}")
            if "facts" in v and v["facts"]:
                report.append(f"   Facts: {v['facts'][0]}\n")
            else:
                report.append("")

    if high_violations:
        report.append(f"\n[HIGH] FINDINGS ({len(high_violations)}):\n")
        for i, v in enumerate(high_violations[:display_limit], 1):
            report.append(f"{i}. {v['entry']}")
            report.append(f"   File: {v['file']}:{v['line']}")
            report.append(f"   Observation: {v['message']}")
            if "facts" in v and v["facts"]:
                for fact in v["facts"]:
                    report.append(f"   - {fact}")
                report.append("")

    if medium_violations:
        report.append(f"\n[MEDIUM] FINDINGS ({len(medium_violations)}):\n")
        for i, v in enumerate(medium_violations[:display_limit], 1):
            report.append(f"{i}. {v['entry']}")
            report.append(f"   File: {v['file']}:{v['line']}")
            report.append(f"   Observation: {v['message']}")
            if "facts" in v and v["facts"]:
                report.append(f"   Facts: {v['facts'][0]}\n")
            else:
                report.append("")

    if clear > 0:
        report.append(f"\n[CLEAR] BOUNDARIES ({clear}):\n")
        good_examples = [r for r in analysis_results if r["quality"]["quality"] == "clear"]
        for i, example in enumerate(good_examples[:display_limit], 1):
            report.append(f"{i}. {example['entry_point']}")
            report.append(f"   File: {example['entry_file']}:{example['entry_line']}")
            if example["controls"]:
                control = example["controls"][0]
                report.append(f"   Control: {control['control_function']} at distance 0")
            report.append(f"   Status: {example['quality']['reason']}\n")

    return "\n".join(report)
