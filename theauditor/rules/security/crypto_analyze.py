"""Cryptography Security Analyzer - Database-Driven Implementation.

Detects weak cryptography and insecure random number usage via indexed data.
NO AST TRAVERSAL. Just efficient SQL queries.

This rule follows the TRUE golden standard:
1. Query the database for pre-indexed data
2. Process results with simple logic  
3. Return findings

Detects:
- Insecure random functions used for security
- Weak cryptographic algorithms (MD5, SHA1, DES, RC4)
- Predictable token generation (timestamps, sequential)
- Weak key derivation functions
"""

import sqlite3
import json
import re
from typing import List, Set
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_crypto_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect cryptographic security issues using indexed data.
    
    Main entry point that delegates to specific detectors.
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First, identify security-sensitive variables
        security_vars = _identify_security_variables(cursor)
        
        # Run each crypto check
        findings.extend(_find_insecure_random(cursor, security_vars))
        findings.extend(_find_weak_crypto_algorithms(cursor))
        findings.extend(_find_predictable_tokens(cursor, security_vars))
        findings.extend(_find_weak_key_derivation(cursor))
        findings.extend(_find_hardcoded_salts(cursor))
        findings.extend(_find_ecb_mode(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# HELPER: Identify Security-Sensitive Variables
# ============================================================================

def _identify_security_variables(cursor) -> Set[str]:
    """Identify variables that hold security-sensitive values."""
    security_vars = set()
    
    # Security-related keywords
    keywords = [
        'token', 'password', 'secret', 'key', 'auth', 'session',
        'salt', 'nonce', 'pin', 'otp', 'code', 'api_key', 'apikey',
        'uuid', 'guid', 'csrf', 'jwt', 'bearer', 'credential'
    ]
    
    # Find assignments with security-related names
    keyword_conditions = ' OR '.join([f'a.target_var LIKE "%{kw}%"' for kw in keywords])
    
    cursor.execute(f"""
        SELECT DISTINCT a.target_var
        FROM assignments a
        WHERE {keyword_conditions}
    """)
    
    for row in cursor.fetchall():
        security_vars.add(row[0])
    
    # Also find symbols with security names
    cursor.execute(f"""
        SELECT DISTINCT s.name
        FROM symbols s
        WHERE s.type IN ('variable', 'constant')
          AND ({' OR '.join([f's.name LIKE "%{kw}%"' for kw in keywords])})
    """)
    
    for row in cursor.fetchall():
        security_vars.add(row[0])
    
    return security_vars


# ============================================================================
# CHECK 1: Insecure Random Functions
# ============================================================================

def _find_insecure_random(cursor, security_vars: Set[str]) -> List[StandardFinding]:
    """Find insecure random functions used for security purposes.
    
    Math.random() and Python's random module are not cryptographically secure.
    """
    findings = []
    
    # Python insecure random functions
    python_weak_random = [
        'random.random', 'random.randint', 'random.choice', 
        'random.randbytes', 'random.randrange', 'random.getrandbits',
        'random.uniform', 'random.sample', 'random.shuffle'
    ]
    
    for func in python_weak_random:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.caller_function
            FROM function_call_args f
            WHERE f.callee_function = ?
            ORDER BY f.file, f.line
        """, [func])
        
        for file, line, called_func, caller in cursor.fetchall():
            # Check if assigned to security variable
            cursor.execute("""
                SELECT a.target_var FROM assignments a
                WHERE a.file = ?
                  AND a.line = ?
                  AND a.source_expr LIKE ?
                LIMIT 1
            """, [file, line, f'%{func}%'])
            
            assignment = cursor.fetchone()
            if assignment and assignment[0] in security_vars:
                findings.append(StandardFinding(
                    rule_name='crypto-insecure-random-python',
                    message=f'Using {func} for security-sensitive variable',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{assignment[0]} = {func}()',
                    fix_suggestion='Use secrets module: secrets.token_hex() or secrets.token_urlsafe()',
                    cwe_id='CWE-330'  # Use of Insufficiently Random Values
                ))
            # Check if in security context (function name)
            elif caller and any(kw in caller.lower() for kw in ['token', 'password', 'auth', 'key', 'secret']):
                findings.append(StandardFinding(
                    rule_name='crypto-insecure-random-python',
                    message=f'Using {func} in security context: {caller}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}() in {caller}',
                    fix_suggestion='Use secrets module for security-sensitive randomness',
                    cwe_id='CWE-330'
                ))
    
    # JavaScript Math.random()
    cursor.execute("""
        SELECT f.file, f.line, f.caller_function
        FROM function_call_args f
        WHERE f.callee_function IN ('Math.random', 'random')
          AND f.file LIKE '%.js' OR f.file LIKE '%.ts'
        ORDER BY f.file, f.line
    """)
    
    for file, line, caller in cursor.fetchall():
        # Check assignment context
        cursor.execute("""
            SELECT a.target_var FROM assignments a
            WHERE a.file = ?
              AND a.line = ?
              AND a.source_expr LIKE '%Math.random%'
            LIMIT 1
        """, [file, line])
        
        assignment = cursor.fetchone()
        if assignment and assignment[0] in security_vars:
            findings.append(StandardFinding(
                rule_name='crypto-insecure-random-js',
                message=f'Math.random() used for security variable: {assignment[0]}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{assignment[0]} = Math.random()',
                fix_suggestion='Use crypto.randomBytes() or crypto.getRandomValues()',
                cwe_id='CWE-330'
            ))
    
    return findings


# ============================================================================
# CHECK 2: Weak Cryptographic Algorithms
# ============================================================================

def _find_weak_crypto_algorithms(cursor) -> List[StandardFinding]:
    """Find usage of weak/broken cryptographic algorithms."""
    findings = []
    
    # Weak hash algorithms
    weak_hashes = {
        'md5': ('MD5', 'SHA-256 or SHA-3'),
        'sha1': ('SHA-1', 'SHA-256 or SHA-3'),
        'MD5': ('MD5', 'SHA-256 or SHA-3'),
        'SHA1': ('SHA-1', 'SHA-256 or SHA-3')
    }
    
    # Check Python hashlib usage
    for algo, (name, recommendation) in weak_hashes.items():
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function, f.argument_expr
            FROM function_call_args f
            WHERE (f.callee_function = 'hashlib.new' AND f.argument_expr LIKE ?)
               OR f.callee_function = ?
            ORDER BY f.file, f.line
        """, [f'%{algo}%', f'hashlib.{algo.lower()}'])
        
        for file, line, func, args in cursor.fetchall():
            # Check if it's file integrity checking (acceptable use)
            cursor.execute("""
                SELECT 1 FROM assignments a
                WHERE a.file = ?
                  AND a.line = ?
                  AND (a.target_var LIKE '%checksum%'
                       OR a.target_var LIKE '%etag%'
                       OR a.target_var LIKE '%cache%')
                LIMIT 1
            """, [file, line])
            
            if not cursor.fetchone():  # Not file hashing
                findings.append(StandardFinding(
                    rule_name='crypto-weak-hash',
                    message=f'Using weak hash algorithm: {name}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{func}({args[:50] if args else ""})',
                    fix_suggestion=f'Use {recommendation}',
                    cwe_id='CWE-327'  # Use of Broken Crypto Algorithm
                ))
    
    # Check JavaScript crypto
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'createHash'
          AND (f.argument_expr LIKE '%md5%' OR f.argument_expr LIKE '%sha1%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        algo = 'MD5' if 'md5' in args.lower() else 'SHA-1'
        findings.append(StandardFinding(
            rule_name='crypto-weak-hash-js',
            message=f'Using weak hash algorithm: {algo}',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'createHash("{algo.lower()}")',
            fix_suggestion='Use createHash("sha256") or stronger',
            cwe_id='CWE-327'
        ))
    
    # Weak encryption algorithms
    weak_encryption = ['des', 'rc4', 'rc2', 'blowfish']
    
    for algo in weak_encryption:
        cursor.execute("""
            SELECT f.file, f.line, f.callee_function
            FROM function_call_args f
            WHERE f.callee_function LIKE ?
               OR f.callee_function LIKE ?
            ORDER BY f.file, f.line
        """, [f'%{algo}%', f'%{algo.upper()}%'])
        
        for file, line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='crypto-weak-encryption',
                message=f'Using weak encryption algorithm: {algo.upper()}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=func,
                fix_suggestion='Use AES-256-GCM or ChaCha20-Poly1305',
                cwe_id='CWE-327'
            ))
    
    return findings


# ============================================================================
# CHECK 3: Predictable Token Generation
# ============================================================================

def _find_predictable_tokens(cursor, security_vars: Set[str]) -> List[StandardFinding]:
    """Find predictable methods for generating security tokens."""
    findings = []
    
    # Timestamp-based token generation
    timestamp_functions = [
        'time.time', 'datetime.now', 'Date.now', 'Date.getTime',
        'timestamp', 'time.clock', 'time.perf_counter'
    ]
    
    for func in timestamp_functions:
        cursor.execute("""
            SELECT a.file, a.line, a.target_var, a.source_expr
            FROM assignments a
            WHERE a.source_expr LIKE ?
            ORDER BY a.file, a.line
        """, [f'%{func}%'])
        
        for file, line, var, expr in cursor.fetchall():
            if var in security_vars:
                findings.append(StandardFinding(
                    rule_name='crypto-predictable-token',
                    message=f'Predictable token generation using timestamp: {var}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=f'{var} = {func}()',
                    fix_suggestion='Use cryptographically secure random: secrets.token_hex() or crypto.randomBytes()',
                    cwe_id='CWE-330'
                ))
    
    # Sequential/incremental tokens
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%++%' 
               OR a.source_expr LIKE '%+= 1%'
               OR a.source_expr LIKE '%+ 1%')
          AND (a.target_var LIKE '%token%'
               OR a.target_var LIKE '%id%'
               OR a.target_var LIKE '%session%'
               OR a.target_var LIKE '%nonce%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-sequential-token',
            message=f'Sequential/incremental token generation: {var}',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{var}++',
            fix_suggestion='Use unpredictable random tokens',
            cwe_id='CWE-330'
        ))
    
    return findings


# ============================================================================
# CHECK 4: Weak Key Derivation
# ============================================================================

def _find_weak_key_derivation(cursor) -> List[StandardFinding]:
    """Find weak key derivation functions."""
    findings = []
    
    # PBKDF2 with weak algorithms
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%pbkdf2%'
          AND (f.argument_expr LIKE '%md5%' OR f.argument_expr LIKE '%sha1%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        algo = 'MD5' if 'md5' in args.lower() else 'SHA-1'
        findings.append(StandardFinding(
            rule_name='crypto-weak-kdf',
            message=f'PBKDF2 with weak hash algorithm: {algo}',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'pbkdf2_hmac("{algo.lower()}", ...)',
            fix_suggestion='Use PBKDF2 with SHA-256 or Argon2/scrypt',
            cwe_id='CWE-916'  # Use of Password Hash With Insufficient Computational Effort
        ))
    
    # Low iteration counts
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%pbkdf2%'
          AND f.argument_expr REGEXP '[0-9]+'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Try to extract iteration count
        import re
        numbers = re.findall(r'\b\d+\b', args)
        for num in numbers:
            if int(num) < 100000:  # OWASP recommends 100,000+
                findings.append(StandardFinding(
                    rule_name='crypto-weak-iterations',
                    message=f'PBKDF2 with low iteration count: {num}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='security',
                    snippet=f'pbkdf2(..., iterations={num})',
                    fix_suggestion='Use at least 100,000 iterations (OWASP recommendation)',
                    cwe_id='CWE-916'
                ))
                break
    
    return findings


# ============================================================================
# CHECK 5: Hardcoded Salts
# ============================================================================

def _find_hardcoded_salts(cursor) -> List[StandardFinding]:
    """Find hardcoded salt values."""
    findings = []
    
    # Find salt assignments with string literals
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%salt%'
          AND (a.source_expr LIKE '"%' OR a.source_expr LIKE "'%")
          AND a.source_expr NOT LIKE '%random%'
          AND a.source_expr NOT LIKE '%generate%'
          AND a.source_expr NOT LIKE '%secrets%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        # Check if it's a literal string (not a function call)
        if not '(' in expr:
            findings.append(StandardFinding(
                rule_name='crypto-hardcoded-salt',
                message=f'Hardcoded salt value: {var}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{var} = "..."',
                fix_suggestion='Generate unique random salt for each password',
                cwe_id='CWE-759'  # Use of One-Way Hash without Salt
            ))
    
    return findings


# ============================================================================
# CHECK 6: ECB Mode Usage
# ============================================================================

def _find_ecb_mode(cursor) -> List[StandardFinding]:
    """Find usage of ECB mode in encryption (insecure)."""
    findings = []
    
    # ECB mode in any encryption context
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_expr LIKE '%ECB%'
          AND (f.callee_function LIKE '%cipher%'
               OR f.callee_function LIKE '%encrypt%'
               OR f.callee_function LIKE '%AES%'
               OR f.callee_function LIKE '%DES%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-ecb-mode',
            message='ECB mode encryption is insecure - reveals data patterns',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{func}(...ECB...)',
            fix_suggestion='Use GCM, CBC, or CTR mode with proper IV',
            cwe_id='CWE-327'
        ))
    
    # Also check for mode assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var
        FROM assignments a
        WHERE a.target_var LIKE '%mode%'
          AND a.source_expr LIKE '%ECB%'
        ORDER BY a.file, a.line
    """)
    
    for file, line, var in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-ecb-mode',
            message=f'ECB mode configured: {var}',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{var} = "ECB"',
            fix_suggestion='Use authenticated encryption modes like GCM',
            cwe_id='CWE-327'
        ))
    
    return findings