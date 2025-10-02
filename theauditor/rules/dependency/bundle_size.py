"""Detect large dependencies that bloat frontend bundles (STUB - optional).

This rule would detect when frontend code imports large packages that
significantly increase bundle size (e.g., importing entire lodash instead
of specific functions).

Future Implementation:
1. Query import_styles for frontend imports
2. Check package sizes from npm registry
3. Detect full-package imports vs selective imports
4. Requires webpack/vite stats integration for accurate bundle analysis

Requirements for full implementation:
- Package size database (from npm registry)
- Bundle analyzer integration (webpack-bundle-analyzer stats)
- Import pattern analysis (full vs selective)
- Framework detection (React/Vue/etc.)

Database Tables Used (when implemented):
- import_styles: Import patterns
- package_configs: Dependencies
- bundle_stats: Webpack/vite bundle analysis (future table)
"""

from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata


METADATA = RuleMetadata(
    name="bundle_size",
    category="dependency",
    target_extensions=['.js', '.ts', '.jsx', '.tsx'],
    exclude_patterns=['node_modules/', '.venv/', 'backend/', 'server/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """STUB: Detect large dependencies that bloat bundles.

    This is a placeholder for future implementation. To enable this rule:
    1. Implement package size lookup (npm registry)
    2. Add bundle analyzer integration
    3. Detect full vs selective imports
    4. Calculate actual bundle impact

    Args:
        context: Rule execution context

    Returns:
        Empty list (stub implementation)
    """
    # Stub - return empty list
    # Full implementation would analyze bundle sizes and import patterns
    return []
