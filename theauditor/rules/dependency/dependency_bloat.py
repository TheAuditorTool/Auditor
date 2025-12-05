"""Detect excessive dependencies (dependency bloat).

Flags projects with too many production or dev dependencies, which increases
attack surface, maintenance burden, and security risk.

CWE: CWE-1104 (Use of Unmaintained Third Party Components) - tangentially related
"""

import json

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q
from theauditor.utils.logging import logger

from .config import DependencyThresholds

METADATA = RuleMetadata(
    name="dependency_bloat",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/"],
    execution_scope="database",
    primary_table="package_configs",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect excessive dependency counts in package files.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        rows = db.query(
            Q("package_configs")
            .select("file_path", "dependencies", "dev_dependencies")
        )

        for file_path, deps, dev_deps in rows:
            findings.extend(_check_dependency_counts(file_path, deps, dev_deps))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_dependency_counts(
    file_path: str,
    deps: str | None,
    dev_deps: str | None,
) -> list[StandardFinding]:
    """Check dependency counts against thresholds."""
    findings = []

    prod_count = _count_dependencies(deps, file_path, "dependencies")
    dev_count = _count_dependencies(dev_deps, file_path, "dev_dependencies")

    # Check production dependencies
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
                cwe_id="CWE-1104",
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
                cwe_id="CWE-1104",
            )
        )

    # Check dev dependencies
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
                cwe_id="CWE-1104",
            )
        )

    return findings


def _count_dependencies(json_str: str | None, file_path: str, field_name: str) -> int:
    """Parse dependency JSON and return count.

    Args:
        json_str: JSON string from database
        file_path: Source file for logging
        field_name: Field name for logging

    Returns:
        Dependency count, or 0 if parsing fails
    """
    if not json_str:
        return 0

    try:
        deps_dict = json.loads(json_str)
        if isinstance(deps_dict, dict):
            return len(deps_dict)
        return 0
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse {field_name} JSON in {file_path}: {e}")
        return 0
