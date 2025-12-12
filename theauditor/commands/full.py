"""Run complete audit pipeline.

2025 Modern: Uses asyncio for parallel execution.
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

import click
from rich.panel import Panel
from rich.text import Text

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, print_status_panel
from theauditor.utils.constants import ExitCodes
from theauditor.utils.error_handler import handle_exceptions


def _get_indexer_errors(db_path: Path, limit: int = 5) -> list[tuple[str, str]]:
    """Fetch indexer errors from database.

    Returns list of (file, short_message) tuples.
    """
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file, message FROM findings_consolidated
            WHERE tool = 'indexer'
            ORDER BY severity DESC, file
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for file_path, message in rows:
            # Extract just the error type, not the full path
            short_msg = message
            if ":" in message:
                # "Parse Error: FATAL: Failed to parse C:\...: Python syntax error: invalid syntax"
                # -> "Python syntax error: invalid syntax"
                parts = message.split(":")
                if len(parts) >= 2:
                    short_msg = parts[-1].strip()
            results.append((file_path, short_msg))
        return results
    except Exception:
        return []


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


@click.command(cls=RichCommand)
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

    DESCRIPTION:
      Executes TheAuditor's complete analysis pipeline in 4 optimized stages
      with intelligent parallelization. This is your main command for full
      codebase auditing.

      Stage 1 - Foundation (Sequential):
        Index repository, detect frameworks (Django, Flask, React, etc.)

      Stage 2 - Data Preparation (Sequential):
        Create workset, build dependency graph, extract control flow graphs

      Stage 3 - Heavy Analysis (3 Parallel Tracks):
        Track A: Taint analysis (isolated for memory)
        Track B: Static analysis (lint, patterns, graph, vuln-scan)
        Track C: Network I/O (version checks, docs) - skipped with --offline

      Stage 4 - Aggregation (Sequential):
        Factual Correlation Engine, generate final report

    AI ASSISTANT CONTEXT:
      Purpose: Run complete security audit with 20 analysis phases
      Input: Source code directory (any language: Python, JS/TS, Go, Rust, Bash)
      Output: .pf/ directory with databases, findings, and reports
      Prerequisites: None (creates .pf/ directory if missing)
      Integration: Primary entry point - runs all other analysis tools
      Performance: 2-20 minutes depending on codebase size

    EXAMPLES:
      aud full                    # Complete audit with network operations
      aud full --index            # Fast reindex (Stage 1+2 only, ~1-3 min)
      aud full --offline          # Air-gapped analysis (no npm/pip checks)
      aud full --quiet            # Minimal output for CI/CD pipelines
      aud full --wipecache        # Force cache rebuild (corruption recovery)

    COMMON WORKFLOWS:
      First time setup:
        aud full                  # Creates .pf/ and runs complete audit

      After code changes:
        aud full --index          # Fast reindex, then run specific analysis

      CI/CD pipeline:
        aud full --quiet --offline  # Minimal output, no network

      Cache problems:
        aud full --wipecache      # Delete all caches, fresh start

    OUTPUT FILES:
      .pf/repo_index.db           Symbol database (queryable with aud query)
      .pf/graphs.db               Call and data flow graphs
      .pf/pipeline.log            Detailed execution trace
      .pf/fce.log                 Factual Correlation Engine output

    PERFORMANCE:
      Small project (<5K LOC):     ~2-3 minutes
      Medium project (20K LOC):    ~5-10 minutes
      Large monorepo (100K+ LOC):  ~15-20 minutes
      Second run (cached):         5-10x faster

    EXIT CODES:
      0 = Success, no critical or high severity issues
      1 = High severity findings detected
      2 = Critical vulnerabilities found
      3 = Pipeline failed (check .pf/pipeline.log)

    RELATED COMMANDS:
      aud taint           Run taint analysis separately
      aud detect-patterns         Run pattern detection separately
      aud workset                 Create focused file subset for analysis
      aud fce                     Run correlation engine separately

    SEE ALSO:
      aud manual pipeline         Learn about the 4-stage pipeline architecture
      aud manual severity         Understand severity classifications

    TROUBLESHOOTING:
      Pipeline hangs during taint phase:
        -> Use --subprocess-taint to isolate taint analysis

      Cache corruption errors:
        -> Run with --wipecache to rebuild all caches

      Network timeouts in CI:
        -> Use --offline to skip version checks and docs

      Memory errors on large codebase:
        -> Run individual phases separately, not full pipeline

      Exit code 3 (pipeline failed):
        -> Check .pf/pipeline.log for specific phase errors

    NOTE:
      Uses intelligent caching - second run is 5-10x faster.
      By default, caches (.pf/.cache/, .pf/context/docs/) are preserved.
      Use --wipecache to force complete rebuild if you suspect corruption."""
    from theauditor.pipeline import run_full_pipeline

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

    console.print()
    print_audit_complete_panel(
        total_phases=result["total_phases"],
        failed_phases=result["failed_phases"],
        phases_with_warnings=result["phases_with_warnings"],
        elapsed_time=result["elapsed_time"],
        index_only=is_index_only,
    )

    created_files = result.get("created_files", [])
    pf_files = [f for f in created_files if f.startswith(".pf/")]

    console.print()
    console.print(
        f"[bold]Files Created[/bold]  "
        f"[dim]Total:[/dim] [bold cyan]{len(created_files)}[/bold cyan]  "
        f"[dim].pf/:[/dim] [cyan]{len(pf_files)}[/cyan]"
    )

    console.print()
    console.print("[bold]Key Artifacts[/bold]")
    if is_index_only:
        console.print("  [cyan].pf/repo_index.db[/cyan]     [dim]Symbol database (queryable)[/dim]")
        console.print("  [cyan].pf/graphs.db[/cyan]         [dim]Call/data flow graphs[/dim]")
        console.print("  [cyan].pf/pipeline.log[/cyan]      [dim]Execution log[/dim]")
        console.print()
        console.print(
            "[dim]Database ready. Run 'aud full' for complete analysis (taint, patterns, fce)[/dim]"
        )
    else:
        console.print("  [cyan].pf/repo_index.db[/cyan]     [dim]Symbol database (queryable)[/dim]")
        console.print("  [cyan].pf/graphs.db[/cyan]         [dim]Call/data flow graphs[/dim]")
        console.print("  [cyan].pf/allfiles.md[/cyan]       [dim]Complete file list[/dim]")
        console.print("  [cyan].pf/pipeline.log[/cyan]      [dim]Full execution log[/dim]")
        console.print("  [cyan].pf/fce.log[/cyan]           [dim]FCE detailed output[/dim]")

    console.print()

    exit_code = ExitCodes.SUCCESS
    failed_phase_names = result.get("failed_phase_names", [])

    if is_index_only:
        # INDEX-ONLY mode: Show index status, NOT security audit status
        console.rule("[bold]INDEX STATUS[/bold]")
        console.print()

        if result["failed_phases"] > 0:
            if failed_phase_names:
                phase_descs = []
                for name in failed_phase_names[:3]:
                    desc = name.split(". ", 1)[-1] if ". " in name else name
                    phase_descs.append(desc)
                failed_summary = ", ".join(phase_descs)
                if len(failed_phase_names) > 3:
                    failed_summary += f" (+{len(failed_phase_names) - 3} more)"
            else:
                failed_summary = f"{result['failed_phases']} phase(s)"

            exit_code = ExitCodes.TASK_INCOMPLETE
            print_status_panel(
                "INDEX INCOMPLETE",
                f"Indexing failed during: {failed_summary}",
                "Check errors above. Database may be partial.",
                level="critical",
            )
        else:
            print_status_panel(
                "INDEX COMPLETE",
                "Database ready. No security analysis was performed.",
                "Run 'aud full' for complete security audit.",
                level="info",
            )

        console.print("\nQuery the database with [cmd]aud context query[/cmd]")
        console.rule()
    else:
        # Full audit mode: Show security findings status
        console.rule("[bold]AUDIT FINAL STATUS[/bold]")
        console.print()

        if result["failed_phases"] > 0:
            if failed_phase_names:
                phase_descs = []
                for name in failed_phase_names[:3]:
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

        # Show breakdown by source/tool
        by_tool = findings.get("by_tool", {})

        # Separate security tools from quality tools
        SECURITY_TOOLS = {
            "taint", "patterns", "terraform", "cdk",
            "github-actions-rules", "vulnerability_scanner", "indexer"
        }

        # Human-friendly tool names
        tool_labels = {
            # Security tools (affect exit code)
            "taint": "Taint Analysis",
            "patterns": "Pattern Detection",
            "terraform": "Terraform Security",
            "cdk": "AWS CDK Security",
            "github-actions-rules": "GitHub Actions",
            "vulnerability_scanner": "Dependency Vulns (OSV)",
            "indexer": "Indexer Errors",
            # Quality tools (visible but don't affect exit code)
            "ruff": "Ruff (Python)",
            "eslint": "ESLint (JS/TS)",
            "mypy": "Mypy (Types)",
            "cfg-analysis": "CFG Analysis",
            "graph-analysis": "Graph Analysis",
            "clippy": "Clippy (Rust)",
            "golangci-lint": "golangci-lint (Go)",
            "shellcheck": "ShellCheck (Bash)",
        }

        def format_tool_line(tool: str, counts: dict) -> str | None:
            """Format a single tool's findings. Returns None if no findings."""
            tool_total = sum(counts.values())
            if tool_total == 0:
                return None

            label = tool_labels.get(tool, tool.replace("-", " ").title())
            parts = []
            if counts.get("critical", 0) > 0:
                parts.append(f"[critical]{counts['critical']} crit[/critical]")
            if counts.get("high", 0) > 0:
                parts.append(f"[high]{counts['high']} high[/high]")
            if counts.get("medium", 0) > 0:
                parts.append(f"[medium]{counts['medium']} med[/medium]")
            if counts.get("low", 0) > 0:
                parts.append(f"[low]{counts['low']} low[/low]")

            severity_str = ", ".join(parts) if parts else "0"
            return f"  {label}: {severity_str}"

        # Split tools into security vs quality
        security_findings = {t: c for t, c in by_tool.items() if t in SECURITY_TOOLS and sum(c.values()) > 0}
        quality_findings = {t: c for t, c in by_tool.items() if t not in SECURITY_TOOLS and sum(c.values()) > 0}

        # Show security findings (these affect exit code)
        if critical + high + medium + low > 0:
            console.print("\n[bold]Security findings[/bold] [dim](affects exit code)[/dim]")
            if critical > 0:
                console.print(f"  [critical]Critical: {critical}[/critical]")
            if high > 0:
                console.print(f"  [high]High:     {high}[/high]")
            if medium > 0:
                console.print(f"  [medium]Medium:   {medium}[/medium]")
            if low > 0:
                console.print(f"  [low]Low:      {low}[/low]")

            if security_findings:
                console.print()
                # Sort security tools by total findings (highest first)
                for tool, counts in sorted(security_findings.items(), key=lambda x: sum(x[1].values()), reverse=True):
                    line = format_tool_line(tool, counts)
                    if line:
                        console.print(line)

            # Show indexer errors inline if present
            if "indexer" in security_findings:
                db_path = Path(root) / ".pf" / "repo_index.db"
                indexer_errors = _get_indexer_errors(db_path)
                if indexer_errors:
                    console.print()
                    console.print("  [dim]Indexer errors (files not analyzed):[/dim]")
                    for file_path, error_msg in indexer_errors:
                        console.print(f"    [red]{file_path}[/red]: {error_msg}")

        # Show quality findings separately (don't affect exit code)
        if quality_findings:
            # Calculate quality totals
            quality_totals = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for counts in quality_findings.values():
                for sev, cnt in counts.items():
                    if sev in quality_totals:
                        quality_totals[sev] += cnt
            quality_total = sum(quality_totals.values())

            console.print(f"\n[bold]Quality/lint findings[/bold] [dim]({quality_total} total, informational)[/dim]")
            # Sort quality tools by total findings (highest first)
            for tool, counts in sorted(quality_findings.items(), key=lambda x: sum(x[1].values()), reverse=True):
                line = format_tool_line(tool, counts)
                if line:
                    console.print(line)

        console.print("\nQuery findings: [cmd]aud query --findings[/cmd]")
        console.rule()

    if exit_code != ExitCodes.SUCCESS:
        sys.exit(exit_code)
