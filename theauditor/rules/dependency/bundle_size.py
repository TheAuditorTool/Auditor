"""Detect inefficient imports that bloat frontend bundles (database-first).

This rule detects when frontend code imports entire packages instead of specific modules,
which can significantly increase bundle size. It uses the import_styles table.

Detection Strategy:
1. Query import_styles for frontend imports (React/Vue projects)
2. Check for full-package imports of known large libraries
3. Flag imports that should use selective/tree-shaken imports

Common Issues:
- import lodash from 'lodash' → Should use: import map from 'lodash/map'
- import * as moment from 'moment' → Should use: import dayjs or date-fns
- import { Button, Modal, Form, ... } from 'antd' → Should use sub-imports

Database Tables Used:
- import_styles: Import patterns and packages
- package_configs: Installed dependencies
"""

import sqlite3
from typing import List, Dict, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata


METADATA = RuleMetadata(
    name="bundle_size",
    category="dependency",
    target_extensions=['.js', '.ts', '.jsx', '.tsx'],
    exclude_patterns=['node_modules/', '.venv/', 'backend/', 'server/', 'test/', '__tests__/'],
    requires_jsx_pass=False,
)


# Known large packages that should use selective imports
# Frozenset for O(1) membership test
LARGE_PACKAGES = frozenset([
    'lodash', 'moment', 'antd', 'element-plus', 'element-ui',
    '@mui/material', 'rxjs', 'recharts'
])

# Package metadata: (recommended_alternative, typical_size_mb, severity)
PACKAGE_METADATA = {
    'lodash': ('lodash/[function]', 1.4, 'MEDIUM'),
    'moment': ('date-fns or dayjs', 0.7, 'MEDIUM'),
    'antd': ('antd/es/[component]', 2.0, 'MEDIUM'),
    'element-plus': ('element-plus/es/[component]', 2.5, 'MEDIUM'),
    'element-ui': ('element-ui/lib/[component]', 2.0, 'MEDIUM'),
    '@mui/material': ('@mui/material/[Component]', 1.5, 'LOW'),  # Tree-shakes well in modern bundlers
    'rxjs': ('rxjs/operators', 0.5, 'LOW'),
    'recharts': ('recharts/[Chart]', 0.8, 'LOW'),
}

# Import styles that indicate full-package imports
FULL_IMPORT_PATTERNS = frozenset([
    'import',        # import lodash from 'lodash'
    'require',       # const lodash = require('lodash')
    'import-default', # import moment from 'moment'
])


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect full-package imports of large libraries in frontend code.

    Checks import_styles table for full imports of known large packages that
    should use selective/tree-shaken imports to reduce bundle size.

    Args:
        context: Rule execution context

    Returns:
        List of findings for inefficient imports
    """
    findings = []

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        # Check if required tables exist (graceful degradation)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = {row[0] for row in cursor.fetchall()}

        if 'import_styles' not in available_tables or 'package_configs' not in available_tables:
            conn.close()
            return findings

        # Check if this is a frontend project by looking for framework dependencies
        cursor.execute("""
            SELECT package_name FROM package_configs
            WHERE package_name IN ('react', 'vue', '@vue/cli', 'next', 'nuxt', '@angular/core', 'svelte')
        """)

        if not cursor.fetchall():
            # Not a frontend project - skip this rule
            conn.close()
            return findings

        # Query all imports from frontend files
        cursor.execute("""
            SELECT DISTINCT file, line, package, import_style
            FROM import_styles
            WHERE package IN ({})
        """.format(','.join(['?' for _ in LARGE_PACKAGES])),
        list(LARGE_PACKAGES))

        seen_issues: Set[str] = set()  # Deduplicate findings

        for file_path, line, package, import_style in cursor.fetchall():
            # Check if this is a full-package import
            if import_style not in FULL_IMPORT_PATTERNS:
                continue

            # Get package metadata
            alternative, size_mb, severity = PACKAGE_METADATA.get(package, ('', 0, 'LOW'))

            # Create deduplication key
            issue_key = f"{file_path}:{package}"
            if issue_key in seen_issues:
                continue
            seen_issues.add(issue_key)

            # Create finding with CORRECT StandardFinding parameters
            findings.append(StandardFinding(
                file_path=file_path,
                line=line,
                rule_name='bundle-size-full-import',
                message=f"Full import of '{package}' (~{size_mb}MB) may bloat bundle. Consider using: {alternative}",
                severity=severity,
                category='dependency',
                snippet=f"import ... from '{package}'",
            ))

        conn.close()

    except sqlite3.Error:
        # Database error - silently fail
        pass

    return findings
