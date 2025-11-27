"""XSS vulnerability detection rules module - Framework-Aware Orchestrator.

This module orchestrates all XSS analyzers based on detected frameworks.
Dramatically reduces false positives by understanding framework context.
"""

import sqlite3

from theauditor.rules.base import StandardFinding, StandardRuleContext

from .dom_xss_analyze import find_dom_xss
from .express_xss_analyze import find_express_xss
from .react_xss_analyze import find_react_xss
from .template_xss_analyze import find_template_injection
from .vue_xss_analyze import find_vue_xss
from .xss_analyze import find_xss_issues


def find_all_xss_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Run all XSS analyzers based on detected frameworks.

    This is the main entry point for XSS detection.
    Runs appropriate analyzers based on framework context.

    Returns:
        Consolidated list of XSS findings with minimal false positives
    """
    findings = []

    if not context.db_path:
        return findings

    findings.extend(find_xss_issues(context))

    frameworks = _get_detected_frameworks(context)

    if "express" in frameworks or "express.js" in frameworks:
        findings.extend(find_express_xss(context))

    if "react" in frameworks:
        findings.extend(find_react_xss(context))

    if "vue" in frameworks or "vuejs" in frameworks:
        findings.extend(find_vue_xss(context))

    findings.extend(find_dom_xss(context))
    findings.extend(find_template_injection(context))

    seen = set()
    deduped = []

    for finding in findings:
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

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT name FROM frameworks")

    for (name,) in cursor.fetchall():
        if name:
            frameworks.add(name.lower())

    conn.close()
    return frameworks


__all__ = [
    "find_all_xss_issues",
    "find_xss_issues",
    "find_express_xss",
    "find_react_xss",
    "find_vue_xss",
    "find_dom_xss",
    "find_template_injection",
]
