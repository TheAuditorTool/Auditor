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
def full(root, quiet, exclude_self, offline, subprocess_taint):
    """Run complete audit pipeline with multiple analysis phases organized in parallel stages."""
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