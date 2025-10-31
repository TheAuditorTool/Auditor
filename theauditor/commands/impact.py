"""Analyze the impact radius of code changes using the AST symbol graph."""

import platform
import click
from pathlib import Path

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


@click.command()
@click.option("--file", required=True, help="Path to the file containing the code to analyze")
@click.option("--line", required=True, type=int, help="Line number of the code to analyze")
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option("--json", is_flag=True, help="Output results as JSON")
@click.option("--max-depth", default=2, type=int, help="Maximum depth for transitive dependencies")
@click.option("--verbose", is_flag=True, help="Show detailed dependency information")
@click.option("--trace-to-backend", is_flag=True, help="Trace frontend API calls to backend endpoints (cross-stack analysis)")
def impact(file, line, db, json, max_depth, verbose, trace_to_backend):
    """Analyze the blast radius of code changes.

    Maps the complete impact of changing a specific function or class by
    tracing both upstream (who depends on this) and downstream (what this
    depends on) dependencies. Essential for understanding risk before
    refactoring or making changes.

    Impact Analysis Reveals:
      - Upstream: All code that calls or imports this function/class
      - Downstream: All code that this function/class depends on
      - Transitive: Multi-hop dependencies (A→B→C)
      - Cross-stack: Frontend API calls traced to backend endpoints

    Risk Levels:
      Low Impact:    < 5 affected files
      Medium Impact: 5-20 affected files
      High Impact:   > 20 affected files (exit code 1)

    Examples:
      aud impact --file src/auth.py --line 42
      aud impact --file api/user.py --line 100 --verbose
      aud impact --file src/utils.js --line 50 --trace-to-backend
      aud impact --file database.py --line 200 --max-depth 3

    Common Use Cases:
      Before refactoring:
        aud impact --file old_module.py --line 1

      Evaluating API changes:
        aud impact --file api/endpoints.py --line 150 --trace-to-backend

      Finding dead code:
        aud impact --file utils.py --line 300
        # If upstream is empty, code might be unused

    Output:
      Default: Human-readable impact report
      --json:  Machine-readable JSON for CI/CD integration

    Report Includes:
      - Direct callers and callees
      - Affected test files
      - Total impact radius
      - Risk assessment
      - File-level summary

    Exit Codes:
      0 = Low impact change
      1 = High impact change (>20 files)
      3 = Analysis error

    AI ASSISTANT CONTEXT:
      Purpose: Measure blast radius of code changes
      Input: .pf/repo_index.db (symbol table and call graph)
      Output: Impact report (stdout) or JSON (with --json flag)
      Prerequisites: aud index (populates symbol table and refs)
      Integration: Pre-refactoring risk assessment, change planning
      Performance: ~1-5 seconds (graph traversal)

    FLAG INTERACTIONS:
      --json + --verbose: Detailed JSON with transitive dependencies
      --trace-to-backend: Enables full-stack tracing (frontend→backend API calls)
      --max-depth: Controls transitive depth (higher = slower but more complete)

    TROUBLESHOOTING:
      "Database not found" error:
        Solution: Run 'aud index' first to build repo_index.db

      "Symbol not found" at line:
        Cause: Line number doesn't contain a function/class definition
        Solution: Provide line number of def/class statement

      Empty upstream (no callers):
        Meaning: Code might be dead/unused
        Action: Consider removing if truly unused

      Very high impact (>100 files):
        Cause: Utility function used everywhere
        Action: Be very careful with changes, add tests

      Slow analysis (>30 seconds):
        Cause: Very high --max-depth on large codebase
        Solution: Reduce --max-depth to 2 or 3

    Note: Requires 'aud index' to be run first."""
    from theauditor.impact_analyzer import analyze_impact, format_impact_report
    from theauditor.config_runtime import load_runtime_config
    import json as json_lib
    
    # Load configuration for default paths
    config = load_runtime_config(".")
    
    # Use default database path if not provided
    if db is None:
        db = config["paths"]["db"]
    
    # Verify database exists
    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud index' first to build the repository index", err=True)
        raise click.ClickException(f"Database not found: {db}")
    
    # Verify file exists (helpful for user)
    file = Path(file)
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
            click.echo("\n⚠ WARNING: High impact change detected!", err=True)
            exit(1)  # Non-zero exit for CI/CD integration
            
    except Exception as e:
        # Only show this for unexpected exceptions, not for already-handled errors
        if "No function or class found at" not in str(e):
            click.echo(f"Error during impact analysis: {e}", err=True)
        raise click.ClickException(str(e))