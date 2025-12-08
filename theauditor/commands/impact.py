"""Analyze the impact radius of code changes using the AST symbol graph."""

import platform
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console

IS_WINDOWS = platform.system() == "Windows"


FILE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".vue", ".rb", ".php",
}


def _detect_target_type(target: str) -> str:
    """Detect whether target is a file path or symbol name."""
    for ext in FILE_EXTENSIONS:
        if target.endswith(ext):
            return "file"
    if "/" in target or "\\" in target:
        return "file"
    return "symbol"


@click.command(cls=RichCommand)
@click.argument("target", required=False)
@click.option("--file", default=None, help="Path to the file containing the code to analyze")
@click.option("--line", default=None, type=int, help="Line number of the code to analyze")
@click.option(
    "--symbol", default=None, help="Symbol name to analyze (alternative to --file --line)"
)
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option("--json", is_flag=True, help="Output results as JSON")
@click.option(
    "--planning-context",
    "planning_context",
    is_flag=True,
    help="Output in planning-friendly format with risk categories",
)
@click.option("--max-depth", default=2, type=int, help="Maximum depth for transitive dependencies")
@click.option("--verbose", is_flag=True, help="Show detailed dependency information")
@click.option(
    "--trace-to-backend",
    is_flag=True,
    help="Trace frontend API calls to backend endpoints (cross-stack analysis)",
)
@click.option(
    "--fail-on-high-impact",
    is_flag=True,
    help="Exit with code 1 if high impact detected (for CI/CD pipelines)",
)
def impact(
    target, file, line, symbol, db, json, planning_context, max_depth, verbose, trace_to_backend, fail_on_high_impact
):
    """Analyze the blast radius of code changes.

    Maps the complete impact of changing a specific function or class by
    tracing both upstream (who depends on this) and downstream (what this
    depends on) dependencies. Essential for understanding risk before
    refactoring or making changes.

    INPUT OPTIONS (choose one):
      --symbol NAME     Query by symbol name (recommended for planning)
      --file PATH       Query by file path
      --file + --line   Query exact location

    Impact Analysis Reveals:
      - Upstream: All code that calls or imports this function/class
      - Downstream: All code that this function/class depends on
      - Transitive: Multi-hop dependencies (A->B->C)
      - Cross-stack: Frontend API calls traced to backend endpoints
      - Coupling Score: 0-100 metric for entanglement (--planning-context)

    Risk Levels:
      Low Impact:    <10 affected files, coupling <30
      Medium Impact: 10-30 affected files, coupling 30-70
      High Impact:   >30 affected files, coupling >70 (warning printed)

    Examples:
      # By symbol name (recommended)
      aud impact --symbol AuthManager
      aud impact --symbol "process_*" --planning-context

      # By file (analyzes first symbol)
      aud impact --file auth.py

      # By exact location
      aud impact --file src/auth.py --line 42
      aud impact --file api/user.py --line 100 --verbose

      # Cross-stack tracing
      aud impact --file src/utils.js --line 50 --trace-to-backend

    PLANNING WORKFLOW INTEGRATION:

      Before creating a plan:
        aud impact --symbol TargetClass --planning-context
        aud planning init --name "Refactor TargetClass"

      Pre-refactor checklist:
        aud deadcode | grep target.py
        aud impact --file target.py --planning-context

      Coupling score interpretation:
        <30  LOW    - Safe to refactor with minimal coordination
        30-70 MEDIUM - Review callers, consider phased rollout
        >70  HIGH   - Extract interface before refactoring

    SLASH COMMAND INTEGRATION:

      This command is used by:
        /theauditor:planning - Step 3 (impact assessment)
        /theauditor:refactor - Step 5 (blast radius check)

    Output Modes:
      Default:            Human-readable impact report
      --json:             Machine-readable JSON for CI/CD
      --planning-context: Planning-friendly format with:
                          - Coupling score (0-100)
                          - Dependency categories (prod/test/config)
                          - Suggested phases for incremental changes
                          - Risk recommendations

    Exit Codes:
      0 = Low impact change
      1 = High impact change (>20 files)
      3 = Analysis error

    AI ASSISTANT CONTEXT:
      Purpose: Measure blast radius + coupling for change planning
      Input: .pf/repo_index.db (symbol table and call graph)
      Output: Impact report, planning context, or JSON
      Prerequisites: aud full (populates symbol table and refs)
      Integration: Pre-refactoring risk assessment, planning agent
      Performance: ~1-5 seconds (graph traversal)

    FLAG INTERACTIONS:
      --symbol: Resolves to file:line automatically from database
      --planning-context: Outputs coupling score, categories, phases
      --json + --verbose: Detailed JSON with transitive dependencies
      --trace-to-backend: Full-stack tracing (frontend->backend API calls)
      --max-depth: Controls transitive depth (higher = slower)

    TROUBLESHOOTING:
      "Must provide either --symbol or --file":
        Solution: Use --symbol NAME or --file PATH

      "Symbol not found":
        Solution: Run 'aud query --pattern "name%"' to find similar

      "Ambiguous symbol - multiple matches":
        Solution: Use --file and --line to specify exact location

      Very high coupling (>70):
        Meaning: Tightly coupled, risky to change
        Action: Extract interface first, then refactor

    SEE ALSO:
      aud manual impact       Learn about blast radius analysis
      aud manual refactor     Detect incomplete refactorings

    Note: Requires 'aud full' to be run first."""

    import json as json_lib
    import sqlite3

    from theauditor.commands.config import DB_PATH
    from theauditor.MachineL.impact_analyzer import (
        analyze_impact,
        format_impact_report,
        format_planning_context,
    )

    if db is None:
        db = DB_PATH

    db_path = Path(db)
    if not db_path.exists():
        err_console.print(f"[error]Error: Database not found at {db}[/error]", highlight=False)
        err_console.print(
            "[error]Run 'aud full' first to build the repository index[/error]",
        )
        raise click.ClickException(f"Database not found: {db}")

    # Handle positional TARGET argument (auto-detect file vs symbol)
    if target and not file and not symbol:
        target_type = _detect_target_type(target)
        if target_type == "file":
            file = target
        else:
            symbol = target

    if symbol is None and file is None:
        raise click.ClickException(
            "Must provide a target.\n"
            "Examples:\n"
            "  aud impact src/auth.py              (positional, auto-detected as file)\n"
            "  aud impact AuthManager              (positional, auto-detected as symbol)\n"
            "  aud impact --symbol AuthManager     (explicit symbol)\n"
            "  aud impact --file auth.py --line 42 (explicit file + line)"
        )

    if symbol:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()

            if "%" in symbol or "*" in symbol:
                pattern = symbol.replace("*", "%")
                cursor.execute(
                    """
                    SELECT name, path, line, type
                    FROM symbols
                    WHERE name LIKE ? AND type IN ('function', 'class')
                    ORDER BY path, line
                """,
                    (pattern,),
                )
            else:
                cursor.execute(
                    """
                    SELECT name, path, line, type
                    FROM symbols
                    WHERE name = ? AND type IN ('function', 'class')
                    ORDER BY path, line
                """,
                    (symbol,),
                )

            results = cursor.fetchall()

            if not results:
                raise click.ClickException(
                    f"Symbol '{symbol}' not found in database.\n"
                    "Hints:\n"
                    "  - Run 'aud full' to rebuild the index\n"
                    "  - Use 'aud query --pattern \"{symbol}%\"' to find similar symbols\n"
                    "  - Class methods are indexed as ClassName.methodName"
                )

            if len(results) == 1:
                sym_name, sym_path, sym_line, sym_type = results[0]
                file = sym_path
                line = sym_line
                err_console.print(
                    f"[error]Resolved: {sym_name} ({sym_type}) at {sym_path}:{sym_line}[/error]",
                    highlight=False,
                )
            else:
                err_console.print(
                    f"[error]Found {len(results)} symbols matching '{symbol}':[/error]",
                    highlight=False,
                )
                for i, (name, path, ln, typ) in enumerate(results[:10], 1):
                    err_console.print(
                        f"[error]  {i}. {name} ({typ}) at {path}:{ln}[/error]",
                        highlight=False,
                    )
                if len(results) > 10:
                    err_console.print(
                        f"[error]  ... and {len(results) - 10} more[/error]",
                        highlight=False,
                    )
                err_console.print(
                    "[error][/error]",
                )
                err_console.print(
                    "[error]Use --file and --line to specify exact location, or refine pattern.[/error]",
                )
                raise click.ClickException("Ambiguous symbol - multiple matches found")

    if file and line is None:
        file_path = Path(file).as_posix()
        if file_path.startswith("./"):
            file_path = file_path[2:]

        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name, line, type
                FROM symbols
                WHERE path = ? AND type IN ('function', 'class')
                ORDER BY line
            """,
                (file_path,),
            )
            file_symbols = cursor.fetchall()

            if not file_symbols:
                cursor.execute(
                    """
                    SELECT name, line, type
                    FROM symbols
                    WHERE path LIKE ? AND type IN ('function', 'class')
                    ORDER BY line
                """,
                    (f"%{file_path}",),
                )
                file_symbols = cursor.fetchall()

            if not file_symbols:
                raise click.ClickException(
                    f"No functions or classes found in '{file}'.\n"
                    "Ensure the file has been indexed with 'aud full'."
                )

            sym_name, sym_line, sym_type = file_symbols[0]
            line = sym_line
            err_console.print(
                f"[error]Analyzing file from first symbol: {sym_name} ({sym_type}) at line {sym_line}[/error]",
                highlight=False,
            )
            err_console.print(
                f"[error]File contains {len(file_symbols)} symbols total[/error]",
                highlight=False,
            )

    if isinstance(file, str):
        file = Path(file)

    if not file.exists():
        err_console.print(
            f"[error]Warning: File {file} not found in filesystem[/error]",
            highlight=False,
        )
        err_console.print(
            "[error]Proceeding with analysis using indexed data...[/error]",
        )

    try:
        result = analyze_impact(
            db_path=str(db_path),
            target_file=str(file),
            target_line=line,
            trace_to_backend=trace_to_backend,
        )

        if json:
            console.print(json_lib.dumps(result, indent=2, sort_keys=True), markup=False)
        elif planning_context:
            report = format_planning_context(result)
            console.print(report, markup=False)
        else:
            report = format_impact_report(result)
            console.print(report, markup=False)

            if verbose and not result.get("error"):
                console.print("\n" + "=" * 60, markup=False)
                console.print("DETAILED DEPENDENCY INFORMATION")
                console.rule()

                if result.get("upstream_transitive"):
                    console.print(
                        f"\nTransitive Upstream Dependencies ({len(result['upstream_transitive'])} total):",
                        highlight=False,
                    )
                    for dep in result["upstream_transitive"][:20]:
                        depth_indicator = "  " * (3 - dep.get("depth", 1))
                        tree_char = "+-" if IS_WINDOWS else "└─"
                        console.print(
                            f"{depth_indicator}{tree_char} {dep['symbol']} in {dep['file']}:{dep['line']}",
                            highlight=False,
                        )
                    if len(result["upstream_transitive"]) > 20:
                        console.print(
                            f"  ... and {len(result['upstream_transitive']) - 20} more",
                            highlight=False,
                        )

                if result.get("downstream_transitive"):
                    console.print(
                        f"\nTransitive Downstream Dependencies ({len(result['downstream_transitive'])} total):",
                        highlight=False,
                    )
                    for dep in result["downstream_transitive"][:20]:
                        depth_indicator = "  " * (3 - dep.get("depth", 1))
                        if dep["file"] != "external":
                            tree_char = "+-" if IS_WINDOWS else "└─"
                            console.print(
                                f"{depth_indicator}{tree_char} {dep['symbol']} in {dep['file']}:{dep['line']}",
                                highlight=False,
                            )
                        else:
                            tree_char = "+-" if IS_WINDOWS else "└─"
                            console.print(
                                f"{depth_indicator}{tree_char} {dep['symbol']} (external)",
                                highlight=False,
                            )
                    if len(result["downstream_transitive"]) > 20:
                        console.print(
                            f"  ... and {len(result['downstream_transitive']) - 20} more",
                            highlight=False,
                        )

        if result.get("error"):
            raise click.ClickException(result["error"])

        summary = result.get("impact_summary", {})
        if summary.get("total_impact", 0) > 20:
            err_console.print(
                "[warning]\n[!] WARNING: High impact change detected![/warning]",
            )
            if fail_on_high_impact:
                raise SystemExit(1)

    except Exception as e:
        if "No function or class found at" not in str(e):
            err_console.print(f"[error]Error during impact analysis: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e
