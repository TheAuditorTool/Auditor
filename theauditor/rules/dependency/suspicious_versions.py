"""Detect suspicious version specifiers in dependencies.

Suspicious versions like "latest", "*", "0.0.001", or "unknown" indicate
poor dependency management and can lead to non-reproducible builds or
security vulnerabilities.

Detection Strategy:
1. Query package_configs for all dependency versions
2. Check against SUSPICIOUS_VERSIONS frozenset from config.py
3. Flag any matches with appropriate severity

Database Tables Used:
- package_configs: Dependency version specifications
"""
from __future__ import annotations


import sqlite3
import json
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query
from .config import SUSPICIOUS_VERSIONS


METADATA = RuleMetadata(
    name="suspicious_versions",
    category="dependency",
    target_extensions=['.json', '.txt', '.toml'],
    exclude_patterns=['node_modules/', '.venv/', 'test/', '__tests__/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect dependencies with suspicious version specifications.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for suspicious versions
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query('package_configs', ['file_path', 'dependencies', 'dev_dependencies'])
        cursor.execute(query)

        for file_path, deps, dev_deps in cursor.fetchall():
            # Check production dependencies
            if deps:
                findings.extend(_check_versions(file_path, deps, is_dev=False))

            # Check dev dependencies
            if dev_deps:
                findings.extend(_check_versions(file_path, dev_deps, is_dev=True))

    finally:
        conn.close()

    return findings


def _check_versions(file_path: str, deps_json: str, is_dev: bool) -> list[StandardFinding]:
    """Check dependency versions for suspicious patterns.

    Args:
        file_path: Path to package file
        deps_json: JSON string of dependencies
        is_dev: True if these are dev dependencies

    Returns:
        List of findings for this dependency set
    """
    findings = []

    try:
        deps_dict = json.loads(deps_json)
        if not isinstance(deps_dict, dict):
            return findings
    except json.JSONDecodeError:
        return findings

    for package, version in deps_dict.items():
        if not version:
            continue

        # Normalize version string
        version_clean = str(version).strip()

        # Check against suspicious versions
        if version_clean in SUSPICIOUS_VERSIONS:
            severity = Severity.MEDIUM if not is_dev else Severity.LOW

            findings.append(StandardFinding(
                rule_name='suspicious-version',
                message=f"Suspicious version '{version_clean}' for package '{package}'",
                file_path=file_path,
                line=1,
                severity=severity,
                category='dependency',
                snippet=f"{package}: {version_clean}",
            ))

    return findings
