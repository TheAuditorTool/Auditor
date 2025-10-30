"""AWS CDK Infrastructure-as-Code security analysis commands.

Commands for analyzing AWS CDK (Python, TypeScript, JavaScript) code, detecting
infrastructure security misconfigurations before deployment.
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

    Detects security misconfigurations in AWS Cloud Development Kit (CDK) code
    (Python, TypeScript, JavaScript) before deployment. Findings are written to
    the database for querying.

    Prerequisites:
        Run indexing first to extract CDK constructs:
          aud index       (recommended - full project indexing)

    Typical Workflow:
        1. aud index                     # Extract CDK constructs from all files
        2. aud cdk analyze               # Detect security issues (writes to DB)
        3. Query .pf/repo_index.db       # Read findings from cdk_findings table

    Security Checks Performed:
        S3 Buckets:
          - Public read access enabled (public_read_access=True)
          - Missing block_public_access configuration

        Databases:
          - Unencrypted RDS instances
          - Unencrypted EBS volumes
          - DynamoDB tables with default encryption

        Network Security:
          - Security groups with unrestricted ingress (0.0.0.0/0, ::/0)
          - Security groups with allow_all_outbound enabled

        IAM Permissions:
          - Wildcard actions in IAM policies (Action: "*")
          - Wildcard resources in IAM policies (Resource: "*")
          - IAM roles with AdministratorAccess policy

    Examples:
        # Run all CDK security checks
        aud cdk analyze

        # Filter by severity (useful for CI/CD)
        aud cdk analyze --severity critical

        # Human-readable report
        aud cdk analyze --format json --output report.json

    Output Locations:
        .pf/repo_index.db::cdk_findings           # CDK findings (query this!)
        .pf/repo_index.db::findings_consolidated  # All findings (includes CDK)
        stdout or --output file                   # Human-readable report

    For AI Integration (IMPORTANT):
        Findings are written to DATABASE, not just stdout.
        Query the database directly:

          SELECT finding_id, file_path, line, severity, category, title
          FROM cdk_findings
          WHERE severity IN ('critical', 'high')
          ORDER BY severity;

        DO NOT parse JSON output - it's for human consumption only.
        Database is the single source of truth.

    Subcommands:
        analyze     Detect CDK infrastructure security issues

    See Also:
        theauditor/aws_cdk/README.md              # CDK analyzer docs
        tests/fixtures/cdk_test_project/          # Example CDK project
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

    Analyzes CDK constructs and writes findings to cdk_findings database table.
    Stdout/JSON output is for human consumption only - AI should query database.

    Detection Categories:
      - Publicly accessible resources (S3, RDS, etc.)
      - Missing encryption configurations
      - Overly permissive network rules (security groups)
      - Excessive IAM permissions (wildcard policies)

    Examples:
      aud cdk analyze                          # All findings
      aud cdk analyze --severity high          # High+ severity only
      aud cdk analyze --format json            # JSON output (human report)
      aud cdk analyze --output cdk_report.json # Write to file

    For AI Integration:
      Step 1: Run analysis (writes to database)
        aud cdk analyze

      Step 2: Query database (DO NOT parse stdout!)
        SELECT * FROM cdk_findings WHERE severity='critical';

    Exit Codes:
      0 = No security issues found
      1 = Security issues detected
      2 = Critical security issues detected
      3 = Analysis failed (database not found, etc.)

    Prerequisites:
      - Run 'aud index' first to populate cdk_constructs table
      - Python CDK: Files must import aws_cdk or from aws_cdk
      - TypeScript/JavaScript CDK: Files must import from aws-cdk-lib
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
