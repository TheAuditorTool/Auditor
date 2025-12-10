"""Run Factual Correlation Engine with vector-based convergence analysis.

Rich-formatted output following blueprint.py patterns.
"""

import click

from theauditor.cli import RichCommand
from theauditor.fce.formatter import FCEFormatter
from theauditor.fce.schema import ConvergencePoint, Fact, Vector
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions

VECTOR_LABELS = {
    Vector.STATIC: "STATIC",
    Vector.FLOW: "FLOW",
    Vector.PROCESS: "PROCESS",
    Vector.STRUCTURAL: "STRUCTURAL",
}


def _render_convergence_report(points: list[ConvergencePoint], detailed: bool = False) -> None:
    """Render convergence report using Rich.

    Args:
        points: List of ConvergencePoints sorted by density DESC
        detailed: If True, show facts for each file
    """
    if not points:
        console.print("\n[dim]No convergence points found.[/dim]")
        console.print("[dim]Tip: Try --min-vectors 1 to see single-vector files[/dim]")
        return

    console.print()
    console.rule("[bold cyan]FCE CONVERGENCE REPORT[/bold cyan]")
    console.print()

    max_density = max(p.signal.density for p in points)
    by_density: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for p in points:
        by_density[p.signal.vector_count] = by_density.get(p.signal.vector_count, 0) + 1

    console.print(f"[bold]Files with convergence:[/bold] [cyan]{len(points)}[/cyan]")
    console.print(
        f"[bold]Max vector density:[/bold] [cyan]{max_density:.0%}[/cyan] "
        f"({int(max_density * 4)}/4)"
    )
    console.print()

    console.print("[bold]Distribution:[/bold]")
    for count in [4, 3, 2, 1]:
        if by_density.get(count, 0) > 0:
            label = _get_density_style(count)
            console.print(f"  {count}/4 vectors: {label}{by_density[count]}[/] files")
    console.print()

    console.print("[dim]Legend: S=Static, F=Flow, P=Process, T=Structural[/dim]")
    console.rule()
    console.print()

    if detailed:
        _render_detailed_list(points[:20])
        if len(points) > 20:
            console.print(f"\n[dim]... and {len(points) - 20} more files[/dim]")
    else:
        _render_compact_list(points[:50])
        if len(points) > 50:
            console.print(f"\n[dim]... and {len(points) - 50} more files[/dim]")

    console.print()
    console.rule()


def _get_density_style(vector_count: int) -> str:
    """Get Rich style tag for density level."""
    return {4: "[bold red]", 3: "[yellow]", 2: "[cyan]"}.get(vector_count, "[dim]")


def _render_compact_list(points: list[ConvergencePoint]) -> None:
    """Render compact list of convergence points."""
    for i, point in enumerate(points, 1):
        vector_codes = FCEFormatter.get_vector_code_string(point.signal)
        density = point.signal.vector_count
        style = _get_density_style(density)

        console.print(
            f"  {i:3}. {style}[{density}/4][/] "
            f"[dim]\\[[/dim]{_colorize_vector_codes(vector_codes)}[dim]\\][/dim] "
            f"{point.file_path}",
            highlight=False,
        )


def _colorize_vector_codes(codes: str) -> str:
    """Colorize vector code string (S, F, P, T or -)."""
    result = []
    colors = {
        "S": "green",
        "F": "red",
        "P": "yellow",
        "T": "magenta",
    }
    for char in codes:
        if char in colors:
            result.append(f"[{colors[char]}]{char}[/{colors[char]}]")
        else:
            result.append("[dim]-[/dim]")
    return "".join(result)


def _render_detailed_list(points: list[ConvergencePoint]) -> None:
    """Render detailed list with facts for each file."""
    for i, point in enumerate(points, 1):
        vector_codes = FCEFormatter.get_vector_code_string(point.signal)
        density = point.signal.vector_count
        style = _get_density_style(density)

        console.print()
        console.print(
            f"[bold]{i}.[/bold] {style}[{density}/4][/] "
            f"[dim]\\[[/dim]{_colorize_vector_codes(vector_codes)}[dim]\\][/dim] "
            f"[bold]{point.file_path}[/bold]",
            highlight=False,
        )

        if point.line_start and point.line_end:
            if point.line_start == point.line_end:
                console.print(f"   [dim]Line:[/dim] {point.line_start}")
            else:
                console.print(f"   [dim]Lines:[/dim] {point.line_start}-{point.line_end}")

        facts_by_vector: dict[Vector, list[Fact]] = {}
        for fact in point.facts:
            if fact.vector not in facts_by_vector:
                facts_by_vector[fact.vector] = []
            facts_by_vector[fact.vector].append(fact)

        for vector in [Vector.STATIC, Vector.FLOW, Vector.PROCESS, Vector.STRUCTURAL]:
            if vector in facts_by_vector:
                vec_style = {
                    Vector.STATIC: "green",
                    Vector.FLOW: "red",
                    Vector.PROCESS: "yellow",
                    Vector.STRUCTURAL: "magenta",
                }[vector]

                console.print(f"   [{vec_style}]{VECTOR_LABELS[vector]}:[/{vec_style}]")

                for fact in facts_by_vector[vector][:5]:
                    line_info = f"L{fact.line}" if fact.line else ""
                    observation = fact.observation
                    if len(observation) > 60:
                        observation = observation[:57] + "..."

                    console.print(
                        f"     [dim]\\[[/dim]{fact.source}[dim]\\][/dim] "
                        f"[dim]{line_info}[/dim] {observation}",
                        highlight=False,
                    )

                remaining = len(facts_by_vector[vector]) - 5
                if remaining > 0:
                    console.print(f"     [dim]... and {remaining} more[/dim]")


def _render_summary(summary: dict) -> None:
    """Render FCE summary statistics."""
    console.print()
    console.print("[bold]FCE Summary[/bold]")
    console.rule(style="dim")

    console.print(f"Files analyzed: [cyan]{summary.get('files_analyzed', 0)}[/cyan]")
    console.print(f"Max vector density: [cyan]{summary.get('max_vector_density', 0):.0%}[/cyan]")
    console.print()

    console.print("[bold]Files by vector count:[/bold]")
    by_count = summary.get("files_by_vector_count", {})
    for count in [4, 3, 2, 1, 0]:
        file_count = by_count.get(count, 0)
        if file_count > 0:
            style = _get_density_style(count)
            console.print(f"  {count}/4: {style}{file_count}[/] files")


@click.command(name="fce", cls=RichCommand)
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--min-vectors",
    type=click.IntRange(1, 4),
    default=2,
    help="Minimum vectors for convergence (1-4, default 2)",
)
@click.option("--detailed", is_flag=True, help="Show facts in text output")
def fce(root, output_format, min_vectors, detailed):
    """Identify where multiple analysis vectors converge.

    The Factual Correlation Engine (FCE) identifies locations where multiple
    INDEPENDENT analysis vectors converge, without imposing subjective risk
    judgments.

    Philosophy: "I am not the judge, I am the evidence locker."

    The Four Vectors:
      S = STATIC     Linters (ruff, eslint, patterns, bandit)
      F = FLOW       Taint analysis (taint_flows, framework patterns)
      P = PROCESS    Change history (churn-analysis, code_diffs)
      T = STRUCTURAL Complexity (cfg-analysis)

    Signal Density:
      4/4 vectors = All dimensions flagging this location
      3/4 vectors = Strong convergence (3 independent signals)
      2/4 vectors = Moderate convergence (default threshold)
      1/4 vectors = Single dimension (use --min-vectors 1 to see)

    Why Vector Count Matters:
      Multiple linters screaming about the same syntax error = 1/4 vectors
      (They're all STATIC - not independent signals)

      Ruff + Taint + Churn + Complexity on same file = 4/4 vectors
      (Four INDEPENDENT dimensions converging)

    Examples:
      aud fce                        # Text report, min 2 vectors
      aud fce --min-vectors 3        # Only show 3+ vector convergence
      aud fce --format json          # JSON output
      aud fce --detailed             # Include facts in text output
      aud fce --format json > out.json  # Save JSON to file

    Output Legend:
      [3/4] [SF-T] src/auth/login.py
        |     |    |
        |     |    +-- File path
        |     +------- Vectors: S=Static, F=Flow, -=missing, T=Structural
        +------------- Density: 3 of 4 vectors present

    Input Sources:
      - findings_consolidated (all linter findings)
      - taint_flows (data flow vulnerabilities)
      - cfg-analysis findings (complexity)
      - churn-analysis findings (change volatility)

    Output:
      Text mode: Human-readable convergence report (Rich formatted)
      JSON mode: Machine-readable with full facts

    Prerequisites:
      Run 'aud full' first to populate analysis data.

    AI ASSISTANT CONTEXT:
      Purpose: Identify multi-vector convergence points (fact aggregation)
      Input: .pf/repo_index.db (findings_consolidated, taint_flows)
      Output: Console (text or json via --format)
      Key Insight: Vector count = signal, tool count = noise
      Philosophy: Report facts, let consumer decide severity

    RELATED COMMANDS:
      aud full            # Run complete pipeline to populate data
      aud taint           # Populates FLOW vector
      aud cfg analyze     # Populates STRUCTURAL vector
      aud detect-patterns # Populates STATIC vector"""
    from theauditor.fce.engine import get_fce_json, run_fce

    if output_format == "json":
        json_output = get_fce_json(root_path=root, min_vectors=min_vectors)
        console.print(json_output, markup=False, highlight=False)
        return

    result = run_fce(root_path=root, min_vectors=min_vectors)

    if result["success"]:
        points = result["convergence_points"]
        _render_convergence_report(points, detailed=detailed)
    else:
        err_console.print(
            f"[error]Error:[/error] {result['error']}",
        )
        raise click.ClickException(result["error"])
