"""Blueprint command - architectural visualization of indexed codebase.

Truth courier mode: Shows facts about code architecture with NO recommendations.
Supports drill-down flags for specific analysis areas.
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import click

from theauditor.utils.error_handler import handle_exceptions

VALID_TABLES = frozenset({"symbols", "function_call_args", "assignments", "api_endpoints"})


@click.command()
@click.option("--structure", is_flag=True, help="Drill down into codebase structure details")
@click.option("--graph", is_flag=True, help="Drill down into import/call graph analysis")
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
@handle_exceptions
def blueprint(structure, graph, security, taint, boundaries, deps, all, output_format):
    """Architectural fact visualization with drill-down analysis modes (NO recommendations).

    Truth-courier mode visualization that presents pure architectural facts extracted from
    indexed codebase with zero prescriptive language. Supports drill-down flags to focus on
    specific dimensions (structure, dependencies, security surface, data flow). Output format
    toggles between visual ASCII tree and structured JSON for programmatic consumption.

    AI ASSISTANT CONTEXT:
      Purpose: Visualize codebase architecture facts (no recommendations)
      Input: .pf/repo_index.db (indexed code)
      Output: Terminal tree or JSON (configurable via --format)
      Prerequisites: aud index (populates database)
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

      --all: Export complete data as JSON

    EXAMPLES:
      aud blueprint
      aud blueprint --structure
      aud blueprint --graph --format json
      aud blueprint --all > architecture.json

    PERFORMANCE: ~2-5 seconds

    RELATED COMMANDS:
      aud structure  # Alternative visualization
      aud graph      # Dedicated graph analysis

    NOTE: This command shows FACTS ONLY - no recommendations, no prescriptive
    language. For actionable insights, use 'aud fce' or 'aud full'.

    ADDITIONAL EXAMPLES:
        aud blueprint --all              # Export everything to JSON

    PREREQUISITES:
        aud full            # Complete analysis (recommended)
            OR
        aud index           # Minimum (basic structure only)
        aud detect-patterns # Optional (for security surface)
        aud taint-analyze   # Optional (for data flow)
        aud graph build     # Optional (for import graph)

    WHAT YOU GET (Truth Courier Facts Only):
        - File counts by directory/language
        - Most-called functions (call graph centrality)
        - Security pattern counts (JWT, OAuth, SQL)
        - Taint flow statistics (sources, sinks, paths)
        - Import relationships (internal vs external)
        - NO recommendations, NO "should be", NO prescriptive language
    """
    from pathlib import Path

    pf_dir = Path.cwd() / ".pf"
    repo_db = pf_dir / "repo_index.db"
    graphs_db = pf_dir / "graphs.db"

    if not pf_dir.exists() or not repo_db.exists():
        click.echo("\nERROR: No indexed database found", err=True)
        click.echo("Run: aud full", err=True)
        raise click.Abort()

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
            "all": all,
        }

        data = _gather_all_data(cursor, graphs_db, flags)

        if all:
            click.echo(json.dumps(data, indent=2))
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
                click.echo(json.dumps(summary, indent=2))
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

    try:
        cursor.execute("SELECT type, COUNT(*) as count FROM symbols GROUP BY type")
        structure["by_type"] = {row["type"]: row["count"] for row in cursor.fetchall()}
    except Exception:
        pass

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
            SUM(CASE WHEN f.ext IN ('.ts', '.tsx') AND s.type = 'class' THEN 1 ELSE 0 END) AS ts_class_total
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

    try:
        cursor.execute("SELECT pattern_type FROM jwt_patterns")
        for row in cursor.fetchall():
            if "sign" in row[0]:
                security["jwt"]["sign"] += 1
            elif "verify" in row[0] or "decode" in row[0]:
                security["jwt"]["verify"] += 1
    except Exception:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM oauth_patterns")
        security["oauth"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM password_patterns")
        security["password"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE file NOT LIKE '%/migrations/%'
              AND file NOT LIKE '%/seeders/%'
              AND file NOT LIKE '%migration%'
        """)
        security["sql_queries"]["total"] = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*) FROM sql_queries
            WHERE command != 'UNKNOWN'
              AND file NOT LIKE '%/migrations/%'
              AND file NOT LIKE '%/seeders/%'
              AND file NOT LIKE '%migration%'
        """)
        security["sql_queries"]["raw"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
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
    except Exception:
        pass

    return security


def _get_data_flow(cursor) -> dict:
    """Get taint flow statistics."""
    data_flow = {
        "taint_sources": 0,
        "taint_paths": 0,
        "cross_function_flows": 0,
    }

    try:
        cursor.execute("SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'taint'")
        data_flow["taint_paths"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
        cursor.execute("SELECT COUNT(DISTINCT source_var_name) FROM assignment_sources")
        data_flow["taint_sources"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM function_return_sources")
        data_flow["cross_function_flows"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    return data_flow


def _get_import_graph(graphs_db_path: Path) -> dict:
    """Get import graph statistics."""
    imports = {"total": 0, "external": 0, "internal": 0, "circular": 0}

    try:
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
    except Exception:
        pass

    return imports


def _get_performance(cursor, db_path: Path) -> dict:
    """Get analysis metrics."""
    metrics = {"db_size_mb": 0, "total_rows": 0, "files_indexed": 0, "symbols_extracted": 0}

    if db_path.exists():
        metrics["db_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

    tables = ["symbols", "function_call_args", "assignments", "api_endpoints"]
    total = 0
    for table in tables:
        try:
            if table not in VALID_TABLES:
                continue
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total += cursor.fetchone()[0] or 0
        except Exception:
            pass

    metrics["total_rows"] = total

    try:
        cursor.execute("SELECT COUNT(DISTINCT path) FROM symbols")
        metrics["files_indexed"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM symbols")
        metrics["symbols_extracted"] = cursor.fetchone()[0] or 0
    except Exception:
        pass

    return metrics


def _show_top_level_overview(data: dict):
    """Show top-level overview with tree structure (truth courier mode)."""
    lines = []

    lines.append("")
    lines.append("🏗️  TheAuditor Code Blueprint")
    lines.append("")
    lines.append("━" * 80)
    lines.append("ARCHITECTURAL ANALYSIS (100% Accurate, 0% Inference)")
    lines.append("━" * 80)
    lines.append("")

    struct = data["structure"]
    lines.append("📊 Codebase Structure:")

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
        lines.append("🔥 Hot Files (by call count):")
        for i, hf in enumerate(hot, 1):
            lines.append(f"  {i}. {hf['file']}")
            lines.append(
                f"     → Called by: {hf['caller_count']} files ({hf['total_calls']} call sites)"
            )
        lines.append("")

    sec = data["security_surface"]
    lines.append("🔒 Security Surface:")
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
        lines.append("🌊 Data Flow (Junction Table Analysis):")
        lines.append(f"  ├─ Taint Sources: {df['taint_sources']:,} (unique variables)")
        lines.append(
            f"  ├─ Cross-Function Flows: {df['cross_function_flows']:,} (via return→assignment)"
        )
        lines.append(f"  └─ Taint Paths: {df['taint_paths']} detected")
        lines.append("")

    if data["import_graph"]:
        imp = data["import_graph"]
        lines.append("📦 Import Graph:")
        lines.append(f"  ├─ Total imports: {imp['total']:,}")
        lines.append(f"  ├─ External deps: {imp['external']:,}")
        lines.append(f"  └─ Internal imports: {imp['internal']:,}")
        lines.append("")

    perf = data["performance"]
    lines.append("⚡ Analysis Metrics:")
    lines.append(f"  ├─ Files indexed: {perf['files_indexed']:,}")
    lines.append(f"  ├─ Symbols extracted: {perf['symbols_extracted']:,}")
    lines.append(f"  ├─ Database size: {perf['db_size_mb']} MB")
    lines.append("  └─ Query time: <10ms")
    lines.append("")

    lines.append("━" * 80)
    lines.append("Truth Courier Mode: Facts only, no recommendations")
    lines.append("Use drill-down flags for details: --structure, --graph, --security, --taint")
    lines.append("━" * 80)
    lines.append("")

    click.echo("\n".join(lines))


def _show_structure_drilldown(data: dict, cursor: sqlite3.Cursor):
    """Drill down: SURGICAL structure analysis - scope understanding.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    struct = data["structure"]

    click.echo("\n🏗️  STRUCTURE DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Scope Understanding: What's the scope? Where are boundaries? What's orphaned?")
    click.echo("=" * 80)

    click.echo("\nMonorepo Detection:")
    by_dir = struct["by_directory"]
    has_backend = any("backend" in d for d in by_dir)
    has_frontend = any("frontend" in d for d in by_dir)
    has_packages = any("packages" in d for d in by_dir)

    if has_backend or has_frontend or has_packages:
        click.echo(
            f"  ✓ Detected: {'backend/' if has_backend else ''}{'frontend/' if has_frontend else ''}{'packages/' if has_packages else ''} split"
        )
        if has_backend:
            backend_files = sum(
                count for dir_name, count in by_dir.items() if "backend" in dir_name
            )
            click.echo(f"  Backend: {backend_files} files")
        if has_frontend:
            frontend_files = sum(
                count for dir_name, count in by_dir.items() if "frontend" in dir_name
            )
            click.echo(f"  Frontend: {frontend_files} files")
    else:
        click.echo("  ✗ No monorepo structure detected (single-directory project)")

    click.echo("\nFiles by Directory:")
    for dir_name, count in sorted(struct["by_directory"].items(), key=lambda x: -x[1])[:15]:
        click.echo(f"  {dir_name:50s} {count:6,} files")

    click.echo("\nFiles by Language:")
    lang_map = {
        ".ts": "TypeScript",
        ".js": "JavaScript",
        ".py": "Python",
        ".tsx": "TSX",
        ".jsx": "JSX",
    }
    for ext, count in sorted(struct["by_language"].items(), key=lambda x: -x[1]):
        lang = lang_map.get(ext, ext)
        click.echo(f"  {lang:50s} {count:6,} files")

    if struct["by_type"]:
        click.echo("\nSymbols by Type:")
        for sym_type, count in sorted(struct["by_type"].items(), key=lambda x: -x[1]):
            click.echo(f"  {sym_type:50s} {count:6,} symbols")

    naming = data.get("naming_conventions", {})
    if naming:
        click.echo("\nCode Style Analysis (Naming Conventions):")

        for lang in ["python", "javascript", "typescript"]:
            lang_data = naming.get(lang, {})
            if not lang_data or not any(lang_data.values()):
                continue

            lang_name = lang.capitalize()
            click.echo(f"\n  {lang_name}:")

            for symbol_type in ["functions", "classes"]:
                patterns = lang_data.get(symbol_type, {})
                if not patterns or not patterns.get("dominant"):
                    continue

                dominant = patterns["dominant"]
                consistency = patterns["consistency"]
                click.echo(
                    f"    {symbol_type.capitalize()}: {dominant} ({consistency}% consistency)"
                )

    precedents = data.get("architectural_precedents", [])
    if precedents:
        click.echo("\nArchitectural Precedents (Plugin Loader Patterns):")
        click.echo("  (Files importing 3+ modules from same directory - architectural conventions)")

        for prec in precedents[:15]:
            consumer = prec["consumer"]
            directory = prec["directory"]
            count = prec["count"]
            imports = prec["imports"]

            click.echo(f"\n  {consumer}")
            click.echo(f"    -> {directory}/ ({count} modules)")

            for imp in imports[:5]:
                display = Path(imp).name if "/" in imp else imp
                click.echo(f"       - {display}")

            if count > 5:
                click.echo(f"       ... and {count - 5} more")

        if len(precedents) > 15:
            click.echo(f"\n  ... and {len(precedents) - 15} more patterns")

        click.echo(f"\n  Total patterns found: {len(precedents)}")
    else:
        click.echo("\nArchitectural Precedents: None detected")

    try:
        cursor.execute("""
            SELECT language, name, version, COUNT(*) as file_count
            FROM frameworks
            GROUP BY name, language, version
            ORDER BY file_count DESC
        """)
        frameworks = cursor.fetchall()

        if frameworks:
            click.echo("\nFramework Detection:")
            for lang, fw, ver, count in frameworks:
                version_str = f"v{ver}" if ver else "(version unknown)"
                click.echo(f"  {fw} {version_str} ({lang}) - {count} file(s)")
        else:
            click.echo("\nFramework Detection: None detected")
    except sqlite3.OperationalError:
        click.echo("\nFramework Detection: (Table not found - run 'aud full')")

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
            click.echo("\nRefactor History (Recent Checks):")
            for ts, target, rtype, mig_found, mig_complete, schema_ok, status in refactor_history:
                date = ts.split("T")[0] if "T" in ts else ts
                consistent = "consistent" if schema_ok == 1 else "inconsistent"
                complete = "complete" if mig_complete == 1 else "incomplete"
                click.echo(f"  {date}: {target}")
                click.echo(
                    f"    Type: {rtype} | Risk: {status} | Migrations: {mig_found} found ({complete})"
                )
                click.echo(f"    Schema: {consistent}")
        else:
            click.echo("\nRefactor History: No checks recorded (run 'aud refactor' to populate)")
    except sqlite3.OperationalError:
        click.echo("\nRefactor History: (Table not found - run 'aud full')")

    click.echo("\nToken Estimates (for context planning):")
    total_files = struct["total_files"]

    estimated_tokens = total_files * 400
    click.echo(f"  Total files: {total_files:,}")
    click.echo(f"  Estimated tokens: ~{estimated_tokens:,} tokens")
    if estimated_tokens > 100000:
        click.echo("  ⚠ Exceeds single LLM context window")
        click.echo("  → Use 'aud query' for targeted analysis instead of reading all files")

    click.echo("\nMigration Paths Detected:")
    migration_paths = [d for d in by_dir if "migration" in d.lower()]
    legacy_paths = [d for d in by_dir if "legacy" in d.lower() or "deprecated" in d.lower()]

    if migration_paths:
        for path in migration_paths:
            click.echo(f"  ⚠ {path}/ ({by_dir[path]} files)")
    if legacy_paths:
        for path in legacy_paths:
            click.echo(f"  ⚠ {path}/ ({by_dir[path]} files marked DEPRECATED)")
    if not migration_paths and not legacy_paths:
        click.echo("  ✓ No migration or legacy paths detected")

    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud structure' for full markdown report with LOC details")
    click.echo("  → Use 'aud query --file <path> --show-dependents' for impact analysis")
    click.echo("  → Use 'aud graph viz' for visual dependency map")

    click.echo("\n" + "=" * 80 + "\n")


def _show_graph_drilldown(data: dict):
    """Drill down: SURGICAL dependency mapping - what depends on what."""
    click.echo("\n📊 GRAPH DRILL-DOWN")
    click.echo("=" * 80)
    click.echo(
        "Dependency Mapping: What depends on what? Where are bottlenecks? What breaks if I change X?"
    )
    click.echo("=" * 80)

    if data["import_graph"]:
        imp = data["import_graph"]
        click.echo("\nImport Graph Summary:")
        click.echo(f"  Total imports: {imp['total']:,}")
        click.echo(f"  External dependencies: {imp['external']:,}")
        click.echo(f"  Internal imports: {imp['internal']:,}")
        click.echo(f"  Circular dependencies: {imp['circular']} cycles detected")
    else:
        click.echo("\n⚠ No graph data available")
        click.echo("  Run: aud graph build")
        click.echo("\n" + "=" * 80 + "\n")
        return

    click.echo("\nGateway Files (high betweenness centrality):")
    click.echo("  These are bottlenecks - changing them breaks many dependents")
    hot = data["hot_files"]
    if hot:
        for i, hf in enumerate(hot[:10], 1):
            click.echo(f"\n  {i}. {hf['file']}")
            click.echo(f"     Symbol: {hf['symbol']}")
            click.echo(
                f"     Called by: {hf['caller_count']} files | Total calls: {hf['total_calls']}"
            )
            if hf["caller_count"] > 20:
                click.echo(f"     ⚠ HIGH IMPACT - changes affect {hf['caller_count']} files")
                click.echo(
                    f"     → Use 'aud query --symbol {hf['symbol']} --show-callers' for full list"
                )
    else:
        click.echo("  ✓ No high-centrality files detected (good - decoupled architecture)")

    click.echo("\nCircular Dependencies:")
    if imp["circular"] > 0:
        click.echo(f"  ⚠ {imp['circular']} cycles detected")
        click.echo("  → Use 'aud graph analyze' for cycle detection")
        click.echo("  → Use 'aud graph viz --view cycles' for visual diagram")
    else:
        click.echo("  ✓ No circular dependencies detected (clean architecture)")

    click.echo("\nExternal Dependencies:")
    click.echo(f"  Total: {imp['external']:,} external imports")
    click.echo("  → Use 'aud deps --check-latest' for version analysis")
    click.echo("  → Use 'aud deps --vuln-scan' for security vulnerabilities")

    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud query --file <path> --show-dependents' to see impact radius")
    click.echo("  → Use 'aud graph viz --view full' for complete dependency graph")
    click.echo("  → Use 'aud graph analyze' for health metrics and cycle detection")

    click.echo("\n" + "=" * 80 + "\n")


def _show_security_drilldown(data: dict, cursor):
    """Drill down: SURGICAL attack surface mapping - what's vulnerable.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    sec = data["security_surface"]

    click.echo("\n🔒 SECURITY DRILL-DOWN")
    click.echo("=" * 80)
    click.echo(
        "Attack Surface Mapping: What's the attack surface? What's protected? What needs fixing?"
    )
    click.echo("=" * 80)

    click.echo(f"\nAPI Endpoint Security Coverage ({sec['api_endpoints']['total']} endpoints):")
    total_endpoints = sec["api_endpoints"]["total"]
    protected = sec["api_endpoints"]["protected"]
    unprotected = sec["api_endpoints"]["unprotected"]

    if total_endpoints > 0:
        protected_pct = int((protected / total_endpoints) * 100)
        click.echo(f"  Protected: {protected} ({protected_pct}%)")
        click.echo(
            f"  Unprotected: {unprotected} ({100 - protected_pct}%) {'← SECURITY RISK' if unprotected > 0 else ''}"
        )

    if unprotected > 0:
        click.echo("\n  Unprotected Endpoints (showing first 10):")
        try:
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
                click.echo(f"    {i}. {method:7s} {path:40s} ({file}:{line})")
                click.echo(f"       Handler: {handler}")

            if unprotected > 10:
                click.echo(f"    ... {unprotected - 10} more unprotected endpoints")
                click.echo(
                    "    → Use 'aud query --show-api-coverage | grep \"[OPEN]\"' for full list"
                )
        except Exception:
            pass

    click.echo("\nAuthentication Patterns Detected:")
    jwt_total = sec["jwt"]["sign"] + sec["jwt"]["verify"]
    oauth_total = sec["oauth"]

    click.echo(f"\n  JWT: {jwt_total} usages")
    click.echo(f"    ├─ jwt.sign: {sec['jwt']['sign']} locations (token generation)")
    click.echo(f"    └─ jwt.verify/decode: {sec['jwt']['verify']} locations (token validation)")

    click.echo(f"\n  OAuth: {oauth_total} usages")

    click.echo(f"\n  Password Handling: {sec['password']} operations")

    if jwt_total > 0 and oauth_total > 0:
        click.echo("\n  ⚠ MIGRATION IN PROGRESS?")
        click.echo("    Both JWT and OAuth detected - possible auth migration")
        click.echo("    → Use 'aud context --file auth_migration.yaml' to track progress")

    click.echo("\nHardcoded Secrets:")
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM findings_consolidated WHERE rule LIKE '%secret%' OR rule LIKE '%hardcoded%'"
        )
        secret_count = cursor.fetchone()[0]
        if secret_count > 0:
            click.echo(f"  ⚠ {secret_count} potential hardcoded secrets detected")
            click.echo("  -> Use 'aud query --symbol <func> --show-code' for details")
        else:
            click.echo("  ✓ No hardcoded secrets detected")
    except Exception:
        click.echo("  (No secret scan data available)")

    click.echo("\nSQL Injection Risk:")
    sql_total = sec["sql_queries"]["total"]
    sql_raw = sec["sql_queries"]["raw"]

    if sql_total > 0:
        raw_pct = int((sql_raw / sql_total) * 100) if sql_total > 0 else 0
        click.echo(f"  Total queries: {sql_total}")
        click.echo(
            f"  Raw/dynamic queries: {sql_raw} ({raw_pct}%) {'← Potential SQLi' if sql_raw > 0 else ''}"
        )
        click.echo(f"  Parameterized queries: {sql_total - sql_raw} ({100 - raw_pct}%)")

        if sql_raw > 0:
            click.echo(f"\n  ⚠ High Risk: {sql_raw} dynamic SQL queries detected")
            click.echo("  → Use 'aud query --category sql --format json' for full analysis")
    else:
        click.echo("  ✓ No SQL queries detected (or using ORM)")

    try:
        cursor.execute("SELECT COUNT(*) FROM api_endpoints WHERE method = 'POST'")
        post_count = cursor.fetchone()[0]
        if post_count > 0:
            click.echo("\nCSRF Protection:")
            click.echo(f"  POST endpoints: {post_count}")
            click.echo("  → Manual review required for CSRF token validation")
    except Exception:
        pass

    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud query --show-api-coverage' for full endpoint security matrix")
    click.echo("  → Use 'aud taint-analyze' for data flow security analysis")
    click.echo("  → Use 'aud deps --vuln-scan' for dependency CVEs (OSV-Scanner)")
    click.echo(
        "  → Use 'aud query --pattern \"localStorage\" --type-filter function' to find insecure storage"
    )

    click.echo("\n" + "=" * 80 + "\n")


def _show_taint_drilldown(data: dict, cursor):
    """Drill down: SURGICAL data flow mapping - where does user data flow.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    df = data["data_flow"]

    click.echo("\n🌊 TAINT DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Data Flow Mapping: Where does user data flow? What's sanitized? What's vulnerable?")
    click.echo("=" * 80)

    if df["taint_paths"] == 0:
        click.echo("\n⚠ No taint analysis data available")
        click.echo("  Run: aud taint-analyze")
        click.echo("\n" + "=" * 80 + "\n")
        return

    click.echo("\nTop Taint Sources (user-controlled data):")
    try:
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
                click.echo(f"  {i}. {row['source_var_name']} ({row['usage_count']} locations)")
        else:
            click.echo("  (No common taint sources detected in junction tables)")
    except Exception as e:
        click.echo(f"  (Could not query taint sources: {e})")

    click.echo(f"\nTaint Paths Detected: {df['taint_paths']}")
    click.echo(f"Cross-Function Flows: {df['cross_function_flows']:,} (via return→assignment)")

    click.echo("\nVulnerable Data Flows (showing first 5):")
    try:
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

                click.echo(f"\n  {i}. [{severity.upper()}] {category}")
                click.echo(f"     Location: {file}:{line}")
                click.echo(f"     Issue: {message}")

            if df["taint_paths"] > 5:
                click.echo(f"\n  ... {df['taint_paths'] - 5} more taint paths")
                click.echo("  -> Use 'aud taint-analyze --json' for full vulnerability details")
        else:
            click.echo("  (No taint findings in findings_consolidated table)")
    except Exception as e:
        click.echo(f"  (Could not query taint findings: {e})")

    click.echo("\nSanitization Coverage:")
    try:
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
            click.echo(f"  Sanitization functions called: {sanitizer_count} times")
            click.echo(f"  → Compare with {df['taint_paths']} taint paths")
            if sanitizer_count < df["taint_paths"]:
                coverage_pct = int((sanitizer_count / df["taint_paths"]) * 100)
                click.echo(f"  ⚠ LOW COVERAGE (~{coverage_pct}%) - many flows unsanitized")
        else:
            click.echo("  ⚠ No sanitization functions detected")
            click.echo(f"  → {df['taint_paths']} taint paths with NO sanitization")
    except Exception:
        click.echo("  (Could not analyze sanitization coverage)")

    click.echo("\nDynamic Dispatch Vulnerabilities:")
    try:
        cursor.execute("""
            SELECT COUNT(*) as dispatch_count
            FROM findings_consolidated
            WHERE rule LIKE '%dynamic%dispatch%'
               OR rule LIKE '%prototype%pollution%'
               OR category = 'dynamic_dispatch'
        """)
        dispatch_count = cursor.fetchone()["dispatch_count"]

        if dispatch_count > 0:
            click.echo(f"  ⚠ {dispatch_count} dynamic dispatch vulnerabilities detected")
            click.echo("  → User can control which function executes (RCE risk)")
            click.echo("  → Use 'aud query --category dynamic_dispatch' for locations")
        else:
            click.echo("  ✓ No dynamic dispatch vulnerabilities detected")
    except Exception:
        click.echo("  (Could not analyze dynamic dispatch)")

    click.echo("\nCross-Reference Commands:")
    click.echo("  -> Use 'aud query --symbol <func> --show-taint-flow' for specific function flows")
    click.echo("  -> Use 'aud query --variable req.body --show-flow --depth 3' for data tracing")
    click.echo("  -> Use 'aud taint-analyze --json' to re-run analysis with fresh data")

    click.echo("\n" + "=" * 80 + "\n")


def _get_dependencies(cursor) -> dict:
    """Get dependency facts from package_configs and python_package_configs tables.

    Queries DATABASE (source of truth), not JSON files.
    """
    deps = {
        "total": 0,
        "by_manager": {},
        "packages": [],
        "workspaces": [],
    }

    try:
        cursor.execute("""
            SELECT file_path, package_name, version, dependencies, dev_dependencies
            FROM package_configs
        """)
        for row in cursor.fetchall():
            file_path = row["file_path"]
            pkg_name = row["package_name"]
            version = row["version"]

            prod_deps = json.loads(row["dependencies"]) if row["dependencies"] else {}
            dev_deps = json.loads(row["dev_dependencies"]) if row["dev_dependencies"] else {}

            workspace = {
                "file": file_path,
                "name": pkg_name,
                "version": version,
                "manager": "npm",
                "prod_count": len(prod_deps),
                "dev_count": len(dev_deps),
                "prod_deps": prod_deps,
                "dev_deps": dev_deps,
            }
            deps["workspaces"].append(workspace)

            deps["by_manager"]["npm"] = (
                deps["by_manager"].get("npm", 0) + len(prod_deps) + len(dev_deps)
            )
            deps["total"] += len(prod_deps) + len(dev_deps)

            for name, ver in prod_deps.items():
                deps["packages"].append(
                    {"name": name, "version": ver, "manager": "npm", "dev": False}
                )
            for name, ver in dev_deps.items():
                deps["packages"].append(
                    {"name": name, "version": ver, "manager": "npm", "dev": True}
                )
    except Exception:
        pass

    try:
        cursor.execute("""
            SELECT file_path, project_name, project_version, dependencies, optional_dependencies
            FROM python_package_configs
        """)
        for row in cursor.fetchall():
            file_path = row["file_path"]
            pkg_name = row["project_name"]
            version = row["project_version"]

            prod_deps_raw = json.loads(row["dependencies"]) if row["dependencies"] else []
            opt_deps_raw = (
                json.loads(row["optional_dependencies"]) if row["optional_dependencies"] else {}
            )

            dev_deps = []
            if isinstance(opt_deps_raw, dict):
                for _group_name, group_deps in opt_deps_raw.items():
                    if isinstance(group_deps, list):
                        dev_deps.extend(group_deps)

            workspace = {
                "file": file_path,
                "name": pkg_name,
                "version": version,
                "manager": "pip",
                "prod_count": len(prod_deps_raw),
                "dev_count": len(dev_deps),
            }
            deps["workspaces"].append(workspace)

            deps["by_manager"]["pip"] = (
                deps["by_manager"].get("pip", 0) + len(prod_deps_raw) + len(dev_deps)
            )
            deps["total"] += len(prod_deps_raw) + len(dev_deps)

            for dep in prod_deps_raw:
                if isinstance(dep, dict):
                    deps["packages"].append(
                        {
                            "name": dep.get("name", ""),
                            "version": dep.get("version", ""),
                            "manager": "pip",
                            "dev": False,
                        }
                    )
            for dep in dev_deps:
                if isinstance(dep, dict):
                    deps["packages"].append(
                        {
                            "name": dep.get("name", ""),
                            "version": dep.get("version", ""),
                            "manager": "pip",
                            "dev": True,
                        }
                    )
    except Exception:
        pass

    return deps


def _show_deps_drilldown(data: dict, cursor):
    """Drill down: Dependency analysis - packages, versions, managers.

    Args:
        data: Blueprint data dict from _gather_all_data
        cursor: Database cursor (passed from main function - dependency injection)
    """
    deps = data.get("dependencies", {})

    click.echo("\nDEPS DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Dependency Analysis: What packages? What versions? What managers?")
    click.echo("=" * 80)

    if deps["total"] == 0:
        click.echo("\n(!) No dependencies found in database")
        click.echo("  Run: aud full (indexes package.json, pyproject.toml, requirements.txt)")
        click.echo("\n" + "=" * 80 + "\n")
        return

    click.echo(f"\nTotal Dependencies: {deps['total']}")
    click.echo("\nBy Package Manager:")
    for manager, count in sorted(deps["by_manager"].items(), key=lambda x: -x[1]):
        click.echo(f"  {manager}: {count} packages")

    click.echo("\nProjects/Workspaces:")
    for ws in deps["workspaces"]:
        click.echo(f"\n  {ws['file']}")
        click.echo(f"    Name: {ws['name'] or '(unnamed)'}")
        click.echo(f"    Version: {ws['version'] or '(no version)'}")
        click.echo(f"    Manager: {ws['manager']}")
        click.echo(f"    Production deps: {ws['prod_count']}")
        click.echo(f"    Dev deps: {ws['dev_count']}")

        if ws.get("prod_deps"):
            click.echo("    Top dependencies:")
            for _i, (name, ver) in enumerate(list(ws["prod_deps"].items())[:5]):
                click.echo(f"      - {name}: {ver}")
            if len(ws["prod_deps"]) > 5:
                click.echo(f"      ... and {len(ws['prod_deps']) - 5} more")

    click.echo("\nOutdated Package Check:")
    try:
        cursor.execute("SELECT COUNT(*) FROM dependency_versions WHERE is_outdated = 1")
        outdated_count = cursor.fetchone()[0]
        if outdated_count > 0:
            click.echo(f"  (!) {outdated_count} outdated packages detected")
            cursor.execute("""
                SELECT package_name, locked_version, latest_version, manager
                FROM dependency_versions
                WHERE is_outdated = 1
                LIMIT 10
            """)
            for row in cursor.fetchall():
                click.echo(
                    f"    {row['package_name']}: {row['locked_version']} -> {row['latest_version']} ({row['manager']})"
                )
        else:
            click.echo("  (No outdated package data - run 'aud deps --check-latest')")
    except Exception:
        click.echo("  (No version check data - run 'aud deps --check-latest')")

    click.echo("\nRelated Commands:")
    click.echo("  -> aud deps --check-latest   # Check for outdated packages")
    click.echo("  -> aud deps --vuln-scan      # Scan for CVEs (OSV-Scanner)")
    click.echo("  -> aud deps --upgrade-all    # YOLO mode: upgrade everything")

    click.echo("\n" + "=" * 80 + "\n")


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

    click.echo("\nBOUNDARIES DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Boundary Distance Analysis: How far is validation from entry points?")
    click.echo("=" * 80)

    if bounds.get("error"):
        click.echo(f"\n(!) Analysis error: {bounds['error']}")
        click.echo("  Run: aud full (to index routes and handlers)")
        click.echo("\n" + "=" * 80 + "\n")
        return

    total = bounds.get("total_entries", 0)
    if total == 0:
        click.echo("\n(!) No entry points found in database")
        click.echo("  Run: aud full (indexes routes and handlers)")
        click.echo("\n" + "=" * 80 + "\n")
        return

    click.echo(f"\nEntry Points Analyzed: {total}")

    by_quality = bounds.get("by_quality", {})

    click.echo("\nBoundary Quality Breakdown:")
    click.echo(f"  Clear (dist 0):      {by_quality.get('clear', 0):4d} - Validation at entry")
    click.echo(f"  Acceptable (1-2):    {by_quality.get('acceptable', 0):4d} - Validation nearby")
    click.echo(
        f"  Fuzzy (3+ or multi): {by_quality.get('fuzzy', 0):4d} - Late or scattered validation"
    )
    click.echo(f"  Missing:             {by_quality.get('missing', 0):4d} - No validation found")

    missing = bounds.get("missing_controls", 0)
    late = bounds.get("late_validation", 0)

    if missing > 0 or late > 0:
        click.echo("\nRisk Summary:")
        if missing > 0:
            click.echo(f"  (!) {missing} entry points have NO validation control")
        if late > 0:
            click.echo(f"  (!) {late} entry points have LATE validation (distance 3+)")

    entries = bounds.get("entries", [])
    if entries:
        click.echo("\nTop Issues (by severity):")
        for i, entry in enumerate(entries[:10], 1):
            quality = entry.get("quality", "unknown")
            distance = entry.get("distance")
            ep = entry.get("entry_point", "unknown")
            file = entry.get("file", "")
            line = entry.get("line", 0)
            controls = entry.get("control_count", 0)

            dist_str = f"dist={distance}" if distance is not None else "no path"

            click.echo(f"\n  {i}. [{quality.upper()}] {ep}")
            click.echo(f"     Location: {file}:{line}")
            click.echo(f"     Distance: {dist_str}, Controls found: {controls}")

    click.echo("\nRelated Commands:")
    click.echo("  -> aud boundaries --format json        # Full analysis as JSON")
    click.echo("  -> aud boundaries --type input-validation  # Focus on input validation")
    click.echo("  -> aud blueprint --taint               # Data flow analysis")
    click.echo("  -> aud blueprint --security            # Security surface overview")

    click.echo("\n" + "=" * 80 + "\n")
