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
# RULE METADATA - Smart File Filtering
# ============================================================================
METADATA = RuleMetadata(
    name="oauth_security",
    category="auth",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=[
        'frontend/',
        'client/',
        'test/',
        'spec.',
        '__tests__',
        'demo/',
        'example/'
    ],
    requires_jsx_pass=False
)


# ============================================================================
# GOLDEN STANDARD: FROZENSETS FOR O(1) LOOKUPS
# ============================================================================

# OAuth/SSO library functions
OAUTH_FUNCTIONS = frozenset([
    'passport.authenticate',
    'oauth2orize.authorize',
    'oauth2orize.token',
    'oauth.authorize',
    'oauth2.authorizationCode',
    'OAuthServer.authorize',
    'oauth2Server.authorize',
    'OAuth2Strategy',
    'OAuthStrategy',
    'authorize',
    'getAuthorizationUrl',
    'getAccessToken',
    'exchangeCode'
])

# OAuth URL patterns
OAUTH_URL_PATTERNS = frozenset([
    '/oauth/authorize',
    '/oauth/callback',
    '/oauth/token',
    '/oauth/redirect',
    '/auth/authorize',
    '/auth/callback',
    '/auth/token',
    '/auth/redirect',
    '/api/oauth',
    '/api/auth',
    '/login/oauth'
])

# OAuth parameter names
OAUTH_PARAMS = frozenset([
    'state',
    'redirect_uri',
    'redirectUri',
    'redirect_url',
    'redirectUrl',
    'response_type',
    'client_id',
    'client_secret',
    'scope',
    'code',
    'access_token',
    'accessToken',
    'refresh_token',
    'refreshToken',
    'authorization_code',
    'authorizationCode'
])

# OAuth providers
OAUTH_PROVIDERS = frozenset([
    'google',
    'github',
    'facebook',
    'twitter',
    'linkedin',
    'microsoft',
    'apple',
    'okta',
    'auth0',
    'cognito'
])

# File path filtering patterns (exclude test/demo files)
FILE_FILTER_PATTERNS = frozenset([
    '%test%',
    '%spec.%',
    '%.test.%',
    '%__tests__%',
    '%demo%',
    '%example%'
])


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_oauth_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect OAuth and SSO security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.

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

    # Find OAuth authorization endpoints
    query = build_query('api_endpoints', ['file', 'method', 'pattern'],
                        where="""(pattern LIKE '%/oauth%'
               OR pattern LIKE '%/auth%'
               OR pattern LIKE '%/authorize%'
               OR pattern LIKE '%/login%')
          AND method IN ('GET', 'POST')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file")
    cursor.execute(query)

    oauth_endpoints = cursor.fetchall()

    for file, method, pattern in oauth_endpoints:
        # Skip if it's clearly not an OAuth endpoint
        if not any(oauth_pattern in pattern.lower() for oauth_pattern in ['oauth', 'authorize', 'callback', 'redirect']):
            continue

        # Check if state parameter is generated/validated
        check_query = build_query('function_call_args', ['COUNT(*)'],
                                  where="""file = ?
              AND (argument_expr LIKE '%state%'
                   OR argument_expr LIKE '%csrf%'
                   OR argument_expr LIKE '%oauthState%'
                   OR argument_expr LIKE '%csrfToken%')""")
        cursor.execute(check_query, [file])

        has_state = cursor.fetchone()[0] > 0

        if not has_state:
            # Also check assignments for state generation
            assign_query = build_query('assignments', ['COUNT(*)'],
                                       where="""file = ?
                  AND (target_var LIKE '%state%'
                       OR target_var LIKE '%oauthState%'
                       OR target_var LIKE '%csrfToken%'
                       OR source_expr LIKE '%state%')""")
            cursor.execute(assign_query, [file])

            has_state_assignment = cursor.fetchone()[0] > 0

            if not has_state_assignment:
                findings.append(StandardFinding(
                    rule_name='oauth-missing-state',
                    message=f'OAuth endpoint {pattern} missing state parameter (CSRF risk)',
                    file_path=file,
                    line=1,  # Endpoint-level finding
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

    # Find redirect operations with user-controlled URLs
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        where="""(callee_function LIKE '%.redirect%'
               OR callee_function LIKE 'redirect%')
          AND (argument_expr LIKE '%req.query%'
               OR argument_expr LIKE '%req.params%'
               OR argument_expr LIKE '%request.query%'
               OR argument_expr LIKE '%redirect_uri%'
               OR argument_expr LIKE '%redirectUri%'
               OR argument_expr LIKE '%redirect_url%'
               OR argument_expr LIKE '%return_url%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        # Check if validation is performed nearby (within 10 lines before)
        val_query = build_query('function_call_args', ['COUNT(*)'],
                               where="""file = ?
              AND line >= ? AND line < ?
              AND (callee_function LIKE '%validate%'
                   OR callee_function LIKE '%whitelist%'
                   OR callee_function LIKE '%allowed%'
                   OR callee_function LIKE '%check%'
                   OR argument_expr LIKE '%whitelist%'
                   OR argument_expr LIKE '%allowed%')""")
        cursor.execute(val_query, [file, max(1, line - 10), line])

        has_validation = cursor.fetchone()[0] > 0

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='oauth-unvalidated-redirect',
                message=f'OAuth redirect without URI validation (open redirect risk)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-601',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(req.query.redirect_uri)',
                recommendation='Validate redirect_uri against whitelist of registered URIs'
            ))

    # Also check for redirect_uri in assignments without validation
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""(target_var LIKE '%redirect%'
               OR target_var LIKE '%returnUrl%')
          AND (source_expr LIKE '%req.query%'
               OR source_expr LIKE '%req.params%'
               OR source_expr LIKE '%request.query%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        # Check for validation after assignment (within 10 lines)
        val_query = build_query('function_call_args', ['COUNT(*)'],
                               where="""file = ?
              AND line > ? AND line <= ?
              AND argument_expr LIKE ?
              AND (callee_function LIKE '%validate%'
                   OR callee_function LIKE '%check%'
                   OR callee_function LIKE '%whitelist%')""")
        cursor.execute(val_query, [file, line, line + 10, f'%{var}%'])

        has_validation = cursor.fetchone()[0] > 0

        if not has_validation:
            findings.append(StandardFinding(
                rule_name='oauth-redirect-assignment-unvalidated',
                message=f'Redirect URI from user input without validation',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-601',
                confidence=Confidence.LOW,
                snippet=f'{var} = {expr[:40]}...',
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

    # Find URL construction with token in fragment (#)
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""(source_expr LIKE '%#access_token=%'
               OR source_expr LIKE '%#token=%'
               OR source_expr LIKE '%#accessToken=%'
               OR source_expr LIKE '%#id_token=%'
               OR source_expr LIKE '%#refresh_token=%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='oauth-token-in-url-fragment',
            message='OAuth token in URL fragment (exposed in browser history)',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='authentication',
            cwe_id='CWE-598',
            confidence=Confidence.HIGH,
            snippet=expr[:60] + '...',
            recommendation='Use authorization code flow; never put tokens in URL'
        ))

    # Find URL construction with token in query parameter (?)
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""(source_expr LIKE '%?access_token=%'
               OR source_expr LIKE '%&access_token=%'
               OR source_expr LIKE '%?token=%'
               OR source_expr LIKE '%&token=%'
               OR source_expr LIKE '%?accessToken=%'
               OR source_expr LIKE '%&accessToken=%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='oauth-token-in-url-param',
            message='OAuth token in URL query parameter (logged by servers)',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='authentication',
            cwe_id='CWE-598',
            confidence=Confidence.HIGH,
            snippet=expr[:60] + '...',
            recommendation='Send tokens in Authorization header or POST body, not URL'
        ))

    # Also check for implicit flow usage (response_type=token)
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""source_expr LIKE '%response_type%'
          AND (source_expr LIKE '%token%'
               OR source_expr LIKE '%id_token%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        # Check if it's using implicit flow (response_type=token instead of code)
        if 'response_type' in expr and 'token' in expr and 'code' not in expr:
            findings.append(StandardFinding(
                rule_name='oauth-implicit-flow',
                message='OAuth implicit flow detected (response_type=token)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                cwe_id='CWE-598',
                confidence=Confidence.MEDIUM,
                snippet=expr[:60] + '...',
                recommendation='Use authorization code flow (response_type=code) instead of implicit flow'
            ))

    return findings
