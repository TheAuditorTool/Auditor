"""Nginx Security Analyzer - Database-First Approach.

Detects security misconfigurations in Nginx configurations:
- Missing rate limiting on proxies (CWE-770)
- Missing security headers (CWE-693)
- Exposed sensitive paths (CWE-552)
- Deprecated SSL/TLS protocols (CWE-327)
- Weak SSL ciphers (CWE-327)
- Server version disclosure (CWE-200)
"""

import json
import re
from dataclasses import dataclass
from typing import Any

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
    name="nginx_security",
    category="deployment",
    target_extensions=[],
    exclude_patterns=["test/", "__tests__/", "node_modules/", ".pf/", ".auditor_venv/"],
    execution_scope="database",
    primary_table="nginx_configs",
)


CRITICAL_HEADERS = {
    "Strict-Transport-Security": "HSTS header for HTTPS enforcement",
    "X-Frame-Options": "Clickjacking protection",
    "X-Content-Type-Options": "MIME sniffing protection",
    "Content-Security-Policy": "XSS and injection protection",
    "X-XSS-Protection": "XSS protection for older browsers",
    "Referrer-Policy": "Control referrer information",
    "Permissions-Policy": "Control browser features",
}

SENSITIVE_PATHS = frozenset([
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    ".env",
    ".htaccess",
    ".htpasswd",
    "wp-admin",
    "phpmyadmin",
    "admin",
    ".DS_Store",
    "Thumbs.db",
    "backup",
    ".backup",
    ".bak",
    ".idea",
    ".vscode",
    ".settings",
    "node_modules",
    "vendor",
    ".dockerignore",
    "Dockerfile",
    "deploy",
    "deployment",
    ".deploy",
])

DEPRECATED_PROTOCOLS = frozenset([
    "SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1", "TLS1", "TLS1.0", "TLS1.1"
])

WEAK_CIPHERS = frozenset([
    "RC4",
    "DES",
    "MD5",
    "NULL",
    "EXPORT",
    "aNULL",
    "eNULL",
    "ADH",
    "AECDH",
    "PSK",
    "SRP",
    "3DES",
    "CAMELLIA",
])


@dataclass
class NginxProxyConfig:
    """Represents a proxy_pass configuration."""
    file_path: str
    block_type: str
    context: str
    proxy_pass: str
    has_rate_limit: bool


@dataclass
class NginxRateLimit:
    """Represents a rate limiting configuration."""
    file_path: str
    context: str
    zone: str
    is_zone: bool


@dataclass
class NginxSSLConfig:
    """Represents SSL/TLS configuration."""
    file_path: str
    context: str
    protocols: str
    ciphers: str


@dataclass
class NginxLocationBlock:
    """Represents a location block configuration."""
    file_path: str
    context: str
    directives: dict[str, Any]


def find_nginx_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Nginx security misconfigurations."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Load all nginx config blocks
        configs = _load_nginx_configs(db)

        # Parse config blocks into structured data
        proxy_configs = []
        rate_limits = []
        security_headers = {}
        ssl_configs = []
        location_blocks = []
        server_tokens = {}

        for config in configs:
            _parse_config_block(
                config,
                proxy_configs,
                rate_limits,
                security_headers,
                ssl_configs,
                location_blocks,
                server_tokens,
            )

        # Run all security checks
        findings.extend(_check_proxy_rate_limiting(proxy_configs, rate_limits))
        findings.extend(_check_security_headers(security_headers, proxy_configs))
        findings.extend(_check_exposed_paths(location_blocks))
        findings.extend(_check_ssl_configurations(ssl_configs))
        findings.extend(_check_server_tokens(server_tokens))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _load_nginx_configs(db: RuleDB) -> list[dict]:
    """Load all nginx configuration blocks from database."""
    configs = []

    rows = db.query(
        Q("nginx_configs")
        .select("file_path", "block_type", "block_context", "directives", "level")
        .order_by("file_path, level")
    )

    for file_path, block_type, block_context, directives_str, level in rows:
        try:
            directives = json.loads(directives_str) if directives_str else {}
        except json.JSONDecodeError:
            directives = {}

        configs.append({
            "file_path": file_path,
            "block_type": block_type,
            "block_context": block_context,
            "directives": directives,
            "level": level,
        })

    return configs


def _parse_config_block(
    config: dict,
    proxy_configs: list[NginxProxyConfig],
    rate_limits: list[NginxRateLimit],
    security_headers: dict[str, set[str]],
    ssl_configs: list[NginxSSLConfig],
    location_blocks: list[NginxLocationBlock],
    server_tokens: dict[str, str],
) -> None:
    """Parse a single Nginx configuration block into structured data."""
    file_path = config["file_path"]
    block_type = config["block_type"]
    block_context = config["block_context"]
    directives = config["directives"]

    # Extract proxy configurations
    if "proxy_pass" in directives:
        proxy_configs.append(
            NginxProxyConfig(
                file_path=file_path,
                block_type=block_type,
                context=block_context,
                proxy_pass=directives["proxy_pass"],
                has_rate_limit="limit_req" in directives,
            )
        )

    # Extract rate limit zones
    if "limit_req_zone" in directives:
        rate_limits.append(
            NginxRateLimit(
                file_path=file_path,
                context=block_context,
                zone=directives["limit_req_zone"],
                is_zone=True,
            )
        )

    # Extract rate limit usage
    if "limit_req" in directives:
        rate_limits.append(
            NginxRateLimit(
                file_path=file_path,
                context=block_context,
                zone=directives["limit_req"],
                is_zone=False,
            )
        )

    # Extract security headers
    if "add_header" in directives:
        _parse_headers(file_path, directives["add_header"], security_headers)

    # Extract SSL configurations
    if "ssl_protocols" in directives or "ssl_ciphers" in directives:
        ssl_configs.append(
            NginxSSLConfig(
                file_path=file_path,
                context=block_context,
                protocols=directives.get("ssl_protocols", ""),
                ciphers=directives.get("ssl_ciphers", ""),
            )
        )

    # Extract location blocks
    if block_type == "location":
        location_blocks.append(
            NginxLocationBlock(
                file_path=file_path,
                context=block_context,
                directives=directives,
            )
        )

    # Extract server_tokens setting
    if "server_tokens" in directives:
        server_tokens[file_path] = directives["server_tokens"]


def _parse_headers(file_path: str, headers: Any, security_headers: dict[str, set[str]]) -> None:
    """Parse add_header directives."""
    if not isinstance(headers, list):
        headers = [headers]

    if file_path not in security_headers:
        security_headers[file_path] = set()

    for header in headers:
        match = re.match(r"(\S+)\s+", str(header))
        if match:
            header_name = match.group(1)
            security_headers[file_path].add(header_name)


def _check_proxy_rate_limiting(
    proxy_configs: list[NginxProxyConfig],
    rate_limits: list[NginxRateLimit],
) -> list[StandardFinding]:
    """Check for proxy_pass without rate limiting."""
    findings = []

    for proxy in proxy_configs:
        if not proxy.has_rate_limit:
            # Check if there's a rate limit defined for the same context
            has_external_limit = any(
                rl.file_path == proxy.file_path
                and rl.context == proxy.context
                and not rl.is_zone
                for rl in rate_limits
            )

            if not has_external_limit:
                findings.append(
                    StandardFinding(
                        rule_name="nginx-proxy-no-rate-limit",
                        message=f"proxy_pass without rate limiting in {proxy.context}",
                        file_path=proxy.file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"proxy_pass {proxy.proxy_pass}",
                        cwe_id="CWE-770",
                    )
                )

    return findings


def _check_security_headers(
    security_headers: dict[str, set[str]],
    proxy_configs: list[NginxProxyConfig],
) -> list[StandardFinding]:
    """Check for missing critical security headers."""
    findings = []
    processed_files = set()

    # Check all files that have headers or proxy configs
    all_files = set(security_headers.keys()) | {p.file_path for p in proxy_configs}

    for file_path in all_files:
        if file_path in processed_files:
            continue
        processed_files.add(file_path)

        file_headers = security_headers.get(file_path, set())

        for header_name in CRITICAL_HEADERS:
            if header_name not in file_headers:
                findings.append(
                    StandardFinding(
                        rule_name="nginx-missing-header",
                        message=f"Missing security header: {header_name}",
                        file_path=file_path,
                        line=1,
                        severity=Severity.MEDIUM,
                        category="security",
                        snippet=f"Missing: add_header {header_name}",
                        cwe_id="CWE-693",
                    )
                )

    return findings


def _check_exposed_paths(location_blocks: list[NginxLocationBlock]) -> list[StandardFinding]:
    """Check for exposed sensitive paths."""
    findings = []

    for location in location_blocks:
        location_pattern = _extract_location_pattern(location.context)
        location_lower = location_pattern.lower()

        for sensitive in SENSITIVE_PATHS:
            if sensitive in location_lower and not _is_path_protected(location):
                findings.append(
                    StandardFinding(
                        rule_name="nginx-exposed-path",
                        message=f"Potentially exposed sensitive path: {location_pattern}",
                        file_path=location.file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"location {location_pattern}",
                        cwe_id="CWE-552",
                    )
                )
                break  # One finding per location is enough

    return findings


def _check_ssl_configurations(ssl_configs: list[NginxSSLConfig]) -> list[StandardFinding]:
    """Check for SSL/TLS misconfigurations."""
    findings = []

    for ssl_config in ssl_configs:
        if ssl_config.protocols:
            findings.extend(_check_ssl_protocols(ssl_config))

        if ssl_config.ciphers:
            findings.extend(_check_ssl_ciphers(ssl_config))

    return findings


def _check_ssl_protocols(config: NginxSSLConfig) -> list[StandardFinding]:
    """Check for deprecated SSL/TLS protocols."""
    findings = []
    protocols_upper = config.protocols.upper()

    for deprecated in DEPRECATED_PROTOCOLS:
        if deprecated.upper() in protocols_upper:
            findings.append(
                StandardFinding(
                    rule_name="nginx-deprecated-protocol",
                    message=f"Using deprecated SSL/TLS protocol: {deprecated}",
                    file_path=config.file_path,
                    line=1,
                    severity=Severity.CRITICAL,
                    category="security",
                    snippet=f"ssl_protocols {config.protocols}",
                    cwe_id="CWE-327",
                )
            )

    return findings


def _check_ssl_ciphers(config: NginxSSLConfig) -> list[StandardFinding]:
    """Check for weak SSL ciphers."""
    findings = []
    ciphers_upper = config.ciphers.upper()

    for weak_cipher in WEAK_CIPHERS:
        if weak_cipher in ciphers_upper:
            snippet = f"ssl_ciphers {config.ciphers}"
            if len(snippet) > 100:
                snippet = snippet[:100] + "..."

            findings.append(
                StandardFinding(
                    rule_name="nginx-weak-cipher",
                    message=f"Using weak SSL cipher: {weak_cipher}",
                    file_path=config.file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category="security",
                    snippet=snippet,
                    cwe_id="CWE-327",
                )
            )

    return findings


def _check_server_tokens(server_tokens: dict[str, str]) -> list[StandardFinding]:
    """Check for server token disclosure."""
    findings = []

    for file_path, value in server_tokens.items():
        if value.lower() != "off":
            findings.append(
                StandardFinding(
                    rule_name="nginx-server-tokens",
                    message="Server version disclosure enabled",
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category="security",
                    snippet=f"server_tokens {value}",
                    cwe_id="CWE-200",
                )
            )

    return findings


def _extract_location_pattern(context: str) -> str:
    """Extract location pattern from context string."""
    if ">" in context:
        return context.split(">")[-1].strip()
    return context


def _is_path_protected(location: NginxLocationBlock) -> bool:
    """Check if location block properly denies access."""
    directives = location.directives

    # Check for explicit deny all
    if "deny" in directives:
        deny_value = str(directives["deny"]).lower()
        if "all" in deny_value:
            return True

    # Check for return 403/404
    if "return" in directives:
        return_value = str(directives["return"])
        if "403" in return_value or "404" in return_value:
            return True

    return False
