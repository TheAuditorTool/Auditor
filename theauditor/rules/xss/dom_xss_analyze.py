"""DOM-specific XSS Detection.

This module detects DOM-based XSS vulnerabilities that occur in client-side JavaScript.
These are particularly dangerous as they can bypass server-side protections.
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
    name="dom_xss",
    category="xss",
    target_extensions=['.js', '.ts', '.jsx', '.tsx', '.html'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.test.js', '*.spec.js'],
    requires_jsx_pass=False
)


# DOM XSS Sources (where malicious data comes from)
DOM_XSS_SOURCES = frozenset([
    'location.search', 'location.hash', 'location.href',
    'location.pathname', 'location.hostname',
    'document.URL', 'document.documentURI', 'document.baseURI',
    'document.referrer', 'document.cookie',
    'window.name', 'window.location',
    'history.pushState', 'history.replaceState',
    'localStorage.getItem', 'sessionStorage.getItem',
    'IndexedDB', 'postMessage', 'message.data',
    'URLSearchParams', 'searchParams.get',
    'document.forms', 'document.anchors'
])

# DOM XSS Sinks (where malicious data gets executed)
DOM_XSS_SINKS = frozenset([
    'innerHTML', 'outerHTML', 'document.write', 'document.writeln',
    'eval', 'setTimeout', 'setInterval', 'Function',
    'insertAdjacentHTML', 'insertAdjacentElement', 'insertAdjacentText',
    'element.setAttribute', 'document.createElement',
    'location.href', 'location.replace', 'location.assign',
    'window.open', 'document.domain',
    'element.src', 'element.href', 'element.action',
    'jQuery.html', 'jQuery.append', 'jQuery.prepend',
    'jQuery.before', 'jQuery.after', 'jQuery.replaceWith',
    'createContextualFragment', 'parseFromString'
])

# Safe DOM methods (properly escape content)
DOM_SAFE_METHODS = frozenset([
    'textContent', 'innerText', 'createTextNode',
    'setAttribute' # when not used with event handlers
])

# Browser API patterns
BROWSER_APIS = frozenset([
    'navigator.', 'screen.', 'window.', 'document.',
    'console.', 'performance.', 'crypto.'
])

# Event handlers for setAttribute injection detection
EVENT_HANDLERS = frozenset([
    'onclick', 'onmouseover', 'onmouseout', 'onload', 'onerror',
    'onfocus', 'onblur', 'onchange', 'onsubmit', 'onkeydown',
    'onkeyup', 'onkeypress', 'ondblclick', 'onmousedown',
    'onmouseup', 'onmousemove', 'oncontextmenu'
])

# Template libraries that can be exploited for injection
TEMPLATE_LIBRARIES = frozenset([
    'Handlebars.compile', 'Mustache.compile', 'doT.compile',
    'ejs.compile', 'underscore.compile', 'lodash.compile', '_.template'
])

# Dangerous eval-like sinks
EVAL_SINKS = frozenset([
    'eval', 'setTimeout', 'setInterval', 'Function', 'execScript'
])


def find_dom_xss(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect DOM-based XSS vulnerabilities.

    Returns:
        List of DOM XSS findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Run checks that require function_call_args or assignments
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

    # Check assignments from DOM sources to dangerous sinks
    # File extension filtering handled by METADATA, pattern matching in Python
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if target contains a dangerous sink
        sink_found = None
        for dom_sink in DOM_XSS_SINKS:
            if dom_sink in target:
                sink_found = dom_sink
                break

        if not sink_found:
            continue

        # Filter in Python: Check if source contains a DOM XSS source
        source_found = None
        for dom_source in DOM_XSS_SOURCES:
            if dom_source in source:
                source_found = dom_source
                break

        if source_found:
            findings.append(StandardFinding(
                rule_name='dom-xss-direct-flow',
                message=f'DOM XSS: Direct flow from {source_found} to {sink_found}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = {source[:60]}...' if len(source) > 60 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # Check function calls with DOM sources as arguments to eval-like sinks
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if function is an eval-like sink
        is_eval_sink = any(sink in func for sink in EVAL_SINKS)
        if not is_eval_sink:
            continue

        # Filter in Python: Check if argument contains a DOM XSS source
        source_found = None
        for source in DOM_XSS_SOURCES:
            if source in args:
                source_found = source
                break

        if source_found:
            findings.append(StandardFinding(
                rule_name='dom-xss-sink-call',
                message=f'DOM XSS: {source_found} passed to {func}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{func}({source_found})',
                cwe_id='CWE-79'
            ))

    return findings


def _check_url_manipulation(conn) -> list[StandardFinding]:
    """Check for URL-based DOM XSS."""
    findings = []
    cursor = conn.cursor()

    # Location manipulation patterns to detect
    location_patterns = ['location.href', 'location.replace', 'location.assign', 'window.location']

    # Check location assignments with user input
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if target is a location manipulation
        is_location = any(pattern in target for pattern in location_patterns)
        if not is_location:
            continue

        # Check for URL sources
        has_url_source = any(s in source for s in [
            'location.search', 'location.hash', 'URLSearchParams',
            'searchParams', 'window.name'
        ])

        if has_url_source:
            findings.append(StandardFinding(
                rule_name='dom-xss-url-redirect',
                message=f'Open Redirect/XSS: User input in {target}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{target} = {source[:60]}...' if len(source) > 60 else f'{target} = {source}',
                cwe_id='CWE-601'
            ))

        # Check for javascript: protocol
        if 'javascript:' in source:
            findings.append(StandardFinding(
                rule_name='dom-xss-javascript-url',
                message=f'XSS: javascript: URL in {target}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = "javascript:..."',
                cwe_id='CWE-79'
            ))

    # Check window.open with user input
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'window.open'
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, url_arg in cursor.fetchall():
        has_user_input = any(s in (url_arg or '') for s in DOM_XSS_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='dom-xss-window-open',
                message='XSS: window.open with user-controlled URL',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'window.open({url_arg[:40]}...)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_event_handler_injection(conn) -> list[StandardFinding]:
    """Check for event handler injection vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check setAttribute with event handlers
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
        # Filter in Python: Check if setAttribute with event handler
        if '.setAttribute' not in handler_name:
            continue

        # Filter in Python: Check if handler name is an event handler
        handler_name_lower = handler_name.lower()
        matched_handler = None
        for handler in EVENT_HANDLERS:
            if handler in handler_name_lower:
                matched_handler = handler
                break

        if not matched_handler:
            continue

        # Check if handler value contains user input
        has_user_input = any(s in handler_value for s in DOM_XSS_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='dom-xss-event-handler',
                message=f'XSS: Event handler {matched_handler} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'setAttribute("{matched_handler}", userInput)',
                cwe_id='CWE-79'
            ))

    # Check for dynamic event listener addition
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 1
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, listener_func in cursor.fetchall():
        # Filter in Python: Check if addEventListener
        if '.addEventListener' not in func:
            continue

        # Check if listener is created from string (eval-like)
        if 'Function' in listener_func or 'eval' in listener_func:
            findings.append(StandardFinding(
                rule_name='dom-xss-dynamic-listener',
                message='XSS: Dynamic event listener from string',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet='addEventListener("click", new Function(userInput))',
                cwe_id='CWE-79'
            ))

    return findings


def _check_dom_clobbering(conn) -> list[StandardFinding]:
    """Check for DOM clobbering vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Safe bracket access patterns
    safe_patterns = ['localStorage', 'sessionStorage', 'location']

    # Check for unsafe ID/name attribute usage
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check if window[ or document[ (but not window["_ or document["_)
        has_window_bracket = 'window[' in source and 'window["_' not in source
        has_document_bracket = 'document[' in source and 'document["_' not in source

        if not (has_window_bracket or has_document_bracket):
            continue

        # Check if accessing user-controlled property (exclude safe patterns)
        if not any(safe in source for safe in safe_patterns):
            findings.append(StandardFinding(
                rule_name='dom-clobbering',
                message='DOM Clobbering: Unsafe window/document property access',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=source[:80] if len(source) > 80 else source,
                cwe_id='CWE-79'
            ))

    # Check for document.getElementById without null checks
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('document.getElementById', 'getElementById')
        ORDER BY f.file, f.line
    """)

    for file, line, func in cursor.fetchall():
        # Check if result is used without null check
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line = ?
              AND a.source_expr IS NOT NULL
        """, [file, line])

        result = cursor.fetchone()
        if result:
            source_expr = result[0]
            # Filter in Python: Check if getElementById without null checks
            has_getElementByID = 'getElementById' in source_expr
            has_null_check = '?' in source_expr or '&&' in source_expr

            if has_getElementByID and not has_null_check:
                findings.append(StandardFinding(
                    rule_name='dom-clobbering-no-null-check',
                    message='DOM Clobbering: getElementById result used without null check',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='xss',
                    snippet='var elem = getElementById(id); elem.innerHTML = ...',
                    cwe_id='CWE-79'
                ))

    return findings


def _check_client_side_templates(conn) -> list[StandardFinding]:
    """Check for client-side template injection."""
    findings = []
    cursor = conn.cursor()

    # Check for template literal usage with innerHTML
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if innerHTML with template literal
        is_innerHTML = '.innerHTML' in target
        has_template_literal = '`' in source and '${' in source

        if not (is_innerHTML and has_template_literal):
            continue

        # Check for DOM sources in template
        has_dom_source = any(s in source for s in DOM_XSS_SOURCES)

        if has_dom_source:
            findings.append(StandardFinding(
                rule_name='dom-xss-template-literal',
                message='XSS: Template literal with DOM source in innerHTML',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{target} = `<div>${{location.search}}</div>`',
                cwe_id='CWE-79'
            ))

    # Check for client-side templating libraries
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, template in cursor.fetchall():
        # Filter in Python: Check if template library function
        matched_lib = None
        for lib_func in TEMPLATE_LIBRARIES:
            if func.startswith(lib_func):
                matched_lib = lib_func
                break

        if not matched_lib:
            continue

        # Check if template contains user input
        has_user_input = any(s in template for s in DOM_XSS_SOURCES)

        if has_user_input:
            # Extract library name for message
            lib = 'template library'
            for l in ['Handlebars', 'Mustache', 'doT', 'ejs', 'underscore', 'lodash']:
                if l in func:
                    lib = l
                    break

            findings.append(StandardFinding(
                rule_name='dom-xss-template-injection',
                message=f'Template Injection: {lib} template with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                snippet=f'{func}(userTemplate)',
                cwe_id='CWE-94'
            ))

    return findings


def _check_web_messaging(conn) -> list[StandardFinding]:
    """Check for postMessage XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check message event handlers
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, event_type in cursor.fetchall():
        # Filter in Python: Check if addEventListener for message event
        is_addEventListener = '.addEventListener' in func
        is_message_event = 'message' in event_type

        if not (is_addEventListener and is_message_event):
            continue

        # Check if handler validates origin
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments a
            WHERE a.file = ?
              AND a.line > ?
              AND a.line < ? + 30
              AND a.source_expr IS NOT NULL
        """, [file, line, line])

        # Fetch all assignments to check for origin validation in Python
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line > ?
              AND a.line < ? + 30
              AND a.source_expr IS NOT NULL
        """, [file, line, line])

        has_origin_check = False
        for (source_expr,) in cursor.fetchall():
            if 'event.origin' in source_expr or 'e.origin' in source_expr:
                has_origin_check = True
                break

        if not has_origin_check:
            # Check if message data is used dangerously
            cursor.execute("""
                SELECT a.target_var, a.source_expr
                FROM assignments a
                WHERE a.file = ?
                  AND a.line > ?
                  AND a.line < ? + 30
                  AND a.source_expr IS NOT NULL
            """, [file, line, line])

            for target_var, source_expr in cursor.fetchall():
                # Filter in Python: Check for event.data/e.data and dangerous usage
                has_event_data = 'event.data' in source_expr or 'e.data' in source_expr
                is_dangerous = '.innerHTML' in (target_var or '') or 'eval' in source_expr

                if has_event_data and is_dangerous:
                    findings.append(StandardFinding(
                        rule_name='dom-xss-postmessage',
                        message='XSS: postMessage data used without origin validation',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='xss',
                        snippet='addEventListener("message", (e) => { el.innerHTML = e.data })',
                        cwe_id='CWE-79'
                    ))
                    break

    # Check postMessage calls with wildcard origin
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 1
          AND f.callee_function IS NOT NULL
          AND (f.argument_expr = "'*'" OR f.argument_expr = '"*"')
        ORDER BY f.file, f.line
    """)

    for file, line, func, arg_expr in cursor.fetchall():
        # Filter in Python: Check if postMessage call
        if 'postMessage' not in func:
            continue

        findings.append(StandardFinding(
            rule_name='dom-xss-postmessage-wildcard',
            message='Security: postMessage with wildcard origin ("*")',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='security',
            snippet='postMessage(data, "*")',
            cwe_id='CWE-345'
        ))

    return findings


def _check_dom_purify_bypass(conn) -> list[StandardFinding]:
    """Check for potential DOMPurify bypass patterns."""
    findings = []
    cursor = conn.cursor()

    # Dangerous DOMPurify config options
    dangerous_configs = ['ALLOW_UNKNOWN_PROTOCOLS', 'ALLOW_DATA_ATTR', 'ALLOW_ARIA_ATTR']

    # Check for mutation XSS patterns
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if innerHTML with DOMPurify.sanitize
        is_innerHTML = '.innerHTML' in target
        has_DOMPurify = 'DOMPurify.sanitize' in source

        if not (is_innerHTML and has_DOMPurify):
            continue

        # Check if using dangerous DOMPurify config
        for config in dangerous_configs:
            if config in source:
                findings.append(StandardFinding(
                    rule_name='dom-xss-purify-config',
                    message=f'XSS: DOMPurify with dangerous config {config}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='xss',
                    snippet=f'DOMPurify.sanitize(input, {{ {config}: true }})',
                    cwe_id='CWE-79'
                ))

    # Check for double encoding/decoding patterns
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    # Double decode patterns to check
    double_decode_patterns = [
        ('decodeURIComponent', 'decodeURIComponent(decodeURIComponent(input))'),
        ('unescape', 'unescape(unescape(input))'),
        ('atob', 'atob(atob(input))')
    ]

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check for double decode patterns
        for pattern, snippet in double_decode_patterns:
            # Check if pattern appears twice (indicating double decode)
            if source.count(pattern) >= 2:
                findings.append(StandardFinding(
                    rule_name='dom-xss-double-decode',
                    message='XSS: Double decoding can bypass sanitization',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='xss',
                    snippet=snippet,
                    cwe_id='CWE-79'
                ))
                break  # Only report once per line

    return findings


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_dom_xss(context)