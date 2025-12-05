"""Dockerfile Security Analyzer - Database-First Approach.

Detects security misconfigurations in Dockerfiles:
- Root user execution (CWE-250)
- Hardcoded secrets in ENV/ARG (CWE-798)
- Private keys in environment variables (CWE-321)
- Weak passwords (CWE-521)
- Vulnerable/EOL base images (CWE-937)
- Unpinned image versions (CWE-494)
- Missing HEALTHCHECK (CWE-1272)
- Sensitive ports exposed (CWE-749)
- Docker API ports exposed (CWE-749) - CRITICAL
- Secret patterns (GitHub PAT, AWS keys, JWT, Stripe, etc.)
"""

import math
import re

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="dockerfile_security",
    category="deployment",
    target_extensions=[],
    exclude_patterns=["test/", "__tests__/", "node_modules/", ".pf/", ".auditor_venv/"],
    execution_scope="database",
    primary_table="docker_images",
)


SENSITIVE_ENV_KEYWORDS = frozenset([
    "PASSWORD",
    "PASS",
    "PWD",
    "SECRET",
    "TOKEN",
    "KEY",
    "API_KEY",
    "ACCESS_KEY",
    "PRIVATE",
    "CREDENTIAL",
    "AUTH",
])

WEAK_PASSWORDS = frozenset([
    "password",
    "123456",
    "admin",
    "root",
    "test",
    "demo",
    "secret",
    "changeme",
    "password123",
    "admin123",
    "letmein",
    "welcome",
    "monkey",
    "dragon",
    "master",
])

VULNERABLE_BASE_IMAGES = frozenset([
    "elasticsearch:2",
    "elasticsearch:5",
    "mysql:5.6",
    "postgres:9",
    "mongo:3",
    "redis:3",
    "node:8",
    "node:10",
    "node:12",
    "python:2",
    "ruby:2.4",
    "php:5",
    "php:7.0",
    "php:7.1",
    "php:7.2",
])

SECRET_VALUE_PATTERNS = [
    re.compile(r"^ghp_[A-Za-z0-9]{36}$"),  # GitHub PAT
    re.compile(r"^ghs_[A-Za-z0-9]{36}$"),  # GitHub Server PAT
    re.compile(r"^gho_[A-Za-z0-9]{36}$"),  # GitHub OAuth
    re.compile(r"^ghu_[A-Za-z0-9]{36}$"),  # GitHub User-to-server
    re.compile(r"^sk-[A-Za-z0-9]{48}$"),   # OpenAI API key
    re.compile(r"^xox[baprs]-[A-Za-z0-9-]+$"),  # Slack tokens
    re.compile(r"^AKIA[A-Z0-9]{16}$"),     # AWS Access Key ID
    re.compile(r"^ASIA[A-Z0-9]{16}$"),     # AWS Temporary Access Key
    re.compile(r"^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"),  # JWT token
    re.compile(r"^sk_live_[A-Za-z0-9]{24,}$"),  # Stripe live key
    re.compile(r"^sk_test_[A-Za-z0-9]{24,}$"),  # Stripe test key
    re.compile(r"^rk_live_[A-Za-z0-9]{24,}$"),  # Stripe restricted key
    re.compile(r"^AC[a-f0-9]{32}$"),       # Twilio Account SID
    re.compile(r"^SK[a-f0-9]{32}$"),       # Twilio API Key
    re.compile(r"^np_[A-Za-z0-9_-]{30,}$"),  # npm token
    re.compile(r"^pypi-[A-Za-z0-9_-]{30,}$"),  # PyPI token
    re.compile(r"^glpat-[A-Za-z0-9_-]{20,}$"),  # GitLab PAT
]

# Patterns that indicate private key material (substring match, not full value)
PRIVATE_KEY_INDICATORS = [
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
]

SENSITIVE_PORTS = {
    22: "SSH",
    23: "Telnet",
    135: "Windows RPC",
    139: "NetBIOS",
    445: "SMB",
    2375: "Docker API (unencrypted)",  # CRITICAL - unauthenticated container access
    2376: "Docker API (TLS)",          # Still sensitive - container management
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    5671: "RabbitMQ (AMQP TLS)",
    5672: "RabbitMQ (AMQP)",
    6379: "Redis",
    11211: "Memcached",
    27017: "MongoDB",
    9200: "Elasticsearch",
    9300: "Elasticsearch (transport)",
}

# Ports that are CRITICAL severity (not just HIGH)
CRITICAL_PORTS = {2375, 2376}  # Docker API = full container escape

OFFICIAL_BASE_IMAGES = frozenset([
    "alpine", "ubuntu", "debian", "centos", "fedora", "busybox", "scratch"
])


def find_docker_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Dockerfile security misconfigurations using indexed data."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Load all data from correct tables
        images = _load_images(db)
        env_vars_by_file = _load_env_vars(db)
        ports_by_file = _load_ports(db)

        for file_path, image_data in images.items():
            env_vars = env_vars_by_file.get(file_path, {"env": {}, "args": {}})
            ports = ports_by_file.get(file_path, [])

            # Check: Root user
            findings.extend(_check_root_user(file_path, image_data))

            # Check: Exposed secrets in ENV/ARG
            findings.extend(_check_exposed_secrets(file_path, env_vars))

            # Check: Vulnerable base images
            findings.extend(_check_vulnerable_images(file_path, image_data))

            # Check: Missing healthcheck
            findings.extend(_check_missing_healthcheck(file_path, image_data))

            # Check: Sensitive ports
            findings.extend(_check_sensitive_ports(file_path, ports))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _load_images(db: RuleDB) -> dict[str, dict]:
    """Load all docker images into a dictionary keyed by file_path."""
    images = {}

    rows = db.query(
        Q("docker_images")
        .select("file_path", "base_image", "user", "has_healthcheck")
    )

    for file_path, base_image, user, has_healthcheck in rows:
        images[file_path] = {
            "base_image": base_image,
            "user": user,
            "has_healthcheck": bool(has_healthcheck),
        }

    return images


def _load_env_vars(db: RuleDB) -> dict[str, dict[str, dict[str, str]]]:
    """Load all environment variables grouped by file_path."""
    env_by_file = {}

    rows = db.query(
        Q("dockerfile_env_vars")
        .select("file_path", "var_name", "var_value", "is_build_arg")
    )

    for file_path, var_name, var_value, is_build_arg in rows:
        if file_path not in env_by_file:
            env_by_file[file_path] = {"env": {}, "args": {}}

        if is_build_arg:
            env_by_file[file_path]["args"][var_name] = var_value
        else:
            env_by_file[file_path]["env"][var_name] = var_value

    return env_by_file


def _load_ports(db: RuleDB) -> dict[str, list[dict]]:
    """Load all exposed ports grouped by file_path."""
    ports_by_file = {}

    rows = db.query(
        Q("dockerfile_ports")
        .select("file_path", "port", "protocol")
    )

    for file_path, port, protocol in rows:
        if file_path not in ports_by_file:
            ports_by_file[file_path] = []
        ports_by_file[file_path].append({
            "port": port,
            "protocol": protocol or "tcp",
        })

    return ports_by_file


def _check_root_user(file_path: str, image_data: dict) -> list[StandardFinding]:
    """Detect containers running as root user."""
    findings = []
    user = image_data.get("user")

    # Explicit root is CRITICAL, no user specified is MEDIUM
    # (many base images already run as non-root by default)
    if user and user.lower() in ("root", "0"):
        findings.append(
            StandardFinding(
                rule_name="dockerfile-root-user",
                message="Container explicitly runs as root user",
                file_path=file_path,
                line=1,
                severity=Severity.CRITICAL,
                category="deployment",
                snippet=f"USER {user}",
                cwe_id="CWE-250",
            )
        )
    elif user is None:
        findings.append(
            StandardFinding(
                rule_name="dockerfile-no-user",
                message="No USER instruction - container may run as root depending on base image",
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="deployment",
                snippet="# USER instruction not found",
                cwe_id="CWE-250",
            )
        )

    return findings


def _check_exposed_secrets(file_path: str, env_vars: dict) -> list[StandardFinding]:
    """Detect hardcoded secrets in ENV and ARG instructions."""
    findings = []

    # Check ENV variables
    for key, value in env_vars.get("env", {}).items():
        if not value or not isinstance(value, str):
            continue

        key_upper = key.upper()
        is_sensitive = any(kw in key_upper for kw in SENSITIVE_ENV_KEYWORDS)

        if is_sensitive:
            if value.lower() in WEAK_PASSWORDS:
                findings.append(
                    StandardFinding(
                        rule_name="dockerfile-weak-password",
                        message=f"Weak password in ENV {key}",
                        file_path=file_path,
                        line=1,
                        severity=Severity.CRITICAL,
                        category="deployment",
                        snippet=f"ENV {key}=***",
                        cwe_id="CWE-521",
                    )
                )
            else:
                findings.append(
                    StandardFinding(
                        rule_name="dockerfile-hardcoded-secret",
                        message=f"Hardcoded secret in ENV instruction: {key}",
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="deployment",
                        snippet=f"ENV {key}=***",
                        cwe_id="CWE-798",
                    )
                )
            continue

        # Check for known secret patterns
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.match(value):
                findings.append(
                    StandardFinding(
                        rule_name="dockerfile-secret-pattern",
                        message=f"Detected secret pattern in ENV {key}",
                        file_path=file_path,
                        line=1,
                        severity=Severity.CRITICAL,
                        category="deployment",
                        snippet=f"ENV {key}=[REDACTED]",
                        cwe_id="CWE-798",
                    )
                )
                break

        # Check for private key material
        for indicator in PRIVATE_KEY_INDICATORS:
            if indicator in value:
                findings.append(
                    StandardFinding(
                        rule_name="dockerfile-private-key",
                        message=f"Private key embedded in ENV {key} - CRITICAL exposure",
                        file_path=file_path,
                        line=1,
                        severity=Severity.CRITICAL,
                        category="deployment",
                        snippet=f"ENV {key}=[PRIVATE KEY REDACTED]",
                        cwe_id="CWE-321",
                    )
                )
                break

        # Check for high entropy values
        if _is_high_entropy(value):
            findings.append(
                StandardFinding(
                    rule_name="dockerfile-high-entropy",
                    message=f"High entropy value in ENV {key} - possible secret",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="deployment",
                    snippet=f"ENV {key}=[REDACTED]",
                    cwe_id="CWE-798",
                )
            )

    # Check ARG (build arguments)
    for key, value in env_vars.get("args", {}).items():
        if not value or not isinstance(value, str):
            continue

        key_upper = key.upper()
        is_sensitive = any(kw in key_upper for kw in SENSITIVE_ENV_KEYWORDS)

        if is_sensitive:
            findings.append(
                StandardFinding(
                    rule_name="dockerfile-arg-secret",
                    message=f"Potential secret in ARG instruction: {key}",
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="deployment",
                    snippet=f"ARG {key}=***",
                    cwe_id="CWE-798",
                )
            )

    return findings


def _check_vulnerable_images(file_path: str, image_data: dict) -> list[StandardFinding]:
    """Detect use of vulnerable or EOL base images."""
    findings = []
    base_image = image_data.get("base_image")

    if not base_image:
        return findings

    # Check for known vulnerable images
    for vuln_pattern in VULNERABLE_BASE_IMAGES:
        if base_image.startswith(vuln_pattern):
            findings.append(
                StandardFinding(
                    rule_name="dockerfile-vulnerable-image",
                    message=f"Base image {vuln_pattern} is deprecated/EOL",
                    file_path=file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category="deployment",
                    snippet=f"FROM {base_image}",
                    cwe_id="CWE-937",
                )
            )
            break

    # Check for unpinned versions
    if ":latest" in base_image or (":" not in base_image and "@" not in base_image):
        findings.append(
            StandardFinding(
                rule_name="dockerfile-unpinned-version",
                message="Base image uses unpinned version (non-reproducible builds)",
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="deployment",
                snippet=f"FROM {base_image}",
                cwe_id="CWE-494",
            )
        )

    # Extract image name without tag/digest
    if "@" in base_image:
        image_name = base_image.split("@")[0]
    elif ":" in base_image:
        image_name = base_image.split(":")[0]
    else:
        image_name = base_image

    # Check for potentially unofficial images (typosquatting risk)
    if "/" not in image_name and image_name not in OFFICIAL_BASE_IMAGES:
        findings.append(
            StandardFinding(
                rule_name="dockerfile-unofficial-image",
                message=f"Image {image_name} lacks registry namespace (typosquatting risk)",
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category="deployment",
                snippet=f"FROM {base_image}",
                cwe_id="CWE-494",
            )
        )

    return findings


def _check_missing_healthcheck(file_path: str, image_data: dict) -> list[StandardFinding]:
    """Detect containers without HEALTHCHECK instruction."""
    findings = []

    if not image_data.get("has_healthcheck"):
        findings.append(
            StandardFinding(
                rule_name="dockerfile-missing-healthcheck",
                message="Container missing HEALTHCHECK instruction - orchestrator cannot monitor health",
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category="deployment",
                snippet="# No HEALTHCHECK instruction found",
                cwe_id="CWE-1272",
            )
        )

    return findings


def _check_sensitive_ports(file_path: str, ports: list[dict]) -> list[StandardFinding]:
    """Detect containers exposing sensitive management ports."""
    findings = []

    for port_info in ports:
        port_num = port_info.get("port")
        protocol = port_info.get("protocol", "tcp")

        if port_num in SENSITIVE_PORTS:
            service_name = SENSITIVE_PORTS[port_num]
            # Docker API ports are CRITICAL - they allow full container escape
            severity = Severity.CRITICAL if port_num in CRITICAL_PORTS else Severity.HIGH
            message = (
                f"Container exposes Docker API port {port_num} - FULL CONTAINER ESCAPE POSSIBLE"
                if port_num in CRITICAL_PORTS
                else f"Container exposes sensitive port {port_num} ({service_name}) - should be behind VPN/bastion"
            )
            findings.append(
                StandardFinding(
                    rule_name="dockerfile-sensitive-port-exposed",
                    message=message,
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category="deployment",
                    snippet=f"EXPOSE {port_num}/{protocol}",
                    cwe_id="CWE-749",
                )
            )

    return findings


def _is_high_entropy(value: str, threshold: float = 4.0) -> bool:
    """Check if a string has high Shannon entropy (potential secret)."""
    # Skip short values
    if len(value) < 10:
        return False

    # Skip values with spaces (likely not secrets)
    if " " in value:
        return False

    # Calculate Shannon entropy
    char_freq = {}
    for char in value:
        char_freq[char] = char_freq.get(char, 0) + 1

    entropy = 0.0
    for count in char_freq.values():
        probability = count / len(value)
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy > threshold
