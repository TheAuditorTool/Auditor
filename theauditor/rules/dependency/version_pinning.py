"""Detect unpinned dependency versions in production code.

Flags dependencies using version ranges (^, ~, >, <, >=, <=, ||) which can lead
to supply chain attacks when malicious versions are published within the range.
Production dependencies should use exact pinned versions for reproducibility
and security.

CWE-1104: Use of Unmaintained Third Party Components
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

from .config import RANGE_PREFIXES

METADATA = RuleMetadata(
    name="version_pinning",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="package_dependencies",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect unpinned version ranges in production dependencies.

    Checks both JavaScript (package_dependencies) and Python
    (python_package_dependencies) for version ranges that could
    allow malicious package updates.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Check JavaScript/Node package dependencies
        findings.extend(_check_js_dependencies(db))

        # Check Python package dependencies
        findings.extend(_check_python_dependencies(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_dependencies(db: RuleDB) -> list[StandardFinding]:
    """Check JavaScript package dependencies for unpinned versions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name", "version_spec", "is_dev", "is_peer")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, version_spec, is_dev, is_peer in rows:
        if not version_spec:
            continue

        version_str = str(version_spec).strip()
        unpinned_prefix = _get_unpinned_prefix(version_str)

        if unpinned_prefix:
            # Lower severity for dev/peer dependencies
            severity = Severity.LOW if is_dev or is_peer else Severity.MEDIUM
            dep_type = "dev" if is_dev else ("peer" if is_peer else "production")

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"{dep_type.capitalize()} dependency '{pkg_name}' uses unpinned version '{version_str}'",
                    file_path=file_path,
                    line=1,  # Line number not available in table
                    severity=severity,
                    category=METADATA.category,
                    snippet=f'"{pkg_name}": "{version_str}"',
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _check_python_dependencies(db: RuleDB) -> list[StandardFinding]:
    """Check Python package dependencies for unpinned versions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "name", "version_spec", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, version_spec, is_dev in rows:
        if not version_spec:
            continue

        version_str = str(version_spec).strip()
        unpinned_prefix = _get_unpinned_prefix(version_str)

        if unpinned_prefix:
            severity = Severity.LOW if is_dev else Severity.MEDIUM
            dep_type = "dev" if is_dev else "production"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Python {dep_type} dependency '{pkg_name}' uses unpinned version '{version_str}'",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name}{version_str}",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _get_unpinned_prefix(version_str: str) -> str | None:
    """Check if version string starts with an unpinned range prefix.

    Args:
        version_str: Version specification string

    Returns:
        The matched prefix if unpinned, None if pinned
    """
    for prefix in RANGE_PREFIXES:
        if version_str.startswith(prefix):
            return prefix
    return None
