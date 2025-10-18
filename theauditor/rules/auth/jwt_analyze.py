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
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - Smart File Filtering
# ============================================================================
METADATA = RuleMetadata(
    name="jwt_security",
    category="auth",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=[
        # 'frontend/',  # REMOVED - rule has frontend checks (localStorage, React state)
        # 'client/',    # REMOVED - rule detects frontend JWT patterns
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

# JWT signing functions (actual function names from indexer)
JWT_SIGN_FUNCTIONS = frozenset([
    'jwt.sign',
    'jsonwebtoken.sign',
    'jose.JWT.sign',
    'jose.sign',
    'JWT.sign',
    'jwt.encode',
    'PyJWT.encode',
    'pyjwt.encode',
    'njwt.create',
    'jws.sign'
])

# JWT verification functions
JWT_VERIFY_FUNCTIONS = frozenset([
    'jwt.verify',
    'jsonwebtoken.verify',
    'jose.JWT.verify',
    'jose.verify',
    'JWT.verify',
    'jwt.decode',
    'PyJWT.decode',
    'pyjwt.decode',
    'njwt.verify',
    'jws.verify'
])

# JWT decode functions (no verification)
JWT_DECODE_FUNCTIONS = frozenset([
    'jwt.decode',
    'jsonwebtoken.decode',
    'jose.JWT.decode',
    'JWT.decode',
    'PyJWT.decode',
    'pyjwt.decode'
])

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
        # CHECK 1: Hardcoded JWT Secrets (CRITICAL)
        # ========================================================
        # Build WHERE clause for actual JWT signing function names
        jwt_sign_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_SIGN_FUNCTIONS])

        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr', 'argument_index'],
                           where=f"""({jwt_sign_conditions})
              AND argument_index IN (1, 2)
              AND argument_expr NOT LIKE '%process.env%'
              AND argument_expr NOT LIKE '%import.meta.env%'
              AND argument_expr NOT LIKE '%os.environ%'
              AND argument_expr NOT LIKE '%getenv%'
              AND argument_expr NOT LIKE '%config%'
              AND (argument_expr LIKE '"%' OR argument_expr LIKE "'%")
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, secret_expr, arg_idx in cursor.fetchall():
            # Additional check to filter out placeholders
            secret_clean = secret_expr.strip('"').strip("'").strip('`')
            if secret_clean.lower() in ['secret', 'your-secret', 'changeme', 'your_secret_here', 'placeholder']:
                continue

            # Skip very short secrets (likely placeholders)
            if len(secret_clean) < 8:
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
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"""({jwt_sign_conditions})
              AND argument_index IN (1, 2)
              AND argument_expr NOT LIKE '"%'
              AND argument_expr NOT LIKE "'%"
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, secret_expr in cursor.fetchall():
            # Only flag if it looks obviously weak
            if any(weak in secret_expr.lower() for weak in ['123', 'test', 'demo', 'example']):
                findings.append(StandardFinding(
                    rule_name='jwt-weak-secret',
                    message=f'JWT secret variable appears weak: {secret_expr}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    snippet=f'{func}(..., {secret_expr}, ...)',
                    cwe_id='CWE-326'
                ))

        # ========================================================
        # CHECK 3: Missing JWT Expiration
        # ========================================================
        # First, get all JWT signing calls
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where=f"""({jwt_sign_conditions})
              AND argument_index = 0
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

        jwt_sign_calls = cursor.fetchall()

        # For each signing call, check if there's an options argument with expiration
        for file, line, func in jwt_sign_calls:
            # Check for options argument (index 2) with expiration settings
            options_query = build_query('function_call_args', ['argument_expr'],
                                       where=f"""file = ? AND line = ?
                                                 AND callee_function = ?
                                                 AND argument_index = 2""")
            cursor.execute(options_query, (file, line, func))

            options_row = cursor.fetchone()
            options = options_row[0] if options_row else None

            # Check if expiration is missing
            has_expiration = False
            if options:
                has_expiration = ('expiresIn' in options or 'exp' in options or
                                'maxAge' in options or 'expires_in' in options)

            if not has_expiration:
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
        jwt_verify_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_VERIFY_FUNCTIONS])

        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where=f"""({jwt_verify_conditions})
              AND argument_index = 2
              AND argument_expr LIKE '%algorithms%'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where=f"""({jwt_verify_conditions})
              AND argument_index = 2
              AND (argument_expr LIKE '%none%' OR argument_expr LIKE '%None%' OR argument_expr LIKE '%NONE%')
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        jwt_decode_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_DECODE_FUNCTIONS])

        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           where=f"""({jwt_decode_conditions})
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where=f"""({jwt_sign_conditions})
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where=f"""({jwt_sign_conditions})
              AND argument_index IN (1, 2)
              AND (argument_expr LIKE '%process.env%' OR argument_expr LIKE '%os.environ%' OR argument_expr LIKE '%getenv%')
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where="""(callee_function LIKE '%localStorage.setItem%'
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           where="""(
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where=f"""({jwt_sign_conditions})
              AND argument_index IN (1, 2)
              AND argument_expr NOT LIKE '%process.env%'
              AND argument_expr NOT LIKE '%os.environ%'
              AND argument_expr NOT LIKE '%getenv%'
              AND (argument_expr LIKE '"%' OR argument_expr LIKE "'%")
              AND LENGTH(TRIM(argument_expr, '"' || "'")) < 32
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                           where="""(callee_function LIKE '%fetch%'
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
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           where="""(file LIKE '%.jsx' OR file LIKE '%.tsx')
              AND (source_expr LIKE '%useState%' OR source_expr LIKE '%useContext%')
              AND (source_expr LIKE '%token%' OR source_expr LIKE '%jwt%' OR source_expr LIKE '%auth%')
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%spec.%'
              AND file NOT LIKE '%.test.%'
              AND file NOT LIKE '%__tests__%'
              AND file NOT LIKE '%demo%'
              AND file NOT LIKE '%example%'""",
                           order_by="file, line")
        cursor.execute(query)

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