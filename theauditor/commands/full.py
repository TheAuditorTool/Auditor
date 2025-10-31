"""Run complete audit pipeline."""

import sys
import click
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option("--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)")
@click.option("--offline", is_flag=True, help="Skip network operations (deps, docs)")
@click.option("--subprocess-taint", is_flag=True, help="Run taint analysis as subprocess (slower but isolated)")
@click.option("--wipecache", is_flag=True, help="Delete all caches before run (for cache corruption recovery)")
def full(root, quiet, exclude_self, offline, subprocess_taint, wipecache):
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
      aud full --offline          # Air-gapped analysis (no npm/pip checks)
      aud full --exclude-self     # Skip TheAuditor's own files
      aud full --quiet            # Minimal output for CI/CD pipelines
      aud full --wipecache        # Force cache rebuild (for corruption recovery)

    Output Files:
      .pf/readthis/*_chunk*.json  # Chunked findings for AI consumption
      .pf/readthis/summary.json   # Executive summary with severity counts
      .pf/raw/*.json              # Raw tool outputs (immutable)
      .pf/pipeline.log            # Detailed execution trace

    Exit Codes:
      0 = No issues found
      1 = High severity findings
      2 = Critical vulnerabilities
      3 = Pipeline failed

    Performance:
      Small project (<5K LOC):     ~2 minutes
      Medium project (20K LOC):    ~10 minutes
      Large monorepo (100K+ LOC):  ~30-60 minutes

    Cache Behavior:
      By default, caches are PRESERVED between runs for speed:
        - AST parsing cache (.pf/.cache/)
        - Documentation cache (.pf/context/docs/)

      Use --wipecache to force a complete cache rebuild.
      This is useful for recovering from cache corruption.

    FLAG INTERACTIONS:
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
    
    # Define log callback for console output
    def log_callback(message, is_error=False):
        if is_error:
            click.echo(message, err=True)
        else:
            click.echo(message)
    
    # Run the pipeline
    result = run_full_pipeline(
        root=root,
        quiet=quiet,
        exclude_self=exclude_self,
        offline=offline,
        use_subprocess_for_taint=subprocess_taint,
        wipe_cache=wipecache,
        log_callback=log_callback if not quiet else None
    )
    
    # Display clear status message based on results
    findings = result.get("findings", {})
    critical = findings.get("critical", 0)
    high = findings.get("high", 0)
    medium = findings.get("medium", 0)
    low = findings.get("low", 0)
    
    click.echo("\n" + "=" * 60)
    click.echo("AUDIT FINAL STATUS")
    click.echo("=" * 60)
    
    # Determine overall status and exit code
    exit_code = ExitCodes.SUCCESS
    
    # Check for pipeline failures first
    if result["failed_phases"] > 0:
        click.echo(f"[WARNING] Pipeline completed with {result['failed_phases']} phase failures")
        click.echo("Some analysis phases could not complete successfully.")
        exit_code = ExitCodes.TASK_INCOMPLETE  # Exit code for pipeline failures
    
    # Then check for security findings
    if critical > 0:
        click.echo(f"\nSTATUS: [CRITICAL] - Audit complete. Found {critical} critical vulnerabilities.")
        click.echo("Immediate action required - deployment should be blocked.")
        exit_code = ExitCodes.CRITICAL_SEVERITY  # Exit code for critical findings
    elif high > 0:
        click.echo(f"\nSTATUS: [HIGH] - Audit complete. Found {high} high-severity issues.")
        click.echo("Priority remediation needed before next release.")
        if exit_code == ExitCodes.SUCCESS:
            exit_code = ExitCodes.HIGH_SEVERITY  # Exit code for high findings (unless already set for failures)
    elif medium > 0 or low > 0:
        click.echo(f"\nSTATUS: [MODERATE] - Audit complete. Found {medium} medium and {low} low issues.")
        click.echo("Schedule fixes for upcoming sprints.")
    else:
        click.echo("\nSTATUS: [CLEAN] - No critical or high-severity issues found.")
        click.echo("Codebase meets security and quality standards.")
    
    # Show findings breakdown if any exist
    if critical + high + medium + low > 0:
        click.echo("\nFindings breakdown:")
        if critical > 0:
            click.echo(f"  - Critical: {critical}")
        if high > 0:
            click.echo(f"  - High: {high}")
        if medium > 0:
            click.echo(f"  - Medium: {medium}")
        if low > 0:
            click.echo(f"  - Low: {low}")
    
    click.echo("\nReview the chunked data in .pf/readthis/ for complete findings.")
    click.echo("=" * 60)
    
    # Exit with appropriate code for CI/CD automation
    # Using standardized exit codes from ExitCodes class
    if exit_code != ExitCodes.SUCCESS:
        sys.exit(exit_code)