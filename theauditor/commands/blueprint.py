"""Blueprint command - architectural visualization of indexed codebase.

Truth courier mode: Shows facts about code architecture with NO recommendations.
Supports drill-down flags for specific analysis areas.
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions

VALID_TABLES = frozenset({"symbols", "function_call_args", "assignments", "api_endpoints"})


@click.command(cls=RichCommand)
@click.option("--structure", is_flag=True, help="Drill down into codebase structure details")
@click.option("--graph", is_flag=True, help="Drill down into import/call graph analysis")
@click.option("--hotspots", is_flag=True, help="Alias for --graph (shows hot files and bottlenecks)")
@click.option("--security", is_flag=True, help="Drill down into security surface details")
@click.option("--taint", is_flag=True, help="Drill down into taint analysis details")
@click.option("--boundaries", is_flag=True, help="Drill down into boundary distance analysis")
@click.option(
    "--deps", is_flag=True, help="Drill down into dependency analysis (packages, versions)"
)
@click.option("--all", is_flag=True, help="Export all data to JSON (ignores other flags)")
@click.option(
    "--format",
    "output_format",
    default="text",
    type=click.Choice(["text", "json"]),
    help="Output format: text (visual tree), json (structured)",
)
@click.option("--monoliths", is_flag=True, help="Find files >threshold lines (too large for AI)")
@click.option(
    "--threshold",
    default=1950,
    type=int,
    help="Line count threshold for --monoliths (default: 1950)",
)
@click.option("--fce", is_flag=True, help="Drill down into FCE vector convergence analysis")
@click.option("--findings", is_flag=True, help="Drill down into findings from all analysis tools")
@click.option("--findings-tool", help="Filter findings by tool (ruff, eslint, taint, cfg-analysis)")
@click.option("--findings-severity", help="Filter findings by severity (critical, high, medium, low)")
@click.option("--validated", is_flag=True, help="Drill down into validation chain health (type safety)")
@handle_exceptions
def blueprint(
    structure,
    graph,
    hotspots,
    security,
    taint,
    boundaries,
    deps,
    all,
    output_format,
    monoliths,
    threshold,
    fce,
    findings,
    findings_tool,
    findings_severity,
    validated,
):
    """Architectural fact visualization with drill-down analysis modes (NO recommendations).

    Truth-courier mode visualization that presents pure architectural facts extracted from
    indexed codebase with zero prescriptive language. Supports drill-down flags to focus on
    specific dimensions (structure, dependencies, security surface, data flow). Output format
    toggles between visual ASCII tree and structured JSON for programmatic consumption.

    AI ASSISTANT CONTEXT:
      Purpose: Visualize codebase architecture facts (no recommendations)
      Input: .pf/repo_index.db (indexed code)
      Output: Terminal tree or JSON (configurable via --format)
      Prerequisites: aud full (populates database)
      Integration: Architecture documentation, onboarding, refactoring planning
      Performance: ~2-5 seconds (database queries + formatting)

    DRILL-DOWN MODES:
      (default): Top-level overview
        - Module count, file organization tree
        - High-level statistics only

      --structure: File organization details
        - Directory structure with LOC counts
        - Module boundaries and package structure

      --graph: Import and call graph analysis
        - Dependency relationships
        - Circular dependency detection
        - Hotspot identification (highly connected modules)

      --security: Security surface facts
        - JWT/OAuth usage locations
        - SQL query locations
        - API endpoint inventory
        - External service calls

      --taint: Data flow analysis
        - Taint sources (user input, network, files)
        - Taint sinks (SQL, commands, file writes)
        - Data flow paths

      --boundaries: Security boundary distance analysis
        - Entry points (routes, handlers)
        - Control points (validation, auth, sanitization)
        - Distance metrics (calls between entry and control)
        - Quality levels (clear, acceptable, fuzzy, missing)

      --fce: Vector convergence analysis
        - Files with multiple analysis vectors converging
        - Signal density distribution (4/4, 3/4, 2/4, 1/4)
        - High-priority files with 3+ vectors

      --all: Export complete data as JSON

    EXAMPLES:
      aud blueprint
      aud blueprint --structure
      aud blueprint --graph --format json
      aud blueprint --all > architecture.json

    PERFORMANCE: ~2-5 seconds

    RELATED COMMANDS:
      aud graph      # Dedicated graph analysis

    SEE ALSO:
      aud manual blueprint    Learn about architectural visualization
      aud manual architecture How TheAuditor's analysis pipeline works

    NOTE: This command shows FACTS ONLY - no recommendations, no prescriptive
    language. For actionable insights, use 'aud fce' or 'aud full'.

    ADDITIONAL EXAMPLES:
        aud blueprint --all              # Export everything to JSON

    PREREQUISITES:
        aud full            # Complete analysis (recommended)
            OR
        aud full --index    # Fast reindex (basic structure only)
        aud detect-patterns # Optional (for security surface)
        aud taint   # Optional (for data flow)
        aud graph build     # Optional (for import graph)

    WHAT YOU GET (Truth Courier Facts Only):
        - File counts by directory/language
        - Most-called functions (call graph centrality)
        - Security pattern counts (JWT, OAuth, SQL)
        - Taint flow statistics (sources, sinks, paths)
        - Import relationships (internal vs external)
        - NO recommendations, NO "should be", NO prescriptive language
    """
    # --hotspots is an alias for --graph
    if hotspots:
        graph = True

    pf_dir = Path.cwd() / ".pf"
    repo_db = pf_dir / "repo_index.db"
    graphs_db = pf_dir / "graphs.db"

    if not pf_dir.exists() or not repo_db.exists():
        err_console.print(
            "[error]\nERROR: No indexed database found[/error]",
        )
        err_console.print(
            "[error]Run: aud full[/error]",
        )
        raise click.Abort()

    if monoliths:
        return _find_monoliths(str(repo_db), threshold, output_format)

    conn = sqlite3.connect(repo_db)
    conn.row_factory = sqlite3.Row

    import re

    conn.create_function(
        "REGEXP", 2, lambda pattern, value: re.match(pattern, value) is not None if value else False
    )

    try:
        cursor = conn.cursor()

        flags = {
            "structure": structure,
            "graph": graph,
            "security": security,
            "taint": taint,
            "boundaries": boundaries,
            "deps": deps,
            "fce": fce,
            "findings": findings,
            "validated": validated,
            "all": all,
        }

        data = _gather_all_data(cursor, graphs_db, flags)

        if all:
            console.print(json.dumps(data, indent=2), markup=False)
            return

        if structure:
            _show_structure_drilldown(data, cursor)
        elif graph:
            _show_graph_drilldown(data)
        elif security:
            _show_security_drilldown(data, cursor)
        elif taint:
            _show_taint_drilldown(data, cursor)
        elif boundaries:
            _show_boundaries_drilldown(data, cursor)
        elif deps:
            _show_deps_drilldown(data, cursor)
        elif fce:
            _show_fce_drilldown(data)
        elif findings:
            _show_findings_drilldown(cursor, findings_tool, findings_severity)
        elif validated:
            _show_validated_drilldown(data, str(repo_db))
        else:
            if output_format == "json":
                summary = {
                    "structure": data["structure"],
                    "hot_files": data["hot_files"][:5],
                    "security_surface": data["security_surface"],
                    "data_flow": data["data_flow"],
                    "import_graph": data["import_graph"],
                    "performance": data["performance"],
                }
                console.print(json.dumps(summary, indent=2), markup=False)
            else:
                _show_top_level_overview(data)

    finally:
        if conn:
            conn.close()


def _gather_all_data(cursor, graphs_db_path: Path, flags: dict) -> dict:
    """Gather blueprint data with logic gating based on flags.

    Performance: Only runs expensive queries when the relevant flag is set.
    - --structure: naming_conventions, architectural_precedents (regex-heavy)
    - --graph: hot_files, import_graph (JOIN-heavy)
    - --security: security_surface (multiple table scans)
    - --taint: data_flow (taint tables)
    - --boundaries: boundary distance analysis (graphs.db)
    - --all: everything
    - (no flags): minimal set for overview
    """
    data = {}
    run_all = flags.get("all", False)

    no_drilldown = not any(
        [
            flags.get("structure"),
            flags.get("graph"),
            flags.get("security"),
            flags.get("taint"),
            flags.get("boundaries"),
            flags.get("deps"),
            flags.get("fce"),
            flags.get("validated"),
        ]
    )

    data["structure"] = _get_structure(cursor)

    if run_all or flags.get("structure"):
        data["naming_conventions"] = _get_naming_conventions(cursor)
    else:
        data["naming_conventions"] = {}

    if run_all or flags.get("structure"):
        data["architectural_precedents"] = _get_architectural_precedents(cursor)
    else:
        data["architectural_precedents"] = []

    if run_all or flags.get("graph") or no_drilldown:
        data["hot_files"] = _get_hot_files(cursor)
    else:
        data["hot_files"] = []

    if run_all or flags.get("security") or no_drilldown:
        data["security_surface"] = _get_security_surface(cursor)
    else:
        data["security_surface"] = {
            "jwt": {"sign": 0, "verify": 0},
            "oauth": 0,
            "password": 0,
            "sql_queries": {"total": 0, "raw": 0},
            "api_endpoints": {"total": 0, "protected": 0, "unprotected": 0},
        }

    if run_all or flags.get("taint") or no_drilldown:
        data["data_flow"] = _get_data_flow(cursor)
    else:
        data["data_flow"] = {"taint_sources": 0, "taint_paths": 0, "cross_function_flows": 0}

    if run_all or flags.get("graph") or no_drilldown:
        if graphs_db_path.exists():
            data["import_graph"] = _get_import_graph(graphs_db_path)
        else:
            data["import_graph"] = None
    else:
        data["import_graph"] = None

    data["performance"] = _get_performance(cursor, Path.cwd() / ".pf" / "repo_index.db")

    if run_all or flags.get("deps") or no_drilldown:
        data["dependencies"] = _get_dependencies(cursor)
    else:
        data["dependencies"] = {"total": 0, "by_manager": {}, "packages": []}

    if run_all or flags.get("boundaries") or no_drilldown:
        data["boundaries"] = _get_boundaries(cursor, graphs_db_path)
    else:
        data["boundaries"] = {"total_entries": 0, "by_quality": {}, "missing_controls": 0}

    if run_all or flags.get("fce"):
        data["fce"] = _get_fce_data()
    else:
        data["fce"] = {"total_points": 0, "by_density": {}, "convergence_points": []}

    if run_all or flags.get("validated"):
        data["validated"] = _get_validation_chain_health()
    else:
        data["validated"] = {
            "total_chains": 0,
            "by_status": {},
            "break_reasons": {},
            "chains": [],
        }

    return data


def _get_structure(cursor) -> dict:
    """Get codebase structure facts with meaningful categorization."""
    structure = {
        "total_files": 0,
        "total_symbols": 0,
        "by_directory": {},
        "by_language": {},
        "by_type": {},
        "by_category": {},
    }

    cursor.execute("SELECT COUNT(DISTINCT path) FROM symbols")
    structure["total_files"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM symbols")
    structure["total_symbols"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT path FROM symbols GROUP BY path")
    paths = [row[0] for row in cursor.fetchall()]

    dir_counts = defaultdict(int)
    lang_counts = defaultdict(int)
    category_counts = defaultdict(int)

    for path in paths:
        parts = path.split("/")
        if len(parts) > 1:
            top_dir = parts[0]
            dir_counts[top_dir] += 1

        ext = Path(path).suffix
        if ext:
            lang_counts[ext] += 1

        path_lower = path.lower()
        if any(p in path_lower for p in ["test", "spec", "__tests__"]):
            category_counts["test"] += 1
        elif any(p in path_lower for p in ["migration", "migrations", "alembic"]):
            category_counts["migrations"] += 1
        elif any(p in path_lower for p in ["seed", "seeders", "fixtures"]):
            category_counts["seeders"] += 1
        elif any(p in path_lower for p in ["script", "scripts", "tools", "bin"]):
            category_counts["scripts"] += 1
        elif any(p in path_lower for p in ["config", "settings", ".config"]):
            category_counts["config"] += 1
        elif any(p in path_lower for p in ["src/", "app/", "lib/", "pkg/", "theauditor/"]):
            category_counts["source"] += 1
        else:
            category_counts["other"] += 1

    structure["by_directory"] = dict(dir_counts)
    structure["by_language"] = dict(lang_counts)
    structure["by_category"] = dict(category_counts)

    cursor.execute("SELECT type, COUNT(*) as count FROM symbols GROUP BY type")
    structure["by_type"] = {row["type"]: row["count"] for row in cursor.fetchall()}

    return structure


def _get_naming_conventions(cursor) -> dict:
    """Analyze naming conventions from indexed symbols using optimized SQL JOIN."""

    cursor.execute("""
        SELECT
            -- Python functions
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS py_func_snake,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS py_func_camel,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS py_func_pascal,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'function' THEN 1 ELSE 0 END) AS py_func_total,

            -- Python classes
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS py_class_snake,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'class' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS py_class_camel,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS py_class_pascal,
            SUM(CASE WHEN f.ext = '.py' AND s.type = 'class' THEN 1 ELSE 0 END) AS py_class_total,

            -- JavaScript functions
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS js_func_snake,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS js_func_camel,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS js_func_pascal,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'function' THEN 1 ELSE 0 END) AS js_func_total,

            -- JavaScript classes
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS js_class_snake,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'class' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS js_class_camel,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS js_class_pascal,
            SUM(CASE WHEN f.ext IN ('.js', '.jsx') AND s.type = 'class' THEN 1 ELSE 0 END) AS js_class_total,

            -- TypeScript functions
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS ts_func_snake,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS ts_func_camel,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS ts_func_pascal,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'function' THEN 1 ELSE 0 END) AS ts_func_total,

            -- TypeScript classes
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS ts_class_snake,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'class' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS ts_class_camel,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS ts_class_pascal,
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'class' THEN 1 ELSE 0 END) AS ts_class_total,

            -- Go functions
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_func_snake,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_camel,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_func_pascal,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'function' THEN 1 ELSE 0 END) AS go_func_total,

            -- Go structs/interfaces (stored as class type)
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS go_class_snake,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_class_camel,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS go_class_pascal,
            SUM(CASE WHEN f.ext = '.go' AND s.type = 'class' THEN 1 ELSE 0 END) AS go_class_total,

            -- Rust functions
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_func_snake,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_camel,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_func_pascal,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'function' THEN 1 ELSE 0 END) AS rs_func_total,

            -- Rust structs/enums/traits (stored as class type)
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS rs_class_snake,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_class_camel,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS rs_class_pascal,
            SUM(CASE WHEN f.ext = '.rs' AND s.type = 'class' THEN 1 ELSE 0 END) AS rs_class_total,

            -- Bash functions
            SUM(CASE WHEN f.ext IN ('.sh', '.bash') AND s.type = 'function' AND s.name REGEXP '^[a-z_][a-z0-9_]*$' THEN 1 ELSE 0 END) AS sh_func_snake,
            SUM(CASE WHEN f.ext IN ('.sh', '.bash') AND s.type = 'function' AND s.name REGEXP '^[a-z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS sh_func_camel,
            SUM(CASE WHEN f.ext IN ('.sh', '.bash') AND s.type = 'function' AND s.name REGEXP '^[A-Z][a-zA-Z0-9]*$' THEN 1 ELSE 0 END) AS sh_func_pascal,
            SUM(CASE WHEN f.ext IN ('.sh', '.bash') AND s.type = 'function' THEN 1 ELSE 0 END) AS sh_func_total
        FROM symbols s
        JOIN files f ON s.path = f.path
        WHERE s.type IN ('function', 'class')
    """)

    row = cursor.fetchone()

    conventions = {
        "python": {
            "functions": _build_pattern_result(row[0], row[1], row[2], row[3]),
            "classes": _build_pattern_result(row[4], row[5], row[6], row[7]),
        },
        "javascript": {
            "functions": _build_pattern_result(row[8], row[9], row[10], row[11]),
            "classes": _build_pattern_result(row[12], row[13], row[14], row[15]),
        },
        "typescript": {
            "functions": _build_pattern_result(row[16], row[17], row[18], row[19]),
            "classes": _build_pattern_result(row[20], row[21], row[22], row[23]),
        },
        "go": {
            "functions": _build_pattern_result(row[24], row[25], row[26], row[27]),
            "structs": _build_pattern_result(row[28], row[29], row[30], row[31]),
        },
        "rust": {
            "functions": _build_pattern_result(row[32], row[33], row[34], row[35]),
            "types": _build_pattern_result(row[36], row[37], row[38], row[39]),
        },
        "bash": {
            "functions": _build_pattern_result(row[40], row[41], row[42], row[43]),
        },
    }

    return conventions


def _build_pattern_result(
    snake_count: int, camel_count: int, pascal_count: int, total: int
) -> dict:
    """Build pattern analysis result from counts."""
    if total == 0:
        return {}

    results = {}

    if snake_count > 0:
        results["snake_case"] = {
            "count": snake_count,
            "percentage": round((snake_count / total) * 100, 1),
        }
    if camel_count > 0:
        results["camelCase"] = {
            "count": camel_count,
            "percentage": round((camel_count / total) * 100, 1),
        }
    if pascal_count > 0:
        results["PascalCase"] = {
            "count": pascal_count,
            "percentage": round((pascal_count / total) * 100, 1),
        }

    if results:
        dominant = max(results.items(), key=lambda x: x[1]["count"])
        results["dominant"] = dominant[0]
        results["consistency"] = dominant[1]["percentage"]

    return results


def _get_architectural_precedents(cursor) -> list[dict]:
    """Detect plugin loader patterns from import graph (refs table).

    A precedent is a code relationship where a consumer file imports 3+ modules
    from the same directory/prefix. These patterns reveal existing architectural
    conventions that can guide refactoring decisions.

    Performance: <0.1 seconds (pure database query)
    """

    cursor.execute("""
        SELECT src, value
        FROM refs
        WHERE kind IN ('import', 'from', 'require')
          AND src NOT LIKE 'node_modules/%'
          AND src NOT LIKE 'venv/%'
          AND src NOT LIKE '.venv/%'
          AND src NOT LIKE 'dist/%'
          AND src NOT LIKE 'build/%'
    """)

    patterns = defaultdict(lambda: defaultdict(set))

    for row in cursor.fetchall():
        source_file = row["src"]
        value = row["value"]

        if "/" in value:
            parts = Path(value).parts

            meaningful_parts = [
                p for p in parts if p not in (".", "..", "") and not p.startswith("@")
            ]
            if meaningful_parts:
                directory = meaningful_parts[0]
                patterns[source_file][directory].add(value)
        elif "." in value:
            parts = value.split(".")
            prefix = parts[0]

            if prefix not in (
                "typing",
                "pathlib",
                "os",
                "sys",
                "json",
                "re",
                "ast",
                "dataclasses",
                "datetime",
                "collections",
                "functools",
                "itertools",
                "react",
                "react-dom",
                "vue",
                "angular",
            ):
                patterns[source_file][prefix].add(value)

    precedents = []

    for consumer, dirs in patterns.items():
        for directory, items in dirs.items():
            if len(items) >= 3:
                precedents.append(
                    {
                        "consumer": consumer,
                        "directory": directory,
                        "count": len(items),
                        "imports": sorted(items),
                    }
                )

    precedents.sort(key=lambda x: x["count"], reverse=True)

    return precedents


def _get_hot_files(cursor) -> list[dict]:
    """Get most-called functions (call graph centrality).

    Filters out:
    - Generic method names (up, down, render, constructor, etc.) that cause false matches
    - Migration/seeder files that inflate call counts
    - Test/spec files
    """
    hot_files = []

    cursor.execute("""
        SELECT
            s.path,
            s.name,
            COUNT(DISTINCT fca.file) as caller_count,
            COUNT(fca.file) as total_calls
        FROM symbols s
        JOIN function_call_args fca ON fca.callee_function = s.name
        WHERE s.type IN ('function', 'method')
            AND s.name NOT IN ('up', 'down', 'render', 'constructor', 'toString',
                               'init', 'run', 'execute', 'handle', 'process',
                               'get', 'set', 'call', 'apply', 'bind')
            AND s.path NOT LIKE '%migration%'
            AND s.path NOT LIKE '%/seeders/%'
            AND s.path NOT LIKE '%test%'
            AND s.path NOT LIKE '%spec%'
            AND s.path NOT LIKE '%node_modules%'
            AND s.path NOT LIKE '%dist/%'
            AND s.path NOT LIKE '%build/%'
        GROUP BY s.path, s.name
        HAVING total_calls > 5
        ORDER BY total_calls DESC
        LIMIT 20
    """)

    for row in cursor.fetchall():
        hot_files.append(
            {
                "file": row["path"],
                "symbol": row["name"],
                "caller_count": row["caller_count"],
                "total_calls": row["total_calls"],
            }
        )

    return hot_files


def _get_security_surface(cursor) -> dict:
    """Get security pattern counts (truth courier - no recommendations)."""
    security = {
        "jwt": {"sign": 0, "verify": 0},
        "oauth": 0,
        "password": 0,
        "sql_queries": {"total": 0, "raw": 0},
        "api_endpoints": {"total": 0, "protected": 0, "unprotected": 0},
    }

    cursor.execute("SELECT pattern_type FROM jwt_patterns")
    for row in cursor.fetchall():
        if "sign" in row[0]:
            security["jwt"]["sign"] += 1
        elif "verify" in row[0] or "decode" in row[0]:
            security["jwt"]["verify"] += 1

    # NOTE: oauth_patterns and password_patterns tables were never implemented
    # Set to 0 until extractors are built (not a fallback - these simply don't exist)
    security["oauth"] = 0
    security["password"] = 0

    cursor.execute("""
        SELECT COUNT(*) FROM sql_queries
        WHERE file_path NOT LIKE '%/migrations/%'
          AND file_path NOT LIKE '%/seeders/%'
          AND file_path NOT LIKE '%migration%'
    """)
    security["sql_queries"]["total"] = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*) FROM sql_queries
        WHERE command != 'UNKNOWN'
          AND file_path NOT LIKE '%/migrations/%'
          AND file_path NOT LIKE '%/seeders/%'
          AND file_path NOT LIKE '%migration%'
    """)
    security["sql_queries"]["raw"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM api_endpoints WHERE method != 'USE'")
    security["api_endpoints"]["total"] = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(*) FROM api_endpoints ae
        JOIN api_endpoint_controls aec
            ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
        WHERE ae.method != 'USE'
    """)
    security["api_endpoints"]["protected"] = cursor.fetchone()[0] or 0
    security["api_endpoints"]["unprotected"] = (
        security["api_endpoints"]["total"] - security["api_endpoints"]["protected"]
    )

    return security


def _get_data_flow(cursor) -> dict:
    """Get taint flow statistics."""
    data_flow = {
        "taint_sources": 0,
        "taint_paths": 0,
        "cross_function_flows": 0,
    }

    cursor.execute("SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'taint'")
    data_flow["taint_paths"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(DISTINCT source_var_name) FROM assignment_sources")
    data_flow["taint_sources"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM function_return_sources")
    data_flow["cross_function_flows"] = cursor.fetchone()[0] or 0

    return data_flow


def _get_import_graph(graphs_db_path: Path) -> dict:
    """Get import graph statistics."""
    imports = {"total": 0, "external": 0, "internal": 0, "circular": 0}

    conn = sqlite3.connect(graphs_db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'import'")
    imports["total"] = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(*) FROM edges WHERE graph_type = 'import' AND target LIKE 'external::%'"
    )
    imports["external"] = cursor.fetchone()[0] or 0
    imports["internal"] = imports["total"] - imports["external"]

    conn.close()

    return imports


def _get_performance(cursor, db_path: Path) -> dict:
    """Get analysis metrics."""
    metrics = {"db_size_mb": 0, "total_rows": 0, "files_indexed": 0, "symbols_extracted": 0}

    if db_path.exists():
        metrics["db_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

    total = 0
    for table in VALID_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total += cursor.fetchone()[0] or 0

    metrics["total_rows"] = total

    cursor.execute("SELECT COUNT(DISTINCT path) FROM symbols")
    metrics["files_indexed"] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM symbols")
    metrics["symbols_extracted"] = cursor.fetchone()[0] or 0

    return metrics


def _show_top_level_overview(data: dict):
    """Show top-level overview with tree structure (truth courier mode)."""
    lines = []

    lines.append("")
    lines.append("TheAuditor Code Blueprint")
    lines.append("")
    lines.append("━" * 80)
    lines.append("ARCHITECTURAL ANALYSIS (100% Accurate, 0% Inference)")
    lines.append("━" * 80)
    lines.append("")

    struct = data["structure"]
    lines.append("[STRUCTURE] Codebase Structure:")

    by_dir = struct["by_directory"]
    if "backend" in by_dir and "frontend" in by_dir:
        lines.append("  ├─ Backend ──────────────────────────┐")
        lines.append(f"  │  Files: {by_dir['backend']:,}")
        lines.append("  │                                      │")
        lines.append("  ├─ Frontend ─────────────────────────┤")
        lines.append(f"  │  Files: {by_dir['frontend']:,}")
        lines.append("  │                                      │")
        lines.append("  └──────────────────────────────────────┘")
    else:
        for dir_name, count in sorted(by_dir.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  ├─ {dir_name}: {count:,} files")

    lines.append(f"  Total Files: {struct['total_files']:,}")
    lines.append(f"  Total Symbols: {struct['total_symbols']:,}")

    by_cat = struct.get("by_category", {})
    if by_cat:
        lines.append("  File Categories:")
        cat_order = ["source", "test", "scripts", "migrations", "seeders", "config", "other"]
        for cat in cat_order:
            if cat in by_cat and by_cat[cat] > 0:
                lines.append(f"    {cat}: {by_cat[cat]:,}")
    lines.append("")

    hot = data["hot_files"][:5]
    if hot:
        lines.append("[HOT] Hot Files (by call count):")
        for i, hf in enumerate(hot, 1):
            lines.append(f"  {i}. {hf['file']}")
            lines.append(
                f"     → Called by: {hf['caller_count']} files ({hf['total_calls']} call sites)"
            )
        lines.append("")

    sec = data["security_surface"]
    lines.append("[SECURITY] Security Surface:")
    lines.append(
        f"  ├─ JWT Usage: {sec['jwt']['sign']} sign operations, {sec['jwt']['verify']} verify operations"
    )
    lines.append(f"  ├─ OAuth Flows: {sec['oauth']} patterns")
    lines.append(f"  ├─ Password Handling: {sec['password']} operations")
    lines.append(
        f"  ├─ SQL Queries: {sec['sql_queries']['total']} total ({sec['sql_queries']['raw']} raw queries)"
    )
    lines.append(
        f"  └─ API Endpoints: {sec['api_endpoints']['total']} total ({sec['api_endpoints']['unprotected']} unprotected)"
    )
    lines.append("")

    df = data["data_flow"]
    if df["taint_paths"] > 0 or df["taint_sources"] > 0:
        lines.append("[DATAFLOW] Data Flow (Junction Table Analysis):")
        lines.append(f"  ├─ Taint Sources: {df['taint_sources']:,} (unique variables)")
        lines.append(
            f"  ├─ Cross-Function Flows: {df['cross_function_flows']:,} (via return→assignment)"
        )
        lines.append(f"  └─ Taint Paths: {df['taint_paths']} detected")
        lines.append("")

    if data["import_graph"]:
        imp = data["import_graph"]
        lines.append("[IMPORTS] Import Graph:")
        lines.append(f"  ├─ Total imports: {imp['total']:,}")
        lines.append(f"  ├─ External deps: {imp['external']:,}")
        lines.append(f"  └─ Internal imports: {imp['internal']:,}")
        lines.append("")

    perf = data["performance"]
    lines.append("[METRICS] Analysis Metrics:")
    lines.append(f"  ├─ Files indexed: {perf['files_indexed']:,}")
    lines.append(f"  ├─ Symbols extracted: {perf['symbols_extracted']:,}")
    lines.append(f"  ├─ Database size: {perf['db_size_mb']} MB")
    lines.append("  └─ Query time: <10ms")
    lines.append("")

    lines.append("━" * 80)
    lines.append("Truth Courier Mode: Facts only, no recommendations")
    lines.append(
        "Drill-down flags: --structure, --graph, --security, --taint, "
        "--boundaries, --deps, --fce, --monoliths"
    )
    lines.append("━" * 80)
    lines.append("")

    console.print("\n".join(lines), markup=False)


def _show_structure_drilldown(data: dict, cursor: sqlite3.Cursor):
    """Drill down: SURGICAL structure analysis - scope understanding.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    struct = data["structure"]

    console.print("\n️  STRUCTURE DRILL-DOWN")
    console.rule()
    console.print("Scope Understanding: What's the scope? Where are boundaries? What's orphaned?")
    console.rule()

    console.print("\nMonorepo Detection:")
    by_dir = struct["by_directory"]
    has_backend = any("backend" in d for d in by_dir)
    has_frontend = any("frontend" in d for d in by_dir)
    has_packages = any("packages" in d for d in by_dir)

    if has_backend or has_frontend or has_packages:
        console.print(
            f"  \\[OK] Detected: {'backend/' if has_backend else ''}{'frontend/' if has_frontend else ''}{'packages/' if has_packages else ''} split",
            highlight=False,
        )
        if has_backend:
            backend_files = sum(
                count for dir_name, count in by_dir.items() if "backend" in dir_name
            )
            console.print(f"  Backend: {backend_files} files", highlight=False)
        if has_frontend:
            frontend_files = sum(
                count for dir_name, count in by_dir.items() if "frontend" in dir_name
            )
            console.print(f"  Frontend: {frontend_files} files", highlight=False)
    else:
        console.print("  \\[X] No monorepo structure detected (single-directory project)")

    console.print("\nFiles by Directory:")
    for dir_name, count in sorted(struct["by_directory"].items(), key=lambda x: -x[1])[:15]:
        console.print(f"  {dir_name:50s} {count:6,} files", highlight=False)

    console.print("\nFiles by Language:")
    lang_map = {
        ".ts": "TypeScript",
        ".js": "JavaScript",
        ".py": "Python",
        ".tsx": "TSX",
        ".jsx": "JSX",
    }
    for ext, count in sorted(struct["by_language"].items(), key=lambda x: -x[1]):
        lang = lang_map.get(ext, ext)
        console.print(f"  {lang:50s} {count:6,} files", highlight=False)

    if struct["by_type"]:
        console.print("\nSymbols by Type:")
        for sym_type, count in sorted(struct["by_type"].items(), key=lambda x: -x[1]):
            console.print(f"  {sym_type:50s} {count:6,} symbols", highlight=False)

    naming = data.get("naming_conventions", {})
    if naming:
        console.print("\nCode Style Analysis (Naming Conventions):")

        for lang in ["python", "javascript", "typescript", "go", "rust", "bash"]:
            lang_data = naming.get(lang, {})
            if not lang_data or not any(lang_data.values()):
                continue

            lang_name = lang.capitalize()
            console.print(f"\n  {lang_name}:", highlight=False)

            symbol_types = ["functions", "classes"]
            if lang == "go":
                symbol_types = ["functions", "structs"]
            elif lang == "rust":
                symbol_types = ["functions", "types"]
            elif lang == "bash":
                symbol_types = ["functions"]

            for symbol_type in symbol_types:
                patterns = lang_data.get(symbol_type, {})
                if not patterns or not patterns.get("dominant"):
                    continue

                dominant = patterns["dominant"]
                consistency = patterns["consistency"]
                console.print(
                    f"    {symbol_type.capitalize()}: {dominant} ({consistency}% consistency)",
                    highlight=False,
                )

    precedents = data.get("architectural_precedents", [])
    if precedents:
        console.print("\nArchitectural Precedents (Plugin Loader Patterns):")
        console.print(
            "  (Files importing 3+ modules from same directory - architectural conventions)"
        )

        for prec in precedents[:15]:
            consumer = prec["consumer"]
            directory = prec["directory"]
            count = prec["count"]
            imports = prec["imports"]

            console.print(f"\n  {consumer}", highlight=False)
            console.print(f"    -> {directory}/ ({count} modules)", highlight=False)

            for imp in imports[:5]:
                display = Path(imp).name if "/" in imp else imp
                console.print(f"       - {display}", highlight=False)

            if count > 5:
                console.print(f"       ... and {count - 5} more", highlight=False)

        if len(precedents) > 15:
            console.print(f"\n  ... and {len(precedents) - 15} more patterns", highlight=False)

        console.print(f"\n  Total patterns found: {len(precedents)}", highlight=False)
    else:
        console.print("\nArchitectural Precedents: None detected")

    try:
        cursor.execute("""
            SELECT language, name, version, COUNT(*) as file_count
            FROM frameworks
            GROUP BY name, language, version
            ORDER BY file_count DESC
        """)
        frameworks = cursor.fetchall()

        if frameworks:
            console.print("\nFramework Detection:")
            for lang, fw, ver, count in frameworks:
                version_str = f"v{ver}" if ver else "(version unknown)"
                console.print(f"  {fw} {version_str} ({lang}) - {count} file(s)", highlight=False)
        else:
            console.print("\nFramework Detection: None detected")
    except sqlite3.OperationalError:
        console.print("\nFramework Detection: (Table not found - run 'aud full')")

    try:
        cursor.execute("""
            SELECT timestamp, target_file, refactor_type, migrations_found,
                   migrations_complete, schema_consistent, validation_status
            FROM refactor_history
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        refactor_history = cursor.fetchall()

        if refactor_history:
            console.print("\nRefactor History (Recent Checks):")
            for ts, target, rtype, mig_found, mig_complete, schema_ok, status in refactor_history:
                date = ts.split("T")[0] if "T" in ts else ts
                consistent = "consistent" if schema_ok == 1 else "inconsistent"
                complete = "complete" if mig_complete == 1 else "incomplete"
                console.print(f"  {date}: {target}", highlight=False)
                console.print(
                    f"    Type: {rtype} | Risk: {status} | Migrations: {mig_found} found ({complete})",
                    highlight=False,
                )
                console.print(f"    Schema: {consistent}", highlight=False)
        else:
            console.print("\nRefactor History: No checks recorded (run 'aud refactor' to populate)")
    except sqlite3.OperationalError:
        console.print("\nRefactor History: (Table not found - run 'aud full')")

    console.print("\nToken Estimates (for context planning):")
    total_files = struct["total_files"]

    estimated_tokens = total_files * 400
    console.print(f"  Total files: {total_files:,}", highlight=False)
    console.print(f"  Estimated tokens: ~{estimated_tokens:,} tokens", highlight=False)
    if estimated_tokens > 100000:
        console.print("  [warning]Exceeds single LLM context window[/warning]")
        console.print("  -> Use 'aud query' for targeted analysis instead of reading all files")

    console.print("\nMigration Paths Detected:")
    migration_paths = [d for d in by_dir if "migration" in d.lower()]
    legacy_paths = [d for d in by_dir if "legacy" in d.lower() or "deprecated" in d.lower()]

    if migration_paths:
        for path in migration_paths:
            console.print(f"  \\[WARN] {path}/ ({by_dir[path]} files)", highlight=False)
    if legacy_paths:
        for path in legacy_paths:
            console.print(
                f"  \\[WARN] {path}/ ({by_dir[path]} files marked DEPRECATED)", highlight=False
            )
    if not migration_paths and not legacy_paths:
        console.print("  [success]No migration or legacy paths detected[/success]")

    console.print("\nCross-Reference Commands:")
    console.print("  -> Use 'aud query --file <path> --show-dependents' for impact analysis")
    console.print("  -> Use 'aud graph viz' for visual dependency map")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _show_graph_drilldown(data: dict):
    """Drill down: SURGICAL dependency mapping - what depends on what."""
    console.print("\n GRAPH DRILL-DOWN")
    console.rule()
    console.print(
        "Dependency Mapping: What depends on what? Where are bottlenecks? What breaks if I change X?"
    )
    console.rule()

    if data["import_graph"]:
        imp = data["import_graph"]
        console.print("\nImport Graph Summary:")
        console.print(f"  Total imports: {imp['total']:,}", highlight=False)
        console.print(f"  External dependencies: {imp['external']:,}", highlight=False)
        console.print(f"  Internal imports: {imp['internal']:,}", highlight=False)
        console.print(
            f"  Circular dependencies: {imp['circular']} cycles detected", highlight=False
        )
    else:
        console.print("\n[warning]No graph data available[/warning]")
        console.print("  Run: aud graph build")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print("\nGateway Files (high betweenness centrality):")
    console.print("  These are bottlenecks - changing them breaks many dependents")
    hot = data["hot_files"]
    if hot:
        for i, hf in enumerate(hot[:10], 1):
            console.print(f"\n  {i}. {hf['file']}", highlight=False)
            console.print(f"     Symbol: {hf['symbol']}", highlight=False)
            console.print(
                f"     Called by: {hf['caller_count']} files | Total calls: {hf['total_calls']}",
                highlight=False,
            )
            if hf["caller_count"] > 20:
                console.print(
                    f"     \\[WARN] HIGH IMPACT - changes affect {hf['caller_count']} files",
                    highlight=False,
                )
                console.print(
                    f"     -> Use 'aud query --symbol {hf['symbol']} --show-callers' for full list",
                    highlight=False,
                )
    else:
        console.print(
            "  [success]No high-centrality files detected (good - decoupled architecture)[/success]"
        )

    console.print("\nCircular Dependencies:")
    if imp["circular"] > 0:
        console.print(f"  \\[WARN] {imp['circular']} cycles detected", highlight=False)
        console.print("  -> Use 'aud graph analyze' for cycle detection")
        console.print("  -> Use 'aud graph viz --view cycles' for visual diagram")
    else:
        console.print("  [success]No circular dependencies detected (clean architecture)[/success]")

    console.print("\nExternal Dependencies:")
    console.print(f"  Total: {imp['external']:,} external imports", highlight=False)
    console.print("  -> Use 'aud deps --check-latest' for version analysis")
    console.print("  -> Use 'aud deps --vuln-scan' for security vulnerabilities")

    console.print("\nCross-Reference Commands:")
    console.print("  -> Use 'aud query --file <path> --show-dependents' to see impact radius")
    console.print("  -> Use 'aud graph viz --view full' for complete dependency graph")
    console.print("  -> Use 'aud graph analyze' for health metrics and cycle detection")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _show_security_drilldown(data: dict, cursor):
    """Drill down: SURGICAL attack surface mapping - what's vulnerable.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    sec = data["security_surface"]

    console.print("\n SECURITY DRILL-DOWN")
    console.rule()
    console.print(
        "Attack Surface Mapping: What's the attack surface? What's protected? What needs fixing?"
    )
    console.rule()

    console.print(
        f"\nAPI Endpoint Security Coverage ({sec['api_endpoints']['total']} endpoints):",
        highlight=False,
    )
    total_endpoints = sec["api_endpoints"]["total"]
    protected = sec["api_endpoints"]["protected"]
    unprotected = sec["api_endpoints"]["unprotected"]

    if total_endpoints > 0:
        protected_pct = int((protected / total_endpoints) * 100)
        console.print(f"  Protected: {protected} ({protected_pct}%)", highlight=False)
        console.print(
            f"  Unprotected: {unprotected} ({100 - protected_pct}%) {'← SECURITY RISK' if unprotected > 0 else ''}",
            highlight=False,
        )

    if unprotected > 0:
        console.print("\n  Unprotected Endpoints (showing first 10):")
        cursor.execute("""
            SELECT ae.method, ae.path, ae.file, ae.line, ae.handler_function
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
            WHERE aec.endpoint_file IS NULL
              AND ae.method != 'USE'
            LIMIT 10
        """)
        for i, row in enumerate(cursor.fetchall(), 1):
            method = row["method"] or "USE"
            path = row["path"] or "(no path)"
            file = row["file"]
            line = row["line"]
            handler = row["handler_function"] or "(unknown)"
            console.print(f"    {i}. {method:7s} {path:40s} ({file}:{line})", highlight=False)
            console.print(f"       Handler: {handler}", highlight=False)

        if unprotected > 10:
            console.print(f"    ... {unprotected - 10} more unprotected endpoints", highlight=False)
            console.print(
                "    -> Use 'aud query --show-api-coverage | grep \"\\[OPEN]\"' for full list"
            )

    console.print("\nAuthentication Patterns Detected:")
    jwt_total = sec["jwt"]["sign"] + sec["jwt"]["verify"]
    oauth_total = sec["oauth"]

    console.print(f"\n  JWT: {jwt_total} usages", highlight=False)
    console.print(
        f"    ├─ jwt.sign: {sec['jwt']['sign']} locations (token generation)", highlight=False
    )
    console.print(
        f"    └─ jwt.verify/decode: {sec['jwt']['verify']} locations (token validation)",
        highlight=False,
    )

    console.print(f"\n  OAuth: {oauth_total} usages", highlight=False)

    console.print(f"\n  Password Handling: {sec['password']} operations", highlight=False)

    if jwt_total > 0 and oauth_total > 0:
        console.print("\n  [warning]MIGRATION IN PROGRESS?[/warning]")
        console.print("    Both JWT and OAuth detected - possible auth migration")
        console.print("    -> Use 'aud context --file auth_migration.yaml' to track progress")

    console.print("\nHardcoded Secrets:")
    cursor.execute(
        "SELECT COUNT(*) FROM findings_consolidated WHERE rule LIKE '%secret%' OR rule LIKE '%hardcoded%'"
    )
    secret_count = cursor.fetchone()[0]
    if secret_count > 0:
        console.print(f"  (!) {secret_count} potential hardcoded secrets detected", highlight=False)
        console.print("  -> Use 'aud query --symbol <func> --show-code' for details")
    else:
        console.print("  [success]No hardcoded secrets detected[/success]")

    console.print("\nSQL Injection Risk:")
    sql_total = sec["sql_queries"]["total"]
    sql_raw = sec["sql_queries"]["raw"]

    if sql_total > 0:
        raw_pct = int((sql_raw / sql_total) * 100) if sql_total > 0 else 0
        console.print(f"  Total queries: {sql_total}", highlight=False)
        console.print(
            f"  Raw/dynamic queries: {sql_raw} ({raw_pct}%) {'← Potential SQLi' if sql_raw > 0 else ''}",
            highlight=False,
        )
        console.print(
            f"  Parameterized queries: {sql_total - sql_raw} ({100 - raw_pct}%)", highlight=False
        )

        if sql_raw > 0:
            console.print(
                f"\n  \\[WARN] High Risk: {sql_raw} dynamic SQL queries detected", highlight=False
            )
            console.print("  -> Use 'aud query --category sql --format json' for full analysis")
    else:
        console.print("  [success]No SQL queries detected (or using ORM)[/success]")

    cursor.execute("SELECT COUNT(*) FROM api_endpoints WHERE method = 'POST'")
    post_count = cursor.fetchone()[0]
    if post_count > 0:
        console.print("\nCSRF Protection:")
        console.print(f"  POST endpoints: {post_count}", highlight=False)
        console.print("  -> Manual review required for CSRF token validation")

    console.print("\nCross-Reference Commands:")
    console.print("  -> Use 'aud query --show-api-coverage' for full endpoint security matrix")
    console.print("  -> Use 'aud taint' for data flow security analysis")
    console.print("  -> Use 'aud deps --vuln-scan' for dependency CVEs (OSV-Scanner)")
    console.print(
        "  -> Use 'aud query --pattern \"localStorage\" --type-filter function' to find insecure storage"
    )

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _show_taint_drilldown(data: dict, cursor):
    """Drill down: SURGICAL data flow mapping - where does user data flow.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    df = data["data_flow"]

    console.print("\n TAINT DRILL-DOWN")
    console.rule()
    console.print(
        "Data Flow Mapping: Where does user data flow? What's sanitized? What's vulnerable?"
    )
    console.rule()

    if df["taint_paths"] == 0:
        console.print("\n[warning]No taint analysis data available[/warning]")
        console.print("  Run: aud taint")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print("\nTop Taint Sources (user-controlled data):")
    cursor.execute("""
        SELECT source_var_name, COUNT(*) as usage_count
        FROM assignment_sources
        WHERE source_var_name IN ('req.body', 'req.query', 'req.params', 'req.headers', 'userInput', 'input')
           OR source_var_name LIKE 'req.%'
           OR source_var_name LIKE 'request.%'
        GROUP BY source_var_name
        ORDER BY usage_count DESC
        LIMIT 5
    """)
    sources = cursor.fetchall()
    if sources:
        for i, row in enumerate(sources, 1):
            console.print(
                f"  {i}. {row['source_var_name']} ({row['usage_count']} locations)", highlight=False
            )
    else:
        console.print("  (No common taint sources detected in junction tables)")

    console.print(f"\nTaint Paths Detected: {df['taint_paths']}", highlight=False)
    console.print(
        f"Cross-Function Flows: {df['cross_function_flows']:,} (via return->assignment)",
        highlight=False,
    )

    console.print("\nVulnerable Data Flows (showing first 5):")
    cursor.execute("""
        SELECT rule, category, file, line, message, severity
        FROM findings_consolidated
        WHERE tool = 'taint'
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                ELSE 4
            END,
            line
        LIMIT 5
    """)
    taint_findings = cursor.fetchall()
    if taint_findings:
        for i, finding in enumerate(taint_findings, 1):
            category = finding["category"] or "unknown"
            file = finding["file"]
            line = finding["line"]
            message = finding["message"] or "Tainted data flow detected"
            severity = finding["severity"] or "medium"

            if len(message) > 80:
                message = message[:77] + "..."

            console.print(f"\n  {i}. \\[{severity.upper()}] {category}", highlight=False)
            console.print(f"     Location: {file}:{line}", highlight=False)
            console.print(f"     Issue: {message}", highlight=False)

        if df["taint_paths"] > 5:
            console.print(f"\n  ... {df['taint_paths'] - 5} more taint paths", highlight=False)
            console.print("  -> Use 'aud taint --json' for full vulnerability details")
    else:
        console.print("  (No taint findings in findings_consolidated table)")

    console.print("\nSanitization Coverage:")
    cursor.execute("""
        SELECT COUNT(*) as sanitizer_count
        FROM function_call_args
        WHERE callee_function LIKE '%sanitize%'
           OR callee_function LIKE '%escape%'
           OR callee_function LIKE '%validate%'
           OR callee_function LIKE '%clean%'
    """)
    sanitizer_count = cursor.fetchone()["sanitizer_count"]

    if sanitizer_count > 0:
        console.print(f"  Sanitization functions called: {sanitizer_count} times", highlight=False)
        console.print(f"  -> Compare with {df['taint_paths']} taint paths", highlight=False)
        if df["taint_paths"] > 0 and sanitizer_count < df["taint_paths"]:
            coverage_pct = int((sanitizer_count / df["taint_paths"]) * 100)
            console.print(
                f"  (!) LOW COVERAGE (~{coverage_pct}%) - many flows unsanitized", highlight=False
            )
    else:
        console.print("  (!) No sanitization functions detected")
        console.print(f"  -> {df['taint_paths']} taint paths with NO sanitization", highlight=False)

    console.print("\nDynamic Dispatch Vulnerabilities:")
    cursor.execute("""
        SELECT COUNT(*) as dispatch_count
        FROM findings_consolidated
        WHERE rule LIKE '%dynamic%dispatch%'
           OR rule LIKE '%prototype%pollution%'
           OR category = 'dynamic_dispatch'
    """)
    dispatch_count = cursor.fetchone()["dispatch_count"]

    if dispatch_count > 0:
        console.print(
            f"  (!) {dispatch_count} dynamic dispatch vulnerabilities detected", highlight=False
        )
        console.print("  -> User can control which function executes (RCE risk)")
        console.print("  -> Use 'aud query --category dynamic_dispatch' for locations")
    else:
        console.print("  [success]No dynamic dispatch vulnerabilities detected[/success]")

    console.print("\nCross-Reference Commands:")
    console.print(
        "  -> Use 'aud query --symbol <func> --show-taint-flow' for specific function flows"
    )
    console.print("  -> Use 'aud query --variable req.body --show-flow --depth 3' for data tracing")
    console.print("  -> Use 'aud taint --json' to re-run analysis with fresh data")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _get_dependencies(cursor) -> dict:
    """Get dependency facts from package tables.

    Uses normalized schema: package_configs + package_dependencies for npm,
    python_package_configs + python_package_dependencies for pip, etc.
    """
    deps = {
        "total": 0,
        "by_manager": {},
        "packages": [],
        "workspaces": [],
    }

    # npm: package_configs + package_dependencies
    cursor.execute("SELECT file_path, package_name, version FROM package_configs")
    npm_workspaces = {}
    for row in cursor.fetchall():
        file_path = row["file_path"]
        npm_workspaces[file_path] = {
            "file": file_path,
            "name": row["package_name"],
            "version": row["version"],
            "manager": "npm",
            "prod_count": 0,
            "dev_count": 0,
        }

    cursor.execute("SELECT file_path, name, version_spec, is_dev FROM package_dependencies")
    for row in cursor.fetchall():
        file_path = row["file_path"]
        is_dev = bool(row["is_dev"])
        deps["packages"].append({
            "name": row["name"],
            "version": row["version_spec"] or "",
            "manager": "npm",
            "dev": is_dev,
        })
        deps["by_manager"]["npm"] = deps["by_manager"].get("npm", 0) + 1
        deps["total"] += 1

        if file_path in npm_workspaces:
            if is_dev:
                npm_workspaces[file_path]["dev_count"] += 1
            else:
                npm_workspaces[file_path]["prod_count"] += 1

    deps["workspaces"].extend(npm_workspaces.values())

    # pip: python_package_configs + python_package_dependencies
    cursor.execute("SELECT file_path, project_name, project_version FROM python_package_configs")
    pip_workspaces = {}
    for row in cursor.fetchall():
        file_path = row["file_path"]
        pip_workspaces[file_path] = {
            "file": file_path,
            "name": row["project_name"],
            "version": row["project_version"],
            "manager": "pip",
            "prod_count": 0,
            "dev_count": 0,
        }

    cursor.execute("SELECT file_path, name, version_spec, is_dev FROM python_package_dependencies")
    for row in cursor.fetchall():
        file_path = row["file_path"]
        is_dev = bool(row["is_dev"])
        deps["packages"].append({
            "name": row["name"],
            "version": row["version_spec"] or "",
            "manager": "pip",
            "dev": is_dev,
        })
        deps["by_manager"]["pip"] = deps["by_manager"].get("pip", 0) + 1
        deps["total"] += 1

        if file_path in pip_workspaces:
            if is_dev:
                pip_workspaces[file_path]["dev_count"] += 1
            else:
                pip_workspaces[file_path]["prod_count"] += 1

    deps["workspaces"].extend(pip_workspaces.values())

    cursor.execute("""
        SELECT file_path, package_name, package_version, edition
        FROM cargo_package_configs
    """)
    for row in cursor.fetchall():
        file_path = row["file_path"]
        pkg_name = row["package_name"]
        version = row["package_version"]

        workspace = {
            "file": file_path,
            "name": pkg_name,
            "version": version,
            "manager": "cargo",
            "prod_count": 0,
            "dev_count": 0,
        }
        deps["workspaces"].append(workspace)

    cursor.execute("""
        SELECT file_path, name, version_spec, is_dev
        FROM cargo_dependencies
    """)
    for row in cursor.fetchall():
        is_dev = bool(row["is_dev"])
        deps["packages"].append(
            {
                "name": row["name"],
                "version": row["version_spec"] or "",
                "manager": "cargo",
                "dev": is_dev,
            }
        )
        deps["by_manager"]["cargo"] = deps["by_manager"].get("cargo", 0) + 1
        deps["total"] += 1

    cursor.execute("""
        SELECT file_path, module_path, go_version
        FROM go_module_configs
    """)
    for row in cursor.fetchall():
        file_path = row["file_path"]
        mod_path = row["module_path"]
        go_ver = row["go_version"]

        workspace = {
            "file": file_path,
            "name": mod_path,
            "version": go_ver,
            "manager": "go",
            "prod_count": 0,
            "dev_count": 0,
        }
        deps["workspaces"].append(workspace)

    cursor.execute("""
        SELECT file_path, module_path, version, is_indirect
        FROM go_module_dependencies
    """)
    for row in cursor.fetchall():
        is_indirect = bool(row["is_indirect"])
        deps["packages"].append(
            {
                "name": row["module_path"],
                "version": row["version"] or "",
                "manager": "go",
                "dev": is_indirect,
            }
        )
        deps["by_manager"]["go"] = deps["by_manager"].get("go", 0) + 1
        deps["total"] += 1

    return deps


def _show_deps_drilldown(data: dict, cursor):
    """Drill down: Dependency analysis - packages, versions, managers.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    deps = data.get("dependencies", {})

    console.print("\nDEPS DRILL-DOWN")
    console.rule()
    console.print("Dependency Analysis: What packages? What versions? What managers?")
    console.rule()

    if deps["total"] == 0:
        console.print("\n(!) No dependencies found in database")
        console.print("  Run: aud full (indexes package.json, pyproject.toml, requirements.txt)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print(f"\nTotal Dependencies: {deps['total']}", highlight=False)
    console.print("\nBy Package Manager:")
    for manager, count in sorted(deps["by_manager"].items(), key=lambda x: -x[1]):
        console.print(f"  {manager}: {count} packages", highlight=False)

    console.print("\nProjects/Workspaces:")
    for ws in deps["workspaces"]:
        console.print(f"\n  {ws['file']}", highlight=False)
        console.print(f"    Name: {ws['name'] or '(unnamed)'}", highlight=False)
        console.print(f"    Version: {ws['version'] or '(no version)'}", highlight=False)
        console.print(f"    Manager: {ws['manager']}", highlight=False)
        console.print(f"    Production deps: {ws['prod_count']}", highlight=False)
        console.print(f"    Dev deps: {ws['dev_count']}", highlight=False)

        if ws.get("prod_deps"):
            console.print("    Top dependencies:")
            for _i, (name, ver) in enumerate(list(ws["prod_deps"].items())[:5]):
                console.print(f"      - {name}: {ver}", highlight=False)
            if len(ws["prod_deps"]) > 5:
                console.print(f"      ... and {len(ws['prod_deps']) - 5} more", highlight=False)

    console.print("\nOutdated Package Check:")
    try:
        cursor.execute("SELECT COUNT(*) FROM dependency_versions WHERE is_outdated = 1")
        outdated_count = cursor.fetchone()[0]
        if outdated_count > 0:
            console.print(f"  (!) {outdated_count} outdated packages detected", highlight=False)
            cursor.execute("""
                SELECT package_name, locked_version, latest_version, manager
                FROM dependency_versions
                WHERE is_outdated = 1
                LIMIT 10
            """)
            for row in cursor.fetchall():
                console.print(
                    f"    {row['package_name']}: {row['locked_version']} -> {row['latest_version']} ({row['manager']})",
                    highlight=False,
                )
        else:
            console.print("  (No outdated package data - run 'aud deps --check-latest')")
    except sqlite3.OperationalError:
        console.print("  (No version check data - run 'aud deps --check-latest')")

    console.print("\nRelated Commands:")
    console.print("  -> aud deps --check-latest   # Check for outdated packages")
    console.print("  -> aud deps --vuln-scan      # Scan for CVEs (OSV-Scanner)")
    console.print("  -> aud deps --upgrade-all    # YOLO mode: upgrade everything")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _get_boundaries(cursor, graphs_db_path: Path) -> dict:
    """Get boundary analysis summary by running the analyzer.

    Runs analyze_input_validation_boundaries() to compute distances
    between entry points and validation controls.
    """
    from theauditor.boundaries.boundary_analyzer import analyze_input_validation_boundaries

    boundaries = {
        "total_entries": 0,
        "by_quality": {
            "clear": 0,
            "acceptable": 0,
            "fuzzy": 0,
            "missing": 0,
        },
        "missing_controls": 0,
        "late_validation": 0,
        "entries": [],
    }

    db_path = Path.cwd() / ".pf" / "repo_index.db"

    try:
        results = analyze_input_validation_boundaries(str(db_path), max_entries=20)

        boundaries["total_entries"] = len(results)

        for result in results:
            quality = result["quality"]["quality"]
            boundaries["by_quality"][quality] = boundaries["by_quality"].get(quality, 0) + 1

            if quality == "missing":
                boundaries["missing_controls"] += 1

            for control in result.get("controls", []):
                if control.get("distance", 0) >= 3:
                    boundaries["late_validation"] += 1
                    break

            distances = [c.get("distance", 999) for c in result.get("controls", [])]
            min_dist = min(distances) if distances else None

            boundaries["entries"].append(
                {
                    "entry_point": result["entry_point"],
                    "file": result["entry_file"],
                    "line": result["entry_line"],
                    "quality": quality,
                    "distance": min_dist,
                    "control_count": len(result.get("controls", [])),
                }
            )

        quality_order = {"missing": 0, "fuzzy": 1, "acceptable": 2, "clear": 3}
        boundaries["entries"].sort(
            key=lambda x: (quality_order.get(x["quality"], 4), -(x["distance"] or 0))
        )

    except Exception as e:
        boundaries["error"] = str(e)

    return boundaries


def _show_boundaries_drilldown(data: dict, cursor):
    """Drill down: SURGICAL boundary distance analysis.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    bounds = data.get("boundaries", {})

    console.print("\nBOUNDARIES DRILL-DOWN")
    console.rule()
    console.print("Boundary Distance Analysis: How far is validation from entry points?")
    console.rule()

    if bounds.get("error"):
        console.print(f"\n(!) Analysis error: {bounds['error']}", highlight=False)
        console.print("  Run: aud full (to index routes and handlers)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    total = bounds.get("total_entries", 0)
    if total == 0:
        console.print("\n(!) No entry points found in database")
        console.print("  Run: aud full (indexes routes and handlers)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print(f"\nEntry Points Analyzed: {total}", highlight=False)

    by_quality = bounds.get("by_quality", {})

    console.print("\nBoundary Quality Breakdown:")
    console.print(
        f"  Clear (dist 0):      {by_quality.get('clear', 0):4d} - Validation at entry",
        highlight=False,
    )
    console.print(
        f"  Acceptable (1-2):    {by_quality.get('acceptable', 0):4d} - Validation nearby",
        highlight=False,
    )
    console.print(
        f"  Fuzzy (3+ or multi): {by_quality.get('fuzzy', 0):4d} - Late or scattered validation",
        highlight=False,
    )
    console.print(
        f"  Missing:             {by_quality.get('missing', 0):4d} - No validation found",
        highlight=False,
    )

    missing = bounds.get("missing_controls", 0)
    late = bounds.get("late_validation", 0)

    if missing > 0 or late > 0:
        console.print("\nRisk Summary:")
        if missing > 0:
            console.print(
                f"  (!) {missing} entry points have NO validation control", highlight=False
            )
        if late > 0:
            console.print(
                f"  (!) {late} entry points have LATE validation (distance 3+)", highlight=False
            )

    entries = bounds.get("entries", [])
    if entries:
        console.print("\nTop Issues (by severity):")
        for i, entry in enumerate(entries[:10], 1):
            quality = entry.get("quality", "unknown")
            distance = entry.get("distance")
            ep = entry.get("entry_point", "unknown")
            file = entry.get("file", "")
            line = entry.get("line", 0)
            controls = entry.get("control_count", 0)

            dist_str = f"dist={distance}" if distance is not None else "no path"

            console.print(f"\n  {i}. \\[{quality.upper()}] {ep}", highlight=False)
            console.print(f"     Location: {file}:{line}", highlight=False)
            console.print(f"     Distance: {dist_str}, Controls found: {controls}", highlight=False)

    console.print("\nRelated Commands:")
    console.print("  -> aud boundaries --format json        # Full analysis as JSON")
    console.print("  -> aud boundaries --type input-validation  # Focus on input validation")
    console.print("  -> aud blueprint --taint               # Data flow analysis")
    console.print("  -> aud blueprint --security            # Security surface overview")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _find_monoliths(db_path: str, threshold: int, output_format: str) -> int:
    """Find monolithic files (>threshold lines) that require chunked reading.

    Args:
        db_path: Path to repo_index.db
        threshold: Line count threshold (default 1950)
        output_format: 'text' or 'json'

    Returns:
        Exit code (0 for success)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            f.path,
            f.loc as line_count,
            COUNT(DISTINCT s.name) as symbol_count
        FROM files f
        LEFT JOIN symbols s ON f.path = s.path
        WHERE f.loc > ?
          AND f.path NOT LIKE '%test%'
          AND f.path NOT LIKE '%/tests/%'
          AND f.path NOT LIKE '%/__pycache__/%'
          AND f.path NOT LIKE '%/node_modules/%'
          AND f.file_category = 'source'
        GROUP BY f.path
        ORDER BY f.loc DESC
    """,
        (threshold,),
    )

    results = cursor.fetchall()
    conn.close()

    if not results:
        if output_format == "json":
            console.print(
                json.dumps({"monoliths": [], "total": 0, "threshold": threshold}, indent=2),
                markup=False,
            )
        else:
            console.print(
                f"No monolithic files found (threshold: {threshold} lines)", highlight=False
            )
            console.print("\nAll files are below the AI readability threshold!")
        return 0

    if output_format == "json":
        output_data = {
            "monoliths": [
                {
                    "path": path,
                    "lines": lines,
                    "symbols": symbols,
                }
                for path, lines, symbols in results
            ],
            "total": len(results),
            "threshold": threshold,
        }
        console.print(json.dumps(output_data, indent=2), markup=False)
    else:
        console.rule()
        console.print(f"Monolithic Files (>{threshold} lines)", highlight=False)
        console.rule()
        console.print(f"Found {len(results)} files requiring chunked reading\n", highlight=False)

        for path, lines, symbols in results:
            console.print(f"\\[MONOLITH] {path}", highlight=False)
            console.print(f"  Lines: {lines:,} (>{threshold})", highlight=False)
            console.print(f"  Symbols: {symbols:,} functions/classes", highlight=False)
            console.print()

        console.rule()
        console.print(f"Total: {len(results)} monolithic files", highlight=False)
        console.rule()

    return 0


def _get_fce_data() -> dict:
    """Get FCE vector convergence data.

    Runs FCE analysis and returns summary for blueprint integration.
    """
    from theauditor.fce import FCEQueryEngine
    from theauditor.fce.formatter import FCEFormatter

    root = Path.cwd()
    fce_data = {
        "total_points": 0,
        "by_density": {4: 0, 3: 0, 2: 0, 1: 0},
        "convergence_points": [],
    }

    try:
        engine = FCEQueryEngine(root)
        points = engine.get_convergence_points(min_vectors=1)
        summary = engine.get_summary()
        engine.close()

        fce_data["total_points"] = len(points)
        fce_data["summary"] = summary

        formatter = FCEFormatter()
        for point in points:
            density = len(point.signal.vectors_present)
            fce_data["by_density"][density] = fce_data["by_density"].get(density, 0) + 1
            fce_data["convergence_points"].append(
                {
                    "file": point.file_path,
                    "density": density,
                    "vectors": formatter.get_vector_code_string(point.signal),
                    "fact_count": len(point.facts),
                }
            )

    except FileNotFoundError:
        fce_data["error"] = "FCE database not found (run aud full)"

    return fce_data


def _show_fce_drilldown(data: dict):
    """Drill down: FCE vector convergence analysis.

    Shows files with multiple analysis vectors converging on them.
    """
    fce = data.get("fce", {})

    console.print("\nFCE DRILL-DOWN")
    console.rule()
    console.print("Vector Convergence Analysis: Where do multiple analysis vectors agree?")
    console.rule()

    if fce.get("error"):
        console.print(f"\n(!) {fce['error']}", highlight=False)
        console.print("  Run: aud full (populates FCE database)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    total = fce.get("total_points", 0)
    if total == 0:
        console.print("\n(!) No convergence points found")
        console.print("  This may indicate a clean codebase or incomplete analysis")
        console.print("  Run: aud full (for complete analysis)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print(f"\nFiles with Vector Convergence: {total}", highlight=False)

    console.print("\nSignal Density Distribution:")
    by_density = fce.get("by_density", {})
    console.print(f"  [red]4/4 vectors (highest):[/red] {by_density.get(4, 0):4d} files")
    console.print(f"  [yellow]3/4 vectors:[/yellow]          {by_density.get(3, 0):4d} files")
    console.print(f"  [cyan]2/4 vectors:[/cyan]            {by_density.get(2, 0):4d} files")
    console.print(f"  [dim]1/4 vectors:[/dim]            {by_density.get(1, 0):4d} files")

    console.print("\nVector Legend:")
    console.print("  S = STATIC (linters: ruff, eslint, bandit)")
    console.print("  F = FLOW (taint analysis)")
    console.print("  P = PROCESS (code churn, change frequency)")
    console.print("  T = STRUCTURAL (complexity, CFG analysis)")

    points = fce.get("convergence_points", [])
    high_priority = [p for p in points if p.get("density", 0) >= 3]

    if high_priority:
        console.print("\nHigh Priority Files (3+ vectors, showing first 10):")
        for i, point in enumerate(high_priority[:10], 1):
            file = point.get("file", "unknown")
            density = point.get("density", 0)
            vectors = point.get("vectors", "----")
            facts = point.get("fact_count", 0)
            console.print(f"\n  {i}. \\[{density}/4] {file}", highlight=False)
            console.print(f"     Vectors: {vectors}", highlight=False)
            console.print(f"     Facts: {facts} findings", highlight=False)

        if len(high_priority) > 10:
            console.print(f"\n  ... and {len(high_priority) - 10} more high-priority files")
    else:
        console.print("\n[success]No files with 3+ vectors (good signal)[/success]")

    summary = fce.get("summary", {})
    if summary:
        console.print("\nSummary Statistics:")
        console.print(f"  Total files analyzed: {summary.get('total_files', 0):,}", highlight=False)
        console.print(
            f"  Files with static findings: {summary.get('static_files', 0):,}", highlight=False
        )
        console.print(
            f"  Files with flow findings: {summary.get('flow_files', 0):,}", highlight=False
        )
        console.print(
            f"  Files with process data: {summary.get('process_files', 0):,}", highlight=False
        )
        console.print(
            f"  Files with structural data: {summary.get('structural_files', 0):,}", highlight=False
        )

    console.print("\nRelated Commands:")
    console.print("  -> aud fce                     # Full FCE convergence report")
    console.print("  -> aud fce --format json       # JSON output for AI consumption")
    console.print("  -> aud fce --min-vectors 3     # Filter to 3+ vectors only")
    console.print("  -> aud explain <file> --fce    # FCE signal for specific file")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _get_validation_chain_health() -> dict:
    """Get validation chain health data.

    Runs validation chain analysis and returns summary for blueprint integration.
    """
    from theauditor.boundaries.chain_tracer import trace_validation_chains

    root = Path.cwd()
    db_path = root / ".pf" / "repo_index.db"
    chain_data = {
        "total_chains": 0,
        "by_status": {"intact": 0, "broken": 0, "no_validation": 0},
        "break_reasons": {},
        "chains": [],
    }

    try:
        chains = trace_validation_chains(db_path=str(db_path), max_entries=100)
        chain_data["total_chains"] = len(chains)

        for chain in chains:
            status = chain.chain_status
            chain_data["by_status"][status] = chain_data["by_status"].get(status, 0) + 1

            # Track break reasons
            if status == "broken" and chain.hops:
                for hop in chain.hops:
                    if hop.break_reason:
                        reason = hop.break_reason
                        chain_data["break_reasons"][reason] = (
                            chain_data["break_reasons"].get(reason, 0) + 1
                        )

            chain_data["chains"].append(
                {
                    "entry_point": chain.entry_point,
                    "file": chain.entry_file,
                    "line": chain.entry_line,
                    "status": chain.chain_status,
                    "hops": len(chain.hops),
                    "break_index": chain.break_index,
                }
            )

    except FileNotFoundError:
        chain_data["error"] = "Database not found (run aud full)"
    except Exception as e:
        chain_data["error"] = f"Analysis error: {e}"

    return chain_data


def _show_validated_drilldown(data: dict, db_path: str):
    """Drill down: Validation chain health analysis.

    Shows where type safety breaks in validation chains from entry points.
    """
    validated = data.get("validated", {})

    console.print("\nVALIDATION CHAIN HEALTH DRILL-DOWN")
    console.rule()
    console.print("Type Safety Analysis: Where does validation break down?")
    console.rule()

    if validated.get("error"):
        console.print(f"\n(!) {validated['error']}", highlight=False)
        console.print("  Run: aud full (populates entry points and call graph)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    total = validated.get("total_chains", 0)
    if total == 0:
        console.print("\n(!) No entry points found for chain analysis")
        console.print("  This may indicate:")
        console.print("    - No HTTP routes/endpoints indexed")
        console.print("    - Run: aud full (indexes routes and handlers)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    by_status = validated.get("by_status", {})
    intact = by_status.get("intact", 0)
    broken = by_status.get("broken", 0)
    no_val = by_status.get("no_validation", 0)

    console.print(f"\nEntry Points Analyzed: {total}", highlight=False)

    console.print("\nChain Health Breakdown:")
    intact_pct = (intact * 100 // total) if total else 0
    broken_pct = (broken * 100 // total) if total else 0
    no_val_pct = (no_val * 100 // total) if total else 0

    console.print(
        f"  [green]Chains Intact:[/green]    {intact:4d} ({intact_pct}%) - Validation preserved"
    )
    console.print(
        f"  [red]Chains Broken:[/red]    {broken:4d} ({broken_pct}%) - Type safety lost"
    )
    console.print(
        f"  [yellow]No Validation:[/yellow]    {no_val:4d} ({no_val_pct}%) - Missing at entry"
    )

    # Show break reasons
    break_reasons = validated.get("break_reasons", {})
    if break_reasons:
        console.print("\nTop Break Reasons:")
        sorted_reasons = sorted(break_reasons.items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:5]:
            console.print(f"  - {reason}: {count}", highlight=False)

    # Show problematic chains
    chains = validated.get("chains", [])
    broken_chains = [c for c in chains if c.get("status") == "broken"]
    no_val_chains = [c for c in chains if c.get("status") == "no_validation"]

    if broken_chains:
        console.print("\nBroken Chains (first 5):")
        for i, chain in enumerate(broken_chains[:5], 1):
            ep = chain.get("entry_point", "unknown")
            file = chain.get("file", "")
            line = chain.get("line", 0)
            hops = chain.get("hops", 0)
            break_idx = chain.get("break_index")
            console.print(f"\n  {i}. [BROKEN] {ep}", highlight=False)
            console.print(f"     Location: {file}:{line}", highlight=False)
            console.print(
                f"     Chain: {hops} hops, breaks at hop {break_idx}", highlight=False
            )

    if no_val_chains:
        console.print("\nMissing Validation (first 5):")
        for i, chain in enumerate(no_val_chains[:5], 1):
            ep = chain.get("entry_point", "unknown")
            file = chain.get("file", "")
            line = chain.get("line", 0)
            console.print(f"\n  {i}. [NO VALIDATION] {ep}", highlight=False)
            console.print(f"     Location: {file}:{line}", highlight=False)

    console.print("\nRelated Commands:")
    console.print("  -> aud boundaries --validated              # Full chain analysis")
    console.print("  -> aud boundaries --validated --format json  # JSON output")
    console.print("  -> aud boundaries --audit                  # Security boundary audit")
    console.print("  -> aud explain <file> --validated          # Chains for specific file")

    console.print("\n" + "=" * 80 + "\n", markup=False)


def _show_findings_drilldown(cursor: sqlite3.Cursor, tool_filter: str | None, severity_filter: str | None):
    """Drill down: All findings from analysis tools.

    Shows findings from: ruff, eslint, taint, cfg-analysis, mypy, terraform, osv, etc.
    """
    console.print("\nFINDINGS DRILL-DOWN")
    console.rule()
    console.print("Consolidated findings from all analysis tools")
    console.rule()

    # Build query with optional filters
    where_clauses = []
    params = []

    if tool_filter:
        where_clauses.append("tool = ?")
        params.append(tool_filter)

    if severity_filter:
        where_clauses.append("severity = ?")
        params.append(severity_filter)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get summary stats
    cursor.execute(f"""
        SELECT tool, COUNT(*) as count
        FROM findings_consolidated
        WHERE {where_sql}
        GROUP BY tool
        ORDER BY count DESC
    """, params)
    tool_counts = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute(f"""
        SELECT severity, COUNT(*) as count
        FROM findings_consolidated
        WHERE {where_sql}
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'error' THEN 3
                WHEN 'medium' THEN 4
                WHEN 'warning' THEN 5
                WHEN 'low' THEN 6
                ELSE 7
            END
    """, params)
    severity_counts = {row[0]: row[1] for row in cursor.fetchall()}

    total = sum(tool_counts.values())

    if total == 0:
        console.print("\n(!) No findings found")
        if tool_filter or severity_filter:
            console.print(f"  Filters applied: tool={tool_filter}, severity={severity_filter}")
        console.print("  Run: aud full (to populate findings)")
        console.print("\n" + "=" * 80 + "\n", markup=False)
        return

    console.print(f"\nTotal Findings: {total:,}", highlight=False)
    if tool_filter or severity_filter:
        console.print(f"  Filters: tool={tool_filter or 'all'}, severity={severity_filter or 'all'}", highlight=False)

    console.print("\nFindings by Tool:")
    for tool_name, count in tool_counts.items():
        pct = (count / total * 100) if total > 0 else 0
        bar_len = int(pct / 2)
        bar = "#" * bar_len
        console.print(f"  {tool_name:20s} {count:6d} ({pct:5.1f}%) {bar}", highlight=False)

    console.print("\nFindings by Severity:")
    severity_colors = {
        "critical": "red bold",
        "high": "red",
        "error": "yellow",
        "medium": "yellow",
        "warning": "cyan",
        "low": "dim",
    }
    for sev, count in severity_counts.items():
        color = severity_colors.get(sev, "white")
        console.print(f"  [{color}]{sev:12s}[/{color}] {count:6d}", highlight=False)

    # Get top files with most findings
    cursor.execute(f"""
        SELECT file, COUNT(*) as count,
               SUM(CASE WHEN severity IN ('critical', 'high', 'error') THEN 1 ELSE 0 END) as high_sev
        FROM findings_consolidated
        WHERE {where_sql}
        GROUP BY file
        ORDER BY high_sev DESC, count DESC
        LIMIT 15
    """, params)
    top_files = cursor.fetchall()

    if top_files:
        console.print("\nTop 15 Files (by high-severity findings):")
        for i, (file, count, high_sev) in enumerate(top_files, 1):
            sev_indicator = f"[red]{high_sev}H[/red]" if high_sev > 0 else "   "
            console.print(f"  {i:2d}. {sev_indicator} {count:4d} findings  {file}", highlight=False)

    # Get sample findings (high severity first)
    cursor.execute(f"""
        SELECT file, line, rule, tool, message, severity
        FROM findings_consolidated
        WHERE {where_sql}
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'error' THEN 3
                ELSE 4
            END,
            file, line
        LIMIT 10
    """, params)
    sample_findings = cursor.fetchall()

    if sample_findings:
        console.print("\nSample High-Priority Findings (first 10):")
        for file, line, rule, tool_name, message, sev in sample_findings:
            sev_display = f"[{severity_colors.get(sev, 'white')}]{sev:8s}[/{severity_colors.get(sev, 'white')}]"
            console.print(f"\n  {sev_display} {file}:{line}", highlight=False)
            console.print(f"    [{tool_name}] {rule}", highlight=False)
            if message:
                msg_short = message[:100] + "..." if len(message) > 100 else message
                console.print(f"    {msg_short}", highlight=False)

    console.print("\nRelated Commands:")
    console.print("  -> aud query --findings                    # All findings (structured)")
    console.print("  -> aud query --findings --severity high    # Filter by severity")
    console.print("  -> aud query --findings --tool ruff        # Filter by tool")
    console.print("  -> aud query --findings --format json      # JSON output for AI")
    console.print("  -> aud blueprint --taint                   # Focus on taint analysis")
    console.print("  -> aud blueprint --security                # Focus on security surface")

    console.print("\n" + "=" * 80 + "\n", markup=False)
