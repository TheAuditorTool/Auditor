"""Input Validation Boundary Analyzer."""

import sqlite3
from pathlib import Path

from theauditor.boundaries.distance import (
    find_all_paths_to_controls,
    measure_boundary_quality,
    _build_graph_index,
)
from theauditor.graph.store import XGraphStore

VALIDATION_PATTERNS = ["validate", "parse", "check", "sanitize", "clean", "schema", "validator"]


def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """Analyze input validation boundaries across all entry points."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    results = []

    try:
        entry_points = []

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

        # Go routes (go_routes uses 'file' column, not 'file_path')
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

        # Rust routes (from attributes)
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

        # Load graph ONCE before loop (O(1) instead of O(N) disk I/O)
        graph_db_path = str(Path(db_path).parent / "graphs.db")
        store = XGraphStore(graph_db_path)
        call_graph = store.load_call_graph()

        if not call_graph.get("nodes") or not call_graph.get("edges"):
            raise RuntimeError(
                f"Graph DB empty or missing at {graph_db_path}. "
                "Run 'aud graph build' to generate the call graph."
            )

        # Build index ONCE for O(1) node lookups (instead of O(N) per lookup)
        _build_graph_index(call_graph)

        for entry in entry_points[:max_entries]:
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

    if critical_violations:
        report.append(f"\n[CRITICAL] FINDINGS ({len(critical_violations)}):\n")
        for i, v in enumerate(critical_violations[:10], 1):
            report.append(f"{i}. {v['entry']}")
            report.append(f"   File: {v['file']}:{v['line']}")
            report.append(f"   Observation: {v['message']}")
            if "facts" in v and v["facts"]:
                report.append(f"   Facts: {v['facts'][0]}\n")
            else:
                report.append("")

    if high_violations:
        report.append(f"\n[HIGH] FINDINGS ({len(high_violations)}):\n")
        for i, v in enumerate(high_violations[:5], 1):
            report.append(f"{i}. {v['entry']}")
            report.append(f"   File: {v['file']}:{v['line']}")
            report.append(f"   Observation: {v['message']}")
            if "facts" in v and v["facts"]:
                for fact in v["facts"]:
                    report.append(f"   - {fact}")
                report.append("")

    if clear > 0:
        report.append(f"\n[CLEAR] BOUNDARIES ({clear}):\n")
        good_examples = [r for r in analysis_results if r["quality"]["quality"] == "clear"]
        for i, example in enumerate(good_examples[:3], 1):
            report.append(f"{i}. {example['entry_point']}")
            report.append(f"   File: {example['entry_file']}:{example['entry_line']}")
            if example["controls"]:
                control = example["controls"][0]
                report.append(f"   Control: {control['control_function']} at distance 0")
            report.append(f"   Status: {example['quality']['reason']}\n")

    return "\n".join(report)
