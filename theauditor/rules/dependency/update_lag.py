"""Detect severely outdated dependencies using indexed version data.

Flags dependencies that are 2+ major versions behind the latest release.
Severely outdated dependencies often miss critical security patches and
may have known vulnerabilities.

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

METADATA = RuleMetadata(
    name="update_lag",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="dependency_versions",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect severely outdated dependencies from version tracking data.

    Uses the dependency_versions table populated by version checking
    to identify packages that are multiple major versions behind.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Build file path map for better finding locations
        file_path_map = _build_file_path_map(db)

        # Query outdated dependencies with major version delta
        rows = db.query(
            Q("dependency_versions")
            .select(
                "manager",
                "package_name",
                "locked_version",
                "latest_version",
                "delta",
                "is_outdated",
                "error",
            )
            .where("is_outdated = ?", 1)
            .where("delta = ?", "major")
            .where("error IS NULL OR error = ?", "")
            .order_by("manager, package_name")
        )

        for manager, pkg_name, locked, latest, delta, is_outdated, error in rows:
            if not locked or not latest:
                continue

            versions_behind = _calculate_major_versions_behind(locked, latest)
            if versions_behind < 2:
                continue

            # Determine severity based on how far behind
            severity = Severity.MEDIUM if versions_behind == 2 else Severity.HIGH

            # Get file path from map or use default
            key = f"{manager}:{pkg_name}"
            file_path = file_path_map.get(key, _default_file_path(manager))

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Dependency '{pkg_name}' is {versions_behind} major versions behind (using {locked}, latest is {latest})",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name}: {locked} -> {latest}",
                    cwe_id="CWE-1104",
                )
            )

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _build_file_path_map(db: RuleDB) -> dict[str, str]:
    """Build a map of manager:package_name -> file_path.

    Args:
        db: RuleDB instance

    Returns:
        Dict mapping "manager:pkg_name" to file_path
    """
    file_map: dict[str, str] = {}

    # Map JavaScript packages
    js_rows = db.query(
        Q("package_dependencies")
        .select("file_path", "name")
        .order_by("file_path")
    )
    for file_path, name in js_rows:
        file_map[f"npm:{name}"] = file_path

    # Map Python packages
    py_rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "name")
        .order_by("file_path")
    )
    for file_path, name in py_rows:
        file_map[f"pypi:{name}"] = file_path

    return file_map


def _default_file_path(manager: str) -> str:
    """Get default file path for a package manager.

    Args:
        manager: Package manager identifier (npm, pypi, etc.)

    Returns:
        Default manifest file path
    """
    defaults = {
        "npm": "package.json",
        "pypi": "requirements.txt",
        "cargo": "Cargo.toml",
        "go": "go.mod",
    }
    return defaults.get(manager, "package.json")


def _calculate_major_versions_behind(locked: str, latest: str) -> int:
    """Calculate how many major versions behind locked is from latest.

    Args:
        locked: Currently locked version string
        latest: Latest available version string

    Returns:
        Number of major versions behind, or 0 if calculation fails
    """
    try:
        # Strip common prefixes (v, ^, ~, <, >, =)
        locked_clean = locked.lstrip("v^~<>=")
        latest_clean = latest.lstrip("v^~<>=")

        locked_major = int(locked_clean.split(".")[0])
        latest_major = int(latest_clean.split(".")[0])

        return max(0, latest_major - locked_major)
    except (ValueError, IndexError):
        return 0
