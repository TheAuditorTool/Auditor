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


import sqlite3
import re
import base64
import math
from typing import Optional
from pathlib import Path
from collections import Counter

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# RULE METADATA - Smart Filtering Configuration
# ============================================================================
# HYBRID JUSTIFICATION: This rule requires file I/O because:
# 1. Entropy calculation is computational (Shannon entropy cannot be pre-indexed)
# 2. Base64 decoding requires runtime processing
# 3. Provider-specific patterns evolve and need regex evaluation
# 4. Sequential/keyboard pattern detection is algorithmic
# ============================================================================

METADATA = RuleMetadata(
    name="hardcoded_secrets",
    category="secrets",
    execution_scope='database',  # Database-wide analysis (runs once per repo)

    # Target source code and config files ONLY
    target_extensions=[
        '.py', '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs',  # Code
        '.env', '.json', '.yml', '.yaml', '.toml', '.ini',    # Config
        '.sh', '.bash', '.zsh'                                 # Scripts
    ],

    # Exclude non-source paths and example files
    exclude_patterns=[
        'node_modules/',      # Dependencies
        'venv/', '.venv/',    # Virtual environments
        'migrations/',        # Database migrations (low priority)
        'test/', '__tests__/', 'tests/',  # Test files
        '.env.example',       # Example templates
        '.env.template',
        'package-lock.json',  # Lock files
        'yarn.lock',
        'dist/', 'build/',    # Build outputs
        '.git/'               # Version control
    ],

    # Not JSX-specific (uses standard tables)
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Use Frozensets)
# ============================================================================

# Security-related variable name keywords
SECRET_KEYWORDS = frozenset([
    'secret', 'token', 'password', 'passwd', 'pwd',
    'api_key', 'apikey', 'auth_token', 'credential',
    'private_key', 'privatekey', 'access_token', 'refresh_token',
    'client_secret', 'client_id', 'bearer', 'oauth', 'jwt',
    'aws_secret', 'aws_access', 'azure_key', 'gcp_key',
    'stripe_key', 'github_token', 'gitlab_token',
    'encryption_key', 'decrypt_key', 'cipher_key',
    'session_key', 'signing_key', 'hmac_key'
])

# Weak/default passwords to detect
WEAK_PASSWORDS = frozenset([
    'password', 'admin', '123456', 'changeme', 'default',
    'test', 'demo', 'sample', 'example', 'password123',
    'admin123', 'root', 'toor', 'pass', 'secret',
    'qwerty', 'letmein', 'welcome', 'monkey', 'dragon'
])

# Placeholder values that are not real secrets
PLACEHOLDER_VALUES = frozenset([
    'placeholder', 'changeme', 'your_password_here',
    'YOUR_API_KEY', 'API_KEY_HERE', '<password>',
    '${PASSWORD}', '{{PASSWORD}}', 'xxx', 'TODO',
    'FIXME', 'CHANGE_ME', 'INSERT_HERE', 'dummy'
])

# Common non-secret values
NON_SECRET_VALUES = frozenset([
    'true', 'false', 'none', 'null', 'undefined',
    'development', 'production', 'test', 'staging',
    'localhost', '127.0.0.1', '0.0.0.0', 'example.com'
])

# URL protocols to skip
URL_PROTOCOLS = frozenset([
    'http://', 'https://', 'ftp://', 'sftp://',
    'ssh://', 'git://', 'file://', 'data://'
])

# Database protocols for connection strings
DB_PROTOCOLS = frozenset([
    'mongodb://', 'postgres://', 'postgresql://',
    'mysql://', 'redis://', 'amqp://', 'rabbitmq://',
    'cassandra://', 'couchdb://', 'elasticsearch://'
])

# Regex for detecting string literals (supports Python & JS styles)
# Credit: @dev-corelift (PR #20) - Prevents false positives on dynamic values
STRING_LITERAL_RE = re.compile(
    r'^(?P<prefix>[rubfRUBF]*)(?P<quote>"""|\'\'\'|"|\'|`)(?P<body>.*)(?P=quote)$',
    re.DOTALL
)

# High-confidence secret patterns (provider-specific)
HIGH_CONFIDENCE_PATTERNS = frozenset([
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    (r'(?i)aws_secret_access_key\s*=\s*["\']([^"\']+)["\']', 'AWS Secret Key'),
    (r'sk_live_[a-zA-Z0-9]{24,}', 'Stripe Live Key'),
    (r'sk_test_[a-zA-Z0-9]{24,}', 'Stripe Test Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Personal Token'),
    (r'gho_[a-zA-Z0-9]{36}', 'GitHub OAuth Token'),
    (r'glpat-[a-zA-Z0-9\-_]{20,}', 'GitLab Token'),
    (r'xox[baprs]-[a-zA-Z0-9\-]+', 'Slack Token'),
    (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----', 'Private Key'),
    (r'AIza[0-9A-Za-z\-_]{35}', 'Google API Key'),
    (r'ya29\.[0-9A-Za-z\-_]+', 'Google OAuth Token'),
    (r'AAAA[A-Za-z0-9]{31}', 'Dropbox Token'),
    (r'sq0csp-[0-9A-Za-z\-_]{43}', 'Square Access Token'),
    (r'sqOatp-[0-9A-Za-z\-_]{22}', 'Square OAuth Secret')
])

# Generic secret patterns (high entropy)
GENERIC_SECRET_PATTERNS = frozenset([
    r'^[a-fA-F0-9]{32,}$',  # Hex strings (MD5, SHA, etc.)
    r'^[A-Z0-9]{20,}$',  # All caps alphanumeric
    r'^[a-zA-Z0-9]{40}$',  # Generic 40-char token
    r'^[A-Za-z0-9+/]{20,}={0,2}$',  # Base64
    r'^[a-zA-Z0-9_\-]{32,}$'  # Generic token with safe chars
])

# Sequential patterns to exclude
SEQUENTIAL_PATTERNS = frozenset([
    'abcdefghijklmnopqrstuvwxyz',
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
    '0123456789',
    'qwertyuiop',
    'asdfghjkl',
    'zxcvbnm'
])

# Keyboard walk patterns to exclude
KEYBOARD_PATTERNS = frozenset([
    'qwerty', 'asdfgh', 'zxcvbn',
    '12345', '098765',
    'qazwsx', 'qweasd',
    'qwertyuiop', 'asdfghjkl'
])


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

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
        # All required tables guaranteed to exist by schema contract
        # (theauditor/indexer/schema.py - TABLES registry with 46 table definitions)
        # If table missing, rule will crash with clear sqlite3.OperationalError (CORRECT behavior)

        # ========================================================
        # DATABASE-BASED CHECKS
        # ========================================================
        # Execute all checks unconditionally (schema contract guarantees table existence)
        findings.extend(_find_secret_assignments(cursor))
        findings.extend(_find_connection_strings(cursor))
        findings.extend(_find_env_fallbacks(cursor))
        findings.extend(_find_dict_secrets(cursor))
        findings.extend(_find_api_keys_in_urls(cursor))

        # ========================================================
        # PATTERN-BASED CHECKS (Justified Hybrid)
        # ========================================================
        # For files with high secret probability, do targeted pattern matching
        # This is necessary because entropy and patterns are computational
        suspicious_files = _get_suspicious_files(cursor)

        for file_path in suspicious_files:
            # Ensure file is within project
            try:
                full_path = context.project_path / file_path
                if full_path.exists() and full_path.is_relative_to(context.project_path):
                    pattern_findings = _scan_file_patterns(full_path, file_path)
                    findings.extend(pattern_findings)
            except (ValueError, OSError):
                # File outside project or can't be read
                continue

    finally:
        conn.close()

    return findings


# ============================================================================
# DATABASE-BASED DETECTION FUNCTIONS
# ============================================================================

def _extract_string_literal(expr: str) -> Optional[str]:
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

    prefix = match.group('prefix') or ''
    quote = match.group('quote')
    body = match.group('body')

    # F-strings interpolate runtime data; they are not static literals
    if any(ch.lower() == 'f' for ch in prefix):
        return None

    # Skip template literals with interpolation
    if quote == '`' and '${' in body:
        return None

    return body


def _find_secret_assignments(cursor) -> list[StandardFinding]:
    """Find variable assignments that look like secrets."""
    findings = []

    # Fetch all assignments with long source expressions, filter in Python
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
        # Check if variable name contains secret keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        var_lower = var.lower()
        if not any(kw in var_lower for kw in SECRET_KEYWORDS):
            continue

        # Skip env variable sources
        if ('process.env' in value or
            'import.meta.env' in value or
            'os.environ' in value or
            'getenv' in value):
            continue

        # Extract literal value (skip dynamic expressions)
        # Credit: @dev-corelift (PR #20) - Prevents flagging request.headers.get(), etc.
        literal_value = _extract_string_literal(value)
        if literal_value is None:
            continue  # Not a static literal, skip

        clean_value = literal_value.strip()

        # Check for weak passwords first
        if var.lower() in ['password', 'passwd', 'pwd'] and clean_value.lower() in WEAK_PASSWORDS:
            findings.append(StandardFinding(
                rule_name='secret-weak-password',
                message=f'Weak/default password in variable "{var}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=Confidence.HIGH,
                cwe_id='CWE-521'  # Weak Password Requirements
            ))
        # Check if value looks like a secret
        elif _is_likely_secret(clean_value):
            # Determine confidence based on variable name
            var_lower = var.lower()
            if any(kw in var_lower for kw in ['password', 'secret', 'api_key', 'private_key']):
                confidence = Confidence.HIGH
            elif any(kw in var_lower for kw in SECRET_KEYWORDS):
                confidence = Confidence.MEDIUM
            else:
                confidence = Confidence.LOW

            findings.append(StandardFinding(
                rule_name='secret-hardcoded-assignment',
                message=f'Hardcoded secret in variable "{var}"',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                confidence=confidence,
                cwe_id='CWE-798'  # Use of Hard-coded Credentials
            ))

    return findings


def _find_connection_strings(cursor) -> list[StandardFinding]:
    """Find database connection strings with embedded passwords."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    for file, line, var, conn_str in cursor.fetchall():
        # Check if source contains DB protocol
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        has_protocol = any(proto in conn_str for proto in DB_PROTOCOLS)
        if not has_protocol:
            continue

        # Check if contains @ (user@host pattern)
        if '@' not in conn_str:
            continue

        # Check if connection string has password
        # Pattern: protocol://user:password@host
        if re.search(r'://[^:]+:[^@]+@', conn_str):
            # Extract the password part for checking
            match = re.search(r'://[^:]+:([^@]+)@', conn_str)
            if match:
                password = match.group(1)
                # Check if it's not a placeholder
                if password not in PLACEHOLDER_VALUES:
                    findings.append(StandardFinding(
                        rule_name='secret-connection-string',
                        message=f'Database connection string with embedded password',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-798'
                    ))

    return findings


def _find_env_fallbacks(cursor) -> list[StandardFinding]:
    """Find environment variable fallbacks with hardcoded secrets."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    fallback_patterns = ['process.env', 'os.environ.get', 'getenv', '||', '??', ' or ']
    secret_keywords_lower = ['secret', 'key', 'token', 'password', 'credential']

    for file, line, var, expr in cursor.fetchall():
        # Check if target_var contains secret keywords
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        var_lower = var.lower()
        if not any(kw in var_lower for kw in secret_keywords_lower):
            continue

        # Check if source_expr contains env fallback patterns
        if not any(pattern in expr for pattern in fallback_patterns):
            continue

        # Extract the fallback value
        fallback_match = (re.search(r'\|\|\s*["\']([^"\']+)["\']', expr) or
                         re.search(r'\?\?\s*["\']([^"\']+)["\']', expr) or
                         re.search(r',\s*["\']([^"\']+)["\']', expr) or
                         re.search(r' or ["\']([^"\']+)["\']', expr))

        if fallback_match:
            fallback = fallback_match.group(1)
            if fallback not in PLACEHOLDER_VALUES and _is_likely_secret(fallback):
                findings.append(StandardFinding(
                    rule_name='secret-env-fallback',
                    message=f'Hardcoded secret as environment variable fallback in "{var}"',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-798'
                ))

    return findings


def _find_dict_secrets(cursor) -> list[StandardFinding]:
    """Find secrets in dictionary/object literals."""
    findings = []

    # Fetch all assignments, filter in Python
    cursor.execute("""
        SELECT file, line, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    for file, line, expr in cursor.fetchall():
        # Skip env variable sources
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        if 'process.env' in expr or 'os.environ' in expr:
            continue

        # Check if expression contains any secret keyword as a key
        for keyword in SECRET_KEYWORDS:
            # Check if keyword appears in dict-like pattern
            if (f'"{keyword}":' not in expr and f"'{keyword}':" not in expr):
                continue

            # Extract the value for this key
            pattern = rf'["\']?{keyword}["\']?\s*:\s*["\']([^"\']+)["\']'
            match = re.search(pattern, expr, re.IGNORECASE)

            if match:
                value = match.group(1)
                if value not in PLACEHOLDER_VALUES and _is_likely_secret(value):
                    findings.append(StandardFinding(
                        rule_name='secret-dict-literal',
                        message=f'Hardcoded secret in dictionary key "{keyword}"',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-798'
                    ))

    return findings


def _find_api_keys_in_urls(cursor) -> list[StandardFinding]:
    """Find API keys embedded in URLs."""
    findings = []

    # Fetch all function_call_args, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
        -- REMOVED LIMIT: was hiding bugs
        """)

    http_functions = frozenset(['fetch', 'axios', 'request', 'get', 'post'])
    api_key_params = ['api_key=', 'apikey=', 'token=', 'key=', 'secret=', 'password=']

    for file, line, func, args in cursor.fetchall():
        # Check if function is HTTP-related
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        if func not in http_functions and not (func.endswith('.get') or func.endswith('.post')):
            continue

        # Check if arguments contain API key parameters
        if not any(param in args for param in api_key_params):
            continue

        # Check if the key looks hardcoded
        key_match = re.search(r'(api_key|apikey|token|key|secret|password)=([^&\s]+)', args, re.IGNORECASE)
        if key_match:
            key_value = key_match.group(2)
            # Skip if it's a variable reference or placeholder
            if (not key_value.startswith('${') and
                not key_value.startswith('process.') and
                key_value not in PLACEHOLDER_VALUES):

                if len(key_value) > 10 and _is_likely_secret(key_value):
                    findings.append(StandardFinding(
                        rule_name='secret-api-key-in-url',
                        message=f'API key hardcoded in URL parameter',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-598'  # Information Exposure Through Query Strings
                    ))

    return findings


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_suspicious_files(cursor) -> list[str]:
    """Get list of files likely to contain secrets."""
    suspicious_files = []

    # Fetch all symbols, filter in Python
    cursor.execute("""
        SELECT path, name
        FROM symbols
        WHERE name IS NOT NULL
          AND path IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    secret_keywords_lower = ['secret', 'token', 'password', 'api_key', 'credential', 'private_key']

    # Count symbols with secret keywords per file
    file_secret_counts = {}
    for path, name in cursor.fetchall():
        name_lower = name.lower()
        if any(kw in name_lower for kw in secret_keywords_lower):
            file_secret_counts[path] = file_secret_counts.get(path, 0) + 1

    # Add files with >3 secret-related symbols
    for path, count in file_secret_counts.items():
        if count > 3:
            suspicious_files.append(path)
            if len(suspicious_files) >= 50:
                break

    # Fetch all files, filter for config/settings files in Python
    cursor.execute("""
        SELECT path
        FROM files
        WHERE path IS NOT NULL
        -- REMOVED LIMIT: was hiding bugs
        """)

    config_patterns = ['config', 'settings', 'env.', '.env']
    exclude_patterns = ['.env.example', '.env.template']

    for (path,) in cursor.fetchall():
        # Check if path contains config patterns
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
        if not any(pattern in path for pattern in config_patterns):
            continue

        # Exclude example/template files
        if any(pattern in path for pattern in exclude_patterns):
            continue

        suspicious_files.append(path)
        if len(suspicious_files) >= 70:
            break

    # Return unique files
    return list(set(suspicious_files))


def _is_likely_secret(value: str) -> bool:
    """Check if a string value is likely a secret.

    This function performs computational analysis that cannot be
    pre-indexed in the database (entropy calculation).
    """
    # Skip short strings
    if len(value) < 16:
        return False

    # Skip obvious non-secrets
    if value.lower() in NON_SECRET_VALUES:
        return False

    # Skip URLs and paths
    if any(value.startswith(proto) for proto in URL_PROTOCOLS):
        return False

    if value.startswith(('/', './', '../')):
        return False

    # Skip UUIDs (common false positive)
    uuid_pattern = r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$'
    if re.match(uuid_pattern, value):
        return False

    # Check for high entropy (randomness)
    entropy = _calculate_entropy(value)

    # Check for sequential or keyboard patterns
    if _is_sequential(value) or _is_keyboard_walk(value):
        return False

    # High entropy indicates a secret
    if entropy > 4.5:
        return True

    # Medium entropy with mixed characters
    if entropy > 3.5:
        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_special = any(not c.isalnum() for c in value)

        # Likely a secret if diverse character set
        if sum([has_upper, has_lower, has_digit, has_special]) >= 3:
            return True

    # Check for common secret patterns
    for pattern in GENERIC_SECRET_PATTERNS:
        if re.match(pattern, value):
            # Additional check for minimum unique characters
            unique_chars = len(set(value))
            if unique_chars >= 5:  # Avoid repetitive strings
                return True

    # Check for Base64 that decodes to high entropy
    if _is_base64_secret(value):
        return True

    return False


def _calculate_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string.

    This is a computational property that cannot be pre-indexed.
    """
    if not s:
        return 0.0

    # Count character frequencies
    freq = Counter(s)
    length = len(s)

    # Calculate entropy
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
        # Check for substrings of length 5+
        for i in range(len(pattern) - 4):
            if pattern[i:i+5] in s_lower:
                # Check what percentage of the string is sequential
                if len(s) <= 10 or pattern[i:i+5] * 2 in s_lower:
                    return True

    return False


def _is_keyboard_walk(s: str) -> bool:
    """Check if string is a keyboard walk pattern."""
    s_lower = s.lower()

    for pattern in KEYBOARD_PATTERNS:
        if pattern in s_lower:
            # Check what percentage is keyboard walk
            if len(s) <= 10 or s_lower.count(pattern) * len(pattern) > len(s) / 2:
                return True

    return False


def _is_base64_secret(value: str) -> bool:
    """Check if a Base64 string decodes to a secret.

    This requires runtime decoding and entropy calculation.
    """
    # Check if it looks like Base64
    base64_pattern = r'^[A-Za-z0-9+/]{20,}={0,2}$'
    if not re.match(base64_pattern, value):
        return False

    try:
        # Attempt to decode
        decoded = base64.b64decode(value, validate=True)

        # Convert bytes to string for entropy calculation
        try:
            decoded_str = decoded.decode('utf-8', errors='ignore')
        except:
            # If can't decode to string, check byte entropy
            decoded_str = str(decoded)

        # Check entropy of decoded content
        entropy = _calculate_entropy(decoded_str)

        # High entropy decoded content indicates encoded secret
        return entropy > 4.0

    except Exception:
        # Not valid Base64
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
        with open(file_path, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Limit to first 5000 lines for performance
        lines = lines[:5000]

        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith(('#', '//', '/*', '*')):
                continue

            # Check high-confidence patterns
            for pattern, description in HIGH_CONFIDENCE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    # Verify it's not in a comment
                    comment_pos = max(line.find('#'), line.find('//'))
                    if comment_pos == -1 or match.start() < comment_pos:
                        findings.append(StandardFinding(
                            rule_name='secret-pattern-match',
                            message=f'{description} detected',
                            file_path=relative_path,
                            line=i,
                            severity=Severity.CRITICAL,
                            category='security',
                            confidence=Confidence.HIGH,
                            cwe_id='CWE-798'
                        ))

            # Check for generic high-entropy strings in assignments
            assignment_match = re.search(r'(\w+)\s*=\s*["\']([^"\']{20,})["\']', line)
            if assignment_match:
                var_name = assignment_match.group(1)
                value = assignment_match.group(2)

                if any(kw in var_name.lower() for kw in SECRET_KEYWORDS):
                    if _is_likely_secret(value):
                        findings.append(StandardFinding(
                            rule_name='secret-high-entropy',
                            message=f'High-entropy string in variable "{var_name}"',
                            file_path=relative_path,
                            line=i,
                            severity=Severity.HIGH,
                            category='security',
                            confidence=Confidence.MEDIUM,
                            cwe_id='CWE-798'
                        ))

    except (OSError, UnicodeDecodeError):
        # File reading failed - graceful degradation
        pass

    return findings


def register_taint_patterns(taint_registry):
    """Register secret-related taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    # Register secret sources
    for keyword in SECRET_KEYWORDS:
        taint_registry.register_source(keyword, 'secret', 'all')

    # Register sinks where secrets shouldn't go
    UNSAFE_SINKS = frozenset([
        'console.log', 'print', 'logger.info', 'logger.debug',
        'response.write', 'res.send', 'res.json'
    ])

    for sink in UNSAFE_SINKS:
        taint_registry.register_sink(sink, 'logging', 'all')