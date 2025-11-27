"""Detect excessive dependencies (dependency bloat).

Too many dependencies increase security surface area, build times, and
maintenance burden. This rule flags projects with excessive direct
dependencies.

Detection Strategy:
1. Query package_configs and count dependencies
2. Compare against DependencyThresholds from config.py
3. Flag if counts exceed thresholds

Database Tables Used:
- package_configs: Dependency declarations
"""

import json
import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

from .config import DependencyThresholds

METADATA = RuleMetadata(
    name="dependency_bloat",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/"],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect excessive dependency counts in package files.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for dependency bloat
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query("package_configs", ["file_path", "dependencies", "dev_dependencies"])
        cursor.execute(query)

        for file_path, deps, dev_deps in cursor.fetchall():
            prod_count = 0
            if deps:
                try:
                    deps_dict = json.loads(deps)
                    if isinstance(deps_dict, dict):
                        prod_count = len(deps_dict)
                except json.JSONDecodeError:
                    pass

            dev_count = 0
            if dev_deps:
                try:
                    dev_dict = json.loads(dev_deps)
                    if isinstance(dev_dict, dict):
                        dev_count = len(dev_dict)
                except json.JSONDecodeError:
                    pass

            if prod_count > DependencyThresholds.MAX_DIRECT_DEPS:
                findings.append(
                    StandardFinding(
                        rule_name="dependency-bloat-production",
                        message=f"Excessive production dependencies: {prod_count} (threshold: {DependencyThresholds.MAX_DIRECT_DEPS})",
                        file_path=file_path,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="dependency",
                        snippet=f"{prod_count} production dependencies declared",
                    )
                )
            elif prod_count > DependencyThresholds.WARN_PRODUCTION_DEPS:
                findings.append(
                    StandardFinding(
                        rule_name="dependency-bloat-warn",
                        message=f"High production dependency count: {prod_count} (warning threshold: {DependencyThresholds.WARN_PRODUCTION_DEPS})",
                        file_path=file_path,
                        line=1,
                        severity=Severity.LOW,
                        category="dependency",
                        snippet=f"{prod_count} production dependencies",
                    )
                )

            if dev_count > DependencyThresholds.MAX_DEV_DEPS:
                findings.append(
                    StandardFinding(
                        rule_name="dependency-bloat-dev",
                        message=f"Excessive dev dependencies: {dev_count} (threshold: {DependencyThresholds.MAX_DEV_DEPS})",
                        file_path=file_path,
                        line=1,
                        severity=Severity.LOW,
                        category="dependency",
                        snippet=f"{dev_count} dev dependencies declared",
                    )
                )

    finally:
        conn.close()

    return findings
