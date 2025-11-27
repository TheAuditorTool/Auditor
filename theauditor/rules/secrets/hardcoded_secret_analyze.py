"""Hardcoded Secrets Analyzer - Hybrid Database/Pattern Approach.

This rule demonstrates a JUSTIFIED HYBRID approach because:
1. Entropy calculation is computational, not indexed
2. Base64 decoding and verification requires runtime processing
3. Pattern matching for secret formats needs regex evaluation
4. Sequential/keyboard pattern detection is algorithmic
5. Normalized assignment metadata distinguishes literal secrets from dynamic sources

Follows gold standard patterns (v1.1+ schema contract compliance):
- Frozensets for O(1) pattern matching
- Direct database queries (assumes all tables exist per schema contract)
- Proper Severity and Confidence enums
- Standardized finding generation with correct parameter names

False positive fixes (2025-11-22):
- Credit: Technique adapted from external contributor @dev-corelift (PR #20)
- Adds literal string extraction to avoid flagging dynamic values like request.headers.get()
- Properly handles f-strings, template literals, and function calls
"""

import base64
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

# Unsafe sinks where secrets should never be logged/exposed
UNSAFE_SINKS = frozenset([
    "console.log",
    "print",
    "logger.info",
    "logger.debug",
    "response.write",
    "res.send",
    "res.json",
])

METADATA = RuleMetadata(
    name="hardcoded_secrets",
    category="secrets",
    execution_scope="database",
    target_extensions=[
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".mjs",
        ".cjs",
        ".env",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".sh",
        ".bash",
        ".zsh",
    ],
    exclude_patterns=[
        "node_modules/",
        "venv/",
        ".venv/",
        "migrations/",
        "test/",
        "__tests__/",
        "tests/",
        ".env.example",
        ".env.template",
        "package-lock.json",
        "yarn.lock",
        "dist/",
        "build/",
        ".git/",
    ],
    requires_jsx_pass=False,
)


SECRET_KEYWORDS = frozenset(
    [
        "secret",
        "token",
        "password",
        "passwd",
        "pwd",
        "api_key",
        "apikey",
        "auth_token",
        "credential",
        "private_key",
        "privatekey",
        "access_token",
        "refresh_token",
        "client_secret",
        "client_id",
        "bearer",
        "oauth",
        "jwt",
        "aws_secret",
        "aws_access",
        "azure_key",
        "gcp_key",
        "stripe_key",
        "github_token",
        "gitlab_token",
        "encryption_key",
        "decrypt_key",
        "cipher_key",
        "session_key",
        "signing_key",
        "hmac_key",
    ]
)


WEAK_PASSWORDS = frozenset(
    [
        "password",
        "admin",
        "123456",
        "changeme",
        "default",
        "test",
        "demo",
        "sample",
        "example",
        "password123",
        "admin123",
        "root",
        "toor",
        "pass",
        "secret",
        "qwerty",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
    ]
)


PLACEHOLDER_VALUES = frozenset(
    [
        "placeholder",
        "changeme",
        "your_password_here",
        "YOUR_API_KEY",
        "API_KEY_HERE",
        "<password>",
        "${PASSWORD}",
        "{{PASSWORD}}",
        "xxx",
        "TODO",
        "FIXME",
        "CHANGE_ME",
        "INSERT_HERE",
        "dummy",
    ]
)


NON_SECRET_VALUES = frozenset(
    [
        "true",
        "false",
        "none",
        "null",
        "undefined",
        "development",
        "production",
        "test",
        "staging",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "example.com",
    ]
)


URL_PROTOCOLS = frozenset(
    ["http://", "https://", "ftp://", "sftp://", "ssh://", "git://", "file://", "data://"]
)


DB_PROTOCOLS = frozenset(
    [
        "mongodb://",
        "postgres://",
        "postgresql://",
        "mysql://",
        "redis://",
        "amqp://",
        "rabbitmq://",
        "cassandra://",
        "couchdb://",
        "elasticsearch://",
    ]
)


STRING_LITERAL_RE = re.compile(
    r'^(?P<prefix>[rubfRUBF]*)(?P<quote>"""|\'\'\'|"|\'|`)(?P<body>.*)(?P=quote)$', re.DOTALL
)


HIGH_CONFIDENCE_PATTERNS = frozenset(
    [
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r'(?i)aws_secret_access_key\s*=\s*["\']([^"\']+)["\']', "AWS Secret Key"),
        (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Key"),
        (r"sk_test_[a-zA-Z0-9]{24,}", "Stripe Test Key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Token"),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
        (r"glpat-[a-zA-Z0-9\-_]{20,}", "GitLab Token"),
        (r"xox[baprs]-[a-zA-Z0-9\-]+", "Slack Token"),
        (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private Key"),
        (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
        (r"ya29\.[0-9A-Za-z\-_]+", "Google OAuth Token"),
        (r"AAAA[A-Za-z0-9]{31}", "Dropbox Token"),
        (r"sq0csp-[0-9A-Za-z\-_]{43}", "Square Access Token"),
        (r"sqOatp-[0-9A-Za-z\-_]{22}", "Square OAuth Secret"),
    ]
)


GENERIC_SECRET_PATTERNS = frozenset(
    [
        r"^[a-fA-F0-9]{32,}$",
        r"^[A-Z0-9]{20,}$",
        r"^[a-zA-Z0-9]{40}$",
        r"^[A-Za-z0-9+/]{20,}={0,2}$",
        r"^[a-zA-Z0-9_\-]{32,}$",
    ]
)


SEQUENTIAL_PATTERNS = frozenset(
    [
        "abcdefghijklmnopqrstuvwxyz",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "0123456789",
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
    ]
)


KEYBOARD_PATTERNS = frozenset(
    ["qwerty", "asdfgh", "zxcvbn", "12345", "098765", "qazwsx", "qweasd", "qwertyuiop", "asdfghjkl"]
)


def find_hardcoded_secrets(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect hardcoded secrets using hybrid approach.

    Detects:
    - API keys and tokens in code
    - Hardcoded passwords
    - Private keys and certificates
    - AWS/Azure/GCP credentials
    - Database connection strings with passwords
    - Environment variable fallbacks

    This is a HYBRID rule that uses:
    - Database for finding string assignments
    - Pattern matching and entropy calculation (computational)

    Args:
        context: Standardized rule context with database path

    Returns:
        List of hardcoded secret findings
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_find_secret_assignments(cursor))
        findings.extend(_find_connection_strings(cursor))
        findings.extend(_find_env_fallbacks(cursor))
        findings.extend(_find_dict_secrets(cursor))
        findings.extend(_find_api_keys_in_urls(cursor))

        suspicious_files = _get_suspicious_files(cursor)

        for file_path in suspicious_files:
            try:
                full_path = context.project_path / file_path
                if full_path.exists() and full_path.is_relative_to(context.project_path):
                    pattern_findings = _scan_file_patterns(full_path, file_path)
                    findings.extend(pattern_findings)
            except (ValueError, OSError):
                continue

    finally:
        conn.close()

    return findings


def _extract_string_literal(expr: str) -> str | None:
    """Extract the inner value of a string literal expression.

    Supports Python prefixes (r/u/b/f) and JavaScript/TypeScript string forms.
    Returns None when the expression is not a static literal (e.g. function
    calls, template strings, or f-strings).

    Credit: @dev-corelift (PR #20) - Prevents flagging dynamic sources

    Examples:
        >>> _extract_string_literal('"hardcoded_secret"')
        'hardcoded_secret'
        >>> _extract_string_literal('request.headers.get("X-API-Key")')
        None  # Not a literal
        >>> _extract_string_literal('f"secret_{user_id}"')
        None  # F-string with interpolation
        >>> _extract_string_literal('`secret_${value}`')
        None  # Template literal with interpolation
    """
    if not expr:
        return None

    expr = expr.strip()
    match = STRING_LITERAL_RE.match(expr)
    if not match:
        return None

    prefix = match.group("prefix") or ""
    quote = match.group("quote")
    body = match.group("body")

    if any(ch.lower() == "f" for ch in prefix):
        return None

    if quote == "`" and "${" in body:
        return None

    return body


def _find_secret_assignments(cursor) -> list[StandardFinding]:
    """Find variable assignments that look like secrets."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
          AND LENGTH(source_expr) > 10
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    for file, line, var, value in cursor.fetchall():
        var_lower = var.lower()
        if not any(kw in var_lower for kw in SECRET_KEYWORDS):
            continue

        if (
            "process.env" in value
            or "import.meta.env" in value
            or "os.environ" in value
            or "getenv" in value
        ):
            continue

        literal_value = _extract_string_literal(value)
        if literal_value is None:
            continue

        clean_value = literal_value.strip()

        if var.lower() in ["password", "passwd", "pwd"] and clean_value.lower() in WEAK_PASSWORDS:
            findings.append(
                StandardFinding(
                    rule_name="secret-weak-password",
                    message=f'Weak/default password in variable "{var}"',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-521",
                )
            )

        elif _is_likely_secret(clean_value):
            var_lower = var.lower()
            if any(kw in var_lower for kw in ["password", "secret", "api_key", "private_key"]):
                confidence = Confidence.HIGH
            elif any(kw in var_lower for kw in SECRET_KEYWORDS):
                confidence = Confidence.MEDIUM
            else:
                confidence = Confidence.LOW

            findings.append(
                StandardFinding(
                    rule_name="secret-hardcoded-assignment",
                    message=f'Hardcoded secret in variable "{var}"',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=confidence,
                    cwe_id="CWE-798",
                )
            )

    return findings


def _find_connection_strings(cursor) -> list[StandardFinding]:
    """Find database connection strings with embedded passwords."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    for file, line, _var, conn_str in cursor.fetchall():
        has_protocol = any(proto in conn_str for proto in DB_PROTOCOLS)
        if not has_protocol:
            continue

        if "@" not in conn_str:
            continue

        if re.search(r"://[^:]+:[^@]+@", conn_str):
            match = re.search(r"://[^:]+:([^@]+)@", conn_str)
            if match:
                password = match.group(1)

                if password not in PLACEHOLDER_VALUES:
                    findings.append(
                        StandardFinding(
                            rule_name="secret-connection-string",
                            message="Database connection string with embedded password",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="security",
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-798",
                        )
                    )

    return findings


def _find_env_fallbacks(cursor) -> list[StandardFinding]:
    """Find environment variable fallbacks with hardcoded secrets."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    fallback_patterns = ["process.env", "os.environ.get", "getenv", "||", "??", " or "]
    secret_keywords_lower = ["secret", "key", "token", "password", "credential"]

    for file, line, var, expr in cursor.fetchall():
        var_lower = var.lower()
        if not any(kw in var_lower for kw in secret_keywords_lower):
            continue

        if not any(pattern in expr for pattern in fallback_patterns):
            continue

        fallback_match = (
            re.search(r'\|\|\s*["\']([^"\']+)["\']', expr)
            or re.search(r'\?\?\s*["\']([^"\']+)["\']', expr)
            or re.search(r',\s*["\']([^"\']+)["\']', expr)
            or re.search(r' or ["\']([^"\']+)["\']', expr)
        )

        if fallback_match:
            fallback = fallback_match.group(1)
            if fallback not in PLACEHOLDER_VALUES and _is_likely_secret(fallback):
                findings.append(
                    StandardFinding(
                        rule_name="secret-env-fallback",
                        message=f'Hardcoded secret as environment variable fallback in "{var}"',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-798",
                    )
                )

    return findings


def _find_dict_secrets(cursor) -> list[StandardFinding]:
    """Find secrets in dictionary/object literals."""
    findings = []

    cursor.execute("""
        SELECT file, line, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    for file, line, expr in cursor.fetchall():
        if "process.env" in expr or "os.environ" in expr:
            continue

        for keyword in SECRET_KEYWORDS:
            if f'"{keyword}":' not in expr and f"'{keyword}':" not in expr:
                continue

            pattern = rf'["\']?{keyword}["\']?\s*:\s*["\']([^"\']+)["\']'
            match = re.search(pattern, expr, re.IGNORECASE)

            if match:
                value = match.group(1)
                if value not in PLACEHOLDER_VALUES and _is_likely_secret(value):
                    findings.append(
                        StandardFinding(
                            rule_name="secret-dict-literal",
                            message=f'Hardcoded secret in dictionary key "{keyword}"',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="security",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-798",
                        )
                    )

    return findings


def _find_api_keys_in_urls(cursor) -> list[StandardFinding]:
    """Find API keys embedded in URLs."""
    findings = []

    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    http_functions = frozenset(["fetch", "axios", "request", "get", "post"])
    api_key_params = ["api_key=", "apikey=", "token=", "key=", "secret=", "password="]

    for file, line, func, args in cursor.fetchall():
        if func not in http_functions and not (func.endswith(".get") or func.endswith(".post")):
            continue

        if not any(param in args for param in api_key_params):
            continue

        key_match = re.search(
            r"(api_key|apikey|token|key|secret|password)=([^&\s]+)", args, re.IGNORECASE
        )
        if key_match:
            key_value = key_match.group(2)

            if (
                not key_value.startswith("${")
                and not key_value.startswith("process.")
                and key_value not in PLACEHOLDER_VALUES
            ) and len(key_value) > 10 and _is_likely_secret(key_value):
                findings.append(
                    StandardFinding(
                        rule_name="secret-api-key-in-url",
                        message="API key hardcoded in URL parameter",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="security",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-598",
                    )
                )

    return findings


def _get_suspicious_files(cursor) -> list[str]:
    """Get list of files likely to contain secrets."""
    suspicious_files = []

    cursor.execute("""
        SELECT path, name
        FROM symbols
        WHERE name IS NOT NULL
          AND path IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    secret_keywords_lower = ["secret", "token", "password", "api_key", "credential", "private_key"]

    file_secret_counts = {}
    for path, name in cursor.fetchall():
        name_lower = name.lower()
        if any(kw in name_lower for kw in secret_keywords_lower):
            file_secret_counts[path] = file_secret_counts.get(path, 0) + 1

    for path, count in file_secret_counts.items():
        if count > 3:
            suspicious_files.append(path)
            if len(suspicious_files) >= 50:
                break

    cursor.execute("""
        SELECT path
        FROM files
        WHERE path IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    config_patterns = ["config", "settings", "env.", ".env"]
    exclude_patterns = [".env.example", ".env.template"]

    for (path,) in cursor.fetchall():
        if not any(pattern in path for pattern in config_patterns):
            continue

        if any(pattern in path for pattern in exclude_patterns):
            continue

        suspicious_files.append(path)
        if len(suspicious_files) >= 70:
            break

    return list(set(suspicious_files))


def _is_likely_secret(value: str) -> bool:
    """Check if a string value is likely a secret.

    This function performs computational analysis that cannot be
    pre-indexed in the database (entropy calculation).
    """

    if len(value) < 16:
        return False

    if value.lower() in NON_SECRET_VALUES:
        return False

    if any(value.startswith(proto) for proto in URL_PROTOCOLS):
        return False

    if value.startswith(("/", "./", "../")):
        return False

    uuid_pattern = r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
    if re.match(uuid_pattern, value):
        return False

    entropy = _calculate_entropy(value)

    if _is_sequential(value) or _is_keyboard_walk(value):
        return False

    if entropy > 4.5:
        return True

    if entropy > 3.5:
        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_special = any(not c.isalnum() for c in value)

        if sum([has_upper, has_lower, has_digit, has_special]) >= 3:
            return True

    for pattern in GENERIC_SECRET_PATTERNS:
        if re.match(pattern, value):
            unique_chars = len(set(value))
            if unique_chars >= 5:
                return True

    return bool(_is_base64_secret(value))


def _calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string.

    This is a computational property that cannot be pre-indexed.
    """
    if not s:
        return 0.0

    freq = Counter(s)
    length = len(s)

    entropy = 0.0
    for count in freq.values():
        probability = count / length
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy


def _is_sequential(s: str) -> bool:
    """Check if string contains sequential characters."""
    s_lower = s.lower()

    for pattern in SEQUENTIAL_PATTERNS:
        for i in range(len(pattern) - 4):
            if pattern[i : i + 5] in s_lower and (len(s) <= 10 or pattern[i : i + 5] * 2 in s_lower):
                return True

    return False


def _is_keyboard_walk(s: str) -> bool:
    """Check if string is a keyboard walk pattern."""
    s_lower = s.lower()

    for pattern in KEYBOARD_PATTERNS:
        if pattern in s_lower and (len(s) <= 10 or s_lower.count(pattern) * len(pattern) > len(s) / 2):
            return True

    return False


def _is_base64_secret(value: str) -> bool:
    """Check if a Base64 string decodes to a secret.

    This requires runtime decoding and entropy calculation.
    """

    base64_pattern = r"^[A-Za-z0-9+/]{20,}={0,2}$"
    if not re.match(base64_pattern, value):
        return False

    try:
        decoded = base64.b64decode(value, validate=True)

        try:
            decoded_str = decoded.decode("utf-8", errors="ignore")
        except Exception:
            decoded_str = str(decoded)

        entropy = _calculate_entropy(decoded_str)

        return entropy > 4.0

    except Exception:
        return False


def _scan_file_patterns(file_path: Path, relative_path: str) -> list[StandardFinding]:
    """Scan file content for secret patterns.

    This is justified file I/O because:
    1. The database doesn't store full file content
    2. Pattern matching requires regex evaluation on actual content
    3. We only scan files identified as suspicious
    """
    findings = []

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        lines = lines[:5000]

        for i, line in enumerate(lines, 1):
            if line.strip().startswith(("#", "//", "/*", "*")):
                continue

            for pattern, description in HIGH_CONFIDENCE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    comment_pos = max(line.find("#"), line.find("//"))
                    if comment_pos == -1 or match.start() < comment_pos:
                        findings.append(
                            StandardFinding(
                                rule_name="secret-pattern-match",
                                message=f"{description} detected",
                                file_path=relative_path,
                                line=i,
                                severity=Severity.CRITICAL,
                                category="security",
                                confidence=Confidence.HIGH,
                                cwe_id="CWE-798",
                            )
                        )

            assignment_match = re.search(r'(\w+)\s*=\s*["\']([^"\']{20,})["\']', line)
            if assignment_match:
                var_name = assignment_match.group(1)
                value = assignment_match.group(2)

                if any(kw in var_name.lower() for kw in SECRET_KEYWORDS) and _is_likely_secret(value):
                    findings.append(
                        StandardFinding(
                            rule_name="secret-high-entropy",
                            message=f'High-entropy string in variable "{var_name}"',
                            file_path=relative_path,
                            line=i,
                            severity=Severity.HIGH,
                            category="security",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-798",
                        )
                    )

    except (OSError, UnicodeDecodeError):
        pass

    return findings


def register_taint_patterns(taint_registry):
    """Register secret-related taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """

    for keyword in SECRET_KEYWORDS:
        taint_registry.register_source(keyword, "secret", "all")

    for sink in UNSAFE_SINKS:
        taint_registry.register_sink(sink, "logging", "all")
