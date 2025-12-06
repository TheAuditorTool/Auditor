"""Detect unused dependencies - packages declared but never imported.

Flags dependencies that are declared in package manifests but never
imported in the codebase. Unused dependencies increase attack surface
and bundle size without providing value.

Detection includes:
- Direct imports (import/require)
- Package.json script references
- CLI tools and build plugins
- Type definition packages

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


CLI_PACKAGES: frozenset[str] = frozenset(
    [
        "eslint",
        "prettier",
        "typescript",
        "tsc",
        "ts-node",
        "tsx",
        "nodemon",
        "concurrently",
        "npm-run-all",
        "husky",
        "lint-staged",
        "commitlint",
        "semantic-release",
        "cross-env",
        "dotenv-cli",
        "rimraf",
        "copyfiles",
        "shx",
        "ncp",
    ]
)


PLUGIN_PACKAGES: frozenset[str] = frozenset(
    [
        "@babel/preset-env",
        "@babel/preset-react",
        "@babel/preset-typescript",
        "@babel/plugin-transform-runtime",
        "eslint-plugin-react",
        "eslint-plugin-react-hooks",
        "eslint-plugin-import",
        "eslint-plugin-jsx-a11y",
        "eslint-config-prettier",
        "eslint-config-airbnb",
        "autoprefixer",
        "postcss-preset-env",
        "tailwindcss",
        "cssnano",
        "babel-loader",
        "css-loader",
        "style-loader",
        "file-loader",
        "url-loader",
        "sass-loader",
        "less-loader",
        "postcss-loader",
        "ts-loader",
        "html-webpack-plugin",
        "mini-css-extract-plugin",
        "terser-webpack-plugin",
    ]
)


STYLING_PACKAGES: frozenset[str] = frozenset(
    [
        "normalize.css",
        "reset-css",
        "sanitize.css",
        "modern-normalize",
        "animate.css",
        "font-awesome",
        "@fortawesome/fontawesome-free",
    ]
)


PYTHON_IMPORT_MAP: dict[str, str] = {
    "pyyaml": "yaml",
    "beautifulsoup4": "bs4",
    "pillow": "pil",
    "scikit-learn": "sklearn",
    "python-dateutil": "dateutil",
    "python-dotenv": "dotenv",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "typing-extensions": "typing_extensions",
    "importlib-metadata": "importlib_metadata",
    "importlib-resources": "importlib_resources",
    "attrs": "attr",
    "ruamel.yaml": "ruamel",
    "google-cloud-storage": "google",
    "google-auth": "google",
    "protobuf": "google",
}


PYTHON_DEV_TOOLS: frozenset[str] = frozenset(
    [
        "pytest",
        "pytest-cov",
        "pytest-asyncio",
        "pytest-mock",
        "pytest-xdist",
        "black",
        "mypy",
        "flake8",
        "pylint",
        "ruff",
        "tox",
        "coverage",
        "isort",
        "pre-commit",
        "pip-tools",
        "build",
        "twine",
        "wheel",
        "setuptools",
        "hatch",
        "flit",
        "poetry",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect packages declared in dependencies but never imported.

    Cross-references declared dependencies against:
    - Direct imports in source code
    - Package.json scripts
    - Known CLI tools and plugins

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        imported_packages = _get_imported_packages(db)

        script_packages = _get_script_referenced_packages(db)

        used_packages = imported_packages | script_packages

        findings.extend(_check_js_unused(db, used_packages))

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

    rows = db.query(Q("import_styles").select("package").order_by("package"))

    for (package,) in rows:
        if not package:
            continue
        base_package = _normalize_package_name(package)
        imported.add(base_package)

    return imported


def _get_script_referenced_packages(db: RuleDB) -> set[str]:
    """Get packages referenced in package.json scripts.

    Parses script commands to find direct package references.

    Args:
        db: RuleDB instance

    Returns:
        Set of package names referenced in scripts
    """
    referenced: set[str] = set()

    rows = db.query(
        Q("package_scripts").select("script_name", "script_command").order_by("script_name")
    )

    for _script_name, script_command in rows:
        if not script_command:
            continue

        parts = script_command.split()
        if parts:
            first_cmd = parts[0]

            if first_cmd in ("cross-env", "npx", "pnpx", "yarn"):
                if len(parts) > 1:
                    first_cmd = parts[1]

            cmd_clean = first_cmd.split("/")[-1]
            if cmd_clean and not cmd_clean.startswith("-"):
                referenced.add(cmd_clean.lower())

    return referenced


def _check_js_unused(db: RuleDB, used: set[str]) -> list[StandardFinding]:
    """Check JavaScript package dependencies for unused packages.

    Args:
        db: RuleDB instance
        used: Set of packages that are imported or referenced

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
        if is_peer:
            continue

        normalized = _normalize_package_name(pkg_name)

        if normalized in used:
            continue

        if _is_exempt_package(pkg_name):
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

        mapped_import = PYTHON_IMPORT_MAP.get(normalized, normalized)

        if normalized in imported or mapped_import in imported:
            continue

        if normalized in PYTHON_DEV_TOOLS:
            continue

        if _is_exempt_package(pkg_name):
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

    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]).lower()
        return package.lower()

    if package.startswith("node:"):
        return package.lower()

    base = package.split("/")[0].split(".")[0]
    return base.lower()


def _is_exempt_package(package: str) -> bool:
    """Check if package is exempt from unused detection.

    Args:
        package: Package name

    Returns:
        True if package should not be flagged as unused
    """
    pkg_lower = package.lower()

    if pkg_lower in CLI_PACKAGES:
        return True

    if pkg_lower in DEV_ONLY_PACKAGES:
        return True

    if pkg_lower in PLUGIN_PACKAGES:
        return True

    if pkg_lower in STYLING_PACKAGES:
        return True

    if package.startswith("@types/"):
        return True

    exempt_patterns = (
        "eslint-",
        "prettier-",
        "@babel/",
        "webpack-",
        "rollup-",
        "vite-",
        "-loader",
        "-plugin",
        "-preset",
        "-config",
    )
    return bool(any(pattern in pkg_lower for pattern in exempt_patterns))
