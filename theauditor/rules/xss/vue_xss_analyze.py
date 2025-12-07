"""Vue.js-specific XSS Detection.

Detects Vue.js-specific cross-site scripting vulnerabilities:
- v-html directive with user input
- Dynamic template compilation
- Render function innerHTML injection
- Component props used in v-html
- Slot content XSS
- Vue filter XSS (Vue 2)
- Computed properties building HTML
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q
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
    execution_scope="database",
    primary_table="function_call_args",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue.js-specific XSS vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        if not _is_vue_app(db):
            return RuleResult(findings=[], manifest=db.get_manifest())

        findings: list[StandardFinding] = []

        findings.extend(_check_vhtml_directive(db))
        findings.extend(_check_template_compilation(db))
        findings.extend(_check_render_functions(db))
        findings.extend(_check_component_props_injection(db))
        findings.extend(_check_slot_injection(db))
        findings.extend(_check_filter_injection(db))
        findings.extend(_check_computed_xss(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _is_vue_app(db: RuleDB) -> bool:
    """Check if this is a Vue.js application."""
    framework_rows = db.query(
        Q("frameworks")
        .select("name")
        .where("name IN (?, ?, ?, ?)", "vue", "vuejs", "vue.js", "Vue")
        .where("language = ?", "javascript")
        .limit(1)
    )
    if list(framework_rows):
        return True

    component_rows = db.query(Q("vue_components").select("name").limit(1))
    return len(list(component_rows)) > 0


def _check_vhtml_directive(db: RuleDB) -> list[StandardFinding]:
    """Check v-html directives with user input."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("vue_directives")
        .select("file", "line", "expression", "in_component")
        .where("directive_name = ?", "v-html")
        .order_by("file, line")
    )

    for file, line, expression, component in rows:
        has_user_input = any(src in (expression or "") for src in VUE_INPUT_SOURCES)

        if has_user_input and not is_sanitized(expression or ""):
            snippet = (
                f'v-html="{expression[:60]}"'
                if len(expression or "") > 60
                else f'v-html="{expression}"'
            )
            findings.append(
                StandardFinding(
                    rule_name="vue-xss-vhtml",
                    message=f"XSS: v-html in {component} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
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

    sql, params = Q.raw("""
        SELECT vd1.file, vd1.line, vd1.in_component
        FROM vue_directives vd1
        JOIN vue_directives vd2 ON vd1.file = vd2.file
            AND vd1.in_component = vd2.in_component
            AND ABS(vd1.line - vd2.line) <= 2
        WHERE vd1.directive_name = 'v-html'
          AND vd2.directive_name = 'v-once'
        ORDER BY vd1.file, vd1.line
    """)
    rows = list(db.execute(sql, params))

    for file, line, _component in rows:
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


def _check_template_compilation(db: RuleDB) -> list[StandardFinding]:
    """Check for dynamic template compilation with user input."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, template_arg in rows:
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

    component_rows = db.query(
        Q("vue_components").select("file", "start_line", "name").where("has_template = ?", 1)
    )

    for file, line, comp_name in component_rows:
        assignment_rows = db.query(
            Q("assignments")
            .select("source_expr")
            .where("file = ?", file)
            .where("line >= ?", line)
            .where("line <= ?", line + 50)
            .where("source_expr IS NOT NULL")
        )

        for (template_source,) in assignment_rows:
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


def _check_render_functions(db: RuleDB) -> list[StandardFinding]:
    """Check render functions for XSS vulnerabilities."""
    findings: list[StandardFinding] = []

    component_rows = db.query(
        Q("vue_components")
        .select("file", "start_line", "name")
        .where("type = ?", "render-function")
    )

    dangerous_props = ["innerHTML", "domProps", "v-html"]

    for file, line, comp_name in component_rows:
        assignment_rows = db.query(
            Q("assignments")
            .select("source_expr")
            .where("file = ?", file)
            .where("line >= ?", line)
            .where("line <= ?", line + 100)
            .where("source_expr IS NOT NULL")
        )

        for (source,) in assignment_rows:
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

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "h", "createVNode", "createElementVNode")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, args in rows:
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


def _check_component_props_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for XSS through component props."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("vue_directives")
        .select(
            "vue_directives.file",
            "vue_directives.line",
            "vue_directives.expression",
            "vue_components.name",
        )
        .join("vue_components", on=[("file", "file"), ("in_component", "name")])
        .where("vue_directives.directive_name = ?", "v-html")
        .where("vue_directives.expression IS NOT NULL")
    )

    for file, dir_line, expression, comp_name in rows:
        if "props." not in (expression or ""):
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

    rows = db.query(
        Q("vue_directives")
        .select("file", "line", "expression", "in_component")
        .where("directive_name = ?", "v-html")
        .where("expression IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, expression, _component in rows:
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


def _check_slot_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for XSS through slot content."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("vue_directives")
        .select("file", "line", "expression", "in_component")
        .where("directive_name = ?", "v-html")
        .where("expression IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, expression, _component in rows:
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

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, source in rows:
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


def _check_filter_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for XSS through Vue filters (Vue 2)."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, filter_def in rows:
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


def _check_computed_xss(db: RuleDB) -> list[StandardFinding]:
    """Check computed properties that might cause XSS."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("vue_hooks")
        .select("file", "line", "component_name", "hook_name", "return_value")
        .where("hook_type = ?", "computed")
        .where("return_value IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, _comp_name, hook_name, return_val in rows:
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

    watcher_rows = db.query(
        Q("vue_hooks")
        .select("file", "line", "component_name", "hook_name")
        .where("hook_type = ?", "watcher")
        .order_by("file, line")
    )

    for file, line, _comp_name, watched_prop in watcher_rows:
        assignment_rows = db.query(
            Q("assignments")
            .select("target_var")
            .where("file = ?", file)
            .where("line >= ?", line)
            .where("line <= ?", line + 20)
            .where("target_var IS NOT NULL")
        )

        has_inner_html = any(".innerHTML" in target_var for (target_var,) in assignment_rows)

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
