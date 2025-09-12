"""TRUE Golden Standard JWT Security Detector.

Detects JWT vulnerabilities using INDEXED DATABASE DATA.
NO AST TRAVERSAL. NO FILE I/O. JUST SQL QUERIES.

This is the REAL golden standard that all rules should follow.
"""

import sqlite3
from typing import List
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_jwt_flaws(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect JWT implementation vulnerabilities using indexed data.
    
    Detects:
    - Algorithm confusion attacks (mixing HS256/RS256)
    - Weak secrets (<32 characters or containing weak patterns)
    - Missing expiration claims
    - Sensitive data in JWT payloads
    - None algorithm usage
    
    This rule demonstrates the TRUE way to write security rules:
    1. Query the database for pre-indexed data
    2. Process results with simple logic
    3. Return findings
    
    NO AST TRAVERSAL. NO TREE WALKING. NO RE-PARSING.
    """
    findings = []
    
    # Validate we have a database
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # ========================================================
        # CHECK 1: Weak JWT Secrets
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr, param_name
            FROM function_call_args
            WHERE callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
              AND param_name = 'arg1'
            ORDER BY file, line
        """)
        
        for file, line, secret_expr, _ in cursor.fetchall():
            # Check if secret is weak
            if _is_weak_secret(secret_expr):
                findings.append(StandardFinding(
                    rule_name='jwt-weak-secret',
                    message=f'Weak JWT secret detected: {_describe_weakness(secret_expr)}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='cryptography',
                    snippet=secret_expr[:100] if len(secret_expr) > 100 else secret_expr,
                    fix_suggestion='Use a cryptographically strong secret with 32+ random characters',
                    cwe_id='CWE-326'
                ))
        
        # ========================================================
        # CHECK 2: Missing JWT Expiration
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
              AND param_name = 'arg2'
            ORDER BY file, line
        """)
        
        for file, line, options_expr in cursor.fetchall():
            # Check if expiration is missing
            if not _has_expiration(options_expr):
                findings.append(StandardFinding(
                    rule_name='jwt-missing-expiration',
                    message='JWT token created without expiration claim',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='authentication',
                    snippet=options_expr[:100] if len(options_expr) > 100 else options_expr,
                    fix_suggestion="Add 'expiresIn' option (e.g., { expiresIn: '1h' })",
                    cwe_id='CWE-613'
                ))
        
        # ========================================================
        # CHECK 3: Algorithm Confusion (HS256 + RS256)
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT f1.file
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.callee_function IN ('jwt.verify', 'jsonwebtoken.verify')
              AND f2.callee_function IN ('jwt.verify', 'jsonwebtoken.verify')
              AND f1.argument_expr LIKE '%HS256%'
              AND f2.argument_expr LIKE '%RS256%'
        """)
        
        for (file,) in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-algorithm-confusion',
                message='Algorithm confusion vulnerability: both HS256 and RS256 algorithms allowed',
                file_path=file,
                line=1,  # Would need join to get exact line
                severity=Severity.CRITICAL,
                category='authentication',
                snippet='',
                fix_suggestion='Use only one algorithm type (symmetric OR asymmetric, not both)',
                cwe_id='CWE-327'
            ))
        
        # ========================================================
        # CHECK 4: None Algorithm Usage
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('jwt.verify', 'jsonwebtoken.verify')
              AND (argument_expr LIKE '%none%' OR argument_expr LIKE '%None%' OR argument_expr LIKE '%NONE%')
            ORDER BY file, line
        """)
        
        for file, line, arg_expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-none-algorithm',
                message='JWT none algorithm vulnerability - allows unsigned tokens',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                snippet=arg_expr[:100],
                fix_suggestion='Never allow "none" algorithm in production',
                cwe_id='CWE-347'
            ))
        
        # ========================================================
        # CHECK 5: Insecure Transport (HTTP instead of HTTPS)
        # ========================================================
        cursor.execute("""
            SELECT DISTINCT a.file, a.line, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE '%http://%'
              AND (a.target_var LIKE '%url%' OR a.target_var LIKE '%endpoint%' OR a.target_var LIKE '%base%')
              AND EXISTS (
                  SELECT 1 FROM function_call_args f
                  WHERE f.file = a.file
                    AND (f.argument_expr LIKE '%token%' OR f.argument_expr LIKE '%jwt%' OR f.argument_expr LIKE '%bearer%')
              )
        """)
        
        for file, line, url_expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='jwt-insecure-transport',
                message='JWT/tokens may be transmitted over insecure HTTP',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='authentication',
                snippet=url_expr[:100],
                fix_suggestion='Use HTTPS for all API endpoints handling authentication tokens',
                cwe_id='CWE-319'
            ))
        
        # ========================================================
        # CHECK 6: Sensitive Data in JWT Payload
        # ========================================================
        cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('jwt.sign', 'jsonwebtoken.sign')
              AND param_name = 'arg0'
              AND (
                   argument_expr LIKE '%password%'
                OR argument_expr LIKE '%secret%'
                OR argument_expr LIKE '%creditCard%'
                OR argument_expr LIKE '%ssn%'
                OR argument_expr LIKE '%apiKey%'
                OR argument_expr LIKE '%privateKey%'
              )
            ORDER BY file, line
        """)
        
        for file, line, payload_expr in cursor.fetchall():
            sensitive_fields = _find_sensitive_fields(payload_expr)
            if sensitive_fields:
                findings.append(StandardFinding(
                    rule_name='jwt-sensitive-data',
                    message=f'Sensitive data in JWT payload: {", ".join(sensitive_fields)}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='data-exposure',
                    snippet=payload_expr[:100],
                    fix_suggestion='Never put sensitive data in JWT payloads - they are only base64 encoded',
                    cwe_id='CWE-312'
                ))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# HELPER FUNCTIONS (Pure logic, no I/O)
# ============================================================================

def _is_weak_secret(secret_expr: str) -> bool:
    """Check if a JWT secret is weak."""
    # Remove quotes and whitespace
    clean_secret = secret_expr.strip().strip('\'"` ')
    
    # Check if it's a variable reference (good) vs hardcoded (bad)
    if clean_secret.startswith('secrets.') or clean_secret.startswith('process.env.'):
        # It's from config/env, likely okay
        return False
    
    # Check for weak patterns
    weak_patterns = ['secret', 'password', 'key', '123', 'test', 'demo', 'example', 'sample', 'default']
    lower_secret = clean_secret.lower()
    
    # Check length (less than 32 chars is weak)
    if len(clean_secret) < 32:
        return True
    
    # Check for weak keywords
    for pattern in weak_patterns:
        if pattern in lower_secret:
            return True
    
    # Check for low entropy (all same char, sequential, etc)
    if len(set(clean_secret)) < 10:  # Less than 10 unique chars
        return True
    
    return False


def _describe_weakness(secret_expr: str) -> str:
    """Describe why a secret is weak."""
    clean_secret = secret_expr.strip().strip('\'"` ')
    
    if len(clean_secret) < 32:
        return f'only {len(clean_secret)} characters (need 32+)'
    
    weak_patterns = ['secret', 'password', 'key', '123', 'test', 'demo', 'example']
    for pattern in weak_patterns:
        if pattern in clean_secret.lower():
            return f'contains weak pattern "{pattern}"'
    
    if len(set(clean_secret)) < 10:
        return 'low entropy (not enough randomness)'
    
    return 'potentially weak'


def _has_expiration(options_expr: str) -> bool:
    """Check if JWT options include expiration."""
    expiry_fields = ['expiresIn', 'exp', 'notAfter', 'expiry', 'maxAge']
    
    for field in expiry_fields:
        if field in options_expr:
            return True
    
    return False


def _find_sensitive_fields(payload_expr: str) -> List[str]:
    """Find sensitive field names in JWT payload."""
    sensitive_patterns = [
        'password', 'passwd', 'pwd', 'secret', 'apikey', 'api_key',
        'private', 'ssn', 'social_security', 'credit_card', 'creditcard',
        'cvv', 'pin', 'tax_id', 'license', 'passport', 'bank_account',
        'routing_number', 'private_key', 'client_secret'
    ]
    
    found = []
    lower_payload = payload_expr.lower()
    
    for pattern in sensitive_patterns:
        if pattern in lower_payload:
            found.append(pattern)
    
    return found[:3]  # Return max 3 for readability