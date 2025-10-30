"""Vue Composition API Hooks Analyzer - Database-First Approach.

Detects Vue 3 Composition API misuse and hook-related issues using
indexed database data. NO AST traversal. Pure SQL queries.

Follows v1.1+ gold standard patterns:
- Frozensets for all patterns (O(1) lookups)
- NO table existence checks (schema contract guarantees all tables exist)
- Direct database queries (crash on missing tables to expose indexer bugs)
- Proper confidence levels via Confidence enum
"""

import sqlite3
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Phase 3B - Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="vue_hooks",
    category="vue",
    target_extensions=['.vue', '.js', '.ts', '.jsx', '.tsx'],
    target_file_patterns=['frontend/', 'client/', 'src/components/', 'src/composables/', 'src/hooks/'],
    exclude_patterns=['backend/', 'server/', 'api/', 'migrations/', '__tests__/', '*.test.*', '*.spec.*'],
    requires_jsx_pass=False  # Composition API uses standard tables
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Vue 3 Composition API lifecycle hooks
COMPOSITION_LIFECYCLE = frozenset([
    'onBeforeMount', 'onMounted', 'onBeforeUpdate', 'onUpdated',
    'onBeforeUnmount', 'onUnmounted', 'onActivated', 'onDeactivated',
    'onErrorCaptured', 'onRenderTracked', 'onRenderTriggered',
    'onServerPrefetch'
])

# Composition API reactivity functions
REACTIVITY_FUNCTIONS = frozenset([
    'ref', 'reactive', 'computed', 'readonly', 'shallowRef',
    'shallowReactive', 'shallowReadonly', 'toRef', 'toRefs',
    'isRef', 'isReactive', 'isReadonly', 'isProxy'
])

# Watch functions
WATCH_FUNCTIONS = frozenset([
    'watch', 'watchEffect', 'watchPostEffect', 'watchSyncEffect'
])

# Provide/inject patterns
PROVIDE_INJECT = frozenset([
    'provide', 'inject'
])

# Cleanup functions
CLEANUP_FUNCTIONS = frozenset([
    'stop', 'unwatch', 'cleanup', 'dispose', 'destroy',
    'removeEventListener', 'clearInterval', 'clearTimeout',
    'unsubscribe', 'abort', 'close'
])

# Functions that must be in setup
SETUP_ONLY_FUNCTIONS = frozenset([
    'useStore', 'useRouter', 'useRoute', 'useMeta',
    'useHead', 'useI18n', 'useNuxt', 'useFetch'
])

# Common memory leak patterns
MEMORY_LEAK_PATTERNS = frozenset([
    'addEventListener', 'setInterval', 'setTimeout',
    'ResizeObserver', 'IntersectionObserver', 'MutationObserver',
    'WebSocket', 'EventSource', 'Worker'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_vue_hooks_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue Composition API hooks misuse and issues.

    Detects:
    - Hooks called outside setup()
    - Missing cleanup in lifecycle hooks
    - Dependency issues in watch/computed
    - Memory leaks from refs/reactive
    - Incorrect hook ordering
    - Excessive reactivity overhead
    - Missing error boundaries

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Vue hooks issues found
    """
    findings = []

    if not context.db_path:
        return findings

    # NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
    # If tables are missing, the rule MUST crash to expose indexer bugs.

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Get Vue Composition API files (schema contract guarantees tables exist)
        vue_files = _get_composition_api_files(cursor)
        if not vue_files:
            return findings

        # Run all checks - schema contract guarantees all tables exist
        findings.extend(_find_hooks_outside_setup(cursor, vue_files))
        findings.extend(_find_missing_cleanup(cursor, vue_files))
        findings.extend(_find_watch_issues(cursor, vue_files))
        findings.extend(_find_memory_leaks(cursor, vue_files))
        findings.extend(_find_incorrect_hook_order(cursor, vue_files))
        findings.extend(_find_excessive_reactivity(cursor, vue_files))
        findings.extend(_find_missing_error_boundaries(cursor, vue_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_composition_api_files(cursor) -> Set[str]:
    """Get all files using Vue Composition API.

    Schema contract (v1.1+) guarantees all tables exist.
    If table is missing, we WANT the rule to crash to expose indexer bugs.
    """
    vue_files = set()

    # Find files with Composition API imports from symbols table
    cursor.execute("""
        SELECT DISTINCT path, name
        FROM symbols
        WHERE name IS NOT NULL
    """)

    # Filter in Python for Vue Composition API patterns
    for path, name in cursor.fetchall():
        name_lower = name.lower()
        if 'vue' in name_lower and any(pattern in name_lower for pattern in ['ref', 'reactive', 'computed', 'watch', 'setup']):
            vue_files.add(path)

    # Find files with Composition API function calls
    comp_api_funcs = list(COMPOSITION_LIFECYCLE | REACTIVITY_FUNCTIONS | WATCH_FUNCTIONS)
    placeholders = ','.join('?' * len(comp_api_funcs))

    cursor.execute(f"""
        SELECT DISTINCT file
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
    """, comp_api_funcs)
    vue_files.update(row[0] for row in cursor.fetchall())

    return vue_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_hooks_outside_setup(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find Composition API hooks called outside setup()."""
    findings = []

    setup_only = list(SETUP_ONLY_FUNCTIONS | COMPOSITION_LIFECYCLE)
    func_placeholders = ','.join('?' * len(setup_only))
    file_placeholders = ','.join('?' * len(vue_files))

    cursor.execute(f"""
        SELECT file, line, callee_function, caller_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({func_placeholders})
        ORDER BY file, line
    """, list(vue_files) + setup_only)

    # Filter in Python for hooks outside setup
    hooks_outside_setup = []
    for file, line, hook, context in cursor.fetchall():
        if not context or ('setup' not in context.lower()):
            hooks_outside_setup.append((file, line, hook, context))

    for file, line, hook, context in hooks_outside_setup:
        if hook in COMPOSITION_LIFECYCLE:
            message = f'Lifecycle hook {hook} must be called in setup()'
            severity = Severity.HIGH
        else:
            message = f'Composition API {hook} should be called in setup()'
            severity = Severity.MEDIUM

        findings.append(StandardFinding(
            rule_name='vue-hook-outside-setup',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='vue-composition-api',
            confidence=Confidence.MEDIUM if context else Confidence.LOW,
            cwe_id='CWE-665'
        ))

    return findings


def _find_missing_cleanup(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find lifecycle hooks with missing cleanup."""
    findings = []

    leak_patterns = list(MEMORY_LEAK_PATTERNS)
    leak_placeholders = ','.join('?' * len(leak_patterns))
    file_placeholders = ','.join('?' * len(vue_files))

    # Find onMounted/onBeforeUnmount pairs
    cursor.execute(f"""
        SELECT DISTINCT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND f1.callee_function IN ('onMounted', 'onActivated')
          AND EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.callee_function IN ({leak_placeholders})
                AND ABS(f2.line - f1.line) <= 20
          )
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f3
              WHERE f3.file = f1.file
                AND f3.callee_function IN ('onUnmounted', 'onDeactivated', 'onBeforeUnmount')
                AND f3.line > f1.line
          )
        ORDER BY f1.file, f1.line
    """, list(vue_files) + leak_patterns)

    for file, line, hook in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-missing-cleanup',
            message=f'{hook} with subscriptions but no cleanup hook',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-memory-leak',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-401'
        ))

    return findings


def _find_watch_issues(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find watch/watchEffect issues."""
    findings = []

    watch_funcs = list(WATCH_FUNCTIONS)
    watch_placeholders = ','.join('?' * len(watch_funcs))
    file_placeholders = ','.join('?' * len(vue_files))

    # Find watch without stop
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ({watch_placeholders})
        ORDER BY f.file, f.line
    """, list(vue_files) + watch_funcs)

    # Filter in Python for watches without stop
    for file, line, watch_func in cursor.fetchall():
        # Check for stop assignment at same line
        cursor.execute("""
            SELECT target_var
            FROM assignments
            WHERE file = ?
              AND line = ?
              AND target_var IS NOT NULL
        """, (file, line))

        has_stop = False
        for (target_var,) in cursor.fetchall():
            if 'stop' in target_var:
                has_stop = True
                break

        if not has_stop:
            findings.append(StandardFinding(
                rule_name='vue-watch-no-stop',
                message=f'{watch_func} without cleanup - memory leak risk',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='vue-memory-leak',
                confidence=Confidence.LOW,
                cwe_id='CWE-401'
            ))

    # Find deep watchers
    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({watch_placeholders})
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """, list(vue_files) + watch_funcs)

    # Filter in Python for deep watchers
    for file, line, func, args in cursor.fetchall():
        if 'deep: true' in args:
            findings.append(StandardFinding(
                rule_name='vue-deep-watch',
                message=f'Deep watcher in {func} - performance impact',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='vue-performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    return findings


def _find_memory_leaks(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find potential memory leaks from refs/reactive."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find large reactive objects
    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ('reactive', 'ref')
          AND LENGTH(argument_expr) > 500
        ORDER BY file, line
    """, list(vue_files))

    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-large-reactive',
            message=f'Large object passed to {func} - performance overhead',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vue-performance',
            confidence=Confidence.LOW,
            cwe_id='CWE-1050'
        ))

    # Find refs in loops
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('ref', 'reactive')
        ORDER BY f.file, f.line
    """, list(vue_files))

    # Store ref calls
    ref_calls = cursor.fetchall()

    # Get all loop blocks
    cursor.execute(f"""
        SELECT file, block_type, start_line, end_line
        FROM cfg_blocks
        WHERE file IN ({file_placeholders})
          AND block_type IS NOT NULL
    """, list(vue_files))

    # Filter in Python for loops
    loop_blocks = []
    for file, block_type, start, end in cursor.fetchall():
        if 'loop' in block_type.lower():
            loop_blocks.append((file, start, end))

    # Check if refs are in loops
    for file, line, func in ref_calls:
        in_loop = False
        for loop_file, start, end in loop_blocks:
            if loop_file == file and start <= line <= end:
                in_loop = True
                break

        if not in_loop:
            continue
        findings.append(StandardFinding(
            rule_name='vue-ref-in-loop',
            message=f'Creating {func} in loop - memory leak risk',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-memory-leak',
            confidence=Confidence.HIGH,
            cwe_id='CWE-401'
        ))

    return findings


def _find_incorrect_hook_order(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find incorrect lifecycle hook ordering."""
    findings = []

    lifecycle = list(COMPOSITION_LIFECYCLE)
    file_placeholders = ','.join('?' * len(vue_files))
    hook_placeholders = ','.join('?' * len(lifecycle))

    # Proper order: onBeforeMount -> onMounted -> onBeforeUpdate -> onUpdated -> onBeforeUnmount -> onUnmounted
    hook_order = {
        'onBeforeMount': 1,
        'onMounted': 2,
        'onBeforeUpdate': 3,
        'onUpdated': 4,
        'onBeforeUnmount': 5,
        'onUnmounted': 6
    }

    cursor.execute(f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({hook_placeholders})
        ORDER BY file, line
    """, list(vue_files) + lifecycle)

    # Group by file
    file_hooks = {}
    for file, line, hook in cursor.fetchall():
        if file not in file_hooks:
            file_hooks[file] = []
        if hook in hook_order:
            file_hooks[file].append((line, hook, hook_order[hook]))

    # Check order
    for file, hooks in file_hooks.items():
        hooks.sort(key=lambda x: x[0])  # Sort by line
        for i in range(len(hooks) - 1):
            if hooks[i][2] > hooks[i + 1][2]:  # Wrong order
                findings.append(StandardFinding(
                    rule_name='vue-hook-order',
                    message=f'{hooks[i][1]} called after {hooks[i + 1][1]} - incorrect order',
                    file_path=file,
                    line=hooks[i][0],
                    severity=Severity.MEDIUM,
                    category='vue-composition-api',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-665'
                ))

    return findings


def _find_excessive_reactivity(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find excessive use of reactivity (performance issue)."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Count reactive calls per file
    cursor.execute(f"""
        SELECT file, COUNT(*) as count
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ('ref', 'reactive', 'computed')
        GROUP BY file
        HAVING count > 50
    """, list(vue_files))

    for file, count in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-excessive-reactivity',
            message=f'File has {count} reactive declarations - performance overhead',
            file_path=file,
            line=1,
            severity=Severity.MEDIUM,
            category='vue-performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_missing_error_boundaries(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find missing error handling in hooks."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find files with hooks but no onErrorCaptured
    cursor.execute(f"""
        SELECT DISTINCT f1.file
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND f1.callee_function IN ('onMounted', 'onUpdated', 'watchEffect')
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND f2.callee_function = 'onErrorCaptured'
          )
        GROUP BY f1.file
        HAVING COUNT(DISTINCT f1.callee_function) > 3
    """, list(vue_files))

    for file, in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-no-error-boundary',
            message='Complex component without error boundary (onErrorCaptured)',
            file_path=file,
            line=1,
            severity=Severity.LOW,
            category='vue-error-handling',
            confidence=Confidence.LOW,
            cwe_id='CWE-248'
        ))

    return findings


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_vue_hooks_issues(context)