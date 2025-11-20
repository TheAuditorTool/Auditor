"""Vue State Management Analyzer - Database-First Approach.

Detects Vuex and Pinia state management anti-patterns and issues using
indexed database data. NO AST traversal. Pure SQL queries.

Follows v1.1+ gold standard patterns:
- Frozensets for all patterns (O(1) lookups)
- NO table existence checks (schema contract guarantees all tables exist)
- Direct database queries (crash on missing tables to expose indexer bugs)
- Proper confidence levels via Confidence enum
"""
from __future__ import annotations


import sqlite3
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Phase 3B - Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="vue_state",
    category="vue",
    target_extensions=['.js', '.ts'],
    target_file_patterns=['frontend/', 'client/', 'src/store/', 'src/stores/', 'store/', 'stores/'],
    exclude_patterns=['backend/', 'server/', 'api/', '__tests__/', '*.test.*', '*.spec.*'],
    requires_jsx_pass=False  # State management uses standard tables
)


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

def find_vue_state_issues(context: StandardRuleContext) -> list[StandardFinding]:
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

    # NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
    # If tables are missing, the rule MUST crash to expose indexer bugs.

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Get state management files (schema contract guarantees tables exist)
        store_files = _get_store_files(cursor)
        if not store_files:
            return findings

        # Run all checks - schema contract guarantees all tables exist
        findings.extend(_find_direct_state_mutations(cursor, store_files))
        findings.extend(_find_async_mutations(cursor, store_files))
        findings.extend(_find_missing_namespacing(cursor, store_files))
        findings.extend(_find_subscription_leaks(cursor, store_files))
        findings.extend(_find_circular_getters(cursor, store_files))
        findings.extend(_find_persistence_issues(cursor, store_files))
        findings.extend(_find_large_stores(cursor, store_files))
        findings.extend(_find_unhandled_action_errors(cursor, store_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_store_files(cursor) -> set[str]:
    """Get all Vuex/Pinia store files.

    Schema contract (v1.1+) guarantees all tables exist.
    If table is missing, we WANT the rule to crash to expose indexer bugs.
    """
    store_files = set()

    # Find store files by name pattern
    cursor.execute("""
        SELECT DISTINCT path
        FROM files
        WHERE path IS NOT NULL
    """)

    # Filter in Python for store patterns
    for (path,) in cursor.fetchall():
        path_lower = path.lower()
        if any(pattern in path_lower for pattern in ['store', 'vuex', 'pinia', 'state']):
            store_files.add(path)

    # Find files with store patterns
    all_patterns = list(VUEX_PATTERNS | PINIA_PATTERNS)
    placeholders = ','.join('?' * len(all_patterns))

    cursor.execute(f"""
        SELECT DISTINCT path, name
        FROM symbols
        WHERE name IN ({placeholders})
           OR name IS NOT NULL
    """, all_patterns)

    # Filter in Python for store-specific patterns
    for path, name in cursor.fetchall():
        if '$store' in name or 'defineStore' in name or 'createStore' in name:
            store_files.add(path)

    return store_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_direct_state_mutations(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find direct state mutations outside of mutations."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find direct assignments to state
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND target_var IS NOT NULL
        ORDER BY file, line
    """, list(store_files))

    # Filter in Python for state mutations outside mutations
    for file, line, target, source in cursor.fetchall():
        # Check if target is state assignment
        if not any(pattern in target for pattern in ['state.', 'this.state.', '$store.state.', 'store.state.']):
            continue

        # Skip mutation files
        file_lower = file.lower()
        if 'mutation' in file_lower or 'reducer' in file_lower:
            continue

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
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """, list(store_files))

    # Filter in Python for state mutations
    for file, line, method, args in cursor.fetchall():
        if 'state.' not in args and '$store.state' not in args:
            continue
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


def _find_async_mutations(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find async operations in mutations (anti-pattern)."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find async operations in mutations
    cursor.execute(f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN (
              'setTimeout', 'setInterval', 'fetch', 'axios',
              'Promise', 'async', 'await', 'then', 'catch'
          )
        ORDER BY file, line
    """, list(store_files))

    # Filter in Python for mutation files
    for file, line, async_op in cursor.fetchall():
        file_lower = file.lower()
        if 'mutation' not in file_lower and 'mutations.' not in file_lower:
            continue
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


def _find_missing_namespacing(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find modules without proper namespacing."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find modules without namespaced: true
    cursor.execute(f"""
        SELECT DISTINCT s1.path, s1.name
        FROM symbols s1
        WHERE s1.path IN ({file_placeholders})
          AND s1.name IS NOT NULL
        ORDER BY s1.path
    """, list(store_files))

    # Group by file and check for namespacing
    file_symbols = {}
    for path, name in cursor.fetchall():
        if path not in file_symbols:
            file_symbols[path] = []
        file_symbols[path].append(name)

    # Filter in Python for module files without namespacing
    for file, symbols in file_symbols.items():
        if 'modules' not in file.lower():
            continue

        # Check if any symbol has namespaced: true
        has_namespace = any('namespaced' in s and 'true' in s for s in symbols)
        if has_namespace:
            continue
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


def _find_subscription_leaks(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find store subscriptions without cleanup."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find subscribe without unsubscribe
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ('subscribe', 'subscribeAction', '$subscribe', '$onAction')
        ORDER BY f.file, f.line
    """, list(store_files))

    # Filter in Python for subscriptions without cleanup
    for file, line, subscription in cursor.fetchall():
        # Check for unsubscribe assignment at same line
        cursor.execute("""
            SELECT target_var
            FROM assignments
            WHERE file = ?
              AND line = ?
              AND target_var IS NOT NULL
        """, (file, line))

        has_unsubscribe = False
        for (target_var,) in cursor.fetchall():
            if 'unsubscribe' in target_var.lower():
                has_unsubscribe = True
                break

        if has_unsubscribe:
            continue
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


def _find_circular_getters(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find circular dependencies in getters."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find getters that reference other getters
    cursor.execute(f"""
        SELECT s.path, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
        ORDER BY s.path, s.line
    """, list(store_files))

    # Store all symbols
    all_symbols = cursor.fetchall()

    # Filter in Python for getter references
    for file, line, name in all_symbols:
        if 'getters.' not in name:
            continue

        # Check for other getters within 10 lines
        has_getter_ref = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and line2 > line and line2 < line + 10 and 'getters.' in name2:
                has_getter_ref = True
                break

        if not has_getter_ref:
            continue
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


def _find_persistence_issues(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find state persistence anti-patterns."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find localStorage/sessionStorage in store
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND (target_var IS NOT NULL OR source_expr IS NOT NULL)
        ORDER BY file, line
    """, list(store_files))

    # Filter in Python for storage usage
    for file, line, target, source in cursor.fetchall():
        if not ('localStorage' in (source or '') or 'sessionStorage' in (source or '') or
                'localStorage' in (target or '') or 'sessionStorage' in (target or '')):
            continue

        if 'localStorage' in (source or '') or 'localStorage' in (target or ''):
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
          AND target_var IS NOT NULL
        ORDER BY file, line
    """, list(store_files))

    # Filter in Python for sensitive patterns
    sensitive_patterns = frozenset(['password', 'token', 'secret', 'apikey', 'creditcard', 'ssn'])

    for file, line, var, _ in cursor.fetchall():
        var_lower = var.lower()

        # Must be in state
        if not var_lower.startswith('state.'):
            continue

        # Check for sensitive patterns
        if not any(pattern in var_lower for pattern in sensitive_patterns):
            continue
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


def _find_large_stores(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find excessively large store definitions."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Count state properties
    cursor.execute(f"""
        SELECT s.path, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
    """, list(store_files))

    # Filter in Python for state properties
    file_props = {}
    for path, name in cursor.fetchall():
        if name.startswith('state.') or name.startswith('state:'):
            if path not in file_props:
                file_props[path] = 0
            file_props[path] += 1

    for file, count in file_props.items():
        if count > 50:
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
        SELECT s.path, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
    """, list(store_files))

    # Filter in Python for actions/mutations
    file_counts = {}
    for path, name in cursor.fetchall():
        name_lower = name.lower()
        if 'action' in name_lower or 'mutation' in name_lower:
            if path not in file_counts:
                file_counts[path] = {'actions': 0, 'mutations': 0}
            if 'action' in name_lower:
                file_counts[path]['actions'] += 1
            if 'mutation' in name_lower:
                file_counts[path]['mutations'] += 1

    for file, counts in file_counts.items():
        actions = counts['actions']
        mutations = counts['mutations']
        if actions > 30 or mutations > 30:
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


def _find_unhandled_action_errors(cursor, store_files: set[str]) -> list[StandardFinding]:
    """Find actions without error handling."""
    findings = []

    file_placeholders = ','.join('?' * len(store_files))

    # Find async actions without try-catch
    cursor.execute(f"""
        SELECT f1.file, f1.line, f1.callee_function
        FROM function_call_args f1
        WHERE f1.file IN ({file_placeholders})
          AND f1.callee_function IN ('fetch', 'axios', 'post', 'get', 'put', 'delete')
        ORDER BY f1.file, f1.line
    """, list(store_files))

    # Filter in Python for action files without error handling
    for file, line, api_call in cursor.fetchall():
        # Check if in action file
        file_lower = file.lower()
        if 'action' not in file_lower and 'actions.' not in file_lower:
            continue

        # Check for error handling nearby
        cursor.execute("""
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 10
              AND callee_function IN ('catch', 'try', 'finally')
        """, (file, line))

        if cursor.fetchone():
            continue
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


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_vue_state_issues(context)