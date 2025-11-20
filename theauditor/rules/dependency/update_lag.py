"""Detect severely outdated dependencies using existing version check data.

This rule detects dependencies that are 2+ major versions behind latest by reading
the deps_latest.json file created by 'aud deps --check-latest'.

ARCHITECTURE NOTE: This is a HYBRID APPROACH (database + file I/O) by design:
- Database-first: Validates packages against package_configs table
- File I/O: Reads pre-computed version comparison data from .pf/raw/deps_latest.json
- Rationale: Version checking requires network calls (npm/PyPI API), which are slow
  and should only run on-demand via 'aud deps --check-latest', not every pattern scan

Workflow Integration:
1. User runs: aud deps --check-latest (creates .pf/raw/deps_latest.json)
2. User runs: aud detect-patterns (this rule reads the JSON file)
3. Rule reports packages that are severely outdated (2+ major versions behind)

Database Tables Used:
- package_configs: Current dependency versions (for validation)
- Reads: .pf/raw/deps_latest.json (if it exists)
"""
from __future__ import annotations


import json
import sqlite3
from pathlib import Path
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query


METADATA = RuleMetadata(
    name="update_lag",
    category="dependency",
    target_extensions=['.json', '.txt', '.toml'],
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect severely outdated dependencies from deps_latest.json.

    Reads version comparison data from .pf/raw/deps_latest.json (created by
    'aud deps --check-latest') and reports packages that are 2+ major versions behind.

    Args:
        context: Rule execution context

    Returns:
        List of findings for severely outdated dependencies
    """
    findings = []

    # Check if deps_latest.json exists
    deps_latest_path = Path(".pf/raw/deps_latest.json")
    if not deps_latest_path.exists():
        # Not an error - just means user hasn't run --check-latest yet
        return findings

    try:
        # Load version comparison data
        with open(deps_latest_path, encoding='utf-8') as f:
            latest_info = json.load(f)

        # Query package_configs to validate packages exist
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        query = build_query('package_configs', ['file_path', 'package_name', 'version'])
        cursor.execute(query)

        package_files = {}
        for file_path, pkg_name, version in cursor.fetchall():
            # Map package name to file path
            if 'package.json' in file_path:
                key = f"npm:{pkg_name}"
            elif 'requirements.txt' in file_path or 'pyproject.toml' in file_path:
                key = f"py:{pkg_name}"
            else:
                key = f"unknown:{pkg_name}"

            package_files[key] = file_path

        conn.close()

        # Check each package for severe update lag
        for key, info in latest_info.items():
            # Skip if version check failed
            if info.get('error'):
                continue

            # Skip if not outdated
            if not info.get('is_outdated', False):
                continue

            # Check version delta
            delta = info.get('delta', '')
            locked = info.get('locked', '')
            latest = info.get('latest', '')

            # Flag major version lag (2+ major versions behind)
            if delta == 'major':
                # Parse manager and package name from key (format: "npm:package-name")
                parts = key.split(':', 1)
                if len(parts) != 2:
                    continue

                manager, pkg_name = parts
                file_path = package_files.get(key, 'package.json' if manager == 'npm' else 'requirements.txt')

                # Try to determine how many major versions behind
                try:
                    locked_major = int(locked.split('.')[0].lstrip('v^~<>='))
                    latest_major = int(latest.split('.')[0].lstrip('v^~<>='))
                    versions_behind = latest_major - locked_major

                    if versions_behind >= 2:
                        severity = Severity.MEDIUM if versions_behind == 2 else Severity.HIGH

                        findings.append(StandardFinding(
                            file_path=file_path,
                            line=1,  # Package files don't have specific lines
                            rule_name='update_lag',
                            message=f"Dependency '{pkg_name}' is {versions_behind} major versions behind (using {locked}, latest is {latest})",
                            severity=severity,
                            category='dependency',
                            snippet=f"{pkg_name}: {locked} (latest: {latest})",
                            cwe_id='CWE-1104'  # Use of Unmaintained Third Party Components
                        ))
                except (ValueError, IndexError):
                    # Can't parse version numbers - skip
                    continue

    except (json.JSONDecodeError, OSError, sqlite3.Error):
        # Silently fail - this is an optional enhancement
        pass

    return findings
