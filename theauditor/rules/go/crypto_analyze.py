"""Go Cryptography Misuse Analyzer.

Detects common Go cryptography vulnerabilities:
1. math/rand in security-sensitive code (use crypto/rand) - CWE-330
2. Weak hashing algorithms (MD5/SHA1) - CWE-328
3. Insecure TLS configuration (InsecureSkipVerify, weak versions) - CWE-295/326
4. Hardcoded secrets in constants/variables - CWE-798
"""

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
        findings.extend(_check_weak_hashing(db))
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

    # Find files importing math/rand
    math_rand_rows = db.query(
        Q("go_imports")
        .select("file_path", "line")
        .where("path = ?", "math/rand")
    )

    math_rand_files = {file_path: line for file_path, line in math_rand_rows}

    if not math_rand_files:
        return findings

    for file_path, import_line in math_rand_files.items():
        # Check if file also imports crypto-related packages
        crypto_import_rows = db.query(
            Q("go_imports")
            .select("path")
            .where("file_path = ?", file_path)
            .where("path LIKE ? OR path LIKE ? OR path LIKE ?", "%crypto%", "%password%", "%auth%")
            .limit(1)
        )
        has_crypto = len(list(crypto_import_rows)) > 0

        # Check for security-related function names
        security_func_rows = db.query(
            Q("go_functions")
            .select("name")
            .where("file_path = ?", file_path)
            .where(
                "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
                "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
                "%token%", "%secret%", "%password%", "%key%", "%auth%", "%session%"
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


def _check_weak_hashing(db: RuleDB) -> list[StandardFinding]:
    """Detect MD5/SHA1 usage for security purposes.

    MD5 and SHA1 are cryptographically broken for security use cases
    like password hashing, digital signatures, or integrity verification.
    """
    findings = []

    # Find files importing weak hash algorithms
    weak_hash_rows = db.query(
        Q("go_imports")
        .select("file_path", "line", "path")
        .where("path = ? OR path = ?", "crypto/md5", "crypto/sha1")
    )

    for file_path, import_line, import_path in weak_hash_rows:
        hash_type = "MD5" if "md5" in import_path else "SHA1"

        # Check for security-related function context
        security_func_rows = db.query(
            Q("go_functions")
            .select("name")
            .where("file_path = ?", file_path)
            .where(
                "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
                "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
                "%password%", "%auth%", "%verify%", "%hash%", "%sign%"
            )
            .limit(1)
        )
        security_context = len(list(security_func_rows)) > 0

        severity = Severity.HIGH if security_context else Severity.MEDIUM
        confidence = Confidence.HIGH if security_context else Confidence.LOW

        findings.append(
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

    return findings


def _check_insecure_tls(db: RuleDB) -> list[StandardFinding]:
    """Detect InsecureSkipVerify and weak TLS versions.

    InsecureSkipVerify: true completely disables certificate validation,
    making the connection vulnerable to MITM attacks.

    TLS versions < 1.2 have known vulnerabilities and should not be used.
    """
    findings = []

    # Check for InsecureSkipVerify: true
    skip_verify_rows = db.query(
        Q("go_variables")
        .select("file_path", "line", "initial_value")
        .where("initial_value LIKE ? OR initial_value LIKE ?",
               "%InsecureSkipVerify%true%", "%InsecureSkipVerify:%true%")
    )

    for file_path, line, initial_value in skip_verify_rows:
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

    # Check for weak TLS versions
    weak_tls_rows = db.query(
        Q("go_variables")
        .select("file_path", "line", "initial_value")
        .where("initial_value LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
               "%tls.VersionSSL30%", "%tls.VersionTLS10%", "%tls.VersionTLS11%")
    )

    for file_path, line, initial_value in weak_tls_rows:
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


def _check_hardcoded_secrets(db: RuleDB) -> list[StandardFinding]:
    """Detect hardcoded secrets in constants and variables.

    Secrets should come from environment variables, config files,
    or secret management systems - never hardcoded in source.
    """
    findings = []

    # Check constants with secret-like names
    secret_const_rows = db.query(
        Q("go_constants")
        .select("file_path", "line", "name", "value")
        .where("value IS NOT NULL")
        .where("value != ?", "")
        .where(
            "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ?",
            "%password%", "%secret%", "%api_key%", "%apikey%",
            "%token%", "%private%key%", "%credential%"
        )
    )

    for file_path, line, name, value in secret_const_rows:
        value = value or ""
        # Skip short values or empty strings
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

    # Check package-level variables with secret-like names
    secret_var_rows = db.query(
        Q("go_variables")
        .select("file_path", "line", "name", "initial_value")
        .where("is_package_level = ?", 1)
        .where("initial_value IS NOT NULL")
        .where("initial_value != ?", "")
        .where(
            "LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? "
            "OR LOWER(name) LIKE ? OR LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
            "%password%", "%secret%", "%api_key%", "%apikey%",
            "%token%", "%private%key%"
        )
    )

    for file_path, line, name, initial_value in secret_var_rows:
        value = initial_value or ""
        # Skip if loaded from environment or config
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

    return findings
