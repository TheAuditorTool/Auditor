"""AWS CDK Infrastructure-as-Code security analysis commands.

Commands for analyzing AWS CDK (Python, TypeScript, JavaScript) code, detecting
infrastructure security misconfigurations before deployment.
"""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.logging import logger


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def cdk():
    """AWS CDK Infrastructure-as-Code security analysis for Python/TypeScript/JavaScript.

    Group command for analyzing AWS Cloud Development Kit code to detect infrastructure
    misconfigurations before deployment. Parses CDK construct definitions (Python, TypeScript,
    JavaScript) and applies security rules for S3 buckets, databases, IAM policies, and
    network configurations.

    AI ASSISTANT CONTEXT:
      Purpose: Detect AWS infrastructure security issues in CDK code
      Input: CDK code files (*.py, *.ts, *.js with CDK imports)
      Output: .pf/repo_index.db (cdk_findings table)
      Prerequisites: aud full (extracts CDK constructs)
      Integration: Pre-deployment validation, IaC security auditing
      Performance: ~5-10 seconds (AST parsing + security rules)

    SECURITY CHECKS:
      S3 Buckets:
        - Public read access enabled (public_read_access=True)
        - Missing block_public_access configuration
        - Unencrypted buckets (missing encryption)

      Databases (RDS/DynamoDB):
        - Unencrypted databases at rest
        - Public accessibility enabled
        - Missing backup retention

      IAM:
        - Overprivileged policies (wildcard permissions)
        - Missing least-privilege enforcement

      Network:
        - Public subnets with sensitive resources
        - Missing network ACLs

    TYPICAL WORKFLOW:
      aud full
      aud cdk analyze

    EXAMPLES:
      aud cdk analyze
      aud cdk analyze --severity high

    RELATED COMMANDS:
      aud terraform  # Terraform IaC analysis
      aud detect-patterns  # Includes CDK security rules

    NOTE: CDK analysis requires CDK imports (aws_cdk library). For Terraform
    configurations (.tf files), use 'aud terraform' instead.

    SEE ALSO:
      aud manual cdk   Learn about AWS CDK security analysis
    """
    pass


@click.command("analyze", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--db", default="./.pf/repo_index.db", help="Source database path")
@click.option(
    "--severity", default="all", help="Filter by severity (critical, high, medium, low, all)"
)
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
      - Run 'aud full' first to populate cdk_constructs table
      - Python CDK: Files must import aws_cdk or from aws_cdk
      - TypeScript/JavaScript CDK: Files must import from aws-cdk-lib
    """
    from ..aws_cdk.analyzer import AWSCdkAnalyzer

    db_path = Path(db) if Path(db).is_absolute() else (Path(root) / db).resolve()

    if not db_path.exists():
        err_console.print(f"[error]Error: Database not found at {db_path}[/error]", highlight=False)
        err_console.print(
            "[error]Run 'aud full' first to extract CDK constructs.[/error]",
        )
        raise SystemExit(3)

    try:
        logger.info(f"Analyzing CDK security with database: {db_path}")

        analyzer = AWSCdkAnalyzer(str(db_path), severity_filter=severity)
        findings = analyzer.analyze()

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
                        "remediation": f.remediation,
                    }
                    for f in findings
                ],
                "summary": {"total": len(findings), "by_severity": _count_by_severity(findings)},
            }

            output_text = json.dumps(output_data, indent=2)
        else:
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

        if output:
            Path(output).write_text(output_text)
            console.print(
                f"CDK analysis complete: {len(findings)} findings written to {output}",
                highlight=False,
            )
        else:
            console.print(output_text, markup=False)

        if not findings:
            raise SystemExit(0)
        elif any(f.severity == "critical" for f in findings):
            raise SystemExit(2)
        else:
            raise SystemExit(1)

    except FileNotFoundError as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise SystemExit(3) from e
    except Exception as e:
        logger.error(f"CDK analysis failed: {e}", exc_info=True)
        err_console.print(f"[error]Error during CDK analysis: {e}[/error]", highlight=False)
        raise SystemExit(3) from e


def _count_by_severity(findings):
    """Count findings by severity level."""
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        severity = f.severity.lower()
        if severity in counts:
            counts[severity] += 1
    return counts


cdk.add_command(analyze)
