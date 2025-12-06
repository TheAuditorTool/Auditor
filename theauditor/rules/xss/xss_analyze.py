"""XSS Detection - Framework-Aware Golden Standard Implementation.

Detects cross-site scripting vulnerabilities with framework awareness:
- Response methods (res.send, res.write)
- DOM manipulation (innerHTML, document.write)
- Dangerous functions (eval, Function)
- React dangerouslySetInnerHTML
- Vue v-html directive
- Angular security bypass methods
- jQuery DOM methods
- Template injection
- javascript: protocol URLs
- PostMessage XSS
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
    ANGULAR_AUTO_ESCAPED,
    COMMON_INPUT_SOURCES,
    EXPRESS_SAFE_SINKS,
    REACT_AUTO_ESCAPED,
    UNIVERSAL_DANGEROUS_SINKS,
    VUE_AUTO_ESCAPED,
    XSS_TARGET_EXTENSIONS,
    is_sanitized,
)

METADATA = RuleMetadata(
    name="xss_core",
    category="xss",
    target_extensions=XSS_TARGET_EXTENSIONS,
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.test.js", "*.spec.js"],
    execution_scope="database",
    primary_table="function_call_args",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Main XSS detection with framework awareness.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        dynamic_safe_sinks: set[str] = set()
        sql, params = Q.raw("""
            SELECT DISTINCT sink_pattern
            FROM framework_safe_sinks
            WHERE is_safe = 1
        """)
        for (pattern,) in db.execute(sql, params):
            if pattern:
                dynamic_safe_sinks.add(pattern)

        detected_frameworks = _get_detected_frameworks(db)
        static_safe_sinks = _build_framework_safe_sinks(db, detected_frameworks)

        combined_safe_sinks = frozenset(set(static_safe_sinks) | dynamic_safe_sinks)

        findings: list[StandardFinding] = []

        findings.extend(_check_response_methods(db, combined_safe_sinks, detected_frameworks))
        findings.extend(_check_dom_manipulation(db, combined_safe_sinks))
        findings.extend(_check_dangerous_functions(db))
        findings.extend(_check_react_dangerouslysetinnerhtml(db))
        findings.extend(_check_vue_vhtml_directive(db))
        findings.extend(_check_angular_bypass(db))
        findings.extend(_check_jquery_methods(db))
        findings.extend(_check_template_injection(db, detected_frameworks))
        findings.extend(_check_direct_user_input_to_sink(db, combined_safe_sinks))
        findings.extend(_check_url_javascript_protocol(db))
        findings.extend(_check_postmessage_xss(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_detected_frameworks(db: RuleDB) -> set[str]:
    """Query frameworks table for detected frameworks."""
    frameworks: set[str] = set()

    sql, params = Q.raw("SELECT DISTINCT name FROM frameworks")
    for (name,) in db.execute(sql, params):
        if name:
            frameworks.add(name.lower())

    return frameworks


def _build_framework_safe_sinks(db: RuleDB, frameworks: set[str]) -> frozenset[str]:
    """Build comprehensive safe sink list based on detected frameworks."""
    safe_sinks: set[str] = set()

    if "express" in frameworks or "express.js" in frameworks:
        safe_sinks.update(EXPRESS_SAFE_SINKS)

    if "react" in frameworks:
        safe_sinks.update(REACT_AUTO_ESCAPED)

    if "vue" in frameworks or "vuejs" in frameworks:
        safe_sinks.update(VUE_AUTO_ESCAPED)

    if "angular" in frameworks:
        safe_sinks.update(s for s in ANGULAR_AUTO_ESCAPED if "bypass" not in s.lower())

    sql, params = Q.raw("""
        SELECT DISTINCT fss.sink_pattern
        FROM framework_safe_sinks fss
        JOIN frameworks f ON fss.framework_id = f.id
        WHERE fss.is_safe = 1
    """)

    for (sink_pattern,) in db.execute(sql, params):
        if sink_pattern:
            safe_sinks.add(sink_pattern)

    return frozenset(safe_sinks)


def _check_response_methods(
    db: RuleDB, safe_sinks: frozenset[str], frameworks: set[str]
) -> list[StandardFinding]:
    """Check response methods with framework awareness."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        args_safe = args or ""
        is_response_method = func.startswith("res.") or func.startswith("response.")
        if not is_response_method:
            continue

        if func in safe_sinks:
            continue

        if ("express" in frameworks or "express.js" in frameworks) and func in EXPRESS_SAFE_SINKS:
            continue

        has_user_input = any(source in args_safe for source in COMMON_INPUT_SOURCES)

        if has_user_input and not is_sanitized(args_safe):
            if func in ["res.send", "res.write", "response.send", "response.write"]:
                severity = Severity.HIGH
            elif func in ["res.end", "response.end"]:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            snippet = (
                f"{func}({args_safe[:60]}...)" if len(args_safe) > 60 else f"{func}({args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-response-unsafe",
                    message=f"XSS: {func} with user input (not JSON-encoded)",
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_dom_manipulation(db: RuleDB, safe_sinks: frozenset[str]) -> list[StandardFinding]:
    """Check dangerous DOM manipulation with user input."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .where("(target_var LIKE '%.innerHTML' OR target_var LIKE '%.outerHTML')")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        source_safe = source or ""
        has_user_input = any(src in source_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input and not is_sanitized(source_safe):
            snippet = (
                f"{target} = {source_safe[:60]}..."
                if len(source_safe) > 60
                else f"{target} = {source_safe}"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-dom-innerhtml",
                    message=f"XSS: {target} assigned user input without sanitization",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "document.write", "document.writeln")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        args_safe = args or ""
        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input and not is_sanitized(args_safe):
            snippet = (
                f"{func}({args_safe[:60]}...)" if len(args_safe) > 60 else f"{func}({args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-document-write",
                    message=f"XSS: {func} with user input is extremely dangerous",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 1")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if "insertAdjacentHTML" not in func:
            continue

        args_safe = args or ""
        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input and not is_sanitized(args_safe):
            snippet = (
                f"{func}(_, {args_safe[:60]}...)"
                if len(args_safe) > 60
                else f"{func}(_, {args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-insert-adjacent-html",
                    message=f"XSS: {func} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_dangerous_functions(db: RuleDB) -> list[StandardFinding]:
    """Check eval() and similar dangerous functions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "eval", "Function", "execScript")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        args_safe = args or ""
        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            snippet = (
                f"{func}({args_safe[:60]}...)" if len(args_safe) > 60 else f"{func}({args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-code-injection",
                    message=f"Code Injection: {func} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    snippet=snippet,
                    cwe_id="CWE-94",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "setTimeout", "setInterval")
        .where("argument_index = 0")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        args_safe = args or ""
        is_string_literal = args_safe.startswith('"') or args_safe.startswith("'")
        if not is_string_literal:
            continue

        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            snippet = (
                f'{func}("{args_safe[:40]}...", ...)'
                if len(args_safe) > 40
                else f'{func}("{args_safe}", ...)'
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-timeout-eval",
                    message=f"Code Injection: {func} with string containing user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    snippet=snippet,
                    cwe_id="CWE-94",
                )
            )

    return findings


def _check_react_dangerouslysetinnerhtml(db: RuleDB) -> list[StandardFinding]:
    """Check React dangerouslySetInnerHTML with user input."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, source in rows:
        source_safe = source or ""
        if "dangerouslySetInnerHTML" not in source_safe:
            continue

        has_user_input = any(src in source_safe for src in COMMON_INPUT_SOURCES)
        has_props = "props." in source_safe or "this.props" in source_safe
        has_state = "state." in source_safe or "this.state" in source_safe

        if (has_user_input or has_props or has_state) and not is_sanitized(source_safe):
            snippet = source_safe[:100] if len(source_safe) > 100 else source_safe
            findings.append(
                StandardFinding(
                    rule_name="xss-react-dangerous-html",
                    message="XSS: dangerouslySetInnerHTML with potentially unsafe input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    sql, params = Q.raw("""
        SELECT file, start_line
        FROM react_components
        WHERE has_jsx = 1
        LIMIT 1
    """)
    react_rows = list(db.execute(sql, params))

    if react_rows:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "param_name", "argument_expr")
            .where("(callee_function IS NOT NULL OR param_name IS NOT NULL)")
            .order_by("file, line")
        )

        for file, line, callee, param, args in rows:
            args_safe = args or ""
            is_dangerous = ("dangerouslySetInnerHTML" in (callee or "")) or (
                param == "dangerouslySetInnerHTML"
            )
            if not is_dangerous:
                continue

            if "__html" in args_safe:
                has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)
                if has_user_input:
                    findings.append(
                        StandardFinding(
                            rule_name="xss-react-dangerous-prop",
                            message="XSS: React dangerouslySetInnerHTML prop with user input",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="xss",
                            snippet="dangerouslySetInnerHTML={__html: ...}",
                            cwe_id="CWE-79",
                        )
                    )
            elif args_safe and not args_safe.strip().startswith("{"):
                findings.append(
                    StandardFinding(
                        rule_name="xss-react-dangerous-prop-indirect",
                        message="XSS: dangerouslySetInnerHTML with variable reference (cannot verify safety)",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="xss",
                        snippet=f"dangerouslySetInnerHTML={{{args_safe[:40]}}}",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_vue_vhtml_directive(db: RuleDB) -> list[StandardFinding]:
    """Check Vue v-html directives with user input."""
    findings: list[StandardFinding] = []

    sql, params = Q.raw("""
        SELECT file, line, directive_name, expression
        FROM vue_directives
        WHERE directive_name = 'v-html'
        ORDER BY file, line
    """)

    for file, line, _directive, expression in db.execute(sql, params):
        expr_safe = expression or ""
        has_user_input = any(src in expr_safe for src in COMMON_INPUT_SOURCES)
        has_route = "$route" in expr_safe
        has_props = "props" in expr_safe

        if has_user_input or has_route or has_props:
            snippet = (
                f'v-html="{expr_safe[:60]}"' if len(expr_safe) > 60 else f'v-html="{expr_safe}"'
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-vue-vhtml",
                    message="XSS: v-html directive with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_angular_bypass(db: RuleDB) -> list[StandardFinding]:
    """Check Angular security bypass methods."""
    findings: list[StandardFinding] = []

    bypass_methods = [
        "bypassSecurityTrustHtml",
        "bypassSecurityTrustScript",
        "bypassSecurityTrustUrl",
        "bypassSecurityTrustResourceUrl",
    ]

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        matched_method = next((m for m in bypass_methods if m in func), None)

        if not matched_method:
            continue

        args_safe = args or ""
        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            snippet = (
                f"{func}({args_safe[:60]}...)" if len(args_safe) > 60 else f"{func}({args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-angular-bypass",
                    message=f"XSS: Angular {matched_method} with user input bypasses security",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_jquery_methods(db: RuleDB) -> list[StandardFinding]:
    """Check jQuery DOM manipulation methods."""
    findings: list[StandardFinding] = []

    jquery_dangerous_methods = [
        ".html",
        ".append",
        ".prepend",
        ".after",
        ".before",
        ".replaceWith",
        ".wrap",
        ".wrapInner",
    ]

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if "$" not in func and "jQuery" not in func:
            continue

        matched_method = next((m for m in jquery_dangerous_methods if m in func), None)

        if not matched_method:
            continue

        args_safe = args or ""
        has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input and not is_sanitized(args_safe):
            snippet = (
                f"{func}({args_safe[:60]}...)" if len(args_safe) > 60 else f"{func}({args_safe})"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-jquery-dom",
                    message=f"XSS: jQuery {matched_method} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_template_injection(db: RuleDB, frameworks: set[str]) -> list[StandardFinding]:
    """Check for template injection vulnerabilities."""
    findings: list[StandardFinding] = []

    if "flask" in frameworks or "django" in frameworks:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("""callee_function IN (
                'render_template_string', 'Template',
                'jinja2.Template', 'from_string'
            )""")
            .where("argument_index = 0")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            args_safe = args or ""
            has_user_input = any(src in args_safe for src in COMMON_INPUT_SOURCES)

            if has_user_input:
                snippet = (
                    f"{func}({args_safe[:60]}...)"
                    if len(args_safe) > 60
                    else f"{func}({args_safe})"
                )
                findings.append(
                    StandardFinding(
                        rule_name="xss-template-injection",
                        message=f"Template Injection: {func} with user input",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        snippet=snippet,
                        cwe_id="CWE-94",
                    )
                )

    if "express" in frameworks:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IN (?, ?, ?)", "ejs.render", "ejs.compile", "res.render")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            if "<%-%" not in args:
                continue

            findings.append(
                StandardFinding(
                    rule_name="xss-ejs-unescaped",
                    message="XSS: EJS unescaped output <%- detected",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{func}(... <%- ... %> ...)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_direct_user_input_to_sink(
    db: RuleDB, safe_sinks: frozenset[str]
) -> list[StandardFinding]:
    """Check for direct user input passed to dangerous sinks."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if func in safe_sinks:
            continue

        matched_sink = next((s for s in UNIVERSAL_DANGEROUS_SINKS if s in func), None)

        if not matched_sink:
            continue

        for source in COMMON_INPUT_SOURCES:
            if source in (args or ""):
                findings.append(
                    StandardFinding(
                        rule_name="xss-direct-taint",
                        message=f"XSS: Direct user input ({source}) to dangerous sink ({matched_sink})",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="xss",
                        snippet=f"{func}({source}...)",
                        cwe_id="CWE-79",
                    )
                )
                break

    return findings


def _check_url_javascript_protocol(db: RuleDB) -> list[StandardFinding]:
    """Check for javascript: protocol in URLs."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        source_safe = source or ""
        is_url_property = ".href" in target or ".src" in target
        if not is_url_property:
            continue

        has_dangerous_protocol = "javascript:" in source_safe or "data:text/html" in source_safe
        if not has_dangerous_protocol:
            continue

        has_user_input = any(src in source_safe for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            snippet = (
                f"{target} = {source_safe[:60]}..."
                if len(source_safe) > 60
                else f"{target} = {source_safe}"
            )
            findings.append(
                StandardFinding(
                    rule_name="xss-javascript-protocol",
                    message="XSS: javascript: or data: URL with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    sql, params = Q.raw("""
        SELECT f1.file, f1.line, f1.callee_function, f1.argument_expr, f2.argument_expr
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
        WHERE f1.argument_index = 0
          AND f2.argument_index = 1
          AND f1.argument_expr IN ("'href'", '"href"', "'src'", '"src"')
          AND f1.callee_function IS NOT NULL
          AND f2.callee_function IS NOT NULL
        ORDER BY f1.file, f1.line
    """)
    rows = list(db.execute(sql, params))

    for file, line, callee, attr, value in rows:
        if "setAttribute" not in callee:
            continue

        if "javascript:" in (value or "") or "data:text/html" in (value or ""):
            has_user_input = any(src in value for src in COMMON_INPUT_SOURCES)

            if has_user_input:
                findings.append(
                    StandardFinding(
                        rule_name="xss-set-attribute-protocol",
                        message=f"XSS: setAttribute({attr}) with javascript: URL",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet=f"setAttribute({attr}, javascript:...)",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_postmessage_xss(db: RuleDB) -> list[StandardFinding]:
    """Check for PostMessage XSS vulnerabilities."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 1")
        .where("(argument_expr = ? OR argument_expr = ?)", "'*'", '"*"')
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, _target_origin in rows:
        if "postMessage" not in func:
            continue

        findings.append(
            StandardFinding(
                rule_name="xss-postmessage-origin",
                message="XSS: postMessage with targetOrigin '*' allows any origin",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="xss",
                snippet=f'{func}(data, "*")',
                cwe_id="CWE-79",
            )
        )

    message_data_patterns = ["event.data", "message.data"]
    dangerous_operations = [".innerHTML", "eval(", "Function("]

    assignment_rows = list(
        db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )
    )

    for file, line, target, source in assignment_rows:
        source_safe = source or ""
        target_safe = target or ""
        has_message_data = any(pattern in source_safe for pattern in message_data_patterns)
        if not has_message_data:
            continue

        has_dangerous_op = any(op in target_safe for op in dangerous_operations) or any(
            op in source_safe for op in dangerous_operations
        )
        if not has_dangerous_op:
            continue

        origin_patterns = ["event.origin", "message.origin"]

        nearby_rows = db.query(
            Q("assignments")
            .select("source_expr")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line - 5, line + 5)
            .where("source_expr IS NOT NULL")
        )

        has_origin_check = any(
            any(pattern in nearby_source for pattern in origin_patterns)
            for (nearby_source,) in nearby_rows
        )

        if not has_origin_check:
            snippet = source_safe[:80] if len(source_safe) > 80 else source_safe
            findings.append(
                StandardFinding(
                    rule_name="xss-postmessage-no-validation",
                    message="XSS: PostMessage data used without origin validation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    return findings
