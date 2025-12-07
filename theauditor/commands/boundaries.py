"""Analyze security boundary enforcement across entry points."""

import json
import sys
from pathlib import Path

import click

from theauditor.boundaries.boundary_analyzer import (
    analyze_input_validation_boundaries,
    generate_report,
)
from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions


@click.command("boundaries", cls=RichCommand)
@handle_exceptions
@click.option("--db", default=None, help="Path to repo_index.db (default: .pf/repo_index.db)")
@click.option(
    "--type",
    "boundary_type",
    type=click.Choice(["all", "input-validation", "multi-tenant", "authorization", "sanitization"]),
    default="all",
    help="Boundary type to analyze",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["report", "json"]),
    default="report",
    help="Output format (report=human-readable, json=machine-parseable)",
)
@click.option(
    "--max-entries",
    default=100,
    type=int,
    help="Maximum entry points to analyze (performance limit)",
)
@click.option(
    "--severity",
    type=click.Choice(["all", "critical", "high", "medium", "low"]),
    default="all",
    help="Filter findings by severity",
)
def boundaries(db, boundary_type, output_format, max_entries, severity):
    """Analyze security boundary enforcement and measure distance from entry to control points.

    Detects where security controls (validation, authentication, sanitization) are enforced
    relative to entry points. Reports factual distance measurements - NOT recommendations.

    CRITICAL CONCEPTS:
      Boundary: Point where trust level changes (external->internal, untrusted->validated)
      Distance: Number of function calls between entry point and control point
      Entry Point: HTTP route, CLI command, message handler (external data ingress)
      Control Point: Validation, authentication, sanitization (security enforcement)

    DISTANCE SEMANTICS:
      Distance 0: Control at entry (validation in function signature)
      Distance 1-2: Control nearby (acceptable for most boundaries)
      Distance 3+: Control far from entry (data spreads before enforcement)
      Distance None: No control found (missing boundary enforcement)

    AI ASSISTANT CONTEXT:
      Purpose: Measure boundary enforcement quality via call-chain distance analysis
      Input: .pf/repo_index.db (symbols, call_graph, routes, validators)
      Output: Boundary analysis report with distance measurements (facts only, NO recommendations)
      Prerequisites: aud full (populates call graph for distance calculation)
      Integration: Security audit pipeline, complements taint analysis
      Runtime: ~5-30s depending on entry point count and call graph size

    EXIT CODES:
      0 = Success, no critical boundary violations detected
      1 = Critical boundary violations found (missing controls at entry points)

    RELATED COMMANDS:
      aud taint      # Track data flow from sources to sinks
      aud blueprint --boundaries  # Show boundary architecture overview
      aud full               # Complete analysis including boundaries

    SEE ALSO:
      aud manual boundaries  # Deep dive into boundary analysis concepts
      aud manual taint       # Understand taint tracking relationship

    TROUBLESHOOTING:
      Error: "Database not found":
        -> Run 'aud full' first to populate repo_index.db
        -> Check .pf/repo_index.db exists

      No entry points found:
        -> Ensure routes/endpoints are indexed (Python/JS routes)
        -> Run 'aud full' with appropriate language support

      Analysis is slow (>60s):
        -> Reduce --max-entries to limit entry point count
        -> Large call graphs increase traversal time
    """

    db = Path.cwd() / ".pf" / "repo_index.db" if db is None else Path(db)

    if not db.exists():
        err_console.print(f"[error]Error: Database not found at {db}[/error]", highlight=False)
        err_console.print(
            "[error]Run 'aud full' first to populate the database[/error]",
        )
        sys.exit(1)

    results = []

    if boundary_type in ["all", "input-validation"]:
        err_console.print(
            "[error]Analyzing input validation boundaries...[/error]",
        )
        validation_results = analyze_input_validation_boundaries(
            db_path=str(db), max_entries=max_entries
        )
        results.extend(validation_results)

    if boundary_type == "multi-tenant":
        err_console.print(
            "[error]Error: Multi-tenant boundary analysis not yet wired to this command[/error]",
        )
        err_console.print(
            "[error]Use: aud full (includes multi-tenant analysis via rules)[/error]",
        )
        sys.exit(1)

    if severity != "all":
        results = [
            r
            for r in results
            if any(v["severity"].lower() == severity for v in r.get("violations", []))
        ]

    if output_format == "json":
        output = {
            "boundary_type": boundary_type,
            "total_entry_points": len(results),
            "analysis": results,
        }
        console.print(json.dumps(output, indent=2), markup=False)
    else:
        report = generate_report(results)
        console.print(report, markup=False)

    critical_count = sum(
        1 for r in results for v in r.get("violations", []) if v["severity"] == "CRITICAL"
    )

    if critical_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
