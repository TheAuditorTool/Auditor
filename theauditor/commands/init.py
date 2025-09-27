"""Initialize TheAuditor for first-time use."""

from pathlib import Path
import click


@click.command()
@click.option("--offline", is_flag=True, help="Skip network operations (deps check, docs fetch)")
@click.option("--skip-docs", is_flag=True, help="Skip documentation fetching")
@click.option("--skip-deps", is_flag=True, help="Skip dependency checking")
def init(offline, skip_docs, skip_deps):
    """Initialize TheAuditor and create analysis infrastructure.

    Sets up the complete TheAuditor environment in your project. This is
    typically the first command you run in a new project. It creates the
    .pf/ directory structure and performs initial analysis.

    Creates Directory Structure:
      .pf/
      ├── raw/                # Immutable tool outputs
      │   ├── *.json         # Tool results in JSON format
      │   └── *.ndjson       # Streaming outputs
      ├── readthis/          # AI-optimized chunks
      │   ├── *_chunk*.json  # Findings split into <65KB chunks
      │   └── summary.json   # Executive summary
      ├── .ast_cache/        # Cached AST trees for performance
      ├── repo_index.db      # SQLite database with all symbols
      ├── manifest.json      # File inventory
      ├── workset.json       # Target file list
      └── pipeline.log       # Execution trace

    Operations Performed:
      1. Index repository - Build symbol database
      2. Create workset - Identify all source files
      3. Check dependencies - Inventory packages (unless --skip-deps)
      4. Fetch documentation - Download API docs (unless --skip-docs)

    Examples:
      aud init                    # Full initialization
      aud init --offline          # Skip network operations
      aud init --skip-docs        # Skip documentation fetch
      aud init --skip-deps        # Skip dependency check

    After init, typical next steps:
      aud full                    # Run complete audit
      aud taint-analyze           # Check for vulnerabilities
      aud lint                    # Run code quality checks

    Note: Safe to run multiple times - won't overwrite existing data."""
    from theauditor.init import initialize_project
    
    click.echo("[INIT] Initializing TheAuditor...\n")
    click.echo("This will run all setup steps:")
    click.echo("  1. Index repository")
    click.echo("  2. Create workset")
    click.echo("  3. Check dependencies")
    click.echo("  4. Fetch documentation")
    click.echo("\n" + "="*60 + "\n")
    
    # Call the refactored initialization logic with progress callback
    result = initialize_project(
        offline=offline,
        skip_docs=skip_docs,
        skip_deps=skip_deps,
        progress_callback=click.echo
    )
    
    stats = result["stats"]
    has_failures = result["has_failures"]
    next_steps = result["next_steps"]
    
    # Results have already been displayed via progress callback
    
    # Summary
    click.echo("\n" + "="*60)
    
    if has_failures:
        click.echo("\n[WARN]  Initialization Partially Complete\n")
    else:
        click.echo("\n[SUCCESS] Initialization Complete!\n")
    
    # Show summary
    click.echo("[STATS] Summary:")
    if stats.get("index", {}).get("success"):
        click.echo(f"  * Indexed: {stats['index']['text_files']} files")
    else:
        click.echo("  * Indexing: [FAILED] Failed")
    
    if stats.get("workset", {}).get("success"):
        click.echo(f"  * Workset: {stats['workset']['files']} files")
    elif stats.get("workset", {}).get("files") == 0:
        click.echo("  * Workset: [WARN]  No files found")
    else:
        click.echo("  * Workset: [FAILED] Failed")
    
    if stats.get("deps", {}).get("success"):
        click.echo(f"  * Dependencies: {stats['deps'].get('total', 0)} total, {stats['deps'].get('outdated', 0)} outdated")
    elif stats.get("deps", {}).get("skipped"):
        click.echo("  * Dependencies: [SKIPPED]  Skipped")
    
    if stats.get("docs", {}).get("success"):
        fetched = stats['docs'].get('fetched', 0)
        cached = stats['docs'].get('cached', 0)
        capsules = stats['docs'].get('capsules', 0)
        if cached > 0:
            click.echo(f"  * Documentation: {fetched} fetched, {cached} cached, {capsules} capsules")
        else:
            click.echo(f"  * Documentation: {fetched} fetched, {capsules} capsules")
    elif stats.get("docs", {}).get("skipped"):
        click.echo("  * Documentation: [SKIPPED]  Skipped")
    
    # Next steps - only show if we have files to work with
    if next_steps:
        click.echo("\n[TARGET] Next steps:")
        for i, step in enumerate(next_steps, 1):
            click.echo(f"  {i}. Run: {step}")
        click.echo("\nOr run all at once:")
        click.echo(f"  {' && '.join(next_steps)}")
    else:
        click.echo("\n[WARN]  No files found to audit. Check that you're in the right directory.")