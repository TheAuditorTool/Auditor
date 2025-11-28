"""Centralized finding prioritization for internal organization."""

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
