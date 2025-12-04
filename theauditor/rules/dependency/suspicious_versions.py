"""Detect suspicious version specifiers in dependencies."""

import json
import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

from .config import SUSPICIOUS_VERSIONS

METADATA = RuleMetadata(
    name="suspicious_versions",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__tests__/"])


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect dependencies with suspicious version specifications."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        query = build_query("package_configs", ["file_path", "dependencies", "dev_dependencies"])
        cursor.execute(query)

        for file_path, deps, dev_deps in cursor.fetchall():
            if deps:
                findings.extend(_check_versions(file_path, deps, is_dev=False))

            if dev_deps:
                findings.extend(_check_versions(file_path, dev_deps, is_dev=True))

    finally:
        conn.close()

    return findings


def _check_versions(file_path: str, deps_json: str, is_dev: bool) -> list[StandardFinding]:
    """Check dependency versions for suspicious patterns."""
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

        version_clean = str(version).strip()

        if version_clean in SUSPICIOUS_VERSIONS:
            severity = Severity.MEDIUM if not is_dev else Severity.LOW

            findings.append(
                StandardFinding(
                    rule_name="suspicious-version",
                    message=f"Suspicious version '{version_clean}' for package '{package}'",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category="dependency",
                    snippet=f"{package}: {version_clean}",
                )
            )

    return findings
