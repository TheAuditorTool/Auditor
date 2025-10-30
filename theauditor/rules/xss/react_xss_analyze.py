"""React-specific XSS Detection.

This module detects XSS vulnerabilities specific to React applications.
Uses database-only approach with React component awareness.
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
    name="react_xss",
    category="xss",
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.test.jsx', '*.spec.tsx'],
    requires_jsx_pass=False
)


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
    cursor = conn.cursor()

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
    react_patterns = ['React.', 'useState', 'useEffect', 'Component']

    cursor.execute("""
        SELECT name FROM symbols
        WHERE name IS NOT NULL
        LIMIT 1000
    """)

    # Filter in Python: Check for React-like symbol names
    for (name,) in cursor.fetchall():
        if any(pattern in name for pattern in react_patterns):
            return True

    return False


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
              AND a.source_expr IS NOT NULL
            ORDER BY a.line
            LIMIT 10
        """, [comp_file, comp_line])

        for line, source in cursor.fetchall():
            # Filter in Python: Check for dangerouslySetInnerHTML with __html
            has_dangerous_prop = 'dangerouslySetInnerHTML' in source and '__html' in source

            if not has_dangerous_prop:
                continue

            # Check for user input
            has_user_input = any(src in source for src in REACT_INPUT_SOURCES)
            has_sanitizer = 'DOMPurify' in source or 'sanitize' in source

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
    markup_patterns = ['createMarkup', 'getRawMarkup', 'getHTML']

    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python: Check if function name contains markup patterns
        is_markup_function = any(pattern in func for pattern in markup_patterns)

        if not is_markup_function:
            continue

        has_user_input = any(src in args for src in REACT_INPUT_SOURCES)

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

    # Dangerous URL patterns
    dangerous_protocols = ['javascript:', 'data:text/html', 'vbscript:']

    # Check assignments to href/src with javascript: protocol
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if target is href/src
        is_url_target = 'href' in target or 'src' in target

        if not is_url_target:
            continue

        # Filter in Python: Check for dangerous protocols
        has_dangerous_protocol = any(protocol in source for protocol in dangerous_protocols)

        if not has_dangerous_protocol:
            continue

        # Check if it's in a React component
        cursor.execute("""
            SELECT rc.name
            FROM react_components rc
            WHERE rc.file = ?
              AND ? BETWEEN rc.start_line AND rc.end_line
        """, [file, line])

        comp_row = cursor.fetchone()
        if comp_row:
            has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

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
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, prop, value in cursor.fetchall():
        # Filter in Python: Check for dangerous protocols or user input
        has_javascript = 'javascript:' in value or 'vbscript:' in value
        has_props = 'props.' in value
        has_state = 'state.' in value

        # Only report if has dangerous protocol OR (has user input that could be dangerous)
        if has_javascript or (has_props or has_state):
            if 'javascript:' in value or 'vbscript:' in value:
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

    # HTML tag patterns to detect
    html_patterns = ['<div>', '<span>', '<script>', '<img', '<iframe']

    # Check for HTML string concatenation with user input
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check if contains HTML tags
        has_html = any(tag in source for tag in html_patterns)

        if not has_html:
            continue

        # Filter in Python: Check for user input or string operations
        has_props = 'props.' in source
        has_state = 'state.' in source
        has_concat = '+' in source
        has_template = '`' in source

        if not (has_props or has_state or has_concat or has_template):
            continue

        # Check if it's being used with dangerouslySetInnerHTML
        cursor.execute("""
            SELECT a2.source_expr
            FROM assignments a2
            WHERE a2.file = ?
              AND ABS(a2.line - ?) <= 5
              AND a2.source_expr IS NOT NULL
        """, [file, line])

        has_dangerous_nearby = False
        for (nearby_source,) in cursor.fetchall():
            if 'dangerouslySetInnerHTML' in nearby_source:
                has_dangerous_nearby = True
                break

        if has_dangerous_nearby:
            has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

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

    # Ref innerHTML patterns to detect
    ref_innerHTML_patterns = ['ref.current.innerHTML', '.current.innerHTML', 'Ref.current.innerHTML']

    # Check for ref.current.innerHTML assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, target, source in cursor.fetchall():
        # Filter in Python: Check if target contains ref innerHTML pattern
        is_ref_innerHTML = any(pattern in target for pattern in ref_innerHTML_patterns)

        if not is_ref_innerHTML:
            continue

        has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

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
        WHERE f.callee_function IN ('useRef', 'createRef', 'React.useRef', 'React.createRef')
        ORDER BY f.file, f.line
    """)

    for file, line, ref_init in cursor.fetchall():
        # Check nearby code for innerHTML usage
        cursor.execute("""
            SELECT a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND a.line > ?
              AND a.line < ? + 50
              AND (a.target_var IS NOT NULL OR a.source_expr IS NOT NULL)
        """, [file, line, line])

        # Filter in Python: Check for .innerHTML usage
        has_innerHTML = False
        for target_var, source_expr in cursor.fetchall():
            if '.innerHTML' in (target_var or '') or '.innerHTML' in (source_expr or ''):
                has_innerHTML = True
                break

        if has_innerHTML:
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

    # User input patterns
    user_input_patterns = ['props.', 'state.', 'params.']

    # Check for dynamic component creation from user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('React.createElement', 'createElement')
          AND f.argument_index = 0
          AND f.argument_expr IS NOT NULL
        ORDER BY f.file, f.line
    """)

    for file, line, func, component_arg in cursor.fetchall():
        # Filter in Python: Check if component type comes from user input
        has_user_input = any(pattern in component_arg for pattern in user_input_patterns)

        if has_user_input:
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
        WHERE a.source_expr IS NOT NULL
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Filter in Python: Check for new Function with user input
        has_new_function = 'new Function' in source
        has_user_input = any(pattern in source for pattern in user_input_patterns)

        if has_new_function and has_user_input:
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
            SELECT a.target_var, a.source_expr
            FROM assignments a
            WHERE a.file = ?
              AND ABS(a.line - ?) <= 20
              AND (a.target_var IS NOT NULL OR a.source_expr IS NOT NULL)
        """, [file, line])

        # Filter in Python: Check for innerHTML or __html
        has_unsafe_html = False
        for target_var, source_expr in cursor.fetchall():
            if '.innerHTML' in (target_var or '') or '__html' in (source_expr or ''):
                has_unsafe_html = True
                break

        if has_unsafe_html:
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


# ============================================================================
# ORCHESTRATOR ENTRY POINT
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_react_xss(context)