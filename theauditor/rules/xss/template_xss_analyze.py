"""Template Injection and XSS Detection.

This module detects template injection vulnerabilities across various template engines.
Covers both server-side and client-side template injection.
"""

import sqlite3
from typing import List, Dict, FrozenSet

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# NO FALLBACKS. NO TABLE EXISTENCE CHECKS. SCHEMA CONTRACT GUARANTEES ALL TABLES EXIST.
# If tables are missing, the rule MUST crash to expose indexer bugs.

# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="template_injection",
    category="xss",
    target_extensions=['.py', '.js', '.ts', '.html', '.ejs', '.pug', '.vue', '.jinja2'],
    exclude_patterns=['test/', '__tests__/', 'node_modules/', '*.test.js'],
    requires_jsx_pass=False,
    execution_scope='database'  # Run once globally, not per-file
)


# Template engines and their unsafe patterns
TEMPLATE_ENGINES: Dict[str, Dict[str, FrozenSet[str]]] = {
    # Python template engines
    'jinja2': {
        'safe': frozenset(['{{}}', '{%%}']),
        'unsafe': frozenset(['|safe', 'autoescape off', 'Markup(', 'render_template_string'])
    },
    'django': {
        'safe': frozenset(['{{}}', '{%%}']),
        'unsafe': frozenset(['|safe', 'autoescape off', 'mark_safe', 'format_html'])
    },
    'mako': {
        'safe': frozenset(['${}']),
        'unsafe': frozenset(['|n', '|h', 'disable_unicode=True'])  # Explicit filter patterns only
    },

    # JavaScript template engines
    'ejs': {
        'safe': frozenset(['<%= %>']),
        'unsafe': frozenset(['<%- %>', 'unescape'])
    },
    'pug': {
        'safe': frozenset(['#{}']),
        'unsafe': frozenset(['!{}', '!{-}', '|'])
    },
    'handlebars': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{{{', '}}}', 'SafeString'])
    },
    'mustache': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{{{', '}}}', '&'])
    },
    'nunjucks': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['|safe', 'autoescape false'])
    },
    'doT': {
        'safe': frozenset(['{{!}}']),
        'unsafe': frozenset(['{{=}}', '{{#}}'])
    },
    'lodash': {
        'safe': frozenset(['<%- %>']),
        'unsafe': frozenset(['<%= %>', '<%'])
    },

    # PHP template engines
    'twig': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['|raw', 'autoescape false'])
    },
    'blade': {
        'safe': frozenset(['{{}}']),
        'unsafe': frozenset(['{!!', '!!}', '@php'])
    }
}

# Template compilation/rendering functions
TEMPLATE_COMPILE_FUNCTIONS = frozenset([
    'compile', 'render', 'render_template', 'render_template_string',
    'Template', 'from_string', 'compileToFunctions',
    'Handlebars.compile', 'ejs.compile', 'pug.compile',
    'nunjucks.renderString', 'doT.template', '_.template'
])

# User input sources
TEMPLATE_INPUT_SOURCES = frozenset([
    'request.', 'req.', 'params.', 'query.', 'body.',
    'user.', 'input.', 'data.', 'form.',
    'GET[', 'POST[', 'REQUEST[', 'COOKIE[',
    'location.', 'window.', 'document.'
])


def find_template_injection(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect template injection and XSS vulnerabilities.

    Returns:
        List of template-related XSS findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)

    try:
        cursor = conn.cursor()

        findings.extend(_check_template_string_injection(conn))
        findings.extend(_check_unsafe_template_syntax(conn))
        findings.extend(_check_dynamic_template_compilation(conn))
        findings.extend(_check_template_autoescape_disabled(conn))
        findings.extend(_check_custom_template_helpers(conn))
        findings.extend(_check_server_side_template_injection(conn))

    finally:
        conn.close()

    return findings


def _check_template_string_injection(conn) -> List[StandardFinding]:
    """Check for template string injection with user input."""
    findings = []
    cursor = conn.cursor()

    # Check for render_template_string and similar with user input
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('render_template_string', 'from_string',
                                   'Template', 'jinja2.Template',
                                   'django.template.Template')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, func, template_arg in cursor.fetchall():
        # Check for user input in template
        has_user_input = any(src in (template_arg or '') for src in TEMPLATE_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='template-string-injection',
                message=f'Template Injection: {func} with user input',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                snippet=f'{func}(request.form.template)',
                cwe_id='CWE-94'
            ))

        # Check for string concatenation/interpolation
        if '+' in (template_arg or '') or 'f"' in (template_arg or '') or '`' in (template_arg or ''):
            findings.append(StandardFinding(
                rule_name='template-dynamic-construction',
                message='Template Injection: Dynamic template construction',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                snippet=f'{func}(base_template + user_content)',
                cwe_id='CWE-94'
            ))

    return findings


def _check_unsafe_template_syntax(conn) -> List[StandardFinding]:
    """Check for unsafe template syntax usage."""
    findings = []
    cursor = conn.cursor()

    # Check assignments for unsafe template patterns (optimized with WHERE filters)
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr IS NOT NULL
          AND (a.source_expr LIKE '%|safe%'
               OR a.source_expr LIKE '%|raw%'
               OR a.source_expr LIKE '%|n%'
               OR a.source_expr LIKE '%|h%'
               OR a.source_expr LIKE '%{{{%'
               OR a.source_expr LIKE '%}}}%'
               OR a.source_expr LIKE '%<%-%'
               OR a.source_expr LIKE '%!{%'
               OR a.source_expr LIKE '%Markup(%'
               OR a.source_expr LIKE '%mark_safe%'
               OR a.source_expr LIKE '%SafeString%'
               OR a.source_expr LIKE '%autoescape%'
               OR a.source_expr LIKE '%unescape%'
               OR a.source_expr LIKE '%format_html%'
               OR a.source_expr LIKE '%{!!%'
               OR a.source_expr LIKE '%@php%'
               OR a.source_expr LIKE '%disable_unicode%'
               OR a.source_expr LIKE '%{{=%'
               OR a.source_expr LIKE '%{{#%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        # Check each template engine's unsafe patterns
        for engine, patterns in TEMPLATE_ENGINES.items():
            for unsafe_pattern in patterns.get('unsafe', []):
                if unsafe_pattern in (source or ''):
                    # Check if user input is involved
                    has_user_input = any(src in source for src in TEMPLATE_INPUT_SOURCES)

                    if has_user_input:
                        normalized = (source or '').replace(' ', '')
                        if engine == 'mako' and unsafe_pattern.lower() == '|n':
                            if '|n' not in normalized:
                                continue
                        if engine == 'mako' and unsafe_pattern.lower() == '|h':
                            if '|h' not in normalized:
                                continue

                        findings.append(StandardFinding(
                            rule_name=f'{engine}-unsafe-syntax',
                            message=f'XSS: {engine} unsafe pattern "{unsafe_pattern}" with user input',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='xss',
                            snippet=f'{unsafe_pattern} with user data',
                            cwe_id='CWE-79'
                        ))

    # Specific check for triple mustache in Handlebars/Mustache
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%{{{%}}}%'
               OR a.source_expr LIKE '%<%-%>%'
               OR a.source_expr LIKE '%!{%}%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        has_user_input = any(src in (source or '') for src in TEMPLATE_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='template-unescaped-output',
                message='XSS: Unescaped template output with user input',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='xss',
                snippet=source[:80] if len(source or '') > 80 else source,
                cwe_id='CWE-79'
            ))

    return findings


def _check_dynamic_template_compilation(conn) -> List[StandardFinding]:
    """Check for dynamic template compilation."""
    findings = []
    cursor = conn.cursor()

    # Check template compilation functions
    for compile_func in TEMPLATE_COMPILE_FUNCTIONS:
        cursor.execute("""
            SELECT f.file, f.line, f.argument_expr
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
              AND f.argument_index = 0
            ORDER BY f.file, f.line
        """, [f'%{compile_func}%'])

        for file, line, template_source in cursor.fetchall():
            # Check if template comes from user input
            has_user_input = any(src in (template_source or '') for src in TEMPLATE_INPUT_SOURCES)

            # Check if template is loaded from database or external source
            has_external = any(ext in (template_source or '') for ext in [
                'database', 'fetch', 'ajax', 'xhr', 'readFile', 'localStorage'
            ])

            if has_user_input:
                findings.append(StandardFinding(
                    rule_name='template-compile-user-input',
                    message=f'Template Injection: {compile_func} with user input',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    snippet=f'{compile_func}(userTemplate)',
                    cwe_id='CWE-94'
                ))
            elif has_external:
                findings.append(StandardFinding(
                    rule_name='template-compile-external',
                    message=f'Template Injection: {compile_func} with external source',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='injection',
                    snippet=f'{compile_func}(fetchedTemplate)',
                    cwe_id='CWE-94'
                ))

    return findings


def _check_template_autoescape_disabled(conn) -> List[StandardFinding]:
    """Check for disabled auto-escaping in templates."""
    findings = []
    cursor = conn.cursor()

    # Check for autoescape disabled patterns
    autoescape_patterns = [
        'autoescape off', 'autoescape false', 'autoescape=False',
        'autoescape: false', '"autoescape": false',
        'AUTOESCAPE = False', 'config.autoescape = false'
    ]

    for pattern in autoescape_patterns:
        cursor.execute("""
            SELECT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE ?
            ORDER BY a.file, a.line
        """, [f'%{pattern}%'])

        for file, line, source in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='template-autoescape-disabled',
                message='XSS: Template auto-escaping disabled',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='configuration',
                snippet=pattern,
                cwe_id='CWE-79'
            ))

    # Check Jinja2 environment configuration
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%Environment%'
          AND f.argument_expr LIKE '%autoescape%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        if 'False' in (args or '') or 'false' in (args or ''):
            findings.append(StandardFinding(
                rule_name='jinja2-autoescape-disabled',
                message='XSS: Jinja2 Environment with autoescape disabled',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='configuration',
                snippet='Environment(autoescape=False)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_custom_template_helpers(conn) -> List[StandardFinding]:
    """Check for unsafe custom template helpers/filters."""
    findings = []
    cursor = conn.cursor()

    # Check for custom Jinja2 filters
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%.filters[%'
           OR f.callee_function LIKE 'app.jinja_env.filters%'
           OR f.callee_function = 'register.filter'
        ORDER BY f.file, f.line
    """)

    for file, line, func, filter_def in cursor.fetchall():
        # Check if filter returns Markup or mark_safe
        if 'Markup' in (filter_def or '') or 'mark_safe' in (filter_def or ''):
            findings.append(StandardFinding(
                rule_name='template-unsafe-filter',
                message='XSS: Custom template filter returns unescaped HTML',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet='Custom filter with Markup/mark_safe',
                cwe_id='CWE-79'
            ))

    # Check Handlebars helpers
    cursor.execute("""
        SELECT f.file, f.line, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('Handlebars.registerHelper', 'registerHelper')
        ORDER BY f.file, f.line
    """)

    for file, line, helper_def in cursor.fetchall():
        # Check if helper uses SafeString
        if 'SafeString' in (helper_def or '') or 'new Handlebars.SafeString' in (helper_def or ''):
            findings.append(StandardFinding(
                rule_name='handlebars-unsafe-helper',
                message='XSS: Handlebars helper returns SafeString (unescaped)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='xss',
                snippet='Handlebars.SafeString(userContent)',
                cwe_id='CWE-79'
            ))

    return findings


def _check_server_side_template_injection(conn) -> List[StandardFinding]:
    r"""Check for server-side template injection (SSTI).

    BUG FIXES (2025-10-17):
    1. SQL LIKE wildcard escape: _ must be escaped as \_ to avoid matching any character
    2. Context awareness: Only flag 'config.' when near template rendering functions
    3. Deduplication: Use DISTINCT to avoid duplicate findings from duplicate DB rows
    """
    findings = []
    cursor = conn.cursor()

    # Check for eval-like patterns in templates
    dangerous_template_patterns = [
        '.__class__', '.__mro__', '.__subclasses__',
        '.__globals__', '.__builtins__', '.__import__',
        'config.', 'self.', 'lipsum.', 'cycler.',
        '|attr(', '|format(', 'getattr(',
        '{{config', '{{self', '{{request',
        '${__', '#{__'  # These contain underscores - will be escaped!
    ]

    # Template rendering functions for proximity checks
    RENDER_FUNCTIONS = frozenset([
        'render_template_string', 'render_template', 'render',
        'ejs.render', 'ejs.compile', 'pug.compile',
        'Handlebars.compile', 'tera.render_str', 'tera.render',
        'compile', 'Template'
    ])

    for pattern in dangerous_template_patterns:
        # FIX 1: Escape underscores for SQL LIKE (prevents ${__ matching ${xy})
        escaped_pattern = pattern.replace('_', '\\_')

        # FIX 2: Context-aware detection for 'config.' pattern
        # Only check proximity to render functions for broad patterns
        needs_proximity_check = pattern in ['config.', 'self.']

        if needs_proximity_check:
            # Only flag if near template rendering functions
            cursor.execute("""
                SELECT DISTINCT a.file, a.line, a.source_expr
                FROM assignments a
                WHERE a.source_expr LIKE ? ESCAPE '\\'
                AND EXISTS (
                    SELECT 1 FROM function_call_args f
                    WHERE f.file = a.file
                    AND ABS(f.line - a.line) <= 20
                    AND (
                        f.callee_function IN ('render_template_string', 'render', 'compile',
                                             'ejs.render', 'ejs.compile', 'Handlebars.compile')
                        OR f.callee_function LIKE '%render%'
                        OR f.callee_function LIKE '%compile%'
                    )
                )
                ORDER BY a.file, a.line
            """, [f'%{escaped_pattern}%'])
        else:
            # FIX 3: Use DISTINCT to avoid duplicate findings from duplicate DB rows
            cursor.execute("""
                SELECT DISTINCT a.file, a.line, a.source_expr
                FROM assignments a
                WHERE a.source_expr LIKE ? ESCAPE '\\'
                ORDER BY a.file, a.line
            """, [f'%{escaped_pattern}%'])

        for file, line, source in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='ssti-dangerous-pattern',
                message=f'SSTI: Dangerous template pattern "{pattern}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='injection',
                snippet=source[:80] if len(source or '') > 80 else source,
                cwe_id='CWE-94'
            ))

    # Check for user-controlled template names
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function IN ('render_template', 'render', 'include')
          AND f.argument_index = 0
        ORDER BY f.file, f.line
    """)

    for file, line, func, template_name in cursor.fetchall():
        # Check if template name comes from user input
        has_user_input = any(src in (template_name or '') for src in TEMPLATE_INPUT_SOURCES)

        if has_user_input:
            findings.append(StandardFinding(
                rule_name='ssti-user-template-name',
                message='SSTI: User controls template name/path',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='injection',
                snippet=f'{func}(request.args.template)',
                cwe_id='CWE-94'
            ))

    # Check for template includes with user input
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%{% include%'
               OR a.source_expr LIKE '%{% extends%'
               OR a.source_expr LIKE '%{% import%')
          AND (a.source_expr LIKE '%request.%'
               OR a.source_expr LIKE '%params.%'
               OR a.source_expr LIKE '%user.%')
        ORDER BY a.file, a.line
    """)

    for file, line, source in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='ssti-dynamic-include',
            message='SSTI: Dynamic template include/extend with user input',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='injection',
            snippet='{% include request.args.partial %}',
            cwe_id='CWE-94'
        ))

    return findings
