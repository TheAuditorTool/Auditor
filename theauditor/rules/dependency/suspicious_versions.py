"""Detect suspicious version specifiers in dependencies.

Flags dangerous version patterns like '*', 'latest', 'dev', 'master', or
other loose constraints that could pull in untested or malicious package
versions. These patterns bypass lockfile guarantees and may introduce
supply chain vulnerabilities.

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

from .config import SUSPICIOUS_VERSIONS

METADATA = RuleMetadata(
    name="suspicious_versions",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__tests__/", "__pycache__/"],
    execution_scope="database",
    primary_table="package_dependencies",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect dependencies with suspicious version specifications.

    Checks both JavaScript (package_dependencies) and Python
    (python_package_dependencies) for dangerous version patterns.

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
        findings.extend(_check_js_versions(db))

        # Check Python package dependencies
        findings.extend(_check_python_versions(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_versions(db: RuleDB) -> list[StandardFinding]:
    """Check JavaScript package dependencies for suspicious versions.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for suspicious JS dependency versions
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name", "version_spec", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, version_spec, is_dev in rows:
        if not version_spec:
            continue

        version_clean = str(version_spec).strip()

        if _is_suspicious_version(version_clean):
            severity = Severity.LOW if is_dev else Severity.MEDIUM
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Suspicious version '{version_clean}' for {dep_type} '{pkg_name}'",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f'"{pkg_name}": "{version_clean}"',
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _check_python_versions(db: RuleDB) -> list[StandardFinding]:
    """Check Python package dependencies for suspicious versions.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for suspicious Python dependency versions
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "name", "version_spec", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, version_spec, is_dev in rows:
        if not version_spec:
            continue

        version_clean = str(version_spec).strip()

        if _is_suspicious_version(version_clean):
            severity = Severity.LOW if is_dev else Severity.MEDIUM
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Suspicious version '{version_clean}' for Python {dep_type} '{pkg_name}'",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name}{version_clean}",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _is_suspicious_version(version: str) -> bool:
    """Check if version string is suspicious.

    Args:
        version: Version specification string

    Returns:
        True if version matches known suspicious patterns
    """
    # Direct match against known suspicious versions
    if version in SUSPICIOUS_VERSIONS:
        return True

    # Check lowercase variant
    version_lower = version.lower()
    if version_lower in SUSPICIOUS_VERSIONS:
        return True

    return False
