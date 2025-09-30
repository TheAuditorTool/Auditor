"""Password Security Analyzer - Database-First Approach.

Detects password security vulnerabilities using database-driven approach.
Follows gold standard patterns from jwt_analyze.py.

NO AST TRAVERSAL. NO FILE I/O. PURE DATABASE QUERIES.

Detects:
- Weak password hashing algorithms (MD5, SHA1)
- Hardcoded passwords in source code
- Lack of password complexity enforcement
- Passwords in GET request parameters

CWE Coverage:
- CWE-327: Use of Broken or Risky Cryptographic Algorithm
- CWE-259: Use of Hard-coded Password
- CWE-521: Weak Password Requirements
- CWE-598: Use of GET Request Method With Sensitive Query Strings
"""

import sqlite3
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# GOLDEN STANDARD: FROZENSETS FOR O(1) LOOKUPS
# ============================================================================

# Weak hash algorithms (broken for password hashing)
WEAK_HASH_ALGORITHMS = frozenset([
    'md5',
    'MD5',
    'sha1',
    'SHA1',
    'sha',
    'SHA',
    'hashlib.md5',
    'hashlib.sha1',
    'hashlib.sha',
    'crypto.createHash("md5")',
    'crypto.createHash("sha1")',
    'crypto.createHash',
    'Crypto.Hash.MD5',
    'Crypto.Hash.SHA1'
])

# Strong password hashing algorithms
STRONG_HASH_ALGORITHMS = frozenset([
    'bcrypt',
    'scrypt',
    'argon2',
    'pbkdf2',
    'bcrypt.hash',
    'bcrypt.hashSync',
    'bcrypt.compare',
    'argon2.hash',
    'argon2.verify',
    'crypto.pbkdf2',
    'crypto.scrypt',
    'Crypto.Protocol.KDF.scrypt',
    'Crypto.Protocol.KDF.PBKDF2'
])

# Password-related keywords
PASSWORD_KEYWORDS = frozenset([
    'password',
    'passwd',
    'pwd',
    'passphrase',
    'pass',
    'user_password',
    'userPassword',
    'userPwd',
    'admin_password',
    'adminPassword'
])

# Common weak/default passwords
WEAK_PASSWORDS = frozenset([
    'password',
    'Password',
    'PASSWORD',
    'admin',
    'Admin',
    'ADMIN',
    '123456',
    'changeme',
    'default',
    'test',
    'demo',
    'sample',
    'password123',
    'admin123',
    'root',
    'toor',
    'pass',
    'secret',
    'qwerty',
    'letmein'
])

# Placeholder password values (not real secrets)
PASSWORD_PLACEHOLDERS = frozenset([
    'your_password_here',
    'YOUR_PASSWORD',
    'PASSWORD_HERE',
    'CHANGE_ME',
    'changeme',
    'placeholder',
    '<password>',
    '${PASSWORD}',
    '{{PASSWORD}}'
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

def find_password_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect password security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of password security findings

    Example findings:
        - const hashed = md5(password)
        - const adminPassword = "admin123"
        - const url = `/reset?password=${pwd}`
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
            # CHECK 1: Weak password hashing
            findings.extend(_check_weak_password_hashing(cursor, existing_tables))

        if 'assignments' in existing_tables:
            # CHECK 2: Hardcoded passwords
            findings.extend(_check_hardcoded_passwords(cursor, existing_tables))

            # CHECK 4: Passwords in GET parameters
            findings.extend(_check_password_in_url(cursor, existing_tables))

        if 'function_call_args' in existing_tables:
            # CHECK 3: Lack of password complexity enforcement
            findings.extend(_check_weak_complexity(cursor, existing_tables))

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
# CHECK 1: Weak Password Hashing
# ============================================================================

def _check_weak_password_hashing(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect weak hash algorithms used for passwords.

    MD5 and SHA1 are broken for password hashing - fast to brute force
    and vulnerable to rainbow table attacks.

    CWE-327: Use of Broken or Risky Cryptographic Algorithm
    """
    findings = []

    # Find hash operations on password-like variables
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%md5%'
               OR f.callee_function LIKE '%MD5%'
               OR f.callee_function LIKE '%sha1%'
               OR f.callee_function LIKE '%SHA1%'
               OR f.callee_function LIKE 'hashlib.md5'
               OR f.callee_function LIKE 'hashlib.sha1'
               OR f.callee_function LIKE 'crypto.createHash')
          AND (f.argument_expr LIKE '%password%'
               OR f.argument_expr LIKE '%passwd%'
               OR f.argument_expr LIKE '%pwd%'
               OR f.argument_expr LIKE '%passphrase%')
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        # Determine which weak algorithm is being used
        algo = 'MD5' if 'md5' in func.lower() else 'SHA1' if 'sha1' in func.lower() else 'weak hash'

        findings.append(StandardFinding(
            rule_name='password-weak-hashing',
            message=f'Weak hash algorithm {algo} used for passwords',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='authentication',
            cwe_id='CWE-327',
            confidence=Confidence.HIGH,
            snippet=f'{func}({args[:40]}...)',
            recommendation='Use bcrypt, scrypt, or argon2 for password hashing'
        ))

    # Also check for createHash with MD5/SHA1 in arguments
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%createHash%'
          AND (f.argument_expr LIKE '%"md5"%'
               OR f.argument_expr LIKE "%'md5'%"
               OR f.argument_expr LIKE '%"sha1"%'
               OR f.argument_expr LIKE "%'sha1'%")
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        algo = 'MD5' if 'md5' in args.lower() else 'SHA1'

        # Check if this is being used in password context (nearby)
        cursor.execute("""
            SELECT COUNT(*) FROM assignments
            WHERE file = ?
              AND ABS(line - ?) <= 5
              AND (target_var LIKE '%password%'
                   OR target_var LIKE '%passwd%'
                   OR target_var LIKE '%pwd%'
                   OR source_expr LIKE '%password%'
                   OR source_expr LIKE '%passwd%')
        """, [file, line])

        if cursor.fetchone()[0] > 0:
            findings.append(StandardFinding(
                rule_name='password-weak-hashing-createhash',
                message=f'crypto.createHash("{algo.lower()}") used in password context',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                cwe_id='CWE-327',
                confidence=Confidence.HIGH,
                snippet=f'{func}("{algo.lower()}")',
                recommendation='Use bcrypt, scrypt, or argon2 for password hashing'
            ))

    return findings


# ============================================================================
# CHECK 2: Hardcoded Passwords
# ============================================================================

def _check_hardcoded_passwords(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect hardcoded passwords in source code.

    Hardcoded passwords are a critical security risk as they:
    - Cannot be rotated without code changes
    - Are visible to anyone with code access
    - Often leaked in version control

    CWE-259: Use of Hard-coded Password
    """
    findings = []

    # Build query for password-related variable assignments
    password_keywords_list = list(PASSWORD_KEYWORDS)
    keyword_conditions = ' OR '.join([f'target_var LIKE ?' for _ in password_keywords_list])
    params = [f'%{kw}%' for kw in password_keywords_list]

    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE ({keyword_conditions})
          AND source_expr NOT LIKE '%process.env%'
          AND source_expr NOT LIKE '%import.meta.env%'
          AND source_expr NOT LIKE '%os.environ%'
          AND source_expr NOT LIKE '%getenv%'
          AND source_expr NOT LIKE '%config%'
          AND source_expr NOT LIKE '%process.argv%'
          AND file NOT LIKE '%test%'
          AND file NOT LIKE '%spec.%'
          AND file NOT LIKE '%.test.%'
          AND file NOT LIKE '%__tests__%'
          AND file NOT LIKE '%demo%'
          AND file NOT LIKE '%example%'
        ORDER BY file, line
    """, params)

    for file, line, var, expr in cursor.fetchall():
        # Clean the expression
        expr_clean = expr.strip().strip('\'"')

        # Skip if it's a placeholder
        if expr_clean in PASSWORD_PLACEHOLDERS:
            continue

        # Skip empty strings
        if not expr_clean or expr_clean in ('', '""', "''"):
            continue

        # Check if it's a literal string (hardcoded)
        if expr and (expr.strip().startswith('"') or expr.strip().startswith("'") or expr.strip().startswith('b"') or expr.strip().startswith("b'")):
            # Check length to avoid false positives on empty strings
            if len(expr_clean) > 0:
                # Check if it's a weak/default password
                if expr_clean in WEAK_PASSWORDS:
                    findings.append(StandardFinding(
                        rule_name='password-weak-default',
                        message=f'Weak/default password "{expr_clean}" in variable "{var}"',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='authentication',
                        cwe_id='CWE-521',
                        confidence=Confidence.HIGH,
                        snippet=f'{var} = "{expr_clean}"',
                        recommendation='Use strong, randomly generated passwords'
                    ))
                # Any other hardcoded password
                elif len(expr_clean) >= 6:  # Minimum password length
                    findings.append(StandardFinding(
                        rule_name='password-hardcoded',
                        message=f'Hardcoded password in variable "{var}"',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='authentication',
                        cwe_id='CWE-259',
                        confidence=Confidence.HIGH,
                        snippet=f'{var} = "***REDACTED***"',
                        recommendation='Store passwords in environment variables or secure secret management systems'
                    ))

    return findings


# ============================================================================
# CHECK 3: Weak Password Complexity Enforcement
# ============================================================================

def _check_weak_complexity(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect lack of password complexity enforcement.

    Strong passwords should enforce:
    - Minimum length (12+ characters)
    - Character diversity (upper, lower, numbers, symbols)
    - No common passwords

    CWE-521: Weak Password Requirements
    """
    findings = []

    # Find password validation functions
    cursor.execute("""
        SELECT f.file, f.line, f.caller_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.argument_expr LIKE '%password%'
               OR f.argument_expr LIKE '%passwd%'
               OR f.argument_expr LIKE '%pwd%')
          AND (f.callee_function LIKE '%validate%'
               OR f.callee_function LIKE '%check%'
               OR f.callee_function LIKE '%verify%'
               OR f.callee_function LIKE '%test%'
               OR f.callee_function LIKE '%.length%')
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    validation_calls = cursor.fetchall()

    for file, line, caller, args in validation_calls:
        args_str = args if args else ''

        # Check for weak length requirements (< 8 characters)
        if '.length' in args_str:
            # Look for comparison with weak minimum
            if any(weak in args_str for weak in ['> 4', '> 5', '> 6', '> 7', '>= 6', '>= 7', '>= 8']):
                findings.append(StandardFinding(
                    rule_name='password-weak-length-requirement',
                    message=f'Weak password length requirement (< 12 characters)',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='authentication',
                    cwe_id='CWE-521',
                    confidence=Confidence.MEDIUM,
                    snippet=args_str[:60],
                    recommendation='Enforce minimum password length of 12+ characters'
                ))

    # Also check for simple length checks in assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%password.length%'
               OR a.source_expr LIKE '%pwd.length%'
               OR a.source_expr LIKE '%passwd.length%')
          AND (a.source_expr LIKE '%> 6%'
               OR a.source_expr LIKE '%> 7%'
               OR a.source_expr LIKE '%> 8%'
               OR a.source_expr LIKE '%>= 8%')
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
            rule_name='password-weak-validation',
            message='Password validation only checks length (no complexity requirements)',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='authentication',
            cwe_id='CWE-521',
            confidence=Confidence.MEDIUM,
            snippet=expr[:60],
            recommendation='Enforce password complexity: length, uppercase, lowercase, numbers, symbols'
        ))

    return findings


# ============================================================================
# CHECK 4: Password in GET Request Parameters
# ============================================================================

def _check_password_in_url(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Detect passwords in GET request parameters.

    Passwords in URLs are logged in:
    - Browser history
    - Server access logs
    - Proxy logs
    - Referrer headers

    CWE-598: Use of GET Request Method With Sensitive Query Strings
    """
    findings = []

    # Find URL construction with password parameters
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%?password=%'
               OR a.source_expr LIKE '%&password=%'
               OR a.source_expr LIKE '%?passwd=%'
               OR a.source_expr LIKE '%&passwd=%'
               OR a.source_expr LIKE '%?pwd=%'
               OR a.source_expr LIKE '%&pwd=%')
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
            rule_name='password-in-url',
            message='Password transmitted in URL query parameter',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='authentication',
            cwe_id='CWE-598',
            confidence=Confidence.HIGH,
            snippet=expr[:60] + '...',
            recommendation='Use POST requests with password in request body, never in URL'
        ))

    # Also check function calls that build URLs
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%url%'
               OR f.callee_function LIKE '%URL%'
               OR f.callee_function LIKE '%uri%'
               OR f.callee_function LIKE '%query%')
          AND (f.argument_expr LIKE '%password%'
               OR f.argument_expr LIKE '%passwd%'
               OR f.argument_expr LIKE '%pwd%')
          AND (f.argument_expr LIKE '%?%'
               OR f.argument_expr LIKE '%&%')
          AND f.file NOT LIKE '%test%'
          AND f.file NOT LIKE '%spec.%'
          AND f.file NOT LIKE '%.test.%'
          AND f.file NOT LIKE '%__tests__%'
          AND f.file NOT LIKE '%demo%'
          AND f.file NOT LIKE '%example%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='password-in-url-construction',
            message=f'Password used in URL construction via {func}',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='authentication',
            cwe_id='CWE-598',
            confidence=Confidence.MEDIUM,
            snippet=f'{func}(...password...)',
            recommendation='Never include passwords in URLs - use POST with body payload'
        ))

    return findings
