"""Vue Component Analyzer - Database-First Approach.

Detects Vue-specific component anti-patterns and performance issues using
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

# Vue directives that modify DOM
VUE_DIRECTIVES = frozenset([
    'v-if', 'v-else', 'v-else-if', 'v-for', 'v-show',
    'v-model', 'v-text', 'v-html', 'v-pre', 'v-cloak', 'v-once'
])

# Props that shouldn't be mutated
IMMUTABLE_PROPS = frozenset([
    'props.', 'this.props.', 'this.$props.',
    'prop.', 'parentProp.', 'inheritedProp.'
])

# Vue lifecycle hooks
LIFECYCLE_HOOKS = frozenset([
    'beforeCreate', 'created', 'beforeMount', 'mounted',
    'beforeUpdate', 'updated', 'beforeDestroy', 'destroyed',
    'beforeUnmount', 'unmounted', 'activated', 'deactivated',
    'errorCaptured', 'renderTracked', 'renderTriggered'
])

# Composition API hooks
COMPOSITION_HOOKS = frozenset([
    'onBeforeMount', 'onMounted', 'onBeforeUpdate', 'onUpdated',
    'onBeforeUnmount', 'onUnmounted', 'onActivated', 'onDeactivated',
    'onErrorCaptured', 'onRenderTracked', 'onRenderTriggered'
])

# Vue methods that cause re-renders
RENDER_TRIGGERS = frozenset([
    '$forceUpdate', 'forceUpdate', '$set', '$delete',
    'Vue.set', 'Vue.delete', 'this.$nextTick'
])

# Expensive operations in templates
EXPENSIVE_TEMPLATE_OPS = frozenset([
    'JSON.stringify', 'JSON.parse', 'Object.keys', 'Object.values',
    'Array.from', '.filter', '.map', '.reduce', '.sort'
])

# Component registration patterns
COMPONENT_REGISTRATION = frozenset([
    'components:', 'component(', 'Vue.component', 'app.component',
    'globalProperties', 'mixins:', 'extends:'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_vue_component_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue component anti-patterns and performance issues.

    Detects:
    - Props mutation anti-pattern
    - Missing keys in v-for loops
    - Excessive component complexity
    - Unnecessary re-renders
    - Missing component names
    - Inefficient computed properties
    - Template expression complexity

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Vue component issues found
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
                'function_call_args', 'api_endpoints', 'cfg_blocks'
            )
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Minimum required tables
        if 'files' not in existing_tables:
            return findings

        # Get Vue files
        vue_files = _get_vue_files(cursor, existing_tables)
        if not vue_files:
            return findings

        # Track available tables for graceful degradation
        has_symbols = 'symbols' in existing_tables
        has_assignments = 'assignments' in existing_tables
        has_function_calls = 'function_call_args' in existing_tables
        has_cfg_blocks = 'cfg_blocks' in existing_tables

        # ========================================================
        # CHECK 1: Props Mutation
        # ========================================================
        if has_assignments:
            findings.extend(_find_props_mutations(cursor, vue_files))

        # ========================================================
        # CHECK 2: Missing Keys in v-for
        # ========================================================
        if has_symbols:
            findings.extend(_find_missing_vfor_keys(cursor, vue_files))

        # ========================================================
        # CHECK 3: Excessive Component Complexity
        # ========================================================
        if has_symbols and has_function_calls:
            findings.extend(_find_complex_components(cursor, vue_files))

        # ========================================================
        # CHECK 4: Unnecessary Re-renders
        # ========================================================
        if has_function_calls:
            findings.extend(_find_unnecessary_rerenders(cursor, vue_files))

        # ========================================================
        # CHECK 5: Missing Component Names
        # ========================================================
        if has_symbols:
            findings.extend(_find_missing_component_names(cursor, vue_files))

        # ========================================================
        # CHECK 6: Inefficient Computed Properties
        # ========================================================
        if has_symbols and has_function_calls:
            findings.extend(_find_inefficient_computed(cursor, vue_files))

        # ========================================================
        # CHECK 7: Template Expression Complexity
        # ========================================================
        if has_symbols:
            findings.extend(_find_complex_template_expressions(cursor, vue_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_vue_files(cursor, existing_tables: Set[str]) -> Set[str]:
    """Get all Vue-related files from the database."""
    vue_files = set()

    # First check the vue_components table if it exists
    if 'vue_components' in existing_tables:
        cursor.execute("""
            SELECT DISTINCT file
            FROM vue_components
        """)
        vue_files.update(row[0] for row in cursor.fetchall())

    # Fallback to file extension check if no Vue components found
    if not vue_files and 'files' in existing_tables:
        cursor.execute("""
            SELECT DISTINCT file_path
            FROM files
            WHERE file_path LIKE '%.vue'
        """)
        vue_files.update(row[0] for row in cursor.fetchall())

    # Also check JavaScript files that import Vue (if still no Vue files found)
    if not vue_files and 'symbols' in existing_tables:
        cursor.execute("""
            SELECT DISTINCT path
            FROM symbols
            WHERE name LIKE '%Vue%'
               OR name LIKE '%defineComponent%'
               OR name LIKE '%createApp%'
        """)
        vue_files.update(row[0] for row in cursor.fetchall())

    return vue_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_props_mutations(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find direct props mutations (anti-pattern in Vue)."""
    findings = []

    props_patterns = list(IMMUTABLE_PROPS)
    placeholders = ','.join('?' * len(vue_files))

    # Find assignments to props
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({placeholders})
          AND (
              target_var LIKE 'props.%'
              OR target_var LIKE 'this.props.%'
              OR target_var LIKE 'this.$props.%'
              OR target_var LIKE '%.props.%'
          )
        ORDER BY file, line
    """, list(vue_files))

    for file, line, target, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-props-mutation',
            message=f'Direct mutation of prop "{target}" - props should be immutable',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-antipattern',
            confidence=Confidence.HIGH,
            cwe_id='CWE-471'
        ))

    return findings


def _find_missing_vfor_keys(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find v-for loops without :key attribute."""
    findings = []

    # First try the vue_directives table if it exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vue_directives'")
    if cursor.fetchone():
        placeholders = ','.join('?' * len(vue_files))

        cursor.execute(f"""
            SELECT file, line, expression
            FROM vue_directives
            WHERE file IN ({placeholders})
              AND directive_name = 'v-for'
              AND has_key = 0
            ORDER BY file, line
        """, list(vue_files))

        for file, line, expression in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-missing-vfor-key',
                message=f'v-for directive without :key attribute: "{expression}"',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='vue-performance',
                confidence=Confidence.HIGH,
                cwe_id='CWE-704'
            ))

        return findings

    # Fallback to pattern search in symbols table
    placeholders = ','.join('?' * len(vue_files))

    # Look for v-for patterns without adjacent key
    cursor.execute(f"""
        SELECT s1.path, s1.line, s1.name
        FROM symbols s1
        WHERE s1.path IN ({placeholders})
          AND s1.name LIKE '%v-for%'
          AND NOT EXISTS (
              SELECT 1 FROM symbols s2
              WHERE s2.path = s1.path
                AND ABS(s2.line - s1.line) <= 2
                AND (s2.name LIKE '%:key%' OR s2.name LIKE '%v-bind:key%')
          )
        ORDER BY s1.path, s1.line
    """, list(vue_files))

    for file, line, directive in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-missing-key',
            message='v-for without :key - causes rendering issues',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='vue-performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_complex_components(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find components with excessive complexity."""
    findings = []

    placeholders = ','.join('?' * len(vue_files))

    # Count methods per component
    cursor.execute(f"""
        SELECT file, COUNT(DISTINCT name) as method_count
        FROM symbols
        WHERE file IN ({placeholders})
          AND type = 'function'
          AND name NOT LIKE 'on%'
          AND name NOT LIKE 'handle%'
        GROUP BY file
        HAVING method_count > 15
    """, list(vue_files))

    for file, method_count in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-complex-component',
            message=f'Component has {method_count} methods - consider splitting',
            file_path=file,
            line=1,
            severity=Severity.MEDIUM,
            category='vue-maintainability',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1061'
        ))

    # Count data properties
    cursor.execute(f"""
        SELECT file, COUNT(*) as data_count
        FROM symbols
        WHERE file IN ({placeholders})
          AND type IN ('property', 'variable')
          AND (name LIKE 'data.%' OR name LIKE 'state.%')
        GROUP BY file
        HAVING data_count > 20
    """, list(vue_files))

    for file, data_count in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-excessive-data',
            message=f'Component has {data_count} data properties - consider composition',
            file_path=file,
            line=1,
            severity=Severity.LOW,
            category='vue-maintainability',
            confidence=Confidence.LOW,
            cwe_id='CWE-1061'
        ))

    return findings


def _find_unnecessary_rerenders(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find unnecessary re-render triggers."""
    findings = []

    render_triggers = list(RENDER_TRIGGERS)
    trigger_placeholders = ','.join('?' * len(render_triggers))
    file_placeholders = ','.join('?' * len(vue_files))

    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE file IN ({file_placeholders})
          AND callee_function IN ({trigger_placeholders})
        ORDER BY file, line
    """, list(vue_files) + render_triggers)

    for file, line, func, args in cursor.fetchall():
        if func == '$forceUpdate' or func == 'forceUpdate':
            severity = Severity.HIGH
            message = 'Using $forceUpdate - indicates reactivity issue'
        else:
            severity = Severity.MEDIUM
            message = f'Manual reactivity trigger {func} - review necessity'

        findings.append(StandardFinding(
            rule_name='vue-unnecessary-rerender',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='vue-performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_missing_component_names(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find components without explicit names (harder to debug)."""
    findings = []

    placeholders = ','.join('?' * len(vue_files))

    # Check for components without name property
    cursor.execute(f"""
        SELECT DISTINCT f.file_path
        FROM files f
        WHERE f.file_path IN ({placeholders})
          AND f.file_path LIKE '%.vue'
          AND NOT EXISTS (
              SELECT 1 FROM symbols s
              WHERE s.path = f.file_path
                AND (s.name = 'name' OR s.name LIKE 'name:' OR s.name LIKE '"name"')
          )
    """, list(vue_files))

    for file, in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-missing-name',
            message='Component missing explicit name - harder to debug',
            file_path=file,
            line=1,
            severity=Severity.LOW,
            category='vue-maintainability',
            confidence=Confidence.LOW,
            cwe_id='CWE-1061'
        ))

    return findings


def _find_inefficient_computed(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find inefficient computed properties."""
    findings = []

    expensive_ops = list(EXPENSIVE_TEMPLATE_OPS)
    ops_placeholders = ','.join('?' * len(expensive_ops))
    file_placeholders = ','.join('?' * len(vue_files))

    # Find computed properties with expensive operations
    cursor.execute(f"""
        SELECT f.file, f.line, f.callee_function, f.caller_function
        FROM function_call_args f
        WHERE f.file IN ({file_placeholders})
          AND f.callee_function IN ({ops_placeholders})
          AND (f.caller_function LIKE '%computed%'
               OR f.caller_function LIKE '%get %')
        ORDER BY f.file, f.line
    """, list(vue_files) + expensive_ops)

    for file, line, operation, computed_name in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-expensive-computed',
            message=f'Expensive operation {operation} in computed property',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vue-performance',
            confidence=Confidence.MEDIUM,
            cwe_id='CWE-1050'
        ))

    return findings


def _find_complex_template_expressions(cursor, vue_files: Set[str]) -> List[StandardFinding]:
    """Find overly complex expressions in templates."""
    findings = []

    placeholders = ','.join('?' * len(vue_files))

    # Find complex expressions (multiple operations in one line)
    cursor.execute(f"""
        SELECT path, line, name
        FROM symbols
        WHERE path IN ({placeholders})
          AND (
              (LENGTH(name) - LENGTH(REPLACE(name, '&&', ''))) / 2 > 2
              OR (LENGTH(name) - LENGTH(REPLACE(name, '||', ''))) / 2 > 2
              OR (LENGTH(name) - LENGTH(REPLACE(name, '?', ''))) > 2
          )
        ORDER BY path, line
    """, list(vue_files))

    for file, line, expression in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-complex-template',
            message='Complex logic in template - move to computed property',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='vue-maintainability',
            confidence=Confidence.LOW,
            cwe_id='CWE-1061'
        ))

    return findings