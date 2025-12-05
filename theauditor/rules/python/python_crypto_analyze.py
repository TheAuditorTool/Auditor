"""Python Cryptography Vulnerability Analyzer - Detects weak crypto, hardcoded keys, and misconfigurations."""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="python_crypto",
    category="cryptography",
    target_extensions=[".py"],
    exclude_patterns=[
        "node_modules/",
        "vendor/",
        ".venv/",
        "__pycache__/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)

# Weak hash algorithms - collision attacks possible
WEAK_HASHES = frozenset([
    "md5",
    "hashlib.md5",
    "MD5",
    "md5sum",
    "sha1",
    "hashlib.sha1",
    "SHA1",
    "sha1sum",
    "sha",
    "hashlib.sha",
    "SHA",
])

# Broken cryptographic algorithms - should never be used
BROKEN_CRYPTO = frozenset([
    "DES",
    "des",
    "DES3",
    "3DES",
    "RC2",
    "RC4",
    "Blowfish",
    "IDEA",
    "CAST5",
    "XOR",
])

# ECB mode patterns - insecure, preserves patterns
ECB_MODE_PATTERNS = frozenset([
    "MODE_ECB",
    "ECB",
    "mode=ECB",
    "AES.MODE_ECB",
    "DES.MODE_ECB",
    "Blowfish.MODE_ECB",
])

# Insecure random for crypto (excludes SystemRandom which is secure)
INSECURE_RANDOM = frozenset([
    "random.random",
    "random.randint",
    "random.choice",
    "random.randrange",
    "random.seed",
    "random.getrandbits",
    "random.randbytes",
])

# Key/secret variable name patterns
KEY_VARIABLES = frozenset([
    "key",
    "secret",
    "password",
    "passphrase",
    "pin",
    "api_key",
    "secret_key",
    "private_key",
    "encryption_key",
    "signing_key",
    "master_key",
    "session_key",
    "symmetric_key",
    "aes_key",
    "des_key",
    "rsa_key",
    "dsa_key",
    "ecdsa_key",
])

# Key derivation functions
KDF_METHODS = frozenset([
    "PBKDF2",
    "pbkdf2_hmac",
    "scrypt",
    "argon2",
    "bcrypt",
    "hashpw",
    "kdf",
    "derive_key",
])

# Weak iteration counts for KDFs
WEAK_ITERATIONS = frozenset(["1000", "5000", "10000"])

# JWT patterns
JWT_PATTERNS = frozenset([
    "jwt.encode",
    "jwt.decode",
    "HS256",
    "none",
    "None",
    "algorithm=none",
    'algorithm="none"',
    "algorithm='none'",
])

# SSL/TLS vulnerability patterns
SSL_PATTERNS = frozenset([
    "ssl.CERT_NONE",
    "verify=False",
    "check_hostname=False",
    "SSLContext",
    "PROTOCOL_SSLv2",
    "PROTOCOL_SSLv3",
    "PROTOCOL_TLSv1",
    "PROTOCOL_TLSv1_1",
])

# Security context keywords
SECURITY_KEYWORDS = frozenset([
    "auth",
    "password",
    "token",
    "session",
    "login",
    "user",
    "secret",
])

# Crypto context keywords
CRYPTO_CONTEXT_KEYWORDS = frozenset([
    "key",
    "token",
    "nonce",
    "salt",
    "iv",
    "crypto",
    "encrypt",
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Python cryptography vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []
        seen: set[str] = set()

        def add_finding(
            file: str,
            line: int,
            rule_name: str,
            message: str,
            severity: Severity,
            confidence: Confidence = Confidence.HIGH,
            cwe_id: str | None = None,
        ) -> None:
            """Add a finding if not already seen."""
            key = f"{file}:{line}:{rule_name}"
            if key in seen:
                return
            seen.add(key)

            findings.append(
                StandardFinding(
                    rule_name=rule_name,
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category=METADATA.category,
                    confidence=confidence,
                    cwe_id=cwe_id,
                )
            )

        # Run all crypto checks
        _check_weak_hashes(db, add_finding)
        _check_broken_crypto(db, add_finding)
        _check_ecb_mode(db, add_finding)
        _check_insecure_random(db, add_finding)
        _check_weak_kdf(db, add_finding)
        _check_jwt_issues(db, add_finding)
        _check_ssl_issues(db, add_finding)
        _check_hardcoded_keys(db, add_finding)
        _check_key_reuse(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_weak_hashes(db: RuleDB, add_finding) -> None:
    """Detect weak hash algorithm usage (MD5, SHA1)."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method:
            continue

        method_lower = method.lower()

        is_weak = (
            method in WEAK_HASHES
            or ".md5" in method_lower
            or ".sha1" in method_lower
        )

        if not is_weak:
            continue

        # Check if used in security context (higher severity)
        is_security = _check_security_context(db, file, line)

        if is_security:
            add_finding(
                file=file,
                line=line,
                rule_name="python-weak-hash",
                message=f"Weak hash {method} used in security context",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-327",
            )
        else:
            add_finding(
                file=file,
                line=line,
                rule_name="python-weak-hash",
                message=f"Weak hash {method} - vulnerable to collisions",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-327",
            )


def _check_broken_crypto(db: RuleDB, add_finding) -> None:
    """Detect broken cryptographic algorithms (DES, RC4, etc.)."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method:
            continue

        method_upper = method.upper()

        # Check method name
        has_broken = "DES" in method_upper or "RC4" in method_upper or "RC2" in method_upper

        # Check args for broken algorithm names
        if not has_broken and args:
            has_broken = any(algo in str(args) for algo in BROKEN_CRYPTO)

        if not has_broken:
            continue

        # Determine which algorithm
        algo = "DES" if "DES" in method_upper else "RC4" if "RC4" in method_upper else "broken algorithm"

        add_finding(
            file=file,
            line=line,
            rule_name="python-broken-crypto",
            message=f"Broken cryptographic algorithm {algo} detected",
            severity=Severity.CRITICAL,
            confidence=Confidence.HIGH,
            cwe_id="CWE-327",
        )


def _check_ecb_mode(db: RuleDB, add_finding) -> None:
    """Detect ECB mode usage - insecure because patterns are preserved."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method:
            continue

        has_ecb = False

        # Check args for ECB patterns
        if args:
            has_ecb = any(ecb in str(args) for ecb in ECB_MODE_PATTERNS) or "MODE_ECB" in str(args)

        # Check method name
        if "ECB" in method.upper():
            has_ecb = True

        if has_ecb:
            add_finding(
                file=file,
                line=line,
                rule_name="python-ecb-mode",
                message="ECB mode encryption is insecure - patterns are preserved",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-327",
            )


def _check_insecure_random(db: RuleDB, add_finding) -> None:
    """Detect insecure random number generation for cryptographic purposes."""
    placeholders = ", ".join("?" for _ in INSECURE_RANDOM)
    sql, params = Q.raw(
        f"""
        SELECT file, line, callee_function, argument_expr, caller_function
        FROM function_call_args
        WHERE callee_function IN ({placeholders})
        ORDER BY file, line
        """,
        list(INSECURE_RANDOM),
    )

    for row in db.execute(sql, params):
        file, line, method, args, caller = row[0], row[1], row[2], row[3], row[4]

        # Check if used in cryptographic context
        is_crypto = _check_crypto_context(db, file, line, caller)

        if is_crypto:
            add_finding(
                file=file,
                line=line,
                rule_name="python-insecure-random",
                message=f"Insecure random {method} used for cryptography",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-338",
            )


def _check_weak_kdf(db: RuleDB, add_finding) -> None:
    """Detect weak key derivation functions - low iterations or missing salt."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method or not args:
            continue

        method_lower = method.lower()

        # Check if this is a KDF method
        is_kdf = (
            method in KDF_METHODS
            or "pbkdf2" in method_lower
            or "scrypt" in method_lower
        )

        if not is_kdf:
            continue

        args_str = str(args)

        # Check for weak iterations
        if any(iters in args_str for iters in WEAK_ITERATIONS):
            add_finding(
                file=file,
                line=line,
                rule_name="python-weak-kdf-iterations",
                message=f"Weak KDF iterations in {method}",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-916",
            )

        # Check for missing salt
        if "salt" not in args_str.lower():
            add_finding(
                file=file,
                line=line,
                rule_name="python-kdf-no-salt",
                message=f"KDF {method} possibly missing salt",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-916",
            )


def _check_jwt_issues(db: RuleDB, add_finding) -> None:
    """Detect JWT/token security issues - algorithm=none, weak secrets."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method or not args:
            continue

        method_lower = method.lower()

        # Check if JWT-related
        is_jwt = (
            method in JWT_PATTERNS
            or "jwt." in method_lower
            or "algorithm" in str(args).lower()
        )

        if not is_jwt:
            continue

        args_lower = str(args).lower()

        # Check for algorithm=none (allows token forgery)
        if any(none in args_lower for none in ["algorithm=none", 'algorithm="none"', "algorithm='none'"]):
            add_finding(
                file=file,
                line=line,
                rule_name="python-jwt-none-algorithm",
                message="JWT with algorithm=none allows token forgery",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-347",
            )
        # Check for weak HS256 secret
        elif "HS256" in str(args) and "secret" in args_lower:
            add_finding(
                file=file,
                line=line,
                rule_name="python-jwt-weak-secret",
                message="JWT HS256 requires strong secret (256+ bits)",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-347",
            )


def _check_ssl_issues(db: RuleDB, add_finding) -> None:
    """Detect SSL/TLS misconfigurations - disabled verification, old protocols."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, method, args = row[0], row[1], row[2], row[3]
        if not method:
            continue

        args_str = str(args) if args else ""

        # Check for SSL patterns
        has_ssl = method in SSL_PATTERNS or any(pattern in args_str for pattern in SSL_PATTERNS)

        if not has_ssl:
            continue

        # Check for disabled verification (MITM possible)
        if "verify=False" in args_str or "CERT_NONE" in args_str:
            add_finding(
                file=file,
                line=line,
                rule_name="python-ssl-no-verify",
                message="SSL certificate verification disabled - MITM attacks possible",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-295",
            )
        # Check for deprecated protocols
        elif any(old in args_str for old in ["SSLv2", "SSLv3", "TLSv1", "TLSv1_1"]):
            add_finding(
                file=file,
                line=line,
                rule_name="python-old-tls",
                message="Deprecated SSL/TLS version detected",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-327",
            )


def _check_hardcoded_keys(db: RuleDB, add_finding) -> None:
    """Detect hardcoded cryptographic keys and secrets."""
    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    for row in rows:
        file, line, var, expr = row[0], row[1], row[2], row[3]
        if not var or not expr:
            continue

        # Check if variable is a key/secret pattern
        is_key_var = (
            var in KEY_VARIABLES
            or var.endswith("_key")
            or var.endswith("_secret")
            or var.endswith("_password")
        )

        if not is_key_var:
            continue

        # Check if value is a hardcoded string literal (not a variable reference)
        expr_str = str(expr)
        is_hardcoded = (
            (expr_str.startswith('"') or expr_str.startswith("'") or
             expr_str.startswith('b"') or expr_str.startswith("b'"))
            and len(expr_str) > 10  # Longer than empty quotes
        )

        if is_hardcoded:
            add_finding(
                file=file,
                line=line,
                rule_name="python-hardcoded-key",
                message=f"Hardcoded cryptographic key/secret: {var}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-798",
            )


def _check_key_reuse(db: RuleDB, add_finding) -> None:
    """Detect key reuse across different contexts."""
    rows = db.query(
        Q("assignments")
        .select("file", "target_var")
    )

    key_counts: dict[tuple[str, str], int] = {}
    for row in rows:
        file, var = row[0], row[1]
        if not var:
            continue

        var_lower = var.lower()
        if "key" not in var_lower and "secret" not in var_lower:
            continue

        key = (file, var)
        key_counts[key] = key_counts.get(key, 0) + 1

    for (file, var), count in key_counts.items():
        if count > 2:
            add_finding(
                file=file,
                line=1,
                rule_name="python-key-reuse",
                message=f'Cryptographic key "{var}" reused {count} times',
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                cwe_id="CWE-323",
            )


def _check_security_context(db: RuleDB, file: str, line: int) -> bool:
    """Check if code is in security-sensitive context."""
    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "argument_expr")
        .where("file = ? AND line >= ? AND line <= ?", file, line - 10, line + 10)
    )

    for row in rows:
        callee, arg_expr = row[0], row[1]
        callee_lower = str(callee).lower() if callee else ""
        arg_lower = str(arg_expr).lower() if arg_expr else ""

        if any(keyword in callee_lower or keyword in arg_lower for keyword in SECURITY_KEYWORDS):
            return True

    return False


def _check_crypto_context(db: RuleDB, file: str, line: int, caller: str | None) -> bool:
    """Check if random is used in cryptographic context."""
    # Check caller function name
    if caller and any(kw in caller.lower() for kw in CRYPTO_CONTEXT_KEYWORDS):
        return True

    # Check nearby function calls for crypto patterns
    rows = db.query(
        Q("function_call_args")
        .select("callee_function")
        .where("file = ? AND line >= ? AND line <= ?", file, line - 20, line + 20)
    )

    return any("crypt" in str(row[0]).lower() for row in rows if row[0])
