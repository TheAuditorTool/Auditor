"""React Hooks Analyzer - Database-Driven Implementation.

Detects React hooks violations and anti-patterns using REAL DATA from
react_hooks, react_components, and variable_usage tables.

No more broken heuristics - this uses actual parsed dependency arrays,
cleanup detection, and component boundaries from the database.
"""

import sqlite3
import json
from typing import List, Dict, Any
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Orchestrator Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="react_hooks_issues",
    category="react",

    # Target React files only
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],

    # Focus on frontend directories
    target_file_patterns=['frontend/', 'client/', 'src/'],

    # Skip non-source files
    exclude_patterns=['node_modules/', '__tests__/', '*.test.jsx', '*.test.tsx', 'migrations/'],

    # Hooks work on transformed data (standard tables)
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ReactHooksPatterns:
    """Immutable pattern definitions for React hooks violations."""

    # Hooks that require dependency arrays
    HOOKS_WITH_DEPS = frozenset([
        'useEffect', 'useCallback', 'useMemo', 'useLayoutEffect', 'useImperativeHandle'
    ])

    # Hooks that should NOT have dependency arrays
    HOOKS_WITHOUT_DEPS = frozenset([
        'useState', 'useReducer', 'useRef', 'useContext', 'useId', 'useDebugValue'
    ])

    # Functions that create subscriptions/timers requiring cleanup
    CLEANUP_REQUIRED = frozenset([
        'addEventListener', 'setInterval', 'setTimeout', 'requestAnimationFrame',
        'subscribe', 'on', 'addListener', 'observe', 'observeIntersection',
        'WebSocket', 'EventSource', 'MutationObserver', 'ResizeObserver'
    ])

    # Cleanup functions
    CLEANUP_FUNCTIONS = frozenset([
        'removeEventListener', 'clearInterval', 'clearTimeout', 'cancelAnimationFrame',
        'unsubscribe', 'off', 'removeListener', 'disconnect', 'close', 'abort'
    ])

    # Hooks that must be called at top level
    TOP_LEVEL_HOOKS = frozenset([
        'useState', 'useEffect', 'useContext', 'useReducer', 'useCallback',
        'useMemo', 'useRef', 'useLayoutEffect', 'useImperativeHandle', 'useDebugValue'
    ])

    # State setters that indicate potential issues
    DANGEROUS_SETTERS = frozenset([
        'push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class ReactHooksAnalyzer:
    """Analyzer for React hooks violations and best practices."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ReactHooksPatterns()
        self.findings = []

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of React hooks violations found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        try:
            # Run all checks (schema contract guarantees tables exist)
            self._check_missing_dependencies()
            self._check_memory_leaks()
            self._check_conditional_hooks()
            self._check_exhaustive_deps()
            self._check_async_useeffect()
            self._check_stale_closures()
            self._check_cleanup_consistency()
            self._check_hook_order()
            self._check_custom_hook_violations()
            self._check_effect_race_conditions()

        finally:
            conn.close()

        return self.findings

    def _check_missing_dependencies(self):
        """Check for missing dependencies in hooks - NOW WITH REAL DATA!"""
        self.cursor.execute("""
            SELECT rh.file, rh.line, rh.hook_name, rh.component_name,
                   rh.dependency_array,
                   GROUP_CONCAT(rhd.dependency_name) as dependency_vars
            FROM react_hooks rh
            LEFT JOIN react_hook_dependencies rhd
                ON rh.file = rhd.hook_file
                AND rh.line = rhd.hook_line
                AND rh.component_name = rhd.hook_component
            WHERE rh.hook_name IN ('useEffect', 'useCallback', 'useMemo')
              AND rh.dependency_array IS NOT NULL
            GROUP BY rh.file, rh.line, rh.hook_name, rh.component_name, rh.dependency_array
        """)

        for row in self.cursor.fetchall():
            file, line, hook_name, component, deps_array_json, deps_vars_concat = row

            # Parse JSON array for declared deps
            try:
                declared_deps = json.loads(deps_array_json) if deps_array_json else []
            except json.JSONDecodeError:
                continue

            # Parse concatenated dependency names
            used_vars = deps_vars_concat.split(',') if deps_vars_concat else []

            # Skip if empty deps array (handled by exhaustive deps check)
            if declared_deps == []:
                continue

            # Find missing dependencies
            missing = []
            for var in used_vars:
                # Clean up variable name
                var_clean = var.split('.')[0] if '.' in var else var

                # Check if it's in declared deps
                if var_clean and var_clean not in declared_deps:
                    # Filter out common false positives
                    if var_clean not in ['console', 'window', 'document', 'Math',
                                         'JSON', 'Object', 'Array', 'undefined', 'null']:
                        missing.append(var_clean)

            if missing:
                self.findings.append(StandardFinding(
                    rule_name='react-missing-dependency',
                    message=f'{hook_name} is missing dependencies: {", ".join(missing[:5])}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react-hooks',
                    snippet=f'{hook_name}(..., [{", ".join(declared_deps)}])',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-670'
                ))

    def _check_memory_leaks(self):
        """Check for potential memory leaks - NOW WITH CLEANUP DETECTION!"""
        self.cursor.execute("""
            SELECT file, line, hook_name, component_name,
                   callback_body, has_cleanup, cleanup_type
            FROM react_hooks
            WHERE hook_name = 'useEffect'
              AND callback_body IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file, line, hook, component, callback, has_cleanup, cleanup_type = row

            # Check if callback contains subscription patterns
            needs_cleanup = False
            subscription_type = None

            for pattern in self.patterns.CLEANUP_REQUIRED:
                if pattern in callback:
                    needs_cleanup = True
                    subscription_type = pattern
                    break

            # If needs cleanup but doesn't have it
            if needs_cleanup and not has_cleanup:
                self.findings.append(StandardFinding(
                    rule_name='react-memory-leak',
                    message=f'useEffect with {subscription_type} is missing cleanup function',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react-hooks',
                    snippet=f'useEffect with {subscription_type}',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-401'
                ))

            # Check for inconsistent cleanup
            elif has_cleanup and cleanup_type and not needs_cleanup:
                # Has cleanup but might not need it
                if cleanup_type not in ['cleanup_function', 'unknown']:
                    self.findings.append(StandardFinding(
                        rule_name='react-unnecessary-cleanup',
                        message=f'useEffect has {cleanup_type} but no subscription detected',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category='react-hooks',
                        snippet=f'useEffect with {cleanup_type}',
                        confidence=Confidence.LOW,
                        cwe_id='CWE-398'
                    ))

    def _check_conditional_hooks(self):
        """Check for hooks called conditionally - USING CFG DATA!"""
        self.cursor.execute("""
            SELECT DISTINCT h.file, h.line, h.hook_name, h.component_name,
                   b.block_type, b.condition_expr
            FROM react_hooks h
            JOIN cfg_blocks b ON h.file = b.file
            WHERE b.block_type IN ('condition', 'loop')
              AND h.line BETWEEN b.start_line AND b.end_line
              AND h.hook_name IN ('useState', 'useEffect', 'useContext', 'useReducer',
                                  'useCallback', 'useMemo', 'useRef')
        """)

        for row in self.cursor.fetchall():
            file, line, hook, component, block_type, condition = row

            self.findings.append(StandardFinding(
                rule_name='react-conditional-hook',
                message=f'{hook} is called inside a {block_type} block',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='react-hooks',
                snippet=f'{hook} inside {block_type}',
                confidence=Confidence.HIGH,
                cwe_id='CWE-670'
            ))

    def _check_exhaustive_deps(self):
        """Check for effects with empty dependencies that should have some."""
        self.cursor.execute("""
            SELECT rh.file, rh.line, rh.hook_name, rh.component_name,
                   rh.dependency_array, rh.callback_body,
                   GROUP_CONCAT(rhd.dependency_name) as dependency_vars
            FROM react_hooks rh
            LEFT JOIN react_hook_dependencies rhd
                ON rh.file = rhd.hook_file
                AND rh.line = rhd.hook_line
                AND rh.component_name = rhd.hook_component
            WHERE rh.hook_name IN ('useEffect', 'useCallback', 'useMemo')
              AND rh.dependency_array = '[]'
            GROUP BY rh.file, rh.line, rh.hook_name, rh.component_name, rh.dependency_array, rh.callback_body
            HAVING dependency_vars IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file, line, hook, component, deps_array, callback, deps_vars_concat = row

            # Parse concatenated dependency names
            used_vars = deps_vars_concat.split(',') if deps_vars_concat else []

            # Filter out globals and built-ins
            local_vars = [v for v in used_vars
                         if v not in ['console', 'window', 'document', 'Math',
                                     'JSON', 'Object', 'Array', 'undefined', 'null']]

            if local_vars:
                self.findings.append(StandardFinding(
                    rule_name='react-exhaustive-deps',
                    message=f'{hook} has empty dependency array but uses: {", ".join(local_vars[:3])}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='react-hooks',
                    snippet=f'{hook}(..., [])',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-670'
                ))

    def _check_async_useeffect(self):
        """Check for async functions passed directly to useEffect."""
        self.cursor.execute("""
            SELECT file, line, component_name, callback_body
            FROM react_hooks
            WHERE hook_name = 'useEffect'
              AND callback_body IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file, line, component, callback = row

            # Check if async is at the beginning (direct async function)
            if callback and callback.strip().startswith('async'):
                self.findings.append(StandardFinding(
                    rule_name='react-async-useeffect',
                    message='useEffect cannot accept async functions directly',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='react-hooks',
                    snippet='useEffect(async () => {...})',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-670'
                ))

    def _check_stale_closures(self):
        """Check for potential stale closure issues."""
        self.cursor.execute("""
            SELECT file, line, hook_name, component_name,
                   dependency_array, callback_body
            FROM react_hooks
            WHERE hook_name = 'useCallback'
              AND dependency_array = '[]'
              AND callback_body IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file, line, hook, component, deps, callback = row

            if 'setState' in (callback or ''):
                self.findings.append(StandardFinding(
                    rule_name='react-stale-closure',
                    message='useCallback with setState and empty deps may cause stale closures',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='react-hooks',
                    snippet='useCallback with setState and []',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-367'
                ))

    def _check_cleanup_consistency(self):
        """Check for inconsistent cleanup patterns."""
        self.cursor.execute("""
            SELECT file, component_name,
                   COUNT(*) as total,
                   SUM(has_cleanup) as with_cleanup
            FROM react_hooks
            WHERE hook_name = 'useEffect'
            GROUP BY file, component_name
            HAVING total > 1 AND with_cleanup > 0 AND with_cleanup < total
        """)

        for row in self.cursor.fetchall():
            file, component, total, with_cleanup = row

            self.findings.append(StandardFinding(
                rule_name='react-inconsistent-cleanup',
                message=f'Component has {with_cleanup}/{total} effects with cleanup - inconsistent pattern',
                file_path=file,
                line=1,
                severity=Severity.LOW,
                category='react-hooks',
                snippet=f'{component}: mixed cleanup pattern',
                confidence=Confidence.LOW,
                cwe_id='CWE-398'
            ))

    def _check_hook_order(self):
        """Check for hooks called in inconsistent order."""
        self.cursor.execute("""
            SELECT h.file, h.component_name, h.hook_name, h.line
            FROM react_hooks h
            JOIN react_components c ON h.file = c.file
              AND h.component_name = c.name
            WHERE h.line BETWEEN c.start_line AND c.end_line
            ORDER BY h.file, h.component_name, h.line
        """)

        current_component = None
        hooks_order = []

        for row in self.cursor.fetchall():
            file, component, hook, line = row

            # New component
            if component != current_component:
                # Check previous component's hook order
                if hooks_order and self._has_order_issue(hooks_order):
                    self.findings.append(StandardFinding(
                        rule_name='react-hooks-order',
                        message=f'Hooks called in inconsistent order in {current_component}',
                        file_path=file,
                        line=hooks_order[0][1],  # First hook's line
                        severity=Severity.MEDIUM,
                        category='react-hooks',
                        snippet=f'Hook order: {", ".join([h[0] for h in hooks_order[:5]])}',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-670'
                    ))

                # Reset for new component
                current_component = component
                hooks_order = []

            hooks_order.append((hook, line))

    def _has_order_issue(self, hooks: List[tuple]) -> bool:
        """Check if hooks have order issues."""
        # Simplified check: state hooks should come before effect hooks
        state_seen = False
        effect_seen = False

        for hook, _ in hooks:
            if hook in ['useState', 'useReducer', 'useRef']:
                if effect_seen:
                    return True  # State hook after effect
                state_seen = True
            elif hook in ['useEffect', 'useLayoutEffect']:
                effect_seen = True

        return False

    def _check_custom_hook_violations(self):
        """Check custom hooks for violations."""
        builtin_hooks = [
            'useState', 'useEffect', 'useContext',
            'useReducer', 'useCallback', 'useMemo',
            'useRef', 'useLayoutEffect', 'useImperativeHandle',
            'useDebugValue', 'useId', 'useTransition',
            'useDeferredValue', 'useSyncExternalStore'
        ]
        placeholders = ",".join("?" for _ in builtin_hooks)

        self.cursor.execute(f"""
            SELECT DISTINCT file, hook_name, component_name, line
            FROM react_hooks
            WHERE hook_name NOT IN ({placeholders})
        """, builtin_hooks)

        for row in self.cursor.fetchall():
            file, hook, component, line = row

            if not hook or not hook.startswith('use'):
                continue

            # Check if it starts with lowercase after 'use'
            if len(hook) > 3 and hook[3].islower():
                self.findings.append(StandardFinding(
                    rule_name='react-custom-hook-naming',
                    message=f'Custom hook {hook} should use PascalCase after "use"',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='react-hooks',
                    snippet=f'{hook}()',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-1078'
                ))

    def _check_effect_race_conditions(self):
        """Check for potential race conditions in effects."""
        self.cursor.execute("""
            SELECT file, component_name, COUNT(*) as effect_count,
                   GROUP_CONCAT(dependency_array) as all_deps
            FROM react_hooks
            WHERE hook_name = 'useEffect'
              AND dependency_array IS NOT NULL
            GROUP BY file, component_name
            HAVING effect_count > 2
        """)

        for row in self.cursor.fetchall():
            file, component, count, all_deps = row

            # Check if multiple effects have overlapping dependencies
            if all_deps and all_deps.count('[id]') > 1:
                self.findings.append(StandardFinding(
                    rule_name='react-effect-race',
                    message=f'Component has {count} effects that may race - consider combining',
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category='react-hooks',
                    snippet=f'{component}: {count} useEffect calls',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-362'
                ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React hooks violations and anti-patterns.

    Uses real data from react_hooks, react_components, and variable_usage
    tables for accurate detection instead of broken heuristics.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of React hooks violations found
    """
    analyzer = ReactHooksAnalyzer(context)
    return analyzer.analyze()
