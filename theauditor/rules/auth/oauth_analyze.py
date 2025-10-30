"""OAuth/SSO Security Analyzer - Database-First Approach.

Detects OAuth and Single Sign-On security vulnerabilities using database-driven approach.
Follows gold standard patterns from jwt_analyze.py.

NO AST TRAVERSAL. NO FILE I/O. PURE DATABASE QUERIES.

Detects:
- Missing state parameter in OAuth flows (CSRF)
- Redirect URI validation bypass
- OAuth tokens in URL fragments/parameters

CWE Coverage:
- CWE-352: Cross-Site Request Forgery (CSRF)
- CWE-601: URL Redirection to Untrusted Site ('Open Redirect')
- CWE-598: Use of GET Request Method With Sensitive Query Strings
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - File Filtering via Orchestrator
# ============================================================================
METADATA = RuleMetadata(
    name="oauth_security",
    category="auth",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=[
        'test/',
        'spec.',
        '.test.',
        '__tests__',
        'demo/',
        'example/'
    ],
    requires_jsx_pass=False,
    execution_scope='database'
)


# ============================================================================
# FROZENSETS FOR O(1) LOOKUPS
# ============================================================================

# OAuth URL patterns to check
OAUTH_URL_KEYWORDS = frozenset([
    'oauth',
    'authorize',
    'callback',
    'redirect',
    'auth',
    'login'
])

# State parameter variations
STATE_KEYWORDS = frozenset([
    'state',
    'csrf',
    'oauthState',
    'csrfToken',
    'oauthstate',
    'csrftoken'
])

# Redirect-related keywords
REDIRECT_KEYWORDS = frozenset([
    'redirect',
    'returnUrl',
    'return_url',
    'redirectUri',
    'redirect_uri',
    'redirect_url'
])

# User input sources
USER_INPUT_SOURCES = frozenset([
    'req.query',
    'req.params',
    'request.query',
    'request.params',
    'request.args'
])

# Validation function keywords
VALIDATION_KEYWORDS = frozenset([
    'validate',
    'whitelist',
    'allowed',
    'check',
    'verify'
])

# OAuth token patterns for URL detection
TOKEN_URL_PATTERNS = frozenset([
    '#access_token=',
    '#token=',
    '#accessToken=',
    '#id_token=',
    '#refresh_token=',
    '?access_token=',
    '&access_token=',
    '?token=',
    '&token=',
    '?accessToken=',
    '&accessToken='
])


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_oauth_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect OAuth and SSO security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.
    All pattern matching done in Python after database fetch.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of OAuth/SSO security findings

    Example findings:
        - OAuth redirect without state parameter
        - res.redirect(req.query.redirect_uri) without validation
        - const url = `/#access_token=${token}`
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # CHECK 1: Missing state parameter
        findings.extend(_check_missing_oauth_state(cursor))

        # CHECK 2: Redirect URI validation bypass
        findings.extend(_check_redirect_validation(cursor))

        # CHECK 3: Token in URL fragment/parameter
        findings.extend(_check_token_in_url(cursor))

    finally:
        conn.close()

    return findings


# ============================================================================
# CHECK 1: Missing OAuth State Parameter
# ============================================================================

def _check_missing_oauth_state(cursor) -> List[StandardFinding]:
    """Detect OAuth flows without state parameter.

    The state parameter prevents CSRF attacks in OAuth flows by:
    - Binding the authorization request to the user's session
    - Preventing attackers from injecting malicious authorization codes

    Without state, attackers can:
    1. Start OAuth flow for victim's account
    2. Capture authorization code
    3. Inject code into victim's session
    4. Gain access to victim's account

    CWE-352: Cross-Site Request Forgery (CSRF)
    """
    findings = []

    # Find all API endpoints
    query = build_query('api_endpoints', ['file', 'line', 'method', 'pattern'],
                        where="method IN ('GET', 'POST')",
                        order_by="file")
    cursor.execute(query)

    oauth_endpoints = []
    for file, line, method, pattern in cursor.fetchall():
        # Filter for OAuth-related endpoints in Python
        pattern_lower = pattern.lower()
        if any(keyword in pattern_lower for keyword in OAUTH_URL_KEYWORDS):
            oauth_endpoints.append((file, line, method, pattern))

    for file, line, method, pattern in oauth_endpoints:
        # Check if state parameter is generated/validated in this file
        check_query = build_query('function_call_args', ['argument_expr'],
                                  where="file = ?",
                                  limit=100)
        cursor.execute(check_query, [file])

        has_state = False
        for (arg_expr,) in cursor.fetchall():
            arg_lower = arg_expr.lower()
            if any(keyword in arg_lower for keyword in STATE_KEYWORDS):
                has_state = True
                break

        if not has_state:
            # Also check assignments for state generation
            assign_query = build_query('assignments', ['target_var', 'source_expr'],
                                       where="file = ?",
                                       limit=100)
            cursor.execute(assign_query, [file])

            for target_var, source_expr in cursor.fetchall():
                target_lower = target_var.lower()
                source_lower = source_expr.lower() if source_expr else ''
                if any(keyword in target_lower or keyword in source_lower for keyword in STATE_KEYWORDS):
                    has_state = True
                    break

        if not has_state:
            findings.append(StandardFinding(
                rule_name='oauth-missing-state',
                message=f'OAuth endpoint {pattern} missing state parameter (CSRF risk)',
                file_path=file,
                line=line or 1,
                severity=Severity.CRITICAL,
                category='authentication',
                cwe_id='CWE-352',
                confidence=Confidence.MEDIUM,
                snippet=f'{method} {pattern}',
                recommendation='Generate random state parameter and validate on callback'
            ))

    return findings


# ============================================================================
# CHECK 2: Redirect URI Validation Bypass
# ============================================================================

def _check_redirect_validation(cursor) -> List[StandardFinding]:
    """Detect OAuth redirect URI validation issues.

    Open redirect vulnerabilities in OAuth callbacks allow attackers to:
    - Steal authorization codes by redirecting to attacker-controlled domains
    - Phish users by appearing to come from legitimate domain

    Proper validation should:
    - Whitelist exact redirect URIs
    - Validate against registered URIs
    - Not use regex with loose patterns
    - Check protocol, domain, and path

    CWE-601: URL Redirection to Untrusted Site
    """
    findings = []

    # Find all redirect function calls
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        order_by="file, line")
    cursor.execute(query)

    redirect_calls = []
    for file, line, func, args in cursor.fetchall():
        # Filter for redirect functions in Python
        if 'redirect' in func.lower():
            # Check if argument contains user input
            args_lower = args.lower()
            if any(user_input in args_lower for user_input in USER_INPUT_SOURCES):
                redirect_calls.append((file, line, func, args))

    for file, line, func, args in redirect_calls:
        # Check if validation is performed nearby (within 10 lines before)
        val_query = build_query('function_call_args', ['callee_function', 'argument_expr'],
                               where="file = ? AND line >= ? AND line < ?")
        cursor.execute(val_query, [file, max(1, line - 10), line])

        has_validation = False
        for val_func, val_args in cursor.fetchall():
            val_func_lower = val_func.lower()
            val_args_lower = val_args.lower()
            if any(keyword in val_func_lower or keyword in val_args_lower for keyword in VALIDATION_KEYWORDS):
                has_validation = True
                break

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='oauth-unvalidated-redirect',
                message='OAuth redirect without URI validation (open redirect risk)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-601',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(user input)',
                recommendation='Validate redirect_uri against whitelist of registered URIs'
            ))

    # Also check for redirect_uri in assignments without validation
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        order_by="file, line")
    cursor.execute(query)

    redirect_assignments = []
    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()
        expr_lower = expr.lower() if expr else ''

        # Check if it's a redirect-related assignment
        if any(keyword in var_lower for keyword in REDIRECT_KEYWORDS):
            # Check if source is user input
            if any(user_input in expr_lower for user_input in USER_INPUT_SOURCES):
                redirect_assignments.append((file, line, var, expr))

    for file, line, var, expr in redirect_assignments:
        # Check for validation after assignment (within 10 lines)
        val_query = build_query('function_call_args', ['callee_function', 'argument_expr'],
                               where="file = ? AND line > ? AND line <= ?")
        cursor.execute(val_query, [file, line, line + 10])

        has_validation = False
        for val_func, val_args in cursor.fetchall():
            val_func_lower = val_func.lower()
            val_args_lower = val_args.lower()

            # Check if validation mentions the variable
            if var.lower() in val_args_lower:
                if any(keyword in val_func_lower for keyword in VALIDATION_KEYWORDS):
                    has_validation = True
                    break

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='oauth-redirect-assignment-unvalidated',
                message='Redirect URI from user input without validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-601',
                confidence=Confidence.LOW,
                snippet=f'{var} = {expr[:40]}' if len(expr) <= 40 else f'{var} = {expr[:40]}...',
                recommendation='Validate redirect_uri before use: check against whitelist'
            ))

    return findings


# ============================================================================
# CHECK 3: OAuth Token in URL Fragment/Parameter
# ============================================================================

def _check_token_in_url(cursor) -> List[StandardFinding]:
    """Detect OAuth tokens in URL fragments or parameters.

    Tokens in URLs are exposed in:
    - Browser history
    - Server logs
    - Referrer headers
    - Proxy logs

    OAuth 2.0 best practices:
    - Use authorization code flow (not implicit flow)
    - Never put access_token in URL
    - Use token in Authorization header or POST body

    CWE-598: Use of GET Request Method With Sensitive Query Strings
    """
    findings = []

    # Find all assignments (fetch once, filter multiple ways)
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        order_by="file, line")
    cursor.execute(query)

    all_assignments = cursor.fetchall()

    # CHECK 3A: Token in URL fragment (#)
    for file, line, var, expr in all_assignments:
        if any(pattern in expr for pattern in ['#access_token=', '#token=', '#accessToken=', '#id_token=', '#refresh_token=']):
            findings.append(StandardFinding(
                rule_name='oauth-token-in-url-fragment',
                message='OAuth token in URL fragment (exposed in browser history)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-598',
                confidence=Confidence.HIGH,
                snippet=expr[:60] if len(expr) <= 60 else expr[:60] + '...',
                recommendation='Use authorization code flow; never put tokens in URL'
            ))

    # CHECK 3B: Token in query parameter (?)
    for file, line, var, expr in all_assignments:
        token_patterns = ['?access_token=', '&access_token=', '?token=', '&token=', '?accessToken=', '&accessToken=']
        if any(pattern in expr for pattern in token_patterns):
            findings.append(StandardFinding(
                rule_name='oauth-token-in-url-param',
                message='OAuth token in URL query parameter (logged by servers)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-598',
                confidence=Confidence.HIGH,
                snippet=expr[:60] if len(expr) <= 60 else expr[:60] + '...',
                recommendation='Send tokens in Authorization header or POST body, not URL'
            ))

    # CHECK 3C: Implicit flow usage (response_type=token)
    for file, line, var, expr in all_assignments:
        expr_lower = expr.lower()
        if 'response_type' in expr_lower and 'token' in expr_lower and 'code' not in expr_lower:
            findings.append(StandardFinding(
                rule_name='oauth-implicit-flow',
                message='OAuth implicit flow detected (response_type=token)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                cwe_id='CWE-598',
                confidence=Confidence.MEDIUM,
                snippet=expr[:60] if len(expr) <= 60 else expr[:60] + '...',
                recommendation='Use authorization code flow (response_type=code) instead of implicit flow'
            ))

    return findings
