"""Input Validation Boundary Analyzer.

Binary quality assessment: validated or unvalidated.
Uses taint registry for input detection and middleware classification.
"""

import sqlite3
from pathlib import Path

from loguru import logger

from theauditor.boundaries.distance import (
    _build_graph_index,
    find_all_paths_to_controls,
    measure_boundary_quality,
)
from theauditor.graph.store import XGraphStore

VALIDATION_PATTERNS = ["validate", "parse", "check", "sanitize", "clean", "schema", "validator"]

# Middleware classification - determines what counts toward "distance"
MIDDLEWARE_TYPES = {
    "AUTH": ["requireAuth", "authenticate", "verifyToken", "passport", "guard", "jwt", "session"],
    "RATE_LIMIT": ["rateLimit", "slowDown", "throttle"],
    "CONTEXT": ["tenant", "context", "cors", "compression", "helmet"],
    "PARSER": ["json", "urlencoded", "multer", "upload", "bodyParser", "cookieParser"],
    "VALIDATION": [
        "validate", "validateBody", "validateParams", "validateQuery",
        "check", "schema", "zod", "joi", "yup", "parse",
    ],
}

# Input source patterns (user input detection)
INPUT_SOURCE_PATTERNS = [
    "req.body", "req.query", "req.params", "request.body", "request.query",
    "request.data", "request.json", "request.form", "request.args",
    "ctx.request.body", "ctx.params", "ctx.query",
]


def classify_middleware(handler_expr: str) -> str:
    """Classify middleware by type. AUTH/RATE_LIMIT/CONTEXT don't count toward distance."""
    if not handler_expr:
        return "UNKNOWN"

    expr_lower = handler_expr.lower()

    for mw_type, patterns in MIDDLEWARE_TYPES.items():
        if any(p.lower() in expr_lower for p in patterns):
            return mw_type

    return "UNKNOWN"


def _check_taint_coverage(cursor, file: str) -> bool:
    """Check if this file has flows in resolved_flow_audit (taint already analyzed it)."""
    try:
        cursor.execute("""
            SELECT 1 FROM resolved_flow_audit
            WHERE source_file = ? AND status IN ('VULNERABLE', 'SANITIZED', 'REACHABLE')
            LIMIT 1
        """, (file,))
        return cursor.fetchone() is not None
    except sqlite3.OperationalError:
        # Table doesn't exist - taint hasn't run
        logger.warning("resolved_flow_audit not found. Run 'aud full' for complete analysis.")
        return False


def _route_accepts_input(cursor, route_file: str) -> bool:
    """Check if route's handler uses request input. Polyglot-aware.

    Derives handler file from route file and queries variable_usage table.
    - Express: routes/*.routes.ts -> controllers/*.controller.ts
    - Python: handler is in same file as route decorator
    - Go/Rust: NOT YET SUPPORTED (variable_usage not indexed)
    """
    # Express: routes/*.routes.ts -> controllers/*.controller.ts
    if "/routes/" in route_file and ".routes." in route_file:
        handler_file = route_file.replace("/routes/", "/controllers/").replace(
            ".routes.", ".controller."
        )
        var_name = "req"

    # Python (Flask/Django/FastAPI): handler is in same file as route
    elif route_file.endswith(".py"):
        handler_file = route_file
        var_name = "request"

    # Default: assume same file, look for req
    else:
        handler_file = route_file
        var_name = "req"

    # Single query - no fallback
    cursor.execute(
        """
        SELECT 1 FROM variable_usage
        WHERE file = ? AND variable_name = ? AND usage_type = 'read'
        LIMIT 1
    """,
        (handler_file, var_name),
    )

    return cursor.fetchone() is not None


# Framework-specific validation middleware patterns (legacy, kept for compatibility)
EXPRESS_VALIDATION_PATTERNS = MIDDLEWARE_TYPES["VALIDATION"]

# Django middleware patterns that provide validation/security
DJANGO_VALIDATION_MIDDLEWARE = [
    "csrfviewmiddleware",
    "authenticationmiddleware",
    "sessionmiddleware",
    "securitymiddleware",
    "xframeoptions",
    "contenttype",
    "validation",
    "sanitize",
    "permission",
]

# Django decorator patterns that indicate security controls
DJANGO_SECURITY_DECORATORS = [
    "login_required",
    "permission_required",
    "user_passes_test",
    "csrf_protect",
    "require_http_methods",
    "require_POST",
    "require_GET",
    "sensitive_post_parameters",
    "sensitive_variables",
    "never_cache",
]


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


def _get_global_middleware(cursor) -> list[tuple]:
    """Get global middleware applied via router.use() or app.use().

    Global middleware applies to ALL routes and should be virtually prepended.
    """
    if not _table_exists(cursor, "express_middleware_chains"):
        return []

    cursor.execute("""
        SELECT execution_order, handler_expr, handler_type
        FROM express_middleware_chains
        WHERE route_path IN ('/', '*', '')
        ORDER BY execution_order ASC
    """)

    return cursor.fetchall()


def _analyze_express_boundaries(cursor, framework_info: list[dict], max_entries: int) -> list[dict]:
    """Analyze boundaries for Express.js projects using middleware chains.

    Express middleware runs BEFORE the handler. Uses middleware classification
    to ignore AUTH/RATE_LIMIT for distance calculation (they don't process input).

    Quality is binary: validated or unvalidated.
    """
    results = []

    if not _table_exists(cursor, "express_middleware_chains"):
        return results

    # Get global middleware (router.use/app.use) to virtually prepend
    global_middleware = _get_global_middleware(cursor)

    # Derive entry points directly from express_middleware_chains
    cursor.execute("""
        SELECT DISTINCT file, route_line, route_path, route_method
        FROM express_middleware_chains
        WHERE route_path NOT IN ('/', '*', '')
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

        # Get the route-specific middleware chain
        cursor.execute("""
            SELECT execution_order, handler_expr, handler_type
            FROM express_middleware_chains
            WHERE file = ? AND route_line = ?
            ORDER BY execution_order ASC
        """, (file, route_line))

        route_chain = cursor.fetchall()

        # Virtual prepend: global middleware + route-specific chain
        full_chain = list(global_middleware) + list(route_chain)

        # Find validation middleware using classification
        validation_controls = []
        effective_distance = 0  # Only count PARSER/UNKNOWN middleware

        for _exec_order, handler_expr, handler_type in full_chain:
            if handler_type == "controller":
                continue

            if handler_type != "middleware":
                continue

            mw_type = classify_middleware(handler_expr)

            # AUTH/RATE_LIMIT/CONTEXT don't count toward distance
            if mw_type in ["AUTH", "RATE_LIMIT", "CONTEXT"]:
                continue

            if mw_type == "VALIDATION":
                validation_controls.append({
                    "control_function": handler_expr,
                    "control_file": file,
                    "control_line": route_line,
                    "distance": effective_distance,
                    "middleware_type": mw_type,
                })
            elif mw_type in ["PARSER", "UNKNOWN"]:
                # Only PARSER and UNKNOWN increase effective distance
                effective_distance += 1

        # Check if route accepts input (queries controller file via variable_usage)
        accepts_input = _route_accepts_input(cursor, file)

        # Binary quality assessment
        quality = measure_boundary_quality(validation_controls, accepts_input)

        # Build violations based on quality
        violations = []
        if quality["quality"] == "unvalidated":
            violations.append({
                "type": "NO_VALIDATION",
                "severity": "MEDIUM",
                "message": "Express route accepts input but has no validation middleware",
                "facts": quality["facts"],
            })

        results.append({
            "entry_point": entry_name,
            "entry_file": file,
            "entry_line": route_line,
            "controls": validation_controls,
            "quality": quality,
            "violations": violations,
            "framework": "express",
            "accepts_input": accepts_input,
        })

    return results


def _analyze_django_boundaries(cursor, framework_info: list[dict], max_entries: int) -> list[dict]:
    """Analyze boundaries for Django projects using middleware + decorators.

    Django's validation architecture:
    1. Global middleware (MIDDLEWARE setting) - runs BEFORE views
       - CsrfViewMiddleware, AuthenticationMiddleware, etc.
       - Middleware with has_process_request/has_process_view runs before handler
    2. View decorators (@login_required, @csrf_protect, etc.)
    3. View permission checks (has_permission_check in class-based views)
    4. Explicit validation in view code (forms, serializers)

    Distance calculation:
    - Middleware with process_request = distance 0 (runs first)
    - Middleware with process_view = distance 1 (runs after URL routing)
    - Decorators = distance 2 (applied to view)
    - In-view validation = distance 3+ (inside handler)
    """
    results = []

    # Step 1: Get global middleware (applies to ALL routes)
    global_middleware = []
    if _table_exists(cursor, "python_django_middleware"):
        cursor.execute("""
            SELECT file, line, middleware_class_name,
                   has_process_request, has_process_view,
                   has_process_response, has_process_exception
            FROM python_django_middleware
        """)
        for row in cursor.fetchall():
            file, line, class_name, has_req, has_view, has_resp, has_exc = row
            middleware_lower = class_name.lower() if class_name else ""

            # Check if this is a validation/security middleware
            is_validation = any(
                pat in middleware_lower for pat in DJANGO_VALIDATION_MIDDLEWARE
            )

            global_middleware.append({
                "file": file,
                "line": line,
                "class_name": class_name,
                "has_process_request": bool(has_req),
                "has_process_view": bool(has_view),
                "is_validation": is_validation,
            })

    # Step 2: Get Django entry points
    # First try python_routes, then derive from decorated views
    routes = []

    if _table_exists(cursor, "python_routes"):
        cursor.execute("""
            SELECT file, line, pattern, method, handler_function
            FROM python_routes
            WHERE framework = 'django'
        """)
        routes = [(r[0], r[1], r[2], r[3], r[4]) for r in cursor.fetchall()]

    # If no routes in python_routes, derive from Django-decorated view functions
    # Django views are typically decorated with @csrf_exempt, @require_http_methods, etc.
    if not routes and _table_exists(cursor, "python_decorators"):
        django_view_decorators = (
            "csrf_exempt", "csrf_protect", "require_http_methods",
            "require_POST", "require_GET", "require_safe",
            "login_required", "permission_required", "user_passes_test",
        )
        placeholders = ",".join("?" * len(django_view_decorators))
        cursor.execute(f"""
            SELECT DISTINCT d.file, MIN(d.line) as line, d.target_name
            FROM python_decorators d
            WHERE d.decorator_name IN ({placeholders})
              AND d.target_type = 'function'
            GROUP BY d.file, d.target_name
            ORDER BY d.file, line
            LIMIT ?
        """, (*django_view_decorators, max_entries))

        for file, line, handler_function in cursor.fetchall():
            # Derive pattern from function name (best effort without urls.py parsing)
            pattern = f"/{handler_function.replace('_', '-')}"
            routes.append((file, line, pattern, "ANY", handler_function))

    for file, line, pattern, method, handler_function in routes:
        entry_name = f"{method or 'GET'} {pattern or '/'}"
        validation_controls = []

        # Step 3: Check global middleware (distance 0-1)
        for mw in global_middleware:
            if mw["is_validation"]:
                # process_request runs before URL dispatch = distance 0
                # process_view runs after URL dispatch = distance 1
                if mw["has_process_request"]:
                    validation_controls.append({
                        "control_function": mw["class_name"],
                        "control_file": mw["file"],
                        "control_line": mw["line"],
                        "distance": 0,
                        "path": [f"middleware:{mw['class_name']}"],
                        "control_type": "middleware_request",
                    })
                elif mw["has_process_view"]:
                    validation_controls.append({
                        "control_function": mw["class_name"],
                        "control_file": mw["file"],
                        "control_line": mw["line"],
                        "distance": 1,
                        "path": [f"middleware:{mw['class_name']}"],
                        "control_type": "middleware_view",
                    })

        # Step 4: Check view decorators (distance 2)
        if _table_exists(cursor, "python_decorators") and handler_function:
            cursor.execute("""
                SELECT decorator_name, line
                FROM python_decorators
                WHERE file = ? AND target_name = ?
            """, (file, handler_function))

            for dec_name, dec_line in cursor.fetchall():
                dec_lower = dec_name.lower() if dec_name else ""
                is_security_decorator = any(
                    pat in dec_lower for pat in DJANGO_SECURITY_DECORATORS
                )
                if is_security_decorator:
                    validation_controls.append({
                        "control_function": dec_name,
                        "control_file": file,
                        "control_line": dec_line,
                        "distance": 2,
                        "path": [f"decorator:@{dec_name}", handler_function or "view"],
                        "control_type": "decorator",
                    })

        # Step 5: Check class-based view permission checks (distance 2)
        if _table_exists(cursor, "python_django_views"):
            cursor.execute("""
                SELECT view_class_name, has_permission_check
                FROM python_django_views
                WHERE file = ? AND line = ?
            """, (file, line))
            view_row = cursor.fetchone()
            if view_row and view_row[1]:  # has_permission_check
                validation_controls.append({
                    "control_function": f"{view_row[0]}.has_permission",
                    "control_file": file,
                    "control_line": line,
                    "distance": 2,
                    "path": [f"view:{view_row[0]}", "permission_check"],
                    "control_type": "view_permission",
                })

        # Step 6: Check for validators in the view file (distance 3+)
        if _table_exists(cursor, "python_validators"):
            cursor.execute("""
                SELECT validator_method, line
                FROM python_validators
                WHERE file = ?
                LIMIT 5
            """, (file,))
            for val_method, val_line in cursor.fetchall():
                validation_controls.append({
                    "control_function": val_method,
                    "control_file": file,
                    "control_line": val_line,
                    "distance": 3,
                    "path": [handler_function or "view", val_method],
                    "control_type": "validator",
                })

        # Check if route accepts input (queries same file for Python)
        accepts_input = _route_accepts_input(cursor, file)

        # Binary quality assessment
        quality = measure_boundary_quality(validation_controls, accepts_input)

        # Build violations
        violations = []
        if quality["quality"] == "unvalidated":
            violations.append({
                "type": "NO_VALIDATION",
                "severity": "MEDIUM",
                "message": "Django route accepts input but has no validation",
                "facts": quality["facts"],
            })

        results.append({
            "entry_point": entry_name,
            "entry_file": file,
            "entry_line": line,
            "controls": validation_controls,
            "quality": quality,
            "violations": violations,
            "framework": "django",
            "accepts_input": accepts_input,
        })

    return results


def analyze_input_validation_boundaries(db_path: str, max_entries: int = 50) -> list[dict]:
    """Analyze input validation boundaries across all entry points.

    Uses framework-aware analysis when possible:
    - Express: Checks express_middleware_chains for validation middleware
    - Django: Checks python_django_middleware, decorators, and view permissions
    - FastAPI: (TODO) Check python decorators and validators
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
        #     results.extend(_analyze_fastapi_boundaries(...))

        # Django analyzer - queries python_django_middleware for global middleware awareness
        if "django" in frameworks:
            django_results = _analyze_django_boundaries(
                cursor, frameworks["django"], max_entries
            )
            results.extend(django_results)
            for r in django_results:
                analyzed_files.add((r["entry_file"], r["entry_line"]))

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

            # Check if entry accepts input (generic check - assume yes for HTTP routes)
            accepts_input = True  # Generic routes are HTTP, assume input

            # Binary quality assessment
            quality = measure_boundary_quality(controls, accepts_input)

            violations = []

            if quality["quality"] == "unvalidated":
                violations.append(
                    {
                        "type": "NO_VALIDATION",
                        "severity": "MEDIUM",
                        "message": "Entry point accepts input without validation",
                        "facts": quality["facts"],
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
                    "accepts_input": accepts_input,
                }
            )

    finally:
        conn.close()

    return results


def generate_report(analysis_results: list[dict]) -> str:
    """Generate human-readable boundary analysis report.

    Quality levels:
    - validated: Has validation middleware
    - unvalidated: Accepts input but no validation
    - no_input: Route doesn't accept user input
    """
    total = len(analysis_results)
    validated = sum(1 for r in analysis_results if r["quality"]["quality"] == "validated")
    unvalidated = sum(1 for r in analysis_results if r["quality"]["quality"] == "unvalidated")
    no_input = sum(1 for r in analysis_results if r["quality"]["quality"] == "no_input")

    # Collect violations by severity
    medium_violations = []

    for result in analysis_results:
        for violation in result["violations"]:
            violation["entry"] = result["entry_point"]
            violation["file"] = result["entry_file"]
            violation["line"] = result["entry_line"]
            medium_violations.append(violation)

    report = []
    report.append("=== INPUT VALIDATION BOUNDARY ANALYSIS ===\n")
    report.append(f"Entry Points Analyzed: {total}")
    report.append(f"  Validated:     {validated} ({validated * 100 // total if total else 0}%)")
    report.append(f"  Unvalidated:   {unvalidated} ({unvalidated * 100 // total if total else 0}%)")
    report.append(f"  No Input:      {no_input} ({no_input * 100 // total if total else 0}%)")

    # Score = validated + no_input (routes without input don't need validation)
    score = (validated + no_input) * 100 // total if total else 0
    report.append(f"\nBoundary Score: {score}%\n")

    display_limit = 10

    # Show unvalidated routes (action items)
    if unvalidated > 0:
        report.append(f"\n[UNVALIDATED] ({unvalidated}):\n")
        unvalidated_examples = [
            r for r in analysis_results if r["quality"]["quality"] == "unvalidated"
        ]
        for i, example in enumerate(unvalidated_examples[:display_limit], 1):
            report.append(f"{i}. {example['entry_point']}")
            report.append(f"   File: {example['entry_file']}:{example['entry_line']}")
            report.append(f"   Status: {example['quality']['reason']}\n")
        if unvalidated > display_limit:
            report.append(f"   ... and {unvalidated - display_limit} more\n")

    # Show validated routes (good examples)
    if validated > 0:
        report.append(f"\n[VALIDATED] ({validated}):\n")
        validated_examples = [r for r in analysis_results if r["quality"]["quality"] == "validated"]
        for i, example in enumerate(validated_examples[:display_limit], 1):
            report.append(f"{i}. {example['entry_point']}")
            report.append(f"   File: {example['entry_file']}:{example['entry_line']}")
            if example["controls"]:
                control = example["controls"][0]
                report.append(f"   Control: {control['control_function']}")
            report.append(f"   Status: {example['quality']['reason']}\n")
        if validated > display_limit:
            report.append(f"   ... and {validated - display_limit} more\n")

    # Show no_input routes (informational)
    if no_input > 0:
        report.append(f"\n[NO INPUT] ({no_input}):\n")
        no_input_examples = [r for r in analysis_results if r["quality"]["quality"] == "no_input"]
        for i, example in enumerate(no_input_examples[:5], 1):
            report.append(f"{i}. {example['entry_point']}")
            report.append(f"   File: {example['entry_file']}:{example['entry_line']}")
            report.append("   Status: No user input detected\n")
        if no_input > 5:
            report.append(f"   ... and {no_input - 5} more\n")

    return "\n".join(report)
