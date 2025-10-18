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
    """Display frameworks and generate AI-consumable output.

    Reads from frameworks table (populated by 'aud index').
    Generates .pf/raw/frameworks.json for AI consumption.

    If database doesn't exist, run 'aud index' first.
    """
    project_path = Path(project_path).resolve()
    db_path = project_path / ".pf" / "repo_index.db"

    if not db_path.exists():
        click.echo("Error: Database not found. Run 'aud index' first.", err=True)
        raise click.ClickException("Database not found - run 'aud index' first")

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


def _read_frameworks_from_db(db_path: Path) -> List[Dict]:
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


def _write_output(frameworks: List[Dict], project_path: Path, output_json: str):
    """Write AI-consumable output to /raw directory.

    Args:
        frameworks: List of framework dictionaries
        project_path: Project root path
        output_json: Optional custom output path
    """
    if output_json:
        save_path = Path(output_json)
    else:
        save_path = project_path / ".pf" / "raw" / "frameworks.json"

    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(frameworks, f, indent=2)

    click.echo(f"Output written to {save_path}")


def _format_table(frameworks: List[Dict]) -> str:
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
