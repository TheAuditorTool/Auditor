"""Project structure and intelligence report command."""

import click
from pathlib import Path
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command("structure")
@handle_exceptions
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--manifest", default="./.pf/manifest.json", help="Path to manifest.json")
@click.option("--db-path", default="./.pf/repo_index.db", help="Path to repo_index.db")
@click.option("--output", default="./.pf/readthis/STRUCTURE.md", help="Output file path")
@click.option("--max-depth", default=4, type=int, help="Maximum directory tree depth")
def structure(root, manifest, db_path, output, max_depth):
    """Generate project structure and intelligence report.
    
    Creates a comprehensive markdown report including:
    - Directory tree visualization
    - Project statistics (files, LOC, tokens)
    - Language distribution
    - Top 10 largest files by tokens
    - Top 15 critical files by convention
    - AI context optimization recommendations
    """
    from theauditor.project_summary import generate_project_summary, generate_directory_tree
    
    # Check if manifest exists (not required but enhances report)
    manifest_exists = Path(manifest).exists()
    db_exists = Path(db_path).exists()
    
    if not manifest_exists and not db_exists:
        click.echo("Warning: Neither manifest.json nor repo_index.db found", err=True)
        click.echo("Run 'aud index' first for complete statistics", err=True)
        click.echo("Generating basic structure report...\n")
    elif not manifest_exists:
        click.echo("Warning: manifest.json not found, statistics will be limited", err=True)
    elif not db_exists:
        click.echo("Warning: repo_index.db not found, symbol counts will be missing", err=True)
    
    # Generate the report
    click.echo(f"Analyzing project structure (max depth: {max_depth})...")
    
    try:
        # Generate full report
        report_content = generate_project_summary(
            root_path=root,
            manifest_path=manifest,
            db_path=db_path,
            max_depth=max_depth
        )
        
        # Ensure output directory exists
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        click.echo(f"\n✓ Project structure report generated: {output}")
        
        # Show summary stats if available
        if manifest_exists:
            import json
            with open(manifest, 'r') as f:
                manifest_data = json.load(f)
            
            total_files = len(manifest_data)
            total_loc = sum(f.get('loc', 0) for f in manifest_data)
            total_bytes = sum(f.get('bytes', 0) for f in manifest_data)
            total_tokens = total_bytes // 4  # Rough approximation
            
            click.echo(f"\nProject Summary:")
            click.echo(f"  Files: {total_files:,}")
            click.echo(f"  LOC: {total_loc:,}")
            click.echo(f"  Tokens: ~{total_tokens:,}")
            
            # Token percentage of Claude's context
            # Claude has 200k context, but practical limit is ~160k for user content
            # (leaving room for system prompts, conversation history, response)
            claude_total_context = 200000  # Total context window
            claude_usable_context = 160000  # Practical limit for user content
            token_percent = (total_tokens / claude_usable_context * 100) if total_tokens > 0 else 0
            
            if token_percent > 100:
                click.echo(f"  Context Usage: {token_percent:.1f}% (EXCEEDS Claude's practical limit)")
            else:
                click.echo(f"  Context Usage: {token_percent:.1f}% of Claude's usable window")
        
        return ExitCodes.SUCCESS
        
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)
        return ExitCodes.TASK_INCOMPLETE