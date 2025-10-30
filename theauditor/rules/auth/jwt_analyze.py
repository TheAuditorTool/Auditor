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
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - File Filtering via Orchestrator
# ============================================================================
METADATA = RuleMetadata(
    name="jwt_security",
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

# Environment variable patterns to skip
ENV_PATTERNS = frozenset([
    'process.env',
    'import.meta.env',
    'os.environ',
    'getenv',
    'config'
])

# Weak environment variable names
WEAK_ENV_NAMES = frozenset([
    'TEST',
    'DEMO',
    'DEV',
    'LOCAL'
])

# localStorage/sessionStorage functions
STORAGE_FUNCTIONS = frozenset([
    'localStorage.setItem',
    'sessionStorage.setItem'
])

# HTTP request functions
HTTP_FUNCTIONS = frozenset([
    'fetch',
    'axios',
    'axios.get',
    'axios.post',
    'request',
    'http.get',
    'http.post',
    'https.get',
    'https.post'
])


def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT vulnerabilities using database queries with Python-side filtering.

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

    All pattern matching done in Python after database fetch.
    File filtering handled by orchestrator via METADATA.
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # ========================================================
        # CHECK 1: Hardcoded JWT Secrets (CRITICAL)
        # ========================================================
        jwt_sign_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_SIGN_FUNCTIONS])

        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function', 'argument_expr', 'argument_index'],
                           where=f"({jwt_sign_conditions}) AND argument_index IN (1, 2)",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, secret_expr, arg_idx in cursor.fetchall():
            # Skip environment variables
            if any(env in secret_expr for env in ENV_PATTERNS):
                continue

            # Must start with quote (hardcoded string)
            if not (secret_expr.startswith('"') or secret_expr.startswith("'")):
                continue

            # Filter out placeholder values
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
                snippet=f"{func}(..., {secret_expr[:50]}, ...)",
                cwe_id='CWE-798'
            ))

        # ========================================================
        # CHECK 2: Weak Variable Secrets
        # ========================================================
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function', 'argument_expr'],
                           where=f"({jwt_sign_conditions}) AND argument_index IN (1, 2)",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, secret_expr in cursor.fetchall():
            # Skip quoted strings (covered by CHECK 1)
            if secret_expr.startswith('"') or secret_expr.startswith("'"):
                continue

            # Check for weak patterns in variable names
            secret_lower = secret_expr.lower()
            weak_keywords = ['123', 'test', 'demo', 'example']

            if any(weak in secret_lower for weak in weak_keywords):
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
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function'],
                           where=f"({jwt_sign_conditions}) AND argument_index = 0",
                           order_by="file, line")
        cursor.execute(query)

        jwt_sign_calls = cursor.fetchall()

        # For each signing call, check if there's an options argument with expiration
        for file, line, func in jwt_sign_calls:
            options_query = build_query('function_call_args',
                                       ['argument_expr'],
                                       where="file = ? AND line = ? AND callee_function = ? AND argument_index = 2")
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
        # CHECK 4: Algorithm Confusion
        # ========================================================
        jwt_verify_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_VERIFY_FUNCTIONS])

        query = build_query('function_call_args',
                           ['file', 'line', 'argument_expr'],
                           where=f"({jwt_verify_conditions}) AND argument_index = 2",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, options in cursor.fetchall():
            # Filter for algorithms option
            if 'algorithms' not in options:
                continue

            # Check for mixing symmetric and asymmetric algorithms
            has_hs = 'HS256' in options or 'HS384' in options or 'HS512' in options
            has_rs = 'RS256' in options or 'RS384' in options or 'RS512' in options
            has_es = 'ES256' in options or 'ES384' in options or 'ES512' in options

            if has_hs and (has_rs or has_es):
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
        query = build_query('function_call_args',
                           ['file', 'line', 'argument_expr'],
                           where=f"({jwt_verify_conditions}) AND argument_index = 2",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, options in cursor.fetchall():
            # Check for 'none' algorithm (case insensitive)
            options_lower = options.lower()
            if 'none' in options_lower:
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
        # CHECK 6: JWT.decode Usage (no verification)
        # ========================================================
        jwt_decode_conditions = ' OR '.join([f"callee_function = '{func}'" for func in JWT_DECODE_FUNCTIONS])

        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function'],
                           where=f"({jwt_decode_conditions}) AND argument_index = 0",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-decode-usage',
                message='JWT.decode does not verify signatures - tokens can be forged',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='authentication',
                snippet=f'{func}() call detected',
                cwe_id='CWE-347'
            ))

        # ========================================================
        # CHECK 7: Sensitive Data in JWT Payloads
        # ========================================================
        query = build_query('function_call_args',
                           ['file', 'line', 'argument_expr'],
                           where=f"({jwt_sign_conditions}) AND argument_index = 0",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, payload in cursor.fetchall():
            # Check for sensitive field names
            payload_lower = payload.lower()
            sensitive_found = []

            for field in JWT_SENSITIVE_FIELDS:
                if field.lower() in payload_lower:
                    sensitive_found.append(field)

            if sensitive_found:
                findings.append(StandardFinding(
                    rule_name='jwt-sensitive-data',
                    message=f'Sensitive data in JWT payload: {", ".join(sensitive_found[:3])}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='data-exposure',
                    snippet=payload[:100],
                    cwe_id='CWE-312'
                ))

        # ========================================================
        # CHECK 8: Weak Environment Variable Names
        # ========================================================
        query = build_query('function_call_args',
                           ['file', 'line', 'argument_expr'],
                           where=f"({jwt_sign_conditions}) AND argument_index IN (1, 2)",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, env_var in cursor.fetchall():
            # Check if using env variable
            if not any(env in env_var for env in ENV_PATTERNS):
                continue

            # Check for weak env var names
            env_var_upper = env_var.upper()
            if any(weak in env_var_upper for weak in WEAK_ENV_NAMES):
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
        # CHECK 9: JWT in localStorage/sessionStorage
        # ========================================================
        # Query all setItem calls
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function', 'argument_expr'],
                           where="argument_index = 0",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, key_expr in cursor.fetchall():
            # Check if it's a storage function
            if not any(storage in func for storage in STORAGE_FUNCTIONS):
                continue

            # Check if key contains JWT-related terms
            key_lower = key_expr.lower()
            jwt_keywords = ['token', 'jwt', 'auth', 'access', 'refresh', 'bearer']

            if any(keyword in key_lower for keyword in jwt_keywords):
                findings.append(StandardFinding(
                    rule_name='jwt-insecure-storage',
                    message='JWT stored in localStorage/sessionStorage - vulnerable to XSS attacks, use httpOnly cookies instead',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='data-exposure',
                    snippet=f'Storage key: {key_expr}',
                    cwe_id='CWE-922'
                ))

        # ========================================================
        # CHECK 10: JWT in URL Parameters
        # ========================================================
        query = build_query('assignments',
                           ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, source in cursor.fetchall():
            # Check for JWT in URL patterns
            url_patterns = ['?token=', '&token=', '?jwt=', '&jwt=', '?access_token=', '&access_token=', '/token/']

            if any(pattern in source for pattern in url_patterns):
                findings.append(StandardFinding(
                    rule_name='jwt-in-url',
                    message='JWT in URL parameters - leaks to browser history, server logs, and referrer headers',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='data-exposure',
                    snippet=f'{target} = {source[:80]}' if len(source) <= 80 else f'{target} = {source[:80]}...',
                    cwe_id='CWE-598'
                ))

        # ========================================================
        # CHECK 11: JWT Secret Too Short
        # ========================================================
        query = build_query('function_call_args',
                           ['file', 'line', 'argument_expr'],
                           where=f"({jwt_sign_conditions}) AND argument_index IN (1, 2)",
                           order_by="file, line")
        cursor.execute(query)

        for file, line, secret_expr in cursor.fetchall():
            # Skip env variables
            if any(env in secret_expr for env in ENV_PATTERNS):
                continue

            # Must be quoted string
            if not (secret_expr.startswith('"') or secret_expr.startswith("'")):
                continue

            # Calculate length
            secret_clean = secret_expr.strip('"').strip("'")
            secret_length = len(secret_clean)

            if secret_length < 32:
                findings.append(StandardFinding(
                    rule_name='jwt-weak-secret-length',
                    message=f'JWT secret is too short ({secret_length} characters) - HMAC-SHA256 requires at least 32 characters for security',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    snippet=f'Secret length: {secret_length} chars',
                    cwe_id='CWE-326'
                ))

        # ========================================================
        # CHECK 12: Cross-Origin JWT Transmission
        # ========================================================
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, func, args in cursor.fetchall():
            # Check if HTTP request function
            if not any(http_func in func for http_func in HTTP_FUNCTIONS):
                continue

            # Check for Authorization header with Bearer token
            if 'Authorization' in args and 'Bearer' in args:
                findings.append(StandardFinding(
                    rule_name='jwt-cross-origin-transmission',
                    message='JWT transmitted with Authorization header - ensure CORS is properly configured to prevent token leaks',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='authentication',
                    snippet=f'Request with Bearer token: {args[:80]}' if len(args) <= 80 else f'Request with Bearer token: {args[:80]}...',
                    cwe_id='CWE-346'
                ))

        # ========================================================
        # CHECK 13: JWT in React State
        # ========================================================
        query = build_query('assignments',
                           ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, target, source in cursor.fetchall():
            # Check for JSX/TSX files
            if not (file.endswith('.jsx') or file.endswith('.tsx')):
                continue

            # Check for React hooks
            if not ('useState' in source or 'useContext' in source):
                continue

            # Check for JWT-related terms
            jwt_terms = ['token', 'jwt', 'auth']
            if any(term in source.lower() for term in jwt_terms):
                findings.append(StandardFinding(
                    rule_name='jwt-in-react-state',
                    message='JWT stored in React state - token lost on page refresh, consider httpOnly cookies for persistent auth',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='authentication',
                    snippet=f'{target} = {source[:80]}' if len(source) <= 80 else f'{target} = {source[:80]}...',
                    cwe_id='CWE-922'
                ))

    finally:
        conn.close()

    return findings
