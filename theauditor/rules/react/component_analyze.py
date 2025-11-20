"""React Component Analyzer - Database-Driven Implementation.

Detects React component anti-patterns and performance issues using data from
react_components, react_hooks, and function_call_args tables.

Focuses on component structure, organization, and best practices.
Schema Contract Compliance: v1.1+ (Fail-Fast, direct schema-bound queries)
"""


import sqlite3
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Orchestrator Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="react_component_issues",
    category="react",

    # Target React files only
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],

    # Focus on frontend directories
    target_file_patterns=['frontend/', 'client/', 'src/components/', 'app/'],

    # Skip non-source files
    exclude_patterns=['node_modules/', '__tests__/', '*.test.jsx', '*.test.tsx', 'migrations/'],

    # Uses standard tables, not *_jsx tables
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ReactComponentPatterns:
    """Immutable pattern definitions for React component violations."""

    # Component size thresholds
    MAX_COMPONENT_LINES = 300
    MAX_COMPONENTS_PER_FILE = 3
    MAX_PROPS_COUNT = 10

    # Component types that should be memoized
    MEMO_CANDIDATES = frozenset([
        'list', 'table', 'grid', 'card', 'item', 'row', 'cell'
    ])

    # Props that indicate performance sensitivity
    PERFORMANCE_PROPS = frozenset([
        'data', 'items', 'list', 'rows', 'options', 'children'
    ])

    # Component naming patterns
    COMPONENT_SUFFIXES = frozenset([
        'Component', 'Container', 'Page', 'View', 'Modal',
        'Dialog', 'Form', 'List', 'Table', 'Card', 'Button'
    ])

    # Anonymous component indicators
    ANONYMOUS_PATTERNS = frozenset([
        'anonymous', 'arrow', 'function', '_', 'temp'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class ReactComponentAnalyzer:
    """Analyzer for React component best practices and anti-patterns."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ReactComponentPatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of React component issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()
        self._bootstrap_component_metadata()

        try:
            # Run all component checks (schema contract guarantees tables exist)
            self._check_large_components()
            self._check_multiple_components_per_file()
            self._check_missing_memoization()
            self._check_inline_components()
            self._check_missing_display_names()
            self._check_component_naming()
            self._check_no_jsx_components()
            self._check_excessive_hooks()
            self._check_prop_complexity()
            self._check_component_hierarchy()

        finally:
            conn.close()

        return self.findings

    def _check_large_components(self):
        """Check for components that are too large."""
        self.cursor.execute("""
            SELECT file, name, type, start_line, end_line,
                   (end_line - start_line) as lines
            FROM react_components
            WHERE (end_line - start_line) > ?
            ORDER BY lines DESC
        """, (self.patterns.MAX_COMPONENT_LINES,))

        for row in self.cursor.fetchall():
            file, name, comp_type, start, end, lines = row

            self.findings.append(StandardFinding(
                rule_name='react-large-component',
                message=f'Component {name} is too large ({lines} lines)',
                file_path=file,
                line=start,
                severity=Severity.MEDIUM,
                category='react-component',
                snippet=f'{name}: {lines} lines (max: {self.patterns.MAX_COMPONENT_LINES})',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1066'
            ))

    def _check_multiple_components_per_file(self):
        """Check for files with too many components."""
        self.cursor.execute("""
            SELECT file, COUNT(*) as component_count,
                   GROUP_CONCAT(name) as components
            FROM react_components
            GROUP BY file
            HAVING component_count > ?
            ORDER BY component_count DESC
        """, (self.patterns.MAX_COMPONENTS_PER_FILE,))

        for row in self.cursor.fetchall():
            file, count, components = row
            comp_list = components.split(',')[:5]  # Show first 5

            self.findings.append(StandardFinding(
                rule_name='react-multiple-components',
                message=f'File contains {count} components (max: {self.patterns.MAX_COMPONENTS_PER_FILE})',
                file_path=file,
                line=1,
                severity=Severity.LOW,
                category='react-component',
                snippet=f'Components: {", ".join(comp_list)}{"..." if count > 5 else ""}',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1066'
            ))

    def _check_missing_memoization(self):
        """Check for components that should be memoized but aren't."""
        performance_tokens = set(self.patterns.PERFORMANCE_PROPS)
        memo_tokens = set(self.patterns.MEMO_CANDIDATES)

        for component in self.components:
            if component['type'] == 'memo' or not component['has_jsx']:
                continue

            name = component['name'] or ''
            basename = self._component_basename(name)
            normalized_basename = basename.lower()
            key = self._component_key(component['file'], name)

            hooks = self.component_hooks.get(key, set())
            dependency_tokens = self.component_dependencies.get(key, set())
            prop_tokens = self._extract_prop_tokens(component['props_type'])

            reason: str | None = None
            if hooks.intersection({'useCallback', 'useMemo'}):
                reason = 'uses optimization hooks'
            elif any(normalized_basename.endswith(token) for token in memo_tokens):
                reason = 'renders list/table items'
            elif (dependency_tokens | prop_tokens).intersection(performance_tokens):
                reason = 'receives data props'

            if reason:
                self.findings.append(StandardFinding(
                    rule_name='react-missing-memo',
                    message=f'Component {name} {reason} but is not memoized',
                    file_path=component['file'],
                    line=component['start_line'] or 1,
                    severity=Severity.LOW,
                    category='react-performance',
                    snippet=f"{component['type']} {name}",
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1050'
                ))

    def _check_inline_components(self):
        """Check for components defined inside other components."""
        self.cursor.execute("""
            SELECT c1.file, c1.name as parent, c2.name as child,
                   c1.start_line, c2.start_line as child_line
            FROM react_components c1
            JOIN react_components c2 ON c1.file = c2.file
            WHERE c2.start_line > c1.start_line
              AND c2.end_line < c1.end_line
              AND c1.name != c2.name
        """)

        for row in self.cursor.fetchall():
            file, parent, child, parent_line, child_line = row

            self.findings.append(StandardFinding(
                rule_name='react-inline-component',
                message=f'Component {child} is defined inside {parent}',
                file_path=file,
                line=child_line,
                severity=Severity.HIGH,
                category='react-component',
                snippet=f'{child} inside {parent}',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    def _check_missing_display_names(self):
        """Check for anonymous components without display names."""
        for component in self.components:
            name = component['name'] or ''
            comp_type = component['type']
            if not name:
                continue

            basename = self._component_basename(name)
            normalized = basename.lower()

            is_anonymous_type = comp_type in ('arrow', 'anonymous')
            is_placeholder_name = normalized in {'anonymous', '_', 'component'}

            if not (is_anonymous_type or is_placeholder_name):
                continue

            if 'component' in normalized or 'container' in normalized:
                continue

            if not self._has_meaningful_display_name(basename):
                self.findings.append(StandardFinding(
                    rule_name='react-missing-display-name',
                    message=f'Component lacks meaningful display name: {name}',
                    file_path=component['file'],
                    line=component['start_line'] or 1,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'{comp_type} component: {name}',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1078'
                ))

    def _check_component_naming(self):
        """Check for poor component naming conventions."""
        self.cursor.execute("""
            SELECT file, name, type, start_line
            FROM react_components
            WHERE name IS NOT NULL
              AND LENGTH(name) > 0
        """)

        for row in self.cursor.fetchall():
            file, name, comp_type, line = row

            # Check for PascalCase
            if name and not name[0].isupper():
                self.findings.append(StandardFinding(
                    rule_name='react-component-naming',
                    message=f'Component {name} should use PascalCase',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'{name}',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-1078'
                ))

            # Check for too short names
            elif len(name) < 3:
                self.findings.append(StandardFinding(
                    rule_name='react-component-naming',
                    message=f'Component name {name} is too short',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'{name}',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1078'
                ))

    def _check_no_jsx_components(self):
        """Check for components that don't return JSX."""
        # JOIN with react_component_hooks to check if component uses hooks
        self.cursor.execute("""
            SELECT
                rc.file,
                rc.name,
                rc.type,
                rc.start_line,
                rc.has_jsx,
                COUNT(rch.hook_name) as hook_count
            FROM react_components rc
            LEFT JOIN react_component_hooks rch
                ON rc.file = rch.component_file
                AND rc.name = rch.component_name
            WHERE rc.has_jsx = 0
            GROUP BY rc.file, rc.name, rc.type, rc.start_line, rc.has_jsx
            HAVING hook_count = 0
        """)

        for row in self.cursor.fetchall():
            file, name, comp_type, line, has_jsx, hook_count = row

            self.findings.append(StandardFinding(
                rule_name='react-no-jsx',
                message=f'Component {name} does not appear to return JSX',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react-component',
                snippet=f'{name}: no JSX detected',
                confidence=Confidence.LOW,
                cwe_id='CWE-1066'
            ))

    def _check_excessive_hooks(self):
        """Check for components with too many hooks."""
        self.cursor.execute("""
            SELECT h.file, h.component_name,
                   COUNT(*) as hook_count,
                   GROUP_CONCAT(h.hook_name) as hooks
            FROM react_hooks h
            JOIN react_components c ON h.file = c.file
              AND h.component_name = c.name
            GROUP BY h.file, h.component_name
            HAVING hook_count > 10
            ORDER BY hook_count DESC
        """)

        for row in self.cursor.fetchall():
            file, component, count, hooks = row
            hook_list = hooks.split(',')[:5]  # Show first 5

            self.findings.append(StandardFinding(
                rule_name='react-excessive-hooks',
                message=f'Component {component} uses {count} hooks - consider refactoring',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='react-component',
                snippet=f'Hooks: {", ".join(hook_list)}...',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1066'
            ))

    def _check_prop_complexity(self):
        """Check for components with too many props."""
        self.cursor.execute("""
            SELECT file, name, start_line, props_type
            FROM react_components
            WHERE props_type IS NOT NULL
              AND LENGTH(props_type) > 200
        """)

        for row in self.cursor.fetchall():
            file, name, line, props = row

            # Count prop fields (simplified)
            prop_count = props.count(':') if props else 0

            if prop_count > self.patterns.MAX_PROPS_COUNT:
                self.findings.append(StandardFinding(
                    rule_name='react-prop-complexity',
                    message=f'Component {name} has ~{prop_count} props - too complex',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'{name}: ~{prop_count} props',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))

    def _check_component_hierarchy(self):
        """Check for potential component hierarchy issues."""
        for file_path, components in self.components_by_file.items():
            total = len(components)
            if total <= 2:
                continue

            containers = 0
            components_count = 0
            pages = 0

            for component in components:
                basename = self._component_basename(component['name']).lower()
                if basename.endswith('container'):
                    containers += 1
                if basename.endswith('component'):
                    components_count += 1
                if basename.endswith('page'):
                    pages += 1

            if pages > 0 and components_count > 0:
                first_line = min((comp['start_line'] or 1) for comp in components)
                self.findings.append(StandardFinding(
                    rule_name='react-mixed-hierarchy',
                    message='File mixes page-level and component-level React components',
                    file_path=file_path,
                    line=first_line,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'Pages: {pages}, Components: {components_count}, Containers: {containers}',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))


    # ------------------------------------------------------------------
    # Metadata bootstrap & helpers
    # ------------------------------------------------------------------

    def _bootstrap_component_metadata(self) -> None:
        """Load component-level metadata and relationship tables once."""
        self.components: list[dict[str, Any]] = []
        self.components_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)

        self.cursor.execute("""
            SELECT file, name, type, start_line, end_line, has_jsx, props_type
            FROM react_components
        """)

        for row in self.cursor.fetchall():
            component = {
                'file': row['file'],
                'name': row['name'],
                'type': row['type'],
                'start_line': row['start_line'],
                'end_line': row['end_line'],
                'has_jsx': bool(row['has_jsx']),
                'props_type': row['props_type'],
            }
            self.components.append(component)
            self.components_by_file[component['file']].append(component)

        self.component_hooks = self._load_component_hooks()
        self.component_dependencies = self._load_component_dependencies()

    def _load_component_hooks(self) -> dict[tuple, set[str]]:
        """Return mapping of components to hooks used."""
        hooks: dict[tuple, set[str]] = defaultdict(set)
        self.cursor.execute("""
            SELECT component_file, component_name, hook_name
            FROM react_component_hooks
        """)
        for row in self.cursor.fetchall():
            key = self._component_key(row['component_file'], row['component_name'])
            hooks[key].add(row['hook_name'])
        return hooks

    def _load_component_dependencies(self) -> dict[tuple, set[str]]:
        """Return mapping of components to dependency tokens."""
        dependencies: dict[tuple, set[str]] = defaultdict(set)
        self.cursor.execute("""
            SELECT hook_file, hook_component, dependency_name
            FROM react_hook_dependencies
        """)
        for row in self.cursor.fetchall():
            normalized = self._normalize_dependency_name(row['dependency_name'])
            if not normalized:
                continue
            key = self._component_key(row['hook_file'], row['hook_component'])
            dependencies[key].add(normalized)
        return dependencies

    @staticmethod
    def _component_key(file_path: str, name: str | None) -> tuple:
        return (file_path, name or '')

    @staticmethod
    def _component_basename(name: str | None) -> str:
        if not name:
            return ''
        return name.split('.')[-1]

    @staticmethod
    def _normalize_dependency_name(name: str | None) -> str | None:
        if not name:
            return None
        token = name.split('.')[-1].strip()
        return token.lower() if token else None

    @staticmethod
    def _extract_prop_tokens(props: str | None) -> set[str]:
        if not props:
            return set()
        tokens: set[str] = set()
        current: list[str] = []
        for char in props:
            if char.isalpha():
                current.append(char.lower())
            else:
                if current:
                    tokens.add(''.join(current))
                    current = []
        if current:
            tokens.add(''.join(current))
        return tokens

    def _has_meaningful_display_name(self, name: str) -> bool:
        lowered = name.lower()
        if lowered in self.patterns.ANONYMOUS_PATTERNS:
            return False
        if any(lowered.endswith(suffix.lower()) for suffix in self.patterns.COMPONENT_SUFFIXES):
            return True
        return len(name) >= 3 and any(char.isalpha() for char in name)


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect React component anti-patterns and best practices violations.

    Uses data from react_components and related tables for accurate detection
    of component structure, organization, and performance issues.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of React component issues found
    """
    analyzer = ReactComponentAnalyzer(context)
    return analyzer.analyze()
