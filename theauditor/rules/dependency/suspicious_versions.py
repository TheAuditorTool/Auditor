"""Detect suspicious version specifiers in dependencies.

Flags dangerous version patterns that could pull in untested or malicious
package versions:

- Wildcards (*, x, X) - CRITICAL: Any version could be installed
- Latest tags (latest, next, canary) - CRITICAL: Bypasses lockfile
- Git URLs without commit hash - HIGH: Not pinned to immutable ref
- Git URLs with 40-char SHA hash - ALLOWED: Immutable commit pinning is secure
- File URLs (file:) - HIGH: Local path, not portable
- HTTP URLs (http://, https://) - CRITICAL: External source without registry
- Pre-release markers (alpha, beta, rc, dev) - MEDIUM: Potentially unstable
- Branch references (master, main, develop) - HIGH: Not a version at all
- Placeholder versions (TBD, TODO, unknown) - HIGH: Not properly configured

CWE-1104: Use of Unmaintained Third Party Components
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

from .config import SUSPICIOUS_VERSIONS

METADATA = RuleMetadata(
    name="suspicious_versions",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__tests__/", "__pycache__/"],
    execution_scope="database",
    primary_table="package_dependencies",
)


WILDCARD_PATTERNS: frozenset[str] = frozenset(["*", "x", "X", "x.x.x", "X.X.X"])
LATEST_PATTERNS: frozenset[str] = frozenset(["latest", "next", "canary", "nightly", "edge"])
BRANCH_PATTERNS: frozenset[str] = frozenset(["master", "main", "develop", "dev", "HEAD"])
PLACEHOLDER_PATTERNS: frozenset[str] = frozenset(
    [
        "TBD",
        "TODO",
        "unknown",
        "UNKNOWN",
        "undefined",
        "null",
        "none",
        "N/A",
    ]
)
PRERELEASE_MARKERS: frozenset[str] = frozenset(
    [
        "alpha",
        "beta",
        "rc",
        "dev",
        "pre",
        "preview",
        "snapshot",
        "SNAPSHOT",
    ]
)


GIT_URL_PREFIXES: tuple[str, ...] = (
    "git://",
    "git+https://",
    "git+ssh://",
    "git+http://",
    "github:",
    "gitlab:",
    "bitbucket:",
    "gist:",
)
FILE_URL_PREFIXES: tuple[str, ...] = (
    "file:",
    "link:",
    "./",
    "../",
)
HTTP_URL_PREFIXES: tuple[str, ...] = (
    "http://",
    "https://",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect dependencies with suspicious version specifications.

    Categorizes and flags dangerous version patterns with appropriate
    severity based on the type of risk.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_js_versions(db))

        findings.extend(_check_python_versions(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_versions(db: RuleDB) -> list[StandardFinding]:
    """Check JavaScript package dependencies for suspicious versions."""
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
        suspicious_info = _classify_suspicious_version(version_clean)

        if suspicious_info:
            _issue_type, base_severity, reason = suspicious_info

            if is_dev and base_severity != Severity.CRITICAL:
                severity = Severity.LOW if base_severity == Severity.MEDIUM else Severity.MEDIUM
            else:
                severity = base_severity

            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Suspicious version for {dep_type} '{pkg_name}': {reason}",
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
    """Check Python package dependencies for suspicious versions."""
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
        suspicious_info = _classify_suspicious_version(version_clean)

        if suspicious_info:
            _issue_type, base_severity, reason = suspicious_info
            if is_dev and base_severity != Severity.CRITICAL:
                severity = Severity.LOW if base_severity == Severity.MEDIUM else Severity.MEDIUM
            else:
                severity = base_severity

            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Suspicious version for Python {dep_type} '{pkg_name}': {reason}",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name}{version_clean}",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _classify_suspicious_version(version: str) -> tuple[str, Severity, str] | None:
    """Classify version string and determine if suspicious.

    Args:
        version: Version specification string

    Returns:
        Tuple of (issue_type, severity, human_reason) if suspicious, None otherwise
    """
    version_lower = version.lower().strip()

    if version_lower in WILDCARD_PATTERNS or version in WILDCARD_PATTERNS:
        return ("wildcard", Severity.CRITICAL, f"wildcard version '{version}' allows any version")

    if version_lower in LATEST_PATTERNS:
        return ("latest", Severity.CRITICAL, f"'{version}' tag bypasses version pinning")

    if any(version_lower.startswith(prefix) for prefix in HTTP_URL_PREFIXES):
        return (
            "http_url",
            Severity.CRITICAL,
            f"HTTP URL '{version[:50]}...' bypasses package registry",
        )

    if any(version_lower.startswith(prefix) for prefix in GIT_URL_PREFIXES):
        if re.search(r"#[a-f0-9]{40}$", version_lower):
            return None
        return (
            "git_url",
            Severity.HIGH,
            f"Git URL '{version[:50]}...' not pinned to a commit hash",
        )

    if any(version_lower.startswith(prefix) for prefix in FILE_URL_PREFIXES):
        return (
            "file_url",
            Severity.HIGH,
            f"File path '{version}' is not portable and bypasses registry",
        )

    if version_lower in BRANCH_PATTERNS:
        return ("branch", Severity.HIGH, f"'{version}' is a branch name, not a version")

    if version_lower in PLACEHOLDER_PATTERNS or version in PLACEHOLDER_PATTERNS:
        return ("placeholder", Severity.HIGH, f"'{version}' is a placeholder, not a real version")

    if _is_experimental_version(version_lower):
        return (
            "experimental",
            Severity.HIGH,
            f"version '{version}' suggests experimental/unstable package",
        )

    prerelease = _contains_prerelease_marker(version_lower)
    if prerelease:
        return (
            "prerelease",
            Severity.MEDIUM,
            f"version '{version}' contains pre-release marker '{prerelease}'",
        )

    if version in SUSPICIOUS_VERSIONS or version_lower in SUSPICIOUS_VERSIONS:
        return ("suspicious", Severity.HIGH, f"version '{version}' is flagged as suspicious")

    return None


def _is_experimental_version(version: str) -> bool:
    """Check if version suggests experimental/unstable state.

    Args:
        version: Version string (lowercase)

    Returns:
        True if version looks experimental
    """

    if version.startswith("0.0."):
        return True

    return version in ("0.0.0", "0.0.1", "0.0.001")


def _contains_prerelease_marker(version: str) -> str | None:
    """Check if version contains a pre-release marker.

    Args:
        version: Version string (lowercase)

    Returns:
        The matched marker if found, None otherwise
    """

    for marker in PRERELEASE_MARKERS:
        if marker in version:
            return marker

    return None
