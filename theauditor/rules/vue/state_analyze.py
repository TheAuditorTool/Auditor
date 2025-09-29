"""Vue State Management Analyzer - Database-First Approach.

Detects Vuex and Pinia state management anti-patterns and issues using
indexed database data. NO AST traversal. Pure SQL queries.

Follows golden standard patterns:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels
"""

import sqlite3
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Vuex patterns
VUEX_PATTERNS = frozenset([
    'createStore', 'useStore', '$store', 'this.$store',
    'mapState', 'mapGetters', 'mapActions', 'mapMutations',
    'commit', 'dispatch', 'subscribe', 'subscribeAction',
    'registerModule', 'unregisterModule', 'hasModule'
])

# Pinia patterns
PINIA_PATTERNS = frozenset([
    'defineStore', 'createPinia', 'setActivePinia',
    'storeToRefs', 'acceptHMRUpdate', 'useStore',
    '$patch', '$reset', '$subscribe', '$onAction',
    '$dispose', 'getActivePinia', 'setMapStoreSuffix'
])

# State mutation patterns
STATE_MUTATIONS = frozenset([
    'state.', 'this.state.', '$store.state.',
    'store.state.', 'this.$store.state.'
])

# Vuex strict mode violations
STRICT_VIOLATIONS = frozenset([
    'state.', 'this.$store.state.', 'store.state.',
    'Object.assign', 'Array.push', 'Array.splice',
    'delete ', 'Vue.set', 'Vue.delete'
])

# Action patterns
ACTION_PATTERNS = frozenset([
    'actions:', 'dispatch', 'store.dispatch', '$store.dispatch',
    'mapActions', 'action.type', 'action.payload'
])

# Mutation patterns
MUTATION_PATTERNS = frozenset([
    'mutations:', 'commit', 'store.commit', '$store.commit',
    'mapMutations', 'mutation.type', 'mutation.payload'
])

# Getter patterns
GETTER_PATTERNS = frozenset([
    'getters:', 'store.getters', '$store.getters',
    'mapGetters', 'rootGetters', 'getter'
])

# Common state management anti-patterns
ANTIPATTERNS = frozenset([
    'localStorage', 'sessionStorage', 'window.',
    'document.', 'global.', 'process.env'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_vue_state_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue state management anti-patterns (Vuex/Pinia).

    Detects:
    - Direct state mutations outside mutations
    - Missing namespacing in modules
    - Synchronous operations in actions
    - State persistence issues
    - Memory leaks from subscriptions
    - Circular dependencies in getters
    - Excessive store size

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Vue state management issues found
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check if required tables exist (Golden Standard)
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'files', 'symbols', 'assignments',
                'function_call_args', 'cfg_blocks'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables
        if 'assignments' not in existing_tables:
            return findings

        # Get state management files
        store_files = _get_store_files(cursor, existing_tables)
        if not store_files:
            return findings

        # Track available tables for graceful degradation
        has_symbols = 'symbols' in existing_tables
        has_function_calls = 'function_call_args' in existing_tables
        has_cfg_blocks = 'cfg_blocks' in existing_tables

        # ========================================================
        # CHECK 1: Direct State Mutations
        # ========================================================
        findings.extend(_find_direct_state_mutations(cursor, store_files))

        # ========================================================
        # CHECK 2: Async in Mutations
        # ========================================================
        if has_function_calls:
            findings.extend(_find_async_mutations(cursor, store_files))

        # ========================================================
        # CHECK 3: Missing Module Namespacing
        # ========================================================
        if has_symbols:
            findings.extend(_find_missing_namespacing(cursor, store_files))

        # ========================================================
        # CHECK 4: Memory Leaks from Subscriptions
        # ========================================================
        if has_function_calls:
            findings.extend(_find_subscription_leaks(cursor, store_files))

        # ========================================================
        # CHECK 5: Circular Dependencies in Getters
        # ========================================================
        if has_symbols and has_function_calls:
            findings.extend(_find_circular_getters(cursor, store_files))

        # ========================================================
        # CHECK 6: State Persistence Issues
        # ========================================================
        findings.extend(_find_persistence_issues(cursor, store_files))

        # ========================================================
        # CHECK 7: Excessive Store Size
        # ========================================================
        if has_symbols:
            findings.extend(_find_large_stores(cursor, store_files))

        # ========================================================
        # CHECK 8: Missing Error Handling in Actions
        # ========================================================
        if has_function_calls:
            findings.extend(_find_unhandled_action_errors(cursor, store_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_store_files(cursor, existing_tables: Set[str]) -> Set[str]:
    """Get all Vuex/Pinia store files."""
    store_files = set()

    # Find store files by name pattern
    if 'files' in existing_tables:
        cursor.execute("""
            SELECT DISTINCT file_path
            FROM files
            WHERE file_path LIKE '%store%'
               OR file_path LIKE '%vuex%'
               OR file_path LIKE '%pinia%'
               OR file_path LIKE '%state%'
        """)
        store_files.update(row[0] for row in cursor.fetchall())

    # Find files with store patterns
    if 'symbols' in existing_tables:
        all_patterns = list(VUEX_PATTERNS | PINIA_PATTERNS)
        placeholders = ','.join('?' * len(all_patterns))

        cursor.execute(f"""
            SELECT DISTINCT path
            FROM symbols
            WHERE name IN ({placeholders})
               OR name LIKE '%$store%'
               OR name LIKE '%defineStore%'
               OR name LIKE '%createStore%'
        """, all_patterns)
        store_files.update(row[0] for row in cursor.fetchall())

    return store_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_direct_state_mutations(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find direct state mutations outside of mutations."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find direct assignments to state
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND (target_var LIKE 'state.%'
               OR target_var LIKE 'this.state.%'
               OR target_var LIKE '$store.state.%'
               OR target_var LIKE 'store.state.%')
          AND file NOT LIKE '%mutation%'
          AND file NOT LIKE '%reducer%'
        ORDER BY file, line
    """, list(store_files))

    for file, line, target, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-direct-state-mutation',
            message=f'Direct state mutation "{target}" outside of mutation',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='vuex-antipattern',
            confidence=Confidence.HIGH,
            cwe_id='CWE-471'
        ))

    # Find array/object mutations
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse')
          AND (f.argument_expr LIKE '%state.%'
               OR f.argument_expr LIKE '%$store.state%')
        ORDER BY f.file, f.line
    """, list(store_files))

    for file, line, method, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-state-array-mutation',
            message=f'Array mutation method {method} on state',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vuex-antipattern',
            confidence=Confidence.HIGH,
            cwe_id='CWE-471'
        ))

    return findings


def _find_async_mutations(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find async operations in mutations (anti-pattern)."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find async operations in mutations
    cursor.execute(f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND (file LIKE '%mutation%' OR file LIKE '%mutations.%')
          AND callee_function IN (
              'setTimeout', 'setInterval', 'fetch', 'axios',
              'Promise', 'async', 'await', 'then', 'catch'
          )
        ORDER BY file, line
    """, list(store_files))

    for file, line, async_op in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-async-mutation',
            message=f'Async operation {async_op} in mutation - use actions instead',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vuex-antipattern',
            confidence=Confidence.HIGH,
            cwe_id='CWE-662'
        ))

    return findings


def _find_missing_namespacing(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find modules without proper namespacing."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find modules without namespaced: true
    cursor.execute(f"""
        SELECT DISTINCT path
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND path LIKE '%modules%'
          AND NOT EXISTS (
              SELECT 1 FROM symbols s2
              WHERE s2.path = path
                AND (s2.name LIKE 'namespaced%true'
                     OR s2.name LIKE '"namespaced": true')
          )
        ORDER BY path
    """, list(store_files))

    for file, in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-module-no-namespace',
            message='Store module without namespacing - naming conflicts risk',
            file_path=file,
            line=1,
            severity=Severity.MEDIUM,
            category='vuex-architecture',
            confidence=Confidence.LOW,
            cwe_id='CWE-1061'
        ))

    return findings


def _find_subscription_leaks(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find store subscriptions without cleanup."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find subscribe without unsubscribe
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('subscribe', 'subscribeAction', '$subscribe', '$onAction')
          AND NOT EXISTS (
              SELECT 1 FROM assignments a
              WHERE a.file = f.file
                AND a.line = f.line
                AND a.target_var LIKE '%unsubscribe%'
          )
        ORDER BY f.file, f.line
    """, list(store_files))

    for file, line, subscription in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-subscription-leak',
            message=f'{subscription} without cleanup - memory leak',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vuex-memory-leak',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-401'
        ))

    return findings


def _find_circular_getters(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find circular dependencies in getters."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find getters that reference other getters
    cursor.execute(f"""
        SELECT s.path, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name LIKE '%getters.%'
          AND EXISTS (
              SELECT 1 FROM symbols s2
              WHERE s2.path = s.path
                AND s2.line > s.line
                AND s2.line < s.line + 10
                AND s2.name LIKE '%getters.%'
          )
        ORDER BY s.path, s.line
    """, list(store_files))

    for file, line, getter in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-circular-getter',
            message='Getter referencing other getters - potential circular dependency',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vuex-architecture',
            confidence=Confidence.LOW,
            cwe_id='CWE-1047'
        ))

    return findings


def _find_persistence_issues(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find state persistence anti-patterns."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find localStorage/sessionStorage in store
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND (source_expr LIKE '%localStorage%'
               OR source_expr LIKE '%sessionStorage%'
               OR target_var LIKE '%localStorage%'
               OR target_var LIKE '%sessionStorage%')
        ORDER BY file, line
    """, list(store_files))

    for file, line, target, source in cursor.fetchall():
        if 'localStorage' in source or 'localStorage' in target:
            storage = 'localStorage'
        else:
            storage = 'sessionStorage'

        findings.append(StandardFinding(
            rule_name='vue-unsafe-persistence',
            message=f'Using {storage} for state persistence - use proper plugins',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vuex-persistence',
            confidence=Confidence.HIGH,
            cwe_id='CWE-922'
        ))

    # Find sensitive data in state
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND (target_var LIKE '%password%'
               OR target_var LIKE '%token%'
               OR target_var LIKE '%secret%'
               OR target_var LIKE '%apiKey%'
               OR target_var LIKE '%creditCard%'
               OR target_var LIKE '%ssn%')
          AND target_var LIKE 'state.%'
        ORDER BY file, line
    """, list(store_files))

    for file, line, var, _ in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-sensitive-in-state',
            message=f'Sensitive data "{var}" in state - security risk',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vuex-security',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-200'
        ))

    return findings


def _find_large_stores(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find excessively large store definitions."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Count state properties
    cursor.execute(f"""
        SELECT path, COUNT(*) as prop_count
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND (name LIKE 'state.%' OR name LIKE 'state:%')
        GROUP BY path
        HAVING prop_count > 50
    """, list(store_files))

    for file, count in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-large-store',
            message=f'Store has {count} state properties - consider modularization',
            file_path=file,
            line=1,
            severity=Severity.MEDIUM,
            category='vuex-architecture',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1061'
        ))

    # Count actions/mutations
    cursor.execute(f"""
        SELECT path,
               SUM(CASE WHEN name LIKE '%action%' THEN 1 ELSE 0 END) as actions,
               SUM(CASE WHEN name LIKE '%mutation%' THEN 1 ELSE 0 END) as mutations
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND (name LIKE '%action%' OR name LIKE '%mutation%')
        GROUP BY path
        HAVING actions > 30 OR mutations > 30
    """, list(store_files))

    for file, actions, mutations in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-too-many-actions',
            message=f'Store has {actions} actions and {mutations} mutations - refactor needed',
            file_path=file,
            line=1,
            severity=Severity.LOW,
            category='vuex-architecture',
            confidence=Confidence.LOW,
            cwe_id='CWE-1061'
        ))

    return findings


def _find_unhandled_action_errors(cursor, store_files: Set[str]) -> List[StandardFinding]:
    """Find actions without error handling."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find async actions without try-catch
    cursor.execute(f"""
        SELECT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND (f1.file LIKE '%action%' OR f1.file LIKE '%actions.%')
          AND f1.callee_function IN ('fetch', 'axios', 'post', 'get', 'put', 'delete')
          AND NOT EXISTS (
              SELECT 1 FROM function_call_args f2
              WHERE f2.file = f1.file
                AND ABS(f2.line - f1.line) <= 10
                AND f2.callee_function IN ('catch', 'try', 'finally')
          )
        ORDER BY f1.file, f1.line
    """, list(store_files))

    for file, line, api_call in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-action-no-error-handling',
            message=f'Action with {api_call} but no error handling',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vuex-error-handling',
            confidence=Confidence.LOW,
            cwe_id='CWE-248'
        ))

    return findings