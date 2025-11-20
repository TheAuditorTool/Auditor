"""Display frameworks detected during indexing and generate AI-consumable output.

This command reads from the frameworks table populated by 'aud index'.
It does NOT re-parse manifests - database is the single source of truth.
"""


import json
import sqlite3
import click
from pathlib import Path
from typing import List, Dict


@click.command("detect-frameworks")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option("--output-json", help="Path to output JSON file (default: .pf/raw/frameworks.json)")
def detect_frameworks(project_path, output_json):
    """Display detected frameworks from indexed codebase in AI-consumable format.

    Reads framework metadata from the database (populated during 'aud index') and outputs
    structured JSON for AI assistant consumption. This command is database-only - it does
    NOT re-parse manifests or analyze source code. The database is the single source of truth.

    AI ASSISTANT CONTEXT:
      Purpose: Exposes detected frameworks/libraries for architecture understanding
      Input: .pf/repo_index.db (frameworks table)
      Output: .pf/raw/frameworks.json (structured framework list)
      Prerequisites: aud index (must run first to populate database)
      Integration: Used by blueprint and structure commands for architecture visualization
      Performance: ~1 second (database query only, no file I/O)

    WHAT IT DETECTS:
      - Python frameworks: Flask, Django, FastAPI, SQLAlchemy, Celery, pytest
      - JavaScript frameworks: React, Vue, Angular, Express, Nest.js, Next.js
      - Database frameworks: PostgreSQL, MySQL, MongoDB, Redis clients
      - Testing frameworks: Jest, Mocha, pytest, unittest
      - Build tools: Webpack, Vite, Rollup, esbuild
      - Cloud SDKs: AWS SDK, Google Cloud, Azure SDK

    SUPPORTED DETECTION METHODS:
      - Package manifests (package.json, requirements.txt, pyproject.toml)
      - Import statements (Python: from flask import, JS: import express from)
      - Decorator patterns (@app.route, @pytest.fixture)
      - Configuration files (pytest.ini, jest.config.js, webpack.config.js)

    HOW IT WORKS:
      1. Connects to .pf/repo_index.db (fails if not exists)
      2. Queries frameworks table (populated by 'aud index' extractors)
      3. Retrieves: framework name, version, language, source file, detection method
      4. Outputs JSON to .pf/raw/frameworks.json (AI-consumable format)
      5. Displays human-readable ASCII table to stdout

    EXAMPLES:
      # Use Case 1: Basic framework detection after indexing
      aud index && aud detect-frameworks

      # Use Case 2: Custom output path for CI/CD integration
      aud detect-frameworks --output-json ./build/frameworks.json

      # Use Case 3: Detect frameworks in specific project directory
      aud detect-frameworks --project-path ./services/api

      # Use Case 4: Pipeline workflow (index → detect → analyze)
      aud index && aud detect-frameworks && aud blueprint --format json

    COMMON WORKFLOWS:
      Architecture Documentation:
        aud index && aud detect-frameworks && aud structure

      Security Audit (framework-specific CVEs):
        aud detect-frameworks && aud deps --vuln-scan

      Tech Stack Analysis (for new team members):
        aud detect-frameworks > tech_stack.txt

    OUTPUT FILES:
      .pf/raw/frameworks.json          # AI-consumable structured output
      .pf/repo_index.db (tables read):
        - frameworks: framework metadata with detection provenance

    OUTPUT FORMAT (JSON Schema):
      [
        {
          "framework": "Flask",
          "version": "2.3.0",
          "language": "python",
          "path": "requirements.txt",
          "source": "manifest",
          "is_primary": true
        },
        {
          "framework": "React",
          "version": "18.2.0",
          "language": "javascript",
          "path": "package.json",
          "source": "manifest",
          "is_primary": true
        }
      ]

    PERFORMANCE EXPECTATIONS:
      Small (<5K LOC):     ~0.5 seconds,  ~50MB RAM
      Medium (20K LOC):    ~1 second,     ~100MB RAM
      Large (100K+ LOC):   ~2 seconds,    ~150MB RAM
      Note: Performance is database-query only (no file parsing)

    PREREQUISITES:
      Required:
        aud index              # Must run first to populate frameworks table

      Optional:
        None (standalone query command)

    EXIT CODES:
      0 = Success, frameworks detected or no frameworks found
      1 = Database not found (run 'aud index' first)
      3 = Database query failed (check .pf/pipeline.log)

    RELATED COMMANDS:
      aud index              # Populates frameworks table (run first)
      aud structure          # Uses framework data for architecture map
      aud blueprint          # Visual architecture including frameworks
      aud deps               # Analyzes framework dependencies for CVEs

    SEE ALSO:
      aud explain workset    # Understand how to filter framework detection

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud index' first to create .pf/repo_index.db

      No frameworks detected despite having package.json:
        → Check 'aud index' output for errors
        → Verify package.json is valid JSON
        → Check .pf/pipeline.log for extractor failures

      Wrong framework versions detected:
        → Re-run 'aud index' to refresh database
        → Framework versions come from manifest files (package.json, requirements.txt)

    NOTE: This is a read-only database query. It does not modify files or re-parse
    manifests. To refresh framework detection, run 'aud index' again.
    """
    # SANDBOX DELEGATION: Check if running in sandbox
    from theauditor.sandbox_executor import is_in_sandbox, execute_in_sandbox

    if not is_in_sandbox():
        # Not in sandbox - delegate to sandbox Python
        import sys
        exit_code = execute_in_sandbox("detect-frameworks", sys.argv[2:], root=project_path)
        sys.exit(exit_code)

    project_path = Path(project_path).resolve()
    db_path = project_path / ".pf" / "repo_index.db"

    if not db_path.exists():
        click.echo("Error: Database not found. Run 'aud full' first.", err=True)
        raise click.ClickException("Database not found - run 'aud full' first")

    try:
        # Read from database (single source of truth)
        frameworks = _read_frameworks_from_db(db_path)

        if not frameworks:
            click.echo("No frameworks detected.")
            # Still write empty output for pipeline consistency
            _write_output(frameworks, project_path, output_json)
            return

        # Generate AI-consumable output (/raw is for external consumption)
        _write_output(frameworks, project_path, output_json)

        # Display human-readable table
        table = _format_table(frameworks)
        click.echo(table)

        click.echo(f"\nDetected {len(frameworks)} framework(s)")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e


def _read_frameworks_from_db(db_path: Path) -> list[dict]:
    """Read frameworks from database (internal data source).

    Args:
        db_path: Path to repo_index.db

    Returns:
        List of framework dictionaries
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, version, language, path, source, is_primary
        FROM frameworks
        ORDER BY is_primary DESC, language, name
    """)

    frameworks = []
    for name, version, language, path, source, is_primary in cursor.fetchall():
        frameworks.append({
            "framework": name,
            "version": version or "unknown",
            "language": language or "unknown",
            "path": path or ".",
            "source": source or "manifest",
            "is_primary": bool(is_primary)
        })

    conn.close()
    return frameworks


def _write_output(frameworks: list[dict], project_path: Path, output_json: str):
    """Write AI-consumable output to consolidated dependency_analysis.

    Args:
        frameworks: List of framework dictionaries
        project_path: Project root path
        output_json: Optional custom output path (for backward compatibility)
    """
    # Write frameworks results to JSON
    output_path = Path(output_json) if output_json else (project_path / ".pf" / "raw" / "frameworks.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(frameworks, f, indent=2)
    click.echo(f"[OK] Frameworks analysis saved to {output_path}")


def _format_table(frameworks: list[dict]) -> str:
    """Format frameworks as human-readable ASCII table.

    Args:
        frameworks: List of framework dictionaries

    Returns:
        Formatted ASCII table string
    """
    if not frameworks:
        return "No frameworks detected."

    headers = ["Framework", "Version", "Language", "Path", "Source"]
    widths = [len(h) for h in headers]

    # Calculate column widths
    for fw in frameworks:
        widths[0] = max(widths[0], len(fw.get("framework", "")))
        widths[1] = max(widths[1], len(fw.get("version", "")))
        widths[2] = max(widths[2], len(fw.get("language", "")))
        widths[3] = max(widths[3], len(fw.get("path", "")))
        widths[4] = max(widths[4], len(fw.get("source", "")))

    # Build table
    separator = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header_row = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, widths)) + "|"

    lines = [separator, header_row, separator]

    for fw in frameworks:
        row = "|" + "|".join(
            f" {fw.get(k, ''):<{w}} "
            for k, w in zip(["framework", "version", "language", "path", "source"], widths)
        ) + "|"
        lines.append(row)

    lines.append(separator)
    return "\n".join(lines)
