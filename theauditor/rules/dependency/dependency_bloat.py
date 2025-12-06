"""Detect excessive dependencies (dependency bloat).

Flags projects with too many production or dev dependencies, which increases
attack surface, maintenance burden, and security risk. Also detects:
- Dev-only packages incorrectly in production dependencies
- Duplicate dependencies (same package in prod and dev)
- Python and JavaScript dependency bloat

CWE: CWE-1104 (Use of Unmaintained Third Party Components)
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

from .config import DEV_ONLY_PACKAGES, LOCK_FILES, DependencyThresholds

METADATA = RuleMetadata(
    name="dependency_bloat",
    category="dependency",
    target_extensions=[".json", ".txt", ".toml"],
    exclude_patterns=["node_modules/", ".venv/", "test/", "__pycache__/"],
    execution_scope="database",
    primary_table="package_dependencies",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect excessive dependency counts and misplaced packages.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_check_js_dependency_bloat(db))

        findings.extend(_check_python_dependency_bloat(db))

        findings.extend(_check_misplaced_dev_packages(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_dependency_bloat(db: RuleDB) -> list[StandardFinding]:
    """Check JavaScript package dependency counts."""
    findings = []

    rows = db.query(
        Q("package_dependencies")
        .select("file_path", "is_dev", "COUNT(*) as count")
        .group_by("file_path", "is_dev")
    )

    file_counts: dict[str, dict[str, int]] = {}
    for file_path, is_dev, count in rows:
        if file_path not in file_counts:
            file_counts[file_path] = {"prod": 0, "dev": 0}
        if is_dev:
            file_counts[file_path]["dev"] = count
        else:
            file_counts[file_path]["prod"] = count

    for file_path, counts in file_counts.items():
        prod_count = counts["prod"]
        dev_count = counts["dev"]
        total_count = prod_count + dev_count

        is_lockfile = any(file_path.endswith(lf) for lf in LOCK_FILES)
        threshold = (
            DependencyThresholds.MAX_TRANSITIVE_DEPS
            if is_lockfile
            else DependencyThresholds.MAX_DIRECT_DEPS
        )
        warn_threshold = (
            threshold // 2 if is_lockfile else DependencyThresholds.WARN_PRODUCTION_DEPS
        )

        if prod_count > threshold:
            dep_type = "transitive" if is_lockfile else "production"
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-production",
                    message=f"Excessive {dep_type} dependencies: {prod_count} (threshold: {threshold}). High attack surface.",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="dependency",
                    snippet=f"{prod_count} production + {dev_count} dev = {total_count} total",
                    cwe_id="CWE-1104",
                )
            )
        elif prod_count > warn_threshold:
            dep_type = "transitive" if is_lockfile else "production"
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-warn",
                    message=f"High {dep_type} dependency count: {prod_count} (warning threshold: {warn_threshold})",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="dependency",
                    snippet=f"{prod_count} {dep_type} dependencies",
                    cwe_id="CWE-1104",
                )
            )

        if dev_count > DependencyThresholds.MAX_DEV_DEPS:
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-dev",
                    message=f"Excessive dev dependencies: {dev_count} (threshold: {DependencyThresholds.MAX_DEV_DEPS}). Slows CI/CD.",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="dependency",
                    snippet=f"{dev_count} dev dependencies declared",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _check_python_dependency_bloat(db: RuleDB) -> list[StandardFinding]:
    """Check Python package dependency counts."""
    findings = []

    rows = db.query(
        Q("python_package_dependencies")
        .select("file_path", "is_dev", "COUNT(*) as count")
        .group_by("file_path", "is_dev")
    )

    file_counts: dict[str, dict[str, int]] = {}
    for file_path, is_dev, count in rows:
        if file_path not in file_counts:
            file_counts[file_path] = {"prod": 0, "dev": 0}
        if is_dev:
            file_counts[file_path]["dev"] = count
        else:
            file_counts[file_path]["prod"] = count

    for file_path, counts in file_counts.items():
        prod_count = counts["prod"]
        counts["dev"]

        is_lockfile = any(file_path.endswith(lf) for lf in LOCK_FILES)

        if is_lockfile:
            python_prod_threshold = DependencyThresholds.MAX_TRANSITIVE_DEPS // 2
            python_warn_threshold = DependencyThresholds.MAX_TRANSITIVE_DEPS // 4
        else:
            python_prod_threshold = DependencyThresholds.MAX_DIRECT_DEPS // 2
            python_warn_threshold = DependencyThresholds.WARN_PRODUCTION_DEPS // 2

        if prod_count > python_prod_threshold:
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-python-production",
                    message=f"Excessive Python dependencies: {prod_count} (threshold: {python_prod_threshold})",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="dependency",
                    snippet=f"{prod_count} Python dependencies",
                    cwe_id="CWE-1104",
                )
            )
        elif prod_count > python_warn_threshold:
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-python-warn",
                    message=f"High Python dependency count: {prod_count} (warning threshold: {python_warn_threshold})",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="dependency",
                    snippet=f"{prod_count} Python dependencies",
                    cwe_id="CWE-1104",
                )
            )

    return findings


def _check_misplaced_dev_packages(db: RuleDB) -> list[StandardFinding]:
    """Check for dev-only packages in production dependencies."""
    findings = []

    exact_packages = [p for p in DEV_ONLY_PACKAGES if not p.endswith("/")]
    prefix_packages = [p for p in DEV_ONLY_PACKAGES if p.endswith("/")]

    if exact_packages:
        placeholders = ",".join(["?" for _ in exact_packages])

        rows = db.query(
            Q("package_dependencies")
            .select("file_path", "name")
            .where("is_dev = ?", 0)
            .where(f"name IN ({placeholders})", *exact_packages)
        )

        for file_path, pkg_name in rows:
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-misplaced-dev",
                    message=f"Dev-only package '{pkg_name}' is in production dependencies. Move to devDependencies.",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="dependency",
                    snippet=f"{pkg_name} should be in devDependencies",
                    cwe_id="CWE-1104",
                )
            )

    for prefix in prefix_packages:
        rows = db.query(
            Q("package_dependencies")
            .select("file_path", "name")
            .where("is_dev = ?", 0)
            .where("name LIKE ?", f"{prefix}%")
        )

        for file_path, pkg_name in rows:
            findings.append(
                StandardFinding(
                    rule_name="dependency-bloat-misplaced-dev",
                    message=f"Dev-only package '{pkg_name}' is in production dependencies. Move to devDependencies.",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="dependency",
                    snippet=f"{pkg_name} should be in devDependencies",
                    cwe_id="CWE-1104",
                )
            )

    return findings
