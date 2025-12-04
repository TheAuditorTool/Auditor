"""Vue.js-specific XSS Detection."""

import sqlite3

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext
from theauditor.rules.xss.constants import (
    VUE_COMPILE_METHODS,
    VUE_INPUT_SOURCES,
    VUE_TARGET_EXTENSIONS,
    is_sanitized,
)

METADATA = RuleMetadata(
    name="vue_xss",
    category="xss",
    target_extensions=VUE_TARGET_EXTENSIONS,
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.spec.js"],
    execution_scope="database")


def find_vue_xss(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Vue.js-specific XSS vulnerabilities."""
    findings = []

    if not context.db_path:
        return findings

    with sqlite3.connect(context.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if not _is_vue_app(cursor):
            return findings

        findings.extend(_check_vhtml_directive(cursor))
        findings.extend(_check_template_compilation(cursor))
        findings.extend(_check_render_functions(cursor))
        findings.extend(_check_component_props_injection(cursor))
        findings.extend(_check_slot_injection(cursor))
        findings.extend(_check_filter_injection(cursor))
        findings.extend(_check_computed_xss(cursor))

    return findings


def _is_vue_app(cursor: sqlite3.Cursor) -> bool:
    """Check if this is a Vue.js application."""

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM frameworks
        WHERE name IN ('vue', 'vuejs', 'vue.js', 'Vue')
          AND language = 'javascript'
    """)

    if cursor.fetchone()["cnt"] > 0:
        return True

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM vue_components
        -- REMOVED LIMIT: was hiding bugs
        """)

    return cursor.fetchone()["cnt"] > 0


def _check_vhtml_directive(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check v-html directives with user input."""
    findings = []

    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, component in cursor.fetchall():
        has_user_input = any(src in (expression or "") for src in VUE_INPUT_SOURCES)

        if has_user_input and not is_sanitized(expression or ""):
            findings.append(
                StandardFinding(
                    rule_name="vue-xss-vhtml",
                    message=f"XSS: v-html in {component} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f'v-html="{expression[:60]}"'
                    if len(expression or "") > 60
                    else f'v-html="{expression}"',
                    cwe_id="CWE-79",
                )
            )

        if "(" in (expression or "") or "?" in (expression or ""):
            findings.append(
                StandardFinding(
                    rule_name="vue-xss-vhtml-complex",
                    message="XSS: v-html with complex expression (verify for user input)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet="v-html with complex expression",
                    cwe_id="CWE-79",
                )
            )

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

    for file, line, _component in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="vue-xss-vhtml-vonce",
                message="XSS: v-html with v-once can cache malicious content",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="xss",
                snippet="v-html combined with v-once",
                cwe_id="CWE-79",
            )
        )

    return findings


def _check_template_compilation(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check for dynamic template compilation with user input."""
    findings = []

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, callee, template_arg in cursor.fetchall():
        is_compile_method = any(method in callee for method in VUE_COMPILE_METHODS)
        if not is_compile_method:
            continue

        has_user_input = any(src in (template_arg or "") for src in VUE_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="vue-template-injection",
                    message=f"Template Injection: {callee} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    snippet=f"{callee}(userTemplate)",
                    cwe_id="CWE-94",
                )
            )

    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name
        FROM vue_components vc
        WHERE vc.has_template = 1
    """)

    for file, line, comp_name in cursor.fetchall():
        cursor.execute(
            """
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 50
              AND a.source_expr IS NOT NULL
        """,
            [file, line, line],
        )

        for (template_source,) in cursor.fetchall():
            has_template = "template:" in template_source
            has_interpolation = "${" in template_source or "`" in template_source

            if not (has_template and has_interpolation):
                continue

            has_user_input = any(src in template_source for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(
                    StandardFinding(
                        rule_name="vue-dynamic-template",
                        message=f"XSS: Component {comp_name} has dynamic template with user input",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet="template: `<div>${userInput}</div>`",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_render_functions(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check render functions for XSS vulnerabilities."""
    findings = []

    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name, vc.setup_return
        FROM vue_components vc
        WHERE vc.type = 'render-function'
           OR vc.setup_return IS NOT NULL
    """)

    for file, line, comp_name, setup_return in cursor.fetchall():
        if setup_return:
            has_render_pattern = "h(" in setup_return or "createVNode" in setup_return
            if not has_render_pattern:
                continue

        dangerous_props = ["innerHTML", "domProps", "v-html"]

        cursor.execute(
            """
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 100
              AND a.source_expr IS NOT NULL
        """,
            [file, line, line],
        )

        for (source,) in cursor.fetchall():
            has_dangerous_prop = any(prop in source for prop in dangerous_props)
            if not has_dangerous_prop:
                continue

            has_user_input = any(src in source for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(
                    StandardFinding(
                        rule_name="vue-render-function-xss",
                        message=f"XSS: Render function in {comp_name} uses innerHTML with user input",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet='h("div", { domProps: { innerHTML: userInput } })',
                        cwe_id="CWE-79",
                    )
                )

    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('h', 'createVNode', 'createElementVNode')
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, args in cursor.fetchall():
        if "innerHTML" not in (args or ""):
            continue

        has_user_input = any(src in (args or "") for src in VUE_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="vue-vnode-innerhtml",
                    message="XSS: VNode created with innerHTML from user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet='h("div", { innerHTML: userContent })',
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_component_props_injection(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check for XSS through component props."""
    findings = []

    cursor.execute("""
        SELECT vc.file, vc.start_line, vc.name, vc.props_definition
        FROM vue_components vc
        WHERE vc.props_definition IS NOT NULL
    """)

    for file, _line, comp_name, _props_def in cursor.fetchall():
        cursor.execute(
            """
            SELECT vd.line, vd.expression
            FROM vue_directives vd
            WHERE vd.file = ?
              AND vd.in_component = ?
              AND vd.directive_name = 'v-html'
              AND vd.expression IS NOT NULL
        """,
            [file, comp_name],
        )

        for dir_line, expression in cursor.fetchall():
            if "props." not in expression:
                continue

            findings.append(
                StandardFinding(
                    rule_name="vue-props-vhtml",
                    message=f"XSS: Component {comp_name} uses props directly in v-html",
                    file_path=file,
                    line=dir_line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet='v-html="props.content"',
                    cwe_id="CWE-79",
                )
            )

    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
          AND vd.expression IS NOT NULL
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, _component in cursor.fetchall():
        if "$attrs" not in expression:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-attrs-vhtml",
                message="XSS: $attrs used in v-html (uncontrolled input)",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="xss",
                snippet='v-html="$attrs.content"',
                cwe_id="CWE-79",
            )
        )

    return findings


def _check_slot_injection(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check for XSS through slot content."""
    findings = []

    cursor.execute("""
        SELECT vd.file, vd.line, vd.expression, vd.in_component
        FROM vue_directives vd
        WHERE vd.directive_name = 'v-html'
          AND vd.expression IS NOT NULL
        ORDER BY vd.file, vd.line
    """)

    for file, line, expression, _component in cursor.fetchall():
        has_slot = "$slots" in expression or "slot." in expression
        if not has_slot:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-slot-vhtml",
                message="XSS: Slot content used in v-html",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="xss",
                snippet='v-html="$slots.default"',
                cwe_id="CWE-79",
            )
        )

    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        has_scoped_slots = "scopedSlots" in source
        has_inner_html = "innerHTML" in source

        if not (has_scoped_slots and has_inner_html):
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-scoped-slot-xss",
                message="XSS: Scoped slot with innerHTML manipulation",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="xss",
                snippet="scopedSlots with innerHTML",
                cwe_id="CWE-79",
            )
        )

    return findings


def _check_filter_injection(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check for XSS through Vue filters (Vue 2)."""
    findings = []

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, filter_def in cursor.fetchall():
        is_filter_registration = func.startswith("Vue.filter") or ".filter" in func
        if not is_filter_registration:
            continue

        if "innerHTML" in (filter_def or "") or "<" in (filter_def or ""):
            findings.append(
                StandardFinding(
                    rule_name="vue-filter-xss",
                    message="XSS: Vue filter may return unescaped HTML",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet="Vue.filter returns HTML string",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_computed_xss(cursor: sqlite3.Cursor) -> list[StandardFinding]:
    """Check computed properties that might cause XSS."""
    findings = []

    cursor.execute("""
        SELECT vh.file, vh.line, vh.component_name, vh.hook_name, vh.return_value
        FROM vue_hooks vh
        WHERE vh.hook_type = 'computed'
          AND vh.return_value IS NOT NULL
        ORDER BY vh.file, vh.line
    """)

    for file, line, _comp_name, hook_name, return_val in cursor.fetchall():
        if any(tag in (return_val or "") for tag in ["<div", "<span", "<script", "<img"]):
            has_user_input = any(src in return_val for src in VUE_INPUT_SOURCES)

            if has_user_input:
                findings.append(
                    StandardFinding(
                        rule_name="vue-computed-html",
                        message=f"XSS: Computed property {hook_name} builds HTML with user input",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet=f"computed: {{ {hook_name}() {{ return `<div>${{user}}</div>` }} }}",
                        cwe_id="CWE-79",
                    )
                )

    cursor.execute("""
        SELECT vh.file, vh.line, vh.component_name, vh.hook_name
        FROM vue_hooks vh
        WHERE vh.hook_type = 'watcher'
        ORDER BY vh.file, vh.line
    """)

    for file, line, _comp_name, watched_prop in cursor.fetchall():
        cursor.execute(
            """
            SELECT a.target_var
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.line <= ? + 20
              AND a.target_var IS NOT NULL
        """,
            [file, line, line],
        )

        has_inner_html = False
        for (target_var,) in cursor.fetchall():
            if ".innerHTML" in target_var:
                has_inner_html = True
                break

        if has_inner_html:
            findings.append(
                StandardFinding(
                    rule_name="vue-watcher-innerhtml",
                    message=f"XSS: Watcher for {watched_prop} manipulates innerHTML",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=f"watch: {{ {watched_prop}() {{ el.innerHTML = ... }} }}",
                    cwe_id="CWE-79",
                )
            )

    return findings


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point."""
    return find_vue_xss(context)
