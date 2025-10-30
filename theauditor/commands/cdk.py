"""AWS CDK Infrastructure-as-Code security analysis commands.

Commands for analyzing AWS CDK Python code, detecting infrastructure
security misconfigurations before deployment.
"""

import json
from pathlib import Path
import click

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@click.group()
@click.help_option("-h", "--help")
def cdk():
    """Analyze AWS CDK Infrastructure-as-Code security.

    Provides infrastructure security analysis for AWS CDK Python code,
    detecting misconfigurations like public S3 buckets, unencrypted databases,
    open security groups, and overly permissive IAM policies.

    Subcommands:
      analyze  - Detect CDK infrastructure security issues

    Typical Workflow:
      1. aud index                     # Extract CDK constructs from Python files
      2. aud cdk analyze               # Detect security issues
      3. aud report                    # Include CDK findings in consolidated report

    The CDK analyzer detects:
      - Public S3 buckets (public_read_access=True)
      - Missing S3 block_public_access configuration
      - Unencrypted RDS instances
      - Unencrypted EBS volumes
      - DynamoDB tables with default encryption
      - Security groups with unrestricted ingress (0.0.0.0/0, ::/0)
      - Security groups with allow_all_outbound
      - IAM policies with wildcard actions or resources
      - IAM roles with AdministratorAccess policy

    Examples:
      aud cdk analyze                          # Run all CDK security checks
      aud cdk analyze --severity critical      # Show only critical findings
      aud cdk analyze --format json            # Export findings as JSON

    Output:
      .pf/repo_index.db (cdk_findings table)   # Security findings stored here
      .pf/readthis/cdk_*.json                  # AI-optimized capsules (future)

    Prerequisites:
      - Must run 'aud index' first to extract CDK constructs
      - Python files must import aws_cdk
    """
    pass


@click.command("analyze")
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--db", default="./.pf/repo_index.db", help="Source database path")
@click.option("--severity", default="all", help="Filter by severity (critical, high, medium, low, all)")
@click.option("--format", "output_format", default="text", help="Output format (text, json)")
@click.option("--output", default=None, help="Output file path (default: stdout)")
def analyze(root, db, severity, output_format, output):
    """Detect AWS CDK infrastructure security issues.

    Analyzes CDK constructs extracted during indexing and applies security
    detection rules to identify misconfigurations.

    The analyzer queries the cdk_constructs and cdk_construct_properties tables
    to detect:
    - Publicly accessible resources
    - Missing encryption configurations
    - Overly permissive network rules
    - Excessive IAM permissions

    Examples:
      aud cdk analyze                          # All findings
      aud cdk analyze --severity high          # High+ severity only
      aud cdk analyze --format json            # JSON output
      aud cdk analyze --output cdk_report.json # Write to file

    Exit Codes:
      0 = No security issues found
      1 = Security issues detected
      2 = Critical security issues detected
      3 = Analysis failed (database not found, etc.)

    Prerequisites:
      - Run 'aud index' first to populate cdk_constructs table
      - CDK Python files must be in project
    """
    from ..aws_cdk.analyzer import AWSCdkAnalyzer

    db_path = Path(root) / Path(db).name if not Path(db).is_absolute() else Path(db)

    if not db_path.exists():
        click.echo(f"Error: Database not found at {db_path}", err=True)
        click.echo("Run 'aud index' first to extract CDK constructs.", err=True)
        raise SystemExit(3)

    try:
        logger.info(f"Analyzing CDK security with database: {db_path}")

        # Run analyzer
        analyzer = AWSCdkAnalyzer(str(db_path), severity_filter=severity)
        findings = analyzer.analyze()

        # Format output
        if output_format == "json":
            output_data = {
                "findings": [
                    {
                        "finding_id": f.finding_id,
                        "file_path": f.file_path,
                        "line": f.line,
                        "construct_id": f.construct_id,
                        "category": f.category,
                        "severity": f.severity,
                        "title": f.title,
                        "description": f.description,
                        "remediation": f.remediation
                    }
                    for f in findings
                ],
                "summary": {
                    "total": len(findings),
                    "by_severity": _count_by_severity(findings)
                }
            }

            output_text = json.dumps(output_data, indent=2)
        else:
            # Text format
            if not findings:
                output_text = "No CDK security issues found.\n"
            else:
                lines = [f"Found {len(findings)} CDK security issue(s):\n"]
                for f in findings:
                    lines.append(f"\n[{f.severity.upper()}] {f.title}")
                    lines.append(f"  File: {f.file_path}:{f.line}")
                    if f.construct_id:
                        lines.append(f"  Construct: {f.construct_id}")
                    lines.append(f"  Category: {f.category}")
                    if f.remediation:
                        lines.append(f"  Remediation: {f.remediation}")
                output_text = "\n".join(lines) + "\n"

        # Write output
        if output:
            Path(output).write_text(output_text)
            click.echo(f"CDK analysis complete: {len(findings)} findings written to {output}")
        else:
            click.echo(output_text)

        # Determine exit code
        if not findings:
            raise SystemExit(0)
        elif any(f.severity == 'critical' for f in findings):
            raise SystemExit(2)
        else:
            raise SystemExit(1)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(3)
    except Exception as e:
        logger.error(f"CDK analysis failed: {e}", exc_info=True)
        click.echo(f"Error during CDK analysis: {e}", err=True)
        raise SystemExit(3)


def _count_by_severity(findings):
    """Count findings by severity level."""
    counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    for f in findings:
        severity = f.severity.lower()
        if severity in counts:
            counts[severity] += 1
    return counts


# Register subcommands
cdk.add_command(analyze)
