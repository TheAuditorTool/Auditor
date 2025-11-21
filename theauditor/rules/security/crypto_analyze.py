"""Cryptography Security Analyzer - Schema Contract Compliant Implementation.

Detects 15+ cryptographic vulnerabilities using database-driven approach.
Follows v1.1+ schema contract compliance (no table checks, no regex).

This implementation:
- Uses frozensets for ALL patterns (O(1) lookups)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Implements multi-layer detection
- Provides confidence scoring
- Maps all findings to CWE IDs
- Tokenizes call metadata from normalized database to avoid substring collisions

False positive fixes (2025-11-22):
- Credit: Token-based matching technique from external contributor @dev-corelift (PR #20)
- Prevents substring collisions like "includes" triggering "DES" warnings
- Uses camelCase-aware identifier tokenization for precise pattern matching
"""


import sqlite3
import re
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
    requires_jsx_pass=False,
    execution_scope="database"  # Database-wide query, not per-file iteration
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

# ============================================================================
# TOKEN-BASED MATCHING (False Positive Prevention)
# Credit: @dev-corelift (PR #20)
# ============================================================================

_CAMEL_CASE_TOKEN_RE = re.compile(r'[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+')


def _split_identifier_tokens(value: Optional[str]) -> List[str]:
    """Split identifiers into normalized, lowercase tokens.

    Handles camelCase, snake_case, kebab-case, and mixed patterns.
    Prevents substring collisions like "includes" matching "DES".

    Examples:
        >>> _split_identifier_tokens("createDES3Cipher")
        ['create', 'des3', 'cipher']
        >>> _split_identifier_tokens("c.path.includes")
        ['c', 'path', 'includes']
    """
    if not value:
        return []

    tokens: List[str] = []

    for chunk in re.split(r'[^0-9A-Za-z]+', value):
        if not chunk:
            continue
        tokens.extend(_CAMEL_CASE_TOKEN_RE.findall(chunk))

    return [token.lower() for token in tokens if token]

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

def find_crypto_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect cryptographic vulnerabilities using schema contract patterns.

    Implements 15+ crypto vulnerability patterns with unconditional execution.
    All required tables guaranteed to exist by schema contract.
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # All required tables guaranteed to exist by schema contract
        # (theauditor/indexer/schema.py - TABLES registry with 46 table definitions)
        # If table missing, rule will crash with clear sqlite3.OperationalError (CORRECT behavior)

        # Core vulnerability detection (15 patterns) - execute unconditionally

        # 1. Weak random number generation
        findings.extend(_find_weak_random_generation(cursor))

        # 2. Weak hash algorithms
        findings.extend(_find_weak_hash_algorithms(cursor))

        # 3. Weak encryption algorithms
        findings.extend(_find_weak_encryption_algorithms(cursor))

        # 4. Missing salt in hashing
        findings.extend(_find_missing_salt(cursor))

        # 5. Static/hardcoded salts
        findings.extend(_find_static_salt(cursor))

        # 6. Weak KDF iterations
        findings.extend(_find_weak_kdf_iterations(cursor))

        # 7. ECB mode usage
        findings.extend(_find_ecb_mode(cursor))

        # 8. Missing IV/nonce
        findings.extend(_find_missing_iv(cursor))

        # 9. Static/hardcoded IV
        findings.extend(_find_static_iv(cursor))

        # 10. Predictable PRNG seeds
        findings.extend(_find_predictable_seeds(cursor))

        # 11. Hardcoded encryption keys
        findings.extend(_find_hardcoded_keys(cursor))

        # 12. Weak key sizes
        findings.extend(_find_weak_key_size(cursor))

        # 13. Passwords in URLs
        findings.extend(_find_password_in_url(cursor))

        # 14. Timing-vulnerable comparisons
        findings.extend(_find_timing_vulnerable_compare(cursor))

        # 15. Deprecated crypto libraries
        findings.extend(_find_deprecated_libraries(cursor))

    finally:
        conn.close()

    return findings

# ============================================================================
# HELPER: Context Detection
# ============================================================================

def _determine_confidence(
    file: str,
    line: int,
    func_name: str,
    cursor
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
    cursor.execute("""
        SELECT callee_function
        FROM function_call_args
        WHERE file = ?
        AND callee_function IS NOT NULL
    """, [file])

    # Filter in Python for nearby security operations
    security_operations = ['encrypt', 'decrypt', 'hash', 'sign', 'verify']
    proximity_count = 0
    for (callee,) in cursor.fetchall():
        # Check line proximity
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        cursor.execute("SELECT line FROM function_call_args WHERE file = ? AND callee_function = ?
        -- REMOVED LIMIT: was hiding bugs
        ", [file, callee])
        func_line = cursor.fetchone()
        if func_line and abs(func_line[0] - line) <= 5:
            # Check if contains security operation
            callee_lower = callee.lower()
            if any(op in callee_lower for op in security_operations):
                proximity_count += 1
                break

    if proximity_count > 0:
        return Confidence.HIGH

    # Check variable assignment context
    cursor.execute("""
        SELECT target_var FROM assignments
        WHERE file = ?
        AND target_var IS NOT NULL
    """, [file])

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

def _find_weak_random_generation(cursor) -> list[StandardFinding]:
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
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        confidence = _determine_confidence(file, line, caller, cursor)

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

def _find_weak_hash_algorithms(cursor) -> list[StandardFinding]:
    """Find usage of weak/broken hash algorithms."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, caller_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, caller, args in cursor.fetchall():
        # Check if callee or args contain weak algo
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_str = callee if callee else ''
        args_str = args if args else ''
        combined = f'{callee_str} {args_str}'.lower()

        # Check each weak algorithm
        weak_algo = None
        for algo in WEAK_HASH_ALGORITHMS:
            if algo.lower() in combined:
                weak_algo = algo
                break

        if not weak_algo:
            continue

        confidence = _determine_confidence(file, line, caller, cursor)

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
    """Check if the identifier or argument contains a crypto alias token.

    Uses token-based matching to prevent false positives from substring collisions.
    Credit: @dev-corelift (PR #20)

    Examples:
        >>> _contains_alias("c.path.includes", "des")
        False  # "includes" doesn't contain "des" as a token
        >>> _contains_alias("createDES3Cipher", "des3")
        True  # "des3" exists as a distinct token
    """
    if not text:
        return False

    text_tokens = set(_split_identifier_tokens(text))
    if not text_tokens:
        return False

    alias_tokens = _split_identifier_tokens(alias)
    if not alias_tokens:
        return False

    # Single-token alias: check for exact match
    if len(alias_tokens) == 1:
        return alias_tokens[0] in text_tokens

    # Multi-token alias: all tokens must be present
    return all(token in text_tokens for token in alias_tokens)


def _find_weak_encryption_algorithms(cursor) -> list[StandardFinding]:
    """Find usage of weak/broken encryption algorithms."""
    findings: list[StandardFinding] = []

    cursor.execute("""
        SELECT DISTINCT file, line, callee_function, argument_expr
        FROM function_call_args
        ORDER BY file, line
    """)

    seen: set[tuple[str, int, str]] = set()

    for file, line, callee, argument in cursor.fetchall():
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
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

def _find_missing_salt(cursor) -> list[StandardFinding]:
    """Find password hashing without salt."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    hash_functions = ['hash', 'digest', 'bcrypt', 'scrypt', 'pbkdf2']
    password_keywords = ['password', 'passwd', 'pwd']

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains hash function
        # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
        #       Rewrite with JOIN or CTE to eliminate per-row queries
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not any(hf in callee_lower for hf in hash_functions):
            continue

        # Check if args contain password keywords
        args_lower = args.lower()
        if not any(pw in args_lower for pw in password_keywords):
            continue

        # Check if salt mentioned in nearby code (within 10 lines)
        cursor.execute("""
            SELECT target_var, source_expr
            FROM assignments
            WHERE file = ?
              AND target_var IS NOT NULL
        """, [file])

        # Filter in Python for nearby salt assignments
        has_salt_nearby = False
        for var, expr in cursor.fetchall():
            # Check line proximity
            # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
            #       Rewrite with JOIN or CTE to eliminate per-row queries
            cursor.execute("SELECT line FROM assignments WHERE file = ? AND target_var = ?
        -- REMOVED LIMIT: was hiding bugs
        ", [file, var])
            assign_line = cursor.fetchone()
            if assign_line and abs(assign_line[0] - line) <= 10:
                # Check for salt in var or expr
                if 'salt' in (var or '').lower() or 'salt' in (expr or '').lower():
                    has_salt_nearby = True
                    break

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

def _find_static_salt(cursor) -> list[StandardFinding]:
    """Find hardcoded salt values."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    secure_patterns = ['random', 'generate', 'uuid', 'secrets', 'urandom']

    for file, line, var, expr in cursor.fetchall():
        # Check if variable name contains 'salt'
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        if 'salt' not in var.lower():
            continue

        # Check if source expression is a string literal (starts with quote)
        if not (expr.startswith('"') or expr.startswith("'")):
            continue

        # Skip if source contains secure patterns
        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

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

def _find_weak_kdf_iterations(cursor) -> list[StandardFinding]:
    """Find weak key derivation functions with low iterations."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    kdf_functions = ['pbkdf2', 'scrypt', 'bcrypt']

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains KDF function
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not any(kdf in callee_lower for kdf in kdf_functions):
            continue

        if not args:
            continue

        # Extract numbers from arguments (potential iteration counts)
        # Split on common delimiters and check if each token is a digit
        numbers = []
        for token in args.replace(',', ' ').replace('(', ' ').replace(')', ' ').replace('=', ' ').split():
            if token.isdigit():
                numbers.append(token)

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

def _find_ecb_mode(cursor) -> list[StandardFinding]:
    """Find usage of ECB mode in encryption."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    crypto_functions = ['cipher', 'encrypt', 'decrypt', 'AES', 'DES']

    for file, line, callee, args in cursor.fetchall():
        # Check if args contain ECB
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        args_lower = args.lower()
        if 'ecb' not in args_lower:
            continue

        # Check if callee is crypto-related
        callee_str = callee if callee else ''
        if not any(cf in callee_str for cf in crypto_functions):
            continue

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
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Check if variable contains 'mode'
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        if 'mode' not in var.lower():
            continue

        # Check if source contains ECB
        if 'ecb' not in expr.lower():
            continue

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

def _find_missing_iv(cursor) -> list[StandardFinding]:
    """Find encryption operations without initialization vector."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains 'encrypt' or 'cipher' but not 'decrypt'
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not ('encrypt' in callee_lower or 'cipher' in callee_lower):
            continue

        if 'decrypt' in callee_lower:
            continue

        # Check if IV/nonce mentioned in arguments
        has_iv_in_args = False
        if args:
            args_lower = args.lower()
            has_iv_in_args = any(term in args_lower for term in ['iv', 'nonce', 'initialization'])

        if not has_iv_in_args:
            # Check proximity for IV generation (within 10 lines)
            cursor.execute("""
                SELECT target_var, source_expr
                FROM assignments
                WHERE file = ?
                  AND target_var IS NOT NULL
            """, [file])

            # Filter in Python for nearby IV assignments
            has_iv_nearby = False
            for var, expr in cursor.fetchall():
                # Check line proximity
                # TODO: N+1 QUERY DETECTED - cursor.execute() inside fetchall() loop
                #       Rewrite with JOIN or CTE to eliminate per-row queries
                cursor.execute("SELECT line FROM assignments WHERE file = ? AND target_var = ?
        -- REMOVED LIMIT: was hiding bugs
        ", [file, var])
                assign_line = cursor.fetchone()
                if assign_line and abs(assign_line[0] - line) <= 10:
                    # Check for iv/nonce in var or random in expr
                    var_lower = (var or '').lower()
                    expr_lower = (expr or '').lower()
                    if 'iv' in var_lower or 'nonce' in var_lower or 'random' in expr_lower:
                        has_iv_nearby = True
                        break


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

def _find_static_iv(cursor) -> list[StandardFinding]:
    """Find hardcoded initialization vectors."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    iv_keywords = ['iv', 'nonce', 'initialization_vector']
    literal_starts = ['"', "'", '[0,', 'bytes(']
    secure_patterns = ['random', 'generate', 'urandom']

    for file, line, var, expr in cursor.fetchall():
        # Check if variable name contains IV keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        var_lower = var.lower()
        if not any(kw in var_lower for kw in iv_keywords):
            continue

        # Check if source looks like a literal
        if not any(expr.startswith(ls) for ls in literal_starts):
            continue

        # Skip if source contains secure patterns
        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

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

def _find_predictable_seeds(cursor) -> list[StandardFinding]:
    """Find predictable seeds for random number generators."""
    findings = []

    # Timestamp-based seeds
    timestamp_functions = [
        'time.time', 'datetime.now', 'Date.now',
        'Date.getTime', 'timestamp', 'time()',
        'microtime', 'performance.now'
    ]

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    seed_keywords = ['seed', 'random']

    for file, line, var, expr in cursor.fetchall():
        # Check if variable contains seed/random keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        var_lower = var.lower()
        if not any(kw in var_lower for kw in seed_keywords):
            continue

        # Check if source contains timestamp function
        ts_func_found = None
        for ts_func in timestamp_functions:
            if ts_func in expr:
                ts_func_found = ts_func
                break

        if ts_func_found:
            findings.append(StandardFinding(
                rule_name='crypto-predictable-seed',
                message=f'Predictable PRNG seed using {ts_func_found}',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{var} = {ts_func_found}()',
                cwe_id='CWE-335'  # Incorrect Usage of Seeds in PRNG
            ))

    # Also check seed() function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains 'seed' or 'srand'
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not ('seed' in callee_lower or 'srand' in callee_lower):
            continue

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

def _find_hardcoded_keys(cursor) -> list[StandardFinding]:
    """Find hardcoded encryption keys."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
          AND LENGTH(source_expr) > 10
        ORDER BY file, line
    """)

    key_keywords = ['key', 'secret', 'cipher_key', 'encryption_key', 'aes_key', 'des_key', 'private_key', 'priv_key']
    literal_starts = ['"', "'", 'b"', "b'"]
    secure_patterns = ['env', 'config', 'random', 'generate']

    for file, line, var, expr in cursor.fetchall():
        # Check if variable name contains key keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        var_lower = var.lower()
        if not any(kw in var_lower for kw in key_keywords):
            continue

        # Check if source looks like a string literal
        if not any(expr.startswith(ls) for ls in literal_starts):
            continue

        # Skip if source contains secure patterns
        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

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

def _find_weak_key_size(cursor) -> list[StandardFinding]:
    """Find usage of weak encryption key sizes."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    keygen_patterns = ['generate_key', 'keygen', 'new_key', 'random', 'key']

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains key generation patterns
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not any(pattern in callee_lower for pattern in keygen_patterns):
            continue

        # Extract numbers that might be key sizes
        # Split on common delimiters and check if each token is a digit
        numbers = []
        for token in args.replace(',', ' ').replace('(', ' ').replace(')', ' ').replace('=', ' ').split():
            if token.isdigit():
                numbers.append(token)

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

def _find_password_in_url(cursor) -> list[StandardFinding]:
    """Find passwords transmitted in URLs."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    url_functions = ['url', 'uri', 'query', 'params']
    sensitive_keywords = ['password', 'passwd', 'pwd', 'token', 'secret']

    for file, line, callee, args in cursor.fetchall():
        # Check if callee contains URL function patterns
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        callee_lower = callee.lower()
        if not any(uf in callee_lower for uf in url_functions):
            continue

        # Check if args contain sensitive keywords
        args_lower = args.lower()
        if not any(kw in args_lower for kw in sensitive_keywords):
            continue

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

def _find_timing_vulnerable_compare(cursor) -> list[StandardFinding]:
    """Find timing-vulnerable string comparisons for secrets."""
    findings = []

    # Fetch all symbols, filter in Python
    cursor.execute("""
        SELECT path, name, line, type
        FROM symbols
        WHERE name IS NOT NULL
          AND type = 'comparison'
        ORDER BY path, line
    """)

    sensitive_keywords = ['password', 'token', 'secret', 'key', 'hash', 'signature']

    for file, name, line, sym_type in cursor.fetchall():
        # Check if name contains sensitive keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        name_lower = name.lower()
        if not any(kw in name_lower for kw in sensitive_keywords):
            continue

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
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee, args in cursor.fetchall():
        # Check if args contain sensitive keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        args_lower = args.lower()
        if not any(kw in args_lower for kw in ['password', 'token', 'secret']):
            continue

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

def _find_deprecated_libraries(cursor) -> list[StandardFinding]:
    """Find usage of deprecated cryptography libraries."""
    findings = []

    deprecated_funcs = [
        ('pycrypto', 'pycrypto is unmaintained'),
        ('mcrypt', 'mcrypt is deprecated'),
        ('CryptoJS.enc.Base64', 'Base64 is encoding, not encryption'),
        ('md5_file', 'MD5 should not be used'),
        ('sha1_file', 'SHA1 is deprecated')
    ]

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, callee in cursor.fetchall():
        # Check if callee contains any deprecated function
        for deprecated, reason in deprecated_funcs:
            if deprecated in callee:
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
                break  # Only report once per callee

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
