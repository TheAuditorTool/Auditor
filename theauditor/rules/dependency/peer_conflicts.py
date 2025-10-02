"""Detect peer dependency version conflicts (STUB - optional advanced rule).

This rule would detect when a project uses dependencies with conflicting
peer dependency requirements (e.g., React 17 library + React 18 project).

Future Implementation:
1. Query package_configs for peer_dependencies
2. Cross-reference with actual installed versions
3. Detect version range conflicts
4. Requires lock file parsing for full dependency tree

Requirements for full implementation:
- Lock file parsing (package-lock.json, yarn.lock, etc.)
- Semver range comparison logic
- Transitive dependency resolution
- Framework version detection

Database Tables Used (when implemented):
- package_configs: Peer dependency declarations
- lock_analysis: Parsed lock file data (future table)
"""

from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata


METADATA = RuleMetadata(
    name="peer_conflicts",
    category="dependency",
    target_extensions=['.json', '.lock'],
    exclude_patterns=['node_modules/', '.venv/', 'test/'],
    requires_jsx_pass=False,
)


def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """STUB: Detect peer dependency version conflicts.

    This is a placeholder for future implementation. To enable this rule:
    1. Implement lock file parser
    2. Add peer dependency resolution logic
    3. Implement semver range comparison
    4. Add conflict detection algorithm

    Args:
        context: Rule execution context

    Returns:
        Empty list (stub implementation)
    """
    # Stub - return empty list
    # Full implementation would parse lock files and detect peer conflicts
    return []
