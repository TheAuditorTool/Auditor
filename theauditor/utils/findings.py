"""Finding prioritization, normalization, and formatting utilities."""

from datetime import UTC, datetime
from typing import Any

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "warning": 4,
    "info": 5,
    "style": 6,
    "unknown": 7,
}


TOOL_IMPORTANCE = {
    "taint-analyzer": 0,
    "vulnerability-scanner": 0,
    "security-rules": 0,
    "sql-injection": 0,
    "xss-detector": 0,
    "docker-analyzer": 0,
    "pattern-detector": 1,
    "orm": 1,
    "database-rules": 1,
    "fce": 2,
    "test": 2,
    "pytest": 2,
    "jest": 2,
    "ml": 3,
    "graph": 3,
    "dependency": 3,
    "deps": 3,
    "ruff": 4,
    "mypy": 4,
    "bandit": 4,
    "pylint": 4,
    "eslint": 5,
    "prettier": 6,
    "format": 7,
    "beautifier": 7,
}


SEVERITY_MAPPINGS = {
    4: "critical",
    3: "high",
    2: "medium",
    1: "low",
    0: "info",
    "error": "high",
    "warning": "medium",
    "warn": "medium",
    "info": "low",
    "note": "low",
    "debug": "low",
    "fatal": "critical",
    "blocker": "critical",
    "major": "high",
    "minor": "low",
    "trivial": "low",
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "style": "style",
    "formatting": "style",
}


def normalize_severity(severity_value):
    """Normalize severity from various formats to standard string."""
    if severity_value is None:
        return "warning"

    if isinstance(severity_value, (int, float)):
        if isinstance(severity_value, float) and 0.0 <= severity_value <= 1.0:
            if severity_value >= 0.9:
                return "critical"
            elif severity_value >= 0.7:
                return "high"
            elif severity_value >= 0.4:
                return "medium"
            else:
                return "low"

        return SEVERITY_MAPPINGS.get(int(severity_value), "warning")

    severity_str = str(severity_value).lower().strip()

    if severity_str in PRIORITY_ORDER:
        return severity_str

    return SEVERITY_MAPPINGS.get(severity_str, "warning")


def get_sort_key(finding):
    """Generate sort key for a finding."""
    normalized_severity = normalize_severity(finding.get("severity"))
    tool_name = str(finding.get("tool", "unknown")).lower()

    return (
        PRIORITY_ORDER.get(normalized_severity, 7),
        TOOL_IMPORTANCE.get(tool_name, 8),
        finding.get("file", "zzz"),
        finding.get("line", 999999),
    )


def sort_findings(findings):
    """Sort findings by priority for optimal report organization."""
    if not findings:
        return findings

    return sorted(findings, key=get_sort_key)


def format_meta_finding(
    finding_type: str,
    file_path: str,
    message: str,
    severity: str = "medium",
    line: int = 0,
    category: str = "architectural",
    confidence: float = 1.0,
    tool: str = "meta-analysis",
    additional_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format a meta-analysis finding into standard findings_consolidated schema."""
    return {
        "file": file_path,
        "line": line,
        "column": None,
        "rule": finding_type,
        "tool": tool,
        "message": message,
        "severity": severity,
        "category": category,
        "confidence": confidence,
        "code_snippet": None,
        "cwe": None,
        "timestamp": datetime.now(UTC).isoformat(),
        "additional_info": additional_info or {},
    }


def format_hotspot_finding(hotspot: dict[str, Any]) -> dict[str, Any]:
    """Format a graph hotspot into a standard finding."""
    file_path = hotspot.get("file") or hotspot.get("id", "unknown")
    score = hotspot.get("score", hotspot.get("total_connections", 0))
    in_deg = hotspot.get("in_degree", 0)
    out_deg = hotspot.get("out_degree", 0)

    if score >= 50:
        severity = "critical"
    elif score >= 30:
        severity = "high"
    elif score >= 15:
        severity = "medium"
    else:
        severity = "low"

    message = (
        f"Architectural hotspot: {score:.0f} connections ({in_deg} incoming, {out_deg} outgoing)"
    )

    return format_meta_finding(
        finding_type="ARCHITECTURAL_HOTSPOT",
        file_path=file_path,
        message=message,
        severity=severity,
        category="architectural",
        confidence=1.0,
        tool="graph-analysis",
        additional_info=hotspot,
    )


def format_cycle_finding(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    """Format a dependency cycle into findings (one per file in cycle)."""
    findings = []
    nodes = cycle.get("nodes", [])
    size = cycle.get("size", len(nodes))

    if size >= 10:
        severity = "critical"
    elif size >= 5:
        severity = "high"
    else:
        severity = "medium"

    for file_path in nodes:
        if not file_path or str(file_path).startswith("external::"):
            continue

        message = f"Circular dependency: part of {size}-file dependency cycle"

        findings.append(
            format_meta_finding(
                finding_type="CIRCULAR_DEPENDENCY",
                file_path=file_path,
                message=message,
                severity=severity,
                category="architectural",
                confidence=1.0,
                tool="graph-analysis",
                additional_info={"cycle_size": size, "cycle_nodes": nodes[:10]},
            )
        )

    return findings


def format_complexity_finding(func_data: dict[str, Any]) -> dict[str, Any]:
    """Format a high-complexity function into a standard finding."""
    file_path = func_data.get("file", "unknown")
    function_name = func_data.get("function", "unknown")
    complexity = func_data.get("complexity", 0)
    line = func_data.get("start_line", 0)

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
        additional_info=func_data,
    )


def format_churn_finding(file_data: dict[str, Any], threshold: int = 50) -> dict[str, Any] | None:
    """Format a high-churn file into a standard finding."""
    file_path = file_data.get("path", "unknown")
    commits = file_data.get("commits_90d", 0)
    authors = file_data.get("unique_authors", 0)
    days = file_data.get("days_since_modified", 0)

    if commits < threshold:
        return None

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
        additional_info=file_data,
    )


def format_coverage_finding(
    file_data: dict[str, Any], threshold: float = 50.0
) -> dict[str, Any] | None:
    """Format a low-coverage file into a standard finding."""
    file_path = file_data.get("path", "unknown")
    coverage_pct = file_data.get("line_coverage_percent", 100.0)
    lines_missing = file_data.get("lines_missing", 0)

    if coverage_pct >= threshold:
        return None

    if coverage_pct < 25:
        severity = "high"
    elif coverage_pct < 40:
        severity = "medium"
    else:
        severity = "low"

    message = f"Low test coverage: {coverage_pct:.1f}% coverage ({lines_missing} uncovered lines)"

    return format_meta_finding(
        finding_type="LOW_TEST_COVERAGE",
        file_path=file_path,
        message=message,
        severity=severity,
        category="testing",
        confidence=1.0,
        tool="coverage-analysis",
        additional_info=file_data,
    )
