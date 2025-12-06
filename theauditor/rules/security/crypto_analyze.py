"""Cryptography Security Analyzer - Fidelity-Compliant Implementation.

Detects cryptographic vulnerabilities:
- Weak random number generation
- Weak/broken hash algorithms
- Weak encryption algorithms
- Missing/static salt
- Weak KDF iterations
- ECB mode usage
- Missing/static IV
- Predictable seeds
- Hardcoded keys
- Weak key sizes
- Passwords in URLs
- Timing-vulnerable comparisons
- Deprecated crypto libraries
"""

import re

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
    name="crypto_security",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".php"],
    exclude_patterns=["test/", "spec.", "__tests__", "demo/"],
    execution_scope="database",
    primary_table="function_call_args",
)

WEAK_RANDOM_FUNCTIONS = frozenset(
    [
        "Math.random",
        "random.random",
        "random.randint",
        "random.choice",
        "random.randbytes",
        "random.randrange",
        "random.getrandbits",
        "random.uniform",
        "random.sample",
        "random.shuffle",
        "rand",
        "mt_rand",
        "lcg_value",
    ]
)

SECURE_RANDOM_FUNCTIONS = frozenset(
    [
        "secrets.token_hex",
        "secrets.token_bytes",
        "secrets.token_urlsafe",
        "secrets.randbits",
        "secrets.choice",
        "crypto.randomBytes",
        "crypto.getRandomValues",
        "crypto.randomFillSync",
        "crypto.randomUUID",
        "os.urandom",
        "SystemRandom",
    ]
)

WEAK_HASH_ALGORITHMS = frozenset(
    [
        "md5",
        "MD5",
        "sha1",
        "SHA1",
        "sha-1",
        "SHA-1",
        "md4",
        "MD4",
        "md2",
        "MD2",
        "sha0",
        "SHA0",
        "ripemd",
        "RIPEMD",
    ]
)

STRONG_HASH_ALGORITHMS = frozenset(
    [
        "sha256",
        "SHA256",
        "sha-256",
        "SHA-256",
        "sha384",
        "SHA384",
        "sha-384",
        "SHA-384",
        "sha512",
        "SHA512",
        "sha-512",
        "SHA-512",
        "sha3-256",
        "SHA3-256",
        "sha3-384",
        "SHA3-384",
        "sha3-512",
        "SHA3-512",
        "blake2b",
        "BLAKE2B",
        "blake2s",
        "BLAKE2S",
    ]
)

WEAK_ENCRYPTION_ALIASES = frozenset(
    [
        "des",
        "3des",
        "tripledes",
        "des-ede3",
        "des-ede",
        "des3",
        "rc4",
        "arcfour",
        "rc2",
        "blowfish",
        "cast",
        "cast5",
        "idea",
        "tea",
        "xtea",
    ]
)

STRONG_ENCRYPTION_ALGORITHMS = frozenset(
    [
        "aes",
        "AES",
        "aes-128-gcm",
        "AES-128-GCM",
        "aes-256-gcm",
        "AES-256-GCM",
        "chacha20",
        "ChaCha20",
        "chacha20-poly1305",
        "ChaCha20-Poly1305",
        "xchacha20",
        "XChaCha20",
    ]
)

INSECURE_MODES = frozenset(["ecb", "ECB", "cbc", "CBC"])

SECURE_MODES = frozenset(["gcm", "GCM", "ccm", "CCM", "eax", "EAX", "ocb", "OCB", "ctr", "CTR"])

SECURITY_KEYWORDS = frozenset(
    [
        "password",
        "passwd",
        "pwd",
        "secret",
        "key",
        "token",
        "auth",
        "authentication",
        "authorization",
        "session",
        "cookie",
        "jwt",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "bearer",
        "credential",
        "credentials",
        "salt",
        "nonce",
        "iv",
        "pin",
        "otp",
        "totp",
        "private",
        "priv",
        "encryption",
        "signature",
        "sign",
        "verify",
        "certificate",
        "cert",
    ]
)

NON_SECURITY_KEYWORDS = frozenset(
    [
        "checksum",
        "etag",
        "cache",
        "hash_table",
        "hashmap",
        "hashtable",
        "test",
        "mock",
        "example",
        "demo",
        "sample",
        "placeholder",
        "file",
        "content",
        "data",
        "index",
        "offset",
        "length",
    ]
)

DEPRECATED_LIBRARIES = frozenset(
    ["pycrypto", "mcrypt", "openssl_encrypt", "openssl_decrypt", "CryptoJS.enc.Base64"]
)

TIMING_VULNERABLE_COMPARISONS = frozenset(
    ["==", "===", "strcmp", "strcasecmp", ".equals", ".compare"]
)

CONSTANT_TIME_COMPARISONS = frozenset(
    [
        "hmac.compare_digest",
        "secrets.compare_digest",
        "crypto.timingSafeEqual",
        "hash_equals",
        "MessageDigest.isEqual",
    ]
)

_CAMEL_CASE_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+")


def _split_identifier_tokens(value: str | None) -> list[str]:
    """Split identifiers into normalized, lowercase tokens."""
    if not value:
        return []
    tokens: list[str] = []
    for chunk in re.split(r"[^0-9A-Za-z]+", value):
        if not chunk:
            continue
        tokens.extend(_CAMEL_CASE_TOKEN_RE.findall(chunk))
    return [token.lower() for token in tokens if token]


def _contains_alias(text: str | None, alias: str) -> bool:
    """Check if the identifier or argument contains a crypto alias token."""
    if not text:
        return False
    text_tokens = set(_split_identifier_tokens(text))
    if not text_tokens:
        return False
    alias_tokens = _split_identifier_tokens(alias)
    if not alias_tokens:
        return False
    if len(alias_tokens) == 1:
        return alias_tokens[0] in text_tokens
    return all(token in text_tokens for token in alias_tokens)


def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file (lower priority)."""
    test_indicators = ["test", "spec", "mock", "fixture", "__tests__", "tests"]
    file_lower = file_path.lower()
    return any(indicator in file_lower for indicator in test_indicators)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect cryptographic vulnerabilities using schema contract patterns.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_find_weak_random_generation(db))
        findings.extend(_find_weak_hash_algorithms(db))
        findings.extend(_find_weak_encryption_algorithms(db))
        findings.extend(_find_missing_salt(db))
        findings.extend(_find_static_salt(db))
        findings.extend(_find_weak_kdf_iterations(db))
        findings.extend(_find_ecb_mode(db))
        findings.extend(_find_missing_iv(db))
        findings.extend(_find_static_iv(db))
        findings.extend(_find_predictable_seeds(db))
        findings.extend(_find_hardcoded_keys(db))
        findings.extend(_find_weak_key_size(db))
        findings.extend(_find_password_in_url(db))
        findings.extend(_find_timing_vulnerable_compare(db))
        findings.extend(_find_deprecated_libraries(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _determine_confidence(db: RuleDB, file: str, line: int, func_name: str) -> Confidence:
    """Determine confidence level based on context analysis."""
    if func_name and any(kw in func_name.lower() for kw in SECURITY_KEYWORDS):
        return Confidence.HIGH

    if func_name and any(kw in func_name.lower() for kw in NON_SECURITY_KEYWORDS):
        return Confidence.LOW

    rows = db.query(
        Q("function_call_args")
        .select("callee_function", "line")
        .where("file = ?", file)
        .where("callee_function IS NOT NULL")
    )

    security_operations = ["encrypt", "decrypt", "hash", "sign", "verify"]
    for callee, func_line in rows:
        if abs(func_line - line) <= 5:
            callee_lower = callee.lower()
            if any(op in callee_lower for op in security_operations):
                return Confidence.HIGH

    var_rows = db.query(
        Q("assignments")
        .select("target_var")
        .where("file = ?", file)
        .where("target_var IS NOT NULL")
    )

    for (var_name,) in var_rows:
        var_lower = var_name.lower() if var_name else ""
        if any(kw in var_lower for kw in SECURITY_KEYWORDS):
            return Confidence.MEDIUM

    return Confidence.MEDIUM


def _find_weak_random_generation(db: RuleDB) -> list[StandardFinding]:
    """Find usage of weak random number generators for security purposes."""
    findings: list[StandardFinding] = []

    funcs_list = list(WEAK_RANDOM_FUNCTIONS)
    placeholders = ",".join(["?"] * len(funcs_list))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *funcs_list)
        .order_by("file, line")
    )

    for file, line, callee, caller, args in rows:
        confidence = _determine_confidence(db, file, line, caller)

        if confidence == Confidence.LOW and _is_test_file(file):
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-insecure-random",
                message=f"Insecure random function {callee} used",
                file_path=file,
                line=line,
                severity=Severity.HIGH if confidence == Confidence.HIGH else Severity.MEDIUM,
                confidence=confidence,
                category="security",
                snippet=f"{callee}({args[:50] if args else ''}...)",
                cwe_id="CWE-330",
            )
        )

    return findings


def _find_weak_hash_algorithms(db: RuleDB) -> list[StandardFinding]:
    """Find usage of weak/broken hash algorithms."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "caller_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, caller, args in rows:
        callee_str = callee if callee else ""
        args_str = args if args else ""
        combined = f"{callee_str} {args_str}".lower()

        weak_algo = None
        for algo in WEAK_HASH_ALGORITHMS:
            if algo.lower() in combined:
                weak_algo = algo
                break

        if not weak_algo:
            continue

        confidence = _determine_confidence(db, file, line, caller)
        if confidence == Confidence.LOW:
            continue

        algo_upper = weak_algo.upper().replace("-", "")

        findings.append(
            StandardFinding(
                rule_name="crypto-weak-hash",
                message=f"Weak hash algorithm {algo_upper} detected",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=confidence,
                category="security",
                snippet=f"{callee}(...{weak_algo}...)",
                cwe_id="CWE-327",
            )
        )

    return findings


def _find_weak_encryption_algorithms(db: RuleDB) -> list[StandardFinding]:
    """Find usage of weak/broken encryption algorithms."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    seen: set[tuple[str, int, str]] = set()

    for file, line, callee, argument in rows:
        callee_lower = (callee or "").lower()
        argument_lower = (argument or "").lower()

        matched_algos: set[str] = set()
        for alias in WEAK_ENCRYPTION_ALIASES:
            if _contains_alias(callee_lower, alias) or _contains_alias(argument_lower, alias):
                matched_algos.add(alias)

        if not matched_algos:
            continue

        algo_names = sorted({alias.upper() for alias in matched_algos})
        signature_key = (file, line, callee or "|".join(algo_names))

        if signature_key in seen:
            continue
        seen.add(signature_key)

        algo_label = ", ".join(algo_names)
        snippet_source = callee or argument or ""

        findings.append(
            StandardFinding(
                rule_name="crypto-weak-encryption",
                message=f"Weak encryption algorithm {algo_label} detected",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                confidence=Confidence.MEDIUM,
                category="security",
                snippet=snippet_source[:120],
                cwe_id="CWE-327",
            )
        )

    return findings


def _find_missing_salt(db: RuleDB) -> list[StandardFinding]:
    """Find password hashing without salt."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    hash_functions = ["hash", "digest", "bcrypt", "scrypt", "pbkdf2"]
    password_keywords = ["password", "passwd", "pwd"]

    for file, line, callee, args in rows:
        callee_lower = callee.lower()
        if not any(hf in callee_lower for hf in hash_functions):
            continue

        args_lower = args.lower()
        if not any(pw in args_lower for pw in password_keywords):
            continue

        assign_rows = db.query(
            Q("assignments")
            .select("target_var", "source_expr", "line")
            .where("file = ?", file)
            .where("target_var IS NOT NULL")
        )

        has_salt_nearby = False
        for var, expr, assign_line in assign_rows:
            if abs(assign_line - line) <= 10 and (
                "salt" in (var or "").lower() or "salt" in (expr or "").lower()
            ):
                has_salt_nearby = True
                break

        has_salt_in_args = "salt" in args.lower() if args else False

        if not has_salt_nearby and not has_salt_in_args:
            findings.append(
                StandardFinding(
                    rule_name="crypto-missing-salt",
                    message="Password hashing without salt detected",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category="security",
                    snippet=f"{callee}(password, ...)",
                    cwe_id="CWE-759",
                )
            )

    return findings


def _find_static_salt(db: RuleDB) -> list[StandardFinding]:
    """Find hardcoded salt values."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    secure_patterns = ["random", "generate", "uuid", "secrets", "urandom"]

    for file, line, var, expr in rows:
        if "salt" not in var.lower():
            continue

        if not (expr.startswith('"') or expr.startswith("'")):
            continue

        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

        if "(" not in expr and not expr.startswith("os."):
            findings.append(
                StandardFinding(
                    rule_name="crypto-static-salt",
                    message=f"Hardcoded salt value in {var}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet=f'{var} = "..."',
                    cwe_id="CWE-760",
                )
            )

    return findings


def _find_weak_kdf_iterations(db: RuleDB) -> list[StandardFinding]:
    """Find weak key derivation functions with low iterations."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    kdf_functions = ["pbkdf2", "scrypt", "bcrypt"]

    for file, line, callee, args in rows:
        callee_lower = callee.lower()
        if not any(kdf in callee_lower for kdf in kdf_functions):
            continue

        if not args:
            continue

        numbers = []
        for token in (
            args.replace(",", " ").replace("(", " ").replace(")", " ").replace("=", " ").split()
        ):
            if token.isdigit():
                numbers.append(token)

        for num_str in numbers:
            num = int(num_str)
            if 100 < num < 100000:
                findings.append(
                    StandardFinding(
                        rule_name="crypto-weak-kdf-iterations",
                        message=f"Weak KDF iteration count: {num}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{callee}(...iterations={num}...)",
                        cwe_id="CWE-916",
                    )
                )
                break

    return findings


def _find_ecb_mode(db: RuleDB) -> list[StandardFinding]:
    """Find usage of ECB mode in encryption."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    crypto_functions = ["cipher", "encrypt", "decrypt", "AES", "DES"]

    for file, line, callee, args in rows:
        args_lower = args.lower()
        if "ecb" not in args_lower:
            continue

        callee_str = callee if callee else ""
        if not any(cf in callee_str for cf in crypto_functions):
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-ecb-mode",
                message="ECB mode encryption is insecure (reveals patterns)",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category="security",
                snippet=f"{callee}(...ECB...)",
                cwe_id="CWE-327",
            )
        )

    assign_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, expr in assign_rows:
        if "mode" not in var.lower():
            continue
        if "ecb" not in expr.lower():
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-ecb-mode-config",
                message=f"ECB mode configured in {var}",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category="security",
                snippet=f'{var} = "ECB"',
                cwe_id="CWE-327",
            )
        )

    return findings


def _find_missing_iv(db: RuleDB) -> list[StandardFinding]:
    """Find encryption operations without initialization vector."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, args in rows:
        callee_lower = callee.lower()
        if not ("encrypt" in callee_lower or "cipher" in callee_lower):
            continue
        if "decrypt" in callee_lower:
            continue

        has_iv_in_args = False
        if args:
            args_lower = args.lower()
            has_iv_in_args = any(term in args_lower for term in ["iv", "nonce", "initialization"])

        if not has_iv_in_args:
            assign_rows = db.query(
                Q("assignments")
                .select("target_var", "source_expr", "line")
                .where("file = ?", file)
                .where("target_var IS NOT NULL")
            )

            has_iv_nearby = False
            for var, expr, assign_line in assign_rows:
                if abs(assign_line - line) <= 10:
                    var_lower = (var or "").lower()
                    expr_lower = (expr or "").lower()
                    if "iv" in var_lower or "nonce" in var_lower or "random" in expr_lower:
                        has_iv_nearby = True
                        break

            if not has_iv_nearby:
                findings.append(
                    StandardFinding(
                        rule_name="crypto-missing-iv",
                        message="Encryption without initialization vector",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{callee}(...)",
                        cwe_id="CWE-329",
                    )
                )

    return findings


def _find_static_iv(db: RuleDB) -> list[StandardFinding]:
    """Find hardcoded initialization vectors."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    iv_keywords = ["iv", "nonce", "initialization_vector"]
    literal_starts = ['"', "'", "[0,", "bytes("]
    secure_patterns = ["random", "generate", "urandom"]

    for file, line, var, expr in rows:
        var_lower = var.lower()
        if not any(kw in var_lower for kw in iv_keywords):
            continue

        if not any(expr.startswith(ls) for ls in literal_starts):
            continue

        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

        if "(" not in expr or "bytes([0" in expr or 'b"\\x00' in expr:
            findings.append(
                StandardFinding(
                    rule_name="crypto-static-iv",
                    message=f"Hardcoded initialization vector in {var}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet=f"{var} = {expr[:50]}",
                    cwe_id="CWE-329",
                )
            )

    return findings


def _find_predictable_seeds(db: RuleDB) -> list[StandardFinding]:
    """Find predictable seeds for random number generators."""
    findings: list[StandardFinding] = []

    timestamp_functions = [
        "time.time",
        "datetime.now",
        "Date.now",
        "Date.getTime",
        "timestamp",
        "time()",
        "microtime",
        "performance.now",
    ]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    seed_keywords = ["seed", "random"]

    for file, line, var, expr in rows:
        var_lower = var.lower()
        if not any(kw in var_lower for kw in seed_keywords):
            continue

        ts_func_found = None
        for ts_func in timestamp_functions:
            if ts_func in expr:
                ts_func_found = ts_func
                break

        if ts_func_found:
            findings.append(
                StandardFinding(
                    rule_name="crypto-predictable-seed",
                    message=f"Predictable PRNG seed using {ts_func_found}",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet=f"{var} = {ts_func_found}()",
                    cwe_id="CWE-335",
                )
            )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, args in func_rows:
        callee_lower = callee.lower()
        if not ("seed" in callee_lower or "srand" in callee_lower):
            continue

        if any(ts in args.lower() for ts in ["time", "date", "timestamp"]):
            findings.append(
                StandardFinding(
                    rule_name="crypto-predictable-seed-func",
                    message="PRNG seeded with predictable value",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet=f"{callee}({args[:50]})",
                    cwe_id="CWE-335",
                )
            )

    return findings


def _find_hardcoded_keys(db: RuleDB) -> list[StandardFinding]:
    """Find hardcoded encryption keys."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .where("LENGTH(source_expr) > 10")
        .order_by("file, line")
    )

    key_keywords = [
        "key",
        "secret",
        "cipher_key",
        "encryption_key",
        "aes_key",
        "des_key",
        "private_key",
        "priv_key",
    ]
    literal_starts = ['"', "'", 'b"', "b'"]
    secure_patterns = ["env", "config", "random", "generate"]

    for file, line, var, expr in rows:
        var_lower = var.lower()
        if not any(kw in var_lower for kw in key_keywords):
            continue

        if not any(expr.startswith(ls) for ls in literal_starts):
            continue

        expr_lower = expr.lower()
        if any(pattern in expr_lower for pattern in secure_patterns):
            continue

        if "os.environ" in expr or "process.env" in expr:
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-hardcoded-key",
                message=f"Hardcoded encryption key in {var}",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                category="security",
                snippet=f'{var} = "***REDACTED***"',
                cwe_id="CWE-798",
            )
        )

    return findings


def _find_weak_key_size(db: RuleDB) -> list[StandardFinding]:
    """Find usage of weak encryption key sizes."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    keygen_patterns = ["generate_key", "keygen", "new_key", "random", "key"]

    for file, line, callee, args in rows:
        callee_lower = callee.lower()
        if not any(pattern in callee_lower for pattern in keygen_patterns):
            continue

        numbers = []
        for token in (
            args.replace(",", " ").replace("(", " ").replace(")", " ").replace("=", " ").split()
        ):
            if token.isdigit():
                numbers.append(token)

        for num_str in numbers:
            num = int(num_str)
            if num in [40, 56, 64, 80]:
                findings.append(
                    StandardFinding(
                        rule_name="crypto-weak-key-size",
                        message=f"Weak key size: {num} bits",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{callee}({num})",
                        cwe_id="CWE-326",
                    )
                )
            elif num in [5, 7, 8, 10]:
                findings.append(
                    StandardFinding(
                        rule_name="crypto-weak-key-size-bytes",
                        message=f"Weak key size: {num} bytes ({num * 8} bits)",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{callee}({num})",
                        cwe_id="CWE-326",
                    )
                )

    return findings


def _find_password_in_url(db: RuleDB) -> list[StandardFinding]:
    """Find passwords transmitted in URLs."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    url_functions = ["url", "uri", "query", "params"]
    sensitive_keywords = ["password", "passwd", "pwd", "token", "secret"]

    for file, line, callee, args in rows:
        callee_lower = callee.lower()
        if not any(uf in callee_lower for uf in url_functions):
            continue

        args_lower = args.lower()
        if not any(kw in args_lower for kw in sensitive_keywords):
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-password-in-url",
                message="Sensitive data in URL parameters",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category="security",
                snippet=f"{callee}(...password...)",
                cwe_id="CWE-598",
            )
        )

    return findings


def _find_timing_vulnerable_compare(db: RuleDB) -> list[StandardFinding]:
    """Find timing-vulnerable string comparisons for secrets."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("symbols")
        .select("path", "name", "line", "type")
        .where("name IS NOT NULL")
        .where("type = ?", "comparison")
        .order_by("path, line")
    )

    sensitive_keywords = ["password", "token", "secret", "key", "hash", "signature"]

    for file, name, line, _sym_type in rows:
        name_lower = name.lower()
        if not any(kw in name_lower for kw in sensitive_keywords):
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-timing-vulnerable",
                message=f"Timing-vulnerable comparison of {name}",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                category="security",
                snippet=f"{name} == ...",
                cwe_id="CWE-208",
            )
        )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN ('strcmp', 'strcasecmp', 'memcmp')")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, args in func_rows:
        args_lower = args.lower()
        if not any(kw in args_lower for kw in ["password", "token", "secret"]):
            continue

        findings.append(
            StandardFinding(
                rule_name="crypto-timing-strcmp",
                message=f"Timing-vulnerable {callee} for secrets",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category="security",
                snippet=f"{callee}(secret, ...)",
                cwe_id="CWE-208",
            )
        )

    return findings


def _find_deprecated_libraries(db: RuleDB) -> list[StandardFinding]:
    """Find usage of deprecated cryptography libraries."""
    findings: list[StandardFinding] = []

    deprecated_funcs = [
        ("pycrypto", "pycrypto is unmaintained"),
        ("mcrypt", "mcrypt is deprecated"),
        ("CryptoJS.enc.Base64", "Base64 is encoding, not encryption"),
        ("md5_file", "MD5 should not be used"),
        ("sha1_file", "SHA1 is deprecated"),
    ]

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee in rows:
        for deprecated, reason in deprecated_funcs:
            if deprecated in callee:
                findings.append(
                    StandardFinding(
                        rule_name="crypto-deprecated-library",
                        message=f"{reason}: {deprecated}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=callee,
                        cwe_id="CWE-327",
                    )
                )
                break

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register crypto-specific patterns with taint analyzer."""
    for func in WEAK_RANDOM_FUNCTIONS:
        taint_registry.register_source(func, "weak_random", "any")

    crypto_sinks = [
        "encrypt",
        "decrypt",
        "sign",
        "verify",
        "generateKey",
        "deriveKey",
        "hash",
        "digest",
    ]
    for sink in crypto_sinks:
        taint_registry.register_sink(sink, "crypto_operation", "any")
