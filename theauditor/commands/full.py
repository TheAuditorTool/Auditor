"""Run complete audit pipeline.

2025 Modern: Uses asyncio for parallel execution.
"""

import asyncio
import sys

import click
from rich.panel import Panel
from rich.text import Text

from theauditor.pipeline.ui import console, print_status_panel
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


def print_audit_complete_panel(
    total_phases: int,
    failed_phases: int,
    phases_with_warnings: int,
    elapsed_time: float,
    index_only: bool = False,
) -> None:
    """Print the AUDIT COMPLETE panel with styled border."""
    minutes = elapsed_time / 60

    if index_only:
        if failed_phases == 0:
            title = "INDEX COMPLETE"
            status_line = f"All {total_phases} phases successful"
            detail = f"Total time: {elapsed_time:.1f}s ({minutes:.1f} minutes)"
            border_style = "green"
        else:
            title = "INDEX INCOMPLETE"
            status_line = f"{failed_phases} phases failed"
            detail = f"Total time: {elapsed_time:.1f}s ({minutes:.1f} minutes)"
            border_style = "yellow"
    elif failed_phases == 0 and phases_with_warnings == 0:
        title = "AUDIT COMPLETE"
        status_line = f"All {total_phases} phases successful"
        detail = f"Total time: {elapsed_time:.1f}s ({minutes:.1f} minutes)"
        border_style = "green"
    elif phases_with_warnings > 0 and failed_phases == 0:
        title = "AUDIT COMPLETE"
        status_line = f"{phases_with_warnings} phases completed with warnings"
        detail = f"Total time: {elapsed_time:.1f}s ({minutes:.1f} minutes)"
        border_style = "yellow"
    else:
        title = "AUDIT COMPLETE"
        status_line = f"{failed_phases} phases failed, {phases_with_warnings} with warnings"
        detail = f"Total time: {elapsed_time:.1f}s ({minutes:.1f} minutes)"
        border_style = "yellow"

    panel = Panel(
        Text.assemble(
            (status_line + "\n", "bold " + border_style),
            (detail, "dim"),
        ),
        title=f"[bold]{title}[/bold]",
        border_style=border_style,
        expand=False,
    )
    console.print(panel)


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option(
    "--exclude-self",
    is_flag=True,
    hidden=True,
    help="Exclude TheAuditor's own files (for self-testing)",
)
@click.option("--offline", is_flag=True, help="Skip network operations (deps, docs)")
@click.option(
    "--subprocess-taint",
    is_flag=True,
    hidden=True,
    help="Run taint analysis as subprocess (slower but isolated)",
)
@click.option(
    "--wipecache", is_flag=True, help="Delete all caches before run (for cache corruption recovery)"
)
@click.option(
    "--index",
    "index_only",
    is_flag=True,
    help="Run indexing only (Stage 1 + 2) - skip heavy analysis",
)
def full(root, quiet, exclude_self, offline, subprocess_taint, wipecache, index_only):
    """Run comprehensive security audit pipeline (20 phases).

    Executes TheAuditor's complete analysis pipeline in 4 optimized stages
    with intelligent parallelization. This is your main command for full
    codebase auditing.

    Pipeline Stages:
      Stage 1: Foundation (Sequential)
        - Index repository (build symbol database)
        - Detect frameworks (Django, Flask, React, etc.)

      Stage 2: Data Preparation (Sequential)
        - Create workset (identify analysis targets)
        - Build dependency graph
        - Extract control flow graphs

      Stage 3: Heavy Analysis (3 Parallel Tracks)
        Track A: Taint analysis (isolated for performance)
        Track B: Static analysis & offline security (lint, patterns, graph, vuln-scan)
        Track C: Network I/O (version checks, docs) - skipped if --offline

      Stage 4: Aggregation (Sequential)
        - Factual Correlation Engine (cross-reference findings)
        - Generate final report

    Examples:
      aud full                    # Complete audit with network operations
      aud full --index            # Fast reindex (Stage 1+2 only, ~1-3 min)
      aud full --offline          # Air-gapped analysis (no npm/pip checks)
      aud full --exclude-self     # Skip TheAuditor's own files
      aud full --quiet            # Minimal output for CI/CD pipelines
      aud full --wipecache        # Force cache rebuild (for corruption recovery)

    Output Files:
      .pf/raw/*.json              # All analysis artifacts (patterns, lint, terraform, etc.)
      .pf/pipeline.log            # Detailed execution trace
      .pf/fce.log                 # Factual Correlation Engine output

    Exit Codes:
      0 = No issues found
      1 = High severity findings
      2 = Critical vulnerabilities
      3 = Pipeline failed

    Performance (with current tree-sitter architecture):
      Small project (<5K LOC):     ~2-3 minutes
      Medium project (20K LOC):    ~5-10 minutes
      Large monorepo (100K+ LOC):  ~15-20 minutes

      If pipeline takes >30 minutes, something is likely broken.
      Check .pf/pipeline.log for the stuck phase.

    Cache Behavior:
      By default, caches are PRESERVED between runs for speed:
        - AST parsing cache (.pf/.cache/)
        - Documentation cache (.pf/context/docs/)

      Use --wipecache to force a complete cache rebuild.
      This is useful for recovering from cache corruption.

    FLAG INTERACTIONS:
      --index: Run Stage 1 (index, detect-frameworks) + Stage 2 (workset, graphs, cfg, metadata)
               Skips Stage 3 (taint, patterns, lint) and Stage 4 (fce, report)
               Use when you just need to reindex after code changes (~1-3 min vs 30-60 min)
      --offline + --subprocess-taint: Air-gapped taint analysis
      --wipecache: Overrides all caching (slowest, cleanest run)
      --quiet + --offline: Minimal output for CI/CD (fastest)
      --exclude-self: Must be used when testing TheAuditor on itself

    TROUBLESHOOTING:
      Pipeline hangs during taint phase:
        Solution: Use --subprocess-taint to isolate taint analysis

      Cache corruption errors:
        Solution: Run with --wipecache to rebuild all caches

      Network timeouts in CI:
        Solution: Use --offline to skip version checks and docs

      Memory errors on large codebase:
        Solution: Run individual phases separately, not full pipeline

      Exit code 3 (pipeline failed):
        Cause: One or more phases failed to complete
        Solution: Check .pf/pipeline.log for specific phase errors

    Note: Uses intelligent caching - second run is 5-10x faster"""
    from theauditor.pipelines import run_full_pipeline

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        result = asyncio.run(
            run_full_pipeline(
                root=root,
                quiet=quiet,
                exclude_self=exclude_self,
                offline=offline,
                use_subprocess_for_taint=subprocess_taint,
                wipe_cache=wipecache,
                index_only=index_only,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[bold red][INFO] Pipeline stopped by user.[/bold red]")
        sys.exit(130)

    findings = result.get("findings", {})
    critical = findings.get("critical", 0)
    high = findings.get("high", 0)
    medium = findings.get("medium", 0)
    low = findings.get("low", 0)
    is_index_only = result.get("index_only", False)

    # === AUDIT COMPLETE Panel (fancy box) ===
    console.print()
    print_audit_complete_panel(
        total_phases=result["total_phases"],
        failed_phases=result["failed_phases"],
        phases_with_warnings=result["phases_with_warnings"],
        elapsed_time=result["elapsed_time"],
        index_only=is_index_only,
    )

    # === Files Created Stats ===
    created_files = result.get("created_files", [])
    pf_files = [f for f in created_files if f.startswith(".pf/")]
    raw_files = [f for f in created_files if f.startswith(".pf/raw/")]

    console.print()
    console.print(
        f"[bold]Files Created[/bold]  "
        f"[dim]Total:[/dim] [bold cyan]{len(created_files)}[/bold cyan]  "
        f"[dim].pf/:[/dim] [cyan]{len(pf_files)}[/cyan]  "
        f"[dim].pf/raw/:[/dim] [cyan]{len(raw_files)}[/cyan]"
    )

    # === Key Artifacts ===
    console.print()
    console.print("[bold]Key Artifacts[/bold]")
    if is_index_only:
        console.print("  [cyan].pf/repo_index.db[/cyan]     [dim]Symbol database (queryable)[/dim]")
        console.print("  [cyan].pf/graphs.db[/cyan]         [dim]Call/data flow graphs[/dim]")
        console.print("  [cyan].pf/pipeline.log[/cyan]      [dim]Execution log[/dim]")
        console.print()
        console.print("[dim]Database ready. Run 'aud full' for complete analysis (taint, patterns, fce)[/dim]")
    else:
        console.print("  [cyan].pf/repo_index.db[/cyan]     [dim]Symbol database (queryable)[/dim]")
        console.print("  [cyan].pf/graphs.db[/cyan]         [dim]Call/data flow graphs[/dim]")
        console.print("  [cyan].pf/raw/[/cyan]              [dim]All analysis artifacts[/dim]")
        console.print("  [cyan].pf/allfiles.md[/cyan]       [dim]Complete file list[/dim]")
        console.print("  [cyan].pf/pipeline.log[/cyan]      [dim]Full execution log[/dim]")
        console.print("  [cyan].pf/fce.log[/cyan]           [dim]FCE detailed output[/dim]")

    # === AUDIT FINAL STATUS Section ===
    console.print()
    console.rule("[bold]AUDIT FINAL STATUS[/bold]")
    console.print()

    exit_code = ExitCodes.SUCCESS
    failed_phase_names = result.get("failed_phase_names", [])

    if result["failed_phases"] > 0:
        # Build a concise description of what failed
        if failed_phase_names:
            # Extract just the phase description (strip "N. " prefix)
            phase_descs = []
            for name in failed_phase_names[:3]:  # Max 3 to keep it brief
                desc = name.split(". ", 1)[-1] if ". " in name else name
                phase_descs.append(desc)
            failed_summary = ", ".join(phase_descs)
            if len(failed_phase_names) > 3:
                failed_summary += f" (+{len(failed_phase_names) - 3} more)"
        else:
            failed_summary = f"{result['failed_phases']} phase(s)"

        exit_code = ExitCodes.TASK_INCOMPLETE
        print_status_panel(
            "PIPELINE FAILED",
            f"Crashed during: {failed_summary}",
            "Check errors above. Fix and re-run. Results are partial.",
            level="critical",
        )
    elif critical > 0:
        print_status_panel(
            "CRITICAL",
            f"Audit complete. Found {critical} critical vulnerabilities.",
            "Immediate action required - deployment should be blocked.",
            level="critical",
        )
        exit_code = ExitCodes.CRITICAL_SEVERITY
    elif high > 0:
        print_status_panel(
            "HIGH",
            f"Audit complete. Found {high} high-severity issues.",
            "Priority remediation needed before next release.",
            level="high",
        )
        if exit_code == ExitCodes.SUCCESS:
            exit_code = ExitCodes.HIGH_SEVERITY
    elif medium > 0 or low > 0:
        print_status_panel(
            "MODERATE",
            f"Audit complete. Found {medium} medium and {low} low issues.",
            "Schedule fixes for upcoming sprints.",
            level="medium",
        )
    else:
        print_status_panel(
            "CLEAN",
            "No critical or high-severity issues found.",
            "Codebase meets security and quality standards.",
            level="success",
        )

    if critical + high + medium + low > 0:
        console.print("\n[bold]Findings breakdown:[/bold]")
        if critical > 0:
            console.print(f"  - [critical]Critical: {critical}[/critical]")
        if high > 0:
            console.print(f"  - [high]High:     {high}[/high]")
        if medium > 0:
            console.print(f"  - [medium]Medium:   {medium}[/medium]")
        if low > 0:
            console.print(f"  - [low]Low:      {low}[/low]")

    console.print("\nReview the findings in [path].pf/raw/[/path]")
    console.rule()

    if exit_code != ExitCodes.SUCCESS:
        sys.exit(exit_code)
