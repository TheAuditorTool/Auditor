"""Session Management Security Analyzer - Database-First Approach.

Detects session and cookie security vulnerabilities using database-driven approach.
Follows gold standard patterns from jwt_analyze.py.

NO AST TRAVERSAL. NO FILE I/O. PURE DATABASE QUERIES.

Detects:
- Missing httpOnly flag on session cookies (XSS can steal sessions)
- Missing secure flag on cookies (MITM attacks)
- Missing SameSite attribute (CSRF attacks)
- Session fixation vulnerabilities
- Missing session timeout/expiration

CWE Coverage:
- CWE-1004: Sensitive Cookie Without 'HttpOnly' Flag
- CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
- CWE-352: Cross-Site Request Forgery (CSRF)
- CWE-384: Session Fixation
- CWE-613: Insufficient Session Expiration
"""

import sqlite3
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA - Smart File Filtering
# ============================================================================
METADATA = RuleMetadata(
    name="session_security",
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

# Cookie-setting functions across frameworks
COOKIE_FUNCTIONS = frozenset([
    'res.cookie',
    'response.cookie',
    'reply.cookie',
    'ctx.cookies.set',
    'cookies.set',
    'res.setHeader',
    'response.setHeader',
    'reply.header'
])

# Session management functions
SESSION_FUNCTIONS = frozenset([
    'session',
    'req.session',
    'request.session',
    'session.create',
    'session.regenerate',
    'session.destroy',
    'express-session',
    'cookie-session'
])

# Required cookie security flags
REQUIRED_COOKIE_FLAGS = frozenset([
    'httpOnly',
    'secure',
    'sameSite'
])

# Session-related variable keywords
SESSION_KEYWORDS = frozenset([
    'session',
    'sessionId',
    'sessionID',
    'session_id',
    'sid',
    'sess',
    'sessionToken',
    'authSession'
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

def find_session_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect session and cookie security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of session security findings

    Example findings:
        - res.cookie('token', jwt) without httpOnly flag
        - session() middleware without maxAge configuration
        - req.session.userId = user.id without session.regenerate()
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
        if 'function_call_args' in existing_tables:
            # CHECK 1: Missing httpOnly flag
            findings.extend(_check_missing_httponly(cursor, existing_tables))

            # CHECK 2: Missing secure flag
            findings.extend(_check_missing_secure(cursor, existing_tables))

            # CHECK 3: Missing SameSite attribute
            findings.extend(_check_missing_samesite(cursor, existing_tables))

            # CHECK 5: Missing session timeout
            findings.extend(_check_missing_timeout(cursor, existing_tables))

        if 'function_call_args' in existing_tables and 'assignments' in existing_tables:
            # CHECK 4: Session fixation
            findings.extend(_check_session_fixation(cursor, existing_tables))

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
            'function_call_args',
            'assignments',
            'symbols',
            'files'
        )
    """)
    return {row[0] for row in cursor.fetchall()}


# ============================================================================
# CHECK 1: Missing httpOnly Flag
# ============================================================================

def _check_missing_httponly(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect cookies set without httpOnly flag.

    Without httpOnly flag, JavaScript can access cookies via document.cookie,
    making them vulnerable to XSS attacks.

    CWE-1004: Sensitive Cookie Without 'HttpOnly' Flag
    """
    findings = []

    # Find all cookie-setting operations
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.cookie'
               OR callee_function LIKE '%cookies.set%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if httpOnly is missing
        if 'httpOnly' not in args_str:
            findings.append(StandardFinding(
                rule_name='session-missing-httponly',
                message='Cookie set without httpOnly flag (XSS can steal session)',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                cwe_id='CWE-1004',
                confidence=Confidence.HIGH,
                snippet=f'{func}(...)',
                recommendation='Set httpOnly: true in cookie options to prevent JavaScript access'
            ))

        # Check if httpOnly is explicitly disabled
        elif 'httpOnly:false' in args_str.replace(' ', '') or 'httpOnly: false' in args_str:
            findings.append(StandardFinding(
                rule_name='session-httponly-disabled',
                message='Cookie httpOnly flag explicitly disabled',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                cwe_id='CWE-1004',
                confidence=Confidence.HIGH,
                snippet=f'{func}(...httpOnly: false...)',
                recommendation='Remove httpOnly: false to enable default protection'
            ))

    return findings


# ============================================================================
# CHECK 2: Missing secure Flag
# ============================================================================

def _check_missing_secure(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect cookies set without secure flag.

    Without secure flag, cookies can be transmitted over unencrypted HTTP,
    making them vulnerable to man-in-the-middle attacks.

    CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
    """
    findings = []

    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.cookie'
               OR callee_function LIKE '%cookies.set%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if secure flag is missing
        if 'secure' not in args_str.lower():
            findings.append(StandardFinding(
                rule_name='session-missing-secure',
                message='Cookie set without secure flag (vulnerable to MITM)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-614',
                confidence=Confidence.HIGH,
                snippet=f'{func}(...)',
                recommendation='Set secure: true to ensure cookies only sent over HTTPS'
            ))

        # Check if secure is explicitly disabled
        elif 'secure:false' in args_str.replace(' ', '') or 'secure: false' in args_str:
            findings.append(StandardFinding(
                rule_name='session-secure-disabled',
                message='Cookie secure flag explicitly disabled',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-614',
                confidence=Confidence.HIGH,
                snippet=f'{func}(...secure: false...)',
                recommendation='Set secure: true for production environments'
            ))

    return findings


# ============================================================================
# CHECK 3: Missing SameSite Attribute
# ============================================================================

def _check_missing_samesite(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect cookies set without SameSite attribute.

    Without SameSite attribute, cookies are sent with cross-site requests,
    making them vulnerable to CSRF attacks.

    CWE-352: Cross-Site Request Forgery (CSRF)
    """
    findings = []

    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.cookie'
               OR callee_function LIKE '%cookies.set%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if SameSite is missing
        if 'sameSite' not in args_str and 'samesite' not in args_str.lower():
            findings.append(StandardFinding(
                rule_name='session-missing-samesite',
                message='Cookie set without SameSite attribute (CSRF risk)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-352',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(...)',
                recommendation='Set sameSite: "strict" or "lax" to prevent CSRF attacks'
            ))

        # Check if SameSite is set to None (disables protection)
        elif 'sameSite:"none"' in args_str.replace(' ', '').lower() or "sameSite:'none'" in args_str.replace(' ', '').lower():
            findings.append(StandardFinding(
                rule_name='session-samesite-none',
                message='Cookie SameSite set to "none" (disables CSRF protection)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-352',
                confidence=Confidence.HIGH,
                snippet=f'{func}(...sameSite: "none"...)',
                recommendation='Use sameSite: "strict" or "lax" instead of "none"'
            ))

    return findings


# ============================================================================
# CHECK 4: Session Fixation
# ============================================================================

def _check_session_fixation(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect session fixation vulnerabilities.

    Session fixation occurs when session ID is not regenerated after login,
    allowing attackers to hijack authenticated sessions.

    CWE-384: Session Fixation
    """
    findings = []

    # Find assignments to session variables (indicating login/authentication)
    cursor.execute("""
        SELECT DISTINCT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%session.%'
               OR a.target_var LIKE '%req.session.%'
               OR a.target_var LIKE '%request.session.%')
          AND (a.target_var LIKE '%user%'
               OR a.target_var LIKE '%userId%'
               OR a.target_var LIKE '%authenticated%'
               OR a.target_var LIKE '%logged%')
          AND a.file NOT LIKE '%test%'
          AND a.file NOT LIKE '%spec.%'
          AND a.file NOT LIKE '%.test.%'
          AND a.file NOT LIKE '%__tests__%'
          AND a.file NOT LIKE '%demo%'
          AND a.file NOT LIKE '%example%'
        ORDER BY a.file, a.line
    """)

    session_assignments = cursor.fetchall()

    for file, line, var, expr in session_assignments:
        # Check if session.regenerate() is called nearby (within 10 lines)
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 10
              AND callee_function LIKE '%session.regenerate%'
        """, [file, line])

        has_regenerate = cursor.fetchone()[0] > 0

        if not has_regenerate:
            findings.append(StandardFinding(
                rule_name='session-fixation',
                message=f'Session variable {var} set without session.regenerate() (session fixation risk)',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-384',
                confidence=Confidence.MEDIUM,
                snippet=f'{var} = {expr[:50]}...',
                recommendation='Call session.regenerate() before setting authentication state'
            ))

    return findings


# ============================================================================
# CHECK 5: Missing Session Timeout
# ============================================================================

def _check_missing_timeout(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect session configuration without timeout/expiration.

    Sessions without expiration can be valid indefinitely, increasing
    the window for session hijacking attacks.

    CWE-613: Insufficient Session Expiration
    """
    findings = []

    # Find session middleware configuration
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%session%'
               OR callee_function = 'session')
          AND argument_index = 0
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if maxAge or expires is missing
        if 'maxAge' not in args_str and 'expires' not in args_str and 'ttl' not in args_str:
            findings.append(StandardFinding(
                rule_name='session-no-timeout',
                message='Session configuration missing expiration (maxAge/expires/ttl)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                cwe_id='CWE-613',
                confidence=Confidence.MEDIUM,
                snippet=f'{func}(...)',
                recommendation='Set cookie.maxAge or expires to limit session lifetime'
            ))

    # Also check cookie configurations for session cookies
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.cookie')
          AND (argument_expr LIKE '%session%'
               OR argument_expr LIKE '%auth%'
               OR argument_expr LIKE '%token%')
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        args_str = args if args else ''

        # Check if maxAge or expires is present in cookie options
        if 'maxAge' not in args_str and 'expires' not in args_str:
            findings.append(StandardFinding(
                rule_name='session-cookie-no-expiration',
                message='Session cookie set without expiration (maxAge/expires)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                cwe_id='CWE-613',
                confidence=Confidence.LOW,
                snippet=f'{func}(...)',
                recommendation='Set maxAge or expires to automatically expire session cookies'
            ))

    return findings
