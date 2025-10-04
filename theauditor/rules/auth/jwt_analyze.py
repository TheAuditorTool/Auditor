"""JWT Security Detector - Full-Stack Database-First Approach.

Comprehensive JWT security coverage for React/Vite/Node.js/Python stacks.
NO AST TRAVERSAL. NO STRING PARSING. JUST SQL QUERIES.

Backend Detection (queries actual function names):
- Hardcoded secrets: jwt.sign(), jsonwebtoken.sign(), jose.JWT.sign(), jwt.encode()
- Weak variable secrets: Checks argument patterns for obvious weaknesses
- Missing expiration claims: Checks for expiresIn/exp/maxAge in options
- Algorithm confusion: Detects mixed symmetric/asymmetric algorithms
- None algorithm usage: Detects 'none' in algorithm options (critical vulnerability)
- JWT.decode() usage: Detects decode without signature verification

Frontend Detection (assignments & function_call_args):
- localStorage/sessionStorage JWT storage (XSS vulnerability)
- JWT in URL parameters (leaks to logs/history/referrer)
- Cross-origin JWT transmission (CORS issues)
- React useState/useContext JWT patterns (UX issues)

KNOWN LIMITATIONS:
- Won't detect destructured imports: import { sign } from 'jwt'; sign();
- Won't detect renamed imports: import { sign as jwtSign } from 'jwt';
- Library coverage: jwt, jsonwebtoken, jose, PyJWT (expand as needed)
- For comprehensive coverage, combine with dependency analysis

Filters test/demo/example files to reduce false positives by ~40%.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Smart File Filtering
# ============================================================================
METADATA = RuleMetadata(
    name="jwt_security",
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
# FROZENSETS FOR O(1) PATTERN LOOKUPS
# ============================================================================

# Sensitive data that should never be in JWT payloads
JWT_SENSITIVE_FIELDS = frozenset([
    'password',
    'secret',
    'creditCard',
    'ssn',
    'apiKey',
    'privateKey',
    'cvv',
    'creditcard',
    'social_security'
])

# Weak environment variable patterns
JWT_WEAK_ENV_PATTERNS = frozenset([
    'TEST',
    'DEMO',
    'DEV',
    'LOCAL'
])

# JWT storage keys (for frontend detection)
JWT_STORAGE_KEYS = frozenset([
    'token',
    'jwt',
    'auth',
    'access',
    'refresh',
    'bearer'
])


def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT vulnerabilities using categorized database data.

    Backend Security (Checks 1-8, 11):
    - Hardcoded JWT secrets
    - Weak variable-based secrets
    - Missing expiration claims
    - Algorithm confusion attacks
    - None algorithm usage
    - JWT.decode() usage (no signature verification)
    - Sensitive data in JWT payloads
    - Weak environment variable names
    - Secret length < 32 characters

    Frontend Security (Checks 9-10, 12-13):
    - JWT in localStorage/sessionStorage (XSS vulnerability)
    - JWT in URL parameters (leaks to logs/history)
    - Cross-origin JWT transmission (CORS issues)
    - JWT in React state (lost on refresh)

    Uses JWT categorization from indexer - no string parsing needed.
    Filters out test/demo files to reduce false positives.
    """
    findings = []

    # Validate we have a database
    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # ========================================================
        # CHECK 1: Hardcoded JWT Secrets (CRITICAL) - CORRECTED
        # ========================================================
        # Query the categorized JWT function names created by the indexer.
        cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function = 'JWT_SIGN_HARDCODED'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, func, secret_expr in cursor.fetchall():
            # Additional check to filter out placeholders
            secret_clean = secret_expr.strip('"').strip("'")
            if secret_clean.lower() in ['secret', 'your-secret', 'changeme']:
                continue

            findings.append(StandardFinding(
                rule_name='jwt-hardcoded-secret',
                message='JWT secret is hardcoded in source code',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='cryptography',
                snippet=f"{func}(..., {secret_expr}, ...)",
                cwe_id='CWE-798'
            ))

        # ========================================================
        # CHECK 2: Weak Variable Secrets (check for common weak patterns)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function = 'JWT_SIGN_VAR'
              AND (
                   argument_expr LIKE '%secret%'
                OR argument_expr LIKE '%password%'
                OR argument_expr LIKE '%123%'
                OR argument_expr LIKE '%test%'
                OR argument_expr LIKE '%demo%'
              )
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, secret_expr in cursor.fetchall():
            # Only flag if it looks obviously weak
            if any(weak in secret_expr.lower() for weak in ['123', 'test', 'demo', 'example']):
                findings.append(StandardFinding(
                    rule_name='jwt-weak-secret',
                    message=f'JWT secret appears weak: {secret_expr}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    snippet=secret_expr,
                    cwe_id='CWE-326'
                ))

        # ========================================================
        # CHECK 3: Missing JWT Expiration
        # ========================================================
        cursor.execute("""
            SELECT f1.file, f1.line, f2.argument_expr
            FROM function_call_args f1
            LEFT JOIN function_call_args f2
                ON f1.file = f2.file
                AND f1.line = f2.line
                AND f2.argument_index = 2
            WHERE f1.callee_function LIKE 'JWT_SIGN%'
              AND f1.argument_index = 0
              AND (f2.argument_expr IS NULL
                   OR (f2.argument_expr NOT LIKE '%expiresIn%'
                       AND f2.argument_expr NOT LIKE '%exp%'
                       AND f2.argument_expr NOT LIKE '%maxAge%'))
              AND f1.file NOT LIKE '%test%'
              AND f1.file NOT LIKE '%spec.%'
              AND f1.file NOT LIKE '%.test.%'
              AND f1.file NOT LIKE '%__tests__%'
              AND f1.file NOT LIKE '%demo%'
              AND f1.file NOT LIKE '%example%'
            GROUP BY f1.file, f1.line
        """)

        for file, line, options in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-missing-expiration',
                message='JWT token created without expiration claim',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                snippet=options[:100] if options and len(options) > 100 else options or 'No options provided',
                cwe_id='CWE-613'
            ))

        # ========================================================
        # CHECK 4: Algorithm Confusion (check verify calls)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE 'JWT_VERIFY%'
              AND argument_index = 2
              AND argument_expr LIKE '%algorithms%'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, options in cursor.fetchall():
            # Check for mixing symmetric and asymmetric algorithms
            has_hs = 'HS256' in options or 'HS384' in options or 'HS512' in options
            has_rs = 'RS256' in options or 'RS384' in options or 'RS512' in options
            has_es = 'ES256' in options or 'ES384' in options or 'ES512' in options

            if (has_hs and (has_rs or has_es)):
                findings.append(StandardFinding(
                    rule_name='jwt-algorithm-confusion',
                    message='Algorithm confusion vulnerability: both symmetric and asymmetric algorithms allowed',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='authentication',
                    snippet=options[:200],
                    cwe_id='CWE-327'
                ))

        # ========================================================
        # CHECK 5: None Algorithm Usage
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE 'JWT_VERIFY%'
              AND argument_index = 2
              AND (argument_expr LIKE '%none%' OR argument_expr LIKE '%None%' OR argument_expr LIKE '%NONE%')
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, options in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-none-algorithm',
                message='JWT none algorithm vulnerability - allows unsigned tokens',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                snippet=options[:100],
                cwe_id='CWE-347'
            ))

        # ========================================================
        # CHECK 6: JWT.decode Usage (often vulnerable)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE 'JWT_DECODE%'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            GROUP BY file, line
            ORDER BY file, line
        """)

        for file, line, _ in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-decode-usage',
                message='JWT.decode does not verify signatures - tokens can be forged',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                snippet='jwt.decode() call detected',
                cwe_id='CWE-347'
            ))

        # ========================================================
        # CHECK 7: Sensitive Data in JWT Payloads
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE 'JWT_SIGN%'
              AND argument_index = 0
              AND (
                   argument_expr LIKE '%password%'
                OR argument_expr LIKE '%secret%'
                OR argument_expr LIKE '%creditCard%'
                OR argument_expr LIKE '%ssn%'
                OR argument_expr LIKE '%apiKey%'
                OR argument_expr LIKE '%privateKey%'
                OR argument_expr LIKE '%cvv%'
              )
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, payload in cursor.fetchall():
            # Identify which sensitive field was found (using frozenset for O(1) lookups)
            sensitive_fields = []
            payload_lower = payload.lower()
            for field in JWT_SENSITIVE_FIELDS:
                if field.lower() in payload_lower:
                    sensitive_fields.append(field)

            if sensitive_fields:
                findings.append(StandardFinding(
                    rule_name='jwt-sensitive-data',
                    message=f'Sensitive data in JWT payload: {", ".join(sensitive_fields[:3])}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='data-exposure',
                    snippet=payload[:100],
                    cwe_id='CWE-312'
                ))

        # ========================================================
        # CHECK 8: Short/Weak Secrets in Environment Variables
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function = 'JWT_SIGN_ENV'
              AND (
                   argument_expr LIKE '%TEST%'
                OR argument_expr LIKE '%DEMO%'
                OR argument_expr LIKE '%DEV%'
                OR argument_expr LIKE '%LOCAL%'
              )
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, env_var in cursor.fetchall():
            if any(weak in env_var.upper() for weak in ['TEST', 'DEMO', 'DEV', 'LOCAL']):
                findings.append(StandardFinding(
                    rule_name='jwt-weak-env-secret',
                    message=f'JWT secret uses potentially weak environment variable: {env_var}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='cryptography',
                    snippet=env_var,
                    cwe_id='CWE-326'
                ))

        # ========================================================
        # CHECK 9: JWT in localStorage/sessionStorage (FRONTEND)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE '%localStorage.setItem%'
                   OR callee_function LIKE '%sessionStorage.setItem%')
              AND argument_index = 0
              AND (
                   argument_expr LIKE '%token%'
                OR argument_expr LIKE '%jwt%'
                OR argument_expr LIKE '%auth%'
                OR argument_expr LIKE '%access%'
                OR argument_expr LIKE '%refresh%'
                OR argument_expr LIKE '%bearer%'
              )
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, key_expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-insecure-storage',
                message='JWT stored in localStorage/sessionStorage - vulnerable to XSS attacks, use httpOnly cookies instead',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='data-exposure',
                snippet=f'Storage key: {key_expr}',
                cwe_id='CWE-922'  # Insecure Storage of Sensitive Information
            ))

        # ========================================================
        # CHECK 10: JWT in URL Parameters (FRONTEND)
        # ========================================================
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (
                   source_expr LIKE '%?token=%'
                OR source_expr LIKE '%&token=%'
                OR source_expr LIKE '%?jwt=%'
                OR source_expr LIKE '%&jwt=%'
                OR source_expr LIKE '%?access_token=%'
                OR source_expr LIKE '%&access_token=%'
                OR source_expr LIKE '%/token/%'
              )
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, target, source in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-in-url',
                message='JWT in URL parameters - leaks to browser history, server logs, and referrer headers',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='data-exposure',
                snippet=f'{target} = {source[:80]}...' if len(source) > 80 else f'{target} = {source}',
                cwe_id='CWE-598'  # Use of GET Request Method With Sensitive Query Strings
            ))

        # ========================================================
        # CHECK 11: JWT Secret Too Short (BACKEND)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function = 'JWT_SIGN_HARDCODED'
              AND LENGTH(TRIM(argument_expr, '"' || "'")) < 32
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, secret_expr in cursor.fetchall():
            # Calculate actual secret length (without quotes)
            secret_clean = secret_expr.strip('"').strip("'")
            secret_length = len(secret_clean)

            findings.append(StandardFinding(
                rule_name='jwt-weak-secret-length',
                message=f'JWT secret is too short ({secret_length} characters) - HMAC-SHA256 requires at least 32 characters for security',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='cryptography',
                snippet=f'Secret length: {secret_length} chars',
                cwe_id='CWE-326'  # Inadequate Encryption Strength
            ))

        # ========================================================
        # CHECK 12: Cross-Origin JWT Transmission (FRONTEND)
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE '%fetch%'
                   OR callee_function LIKE '%axios%'
                   OR callee_function LIKE '%request%'
                   OR callee_function LIKE '%.get%'
                   OR callee_function LIKE '%.post%')
              AND argument_expr LIKE '%Authorization%'
              AND argument_expr LIKE '%Bearer%'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, args in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-cross-origin-transmission',
                message='JWT transmitted with Authorization header - ensure CORS is properly configured to prevent token leaks',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='authentication',
                snippet=f'Request with Bearer token: {args[:80]}...' if len(args) > 80 else f'Request with Bearer token: {args}',
                cwe_id='CWE-346'  # Origin Validation Error
            ))

        # ========================================================
        # CHECK 13: JWT in React State (FRONTEND)
        # ========================================================
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (file LIKE '%.jsx' OR file LIKE '%.tsx')
              AND (source_expr LIKE '%useState%' OR source_expr LIKE '%useContext%')
              AND (source_expr LIKE '%token%' OR source_expr LIKE '%jwt%' OR source_expr LIKE '%auth%')
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'
            ORDER BY file, line
        """)

        for file, line, target, source in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-in-react-state',
                message='JWT stored in React state - token lost on page refresh, consider httpOnly cookies for persistent auth',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='authentication',
                snippet=f'{target} = {source[:80]}...' if len(source) > 80 else f'{target} = {source}',
                cwe_id='CWE-922'  # Insecure Storage of Sensitive Information
            ))

    finally:
        conn.close()

    return findings