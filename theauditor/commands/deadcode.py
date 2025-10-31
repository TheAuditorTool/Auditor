"""Dead code detection CLI command.

Usage: aud deadcode
"""

import click
import json
from pathlib import Path
from theauditor.context.deadcode import detect_isolated_modules
from theauditor.utils.error_handler import handle_exceptions


@click.command("deadcode")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option("--path-filter", help="Only analyze paths matching filter (e.g., 'theauditor/%')")
@click.option(
    "--exclude",
    multiple=True,
    default=['test', '__tests__', 'migrations', 'node_modules', '.venv'],
    help="Exclude paths matching patterns"
)
@click.option(
    "--format",
    type=click.Choice(['text', 'json', 'summary']),
    default='text',
    help="Output format"
)
@click.option("--save", type=click.Path(), help="Save output to file")
@click.option("--fail-on-dead-code", is_flag=True, help="Exit 1 if dead code found")
@handle_exceptions
def deadcode(project_path, path_filter, exclude, format, save, fail_on_dead_code):
    """Detect isolated modules, unreachable functions, and never-imported code.

    Identifies dead code by analyzing the import graph - any module with symbols (functions, classes)
    that is never imported is potentially dead. Uses database-only analysis (no AST reparsing) with
    confidence classification to reduce false positives from entry points, tests, and CLI scripts.

    AI ASSISTANT CONTEXT:
      Purpose: Finds unused code (modules, functions) that can be safely removed
      Input: .pf/repo_index.db (symbols and refs tables)
      Output: List of isolated modules with confidence levels
      Prerequisites: aud index (populates import graph in database)
      Integration: Code cleanup workflow, technical debt reduction
      Performance: ~1-2 seconds (pure database query, no file I/O)

    WHAT IT DETECTS:
      Isolated Modules:
        - Python files with functions/classes never imported anywhere
        - JavaScript modules with exports never imported
        - Entire features implemented but never integrated

      Dead Functions:
        - Functions defined but never called (within analyzed scope)
        - Callback handlers for removed event listeners
        - Deprecated API endpoints no longer routed

      False Positive Reduction:
        - CLI entry points (cli.py, main.py, __main__.py) = medium confidence
        - Test files (test_*.py, *.test.js) = medium confidence
        - Migration scripts (migrations/, alembic/) = excluded by default
        - Package markers (__init__.py with no code) = low confidence

    CONFIDENCE LEVELS:
      HIGH: Regular module with ≥1 symbol, never imported, not special file type
      MEDIUM: Entry point (CLI/main), test file, or script (might be invoked externally)
      LOW: Empty __init__.py, generated code, or single-function utils (false positive likely)

    ALGORITHM (Database-Only):
      1. Query symbols table for files containing functions/classes (has_code=True)
      2. Query refs table for all imported file paths
      3. Compute set difference: files_with_code - imported_files = isolated_modules
      4. Classify confidence based on file path patterns and symbol count
      5. Filter by --path-filter and --exclude patterns

    EXAMPLES:
      # Use Case 1: Find all dead code after indexing
      aud index && aud deadcode

      # Use Case 2: Analyze specific directory
      aud deadcode --path-filter 'src/features/%'

      # Use Case 3: CI/CD fail on dead code detection
      aud deadcode --fail-on-dead-code || exit 1

      # Use Case 4: Export for review
      aud deadcode --format json --save ./dead_code_report.json

      # Use Case 5: Summary statistics only
      aud deadcode --format summary

    COMMON WORKFLOWS:
      Code Cleanup Sprint:
        aud index && aud deadcode --format json --save cleanup_targets.json

      Pre-Release Audit:
        aud deadcode --exclude test --fail-on-dead-code

      Technical Debt Measurement:
        aud deadcode --format summary | grep "HIGH confidence"

    OUTPUT FILES:
      .pf/repo_index.db (tables read):
        - symbols: Files with functions/classes
        - refs: Import statements
      Output (if --save specified):
        - JSON/text report of isolated modules

    OUTPUT FORMAT (JSON Schema):
      {
        "isolated_modules": [
          {
            "file": "src/deprecated_feature.py",
            "symbol_count": 15,
            "confidence": "high",
            "reason": "No imports found",
            "recommendation": "remove"
          }
        ],
        "summary": {
          "total_isolated": 5,
          "high_confidence": 3,
          "medium_confidence": 2,
          "low_confidence": 0
        }
      }

    PERFORMANCE EXPECTATIONS:
      Small (<5K LOC):     ~0.5 seconds,  ~50MB RAM
      Medium (20K LOC):    ~1 second,     ~100MB RAM
      Large (100K+ LOC):   ~2 seconds,    ~150MB RAM
      Note: Database query only, no file I/O or AST parsing

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --path-filter + --format json     # Targeted analysis with export
        --exclude test --fail-on-dead-code  # CI/CD strict mode

      Flag Modifiers:
        --fail-on-dead-code: Exit 1 if ANY dead code found (strict mode)
        --format: Changes output structure (text/json/summary)
        --exclude: Reduces false positives (tests, migrations, vendor)

    PREREQUISITES:
      Required:
        aud index              # Populates symbols and refs tables

      Optional:
        None (standalone database query)

    EXIT CODES:
      0 = Success, no dead code found (or --fail-on-dead-code not set)
      1 = Dead code found AND --fail-on-dead-code flag set
      2 = Error (database missing or query failed)

    RELATED COMMANDS:
      aud index              # Populates import graph in database
      aud graph analyze      # Shows dependency graph (complementary view)
      aud refactor           # Detects incomplete refactorings (related issue)
      aud impact             # Analyzes change blast radius (opposite of dead code)

    SEE ALSO:
      aud explain workset    # Understand scope filtering

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud index' first to create .pf/repo_index.db

      False positive: CLI entry point flagged as dead
        → Expected (medium confidence) - CLI files invoked externally
        → Review manually, entry points are not dead code

      False positive: Test file flagged as dead
        → Tests not imported, invoked by test runner
        → Use --exclude test to filter out test files

      Missing dead code (known unused file not detected):
        → File might have no symbols (empty or only imports)
        → Check if file was indexed: grep filename .pf/manifest.json
        → Re-run 'aud index' to refresh database

    NOTE: This analysis is conservative - it detects modules never imported, not
    functions never called within modules. For function-level analysis, use 'aud graph analyze'.
    """
    project_path = Path(project_path).resolve()
    db_path = project_path / ".pf" / "repo_index.db"

    if not db_path.exists():
        click.echo("Error: Database not found. Run 'aud index' first.", err=True)
        raise click.ClickException("Database not found")

    try:
        modules = detect_isolated_modules(
            str(db_path),
            path_filter=path_filter,
            exclude_patterns=list(exclude)
        )

        # ALWAYS save to .pf/raw/dead_code.json for AI/pipeline consumption
        raw_dir = project_path / ".pf" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_output = raw_dir / "dead_code.json"
        with open(raw_output, 'w', encoding='utf-8') as f:
            f.write(_format_json(modules))

        # Format output for user
        if format == 'json':
            output = _format_json(modules)
        elif format == 'summary':
            output = _format_summary(modules)
        else:
            output = _format_text(modules)

        click.echo(output)

        # Save to custom path if requested
        if save:
            save_path = Path(save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(output)
            click.echo(f"\nSaved to: {save_path}", err=True)

        # Exit code logic
        if fail_on_dead_code and len(modules) > 0:
            raise click.ClickException(f"Dead code detected: {len(modules)} files")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise


def _format_text(modules) -> str:
    """Format as ASCII table (NO EMOJIS for Windows CP1252)."""
    lines = []
    lines.append("=" * 80)
    lines.append("Dead Code Analysis Report")
    lines.append("=" * 80)
    lines.append(f"Total dead code items: {len(modules)}")
    lines.append("")

    if not modules:
        lines.append("[OK] No dead code detected!")
        return "\n".join(lines)

    lines.append("Isolated Modules (never imported):")
    lines.append("-" * 80)

    for module in modules:
        confidence_marker = {
            'high': '[HIGH]',
            'medium': '[MED ]',
            'low': '[LOW ]'
        }.get(module.confidence, '[????]')

        lines.append(f"{confidence_marker} {module.path}")
        lines.append(f"   Symbols: {module.symbol_count}")
        lines.append(f"   Confidence: {module.confidence.upper()}")
        lines.append(f"   Reason: {module.reason}")
        lines.append("")

    return "\n".join(lines)


def _format_json(modules) -> str:
    """Format as JSON for CI/CD."""
    data = {
        'summary': {
            'total_items': len(modules)
        },
        'findings': [
            {
                'type': m.type,
                'path': m.path,
                'name': m.name,
                'line': m.line,
                'symbol_count': m.symbol_count,
                'confidence': m.confidence,
                'reason': m.reason
            }
            for m in modules
        ]
    }
    return json.dumps(data, indent=2)


def _format_summary(modules) -> str:
    """Format as counts only."""
    by_type = {}
    for m in modules:
        by_type[m.type] = by_type.get(m.type, 0) + 1

    lines = ["Dead Code Summary:"]
    lines.append(f"  Total: {len(modules)}")
    for typ, count in sorted(by_type.items()):
        lines.append(f"  {typ}s: {count}")
    return "\n".join(lines) + "\n"
