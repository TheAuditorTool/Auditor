"""Go Cryptography Misuse Analyzer.

Detects common Go cryptography vulnerabilities:
1. math/rand in security-sensitive code (use crypto/rand) - CWE-330
2. Weak hashing/encryption algorithms (MD5/SHA1/DES/RC4) - CWE-327/328
3. Insecure TLS configuration (InsecureSkipVerify, weak versions) - CWE-295/326
4. Hardcoded secrets in constants/variables - CWE-798
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
    primary_table="go_imports",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Go cryptography misuse.

    Args:
        context: Provides db_path and project context

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_insecure_random(db))
        findings.extend(_check_weak_crypto(db))
        findings.extend(_check_insecure_tls(db))
        findings.extend(_check_hardcoded_secrets(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_insecure_random(db: RuleDB) -> list[StandardFinding]:
    """Detect math/rand usage in security-sensitive code.

    math/rand is not cryptographically secure. When used alongside
    crypto imports or in functions with security-related names,
    it likely indicates a vulnerability.
    """
    findings = []

    math_rand_rows = db.query(
        Q("go_imports").select("file", "line").where("path = ?", "math/rand")
    )

    math_rand_files = dict(math_rand_rows)

    if not math_rand_files:
        return findings

    for file_path, import_line in math_rand_files.items():
        crypto_import_rows = db.query(
            Q("go_imports")
            .select("path")
            .where("file = ?", file_path)
            .where("path LIKE ? OR path LIKE ? OR path LIKE ?", "%crypto%", "%password%", "%auth%")
            .limit(1)
        )
        has_crypto = len(list(crypto_import_rows)) > 0

        security_func_rows = db.query(
            Q("go_functions")
            .select("name")
            .where("file = ?", file_path)
            .where(
                "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
                "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
                "%token%",
                "%secret%",
                "%password%",
                "%key%",
                "%auth%",
                "%session%",
            )
            .limit(1)
        )
        has_security_funcs = len(list(security_func_rows)) > 0

        if has_crypto or has_security_funcs:
            findings.append(
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

    return findings


def _check_weak_crypto(db: RuleDB) -> list[StandardFinding]:
    """Detect weak cryptographic algorithms.

    MD5, SHA1, DES, and RC4 are cryptographically broken for security use cases
    like password hashing, digital signatures, encryption, or integrity verification.
    """
    findings = []

    weak_crypto_rows = db.query(
        Q("go_imports")
        .select("file", "line", "path")
        .where(
            "path = ? OR path = ? OR path = ? OR path = ?",
            "crypto/md5",
            "crypto/sha1",
            "crypto/des",
            "crypto/rc4",
        )
    )

    for file_path, import_line, import_path in weak_crypto_rows:
        if "md5" in import_path:
            algo_type = "MD5"
            algo_category = "hash"
        elif "sha1" in import_path:
            algo_type = "SHA1"
            algo_category = "hash"
        elif "des" in import_path:
            algo_type = "DES"
            algo_category = "cipher"
        elif "rc4" in import_path:
            algo_type = "RC4"
            algo_category = "cipher"
        else:
            continue

        security_func_rows = db.query(
            Q("go_functions")
            .select("name")
            .where("file = ?", file_path)
            .where(
                "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
                "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
                "%password%",
                "%auth%",
                "%verify%",
                "%hash%",
                "%sign%",
                "%encrypt%",
            )
            .limit(1)
        )
        security_context = len(list(security_func_rows)) > 0

        severity = Severity.HIGH if security_context else Severity.MEDIUM
        confidence = Confidence.HIGH if security_context else Confidence.LOW

        if algo_category == "hash":
            message = f"{algo_type} is cryptographically weak - use SHA-256 or better"
        else:
            message = f"{algo_type} is cryptographically broken - use AES-GCM or ChaCha20-Poly1305"

        findings.append(
            StandardFinding(
                rule_name=f"go-weak-{algo_category}-{algo_type.lower()}",
                message=message,
                file_path=file_path,
                line=import_line,
                severity=severity,
                category="crypto",
                confidence=confidence,
                cwe_id="CWE-328" if algo_category == "hash" else "CWE-327",
            )
        )

    return findings


def _check_insecure_tls(db: RuleDB) -> list[StandardFinding]:
    """Detect InsecureSkipVerify and weak TLS versions.

    InsecureSkipVerify: true completely disables certificate validation,
    making the connection vulnerable to MITM attacks.

    TLS versions < 1.2 have known vulnerabilities and should not be used.
    """
    findings = []

    skip_verify_rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(
            "initial_value LIKE ? OR initial_value LIKE ?",
            "%InsecureSkipVerify%true%",
            "%InsecureSkipVerify:%true%",
        )
    )

    for file_path, line, _initial_value in skip_verify_rows:
        findings.append(
            StandardFinding(
                rule_name="go-insecure-tls-skip-verify",
                message="InsecureSkipVerify: true disables TLS certificate validation",
                file_path=file_path,
                line=line,
                severity=Severity.CRITICAL,
                category="crypto",
                confidence=Confidence.HIGH,
                cwe_id="CWE-295",
            )
        )

    weak_tls_rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(
            "initial_value LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
            "%tls.VersionSSL30%",
            "%tls.VersionTLS10%",
            "%tls.VersionTLS11%",
        )
    )

    for file_path, line, _initial_value in weak_tls_rows:
        findings.append(
            StandardFinding(
                rule_name="go-weak-tls-version",
                message="Weak TLS version configured - use TLS 1.2 or higher",
                file_path=file_path,
                line=line,
                severity=Severity.HIGH,
                category="crypto",
                confidence=Confidence.HIGH,
                cwe_id="CWE-326",
            )
        )

    return findings


SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    (re.compile(r"[0-9a-zA-Z/+]{40}"), "AWS Secret Key (40-char base64)"),
    (re.compile(r"ghp_[0-9a-zA-Z]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"gho_[0-9a-zA-Z]{36}"), "GitHub OAuth Token"),
    (re.compile(r"ghu_[0-9a-zA-Z]{36}"), "GitHub User Token"),
    (re.compile(r"ghs_[0-9a-zA-Z]{36}"), "GitHub Server Token"),
    (re.compile(r"ghr_[0-9a-zA-Z]{36}"), "GitHub Refresh Token"),
    (re.compile(r"sk-[0-9a-zA-Z]{48}"), "OpenAI API Key"),
    (re.compile(r"sk-live-[0-9a-zA-Z]{24,}"), "Stripe Live Secret Key"),
    (re.compile(r"sk-test-[0-9a-zA-Z]{24,}"), "Stripe Test Secret Key"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z-]{10,}"), "Slack Token"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "Google API Key"),
    (re.compile(r"ya29\.[0-9A-Za-z_-]+"), "Google OAuth Token"),
    (re.compile(r"[0-9a-f]{32}-us[0-9]{1,2}"), "Mailchimp API Key"),
    (re.compile(r"SG\.[0-9A-Za-z_-]{22}\.[0-9A-Za-z_-]{43}"), "SendGrid API Key"),
    (re.compile(r"key-[0-9a-zA-Z]{32}"), "Mailgun API Key"),
]


def _check_hardcoded_secrets(db: RuleDB) -> list[StandardFinding]:
    """Detect hardcoded secrets in constants and variables.

    Detects:
    1. Variables/constants with secret-like names
    2. High-entropy strings matching known API key patterns
    """
    findings = []

    secret_const_rows = db.query(
        Q("go_constants")
        .select("file", "line", "name", "value")
        .where("value IS NOT NULL")
        .where("value != ?", "")
        .where(
            "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ?",
            "%password%",
            "%secret%",
            "%api_key%",
            "%apikey%",
            "%token%",
            "%private%key%",
            "%credential%",
        )
    )

    for file_path, line, name, value in secret_const_rows:
        value = value or ""
        if len(value) < 5 or value in ('""', "''", '""', "nil"):
            continue

        findings.append(
            StandardFinding(
                rule_name="go-hardcoded-secret",
                message=f"Potential hardcoded secret in constant '{name}'",
                file_path=file_path,
                line=line,
                severity=Severity.HIGH,
                category="crypto",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-798",
            )
        )

    secret_var_rows = db.query(
        Q("go_variables")
        .select("file", "line", "name", "initial_value")
        .where("is_package_level = ?", 1)
        .where("initial_value IS NOT NULL")
        .where("initial_value != ?", "")
        .where(
            "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
            "%password%",
            "%secret%",
            "%api_key%",
            "%apikey%",
            "%token%",
            "%private%key%",
        )
    )

    for file_path, line, name, initial_value in secret_var_rows:
        value = initial_value or ""
        if "os.Getenv" in value or "viper" in value.lower():
            continue

        findings.append(
            StandardFinding(
                rule_name="go-hardcoded-secret-var",
                message=f"Potential hardcoded secret in package variable '{name}'",
                file_path=file_path,
                line=line,
                severity=Severity.HIGH,
                category="crypto",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-798",
            )
        )

    all_const_rows = db.query(
        Q("go_constants")
        .select("file", "line", "name", "value")
        .where("value IS NOT NULL")
        .where("LENGTH(value) > ?", 15)
    )

    seen_findings: set[tuple[str, int]] = set()
    for file_path, line, name, value in all_const_rows:
        value = value or ""

        clean_value = value.strip('"').strip("'").strip("`")

        for pattern, secret_type in SECRET_PATTERNS:
            if pattern.search(clean_value):
                key = (file_path, line)
                if key in seen_findings:
                    continue
                seen_findings.add(key)

                findings.append(
                    StandardFinding(
                        rule_name="go-hardcoded-api-key",
                        message=f"Hardcoded {secret_type} detected in '{name}'",
                        file_path=file_path,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="crypto",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-798",
                    )
                )
                break

    return findings
