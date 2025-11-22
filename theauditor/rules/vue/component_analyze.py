"""Vue Component Analyzer - Database-First Approach.

Detects Vue-specific component anti-patterns and performance issues using
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
    name="vue_component",
    category="vue",
    target_extensions=['.vue', '.js', '.ts', '.jsx', '.tsx'],
    target_file_patterns=['frontend/', 'client/', 'src/components/', 'src/views/', 'src/pages/'],
    exclude_patterns=['backend/', 'server/', 'api/', 'migrations/', '__tests__/', '*.test.*', '*.spec.*'],
    requires_jsx_pass=False  # Uses standard tables, not JSX-preserved
)


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

def find_vue_component_issues(context: StandardRuleContext) -> list[StandardFinding]:
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
        findings.extend(_find_props_mutations(cursor, vue_files))
        findings.extend(_find_missing_vfor_keys(cursor, vue_files))
        findings.extend(_find_complex_components(cursor, vue_files))
        findings.extend(_find_unnecessary_rerenders(cursor, vue_files))
        findings.extend(_find_missing_component_names(cursor, vue_files))
        findings.extend(_find_inefficient_computed(cursor, vue_files))
        findings.extend(_find_complex_template_expressions(cursor, vue_files))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_vue_files(cursor) -> set[str]:
    """Get all Vue-related files from the database.

    Schema contract (v1.1+) guarantees all tables exist.
    If table is missing, we WANT the rule to crash to expose indexer bugs.

    Queries ALL relevant tables and combines results - no conditional logic.
    No early returns - trust the database schema.
    """
    vue_files = set()

    # Primary source: vue_components table (schema contract guarantees existence)
    cursor.execute("""
        SELECT DISTINCT file
        FROM vue_components
    """)
    vue_files.update(row[0] for row in cursor.fetchall())

    # Secondary source: Files with .vue extension
    cursor.execute("""
        SELECT DISTINCT path
        FROM files
        WHERE ext = '.vue'
    """)
    vue_files.update(row[0] for row in cursor.fetchall())

    # Tertiary source: JavaScript/TypeScript files that import Vue
    cursor.execute("""
        SELECT DISTINCT path
        FROM symbols
        WHERE name IS NOT NULL
    """)

    # Filter in Python for Vue patterns
    for (path,) in cursor.fetchall():
        # Get symbols for this file
        cursor.execute("SELECT name FROM symbols WHERE path = ?", (path,))
        for (name,) in cursor.fetchall():
            if name and any(pattern in name for pattern in ['Vue', 'defineComponent', 'createApp']):
                vue_files.add(path)
                break

    return vue_files


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def _find_props_mutations(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find direct props mutations (anti-pattern in Vue)."""
    findings = []

    props_patterns = list(IMMUTABLE_PROPS)
    placeholders = ','.join('?' * len(vue_files))

    # Find assignments to props
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE file IN ({placeholders})
          AND target_var IS NOT NULL
        ORDER BY file, line
    """, list(vue_files))

    # Filter in Python for props mutations
    props_mutations = []
    for file, line, target, source in cursor.fetchall():
        if any(pattern in target for pattern in IMMUTABLE_PROPS):
            props_mutations.append((file, line, target, source))

    for file, line, target, source in props_mutations:
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


def _find_missing_vfor_keys(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find v-for loops without :key attribute.

    Uses BOTH vue_directives (authoritative) and symbols (heuristic) to
    maximize detection coverage. No conditional logic - executes both strategies
    unconditionally and deduplicates findings.
    """
    findings = []
    found_locations = set()  # Deduplicate findings by (file, line)

    placeholders = ','.join('?' * len(vue_files))

    # Strategy 1: Query vue_directives table (HIGH confidence, authoritative)
    cursor.execute(f"""
        SELECT file, line, expression
        FROM vue_directives
        WHERE file IN ({placeholders})
          AND directive_name = 'v-for'
          AND has_key = 0
        ORDER BY file, line
    """, list(vue_files))

    for file, line, expression in cursor.fetchall():
        location = (file, line)
        if location not in found_locations:
            found_locations.add(location)
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

    # Strategy 2: Query symbols table (MEDIUM confidence, heuristic)
    # Look for v-for patterns without adjacent key
    cursor.execute(f"""
        SELECT s1.path, s1.line, s1.name
        FROM symbols s1
        WHERE s1.path IN ({placeholders})
          AND s1.name IS NOT NULL
        ORDER BY s1.path, s1.line
    """, list(vue_files))

    # Filter in Python for v-for without keys
    all_symbols = cursor.fetchall()
    for file, line, name in all_symbols:
        if 'v-for' not in name:
            continue

        # Check for adjacent :key symbols within 2 lines
        has_key = False
        for file2, line2, name2 in all_symbols:
            if file2 == file and abs(line2 - line) <= 2:
                if ':key' in name2 or 'v-bind:key' in name2:
                    has_key = True
                    break

        if not has_key:
            location = (file, line)
            if location not in found_locations:  # Deduplicate
                found_locations.add(location)
                findings.append(StandardFinding(
                    rule_name='vue-missing-vfor-key-heuristic',
                    message='v-for without :key detected via heuristic - verify manually',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='vue-performance',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-704'
                ))

    return findings


def _find_complex_components(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find components with excessive complexity."""
    findings = []

    placeholders = ','.join('?' * len(vue_files))

    # Count methods per component
    cursor.execute(f"""
        SELECT path AS file, name
        FROM symbols
        WHERE path IN ({placeholders})
          AND type = 'function'
          AND name IS NOT NULL
    """, list(vue_files))

    # Filter in Python for non-event-handler methods
    file_methods = {}
    for file, name in cursor.fetchall():
        if not name.startswith('on') and not name.startswith('handle'):
            if file not in file_methods:
                file_methods[file] = set()
            file_methods[file].add(name)

    for file, methods in file_methods.items():
        method_count = len(methods)
        if method_count > 15:
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
        SELECT path AS file, name
        FROM symbols
        WHERE path IN ({placeholders})
          AND type IN ('property', 'variable')
          AND name IS NOT NULL
    """, list(vue_files))

    # Filter in Python for data/state properties
    file_data = {}
    for file, name in cursor.fetchall():
        if name.startswith('data.') or name.startswith('state.'):
            if file not in file_data:
                file_data[file] = 0
            file_data[file] += 1

    for file, data_count in file_data.items():
        if data_count > 20:
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


def _find_unnecessary_rerenders(cursor, vue_files: set[str]) -> list[StandardFinding]:
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


def _find_missing_component_names(cursor, vue_files: set[str]) -> list[StandardFinding]:
    """Find components without explicit names (harder to debug)."""
    findings = []

    placeholders = ','.join('?' * len(vue_files))

    # Check for components without name property
    cursor.execute(f"""
        SELECT DISTINCT f.path
        FROM files f
        WHERE f.path IN ({placeholders})
          AND f.ext = '.vue'
    """, list(vue_files))

    # Filter in Python for components without name
    vue_component_files = [row[0] for row in cursor.fetchall()]

    for file in vue_component_files:
        # Check for name property in symbols
        cursor.execute("""
            SELECT name
            FROM symbols
            WHERE path = ?
              AND name IS NOT NULL
        """, (file,))

        has_name = False
        for (name,) in cursor.fetchall():
            if name == 'name' or name.startswith('name:') or name.startswith('"name"'):
                has_name = True
                break

        if not has_name:
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


def _find_inefficient_computed(cursor, vue_files: set[str]) -> list[StandardFinding]:
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
          AND f.caller_function IS NOT NULL
        ORDER BY f.file, f.line
    """, list(vue_files) + expensive_ops)

    # Filter in Python for computed properties
    expensive_computed = []
    for file, line, operation, computed_name in cursor.fetchall():
        if 'computed' in computed_name or 'get ' in computed_name:
            expensive_computed.append((file, line, operation, computed_name))

    for file, line, operation, computed_name in expensive_computed:
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


def _find_complex_template_expressions(cursor, vue_files: set[str]) -> list[StandardFinding]:
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


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_vue_component_issues(context)