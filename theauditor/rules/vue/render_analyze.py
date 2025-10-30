"""Vue Render Analyzer - Database-First Approach.

Detects Vue rendering anti-patterns and performance issues using
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
    name="vue_render",
    category="vue",
    target_extensions=['.vue', '.js', '.ts', '.jsx', '.tsx'],
    target_file_patterns=['frontend/', 'client/', 'src/components/', 'src/views/'],
    exclude_patterns=['backend/', 'server/', 'api/', 'migrations/', '__tests__/', '*.test.*', '*.spec.*'],
    requires_jsx_pass=False  # Render patterns use standard tables
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Render functions and methods
RENDER_FUNCTIONS = frozenset([
    'render', 'h', 'createVNode', 'createElementVNode',
    'createTextVNode', 'createCommentVNode', 'createStaticVNode',
    'resolveComponent', 'resolveDynamicComponent', 'resolveDirective',
    'withDirectives', 'renderSlot', 'renderList'
])

# Template compiler hints
COMPILER_HINTS = frozenset([
    'v-once', 'v-memo', 'v-pre', 'key', ':key',
    'v-show', 'v-if', 'v-else', 'v-else-if'
])

# Performance-critical directives
PERF_DIRECTIVES = frozenset([
    'v-for', 'v-if', 'v-show', 'v-model',
    'v-memo', 'v-once', 'v-slot'
])

# Functions that trigger re-renders
RERENDER_TRIGGERS = frozenset([
    '$forceUpdate', 'forceUpdate', '$set', '$delete',
    'Vue.set', 'Vue.delete', 'nextTick', '$nextTick'
])

# Virtual DOM optimization patterns
VDOM_OPTIMIZATIONS = frozenset([
    'shallowRef', 'shallowReactive', 'markRaw', 'toRaw',
    'v-once', 'v-memo', 'key', 'track-by'
])

# Expensive DOM operations
EXPENSIVE_DOM_OPS = frozenset([
    'innerHTML', 'outerHTML', 'insertAdjacentHTML',
    'document.write', 'document.writeln',
    'appendChild', 'removeChild', 'replaceChild',
    'cloneNode', 'importNode'
])

# Event handler patterns
EVENT_HANDLERS = frozenset([
    '@click', '@input', '@change', '@submit',
    '@keyup', '@keydown', '@mouseenter', '@mouseleave',
    'v-on:', 'addEventListener'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_vue_render_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue rendering anti-patterns and performance issues.

    Detects:
    - v-if with v-for (performance anti-pattern)
    - Missing keys in lists
    - Unnecessary re-renders
    - Large lists without virtualization
    - Complex computed chains
    - Direct DOM manipulation
    - Inefficient event handlers

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Vue render issues found
    """
    findings = []

    if not context.db_path:
        return findings

    # NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
    # If tables are missing, the rule MUST crash to expose indexer bugs.

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Get Vue files (schema contract guarantees tables exist)
        vue_files = _get_vue_files(cursor)
        if not vue_files:
            return findings

        # Run all checks - schema contract guarantees all tables exist
        findings.extend(_find_vif_with_vfor(cursor, vue_files))
        findings.extend(_find_missing_list_keys(cursor, vue_files))
        findings.extend(_find_unnecessary_rerenders(cursor, vue_files))
        findings.extend(_find_unoptimized_lists(cursor, vue_files))
        findings.extend(_find_complex_render_functions(cursor, vue_files))
        findings.extend(_find_direct_dom_manipulation(cursor, vue_files))
        findings.extend(_find_inefficient_event_handlers(cursor, vue_files))
        findings.extend(_find_missing_optimizations(cursor, vue_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_vue_files(cursor) -> Set[str]:
    """Get all Vue-related files from the database.

    Schema contract (v1.1+) guarantees all tables exist.
    If table is missing, we WANT the rule to crash to expose indexer bugs.
    """
    vue_files = set()

    # Check files table by extension
    cursor.execute("""
        SELECT DISTINCT path, ext
        FROM files
        WHERE ext IN ('.vue', '.js', '.ts')
    """)

    # Filter in Python for Vue files
    for path, ext in cursor.fetchall():
        path_lower = path.lower()
        if ext == '.vue' or (ext in ('.js', '.ts') and 'vue' in path_lower):
            vue_files.add(path)

    # Also check for Vue patterns in symbols
    cursor.execute("""
        SELECT DISTINCT path, name
        FROM symbols
        WHERE name IS NOT NULL
    """)

    # Filter in Python for Vue patterns
    for path, name in cursor.fetchall():
        if any(pattern in name for pattern in ['Vue', 'v-for', 'v-if', 'template']):
            vue_files.add(path)

    return vue_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_vif_with_vfor(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find v-if used with v-for (performance anti-pattern)."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Look for v-if and v-for on same element or line
    cursor.execute(f"""
        SELECT s1.path, s1.line, s1.name
        FROM symbols s1
        WHERE s1.path IN ({file_placeholders})
          AND s1.name IS NOT NULL
        ORDER BY s1.path, s1.line
    """, list(vue_files))

    # Filter in Python for v-for with adjacent v-if
    all_symbols = cursor.fetchall()
    vfor_with_vif = []

    for file, line, name in all_symbols:
        if 'v-for' not in name:
            continue

        # Check for v-if within 1 line
        has_vif = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and abs(line2 - line) <= 1 and 'v-if' in name2:
                has_vif = True
                break

        if has_vif:
            vfor_with_vif.append((file, line))

    for file, line in vfor_with_vif:
        findings.append(StandardFinding(
            rule_name='vue-vif-with-vfor',
            message='v-if with v-for on same element - use computed property instead',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-performance',
            confidence=Confidence.HIGH,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_missing_list_keys(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find v-for without proper keys."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find v-for without :key
    cursor.execute(f"""
        SELECT path, line, name
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND name IS NOT NULL
        ORDER BY path, line
    """, list(vue_files))

    # Store all symbols
    all_symbols = cursor.fetchall()

    # Filter in Python for v-for without keys
    for file, line, name in all_symbols:
        if 'v-for' not in name:
            continue

        # Check for adjacent :key within 2 lines
        has_key = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and abs(line2 - line) <= 2:
                if ':key' in name2 or 'v-bind:key' in name2 or 'key=' in name2:
                    has_key = True
                    break

        if not has_key:
            findings.append(StandardFinding(
                rule_name='vue-missing-key',
                message='v-for without unique :key - causes rendering issues',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='vue-performance',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-1050'
            ))

    # Check for index as key
    for file, line, name in all_symbols:
        # Filter in Python for index key patterns
        if ':key="index"' in name or ':key="i"' in name or ':key="idx"' in name:
            findings.append(StandardFinding(
                rule_name='vue-index-as-key',
                message='Using array index as :key - causes issues when list changes',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='vue-performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1050'
            ))

    return findings


def _find_unnecessary_rerenders(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find unnecessary re-render triggers."""
    findings = []

    triggers = list(RERENDER_TRIGGERS)
    trigger_placeholders = ','.join('?' * len(triggers))
    file_placeholders = ','.join('?' * len(vue_files))

    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({trigger_placeholders})
        ORDER BY file, line
    """, list(vue_files) + triggers)

    for file, line, func, args in cursor.fetchall():
        if func in ['$forceUpdate', 'forceUpdate']:
            severity = Severity.HIGH
            message = 'Using $forceUpdate indicates reactivity system failure'
        else:
            severity = Severity.MEDIUM
            message = f'Manual reactivity trigger {func} - review necessity'

        findings.append(StandardFinding(
            rule_name='vue-force-update',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='vue-performance',
            confidence=Confidence.HIGH,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_unoptimized_lists(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find large lists without virtualization."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find v-for with large datasets
    cursor.execute(f"""
        SELECT s1.path, s1.line, s1.name
        FROM symbols s1
        WHERE s1.path IN ({file_placeholders})
          AND s1.name IS NOT NULL
        ORDER BY s1.path, s1.line
    """, list(vue_files))

    # Store all symbols
    all_symbols = cursor.fetchall()

    # Filter in Python for v-for with large datasets
    for file, line, name in all_symbols:
        if 'v-for' not in name:
            continue

        # Check for large list patterns
        if any(pattern in name for pattern in ['1000', '10000', '.length > 100', '.length > 500']):
            findings.append(StandardFinding(
                rule_name='vue-large-list',
                message='Large list without virtual scrolling - performance impact',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='vue-performance',
                confidence=Confidence.LOW,
                cwe_id='CWE-1050'
            ))

    # Check for nested v-for
    for file, line, name in all_symbols:
        if 'v-for' not in name:
            continue

        # Check for nested v-for within 10 lines
        has_nested = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and line2 > line and line2 < line + 10 and 'v-for' in name2:
                has_nested = True
                break

        if not has_nested:
            continue
        findings.append(StandardFinding(
            rule_name='vue-nested-vfor',
            message='Nested v-for loops - O(n²) complexity',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_complex_render_functions(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find overly complex render functions."""
    findings = []

    render_funcs = list(RENDER_FUNCTIONS)
    func_placeholders = ','.join('?' * len(render_funcs))
    file_placeholders = ','.join('?' * len(vue_files))

    # Count render function calls
    cursor.execute(f"""
        SELECT file, caller_function, COUNT(*) as call_count
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({func_placeholders})
          AND caller_function IS NOT NULL
        GROUP BY file, caller_function
        HAVING call_count > 10
    """, list(vue_files) + render_funcs)

    for file, function, count in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-complex-render',
            message=f'Render function with {count} VNode calls - consider template',
            file_path=file,
            line=1,
            severity=Severity.MEDIUM,
            category='vue-maintainability',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1061'
        ))

    return findings


def _find_direct_dom_manipulation(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find direct DOM manipulation (anti-pattern in Vue)."""
    findings = []

    dom_ops = list(EXPENSIVE_DOM_OPS)
    ops_placeholders = ','.join('?' * len(dom_ops))
    file_placeholders = ','.join('?' * len(vue_files))

    cursor.execute(f"""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IS NOT NULL
        ORDER BY file, line
    """, list(vue_files))

    # Filter in Python for DOM operations
    for file, line, operation in cursor.fetchall():
        # Check if it's in expensive DOM ops or starts with document./window.
        if operation not in dom_ops and not operation.startswith('document.') and not operation.startswith('window.'):
            continue
        if operation in ['innerHTML', 'document.write']:
            severity = Severity.HIGH
            message = f'Direct DOM manipulation with {operation} - security risk'
        else:
            severity = Severity.MEDIUM
            message = f'Direct DOM manipulation {operation} - use Vue reactivity'

        findings.append(StandardFinding(
            rule_name='vue-direct-dom',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='vue-antipattern',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-79' if 'innerHTML' in operation else 'CWE-1061'
        ))

    return findings


def _find_inefficient_event_handlers(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find inefficient event handler patterns."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find inline arrow functions in templates
    cursor.execute(f"""
        SELECT file, line, source_expr
        FROM assignments
        WHERE file IN ({file_placeholders})
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """, list(vue_files))

    # Filter in Python for inline event handlers
    for file, line, handler in cursor.fetchall():
        if any(pattern in handler for pattern in ['@click="() =>', '@input="() =>', '@change="() =>', 'v-on:']):
            findings.append(StandardFinding(
                rule_name='vue-inline-handler',
                message='Inline arrow function in template - recreated on each render',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='vue-performance',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-1050'
            ))

    # Find event handlers without modifiers
    cursor.execute(f"""
        SELECT path, line, name
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND name IS NOT NULL
        ORDER BY path, line
    """, list(vue_files))

    # Filter in Python for @submit without .prevent
    for file, line, name in cursor.fetchall():
        if '@submit' in name and '.prevent' not in name:
            findings.append(StandardFinding(
                rule_name='vue-missing-prevent',
                message='Form submit without .prevent modifier',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='vue-bestpractice',
                confidence=Confidence.HIGH,
                cwe_id='CWE-1061'
            ))

    return findings


def _find_missing_optimizations(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find missing render optimizations."""
    findings = []

    file_placeholders = ','.join('?' * len(vue_files))

    # Find static content without v-once
    cursor.execute(f"""
        SELECT path, line, name
        FROM symbols
        WHERE path IN ({file_placeholders})
          AND type = 'template'
          AND LENGTH(name) > 200
          AND name IS NOT NULL
        ORDER BY path, line
        LIMIT 10
    """, list(vue_files))

    # Filter in Python for static content
    for file, line, name in cursor.fetchall():
        if '{{' not in name and 'v-once' not in name and 'v-pre' not in name:
            findings.append(StandardFinding(
                rule_name='vue-static-content',
                message='Large static content without v-once directive',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='vue-performance',
                confidence=Confidence.LOW,
                cwe_id='CWE-1050'
            ))

    # Find computed without caching
    cursor.execute(f"""
        SELECT s.path, s.line, s.name
        FROM symbols s
        WHERE s.path IN ({file_placeholders})
          AND s.name IS NOT NULL
        ORDER BY s.path, s.line
    """, list(vue_files))

    # Filter in Python for computed properties
    computed_symbols = [(file, line, name) for file, line, name in cursor.fetchall() if 'computed' in name]

    for file, line, name in computed_symbols:
        # Check for non-deterministic functions nearby
        cursor.execute("""
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 5
              AND callee_function IN ('Math.random', 'Date.now', 'performance.now')
        """, (file, line))

        if cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='vue-computed-side-effects',
                message='Computed property with non-deterministic value',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='vue-antipattern',
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-1061'
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
    return find_vue_render_issues(context)