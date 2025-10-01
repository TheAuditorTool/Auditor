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
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


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
        # Check which tables exist (graceful degradation)
        existing_tables = _check_tables(cursor)
        if not existing_tables:
            return findings

        # Run security checks
        if 'api_endpoints' in existing_tables and 'function_call_args' in existing_tables:
            # CHECK 1: Missing state parameter
            findings.extend(_check_missing_oauth_state(cursor, existing_tables))

        if 'function_call_args' in existing_tables:
            # CHECK 2: Redirect URI validation bypass
            findings.extend(_check_redirect_validation(cursor, existing_tables))

        if 'assignments' in existing_tables:
            # CHECK 3: Token in URL fragment/parameter
            findings.extend(_check_token_in_url(cursor, existing_tables))

    finally:
        conn.close()

    return findings


# ============================================================================
# HELPER: Table Existence Check
# ============================================================================

def _check_tables(cursor) -> Set[str]:
    """Check which tables exist in database for graceful degradation."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN (
            'api_endpoints',
            'function_call_args',
            'assignments',
            'symbols',
            'files'
        )
    """)
    return {row[0] for row in cursor.fetchall()}


# ============================================================================
# CHECK 1: Missing OAuth State Parameter
# ============================================================================

def _check_missing_oauth_state(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
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

    if 'api_endpoints' not in existing_tables:
        # Fallback: Check function calls for OAuth operations
        return _check_oauth_state_fallback(cursor, existing_tables)

    # Find OAuth authorization endpoints
    cursor.execute("""
        SELECT e.file, e.method, e.pattern
        FROM api_endpoints e
        WHERE (e.pattern LIKE '%/oauth%'
               OR e.pattern LIKE '%/auth%'
               OR e.pattern LIKE '%/authorize%'
               OR e.pattern LIKE '%/login%')
          AND e.method IN ('GET', 'POST')
          AND e.file NOT LIKE '%test%'
          AND e.file NOT LIKE '%spec.%'
          AND e.file NOT LIKE '%.test.%'
          AND e.file NOT LIKE '%__tests__%'
          AND e.file NOT LIKE '%demo%'
          AND e.file NOT LIKE '%example%'
        ORDER BY e.file
    """)

    oauth_endpoints = cursor.fetchall()

    for file, method, pattern in oauth_endpoints:
        # Skip if it's clearly not an OAuth endpoint
        if not any(oauth_pattern in pattern.lower() for oauth_pattern in ['oauth', 'authorize', 'callback', 'redirect']):
            continue

        # Check if state parameter is generated/validated
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND (argument_expr LIKE '%state%'
                   OR param_name = 'state'
                   OR argument_expr LIKE '%csrf%'
                   OR param_name = 'csrf')
        """, [file])

        has_state = cursor.fetchone()[0] > 0

        if not has_state:
            # Also check assignments for state generation
            cursor.execute("""
                SELECT COUNT(*) FROM assignments
                WHERE file = ?
                  AND (target_var LIKE '%state%'
                       OR target_var LIKE '%oauthState%'
                       OR target_var LIKE '%csrfToken%'
                       OR source_expr LIKE '%state%')
            """, [file])

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


def _check_oauth_state_fallback(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Fallback check for OAuth state when api_endpoints table unavailable."""
    findings = []

    # Find OAuth function calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%authorize%'
               OR f.callee_function LIKE '%oauth%'
               OR f.callee_function LIKE '%OAuth%'
               OR f.callee_function LIKE '%getAuthorizationUrl%')
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if state parameter is present
        if 'state' not in args_str.lower():
            findings.append(StandardFinding(
                rule_name='oauth-authorize-no-state',
                message=f'OAuth authorization call {func} without state parameter',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-352',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(...)',
                recommendation='Include state parameter in OAuth authorization URL'
            ))

    return findings


# ============================================================================
# CHECK 2: Redirect URI Validation Bypass
# ============================================================================

def _check_redirect_validation(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
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
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%.redirect%'
               OR f.callee_function LIKE 'redirect%')
          AND (f.argument_expr LIKE '%req.query%'
               OR f.argument_expr LIKE '%req.params%'
               OR f.argument_expr LIKE '%request.query%'
               OR f.argument_expr LIKE '%redirect_uri%'
               OR f.argument_expr LIKE '%redirectUri%'
               OR f.argument_expr LIKE '%redirect_url%'
               OR f.argument_expr LIKE '%return_url%')
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if validation is performed nearby (within 10 lines before)
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND line >= ? AND line < ?
              AND (callee_function LIKE '%validate%'
                   OR callee_function LIKE '%whitelist%'
                   OR callee_function LIKE '%allowed%'
                   OR callee_function LIKE '%check%'
                   OR argument_expr LIKE '%whitelist%'
                   OR argument_expr LIKE '%allowed%')
        """, [file, max(1, line - 10), line])

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
    if 'assignments' in existing_tables:
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE (a.target_var LIKE '%redirect%'
                   OR a.target_var LIKE '%returnUrl%')
              AND (a.source_expr LIKE '%req.query%'
                   OR a.source_expr LIKE '%req.params%'
                   OR a.source_expr LIKE '%request.query%')
              AND a.file NOT LIKE '%test%'
              AND a.file NOT LIKE '%spec.%'
              AND a.file NOT LIKE '%.test.%'
              AND a.file NOT LIKE '%__tests__%'
              AND a.file NOT LIKE '%demo%'
              AND a.file NOT LIKE '%example%'
            ORDER BY a.file, a.line
        """)

        for file, line, var, expr in cursor.fetchall():
            # Check for validation after assignment (within 10 lines)
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND line > ? AND line <= ?
                  AND (argument_expr LIKE ?
                       OR param_name = ?)
                  AND (callee_function LIKE '%validate%'
                       OR callee_function LIKE '%check%'
                       OR callee_function LIKE '%whitelist%')
            """, [file, line, line + 10, f'%{var}%', var])

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

def _check_token_in_url(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
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
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%#access_token=%'
               OR a.source_expr LIKE '%#token=%'
               OR a.source_expr LIKE '%#accessToken=%'
               OR a.source_expr LIKE '%#id_token=%'
               OR a.source_expr LIKE '%#refresh_token=%')
          AND a.file NOT LIKE '%test%'
          AND a.file NOT LIKE '%spec.%'
          AND a.file NOT LIKE '%.test.%'
          AND a.file NOT LIKE '%__tests__%'
          AND a.file NOT LIKE '%demo%'
          AND a.file NOT LIKE '%example%'
        ORDER BY a.file, a.line
    """)

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
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%?access_token=%'
               OR a.source_expr LIKE '%&access_token=%'
               OR a.source_expr LIKE '%?token=%'
               OR a.source_expr LIKE '%&token=%'
               OR a.source_expr LIKE '%?accessToken=%'
               OR a.source_expr LIKE '%&accessToken=%')
          AND a.file NOT LIKE '%test%'
          AND a.file NOT LIKE '%spec.%'
          AND a.file NOT LIKE '%.test.%'
          AND a.file NOT LIKE '%__tests__%'
          AND a.file NOT LIKE '%demo%'
          AND a.file NOT LIKE '%example%'
        ORDER BY a.file, a.line
    """)

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
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%response_type%'
          AND (a.source_expr LIKE '%token%'
               OR a.source_expr LIKE '%id_token%')
          AND a.file NOT LIKE '%test%'
          AND a.file NOT LIKE '%spec.%'
          AND a.file NOT LIKE '%.test.%'
          AND a.file NOT LIKE '%__tests__%'
          AND a.file NOT LIKE '%demo%'
          AND a.file NOT LIKE '%example%'
        ORDER BY a.file, a.line
    """)

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
