"""React-specific XSS Detection.

This module detects XSS vulnerabilities specific to React applications.
Uses database-only approach with React component awareness.
"""

import sqlite3
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# React dangerous props/methods
REACT_DANGEROUS_PROPS = frozenset([
    'dangerouslySetInnerHTML',
    'href',  # When used with javascript: URLs
    'src',   # When used with javascript: URLs
    'formAction',  # Can execute javascript:
    'data',  # In object/embed tags
    'srcdoc'  # iframe srcdoc can contain scripts
])

# React component patterns
REACT_COMPONENT_PATTERNS = frozenset([
    'React.Component', 'React.PureComponent',
    'React.FC', 'React.FunctionComponent',
    'Component', 'PureComponent', 'useState', 'useEffect'
])

# User input sources in React
REACT_INPUT_SOURCES = frozenset([
    'props.', 'this.props.',
    'state.', 'this.state.',
    'location.search', 'location.hash',
    'match.params', 'params.',
    'query.', 'searchParams.',
    'localStorage.getItem', 'sessionStorage.getItem',
    'document.cookie', 'window.name',
    'event.target.value', 'e.target.value',
    'ref.current.value'
])

# Safe React methods (auto-escaped)
REACT_SAFE_METHODS = frozenset([
    'React.createElement', 'createElement',
    'React.cloneElement', 'cloneElement',
    'jsx', 'jsxs', 'jsxDEV'  # JSX runtime
])


def find_react_xss(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React-specific XSS vulnerabilities.

    Returns:
        List of React-specific XSS findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)

    try:
        # Only run if React is detected
        if not _is_react_app(conn):
            return findings

        findings.extend(_check_dangerous_html_prop(conn))
        findings.extend(_check_javascript_urls(conn))
        findings.extend(_check_unsafe_html_creation(conn))
        findings.extend(_check_ref_innerhtml(conn))
        findings.extend(_check_component_injection(conn))
        findings.extend(_check_server_side_rendering(conn))

    finally:
        conn.close()

    return findings


def _is_react_app(conn) -> bool:
    """Check if this is a React application."""
    cursor = conn.cursor()

    # Check frameworks table
    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name IN ('react', 'React', 'react.js')
          AND language = 'javascript'
    """)

    if cursor.fetchone()[0] > 0:
        return True

    # Check react_components table if available
    cursor.execute("""
        SELECT COUNT(*) FROM react_components
        LIMIT 1
    """)

    if cursor.fetchone()[0] > 0:
        return True

    # Fallback: Check for React patterns
    cursor.execute("""
        SELECT COUNT(*) FROM symbols
        WHERE name LIKE '%React.%'
           OR name LIKE '%useState%'
           OR name LIKE '%useEffect%'
           OR name LIKE '%Component%'
        LIMIT 1
    """)

    return cursor.fetchone()[0] > 0


def _check_dangerous_html_prop(conn) -> List[StandardFinding]:
    """Check for dangerouslySetInnerHTML with user input."""
    findings = []
    cursor = conn.cursor()

    # Check React components table for dangerouslySetInnerHTML usage
    cursor.execute("""
        SELECT rc.file, rc.start_line, rc.name
        FROM react_components rc
        WHERE rc.has_jsx = 1
    """)

    components_with_jsx = cursor.fetchall()

    for comp_file, comp_line, comp_name in components_with_jsx:
        # Check for dangerouslySetInnerHTML in component's range
        cursor.execute("""
            SELECT a.line, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line >= ?
              AND a.source_expr LIKE '%dangerouslySetInnerHTML%'
              AND a.source_expr LIKE '%__html%'
            ORDER BY a.line
            LIMIT 10
        """, [comp_file, comp_line])

        for line, source in cursor.fetchall():
            # Check for user input
            has_user_input = any(src in (source or '') for src in REACT_INPUT_SOURCES)
            has_sanitizer = 'DOMPurify' in (source or '') or 'sanitize' in (source or '')

            if has_user_input and not has_sanitizer:
                findings.append(StandardFinding(
                    rule_name='react-xss-dangerous-html',
                    message=f'XSS: {comp_name} uses dangerouslySetInnerHTML with user input',
                    file_path=comp_file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='xss',
                    snippet='dangerouslySetInnerHTML={{__html: props.userContent}}',
                    cwe_id='CWE-79'
                ))

    # Also check function_call_args for createMarkup patterns
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%createMarkup%'
           OR f.callee_function LIKE '%getRawMarkup%'
           OR f.callee_function LIKE '%getHTML%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        has_user_input = any(src in (args or '') for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-markup-function',
                message=f'XSS: {func} creates HTML from user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}(props.content)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_javascript_urls(conn) -> List[StandardFinding]:
    """Check for javascript: URLs in href/src props."""
    findings = []
    cursor = conn.cursor()

    # Check assignments to href/src with javascript: protocol
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%href%' OR a.target_var LIKE '%src%')
          AND (a.source_expr LIKE '%javascript:%'
               OR a.source_expr LIKE '%data:text/html%'
               OR a.source_expr LIKE '%vbscript:%')
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Check if it's in a React component
        cursor.execute("""
            SELECT rc.name
            FROM react_components rc
            WHERE rc.file = ?
              AND ? BETWEEN rc.start_line AND rc.end_line
        """, [file, line])

        comp_row = cursor.fetchone()
        if comp_row:
            has_user_input = any(src in (source or '') for src in REACT_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='react-xss-javascript-url',
                    message=f'XSS: Component {comp_row[0]} uses javascript: URL with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet=f'href={{javascript:props.action}}',
                    cwe_id='CWE-79'
                ))

    # Check JSX props directly
    cursor.execute("""
        SELECT f.file, f.line, f.param_name, f.argument_expr
        FROM function_call_args f
        WHERE f.param_name IN ('href', 'src', 'action', 'formAction')
          AND (f.argument_expr LIKE '%javascript:%'
               OR f.argument_expr LIKE '%props.%'
               OR f.argument_expr LIKE '%state.%')
        ORDER BY f.file, f.line
    """)

    for file, line, prop, value in cursor.fetchall():
        if 'javascript:' in (value or '') or 'vbscript:' in (value or ''):
            findings.append(StandardFinding(
                rule_name='react-xss-unsafe-prop',
                message=f'XSS: {prop} prop with potentially unsafe URL',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{prop}={{props.url}}',
                cwe_id='CWE-79'
            ))

    return findings


def _check_unsafe_html_creation(conn) -> List[StandardFinding]:
    """Check for unsafe HTML string creation in React components."""
    findings = []
    cursor = conn.cursor()

    # Check for HTML string concatenation with user input
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%<div>%'
               OR a.source_expr LIKE '%<span>%'
               OR a.source_expr LIKE '%<script>%'
               OR a.source_expr LIKE '%<img%'
               OR a.source_expr LIKE '%<iframe%')
          AND (a.source_expr LIKE '%props.%'
               OR a.source_expr LIKE '%state.%'
               OR a.source_expr LIKE '%+%'  -- String concatenation
               OR a.source_expr LIKE '%`%')  -- Template literals
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check if it's being used with dangerouslySetInnerHTML
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments a2
            WHERE a2.file = ?
              AND ABS(a2.line - ?) <= 5
              AND a2.source_expr LIKE '%dangerouslySetInnerHTML%'
        """, [file, line])

        if cursor.fetchone()[0] > 0:
            has_user_input = any(src in (source or '') for src in REACT_INPUT_SOURCES)

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='react-xss-html-concatenation',
                    message='XSS: HTML string built with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    snippet='`<div>${props.userInput}</div>`',
                    cwe_id='CWE-79'
                ))

    return findings


def _check_ref_innerhtml(conn) -> List[StandardFinding]:
    """Check for direct DOM manipulation via refs."""
    findings = []
    cursor = conn.cursor()

    # Check for ref.current.innerHTML assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%ref.current.innerHTML%'
           OR a.target_var LIKE '%.current.innerHTML%'
           OR a.target_var LIKE '%Ref.current.innerHTML%'
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        has_user_input = any(src in (source or '') for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-ref-innerhtml',
                message='XSS: Direct innerHTML manipulation via React ref',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = props.content',
                cwe_id='CWE-79'
            ))

    # Check for ref callbacks that manipulate DOM
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'useRef'
           OR f.callee_function = 'createRef'
           OR f.callee_function = 'React.useRef'
           OR f.callee_function = 'React.createRef'
        ORDER BY f.file, f.line
    """)

    for file, line, ref_init in cursor.fetchall():
        # Check nearby code for innerHTML usage
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line > ?
              AND a.line < ? + 50
              AND (a.target_var LIKE '%.innerHTML%'
                   OR a.source_expr LIKE '%.innerHTML%')
        """, [file, line, line])

        if cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='react-xss-ref-usage',
                message='XSS: React ref used for direct DOM manipulation',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet='useRef() followed by .innerHTML assignment',
                cwe_id='CWE-79'
            ))

    return findings


def _check_component_injection(conn) -> List[StandardFinding]:
    """Check for dynamic component injection vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check for dynamic component creation from user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('React.createElement', 'createElement')
          AND f.argument_index = 0  -- Component type
          AND (f.argument_expr LIKE '%props.%'
               OR f.argument_expr LIKE '%state.%'
               OR f.argument_expr LIKE '%params.%')
        ORDER BY f.file, f.line
    """)

    for file, line, func, component_arg in cursor.fetchall():
        # Dynamic component type from user input is dangerous
        findings.append(StandardFinding(
            rule_name='react-component-injection',
            message='Component Injection: Dynamic component type from user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='injection',
            snippet=f'{func}(props.componentType, ...)',
            cwe_id='CWE-74'
        ))

    # Check for eval-like patterns in React
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%new Function%'
          AND (a.source_expr LIKE '%props.%'
               OR a.source_expr LIKE '%state.%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='react-code-injection',
            message='Code Injection: new Function() with user input in React component',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='injection',
            snippet='new Function(props.code)',
            cwe_id='CWE-94'
        ))

    return findings


def _check_server_side_rendering(conn) -> List[StandardFinding]:
    """Check for SSR-specific XSS vulnerabilities."""
    findings = []
    cursor = conn.cursor()

    # Check for renderToString/renderToStaticMarkup with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('renderToString', 'renderToStaticMarkup',
                                   'ReactDOMServer.renderToString',
                                   'ReactDOMServer.renderToStaticMarkup')
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if the rendered component contains user input
        has_user_input = any(src in (args or '') for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-ssr-xss',
                message='SSR XSS: Server-side rendering with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}(<App userInput={{req.body}} />)',
                cwe_id='CWE-79'
            ))

    # Check for hydration issues
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function IN ('hydrate', 'ReactDOM.hydrate',
                                   'hydrateRoot', 'ReactDOM.hydrateRoot')
        ORDER BY f.file, f.line
    """)

    for file, line, func in cursor.fetchall():
        # Check if initial HTML contains user input
        cursor.execute("""
            SELECT a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND ABS(a.line - ?) <= 20
              AND (a.target_var LIKE '%.innerHTML%'
                   OR a.source_expr LIKE '%__html%')
        """, [file, line])

        if cursor.fetchone():
            findings.append(StandardFinding(
                rule_name='react-hydration-xss',
                message='XSS: React hydration with potentially unsafe initial HTML',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet=f'{func}(...) with unsafe initial HTML',
                cwe_id='CWE-79'
            ))

    return findings