"""Detect unused dependencies - packages declared but never imported.

Flags dependencies that are declared in package manifests but never
imported in the codebase. Unused dependencies increase attack surface
and bundle size without providing value.

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

from .config import DEV_ONLY_PACKAGES

METADATA = RuleMetadata(
    name="unused_dependencies",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml", ".lock"],
    exclude_patterns=["node_modules/", ".venv/", "venv/", "dist/", "build/", "__pycache__/"],
    execution_scope="database",
    primary_table="package_dependencies",
)

# Packages that are used via CLI or config, not imports
CLI_PACKAGES: frozenset[str] = frozenset([
    "eslint",
    "prettier",
    "typescript",
    "tsc",
    "ts-node",
    "nodemon",
    "concurrently",
    "npm-run-all",
    "husky",
    "lint-staged",
    "commitlint",
    "semantic-release",
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect packages declared in dependencies but never imported.

    Cross-references declared dependencies against actual imports to find
    packages that may be unnecessary.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Get all imported package names
        imported_packages = _get_imported_packages(db)

        # Check JavaScript/Node dependencies
        findings.extend(_check_js_unused(db, imported_packages))

        # Check Python dependencies
        findings.extend(_check_python_unused(db, imported_packages))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_imported_packages(db: RuleDB) -> set[str]:
    """Get all imported package names (normalized to base package).

    Args:
        db: RuleDB instance

    Returns:
        Set of normalized package names that are imported
    """
    imported: set[str] = set()

    rows = db.query(
        Q("import_styles")
        .select("package")
        .order_by("package")
    )

    for (package,) in rows:
        if not package:
            continue
        base_package = _normalize_package_name(package)
        imported.add(base_package)

    return imported


def _check_js_unused(db: RuleDB, imported: set[str]) -> list[StandardFinding]:
    """Check JavaScript package dependencies for unused packages.

    Args:
        db: RuleDB instance
        imported: Set of imported package names

    Returns:
        List of findings for unused JS dependencies
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name", "is_dev", "is_peer")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, is_dev, is_peer in rows:
        # Skip peer dependencies - they're provided by consumers
        if is_peer:
            continue

        normalized = _normalize_package_name(pkg_name)

        # Skip if actually imported
        if normalized in imported:
            continue

        # Skip CLI/build tools that aren't imported
        if _is_cli_or_build_tool(pkg_name):
            continue

        # Skip type definition packages
        if pkg_name.startswith("@types/"):
            continue

        severity = Severity.LOW if is_dev else Severity.MEDIUM
        dep_type = "dev" if is_dev else "production"

        findings.append(
            StandardFinding(
                rule_name=METADATA.name,
                message=f"{dep_type.capitalize()} dependency '{pkg_name}' declared but never imported",
                file_path=file_path,
                line=1,
                severity=severity,
                category=METADATA.category,
                snippet=f'"{pkg_name}": "..."',
                cwe_id="CWE-1104",
            )
        )

    return findings


def _check_python_unused(db: RuleDB, imported: set[str]) -> list[StandardFinding]:
    """Check Python package dependencies for unused packages.

    Args:
        db: RuleDB instance
        imported: Set of imported package names

    Returns:
        List of findings for unused Python dependencies
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "name", "is_dev")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, is_dev in rows:
        normalized = _normalize_package_name(pkg_name)

        # Skip if actually imported
        if normalized in imported:
            continue

        # Skip CLI/build tools
        if _is_cli_or_build_tool(pkg_name):
            continue

        severity = Severity.LOW if is_dev else Severity.MEDIUM
        dep_type = "dev" if is_dev else "production"

        findings.append(
            StandardFinding(
                rule_name=METADATA.name,
                message=f"Python {dep_type} dependency '{pkg_name}' declared but never imported",
                file_path=file_path,
                line=1,
                severity=severity,
                category=METADATA.category,
                snippet=f"{pkg_name}",
                cwe_id="CWE-1104",
            )
        )

    return findings


def _normalize_package_name(package: str) -> str:
    """Normalize package name to base package for comparison.

    Handles scoped packages (@org/pkg), subpath imports (pkg/subpath),
    and node: protocol.

    Args:
        package: Package name or import path

    Returns:
        Normalized base package name in lowercase
    """
    # Handle scoped packages (@org/package)
    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]).lower()
        return package.lower()

    # Handle node: protocol
    if package.startswith("node:"):
        return package.lower()

    # Get base package (before / or .)
    base = package.split("/")[0].split(".")[0]
    return base.lower()


def _is_cli_or_build_tool(package: str) -> bool:
    """Check if package is a CLI or build tool that isn't imported.

    Args:
        package: Package name

    Returns:
        True if package is a CLI/build tool
    """
    pkg_lower = package.lower()

    # Check against known CLI packages
    if pkg_lower in CLI_PACKAGES:
        return True

    # Check against dev-only packages from config
    if pkg_lower in DEV_ONLY_PACKAGES:
        return True

    # Heuristic: packages starting with these are usually build/dev tools
    build_prefixes = ("eslint-", "prettier-", "@babel/", "webpack-", "rollup-", "vite-")
    if any(pkg_lower.startswith(prefix) for prefix in build_prefixes):
        return True

    return False
