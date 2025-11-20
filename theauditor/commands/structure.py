"""Project structure and intelligence report command."""


import click
import sqlite3
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
@click.option("--monoliths", is_flag=True, help="Find files >2150 lines (too large for AI to read)")
@click.option("--threshold", default=2150, type=int, help="Line count threshold for --monoliths (default: 2150)")
@click.option("--format", type=click.Choice(['text', 'json']), default='text', help="Output format for --monoliths")
def structure(root, manifest, db_path, output, max_depth, monoliths, threshold, format):
    """Generate comprehensive project structure and intelligence report.

    Creates a detailed markdown report optimized for AI assistants to
    quickly understand your codebase architecture, identify key files,
    and make informed decisions about where to focus attention.

    Report Sections:
      1. Project Overview:
         - Total files, lines of code, estimated tokens
         - Language distribution with percentages
         - Framework detection (Django, React, etc.)

      2. Directory Structure:
         - Visual ASCII tree (configurable depth)
         - Folder purposes and contents
         - Hidden directory indicators

      3. Code Intelligence:
         - Top 10 largest files by token count
         - Top 15 critical files (main, index, app, etc.)
         - Entry points and configuration files
         - Test file locations

      4. AI Optimization Insights:
         - Token usage vs Claude's context window
         - Files that should be prioritized
         - Files that can be safely ignored
         - Chunking recommendations for large files

      5. Architecture Patterns:
         - Monorepo detection
         - Frontend/backend separation
         - Microservices structure
         - Package organization

    Examples:
      aud structure                      # Generate full report
      aud structure --max-depth 2        # Shallow directory tree
      aud structure --output report.md   # Custom output location

    Output:
      .pf/readthis/STRUCTURE.md         # Markdown report

    Report Format:
      # Project: MyApp
      ## Overview
      - Files: 234
      - LOC: 45,678
      - Tokens: ~250,000 (25% of Claude's context)

      ## Directory Tree
      ```
      myapp/
      ├── src/           [125 files, 30K LOC]
      │   ├── api/       [45 files]
      │   └── utils/     [20 files]
      └── tests/         [89 files]
      ```

      ## Critical Files
      1. src/main.py (Entry point, 2.5K tokens)
      2. src/api/auth.py (Authentication, 1.8K tokens)
      ...

    Use Cases:
      - AI Onboarding: Help AI understand project layout
      - Documentation: Auto-generate project docs
      - Code Review: Identify architecture issues
      - Refactoring: Find reorganization opportunities

    Token Estimation:
      - 1 token ≈ 4 bytes (rough approximation)
      - Claude context: ~1M tokens
      - Shows percentage of context your project uses

    Note: Run 'aud index' first for complete statistics including
    symbol counts and detailed code metrics.

    Monolith Detection (--monoliths flag):
      Identifies files larger than 2150 lines (approximately 80KB or 25k tokens)
      which cannot be read by AI assistants in a single request. These files
      require chunked reading (see agents/refactor.md Task 3.4 for workflow).

      Usage:
        aud structure --monoliths                  # Find all large files
        aud structure --monoliths --threshold 3000 # Custom threshold
        aud structure --monoliths --format json    # JSON output

      Output shows:
        - File path
        - Line count (compared to threshold)
        - Symbol count (functions, classes)
        - Refactor recommendation
    """
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("structure", sys.argv[2:], root=root)
        sys.exit(exit_code)

    from theauditor.project_summary import generate_project_summary, generate_directory_tree

    # Handle --monoliths flag (separate mode)
    if monoliths:
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            click.echo("Error: Database not found. Run 'aud full' first.", err=True)
            return ExitCodes.TASK_INCOMPLETE

        return _find_monoliths(db_path, threshold, format)

    # Normal structure report generation (original behavior)
    # Check if manifest exists (not required but enhances report)
    manifest_exists = Path(manifest).exists()
    db_exists = Path(db_path).exists()
    
    if not manifest_exists and not db_exists:
        click.echo("Warning: Neither manifest.json nor repo_index.db found", err=True)
        click.echo("Run 'aud full' first for complete statistics", err=True)
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
            with open(manifest) as f:
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


def _find_monoliths(db_path: str, threshold: int, output_format: str) -> int:
    """Find monolithic files (>threshold lines) that require chunked reading.

    Args:
        db_path: Path to repo_index.db
        threshold: Line count threshold (default 2150)
        output_format: 'text' or 'json'

    Returns:
        ExitCodes.SUCCESS or TASK_INCOMPLETE
    """
    import json

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query: Find files with max line number > threshold
        # Group by path to get line count and symbol count per file
        cursor.execute("""
            SELECT
                path,
                MAX(line) as line_count,
                COUNT(DISTINCT name) as symbol_count
            FROM symbols
            WHERE path NOT LIKE '%test%'
              AND path NOT LIKE '%/tests/%'
              AND path NOT LIKE '%/__pycache__/%'
              AND path NOT LIKE '%/node_modules/%'
            GROUP BY path
            HAVING line_count > ?
            ORDER BY line_count DESC
        """, (threshold,))

        results = cursor.fetchall()
        conn.close()

        if not results:
            if output_format == 'json':
                click.echo(json.dumps({
                    'monoliths': [],
                    'total': 0,
                    'threshold': threshold
                }, indent=2))
            else:
                click.echo(f"No monolithic files found (threshold: {threshold} lines)")
                click.echo("\nAll files are below the AI readability threshold!")
            return ExitCodes.SUCCESS

        # Format output
        if output_format == 'json':
            output_data = {
                'monoliths': [
                    {
                        'path': path,
                        'lines': lines,
                        'symbols': symbols,
                        'recommendation': 'Refactor using chunked reading (agents/refactor.md Task 3.4)'
                    }
                    for path, lines, symbols in results
                ],
                'total': len(results),
                'threshold': threshold
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            # Text format
            click.echo("=" * 80)
            click.echo(f"Monolithic Files (>{threshold} lines)")
            click.echo("=" * 80)
            click.echo(f"Found {len(results)} files requiring chunked reading\n")

            for path, lines, symbols in results:
                click.echo(f"[MONOLITH] {path}")
                click.echo(f"  Lines: {lines:,} (>{threshold})")
                click.echo(f"  Symbols: {symbols:,} functions/classes")
                click.echo(f"  Recommend: Refactor using chunked reading")
                click.echo(f"             See agents/refactor.md Task 3.4 for workflow")
                click.echo()

            click.echo("=" * 80)
            click.echo(f"Total: {len(results)} monolithic files requiring refactor planning")
            click.echo("=" * 80)
            click.echo("\nNext Steps:")
            click.echo("  1. Trigger planning agent with: 'refactor <file> into modular files'")
            click.echo("  2. Agent will automatically use chunked reading (1500-line chunks)")
            click.echo("  3. Plan will follow database structure analysis + file content")

        return ExitCodes.SUCCESS

    except Exception as e:
        click.echo(f"Error finding monoliths: {e}", err=True)
        return ExitCodes.TASK_INCOMPLETE