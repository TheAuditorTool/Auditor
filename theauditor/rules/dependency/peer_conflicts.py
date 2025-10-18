"""Detect peer dependency mismatches (database-first implementation).

This rule detects when declared peer dependencies don't match actual installed versions
by checking the package_configs table. It doesn't require lock file parsing.

Detection Strategy:
1. Query peer_dependencies from package_configs
2. Query actual installed versions from same table
3. Check if peer requirements are satisfied
4. Flag mismatches (e.g., package requires React ^17 but project has React 18)

Database Tables Used:
- package_configs: Peer dependency declarations and actual versions
"""

import json
import sqlite3
from typing import List, Dict
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query


METADATA = RuleMetadata(
    name="peer_conflicts",
    category="dependency",
    target_extensions=['.json'],  # Only npm packages have peer dependencies
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect peer dependency version mismatches.

    Checks if peer dependency requirements match actual installed versions.
    Common issue: Installing a library that requires React ^17 when project uses React 18.

    Args:
        context: Rule execution context

    Returns:
        List of findings for peer dependency conflicts
    """
    findings = []

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        # Load all packages with their versions and peer dependencies
        query = build_query('package_configs', ['file_path', 'package_name', 'version', 'peer_dependencies'],
                           where='peer_dependencies IS NOT NULL')
        cursor.execute(query)
        # ✅ FIX: Store first query results before executing second query (Phase 3C fix preserved)
        packages_with_peers = cursor.fetchall()

        # Build map of installed packages and their versions
        installed_versions: Dict[str, str] = {}
        query = build_query('package_configs', ['package_name', 'version'])
        cursor.execute(query)
        for pkg_name, version in cursor.fetchall():
            if version:
                installed_versions[pkg_name] = version

        # Check each package's peer dependencies
        for file_path, pkg_name, version, peer_deps_json in packages_with_peers:
            if not peer_deps_json:
                continue

            try:
                peer_deps = json.loads(peer_deps_json)
                if not isinstance(peer_deps, dict):
                    continue

                for peer_name, peer_requirement in peer_deps.items():
                    if not peer_name or not peer_requirement:
                        continue

                    # Check if peer dependency is installed
                    actual_version = installed_versions.get(peer_name)

                    if not actual_version:
                        # Peer dependency not installed
                        findings.append(StandardFinding(
                            file_path=file_path,
                            line=1,
                            rule_name='peer-dependency-missing',
                            message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' ({peer_requirement}) but it is not installed",
                            severity=Severity.MEDIUM,
                            category='dependency',
                            snippet=f"{pkg_name} requires {peer_name}: {peer_requirement}",
                            cwe_id='CWE-1104'  # Use of Unmaintained Third Party Components
                        ))
                        continue

                    # Check for major version mismatch (simple heuristic)
                    # This detects obvious conflicts like "^17.0.0" vs "18.2.0"
                    if _has_major_version_mismatch(peer_requirement, actual_version):
                        findings.append(StandardFinding(
                            file_path=file_path,
                            line=1,
                            rule_name='peer-dependency-conflict',
                            message=f"Package '{pkg_name}' requires peer dependency '{peer_name}' {peer_requirement}, but version {actual_version} is installed",
                            severity=Severity.HIGH,
                            category='dependency',
                            snippet=f"{pkg_name} requires {peer_name} {peer_requirement} (installed: {actual_version})",
                            cwe_id='CWE-1104'
                        ))

            except json.JSONDecodeError:
                continue

        conn.close()

    except sqlite3.Error:
        # Database error - silently fail
        pass

    return findings


def _has_major_version_mismatch(requirement: str, actual: str) -> bool:
    """Check if requirement and actual version have major version mismatch.

    This is a simple heuristic that detects obvious conflicts.
    Examples:
        requirement="^17.0.0", actual="18.2.0" → True (mismatch)
        requirement="^17.0.0", actual="17.5.0" → False (compatible)
        requirement=">=16.0.0", actual="18.2.0" → False (compatible)

    Args:
        requirement: Version requirement string (e.g., "^17.0.0", ">=16.0.0")
        actual: Actual installed version (e.g., "18.2.0")

    Returns:
        True if there's a major version mismatch
    """
    try:
        # Extract required major version
        # Handle npm version ranges: ^, ~, >=, >, <, <=, *, x
        req_clean = requirement.lstrip('^~<>=vV').split('.')[0]
        if req_clean in ('*', 'x', 'X', ''):
            return False  # Wildcard matches anything

        req_major = int(req_clean)

        # Extract actual major version
        actual_clean = actual.lstrip('vV').split('.')[0]
        actual_major = int(actual_clean)

        # Check for mismatch based on range operator
        if requirement.startswith('^'):
            # Caret (^) allows changes that don't modify left-most non-zero digit
            # ^17.0.0 means >=17.0.0 <18.0.0
            return actual_major != req_major
        elif requirement.startswith('~'):
            # Tilde (~) allows patch-level changes
            # ~17.0.0 means >=17.0.0 <17.1.0
            return actual_major != req_major
        elif requirement.startswith('>='):
            # Greater than or equal - actual must be >= required
            return actual_major < req_major
        elif requirement.startswith('>'):
            # Greater than - actual must be > required
            return actual_major <= req_major
        elif requirement.startswith('<='):
            # Less than or equal - actual must be <= required
            return actual_major > req_major
        elif requirement.startswith('<'):
            # Less than - actual must be < required
            return actual_major >= req_major
        else:
            # Exact version or plain number - must match exactly
            return actual_major != req_major

    except (ValueError, IndexError):
        # Can't parse versions - assume no conflict
        return False
