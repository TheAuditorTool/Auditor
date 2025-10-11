"""Interpretive intelligence layer for taint analysis - optional severity scoring and vulnerability classification."""

import platform
from collections import defaultdict
from typing import Any

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


def calculate_severity(path_data: dict[str, Any]) -> str:
    """
    Calculate severity based on vulnerability type and path complexity.
    This is interpretive logic that assigns risk levels.
    
    Args:
        path_data: Dictionary with vulnerability_type and path information
        
    Returns:
        Severity level: "critical", "high", "medium", or "low"
    """
    vulnerability_type = path_data.get("vulnerability_type", "")
    path_length = len(path_data.get("path", []))

    high_severity = ["SQL Injection", "Command Injection", "NoSQL Injection"]
    medium_severity = ["Cross-Site Scripting (XSS)", "Path Traversal", "LDAP Injection"]

    if vulnerability_type in high_severity:
        return "critical" if path_length <= 2 else "high"
    elif vulnerability_type in medium_severity:
        return "high" if path_length <= 2 else "medium"
    else:
        return "medium" if path_length <= 3 else "low"


def classify_vulnerability(sink: dict[str, Any], security_sinks: dict[str, list[str]]) -> str:
    """
    Classify the vulnerability based on sink type.
    This is interpretive logic that categorizes vulnerabilities.
    
    Args:
        sink: Sink dictionary with name
        security_sinks: Mapping of vulnerability types to sink patterns
        
    Returns:
        Human-readable vulnerability type
    """
    sink_name = sink["name"].lower() if "name" in sink else ""

    for vuln_type, sinks in security_sinks.items():
        if any(s.lower() in sink_name for s in sinks):
            return {
                "sql": "SQL Injection",
                "command": "Command Injection",
                "xss": "Cross-Site Scripting (XSS)",
                "path": "Path Traversal",
                "ldap": "LDAP Injection",
                "nosql": "NoSQL Injection"
            }.get(vuln_type, vuln_type.upper())

    return "Data Exposure"


def is_vulnerable_sink(sink: dict[str, Any], metadata: dict[str, Any] | None = None) -> bool:
    """
    Check if a sink is actually vulnerable based on metadata from truth courier.
    This is interpretive logic that makes security judgments on top of facts.

    The truth courier (taint/database.py) provides metadata about sinks including:
    - risk_level: "high", "medium", "low"
    - risk_factors: List of risk indicators
    - query_text: The actual query string (for SQL)
    - arguments: Function call arguments

    This function interprets that metadata to judge vulnerability.

    Args:
        sink: Sink dictionary with name and category
        metadata: Pre-computed metadata from taint analyzer (sink.get("metadata"))

    Returns:
        True if the sink is judged to be vulnerable, False if safe
    """
    # Extract metadata (may be None if not provided by truth courier)
    risk_metadata = metadata or {}
    sink_category = sink.get("category", "")
    sink_name = sink.get("name", "").lower()

    # SQL injection context checking
    if sink_category == "sql" or "execute" in sink_name or "query" in sink_name:
        # Use risk_level from truth courier if available
        risk_level = risk_metadata.get("risk_level", "medium")

        # High risk SQL operations are vulnerable
        if risk_level == "high":
            return True

        # Check risk_factors for specific patterns
        risk_factors = risk_metadata.get("risk_factors", [])

        # Safe patterns (parameterization, prepared statements)
        safe_indicators = [
            "parameterized",
            "prepared_statement",
            "orm_safe",
            "bound_parameters"
        ]

        for indicator in safe_indicators:
            if indicator in risk_factors:
                return False  # Not vulnerable - using safe pattern

        # Dangerous patterns (string concatenation, dynamic SQL)
        dangerous_indicators = [
            "string_concatenation",
            "format_string",
            "dynamic_sql",
            "user_controlled"
        ]

        for indicator in dangerous_indicators:
            if indicator in risk_factors:
                return True  # Vulnerable - using dangerous pattern

        # Default: medium risk is considered vulnerable
        return risk_level in ["high", "medium"]

    # Command injection context checking
    elif sink_category == "command" or any(cmd in sink_name for cmd in ["system", "exec", "spawn"]):
        risk_level = risk_metadata.get("risk_level", "medium")
        risk_factors = risk_metadata.get("risk_factors", [])

        # Check for safe execution patterns
        if "shell_false" in risk_factors or "escaped" in risk_factors:
            return False  # Not vulnerable - using safe execution

        # High/medium risk command operations are vulnerable
        return risk_level in ["high", "medium"]

    # Path traversal context checking
    elif sink_category == "path":
        risk_level = risk_metadata.get("risk_level", "medium")
        risk_factors = risk_metadata.get("risk_factors", [])

        # Check for sanitization
        if "sanitized" in risk_factors or "normalized" in risk_factors:
            return False  # Path is sanitized

        # High/medium risk path operations are vulnerable
        return risk_level in ["high", "medium"]

    # XSS and other categories
    elif sink_category in ["xss", "html", "dom"]:
        risk_level = risk_metadata.get("risk_level", "medium")
        risk_factors = risk_metadata.get("risk_factors", [])

        # Check for safe rendering
        if "escaped" in risk_factors or "sanitized" in risk_factors:
            return False

        return risk_level in ["high", "medium"]

    # Default: consider it vulnerable if we can't prove it's safe
    # This is the conservative security posture
    return True


def generate_summary(paths: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate a summary of the taint analysis results.
    This is interpretive logic that creates risk assessments and recommendations.
    
    Args:
        paths: List of taint path dictionaries
        
    Returns:
        Summary with risk levels and recommendations
    """
    if not paths:
        return {
            "risk_level": "low",
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "recommendation": "No direct taint paths found. Continue monitoring for indirect flows."
        }

    severity_counts = defaultdict(int)
    for path in paths:
        # Calculate severity for each path
        severity = calculate_severity(path)
        severity_counts[severity] += 1

    # Determine overall risk level with clear explanation
    critical_count = severity_counts.get("critical", 0)
    high_count = severity_counts.get("high", 0)
    medium_count = severity_counts.get("medium", 0)
    low_count = severity_counts.get("low", 0)

    if critical_count > 0:
        risk_level = "critical"
        recommendation = f"URGENT: Critical risk level assigned due to {critical_count} critical-severity vulnerability(ies). Immediate remediation required!"
    elif high_count > 2:
        risk_level = "high"
        recommendation = f"High risk level assigned due to {high_count} high-severity vulnerabilities. Priority remediation needed."
    elif high_count > 0:
        risk_level = "medium"
        recommendation = f"Medium risk level assigned due to {high_count} high-severity vulnerability(ies) found. Schedule remediation in next sprint."
    elif medium_count > 5:
        risk_level = "medium"
        recommendation = f"Medium risk level assigned due to high volume ({medium_count}) of medium-severity findings. Review and prioritize fixes."
    else:
        risk_level = "low"
        recommendation = f"Low risk level assigned. Found {medium_count} medium and {low_count} low severity issues. Review and address as time permits."

    return {
        "risk_level": risk_level,
        "critical_count": severity_counts.get("critical", 0),
        "high_count": severity_counts.get("high", 0),
        "medium_count": severity_counts.get("medium", 0),
        "low_count": severity_counts.get("low", 0),
        "recommendation": recommendation,
        "most_common_vulnerability": max(
            [(v, k) for k, v in severity_counts.items()],
            default=(0, "None")
        )[1] if paths else "None"
    }


def format_taint_report(analysis_result: dict[str, Any]) -> str:
    """
    Format taint analysis results into a human-readable report.
    This is interpretive presentation logic.
    
    Args:
        analysis_result: Raw analysis results from trace_taint
        
    Returns:
        Formatted string report
    """
    lines = []

    # Use ASCII characters on Windows, Unicode elsewhere
    if IS_WINDOWS:
        border_char = "="
        section_char = "-"
        arrow = "->"
    else:
        border_char = "="
        section_char = "─"
        arrow = "→"

    # Header
    lines.append(border_char * 60)
    lines.append("TAINT ANALYSIS SECURITY REPORT")
    lines.append(border_char * 60)

    if not analysis_result.get("success"):
        lines.append(f"\nError: {analysis_result.get('error', 'Unknown error')}")
        return "\n".join(lines)

    # Summary
    summary = analysis_result.get("summary", {})
    lines.append(f"\nRisk Level: {summary.get('risk_level', '').upper()}")
    lines.append(f"Recommendation: {summary.get('recommendation', '')}")

    # Statistics
    lines.append(f"\n{section_char * 40}")
    lines.append("SCAN STATISTICS")
    lines.append(f"{section_char * 40}")
    lines.append(f"Taint Sources Found: {analysis_result.get('sources_found', 0)}")
    lines.append(f"Security Sinks Found: {analysis_result.get('sinks_found', 0)}")
    lines.append(f"Total Vulnerabilities: {analysis_result.get('total_vulnerabilities', 0)}")

    # Vulnerabilities by type
    vuln_types = analysis_result.get("vulnerabilities_by_type", {})
    if vuln_types:
        lines.append(f"\n{section_char * 40}")
        lines.append("VULNERABILITIES BY TYPE")
        lines.append(f"{section_char * 40}")
        for vuln_type, count in sorted(vuln_types.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {vuln_type}: {count}")

    # Severity breakdown
    lines.append(f"\n{section_char * 40}")
    lines.append("SEVERITY BREAKDOWN")
    lines.append(f"{section_char * 40}")
    lines.append(f"  CRITICAL: {summary.get('critical_count', 0)}")
    lines.append(f"  HIGH: {summary.get('high_count', 0)}")
    lines.append(f"  MEDIUM: {summary.get('medium_count', 0)}")
    lines.append(f"  LOW: {summary.get('low_count', 0)}")

    # Detailed paths (limit to top 10)
    # Handle both "taint_paths" and "paths" keys for compatibility
    paths = analysis_result.get("taint_paths", analysis_result.get("paths", []))
    if paths:
        lines.append(f"\n{section_char * 40}")
        lines.append("TOP VULNERABILITY PATHS")
        lines.append(f"{section_char * 40}")

        # Sort by severity
        sorted_paths = sorted(paths, key=lambda p: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(p.get("severity", "unknown"), 4),
            p.get("path_length", 0)
        ))

        for i, path in enumerate(sorted_paths[:10], 1):
            lines.append(f"\n{i}. {path.get('vulnerability_type', 'Unknown')} ({path.get('severity', 'unknown').upper()})")
            lines.append(f"   Source: {path.get('source', {}).get('name', '')} at {path.get('source', {}).get('file', '')}:{path.get('source', {}).get('line', 0)}")
            lines.append(f"   Sink: {path.get('sink', {}).get('name', '')} at {path.get('sink', {}).get('file', '')}:{path.get('sink', {}).get('line', 0)}")
            lines.append(f"   Path Length: {path.get('path_length', 0)} steps")

            if len(path.get('path', [])) <= 4:
                lines.append("   Flow:")
                for step in path.get('path', []):
                    if isinstance(step, dict):
                        lines.append(f"     {arrow} {step.get('name', '')}")

    lines.append("\n" + border_char * 60)

    return "\n".join(lines)


def get_taint_summary(taint_data: dict[str, Any]) -> dict[str, Any]:
    """
    Distill potentially large taint analysis data into a concise, AI-readable summary.
    This is interpretive intelligence that extracts key insights.
    
    This function solves the "200MB file paradox" by extracting key insights
    from large taint analysis results that the AI cannot read directly.
    
    Args:
        taint_data: Large taint analysis dict with vulnerability paths
        
    Returns:
        Concise summary (<1MB) with key security insights
    """
    vulnerabilities = taint_data.get("vulnerabilities", [])

    # Count vulnerabilities by type
    vuln_by_type = defaultdict(int)
    vuln_by_severity = defaultdict(int)
    source_files = set()
    sink_files = set()

    for vuln in vulnerabilities:
        # Categorize by type
        vuln_type = vuln.get("vulnerability_type", "")  # Empty not unknown
        vuln_by_type[vuln_type] += 1

        # Categorize by severity
        severity = vuln.get("severity", "medium")
        vuln_by_severity[severity] += 1

        # Track source and sink files
        if "source" in vuln:
            source_files.add(vuln["source"].get("file", ""))  # Empty not unknown
        if "sink" in vuln:
            sink_files.add(vuln["sink"].get("file", ""))  # Empty not unknown

    # Find top risky source files (files that originate the most vulnerabilities)
    source_file_counts = defaultdict(int)
    for vuln in vulnerabilities[:100]:  # Limit for efficiency
        if "source" in vuln:
            source_file = vuln["source"].get("file", "")  # Empty not unknown
            source_file_counts[source_file] += 1

    top_source_files = sorted(
        source_file_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    # Find top vulnerable sinks (functions that are most frequently vulnerable)
    sink_counts = defaultdict(int)
    for vuln in vulnerabilities[:100]:  # Limit for efficiency
        if "sink" in vuln:
            sink_name = vuln["sink"].get("name", "")  # Empty not unknown
            sink_counts[sink_name] += 1

    top_sinks = sorted(
        sink_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    # Extract critical vulnerabilities (first 5 high/critical severity)
    critical_vulns = []
    for vuln in vulnerabilities:
        if vuln.get("severity") in ["critical", "high"] and len(critical_vulns) < 5:
            # Create a condensed version
            critical_vulns.append({
                "type": vuln.get("vulnerability_type", ""),  # Empty not unknown
                "severity": vuln.get("severity"),
                "source": f"{vuln.get('source', {}).get('file', '')}:{vuln.get('source', {}).get('line', 0)}",  # Empty not unknown
                "sink": f"{vuln.get('sink', {}).get('file', '')}:{vuln.get('sink', {}).get('line', 0)}",  # Empty not unknown
                "path_length": len(vuln.get("path", []))
            })

    # Create summary
    summary = {
        "statistics": {
            "total_vulnerabilities": len(vulnerabilities),
            "unique_source_files": len(source_files),
            "unique_sink_files": len(sink_files),
            "total_paths_analyzed": taint_data.get("total_paths", 0)
        },
        "vulnerabilities_by_type": dict(vuln_by_type),
        "vulnerabilities_by_severity": dict(vuln_by_severity),
        "top_risky_source_files": [
            {"file": file, "vulnerability_count": count}
            for file, count in top_source_files
        ],
        "top_vulnerable_sinks": [
            {"sink": sink, "occurrence_count": count}
            for sink, count in top_sinks
        ],
        "critical_vulnerabilities": critical_vulns,
        "security_insights": {
            "has_sql_injection": vuln_by_type.get("sql_injection", 0) > 0,
            "has_xss": vuln_by_type.get("xss", 0) > 0,
            "has_command_injection": vuln_by_type.get("command_injection", 0) > 0,
            "has_path_traversal": vuln_by_type.get("path_traversal", 0) > 0,
            "critical_count": vuln_by_severity.get("critical", 0),
            "high_count": vuln_by_severity.get("high", 0),
            "risk_level": "critical" if vuln_by_severity.get("critical", 0) > 0
                         else "high" if vuln_by_severity.get("high", 0) > 5
                         else "medium" if len(vulnerabilities) > 10
                         else "low"
        }
    }

    return summary
