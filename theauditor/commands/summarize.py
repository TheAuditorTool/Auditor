"""Generate guidance summaries from consolidated analysis files.

Creates 5 focused summaries for quick orientation:
- SAST_Summary.json: Top 20 security findings
- SCA_Summary.json: Top 20 dependency issues
- Intelligence_Summary.json: Top 20 code intelligence insights
- Quick_Start.json: Top 10 critical issues across ALL domains
- Query_Guide.json: How to query via aud commands

Truth courier principle: Highlight findings, show metrics, NO recommendations.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List
import click
from theauditor.utils.error_handler import handle_exceptions


@click.command()
@click.option("--root", default=".", help="Root directory")
@handle_exceptions
def summarize(root):
    """Generate 5 guidance summaries from consolidated analysis files.

    Reads consolidated group files (.pf/raw/*_analysis.json) and generates
    focused summaries for quick orientation. These are truth courier documents:
    highlight findings, show metrics, point to hotspots, but NEVER recommend fixes.

    Output:
      .pf/raw/SAST_Summary.json         - Top 20 security findings
      .pf/raw/SCA_Summary.json          - Top 20 dependency issues
      .pf/raw/Intelligence_Summary.json - Top 20 code intelligence insights
      .pf/raw/Quick_Start.json          - Top 10 critical across all domains
      .pf/raw/Query_Guide.json          - How to query via aud commands

    Prerequisites:
      aud full  # Or individual commands: aud detect-patterns, aud taint-analyze, etc.

    Examples:
      aud summarize                     # Generate all 5 summaries
      aud summarize --root /path/to/project
    """
    raw_dir = Path(root) / ".pf" / "raw"

    if not raw_dir.exists():
        click.echo(f"[ERROR] Directory not found: {raw_dir}")
        click.echo("Run 'aud index' or 'aud full' first to generate analysis data")
        return

    click.echo("[SUMMARIZE] Generating guidance summaries...")

    # Generate SAST Summary
    try:
        sast = generate_sast_summary(raw_dir)
        with open(raw_dir / 'SAST_Summary.json', 'w') as f:
            json.dump(sast, f, indent=2)
        click.echo(f"  [OK] SAST_Summary.json ({len(sast.get('top_findings', []))} findings)")
    except Exception as e:
        click.echo(f"  [WARN] SAST summary failed: {e}")

    # Generate SCA Summary
    try:
        sca = generate_sca_summary(raw_dir)
        with open(raw_dir / 'SCA_Summary.json', 'w') as f:
            json.dump(sca, f, indent=2)
        click.echo(f"  [OK] SCA_Summary.json ({len(sca.get('top_issues', []))} issues)")
    except Exception as e:
        click.echo(f"  [WARN] SCA summary failed: {e}")

    # Generate Intelligence Summary
    try:
        intelligence = generate_intelligence_summary(raw_dir)
        with open(raw_dir / 'Intelligence_Summary.json', 'w') as f:
            json.dump(intelligence, f, indent=2)
        click.echo(f"  [OK] Intelligence_Summary.json ({len(intelligence.get('top_insights', []))} insights)")
    except Exception as e:
        click.echo(f"  [WARN] Intelligence summary failed: {e}")

    # Generate Quick Start
    try:
        quick_start = generate_quick_start(raw_dir)
        with open(raw_dir / 'Quick_Start.json', 'w') as f:
            json.dump(quick_start, f, indent=2)
        click.echo(f"  [OK] Quick_Start.json ({len(quick_start.get('top_10_critical', []))} critical issues)")
    except Exception as e:
        click.echo(f"  [WARN] Quick Start failed: {e}")

    # Generate Query Guide
    try:
        query_guide = generate_query_guide()
        with open(raw_dir / 'Query_Guide.json', 'w') as f:
            json.dump(query_guide, f, indent=2)
        click.echo(f"  [OK] Query_Guide.json")
    except Exception as e:
        click.echo(f"  [WARN] Query Guide failed: {e}")

    click.echo("[OK] Generated 5 guidance summaries in .pf/raw/")


def generate_sast_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate SAST summary from security_analysis.json."""
    security_path = raw_dir / 'security_analysis.json'

    if not security_path.exists():
        return {
            "summary_type": "SAST",
            "error": "security_analysis.json not found - run 'aud detect-patterns' and 'aud taint-analyze'",
            "total_vulnerabilities": 0,
            "top_findings": []
        }

    with open(security_path, 'r') as f:
        security = json.load(f)

    # Extract findings from all analyses
    all_findings = []

    # Patterns
    patterns = security.get("analyses", {}).get("patterns", {})
    if patterns and "findings" in patterns:
        all_findings.extend(patterns["findings"])

    # Taint flows
    taint = security.get("analyses", {}).get("taint", {})
    if taint and "vulnerabilities" in taint:
        all_findings.extend(taint["vulnerabilities"])

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        all_findings,
        key=lambda f: (severity_order.get(f.get("severity", "low"), 99), f.get("file", ""))
    )[:20]

    # Count by severity
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in all_findings:
        sev = f.get("severity", "low")
        if sev in by_severity:
            by_severity[sev] += 1

    return {
        "summary_type": "SAST",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_vulnerabilities": len(all_findings),
        "by_severity": by_severity,
        "top_findings": sorted_findings,
        "detail_location": ".pf/raw/security_analysis.json",
        "query_alternative": "Use 'aud query --category jwt' or 'aud query --pattern password%' for targeted searches"
    }


def generate_sca_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate SCA summary from dependency_analysis.json."""
    deps_path = raw_dir / 'dependency_analysis.json'

    if not deps_path.exists():
        return {
            "summary_type": "SCA",
            "error": "dependency_analysis.json not found - run 'aud deps --vuln-scan'",
            "total_issues": 0,
            "top_issues": []
        }

    with open(deps_path, 'r') as f:
        deps = json.load(f)

    # Extract CVEs and outdated packages
    all_issues = []

    # Vulnerabilities
    deps_data = deps.get("analyses", {}).get("deps", {})
    if deps_data and "vulnerabilities" in deps_data:
        all_issues.extend(deps_data["vulnerabilities"])

    # Outdated packages
    if deps_data and "outdated" in deps_data:
        for pkg in deps_data["outdated"]:
            all_issues.append({
                "type": "outdated",
                "package": pkg.get("name"),
                "current": pkg.get("current_version"),
                "latest": pkg.get("latest_version"),
                "severity": "low"
            })

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_issues = sorted(
        all_issues,
        key=lambda i: (severity_order.get(i.get("severity", "low"), 99), i.get("package", ""))
    )[:20]

    return {
        "summary_type": "SCA",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_issues": len(all_issues),
        "by_type": {
            "vulnerabilities": len([i for i in all_issues if i.get("type") != "outdated"]),
            "outdated": len([i for i in all_issues if i.get("type") == "outdated"])
        },
        "top_issues": sorted_issues,
        "detail_location": ".pf/raw/dependency_analysis.json",
        "query_alternative": "Use 'aud deps --vuln-scan --print-stats' for detailed analysis"
    }


def generate_intelligence_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate intelligence summary from graph + correlation analysis."""
    graph_path = raw_dir / 'graph_analysis.json'
    fce_path = raw_dir / 'correlation_analysis.json'

    all_insights = []

    # Graph insights
    if graph_path.exists():
        with open(graph_path, 'r') as f:
            graph = json.load(f)

        # Cycles
        analyze = graph.get("analyses", {}).get("analyze", {})
        if analyze and "cycles" in analyze:
            for cycle in analyze["cycles"][:5]:
                all_insights.append({
                    "type": "cycle",
                    "severity": "medium",
                    "description": f"Circular dependency: {len(cycle.get('nodes', []))} nodes",
                    "details": cycle
                })

        # Hotspots
        if analyze and "hotspots" in analyze:
            for hotspot in analyze["hotspots"][:10]:
                all_insights.append({
                    "type": "hotspot",
                    "severity": "low",
                    "description": f"High centrality: {hotspot.get('id')}",
                    "details": hotspot
                })

    # FCE correlations
    if fce_path.exists():
        with open(fce_path, 'r') as f:
            fce = json.load(f)

        if "correlations" in fce:
            for corr in fce["correlations"][:5]:
                all_insights.append({
                    "type": "correlation",
                    "severity": corr.get("severity", "medium"),
                    "description": f"Meta-finding: {corr.get('description')}",
                    "details": corr
                })

    return {
        "summary_type": "Intelligence",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_insights": len(all_insights),
        "by_type": {
            "cycles": len([i for i in all_insights if i.get("type") == "cycle"]),
            "hotspots": len([i for i in all_insights if i.get("type") == "hotspot"]),
            "correlations": len([i for i in all_insights if i.get("type") == "correlation"])
        },
        "top_insights": all_insights[:20],
        "detail_location": ".pf/raw/graph_analysis.json and correlation_analysis.json",
        "query_alternative": "Use 'aud query --symbol X --show-callers --depth 3' to explore dependencies"
    }


def generate_quick_start(raw_dir: Path) -> Dict[str, Any]:
    """Generate ultra-condensed top 10 across ALL domains."""
    # Load all 3 summaries
    sast = generate_sast_summary(raw_dir)
    sca = generate_sca_summary(raw_dir)
    intelligence = generate_intelligence_summary(raw_dir)

    # Combine top critical issues
    all_critical = []

    # SAST critical/high
    for f in sast.get("top_findings", []):
        if f.get("severity") in ["critical", "high"]:
            all_critical.append({
                "domain": "SAST",
                "severity": f.get("severity"),
                "description": f.get("message", f.get("description", "Security issue")),
                "location": f.get("file"),
                "line": f.get("line")
            })

    # SCA critical/high
    for i in sca.get("top_issues", []):
        if i.get("severity") in ["critical", "high"]:
            all_critical.append({
                "domain": "SCA",
                "severity": i.get("severity"),
                "description": f"{i.get('package')}: {i.get('type', 'issue')}",
                "location": i.get("package")
            })

    # Intelligence high-impact
    for insight in intelligence.get("top_insights", []):
        if insight.get("severity") in ["high", "critical"]:
            all_critical.append({
                "domain": "Intelligence",
                "severity": insight.get("severity"),
                "description": insight.get("description"),
                "type": insight.get("type")
            })

    # Sort and take top 10
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    top_10 = sorted(
        all_critical,
        key=lambda x: severity_order.get(x.get("severity", "low"), 99)
    )[:10]

    return {
        "summary_type": "Quick Start",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "purpose": "Read this first - top 10 most critical issues across all analysis domains",
        "top_10_critical": top_10,
        "next_steps": [
            "Review SAST_Summary.json for security vulnerabilities",
            "Review SCA_Summary.json for dependency issues",
            "Review Intelligence_Summary.json for architectural concerns",
            "Query database via 'aud query' for detailed exploration"
        ],
        "full_summaries": {
            "sast": ".pf/raw/SAST_Summary.json",
            "sca": ".pf/raw/SCA_Summary.json",
            "intelligence": ".pf/raw/Intelligence_Summary.json"
        }
    }


def generate_query_guide() -> Dict[str, Any]:
    """Generate query reference guide."""
    return {
        "guide_type": "Query Reference",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "purpose": "AI assistants should query database directly instead of parsing JSON files",
        "primary_interaction": "Database queries via 'aud query' and 'aud context'",
        "queries_by_domain": {
            "Security Patterns": {
                "examples": [
                    "aud query --category jwt",
                    "aud query --category oauth",
                    "aud query --pattern 'password%'"
                ],
                "description": "Find security findings by category or pattern"
            },
            "Taint Analysis": {
                "examples": [
                    "aud query --variable user_input --show-flow",
                    "aud query --symbol db.execute --show-callers"
                ],
                "description": "Trace data flow from sources to sinks"
            },
            "Graph Analysis": {
                "examples": [
                    "aud query --file api.py --show-dependencies",
                    "aud query --symbol authenticate --show-callers --depth 3"
                ],
                "description": "Explore call graphs and import dependencies"
            },
            "Code Quality": {
                "examples": [
                    "aud query --symbol calculate_total --show-callees",
                    "aud cfg analyze --complexity-threshold 20"
                ],
                "description": "Find code complexity and quality issues"
            },
            "Dependencies": {
                "examples": [
                    "aud deps --vuln-scan",
                    "aud docs fetch --deps .pf/raw/deps.json"
                ],
                "description": "Analyze dependencies and vulnerabilities"
            },
            "Infrastructure": {
                "examples": [
                    "aud terraform analyze",
                    "aud workflows analyze"
                ],
                "description": "Audit IaC and CI/CD configurations"
            },
            "Semantic Classification": {
                "examples": [
                    "aud context --file refactor_rules.yaml"
                ],
                "description": "Apply custom semantic rules to findings"
            }
        },
        "performance_comparison": {
            "database_query": "<10ms per query",
            "json_parsing": "1-2s to read multiple files",
            "token_savings": "5,000-10,000 tokens per refactoring iteration",
            "accuracy": "100% (database is source of truth)"
        },
        "consolidated_files": {
            "purpose": "Archival and debugging only - query database for analysis",
            "files": [
                "graph_analysis.json",
                "security_analysis.json",
                "quality_analysis.json",
                "dependency_analysis.json",
                "infrastructure_analysis.json",
                "correlation_analysis.json"
            ]
        }
    }
