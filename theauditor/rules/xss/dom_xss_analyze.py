"""DOM-specific XSS Detection.

Detects DOM-based cross-site scripting vulnerabilities including:
- Direct source-to-sink flows (location.* -> innerHTML)
- URL manipulation and open redirects
- Event handler injection
- DOM clobbering attacks
- Client-side template injection
- postMessage origin validation
- DOMPurify bypass patterns
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
    COMMON_INPUT_SOURCES,
    UNIVERSAL_DANGEROUS_SINKS,
)

METADATA = RuleMetadata(
    name="dom_xss",
    category="xss",
    target_extensions=[".js", ".ts", ".jsx", ".tsx", ".html"],
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.test.js", "*.spec.js"],
    execution_scope="database",
    primary_table="assignments",
)


DOM_XSS_SOURCES = COMMON_INPUT_SOURCES | frozenset(
    [
        "history.pushState",
        "history.replaceState",
        "IndexedDB",
        "document.forms",
        "document.anchors",
        "document.documentURI",
        "document.baseURI",
        "searchParams.get",
    ]
)


DOM_XSS_SINKS = UNIVERSAL_DANGEROUS_SINKS | frozenset(
    [
        "insertAdjacentElement",
        "insertAdjacentText",
        "element.setAttribute",
        "document.createElement",
        "location.href",
        "location.replace",
        "location.assign",
        "window.open",
        "document.domain",
        "element.src",
        "element.href",
        "element.action",
        "jQuery.html",
        "jQuery.append",
        "jQuery.prepend",
        "jQuery.before",
        "jQuery.after",
        "jQuery.replaceWith",
    ]
)


EVENT_HANDLERS = frozenset(
    [
        "onclick",
        "onmouseover",
        "onmouseout",
        "onload",
        "onerror",
        "onfocus",
        "onblur",
        "onchange",
        "onsubmit",
        "onkeydown",
        "onkeyup",
        "onkeypress",
        "ondblclick",
        "onmousedown",
        "onmouseup",
        "onmousemove",
        "oncontextmenu",
    ]
)


TEMPLATE_LIBRARIES = frozenset(
    [
        "Handlebars.compile",
        "Mustache.compile",
        "doT.compile",
        "ejs.compile",
        "underscore.compile",
        "lodash.compile",
        "_.template",
    ]
)


EVAL_SINKS = frozenset(["eval", "setTimeout", "setInterval", "Function", "execScript"])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect DOM-based XSS vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        findings.extend(_check_direct_dom_flows(db))
        findings.extend(_check_url_manipulation(db))
        findings.extend(_check_event_handler_injection(db))
        findings.extend(_check_dom_clobbering(db))
        findings.extend(_check_client_side_templates(db))
        findings.extend(_check_web_messaging(db))
        findings.extend(_check_dom_purify_bypass(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_direct_dom_flows(db: RuleDB) -> list[StandardFinding]:
    """Check for direct data flows from sources to sinks."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .where("""(
            target_var LIKE '%innerHTML%'
            OR target_var LIKE '%outerHTML%'
            OR target_var LIKE '%document.write%'
            OR target_var LIKE '%eval%'
            OR target_var LIKE '%location.href%'
        )""")
    )

    for file, line, target, source in rows:
        sink_found = next((s for s in DOM_XSS_SINKS if s in target), None)
        if not sink_found:
            continue

        source_found = next((s for s in DOM_XSS_SOURCES if s in source), None)
        if source_found:
            snippet = f"{target} = {source[:60]}..." if len(source) > 60 else f"{target} = {source}"
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-direct-flow",
                    message=f"DOM XSS: Direct flow from {source_found} to {sink_found}",
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
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .where("""(
            callee_function LIKE '%eval%'
            OR callee_function LIKE '%setTimeout%'
            OR callee_function LIKE '%setInterval%'
            OR callee_function LIKE '%Function%'
        )""")
    )

    for file, line, func, args in rows:
        is_eval_sink = any(sink in func for sink in EVAL_SINKS)
        if not is_eval_sink:
            continue

        source_found = next((s for s in DOM_XSS_SOURCES if s in args), None)
        if source_found:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-sink-call",
                    message=f"DOM XSS: {source_found} passed to {func}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f"{func}({args[:40]}...)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_url_manipulation(db: RuleDB) -> list[StandardFinding]:
    """Check for URL-based DOM XSS."""
    findings: list[StandardFinding] = []

    location_patterns = ["location.href", "location.replace", "location.assign", "window.location"]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        is_location = any(pattern in target for pattern in location_patterns)
        if not is_location:
            continue

        has_url_source = any(
            s in source
            for s in [
                "location.search",
                "location.hash",
                "URLSearchParams",
                "searchParams",
                "window.name",
            ]
        )

        if has_url_source:
            snippet = f"{target} = {source[:60]}..." if len(source) > 60 else f"{target} = {source}"
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-url-redirect",
                    message=f"Open Redirect/XSS: User input in {target}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-601",
                )
            )

        if "javascript:" in source:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-javascript-url",
                    message=f"XSS: javascript: URL in {target}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f'{target} = "javascript:..."',
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function = ?", "window.open")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, url_arg in rows:
        has_user_input = any(s in (url_arg or "") for s in DOM_XSS_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-window-open",
                    message="XSS: window.open with user-controlled URL",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"window.open({url_arg[:40]}...)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_event_handler_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for event handler injection vulnerabilities."""
    findings: list[StandardFinding] = []

    sql, params = Q.raw("""
        SELECT f1.file, f1.line, f1.callee_function, f1.argument_expr, f2.argument_expr
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
        WHERE f1.argument_index = 0
          AND f2.argument_index = 1
          AND f1.callee_function IS NOT NULL
          AND f1.argument_expr IS NOT NULL
        ORDER BY f1.file, f1.line
    """)
    rows = db.execute(sql, params)

    for file, line, callee_func, arg0, arg1 in rows:
        if "setAttribute" not in (callee_func or ""):
            continue

        arg0_clean = (arg0 or "").strip("'\"").lower()
        if not arg0_clean.startswith("on"):
            continue

        matched_handler = next((h for h in EVENT_HANDLERS if h == arg0_clean), None)
        if not matched_handler:
            matched_handler = arg0_clean

        has_user_input = any(s in (arg1 or "") for s in DOM_XSS_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-event-handler",
                    message=f"XSS: Event handler {matched_handler} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f'setAttribute("{matched_handler}", userInput)',
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 1")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, listener_func in rows:
        if ".addEventListener" not in func:
            continue

        if "Function" in listener_func or "eval" in listener_func:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-dynamic-listener",
                    message="XSS: Dynamic event listener from string",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet='addEventListener("click", new Function(userInput))',
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_dom_clobbering(db: RuleDB) -> list[StandardFinding]:
    """Check for DOM clobbering vulnerabilities."""
    findings: list[StandardFinding] = []

    safe_patterns = ["localStorage", "sessionStorage", "location"]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, source in rows:
        has_window_bracket = "window[" in source and 'window["_' not in source
        has_document_bracket = "document[" in source and 'document["_' not in source

        if not (has_window_bracket or has_document_bracket):
            continue

        if not any(safe in source for safe in safe_patterns):
            snippet = source[:80] if len(source) > 80 else source
            findings.append(
                StandardFinding(
                    rule_name="dom-clobbering",
                    message="DOM Clobbering: Unsafe window/document property access",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=snippet,
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IN (?, ?)", "document.getElementById", "getElementById")
        .order_by("file, line")
    )

    for file, line, _func in rows:
        check_rows = db.query(
            Q("assignments")
            .select("source_expr")
            .where("file = ?", file)
            .where("line = ?", line)
            .where("source_expr IS NOT NULL")
        )

        for (source_expr,) in check_rows:
            has_get_element_by_id = "getElementById" in source_expr
            has_null_check = "?" in source_expr or "&&" in source_expr

            if has_get_element_by_id and not has_null_check:
                findings.append(
                    StandardFinding(
                        rule_name="dom-clobbering-no-null-check",
                        message="DOM Clobbering: getElementById result used without null check",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="xss",
                        snippet="var elem = getElementById(id); elem.innerHTML = ...",
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_client_side_templates(db: RuleDB) -> list[StandardFinding]:
    """Check for client-side template injection."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        is_inner_html = ".innerHTML" in target
        has_template_literal = "`" in source and "${" in source

        if not (is_inner_html and has_template_literal):
            continue

        has_dom_source = any(s in source for s in DOM_XSS_SOURCES)

        if has_dom_source:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-template-literal",
                    message="XSS: Template literal with DOM source in innerHTML",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{target} = `<div>${{location.search}}</div>`",
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, template in rows:
        matched_lib = next((lib for lib in TEMPLATE_LIBRARIES if func.startswith(lib)), None)

        if not matched_lib:
            continue

        has_user_input = any(s in template for s in DOM_XSS_SOURCES)

        if has_user_input:
            lib = "template library"
            for lib_name in ["Handlebars", "Mustache", "doT", "ejs", "underscore", "lodash"]:
                if lib_name in func:
                    lib = lib_name
                    break

            findings.append(
                StandardFinding(
                    rule_name="dom-xss-template-injection",
                    message=f"Template Injection: {lib} template with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    snippet=f"{func}(userTemplate)",
                    cwe_id="CWE-94",
                )
            )

    return findings


def _check_web_messaging(db: RuleDB) -> list[StandardFinding]:
    """Check for postMessage XSS vulnerabilities."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function LIKE ?", "%.addEventListener%")
        .where("argument_expr LIKE ?", "%message%")
    )

    for file, line, _func, _event_type in rows:
        origin_check_rows = db.query(
            Q("assignments")
            .select("file")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line + 1, line + 30)
            .where("source_expr IS NOT NULL")
            .where("(source_expr LIKE '%event.origin%' OR source_expr LIKE '%e.origin%')")
        )

        has_origin_check = len(list(origin_check_rows)) > 0

        if not has_origin_check:
            sink_rows = db.query(
                Q("assignments")
                .select("file")
                .where("file = ?", file)
                .where("line BETWEEN ? AND ?", line + 1, line + 30)
                .where("(source_expr LIKE '%event.data%' OR source_expr LIKE '%e.data%')")
                .where("(target_var LIKE '%.innerHTML%' OR source_expr LIKE '%eval%')")
            )

            if len(list(sink_rows)) > 0:
                findings.append(
                    StandardFinding(
                        rule_name="dom-xss-postmessage",
                        message="XSS: postMessage data used in dangerous sink without origin validation",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet='addEventListener("message", (e) => { el.innerHTML = e.data })',
                        cwe_id="CWE-79",
                    )
                )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("argument_index = 1")
        .where("callee_function LIKE ?", "%postMessage%")
        .where("(argument_expr = ? OR argument_expr = ?)", "'*'", '"*"')
    )

    for file, line, _func in rows:
        findings.append(
            StandardFinding(
                rule_name="dom-xss-postmessage-wildcard",
                message='Security: postMessage with wildcard origin ("*")',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="security",
                snippet='postMessage(data, "*")',
                cwe_id="CWE-345",
            )
        )

    return findings


def _check_dom_purify_bypass(db: RuleDB) -> list[StandardFinding]:
    """Check for potential DOMPurify bypass patterns."""
    findings: list[StandardFinding] = []

    dangerous_configs = ["ALLOW_UNKNOWN_PROTOCOLS", "ALLOW_DATA_ATTR", "ALLOW_ARIA_ATTR"]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, target, source in rows:
        is_inner_html = ".innerHTML" in target
        has_dom_purify = "DOMPurify.sanitize" in source

        if not (is_inner_html and has_dom_purify):
            continue

        for config in dangerous_configs:
            if config in source:
                findings.append(
                    StandardFinding(
                        rule_name="dom-xss-purify-config",
                        message=f"XSS: DOMPurify with dangerous config {config}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="xss",
                        snippet=f"DOMPurify.sanitize(input, {{ {config}: true }})",
                        cwe_id="CWE-79",
                    )
                )

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    double_decode_patterns = [
        ("decodeURIComponent", "decodeURIComponent(decodeURIComponent(input))"),
        ("unescape", "unescape(unescape(input))"),
        ("atob", "atob(atob(input))"),
    ]

    for file, line, source in rows:
        for pattern, snippet in double_decode_patterns:
            if source.count(pattern) >= 2:
                findings.append(
                    StandardFinding(
                        rule_name="dom-xss-double-decode",
                        message="XSS: Double decoding can bypass sanitization",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="xss",
                        snippet=snippet,
                        cwe_id="CWE-79",
                    )
                )
                break

    return findings
