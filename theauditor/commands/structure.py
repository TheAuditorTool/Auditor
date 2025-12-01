"""Project structure and intelligence report command."""

import sqlite3
from pathlib import Path

import click

from theauditor.pipeline.ui import console
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command("structure")
@handle_exceptions
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--manifest", default="./.pf/manifest.json", help="Path to manifest.json")
@click.option("--db-path", default="./.pf/repo_index.db", help="Path to repo_index.db")
@click.option("--output", default="./.pf/STRUCTURE.md", help="Output file path")
@click.option("--max-depth", default=4, type=int, help="Maximum directory tree depth")
@click.option("--monoliths", is_flag=True, help="Find files >2150 lines (too large for AI to read)")
@click.option(
    "--threshold",
    default=2150,
    type=int,
    help="Line count threshold for --monoliths (default: 2150)",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format for --monoliths",
)
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
      .pf/STRUCTURE.md                  # Markdown report

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
    from theauditor.project_summary import generate_project_summary

    if monoliths:
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            console.print(
                "[error]Error: Database not found. Run 'aud full' first.[/error]", stderr=True
            )
            return ExitCodes.TASK_INCOMPLETE

        return _find_monoliths(db_path, threshold, format)

    manifest_exists = Path(manifest).exists()
    db_exists = Path(db_path).exists()

    if not manifest_exists and not db_exists:
        console.print(
            "[error]Warning: Neither manifest.json nor repo_index.db found[/error]", stderr=True
        )
        console.print("[error]Run 'aud full' first for complete statistics[/error]", stderr=True)
        console.print("Generating basic structure report...\n")
    elif not manifest_exists:
        console.print(
            "[error]Warning: manifest.json not found, statistics will be limited[/error]",
            stderr=True,
        )
    elif not db_exists:
        console.print(
            "[error]Warning: repo_index.db not found, symbol counts will be missing[/error]",
            stderr=True,
        )

    console.print(f"Analyzing project structure (max depth: {max_depth})...", highlight=False)

    try:
        report_content = generate_project_summary(
            root_path=root, manifest_path=manifest, db_path=db_path, max_depth=max_depth
        )

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        console.print(f"\n\\[OK] Project structure report generated: {output}", highlight=False)

        if manifest_exists:
            import json

            with open(manifest) as f:
                manifest_data = json.load(f)

            total_files = len(manifest_data)
            total_loc = sum(f.get("loc", 0) for f in manifest_data)
            total_bytes = sum(f.get("bytes", 0) for f in manifest_data)
            total_tokens = total_bytes // 4

            console.print("\nProject Summary:")
            console.print(f"  Files: {total_files:,}", highlight=False)
            console.print(f"  LOC: {total_loc:,}", highlight=False)
            console.print(f"  Tokens: ~{total_tokens:,}", highlight=False)

            claude_usable_context = 160000
            token_percent = (total_tokens / claude_usable_context * 100) if total_tokens > 0 else 0

            if token_percent > 100:
                console.print(
                    f"  Context Usage: {token_percent:.1f}% (EXCEEDS Claude's practical limit)",
                    highlight=False,
                )
            else:
                console.print(
                    f"  Context Usage: {token_percent:.1f}% of Claude's usable window",
                    highlight=False,
                )

        return ExitCodes.SUCCESS

    except Exception as e:
        console.print(f"[error]Error generating report: {e}[/error]", stderr=True, highlight=False)
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

        cursor.execute(
            """
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
            return ExitCodes.SUCCESS

        if output_format == "json":
            output_data = {
                "monoliths": [
                    {
                        "path": path,
                        "lines": lines,
                        "symbols": symbols,
                        "recommendation": "Refactor using chunked reading (agents/refactor.md Task 3.4)",
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
            console.print(
                f"Found {len(results)} files requiring chunked reading\n", highlight=False
            )

            for path, lines, symbols in results:
                console.print(f"\\[MONOLITH] {path}", highlight=False)
                console.print(f"  Lines: {lines:,} (>{threshold})", highlight=False)
                console.print(f"  Symbols: {symbols:,} functions/classes", highlight=False)
                console.print("  Recommend: Refactor using chunked reading")
                console.print("             See agents/refactor.md Task 3.4 for workflow")
                console.print()

            console.rule()
            console.print(
                f"Total: {len(results)} monolithic files requiring refactor planning",
                highlight=False,
            )
            console.rule()
            console.print("\nNext Steps:")
            console.print("  1. Trigger planning agent with: 'refactor <file> into modular files'")
            console.print("  2. Agent will automatically use chunked reading (1500-line chunks)")
            console.print("  3. Plan will follow database structure analysis + file content")

        return ExitCodes.SUCCESS

    except Exception as e:
        console.print(f"[error]Error finding monoliths: {e}[/error]", stderr=True, highlight=False)
        return ExitCodes.TASK_INCOMPLETE
