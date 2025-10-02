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

import sqlite3
import json
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA
# ============================================================================

METADATA = RuleMetadata(
    name="ghost_dependencies",
    category="dependency",
    target_extensions=['.py', '.js', '.ts', '.tsx', '.jsx', '.mjs', '.cjs'],
    exclude_patterns=[
        'node_modules/',
        '.venv/',
        'venv/',
        '__pycache__/',
        'dist/',
        'build/',
        '.git/',
    ],
    requires_jsx_pass=False,
)


# ============================================================================
# STDLIB EXCLUSIONS
# ============================================================================
# Built-in modules that don't need to be declared in package files
# ============================================================================

# Python standard library modules (partial list - common ones)
PYTHON_STDLIB = frozenset([
    'os', 'sys', 'json', 'time', 'datetime', 'math', 'random',
    'collections', 'itertools', 'functools', 'operator',
    're', 'string', 'unicodedata',
    'pathlib', 'glob', 'fnmatch', 'tempfile', 'shutil',
    'subprocess', 'threading', 'multiprocessing', 'queue',
    'socket', 'ssl', 'http', 'urllib', 'email', 'base64',
    'hashlib', 'hmac', 'secrets', 'uuid',
    'logging', 'warnings', 'traceback', 'inspect', 'ast',
    'typing', 'dataclasses', 'enum', 'abc',
    'io', 'pickle', 'csv', 'xml', 'html', 'sqlite3',
])

# Node.js core modules (all don't need package.json entries)
NODEJS_STDLIB = frozenset([
    'fs', 'path', 'os', 'util', 'events', 'stream', 'buffer',
    'crypto', 'http', 'https', 'net', 'dns', 'tls', 'dgram',
    'url', 'querystring', 'zlib', 'readline', 'repl',
    'child_process', 'cluster', 'worker_threads',
    'assert', 'console', 'process', 'timers', 'module',
    'vm', 'v8', 'inspector', 'async_hooks', 'perf_hooks',
    # Node.js prefixed variants
    'node:fs', 'node:path', 'node:os', 'node:util', 'node:events',
    'node:stream', 'node:buffer', 'node:crypto', 'node:http',
    'node:https', 'node:net', 'node:dns', 'node:tls',
    'node:url', 'node:zlib', 'node:child_process', 'node:cluster',
])

# Combined stdlib set
ALL_STDLIB = PYTHON_STDLIB | NODEJS_STDLIB


# ============================================================================
# MAIN DETECTION FUNCTION
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
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
        # Check if required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = {row[0] for row in cursor.fetchall()}

        if 'import_styles' not in available_tables:
            return findings
        if 'package_configs' not in available_tables:
            return findings

        # Get all declared dependencies from package files
        declared_deps = _get_declared_dependencies(cursor)

        # Get all imported packages from code
        imported_packages = _get_imported_packages(cursor)

        # Find ghost dependencies
        findings = _find_ghost_dependencies(
            cursor,
            imported_packages,
            declared_deps
        )

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_declared_dependencies(cursor) -> Set[str]:
    """Extract all declared package names from package_configs table.

    Queries package_configs and parses JSON dependency fields.

    Args:
        cursor: Database cursor

    Returns:
        Set of declared package names (normalized to lowercase)
    """
    declared = set()

    cursor.execute("""
        SELECT dependencies, dev_dependencies, peer_dependencies
        FROM package_configs
    """)

    for deps_json, dev_deps_json, peer_deps_json in cursor.fetchall():
        # Parse dependencies JSON
        for deps_str in [deps_json, dev_deps_json, peer_deps_json]:
            if not deps_str:
                continue

            try:
                deps_dict = json.loads(deps_str)
                if isinstance(deps_dict, dict):
                    # Add all package names (normalized to lowercase)
                    declared.update(pkg.lower() for pkg in deps_dict.keys())
            except (json.JSONDecodeError, AttributeError):
                # Malformed JSON - skip
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

    cursor.execute("""
        SELECT DISTINCT file, line, package, import_style
        FROM import_styles
        ORDER BY package, file, line
    """)

    for file, line, package, import_style in cursor.fetchall():
        if not package:
            continue

        # Normalize package name
        # For scoped packages (@org/pkg), keep full name
        # For submodule imports (pkg/submodule), extract base package
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
    # Handle scoped packages (@org/pkg)
    if package.startswith('@'):
        # Keep scoped package intact
        parts = package.split('/', 2)
        if len(parts) >= 2:
            return '/'.join(parts[:2]).lower()
        return package.lower()

    # Handle node:* prefixed core modules
    if package.startswith('node:'):
        return package.lower()

    # Handle submodule imports (pkg/submodule)
    base = package.split('/')[0].split('.')[0]

    return base.lower()


def _find_ghost_dependencies(
    cursor,
    imported_packages: dict,
    declared_deps: Set[str]
) -> List[StandardFinding]:
    """Find packages that are imported but not declared.

    Args:
        cursor: Database cursor
        imported_packages: Dict of package -> [(file, line, ...)]
        declared_deps: Set of declared package names

    Returns:
        List of findings for ghost dependencies
    """
    findings = []
    seen = set()  # Deduplicate by package name

    for package, import_locations in imported_packages.items():
        # Skip stdlib modules
        if package in ALL_STDLIB:
            continue

        # Skip if declared
        if package in declared_deps:
            continue

        # Skip if already reported
        if package in seen:
            continue
        seen.add(package)

        # Get first import location for error reporting
        file, line, full_package, import_style = import_locations[0]

        findings.append(StandardFinding(
            rule_name='ghost-dependency',
            message=f"Package '{package}' imported but not declared in dependencies",
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='dependency',
            snippet=f"import: {full_package} (style: {import_style})",
            cwe_id='CWE-1104'  # Use of Unmaintained Third Party Components
        ))

    return findings
