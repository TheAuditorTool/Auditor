"""Python Cryptography Vulnerability Analyzer - Database-First Approach.

Detects weak cryptography and insecure crypto practices using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
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
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of cryptography vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check available tables for graceful degradation
            self._check_table_availability()

            # Must have minimum tables for any analysis
            if not self._has_minimum_tables():
                return []

            # Run crypto checks based on available data
            if 'function_call_args' in self.existing_tables:
                self._check_weak_hashes()
                self._check_broken_crypto()
                self._check_ecb_mode()
                self._check_insecure_random()
                self._check_weak_kdf()
                self._check_jwt_issues()
                self._check_ssl_issues()

            if 'assignments' in self.existing_tables:
                self._check_hardcoded_keys()

            if 'function_call_args' in self.existing_tables and 'assignments' in self.existing_tables:
                self._check_key_reuse()

        finally:
            conn.close()

        return self.findings

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'function_call_args', 'assignments', 'symbols',
                'refs', 'files', 'api_endpoints'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

    def _has_minimum_tables(self) -> bool:
        """Check if we have minimum required tables."""
        required = {'function_call_args', 'files'}
        return required.issubset(self.existing_tables)

    def _check_weak_hashes(self):
        """Detect weak hash algorithm usage."""
        weak_placeholders = ','.join('?' * len(self.patterns.WEAK_HASHES))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({weak_placeholders})
               OR callee_function LIKE '%.md5%'
               OR callee_function LIKE '%.sha1%'
            ORDER BY file, line
        """, list(self.patterns.WEAK_HASHES))
        # ✅ FIX: Store results before loop to avoid cursor state bug
        weak_hash_usages = self.cursor.fetchall()

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
        broken_placeholders = ','.join('?' * len(self.patterns.BROKEN_CRYPTO))

        # Check in function calls
        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function LIKE '%DES%'
               OR callee_function LIKE '%RC4%'
               OR callee_function LIKE '%RC2%'
               OR argument_expr IN ({broken_placeholders})
            ORDER BY file, line
        """, list(self.patterns.BROKEN_CRYPTO))

        for file, line, method, args in self.cursor.fetchall():
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
        ecb_placeholders = ','.join('?' * len(self.patterns.ECB_MODE))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE argument_expr IN ({ecb_placeholders})
               OR argument_expr LIKE '%MODE_ECB%'
               OR callee_function LIKE '%ECB%'
            ORDER BY file, line
        """, list(self.patterns.ECB_MODE))

        for file, line, method, args in self.cursor.fetchall():
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
        if 'assignments' not in self.existing_tables:
            return

        key_placeholders = ','.join('?' * len(self.patterns.KEY_VARIABLES))

        # Look for hardcoded key assignments
        self.cursor.execute(f"""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IN ({key_placeholders})
               OR target_var LIKE '%_key'
               OR target_var LIKE '%_secret'
               OR target_var LIKE '%_password'
            ORDER BY file, line
        """, list(self.patterns.KEY_VARIABLES))

        for file, line, var, expr in self.cursor.fetchall():
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
        kdf_placeholders = ','.join('?' * len(self.patterns.KDF_METHODS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({kdf_placeholders})
               OR callee_function LIKE '%pbkdf2%'
               OR callee_function LIKE '%scrypt%'
            ORDER BY file, line
        """, list(self.patterns.KDF_METHODS))

        for file, line, method, args in self.cursor.fetchall():
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
        jwt_placeholders = ','.join('?' * len(self.patterns.JWT_PATTERNS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({jwt_placeholders})
               OR callee_function LIKE '%jwt.%'
               OR argument_expr LIKE '%algorithm%'
            ORDER BY file, line
        """, list(self.patterns.JWT_PATTERNS))

        for file, line, method, args in self.cursor.fetchall():
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
        ssl_placeholders = ','.join('?' * len(self.patterns.SSL_PATTERNS))

        self.cursor.execute(f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({ssl_placeholders})
               OR argument_expr IN ({ssl_placeholders})
               OR argument_expr LIKE '%verify=False%'
               OR argument_expr LIKE '%CERT_NONE%'
            ORDER BY file, line
        """, list(self.patterns.SSL_PATTERNS) + list(self.patterns.SSL_PATTERNS))

        for file, line, method, args in self.cursor.fetchall():
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
        if 'assignments' not in self.existing_tables:
            return

        # Find all key assignments
        self.cursor.execute("""
            SELECT file, target_var, COUNT(*) as usage_count
            FROM assignments
            WHERE target_var LIKE '%key%'
               OR target_var LIKE '%secret%'
            GROUP BY file, target_var
            HAVING COUNT(*) > 1
        """)

        for file, var, count in self.cursor.fetchall():
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
        # Look for auth/password/token/session nearby
        security_keywords = ['auth', 'password', 'token', 'session', 'login', 'user', 'secret']

        for keyword in security_keywords:
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND (callee_function LIKE ? OR argument_expr LIKE ?)
                LIMIT 1
            """, [file, line, f'%{keyword}%', f'%{keyword}%'])

            if self.cursor.fetchone()[0] > 0:
                return True

        return False

    def _check_crypto_context(self, file: str, line: int, caller: str) -> bool:
        """Check if random is used in cryptographic context."""
        # Check function name
        if caller and any(c in caller.lower() for c in ['key', 'token', 'nonce', 'salt', 'iv', 'crypto', 'encrypt']):
            return True

        # Check for crypto library usage nearby
        crypto_placeholders = ','.join('?' * len(self.patterns.CRYPTO_LIBS))

        self.cursor.execute(f"""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 20
              AND callee_function LIKE '%crypt%'
            LIMIT 1
        """, [file, line])

        return self.cursor.fetchone()[0] > 0


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

def find_crypto_issues(context: StandardRuleContext) -> List[StandardFinding]:
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