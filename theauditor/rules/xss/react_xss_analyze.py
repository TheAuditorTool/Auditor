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
    requires_jsx_pass=False,
    execution_scope="database"  # Database-wide query, not per-file iteration
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


def find_react_xss(context: StandardRuleContext) -> list[StandardFinding]:
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
    """Check if this is a React application.

    Modernization (2025-11-22):
    - Removed LIMIT 1000 symbol scan fallback (non-deterministic, violates ZERO FALLBACK POLICY)
    - Trust the indexer: if frameworks table is empty AND react_components is empty, it's not React
    """
    cursor = conn.cursor()

    # Check frameworks table
    cursor.execute("""
        SELECT 1 FROM frameworks
        WHERE name IN ('react', 'React', 'react.js')
          AND language = 'javascript'
        -- REMOVED LIMIT: was hiding bugs
        """)

    if cursor.fetchone() is not None:
        return True

    # Secondary check: react_components table
    # This is legitimate - not all React apps populate frameworks table
    # but components would still be extracted
    cursor.execute("""
        SELECT 1 FROM react_components
        -- REMOVED LIMIT: was hiding bugs
        """)

    return cursor.fetchone() is not None


def _check_dangerous_html_prop(conn) -> list[StandardFinding]:
    """Check for dangerouslySetInnerHTML with user input.

    Modernization (2025-11-22):
    - Fixed N+1 query: Single JOIN instead of loop + query per component
    - Fixed blind spot: Removed LIMIT 10 that missed vulnerabilities beyond first 10 lines
    - Fixed scope: Added end_line boundary to prevent spanning multiple components
    - Memory safe: Stream results with cursor iteration instead of fetchall()
    - Performance: Filter for dangerouslySetInnerHTML in SQL to reduce data transfer
    """
    findings = []
    cursor = conn.cursor()

    # OPTIMIZATION: Single JOIN query instead of N+1 loop
    # Filters in SQL for dangerouslySetInnerHTML AND __html to reduce result set
    # Scans entire component scope (start_line to end_line), not just first 10 lines
    cursor.execute("""
        SELECT rc.file, a.line, rc.name, a.source_expr
        FROM react_components rc
        JOIN assignments a ON rc.file = a.file
        WHERE rc.has_jsx = 1
          AND a.line BETWEEN rc.start_line AND rc.end_line
          AND a.source_expr IS NOT NULL
          AND a.source_expr LIKE '%dangerouslySetInnerHTML%'
          AND a.source_expr LIKE '%__html%'
    """)

    # Memory safe: Iterate cursor directly (streams rows)
    for file, line, comp_name, source in cursor:
        # Already filtered by SQL for dangerouslySetInnerHTML + __html
        # Now check for sanitizers (fast fail) and user input

        # Skip if sanitized
        if 'DOMPurify' in source or 'sanitize' in source:
            continue

        # Check for user input sources
        has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-dangerous-html',
                message=f'XSS: {comp_name} uses dangerouslySetInnerHTML with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=source[:100] + '...' if len(source) > 100 else source,
                cwe_id='CWE-79'
            ))

    # Check function_call_args for createMarkup patterns
    # OPTIMIZATION: Push pattern matching to SQL WHERE clause
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IS NOT NULL
          AND f.argument_expr IS NOT NULL
          AND (
              f.callee_function LIKE '%createMarkup%'
              OR f.callee_function LIKE '%getRawMarkup%'
              OR f.callee_function LIKE '%getHTML%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, func, args in cursor:
        # Already filtered by SQL for markup patterns
        # Just check for user input now
        has_user_input = any(src in args for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-markup-function',
                message=f'XSS: {func} creates HTML from user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                cwe_id='CWE-79'
            ))

    return findings


def _check_javascript_urls(conn) -> list[StandardFinding]:
    """Check for javascript: URLs in href/src props.

    Modernization (2025-11-22):
    - Fixed Inverse N+1: Single JOIN instead of loop + query per assignment
    - Performance: Push href/src and protocol filtering to SQL
    - Memory safe: Stream results with cursor iteration
    """
    findings = []
    cursor = conn.cursor()

    # OPTIMIZATION: JOIN assignments with react_components upfront
    # Filter for href/src targets AND dangerous protocols in SQL
    # This eliminates fetching + filtering hundreds of thousands of irrelevant rows
    cursor.execute("""
        SELECT a.file, a.line, rc.name, a.target_var, a.source_expr
        FROM assignments a
        JOIN react_components rc
          ON a.file = rc.file
          AND a.line BETWEEN rc.start_line AND rc.end_line
        WHERE a.target_var IS NOT NULL
          AND a.source_expr IS NOT NULL
          AND (a.target_var LIKE '%href%' OR a.target_var LIKE '%src%')
          AND (
              a.source_expr LIKE '%javascript:%'
              OR a.source_expr LIKE '%data:text/html%'
              OR a.source_expr LIKE '%vbscript:%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, comp_name, target, source in cursor:
        # Already filtered by SQL for href/src and dangerous protocols
        # Just verify user input now
        has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-javascript-url',
                message=f'XSS: Component {comp_name} uses dangerous URL protocol with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # Check JSX props directly
    # OPTIMIZATION: Push protocol filtering to SQL
    cursor.execute("""
        SELECT f.file, f.line, f.param_name, f.argument_expr
        FROM function_call_args f
        WHERE f.param_name IN ('href', 'src', 'action', 'formAction')
          AND f.argument_expr IS NOT NULL
          AND (
              f.argument_expr LIKE '%javascript:%'
              OR f.argument_expr LIKE '%vbscript:%'
              OR f.argument_expr LIKE '%props.%'
              OR f.argument_expr LIKE '%state.%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, prop, value in cursor:
        # Already filtered by SQL for dangerous patterns
        # Verify it's actually dangerous (has protocol + user input)
        has_dangerous = 'javascript:' in value or 'vbscript:' in value
        has_user_input = 'props.' in value or 'state.' in value

        if has_dangerous or has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-unsafe-prop',
                message=f'XSS: {prop} prop with potentially unsafe URL',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=f'{prop}={{{value[:40]}...}}' if len(value) > 40 else f'{prop}={{{value}}}',
                cwe_id='CWE-79'
            ))

    return findings


def _check_unsafe_html_creation(conn) -> list[StandardFinding]:
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
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
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


def _check_ref_innerhtml(conn) -> list[StandardFinding]:
    """Check for direct DOM manipulation via refs.

    Modernization (2025-11-22):
    - Performance: Push ref innerHTML pattern filtering to SQL
    - Fixed N+1: Single range JOIN instead of loop + proximity query per ref
    - Memory safe: Stream results with cursor iteration
    """
    findings = []
    cursor = conn.cursor()

    # OPTIMIZATION: Filter for ref innerHTML patterns in SQL
    # Eliminates fetching hundreds of thousands of irrelevant assignments
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
          AND (
              target_var LIKE '%ref.current.innerHTML%'
              OR target_var LIKE '%.current.innerHTML%'
              OR target_var LIKE '%Ref.current.innerHTML%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line, target, source in cursor:
        # Already filtered by SQL for ref innerHTML patterns
        # Just check for user input now
        has_user_input = any(src in source for src in REACT_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='react-xss-ref-innerhtml',
                message='XSS: Direct innerHTML manipulation via React ref',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='xss',
                snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
                cwe_id='CWE-79'
            ))

    # OPTIMIZATION: Fix N+1 proximity check with self-JOIN
    # Find useRef/createRef calls that have innerHTML usage within 50 lines
    # Single query instead of loop + query per ref
    cursor.execute("""
        SELECT DISTINCT f.file, f.line
        FROM function_call_args f
        JOIN assignments a
          ON f.file = a.file
          AND a.line BETWEEN f.line + 1 AND f.line + 50
        WHERE f.callee_function IN ('useRef', 'createRef', 'React.useRef', 'React.createRef')
          AND (
              a.target_var LIKE '%.innerHTML%'
              OR a.source_expr LIKE '%.innerHTML%'
          )
    """)

    # Memory safe: Iterate cursor directly
    for file, line in cursor:
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


def _check_component_injection(conn) -> list[StandardFinding]:
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


def _check_server_side_rendering(conn) -> list[StandardFinding]:
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
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
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

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Orchestrator-compatible entry point.

    This is the standardized interface that the orchestrator expects.
    Delegates to the main implementation function for backward compatibility.
    """
    return find_react_xss(context)