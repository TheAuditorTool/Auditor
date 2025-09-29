"""XSS (Cross-Site Scripting) Vulnerability Analyzer - Pure Database Implementation.

This module detects XSS vulnerabilities using ONLY indexed database data.
NO AST TRAVERSAL. NO FILE I/O. Just efficient SQL queries.

Detects:
- Direct user input in dangerous sinks (innerHTML, document.write)
- Unescaped template rendering
- React dangerouslySetInnerHTML with user data
- Vue v-html directives with user input
- Response methods with unsanitized user input
- eval() and Function() with user data
- jQuery html() methods with user input
- Direct DOM manipulation with tainted data
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_xss_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect XSS vulnerabilities using indexed database data.
    
    Returns:
        List of XSS vulnerability findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Run all XSS detection checks
        findings.extend(_find_innerhtml_xss(cursor))
        findings.extend(_find_document_write_xss(cursor))
        findings.extend(_find_response_xss(cursor))
        findings.extend(_find_eval_xss(cursor))
        findings.extend(_find_react_dangerous_html(cursor))
        findings.extend(_find_vue_vhtml(cursor))
        findings.extend(_find_jquery_html_xss(cursor))
        findings.extend(_find_template_injection(cursor))
        findings.extend(_find_url_parameter_xss(cursor))
        findings.extend(_find_cookie_xss(cursor))
        findings.extend(_find_unescaped_output(cursor))
        findings.extend(_find_dom_xss_sinks(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# CHECK 1: innerHTML XSS
# ============================================================================

def _find_innerhtml_xss(cursor) -> List[StandardFinding]:
    """Find innerHTML assignments with user input."""
    findings = []
    
    # Find innerHTML assignments with user input
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%.innerHTML'
               OR a.target_var LIKE '%.outerHTML')
          AND (a.source_expr LIKE '%req.body%'
               OR a.source_expr LIKE '%req.query%'
               OR a.source_expr LIKE '%req.params%'
               OR a.source_expr LIKE '%request.body%'
               OR a.source_expr LIKE '%request.query%'
               OR a.source_expr LIKE '%request.params%'
               OR a.source_expr LIKE '%location.search%'
               OR a.source_expr LIKE '%location.hash%'
               OR a.source_expr LIKE '%URLSearchParams%'
               OR a.source_expr LIKE '%.value%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, target, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-innerhtml',
            message=f'XSS: {target} assigned user input without sanitization',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
            cwe_id='CWE-79'
        ))
    
    # Also check function calls that set innerHTML
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%.innerHTML%'
               OR f.callee_function = 'innerHTML')
          AND (f.argument_expr LIKE '%req.%'
               OR f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%params%'
               OR f.argument_expr LIKE '%query%'
               OR f.argument_expr LIKE '%body%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-innerhtml-call',
            message=f'XSS: {func} called with user input',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 2: document.write XSS
# ============================================================================

def _find_document_write_xss(cursor) -> List[StandardFinding]:
    """Find document.write with user input."""
    findings = []
    
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('document.write', 'document.writeln')
          AND (f.argument_expr LIKE '%req.%'
               OR f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%location.%'
               OR f.argument_expr LIKE '%URLSearchParams%'
               OR f.argument_expr LIKE '%cookie%'
               OR f.argument_expr LIKE '%.value%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-document-write',
            message=f'XSS: {func} with user input is extremely dangerous',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 3: Response XSS (res.send, res.write)
# ============================================================================

def _find_response_xss(cursor) -> List[StandardFinding]:
    """Find server responses with unsanitized user input."""
    findings = []
    
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.send', 'res.write', 'res.end', 
                                   'response.send', 'response.write', 'response.end')
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%'
               OR f.argument_expr LIKE '%request.body%'
               OR f.argument_expr LIKE '%request.query%'
               OR f.argument_expr LIKE '%request.params%')
          AND f.argument_expr NOT LIKE '%escape%'
          AND f.argument_expr NOT LIKE '%sanitize%'
          AND f.argument_expr NOT LIKE '%encode%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-response',
            message=f'XSS: {func} sends user input without escaping',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    # Check for template rendering with user data
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('res.render', 'response.render', 'render')
          AND f.param_name = 'arg1'
          AND (f.argument_expr LIKE '%req.body%'
               OR f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-template-render',
            message='XSS: Template rendering with unsanitized user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 4: eval() XSS
# ============================================================================

def _find_eval_xss(cursor) -> List[StandardFinding]:
    """Find eval() and Function() with user input."""
    findings = []
    
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('eval', 'Function', 'setTimeout', 'setInterval')
          AND (f.argument_expr LIKE '%req.%'
               OR f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%body%'
               OR f.argument_expr LIKE '%query%'
               OR f.argument_expr LIKE '%params%'
               OR f.argument_expr LIKE '%user%'
               OR f.argument_expr LIKE '%input%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-eval',
            message=f'Code injection: {func} with user input',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='injection',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-94'
        ))
    
    return findings


# ============================================================================
# CHECK 5: React dangerouslySetInnerHTML
# ============================================================================

def _find_react_dangerous_html(cursor) -> List[StandardFinding]:
    """Find React dangerouslySetInnerHTML with user input."""
    findings = []
    
    # Check assignments with dangerouslySetInnerHTML
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%dangerouslySetInnerHTML%'
          AND (a.source_expr LIKE '%props.%'
               OR a.source_expr LIKE '%state.%'
               OR a.source_expr LIKE '%params%'
               OR a.source_expr LIKE '%query%'
               OR a.source_expr LIKE '%user%'
               OR a.source_expr LIKE '%input%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-react-dangerous-html',
            message='XSS: dangerouslySetInnerHTML with user input',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet=source[:100] if len(source) > 100 else source,
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 6: Vue v-html directive
# ============================================================================

def _find_vue_vhtml(cursor) -> List[StandardFinding]:
    """Find Vue v-html directives with user input."""
    findings = []
    
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%v-html%'
          AND (a.source_expr LIKE '%$route%'
               OR a.source_expr LIKE '%props%'
               OR a.source_expr LIKE '%user%'
               OR a.source_expr LIKE '%input%'
               OR a.source_expr LIKE '%params%'
               OR a.source_expr LIKE '%query%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-vue-vhtml',
            message='XSS: v-html directive with user input',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='xss',
            snippet=source[:100] if len(source) > 100 else source,
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 7: jQuery html() method
# ============================================================================

def _find_jquery_html_xss(cursor) -> List[StandardFinding]:
    """Find jQuery html() method with user input."""
    findings = []
    
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%.html'
               OR f.callee_function LIKE '%.append'
               OR f.callee_function LIKE '%.prepend'
               OR f.callee_function LIKE '%.after'
               OR f.callee_function LIKE '%.before'
               OR f.callee_function LIKE '%.replaceWith')
          AND (f.argument_expr LIKE '%req.%'
               OR f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%.val()%'
               OR f.argument_expr LIKE '%input%'
               OR f.argument_expr LIKE '%user%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-jquery',
            message=f'XSS: jQuery {func} with user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 8: Template Injection
# ============================================================================

def _find_template_injection(cursor) -> List[StandardFinding]:
    """Find template injection vulnerabilities."""
    findings = []
    
    # Python template injection
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('render_template_string', 'Template')
          AND (f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%user%'
               OR f.argument_expr LIKE '%input%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-template-injection',
            message=f'Template injection: {func} with user input',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='injection',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-94'
        ))
    
    # JavaScript template literals with user input
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%`%${%}%`%'
          AND (a.source_expr LIKE '%req.%'
               OR a.source_expr LIKE '%request.%'
               OR a.source_expr LIKE '%user%'
               OR a.source_expr LIKE '%input%')
          AND (a.target_var LIKE '%.innerHTML'
               OR a.target_var LIKE '%.html'
               OR a.target_var LIKE '%template%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-template-literal',
            message='XSS: Template literal with user input in HTML context',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=source[:100] if len(source) > 100 else source,
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 9: URL Parameter XSS
# ============================================================================

def _find_url_parameter_xss(cursor) -> List[StandardFinding]:
    """Find URL parameters directly used in output."""
    findings = []
    
    # Direct use of location.search/hash
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%location.search%'
               OR a.source_expr LIKE '%location.hash%'
               OR a.source_expr LIKE '%location.href%'
               OR a.source_expr LIKE '%URLSearchParams%')
          AND (a.target_var LIKE '%.innerHTML'
               OR a.target_var LIKE '%.textContent'
               OR a.target_var LIKE '%.value')
        ORDER BY a.file, a.line
    """)
    
    for file, line, target, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-url-parameter',
            message='XSS: URL parameters directly assigned to DOM',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 10: Cookie XSS
# ============================================================================

def _find_cookie_xss(cursor) -> List[StandardFinding]:
    """Find cookie values used unsafely."""
    findings = []
    
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%document.cookie%'
          AND (a.target_var LIKE '%.innerHTML'
               OR a.target_var LIKE '%.html')
        ORDER BY a.file, a.line
    """)
    
    for file, line, target, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-cookie',
            message='XSS: Cookie value assigned to innerHTML',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 11: Unescaped Output
# ============================================================================

def _find_unescaped_output(cursor) -> List[StandardFinding]:
    """Find unescaped output in various contexts."""
    findings = []
    
    # Flask/Jinja2 |safe filter with user input
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%|safe%'
          AND (a.source_expr LIKE '%request.%'
               OR a.source_expr LIKE '%user%'
               OR a.source_expr LIKE '%input%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-unsafe-filter',
            message='XSS: |safe filter with user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=source[:100] if len(source) > 100 else source,
            cwe_id='CWE-79'
        ))
    
    # Django mark_safe with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('mark_safe', 'format_html')
          AND (f.argument_expr LIKE '%request.%'
               OR f.argument_expr LIKE '%user%'
               OR f.argument_expr LIKE '%input%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='xss-mark-safe',
            message=f'XSS: {func} with user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='xss',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            cwe_id='CWE-79'
        ))
    
    return findings


# ============================================================================
# CHECK 12: DOM XSS Sinks
# ============================================================================

def _find_dom_xss_sinks(cursor) -> List[StandardFinding]:
    """Find DOM XSS sinks with user input."""
    findings = []
    
    # Additional DOM XSS sinks
    dom_sinks = [
        'insertAdjacentHTML', 'createContextualFragment',
        'parseFromString', 'writeln', 'replaceChild',
        'insertBefore', 'appendChild'
    ]
    
    for sink in dom_sinks:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND (f.argument_expr LIKE '%req.%'
                   OR f.argument_expr LIKE '%request.%'
                   OR f.argument_expr LIKE '%location.%'
                   OR f.argument_expr LIKE '%user%'
                   OR f.argument_expr LIKE '%input%')
            ORDER BY f.file, f.line
        """, [f'%{sink}%'])
        
        for file, line, func, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='xss-dom-sink',
                message=f'DOM XSS: {func} with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                cwe_id='CWE-79'
            ))
    
    # Check for element.setAttribute with dangerous attributes
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%.setAttribute'
          AND f.param_name = 'arg0'
          AND (f.argument_expr LIKE '%onclick%'
               OR f.argument_expr LIKE '%onload%'
               OR f.argument_expr LIKE '%onerror%'
               OR f.argument_expr LIKE '%onmouseover%'
               OR f.argument_expr LIKE '%href%'
               OR f.argument_expr LIKE '%src%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, attr in cursor.fetchall():
        # Check if the value (arg1) contains user input
        cursor.execute("""
            SELECT f.argument_expr
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line = ?
              AND f.callee_function LIKE '%.setAttribute'
              AND f.param_name = 'arg1'
              AND (f.argument_expr LIKE '%req.%'
                   OR f.argument_expr LIKE '%request.%'
                   OR f.argument_expr LIKE '%user%'
                   OR f.argument_expr LIKE '%input%')
        """, [file, line])
        
        value_row = cursor.fetchone()
        if value_row:
            findings.append(StandardFinding(
                rule_name='xss-set-attribute',
                message=f'XSS: setAttribute({attr}) with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'setAttribute({attr}, user_input)',
                cwe_id='CWE-79'
            ))
    
    return findings