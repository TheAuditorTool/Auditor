"""Go Cryptography Misuse Analyzer - Database-First Approach."""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="go_crypto",
    category="crypto",
    target_extensions=[".go"],
    exclude_patterns=[
        "vendor/",
        "node_modules/",
        "testdata/",
        "_test.go",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class GoCryptoPatterns:
    """Immutable pattern definitions for Go crypto misuse detection."""

    # Insecure random sources
    INSECURE_RANDOM = frozenset([
        "math/rand",
    ])

    # Secure random (for comparison)
    SECURE_RANDOM = frozenset([
        "crypto/rand",
    ])

    # Weak hash algorithms
    WEAK_HASHES = frozenset([
        "crypto/md5",
        "crypto/sha1",
    ])

    # Strong hash algorithms (for comparison)
    STRONG_HASHES = frozenset([
        "crypto/sha256",
        "crypto/sha512",
        "golang.org/x/crypto/sha3",
        "golang.org/x/crypto/blake2b",
        "golang.org/x/crypto/argon2",
        "golang.org/x/crypto/bcrypt",
        "golang.org/x/crypto/scrypt",
    ])

    # Insecure TLS patterns
    INSECURE_TLS = frozenset([
        "InsecureSkipVerify",
        "MinVersion",
        "tls.VersionSSL30",
        "tls.VersionTLS10",
        "tls.VersionTLS11",
    ])

    # Hardcoded secret indicators
    SECRET_PATTERNS = frozenset([
        "password",
        "secret",
        "api_key",
        "apikey",
        "api-key",
        "token",
        "credential",
        "private_key",
        "privatekey",
        "auth",
    ])


class GoCryptoAnalyzer:
    """Analyzer for Go cryptography misuse."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.patterns = GoCryptoPatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        try:
            # Run crypto checks (tables guaranteed to exist by schema)
            self._check_insecure_random()
            self._check_weak_hashing()
            self._check_insecure_tls()
            self._check_hardcoded_secrets()

        finally:
            conn.close()

        return self.findings

    def _check_insecure_random(self):
        """Detect math/rand usage for security-sensitive operations."""
        # Find files that import math/rand
        self.cursor.execute("""
            SELECT DISTINCT file_path, line, path as import_path
            FROM go_imports
            WHERE path = 'math/rand'
        """)

        math_rand_files = {row["file_path"]: row["line"] for row in self.cursor.fetchall()}

        if not math_rand_files:
            return

        # Check if these files also have crypto-related code
        for file_path, import_line in math_rand_files.items():
            # Check for crypto-related imports or function names in same file
            self.cursor.execute("""
                SELECT path FROM go_imports
                WHERE file_path = ?
                  AND (path LIKE '%crypto%' OR path LIKE '%password%' OR path LIKE '%auth%')
            """, (file_path,))

            has_crypto = self.cursor.fetchone() is not None

            # Check for security-related function names
            self.cursor.execute("""
                SELECT name FROM go_functions
                WHERE file_path = ?
                  AND (LOWER(name) LIKE '%token%'
                       OR LOWER(name) LIKE '%secret%'
                       OR LOWER(name) LIKE '%password%'
                       OR LOWER(name) LIKE '%key%'
                       OR LOWER(name) LIKE '%auth%'
                       OR LOWER(name) LIKE '%session%')
            """, (file_path,))

            has_security_funcs = self.cursor.fetchone() is not None

            if has_crypto or has_security_funcs:
                self.findings.append(
                    StandardFinding(
                        rule_name="go-insecure-random",
                        message="math/rand used in file with crypto/security code - use crypto/rand",
                        file_path=file_path,
                        line=import_line,
                        severity=Severity.HIGH,
                        category="crypto",
                        confidence=Confidence.HIGH if has_crypto else Confidence.MEDIUM,
                        cwe_id="CWE-330",
                    )
                )

    def _check_weak_hashing(self):
        """Detect MD5/SHA1 usage for security purposes."""
        # Find files importing weak hash algorithms
        self.cursor.execute("""
            SELECT DISTINCT file_path, line, path as import_path
            FROM go_imports
            WHERE path IN ('crypto/md5', 'crypto/sha1')
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            import_line = row["line"]
            hash_type = "MD5" if "md5" in row["import_path"] else "SHA1"

            # Check context - is this for checksums or security?
            self.cursor.execute("""
                SELECT name FROM go_functions
                WHERE file_path = ?
                  AND (LOWER(name) LIKE '%password%'
                       OR LOWER(name) LIKE '%auth%'
                       OR LOWER(name) LIKE '%verify%'
                       OR LOWER(name) LIKE '%hash%'
                       OR LOWER(name) LIKE '%sign%')
            """, (file_path,))

            security_context = self.cursor.fetchone() is not None

            severity = Severity.HIGH if security_context else Severity.MEDIUM
            confidence = Confidence.HIGH if security_context else Confidence.LOW

            self.findings.append(
                StandardFinding(
                    rule_name=f"go-weak-hash-{hash_type.lower()}",
                    message=f"{hash_type} is cryptographically weak - use SHA-256 or better",
                    file_path=file_path,
                    line=import_line,
                    severity=severity,
                    category="crypto",
                    confidence=confidence,
                    cwe_id="CWE-328",
                )
            )

    def _check_insecure_tls(self):
        """Detect InsecureSkipVerify and weak TLS versions."""
        # Check for InsecureSkipVerify in struct fields or variables
        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%InsecureSkipVerify%true%'
               OR initial_value LIKE '%InsecureSkipVerify:%true%'
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-insecure-tls-skip-verify",
                    message="InsecureSkipVerify: true disables TLS certificate validation",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.CRITICAL,
                    category="crypto",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-295",
                )
            )

        # Check for weak TLS versions
        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%tls.VersionSSL30%'
               OR initial_value LIKE '%tls.VersionTLS10%'
               OR initial_value LIKE '%tls.VersionTLS11%'
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-weak-tls-version",
                    message="Weak TLS version configured - use TLS 1.2 or higher",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.HIGH,
                    category="crypto",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-326",
                )
            )

    def _check_hardcoded_secrets(self):
        """Detect hardcoded secrets in constants and variables."""
        # Check constants with suspicious names and string values
        self.cursor.execute("""
            SELECT file_path, line, name, value
            FROM go_constants
            WHERE value IS NOT NULL
              AND value != ''
              AND (LOWER(name) LIKE '%password%'
                   OR LOWER(name) LIKE '%secret%'
                   OR LOWER(name) LIKE '%api_key%'
                   OR LOWER(name) LIKE '%apikey%'
                   OR LOWER(name) LIKE '%token%'
                   OR LOWER(name) LIKE '%private%key%'
                   OR LOWER(name) LIKE '%credential%')
        """)

        for row in self.cursor.fetchall():
            value = row["value"] or ""
            # Skip empty or obviously placeholder values
            if len(value) < 5 or value in ('""', "''", '""', "nil"):
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="go-hardcoded-secret",
                    message=f"Potential hardcoded secret in constant '{row['name']}'",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.HIGH,
                    category="crypto",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-798",
                )
            )

        # Check package-level variables with suspicious names
        self.cursor.execute("""
            SELECT file_path, line, name, initial_value
            FROM go_variables
            WHERE is_package_level = 1
              AND initial_value IS NOT NULL
              AND initial_value != ''
              AND (LOWER(name) LIKE '%password%'
                   OR LOWER(name) LIKE '%secret%'
                   OR LOWER(name) LIKE '%api_key%'
                   OR LOWER(name) LIKE '%apikey%'
                   OR LOWER(name) LIKE '%token%'
                   OR LOWER(name) LIKE '%private%key%')
        """)

        for row in self.cursor.fetchall():
            value = row["initial_value"] or ""
            # Skip if it's reading from env
            if "os.Getenv" in value or "viper" in value.lower():
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="go-hardcoded-secret-var",
                    message=f"Potential hardcoded secret in package variable '{row['name']}'",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.HIGH,
                    category="crypto",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-798",
                )
            )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Go cryptography misuse."""
    analyzer = GoCryptoAnalyzer(context)
    return analyzer.analyze()
