"""Golden Standard Nginx Security Analyzer.

Detects security misconfigurations in Nginx configurations via database analysis.
Demonstrates database-aware rule pattern for TheAuditor.

MIGRATION STATUS: Golden Standard Reference [2024-12-13]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
import re
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class NginxPatterns:
    """Configuration for Nginx security patterns."""

    # Critical security headers
    CRITICAL_HEADERS = {
        'Strict-Transport-Security': 'HSTS header for HTTPS enforcement',
        'X-Frame-Options': 'Clickjacking protection',
        'X-Content-Type-Options': 'MIME sniffing protection',
        'Content-Security-Policy': 'XSS and injection protection',
        'X-XSS-Protection': 'XSS protection for older browsers',
        'Referrer-Policy': 'Control referrer information',
        'Permissions-Policy': 'Control browser features'
    }

    # Sensitive paths that should be protected
    SENSITIVE_PATHS = frozenset([
        '.git', '.svn', '.hg', '.bzr',              # Version control
        '.env', '.htaccess', '.htpasswd',           # Configuration files
        'wp-admin', 'phpmyadmin', 'admin',          # Admin interfaces
        '.DS_Store', 'Thumbs.db',                   # OS files
        'backup', '.backup', '.bak',                # Backup files
        '.idea', '.vscode', '.settings',            # IDE files
        'node_modules', 'vendor',                   # Dependencies
        '.dockerignore', 'Dockerfile',              # Docker files
        'deploy', 'deployment', '.deploy'           # Deployment files
    ])

    # Deprecated SSL/TLS protocols
    DEPRECATED_PROTOCOLS = frozenset([
        'SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.0', 'TLSv1.1', 'TLS1', 'TLS1.0', 'TLS1.1'
    ])

    # Weak SSL ciphers
    WEAK_CIPHERS = frozenset([
        'RC4', 'DES', 'MD5', 'NULL', 'EXPORT',
        'aNULL', 'eNULL', 'ADH', 'AECDH',
        'PSK', 'SRP', '3DES', 'CAMELLIA'
    ])

    # Acceptable SSL protocols
    STRONG_PROTOCOLS = frozenset(['TLSv1.2', 'TLSv1.3'])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Nginx security misconfigurations.

    Analyzes nginx_configs table for:
    - proxy_pass without rate limiting
    - Missing critical security headers
    - Exposed sensitive directories
    - SSL/TLS misconfigurations
    - Server token disclosure

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    analyzer = NginxAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# NGINX ANALYZER CLASS
# ============================================================================

class NginxAnalyzer:
    """Main analyzer for Nginx configurations."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = NginxPatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        # Track configurations across blocks
        self.proxy_configs: List[NginxProxyConfig] = []
        self.rate_limits: List[NginxRateLimit] = []
        self.security_headers: Dict[str, Set[str]] = {}
        self.ssl_configs: List[NginxSSLConfig] = []
        self.location_blocks: List[NginxLocationBlock] = []
        self.server_tokens: Dict[str, str] = {}

    def analyze(self) -> List[StandardFinding]:
        """Run complete Nginx analysis."""
        # Load and parse configurations
        self._load_nginx_configs()

        # Run security checks
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

            cursor.execute("""
                SELECT file_path, block_type, block_context, directives, level
                FROM nginx_configs
                ORDER BY file_path, level
            """)

            for row in cursor.fetchall():
                self._parse_config_block(row)

            conn.close()

        except (sqlite3.Error, Exception):
            # Continue without data if database unavailable
            pass

    def _parse_config_block(self, row: tuple) -> None:
        """Parse a single Nginx configuration block."""
        file_path = row[0]
        block_type = row[1]
        block_context = row[2]
        directives_json = row[3]
        level = row[4]

        # Parse directives
        try:
            directives = json.loads(directives_json) if directives_json else {}
        except json.JSONDecodeError:
            directives = {}

        # Track proxy_pass configurations
        if 'proxy_pass' in directives:
            self.proxy_configs.append(NginxProxyConfig(
                file_path=file_path,
                block_type=block_type,
                context=block_context,
                proxy_pass=directives['proxy_pass'],
                has_rate_limit='limit_req' in directives
            ))

        # Track rate limiting
        if 'limit_req_zone' in directives:
            self.rate_limits.append(NginxRateLimit(
                file_path=file_path,
                context=block_context,
                zone=directives['limit_req_zone'],
                is_zone=True
            ))

        if 'limit_req' in directives:
            self.rate_limits.append(NginxRateLimit(
                file_path=file_path,
                context=block_context,
                zone=directives['limit_req'],
                is_zone=False
            ))

        # Track security headers
        if 'add_header' in directives:
            self._parse_headers(file_path, directives['add_header'])

        # Track SSL configurations
        if 'ssl_protocols' in directives or 'ssl_ciphers' in directives:
            self.ssl_configs.append(NginxSSLConfig(
                file_path=file_path,
                context=block_context,
                protocols=directives.get('ssl_protocols', ''),
                ciphers=directives.get('ssl_ciphers', '')
            ))

        # Track location blocks
        if block_type == 'location':
            self.location_blocks.append(NginxLocationBlock(
                file_path=file_path,
                context=block_context,
                directives=directives
            ))

        # Track server tokens
        if 'server_tokens' in directives:
            self.server_tokens[file_path] = directives['server_tokens']

    def _parse_headers(self, file_path: str, headers: Any) -> None:
        """Parse add_header directives."""
        if not isinstance(headers, list):
            headers = [headers]

        if file_path not in self.security_headers:
            self.security_headers[file_path] = set()

        for header in headers:
            # Extract header name
            match = re.match(r'(\S+)\s+', str(header))
            if match:
                header_name = match.group(1)
                self.security_headers[file_path].add(header_name)

    def _check_proxy_rate_limiting(self) -> None:
        """Check for proxy_pass without rate limiting."""
        for proxy in self.proxy_configs:
            if not proxy.has_rate_limit:
                # Check if context has separate rate limiting
                has_external_limit = any(
                    rl.file_path == proxy.file_path and
                    rl.context == proxy.context and
                    not rl.is_zone
                    for rl in self.rate_limits
                )

                if not has_external_limit:
                    self.findings.append(StandardFinding(
                        rule_name='nginx-proxy-no-rate-limit',
                        message=f'proxy_pass without rate limiting in {proxy.context}',
                        file_path=proxy.file_path,
                        line=1,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=f'proxy_pass {proxy.proxy_pass}',
                        fix_suggestion='Add limit_req directive to protect against DoS attacks'
                    ))

    def _check_security_headers(self) -> None:
        """Check for missing critical security headers."""
        processed_files = set()

        for file_path in set(self.security_headers.keys()) | set(p.file_path for p in self.proxy_configs):
            if file_path in processed_files:
                continue
            processed_files.add(file_path)

            file_headers = self.security_headers.get(file_path, set())

            for header_name, description in self.patterns.CRITICAL_HEADERS.items():
                if header_name not in file_headers:
                    self.findings.append(StandardFinding(
                        rule_name='nginx-missing-header',
                        message=f'Missing security header: {header_name}',
                        file_path=file_path,
                        line=1,
                        severity=Severity.MEDIUM,
                        category='security',
                        snippet=f'Missing: add_header {header_name}',
                        fix_suggestion=f'Add "{header_name}" header for {description}'
                    ))

    def _check_exposed_paths(self) -> None:
        """Check for exposed sensitive paths."""
        for location in self.location_blocks:
            # Extract location pattern
            location_pattern = self._extract_location_pattern(location.context)
            location_lower = location_pattern.lower()

            # Check against sensitive patterns
            for sensitive in self.patterns.SENSITIVE_PATHS:
                if sensitive in location_lower:
                    if not self._is_path_protected(location):
                        self.findings.append(StandardFinding(
                            rule_name='nginx-exposed-path',
                            message=f'Potentially exposed sensitive path: {location_pattern}',
                            file_path=location.file_path,
                            line=1,
                            severity=Severity.HIGH,
                            category='security',
                            snippet=f'location {location_pattern}',
                            fix_suggestion='Add "deny all;" or "return 404;" to protect this path'
                        ))

    def _check_ssl_configurations(self) -> None:
        """Check for SSL/TLS misconfigurations."""
        for ssl_config in self.ssl_configs:
            # Check protocols
            if ssl_config.protocols:
                self._check_ssl_protocols(ssl_config)

            # Check ciphers
            if ssl_config.ciphers:
                self._check_ssl_ciphers(ssl_config)

    def _check_ssl_protocols(self, config: 'NginxSSLConfig') -> None:
        """Check for deprecated SSL/TLS protocols."""
        protocols_upper = config.protocols.upper()

        for deprecated in self.patterns.DEPRECATED_PROTOCOLS:
            if deprecated.upper() in protocols_upper:
                self.findings.append(StandardFinding(
                    rule_name='nginx-deprecated-protocol',
                    message=f'Using deprecated SSL/TLS protocol: {deprecated}',
                    file_path=config.file_path,
                    line=1,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'ssl_protocols {config.protocols}',
                    fix_suggestion='Use only TLSv1.2 and TLSv1.3: ssl_protocols TLSv1.2 TLSv1.3;'
                ))

    def _check_ssl_ciphers(self, config: 'NginxSSLConfig') -> None:
        """Check for weak SSL ciphers."""
        ciphers_upper = config.ciphers.upper()

        for weak_cipher in self.patterns.WEAK_CIPHERS:
            if weak_cipher in ciphers_upper:
                self.findings.append(StandardFinding(
                    rule_name='nginx-weak-cipher',
                    message=f'Using weak SSL cipher: {weak_cipher}',
                    file_path=config.file_path,
                    line=1,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=self._truncate_snippet(f'ssl_ciphers {config.ciphers}', 100),
                    fix_suggestion='Use strong cipher suites: ssl_ciphers HIGH:!aNULL:!MD5;'
                ))

    def _check_server_tokens(self) -> None:
        """Check for server token disclosure."""
        for file_path, value in self.server_tokens.items():
            if value.lower() != 'off':
                self.findings.append(StandardFinding(
                    rule_name='nginx-server-tokens',
                    message='Server version disclosure enabled',
                    file_path=file_path,
                    line=1,
                    severity=Severity.LOW,
                    category='security',
                    snippet=f'server_tokens {value}',
                    fix_suggestion='Set "server_tokens off;" to hide Nginx version'
                ))

    def _extract_location_pattern(self, context: str) -> str:
        """Extract location pattern from context string."""
        if '>' in context:
            return context.split('>')[-1].strip()
        return context

    def _is_path_protected(self, location: 'NginxLocationBlock') -> bool:
        """Check if location block properly denies access."""
        directives = location.directives

        # Check for deny directive
        if 'deny' in directives:
            deny_value = str(directives['deny']).lower()
            if 'all' in deny_value:
                return True

        # Check for return 403/404
        if 'return' in directives:
            return_value = str(directives['return'])
            if '403' in return_value or '404' in return_value:
                return True

        return False

    def _truncate_snippet(self, text: str, max_length: int) -> str:
        """Truncate long snippets for readability."""
        if len(text) > max_length:
            return text[:max_length] + '...'
        return text


# ============================================================================
# DATA MODELS
# ============================================================================

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
    is_zone: bool  # True for limit_req_zone, False for limit_req


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
    directives: Dict[str, Any]