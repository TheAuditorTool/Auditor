"""Input Validation Boundary Analyzer.

Detects where external input enters the system and measures distance to validation.

Boundary Definition:
    - Entry Points: HTTP routes, CLI commands, file uploads, message handlers
    - Control Points: Schema validation, type checks, sanitizers
    - Violation: Entry point uses external data before validation

Examples of Violations:

    BAD (distance = 3):
        @app.post('/user')
        def create_user(request):           # ← Entry (req.body untrusted)
            user_service.create(request.json)   # ← Distance 1 (no validation yet!)
                def create(data):
                    db.insert('users', data)    # ← Distance 2 (STILL no validation!)
                        def insert(table, data):
                            validate(data)      # ← Distance 3 (TOO LATE! Data already in DB layer)

    GOOD (distance = 0):
        @app.post('/user')
        def create_user(data: UserSchema):  # ← Validation IN signature (distance 0)
            db.insert('users', data)        # ← Safe! Already validated
"""

import sqlite3

from theauditor.boundaries.distance import find_all_paths_to_controls, measure_boundary_quality

VALIDATION_PATTERNS = ["validate", "parse", "check", "sanitize", "clean", "schema", "validator"]


def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """
    Analyze input validation boundaries across all entry points.

    Args:
        db_path: Path to repo_index.db
        max_entries: Maximum entry points to analyze (performance limit)

    Returns:
        List of boundary analysis results with:
            - entry_point: Route/command name
            - entry_file: File path
            - entry_line: Line number
            - controls: List of validation points found
            - quality: Boundary quality assessment
            - violations: List of issues found

    Example Output:
        [
            {
                'entry_point': 'POST /api/users',
                'entry_file': 'src/routes/users.js',
                'entry_line': 34,
                'controls': [
                    {'control_function': 'validateUser', 'distance': 2, ...}
                ],
                'quality': {
                    'quality': 'acceptable',
                    'reason': 'Single validation at distance 2',
                    ...
                },
                'violations': []
            }
        ]
    """
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

        for entry in entry_points[:max_entries]:
            controls = find_all_paths_to_controls(
                db_path=db_path,
                entry_file=entry["file"],
                entry_line=entry["line"],
                control_patterns=VALIDATION_PATTERNS,
                max_depth=5,
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
    """
    Generate human-readable boundary analysis report.

    Args:
        analysis_results: Output from analyze_input_validation_boundaries()

    Returns:
        Formatted text report
    """
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
