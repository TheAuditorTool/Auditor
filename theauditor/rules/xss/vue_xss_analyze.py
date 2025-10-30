"""Vue.js-specific XSS Detection.

This module detects XSS vulnerabilities specific to Vue.js applications.
Uses Vue-specific database tables for accurate detection.
"""

import sqlite3
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
# If tables are missing, the rule MUST crash to expose indexer bugs.

# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="vue_xss",
    category="xss",
    target_extensions=['.vue', '.js', '.ts'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.spec.js'],
    requires_jsx_pass=False
)


# Vue dangerous directives
VUE_DANGEROUS_DIRECTIVES = frozenset([
    'v-html',  # Raw HTML rendering
    'v-once',  # Combined with v-html can be dangerous
    'v-pre'    # Skips compilation - can expose templates
])

# Vue safe directives (auto-escaped)
VUE_SAFE_DIRECTIVES = frozenset([
    'v-text',  # Safe text binding
    'v-model',  # Two-way binding (escaped)
    'v-show', 'v-if', 'v-else', 'v-else-if',  # Conditionals
    'v-for',  # Iteration
    'v-bind', ':',  # Attribute binding (mostly safe)
    'v-on', '@'  # Event binding
])

# User input sources in Vue
VUE_INPUT_SOURCES = frozenset([
    '$route.params', '$route.query', '$route.hash',
    'props.', 'this.props',
    'data.', 'this.data',
    '$attrs', '$listeners',
    'localStorage.getItem', 'sessionStorage.getItem',
    'document.cookie', 'window.location',
    '$refs.', 'event.target.value'
])

# Vue template compilation methods
VUE_COMPILE_METHODS = frozenset([
    'Vue.compile', '$compile',
    'compileToFunctions', 'parseComponent'
])


def find_vue_xss(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Vue.js-specific XSS vulnerabilities.

    Returns:
        List of Vue-specific XSS findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Only run if Vue is detected
        if not _is_vue_app(conn):
            return findings

        findings.extend(_check_vhtml_directive(conn))
        findings.extend(_check_template_compilation(conn))
        findings.extend(_check_render_functions(conn))
        findings.extend(_check_component_props_injection(conn))
        findings.extend(_check_slot_injection(conn))
        findings.extend(_check_filter_injection(conn))
        findings.extend(_check_computed_xss(conn))

    finally:
        conn.close()

    return findings


def _is_vue_app(conn) -> bool:
    """Check if this is a Vue.js application."""
    cursor = conn.cursor()

    # Check frameworks table
    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name IN ('vue', 'vuejs', 'vue.js', 'Vue')
          AND language = 'javascript'
    """)

    if cursor.fetchone()[0] > 0:
        return True

    # Check vue_components table
    cursor.execute("""
        SELECT COUNT(*) FROM vue_components
        LIMIT 1
    """)

    if cursor.fetchone()[0] > 0:
        return True

    # Fallback: Check for Vue patterns
    vue_patterns = ['Vue.', 'createApp', 'defineComponent', 'reactive', 'computed']

    cursor.execute("""
        SELECT name FROM symbols
        WHERE name IS NOT NULL
        LIMIT 1000
    """)

    # Filter in Python: Check for Vue-like symbol names
    for (name,) in cursor.fetchall():
        if any(pattern in name for pattern in vue_patterns):
            return True

    return False


def _check_vhtml_directive(conn) -> List[StandardFinding]:
    """Check v-html directives with user input."""
    findings = []
    cursor = conn.cursor()

    # Use Vue directives table directly
    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, component in cursor.fetchall():
        # Check if expression contains user input
        has_user_input = any(src in (expression or '') for src in VUE_INPUT_SOURCES)
        has_sanitizer = 'DOMPurify' in (expression or '') or 'sanitize' in (expression or '')

        if has_user_input and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='vue-xss-vhtml',
                message=f'XSS: v-html in {component} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'v-html="{expression[:60]}"' if len(expression or '') > 60 else f'v-html="{expression}"',
                cwe_id='CWE-79'
            ))

        # Check for complex expressions that might hide user input
        if '(' in (expression or '') or '?' in (expression or ''):  # Method calls or ternary
            findings.append(StandardFinding(
                rule_name='vue-xss-vhtml-complex',
                message='XSS: v-html with complex expression (verify for user input)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=f'v-html with complex expression',
                cwe_id='CWE-79'
            ))

    # Check for v-html combined with v-once (caching issues)
    cursor.execute("""
        SELECT vd1.file, vd1.line, vd1.in_component
        FROM vue_directives vd1
        JOIN vue_directives vd2 ON vd1.file = vd2.file
            AND vd1.in_component = vd2.in_component
            AND ABS(vd1.line - vd2.line) <= 2
        WHERE vd1.directive_name = 'v-html'
          AND vd2.directive_name = 'v-once'
        ORDER BY vd1.file, vd1.line
    """)

    for file, line, component in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='vue-xss-vhtml-vonce',
            message='XSS: v-html with v-once can cache malicious content',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='xss',
            snippet='v-html combined with v-once',
            cwe_id='CWE-79'
        ))

    return findings


def _check_template_compilation(conn) -> List[StandardFinding]:
    """Check for dynamic template compilation with user input."""
    findings = []
    cursor = conn.cursor()

    # Check for Vue.compile() or similar with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, callee, template_arg in cursor.fetchall():
        # Filter in Python: Check if callee matches any compile method
        is_compile_method = any(method in callee for method in VUE_COMPILE_METHODS)
        if not is_compile_method:
            continue

        has_user_input = any(src in (template_arg or '') for src in VUE_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='vue-template-injection',
                message=f'Template Injection: {callee} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                snippet=f'{callee}(userTemplate)',
                cwe_id='CWE-94'
            ))

    # Check for inline templates with user input
    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name
        FROM vue_components vc
        WHERE vc.has_template = 1
    """)

    for file, line, comp_name in cursor.fetchall():
        # Check if template contains user input interpolation
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 50
              AND a.source_expr IS NOT NULL
        """, [file, line, line])

        for (template_source,) in cursor.fetchall():
            # Filter in Python: Check for template with interpolation
            has_template = 'template:' in template_source
            has_interpolation = '${' in template_source or '`' in template_source

            if not (has_template and has_interpolation):
                continue

            has_user_input = any(src in template_source for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='vue-dynamic-template',
                    message=f'XSS: Component {comp_name} has dynamic template with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet='template: `<div>${userInput}</div>`',
                    cwe_id='CWE-79'
                ))

    return findings


def _check_render_functions(conn) -> List[StandardFinding]:
    """Check render functions for XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check Vue components with render functions
    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name, vc.setup_return
        FROM vue_components vc
        WHERE vc.type = 'render-function'
           OR vc.setup_return IS NOT NULL
    """)

    for file, line, comp_name, setup_return in cursor.fetchall():
        # Filter in Python: Check if setup_return contains render function patterns
        if setup_return:
            has_render_pattern = 'h(' in setup_return or 'createVNode' in setup_return
            if not has_render_pattern:
                continue

        # Check for innerHTML or dangerous props in render function
        dangerous_props = ['innerHTML', 'domProps', 'v-html']

        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 100
              AND a.source_expr IS NOT NULL
        """, [file, line, line])

        for (source,) in cursor.fetchall():
            # Filter in Python: Check for dangerous props
            has_dangerous_prop = any(prop in source for prop in dangerous_props)
            if not has_dangerous_prop:
                continue

            has_user_input = any(src in source for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='vue-render-function-xss',
                    message=f'XSS: Render function in {comp_name} uses innerHTML with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet='h("div", { domProps: { innerHTML: userInput } })',
                    cwe_id='CWE-79'
                ))

    # Check for JSX in Vue (if used)
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('h', 'createVNode', 'createElementVNode')
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, args in cursor.fetchall():
        # Filter in Python: Check for innerHTML
        if 'innerHTML' not in (args or ''):
            continue

        has_user_input = any(src in (args or '') for src in VUE_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='vue-vnode-innerhtml',
                message='XSS: VNode created with innerHTML from user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet='h("div", { innerHTML: userContent })',
                cwe_id='CWE-79'
            ))

    return findings


def _check_component_props_injection(conn) -> List[StandardFinding]:
    """Check for XSS through component props."""
    findings = []
    cursor = conn.cursor()

    # Check Vue components with dangerous props
    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name, vc.props_definition
        FROM vue_components vc
        WHERE vc.props_definition IS NOT NULL
    """)

    for file, line, comp_name, props_def in cursor.fetchall():
        # Check if props are used with v-html
        cursor.execute("""
            SELECT vd.line, vd.expression
            FROM vue_directives vd
            WHERE vd.file = ?
              AND vd.in_component = ?
              AND vd.directive_name = 'v-html'
              AND vd.expression IS NOT NULL
        """, [file, comp_name])

        for dir_line, expression in cursor.fetchall():
            # Filter in Python: Check for props usage
            if 'props.' not in expression:
                continue

            findings.append(StandardFinding(
                rule_name='vue-props-vhtml',
                message=f'XSS: Component {comp_name} uses props directly in v-html',
                file_path=file,
                line=dir_line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'v-html="props.content"',
                cwe_id='CWE-79'
            ))

    # Check for $attrs usage with v-html
    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
          AND vd.expression IS NOT NULL
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, component in cursor.fetchall():
        # Filter in Python: Check for $attrs usage
        if '$attrs' not in expression:
            continue

        findings.append(StandardFinding(
            rule_name='vue-attrs-vhtml',
            message='XSS: $attrs used in v-html (uncontrolled input)',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet='v-html="$attrs.content"',
            cwe_id='CWE-79'
        ))

    return findings


def _check_slot_injection(conn) -> List[StandardFinding]:
    """Check for XSS through slot content."""
    findings = []
    cursor = conn.cursor()

    # Check for slot content used with v-html
    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
          AND vd.expression IS NOT NULL
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, component in cursor.fetchall():
        # Filter in Python: Check for slot usage
        has_slot = '$slots' in expression or 'slot.' in expression
        if not has_slot:
            continue

        findings.append(StandardFinding(
            rule_name='vue-slot-vhtml',
            message='XSS: Slot content used in v-html',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet='v-html="$slots.default"',
            cwe_id='CWE-79'
        ))

    # Check for scoped slots with dangerous content
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check for scopedSlots with innerHTML
        has_scoped_slots = 'scopedSlots' in source
        has_innerHTML = 'innerHTML' in source

        if not (has_scoped_slots and has_innerHTML):
            continue

        findings.append(StandardFinding(
            rule_name='vue-scoped-slot-xss',
            message='XSS: Scoped slot with innerHTML manipulation',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='xss',
            snippet='scopedSlots with innerHTML',
            cwe_id='CWE-79'
        ))

    return findings


def _check_filter_injection(conn) -> List[StandardFinding]:
    """Check for XSS through Vue filters (Vue 2)."""
    findings = []
    cursor = conn.cursor()

    # Check for custom filters that don't escape HTML
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, filter_def in cursor.fetchall():
        # Filter in Python: Check if function is a Vue filter registration
        is_filter_registration = func.startswith('Vue.filter') or '.filter' in func
        if not is_filter_registration:
            continue

        # Check if filter returns raw HTML
        if 'innerHTML' in (filter_def or '') or '<' in (filter_def or ''):
            findings.append(StandardFinding(
                rule_name='vue-filter-xss',
                message='XSS: Vue filter may return unescaped HTML',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet='Vue.filter returns HTML string',
                cwe_id='CWE-79'
            ))

    return findings


def _check_computed_xss(conn) -> List[StandardFinding]:
    """Check computed properties that might cause XSS."""
    findings = []
    cursor = conn.cursor()

    # Check Vue hooks for computed properties with dangerous patterns
    cursor.execute("""
        SELECT vh.file, vh.line, vh.component_name, vh.hook_name, vh.return_value
        FROM vue_hooks vh
        WHERE vh.hook_type = 'computed'
          AND vh.return_value IS NOT NULL
        ORDER BY vh.file, vh.line
    """)

    for file, line, comp_name, hook_name, return_val in cursor.fetchall():
        # Check if computed property builds HTML
        if any(tag in (return_val or '') for tag in ['<div', '<span', '<script', '<img']):
            has_user_input = any(src in return_val for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='vue-computed-html',
                    message=f'XSS: Computed property {hook_name} builds HTML with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet=f'computed: {{ {hook_name}() {{ return `<div>${{user}}</div>` }} }}',
                    cwe_id='CWE-79'
                ))

    # Check for watchers that manipulate innerHTML
    cursor.execute("""
        SELECT vh.file, vh.line, vh.component_name, vh.hook_name
        FROM vue_hooks vh
        WHERE vh.hook_type = 'watcher'
        ORDER BY vh.file, vh.line
    """)

    for file, line, comp_name, watched_prop in cursor.fetchall():
        # Check if watcher manipulates DOM
        cursor.execute("""
            SELECT a.target_var
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 20
              AND a.target_var IS NOT NULL
        """, [file, line, line])

        # Filter in Python: Check for innerHTML manipulation
        has_innerHTML = False
        for (target_var,) in cursor.fetchall():
            if '.innerHTML' in target_var:
                has_innerHTML = True
                break

        if has_innerHTML:
            findings.append(StandardFinding(
                rule_name='vue-watcher-innerhtml',
                message=f'XSS: Watcher for {watched_prop} manipulates innerHTML',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=f'watch: {{ {watched_prop}() {{ el.innerHTML = ... }} }}',
                cwe_id='CWE-79'
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
    return find_vue_xss(context)