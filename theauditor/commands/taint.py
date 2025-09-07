"""Perform taint analysis to detect security vulnerabilities via data flow tracking."""

import sys
import platform
import click
from pathlib import Path
from datetime import datetime, UTC
from theauditor.utils.error_handler import handle_exceptions

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"



@click.command("taint-analyze")
@handle_exceptions
@click.option("--db", default=None, help="Path to the SQLite database (default: repo_index.db)")
@click.option("--output", default="./.pf/raw/taint_analysis.json", help="Output path for analysis results")
@click.option("--max-depth", default=5, type=int, help="Maximum depth for taint propagation tracing")
@click.option("--json", is_flag=True, help="Output raw JSON instead of formatted report")
@click.option("--verbose", is_flag=True, help="Show detailed path information")
@click.option("--severity", type=click.Choice(["all", "critical", "high", "medium", "low"]), 
              default="all", help="Filter results by severity level")
@click.option("--rules/--no-rules", default=True, help="Enable/disable rule-based detection")
def taint_analyze(db, output, max_depth, json, verbose, severity, rules):
    """
    Perform taint analysis to detect security vulnerabilities.
    
    This command traces the flow of untrusted data from taint sources
    (user inputs) to security sinks (dangerous functions) to identify
    potential injection vulnerabilities and data exposure risks.
    
    The analysis detects:
    - SQL Injection
    - Command Injection  
    - Cross-Site Scripting (XSS)
    - Path Traversal
    - LDAP Injection
    - NoSQL Injection
    
    Example:
        aud taint-analyze
        aud taint-analyze --severity critical --verbose
        aud taint-analyze --json --output vulns.json
    """
    from theauditor.taint_analyzer import trace_taint, save_taint_analysis, normalize_taint_path, SECURITY_SINKS
    from theauditor.taint.insights import format_taint_report, calculate_severity, generate_summary, classify_vulnerability
    from theauditor.config_runtime import load_runtime_config
    from theauditor.rules.orchestrator import RulesOrchestrator, RuleContext
    from theauditor.taint.registry import TaintRegistry
    import json as json_lib
    
    # Load configuration for default paths
    config = load_runtime_config(".")
    
    # Use default database path if not provided
    if db is None:
        db = config["paths"]["db"]
    
    # Verify database exists
    db_path = Path(db)
    if not db_path.exists():
        click.echo(f"Error: Database not found at {db}", err=True)
        click.echo("Run 'aud index' first to build the repository index", err=True)
        raise click.ClickException(f"Database not found: {db}")
    
    # Check if rules are enabled
    if rules:
        # STAGE 1: Initialize infrastructure
        click.echo("Initializing security analysis infrastructure...")
        registry = TaintRegistry()
        orchestrator = RulesOrchestrator(project_path=Path("."), db_path=db_path)
        
        # Track all findings
        all_findings = []
        
        # STAGE 2: Run standalone infrastructure rules
        click.echo("Running infrastructure and configuration analysis...")
        infra_findings = orchestrator.run_standalone_rules()
        all_findings.extend(infra_findings)
        click.echo(f"  Found {len(infra_findings)} infrastructure issues")
        
        # STAGE 3: Run discovery rules to populate registry
        click.echo("Discovering framework-specific patterns...")
        discovery_findings = orchestrator.run_discovery_rules(registry)
        all_findings.extend(discovery_findings)
        
        stats = registry.get_stats()
        click.echo(f"  Registry now has {stats['total_sinks']} sinks, {stats['total_sources']} sources")
        
        # STAGE 4: Run enriched taint analysis with registry
        click.echo("Performing data-flow taint analysis...")
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth,
            registry=registry
        )
        
        # Extract taint paths
        taint_paths = result.get("taint_paths", result.get("paths", []))
        click.echo(f"  Found {len(taint_paths)} taint flow vulnerabilities")
        
        # STAGE 5: Run taint-dependent rules
        click.echo("Running advanced security analysis...")
        
        # Create taint checker from results
        def taint_checker(var_name, line_num=None):
            """Check if variable is in any taint path."""
            for path in taint_paths:
                # Check source
                if path.get("source", {}).get("name") == var_name:
                    return True
                # Check sink
                if path.get("sink", {}).get("name") == var_name:
                    return True
                # Check intermediate steps
                for step in path.get("path", []):
                    if isinstance(step, dict) and step.get("name") == var_name:
                        return True
            return False
        
        advanced_findings = orchestrator.run_taint_dependent_rules(taint_checker)
        all_findings.extend(advanced_findings)
        click.echo(f"  Found {len(advanced_findings)} advanced security issues")
        
        # STAGE 6: Consolidate all findings
        click.echo(f"\nTotal vulnerabilities found: {len(all_findings) + len(taint_paths)}")
        
        # Add all non-taint findings to result
        result["infrastructure_issues"] = infra_findings
        result["discovery_findings"] = discovery_findings
        result["advanced_findings"] = advanced_findings
        result["all_rule_findings"] = all_findings
        
        # Update total count
        result["total_vulnerabilities"] = len(taint_paths) + len(all_findings)
    else:
        # Original taint analysis without orchestrator
        click.echo("Performing taint analysis (rules disabled)...")
        result = trace_taint(
            db_path=str(db_path),
            max_depth=max_depth
        )
    
    # Enrich raw paths with interpretive insights
    if result.get("success"):
        # Add severity and classification to each path
        enriched_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            # Normalize the path first
            path = normalize_taint_path(path)
            # Add severity
            path["severity"] = calculate_severity(path)
            # Enrich sink information with vulnerability classification
            path["vulnerability_type"] = classify_vulnerability(
                path.get("sink", {}), 
                SECURITY_SINKS
            )
            enriched_paths.append(path)
        
        # Update result with enriched paths
        result["taint_paths"] = enriched_paths
        result["paths"] = enriched_paths
        
        # Generate summary
        result["summary"] = generate_summary(enriched_paths)
    
    # Filter by severity if requested
    if severity != "all" and result.get("success"):
        filtered_paths = []
        for path in result.get("taint_paths", result.get("paths", [])):
            # Normalize the path to ensure all keys exist
            path = normalize_taint_path(path)
            if path["severity"].lower() == severity or (
                severity == "critical" and path["severity"].lower() == "critical"
            ) or (
                severity == "high" and path["severity"].lower() in ["critical", "high"]
            ):
                filtered_paths.append(path)
        
        # Update counts
        result["taint_paths"] = filtered_paths
        result["paths"] = filtered_paths  # Keep both keys synchronized
        result["total_vulnerabilities"] = len(filtered_paths)
        
        # Recalculate vulnerability types
        from collections import defaultdict
        vuln_counts = defaultdict(int)
        for path in filtered_paths:
            # Path is already normalized from filtering above
            vuln_counts[path.get("vulnerability_type", "Unknown")] += 1
        result["vulnerabilities_by_type"] = dict(vuln_counts)
        
        # CRITICAL FIX: Recalculate summary with filtered paths
        from theauditor.taint.insights import generate_summary
        result["summary"] = generate_summary(filtered_paths)
    
    # Save COMPLETE taint analysis results to raw (including all data)
    save_taint_analysis(result, output)
    click.echo(f"Raw analysis results saved to: {output}")
    
    # Output results
    if json:
        # JSON output for programmatic use
        click.echo(json_lib.dumps(result, indent=2, sort_keys=True))
    else:
        # Human-readable report
        report = format_taint_report(result)
        click.echo(report)
        
        # Additional verbose output
        if verbose and result.get("success"):
            paths = result.get("taint_paths", result.get("paths", []))
            if paths and len(paths) > 10:
                click.echo("\n" + "=" * 60)
                click.echo("ADDITIONAL VULNERABILITY DETAILS")
                click.echo("=" * 60)
                
                for i, path in enumerate(paths[10:20], 11):
                    # Normalize path to ensure all keys exist
                    path = normalize_taint_path(path)
                    click.echo(f"\n{i}. {path['vulnerability_type']} ({path['severity']})")
                    click.echo(f"   Source: {path['source']['file']}:{path['source']['line']}")
                    click.echo(f"   Sink: {path['sink']['file']}:{path['sink']['line']}")
                    arrow = "->" if IS_WINDOWS else "→"
                    click.echo(f"   Pattern: {path['source'].get('pattern', '')} {arrow} {path['sink'].get('pattern', '')}")  # Empty not unknown
                
                if len(paths) > 20:
                    click.echo(f"\n... and {len(paths) - 20} additional vulnerabilities not shown")
    
    # Provide actionable recommendations based on findings
    if not json and result.get("success"):
        summary = result.get("summary", {})
        risk_level = summary.get("risk_level", "UNKNOWN")
        
        click.echo("\n" + "=" * 60)
        click.echo("RECOMMENDED ACTIONS")
        click.echo("=" * 60)
        
        if risk_level == "CRITICAL":
            click.echo("[CRITICAL] CRITICAL SECURITY ISSUES DETECTED")
            click.echo("1. Review and fix all CRITICAL vulnerabilities immediately")
            click.echo("2. Add input validation and sanitization at all entry points")
            click.echo("3. Use parameterized queries for all database operations")
            click.echo("4. Implement output encoding for all user-controlled data")
            click.echo("5. Consider a security audit before deployment")
        elif risk_level == "HIGH":
            click.echo("[HIGH] HIGH RISK VULNERABILITIES FOUND")
            click.echo("1. Prioritize fixing HIGH severity issues this sprint")
            click.echo("2. Review all user input handling code")
            click.echo("3. Implement security middleware/filters")
            click.echo("4. Add security tests for vulnerable paths")
        elif risk_level == "MEDIUM":
            click.echo("[MEDIUM] MODERATE SECURITY CONCERNS")
            click.echo("1. Schedule vulnerability fixes for next sprint")
            click.echo("2. Review and update security best practices")
            click.echo("3. Add input validation where missing")
        else:
            click.echo("[LOW] LOW RISK PROFILE")
            click.echo("1. Continue following secure coding practices")
            click.echo("2. Regular security scanning recommended")
            click.echo("3. Keep dependencies updated")
    
    # Exit with appropriate code
    if result.get("success"):
        summary = result.get("summary", {})
        if summary.get("critical_count", 0) > 0:
            exit(2)  # Critical vulnerabilities found
        elif summary.get("high_count", 0) > 0:
            exit(1)  # High severity vulnerabilities found
    else:
        raise click.ClickException(result.get("error", "Analysis failed"))