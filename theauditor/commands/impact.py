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
    """
    Analyze the impact radius of changing code at a specific location.
    
    This command traces both upstream dependencies (who calls this code)
    and downstream dependencies (what this code calls) to help understand
    the blast radius of potential changes.
    
    Example:
        aud impact --file src/auth.py --line 42
        aud impact --file theauditor/indexer.py --line 100 --verbose
    """
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