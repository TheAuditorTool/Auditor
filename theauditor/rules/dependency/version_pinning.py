"""Detect unpinned dependency versions in production code.

Flags dependencies using version ranges (^, ~, >, <, >=, <=, ||) which can lead
to supply chain attacks when malicious versions are published within the range.
Also detects git URLs, file references, and HTTP URLs which bypass lockfile
guarantees entirely.

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

# Patterns that indicate non-registry sources (bypass lockfile entirely)
GIT_PREFIXES: frozenset[str] = frozenset([
    "git://",
    "git+ssh://",
    "git+https://",
    "git+http://",
    "github:",
    "gitlab:",
    "bitbucket:",
])

URL_PREFIXES: frozenset[str] = frozenset([
    "http://",
    "https://",
])

FILE_PREFIXES: frozenset[str] = frozenset([
    "file:",
    "link:",
    "portal:",  # pnpm portal protocol
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect unpinned version ranges in production dependencies.

    Checks both JavaScript (package_dependencies) and Python
    (python_package_dependencies) for:
    - Version ranges (^, ~, >, <) that allow automatic updates
    - Git URLs that bypass registry and lockfile
    - File references that may change without version tracking
    - HTTP URLs that could serve different content over time

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
        issue = _classify_version_issue(version_str)

        if issue:
            issue_type, severity_boost, description = issue
            # Lower severity for dev/peer dependencies, but git URLs stay HIGH
            base_severity = Severity.HIGH if severity_boost else Severity.MEDIUM
            if is_dev or is_peer:
                severity = Severity.MEDIUM if severity_boost else Severity.LOW
            else:
                severity = base_severity

            dep_type = "dev" if is_dev else ("peer" if is_peer else "production")

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"{dep_type.capitalize()} dependency '{pkg_name}' {description}",
                    file_path=file_path,
                    line=1,
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
        .select("file_path", "name", "version_spec", "is_dev", "git_url")
        .order_by("file_path, name")
    )

    for file_path, pkg_name, version_spec, is_dev, git_url in rows:
        # Check git_url column directly (Python package schema has it)
        if git_url:
            severity = Severity.MEDIUM if is_dev else Severity.HIGH
            dep_type = "dev" if is_dev else "production"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Python {dep_type} dependency '{pkg_name}' uses git URL (bypasses PyPI)",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name} @ {git_url[:50]}...",
                    cwe_id="CWE-1104",
                )
            )
            continue

        if not version_spec:
            continue

        version_str = str(version_spec).strip()
        issue = _classify_version_issue(version_str)

        if issue:
            issue_type, severity_boost, description = issue
            base_severity = Severity.HIGH if severity_boost else Severity.MEDIUM
            severity = Severity.MEDIUM if is_dev and severity_boost else (Severity.LOW if is_dev else base_severity)
            dep_type = "dev" if is_dev else "production"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Python {dep_type} dependency '{pkg_name}' {description}",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category=METADATA.category,
                    snippet=f"{pkg_name}{version_str}",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _classify_version_issue(version_str: str) -> tuple[str, bool, str] | None:
    """Classify version string issue type.

    Args:
        version_str: Version specification string

    Returns:
        Tuple of (issue_type, is_high_severity, description) or None if clean
    """
    version_lower = version_str.lower()

    # Check for git URLs (HIGH severity - bypasses lockfile entirely)
    for prefix in GIT_PREFIXES:
        if version_lower.startswith(prefix):
            return ("git", True, f"uses git URL '{version_str[:40]}...' (bypasses registry lockfile)")

    # Check for HTTP URLs (HIGH severity - content can change)
    for prefix in URL_PREFIXES:
        if version_lower.startswith(prefix):
            return ("url", True, f"uses HTTP URL (content may change without version bump)")

    # Check for file references (MEDIUM severity - local but untracked)
    for prefix in FILE_PREFIXES:
        if version_lower.startswith(prefix):
            return ("file", False, f"uses local file reference '{version_str}' (not version controlled)")

    # Check for npm: alias protocol
    if version_lower.startswith("npm:"):
        # npm:package@version is actually okay if version is pinned
        # but npm:package without version is dangerous
        if "@" not in version_str[4:]:
            return ("alias", True, f"uses npm alias without version '{version_str}'")

    # Check for workspace protocol (usually okay but flag it)
    if version_lower.startswith("workspace:"):
        # workspace:* is unpinned, workspace:^1.0.0 has range
        if "*" in version_str or "^" in version_str or "~" in version_str:
            return ("workspace", False, f"uses unpinned workspace reference '{version_str}'")

    # Check for range prefixes (MEDIUM severity - allows auto-updates)
    for prefix in RANGE_PREFIXES:
        if version_str.startswith(prefix):
            return ("range", False, f"uses unpinned version '{version_str}'")

    return None
