"""Centralized finding prioritization for internal organization.

This module provides consistent sorting of findings to ensure
critical security issues appear before style warnings in reports.
This is NOT severity mapping for tools, but internal organization
for optimal AI context utilization.
"""
from __future__ import annotations


# Priority order for internal organization (lower = higher priority)
# This is our SINGLE SOURCE OF TRUTH for severity ranking
PRIORITY_ORDER = {
    "critical": 0,  # Immediate security threats
    "high": 1,      # Serious bugs/vulnerabilities  
    "medium": 2,    # Should fix soon
    "low": 3,       # Minor issues
    "warning": 4,   # Potential problems
    "info": 5,      # Informational
    "style": 6,     # Code style/formatting
    "unknown": 7    # Unrecognized severity
}

# Tool importance for secondary sorting (lower = more important)
# Security tools rank higher than style tools
TOOL_IMPORTANCE = {
    # Security tools - highest importance
    "taint-analyzer": 0,
    "vulnerability-scanner": 0,
    "security-rules": 0,
    "sql-injection": 0,
    "xss-detector": 0,
    "docker-analyzer": 0,  # Docker security findings
    
    # Pattern detection
    "pattern-detector": 1,
    "orm": 1,
    "database-rules": 1,
    
    # Testing and validation
    "fce": 2,
    "test": 2,
    "pytest": 2,
    "jest": 2,
    
    # Analysis tools
    "ml": 3,
    "graph": 3,
    "dependency": 3,
    "deps": 3,
    
    # Code quality
    "ruff": 4,
    "mypy": 4,
    "bandit": 4,
    "pylint": 4,
    
    # Style tools - lowest importance
    "eslint": 5,
    "prettier": 6,
    "format": 7,
    "beautifier": 7
}

# Comprehensive severity normalization mappings
# Handles all formats: integers, strings, alternatives
SEVERITY_MAPPINGS = {
    # Integer mappings (Docker uses 4=critical, CVE uses 1-4 scale)
    4: "critical",  # Docker's highest
    3: "high",
    2: "medium",
    1: "low",
    0: "info",      # Sometimes used for informational
    
    # String alternatives from various tools
    "error": "high",        # ESLint, many linters
    "warning": "medium",    # Standard warning
    "warn": "medium",       # Prettier variant
    "info": "low",          # Informational
    "note": "low",          # Ruff uses this
    "debug": "low",         # Debug-level issues
    "fatal": "critical",    # Some tools use fatal
    "blocker": "critical",  # Severity naming from bug trackers
    "major": "high",        
    "minor": "low",
    "trivial": "low",
    
    # Pass-through for already normalized
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    
    # Style-specific (for prettier/eslint)
    "style": "style",
    "formatting": "style"
}

def normalize_severity(severity_value):
    """Normalize severity from various formats to standard string.
    
    Handles integers (Docker), floats (ML confidence), strings (ESLint),
    and missing values (test failures).
    
    Args:
        severity_value: Can be int, float, string, or None
        
    Returns:
        Normalized severity string from PRIORITY_ORDER keys
    """
    if severity_value is None:
        return "warning"  # Default for missing severity
    
    # Handle numeric types
    if isinstance(severity_value, (int, float)):
        # ML confidence scores (0.0-1.0)
        if isinstance(severity_value, float) and 0.0 <= severity_value <= 1.0:
            if severity_value >= 0.9:
                return "critical"
            elif severity_value >= 0.7:
                return "high"
            elif severity_value >= 0.4:
                return "medium"
            else:
                return "low"
        # Integer severity (Docker style, CVE scores)
        return SEVERITY_MAPPINGS.get(int(severity_value), "warning")
    
    # Handle string types
    severity_str = str(severity_value).lower().strip()
    
    # Check if it's already a valid normalized severity
    if severity_str in PRIORITY_ORDER:
        return severity_str
    
    # Try to map it
    return SEVERITY_MAPPINGS.get(severity_str, "warning")

def get_sort_key(finding):
    """Generate sort key for a finding.
    
    Multi-level sort: severity -> tool -> file -> line
    
    Args:
        finding: Dictionary with severity, tool, file, line fields
        
    Returns:
        Tuple for sorting (lower values = higher priority)
    """
    # Normalize severity to handle all formats
    normalized_severity = normalize_severity(finding.get("severity"))
    
    # Get tool name, handle missing
    tool_name = str(finding.get("tool", "unknown")).lower()
    
    # Build sort key with defaults for missing fields
    return (
        PRIORITY_ORDER.get(normalized_severity, 7),      # Severity priority
        TOOL_IMPORTANCE.get(tool_name, 8),               # Tool priority
        finding.get("file", "zzz"),                      # File path
        finding.get("line", 999999)                      # Line number
    )

def sort_findings(findings):
    """Sort findings by priority for optimal report organization.
    
    Critical security issues will appear first, style issues last.
    This ensures AI sees the most important issues within its
    limited context window.
    
    Args:
        findings: List of finding dictionaries
        
    Returns:
        New sorted list (original unchanged)
    """
    if not findings:
        return findings
    
    return sorted(findings, key=get_sort_key)