"""Detect ghost dependencies - packages imported but not declared.

Ghost dependencies are packages that are used in code (via import/require)
but not declared in package.json or requirements.txt. This creates hidden
dependencies that can break builds when node_modules or virtualenv are
recreated.

Detection Strategy:
1. Query import_styles table for all package imports
2. Query package_configs table for all declared dependencies
3. Find imports that don't have matching declarations
4. Exclude stdlib packages (built-in Python/Node.js modules)

Database Tables Used:
- import_styles: Track all import/require statements
- package_configs: Declared dependencies from package files
"""

import json
import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="ghost_dependencies",
    category="dependency",
    target_extensions=[".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "node_modules/",
        ".venv/",
        "venv/",
        "__pycache__/",
        "dist/",
        "build/",
        ".git/",
    ],
    requires_jsx_pass=False,
)


PYTHON_STDLIB = frozenset(
    [
        "os",
        "sys",
        "json",
        "time",
        "datetime",
        "math",
        "random",
        "collections",
        "itertools",
        "functools",
        "operator",
        "re",
        "string",
        "unicodedata",
        "pathlib",
        "glob",
        "fnmatch",
        "tempfile",
        "shutil",
        "subprocess",
        "threading",
        "multiprocessing",
        "queue",
        "socket",
        "ssl",
        "http",
        "urllib",
        "email",
        "base64",
        "hashlib",
        "hmac",
        "secrets",
        "uuid",
        "logging",
        "warnings",
        "traceback",
        "inspect",
        "ast",
        "typing",
        "dataclasses",
        "enum",
        "abc",
        "io",
        "pickle",
        "csv",
        "xml",
        "html",
        "sqlite3",
    ]
)


NODEJS_STDLIB = frozenset(
    [
        "fs",
        "path",
        "os",
        "util",
        "events",
        "stream",
        "buffer",
        "crypto",
        "http",
        "https",
        "net",
        "dns",
        "tls",
        "dgram",
        "url",
        "querystring",
        "zlib",
        "readline",
        "repl",
        "child_process",
        "cluster",
        "worker_threads",
        "assert",
        "console",
        "process",
        "timers",
        "module",
        "vm",
        "v8",
        "inspector",
        "async_hooks",
        "perf_hooks",
        "node:fs",
        "node:path",
        "node:os",
        "node:util",
        "node:events",
        "node:stream",
        "node:buffer",
        "node:crypto",
        "node:http",
        "node:https",
        "node:net",
        "node:dns",
        "node:tls",
        "node:url",
        "node:zlib",
        "node:child_process",
        "node:cluster",
    ]
)


ALL_STDLIB = PYTHON_STDLIB | NODEJS_STDLIB


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect packages imported in code but not declared in package files.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for ghost dependencies

    Known Limitations:
    - Cannot detect monorepo workspace dependencies
    - May flag dev dependencies that are intentionally omitted
    - Requires accurate import extraction from indexer
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        declared_deps = _get_declared_dependencies(cursor)

        imported_packages = _get_imported_packages(cursor)

        findings = _find_ghost_dependencies(cursor, imported_packages, declared_deps)

    finally:
        conn.close()

    return findings


def _get_declared_dependencies(cursor) -> set[str]:
    """Extract all declared package names from package_configs table.

    Queries package_configs and parses JSON dependency fields.

    Args:
        cursor: Database cursor

    Returns:
        Set of declared package names (normalized to lowercase)
    """
    declared = set()

    query = build_query(
        "package_configs", ["dependencies", "dev_dependencies", "peer_dependencies"]
    )
    cursor.execute(query)

    for deps_json, dev_deps_json, peer_deps_json in cursor.fetchall():
        for deps_str in [deps_json, dev_deps_json, peer_deps_json]:
            if not deps_str:
                continue

            try:
                deps_dict = json.loads(deps_str)
                if isinstance(deps_dict, dict):
                    declared.update(pkg.lower() for pkg in deps_dict)
            except (json.JSONDecodeError, AttributeError):
                continue

    return declared


def _get_imported_packages(cursor) -> dict:
    """Extract all imported package names from import_styles table.

    Args:
        cursor: Database cursor

    Returns:
        Dict mapping package names to list of (file, line) tuples
    """
    imports = {}

    query = build_query(
        "import_styles", ["file", "line", "package", "import_style"], order_by="package, file, line"
    )
    cursor.execute(query)

    for file, line, package, import_style in cursor.fetchall():
        if not package:
            continue

        base_package = _normalize_package_name(package)

        if base_package not in imports:
            imports[base_package] = []

        imports[base_package].append((file, line, package, import_style))

    return imports


def _normalize_package_name(package: str) -> str:
    """Normalize package name for comparison.

    Examples:
        'requests' -> 'requests'
        'django.contrib.auth' -> 'django'
        'lodash/map' -> 'lodash'
        '@vue/reactivity' -> '@vue/reactivity'
        'node:fs' -> 'node:fs' (keep node: prefix)

    Args:
        package: Raw package name from import

    Returns:
        Normalized base package name (lowercase)
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


def _find_ghost_dependencies(
    cursor, imported_packages: dict, declared_deps: set[str]
) -> list[StandardFinding]:
    """Find packages that are imported but not declared.

    Args:
        cursor: Database cursor
        imported_packages: Dict of package -> [(file, line, ...)]
        declared_deps: Set of declared package names

    Returns:
        List of findings for ghost dependencies
    """
    findings = []
    seen = set()

    for package, import_locations in imported_packages.items():
        if package in ALL_STDLIB:
            continue

        if package in declared_deps:
            continue

        if package in seen:
            continue
        seen.add(package)

        file, line, full_package, import_style = import_locations[0]

        findings.append(
            StandardFinding(
                rule_name="ghost-dependency",
                message=f"Package '{package}' imported but not declared in dependencies",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="dependency",
                snippet=f"import: {full_package} (style: {import_style})",
                cwe_id="CWE-1104",
            )
        )

    return findings
