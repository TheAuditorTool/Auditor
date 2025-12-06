"""Hardcoded Secrets Analyzer - Hybrid Database/Pattern Approach.

Detects hardcoded secrets including:
- API keys, tokens, passwords in variable assignments
- Database connection strings with embedded credentials
- Environment variable fallbacks with hardcoded secrets
- High-entropy strings in secret-named variables
- Known secret patterns (AWS, Stripe, GitHub, etc.)

CWE-798: Use of Hard-coded Credentials
CWE-521: Weak Password Requirements
CWE-598: Use of GET Request Method With Sensitive Query Strings
"""

import base64
import math
import re
from collections import Counter
from pathlib import Path

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
    name="hardcoded_secrets",
    category="secrets",
    execution_scope="database",
    primary_table="assignments",
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
    [
        "http://",
        "https://",
        "ftp://",
        "sftp://",
        "ssh://",
        "git://",
        "file://",
        "data://",
    ]
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
    r'^(?P<prefix>[rubfRUBF]*)(?P<quote>"""|\'\'\'|"|\'|`)(?P<body>.*)(?P=quote)$',
    re.DOTALL,
)

HIGH_CONFIDENCE_PATTERNS = (
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r'(?i)aws_secret_access_key\s*=\s*["\']([^"\']+)["\']', "AWS Secret Key"),
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Key"),
    (r"sk_test_[a-zA-Z0-9]{24,}", "Stripe Test Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub Server Token"),
    (r"ghr_[a-zA-Z0-9]{36}", "GitHub Refresh Token"),
    (r"glpat-[a-zA-Z0-9\-_]{20,}", "GitLab Token"),
    (r"xox[baprs]-[a-zA-Z0-9\-]+", "Slack Token"),
    (r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "Private Key"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"ya29\.[0-9A-Za-z\-_]+", "Google OAuth Token"),
    (r"AAAA[A-Za-z0-9]{31}", "Dropbox Token"),
    (r"sq0csp-[0-9A-Za-z\-_]{43}", "Square Access Token"),
    (r"sqOatp-[0-9A-Za-z\-_]{22}", "Square OAuth Secret"),
    (r"npm_[a-zA-Z0-9]{36}", "NPM Token"),
    (r"pypi-[a-zA-Z0-9]{36,}", "PyPI Token"),
    (r"SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}", "SendGrid API Key"),
    (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
)

GENERIC_SECRET_PATTERNS = (
    r"^[a-fA-F0-9]{32,}$",
    r"^[A-Z0-9]{20,}$",
    r"^[a-zA-Z0-9]{40}$",
    r"^[A-Za-z0-9+/]{20,}={0,2}$",
    r"^[a-zA-Z0-9_\-]{32,}$",
)

SEQUENTIAL_PATTERNS = (
    "abcdefghijklmnopqrstuvwxyz",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)

KEYBOARD_PATTERNS = frozenset(
    [
        "qwerty",
        "asdfgh",
        "zxcvbn",
        "12345",
        "098765",
        "qazwsx",
        "qweasd",
        "qwertyuiop",
        "asdfghjkl",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect hardcoded secrets using hybrid database/pattern approach.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_find_secret_assignments(db))
        findings.extend(_find_connection_strings(db))
        findings.extend(_find_env_fallbacks(db))
        findings.extend(_find_dict_secrets(db))
        findings.extend(_find_api_keys_in_urls(db))

        suspicious_files = _get_suspicious_files(db)

        for file_path in suspicious_files:
            full_path = context.project_path / file_path

            if not full_path.exists():
                continue
            if not full_path.is_relative_to(context.project_path):
                continue

            pattern_findings = _scan_file_patterns(full_path, file_path)
            findings.extend(pattern_findings)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _extract_string_literal(expr: str) -> str | None:
    """Extract the inner value of a string literal expression."""
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


def _find_secret_assignments(db: RuleDB) -> list[StandardFinding]:
    """Find variable assignments that look like secrets."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .where("LENGTH(source_expr) > 10")
        .order_by("file, line")
    )

    for file, line, var, value in rows:
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


def _find_connection_strings(db: RuleDB) -> list[StandardFinding]:
    """Find database connection strings with embedded passwords."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, _var, conn_str in rows:
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


def _find_env_fallbacks(db: RuleDB) -> list[StandardFinding]:
    """Find environment variable fallbacks with hardcoded secrets."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    fallback_patterns = ["process.env", "os.environ.get", "getenv", "||", "??", " or "]
    secret_keywords_lower = ["secret", "key", "token", "password", "credential"]

    for file, line, var, expr in rows:
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


def _find_dict_secrets(db: RuleDB) -> list[StandardFinding]:
    """Find secrets in dictionary/object literals."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "source_expr").where("source_expr IS NOT NULL")
    )

    for file, line, expr in rows:
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


def _find_api_keys_in_urls(db: RuleDB) -> list[StandardFinding]:
    """Find API keys embedded in URLs."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    http_functions = frozenset(["fetch", "axios", "request", "get", "post"])
    api_key_params = ["api_key=", "apikey=", "token=", "key=", "secret=", "password="]

    for file, line, func, args in rows:
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
                and len(key_value) > 10
                and _is_likely_secret(key_value)
            ):
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


def _get_suspicious_files(db: RuleDB) -> list[str]:
    """Get list of files likely to contain secrets."""
    suspicious_files = []

    rows = db.query(
        Q("symbols").select("path", "name").where("name IS NOT NULL").where("path IS NOT NULL")
    )

    secret_keywords_lower = ["secret", "token", "password", "api_key", "credential", "private_key"]

    file_secret_counts: dict[str, int] = {}
    for path, name in rows:
        name_lower = name.lower()
        if any(kw in name_lower for kw in secret_keywords_lower):
            file_secret_counts[path] = file_secret_counts.get(path, 0) + 1

    for path, count in file_secret_counts.items():
        if count > 3:
            suspicious_files.append(path)
            if len(suspicious_files) >= 50:
                break

    file_rows = db.query(Q("files").select("path").where("path IS NOT NULL"))

    config_patterns = ["config", "settings", "env.", ".env"]
    exclude_patterns = [".env.example", ".env.template"]

    for (path,) in file_rows:
        if not any(pattern in path for pattern in config_patterns):
            continue

        if any(pattern in path for pattern in exclude_patterns):
            continue

        suspicious_files.append(path)
        if len(suspicious_files) >= 70:
            break

    return list(set(suspicious_files))


def _is_likely_secret(value: str) -> bool:
    """Check if a string value is likely a secret."""
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
    """Calculate Shannon entropy of a string."""
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
            if pattern[i : i + 5] in s_lower and (
                len(s) <= 10 or pattern[i : i + 5] * 2 in s_lower
            ):
                return True

    return False


def _is_keyboard_walk(s: str) -> bool:
    """Check if string is a keyboard walk pattern."""
    s_lower = s.lower()

    for pattern in KEYBOARD_PATTERNS:
        if pattern in s_lower and (
            len(s) <= 10 or s_lower.count(pattern) * len(pattern) > len(s) / 2
        ):
            return True

    return False


def _is_base64_secret(value: str) -> bool:
    """Check if a Base64 string decodes to a secret."""
    base64_pattern = r"^[A-Za-z0-9+/]{20,}={0,2}$"
    if not re.match(base64_pattern, value):
        return False

    try:
        decoded = base64.b64decode(value, validate=True)
        decoded_str = decoded.decode("utf-8", errors="ignore")
        entropy = _calculate_entropy(decoded_str)
        return entropy > 4.0
    except (ValueError, TypeError):
        return False


def _scan_file_patterns(file_path: Path, relative_path: str) -> list[StandardFinding]:
    """Scan file content for secret patterns.

    Note: No try/except per Zero Fallback policy. Caller must verify file exists.
    I/O errors will crash and expose the underlying issue.
    """
    findings = []

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

    return findings
