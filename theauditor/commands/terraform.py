"""Terraform Infrastructure as Code analysis.

Commands for analyzing Terraform configurations, building provisioning flow
graphs, and detecting infrastructure security issues.
"""

import json
from pathlib import Path
import click

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@click.group()
@click.help_option("-h", "--help")
def terraform():
    """Infrastructure-as-Code security analysis for Terraform configurations and provisioning flows.

    Group command for analyzing Terraform .tf files to detect infrastructure misconfigurations,
    build resource dependency graphs, track sensitive data propagation, and assess blast radius
    for infrastructure changes. Focuses on security issues that would be deployed to production.

    AI ASSISTANT CONTEXT:
      Purpose: Detect infrastructure security issues in Terraform code
      Input: *.tf files (indexed by 'aud index')
      Output: .pf/raw/terraform_findings.json (security issues)
      Prerequisites: aud index (extracts Terraform resources)
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
      aud index
      aud terraform provision
      aud terraform analyze

    EXAMPLES:
      aud terraform provision
      aud terraform analyze --output ./tf_issues.json

    RELATED COMMANDS:
      aud cdk       # AWS CDK security analysis
      aud detect-patterns  # Includes IaC security rules

    NOTE: Terraform analysis requires .tf files in project. For AWS CDK
    (Python/TypeScript), use 'aud cdk' instead.
    """
    pass


@terraform.command("provision")
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--workset", is_flag=True, help="Build graph for workset files only")
@click.option("--output", default="./.pf/raw/terraform_graph.json", help="Output JSON path")
@click.option("--db", default="./.pf/repo_index.db", help="Source database path")
@click.option("--graphs-db", default="./.pf/graphs.db", help="Graph database path")
def provision(root, workset, output, db, graphs_db):
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
      aud terraform provision --output graph.json # Custom output path

    Prerequisites:
      - Must run 'aud index' first to extract Terraform resources
      - Terraform files must be in project (.tf, .tfvars)

    Output:
      .pf/graphs.db                      # Graph stored with type 'terraform_provisioning'
      .pf/raw/terraform_graph.json       # JSON export of graph structure

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
        # Verify database exists
        db_path = Path(db)
        if not db_path.exists():
            click.echo(f"Error: Database not found: {db}", err=True)
            click.echo("Run 'aud index' first to extract Terraform resources.", err=True)
            raise click.Abort()

        # Load workset if requested
        file_filter = None
        if workset:
            workset_path = Path(".pf/workset.json")
            if not workset_path.exists():
                click.echo("Error: Workset file not found. Run 'aud workset' first.", err=True)
                raise click.Abort()

            with open(workset_path) as f:
                workset_data = json.load(f)
                workset_files = {p["path"] for p in workset_data.get("paths", [])}
                file_filter = workset_files
                click.echo(f"Building graph for {len(workset_files)} workset files...")

        # Build provisioning flow graph
        click.echo("Building Terraform provisioning flow graph...")
        builder = TerraformGraphBuilder(db_path=str(db_path))
        graph = builder.build_provisioning_flow_graph(root=root)

        # Filter by workset if requested
        if file_filter:
            # Filter nodes to only those from workset files
            filtered_nodes = [n for n in graph['nodes'] if n['file'] in file_filter]
            node_ids = {n['id'] for n in filtered_nodes}

            # Filter edges to only those connecting filtered nodes
            filtered_edges = [
                e for e in graph['edges']
                if e['source'] in node_ids and e['target'] in node_ids
            ]

            graph['nodes'] = filtered_nodes
            graph['edges'] = filtered_edges
            graph['metadata']['stats']['workset_filtered'] = True

        # Write output
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(graph, f, indent=2)

        # Display summary
        stats = graph['metadata']['stats']

        click.echo(f"\nProvisioning Graph Built:")
        click.echo(f"  Variables: {stats['total_variables']}")
        click.echo(f"  Resources: {stats['total_resources']}")
        click.echo(f"  Outputs: {stats['total_outputs']}")
        click.echo(f"  Edges: {stats['edges_created']}")
        click.echo(f"  Files: {stats['files_processed']}")
        click.echo(f"\nGraph stored in: {graphs_db}")
        click.echo(f"JSON export: {output_path}")

        # Check for sensitive data flows
        sensitive_nodes = [n for n in graph['nodes'] if n.get('is_sensitive')]
        if sensitive_nodes:
            click.echo(f"\nSensitive Data Nodes Detected: {len(sensitive_nodes)}")
            for node in sensitive_nodes[:3]:  # Show first 3
                click.echo(f"  - {node['name']} ({node['node_type']})")
            if len(sensitive_nodes) > 3:
                click.echo(f"  ... and {len(sensitive_nodes) - 3} more")

        # Check for public exposure
        public_nodes = [n for n in graph['nodes'] if n.get('has_public_exposure')]
        if public_nodes:
            click.echo(f"\nPublic Exposure Detected: {len(public_nodes)} resources")
            for node in public_nodes[:3]:
                click.echo(f"  - {node['name']} ({node['terraform_type']})")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        logger.error(f"Failed to build provisioning graph: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@terraform.command("analyze")
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--severity", type=click.Choice(['critical', 'high', 'medium', 'low', 'all']), default="all", help="Minimum severity to report")
@click.option("--categories", multiple=True, help="Specific categories to check (e.g., public_exposure, iam_wildcard)")
@click.option("--output", default="./.pf/raw/terraform_findings.json", help="Output JSON path")
@click.option("--db", default="./.pf/repo_index.db", help="Database path")
def analyze(root, severity, categories, output, db):
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
      - Run 'aud index' first to extract Terraform resources
      - Optionally run 'aud terraform provision' for graph-based analysis

    Output:
      .pf/raw/terraform_findings.json    # JSON findings export
      terraform_findings table           # Database findings for FCE
    """
    from ..terraform.analyzer import TerraformAnalyzer

    try:
        # Verify database exists
        db_path = Path(db)
        if not db_path.exists():
            click.echo(f"Error: Database not found: {db}", err=True)
            click.echo("Run 'aud index' first to extract Terraform resources.", err=True)
            raise click.Abort()

        # Run analyzer
        click.echo("Analyzing Terraform configurations for security issues...")
        analyzer = TerraformAnalyzer(db_path=str(db_path), severity_filter=severity)
        findings = analyzer.analyze()

        # Filter by categories if specified
        if categories:
            findings = [f for f in findings if f.category in categories]
            click.echo(f"Filtered to categories: {', '.join(categories)}")

        # Export to JSON
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        findings_json = [
            {
                'finding_id': f.finding_id,
                'file_path': f.file_path,
                'resource_id': f.resource_id,
                'category': f.category,
                'severity': f.severity,
                'title': f.title,
                'description': f.description,
                'line': f.line,
                'remediation': f.remediation
            }
            for f in findings
        ]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(findings_json, f, indent=2)

        # Display summary
        click.echo(f"\nTerraform Security Analysis Complete:")
        click.echo(f"  Total findings: {len(findings)}")

        # Count by severity
        from collections import Counter
        severity_counts = Counter(f.severity for f in findings)
        for sev in ['critical', 'high', 'medium', 'low', 'info']:
            if severity_counts[sev] > 0:
                click.echo(f"  {sev.capitalize()}: {severity_counts[sev]}")

        # Count by category
        category_counts = Counter(f.category for f in findings)
        click.echo(f"\nFindings by category:")
        for cat, count in category_counts.most_common():
            click.echo(f"  {cat}: {count}")

        click.echo(f"\nFindings exported to: {output_path}")
        click.echo(f"Findings stored in terraform_findings table for FCE correlation")

        # Show sample findings
        if findings:
            click.echo(f"\nSample findings (first 3):")
            for finding in findings[:3]:
                click.echo(f"\n  [{finding.severity.upper()}] {finding.title}")
                click.echo(f"  File: {finding.file_path}:{finding.line}")
                click.echo(f"  {finding.description}")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        logger.error(f"Failed to analyze Terraform: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@terraform.command("report")
@click.option("--format", type=click.Choice(['text', 'json', 'markdown']), default="text", help="Output format")
@click.option("--output", help="Output file path (stdout if not specified)")
@click.option("--severity", type=click.Choice(['critical', 'high', 'medium', 'low', 'all']), default="all", help="Minimum severity to report")
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
    click.echo("Error: 'terraform report' not yet implemented (Phase 7)", err=True)
    click.echo("Run 'aud terraform provision' to build provisioning graph.", err=True)
    raise click.Abort()
