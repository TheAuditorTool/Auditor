"""Detect unused dependencies - packages declared but never imported.

Unused dependencies bloat package size, increase installation time, and
create unnecessary security surface area. This rule finds packages that
are declared in package.json or requirements.txt but never actually used.

Detection Strategy:
1. Query package_configs for all declared dependencies
2. Query import_styles for all actual imports
3. Find declared packages with zero imports
4. Exclude dev dependencies that may not be directly imported

Database Tables Used:
- package_configs: Declared dependencies from package files
- import_styles: Actual import/require statements in code
"""


import sqlite3
import json
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query


METADATA = RuleMetadata(
    name="unused_dependencies",
    category="dependency",
    target_extensions=['.json', '.txt', '.toml', '.lock'],  # Package files only
    exclude_patterns=['node_modules/', '.venv/', 'venv/', 'dist/', 'build/'],
    execution_scope='database',
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect packages declared in dependencies but never imported.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for unused dependencies
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Get declared dependencies with file locations
        declared_deps = _get_declared_with_locations(cursor)

        # Get all imported package names
        imported_packages = _get_imported_package_names(cursor)

        # Find unused dependencies
        findings = _find_unused(declared_deps, imported_packages)

    finally:
        conn.close()

    return findings


def _get_declared_with_locations(cursor) -> dict[str, tuple]:
    """Get declared dependencies with their file locations.

    Returns:
        Dict mapping package name -> (file_path, is_dev_dep, is_peer_dep)
    """
    declared = {}

    query = build_query('package_configs', ['file_path', 'dependencies', 'dev_dependencies', 'peer_dependencies'])
    cursor.execute(query)

    for file_path, deps, dev_deps, peer_deps in cursor.fetchall():
        # Production dependencies
        if deps:
            try:
                deps_dict = json.loads(deps)
                if isinstance(deps_dict, dict):
                    for pkg in deps_dict.keys():
                        declared[pkg.lower()] = (file_path, False, False)
            except json.JSONDecodeError:
                pass

        # Dev dependencies (lower priority for unused check)
        if dev_deps:
            try:
                dev_dict = json.loads(dev_deps)
                if isinstance(dev_dict, dict):
                    for pkg in dev_dict.keys():
                        if pkg.lower() not in declared:  # Don't override production deps
                            declared[pkg.lower()] = (file_path, True, False)
            except json.JSONDecodeError:
                pass

        # Peer dependencies (usually required by frameworks, not directly imported)
        if peer_deps:
            try:
                peer_dict = json.loads(peer_deps)
                if isinstance(peer_dict, dict):
                    for pkg in peer_dict.keys():
                        if pkg.lower() not in declared:
                            declared[pkg.lower()] = (file_path, False, True)
            except json.JSONDecodeError:
                pass

    return declared


def _get_imported_package_names(cursor) -> set[str]:
    """Get all imported package names (normalized).

    Returns:
        Set of imported package names (lowercase, base package only)
    """
    imported = set()

    query = build_query('import_styles', ['package'])
    cursor.execute(query)

    for (package,) in cursor.fetchall():
        if not package:
            continue

        # Normalize to base package name
        base_package = _normalize_package_name(package)
        imported.add(base_package)

    return imported


def _normalize_package_name(package: str) -> str:
    """Normalize package name to base package (same logic as ghost_dependencies)."""
    if package.startswith('@'):
        parts = package.split('/', 2)
        if len(parts) >= 2:
            return '/'.join(parts[:2]).lower()
        return package.lower()

    if package.startswith('node:'):
        return package.lower()

    base = package.split('/')[0].split('.')[0]
    return base.lower()


def _find_unused(declared_deps: dict[str, tuple], imported: set[str]) -> list[StandardFinding]:
    """Find declared dependencies that are never imported.

    Args:
        declared_deps: Dict of package -> (file, is_dev, is_peer)
        imported: Set of imported package names

    Returns:
        List of findings for unused dependencies
    """
    findings = []

    for package, (file_path, is_dev, is_peer) in declared_deps.items():
        # Skip peer dependencies (they may not be directly imported)
        if is_peer:
            continue

        # Check if imported
        if package in imported:
            continue

        # Determine severity
        if is_dev:
            severity = Severity.LOW  # Dev deps less critical
            message = f"Dev dependency '{package}' declared but never imported"
        else:
            severity = Severity.MEDIUM  # Production deps more important
            message = f"Production dependency '{package}' declared but never imported"

        findings.append(StandardFinding(
            rule_name='unused-dependency',
            message=message,
            file_path=file_path,
            line=1,  # Package files don't have specific line numbers
            severity=severity,
            category='dependency',
            snippet=f"Declared in {file_path}",
        ))

    return findings
