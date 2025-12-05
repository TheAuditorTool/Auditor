"""Detect peer dependency mismatches (database-first implementation).

Detects packages that declare peer dependency requirements which are either
missing or have version mismatches with installed packages.

CWE: CWE-1104 (Use of Unmaintained Third Party Components)
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

METADATA = RuleMetadata(
    name="peer_conflicts",
    category="dependency",
    target_extensions=[".json"],
    exclude_patterns=["node_modules/", ".venv/", "test/"],
    execution_scope="database",
    primary_table="package_configs",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect peer dependency version mismatches.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        # Get all installed package versions
        installed_versions = _get_installed_versions(db)

        # Get packages with peer dependencies
        packages_with_peers = _get_packages_with_peers(db)

        # Check for peer conflicts
        for file_path, pkg_name, _version, peer_deps_json in packages_with_peers:
            findings.extend(
                _check_peer_deps(file_path, pkg_name, peer_deps_json, installed_versions)
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_installed_versions(db: RuleDB) -> dict[str, str]:
    """Get all installed package versions."""
    installed = {}

    rows = db.query(
        Q("package_configs")
        .select("package_name", "version")
    )

    for pkg_name, version in rows:
        if version:
            installed[pkg_name] = version

    return installed


def _get_packages_with_peers(db: RuleDB) -> list[tuple]:
    """Get packages that have peer dependencies."""
    rows = db.query(
        Q("package_configs")
        .select("file_path", "package_name", "version", "peer_dependencies")
        .where("peer_dependencies IS NOT NULL")
    )
    return rows


def _check_peer_deps(
    file_path: str,
    pkg_name: str,
    peer_deps_json: str | None,
    installed_versions: dict[str, str],
) -> list[StandardFinding]:
    """Check peer dependencies for a single package."""
    findings = []

    if not peer_deps_json:
        return findings

    try:
        peer_deps = json.loads(peer_deps_json)
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse peer_dependencies JSON for {pkg_name}: {e}")
        return findings

    if not isinstance(peer_deps, dict):
        return findings

    for peer_name, peer_requirement in peer_deps.items():
        if not peer_name or not peer_requirement:
            continue

        actual_version = installed_versions.get(peer_name)

        if not actual_version:
            findings.append(
                StandardFinding(
                    file_path=file_path,
                    line=1,
                    rule_name="peer-dependency-missing",
                    message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' ({peer_requirement}) but it is not installed",
                    severity=Severity.MEDIUM,
                    category="dependency",
                    snippet=f"{pkg_name} requires {peer_name}: {peer_requirement}",
                    cwe_id="CWE-1104",
                )
            )
            continue

        if _has_major_version_mismatch(peer_requirement, actual_version):
            findings.append(
                StandardFinding(
                    file_path=file_path,
                    line=1,
                    rule_name="peer-dependency-conflict",
                    message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' {peer_requirement}, but version {actual_version} is installed",
                    severity=Severity.HIGH,
                    category="dependency",
                    snippet=f"{pkg_name} requires {peer_name} {peer_requirement} (installed: {actual_version})",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _has_major_version_mismatch(requirement: str, actual: str) -> bool:
    """Check if requirement and actual version have major version mismatch.

    Args:
        requirement: Semver requirement string (e.g., "^17.0.0", ">=16.0.0")
        actual: Actual installed version (e.g., "18.2.0")

    Returns:
        True if there's a major version incompatibility
    """
    try:
        req_clean = requirement.lstrip("^~<>=vV").split(".")[0]
        if req_clean in ("*", "x", "X", ""):
            return False

        req_major = int(req_clean)

        actual_clean = actual.lstrip("vV").split(".")[0]
        actual_major = int(actual_clean)

        if requirement.startswith("^") or requirement.startswith("~"):
            return actual_major != req_major
        elif requirement.startswith(">="):
            return actual_major < req_major
        elif requirement.startswith(">"):
            return actual_major <= req_major
        elif requirement.startswith("<="):
            return actual_major > req_major
        elif requirement.startswith("<"):
            return actual_major >= req_major
        else:
            return actual_major != req_major

    except (ValueError, IndexError):
        return False
