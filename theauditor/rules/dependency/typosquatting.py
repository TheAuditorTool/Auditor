"""Detect potential typosquatting in package names.

Typosquatting is a supply chain attack where malicious packages use names
that are slight misspellings of popular packages, hoping developers will
accidentally install them. This rule checks both declared dependencies
and actual imports against a known list of typosquat patterns.

CWE-1357: Reliance on Insufficiently Trustworthy Component
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

from .config import TYPOSQUATTING_MAP

METADATA = RuleMetadata(
    name="typosquatting",
    category="dependency",
    target_extensions=[".py", ".js", ".ts", ".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="import_styles",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect potential typosquatting in package names.

    Checks both declared dependencies (from package manifests) and actual
    imports in source code against known typosquat patterns.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Check declared JavaScript dependencies
        findings.extend(_check_js_declared_packages(db))

        # Check declared Python dependencies
        findings.extend(_check_python_declared_packages(db))

        # Check actual imports in source code
        findings.extend(_check_imported_packages(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_declared_packages(db: RuleDB) -> list[StandardFinding]:
    """Check declared JavaScript dependencies for typosquatting.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for typosquatted JS dependencies
    """
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, is_dev in rows:
        if not pkg_name:
            continue

        pkg_lower = pkg_name.lower()
        if pkg_lower in seen:
            continue

        if pkg_lower in TYPOSQUATTING_MAP:
            correct_name = TYPOSQUATTING_MAP[pkg_lower]
            seen.add(pkg_lower)
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Potential typosquatting: {dep_type} '{pkg_name}' may be a typosquat of '{correct_name}'",
                    file_path=file_path,
                    line=1,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=f'"{pkg_name}": "..." (expected: {correct_name})',
                    cwe_id="CWE-1357",
                )
            )

    return findings


def _check_python_declared_packages(db: RuleDB) -> list[StandardFinding]:
    """Check declared Python dependencies for typosquatting.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for typosquatted Python dependencies
    """
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "name", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, is_dev in rows:
        if not pkg_name:
            continue

        pkg_lower = pkg_name.lower()
        if pkg_lower in seen:
            continue

        if pkg_lower in TYPOSQUATTING_MAP:
            correct_name = TYPOSQUATTING_MAP[pkg_lower]
            seen.add(pkg_lower)
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Potential typosquatting: Python {dep_type} '{pkg_name}' may be a typosquat of '{correct_name}'",
                    file_path=file_path,
                    line=1,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=f"{pkg_name} (expected: {correct_name})",
                    cwe_id="CWE-1357",
                )
            )

    return findings


def _check_imported_packages(db: RuleDB) -> list[StandardFinding]:
    """Check imported packages in source code for typosquatting.

    Args:
        db: RuleDB instance

    Returns:
        List of findings for typosquatted imports
    """
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    rows = db.query(
        Q("import_styles")
        .select("file", "line", "package")
        .order_by("package, file, line")
    )

    for file_path, line, package in rows:
        if not package:
            continue

        # Normalize to base package name
        base_package = _get_base_package(package)
        if base_package in seen:
            continue

        if base_package in TYPOSQUATTING_MAP:
            correct_name = TYPOSQUATTING_MAP[base_package]
            seen.add(base_package)

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Importing potentially typosquatted package: '{base_package}' may be a typosquat of '{correct_name}'",
                    file_path=file_path,
                    line=line,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=f"import {package}",
                    cwe_id="CWE-1357",
                )
            )

    return findings


def _get_base_package(package: str) -> str:
    """Extract base package name from import path.

    Args:
        package: Full import path (e.g., "lodash/merge")

    Returns:
        Base package name in lowercase (e.g., "lodash")
    """
    # Handle scoped packages (@org/pkg)
    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]).lower()
        return package.lower()

    # Get base package (before / or .)
    base = package.split("/")[0].split(".")[0]
    return base.lower()
