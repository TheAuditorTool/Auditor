"""React Component Analyzer - Database-Driven Implementation.

Detects React component anti-patterns and performance issues using data from
react_components, react_hooks, and function_call_args tables.

Focuses on component structure, organization, and best practices.
"""

import sqlite3
import json
from typing import List, Set, Dict, Any, Optional
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
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of React component issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check available tables
            self._check_table_availability()

            # Must have react_components table for analysis
            if 'react_components' not in self.existing_tables:
                return []

            # Run all component checks
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

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'react_components', 'react_hooks', 'function_call_args',
                'variable_usage', 'symbols'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

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
        if 'react_hooks' not in self.existing_tables:
            return

        self.cursor.execute("""
            SELECT c.file, c.name, c.type, c.start_line,
                   c.hooks_used, c.props_type
            FROM react_components c
            WHERE c.type != 'memo'
              AND c.has_jsx = 1
              AND (
                  c.hooks_used LIKE '%useCallback%'
                  OR c.hooks_used LIKE '%useMemo%'
                  OR c.props_type LIKE '%data%'
                  OR c.props_type LIKE '%items%'
                  OR c.props_type LIKE '%list%'
              )
        """)

        for row in self.cursor.fetchall():
            file, name, comp_type, line, hooks, props = row

            # Check if name suggests it should be memoized
            should_memo = False
            reason = ''

            if hooks and ('useCallback' in hooks or 'useMemo' in hooks):
                should_memo = True
                reason = 'uses optimization hooks'
            elif any(pattern in name.lower() for pattern in self.patterns.MEMO_CANDIDATES):
                should_memo = True
                reason = 'renders list/table items'
            elif props and any(prop in props for prop in self.patterns.PERFORMANCE_PROPS):
                should_memo = True
                reason = 'receives data props'

            if should_memo:
                self.findings.append(StandardFinding(
                    rule_name='react-missing-memo',
                    message=f'Component {name} {reason} but is not memoized',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-performance',
                    snippet=f'{comp_type} {name}',
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
        self.cursor.execute("""
            SELECT file, name, type, start_line
            FROM react_components
            WHERE (type IN ('arrow', 'anonymous')
                   OR name IN ('anonymous', '_', 'Component'))
              AND name NOT LIKE '%Component%'
              AND name NOT LIKE '%Container%'
        """)

        for row in self.cursor.fetchall():
            file, name, comp_type, line = row

            self.findings.append(StandardFinding(
                rule_name='react-missing-display-name',
                message=f'Component lacks meaningful display name: {name}',
                file_path=file,
                line=line,
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
        self.cursor.execute("""
            SELECT file, name, type, start_line, has_jsx, hooks_used
            FROM react_components
            WHERE has_jsx = 0
              AND (hooks_used IS NULL OR hooks_used = '[]')
        """)

        for row in self.cursor.fetchall():
            file, name, comp_type, line, has_jsx, hooks = row

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
        if 'react_hooks' not in self.existing_tables:
            return

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
        self.cursor.execute("""
            SELECT file,
                   SUM(CASE WHEN name LIKE '%Container%' THEN 1 ELSE 0 END) as containers,
                   SUM(CASE WHEN name LIKE '%Component%' THEN 1 ELSE 0 END) as components,
                   SUM(CASE WHEN name LIKE '%Page%' THEN 1 ELSE 0 END) as pages,
                   COUNT(*) as total
            FROM react_components
            GROUP BY file
            HAVING total > 2
        """)

        for row in self.cursor.fetchall():
            file, containers, components, pages, total = row

            # Check for mixed hierarchy levels
            if pages > 0 and components > 0:
                self.findings.append(StandardFinding(
                    rule_name='react-mixed-hierarchy',
                    message='File mixes page-level and component-level React components',
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category='react-component',
                    snippet=f'Pages: {pages}, Components: {components}',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
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