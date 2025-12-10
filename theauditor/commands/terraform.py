"""Terraform Infrastructure as Code analysis.

Commands for analyzing Terraform configurations, building provisioning flow
graphs, and detecting infrastructure security issues.
"""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.logging import logger


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def terraform():
    """Infrastructure-as-Code security analysis for Terraform configurations and provisioning flows.

    Group command for analyzing Terraform .tf files to detect infrastructure misconfigurations,
    build resource dependency graphs, track sensitive data propagation, and assess blast radius
    for infrastructure changes. Focuses on security issues that would be deployed to production.

    AI ASSISTANT CONTEXT:
      Purpose: Detect infrastructure security issues in Terraform code
      Input: *.tf files (extracted by 'aud full')
      Output: Console or JSON (--json), findings stored in database
      Prerequisites: aud full (extracts Terraform resources)
      Integration: Pre-deployment security validation, IaC auditing
      Performance: ~5-15 seconds (HCL parsing + security rules)

    SUBCOMMANDS:
      provision: Build provisioning flow graph (var→resource→output)
      analyze:   Run security rules on Terraform configurations
      report:    Generate consolidated infrastructure security report

    PROVISIONING GRAPH INSIGHTS:
      - Variable → Resource → Output data flows
      - Resource dependency chains (depends_on, implicit)
      - Sensitive data propagation (secrets, credentials)
      - Public exposure blast radius (internet-facing resources)

    SECURITY CHECKS:
      - Public S3 buckets, unencrypted databases
      - Overprivileged IAM policies (wildcard permissions)
      - Missing encryption at rest/transit
      - Hard-coded secrets in configurations

    TYPICAL WORKFLOW:
      aud full
      aud terraform provision
      aud terraform analyze

    EXAMPLES:
      aud terraform provision
      aud terraform analyze --severity critical

    RELATED COMMANDS:
      aud cdk       # AWS CDK security analysis
      aud detect-patterns  # Includes IaC security rules

    NOTE: Terraform analysis requires .tf files in project. For AWS CDK
    (Python/TypeScript), use 'aud cdk' instead.

    SEE ALSO:
      aud manual terraform   Learn about IaC security analysis
    """
    pass


@terraform.command("provision", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--workset", is_flag=True, help="Build graph for workset files only")
@click.option("--db", default="./.pf/repo_index.db", help="Source database path")
@click.option("--graphs-db", default="./.pf/graphs.db", help="Graph database path")
def provision(root, workset, db, graphs_db):
    """Build Terraform provisioning flow graph.

    Constructs a data flow graph showing how variables, resources, and
    outputs connect through dependencies and interpolations.

    The graph enables:
    - Tracing sensitive data (e.g., passwords) through infrastructure
    - Understanding resource dependency chains
    - Calculating blast radius of changes
    - Identifying public exposure paths

    Examples:
      aud terraform provision                    # Build full graph
      aud terraform provision --workset          # Graph for changed files

    Prerequisites:
      - Must run 'aud full' first to extract Terraform resources
      - Terraform files must be in project (.tf, .tfvars)

    Output:
      .pf/graphs.db                      # Graph stored with type 'terraform_provisioning'
      Use --json for graph export        # Pipe to file if needed

    Graph Structure:
      Nodes:
        - Variables (source nodes): Inputs to infrastructure
        - Resources (processing nodes): AWS/Azure/GCP resources
        - Outputs (sink nodes): Exported values

      Edges:
        - variable_reference: Variable -> Resource (var.X used in resource)
        - resource_dependency: Resource -> Resource (depends_on)
        - output_reference: Resource -> Output (output references resource)
    """
    from ..terraform.graph import TerraformGraphBuilder

    try:
        db_path = Path(db)
        if not db_path.exists():
            err_console.print(f"[error]Error: Database not found: {db}[/error]", highlight=False)
            err_console.print(
                "[error]Run 'aud full' first to extract Terraform resources.[/error]",
            )
            raise click.Abort()

        file_filter = None
        if workset:
            workset_path = Path(".pf/workset.json")
            if not workset_path.exists():
                err_console.print(
                    "[error]Error: Workset file not found. Run 'aud workset' first.[/error]",
                )
                raise click.Abort()

            with open(workset_path) as f:
                workset_data = json.load(f)
                workset_files = {p["path"] for p in workset_data.get("paths", [])}
                file_filter = workset_files
                console.print(
                    f"Building graph for {len(workset_files)} workset files...", highlight=False
                )

        console.print("Building Terraform provisioning flow graph...")
        builder = TerraformGraphBuilder(db_path=str(db_path))
        graph = builder.build_provisioning_flow_graph(root=root)

        if file_filter:
            filtered_nodes = [n for n in graph["nodes"] if n["file"] in file_filter]
            node_ids = {n["id"] for n in filtered_nodes}

            filtered_edges = [
                e for e in graph["edges"] if e["source"] in node_ids and e["target"] in node_ids
            ]

            graph["nodes"] = filtered_nodes
            graph["edges"] = filtered_edges
            graph["metadata"]["stats"]["workset_filtered"] = True

        stats = graph["metadata"]["stats"]

        console.print("\nProvisioning Graph Built:")
        console.print(f"  Variables: {stats['total_variables']}", highlight=False)
        console.print(f"  Resources: {stats['total_resources']}", highlight=False)
        console.print(f"  Outputs: {stats['total_outputs']}", highlight=False)
        console.print(f"  Edges: {stats['edges_created']}", highlight=False)
        console.print(f"  Files: {stats['files_processed']}", highlight=False)
        console.print(f"\nGraph stored in: {graphs_db}", highlight=False)

        sensitive_nodes = [n for n in graph["nodes"] if n.get("is_sensitive")]
        if sensitive_nodes:
            console.print(
                f"\nSensitive Data Nodes Detected: {len(sensitive_nodes)}", highlight=False
            )
            for node in sensitive_nodes[:3]:
                console.print(f"  - {node['name']} ({node['node_type']})", highlight=False)
            if len(sensitive_nodes) > 3:
                console.print(f"  ... and {len(sensitive_nodes) - 3} more", highlight=False)

        public_nodes = [n for n in graph["nodes"] if n.get("has_public_exposure")]
        if public_nodes:
            console.print(
                f"\nPublic Exposure Detected: {len(public_nodes)} resources", highlight=False
            )
            for node in public_nodes[:3]:
                console.print(f"  - {node['name']} ({node['terraform_type']})", highlight=False)

    except FileNotFoundError as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.Abort() from e
    except Exception as e:
        logger.error(f"Failed to build provisioning graph: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.Abort() from e


@terraform.command("analyze", cls=RichCommand)
@click.option("--root", default=".", help="Root directory to analyze")
@click.option(
    "--severity",
    type=click.Choice(["critical", "high", "medium", "low", "all"]),
    default="all",
    help="Minimum severity to report",
)
@click.option(
    "--categories",
    multiple=True,
    help="Specific categories to check (e.g., public_exposure, iam_wildcard)",
)
@click.option("--db", default="./.pf/repo_index.db", help="Database path")
def analyze(root, severity, categories, db):
    """Analyze Terraform for security issues.

    Detects infrastructure security issues including:
    - Public exposure (S3 buckets, databases, security groups)
    - Overly permissive IAM policies (wildcards)
    - Hardcoded secrets in resource configurations
    - Missing encryption for sensitive resources
    - Unencrypted network traffic

    Examples:
      aud terraform analyze                      # Full analysis
      aud terraform analyze --severity critical  # Critical issues only
      aud terraform analyze --categories public_exposure

    Prerequisites:
      - Run 'aud full' first to extract Terraform resources
      - Optionally run 'aud terraform provision' for graph-based analysis

    Output:
      Console or JSON (--format json)    # Findings to stdout
      findings_consolidated table        # Database findings for FCE
    """
    from ..terraform.analyzer import TerraformAnalyzer

    try:
        db_path = Path(db)
        if not db_path.exists():
            err_console.print(f"[error]Error: Database not found: {db}[/error]", highlight=False)
            err_console.print(
                "[error]Run 'aud full' first to extract Terraform resources.[/error]",
            )
            raise click.Abort()

        console.print("Analyzing Terraform configurations for security issues...")
        analyzer = TerraformAnalyzer(db_path=str(db_path), severity_filter=severity)
        findings = analyzer.analyze()

        if categories:
            findings = [f for f in findings if f.category in categories]
            console.print(f"Filtered to categories: {', '.join(categories)}", highlight=False)

        console.print("\nTerraform Security Analysis Complete:")
        console.print(f"  Total findings: {len(findings)}", highlight=False)

        from collections import Counter

        severity_counts = Counter(f.severity for f in findings)
        for sev in ["critical", "high", "medium", "low", "info"]:
            if severity_counts[sev] > 0:
                console.print(f"  {sev.capitalize()}: {severity_counts[sev]}", highlight=False)

        category_counts = Counter(f.category for f in findings)
        console.print("\nFindings by category:")
        for cat, count in category_counts.most_common():
            console.print(f"  {cat}: {count}", highlight=False)

        console.print("\nFindings stored in terraform_findings table for FCE correlation")

        if findings:
            console.print("\nSample findings (first 3):")
            for finding in findings[:3]:
                console.print(
                    f"\n  \\[{finding.severity.upper()}] {finding.title}", highlight=False
                )
                console.print(f"  File: {finding.file_path}:{finding.line}", highlight=False)
                console.print(f"  {finding.description}", highlight=False)

    except FileNotFoundError as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.Abort() from e
    except Exception as e:
        logger.error(f"Failed to analyze Terraform: {e}", exc_info=True)
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.Abort() from e


@terraform.command("report", cls=RichCommand)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "markdown"]),
    default="text",
    help="Output format",
)
@click.option("--output", help="Output file path (stdout if not specified)")
@click.option(
    "--severity",
    type=click.Choice(["critical", "high", "medium", "low", "all"]),
    default="all",
    help="Minimum severity to report",
)
def report(format, output, severity):
    """Generate Terraform security report.

    [PHASE 7 - NOT YET IMPLEMENTED]

    Generates a comprehensive report of infrastructure security findings
    including blast radius analysis and remediation recommendations.

    Examples:
      aud terraform report                       # Text report to stdout
      aud terraform report --format json         # JSON export
      aud terraform report --output report.md --format markdown

    Prerequisites:
      - Run 'aud terraform analyze' first to generate findings

    This command will be implemented in Phase 7.
    """
    err_console.print(
        "[error]Error: 'terraform report' not yet implemented (Phase 7)[/error]",
    )
    err_console.print(
        "[error]Run 'aud terraform provision' to build provisioning graph.[/error]",
    )
    raise click.Abort()
