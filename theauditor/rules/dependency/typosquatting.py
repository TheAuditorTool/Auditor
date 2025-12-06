"""Detect potential typosquatting in package names.

Typosquatting is a supply chain attack where malicious packages use names
that are slight misspellings of popular packages, hoping developers will
accidentally install them.

Detection methods:
1. Known typosquat patterns (static map)
2. Levenshtein distance to popular packages (algorithmic detection)
3. Common typosquat patterns (character swaps, doubles, omissions)

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


POPULAR_PACKAGES: frozenset[str] = frozenset(
    [
        "lodash",
        "express",
        "react",
        "axios",
        "moment",
        "chalk",
        "commander",
        "request",
        "debug",
        "async",
        "bluebird",
        "underscore",
        "uuid",
        "mkdirp",
        "glob",
        "minimist",
        "yargs",
        "inquirer",
        "semver",
        "body-parser",
        "webpack",
        "babel",
        "typescript",
        "eslint",
        "prettier",
        "jest",
        "mocha",
        "vue",
        "angular",
        "jquery",
        "bootstrap",
        "tailwindcss",
        "next",
        "nuxt",
        "socket.io",
        "mongoose",
        "sequelize",
        "knex",
        "pg",
        "mysql",
        "redis",
        "jsonwebtoken",
        "bcrypt",
        "passport",
        "helmet",
        "cors",
        "dotenv",
        "requests",
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "pillow",
        "django",
        "flask",
        "fastapi",
        "sqlalchemy",
        "celery",
        "redis",
        "boto3",
        "tensorflow",
        "pytorch",
        "scikit-learn",
        "keras",
        "pyyaml",
        "pydantic",
        "httpx",
        "aiohttp",
        "beautifulsoup4",
        "cryptography",
        "paramiko",
        "fabric",
        "ansible",
        "pytest",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect potential typosquatting in package names.

    Uses multiple detection methods:
    1. Known typosquat patterns from static map
    2. Levenshtein distance to popular packages
    3. Pattern-based detection (swaps, doubles, omissions)

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_js_declared_packages(db))

        findings.extend(_check_python_declared_packages(db))

        findings.extend(_check_imported_packages(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_js_declared_packages(db: RuleDB) -> list[StandardFinding]:
    """Check declared JavaScript dependencies for typosquatting."""
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    rows = db.query(
        Q("package_dependencies").select("file_path", "name", "is_dev").order_by("file_path, name")
    )

    for file_path, pkg_name, is_dev in rows:
        if not pkg_name:
            continue

        pkg_lower = pkg_name.lower()
        if pkg_lower in seen:
            continue

        typosquat_info = _detect_typosquat(pkg_lower)
        if typosquat_info:
            correct_name, detection_method = typosquat_info
            seen.add(pkg_lower)
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Potential typosquatting: {dep_type} '{pkg_name}' may be a typosquat of '{correct_name}' ({detection_method})",
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
    """Check declared Python dependencies for typosquatting."""
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

        typosquat_info = _detect_typosquat(pkg_lower)
        if typosquat_info:
            correct_name, detection_method = typosquat_info
            seen.add(pkg_lower)
            dep_type = "dev dependency" if is_dev else "dependency"

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Potential typosquatting: Python {dep_type} '{pkg_name}' may be a typosquat of '{correct_name}' ({detection_method})",
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
    """Check imported packages in source code for typosquatting."""
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    rows = db.query(
        Q("import_styles").select("file", "line", "package").order_by("package, file, line")
    )

    for file_path, line, package in rows:
        if not package:
            continue

        base_package = _get_base_package(package)
        if base_package in seen:
            continue

        typosquat_info = _detect_typosquat(base_package)
        if typosquat_info:
            correct_name, detection_method = typosquat_info
            seen.add(base_package)

            findings.append(
                StandardFinding(
                    rule_name=METADATA.name,
                    message=f"Importing potentially typosquatted package: '{base_package}' may be a typosquat of '{correct_name}' ({detection_method})",
                    file_path=file_path,
                    line=line,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=f"import {package}",
                    cwe_id="CWE-1357",
                )
            )

    return findings


def _detect_typosquat(pkg_name: str) -> tuple[str, str] | None:
    """Detect if package name is a potential typosquat.

    Args:
        pkg_name: Package name to check (lowercase)

    Returns:
        Tuple of (correct_name, detection_method) if typosquat detected, None otherwise
    """

    if pkg_name in TYPOSQUATTING_MAP:
        return (TYPOSQUATTING_MAP[pkg_name], "known pattern")

    if pkg_name in POPULAR_PACKAGES:
        return None

    for popular in POPULAR_PACKAGES:
        distance = _levenshtein_distance(pkg_name, popular)

        if len(popular) >= 4 and 0 < distance <= 2:
            if abs(len(pkg_name) - len(popular)) <= 2:
                return (popular, f"similar name (edit distance: {distance})")

    pattern_match = _check_typosquat_patterns(pkg_name)
    if pattern_match:
        return pattern_match

    return None


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Number of edits needed to transform s1 to s2
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _check_typosquat_patterns(pkg_name: str) -> tuple[str, str] | None:
    """Check for common typosquatting patterns.

    Patterns checked:
    - Doubled characters (requestss)
    - Missing hyphens (bodyparser vs body-parser)
    - Hyphen vs underscore (body_parser vs body-parser)
    - Common prefixes (python-requests, py-requests)

    Args:
        pkg_name: Package name to check

    Returns:
        Tuple of (correct_name, pattern_description) if match found
    """

    if len(pkg_name) > 3 and pkg_name[-1] == pkg_name[-2]:
        potential = pkg_name[:-1]
        if potential in POPULAR_PACKAGES:
            return (potential, "doubled character")

    if "-" in pkg_name:
        underscore_variant = pkg_name.replace("-", "_")
        if underscore_variant in POPULAR_PACKAGES:
            return (underscore_variant, "hyphen/underscore confusion")
    if "_" in pkg_name:
        hyphen_variant = pkg_name.replace("_", "-")
        if hyphen_variant in POPULAR_PACKAGES:
            return (hyphen_variant, "hyphen/underscore confusion")

    for popular in POPULAR_PACKAGES:
        if "-" in popular:
            no_hyphen = popular.replace("-", "")
            if pkg_name == no_hyphen:
                return (popular, "missing hyphen")

    suspicious_prefixes = ("python-", "py-", "node-", "js-", "npm-")
    for prefix in suspicious_prefixes:
        if pkg_name.startswith(prefix):
            base = pkg_name[len(prefix) :]
            if base in POPULAR_PACKAGES:
                return (base, f"suspicious prefix '{prefix}'")

    return None


def _get_base_package(package: str) -> str:
    """Extract base package name from import path.

    Args:
        package: Full import path (e.g., "lodash/merge")

    Returns:
        Base package name in lowercase (e.g., "lodash")
    """

    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]).lower()
        return package.lower()

    base = package.split("/")[0].split(".")[0]
    return base.lower()
