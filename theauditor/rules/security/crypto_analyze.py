"""Cryptography Security Analyzer - Golden Standard Implementation.

Detects 15+ cryptographic vulnerabilities using database-driven approach with
intelligent fallbacks. Follows EXACT golden standard patterns.

This implementation:
- Uses frozensets for ALL patterns
- Checks table existence before queries
- Uses parameterized queries (no SQL injection)
- Implements multi-layer detection
- Provides confidence scoring
- Maps all findings to CWE IDs
"""

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata
)

# ============================================================================
# RULE METADATA (Golden Standard)
# ============================================================================

METADATA = RuleMetadata(
    name="crypto_security",
    category="security",
    target_extensions=['.py', '.js', '.ts', '.php'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'demo/'],
    requires_jsx_pass=False
)

# ============================================================================
# GOLDEN STANDARD: FROZENSETS FOR ALL PATTERNS
# ============================================================================

# Weak random number generators
WEAK_RANDOM_FUNCTIONS = frozenset([
    'Math.random',
    'random.random',
    'random.randint',
    'random.choice',
    'random.randbytes',
    'random.randrange',
    'random.getrandbits',
    'random.uniform',
    'random.sample',
    'random.shuffle',
    'rand',
    'mt_rand',  # PHP
    'lcg_value'  # PHP
])

# Cryptographically secure alternatives
SECURE_RANDOM_FUNCTIONS = frozenset([
    'secrets.token_hex',
    'secrets.token_bytes',
    'secrets.token_urlsafe',
    'secrets.randbits',
    'secrets.choice',
    'crypto.randomBytes',
    'crypto.getRandomValues',
    'crypto.randomFillSync',
    'crypto.randomUUID',
    'os.urandom',
    'SystemRandom'
])

# Weak hash algorithms
WEAK_HASH_ALGORITHMS = frozenset([
    'md5', 'MD5',
    'sha1', 'SHA1', 'sha-1', 'SHA-1',
    'md4', 'MD4',
    'md2', 'MD2',
    'sha0', 'SHA0',
    'ripemd', 'RIPEMD'
])

# Strong hash algorithms
STRONG_HASH_ALGORITHMS = frozenset([
    'sha256', 'SHA256', 'sha-256', 'SHA-256',
    'sha384', 'SHA384', 'sha-384', 'SHA-384',
    'sha512', 'SHA512', 'sha-512', 'SHA-512',
    'sha3-256', 'SHA3-256',
    'sha3-384', 'SHA3-384',
    'sha3-512', 'SHA3-512',
    'blake2b', 'BLAKE2B',
    'blake2s', 'BLAKE2S'
])

# Weak encryption algorithms
WEAK_ENCRYPTION_ALIASES = frozenset([
    'des', '3des', 'tripledes', 'des-ede3', 'des-ede', 'des3',
    'rc4', 'arcfour', 'rc2',
    'blowfish', 'cast', 'cast5', 'idea', 'tea', 'xtea'
])

# Strong encryption algorithms
STRONG_ENCRYPTION_ALGORITHMS = frozenset([
    'aes', 'AES',
    'aes-128-gcm', 'AES-128-GCM',
    'aes-256-gcm', 'AES-256-GCM',
    'chacha20', 'ChaCha20',
    'chacha20-poly1305', 'ChaCha20-Poly1305',
    'xchacha20', 'XChaCha20'
])

# Insecure encryption modes
INSECURE_MODES = frozenset([
    'ecb', 'ECB',
    'cbc', 'CBC'  # Without HMAC
])

# Secure encryption modes
SECURE_MODES = frozenset([
    'gcm', 'GCM',
    'ccm', 'CCM',
    'eax', 'EAX',
    'ocb', 'OCB',
    'ctr', 'CTR'  # With HMAC
])

# Security-related keywords for context detection
SECURITY_KEYWORDS = frozenset([
    'password', 'passwd', 'pwd',
    'secret', 'key', 'token',
    'auth', 'authentication', 'authorization',
    'session', 'cookie', 'jwt',
    'api_key', 'apikey', 'access_token',
    'refresh_token', 'bearer',
    'credential', 'credentials',
    'salt', 'nonce', 'iv',
    'pin', 'otp', 'totp',
    'private', 'priv', 'encryption',
    'signature', 'sign', 'verify',
    'certificate', 'cert'
])

# Non-security context keywords (for reducing false positives)
NON_SECURITY_KEYWORDS = frozenset([
    'checksum', 'etag', 'cache',
    'hash_table', 'hashmap', 'hashtable',
    'test', 'mock', 'example',
    'demo', 'sample', 'placeholder',
    'file', 'content', 'data',
    'index', 'offset', 'length'
])

# Deprecated crypto libraries
DEPRECATED_LIBRARIES = frozenset([
    'pycrypto',
    'mcrypt',
    'openssl_encrypt',  # PHP deprecated functions
    'openssl_decrypt',
    'CryptoJS.enc.Base64'  # Not encryption
])

# Timing-vulnerable comparison functions
TIMING_VULNERABLE_COMPARISONS = frozenset([
    '==',
    '===',
    'strcmp',
    'strcasecmp',
    '.equals',
    '.compare'
])

# Constant-time comparison functions
CONSTANT_TIME_COMPARISONS = frozenset([
    'hmac.compare_digest',
    'secrets.compare_digest',
    'crypto.timingSafeEqual',
    'hash_equals',  # PHP
    'MessageDigest.isEqual'  # Java
])

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_crypto_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect cryptographic vulnerabilities using golden standard patterns.

    Implements 15+ crypto vulnerability patterns with multi-layer detection
    and intelligent fallbacks.
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # MANDATORY: Check table existence first
        existing_tables = _check_tables(cursor)
        if not existing_tables:
            return findings

        # Core vulnerability detection (15 patterns)

        # 1. Weak random number generation
        if 'function_call_args' in existing_tables:
            findings.extend(_find_weak_random_generation(cursor, existing_tables))

        # 2. Weak hash algorithms
        if 'function_call_args' in existing_tables:
            findings.extend(_find_weak_hash_algorithms(cursor, existing_tables))

        # 3. Weak encryption algorithms
        if 'function_call_args' in existing_tables:
            findings.extend(_find_weak_encryption_algorithms(cursor, existing_tables))

        # 4. Missing salt in hashing
        if 'function_call_args' in existing_tables and 'assignments' in existing_tables:
            findings.extend(_find_missing_salt(cursor, existing_tables))

        # 5. Static/hardcoded salts
        if 'assignments' in existing_tables:
            findings.extend(_find_static_salt(cursor, existing_tables))

        # 6. Weak KDF iterations
        if 'function_call_args' in existing_tables:
            findings.extend(_find_weak_kdf_iterations(cursor, existing_tables))

        # 7. ECB mode usage
        if 'function_call_args' in existing_tables:
            findings.extend(_find_ecb_mode(cursor, existing_tables))

        # 8. Missing IV/nonce
        if 'function_call_args' in existing_tables:
            findings.extend(_find_missing_iv(cursor, existing_tables))

        # 9. Static/hardcoded IV
        if 'assignments' in existing_tables:
            findings.extend(_find_static_iv(cursor, existing_tables))

        # 10. Predictable PRNG seeds
        if 'assignments' in existing_tables:
            findings.extend(_find_predictable_seeds(cursor, existing_tables))

        # 11. Hardcoded encryption keys
        if 'assignments' in existing_tables:
            findings.extend(_find_hardcoded_keys(cursor, existing_tables))

        # 12. Weak key sizes
        if 'function_call_args' in existing_tables:
            findings.extend(_find_weak_key_size(cursor, existing_tables))

        # 13. Passwords in URLs
        if 'function_call_args' in existing_tables:
            findings.extend(_find_password_in_url(cursor, existing_tables))

        # 14. Timing-vulnerable comparisons
        if 'function_call_args' in existing_tables and 'symbols' in existing_tables:
            findings.extend(_find_timing_vulnerable_compare(cursor, existing_tables))

        # 15. Deprecated crypto libraries
        if 'function_call_args' in existing_tables:
            findings.extend(_find_deprecated_libraries(cursor, existing_tables))

    finally:
        conn.close()

    return findings

# ============================================================================
# HELPER: Table Existence Check (MANDATORY)
# ============================================================================

def _check_tables(cursor) -> Set[str]:
    """Check which tables exist in the database.

    This is MANDATORY to avoid crashes on missing tables.
    """
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND name IN (
            'assignments',
            'function_call_args',
            'symbols',
            'cfg_blocks',
            'files',
            'api_endpoints'
        )
    """)
    return {row[0] for row in cursor.fetchall()}

# ============================================================================
# HELPER: Context Detection
# ============================================================================

def _determine_confidence(
    file: str,
    line: int,
    func_name: str,
    cursor,
    existing_tables: Set[str]
) -> Confidence:
    """Determine confidence level based on context analysis.

    Uses multiple signals to determine if crypto usage is security-critical.
    """
    # Check if in security-related function
    if func_name and any(kw in func_name.lower() for kw in SECURITY_KEYWORDS):
        return Confidence.HIGH

    # Check if NOT in non-security context
    if func_name and any(kw in func_name.lower() for kw in NON_SECURITY_KEYWORDS):
        return Confidence.LOW

    # Check proximity to security operations (within 5 lines)
    if 'function_call_args' in existing_tables:
        cursor.execute("""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
            AND ABS(line - ?) <= 5
            AND (callee_function LIKE '%encrypt%'
                 OR callee_function LIKE '%decrypt%'
                 OR callee_function LIKE '%hash%'
                 OR callee_function LIKE '%sign%'
                 OR callee_function LIKE '%verify%')
        """, [file, line])

        proximity_count = cursor.fetchone()[0]
        if proximity_count > 0:
            return Confidence.HIGH

    # Check variable assignment context
    if 'assignments' in existing_tables:
        cursor.execute("""
            SELECT target_var FROM assignments
            WHERE file = ?
            AND ABS(line - ?) <= 3
        """, [file, line])

        for row in cursor.fetchall():
            var_name = row[0].lower() if row[0] else ''
            if any(kw in var_name for kw in SECURITY_KEYWORDS):
                return Confidence.MEDIUM

    return Confidence.MEDIUM  # Default to medium

def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file (lower priority)."""
    test_indicators = ['test', 'spec', 'mock', 'fixture', '__tests__', 'tests']
    file_lower = file_path.lower()
    return any(indicator in file_lower for indicator in test_indicators)

# ============================================================================
# PATTERN 1: Weak Random Number Generation
# ============================================================================

def _find_weak_random_generation(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of weak random number generators for security purposes."""
    findings = []

    # Build parameterized query
    placeholders = ' OR '.join(['callee_function = ?' for _ in WEAK_RANDOM_FUNCTIONS])
    params = list(WEAK_RANDOM_FUNCTIONS)

    cursor.execute(f"""
        SELECT file, line, callee_function, caller_function, argument_expr
        FROM function_call_args
        WHERE {placeholders}
        ORDER BY file, line
    """, params)

    for file, line, callee, caller, args in cursor.fetchall():
        # Determine confidence based on context
        confidence = _determine_confidence(file, line, caller, cursor, existing_tables)

        # Skip if low confidence and in test file
        if confidence == Confidence.LOW and _is_test_file(file):
            continue

        findings.append(StandardFinding(
            rule_name='crypto-insecure-random',
            message=f'Insecure random function {callee} used',
            file_path=file,
            line=line,
            severity=Severity.HIGH if confidence == Confidence.HIGH else Severity.MEDIUM,
            confidence=confidence,
            category='security',
            snippet=f'{callee}({args[:50] if args else ""}...)',
            cwe_id='CWE-330'  # Use of Insufficiently Random Values
        ))

    return findings

# ============================================================================
# PATTERN 2: Weak Hash Algorithms
# ============================================================================

def _find_weak_hash_algorithms(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of weak/broken hash algorithms."""
    findings = []

    # Check direct hash function calls
    for weak_algo in WEAK_HASH_ALGORITHMS:
        cursor.execute("""
            SELECT file, line, callee_function, caller_function, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE ?
                   OR callee_function LIKE ?
                   OR argument_expr LIKE ?)
            ORDER BY file, line
        """, [f'%{weak_algo}%', f'hashlib.{weak_algo}', f'%{weak_algo}%'])

        for file, line, callee, caller, args in cursor.fetchall():
            confidence = _determine_confidence(file, line, caller, cursor, existing_tables)

            # Skip if explicitly for file checksums
            if confidence == Confidence.LOW:
                continue

            algo_upper = weak_algo.upper().replace('-', '')

            findings.append(StandardFinding(
                rule_name='crypto-weak-hash',
                message=f'Weak hash algorithm {algo_upper} detected',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=confidence,
                category='security',
                snippet=f'{callee}(...{weak_algo}...)',
                cwe_id='CWE-327'  # Use of Broken or Risky Cryptographic Algorithm
            ))

    return findings

# ============================================================================
# PATTERN 3: Weak Encryption Algorithms
# ============================================================================

def _contains_alias(text: Optional[str], alias: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if alias in {'des', 'des3', 'tripledes', 'des-ede3', 'des-ede'}:
        return any(
            keyword in lowered for keyword in (
                'des(', 'des3(', 'tripledes(', 'des-ede3(', 'des-ede('
            )
        )
    pattern = rf'(?<![a-z0-9_]){re.escape(alias.lower())}(?![a-z0-9_])'
    return re.search(pattern, lowered) is not None


def _find_weak_encryption_algorithms(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of weak/broken encryption algorithms."""
    findings: List[StandardFinding] = []

    if 'function_call_args' not in existing_tables:
        return findings

    cursor.execute("""
        SELECT DISTINCT file, line, callee_function, argument_expr
        FROM function_call_args
        ORDER BY file, line
    """)

    seen: Set[Tuple[str, int, str]] = set()

    for file, line, callee, argument in cursor.fetchall():
        callee_lower = (callee or '').lower()
        argument_lower = (argument or '').lower()

        matched_algos = set()

        for alias in WEAK_ENCRYPTION_ALIASES:
            if _contains_alias(callee_lower, alias) or _contains_alias(argument_lower, alias):
                matched_algos.add(alias)

        if not matched_algos:
            continue

        algo_names = sorted({alias.upper() for alias in matched_algos})
        signature_key = (
            file,
            line,
            callee or '|'.join(algo_names)
        )

        if signature_key in seen:
            continue
        seen.add(signature_key)

        algo_label = ', '.join(algo_names)
        snippet_source = callee or argument or ''

        findings.append(StandardFinding(
            rule_name='crypto-weak-encryption',
            message=f'Weak encryption algorithm {algo_label} detected',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            confidence=Confidence.MEDIUM,
            category='security',
            snippet=snippet_source[:120],
            cwe_id='CWE-327'
        ))

    return findings

# ============================================================================
# PATTERN 4: Missing Salt in Hashing
# ============================================================================

def _find_missing_salt(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find password hashing without salt."""
    findings = []

    # Find hash operations on password-like variables
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%hash%'
               OR f.callee_function LIKE '%digest%'
               OR f.callee_function LIKE '%bcrypt%'
               OR f.callee_function LIKE '%scrypt%'
               OR f.callee_function LIKE '%pbkdf2%')
          AND (f.argument_expr LIKE '%password%'
               OR f.argument_expr LIKE '%passwd%'
               OR f.argument_expr LIKE '%pwd%')
        ORDER BY f.file, f.line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if salt mentioned in nearby code (within 10 lines)
        cursor.execute("""
            SELECT COUNT(*) FROM assignments
            WHERE file = ?
              AND ABS(line - ?) <= 10
              AND (target_var LIKE '%salt%' OR source_expr LIKE '%salt%')
        """, [file, line])

        has_salt_nearby = cursor.fetchone()[0] > 0

        # Also check if salt in function arguments
        has_salt_in_args = 'salt' in args.lower() if args else False

        if not has_salt_nearby and not has_salt_in_args:
            findings.append(StandardFinding(
                rule_name='crypto-missing-salt',
                message='Password hashing without salt detected',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category='security',
                snippet=f'{callee}(password, ...)',
                cwe_id='CWE-759'  # Use of One-Way Hash without Salt
            ))

    return findings

# ============================================================================
# PATTERN 5: Static/Hardcoded Salts
# ============================================================================

def _find_static_salt(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find hardcoded salt values."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var LIKE '%salt%'
          AND (source_expr LIKE '"%' OR source_expr LIKE "'%")
          AND source_expr NOT LIKE '%random%'
          AND source_expr NOT LIKE '%generate%'
          AND source_expr NOT LIKE '%uuid%'
          AND source_expr NOT LIKE '%secrets%'
          AND source_expr NOT LIKE '%urandom%'
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Check if it's a literal string (not function call)
        if '(' not in expr and not expr.startswith('os.'):
            findings.append(StandardFinding(
                rule_name='crypto-static-salt',
                message=f'Hardcoded salt value in {var}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{var} = "..."',
                cwe_id='CWE-760'  # Use of One-Way Hash with Predictable Salt
            ))

    return findings

# ============================================================================
# PATTERN 6: Weak KDF Iterations
# ============================================================================

def _find_weak_kdf_iterations(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find weak key derivation functions with low iterations."""
    findings = []

    # Find PBKDF2 and similar KDF calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%pbkdf2%'
           OR callee_function LIKE '%scrypt%'
           OR callee_function LIKE '%bcrypt%'
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        if not args:
            continue

        # Extract numbers from arguments (potential iteration counts)
        numbers = re.findall(r'\b(\d+)\b', args)

        for num_str in numbers:
            num = int(num_str)
            # OWASP recommends minimum 100,000 iterations for PBKDF2
            if num < 100000 and num > 100:  # Filter out obvious non-iteration numbers
                findings.append(StandardFinding(
                    rule_name='crypto-weak-kdf-iterations',
                    message=f'Weak KDF iteration count: {num}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{callee}(...iterations={num}...)',
                    cwe_id='CWE-916'  # Use of Password Hash With Insufficient Computational Effort
                ))
                break  # Only report once per call

    return findings

# ============================================================================
# PATTERN 7: ECB Mode Usage
# ============================================================================

def _find_ecb_mode(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of ECB mode in encryption."""
    findings = []

    # ECB mode in function arguments
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (argument_expr LIKE '%ECB%' OR argument_expr LIKE '%ecb%')
          AND (callee_function LIKE '%cipher%'
               OR callee_function LIKE '%encrypt%'
               OR callee_function LIKE '%decrypt%'
               OR callee_function LIKE '%AES%'
               OR callee_function LIKE '%DES%')
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-ecb-mode',
            message='ECB mode encryption is insecure (reveals patterns)',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            category='security',
            snippet=f'{callee}(...ECB...)',
            cwe_id='CWE-327'
        ))

    # Also check mode variable assignments
    if 'assignments' in existing_tables:
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%mode%' OR target_var LIKE '%MODE%')
              AND (source_expr LIKE '%ECB%' OR source_expr LIKE '%ecb%')
            ORDER BY file, line
        """)

        for file, line, var, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='crypto-ecb-mode-config',
                message=f'ECB mode configured in {var}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{var} = "ECB"',
                cwe_id='CWE-327'
            ))

    return findings

# ============================================================================
# PATTERN 8: Missing IV/Nonce
# ============================================================================

def _find_missing_iv(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find encryption operations without initialization vector."""
    findings = []

    # Find encryption calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%encrypt%'
               OR callee_function LIKE '%cipher%')
          AND callee_function NOT LIKE '%decrypt%'
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if IV/nonce mentioned in arguments
        has_iv_in_args = False
        if args:
            args_lower = args.lower()
            has_iv_in_args = any(term in args_lower for term in ['iv', 'nonce', 'initialization'])

        if not has_iv_in_args:
            # Check proximity for IV generation (within 10 lines)
            cursor.execute("""
                SELECT COUNT(*) FROM assignments
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND (target_var LIKE '%iv%'
                       OR target_var LIKE '%nonce%'
                       OR source_expr LIKE '%random%')
            """, [file, line])

            has_iv_nearby = cursor.fetchone()[0] > 0

            if not has_iv_nearby:
                findings.append(StandardFinding(
                    rule_name='crypto-missing-iv',
                    message='Encryption without initialization vector',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{callee}(...)',
                    cwe_id='CWE-329'  # Not Using Random IV with CBC Mode
                ))

    return findings

# ============================================================================
# PATTERN 9: Static/Hardcoded IV
# ============================================================================

def _find_static_iv(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find hardcoded initialization vectors."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE (target_var LIKE '%iv%' OR target_var LIKE '%nonce%'
               OR target_var LIKE '%initialization_vector%')
          AND (source_expr LIKE '"%' OR source_expr LIKE "'%"
               OR source_expr LIKE '[0,%' OR source_expr LIKE 'bytes(%')
          AND source_expr NOT LIKE '%random%'
          AND source_expr NOT LIKE '%generate%'
          AND source_expr NOT LIKE '%urandom%'
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Check if it's a static value
        if not '(' in expr or 'bytes([0' in expr or 'b"\\x00' in expr:
            findings.append(StandardFinding(
                rule_name='crypto-static-iv',
                message=f'Hardcoded initialization vector in {var}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{var} = {expr[:50]}',
                cwe_id='CWE-329'
            ))

    return findings

# ============================================================================
# PATTERN 10: Predictable PRNG Seeds
# ============================================================================

def _find_predictable_seeds(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find predictable seeds for random number generators."""
    findings = []

    # Timestamp-based seeds
    timestamp_functions = [
        'time.time', 'datetime.now', 'Date.now',
        'Date.getTime', 'timestamp', 'time()',
        'microtime', 'performance.now'
    ]

    for ts_func in timestamp_functions:
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr LIKE ?
              AND (target_var LIKE '%seed%'
                   OR target_var LIKE '%random%')
            ORDER BY file, line
        """, [f'%{ts_func}%'])

        for file, line, var, expr in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='crypto-predictable-seed',
                message=f'Predictable PRNG seed using {ts_func}',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{var} = {ts_func}()',
                cwe_id='CWE-335'  # Incorrect Usage of Seeds in PRNG
            ))

    # Also check seed() function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%seed%' OR callee_function LIKE '%srand%')
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if using predictable value
        if any(ts in args.lower() for ts in ['time', 'date', 'timestamp']):
            findings.append(StandardFinding(
                rule_name='crypto-predictable-seed-func',
                message='PRNG seeded with predictable value',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{callee}({args[:50]})',
                cwe_id='CWE-335'
            ))

    return findings

# ============================================================================
# PATTERN 11: Hardcoded Encryption Keys
# ============================================================================

def _find_hardcoded_keys(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find hardcoded encryption keys."""
    findings = []

    # Key-related variable names
    key_patterns = [
        '%key%', '%KEY%',
        '%secret%', '%SECRET%',
        '%cipher_key%', '%encryption_key%',
        '%aes_key%', '%des_key%',
        '%private_key%', '%priv_key%'
    ]

    conditions = ' OR '.join(['target_var LIKE ?' for _ in key_patterns])

    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE ({conditions})
          AND (source_expr LIKE '"%' OR source_expr LIKE "'%"
               OR source_expr LIKE 'b"%' OR source_expr LIKE "b'%")
          AND source_expr NOT LIKE '%env%'
          AND source_expr NOT LIKE '%config%'
          AND source_expr NOT LIKE '%random%'
          AND source_expr NOT LIKE '%generate%'
          AND LENGTH(source_expr) > 10
        ORDER BY file, line
    """, key_patterns)

    for file, line, var, expr in cursor.fetchall():
        # Skip if it's reading from environment or config
        if 'os.environ' in expr or 'process.env' in expr:
            continue

        findings.append(StandardFinding(
            rule_name='crypto-hardcoded-key',
            message=f'Hardcoded encryption key in {var}',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            category='security',
            snippet=f'{var} = "***REDACTED***"',
            cwe_id='CWE-798'  # Use of Hard-coded Credentials
        ))

    return findings

# ============================================================================
# PATTERN 12: Weak Key Sizes
# ============================================================================

def _find_weak_key_size(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of weak encryption key sizes."""
    findings = []

    # Common key generation functions with size parameters
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%generate_key%'
               OR callee_function LIKE '%keygen%'
               OR callee_function LIKE '%new_key%'
               OR callee_function LIKE '%random%key%')
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Extract numbers that might be key sizes
        numbers = re.findall(r'\b(\d+)\b', args)

        for num_str in numbers:
            num = int(num_str)
            # Check for weak key sizes (bits or bytes)
            if num in [40, 56, 64, 80]:  # Known weak key sizes in bits
                findings.append(StandardFinding(
                    rule_name='crypto-weak-key-size',
                    message=f'Weak key size: {num} bits',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{callee}({num})',
                    cwe_id='CWE-326'  # Inadequate Encryption Strength
                ))
            elif num in [5, 7, 8, 10]:  # Weak sizes in bytes
                findings.append(StandardFinding(
                    rule_name='crypto-weak-key-size-bytes',
                    message=f'Weak key size: {num} bytes ({num * 8} bits)',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{callee}({num})',
                    cwe_id='CWE-326'
                ))

    return findings

# ============================================================================
# PATTERN 13: Passwords in URLs
# ============================================================================

def _find_password_in_url(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find passwords transmitted in URLs."""
    findings = []

    # URL-building functions with password parameters
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%url%'
               OR callee_function LIKE '%uri%'
               OR callee_function LIKE '%query%'
               OR callee_function LIKE '%params%')
          AND (argument_expr LIKE '%password%'
               OR argument_expr LIKE '%passwd%'
               OR argument_expr LIKE '%pwd%'
               OR argument_expr LIKE '%token%'
               OR argument_expr LIKE '%secret%')
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-password-in-url',
            message='Sensitive data in URL parameters',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            category='security',
            snippet=f'{callee}(...password...)',
            cwe_id='CWE-598'  # Information Exposure Through Query Strings in GET Request
        ))

    return findings

# ============================================================================
# PATTERN 14: Timing-Vulnerable Comparisons
# ============================================================================

def _find_timing_vulnerable_compare(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find timing-vulnerable string comparisons for secrets."""
    findings = []

    # Find comparisons involving security-sensitive variables
    if 'symbols' in existing_tables:
        cursor.execute("""
            SELECT path, name, line
            FROM symbols
            WHERE (name LIKE '%password%'
                   OR name LIKE '%token%'
                   OR name LIKE '%secret%'
                   OR name LIKE '%key%'
                   OR name LIKE '%hash%'
                   OR name LIKE '%signature%')
              AND type = 'comparison'
            ORDER BY path, line
        """)

        for file, name, line in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='crypto-timing-vulnerable',
                message=f'Timing-vulnerable comparison of {name}',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                category='security',
                snippet=f'{name} == ...',
                cwe_id='CWE-208'  # Observable Timing Discrepancy
            ))

    # Also check for strcmp and similar functions
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ('strcmp', 'strcasecmp', 'memcmp')
          AND (argument_expr LIKE '%password%'
               OR argument_expr LIKE '%token%'
               OR argument_expr LIKE '%secret%')
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='crypto-timing-strcmp',
            message=f'Timing-vulnerable {callee} for secrets',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            category='security',
            snippet=f'{callee}(secret, ...)',
            cwe_id='CWE-208'
        ))

    return findings

# ============================================================================
# PATTERN 15: Deprecated Crypto Libraries
# ============================================================================

def _find_deprecated_libraries(cursor, existing_tables: Set[str]) -> List[StandardFinding]:
    """Find usage of deprecated cryptography libraries."""
    findings = []

    deprecated_funcs = [
        ('pycrypto', 'pycrypto is unmaintained'),
        ('mcrypt', 'mcrypt is deprecated'),
        ('CryptoJS.enc.Base64', 'Base64 is encoding, not encryption'),
        ('md5_file', 'MD5 should not be used'),
        ('sha1_file', 'SHA1 is deprecated')
    ]

    for deprecated, reason in deprecated_funcs:
        cursor.execute("""
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function LIKE ?
            ORDER BY file, line
        """, [f'%{deprecated}%'])

        for file, line, callee in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='crypto-deprecated-library',
                message=f'{reason}: {deprecated}',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                snippet=callee,
                cwe_id='CWE-327'
            ))

    return findings

# ============================================================================
# TAINT INTEGRATION (for future taint analyzer)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register crypto-specific patterns with taint analyzer.

    This allows the taint analyzer to track weak random sources
    flowing into cryptographic operations.
    """
    # Register weak random as taint sources
    for func in WEAK_RANDOM_FUNCTIONS:
        taint_registry.register_source(func, "weak_random", "any")

    # Register crypto operations as sinks
    crypto_sinks = [
        'encrypt', 'decrypt',
        'sign', 'verify',
        'generateKey', 'deriveKey',
        'hash', 'digest'
    ]

    for sink in crypto_sinks:
        taint_registry.register_sink(sink, "crypto_operation", "any")
