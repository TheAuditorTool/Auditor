"""React State Analyzer - Database-Driven Implementation.

Detects React state management issues and anti-patterns using data from
react_hooks, variable_usage, and assignments tables.

Focuses on state complexity, prop drilling, and state management best practices.
"""
from __future__ import annotations


import sqlite3
import json
from typing import List, Dict, Any
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Orchestrator Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="react_state_issues",
    category="react",

    # Target React files only
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],

    # Focus on frontend directories
    target_file_patterns=['frontend/', 'client/', 'src/'],

    # Skip non-source files
    exclude_patterns=['node_modules/', '__tests__/', '*.test.jsx', '*.test.tsx', 'migrations/'],

    # Uses standard tables for state management analysis
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ReactStatePatterns:
    """Immutable pattern definitions for React state management."""

    # State complexity thresholds
    MAX_USESTATE_PER_COMPONENT = 7
    MAX_STATE_UPDATES_PER_FUNCTION = 3
    REDUCER_THRESHOLD = 5  # When to suggest useReducer

    # State naming patterns
    STATE_PREFIXES = frozenset([
        'is', 'has', 'should', 'can', 'will', 'did'
    ])

    # Common state variables
    COMMON_STATE = frozenset([
        'loading', 'error', 'data', 'isLoading', 'isError',
        'isOpen', 'isVisible', 'isActive', 'isDisabled'
    ])

    # Context/global state indicators
    CONTEXT_PATTERNS = frozenset([
        'context', 'store', 'provider', 'global', 'app',
        'theme', 'auth', 'user', 'session', 'config'
    ])

    # Prop drilling indicators
    DRILL_PROPS = frozenset([
        'user', 'auth', 'theme', 'config', 'settings',
        'data', 'state', 'dispatch', 'actions'
    ])

    # State setter patterns
    STATE_SETTERS = frozenset([
        'set', 'update', 'change', 'toggle', 'reset', 'clear'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class ReactStateAnalyzer:
    """Analyzer for React state management patterns and issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ReactStatePatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of React state management issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Run all state management checks (schema contract guarantees tables exist)
            self._check_excessive_usestate()
            self._check_missing_usereducer()
            self._check_state_naming()
            self._check_multiple_state_updates()
            self._check_prop_drilling()
            self._check_global_state_candidates()
            self._check_unnecessary_state()
            self._check_state_initialization()
            self._check_complex_state_objects()
            self._check_state_batching()

        finally:
            conn.close()

        return self.findings

    def _check_excessive_usestate(self):
        """Check for components with too many useState hooks."""
        self.cursor.execute("""
            SELECT file, component_name,
                   COUNT(*) as state_count,
                   GROUP_CONCAT(hook_name) as hooks
            FROM react_hooks
            WHERE hook_name = 'useState'
            GROUP BY file, component_name
            HAVING state_count > ?
            ORDER BY state_count DESC
        """, (self.patterns.MAX_USESTATE_PER_COMPONENT,))

        for row in self.cursor.fetchall():
            file, component, count, hooks = row

            self.findings.append(StandardFinding(
                rule_name='react-excessive-state',
                message=f'Component {component} has {count} useState hooks',
                file_path=file,
                line=1,
                severity=Severity.MEDIUM,
                category='react-state',
                snippet=f'{count} useState calls',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1066'
            ))

    def _check_missing_usereducer(self):
        """Check for components that should use useReducer."""
        self.cursor.execute("""
            SELECT h.file, h.component_name,
                   COUNT(*) as state_count
            FROM react_hooks h
            WHERE h.hook_name = 'useState'
              AND NOT EXISTS (
                  SELECT 1 FROM react_hooks h2
                  WHERE h2.file = h.file
                    AND h2.component_name = h.component_name
                    AND h2.hook_name = 'useReducer'
              )
            GROUP BY h.file, h.component_name
            HAVING state_count >= ?
        """, (self.patterns.REDUCER_THRESHOLD,))

        for row in self.cursor.fetchall():
            file, component, count = row

            self.findings.append(StandardFinding(
                rule_name='react-missing-reducer',
                message=f'Component with {count} states should consider useReducer',
                file_path=file,
                line=1,
                severity=Severity.LOW,
                category='react-state',
                snippet=f'{component}: {count} useState hooks',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-1066'
            ))

    def _check_state_naming(self):
        """Check for poor state variable naming."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.source_expr IS NOT NULL
              AND a.target_var IS NOT NULL
            LIMIT 500
        """)

        for row in self.cursor.fetchall():
            file, line, var_name, source = row

            if not var_name:
                continue

            # Check if source contains useState
            source_str = str(source) if source else ''
            if 'useState' not in source_str:
                continue

            # Check for boolean state without proper prefix
            if 'true' in source_str.lower() or 'false' in source_str.lower():
                if not any(var_name.startswith(prefix) for prefix in self.patterns.STATE_PREFIXES):
                    self.findings.append(StandardFinding(
                        rule_name='react-state-naming',
                        message=f'Boolean state {var_name} should use is/has/should prefix',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category='react-state',
                        snippet=f'const [{var_name}, ...] = useState',
                        confidence=Confidence.LOW,
                        cwe_id='CWE-1078'
                    ))

    def _check_multiple_state_updates(self):
        """Check for multiple state updates in single function."""
        # Fetch all function_call_args, group in Python
        self.cursor.execute("""
            SELECT file, caller_function, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND caller_function IS NOT NULL
              AND caller_function != 'global'
            LIMIT 1000
        """)

        # Group by file and caller_function
        updates_by_function = {}
        for file, caller, callee in self.cursor.fetchall():
            # Check if callee starts with 'set'
            if not (callee and callee.startswith('set')):
                continue

            key = (file, caller)
            if key not in updates_by_function:
                updates_by_function[key] = []
            updates_by_function[key].append(callee)

        # Check for excessive updates
        for (file, function), setters in updates_by_function.items():
            count = len(setters)
            if count > self.patterns.MAX_STATE_UPDATES_PER_FUNCTION:
                if all('set' in s.lower() for s in setters):
                    self.findings.append(StandardFinding(
                        rule_name='react-multiple-updates',
                        message=f'Function {function} updates state {count} times',
                        file_path=file,
                        line=1,
                        severity=Severity.LOW,
                        category='react-state',
                        snippet=f'{count} setState calls',
                        confidence=Confidence.LOW,
                        cwe_id='CWE-1050'
                    ))

    def _check_prop_drilling(self):
        """Check for potential prop drilling patterns."""
        # Fetch all react_components, filter in Python
        self.cursor.execute("""
            SELECT file, name, props_type
            FROM react_components
            WHERE props_type IS NOT NULL
        """)

        # Group by file and prop
        prop_usage = {}
        for file, component, props_type in self.cursor.fetchall():
            props_str = str(props_type) if props_type else ''
            for prop in self.patterns.DRILL_PROPS:
                if prop in props_str:
                    key = (file, prop)
                    if key not in prop_usage:
                        prop_usage[key] = set()
                    prop_usage[key].add(component)

        # Check for drilling (prop used in >2 components in same file)
        for (file, prop), components in prop_usage.items():
            count = len(components)
            if count > 2:
                self.findings.append(StandardFinding(
                    rule_name='react-prop-drilling',
                    message=f'{count} components receive "{prop}" prop - possible prop drilling',
                    file_path=file,
                    line=1,
                    severity=Severity.LOW,
                    category='react-state',
                    snippet=f'{prop} passed through {count} components',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))

    def _check_global_state_candidates(self):
        """Check for state that should be global."""
        # Fetch all variable_usage, filter in Python
        self.cursor.execute("""
            SELECT variable_name, in_component
            FROM variable_usage
            WHERE variable_name IS NOT NULL
              AND in_component != ''
            LIMIT 1000
        """)

        # Group by variable_name and pattern
        var_usage = {}
        for var_name, component in self.cursor.fetchall():
            # Check if var_name contains any context pattern
            for pattern in self.patterns.CONTEXT_PATTERNS:
                if pattern in var_name:
                    if var_name not in var_usage:
                        var_usage[var_name] = set()
                    var_usage[var_name].add(component)
                    break

        # Check for variables used in >3 components
        for var, components in var_usage.items():
            count = len(components)
            if count > 3:
                comp_list = list(components)[:3]
                self.findings.append(StandardFinding(
                    rule_name='react-global-state',
                    message=f'Variable {var} used in {count} components - candidate for global state',
                    file_path='',
                    line=1,
                    severity=Severity.LOW,
                    category='react-state',
                    snippet=f'Used in: {", ".join(comp_list)}...',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))

    def _check_unnecessary_state(self):
        """Check for state that could be derived."""
        self.cursor.execute("""
            SELECT h1.file, h1.line, h1.component_name
            FROM react_hooks h1
            WHERE h1.hook_name = 'useState'
              AND EXISTS (
                  SELECT 1 FROM react_hooks h2
                  WHERE h2.file = h1.file
                    AND h2.component_name = h1.component_name
                    AND h2.hook_name = 'useEffect'
                    AND h2.line > h1.line
                    AND h2.line < h1.line + 5
                    AND h2.dependency_array IS NOT NULL
                    AND h2.dependency_array != '[]'
              )
            LIMIT 50
        """)

        for row in self.cursor.fetchall():
            file, line, component = row

            self.findings.append(StandardFinding(
                rule_name='react-unnecessary-state',
                message='State immediately updated in effect - may be unnecessary',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='react-state',
                snippet='useState followed by immediate useEffect',
                confidence=Confidence.LOW,
                cwe_id='CWE-1066'
            ))

    def _check_state_initialization(self):
        """Check for expensive state initialization."""
        # Fetch all useState hooks, filter in Python
        self.cursor.execute("""
            SELECT file, line, hook_name, callback_body
            FROM react_hooks
            WHERE hook_name = 'useState'
              AND callback_body IS NOT NULL
            LIMIT 200
        """)

        expensive_patterns = ['fetch', 'localStorage', 'sessionStorage', 'JSON.parse']

        for row in self.cursor.fetchall():
            file, line, hook, callback = row

            if not callback or len(callback) <= 50:
                continue

            # Check for expensive operations
            callback_str = str(callback)
            has_expensive = any(pattern in callback_str for pattern in expensive_patterns)

            if has_expensive:
                self.findings.append(StandardFinding(
                    rule_name='react-expensive-init',
                    message='Expensive operation in useState initialization',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='react-state',
                    snippet='useState with expensive initialization',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-1050'
                ))

    def _check_complex_state_objects(self):
        """Check for overly complex state objects."""
        # Fetch all useState hooks, filter in Python
        self.cursor.execute("""
            SELECT file, line, component_name, callback_body
            FROM react_hooks
            WHERE hook_name = 'useState'
              AND callback_body IS NOT NULL
            LIMIT 200
        """)

        for row in self.cursor.fetchall():
            file, line, component, callback = row

            callback_str = str(callback) if callback else ''

            # Check if callback contains object literal and is long
            if '{' not in callback_str or len(callback_str) <= 200:
                continue

            # Count approximate number of properties
            prop_count = callback_str.count(':')

            if prop_count > 5:
                self.findings.append(StandardFinding(
                    rule_name='react-complex-state',
                    message=f'Complex state object with ~{prop_count} properties',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-state',
                    snippet=f'useState with {prop_count}+ properties',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-1066'
                ))

    def _check_state_batching(self):
        """Check for state updates that should be batched."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, caller_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND caller_function IS NOT NULL
            LIMIT 1000
        """)

        # Build map of file -> line -> calls
        calls_by_location = {}
        for file, line, callee, caller in self.cursor.fetchall():
            # Check if callee starts with 'set'
            if not (callee and callee.startswith('set')):
                continue

            key = file
            if key not in calls_by_location:
                calls_by_location[key] = {}

            line_key = (line, caller)
            if line_key not in calls_by_location[key]:
                calls_by_location[key][line_key] = []
            calls_by_location[key][line_key].append(callee)

        # Check for consecutive lines with setters in same function
        for file, line_data in calls_by_location.items():
            sorted_lines = sorted(line_data.keys())
            for i in range(len(sorted_lines) - 1):
                (line1, caller1), (line2, caller2) = sorted_lines[i], sorted_lines[i + 1]

                # Check if consecutive lines in same function
                if line2 == line1 + 1 and caller1 == caller2:
                    setter1 = line_data[(line1, caller1)][0]
                    setter2 = line_data[(line2, caller2)][0]

                    self.findings.append(StandardFinding(
                        rule_name='react-unbatched-updates',
                        message=f'Consecutive state updates: {setter1}, {setter2}',
                        file_path=file,
                        line=line1,
                        severity=Severity.LOW,
                        category='react-state',
                        snippet=f'{setter1}(); {setter2}()',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-1050'
                    ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect React state management issues and anti-patterns.

    Uses data from react_hooks and related tables to identify state
    complexity, prop drilling, and management issues.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of React state management issues found
    """
    analyzer = ReactStateAnalyzer(context)
    return analyzer.analyze()
