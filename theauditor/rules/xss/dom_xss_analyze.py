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


def find_dom_xss(context: StandardRuleContext) -> List[StandardFinding]:
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


def _check_direct_dom_flows(conn) -> List[StandardFinding]:
    """Check for direct data flows from sources to sinks."""
    findings = []
    cursor = conn.cursor()

    # Check assignments from DOM sources to dangerous sinks
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.file LIKE '%.js' OR a.file LIKE '%.ts'
           OR a.file LIKE '%.jsx' OR a.file LIKE '%.tsx'
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Check if source contains DOM XSS source
        source_found = None
        for dom_source in DOM_XSS_SOURCES:
            if dom_source in (source or ''):
                source_found = dom_source
                break

        # Check if target is a dangerous sink
        sink_found = None
        for dom_sink in DOM_XSS_SINKS:
            if dom_sink in (target or ''):
                sink_found = dom_sink
                break

        if source_found and sink_found:
            # Direct flow from source to sink
            findings.append(StandardFinding(
                rule_name='dom-xss-direct-flow',
                message=f'DOM XSS: Direct flow from {source_found} to {sink_found}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = {source[:60]}...' if len(source or '') > 60 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # Check function calls with DOM sources as arguments to sinks
    for sink in DOM_XSS_SINKS:
        if '.' in sink:
            continue  # Skip property sinks for this check

        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'%{sink}%'])

        for file, line, func, args in cursor.fetchall():
            # Check if args contain DOM source
            for source in DOM_XSS_SOURCES:
                if source in (args or ''):
                    findings.append(StandardFinding(
                        rule_name='dom-xss-sink-call',
                        message=f'DOM XSS: {source} passed to {func}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='xss',
                        snippet=f'{func}({source})',
                        cwe_id='CWE-79'
                    ))
                    break

    return findings


def _check_url_manipulation(conn) -> List[StandardFinding]:
    """Check for URL-based DOM XSS."""
    findings = []
    cursor = conn.cursor()

    # Check location assignments with user input
    location_sinks = ['location.href', 'location.replace', 'location.assign', 'window.location']

    for sink in location_sinks:
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.target_var LIKE ?
            ORDER BY a.file, a.line
        """, [f'%{sink}%'])

        for file, line, target, source in cursor.fetchall():
            # Check for URL sources
            has_url_source = any(s in (source or '') for s in [
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
                    snippet=f'{target} = {source[:60]}...' if len(source or '') > 60 else f'{target} = {source}',
                    cwe_id='CWE-601'
                ))

            # Check for javascript: protocol
            if 'javascript:' in (source or ''):
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


def _check_event_handler_injection(conn) -> List[StandardFinding]:
    """Check for event handler injection vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Event handler attributes
    event_handlers = [
        'onclick', 'onmouseover', 'onmouseout', 'onload', 'onerror',
        'onfocus', 'onblur', 'onchange', 'onsubmit', 'onkeydown',
        'onkeyup', 'onkeypress', 'ondblclick', 'onmousedown',
        'onmouseup', 'onmousemove', 'oncontextmenu'
    ]

    # Check setAttribute with event handlers
    for handler in event_handlers:
        cursor.execute("""
            SELECT f1.file, f1.line, f2.argument_expr
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
            WHERE f1.callee_function LIKE '%.setAttribute%'
              AND f1.argument_index = 0
              AND f1.argument_expr LIKE ?
              AND f2.argument_index = 1
            ORDER BY f1.file, f1.line
        """, [f'%{handler}%'])

        for file, line, handler_value in cursor.fetchall():
            has_user_input = any(s in (handler_value or '') for s in DOM_XSS_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='dom-xss-event-handler',
                    message=f'XSS: Event handler {handler} with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='xss',
                    snippet=f'setAttribute("{handler}", userInput)',
                    cwe_id='CWE-79'
                ))

    # Check for dynamic event listener addition
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%.addEventListener%'
          AND f.argument_index = 1
        ORDER BY f.file, f.line
    """)

    for file, line, listener_func in cursor.fetchall():
        # Check if listener is created from string (eval-like)
        if 'Function' in (listener_func or '') or 'eval' in (listener_func or ''):
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


def _check_dom_clobbering(conn) -> List[StandardFinding]:
    """Check for DOM clobbering vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check for unsafe ID/name attribute usage
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%window[%'
               OR a.source_expr LIKE '%document[%')
          AND a.source_expr NOT LIKE '%window["_%'
          AND a.source_expr NOT LIKE '%document["_%'
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check if accessing user-controlled property
        if not any(safe in source for safe in ['localStorage', 'sessionStorage', 'location']):
            findings.append(StandardFinding(
                rule_name='dom-clobbering',
                message='DOM Clobbering: Unsafe window/document property access',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=source[:80] if len(source or '') > 80 else source,
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
              AND a.source_expr LIKE '%getElementById%'
              AND a.source_expr NOT LIKE '%?%'
              AND a.source_expr NOT LIKE '%&&%'
        """, [file, line])

        if cursor.fetchone():
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


def _check_client_side_templates(conn) -> List[StandardFinding]:
    """Check for client-side template injection."""
    findings = []
    cursor = conn.cursor()

    # Check for template literal usage with innerHTML
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%.innerHTML%'
          AND a.source_expr LIKE '%`%'
          AND a.source_expr LIKE '%${%'
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Check for DOM sources in template
        has_dom_source = any(s in (source or '') for s in DOM_XSS_SOURCES)

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
    template_libs = ['Handlebars', 'Mustache', 'doT', 'ejs', 'underscore', 'lodash']

    for lib in template_libs:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'{lib}.compile%'])

        for file, line, func, template in cursor.fetchall():
            has_user_input = any(s in (template or '') for s in DOM_XSS_SOURCES)

            if has_user_input:
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


def _check_web_messaging(conn) -> List[StandardFinding]:
    """Check for postMessage XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check message event handlers
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%.addEventListener%'
          AND f.argument_index = 0
          AND f.argument_expr LIKE '%message%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, event_type in cursor.fetchall():
        # Check if handler validates origin
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments a
            WHERE a.file = ?
              AND a.line > ?
              AND a.line < ? + 30
              AND (a.source_expr LIKE '%event.origin%'
                   OR a.source_expr LIKE '%e.origin%')
        """, [file, line, line])

        has_origin_check = cursor.fetchone()[0] > 0

        if not has_origin_check:
            # Check if message data is used dangerously
            cursor.execute("""
                SELECT a.target_var, a.source_expr
                FROM assignments a
                WHERE a.file = ?
                  AND a.line > ?
                  AND a.line < ? + 30
                  AND (a.source_expr LIKE '%event.data%'
                       OR a.source_expr LIKE '%e.data%')
                  AND (a.target_var LIKE '%.innerHTML%'
                       OR a.source_expr LIKE '%eval%')
            """, [file, line, line])

            dangerous_use = cursor.fetchone()
            if dangerous_use:
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

    # Check postMessage calls with wildcard origin
    cursor.execute("""
        SELECT f.file, f.line
        FROM function_call_args f
        WHERE f.callee_function LIKE '%postMessage%'
          AND f.argument_index = 1
          AND (f.argument_expr = "'*'" OR f.argument_expr = '"*"')
        ORDER BY f.file, f.line
    """)

    for file, line in cursor.fetchall():
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


def _check_dom_purify_bypass(conn) -> List[StandardFinding]:
    """Check for potential DOMPurify bypass patterns."""
    findings = []
    cursor = conn.cursor()

    # Check for mutation XSS patterns
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%.innerHTML%'
          AND a.source_expr LIKE '%DOMPurify.sanitize%'
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check if using dangerous DOMPurify config
        dangerous_configs = ['ALLOW_UNKNOWN_PROTOCOLS', 'ALLOW_DATA_ATTR', 'ALLOW_ARIA_ATTR']

        for config in dangerous_configs:
            if config in (source or ''):
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
        WHERE (a.source_expr LIKE '%decodeURIComponent%decodeURIComponent%'
               OR a.source_expr LIKE '%unescape%unescape%'
               OR a.source_expr LIKE '%atob%atob%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='dom-xss-double-decode',
            message='XSS: Double decoding can bypass sanitization',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='xss',
            snippet='decodeURIComponent(decodeURIComponent(input))',
            cwe_id='CWE-79'
        ))

    return findings