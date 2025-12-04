"""Nginx Security Analyzer - Database-First Approach."""

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="nginx_security",
    category="deployment",
    target_extensions=[],
    exclude_patterns=["test/", "__tests__/", "node_modules/", ".pf/", ".auditor_venv/"])


@dataclass(frozen=True)
class NginxPatterns:
    """Configuration for Nginx security patterns."""

    CRITICAL_HEADERS = {
        "Strict-Transport-Security": "HSTS header for HTTPS enforcement",
        "X-Frame-Options": "Clickjacking protection",
        "X-Content-Type-Options": "MIME sniffing protection",
        "Content-Security-Policy": "XSS and injection protection",
        "X-XSS-Protection": "XSS protection for older browsers",
        "Referrer-Policy": "Control referrer information",
        "Permissions-Policy": "Control browser features",
    }

    SENSITIVE_PATHS = frozenset(
        [
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
        ]
    )

    DEPRECATED_PROTOCOLS = frozenset(
        ["SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1", "TLS1", "TLS1.0", "TLS1.1"]
    )

    WEAK_CIPHERS = frozenset(
        [
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
        ]
    )

    STRONG_PROTOCOLS = frozenset(["TLSv1.2", "TLSv1.3"])


def find_nginx_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Nginx security misconfigurations."""
    analyzer = NginxAnalyzer(context)
    return analyzer.analyze()


class NginxAnalyzer:
    """Main analyzer for Nginx configurations."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = NginxPatterns()
        self.findings: list[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        self.proxy_configs: list[NginxProxyConfig] = []
        self.rate_limits: list[NginxRateLimit] = []
        self.security_headers: dict[str, set[str]] = {}
        self.ssl_configs: list[NginxSSLConfig] = []
        self.location_blocks: list[NginxLocationBlock] = []
        self.server_tokens: dict[str, str] = {}

    def analyze(self) -> list[StandardFinding]:
        """Run complete Nginx analysis."""

        self._load_nginx_configs()

        self._check_proxy_rate_limiting()
        self._check_security_headers()
        self._check_exposed_paths()
        self._check_ssl_configurations()
        self._check_server_tokens()

        return self.findings

    def _load_nginx_configs(self) -> None:
        """Load and parse Nginx configurations from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            from theauditor.indexer.schema import build_query

            query = build_query(
                "nginx_configs",
                ["file_path", "block_type", "block_context", "directives", "level"],
                order_by="file_path, level",
            )
            cursor.execute(query)

            for row in cursor.fetchall():
                self._parse_config_block(row)

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _parse_config_block(self, row: tuple) -> None:
        """Parse a single Nginx configuration block."""
        file_path = row[0]
        block_type = row[1]
        block_context = row[2]
        directives_json = row[3]

        try:
            directives = json.loads(directives_json) if directives_json else {}
        except json.JSONDecodeError:
            directives = {}

        if "proxy_pass" in directives:
            self.proxy_configs.append(
                NginxProxyConfig(
                    file_path=file_path,
                    block_type=block_type,
                    context=block_context,
                    proxy_pass=directives["proxy_pass"],
                    has_rate_limit="limit_req" in directives,
                )
            )

        if "limit_req_zone" in directives:
            self.rate_limits.append(
                NginxRateLimit(
                    file_path=file_path,
                    context=block_context,
                    zone=directives["limit_req_zone"],
                    is_zone=True,
                )
            )

        if "limit_req" in directives:
            self.rate_limits.append(
                NginxRateLimit(
                    file_path=file_path,
                    context=block_context,
                    zone=directives["limit_req"],
                    is_zone=False,
                )
            )

        if "add_header" in directives:
            self._parse_headers(file_path, directives["add_header"])

        if "ssl_protocols" in directives or "ssl_ciphers" in directives:
            self.ssl_configs.append(
                NginxSSLConfig(
                    file_path=file_path,
                    context=block_context,
                    protocols=directives.get("ssl_protocols", ""),
                    ciphers=directives.get("ssl_ciphers", ""),
                )
            )

        if block_type == "location":
            self.location_blocks.append(
                NginxLocationBlock(
                    file_path=file_path, context=block_context, directives=directives
                )
            )

        if "server_tokens" in directives:
            self.server_tokens[file_path] = directives["server_tokens"]

    def _parse_headers(self, file_path: str, headers: Any) -> None:
        """Parse add_header directives."""
        if not isinstance(headers, list):
            headers = [headers]

        if file_path not in self.security_headers:
            self.security_headers[file_path] = set()

        for header in headers:
            match = re.match(r"(\S+)\s+", str(header))
            if match:
                header_name = match.group(1)
                self.security_headers[file_path].add(header_name)

    def _check_proxy_rate_limiting(self) -> None:
        """Check for proxy_pass without rate limiting."""
        for proxy in self.proxy_configs:
            if not proxy.has_rate_limit:
                has_external_limit = any(
                    rl.file_path == proxy.file_path
                    and rl.context == proxy.context
                    and not rl.is_zone
                    for rl in self.rate_limits
                )

                if not has_external_limit:
                    self.findings.append(
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

    def _check_security_headers(self) -> None:
        """Check for missing critical security headers."""
        processed_files = set()

        for file_path in set(self.security_headers.keys()) | {
            p.file_path for p in self.proxy_configs
        }:
            if file_path in processed_files:
                continue
            processed_files.add(file_path)

            file_headers = self.security_headers.get(file_path, set())

            for header_name, _description in self.patterns.CRITICAL_HEADERS.items():
                if header_name not in file_headers:
                    self.findings.append(
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

    def _check_exposed_paths(self) -> None:
        """Check for exposed sensitive paths."""
        for location in self.location_blocks:
            location_pattern = self._extract_location_pattern(location.context)
            location_lower = location_pattern.lower()

            for sensitive in self.patterns.SENSITIVE_PATHS:
                if sensitive in location_lower and not self._is_path_protected(location):
                    self.findings.append(
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

    def _check_ssl_configurations(self) -> None:
        """Check for SSL/TLS misconfigurations."""
        for ssl_config in self.ssl_configs:
            if ssl_config.protocols:
                self._check_ssl_protocols(ssl_config)

            if ssl_config.ciphers:
                self._check_ssl_ciphers(ssl_config)

    def _check_ssl_protocols(self, config: NginxSSLConfig) -> None:
        """Check for deprecated SSL/TLS protocols."""
        protocols_upper = config.protocols.upper()

        for deprecated in self.patterns.DEPRECATED_PROTOCOLS:
            if deprecated.upper() in protocols_upper:
                self.findings.append(
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

    def _check_ssl_ciphers(self, config: NginxSSLConfig) -> None:
        """Check for weak SSL ciphers."""
        ciphers_upper = config.ciphers.upper()

        for weak_cipher in self.patterns.WEAK_CIPHERS:
            if weak_cipher in ciphers_upper:
                self.findings.append(
                    StandardFinding(
                        rule_name="nginx-weak-cipher",
                        message=f"Using weak SSL cipher: {weak_cipher}",
                        file_path=config.file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=self._truncate_snippet(f"ssl_ciphers {config.ciphers}", 100),
                        cwe_id="CWE-327",
                    )
                )

    def _check_server_tokens(self) -> None:
        """Check for server token disclosure."""
        for file_path, value in self.server_tokens.items():
            if value.lower() != "off":
                self.findings.append(
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

    def _extract_location_pattern(self, context: str) -> str:
        """Extract location pattern from context string."""
        if ">" in context:
            return context.split(">")[-1].strip()
        return context

    def _is_path_protected(self, location: NginxLocationBlock) -> bool:
        """Check if location block properly denies access."""
        directives = location.directives

        if "deny" in directives:
            deny_value = str(directives["deny"]).lower()
            if "all" in deny_value:
                return True

        if "return" in directives:
            return_value = str(directives["return"])
            if "403" in return_value or "404" in return_value:
                return True

        return False

    def _truncate_snippet(self, text: str, max_length: int) -> str:
        """Truncate long snippets for readability."""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text


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
