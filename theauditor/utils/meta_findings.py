"""
Meta-finding formatter for architectural insights.

This module provides utilities to format meta-analysis findings (from graph,
CFG, churn, coverage analyzers) into the standard findings_consolidated format
for dual-write pattern: database (FCE performance) + JSON (AI consumption).
"""
from __future__ import annotations


from datetime import datetime, UTC
from typing import Dict, Any, List, Optional


def format_meta_finding(
    finding_type: str,
    file_path: str,
    message: str,
    severity: str = "medium",
    line: int = 0,
    category: str = "architectural",
    confidence: float = 1.0,
    tool: str = "meta-analysis",
    additional_info: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Format a meta-analysis finding into standard findings_consolidated schema.

    Meta-findings are factual observations about code architecture, complexity,
    churn, and coverage. They maintain Truth Courier principles by reporting
    only verifiable facts without interpretation (unless from insights module).

    Args:
        finding_type: Type of meta-finding (e.g., "HOTSPOT", "HIGH_COMPLEXITY",
                     "HIGH_CHURN", "LOW_COVERAGE")
        file_path: Path to the file where finding was detected
        message: Human-readable description of the finding
        severity: Severity level ("critical", "high", "medium", "low")
        line: Line number (0 if file-level finding)
        category: Finding category (default: "architectural")
        confidence: Confidence score 0.0-1.0 (default: 1.0 for factual findings)
        tool: Tool name (default: "meta-analysis")
        additional_info: Optional dict of additional finding data

    Returns:
        Dict formatted for findings_consolidated table insertion

    Example:
        >>> format_meta_finding(
        ...     finding_type="ARCHITECTURAL_HOTSPOT",
        ...     file_path="src/core/auth.py",
        ...     message="High connectivity: 47 dependencies",
        ...     severity="high",
        ...     confidence=1.0
        ... )
        {
            'file': 'src/core/auth.py',
            'line': 0,
            'column': None,
            'rule': 'ARCHITECTURAL_HOTSPOT',
            'tool': 'meta-analysis',
            'message': 'High connectivity: 47 dependencies',
            'severity': 'high',
            'category': 'architectural',
            'confidence': 1.0,
            'code_snippet': None,
            'cwe': None,
            'timestamp': '2025-01-...',
            'additional_info': {...}
        }
    """
    return {
        'file': file_path,
        'line': line,
        'column': None,  # Meta-findings are typically file or line-level
        'rule': finding_type,
        'tool': tool,
        'message': message,
        'severity': severity,
        'category': category,
        'confidence': confidence,
        'code_snippet': None,  # Not applicable for meta-findings
        'cwe': None,  # Not applicable for architectural findings
        'timestamp': datetime.now(UTC).isoformat(),
        'additional_info': additional_info or {}
    }


def format_hotspot_finding(hotspot: dict[str, Any]) -> dict[str, Any]:
    """
    Format a graph hotspot into a standard finding.

    Args:
        hotspot: Hotspot dict from graph analyzer with fields:
                 - file or id: File path
                 - score or total_connections: Connectivity score
                 - in_degree, out_degree: Dependency counts

    Returns:
        Formatted finding dict
    """
    file_path = hotspot.get('file') or hotspot.get('id', 'unknown')
    score = hotspot.get('score', hotspot.get('total_connections', 0))
    in_deg = hotspot.get('in_degree', 0)
    out_deg = hotspot.get('out_degree', 0)

    # Determine severity based on connectivity score
    if score >= 50:
        severity = "critical"
    elif score >= 30:
        severity = "high"
    elif score >= 15:
        severity = "medium"
    else:
        severity = "low"

    message = (
        f"Architectural hotspot: {score:.0f} connections "
        f"({in_deg} incoming, {out_deg} outgoing)"
    )

    return format_meta_finding(
        finding_type="ARCHITECTURAL_HOTSPOT",
        file_path=file_path,
        message=message,
        severity=severity,
        category="architectural",
        confidence=1.0,
        tool="graph-analysis",
        additional_info=hotspot
    )


def format_cycle_finding(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Format a dependency cycle into findings (one per file in cycle).

    Args:
        cycle: Cycle dict from graph analyzer with fields:
               - nodes: List of files in cycle
               - size: Number of nodes in cycle

    Returns:
        List of formatted findings, one per file in cycle
    """
    findings = []
    nodes = cycle.get('nodes', [])
    size = cycle.get('size', len(nodes))

    # Severity based on cycle size
    if size >= 10:
        severity = "critical"
    elif size >= 5:
        severity = "high"
    else:
        severity = "medium"

    for file_path in nodes:
        if not file_path or str(file_path).startswith('external::'):
            continue

        message = f"Circular dependency: part of {size}-file dependency cycle"

        findings.append(format_meta_finding(
            finding_type="CIRCULAR_DEPENDENCY",
            file_path=file_path,
            message=message,
            severity=severity,
            category="architectural",
            confidence=1.0,
            tool="graph-analysis",
            additional_info={'cycle_size': size, 'cycle_nodes': nodes[:10]}  # Limit for size
        ))

    return findings


def format_complexity_finding(func_data: dict[str, Any]) -> dict[str, Any]:
    """
    Format a high-complexity function into a standard finding.

    Args:
        func_data: Function complexity dict from CFG analyzer with fields:
                   - file: File path
                   - function: Function name
                   - complexity: Cyclomatic complexity score
                   - start_line: Function start line
                   - block_count, has_loops: Additional metrics

    Returns:
        Formatted finding dict
    """
    file_path = func_data.get('file', 'unknown')
    function_name = func_data.get('function', 'unknown')
    complexity = func_data.get('complexity', 0)
    line = func_data.get('start_line', 0)

    # McCabe complexity guidelines
    if complexity >= 50:
        severity = "critical"
    elif complexity >= 21:
        severity = "high"
    elif complexity >= 11:
        severity = "medium"
    else:
        severity = "low"

    message = f"High cyclomatic complexity: {complexity} in function '{function_name}'"

    return format_meta_finding(
        finding_type="HIGH_CYCLOMATIC_COMPLEXITY",
        file_path=file_path,
        message=message,
        severity=severity,
        line=line,
        category="code_quality",
        confidence=1.0,
        tool="cfg-analysis",
        additional_info=func_data
    )


def format_churn_finding(file_data: dict[str, Any], threshold: int = 50) -> dict[str, Any] | None:
    """
    Format a high-churn file into a standard finding.

    Args:
        file_data: File churn dict from metadata collector with fields:
                   - path: File path
                   - commits_90d: Number of commits in last 90 days
                   - unique_authors: Number of distinct authors
                   - days_since_modified: Days since last modification
        threshold: Minimum commits to flag (default: 50)

    Returns:
        Formatted finding dict, or None if below threshold
    """
    file_path = file_data.get('path', 'unknown')
    commits = file_data.get('commits_90d', 0)
    authors = file_data.get('unique_authors', 0)
    days = file_data.get('days_since_modified', 0)

    if commits < threshold:
        return None

    # Severity based on commit frequency
    if commits >= 100:
        severity = "high"
    elif commits >= 75:
        severity = "medium"
    else:
        severity = "low"

    message = (
        f"High code churn: {commits} commits in 90 days "
        f"by {authors} author(s), last modified {days} days ago"
    )

    return format_meta_finding(
        finding_type="HIGH_CODE_CHURN",
        file_path=file_path,
        message=message,
        severity=severity,
        category="maintenance",
        confidence=1.0,
        tool="churn-analysis",
        additional_info=file_data
    )


def format_coverage_finding(file_data: dict[str, Any], threshold: float = 50.0) -> dict[str, Any] | None:
    """
    Format a low-coverage file into a standard finding.

    Args:
        file_data: File coverage dict from metadata collector with fields:
                   - path: File path
                   - line_coverage_percent: Coverage percentage
                   - lines_executed, lines_missing: Line counts
                   - uncovered_lines: List of uncovered line numbers
        threshold: Maximum coverage % to flag (default: 50%)

    Returns:
        Formatted finding dict, or None if above threshold
    """
    file_path = file_data.get('path', 'unknown')
    coverage_pct = file_data.get('line_coverage_percent', 100.0)
    lines_missing = file_data.get('lines_missing', 0)

    if coverage_pct >= threshold:
        return None

    # Severity based on coverage percentage
    if coverage_pct < 25:
        severity = "high"
    elif coverage_pct < 40:
        severity = "medium"
    else:
        severity = "low"

    message = (
        f"Low test coverage: {coverage_pct:.1f}% coverage "
        f"({lines_missing} uncovered lines)"
    )

    return format_meta_finding(
        finding_type="LOW_TEST_COVERAGE",
        file_path=file_path,
        message=message,
        severity=severity,
        category="testing",
        confidence=1.0,
        tool="coverage-analysis",
        additional_info=file_data
    )
