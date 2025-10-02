"""Detect severely outdated dependencies (STUB - requires registry API).

This rule would check if dependencies are 2+ major versions behind the latest.
Currently a stub - full implementation requires API integration with npm/PyPI.

Future Implementation:
1. Query package_configs for current versions
2. Call npm registry API / PyPI JSON API for latest versions
3. Compare major version numbers
4. Flag packages that are 2+ major versions behind

Requirements for full implementation:
- Network access to npm registry (https://registry.npmjs.org/)
- Network access to PyPI JSON API (https://pypi.org/pypi/{package}/json)
- Rate limiting to avoid API throttling
- Caching to reduce API calls

Database Tables Used (when implemented):
- package_configs: Current dependency versions
"""

from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata


METADATA = RuleMetadata(
    name="update_lag",
    category="dependency",
    target_extensions=['.json', '.txt', '.toml'],
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """STUB: Detect severely outdated dependencies.

    This is a placeholder for future implementation. To enable this rule:
    1. Implement registry API client (npm/PyPI)
    2. Add version comparison logic
    3. Add caching to reduce API calls
    4. Handle rate limiting

    Args:
        context: Rule execution context

    Returns:
        Empty list (stub implementation)
    """
    # Stub - return empty list
    # Full implementation would query registry APIs and compare versions
    return []
