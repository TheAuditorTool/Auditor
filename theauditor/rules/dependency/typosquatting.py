"""Detect potential typosquatting in package names.

Typosquatting is a supply-chain attack where malicious packages use names
similar to popular packages (e.g., 'requets' instead of 'requests').
This rule detects common typos and suspicious package names.

Detection Strategy:
1. Query package_configs and import_styles for all package names
2. Check against TYPOSQUATTING_MAP from config.py
3. Flag potential typos with suggested corrections

Database Tables Used:
- package_configs: Declared dependencies
- import_styles: Imported packages
"""

import sqlite3
import json
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query
from .config import TYPOSQUATTING_MAP


METADATA = RuleMetadata(
    name="typosquatting",
    category="dependency",
    target_extensions=['.py', '.js', '.ts', '.json', '.txt'],
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    execution_scope='database',
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect potential typosquatting in package names.

    Args:
        context: Rule execution context with db_path

    Returns:
        List of findings for potential typosquatting
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check declared dependencies
        findings.extend(_check_declared_packages(cursor))

        # Check imported packages
        findings.extend(_check_imported_packages(cursor))

    finally:
        conn.close()

    return findings


def _check_declared_packages(cursor) -> List[StandardFinding]:
    """Check declared dependencies for typosquatting.

    Args:
        cursor: Database cursor

    Returns:
        List of findings for declared dependencies
    """
    findings = []
    seen = set()

    query = build_query('package_configs', ['file_path', 'dependencies', 'dev_dependencies'])
    cursor.execute(query)

    for file_path, deps, dev_deps in cursor.fetchall():
        for deps_json in [deps, dev_deps]:
            if not deps_json:
                continue

            try:
                deps_dict = json.loads(deps_json)
                if not isinstance(deps_dict, dict):
                    continue

                for package in deps_dict.keys():
                    package_lower = package.lower()

                    # Skip if already reported
                    if package_lower in seen:
                        continue

                    # Check against typosquatting map
                    if package_lower in TYPOSQUATTING_MAP:
                        correct_name = TYPOSQUATTING_MAP[package_lower]
                        seen.add(package_lower)

                        findings.append(StandardFinding(
                            rule_name='typosquatting',
                            message=f"Potential typosquatting: '{package}' (did you mean '{correct_name}'?)",
                            file_path=file_path,
                            line=1,
                            severity=Severity.CRITICAL,  # Supply chain attacks are critical
                            category='dependency',
                            snippet=f"Declared: {package}, Expected: {correct_name}",
                            cwe_id='CWE-1357'  # Reliance on Insufficiently Trustworthy Component
                        ))

            except json.JSONDecodeError:
                continue

    return findings


def _check_imported_packages(cursor) -> List[StandardFinding]:
    """Check imported packages for typosquatting.

    Args:
        cursor: Database cursor

    Returns:
        List of findings for imported packages
    """
    findings = []
    seen = set()

    query = build_query('import_styles', ['file', 'line', 'package'],
                       order_by='package, file, line')
    cursor.execute(query)

    for file, line, package in cursor.fetchall():
        if not package:
            continue

        # Normalize package name (base package only)
        base_package = package.split('/')[0].split('.')[0].lower()

        # Skip if already reported
        if base_package in seen:
            continue

        # Check against typosquatting map
        if base_package in TYPOSQUATTING_MAP:
            correct_name = TYPOSQUATTING_MAP[base_package]
            seen.add(base_package)

            findings.append(StandardFinding(
                rule_name='typosquatting-import',
                message=f"Importing potentially typosquatted package: '{base_package}' (did you mean '{correct_name}'?)",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='dependency',
                snippet=f"import {package}",
                cwe_id='CWE-1357'
            ))

    return findings
