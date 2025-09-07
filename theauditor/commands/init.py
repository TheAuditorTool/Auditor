"""Initialize TheAuditor for first-time use."""

from pathlib import Path
import click


@click.command()
@click.option("--offline", is_flag=True, help="Skip network operations (deps check, docs fetch)")
@click.option("--skip-docs", is_flag=True, help="Skip documentation fetching")
@click.option("--skip-deps", is_flag=True, help="Skip dependency checking")
def init(offline, skip_docs, skip_deps):
    """Initialize TheAuditor for first-time use (runs all setup steps)."""
    from theauditor.init import initialize_project
    
    click.echo("[INIT] Initializing TheAuditor...\n")
    click.echo("This will run all setup steps:")
    click.echo("  1. Index repository")
    click.echo("  2. Create workset")
    click.echo("  3. Check dependencies")
    click.echo("  4. Fetch documentation")
    click.echo("\n" + "="*60 + "\n")
    
    # Call the refactored initialization logic
    result = initialize_project(
        offline=offline,
        skip_docs=skip_docs,
        skip_deps=skip_deps
    )
    
    stats = result["stats"]
    has_failures = result["has_failures"]
    next_steps = result["next_steps"]
    
    # Display step-by-step results
    click.echo("[INDEX] Step 1/5: Indexing repository...")
    if stats.get("index", {}).get("success"):
        click.echo(f"  [OK] Indexed {stats['index']['text_files']} text files")
    else:
        click.echo(f"  [FAIL] Failed: {stats['index'].get('error', 'Unknown error')}", err=True)
    
    click.echo("\n[TARGET] Step 2/5: Creating workset...")
    if stats.get("workset", {}).get("success"):
        click.echo(f"  [OK] Workset created with {stats['workset']['files']} files")
    elif stats.get("workset", {}).get("files") == 0:
        click.echo("  [WARN]  No files found to create workset")
    else:
        click.echo(f"  [FAIL] Failed: {stats['workset'].get('error', 'Unknown error')}", err=True)
    
    if not skip_deps and not offline:
        click.echo("\n[PACKAGE] Step 3/4: Checking dependencies...")
        if stats.get("deps", {}).get("success"):
            if stats["deps"]["total"] > 0:
                click.echo(f"  [OK] Found {stats['deps']['total']} dependencies ({stats['deps']['outdated']} outdated)")
            else:
                click.echo("  [OK] No dependency files found")
        else:
            click.echo(f"  [FAIL] Failed: {stats['deps'].get('error', 'Unknown error')}", err=True)
    else:
        click.echo("\n[PACKAGE] Step 3/4: Skipping dependency check (offline/skipped)")
    
    if not skip_docs and not offline:
        click.echo("\n[DOCS] Step 4/4: Fetching documentation...")
        if stats.get("docs", {}).get("success"):
            fetched = stats['docs'].get('fetched', 0)
            cached = stats['docs'].get('cached', 0)
            if fetched > 0 and cached > 0:
                click.echo(f"  [OK] Fetched {fetched} new docs, using {cached} cached docs")
            elif fetched > 0:
                click.echo(f"  [OK] Fetched {fetched} docs")
            elif cached > 0:
                click.echo(f"  [OK] Using {cached} cached docs (already up-to-date)")
            else:
                click.echo("  [WARN] No docs fetched or cached")
            
            # Report any errors from the stats
            if stats['docs'].get('errors'):
                errors = stats['docs']['errors']
                rate_limited = [e for e in errors if "rate limited" in e.lower()]
                other_errors = [e for e in errors if "rate limited" not in e.lower()]
                
                if rate_limited:
                    click.echo(f"  [WARN]  {len(rate_limited)} packages rate-limited (will retry with delay)")
                if other_errors and len(other_errors) <= 3:
                    for err in other_errors[:3]:
                        click.echo(f"  [WARN]  {err}")
                elif other_errors:
                    click.echo(f"  [WARN]  {len(other_errors)} packages failed to fetch")
            
            click.echo(f"  [OK] Created {stats['docs']['capsules']} doc capsules")
        elif stats["docs"].get("error") == "Interrupted by user":
            click.echo("\n  [WARN]  Documentation fetch interrupted (Ctrl+C)")
        else:
            click.echo(f"  [FAIL] Failed: {stats['docs'].get('error', 'Unknown error')}", err=True)
    else:
        click.echo("\n[DOCS] Step 4/4: Skipping documentation (offline/skipped)")
    
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