"""React Render Analyzer - Database-Driven Implementation.

Detects React rendering performance issues and anti-patterns using data from
react_components, function_call_args, and symbols tables.

Focuses on render optimization and performance bottlenecks.
"""

import sqlite3
from typing import List, Dict, Any
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
            # Run all rendering checks (schema contract guarantees tables exist)
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

    def _check_expensive_operations(self):
        """Check for expensive operations in render methods."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args with components, filter in Python
        self.cursor.execute("""
            SELECT DISTINCT f.file, f.line, f.callee_function,
                   f.caller_function, c.name
            FROM function_call_args f
            JOIN react_components c ON f.file = c.file
            WHERE f.line BETWEEN c.start_line AND c.end_line
            LIMIT 1000
        """)

        for row in self.cursor.fetchall():
            file, line, callee, caller, component = row

            # Skip if in useMemo or useCallback
            if caller and ('useMemo' in caller or 'useCallback' in caller):
                continue

            # Check if callee contains expensive operation
            operation = None
            for op in self.patterns.EXPENSIVE_OPERATIONS:
                if f'.{op}' in callee:
                    operation = op
                    break

            if operation:
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
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row

            # Check if args contains state or props
            args_str = str(args) if args else ''
            if not ('state' in args_str or 'props' in args_str):
                continue

            # Check if callee ends with mutating method
            method_found = None
            for method in self.patterns.MUTATING_METHODS:
                if callee and f'.{method}' in callee:
                    method_found = method
                    break

            if method_found:
                self.findings.append(StandardFinding(
                    rule_name='react-direct-mutation',
                    message=f'Direct state/props mutation using {method_found}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react-state',
                    snippet=f'{callee}',
                    confidence=Confidence.HIGH if 'state' in args_str else Confidence.MEDIUM,
                    cwe_id='CWE-682'
                ))

    def _check_inline_functions(self):
        """Check for inline arrow functions in render."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, argument_expr, callee_function
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, args, callee = row

            # Skip use% hooks
            if callee and callee.startswith('use'):
                continue

            # Check for inline function patterns
            args_str = str(args) if args else ''
            has_inline = ('() =>' in args_str or
                         'function()' in args_str or
                         'function (' in args_str or
                         '.bind(' in args_str)

            if not has_inline:
                continue

            # Check if it's likely in a render context (has event handlers)
            if any(handler in args_str for handler in self.patterns.EVENT_HANDLERS):
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
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row

            # Check if callee ends with .map
            if not (callee and '.map' in callee):
                continue

            # Check if args missing 'key' prop
            args_str = str(args) if args else ''
            if args_str and 'key' in args_str:
                continue

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
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, callee = row

            # Skip if it's in a hook
            if callee and 'use' in callee.lower():
                continue

            # Check if callee matches any object creator
            if callee in self.patterns.OBJECT_CREATORS:
                self.findings.append(StandardFinding(
                    rule_name='react-object-creation',
                    message=f'Creating new {callee} in render path',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-performance',
                    snippet=f'{callee}',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1050'
                ))

    def _check_index_as_key(self):
        """Check for using array index as key."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row

            # Check if callee ends with .map
            if not (callee and '.map' in callee):
                continue

            # Check if args contains index as key
            args_str = str(args) if args else ''
            has_index_key = ('key={index}' in args_str or
                           'key={i}' in args_str or
                           'key={idx}' in args_str)

            if has_index_key:
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
        # Fetch all useState hooks
        self.cursor.execute("""
            SELECT file, line, component_name
            FROM react_hooks
            WHERE hook_name = 'useState'
            LIMIT 200
        """)
        use_states = self.cursor.fetchall()

        # Fetch all useEffect hooks with dependency arrays
        self.cursor.execute("""
            SELECT file, line, component_name, dependency_array
            FROM react_hooks
            WHERE hook_name = 'useEffect'
              AND dependency_array IS NOT NULL
            LIMIT 200
        """)
        use_effects = self.cursor.fetchall()

        # Build map of component -> useEffects
        effects_by_component = {}
        for file, line, component, deps in use_effects:
            key = (file, component)
            if key not in effects_by_component:
                effects_by_component[key] = []
            effects_by_component[key].append((line, deps))

        # Check each useState for nearby useEffect with props
        for file, line, component in use_states:
            key = (file, component)
            if key not in effects_by_component:
                continue

            for effect_line, deps in effects_by_component[key]:
                # Check if useEffect is within 10 lines after useState
                if effect_line > line and effect_line < line + 10:
                    # Check if dependency array contains 'props'
                    deps_str = str(deps) if deps else ''
                    if 'props' in deps_str:
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
                        break

    def _check_anonymous_functions_in_props(self):
        """Check for anonymous functions passed as props."""
        # Fetch all function_call_args with components, filter in Python
        self.cursor.execute("""
            SELECT f.file, f.line, f.argument_expr, f.callee_function, c.name
            FROM function_call_args f
            JOIN react_components c ON f.file = c.file
            WHERE c.has_jsx = 1
              AND f.line BETWEEN c.start_line AND c.end_line
              AND f.argument_expr IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, args, callee, component = row

            # Skip use% hooks
            if callee and callee.startswith('use'):
                continue

            # Check for anonymous functions
            args_str = str(args) if args else ''
            has_anonymous = '=>' in args_str or 'function' in args_str

            if has_anonymous and len(args_str) < 50:  # Short inline functions
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
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, args = row

            # Check for inline style objects
            args_str = str(args) if args else ''
            has_inline_style = 'style={{' in args_str or 'style={ {' in args_str

            if has_inline_style:
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
