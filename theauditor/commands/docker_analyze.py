"""Docker security analysis command."""

import click
import json
from pathlib import Path
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.exit_codes import ExitCodes


@click.command("docker-analyze")
@handle_exceptions
@click.option("--db-path", default="./.pf/repo_index.db", help="Path to repo_index.db")
@click.option("--output", help="Output file for findings (JSON format)")
@click.option("--severity", type=click.Choice(["all", "critical", "high", "medium", "low"]), 
              default="all", help="Minimum severity to report")
@click.option("--check-vulns/--no-check-vulns", default=True, 
              help="Check base images for vulnerabilities (requires network)")
def docker_analyze(db_path, output, severity, check_vulns):
    """Analyze Docker images for security issues.
    
    Detects:
    - Containers running as root
    - Exposed secrets in ENV/ARG instructions
    - High entropy values (potential secrets)
    - Base image vulnerabilities (if --check-vulns enabled)
    """
    from theauditor.docker_analyzer import analyze_docker_images
    
    # Check if database exists
    if not Path(db_path).exists():
        click.echo(f"Error: Database not found at {db_path}", err=True)
        click.echo("Run 'aud index' first to create the database", err=True)
        return ExitCodes.TASK_INCOMPLETE
    
    # Run analysis
    click.echo("Analyzing Docker images for security issues...")
    if check_vulns:
        click.echo("  Including vulnerability scan of base images...")
    findings = analyze_docker_images(db_path, check_vulnerabilities=check_vulns)
    
    # Filter by severity if requested
    if severity != "all":
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        min_severity = severity_order.get(severity.lower(), 0)
        findings = [f for f in findings 
                   if severity_order.get(f.get("severity", "").lower(), 0) >= min_severity]
    
    # Count by severity
    severity_counts = {}
    for finding in findings:
        sev = finding.get("severity", "unknown").lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    # Display results
    if findings:
        click.echo(f"\nFound {len(findings)} Docker security issues:")
        
        # Show severity breakdown
        for sev in ["critical", "high", "medium", "low"]:
            if sev in severity_counts:
                click.echo(f"  {sev.upper()}: {severity_counts[sev]}")
        
        # Show findings
        click.echo("\nFindings:")
        for finding in findings:
            click.echo(f"\n[{finding['severity'].upper()}] {finding['type']}")
            click.echo(f"  File: {finding['file']}")
            click.echo(f"  {finding['message']}")
            if finding.get('recommendation'):
                click.echo(f"  Fix: {finding['recommendation']}")
    else:
        click.echo("No Docker security issues found")
    
    # Save to file if requested
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump({
                "findings": findings,
                "summary": severity_counts,
                "total": len(findings)
            }, f, indent=2)
        
        click.echo(f"\nResults saved to: {output}")
    
    # Exit with appropriate code
    if severity_counts.get("critical", 0) > 0:
        return ExitCodes.CRITICAL_SEVERITY
    elif severity_counts.get("high", 0) > 0:
        return ExitCodes.HIGH_SEVERITY
    else:
        return ExitCodes.SUCCESS