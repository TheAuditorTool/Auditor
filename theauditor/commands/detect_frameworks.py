"""Display frameworks detected during indexing and generate AI-consumable output.

This command reads from the frameworks table populated by 'aud full'.
It does NOT re-parse manifests - database is the single source of truth.
"""

import json
import sqlite3
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console


@click.command("detect-frameworks", cls=RichCommand)
@click.option("--project-path", default=".", help="Root directory to analyze")
def detect_frameworks(project_path):
    """Display detected frameworks from indexed codebase in AI-consumable format.

    Reads framework metadata from the database (populated during 'aud full') and outputs
    structured JSON for AI assistant consumption. This command is database-only - it does
    NOT re-parse manifests or analyze source code. The database is the single source of truth.

    AI ASSISTANT CONTEXT:
      Purpose: Exposes detected frameworks/libraries for architecture understanding
      Input: .pf/repo_index.db (frameworks table)
      Output: Console (table) or JSON (--json flag)
      Prerequisites: aud full (must run first to populate database)
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
      2. Queries frameworks table (populated by 'aud full' extractors)
      3. Retrieves: framework name, version, language, source file, detection method
      4. Outputs human-readable ASCII table to stdout (or JSON with --json flag)

    EXAMPLES:
      # Use Case 1: Basic framework detection after indexing
      aud full && aud detect-frameworks

      # Use Case 2: JSON output for CI/CD integration
      aud detect-frameworks --json > ./build/frameworks.json

      # Use Case 3: Detect frameworks in specific project directory
      aud detect-frameworks --project-path ./services/api

      # Use Case 4: Pipeline workflow (index → detect → analyze)
      aud full && aud detect-frameworks && aud blueprint --format json

    COMMON WORKFLOWS:
      Architecture Documentation:
        aud full && aud detect-frameworks && aud blueprint

      Security Audit (framework-specific CVEs):
        aud detect-frameworks && aud deps --vuln-scan

      Tech Stack Analysis (for new team members):
        aud detect-frameworks > tech_stack.txt

    OUTPUT:
      Console: Human-readable table
      --json: Structured JSON to stdout (pipe to file if needed)
      Data source: .pf/repo_index.db (frameworks table)

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
        aud full               # Must run first to populate frameworks table

      Optional:
        None (standalone query command)

    EXIT CODES:
      0 = Success, frameworks detected or no frameworks found
      1 = Database not found (run 'aud full' first)
      3 = Database query failed (check .pf/pipeline.log)

    RELATED COMMANDS:
      aud full               # Populates frameworks table (run first)
      aud blueprint          # Visual architecture including frameworks
      aud deps               # Analyzes framework dependencies for CVEs

    SEE ALSO:
      aud manual frameworks  # Deep dive into framework detection concepts
      aud manual deps        # Understand dependency analysis

    TROUBLESHOOTING:
      Error: "Database not found"
        → Run 'aud full' first to create .pf/repo_index.db

      No frameworks detected despite having package.json:
        → Check 'aud full' output for errors
        → Verify package.json is valid JSON
        → Check .pf/pipeline.log for extractor failures

      Wrong framework versions detected:
        → Re-run 'aud full' to refresh database
        → Framework versions come from manifest files (package.json, requirements.txt)

    NOTE: This is a read-only database query. It does not modify files or re-parse
    manifests. To refresh framework detection, run 'aud full' again.
    """
    project_path = Path(project_path).resolve()
    db_path = project_path / ".pf" / "repo_index.db"

    if not db_path.exists():
        err_console.print(
            "[error]Error: Database not found. Run 'aud full' first.[/error]",
        )
        raise click.ClickException("Database not found - run 'aud full' first")

    try:
        frameworks = _read_frameworks_from_db(db_path)

        if not frameworks:
            console.print("No frameworks detected.")
            return

        table = _format_table(frameworks)
        console.print(table, markup=False)

        console.print(f"\nDetected {len(frameworks)} framework(s)", highlight=False)

    except Exception as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
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
        frameworks.append(
            {
                "framework": name,
                "version": version or "unknown",
                "language": language or "unknown",
                "path": path or ".",
                "source": source or "manifest",
                "is_primary": bool(is_primary),
            }
        )

    conn.close()
    return frameworks


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

    for fw in frameworks:
        widths[0] = max(widths[0], len(fw.get("framework", "")))
        widths[1] = max(widths[1], len(fw.get("version", "")))
        widths[2] = max(widths[2], len(fw.get("language", "")))
        widths[3] = max(widths[3], len(fw.get("path", "")))
        widths[4] = max(widths[4], len(fw.get("source", "")))

    separator = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header_row = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, widths, strict=True)) + "|"

    lines = [separator, header_row, separator]

    for fw in frameworks:
        row = (
            "|"
            + "|".join(
                f" {fw.get(k, ''):<{w}} "
                for k, w in zip(
                    ["framework", "version", "language", "path", "source"], widths, strict=True
                )
            )
            + "|"
        )
        lines.append(row)

    lines.append(separator)
    return "\n".join(lines)
