"""XSS Detection - Framework-Aware Golden Standard Implementation.

CRITICAL: This module queries frameworks table to eliminate false positives.
Uses frozensets for O(1) lookups following Golden Standard pattern.

NO AST TRAVERSAL. NO FILE I/O. Pure database queries.
"""


import sqlite3
from typing import List, FrozenSet, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="xss_core",
    category="xss",
    target_extensions=['.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.html'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.test.js', '*.spec.js'],
    requires_jsx_pass=False
)


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


# NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
# If tables are missing, the rule MUST crash to expose indexer bugs.


def find_xss_issues(context: StandardRuleContext) -> list[StandardFinding]:
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


def _get_detected_frameworks(conn) -> set[str]:
    """Query frameworks table for detected frameworks."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM frameworks WHERE is_primary = 1")
    frameworks = {row[0].lower() for row in cursor.fetchall() if row[0]}

    # Also check for secondary frameworks
    cursor.execute("SELECT DISTINCT name FROM frameworks WHERE is_primary = 0")
    frameworks.update(row[0].lower() for row in cursor.fetchall() if row[0])

    return frameworks


def _build_framework_safe_sinks(conn, frameworks: set[str]) -> frozenset[str]:
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

def _check_response_methods(conn, safe_sinks: frozenset[str], frameworks: set[str]) -> list[StandardFinding]:
    """Check response methods with framework awareness."""
    findings = []
    cursor = conn.cursor()

    # Query all response method calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if function is a response method
        is_response_method = func.startswith('res.') or func.startswith('response.')
        if not is_response_method:
            continue

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

def _check_dom_manipulation(conn, safe_sinks: frozenset[str]) -> list[StandardFinding]:
    """Check dangerous DOM manipulation with user input."""
    findings = []
    cursor = conn.cursor()

    # Check innerHTML/outerHTML assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check for innerHTML or outerHTML
        has_dangerous_property = '.innerHTML' in target or '.outerHTML' in target
        if not has_dangerous_property:
            continue

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
        WHERE f.argument_index = 1
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check for insertAdjacentHTML
        if 'insertAdjacentHTML' not in func:
            continue

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

def _check_dangerous_functions(conn) -> list[StandardFinding]:
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
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if argument is a string literal
        is_string_literal = args.startswith('"') or args.startswith("'")
        if not is_string_literal:
            continue

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

def _check_react_dangerouslysetinnerhtml(conn) -> list[StandardFinding]:
    """Check React dangerouslySetInnerHTML with user input."""
    findings = []
    cursor = conn.cursor()

    # Check assignments containing dangerouslySetInnerHTML
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check for dangerouslySetInnerHTML
        if 'dangerouslySetInnerHTML' not in (source or ''):
            continue

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
            SELECT f.file, f.line, f.callee_function, f.param_name, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function IS NOT NULL
               OR f.param_name IS NOT NULL
            ORDER BY f.file, f.line
        """)

        for file, line, callee, param, args in cursor.fetchall():
            # Filter in Python: Check for dangerouslySetInnerHTML
            is_dangerous = ('dangerouslySetInnerHTML' in (callee or '')) or (param == 'dangerouslySetInnerHTML')
            if not is_dangerous:
                continue

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

def _check_vue_vhtml_directive(conn) -> list[StandardFinding]:
    """Check Vue v-html directives with user input.

    NO FALLBACKS. Schema contract guarantees vue_directives table exists.
    If table missing, rule MUST crash to expose indexer bug.
    """
    findings = []
    cursor = conn.cursor()

    # Query vue_directives table - assume it exists per schema contract
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

    return findings


# ============================================================================
# CHECK 6: Angular bypassSecurityTrust
# ============================================================================

def _check_angular_bypass(conn) -> list[StandardFinding]:
    """Check Angular security bypass methods."""
    findings = []
    cursor = conn.cursor()

    bypass_methods = [
        'bypassSecurityTrustHtml',
        'bypassSecurityTrustScript',
        'bypassSecurityTrustUrl',
        'bypassSecurityTrustResourceUrl'
    ]

    # Fetch all function calls, filter in Python
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if function contains any bypass method
        matched_method = None
        for method in bypass_methods:
            if method in func:
                matched_method = method
                break

        if not matched_method:
            continue

        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='xss-angular-bypass',
                message=f'XSS: Angular {matched_method} with user input bypasses security',
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

def _check_jquery_methods(conn) -> list[StandardFinding]:
    """Check jQuery DOM manipulation methods."""
    findings = []
    cursor = conn.cursor()

    # jQuery methods that can cause XSS
    jquery_dangerous_methods = [
        '.html', '.append', '.prepend', '.after', '.before',
        '.replaceWith', '.wrap', '.wrapInner'
    ]

    # Fetch all function calls, filter in Python
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if it's actually jQuery ($ or jQuery prefix)
        if '$' not in func and 'jQuery' not in func:
            continue

        # Filter in Python: Check if function contains any dangerous jQuery method
        matched_method = None
        for method in jquery_dangerous_methods:
            if method in func:
                matched_method = method
                break

        if not matched_method:
            continue

        has_user_input = any(src in (args or '') for src in USER_INPUT_SOURCES)
        has_sanitizer = any(san in (args or '') for san in COMMON_SANITIZERS)

        if has_user_input and not has_sanitizer:
            findings.append(StandardFinding(
                rule_name='xss-jquery-dom',
                message=f'XSS: jQuery {matched_method} with user input',
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

def _check_template_injection(conn, frameworks: set[str]) -> list[StandardFinding]:
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
              AND f.argument_expr IS NOT NULL
            ORDER BY f.file, f.line
        """)

        for file, line, func, args in cursor.fetchall():
            # Filter in Python: Check for unescaped EJS syntax
            if '<%-%' not in args:
                continue

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

def _check_direct_user_input_to_sink(conn, safe_sinks: frozenset[str]) -> list[StandardFinding]:
    """Check for direct user input passed to dangerous sinks."""
    findings = []
    cursor = conn.cursor()

    # Find direct taint source to sink flows
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 0
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Skip if it's a safe sink (shouldn't happen but be defensive)
        if func in safe_sinks:
            continue

        # Filter in Python: Check if function contains any dangerous sink
        matched_sink = None
        for dangerous_sink in UNIVERSAL_DANGEROUS_SINKS:
            if dangerous_sink in func:
                matched_sink = dangerous_sink
                break

        if not matched_sink:
            continue

        # Direct check for user input patterns
        for source in USER_INPUT_SOURCES:
            if source in (args or ''):
                findings.append(StandardFinding(
                    rule_name='xss-direct-taint',
                    message=f'XSS: Direct user input ({source}) to dangerous sink ({matched_sink})',
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

def _check_url_javascript_protocol(conn) -> list[StandardFinding]:
    """Check for javascript: protocol in URLs."""
    findings = []
    cursor = conn.cursor()

    # Check href and src assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check for href or src assignment
        is_url_property = '.href' in target or '.src' in target
        if not is_url_property:
            continue

        # Filter in Python: Check for javascript: or data: protocol
        has_dangerous_protocol = 'javascript:' in source or 'data:text/html' in source
        if not has_dangerous_protocol:
            continue

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
        SELECT f1.file, f1.line, f1.callee_function, f1.argument_expr as attr_name, f2.argument_expr as attr_value
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file AND f1.line = f2.line
        WHERE f1.argument_index = 0
          AND f2.argument_index = 1
          AND f1.argument_expr IN ("'href'", '"href"', "'src'", '"src"')
          AND f1.callee_function IS NOT NULL
          AND f2.callee_function IS NOT NULL
        ORDER BY f1.file, f1.line
    """)

    for file, line, callee, attr, value in cursor.fetchall():
        # Filter in Python: Check if both callees are setAttribute
        if 'setAttribute' not in callee:
            continue

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

def _check_postmessage_xss(conn) -> list[StandardFinding]:
    """Check for PostMessage XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check postMessage with targetOrigin '*'
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_index = 1
          AND (f.argument_expr = "'*'" OR f.argument_expr = '"*"')
          AND f.callee_function IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, target_origin in cursor.fetchall():
        # Filter in Python: Check for postMessage
        if 'postMessage' not in func:
            continue

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
    message_data_patterns = ['event.data', 'message.data']
    dangerous_operations = ['.innerHTML', 'eval(', 'Function(']

    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if source contains message data
        has_message_data = any(pattern in source for pattern in message_data_patterns)
        if not has_message_data:
            continue

        # Filter in Python: Check if target or source contains dangerous operation
        has_dangerous_op = any(op in (target or '') for op in dangerous_operations) or \
                          any(op in source for op in dangerous_operations)
        if not has_dangerous_op:
            continue

        # Check if there's origin validation
        # This is a heuristic - look for event.origin check nearby
        origin_patterns = ['event.origin', 'message.origin']

        cursor.execute("""
            SELECT source_expr
            FROM assignments
            WHERE file = ?
              AND ABS(line - ?) <= 5
              AND source_expr IS NOT NULL
        """, [file, line])

        has_origin_check = False
        for (nearby_source,) in cursor.fetchall():
            if any(pattern in nearby_source for pattern in origin_patterns):
                has_origin_check = True
                break

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


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_xss_issues(context)
