"""Analyze the impact radius of code changes using the AST symbol graph."""

import platform
import click
from pathlib import Path

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


@click.command()
@click.option("--file", default=None, help="Path to the file containing the code to analyze")
@click.option("--line", default=None, type=int, help="Line number of the code to analyze")
@click.option("--symbol", default=None, help="Symbol name to analyze (alternative to --file --line)")
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option("--json", is_flag=True, help="Output results as JSON")
@click.option("--planning-context", "planning_context", is_flag=True, help="Output in planning-friendly format with risk categories")
@click.option("--max-depth", default=2, type=int, help="Maximum depth for transitive dependencies")
@click.option("--verbose", is_flag=True, help="Show detailed dependency information")
@click.option("--trace-to-backend", is_flag=True, help="Trace frontend API calls to backend endpoints (cross-stack analysis)")
def impact(file, line, symbol, db, json, planning_context, max_depth, verbose, trace_to_backend):
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
      High Impact:   >30 affected files, coupling >70 (exit code 1)

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
      Prerequisites: aud index (populates symbol table and refs)
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

    Note: Requires 'aud index' to be run first."""
    # Import directly to avoid __init__.py which has missing taint module
    import sys
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "impact_analyzer",
        Path(__file__).parent.parent / "insights" / "impact_analyzer.py"
    )
    impact_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(impact_module)
    analyze_impact = impact_module.analyze_impact
    format_impact_report = impact_module.format_impact_report
    format_planning_context = impact_module.format_planning_context
    classify_risk = impact_module.classify_risk
    from theauditor.config_runtime import load_runtime_config
    import json as json_lib
    import sqlite3

    # Load configuration for default paths
    config = load_runtime_config(".")

    # Use default database path if not provided
    if db is None:
        db = config["paths"]["db"]

    # Verify database exists
    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud full' first to build the repository index", err=True)
        raise click.ClickException(f"Database not found: {db}")

    # Input validation: need either (file + line) or (symbol)
    if symbol is None and file is None:
        raise click.ClickException(
            "Must provide either --symbol or --file.\n"
            "Examples:\n"
            "  aud impact --symbol AuthManager\n"
            "  aud impact --file auth.py --line 42\n"
            "  aud impact --file auth.py  (analyzes all symbols in file)"
        )

    # If symbol provided, resolve it to file:line from database
    if symbol:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            # Support pattern matching with % or *
            if '%' in symbol or '*' in symbol:
                pattern = symbol.replace('*', '%')
                cursor.execute("""
                    SELECT name, path, line, type
                    FROM symbols
                    WHERE name LIKE ? AND type IN ('function', 'class')
                    ORDER BY path, line
                """, (pattern,))
            else:
                cursor.execute("""
                    SELECT name, path, line, type
                    FROM symbols
                    WHERE name = ? AND type IN ('function', 'class')
                    ORDER BY path, line
                """, (symbol,))

            results = cursor.fetchall()

            if not results:
                raise click.ClickException(
                    f"Symbol '{symbol}' not found in database.\n"
                    "Hints:\n"
                    "  - Run 'aud index' to rebuild the index\n"
                    "  - Use 'aud query --pattern \"{symbol}%\"' to find similar symbols\n"
                    "  - Class methods are indexed as ClassName.methodName"
                )

            if len(results) == 1:
                # Single match - use it
                sym_name, sym_path, sym_line, sym_type = results[0]
                file = sym_path
                line = sym_line
                click.echo(f"Resolved: {sym_name} ({sym_type}) at {sym_path}:{sym_line}", err=True)
            else:
                # Multiple matches - show them and ask for clarification
                click.echo(f"Found {len(results)} symbols matching '{symbol}':", err=True)
                for i, (name, path, ln, typ) in enumerate(results[:10], 1):
                    click.echo(f"  {i}. {name} ({typ}) at {path}:{ln}", err=True)
                if len(results) > 10:
                    click.echo(f"  ... and {len(results) - 10} more", err=True)
                click.echo("", err=True)
                click.echo("Use --file and --line to specify exact location, or refine pattern.", err=True)
                raise click.ClickException("Ambiguous symbol - multiple matches found")

    # If file provided without line, analyze whole file (list all symbols)
    if file and line is None:
        file_path = Path(file).as_posix()
        if file_path.startswith("./"):
            file_path = file_path[2:]

        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, line, type
                FROM symbols
                WHERE path = ? AND type IN ('function', 'class')
                ORDER BY line
            """, (file_path,))
            file_symbols = cursor.fetchall()

            # Also try with path variations
            if not file_symbols:
                cursor.execute("""
                    SELECT name, line, type
                    FROM symbols
                    WHERE path LIKE ? AND type IN ('function', 'class')
                    ORDER BY line
                """, (f"%{file_path}",))
                file_symbols = cursor.fetchall()

            if not file_symbols:
                raise click.ClickException(
                    f"No functions or classes found in '{file}'.\n"
                    "Ensure the file has been indexed with 'aud index'."
                )

            # Use first symbol as target (typically module-level or first function)
            sym_name, sym_line, sym_type = file_symbols[0]
            line = sym_line
            click.echo(f"Analyzing file from first symbol: {sym_name} ({sym_type}) at line {sym_line}", err=True)
            click.echo(f"File contains {len(file_symbols)} symbols total", err=True)

    # Convert file to Path if string
    if isinstance(file, str):
        file = Path(file)

    # Verify file exists (helpful for user)
    if not file.exists():
        click.echo(f"Warning: File {file} not found in filesystem", err=True)
        click.echo("Proceeding with analysis using indexed data...", err=True)
    
    # Perform impact analysis
    try:
        result = analyze_impact(
            db_path=str(db_path),
            target_file=str(file),
            target_line=line,
            trace_to_backend=trace_to_backend
        )
        
        # Output results
        if json:
            # JSON output for programmatic use
            click.echo(json_lib.dumps(result, indent=2, sort_keys=True))
        elif planning_context:
            # Planning-friendly format with risk categories
            report = format_planning_context(result)
            click.echo(report)
        else:
            # Human-readable report
            report = format_impact_report(result)
            click.echo(report)
            
            # Additional verbose output
            if verbose and not result.get("error"):
                click.echo("\n" + "=" * 60)
                click.echo("DETAILED DEPENDENCY INFORMATION")
                click.echo("=" * 60)
                
                # Show transitive upstream
                if result.get("upstream_transitive"):
                    click.echo(f"\nTransitive Upstream Dependencies ({len(result['upstream_transitive'])} total):")
                    for dep in result["upstream_transitive"][:20]:
                        depth_indicator = "  " * (3 - dep.get("depth", 1))
                        tree_char = "+-" if IS_WINDOWS else "└─"
                        click.echo(f"{depth_indicator}{tree_char} {dep['symbol']} in {dep['file']}:{dep['line']}")
                    if len(result["upstream_transitive"]) > 20:
                        click.echo(f"  ... and {len(result['upstream_transitive']) - 20} more")
                
                # Show transitive downstream
                if result.get("downstream_transitive"):
                    click.echo(f"\nTransitive Downstream Dependencies ({len(result['downstream_transitive'])} total):")
                    for dep in result["downstream_transitive"][:20]:
                        depth_indicator = "  " * (3 - dep.get("depth", 1))
                        if dep["file"] != "external":
                            tree_char = "+-" if IS_WINDOWS else "└─"
                            click.echo(f"{depth_indicator}{tree_char} {dep['symbol']} in {dep['file']}:{dep['line']}")
                        else:
                            tree_char = "+-" if IS_WINDOWS else "└─"
                            click.echo(f"{depth_indicator}{tree_char} {dep['symbol']} (external)")
                    if len(result["downstream_transitive"]) > 20:
                        click.echo(f"  ... and {len(result['downstream_transitive']) - 20} more")
        
        # Exit with appropriate code
        if result.get("error"):
            # Error already displayed in the report, just exit with code
            exit(3)  # Exit code 3 for analysis errors
        
        # Warn if high impact
        summary = result.get("impact_summary", {})
        if summary.get("total_impact", 0) > 20:
            click.echo("\n[!] WARNING: High impact change detected!", err=True)
            exit(1)  # Non-zero exit for CI/CD integration
            
    except Exception as e:
        # Only show this for unexpected exceptions, not for already-handled errors
        if "No function or class found at" not in str(e):
            click.echo(f"Error during impact analysis: {e}", err=True)
        raise click.ClickException(str(e))