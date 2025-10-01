"""Dockerfile Security Analyzer - Database-First Approach.

Detects security misconfigurations in Dockerfile images.
Uses pre-extracted data from docker_images table - NO FILE I/O.

This rule queries docker_images table populated by the indexer
with Dockerfile configuration data (USER instruction, ENV/ARG, base images).

Detects:
- Root user containers (missing USER instruction)
- Hardcoded secrets in ENV/ARG
- High-entropy strings (potential secrets)
- Vulnerable/outdated base images
- Base image CVE scanning (optional)

Migration Status: Gold Standard - Database-First Architecture
"""

import json
import math
import re
import sqlite3
from typing import List, Optional
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA
# ============================================================================

METADATA = RuleMetadata(
    name="dockerfile_security",
    category="deployment",

    # Target Dockerfiles specifically
    target_extensions=[],  # Empty = runs at database level, not per-file
    exclude_patterns=['test/', '__tests__/', 'node_modules/'],

    # Database-first: not JSX-specific
    requires_jsx_pass=False,
)


# ============================================================================
# SECURITY PATTERNS (Frozensets for O(1) Lookup)
# ============================================================================

@dataclass(frozen=True)
class DockerfilePatterns:
    """Pattern definitions for Dockerfile security analysis."""

    # Sensitive environment variable keywords
    SENSITIVE_ENV_KEYWORDS: frozenset = frozenset([
        'PASSWORD', 'PASS', 'PWD', 'SECRET', 'TOKEN', 'KEY',
        'API_KEY', 'ACCESS_KEY', 'PRIVATE', 'CREDENTIAL', 'AUTH'
    ])

    # Common weak passwords
    WEAK_PASSWORDS: frozenset = frozenset([
        'password', '123456', 'admin', 'root', 'test', 'demo',
        'secret', 'changeme', 'password123', 'admin123',
        'letmein', 'welcome', 'monkey', 'dragon', 'master'
    ])

    # Known vulnerable base images (EOL versions)
    VULNERABLE_BASE_IMAGES: frozenset = frozenset([
        'elasticsearch:2', 'elasticsearch:5',
        'mysql:5.6', 'postgres:9', 'mongo:3', 'redis:3',
        'node:8', 'node:10', 'node:12',
        'python:2', 'ruby:2.4',
        'php:5', 'php:7.0', 'php:7.1', 'php:7.2'
    ])


# Secret detection patterns (compiled regex - expensive but necessary)
SECRET_VALUE_PATTERNS = [
    re.compile(r'^ghp_[A-Za-z0-9]{36}$'),        # GitHub PAT
    re.compile(r'^ghs_[A-Za-z0-9]{36}$'),        # GitHub secret
    re.compile(r'^sk-[A-Za-z0-9]{48}$'),         # OpenAI API key
    re.compile(r'^xox[baprs]-[A-Za-z0-9-]+$'),   # Slack token
    re.compile(r'^AKIA[A-Z0-9]{16}$'),           # AWS access key
]


# ============================================================================
# MAIN DETECTION FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Dockerfile security misconfigurations using indexed data.

    Detection Strategy:
    1. Query docker_images table for all Dockerfiles
    2. Check USER instruction (root user detection)
    3. Scan ENV/ARG for hardcoded secrets
    4. Validate base image versions
    5. Optional: Scan base images for CVEs

    Database Tables Used:
    - docker_images: Dockerfile metadata (USER, ENV, ARG, base_image)

    Args:
        context: Rule execution context with database path

    Returns:
        List of findings for detected security issues

    Known Limitations:
    - Multi-stage builds: Only checks final USER instruction
    - ARG secrets: Detects but cannot prevent build-time exposure
    - CVE scanning: Requires network access (optional)
    """
    findings = []

    if not context.db_path:
        return findings

    patterns = DockerfilePatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check if docker_images table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='docker_images'
        """)

        if not cursor.fetchone():
            # No Dockerfiles in project - return empty
            return findings

        # Run security checks
        findings.extend(_check_root_user(cursor, patterns))
        findings.extend(_check_exposed_secrets(cursor, patterns))
        findings.extend(_check_vulnerable_images(cursor, patterns))

        # Optional: CVE scanning (requires network, skip in offline mode)
        # findings.extend(_check_base_image_cves(cursor))

    finally:
        conn.close()

    return findings


# ============================================================================
# SECURITY CHECKS
# ============================================================================

def _check_root_user(cursor, patterns: DockerfilePatterns) -> List[StandardFinding]:
    """Detect containers running as root user.

    CIS Docker Benchmark: Containers should never run as root.
    A container breakout would grant attacker root privileges on the host.

    Checks docker_images.env_vars['_DOCKER_USER'] field.
    """
    findings = []

    cursor.execute("SELECT file_path, env_vars FROM docker_images")

    for row in cursor.fetchall():
        file_path = row[0]
        env_vars_json = row[1]

        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
        except json.JSONDecodeError:
            continue

        # Check for _DOCKER_USER key (set by USER instruction in Dockerfile)
        docker_user = env_vars.get('_DOCKER_USER')

        # Missing USER instruction or explicitly set to root
        if docker_user is None or docker_user.lower() == 'root':
            severity = Severity.HIGH if docker_user is None else Severity.CRITICAL
            msg_suffix = 'not set' if docker_user is None else 'set to root'

            findings.append(StandardFinding(
                rule_name='dockerfile-root-user',
                message=f'Container runs as root user (USER instruction {msg_suffix})',
                file_path=file_path,
                line=1,
                severity=severity,
                category='deployment',
                snippet=f'USER {docker_user or "[not set]"}',
                cwe_id='CWE-250'  # Execution with Unnecessary Privileges
            ))

    return findings


def _check_exposed_secrets(cursor, patterns: DockerfilePatterns) -> List[StandardFinding]:
    """Detect hardcoded secrets in ENV and ARG instructions.

    ENV and ARG values are stored in image layers and can be inspected
    by anyone with access to the image. Secrets must use Docker secrets
    or external secret managers.

    Detection methods:
    1. Sensitive key names (PASSWORD, TOKEN, etc.)
    2. Known secret patterns (GitHub PAT, AWS keys, etc.)
    3. High Shannon entropy (random-looking strings)
    """
    findings = []

    cursor.execute("SELECT file_path, env_vars, build_args FROM docker_images")

    for row in cursor.fetchall():
        file_path = row[0]
        env_vars_json = row[1]
        build_args_json = row[2]

        try:
            env_vars = json.loads(env_vars_json) if env_vars_json else {}
            build_args = json.loads(build_args_json) if build_args_json else {}
        except json.JSONDecodeError:
            continue

        # Check ENV variables
        for key, value in env_vars.items():
            # Skip internal tracking keys
            if key.startswith('_DOCKER_'):
                continue

            if not value or not isinstance(value, str):
                continue

            key_upper = key.upper()

            # Check 1: Sensitive key names
            is_sensitive = any(kw in key_upper for kw in patterns.SENSITIVE_ENV_KEYWORDS)

            if is_sensitive:
                # Check for weak passwords
                if value.lower() in patterns.WEAK_PASSWORDS:
                    findings.append(StandardFinding(
                        rule_name='dockerfile-weak-password',
                        message=f'Weak password in ENV {key}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.CRITICAL,
                        category='deployment',
                        snippet=f'ENV {key}=***',
                        cwe_id='CWE-521'  # Weak Password Requirements
                    ))
                else:
                    findings.append(StandardFinding(
                        rule_name='dockerfile-hardcoded-secret',
                        message=f'Hardcoded secret in ENV instruction: {key}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category='deployment',
                        snippet=f'ENV {key}=***',
                        cwe_id='CWE-798'  # Use of Hard-coded Credentials
                    ))
                continue

            # Check 2: Known secret patterns
            for pattern in SECRET_VALUE_PATTERNS:
                if pattern.match(value):
                    findings.append(StandardFinding(
                        rule_name='dockerfile-secret-pattern',
                        message=f'Detected secret pattern in ENV {key}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.CRITICAL,
                        category='deployment',
                        snippet=f'ENV {key}=[REDACTED]',
                        cwe_id='CWE-798'
                    ))
                    break

            # Check 3: High entropy (potential secret)
            if _is_high_entropy(value):
                findings.append(StandardFinding(
                    rule_name='dockerfile-high-entropy',
                    message=f'High entropy value in ENV {key} - possible secret',
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,
                    category='deployment',
                    snippet=f'ENV {key}=[REDACTED]',
                    cwe_id='CWE-798'
                ))

        # Check ARG variables (build-time only, lower severity)
        for key, value in build_args.items():
            if not value or not isinstance(value, str):
                continue

            key_upper = key.upper()
            is_sensitive = any(kw in key_upper for kw in patterns.SENSITIVE_ENV_KEYWORDS)

            if is_sensitive:
                findings.append(StandardFinding(
                    rule_name='dockerfile-arg-secret',
                    message=f'Potential secret in ARG instruction: {key}',
                    file_path=file_path,
                    line=1,
                    severity=Severity.MEDIUM,  # Lower than ENV (build-time only)
                    category='deployment',
                    snippet=f'ARG {key}=***',
                    cwe_id='CWE-798'
                ))

    return findings


def _check_vulnerable_images(cursor, patterns: DockerfilePatterns) -> List[StandardFinding]:
    """Detect use of vulnerable or EOL base images.

    Checks for:
    1. Known vulnerable/deprecated versions
    2. Unpinned versions (:latest tag)
    3. Images without registry namespace (typosquatting risk)
    """
    findings = []

    cursor.execute("SELECT DISTINCT file_path, base_image FROM docker_images WHERE base_image IS NOT NULL")

    for row in cursor.fetchall():
        file_path = row[0]
        base_image = row[1]

        # Check for known vulnerable versions
        for vuln_pattern in patterns.VULNERABLE_BASE_IMAGES:
            if base_image.startswith(vuln_pattern):
                findings.append(StandardFinding(
                    rule_name='dockerfile-vulnerable-image',
                    message=f'Base image {vuln_pattern} is deprecated/EOL',
                    file_path=file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category='deployment',
                    snippet=f'FROM {base_image}',
                    cwe_id='CWE-937'  # Using Outdated Component
                ))
                break

        # Check for unpinned versions
        if ':latest' in base_image or (':' not in base_image and '@' not in base_image):
            findings.append(StandardFinding(
                rule_name='dockerfile-unpinned-version',
                message=f'Base image uses unpinned version (non-reproducible builds)',
                file_path=file_path,
                line=1,
                severity=Severity.MEDIUM,
                category='deployment',
                snippet=f'FROM {base_image}',
                cwe_id='CWE-494'  # Download of Code Without Integrity Check
            ))

        # Extract image name (without tag/digest)
        if '@' in base_image:
            image_name = base_image.split('@')[0]
        elif ':' in base_image:
            image_name = base_image.split(':')[0]
        else:
            image_name = base_image

        # Check for images without namespace (typosquatting risk)
        # Official images like 'alpine', 'ubuntu' are whitelisted
        official_images = {'alpine', 'ubuntu', 'debian', 'centos', 'fedora', 'busybox', 'scratch'}

        if '/' not in image_name and image_name not in official_images:
            findings.append(StandardFinding(
                rule_name='dockerfile-unofficial-image',
                message=f'Image {image_name} lacks registry namespace (typosquatting risk)',
                file_path=file_path,
                line=1,
                severity=Severity.LOW,
                category='deployment',
                snippet=f'FROM {base_image}',
                cwe_id='CWE-494'
            ))

    return findings


def _is_high_entropy(value: str, threshold: float = 4.0) -> bool:
    """Check if a string has high Shannon entropy (potential secret).

    Shannon entropy measures randomness. High entropy indicates
    random-looking strings that might be API keys, tokens, or secrets.

    Args:
        value: String to analyze
        threshold: Entropy threshold (default 4.0 bits per character)

    Returns:
        True if entropy exceeds threshold
    """
    # Skip short strings (not enough data)
    if len(value) < 10:
        return False

    # Skip strings with spaces (likely prose, not secrets)
    if ' ' in value:
        return False

    # Calculate character frequency
    char_freq = {}
    for char in value:
        char_freq[char] = char_freq.get(char, 0) + 1

    # Calculate Shannon entropy: H(X) = -Σ p(x) * log2(p(x))
    entropy = 0.0
    for count in char_freq.values():
        probability = count / len(value)
        if probability > 0:
            entropy -= probability * math.log2(probability)

    return entropy > threshold


# ============================================================================
# OPTIONAL: CVE SCANNING (Requires Network)
# ============================================================================
# Commented out by default - enable if needed
#
# def _check_base_image_cves(cursor) -> List[StandardFinding]:
#     """Scan base images for known CVEs using vulnerability scanner.
#
#     Requires:
#     - Network access
#     - vulnerability_scanner module
#     """
#     findings = []
#
#     # Get unique base images
#     cursor.execute("SELECT DISTINCT file_path, base_image FROM docker_images WHERE base_image IS NOT NULL")
#
#     dependencies = []
#     for row in cursor.fetchall():
#         file_path = row[0]
#         base_image = row[1]
#
#         # Parse image:tag format
#         if ':' in base_image:
#             name, version = base_image.rsplit(':', 1)
#         elif '@' in base_image:
#             name, version = base_image.split('@')
#         else:
#             name, version = base_image, 'latest'
#
#         dependencies.append({
#             'manager': 'docker',
#             'name': name,
#             'version': version,
#             'source_file': file_path
#         })
#
#     if not dependencies:
#         return findings
#
#     # Import vulnerability scanner (lazy import to avoid circular dependency)
#     try:
#         from theauditor.vulnerability_scanner import scan_dependencies
#         vuln_results = scan_dependencies(dependencies, offline=False)
#     except ImportError:
#         return findings
#
#     # Convert vulnerability findings to StandardFinding
#     for vuln in vuln_results:
#         severity_map = {
#             'critical': Severity.CRITICAL,
#             'high': Severity.HIGH,
#             'medium': Severity.MEDIUM,
#             'low': Severity.LOW,
#         }
#
#         findings.append(StandardFinding(
#             rule_name='dockerfile-base-image-cve',
#             message=f"Base image has CVE: {vuln.get('title', 'Unknown vulnerability')}",
#             file_path=vuln.get('source_file', 'Dockerfile'),
#             line=1,
#             severity=severity_map.get(vuln.get('severity', 'medium'), Severity.MEDIUM),
#             category='deployment',
#             snippet=f"FROM {vuln.get('package', 'unknown')}",
#             cwe_id='CWE-937'
#         ))
#
#     return findings
