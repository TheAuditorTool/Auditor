"""XSS vulnerability detection rules module - Framework-Aware Orchestrator.

This module orchestrates all XSS analyzers based on detected frameworks.
Dramatically reduces false positives by understanding framework context.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding

# Import all analyzers
from .xss_analyze import find_xss_issues
from .express_xss_analyze import find_express_xss
from .react_xss_analyze import find_react_xss
from .vue_xss_analyze import find_vue_xss
from .dom_xss_analyze import find_dom_xss
from .template_xss_analyze import find_template_injection


def find_all_xss_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Run all XSS analyzers based on detected frameworks.

    This is the main entry point for XSS detection.
    Runs appropriate analyzers based on framework context.

    Returns:
        Consolidated list of XSS findings with minimal false positives
    """
    findings = []

    if not context.db_path:
        return findings

    # Always run core XSS checks (framework-aware)
    findings.extend(find_xss_issues(context))

    # Get detected frameworks
    frameworks = _get_detected_frameworks(context)

    # Run framework-specific analyzers
    if 'express' in frameworks or 'express.js' in frameworks:
        findings.extend(find_express_xss(context))

    if 'react' in frameworks:
        findings.extend(find_react_xss(context))

    if 'vue' in frameworks or 'vuejs' in frameworks:
        findings.extend(find_vue_xss(context))

    # Always run specialized analyzers (they do their own filtering)
    findings.extend(find_dom_xss(context))
    findings.extend(find_template_injection(context))

    # Deduplicate findings
    seen = set()
    deduped = []

    for finding in findings:
        # Create unique key for each finding
        key = (finding.file_path, finding.line, finding.rule_name)

        if key not in seen:
            seen.add(key)
            deduped.append(finding)

    return deduped


def _get_detected_frameworks(context: StandardRuleContext) -> set:
    """Get list of detected frameworks from database."""
    frameworks = set()

    if not context.db_path:
        return frameworks

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT name FROM frameworks")

        for (name,) in cursor.fetchall():
            if name:
                frameworks.add(name.lower())

        conn.close()
    except Exception:
        # If frameworks table doesn't exist, return empty set
        pass

    return frameworks


# Export both new and legacy functions
__all__ = [
    'find_all_xss_issues',  # New framework-aware orchestrator
    'find_xss_issues',      # Core XSS analyzer
    'find_express_xss',     # Express-specific
    'find_react_xss',       # React-specific
    'find_vue_xss',         # Vue-specific
    'find_dom_xss',         # DOM XSS
    'find_template_injection',  # Template injection
]