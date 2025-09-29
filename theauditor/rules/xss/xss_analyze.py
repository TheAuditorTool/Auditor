"""XSS Detection - Framework-Aware Golden Standard Implementation.

CRITICAL: This module queries frameworks table to eliminate false positives.
Uses frozensets for O(1) lookups following Golden Standard pattern.

NO AST TRAVERSAL. NO FILE I/O. Pure database queries.
"""

import sqlite3
from typing import List, Set, FrozenSet
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# ============================================================================
# GOLDEN STANDARD: Frozensets for O(1) lookups
# ============================================================================

# Framework-specific SAFE sinks (these auto-escape/encode)
EXPRESS_SAFE_SINKS = frozenset([
    'res.json', 'res.jsonp', 'res.status().json',
    'response.json', 'response.jsonp', 'response.status().json'
])

REACT_AUTO_ESCAPED = frozenset([
    'React.createElement', 'jsx', 'JSXElement',
    'createElement', 'cloneElement'
])

VUE_AUTO_ESCAPED = frozenset([
    'createVNode', 'h', 'createElementVNode',
    'createTextVNode', 'createCommentVNode'
])

ANGULAR_AUTO_ESCAPED = frozenset([
    'sanitize', 'DomSanitizer.sanitize',
    'bypassSecurityTrustHtml'  # Actually this is dangerous, will flag it
])

# Universal DANGEROUS sinks (always risky)
UNIVERSAL_DANGEROUS_SINKS = frozenset([
    'innerHTML', 'outerHTML', 'document.write', 'document.writeln',
    'eval', 'Function', 'setTimeout', 'setInterval', 'execScript',
    'insertAdjacentHTML', 'createContextualFragment', 'parseFromString',
    'writeln', 'documentElement.innerHTML'
])

# User input sources (taint sources)
USER_INPUT_SOURCES = frozenset([
    'req.body', 'req.query', 'req.params', 'req.cookies', 'req.headers',
    'request.body', 'request.query', 'request.params', 'request.cookies',
    'location.search', 'location.hash', 'location.href', 'location.pathname',
    'URLSearchParams', 'searchParams', 'document.cookie',
    'localStorage.getItem', 'sessionStorage.getItem',
    'window.name', 'document.referrer', 'document.URL',
    '.value', 'event.data', 'message.data', 'postMessage'
])

# Common sanitizers (if these are used, likely safe)
COMMON_SANITIZERS = frozenset([
    'DOMPurify.sanitize', 'sanitize', 'escape', 'escapeHtml',
    'encodeURIComponent', 'encodeURI', 'encodeHTML',
    'Handlebars.escapeExpression', 'lodash.escape', '_.escape',
    'he.encode', 'entities.encode', 'htmlspecialchars',
    'validator.escape', 'xss.clean', 'sanitize-html'
])


def find_xss_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Main XSS detection with framework awareness.

    Returns:
        List of XSS findings with drastically reduced false positives
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)

    try:
        # 1. Get framework context FIRST (critical for accuracy)
        detected_frameworks = _get_detected_frameworks(conn)
        safe_sinks = _build_framework_safe_sinks(conn, detected_frameworks)

        # 2. Run XSS checks with framework context
        findings.extend(_check_response_methods(conn, safe_sinks, detected_frameworks))
        findings.extend(_check_dom_manipulation(conn, safe_sinks))
        findings.extend(_check_dangerous_functions(conn))
        findings.extend(_check_react_dangerouslysetinnerhtml(conn))
        findings.extend(_check_vue_vhtml_directive(conn))
        findings.extend(_check_angular_bypass(conn))
        findings.extend(_check_jquery_methods(conn))
        findings.extend(_check_template_injection(conn, detected_frameworks))
        findings.extend(_check_direct_user_input_to_sink(conn, safe_sinks))
        findings.extend(_check_url_javascript_protocol(conn))
        findings.extend(_check_postmessage_xss(conn))

    finally:
        conn.close()

    return findings


def _get_detected_frameworks(conn) -> Set[str]:
    """Query frameworks table for detected frameworks."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM frameworks WHERE is_primary = 1")
    frameworks = {row[0].lower() for row in cursor.fetchall() if row[0]}

    # Also check for secondary frameworks
    cursor.execute("SELECT DISTINCT name FROM frameworks WHERE is_primary = 0")
    frameworks.update(row[0].lower() for row in cursor.fetchall() if row[0])

    return frameworks


def _build_framework_safe_sinks(conn, frameworks: Set[str]) -> FrozenSet[str]:
    """Build comprehensive safe sink list based on detected frameworks."""
    safe_sinks = set()

    # Add framework-specific safe sinks
    if 'express' in frameworks or 'express.js' in frameworks:
        safe_sinks.update(EXPRESS_SAFE_SINKS)

    if 'react' in frameworks:
        safe_sinks.update(REACT_AUTO_ESCAPED)

    if 'vue' in frameworks or 'vuejs' in frameworks:
        safe_sinks.update(VUE_AUTO_ESCAPED)

    if 'angular' in frameworks:
        # Note: bypassSecurityTrustHtml is NOT safe, don't add it
        safe_sinks.update(s for s in ANGULAR_AUTO_ESCAPED if 'bypass' not in s.lower())

    # Query framework_safe_sinks table for additional safe sinks
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT fss.sink_pattern
        FROM framework_safe_sinks fss
        JOIN frameworks f ON fss.framework_id = f.id
        WHERE fss.is_safe = 1
    """)

    for row in cursor.fetchall():
        if row[0]:
            safe_sinks.add(row[0])

    return frozenset(safe_sinks)


# ============================================================================
# CHECK 1: Response Methods (Express/Node.js)
# ============================================================================

def _check_response_methods(conn, safe_sinks: FrozenSet[str], frameworks: Set[str]) -> List[StandardFinding]:
    """Check response methods with framework awareness."""
    findings = []
    cursor = conn.cursor()

    # Query all response method calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE 'res.%'
               OR f.callee_function LIKE 'response.%')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # CRITICAL: Skip if it's a framework-safe sink
        if func in safe_sinks:
            continue

        # Skip res.json/jsonp in Express (they're safe!)
        if ('express' in frameworks or 'express.js' in frameworks):
            if func in EXPRESS_SAFE_SINKS:
                continue

        # Check if user input in arguments (potential XSS)
        has_user_input = any(source in (args or '') for source in USER_INPUT_SOURCES)
        has_sanitizer = any(san in (args or '') for san in COMMON_SANITIZERS)

        if has_user_input and not has_sanitizer:
            # Determine severity based on sink danger level
            if func in ['res.send', 'res.write', 'response.send', 'response.write']:
                severity = Severity.HIGH
            elif func in ['res.end', 'response.end']:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(StandardFinding(
                rule_name='xss-response-unsafe',
                message=f'XSS: {func} with user input (not JSON-encoded)',
                file_path=file,
                line=line,
                severity=severity,
                category='xss',
                snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                cwe_id='CWE-79'
            ))

    return findings


# ============================================================================
# CHECK 2: DOM Manipulation (innerHTML, document.write)
# ============================================================================

def _check_dom_manipulation(conn, safe_sinks: FrozenSet[str]) -> List[StandardFinding]:
    """Check dangerous DOM manipulation with user input."""
    findings = []
    cursor = conn.cursor()

    # Check innerHTML/outerHTML assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%.innerHTML%'
               OR a.target_var LIKE '%.outerHTML%')
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Check for user input
        has_user_input = any(src in (source or '') for src in USER_INPUT_SOURCES)
        has_sanitizer = any(san in (source or '') for san in COMMON_SANITIZERS)

        if has_user_input and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='xss-dom-innerhtml',
                message=f'XSS: {target} assigned user input without sanitization',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = {source[:60]}...' if len(source or '') > 60 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # Check document.write/writeln
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('document.write', 'document.writeln')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)
        has_sanitizer = any(san in (args or '') for san in COMMON_SANITIZERS)

        if has_user_input and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='xss-document-write',
                message=f'XSS: {func} with user input is extremely dangerous',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                cwe_id='CWE-79'
            ))

    # Check insertAdjacentHTML
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%insertAdjacentHTML%'
          AND f.argument_index = 1
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)
        has_sanitizer = any(san in (args or '') for san in COMMON_SANITIZERS)

        if has_user_input and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='xss-insert-adjacent-html',
                message=f'XSS: {func} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{func}(_, {args[:60]}...)' if len(args or '') > 60 else f'{func}(_, {args})',
                cwe_id='CWE-79'
            ))

    return findings


# ============================================================================
# CHECK 3: Dangerous Functions (eval, Function, setTimeout with strings)
# ============================================================================

def _check_dangerous_functions(conn) -> List[StandardFinding]:
    """Check eval() and similar dangerous functions."""
    findings = []
    cursor = conn.cursor()

    # Check eval, Function constructor, setTimeout/setInterval with strings
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('eval', 'Function', 'execScript')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='xss-code-injection',
                message=f'Code Injection: {func} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                cwe_id='CWE-94'
            ))

    # Check setTimeout/setInterval with string arguments (code execution)
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('setTimeout', 'setInterval')
          AND f.argument_index = 0
          AND (f.argument_expr LIKE '"%' OR f.argument_expr LIKE "'%")
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # String argument to setTimeout/setInterval is evaluated
        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='xss-timeout-eval',
                message=f'Code Injection: {func} with string containing user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                snippet=f'{func}("{args[:40]}...", ...)' if len(args or '') > 40 else f'{func}("{args}", ...)',
                cwe_id='CWE-94'
            ))

    return findings


# ============================================================================
# CHECK 4: React dangerouslySetInnerHTML
# ============================================================================

def _check_react_dangerouslysetinnerhtml(conn) -> List[StandardFinding]:
    """Check React dangerouslySetInnerHTML with user input."""
    findings = []
    cursor = conn.cursor()

    # Check assignments containing dangerouslySetInnerHTML
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%dangerouslySetInnerHTML%'
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check if user input is involved
        has_user_input = any(src in (source or '') for src in USER_INPUT_SOURCES)
        has_props = 'props.' in (source or '') or 'this.props' in (source or '')
        has_state = 'state.' in (source or '') or 'this.state' in (source or '')
        has_sanitizer = any(san in (source or '') for san in COMMON_SANITIZERS)

        if (has_user_input or has_props or has_state) and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='xss-react-dangerous-html',
                message='XSS: dangerouslySetInnerHTML with potentially unsafe input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=source[:100] if len(source or '') > 100 else source,
                cwe_id='CWE-79'
            ))

    # Also check React components table if available
    cursor.execute("""
        SELECT r.file, r.start_line
        FROM react_components r
        WHERE r.has_jsx = 1
        LIMIT 1
    """)

    # If we have React component data, do deeper analysis
    if cursor.fetchone():
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE '%dangerouslySetInnerHTML%'
               OR f.param_name = 'dangerouslySetInnerHTML'
            ORDER BY f.file, f.line
        """)

        for file, line, args in cursor.fetchall():
            if args and '__html' in args:
                has_user_input = any(src in args for src in USER_INPUT_SOURCES)
                if has_user_input:
                    findings.append(StandardFinding(
                        rule_name='xss-react-dangerous-prop',
                        message='XSS: React dangerouslySetInnerHTML prop with user input',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='xss',
                        snippet=f'dangerouslySetInnerHTML={{__html: ...}}',
                        cwe_id='CWE-79'
                    ))

    return findings


# ============================================================================
# CHECK 5: Vue v-html directive
# ============================================================================

def _check_vue_vhtml_directive(conn) -> List[StandardFinding]:
    """Check Vue v-html directives with user input."""
    findings = []
    cursor = conn.cursor()

    # First check if we have Vue directive data
    cursor.execute("SELECT COUNT(*) FROM vue_directives LIMIT 1")
    has_vue_data = cursor.fetchone()[0] > 0

    if has_vue_data:
        # Use Vue-specific tables
        cursor.execute("""
            SELECT vd.file, vd.line, vd.directive_name, vd.expression
            FROM vue_directives vd
            WHERE vd.directive_name = 'v-html'
            ORDER BY vd.file, vd.line
        """)

        for file, line, directive, expression in cursor.fetchall():
            # Check if expression contains user input
            has_user_input = any(src in (expression or '') for src in USER_INPUT_SOURCES)
            has_route = '$route' in (expression or '')
            has_props = 'props' in (expression or '')

            if has_user_input or has_route or has_props:
                findings.append(StandardFinding(
                    rule_name='xss-vue-vhtml',
                    message='XSS: v-html directive with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='xss',
                    snippet=f'v-html="{expression[:60]}"' if len(expression or '') > 60 else f'v-html="{expression}"',
                    cwe_id='CWE-79'
                ))
    else:
        # Fallback: Check assignments for v-html pattern
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%v-html%'
            ORDER BY a.file, a.line
        """)

        for file, line, source in cursor.fetchall():
            has_user_input = any(src in (source or '') for src in USER_INPUT_SOURCES)
            has_route = '$route' in (source or '')

            if has_user_input or has_route:
                findings.append(StandardFinding(
                    rule_name='xss-vue-vhtml-fallback',
                    message='XSS: v-html with user input detected',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='xss',
                    snippet=source[:100] if len(source or '') > 100 else source,
                    cwe_id='CWE-79'
                ))

    return findings


# ============================================================================
# CHECK 6: Angular bypassSecurityTrust
# ============================================================================

def _check_angular_bypass(conn) -> List[StandardFinding]:
    """Check Angular security bypass methods."""
    findings = []
    cursor = conn.cursor()

    bypass_methods = [
        'bypassSecurityTrustHtml',
        'bypassSecurityTrustScript',
        'bypassSecurityTrustUrl',
        'bypassSecurityTrustResourceUrl'
    ]

    for method in bypass_methods:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'%{method}%'])

        for file, line, func, args in cursor.fetchall():
            has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='xss-angular-bypass',
                    message=f'XSS: Angular {method} with user input bypasses security',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='xss',
                    snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                    cwe_id='CWE-79'
                ))

    return findings


# ============================================================================
# CHECK 7: jQuery Methods
# ============================================================================

def _check_jquery_methods(conn) -> List[StandardFinding]:
    """Check jQuery DOM manipulation methods."""
    findings = []
    cursor = conn.cursor()

    # jQuery methods that can cause XSS
    jquery_dangerous_methods = [
        '.html', '.append', '.prepend', '.after', '.before',
        '.replaceWith', '.wrap', '.wrapInner'
    ]

    for method in jquery_dangerous_methods:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'%{method}%'])

        for file, line, func, args in cursor.fetchall():
            # Check if it's actually jQuery ($ or jQuery prefix)
            if '$' not in func and 'jQuery' not in func:
                continue

            has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)
            has_sanitizer = any(san in (args or '') for san in COMMON_SANITIZERS)

            if has_user_input and not has_sanitizer:
                findings.append(StandardFinding(
                    rule_name='xss-jquery-dom',
                    message=f'XSS: jQuery {method} with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                    cwe_id='CWE-79'
                ))

    return findings


# ============================================================================
# CHECK 8: Template Injection
# ============================================================================

def _check_template_injection(conn, frameworks: Set[str]) -> List[StandardFinding]:
    """Check for template injection vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Python template injection
    if 'flask' in frameworks or 'django' in frameworks:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('render_template_string', 'Template',
                                       'jinja2.Template', 'from_string')
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """)

        for file, line, func, args in cursor.fetchall():
            has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='xss-template-injection',
                    message=f'Template Injection: {func} with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    snippet=f'{func}({args[:60]}...)' if len(args or '') > 60 else f'{func}({args})',
                    cwe_id='CWE-94'
                ))

    # EJS template injection (Node.js)
    if 'express' in frameworks:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IN ('ejs.render', 'ejs.compile', 'res.render')
              AND f.argument_expr LIKE '%<%-%'
            ORDER BY f.file, f.line
        """)

        for file, line, func, args in cursor.fetchall():
            # <%- is unescaped in EJS
            findings.append(StandardFinding(
                rule_name='xss-ejs-unescaped',
                message='XSS: EJS unescaped output <%- detected',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}(... <%- ... %> ...)',
                cwe_id='CWE-79'
            ))

    return findings


# ============================================================================
# CHECK 9: Direct User Input to Sink
# ============================================================================

def _check_direct_user_input_to_sink(conn, safe_sinks: FrozenSet[str]) -> List[StandardFinding]:
    """Check for direct user input passed to dangerous sinks."""
    findings = []
    cursor = conn.cursor()

    # Find direct taint source to sink flows
    for dangerous_sink in UNIVERSAL_DANGEROUS_SINKS:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'%{dangerous_sink}%'])

        for file, line, func, args in cursor.fetchall():
            # Skip if it's a safe sink (shouldn't happen but be defensive)
            if func in safe_sinks:
                continue

            # Direct check for user input patterns
            for source in USER_INPUT_SOURCES:
                if source in (args or ''):
                    findings.append(StandardFinding(
                        rule_name='xss-direct-taint',
                        message=f'XSS: Direct user input ({source}) to dangerous sink ({dangerous_sink})',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='xss',
                        snippet=f'{func}({source}...)',
                        cwe_id='CWE-79'
                    ))
                    break

    return findings


# ============================================================================
# CHECK 10: JavaScript Protocol in URLs
# ============================================================================

def _check_url_javascript_protocol(conn) -> List[StandardFinding]:
    """Check for javascript: protocol in URLs."""
    findings = []
    cursor = conn.cursor()

    # Check href and src assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%.href%' OR a.target_var LIKE '%.src%')
          AND (a.source_expr LIKE '%javascript:%'
               OR a.source_expr LIKE '%data:text/html%')
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        has_user_input = any(src in (source or '') for src in USER_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='xss-javascript-protocol',
                message='XSS: javascript: or data: URL with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{target} = {source[:60]}...' if len(source or '') > 60 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # Check setAttribute for href/src
    cursor.execute("""
        SELECT f1.file, f1.line, f1.argument_expr as attr_name, f2.argument_expr as attr_value
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
        WHERE f1.callee_function LIKE '%.setAttribute%'
          AND f1.argument_index = 0
          AND f2.callee_function LIKE '%.setAttribute%'
          AND f2.argument_index = 1
          AND f1.argument_expr IN ("'href'", '"href"', "'src'", '"src"')
        ORDER BY f1.file, f1.line
    """)

    for file, line, attr, value in cursor.fetchall():
        if 'javascript:' in (value or '') or 'data:text/html' in (value or ''):
            has_user_input = any(src in value for src in USER_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='xss-set-attribute-protocol',
                    message=f'XSS: setAttribute({attr}) with javascript: URL',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet=f'setAttribute({attr}, javascript:...)',
                    cwe_id='CWE-79'
                ))

    return findings


# ============================================================================
# CHECK 11: PostMessage XSS
# ============================================================================

def _check_postmessage_xss(conn) -> List[StandardFinding]:
    """Check for PostMessage XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check postMessage with targetOrigin '*'
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%postMessage%'
          AND f.argument_index = 1
          AND (f.argument_expr = "'*'" OR f.argument_expr = '"*"')
        ORDER BY f.file, f.line
    """)

    for file, line, func, target_origin in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-postmessage-origin',
            message="XSS: postMessage with targetOrigin '*' allows any origin",
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{func}(data, "*")',
            cwe_id='CWE-79'
        ))

    # Check message event handlers without origin validation
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%event.data%'
               OR a.source_expr LIKE '%message.data%')
          AND (a.target_var LIKE '%.innerHTML%'
               OR a.source_expr LIKE '%eval(%'
               OR a.source_expr LIKE '%Function(%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check if there's origin validation
        # This is a heuristic - look for event.origin check nearby
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments a2
            WHERE a2.file = ?
              AND ABS(a2.line - ?) <= 5
              AND (a2.source_expr LIKE '%event.origin%'
                   OR a2.source_expr LIKE '%message.origin%')
        """, [file, line])

        has_origin_check = cursor.fetchone()[0] > 0

        if not has_origin_check:
            findings.append(StandardFinding(
                rule_name='xss-postmessage-no-validation',
                message='XSS: PostMessage data used without origin validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=source[:80] if len(source or '') > 80 else source,
                cwe_id='CWE-79'
            ))

    return findings