"""JWT Security Detector - Database-First Approach.

Uses categorized JWT data from the indexer.
NO AST TRAVERSAL. NO STRING PARSING. JUST SQL QUERIES.

This rule uses the JWT categorization built into the indexer:
- JWT_SIGN_HARDCODED: Hardcoded secrets (always vulnerable)
- JWT_SIGN_ENV: Environment variables (usually safe)
- JWT_SIGN_VAR: Variables (need context check)
- JWT_SIGN_CONFIG: Config object access (usually safe)
- JWT_VERIFY#: Verify calls with options
- JWT_DECODE#: Decode calls (potentially vulnerable)
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT vulnerabilities using categorized database data.

    Detects:
    - Hardcoded JWT secrets
    - Weak variable-based secrets
    - Missing expiration claims
    - None algorithm usage
    - Algorithm confusion attacks
    - Sensitive data in payloads

    Uses JWT categorization from indexer - no string parsing needed.
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
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function = 'JWT_SIGN_HARDCODED'
            ORDER BY file, line
        """)

        for file, line, secret_expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-hardcoded-secret',
                message='JWT secret is hardcoded in source code',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='cryptography',
                snippet=secret_expr[:100] if len(secret_expr) > 100 else secret_expr,
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
            ORDER BY file, line
        """)

        for file, line, payload in cursor.fetchall():
            # Identify which sensitive field was found
            sensitive_fields = []
            for field in ['password', 'secret', 'creditCard', 'ssn', 'apiKey', 'privateKey', 'cvv']:
                if field.lower() in payload.lower():
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

    finally:
        conn.close()

    return findings