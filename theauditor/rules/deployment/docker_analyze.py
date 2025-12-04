"""Dockerfile Security Analyzer - Database-First Approach."""

import json
import math
import re
import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="dockerfile_security",
    category="deployment",
    target_extensions=[],
    exclude_patterns=["test/", "__tests__/", "node_modules/", ".pf/", ".auditor_venv/"])


@dataclass(frozen=True)
class DockerfilePatterns:
    """Pattern definitions for Dockerfile security analysis."""

    SENSITIVE_ENV_KEYWORDS: frozenset = frozenset(
        [
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
        ]
    )

    WEAK_PASSWORDS: frozenset = frozenset(
        [
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
        ]
    )

    VULNERABLE_BASE_IMAGES: frozenset = frozenset(
        [
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
        ]
    )


SECRET_VALUE_PATTERNS = [
    re.compile(r"^ghp_[A-Za-z0-9]{36}$"),
    re.compile(r"^ghs_[A-Za-z0-9]{36}$"),
    re.compile(r"^sk-[A-Za-z0-9]{48}$"),
    re.compile(r"^xox[baprs]-[A-Za-z0-9-]+$"),
    re.compile(r"^AKIA[A-Z0-9]{16}$"),
]


SENSITIVE_PORT_NUMS = frozenset(
    [
        "22",
        "23",
        "135",
        "139",
        "445",
        "3389",
        "3306",
        "5432",
        "6379",
        "27017",
        "9200",
    ]
)


def find_docker_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Dockerfile security misconfigurations using indexed data."""
    findings = []

    if not context.db_path:
        return findings

    patterns = DockerfilePatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_check_root_user(cursor, patterns))
        findings.extend(_check_exposed_secrets(cursor, patterns))
        findings.extend(_check_vulnerable_images(cursor, patterns))
        findings.extend(_check_missing_healthcheck(cursor))
        findings.extend(_check_sensitive_ports(cursor))

    finally:
        conn.close()

    return findings


def _check_root_user(cursor, patterns: DockerfilePatterns) -> list[StandardFinding]:
    """Detect containers running as root user."""
    findings = []

    from theauditor.indexer.schema import build_query

    query = build_query("docker_images", ["file_path", "env_vars"])
    cursor.execute(query)

    for row in cursor.fetchall():
        file_path = row[0]
        env_vars_json = row[1]

        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
        except json.JSONDecodeError:
            continue

        docker_user = env_vars.get("_DOCKER_USER")

        if docker_user is None or docker_user.lower() == "root":
            severity = Severity.HIGH if docker_user is None else Severity.CRITICAL
            msg_suffix = "not set" if docker_user is None else "set to root"

            findings.append(
                StandardFinding(
                    rule_name="dockerfile-root-user",
                    message=f"Container runs as root user (USER instruction {msg_suffix})",
                    file_path=file_path,
                    line=1,
                    severity=severity,
                    category="deployment",
                    snippet=f"USER {docker_user or '[not set]'}",
                    cwe_id="CWE-250",
                )
            )

    return findings


def _check_exposed_secrets(cursor, patterns: DockerfilePatterns) -> list[StandardFinding]:
    """Detect hardcoded secrets in ENV and ARG instructions."""
    findings = []

    from theauditor.indexer.schema import build_query

    query = build_query("docker_images", ["file_path", "env_vars", "build_args"])
    cursor.execute(query)

    for row in cursor.fetchall():
        file_path = row[0]
        env_vars_json = row[1]
        build_args_json = row[2]

        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
            build_args = json.loads(build_args_json) if build_args_json else {}
        except json.JSONDecodeError:
            continue

        for key, value in env_vars.items():
            if key.startswith("_DOCKER_"):
                continue

            if not value or not isinstance(value, str):
                continue

            key_upper = key.upper()

            is_sensitive = any(kw in key_upper for kw in patterns.SENSITIVE_ENV_KEYWORDS)

            if is_sensitive:
                if value.lower() in patterns.WEAK_PASSWORDS:
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

        for key, value in build_args.items():
            if not value or not isinstance(value, str):
                continue

            key_upper = key.upper()
            is_sensitive = any(kw in key_upper for kw in patterns.SENSITIVE_ENV_KEYWORDS)

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


def _check_vulnerable_images(cursor, patterns: DockerfilePatterns) -> list[StandardFinding]:
    """Detect use of vulnerable or EOL base images."""
    findings = []

    from theauditor.indexer.schema import build_query

    query = build_query(
        "docker_images", ["file_path", "base_image"], where="base_image IS NOT NULL"
    )
    cursor.execute(query)

    for row in cursor.fetchall():
        file_path = row[0]
        base_image = row[1]

        for vuln_pattern in patterns.VULNERABLE_BASE_IMAGES:
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

        if "@" in base_image:
            image_name = base_image.split("@")[0]
        elif ":" in base_image:
            image_name = base_image.split(":")[0]
        else:
            image_name = base_image

        official_images = {"alpine", "ubuntu", "debian", "centos", "fedora", "busybox", "scratch"}

        if "/" not in image_name and image_name not in official_images:
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


def _is_high_entropy(value: str, threshold: float = 4.0) -> bool:
    """Check if a string has high Shannon entropy (potential secret)."""

    if len(value) < 10:
        return False

    if " " in value:
        return False

    char_freq = {}
    for char in value:
        char_freq[char] = char_freq.get(char, 0) + 1

    entropy = 0.0
    for count in char_freq.values():
        probability = count / len(value)
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy > threshold


def _check_missing_healthcheck(cursor) -> list[StandardFinding]:
    """Detect containers without HEALTHCHECK instruction."""
    findings = []

    from theauditor.indexer.schema import build_query

    query = build_query(
        "docker_images", ["file_path"], where="has_healthcheck = 0 OR has_healthcheck IS NULL"
    )
    cursor.execute(query)

    for row in cursor.fetchall():
        file_path = row[0]

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


def _check_sensitive_ports(cursor) -> list[StandardFinding]:
    """Detect containers exposing sensitive management ports."""
    findings = []

    from theauditor.indexer.schema import build_query

    query = build_query(
        "docker_images",
        ["file_path", "exposed_ports"],
        where="exposed_ports IS NOT NULL AND exposed_ports != '[]'",
    )
    cursor.execute(query)

    for row in cursor.fetchall():
        file_path = row[0]
        ports_json = row[1]

        try:
            ports = json.loads(ports_json) if ports_json else []
        except json.JSONDecodeError:
            continue

        for port_spec in ports:
            port_num = port_spec.split("/")[0].strip()

            if port_num in SENSITIVE_PORT_NUMS:
                port_service_map = {
                    "22": "SSH",
                    "23": "Telnet",
                    "135": "Windows RPC",
                    "139": "NetBIOS",
                    "445": "SMB",
                    "3389": "RDP",
                    "3306": "MySQL",
                    "5432": "PostgreSQL",
                    "6379": "Redis",
                    "27017": "MongoDB",
                    "9200": "Elasticsearch",
                }
                service_name = port_service_map.get(port_num, "Unknown")

                findings.append(
                    StandardFinding(
                        rule_name="dockerfile-sensitive-port-exposed",
                        message=f"Container exposes sensitive port {port_num} ({service_name}) - should be behind VPN/bastion",
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="deployment",
                        snippet=f"EXPOSE {port_spec}",
                        cwe_id="CWE-749",
                    )
                )

    return findings
