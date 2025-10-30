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
# RULE METADATA - File Filtering via Orchestrator
# ============================================================================
METADATA = RuleMetadata(
    name="password_security",
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

# Weak hash algorithm keywords (used in function names)
WEAK_HASH_KEYWORDS = frozenset([
    'md5',
    'sha1',
    'sha',
    'createhash'  # crypto.createHash
])

# Strong password hashing algorithms
STRONG_HASH_ALGORITHMS = frozenset([
    'bcrypt',
    'scrypt',
    'argon2',
    'pbkdf2'
])

# Password-related keywords
PASSWORD_KEYWORDS = frozenset([
    'password',
    'passwd',
    'pwd',
    'passphrase',
    'pass'
])

# Common weak/default passwords
WEAK_PASSWORDS = frozenset([
    'password',
    'admin',
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
    'secret',
    'qwerty',
    'letmein'
])

# Placeholder password values (not real secrets)
PASSWORD_PLACEHOLDERS = frozenset([
    'your_password_here',
    'your_password',
    'password_here',
    'change_me',
    'changeme',
    'placeholder',
    '<password>',
    '${password}',
    '{{password}}'
])

# Environment variable patterns
ENV_PATTERNS = frozenset([
    'process.env',
    'import.meta.env',
    'os.environ',
    'getenv',
    'config',
    'process.argv'
])

# URL-related function keywords
URL_FUNCTION_KEYWORDS = frozenset([
    'url',
    'uri',
    'query',
    'querystring'
])


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_password_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect password security vulnerabilities.

    This is a database-first rule following the gold standard pattern.
    NO file I/O, NO AST traversal - only SQL queries on indexed data.
    All pattern matching done in Python after database fetch.

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

    # Fetch all function calls, filter in Python
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        order_by="file, line")
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        # Check if function contains weak hash keywords
        is_weak_hash = any(keyword in func_lower for keyword in WEAK_HASH_KEYWORDS)
        if not is_weak_hash:
            continue

        # Check if arguments contain password keywords
        args_lower = args.lower() if args else ''
        has_password_context = any(keyword in args_lower for keyword in PASSWORD_KEYWORDS)
        if not has_password_context:
            continue

        # Determine which algorithm
        algo = 'MD5' if 'md5' in func_lower else 'SHA1' if 'sha1' in func_lower else 'weak hash'

        findings.append(StandardFinding(
            rule_name='password-weak-hashing',
            message=f'Weak hash algorithm {algo} used for passwords',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='authentication',
            cwe_id='CWE-327',
            confidence=Confidence.HIGH,
            snippet=f'{func}({args[:40]})' if len(args) <= 40 else f'{func}({args[:40]}...)',
            recommendation='Use bcrypt, scrypt, or argon2 for password hashing'
        ))

    # Also check for crypto.createHash with weak algorithms
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                        order_by="file, line")
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        # Check for createHash functions
        if 'createhash' not in func.lower():
            continue

        # Check if args specify weak algorithm
        args_lower = args.lower()
        is_weak = ('md5' in args_lower or 'sha1' in args_lower)
        if not is_weak:
            continue

        algo = 'MD5' if 'md5' in args_lower else 'SHA1'

        # Check if this is in password context (nearby assignments)
        query_nearby = build_query('assignments', ['target_var', 'source_expr', 'line'],
                                   where="file = ?")
        cursor.execute(query_nearby, [file])

        # Filter in Python for nearby password context
        nearby_password = False
        for target, source, assign_line in cursor.fetchall():
            if abs(assign_line - line) > 5:
                continue

            target_lower = (target or '').lower()
            source_lower = (source or '').lower()

            if any(kw in target_lower or kw in source_lower for kw in PASSWORD_KEYWORDS):
                nearby_password = True
                break

        if nearby_password:
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

    # Fetch all assignments, filter in Python
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                       order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        # Check if variable name contains password keywords
        var_lower = var.lower()
        has_password_keyword = any(keyword in var_lower for keyword in PASSWORD_KEYWORDS)
        if not has_password_keyword:
            continue

        # Skip environment variables
        if any(env in expr for env in ENV_PATTERNS):
            continue

        # Clean the expression
        expr_clean = expr.strip().strip('\'"')

        # Skip placeholders
        if expr_clean.lower() in PASSWORD_PLACEHOLDERS:
            continue

        # Skip empty strings
        if not expr_clean or expr_clean in ('', '""', "''"):
            continue

        # Check if it's a literal string (hardcoded)
        is_literal = (expr.strip().startswith('"') or expr.strip().startswith("'") or
                     expr.strip().startswith('b"') or expr.strip().startswith("b'"))

        if is_literal and len(expr_clean) > 0:
            # Check if it's a weak/default password
            if expr_clean.lower() in WEAK_PASSWORDS:
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

    # Fetch all function calls, filter in Python
    query = build_query('function_call_args', ['file', 'line', 'caller_function', 'argument_expr', 'callee_function'],
                       order_by="file, line")
    cursor.execute(query)

    for file, line, caller, args, callee in cursor.fetchall():
        args_lower = (args or '').lower()

        # Check if arguments contain password keywords
        has_password = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        if not has_password:
            continue

        # Check if it's a validation function
        callee_lower = callee.lower()
        is_validation = any(kw in callee_lower for kw in ['validate', 'check', 'verify', 'test', 'length'])
        if not is_validation:
            continue

        # Check for weak length requirements
        if '.length' in args_lower:
            # Look for comparison with weak minimum
            weak_comparisons = ['> 4', '> 5', '> 6', '> 7', '>= 6', '>= 7', '>= 8']
            if any(weak in args_lower for weak in weak_comparisons):
                findings.append(StandardFinding(
                    rule_name='password-weak-length-requirement',
                    message='Weak password length requirement (< 12 characters)',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='authentication',
                    cwe_id='CWE-521',
                    confidence=Confidence.MEDIUM,
                    snippet=args[:60] if len(args) <= 60 else args[:60] + '...',
                    recommendation='Enforce minimum password length of 12+ characters'
                ))

    # Also check for simple length checks in assignments
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                       order_by="file, line")
    cursor.execute(query)

    for file, line, var, expr in cursor.fetchall():
        expr_lower = expr.lower()

        # Check for password length checks
        has_password_length = any(f'{kw}.length' in expr_lower for kw in ['password', 'pwd', 'passwd'])
        if not has_password_length:
            continue

        # Check for weak length comparisons
        weak_patterns = ['> 6', '> 7', '> 8', '>= 8']
        if any(pattern in expr_lower for pattern in weak_patterns):
            findings.append(StandardFinding(
                rule_name='password-weak-validation',
                message='Password validation only checks length (no complexity requirements)',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                cwe_id='CWE-521',
                confidence=Confidence.MEDIUM,
                snippet=expr[:60] if len(expr) <= 60 else expr[:60] + '...',
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

    # Fetch all assignments, filter in Python
    query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                       order_by="file, line")
    cursor.execute(query)

    url_param_patterns = ['?password=', '&password=', '?passwd=', '&passwd=', '?pwd=', '&pwd=']

    for file, line, var, expr in cursor.fetchall():
        # Check for URL patterns with password parameters
        if any(pattern in expr for pattern in url_param_patterns):
            findings.append(StandardFinding(
                rule_name='password-in-url',
                message='Password transmitted in URL query parameter',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                cwe_id='CWE-598',
                confidence=Confidence.HIGH,
                snippet=expr[:60] if len(expr) <= 60 else expr[:60] + '...',
                recommendation='Use POST requests with password in request body, never in URL'
            ))

    # Also check function calls that build URLs
    query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                       order_by="file, line")
    cursor.execute(query)

    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()

        # Check if it's a URL-related function
        is_url_function = any(kw in func_lower for kw in URL_FUNCTION_KEYWORDS)
        if not is_url_function:
            continue

        args_lower = args.lower()

        # Check if arguments contain password keywords and query params
        has_password = any(kw in args_lower for kw in PASSWORD_KEYWORDS)
        has_query_params = ('?' in args or '&' in args)

        if has_password and has_query_params:
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
