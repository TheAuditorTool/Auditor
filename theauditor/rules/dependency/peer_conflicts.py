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
        findings: list[StandardFinding] = []

        installed_versions = _get_installed_versions(db)
        peer_requirements = _get_peer_requirements(db)

        for file_path, peer_name, peer_version_spec in peer_requirements:
            actual_version = installed_versions.get(peer_name)

            if not actual_version:
                findings.append(
                    StandardFinding(
                        file_path=file_path,
                        line=1,
                        rule_name="peer-dependency-missing",
                        message=f"Peer dependency '{peer_name}' ({peer_version_spec}) is not installed",
                        severity=Severity.MEDIUM,
                        category="dependency",
                        snippet=f"peerDependencies: {peer_name}: {peer_version_spec}",
                        cwe_id="CWE-1104",
                    )
                )
                continue

            mismatch_reason = _check_version_mismatch(peer_version_spec, actual_version)
            if mismatch_reason:
                findings.append(
                    StandardFinding(
                        file_path=file_path,
                        line=1,
                        rule_name="peer-dependency-conflict",
                        message=f"Peer dependency '{peer_name}' requires {peer_version_spec}, but {actual_version} installed: {mismatch_reason}",
                        severity=Severity.HIGH,
                        category="dependency",
                        snippet=f"{peer_name} {peer_version_spec} (installed: {actual_version})",
                        cwe_id="CWE-1104",
                    )
                )

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_installed_versions(db: RuleDB) -> dict[str, str]:
    """Get installed package versions from regular (non-peer) dependencies."""
    installed = {}

    rows = db.query(Q("package_dependencies").select("name", "version_spec").where("is_peer = 0"))

    for name, version in rows:
        if version:
            installed[name] = version

    return installed


def _get_peer_requirements(db: RuleDB) -> list[tuple]:
    """Get peer dependency requirements from package_dependencies."""
    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name", "version_spec")
        .where("is_peer = 1")
        .order_by("file_path, name")
    )
    return list(rows)


def _check_version_mismatch(requirement: str, actual: str) -> str | None:
    """Check if requirement and actual version are incompatible.

    Args:
        requirement: Semver requirement string (e.g., "^17.0.0", ">=16.0.0")
        actual: Actual installed version (e.g., "18.2.0")

    Returns:
        Mismatch reason string if incompatible, None if compatible
    """
    requirement = requirement.strip()

    if "||" in requirement:
        ranges = [r.strip() for r in requirement.split("||")]
        mismatches = []
        for r in ranges:
            mismatch = _check_single_range(r, actual)
            if mismatch is None:
                return None
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

    actual_parts = _parse_version(actual)
    if actual_parts is None:
        return None

    actual_major, actual_minor, actual_patch = actual_parts

    if requirement in ("*", "x", "X", ""):
        return None

    if requirement.startswith("^"):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if actual_major != req_major:
            return f"major version {actual_major} != {req_major}"

        if req_major == 0:
            if actual_minor < req_minor:
                return f"minor version {actual_minor} < {req_minor} (0.x range)"
        return None

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

    if requirement.startswith(">="):
        req_parts = _parse_version(requirement[2:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) < (req_major, req_minor, req_patch):
            return f"version {actual} < {requirement[2:]}"
        return None

    if requirement.startswith(">") and not requirement.startswith(">="):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) <= (req_major, req_minor, req_patch):
            return f"version {actual} <= {requirement[1:]}"
        return None

    if requirement.startswith("<="):
        req_parts = _parse_version(requirement[2:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) > (req_major, req_minor, req_patch):
            return f"version {actual} > {requirement[2:]}"
        return None

    if requirement.startswith("<") and not requirement.startswith("<="):
        req_parts = _parse_version(requirement[1:])
        if req_parts is None:
            return None
        req_major, req_minor, req_patch = req_parts

        if (actual_major, actual_minor, actual_patch) >= (req_major, req_minor, req_patch):
            return f"version {actual} >= {requirement[1:]}"
        return None

    req_parts = _parse_version(requirement)
    if req_parts is None:
        return None
    req_major, _req_minor, _req_patch = req_parts

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

    version = version.lstrip("vV").strip()

    version = re.split(r"[-+]", version)[0]

    parts = version.split(".")

    try:
        major = int(parts[0]) if len(parts) > 0 and parts[0] else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2] else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return None
