"""Detect peer dependency mismatches (database-first implementation).

Detects packages that declare peer dependency requirements which are either
missing or have version mismatches with installed packages. Handles:
- Caret ranges (^17.0.0): major version must match
- Tilde ranges (~17.0.0): major.minor must match
- OR ranges (^16.0.0 || ^17.0.0 || ^18.0.0): any range satisfies
- Comparison operators (>=, >, <, <=)
- Wildcard versions (*, x, X)
- Prerelease versions (-alpha, -beta, -rc)

CWE: CWE-1104 (Use of Unmaintained Third Party Components)
"""

import json
import re

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

        mismatch_reason = _check_version_mismatch(peer_requirement, actual_version)
        if mismatch_reason:
            findings.append(
                StandardFinding(
                    file_path=file_path,
                    line=1,
                    rule_name="peer-dependency-conflict",
                    message=f"Package '{pkg_name}' requires peer '{peer_name}' {peer_requirement}, but {actual_version} installed: {mismatch_reason}",
                    severity=Severity.HIGH,
                    category="dependency",
                    snippet=f"{pkg_name} requires {peer_name} {peer_requirement} (installed: {actual_version})",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _check_version_mismatch(requirement: str, actual: str) -> str | None:
    """Check if requirement and actual version are incompatible.

    Args:
        requirement: Semver requirement string (e.g., "^17.0.0", ">=16.0.0")
        actual: Actual installed version (e.g., "18.2.0")

    Returns:
        Mismatch reason string if incompatible, None if compatible
    """
    requirement = requirement.strip()

    # Handle OR ranges (||)
    if "||" in requirement:
        ranges = [r.strip() for r in requirement.split("||")]
        mismatches = []
        for r in ranges:
            mismatch = _check_single_range(r, actual)
            if mismatch is None:
                return None  # At least one range matches
            mismatches.append(mismatch)
        return f"no matching range (tried: {', '.join(ranges)})"

    return _check_single_range(requirement, actual)


def _check_single_range(requirement: str, actual: str) -> str | None:
    """Check a single version range against actual version.

    Args:
        requirement: Single semver range (e.g., "^17.0.0", ">=16.0.0")
        actual: Actual installed version

    Returns:
        Mismatch reason string if incompatible, None if compatible
    """
    # Parse actual version
    actual_parts = _parse_version(actual)
    if actual_parts is None:
        return None  # Can't parse, assume OK

    actual_major, actual_minor, actual_patch = actual_parts

    # Handle wildcards
    if requirement in ("*", "x", "X", ""):
        return None

    # Handle caret range (^): compatible with major version
    if requirement.startswith("^"):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if actual_major != req_major:
            return f"major version {actual_major} != {req_major}"
        # For 0.x versions, caret is more restrictive
        if req_major == 0:
            if actual_minor < req_minor:
                return f"minor version {actual_minor} < {req_minor} (0.x range)"
        return None

    # Handle tilde range (~): compatible with major.minor
    if requirement.startswith("~"):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, _req_patch = req_parts

        if actual_major != req_major:
            return f"major version {actual_major} != {req_major}"
        if actual_minor != req_minor:
            return f"minor version {actual_minor} != {req_minor}"
        return None

    # Handle >=
    if requirement.startswith(">="):
        req_parts = _parse_version(requirement[2:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) < (req_major, req_minor, req_patch):
            return f"version {actual} < {requirement[2:]}"
        return None

    # Handle >
    if requirement.startswith(">") and not requirement.startswith(">="):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) <= (req_major, req_minor, req_patch):
            return f"version {actual} <= {requirement[1:]}"
        return None

    # Handle <=
    if requirement.startswith("<="):
        req_parts = _parse_version(requirement[2:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) > (req_major, req_minor, req_patch):
            return f"version {actual} > {requirement[2:]}"
        return None

    # Handle <
    if requirement.startswith("<") and not requirement.startswith("<="):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) >= (req_major, req_minor, req_patch):
            return f"version {actual} >= {requirement[1:]}"
        return None

    # Handle exact version or implicit caret (npm default)
    req_parts = _parse_version(requirement)
    if req_parts is None:
        return None
    req_major, _req_minor, _req_patch = req_parts

    # Default: treat as major version requirement
    if actual_major != req_major:
        return f"major version {actual_major} != {req_major}"

    return None


def _parse_version(version: str) -> tuple[int, int, int] | None:
    """Parse version string into (major, minor, patch) tuple.

    Handles:
    - Standard semver: 1.2.3
    - With v prefix: v1.2.3
    - With prerelease: 1.2.3-alpha.1
    - Partial versions: 1.2, 1

    Args:
        version: Version string to parse

    Returns:
        Tuple of (major, minor, patch) or None if unparseable
    """
    # Strip v prefix
    version = version.lstrip("vV").strip()

    # Remove prerelease and build metadata
    version = re.split(r"[-+]", version)[0]

    # Split into parts
    parts = version.split(".")

    try:
        major = int(parts[0]) if len(parts) > 0 and parts[0] else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2] else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return None
