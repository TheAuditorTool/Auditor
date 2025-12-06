"""Detect severely outdated dependencies using indexed version data.

Flags dependencies that are significantly behind the latest release:
- 2+ major versions behind (HIGH/CRITICAL severity)
- 1 major version behind for security-critical packages (MEDIUM severity)
- Many minor versions behind (LOW severity)

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


SECURITY_CRITICAL_PACKAGES: frozenset[str] = frozenset(
    [
        "lodash",
        "express",
        "axios",
        "node-fetch",
        "got",
        "request",
        "minimist",
        "yargs",
        "commander",
        "jsonwebtoken",
        "passport",
        "bcrypt",
        "crypto-js",
        "helmet",
        "cors",
        "body-parser",
        "cookie-parser",
        "dotenv",
        "webpack",
        "serialize-javascript",
        "handlebars",
        "marked",
        "highlight.js",
        "moment",
        "luxon",
        "django",
        "flask",
        "requests",
        "urllib3",
        "pyyaml",
        "pillow",
        "jinja2",
        "cryptography",
        "paramiko",
        "pyjwt",
        "werkzeug",
        "gunicorn",
        "celery",
        "sqlalchemy",
        "psycopg2",
        "pymysql",
        "redis",
        "boto3",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect severely outdated dependencies from version tracking data.

    Uses the dependency_versions table to identify packages that are
    significantly behind, with special attention to security-critical packages.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        file_path_map = _build_file_path_map(db)

        findings.extend(_check_major_outdated(db, file_path_map))
        findings.extend(_check_minor_outdated(db, file_path_map))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_major_outdated(db: RuleDB, file_path_map: dict[str, str]) -> list[StandardFinding]:
    """Check for major version lag (most severe).

    Args:
        db: RuleDB instance
        file_path_map: Map of manager:package -> file_path

    Returns:
        List of findings for major version outdated packages
    """
    findings: list[StandardFinding] = []

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

    for manager, pkg_name, locked, latest, _delta, _is_outdated, _error in rows:
        if not locked or not latest:
            continue

        versions_behind = _calculate_major_versions_behind(locked, latest)
        is_critical = pkg_name.lower() in SECURITY_CRITICAL_PACKAGES

        if versions_behind >= 3:
            severity = Severity.CRITICAL if is_critical else Severity.HIGH
        elif versions_behind == 2:
            severity = Severity.HIGH if is_critical else Severity.MEDIUM
        elif versions_behind == 1 and is_critical:
            severity = Severity.MEDIUM
        else:
            continue

        key = f"{manager}:{pkg_name}"
        file_path = file_path_map.get(key, _default_file_path(manager))

        critical_note = " (security-critical package)" if is_critical else ""
        findings.append(
            StandardFinding(
                rule_name=METADATA.name,
                message=f"Dependency '{pkg_name}' is {versions_behind} major version(s) behind{critical_note} ({locked} -> {latest})",
                file_path=file_path,
                line=1,
                severity=severity,
                category=METADATA.category,
                snippet=f"{pkg_name}: {locked} -> {latest}",
                cwe_id="CWE-1104",
            )
        )

    return findings


def _check_minor_outdated(db: RuleDB, file_path_map: dict[str, str]) -> list[StandardFinding]:
    """Check for significant minor version lag.

    Packages on same major but many minors behind may miss security patches.

    Args:
        db: RuleDB instance
        file_path_map: Map of manager:package -> file_path

    Returns:
        List of findings for minor version outdated packages
    """
    findings: list[StandardFinding] = []

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
        .where("delta = ?", "minor")
        .where("error IS NULL OR error = ?", "")
        .order_by("manager, package_name")
    )

    for manager, pkg_name, locked, latest, _delta, _is_outdated, _error in rows:
        if not locked or not latest:
            continue

        minors_behind = _calculate_minor_versions_behind(locked, latest)
        is_critical = pkg_name.lower() in SECURITY_CRITICAL_PACKAGES

        threshold = 3 if is_critical else 5
        if minors_behind < threshold:
            continue

        severity = Severity.MEDIUM if is_critical else Severity.LOW

        key = f"{manager}:{pkg_name}"
        file_path = file_path_map.get(key, _default_file_path(manager))

        critical_note = " (security-critical)" if is_critical else ""
        findings.append(
            StandardFinding(
                rule_name=METADATA.name,
                message=f"Dependency '{pkg_name}' is {minors_behind} minor versions behind{critical_note} ({locked} -> {latest})",
                file_path=file_path,
                line=1,
                severity=severity,
                category=METADATA.category,
                snippet=f"{pkg_name}: {locked} -> {latest}",
                cwe_id="CWE-1104",
            )
        )

    return findings


def _build_file_path_map(db: RuleDB) -> dict[str, str]:
    """Build a map of manager:package_name -> file_path.

    Args:
        db: RuleDB instance

    Returns:
        Dict mapping "manager:pkg_name" to file_path
    """
    file_map: dict[str, str] = {}

    js_rows = db.query(Q("package_dependencies").select("file_path", "name").order_by("file_path"))
    for file_path, name in js_rows:
        file_map[f"npm:{name}"] = file_path

    py_rows = db.query(
        Q("python_package_dependencies").select("file_path", "name").order_by("file_path")
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

    Handles SemVer 0.x.y correctly: in the 0.x.y range, minor version bumps
    are considered breaking changes per SemVer spec. So 0.1.0 -> 0.2.0 is
    treated as 1 major version behind for severity purposes.

    Args:
        locked: Currently locked version string
        latest: Latest available version string

    Returns:
        Number of major versions behind, or 0 if unparseable/not behind
    """
    locked_clean = locked.lstrip("v^~<>=")
    latest_clean = latest.lstrip("v^~<>=")

    locked_parts = locked_clean.split(".")
    latest_parts = latest_clean.split(".")

    if len(locked_parts) < 1 or len(latest_parts) < 1:
        return 0

    try:
        locked_major = int(locked_parts[0])
        latest_major = int(latest_parts[0])
    except ValueError:
        return 0

    if locked_major == 0 and latest_major == 0:
        if len(locked_parts) >= 2 and len(latest_parts) >= 2:
            try:
                locked_minor = int(locked_parts[1])
                latest_minor = int(latest_parts[1])
                if latest_minor > locked_minor:
                    return 1
            except ValueError:
                pass

    return max(0, latest_major - locked_major)


def _calculate_minor_versions_behind(locked: str, latest: str) -> int:
    """Calculate how many minor versions behind locked is from latest.

    Assumes same major version.

    Args:
        locked: Currently locked version string
        latest: Latest available version string

    Returns:
        Number of minor versions behind, or 0 if unparseable/not behind
    """
    locked_clean = locked.lstrip("v^~<>=")
    latest_clean = latest.lstrip("v^~<>=")

    locked_parts = locked_clean.split(".")
    latest_parts = latest_clean.split(".")

    if len(locked_parts) < 2 or len(latest_parts) < 2:
        return 0

    try:
        locked_minor = int(locked_parts[1])
        latest_minor = int(latest_parts[1])
    except ValueError:
        return 0

    return max(0, latest_minor - locked_minor)
