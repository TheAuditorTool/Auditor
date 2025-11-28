"""DOM-specific XSS Detection."""

import sqlite3

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="dom_xss",
    category="xss",
    target_extensions=[".js", ".ts", ".jsx", ".tsx", ".html"],
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.test.js", "*.spec.js"],
    requires_jsx_pass=False,
    execution_scope="database",
)


DOM_XSS_SOURCES = frozenset(
    [
        "location.search",
        "location.hash",
        "location.href",
        "location.pathname",
        "location.hostname",
        "document.URL",
        "document.documentURI",
        "document.baseURI",
        "document.referrer",
        "document.cookie",
        "window.name",
        "window.location",
        "history.pushState",
        "history.replaceState",
        "localStorage.getItem",
        "sessionStorage.getItem",
        "IndexedDB",
        "postMessage",
        "message.data",
        "URLSearchParams",
        "searchParams.get",
        "document.forms",
        "document.anchors",
    ]
)


DOM_XSS_SINKS = frozenset(
    [
        "innerHTML",
        "outerHTML",
        "document.write",
        "document.writeln",
        "eval",
        "setTimeout",
        "setInterval",
        "Function",
        "insertAdjacentHTML",
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
        "createContextualFragment",
        "parseFromString",
    ]
)


DOM_SAFE_METHODS = frozenset(["textContent", "innerText", "createTextNode", "setAttribute"])


BROWSER_APIS = frozenset(
    ["navigator.", "screen.", "window.", "document.", "console.", "performance.", "crypto."]
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


def find_dom_xss(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect DOM-based XSS vulnerabilities."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)

    try:
        findings.extend(_check_direct_dom_flows(conn))
        findings.extend(_check_url_manipulation(conn))
        findings.extend(_check_event_handler_injection(conn))
        findings.extend(_check_dom_clobbering(conn))
        findings.extend(_check_client_side_templates(conn))
        findings.extend(_check_web_messaging(conn))
        findings.extend(_check_dom_purify_bypass(conn))

    finally:
        conn.close()

    return findings


def _check_direct_dom_flows(conn) -> list[StandardFinding]:
    """Check for direct data flows from sources to sinks."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
          AND (
              a.target_var LIKE '%innerHTML%'
              OR a.target_var LIKE '%outerHTML%'
              OR a.target_var LIKE '%document.write%'
              OR a.target_var LIKE '%eval%'
              OR a.target_var LIKE '%location.href%'
          )
    """)

    for file, line, target, source in cursor:
        sink_found = next((s for s in DOM_XSS_SINKS if s in target), None)
        if not sink_found:
            continue

        source_found = next((s for s in DOM_XSS_SOURCES if s in source), None)
        if source_found:
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-direct-flow",
                    message=f"DOM XSS: Direct flow from {source_found} to {sink_found}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f"{target} = {source[:60]}..."
                    if len(source) > 60
                    else f"{target} = {source}",
                    cwe_id="CWE-79",
                )
            )

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
          AND (
              f.callee_function LIKE '%eval%'
              OR f.callee_function LIKE '%setTimeout%'
              OR f.callee_function LIKE '%setInterval%'
              OR f.callee_function LIKE '%Function%'
          )
    """)

    for file, line, func, args in cursor:
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


def _check_url_manipulation(conn) -> list[StandardFinding]:
    """Check for URL-based DOM XSS."""
    findings = []
    cursor = conn.cursor()

    location_patterns = ["location.href", "location.replace", "location.assign", "window.location"]

    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
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
            findings.append(
                StandardFinding(
                    rule_name="dom-xss-url-redirect",
                    message=f"Open Redirect/XSS: User input in {target}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{target} = {source[:60]}..."
                    if len(source) > 60
                    else f"{target} = {source}",
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

    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'window.open'
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, url_arg in cursor.fetchall():
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


def _check_event_handler_injection(conn) -> list[StandardFinding]:
    """Check for event handler injection vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f1.file, f1.line, f1.argument_expr as handler_name, f2.argument_expr as handler_value
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
        WHERE f1.argument_index = 0
          AND f2.argument_index = 1
          AND f1.callee_function IS NOT NULL
          AND f1.argument_expr IS NOT NULL
        ORDER BY f1.file, f1.line
    """)

    for file, line, handler_name, handler_value in cursor.fetchall():
        if ".setAttribute" not in handler_name:
            continue

        handler_name_lower = handler_name.lower()
        matched_handler = None
        for handler in EVENT_HANDLERS:
            if handler in handler_name_lower:
                matched_handler = handler
                break

        if not matched_handler:
            continue

        has_user_input = any(s in handler_value for s in DOM_XSS_SOURCES)

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

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 1
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, listener_func in cursor.fetchall():
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


def _check_dom_clobbering(conn) -> list[StandardFinding]:
    """Check for DOM clobbering vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    safe_patterns = ["localStorage", "sessionStorage", "location"]

    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        has_window_bracket = "window[" in source and 'window["_' not in source
        has_document_bracket = "document[" in source and 'document["_' not in source

        if not (has_window_bracket or has_document_bracket):
            continue

        if not any(safe in source for safe in safe_patterns):
            findings.append(
                StandardFinding(
                    rule_name="dom-clobbering",
                    message="DOM Clobbering: Unsafe window/document property access",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=source[:80] if len(source) > 80 else source,
                    cwe_id="CWE-79",
                )
            )

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('document.getElementById', 'getElementById')
        ORDER BY f.file, f.line
    """)

    for file, line, _func in cursor.fetchall():
        cursor.execute(
            """
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line = ?
              AND a.source_expr IS NOT NULL
        """,
            [file, line],
        )

        result = cursor.fetchone()
        if result:
            source_expr = result[0]

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


def _check_client_side_templates(conn) -> list[StandardFinding]:
    """Check for client-side template injection."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
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

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, template in cursor.fetchall():
        matched_lib = None
        for lib_func in TEMPLATE_LIBRARIES:
            if func.startswith(lib_func):
                matched_lib = lib_func
                break

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


def _check_web_messaging(conn) -> list[StandardFinding]:
    """Check for postMessage XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function LIKE '%.addEventListener%'
          AND f.argument_expr LIKE '%message%'
    """)

    for file, line, _func, _event_type in cursor:
        cursor.execute(
            """
            SELECT 1
            FROM assignments a
            WHERE a.file = ?
              AND a.line BETWEEN ? + 1 AND ? + 30
              AND a.source_expr IS NOT NULL
              AND (a.source_expr LIKE '%event.origin%' OR a.source_expr LIKE '%e.origin%')
        -- REMOVED LIMIT: was hiding bugs
        """,
            [file, line, line],
        )

        has_origin_check = cursor.fetchone() is not None

        if not has_origin_check:
            cursor.execute(
                """
                SELECT 1
                FROM assignments a
                WHERE a.file = ?
                  AND a.line BETWEEN ? + 1 AND ? + 30
                  AND (a.source_expr LIKE '%event.data%' OR a.source_expr LIKE '%e.data%')
                  AND (a.target_var LIKE '%.innerHTML%' OR a.source_expr LIKE '%eval%')
        -- REMOVED LIMIT: was hiding bugs
        """,
                [file, line, line],
            )

            if cursor.fetchone() is not None:
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

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.argument_index = 1
          AND f.callee_function LIKE '%postMessage%'
          AND (f.argument_expr = "'*'" OR f.argument_expr = '"*"')
    """)

    for file, line, _func in cursor:
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


def _check_dom_purify_bypass(conn) -> list[StandardFinding]:
    """Check for potential DOMPurify bypass patterns."""
    findings = []
    cursor = conn.cursor()

    dangerous_configs = ["ALLOW_UNKNOWN_PROTOCOLS", "ALLOW_DATA_ATTR", "ALLOW_ARIA_ATTR"]

    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
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

    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    double_decode_patterns = [
        ("decodeURIComponent", "decodeURIComponent(decodeURIComponent(input))"),
        ("unescape", "unescape(unescape(input))"),
        ("atob", "atob(atob(input))"),
    ]

    for file, line, source in cursor.fetchall():
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


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point."""
    return find_dom_xss(context)
