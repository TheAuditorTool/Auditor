"""React Render Analyzer - Database-Driven Implementation.

Detects React rendering performance issues and anti-patterns using data from
react_components, function_call_args, and symbols tables.

Focuses on render optimization and performance bottlenecks.
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
    name="react_render_issues",
    category="react",

    # Target React files only
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],

    # Focus on frontend directories
    target_file_patterns=['frontend/', 'client/', 'src/'],

    # Skip non-source files
    exclude_patterns=['node_modules/', '__tests__/', '*.test.jsx', '*.test.tsx', 'migrations/'],

    # Uses standard tables for render performance analysis
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ReactRenderPatterns:
    """Immutable pattern definitions for React rendering issues."""

    # Expensive operations that shouldn't be in render
    EXPENSIVE_OPERATIONS = frozenset([
        'sort', 'filter', 'map', 'reduce', 'find', 'findIndex',
        'forEach', 'reverse', 'concat', 'slice', 'splice'
    ])

    # Array mutating methods
    MUTATING_METHODS = frozenset([
        'push', 'pop', 'shift', 'unshift', 'splice',
        'sort', 'reverse', 'fill', 'copyWithin'
    ])

    # Methods that create new objects/arrays
    OBJECT_CREATORS = frozenset([
        'Object.create', 'Object.assign', 'Object.freeze',
        'Array.from', 'Array.of', 'new Array', 'new Object',
        'new Map', 'new Set', 'new Date', 'Date.now'
    ])

    # Inline function patterns
    INLINE_FUNCTION_PATTERNS = frozenset([
        '() =>', 'function()', 'function ()', '=>',
        'bind(', '.bind('
    ])

    # JSX event handlers
    EVENT_HANDLERS = frozenset([
        'onClick', 'onChange', 'onSubmit', 'onFocus', 'onBlur',
        'onMouseEnter', 'onMouseLeave', 'onKeyDown', 'onKeyUp',
        'onScroll', 'onLoad', 'onError', 'onDragStart', 'onDrop'
    ])

    # Performance-sensitive props
    PERF_PROPS = frozenset([
        'key', 'ref', 'children', 'style', 'className'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class ReactRenderAnalyzer:
    """Analyzer for React rendering performance and optimization."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ReactRenderPatterns()
        self.findings = []
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of React rendering issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check available tables
            self._check_table_availability()

            # Need at least function_call_args for analysis
            if 'function_call_args' not in self.existing_tables:
                return []

            # Run all rendering checks
            self._check_expensive_operations()
            self._check_array_mutations()
            self._check_inline_functions()
            self._check_missing_keys()
            self._check_object_creation()
            self._check_index_as_key()
            self._check_derived_state()
            self._check_anonymous_functions_in_props()
            self._check_excessive_renders()
            self._check_style_objects()

        finally:
            conn.close()

        return self.findings

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'react_components', 'function_call_args', 'symbols',
                'assignments', 'react_hooks'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

    def _check_expensive_operations(self):
        """Check for expensive operations in render methods."""
        if 'react_components' not in self.existing_tables:
            return

        for operation in self.patterns.EXPENSIVE_OPERATIONS:
            self.cursor.execute("""
                SELECT DISTINCT f.file, f.line, f.callee_function,
                       f.caller_function, c.name
                FROM function_call_args f
                JOIN react_components c ON f.file = c.file
                WHERE f.callee_function LIKE '%.' || ?
                  AND f.line BETWEEN c.start_line AND c.end_line
                  AND f.caller_function NOT LIKE '%useMemo%'
                  AND f.caller_function NOT LIKE '%useCallback%'
                LIMIT 100
            """, (operation,))

            for row in self.cursor.fetchall():
                file, line, callee, caller, component = row

                self.findings.append(StandardFinding(
                    rule_name='react-expensive-operation',
                    message=f'Expensive {operation} operation in render path',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='react-performance',
                    snippet=f'{callee} in {component}',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1050'
                ))

    def _check_array_mutations(self):
        """Check for direct array/object mutations."""
        for method in self.patterns.MUTATING_METHODS:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%.' || ?
                  AND (argument_expr LIKE '%state%'
                       OR argument_expr LIKE '%props%')
                LIMIT 50
            """, (method,))

            for row in self.cursor.fetchall():
                file, line, callee, args = row

                self.findings.append(StandardFinding(
                    rule_name='react-direct-mutation',
                    message=f'Direct state/props mutation using {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react-state',
                    snippet=f'{callee}',
                    confidence=Confidence.HIGH if 'state' in str(args) else Confidence.MEDIUM,
                    cwe_id='CWE-682'
                ))

    def _check_inline_functions(self):
        """Check for inline arrow functions in render."""
        self.cursor.execute("""
            SELECT file, line, argument_expr, callee_function
            FROM function_call_args
            WHERE (argument_expr LIKE '%() =>%'
                   OR argument_expr LIKE '%function()%'
                   OR argument_expr LIKE '%function (%'
                   OR argument_expr LIKE '%.bind(%')
              AND callee_function NOT LIKE 'use%'
            LIMIT 100
        """)

        for row in self.cursor.fetchall():
            file, line, args, callee = row

            # Check if it's likely in a render context
            if any(handler in str(args) for handler in self.patterns.EVENT_HANDLERS):
                self.findings.append(StandardFinding(
                    rule_name='react-inline-function',
                    message='Inline function in render will cause re-renders',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-performance',
                    snippet='Inline arrow function or bind',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1050'
                ))

    def _check_missing_keys(self):
        """Check for missing key props in lists."""
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE '%.map'
              AND (argument_expr NOT LIKE '%key%'
                   OR argument_expr IS NULL)
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row

            self.findings.append(StandardFinding(
                rule_name='react-missing-key',
                message='Array.map without key prop in JSX',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='react-performance',
                snippet=f'{callee}',
                confidence=Confidence.LOW,  # Hard to be certain without JSX context
                cwe_id='CWE-1050'
            ))

    def _check_object_creation(self):
        """Check for object/array creation in render."""
        for creator in self.patterns.OBJECT_CREATORS:
            self.cursor.execute("""
                SELECT file, line, callee_function
                FROM function_call_args
                WHERE callee_function = ?
                LIMIT 50
            """, (creator,))

            for row in self.cursor.fetchall():
                file, line, callee = row

                # Skip if it's in a hook
                if 'use' not in callee.lower():
                    self.findings.append(StandardFinding(
                        rule_name='react-object-creation',
                        message=f'Creating new {creator} in render path',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category='react-performance',
                        snippet=f'{creator}',
                        confidence=Confidence.LOW,
                        cwe_id='CWE-1050'
                    ))

    def _check_index_as_key(self):
        """Check for using array index as key."""
        self.cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE '%.map'
              AND (argument_expr LIKE '%key={index}%'
                   OR argument_expr LIKE '%key={i}%'
                   OR argument_expr LIKE '%key={idx}%')
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, args = row

            self.findings.append(StandardFinding(
                rule_name='react-index-key',
                message='Using array index as key prop can cause issues',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='react-performance',
                snippet='key={index}',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    def _check_derived_state(self):
        """Check for unnecessary derived state."""
        if 'react_hooks' not in self.existing_tables:
            return

        self.cursor.execute("""
            SELECT h1.file, h1.line, h1.component_name
            FROM react_hooks h1
            WHERE h1.hook_name = 'useState'
              AND EXISTS (
                  SELECT 1 FROM react_hooks h2
                  WHERE h2.file = h1.file
                    AND h2.component_name = h1.component_name
                    AND h2.hook_name = 'useEffect'
                    AND h2.dependency_array LIKE '%props%'
                    AND h2.line > h1.line
                    AND h2.line < h1.line + 10
              )
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, component = row

            self.findings.append(StandardFinding(
                rule_name='react-derived-state',
                message='Possible unnecessary derived state from props',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='react-state',
                snippet=f'useState followed by useEffect with props dependency',
                confidence=Confidence.LOW,
                cwe_id='CWE-1066'
            ))

    def _check_anonymous_functions_in_props(self):
        """Check for anonymous functions passed as props."""
        if 'react_components' not in self.existing_tables:
            return

        self.cursor.execute("""
            SELECT f.file, f.line, f.argument_expr, c.name
            FROM function_call_args f
            JOIN react_components c ON f.file = c.file
            WHERE c.has_jsx = 1
              AND f.line BETWEEN c.start_line AND c.end_line
              AND (f.argument_expr LIKE '%=>%'
                   OR f.argument_expr LIKE '%function%')
              AND f.callee_function NOT LIKE 'use%'
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, args, component = row

            if len(str(args)) < 50:  # Short inline functions
                self.findings.append(StandardFinding(
                    rule_name='react-anonymous-prop',
                    message=f'Anonymous function in props causes re-renders',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-performance',
                    snippet=f'Anonymous function in {component}',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1050'
                ))

    def _check_excessive_renders(self):
        """Check for components that might render too often."""
        if 'react_hooks' not in self.existing_tables:
            return

        self.cursor.execute("""
            SELECT file, component_name,
                   COUNT(CASE WHEN hook_name = 'useState' THEN 1 END) as state_count,
                   COUNT(CASE WHEN hook_name = 'useEffect' THEN 1 END) as effect_count
            FROM react_hooks
            GROUP BY file, component_name
            HAVING state_count > 5 AND effect_count > 3
        """)

        for row in self.cursor.fetchall():
            file, component, states, effects = row

            self.findings.append(StandardFinding(
                rule_name='react-excessive-renders',
                message=f'Component with {states} states and {effects} effects may render excessively',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='react-performance',
                snippet=f'{component}: {states} useState, {effects} useEffect',
                confidence=Confidence.LOW,
                cwe_id='CWE-1050'
            ))

    def _check_style_objects(self):
        """Check for inline style objects."""
        self.cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE argument_expr LIKE '%style={{%'
               OR argument_expr LIKE '%style={ {%'
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, args = row

            self.findings.append(StandardFinding(
                rule_name='react-inline-style',
                message='Inline style object causes unnecessary re-renders',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='react-performance',
                snippet='style={{ ... }}',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React rendering performance issues and anti-patterns.

    Uses data from function_call_args and react tables to identify
    rendering bottlenecks and optimization opportunities.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of React rendering issues found
    """
    analyzer = ReactRenderAnalyzer(context)
    return analyzer.analyze()