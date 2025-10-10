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
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - Smart File Filtering
# ============================================================================
METADATA = RuleMetadata(
    name="password_security",
    category="auth",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=[
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

# Weak hash algorithms (broken for password hashing)
# NOTE: These frozensets are currently unused (patterns hardcoded in SQL)
# TODO: Refactor to use frozensets in Python logic for O(1) lookups
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
    'createhash',  # Normalized form for matching
    'crypto.hash.md5',
    'crypto.hash.sha1'
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
        # CHECK 1: Weak password hashing
        findings.extend(_check_weak_password_hashing(cursor))

        # CHECK 2: Hardcoded passwords
        findings.extend(_check_hardcoded_passwords(cursor))

        # CHECK 3: Lack of password complexity enforcement
        findings.extend(_check_weak_complexity(cursor))

        # CHECK 4: Passwords in GET parameters
        findings.extend(_check_password_in_url(cursor))

    finally:
        conn.close()

    return findings


# ============================================================================
# CHECK 1: Weak Password Hashing
# ============================================================================

def _check_weak_password_hashing(cursor) -> List[StandardFinding]:
    """Detect weak hash algorithms used for passwords.

    MD5 and SHA1 are broken for password hashing - fast to brute force
    and vulnerable to rainbow table attacks.

    CWE-327: Use of Broken or Risky Cryptographic Algorithm
    """
    findings = []

    # Find hash operations on password-like variables
    # NOTE: File filtering handled by orchestrator via METADATA exclude_patterns
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        where="""(callee_function LIKE '%md5%'
               OR callee_function LIKE '%MD5%'
               OR callee_function LIKE '%sha1%'
               OR callee_function LIKE '%SHA1%'
               OR callee_function LIKE 'hashlib.md5'
               OR callee_function LIKE 'hashlib.sha1'
               OR callee_function LIKE 'crypto.createHash')
          AND (argument_expr LIKE '%password%'
               OR argument_expr LIKE '%passwd%'
               OR argument_expr LIKE '%pwd%'
               OR argument_expr LIKE '%passphrase%')""",
                        order_by="file, line")
    cursor.execute(query)

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
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        where="""callee_function LIKE '%createHash%'
          AND (argument_expr LIKE '%"md5"%'
               OR argument_expr LIKE "%'md5'%"
               OR argument_expr LIKE '%"sha1"%'
               OR argument_expr LIKE "%'sha1'%")""",
                        order_by="file, line")
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        algo = 'MD5' if 'md5' in args.lower() else 'SHA1'

        # Check if this is being used in password context (nearby)
        # NOTE: Using manual SQL for COUNT(*) since build_query() doesn't support aggregate functions
        cursor.execute("""
            SELECT COUNT(*)
            FROM assignments
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

def _check_hardcoded_passwords(cursor) -> List[StandardFinding]:
    """Detect hardcoded passwords in source code.

    Hardcoded passwords are a critical security risk as they:
    - Cannot be rotated without code changes
    - Are visible to anyone with code access
    - Often leaked in version control

    CWE-259: Use of Hard-coded Password
    """
    findings = []

    # Build query for password-related variable assignments using schema-compliant approach
    password_keywords_list = list(PASSWORD_KEYWORDS)
    keyword_conditions = ' OR '.join(['target_var LIKE ?' for _ in password_keywords_list])
    params = [f'%{kw}%' for kw in password_keywords_list]

    # Use build_query with proper where parameter
    where_clause = (
        f"({keyword_conditions}) "
        "AND source_expr NOT LIKE '%process.env%' "
        "AND source_expr NOT LIKE '%import.meta.env%' "
        "AND source_expr NOT LIKE '%os.environ%' "
        "AND source_expr NOT LIKE '%getenv%' "
        "AND source_expr NOT LIKE '%config%' "
        "AND source_expr NOT LIKE '%process.argv%'"
    )

    # Build query using schema contract system
    query = build_query('assignments',
                       ['file', 'line', 'target_var', 'source_expr'],
                       where=where_clause,
                       order_by="file, line")

    cursor.execute(query, params)

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

def _check_weak_complexity(cursor) -> List[StandardFinding]:
    """Detect lack of password complexity enforcement.

    Strong passwords should enforce:
    - Minimum length (12+ characters)
    - Character diversity (upper, lower, numbers, symbols)
    - No common passwords

    CWE-521: Weak Password Requirements
    """
    findings = []

    # Find password validation functions
    query = build_query('function_call_args', ['file', 'line', 'caller_function', 'argument_expr'],
                        where="""(argument_expr LIKE '%password%'
               OR argument_expr LIKE '%passwd%'
               OR argument_expr LIKE '%pwd%')
          AND (callee_function LIKE '%validate%'
               OR callee_function LIKE '%check%'
               OR callee_function LIKE '%verify%'
               OR callee_function LIKE '%test%'
               OR callee_function LIKE '%.length%')""",
                        order_by="file, line")
    cursor.execute(query)

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
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""(source_expr LIKE '%password.length%'
               OR source_expr LIKE '%pwd.length%'
               OR source_expr LIKE '%passwd.length%')
          AND (source_expr LIKE '%> 6%'
               OR source_expr LIKE '%> 7%'
               OR source_expr LIKE '%> 8%'
               OR source_expr LIKE '%>= 8%')""",
                        order_by="file, line")
    cursor.execute(query)

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

def _check_password_in_url(cursor) -> List[StandardFinding]:
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
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                        where="""(source_expr LIKE '%?password=%'
               OR source_expr LIKE '%&password=%'
               OR source_expr LIKE '%?passwd=%'
               OR source_expr LIKE '%&passwd=%'
               OR source_expr LIKE '%?pwd=%'
               OR source_expr LIKE '%&pwd=%')""",
                        order_by="file, line")
    cursor.execute(query)

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
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        where="""(callee_function LIKE '%url%'
               OR callee_function LIKE '%URL%'
               OR callee_function LIKE '%uri%'
               OR callee_function LIKE '%query%')
          AND (argument_expr LIKE '%password%'
               OR argument_expr LIKE '%passwd%'
               OR argument_expr LIKE '%pwd%')
          AND (argument_expr LIKE '%?%'
               OR argument_expr LIKE '%&%')""",
                        order_by="file, line")
    cursor.execute(query)

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
