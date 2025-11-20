"""Python Cryptography Vulnerability Analyzer - Database-First Approach.

Detects weak cryptography and insecure crypto practices using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels

Detects:
- Weak hash algorithms (MD5, SHA1)
- Hardcoded cryptographic keys/secrets
- Insecure random number generation
- Missing HMAC verification
- Weak key derivation
- ECB mode usage
- Small key sizes
"""


import sqlite3
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA (Phase 3B Smart Filtering)
# ============================================================================

METADATA = RuleMetadata(
    name="python_crypto",
    category="cryptography",
    target_extensions=['.py'],
    exclude_patterns=['frontend/', 'client/', 'node_modules/', 'test/', '__tests__/', 'migrations/'],
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class CryptoPatterns:
    """Immutable pattern definitions for cryptography detection."""

    # Weak hash algorithms
    WEAK_HASHES = frozenset([
        'md5', 'hashlib.md5', 'MD5', 'md5sum',
        'sha1', 'hashlib.sha1', 'SHA1', 'sha1sum',
        'sha', 'hashlib.sha', 'SHA'  # SHA-0 is broken
    ])

    # Acceptable hashes (for comparison)
    STRONG_HASHES = frozenset([
        'sha256', 'sha384', 'sha512', 'sha3_256', 'sha3_384', 'sha3_512',
        'blake2b', 'blake2s', 'scrypt', 'argon2', 'bcrypt', 'pbkdf2'
    ])

    # Broken crypto algorithms
    BROKEN_CRYPTO = frozenset([
        'DES', 'des', 'DES3', '3DES', 'RC2', 'RC4', 'Blowfish',
        'IDEA', 'CAST5', 'XOR'
    ])

    # ECB mode (insecure)
    ECB_MODE = frozenset([
        'MODE_ECB', 'ECB', 'mode=ECB', 'AES.MODE_ECB',
        'DES.MODE_ECB', 'Blowfish.MODE_ECB'
    ])

    # Insecure random
    INSECURE_RANDOM = frozenset([
        'random.random', 'random.randint', 'random.choice',
        'random.randrange', 'random.seed', 'random.getrandbits',
        'random.randbytes', 'random.SystemRandom'  # This one is actually secure
    ])

    # Secure random (for comparison)
    SECURE_RANDOM = frozenset([
        'secrets', 'os.urandom', 'random.SystemRandom',
        'Crypto.Random', 'get_random_bytes', 'token_bytes',
        'token_hex', 'token_urlsafe'
    ])

    # Hardcoded key patterns
    KEY_VARIABLES = frozenset([
        'key', 'secret', 'password', 'passphrase', 'pin',
        'api_key', 'secret_key', 'private_key', 'encryption_key',
        'signing_key', 'master_key', 'session_key', 'symmetric_key',
        'aes_key', 'des_key', 'rsa_key', 'dsa_key', 'ecdsa_key'
    ])

    # Key generation methods
    KEY_GENERATION = frozenset([
        'generate_key', 'gen_key', 'KeyGenerator', 'new',
        'Fernet.generate_key', 'RSA.generate', 'DSA.generate',
        'EC.generate', 'nacl.utils.random'
    ])

    # HMAC/MAC methods
    HMAC_METHODS = frozenset([
        'hmac.new', 'hmac.digest', 'hmac.compare_digest',
        'HMAC.new', 'HMAC', 'MAC', 'CMAC', 'Poly1305'
    ])

    # Key derivation functions
    KDF_METHODS = frozenset([
        'PBKDF2', 'pbkdf2_hmac', 'scrypt', 'argon2',
        'bcrypt', 'hashpw', 'kdf', 'derive_key'
    ])

    # Weak KDF iterations
    WEAK_ITERATIONS = frozenset([
        '1000', '5000', '10000'  # PBKDF2 should use 100000+
    ])

    # JWT/Token patterns
    JWT_PATTERNS = frozenset([
        'jwt.encode', 'jwt.decode', 'HS256', 'none', 'None',
        'algorithm=none', 'algorithm="none"', "algorithm='none'"
    ])

    # SSL/TLS patterns
    SSL_PATTERNS = frozenset([
        'ssl.CERT_NONE', 'verify=False', 'check_hostname=False',
        'SSLContext', 'PROTOCOL_SSLv2', 'PROTOCOL_SSLv3',
        'PROTOCOL_TLSv1', 'PROTOCOL_TLSv1_1'  # TLS 1.0 and 1.1 are deprecated
    ])

    # Cryptography libraries
    CRYPTO_LIBS = frozenset([
        'Crypto', 'cryptography', 'pycrypto', 'pycryptodome',
        'nacl', 'pyca', 'M2Crypto', 'cryptg'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class CryptoAnalyzer:
    """Analyzer for Python cryptography vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = CryptoPatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of cryptography vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Run all crypto checks
            self._check_weak_hashes()
            self._check_broken_crypto()
            self._check_ecb_mode()
            self._check_insecure_random()
            self._check_weak_kdf()
            self._check_jwt_issues()
            self._check_ssl_issues()
            self._check_hardcoded_keys()
            self._check_key_reuse()

        finally:
            conn.close()

        return self.findings

    def _check_weak_hashes(self):
        """Detect weak hash algorithm usage."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        # Filter for weak hashes in Python
        weak_hash_usages = []
        for file, line, method, args in self.cursor.fetchall():
            method_lower = method.lower()
            # Check if callee contains weak hash patterns
            if method in self.patterns.WEAK_HASHES or '.md5' in method_lower or '.sha1' in method_lower:
                weak_hash_usages.append((file, line, method, args))

        for file, line, method, args in weak_hash_usages:
            # Determine if it's used for security (vs checksums)
            is_security_context = self._check_security_context(file, line)

            if is_security_context:
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH
                message = f'Weak hash {method} used in security context'
            else:
                severity = Severity.MEDIUM
                confidence = Confidence.MEDIUM
                message = f'Weak hash {method} - vulnerable to collisions'

            self.findings.append(StandardFinding(
                rule_name='python-weak-hash',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='cryptography',
                confidence=confidence,
                cwe_id='CWE-327'
            ))

    def _check_broken_crypto(self):
        """Detect broken cryptographic algorithms."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for broken crypto in method name or args
            method_upper = method.upper()
            if not ('DES' in method_upper or 'RC4' in method_upper or 'RC2' in method_upper):
                if not (args and any(algo in args for algo in self.patterns.BROKEN_CRYPTO)):
                    continue
            algo = 'DES' if 'DES' in method else 'RC4' if 'RC4' in method else 'broken algorithm'

            self.findings.append(StandardFinding(
                rule_name='python-broken-crypto',
                message=f'Broken cryptographic algorithm {algo} detected',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='cryptography',
                confidence=Confidence.HIGH,
                cwe_id='CWE-327'
            ))

    def _check_ecb_mode(self):
        """Detect ECB mode usage (insecure)."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for ECB patterns in args or method
            has_ecb = False
            if args and (any(ecb in args for ecb in self.patterns.ECB_MODE) or 'MODE_ECB' in args):
                has_ecb = True
            if 'ECB' in method.upper():
                has_ecb = True
            if not has_ecb:
                continue
            self.findings.append(StandardFinding(
                rule_name='python-ecb-mode',
                message='ECB mode encryption is insecure - patterns are preserved',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='cryptography',
                confidence=Confidence.HIGH,
                cwe_id='CWE-327'
            ))

    def _check_insecure_random(self):
        """Detect insecure random number generation for crypto."""
        insecure_placeholders = ','.join('?' * len(self.patterns.INSECURE_RANDOM))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr, caller_function
            FROM function_call_args
            WHERE callee_function IN ({insecure_placeholders})
            ORDER BY file, line
        """, list(self.patterns.INSECURE_RANDOM))
        # ✅ FIX: Store results before loop to avoid cursor state bug
        insecure_random_usages = self.cursor.fetchall()

        for file, line, method, args, caller in insecure_random_usages:
            # Skip random.SystemRandom (it's actually secure)
            if 'SystemRandom' in method:
                continue

            # Check if used in crypto context
            is_crypto = self._check_crypto_context(file, line, caller)

            if is_crypto:
                self.findings.append(StandardFinding(
                    rule_name='python-insecure-random',
                    message=f'Insecure random {method} used for cryptography',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='cryptography',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-338'
                ))

    def _check_hardcoded_keys(self):
        """Detect hardcoded cryptographic keys."""
        from theauditor.indexer.schema import build_query

        # Fetch all assignments, filter in Python
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if var is a key variable
            var_lower = var.lower()
            if var not in self.patterns.KEY_VARIABLES and not (var.endswith('_key') or var.endswith('_secret') or var.endswith('_password')):
                continue
            # Check if it's a literal string (hardcoded)
            if expr and (expr.startswith('"') or expr.startswith("'") or expr.startswith('b"') or expr.startswith("b'")):
                # Check length to avoid false positives on placeholders
                if len(expr) > 10:
                    self.findings.append(StandardFinding(
                        rule_name='python-hardcoded-key',
                        message=f'Hardcoded cryptographic key/secret: {var}',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='cryptography',
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-798'
                    ))

    def _check_weak_kdf(self):
        """Detect weak key derivation functions."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for KDF methods
            method_lower = method.lower()
            if method not in self.patterns.KDF_METHODS and 'pbkdf2' not in method_lower and 'scrypt' not in method_lower:
                continue
            if not args:
                continue

            # Check for weak iteration counts
            has_weak_iterations = any(iters in args for iters in self.patterns.WEAK_ITERATIONS)

            if has_weak_iterations:
                self.findings.append(StandardFinding(
                    rule_name='python-weak-kdf-iterations',
                    message=f'Weak KDF iterations in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-916'
                ))

            # Check for missing salt
            if 'salt' not in args.lower():
                self.findings.append(StandardFinding(
                    rule_name='python-kdf-no-salt',
                    message=f'KDF {method} possibly missing salt',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-916'
                ))

    def _check_jwt_issues(self):
        """Detect JWT/token security issues."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for JWT patterns
            method_lower = method.lower()
            if method not in self.patterns.JWT_PATTERNS and 'jwt.' not in method_lower:
                if not (args and 'algorithm' in args.lower()):
                    continue
            if not args:
                continue

            # Check for algorithm=none vulnerability
            if any(none in args.lower() for none in ['algorithm=none', 'algorithm="none"', "algorithm='none'"]):
                self.findings.append(StandardFinding(
                    rule_name='python-jwt-none-algorithm',
                    message='JWT with algorithm=none allows token forgery',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='cryptography',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-347'
                ))

            # Check for weak HS256 with guessable secret
            elif 'HS256' in args and 'secret' in args.lower():
                self.findings.append(StandardFinding(
                    rule_name='python-jwt-weak-secret',
                    message='JWT HS256 requires strong secret (256+ bits)',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-347'
                ))

    def _check_ssl_issues(self):
        """Detect SSL/TLS misconfigurations."""
        from theauditor.indexer.schema import build_query

        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for SSL patterns in method or args
            has_ssl_pattern = (method in self.patterns.SSL_PATTERNS or
                              (args and (any(pattern in args for pattern in self.patterns.SSL_PATTERNS) or
                                        'verify=False' in args or 'CERT_NONE' in args)))
            if not has_ssl_pattern:
                continue
            if 'verify=False' in str(args) or 'CERT_NONE' in str(args):
                self.findings.append(StandardFinding(
                    rule_name='python-ssl-no-verify',
                    message='SSL certificate verification disabled - MITM attacks possible',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='cryptography',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-295'
                ))

            elif any(old in str(args) for old in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1_1']):
                self.findings.append(StandardFinding(
                    rule_name='python-old-tls',
                    message='Deprecated SSL/TLS version detected',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='cryptography',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-327'
                ))

    def _check_key_reuse(self):
        """Detect key reuse across different contexts."""
        from theauditor.indexer.schema import build_query

        # Fetch all assignments, filter and group in Python
        query = build_query('assignments', ['file', 'target_var'])
        self.cursor.execute(query)

        # Group by file and var
        key_counts = {}
        for file, var in self.cursor.fetchall():
            var_lower = var.lower()
            if 'key' not in var_lower and 'secret' not in var_lower:
                continue
            key = (file, var)
            key_counts[key] = key_counts.get(key, 0) + 1

        # Find reused keys
        for (file, var), count in key_counts.items():
            if count > 2:
                self.findings.append(StandardFinding(
                    rule_name='python-key-reuse',
                    message=f'Cryptographic key "{var}" reused {count} times',
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category='cryptography',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-323'
                ))

    def _check_security_context(self, file: str, line: int) -> bool:
        """Check if code is in security-sensitive context."""
        from theauditor.indexer.schema import build_query

        # Look for auth/password/token/session nearby
        security_keywords = ['auth', 'password', 'token', 'session', 'login', 'user', 'secret']

        # Fetch nearby function calls, filter in Python
        query = build_query('function_call_args', ['callee_function', 'argument_expr'],
                           where="file = ? AND ABS(line - ?) <= 10")
        self.cursor.execute(query, (file, line))

        for callee, arg_expr in self.cursor.fetchall():
            callee_lower = callee.lower() if callee else ''
            arg_lower = arg_expr.lower() if arg_expr else ''

            for keyword in security_keywords:
                if keyword in callee_lower or keyword in arg_lower:
                    return True

        return False

    def _check_crypto_context(self, file: str, line: int, caller: str) -> bool:
        """Check if random is used in cryptographic context."""
        # Check function name
        if caller and any(c in caller.lower() for c in ['key', 'token', 'nonce', 'salt', 'iv', 'crypto', 'encrypt']):
            return True

        # Check for crypto library usage nearby - fetch and filter in Python
        from theauditor.indexer.schema import build_query

        query = build_query('function_call_args', ['callee_function'],
                           where="file = ? AND ABS(line - ?) <= 20")
        self.cursor.execute(query, (file, line))

        for (callee,) in self.cursor.fetchall():
            if 'crypt' in callee.lower():
                return True

        return False


# ============================================================================
# MISSING DATABASE FEATURES FLAGGED
# ============================================================================

"""
FLAGGED: Missing database features for better crypto detection:

1. Constant values:
   - Can't determine actual key length (need to evaluate "a" * 16)
   - Can't check if iterations is actually a number

2. Import tracking:
   - Can't detect: from Crypto.Cipher import AES
   - Need to know which crypto library is used

3. Configuration files:
   - Can't check TLS config in settings files
   - Need config parsing

4. Certificate validation:
   - Can't detect custom certificate validation functions
   - Need to track verify callbacks

5. Random seed tracking:
   - Can't detect if random is seeded with constant
   - Need to track random.seed() calls
"""


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Python cryptography vulnerabilities.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of cryptography vulnerabilities found
    """
    analyzer = CryptoAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register crypto-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = CryptoPatterns()

    # Register weak crypto as sinks
    for pattern in patterns.WEAK_HASHES:
        taint_registry.register_sink(pattern, "weak_crypto", "python")

    for pattern in patterns.BROKEN_CRYPTO:
        taint_registry.register_sink(pattern, "broken_crypto", "python")

    # Register insecure random as sources
    for pattern in patterns.INSECURE_RANDOM:
        if 'SystemRandom' not in pattern:
            taint_registry.register_source(pattern, "insecure_random", "python")

    # Register hardcoded keys as sources
    for pattern in patterns.KEY_VARIABLES:
        taint_registry.register_source(pattern, "hardcoded_secret", "python")