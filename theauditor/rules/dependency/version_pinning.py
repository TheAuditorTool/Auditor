"""Detect unpinned dependency versions in production code.

Unpinned versions (using ^, ~, *, etc.) can lead to non-reproducible builds
and unexpected breaking changes. Production dependencies should use exact
versions or lock files.

Detection Strategy:
1. Query package_configs for production dependencies
2. Check versions for range prefixes (^, ~, >, etc.)
3. Flag unpinned versions with appropriate severity

Database Tables Used:
- package_configs: Dependency version specifications
"""
from __future__ import annotations


import sqlite3
import json
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query
from .config import RANGE_PREFIXES


METADATA = RuleMetadata(
    name="version_pinning",
    category="dependency",
    target_extensions=['.json', '.txt', '.toml'],
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect unpinned version ranges in production dependencies.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for unpinned versions
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query('package_configs', ['file_path', 'package_name', 'dependencies'])
        cursor.execute(query)

        for file_path, package_name, deps in cursor.fetchall():
            if not deps:
                continue

            try:
                deps_dict = json.loads(deps)
                if not isinstance(deps_dict, dict):
                    continue

                for pkg, version in deps_dict.items():
                    if not version:
                        continue

                    version_str = str(version).strip()

                    # Check for range prefixes
                    for prefix in RANGE_PREFIXES:
                        if version_str.startswith(prefix):
                            findings.append(StandardFinding(
                                rule_name='version_pinning',
                                message=f"Production dependency '{pkg}' uses unpinned version '{version_str}'",
                                file_path=file_path,
                                line=1,
                                severity=Severity.MEDIUM,
                                category='dependency',
                                snippet=f"{pkg}: {version_str} (prefix: {prefix})",
                            ))
                            break  # Only report once per package

            except json.JSONDecodeError:
                continue

    finally:
        conn.close()

    return findings
